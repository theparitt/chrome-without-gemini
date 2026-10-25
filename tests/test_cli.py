from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chrome_without_gemini import __version__
from chrome_without_gemini.cli import main


class CliTests(unittest.TestCase):
    def test_version_without_reading_chrome(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["--version"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn(__version__, output.getvalue())

    def test_help_lists_available_actions(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("restore-button", output.getvalue())
        self.assertIn("export-macos-policy", output.getvalue())

    def test_import_does_not_require_tk(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import chrome_without_gemini.cli; assert 'tkinter' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_export_isolated_and_does_not_create_state(self):
        root = Path(__file__).resolve().parents[1] / "build" / "test-tmp"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            destination = Path(directory) / "profile.mobileconfig"
            state = Path(directory) / "state"
            with redirect_stdout(io.StringIO()):
                result = main(["--state-root", str(state), "export-macos-policy", str(destination)])
            self.assertEqual(result, 0)
            self.assertEqual(
                plistlib.loads(destination.read_bytes())["PayloadContent"][0]["GeminiSettings"], 1
            )
            self.assertFalse(state.exists())

    def test_failure_has_nonzero_exit_and_clear_stderr(self):
        with patch("chrome_without_gemini.cli.ChromeControl") as control:
            control.return_value.disable.side_effect = PermissionError("Access denied")
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(["disable"]), 1)
            self.assertIn("Access denied", error.getvalue())

    def test_disable_defaults_to_both(self):
        with (
            patch("chrome_without_gemini.cli.ChromeControl") as control,
            redirect_stdout(io.StringIO()),
        ):
            control.return_value.disable.return_value = "saved"
            self.assertEqual(main(["disable"]), 0)
            control.return_value.disable.assert_called_once_with(("gemini", "lens"))

    def test_lens_only_and_restore_selectors(self):
        with (
            patch("chrome_without_gemini.cli.ChromeControl") as control,
            redirect_stdout(io.StringIO()),
        ):
            control.return_value.disable.return_value = "saved"
            control.return_value.restore.return_value = "restored"
            self.assertEqual(main(["disable", "--only", "lens"]), 0)
            control.return_value.disable.assert_called_once_with(("lens",))
            self.assertEqual(main(["restore", "--only", "gemini"]), 0)
            control.return_value.restore.assert_called_once_with(("gemini",))


if __name__ == "__main__":
    unittest.main()
