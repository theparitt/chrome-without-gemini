"""Profile discovery and reversible preference edits. Never terminate Chrome."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass


class AppError(Exception):
    """An actionable error that can be shown directly to the user."""


def run_command(args: list[str]) -> subprocess.CompletedProcess:
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=15, **options)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AppError(f"Could not run {args[0]}: {exc}") from exc


def chrome_running() -> bool:
    if sys.platform == "win32":
        result = run_command(["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"])
        if result.returncode:
            raise AppError(
                "Could not check whether Chrome is running. No preferences were changed."
            )
        return any(
            row and row[0].lower() == "chrome.exe" for row in csv.reader(io.StringIO(result.stdout))
        )
    result = run_command(["ps", "-A", "-o", "comm="])
    if result.returncode:
        raise AppError("Could not check whether Chrome is running. No preferences were changed.")
    names = {
        "chrome",
        "google-chrome",
        "google-chrome-stable",
        "Google Chrome",
        "Google Chrome Helper",
    }
    return any(Path(line.strip()).name in names for line in result.stdout.splitlines())


def require_chrome_closed() -> None:
    if chrome_running():
        raise AppError(
            "Quit Chrome completely, including its background processes, then try again. "
            "Your tabs will not be closed by this app."
        )


def default_chrome_root(platform: str = sys.platform, home: Path | None = None) -> Path:
    home = home or Path.home()
    if platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "Google/Chrome/User Data"
        )
    if platform == "darwin":
        return home / "Library/Application Support/Google/Chrome"
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "google-chrome"


def default_state_root() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "ChromeWithoutGemini"
    if sys.platform == "darwin":
        return home / "Library/Application Support/Chrome Without Gemini"
    return Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "chrome-without-gemini"


def read_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AppError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise AppError(f"Expected a JSON object in {path}.")
    return result


def atomic_write(path: Path, data: bytes) -> None:
    """Replace a file in its own directory, retaining existing access bits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise AppError(f"Refusing to replace a symbolic link: {path}")
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    handle, temp_name = tempfile.mkstemp(prefix=".cwg-", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_json(path: Path, data: dict) -> None:
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


class Journal:
    """Store only original values touched by this tool, never full Chrome profiles."""

    def __init__(self, root: Path | None = None):
        self.root = root or default_state_root()
        self.path = self.root / "changes.json"

    def read(self) -> dict:
        if not self.path.exists():
            return {"schema": 1, "toolbar": {}, "disable": None}
        data = read_json(self.path)
        if data.get("schema") != 1 or not isinstance(data.get("toolbar"), dict):
            raise AppError("Unrecognized backup format. Keep changes.json and update the app.")
        return data

    def write(self, data: dict) -> None:
        write_json(self.path, data)

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / "operation.lock"
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise AppError(
                f"Another operation is active. If the app previously crashed, close all "
                f"copies and remove the empty lock folder: {lock}"
            ) from exc
        try:
            yield
        finally:
            lock.rmdir()


@dataclass(frozen=True)
class Profile:
    path: Path
    name: str
    pinned: bool | None


def discover_profiles(root: Path) -> list[Profile]:
    if not root.is_dir():
        return []
    profiles = []
    for child in sorted(root.iterdir()):
        if child.name != "Default" and not child.name.startswith("Profile "):
            continue
        path = child / "Preferences"
        if not path.is_file() or child.is_symlink() or path.is_symlink():
            continue
        prefs = read_json(path)
        glic = prefs.get("glic", {})
        if not isinstance(glic, dict):
            raise AppError(f"Unrecognized Gemini preferences in {path}.")
        # Account display names are unnecessary for choosing a profile and can leak
        # into screenshots. Use Chrome's generic folder labels instead.
        name = "Default profile" if child.name == "Default" else child.name
        profiles.append(Profile(path.resolve(), str(name), glic.get("pinned_to_tabstrip")))
    return profiles


def toolbar_value(prefs: dict) -> dict:
    glic = prefs.get("glic", {})
    if not isinstance(glic, dict):
        raise AppError("Chrome's glic preferences have an unexpected format.")
    return {
        "parent_present": "glic" in prefs,
        "present": "pinned_to_tabstrip" in glic,
        "value": glic.get("pinned_to_tabstrip"),
    }


class Toolbar:
    def __init__(self, journal: Journal):
        self.journal = journal

    def hide(self, profiles: list[Profile]) -> str:
        if not profiles:
            raise AppError("Select at least one Chrome profile.")
        require_chrome_closed()
        with self.journal.locked():
            state = self.journal.read()
            prepared = []
            for profile in profiles:
                path = profile.path
                raw = path.read_bytes()
                prefs = read_json(path)
                before = toolbar_value(prefs)
                key = str(path)
                if key in state["toolbar"] and before["value"] is not False:
                    raise AppError(
                        f"{profile.name}: this setting changed since the last operation. "
                        "Undo or review it before applying again."
                    )
                if key not in state["toolbar"]:
                    state["toolbar"][key] = before
                prefs.setdefault("glic", {})["pinned_to_tabstrip"] = False
                prepared.append((path, raw, prefs))
            # Save recovery information before the first mutation.
            self.journal.write(state)
            self._commit(prepared)
        return f"Button hidden in {len(profiles)} profile(s). You can now reopen Chrome."

    def restore(self) -> str:
        require_chrome_closed()
        with self.journal.locked():
            state = self.journal.read()
            if not state["toolbar"]:
                return "No toolbar changes to undo."
            prepared = []
            for key, before in state["toolbar"].items():
                path = Path(key)
                raw = path.read_bytes()
                prefs = read_json(path)
                current = toolbar_value(prefs)
                # Prepared but unapplied writes are also safe to undo.
                if current != before and current["value"] is not False:
                    raise AppError(
                        f"{path.parent.name}: the toolbar setting changed after this app "
                        "ran. Undo stopped to preserve that newer choice."
                    )
                if before["present"]:
                    prefs.setdefault("glic", {})["pinned_to_tabstrip"] = before["value"]
                elif "glic" in prefs:
                    prefs["glic"].pop("pinned_to_tabstrip", None)
                    if not before["parent_present"] and not prefs["glic"]:
                        del prefs["glic"]
                prepared.append((path, raw, prefs))
            self._commit(prepared)
            count = len(prepared)
            state["toolbar"] = {}
            self.journal.write(state)
        return f"Restored the original toolbar setting in {count} profile(s)."

    @staticmethod
    def _commit(prepared: list[tuple[Path, bytes, dict]]) -> None:
        completed = []
        try:
            for path, raw, prefs in prepared:
                require_chrome_closed()
                if path.read_bytes() != raw:
                    raise AppError(
                        f"{path} changed during this operation. Try again with Chrome closed."
                    )
                write_json(path, prefs)
                completed.append((path, raw, prefs))
        except Exception:
            # Roll back only if no other writer has changed the file in the meantime.
            for path, raw, written in reversed(completed):
                if read_json(path) == written:
                    atomic_write(path, raw)
            raise
