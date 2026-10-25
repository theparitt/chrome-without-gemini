"""Platform-specific Gemini control. No downloads, services, or scheduled tasks."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import plistlib
import shutil
import sys
import uuid

from .core import AppError, Journal, atomic_write

POLICY_KEY = r"Software\Policies\Google\Chrome"
PROFILE_ID = "org.chromewithoutgemini.chrome-policy"


class WindowsPolicy:
    """Change one current-user registry value, keeping its original type and value."""

    def __init__(self, registry=None):
        if registry is None:
            import winreg

            registry = winreg
        self.reg = registry

    def read(self) -> dict:
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, POLICY_KEY) as key:
                value, kind = self.reg.QueryValueEx(key, "GeminiSettings")
                if isinstance(value, bytes):
                    value = {"base64": base64.b64encode(value).decode("ascii")}
                return {"present": True, "value": value, "kind": kind}
        except FileNotFoundError:
            return {"present": False}

    def write(self, snapshot: dict) -> None:
        if snapshot["present"]:
            with self.reg.CreateKeyEx(
                self.reg.HKEY_CURRENT_USER, POLICY_KEY, 0, self.reg.KEY_SET_VALUE
            ) as key:
                value = snapshot["value"]
                if isinstance(value, dict) and "base64" in value:
                    value = base64.b64decode(value["base64"])
                self.reg.SetValueEx(key, "GeminiSettings", 0, snapshot["kind"], value)
        else:
            try:
                with self.reg.OpenKey(
                    self.reg.HKEY_CURRENT_USER, POLICY_KEY, 0, self.reg.KEY_SET_VALUE
                ) as key:
                    self.reg.DeleteValue(key, "GeminiSettings")
            except FileNotFoundError:
                pass

    def disabled_snapshot(self) -> dict:
        return {"present": True, "value": 1, "kind": self.reg.REG_DWORD}


def mac_profile() -> bytes:
    """Generate an explicit, removable configuration profile containing ONE policy."""
    data = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": PROFILE_ID,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": "Chrome Without Gemini",
        "PayloadDescription": "Disables Gemini integration in Google Chrome. "
        "Remove this profile in System Settings to undo.",
        "PayloadRemovalDisallowed": False,
        "PayloadScope": "User",
        "PayloadContent": [
            {
                "PayloadType": "com.google.Chrome",
                "PayloadVersion": 1,
                "PayloadIdentifier": PROFILE_ID + ".settings",
                "PayloadUUID": str(uuid.uuid4()).upper(),
                "PayloadDisplayName": "Disable Gemini in Chrome",
                "GeminiSettings": 1,
            }
        ],
    }
    return plistlib.dumps(data, sort_keys=False)


def desktop_quote(value: str) -> str:
    """Quote one Desktop Entry Exec argument, including the desktop-file escape layer."""
    if any(c in value for c in "\r\n\x00"):
        raise AppError("The Chrome executable path contains an invalid character.")
    escaped = ""
    for char in value:
        if char == "%":
            escaped += "%%"
        elif char == "\\":
            escaped += "\\\\\\\\"
        elif char in '"`$':
            escaped += "\\\\" + char
        else:
            escaped += char
    return '"' + escaped + '"'


def linux_launcher(binary: str) -> bytes:
    # A separate launcher preserves the user's existing Chrome/default-browser configuration.
    return (
        "[Desktop Entry]\nVersion=1.0\nType=Application\nName=Chrome (Without Gemini)\n"
        "Comment=Start Google Chrome with Gemini disabled\n"
        f"Exec={desktop_quote(binary)} --disable-features=Glic %U\n"
        "Terminal=false\nIcon=google-chrome\nCategories=Network;WebBrowser;\n"
        "StartupWMClass=Google-chrome\n"
    ).encode("utf-8")


def linux_launcher_path() -> Path:
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "applications/chrome-without-gemini.desktop"
    )


class GeminiControl:
    def __init__(
        self,
        journal: Journal,
        platform: str = sys.platform,
        policy=None,
        launcher_path: Path | None = None,
        binary: str | None = None,
    ):
        self.journal = journal
        self.platform = platform
        self.policy = policy
        self.launcher_path = launcher_path
        self.binary = binary

    def _policy(self):
        if self.policy is None:
            self.policy = WindowsPolicy()
        return self.policy

    def disable(self) -> str:
        if self.platform == "darwin":
            raise AppError(
                "On macOS, export the policy profile and install it in System Settings. "
                "Export alone does not disable Gemini."
            )
        with self.journal.locked():
            state = self.journal.read()
            previous = state["disable"]
            if previous and previous["platform"] != self.platform:
                raise AppError("The backup belongs to another operating system.")
            if self.platform == "win32":
                policy = self._policy()
                current = policy.read()
                applied = policy.disabled_snapshot()
                if previous and current not in (previous["before"], previous["applied"]):
                    raise AppError(
                        "GeminiSettings changed outside this app. Review chrome://policy first."
                    )
                if not previous:
                    state["disable"] = {
                        "platform": self.platform,
                        "before": current,
                        "applied": applied,
                    }
                    self.journal.write(state)
                policy.write(applied)
                if policy.read() != applied:
                    raise AppError("Windows did not save the policy. No success has been recorded.")
                return (
                    "GeminiSettings=1 saved for your Windows account. Restart Chrome, then check "
                    "chrome://policy for GeminiSettings = 1 with status OK. "
                    "Chrome may show 'Managed by your organization' for this local policy."
                )
            path = self.launcher_path or linux_launcher_path()
            binary = (
                self.binary or shutil.which("google-chrome-stable") or shutil.which("google-chrome")
            )
            if not binary:
                raise AppError(
                    "Google Chrome was not found. Install Google Chrome stable first. "
                    "Flatpak, Snap, and Chromium are not supported by the launcher."
                )
            if path.is_symlink():
                raise AppError("The launcher is a symbolic link; it will not be replaced.")
            content = linux_launcher(binary)
            if previous:
                if str(path) != previous["path"]:
                    raise AppError(
                        "The launcher location changed. Undo the previous launcher first."
                    )
                expected = base64.b64decode(previous["applied"])
                if not path.exists() or path.read_bytes() != expected:
                    raise AppError(
                        "The launcher was changed outside this app. It will not be overwritten."
                    )
                # Reapplying must not change the bytes recorded for Undo.
                content = expected
            else:
                if path.exists():
                    raise AppError(f"A file already exists at {path}. Rename it before continuing.")
                state["disable"] = {
                    "platform": self.platform,
                    "path": str(path),
                    "applied": base64.b64encode(content).decode("ascii"),
                }
                self.journal.write(state)
            atomic_write(path, content)
            os.chmod(path, 0o644)
            return (
                "Added 'Chrome (Without Gemini)' to your application menu. Quit every Chrome "
                "process before opening that launcher. Gemini is disabled only when launched "
                "this way; other launchers and already-running sessions are unaffected. "
                "Verify --disable-features=Glic at chrome://version. This fallback may change "
                "with future Chrome releases."
            )

    def restore(self) -> str:
        if self.platform == "darwin":
            return (
                "To undo on macOS, remove the 'Chrome Without Gemini' profile in System Settings "
                "> General > Device Management, then restart Chrome. Deleting the exported "
                "file does not remove an installed profile."
            )
        with self.journal.locked():
            state = self.journal.read()
            previous = state["disable"]
            if not previous:
                return "No Gemini changes to undo."
            if previous["platform"] != self.platform:
                raise AppError("The backup belongs to another operating system.")
            if self.platform == "win32":
                policy = self._policy()
                if policy.read() not in (previous["before"], previous["applied"]):
                    raise AppError(
                        "GeminiSettings changed after this app ran. Restore stopped to "
                        "preserve that newer setting."
                    )
                policy.write(previous["before"])
                if policy.read() != previous["before"]:
                    raise AppError("Could not verify the restored policy. The backup was retained.")
            else:
                path = Path(previous["path"])
                if path.is_symlink():
                    raise AppError("The launcher is now a symbolic link. It will not be removed.")
                if path.exists():
                    if path.read_bytes() != base64.b64decode(previous["applied"]):
                        raise AppError(
                            "The launcher has changed. Restore stopped to preserve your edits."
                        )
                    path.unlink()
            state["disable"] = None
            self.journal.write(state)
        return "Restored the original Gemini policy or removed this app's launcher. Restart Chrome."

    def export_mac(self, destination: Path) -> str:
        if destination.exists():
            raise AppError("Choose a new filename; existing profiles are not overwritten.")
        atomic_write(destination, mac_profile())
        return (
            f"Exported {destination}. Open the file, then install 'Chrome Without Gemini' in "
            "System Settings > General > Device Management. It contains only GeminiSettings=1. "
            "Restart Chrome and verify GeminiSettings = 1, status OK at chrome://policy. "
            "Exporting the file alone does not apply it."
        )

    def status(self) -> str:
        if self.platform == "win32":
            current = self._policy().read()
            return (
                "Local Gemini policy: disabled (restart / verify in Chrome)"
                if current == self._policy().disabled_snapshot()
                else "Local Gemini policy: not disabled by this setting"
            )
        if self.platform == "darwin":
            return "macOS: verify installation and effective policy at chrome://policy"
        path = self.launcher_path or linux_launcher_path()
        return (
            "Linux AI-off launcher: installed; use it after fully quitting Chrome"
            if path.exists()
            else "Linux AI-off launcher: not installed"
        )
