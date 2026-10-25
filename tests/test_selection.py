import base64
import copy
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from chrome_without_gemini.controls import ChromeControl, DEFAULT_FEATURES, launcher_content
from chrome_without_gemini.core import AppError, Journal
from chrome_without_gemini.platforms import mac_profile, linux_launcher


class FakePolicy:
    def __init__(self):
        self.value = {"present": False}
        self.fail = False

    def read(self):
        return copy.deepcopy(self.value)

    def write(self, value):
        if self.fail:
            raise PermissionError("denied")
        self.value = copy.deepcopy(value)

    def disabled_snapshot(self):
        return {"present": True, "value": 1, "kind": 4}


class SelectionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "build" / "test-tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = Journal(self.root / "state")
        self.policies = {
            name: FakePolicy() for name in ("GeminiSettings", "SearchContentSharingSettings")
        }
        self.windows = ChromeControl(self.journal, "win32", policies=self.policies)
        self.launcher = self.root / "launcher.desktop"
        self.linux = ChromeControl(
            self.journal, "linux", launcher_path=self.launcher, binary="/opt/google/chrome"
        )

    def test_windows_default_blocks_both(self):
        self.assertEqual(DEFAULT_FEATURES, ("gemini", "lens"))
        self.windows.disable()
        for policy in self.policies.values():
            self.assertEqual(policy.read(), policy.disabled_snapshot())
        self.windows.restore()
        self.assertTrue(all(not policy.read()["present"] for policy in self.policies.values()))

    def test_windows_lens_only_does_not_change_gemini(self):
        self.windows.disable(("lens",))
        self.assertFalse(self.policies["GeminiSettings"].read()["present"])
        self.assertEqual(self.policies["SearchContentSharingSettings"].read()["value"], 1)

    def test_partial_restore_keeps_other_policy_and_original_type(self):
        old = {"present": True, "value": "original", "kind": 1}
        self.policies["GeminiSettings"].value = old
        self.windows.disable()
        self.windows.disable()
        self.windows.restore(("gemini",))
        self.assertEqual(self.policies["GeminiSettings"].read(), old)
        self.assertEqual(self.policies["SearchContentSharingSettings"].read()["value"], 1)
        self.assertIn("SearchContentSharingSettings", self.journal.read()["policy_changes"])

    def test_second_policy_permission_failure_rolls_back_first(self):
        self.policies["SearchContentSharingSettings"].fail = True
        with self.assertRaises(PermissionError):
            self.windows.disable()
        self.assertFalse(self.policies["GeminiSettings"].read()["present"])
        self.policies["SearchContentSharingSettings"].fail = False
        self.windows.restore()
        self.assertEqual(self.journal.read()["policy_changes"], {})

    def test_conflicting_second_policy_prevents_any_restore(self):
        self.windows.disable()
        self.policies["SearchContentSharingSettings"].value = {
            "present": True,
            "value": 0,
            "kind": 4,
        }
        with self.assertRaises(AppError):
            self.windows.restore()
        self.assertEqual(self.policies["GeminiSettings"].read()["value"], 1)

    def test_legacy_windows_backup_preserves_first_original(self):
        original = {"present": True, "value": 0, "kind": 4}
        applied = self.policies["GeminiSettings"].disabled_snapshot()
        self.policies["GeminiSettings"].value = applied
        self.journal.write(
            {
                "schema": 1,
                "toolbar": {},
                "disable": {"platform": "win32", "before": original, "applied": applied},
            }
        )
        self.windows.disable()
        self.windows.restore()
        self.assertEqual(self.policies["GeminiSettings"].read(), original)
        self.assertFalse(self.policies["SearchContentSharingSettings"].read()["present"])

    def test_mac_exports_exact_selected_policies(self):
        for features, expected in (
            (DEFAULT_FEATURES, {"GeminiSettings": 1, "SearchContentSharingSettings": 1}),
            (("lens",), {"SearchContentSharingSettings": 1}),
        ):
            data = plistlib.loads(mac_profile(features))
            settings = {
                key: value
                for key, value in data["PayloadContent"][0].items()
                if not key.startswith("Payload")
            }
            self.assertEqual(settings, expected)
            self.assertFalse(data["PayloadRemovalDisallowed"])

    def test_default_mac_export_is_not_marked_applied(self):
        control = ChromeControl(self.journal, "darwin")
        path = self.root / "profile.mobileconfig"
        result = control.export_mac(path)
        self.assertIn("does not apply", result)
        self.assertFalse(self.journal.path.exists())
        self.assertIn(
            "SearchContentSharingSettings", plistlib.loads(path.read_bytes())["PayloadContent"][0]
        )

    def test_linux_default_and_selective_undo(self):
        self.linux.disable()
        self.assertIn(
            b"--disable-features=Glic,LensOverlay,LensStandalone", self.launcher.read_bytes()
        )
        self.linux.restore(("lens",))
        self.assertIn(b"--disable-features=Glic %U", self.launcher.read_bytes())
        self.assertNotIn(b"LensOverlay", self.launcher.read_bytes())
        self.linux.restore()
        self.assertFalse(self.launcher.exists())

    def test_linux_can_upgrade_legacy_launcher(self):
        content = linux_launcher("/opt/google/chrome")
        self.launcher.write_bytes(content)
        self.journal.write(
            {
                "schema": 1,
                "toolbar": {},
                "disable": {
                    "platform": "linux",
                    "path": str(self.launcher),
                    "applied": base64.b64encode(content).decode("ascii"),
                },
            }
        )
        self.linux.disable()
        self.assertIn(b"LensStandalone", self.launcher.read_bytes())
        self.linux.restore()
        self.assertFalse(self.launcher.exists())

    def test_linux_retains_features_when_another_is_added(self):
        self.linux.disable(("lens",))
        self.assertNotIn(b"Glic", self.launcher.read_bytes())
        self.linux.disable(("gemini",))
        self.assertIn(b"Glic,LensOverlay,LensStandalone", self.launcher.read_bytes())

    def test_linux_conflict_is_not_overwritten(self):
        self.linux.disable()
        self.launcher.write_bytes(b"user edited")
        with self.assertRaises(AppError):
            self.linux.restore()
        self.assertEqual(self.launcher.read_bytes(), b"user edited")

    def test_linux_write_failure_can_be_recovered(self):
        self.linux.disable(("gemini",))
        old = self.launcher.read_bytes()
        with patch("chrome_without_gemini.controls.atomic_write", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                self.linux.disable(("lens",))
        self.assertEqual(self.launcher.read_bytes(), old)
        self.linux.restore(("lens",))
        self.assertEqual(self.launcher.read_bytes(), old)

    def test_empty_or_unknown_selection_is_rejected_without_state(self):
        for features in ((), ("unknown",)):
            with self.assertRaises(AppError):
                self.windows.disable(features)
        self.assertFalse(self.journal.path.exists())

    def test_lens_launcher_does_not_disable_unrelated_features(self):
        data = launcher_content("/opt/chrome", ("lens",))
        self.assertIn(b"--disable-features=LensOverlay,LensStandalone %U", data)
        self.assertNotIn(b"Glic", data)


if __name__ == "__main__":
    unittest.main()
