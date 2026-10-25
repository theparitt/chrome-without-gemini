"""Selectable Gemini and Google Lens controls; both are selected by default."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import shutil
import sys

from .core import AppError, Journal, atomic_write
from .platforms import WindowsPolicy, desktop_quote, linux_launcher_path, mac_profile

DEFAULT_FEATURES = ("gemini", "lens")
POLICIES = {"gemini": "GeminiSettings", "lens": "SearchContentSharingSettings"}
SWITCHES = {"gemini": ("Glic",), "lens": ("LensOverlay", "LensStandalone")}


def select_features(features=DEFAULT_FEATURES) -> tuple[str, ...]:
    selected = set(features)
    if not selected or not selected <= set(DEFAULT_FEATURES):
        raise AppError("Select Gemini, Google Lens, or both.")
    return tuple(feature for feature in DEFAULT_FEATURES if feature in selected)


def feature_label(features) -> str:
    return " + ".join("Gemini" if feature == "gemini" else "Google Lens" for feature in features)


def launcher_content(binary: str, features) -> bytes:
    flags = ",".join(flag for feature in select_features(features) for flag in SWITCHES[feature])
    return (
        "[Desktop Entry]\nVersion=1.0\nType=Application\nName=Chrome (Without Gemini)\n"
        f"Comment=Start Chrome with {feature_label(features)} disabled\n"
        f"Exec={desktop_quote(binary)} --disable-features={flags} %U\n"
        "Terminal=false\nIcon=google-chrome\nCategories=Network;WebBrowser;\n"
        "StartupWMClass=Google-chrome\n"
    ).encode("utf-8")


class ChromeControl:
    def __init__(
        self,
        journal: Journal,
        platform: str = sys.platform,
        policies=None,
        launcher_path: Path | None = None,
        binary: str | None = None,
    ):
        self.journal = journal
        self.platform = platform
        self.policies = policies if policies is not None else {}
        self.launcher_path = launcher_path or linux_launcher_path()
        self.binary = binary

    def _policy(self, name):
        if name not in self.policies:
            self.policies[name] = WindowsPolicy(name=name)
        return self.policies[name]

    @staticmethod
    def _migrate_windows(state):
        records = state.setdefault("policy_changes", {})
        legacy = state.get("disable")
        if legacy:
            if legacy.get("platform") != "win32":
                raise AppError("The recovery file belongs to another operating system.")
            records.setdefault(
                "GeminiSettings", {"before": legacy["before"], "applied": legacy["applied"]}
            )
            state["disable"] = None
        state["schema"] = 2
        return records

    def _windows(self, selected, restore=False):
        with self.journal.locked():
            state = self.journal.read()
            records = self._migrate_windows(state)
            prepared = []
            for feature in selected:
                name = POLICIES[feature]
                policy = self._policy(name)
                current = policy.read()
                record = records.get(name)
                if record and current not in (record["before"], record["applied"]):
                    raise AppError(
                        f"{name} changed outside this app. Review chrome://policy "
                        "before continuing; no selected policies were changed."
                    )
                if restore:
                    if not record:
                        continue
                    desired = record["before"]
                else:
                    desired = policy.disabled_snapshot()
                    if not record:
                        records[name] = {"before": current, "applied": desired}
                prepared.append((name, policy, current, desired))
            # A prepared operation can be recovered even if a process stops mid-write.
            self.journal.write(state)
            completed = []
            try:
                for name, policy, current, desired in prepared:
                    if policy.read() != current:
                        raise AppError(f"{name} changed during this operation. Try again.")
                    policy.write(desired)
                    completed.append((name, policy, current, desired))
                    if policy.read() != desired:
                        raise AppError(
                            f"Could not verify {name}; recovery information was retained."
                        )
            except Exception as exc:
                failed_rollback = []
                for name, policy, current, desired in reversed(completed):
                    try:
                        if policy.read() == desired:
                            policy.write(current)
                            if policy.read() != current:
                                failed_rollback.append(name)
                        elif policy.read() != current:
                            failed_rollback.append(name)
                    except Exception:
                        failed_rollback.append(name)
                if failed_rollback:
                    raise AppError(
                        "The operation failed and some settings need recovery: "
                        + ", ".join(failed_rollback)
                        + ". Keep changes.json and use "
                        "Undo after resolving the permissions or conflict."
                    ) from exc
                raise
            if restore:
                for name, _, _, _ in prepared:
                    records.pop(name, None)
                self.journal.write(state)
        if restore:
            return f"Restored original settings for {feature_label(selected)}. Restart Chrome."
        settings = ", ".join(f"{POLICIES[feature]}=1" for feature in selected)
        return (
            f"Saved {settings}. Restart Chrome and verify these values with status OK at "
            "chrome://policy. A local policy can add 'Managed by your organization'. "
            "Lens policy also disables Chrome's AI Mode page/file-sharing entry points."
            if "lens" in selected
            else f"Saved {settings}. Restart Chrome and verify it at chrome://policy."
        )

    def _linux(self, selected, restore=False):
        path = self.launcher_path
        with self.journal.locked():
            state = self.journal.read()
            record = state.get("disable")
            if record and record.get("platform") != self.platform:
                raise AppError("The recovery file belongs to another operating system.")
            if path.is_symlink():
                raise AppError("The launcher is a symbolic link; it will not be changed.")
            current = path.read_bytes() if path.exists() else None
            if record:
                if str(path) != record["path"]:
                    raise AppError("The launcher location changed. Restore the original location.")
                allowed = [base64.b64decode(record["applied"])]
                if "pending_before" in record:
                    prior = record["pending_before"]
                    allowed.append(base64.b64decode(prior) if prior is not None else None)
                if current not in allowed:
                    raise AppError(
                        "The launcher changed outside this app. Your edits were preserved."
                    )
                active = set(record.get("features", ["gemini"]))
            else:
                if restore:
                    return "No launcher changes to undo."
                if current is not None:
                    raise AppError(
                        "A launcher already exists at this path and will not be replaced."
                    )
                active = set()
            active = active - set(selected) if restore else active | set(selected)
            if not active:
                if path.exists():
                    path.unlink()
                state["disable"] = None
                state["schema"] = 2
                self.journal.write(state)
                return "Removed this app's launcher. Quit Chrome and use your normal launcher."
            features = select_features(active)
            binary = (
                (record or {}).get("binary")
                or self.binary
                or shutil.which("google-chrome-stable")
                or shutil.which("google-chrome")
            )
            if not binary:
                raise AppError(
                    "Google Chrome stable was not found. Flatpak, Snap, and Chromium "
                    "are not supported by this launcher."
                )
            content = launcher_content(binary, features)
            state["schema"] = 2
            state["disable"] = {
                "platform": self.platform,
                "path": str(path),
                "binary": binary,
                "features": list(features),
                "applied": base64.b64encode(content).decode("ascii"),
                "pending_before": base64.b64encode(current).decode("ascii")
                if current is not None
                else None,
            }
            self.journal.write(state)
            atomic_write(path, content)
            os.chmod(path, 0o644)
            state["disable"].pop("pending_before")
            self.journal.write(state)
        flags = ",".join(flag for feature in features for flag in SWITCHES[feature])
        return (
            f"Launcher configured for {feature_label(features)}. Quit all Chrome processes, "
            "then open 'Chrome (Without Gemini)' from the application menu. Verify "
            f"--disable-features={flags} at chrome://version. Only starts through this "
            "launcher are affected. This fallback is experimental; ordinary image search "
            "may remain. Creating the launcher does not change a running session."
        )

    def disable(self, features=DEFAULT_FEATURES):
        selected = select_features(features)
        if self.platform == "win32":
            return self._windows(selected)
        if self.platform == "darwin":
            raise AppError(
                "Export the selected macOS policies, then install the profile in "
                "System Settings. Export alone does not apply them."
            )
        return self._linux(selected)

    def restore(self, features=DEFAULT_FEATURES):
        selected = select_features(features)
        if self.platform == "win32":
            return self._windows(selected, restore=True)
        if self.platform == "darwin":
            return (
                "Remove the installed 'Chrome Without Gemini' profile in System Settings > "
                "General > Device Management, then restart Chrome. To retain one feature's "
                "block, remove the combined profile and install a freshly exported profile "
                "with only that feature selected. Deleting the file does not uninstall it."
            )
        return self._linux(selected, restore=True)

    def export_mac(self, destination: Path, features=DEFAULT_FEATURES):
        selected = select_features(features)
        if destination.exists():
            raise AppError("Choose a new filename; existing profiles are not overwritten.")
        atomic_write(destination, mac_profile(selected))
        settings = ", ".join(f"{POLICIES[feature]}=1" for feature in selected)
        return (
            f"Exported profile with {settings}. Open the file and install 'Chrome Without "
            "Gemini' in System Settings > General > Device Management. Replace/remove an "
            "older combined profile when changing selections. Restart Chrome and verify "
            "the selected policies at chrome://policy. Export alone does not apply them."
        )

    def status(self):
        if self.platform == "win32":
            parts = []
            for feature in DEFAULT_FEATURES:
                policy = self._policy(POLICIES[feature])
                disabled = policy.read() == policy.disabled_snapshot()
                parts.append(
                    f"{feature_label([feature])}: "
                    + ("local policy disabled" if disabled else "not blocked here")
                )
            return "; ".join(parts) + ". Restart / verify at chrome://policy."
        if self.platform == "darwin":
            return "macOS: verify selected Gemini / Lens policies at chrome://policy."
        state = self.journal.read()
        record = state.get("disable")
        if not record:
            return "Linux AI-off launcher: not configured by this app."
        return (
            "Linux launcher selection: "
            + feature_label(record.get("features", ["gemini"]))
            + ". Use it after fully quitting Chrome."
        )
