import copy
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from chrome_without_gemini.core import (
    AppError,
    Journal,
    Profile,
    Toolbar,
    chrome_running,
    discover_profiles,
    read_json,
    write_json,
)
from chrome_without_gemini.platforms import GeminiControl, desktop_quote, mac_profile


class Fixture(unittest.TestCase):
    def setUp(self):
        fixture_root = Path(__file__).resolve().parents[1] / "build" / "test-tmp"
        fixture_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixture_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = Journal(self.root / "state")
        self.toolbar = Toolbar(self.journal)
        self.closed = patch("chrome_without_gemini.core.chrome_running", return_value=False)
        self.closed.start()
        self.addCleanup(self.closed.stop)

    def profile(self, name="Default", prefs=None):
        path = self.root / "chrome" / name / "Preferences"
        write_json(path, prefs if prefs is not None else {"glic": {"pinned_to_tabstrip": True}})
        return Profile(path.resolve(), name, None)


class ToolbarTests(Fixture):
    def test_hide_and_restore_preserve_unrelated_changes(self):
        profile = self.profile(
            prefs={
                "glic": {"pinned_to_tabstrip": True, "zoom_level": 100},
                "bookmarks": "untouched",
            }
        )
        self.toolbar.hide([profile])
        prefs = read_json(profile.path)
        self.assertIs(prefs["glic"]["pinned_to_tabstrip"], False)
        prefs["new_setting"] = "made after hide"
        prefs["glic"]["zoom_level"] = 120
        write_json(profile.path, prefs)
        self.toolbar.restore()
        restored = read_json(profile.path)
        self.assertIs(restored["glic"]["pinned_to_tabstrip"], True)
        self.assertEqual(restored["new_setting"], "made after hide")
        self.assertEqual(restored["glic"]["zoom_level"], 120)

    def test_missing_parent_is_removed_on_restore(self):
        profile = self.profile(prefs={"unrelated": {"value": 9}})
        self.toolbar.hide([profile])
        self.toolbar.restore()
        self.assertEqual(read_json(profile.path), {"unrelated": {"value": 9}})

    def test_new_sibling_is_preserved_when_parent_was_absent(self):
        profile = self.profile(prefs={})
        self.toolbar.hide([profile])
        prefs = read_json(profile.path)
        prefs["glic"]["zoom_level"] = 90
        write_json(profile.path, prefs)
        self.toolbar.restore()
        self.assertEqual(read_json(profile.path), {"glic": {"zoom_level": 90}})

    def test_existing_empty_parent_is_retained(self):
        profile = self.profile(prefs={"glic": {}})
        self.toolbar.hide([profile])
        self.toolbar.restore()
        self.assertEqual(read_json(profile.path), {"glic": {}})

    def test_repeated_apply_does_not_replace_original(self):
        profile = self.profile()
        self.toolbar.hide([profile])
        self.toolbar.hide([profile])
        self.toolbar.restore()
        self.assertTrue(read_json(profile.path)["glic"]["pinned_to_tabstrip"])

    def test_restores_already_hidden_baseline(self):
        profile = self.profile(prefs={"glic": {"pinned_to_tabstrip": False}})
        self.toolbar.hide([profile])
        self.toolbar.restore()
        self.assertIs(read_json(profile.path)["glic"]["pinned_to_tabstrip"], False)

    def test_rejects_running_chrome_without_writes(self):
        profile = self.profile()
        before = profile.path.read_bytes()
        with patch("chrome_without_gemini.core.chrome_running", return_value=True):
            with self.assertRaises(AppError):
                self.toolbar.hide([profile])
        self.assertEqual(profile.path.read_bytes(), before)
        self.assertFalse(self.journal.path.exists())

    def test_corrupt_second_profile_prevents_first_write(self):
        first, second = self.profile(), self.profile("Profile 1")
        before = first.path.read_bytes()
        second.path.write_text("invalid json", encoding="utf-8")
        with self.assertRaises(AppError):
            self.toolbar.hide([first, second])
        self.assertEqual(first.path.read_bytes(), before)
        self.assertFalse(self.journal.path.exists())

    def test_unexpected_glic_shape_stops_changes(self):
        profile = self.profile(prefs={"glic": "unexpected"})
        with self.assertRaises(AppError):
            self.toolbar.hide([profile])

    def test_restore_refuses_newer_user_choice(self):
        profile = self.profile(prefs={})
        self.toolbar.hide([profile])
        write_json(profile.path, {"glic": {"pinned_to_tabstrip": True}})
        with self.assertRaises(AppError):
            self.toolbar.restore()
        self.assertTrue(self.journal.read()["toolbar"])
        self.assertTrue(read_json(profile.path)["glic"]["pinned_to_tabstrip"])

    def test_failed_second_write_rolls_back_first(self):
        first, second = self.profile(), self.profile("Profile 1")
        original = first.path.read_bytes()
        actual_write = write_json

        def failing_write(path, data):
            if path == second.path:
                raise PermissionError("simulated read-only profile")
            actual_write(path, data)

        with patch("chrome_without_gemini.core.write_json", side_effect=failing_write):
            with self.assertRaises(PermissionError):
                self.toolbar.hide([first, second])
        self.assertEqual(first.path.read_bytes(), original)
        # The journal survives, and undo can recover a prepared-but-unapplied operation.
        self.toolbar.restore()
        self.assertFalse(self.journal.read()["toolbar"])

    def test_journal_contains_only_the_touched_setting(self):
        profile = self.profile(
            prefs={"glic": {"pinned_to_tabstrip": True}, "private": "NEVER_COPY_THIS"}
        )
        self.toolbar.hide([profile])
        self.assertNotIn("NEVER_COPY_THIS", self.journal.path.read_text(encoding="utf-8"))

    def test_lock_prevents_overlapping_operations(self):
        with self.journal.locked():
            with self.assertRaises(AppError):
                with self.journal.locked():
                    pass
        self.assertFalse((self.journal.root / "operation.lock").exists())

    def test_discovery_excludes_system_guest_and_arbitrary_folders(self):
        for name in ("Default", "Profile 1", "System Profile", "Guest Profile", "other"):
            self.profile(name)
        found = discover_profiles(self.root / "chrome")
        self.assertEqual([p.path.parent.name for p in found], ["Default", "Profile 1"])

    def test_discovery_does_not_expose_chrome_account_names(self):
        self.profile(prefs={"profile": {"name": "PRIVATE ACCOUNT DISPLAY NAME"}})
        self.profile("Profile 1", prefs={"profile": {"name": "SECOND PRIVATE ACCOUNT"}})
        found = discover_profiles(self.root / "chrome")
        self.assertEqual([p.name for p in found], ["Default profile", "Profile 1"])
        self.assertNotIn("PRIVATE", repr(found))


