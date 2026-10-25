"""Test the packaged CLI without reading or changing a real Chrome installation."""

from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chrome_without_gemini import __version__  # noqa: E402


def main():
    suffix = ".exe" if sys.platform == "win32" else ""
    binary = ROOT / "dist" / ("ChromeWithoutGeminiCLI" + suffix)
    version = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, check=True, timeout=60
    )
    assert __version__ in version.stdout, version.stdout
    help_result = subprocess.run(
        [str(binary), "--help"], capture_output=True, text=True, check=True, timeout=60
    )
    assert "hide-button" in help_result.stdout, help_result.stdout
    assert "restore-gemini" in help_result.stdout, help_result.stdout
    fixture_root = ROOT / "build" / "cli-fixtures"
    fixture_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
        profile = Path(directory) / "test.mobileconfig"
        subprocess.run(
            [
                str(binary),
                "--state-root",
                str(Path(directory) / "state"),
                "export-macos-policy",
                str(profile),
            ],
            check=True,
            timeout=60,
            capture_output=True,
            text=True,
        )
        data = plistlib.loads(profile.read_bytes())
        assert data["PayloadContent"][0]["GeminiSettings"] == 1
        assert data["PayloadRemovalDisallowed"] is False
        assert not (Path(directory) / "state").exists()
    print("Packaged CLI version, help, and isolated profile export passed.")


if __name__ == "__main__":
    main()