class MemoryPolicy:
    def __init__(self, initial=None):
        self.value = initial or {"present": False}
        self.fail = False

    def read(self):
        return copy.deepcopy(self.value)

    def write(self, value):
        if self.fail:
            raise PermissionError("registry blocked")
        self.value = copy.deepcopy(value)

    def disabled_snapshot(self):
        return {"present": True, "value": 1, "kind": 4}


class PolicyTests(Fixture):
    def control(self, initial=None):
        policy = MemoryPolicy(initial)
        return GeminiControl(self.journal, "win32", policy), policy

    def test_restore_original_value_and_type(self):
        original = {"present": True, "value": "existing", "kind": 1}
        control, policy = self.control(original)
        control.disable()
        control.disable()
        self.assertEqual(policy.read(), policy.disabled_snapshot())
        control.restore()
        self.assertEqual(policy.read(), original)

    def test_restore_absent_original(self):
        control, policy = self.control()
        control.disable()
        control.restore()
        self.assertEqual(policy.read(), {"present": False})

    def test_policy_permission_failure_retains_backup(self):
        control, policy = self.control()
        policy.fail = True
        with self.assertRaises(PermissionError):
            control.disable()
        self.assertEqual(policy.read(), {"present": False})
        self.assertIsNotNone(self.journal.read()["disable"])
        policy.fail = False
        control.restore()
        self.assertIsNone(self.journal.read()["disable"])

    def test_new_external_policy_is_not_overwritten_on_restore(self):
        control, policy = self.control()
        control.disable()
        policy.value = {"present": True, "value": 0, "kind": 4}
        with self.assertRaises(AppError):
            control.restore()
        self.assertEqual(policy.read()["value"], 0)

    def test_mac_profile_has_only_one_policy_and_is_removable(self):
        data = plistlib.loads(mac_profile())
        payload = data["PayloadContent"][0]
        settings = {k: v for k, v in payload.items() if not k.startswith("Payload")}
        self.assertEqual(settings, {"GeminiSettings": 1})
        self.assertFalse(data["PayloadRemovalDisallowed"])
        self.assertEqual(data["PayloadScope"], "User")

    def test_export_is_not_marked_applied_and_does_not_overwrite(self):
        control = GeminiControl(self.journal, "darwin")
        path = self.root / "test.mobileconfig"
        result = control.export_mac(path)
        self.assertIn("does not apply", result)
        self.assertFalse(self.journal.path.exists())
        with self.assertRaises(AppError):
            control.export_mac(path)

    def test_linux_launcher_and_restore(self):
        path = self.root / "applications" / "chrome-without-gemini.desktop"
        control = GeminiControl(
            self.journal, "linux", launcher_path=path, binary="/opt/Google Chrome/chrome"
        )
        self.assertIn("only when launched", control.disable())
        text = path.read_text(encoding="utf-8")
        self.assertIn('Exec="/opt/Google Chrome/chrome" --disable-features=Glic %U', text)
        control.disable()
        control.restore()
        self.assertFalse(path.exists())

    def test_linux_preserves_existing_launcher(self):
        path = self.root / "chrome.desktop"
        path.write_text("existing", encoding="utf-8")
        control = GeminiControl(self.journal, "linux", launcher_path=path, binary="/usr/bin/chrome")
        with self.assertRaises(AppError):
            control.disable()
        self.assertEqual(path.read_text(encoding="utf-8"), "existing")

    def test_linux_reapply_retains_restore_data_when_binary_location_changes(self):
        path = self.root / "chrome.desktop"
        control = GeminiControl(self.journal, "linux", launcher_path=path, binary="/usr/bin/chrome")
        control.disable()
        original = path.read_bytes()
        control.binary = "/opt/google/chrome"
        control.disable()
        self.assertEqual(path.read_bytes(), original)
        control.restore()
        self.assertFalse(path.exists())

    def test_linux_restore_preserves_newer_edits(self):
        path = self.root / "chrome.desktop"
        control = GeminiControl(self.journal, "linux", launcher_path=path, binary="/usr/bin/chrome")
        control.disable()
        path.write_text("edited launcher", encoding="utf-8")
        with self.assertRaises(AppError):
            control.restore()
        self.assertTrue(path.exists())

    def test_desktop_exec_escaping(self):
        self.assertEqual(desktop_quote('/opt/100%/a"b'), '"/opt/100%%/a\\\\"b"')
        with self.assertRaises(AppError):
            desktop_quote("/opt/chrome\nExec=unwanted")


class ProcessTests(unittest.TestCase):
    def test_windows_process_output_parsing(self):
        from types import SimpleNamespace

        with (
            patch("chrome_without_gemini.core.sys.platform", "win32"),
            patch("chrome_without_gemini.core.run_command") as command,
        ):
            command.return_value = SimpleNamespace(returncode=0, stdout='"chrome.exe","123"\n')
            self.assertTrue(chrome_running())
            command.return_value = SimpleNamespace(returncode=0, stdout="INFO: none\n")
            self.assertFalse(chrome_running())

    def test_process_check_fails_closed(self):
        from types import SimpleNamespace

        with patch("chrome_without_gemini.core.run_command") as command:
            command.return_value = SimpleNamespace(returncode=1, stdout="")
            with self.assertRaises(AppError):
                chrome_running()


if __name__ == "__main__":
    unittest.main()
