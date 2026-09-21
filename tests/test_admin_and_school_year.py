import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from project.core import admin_auth
from project.core.school_year import school_year_for_date
from project.gui.screens.c_form import FormScreen
from project.gui.screens.g_admin import AdminScreen, notify_admin_self_test_failure
from project.services.self_test import SelfTestCheck, SelfTestReport
from project.utils import network_status
from project.utils.network_status import ConnectivityGate, _split_nmcli_escaped


class SchoolYearTests(unittest.TestCase):
    def test_rollover_is_first_of_september(self):
        self.assertEqual(school_year_for_date(dt.date(2026, 8, 31)), "2025/2026")
        self.assertEqual(school_year_for_date(dt.date(2026, 9, 1)), "2026/2027")
        self.assertEqual(school_year_for_date(dt.date(2026, 12, 31)), "2026/2027")
        self.assertEqual(school_year_for_date(dt.date(2027, 1, 1)), "2026/2027")
        self.assertEqual(school_year_for_date(dt.date(2027, 8, 31)), "2026/2027")


class AdminAuthTests(unittest.TestCase):
    def test_default_password_verifies_without_plaintext_in_config(self):
        initial_password = "".join(map(chr, (115, 115, 106, 117, 110, 105, 97, 100, 109, 105, 110, 105, 115, 116, 114, 97, 99, 105, 106, 97)))
        self.assertTrue(admin_auth.verify_admin_password(initial_password, admin_auth.config.ADMIN_PASSWORD_HASH))
        self.assertFalse(admin_auth.verify_admin_password("pogresnalonzinaka", admin_auth.config.ADMIN_PASSWORD_HASH))
        self.assertNotIn(initial_password, admin_auth.config.ADMIN_PASSWORD_HASH)

    def test_password_change_is_hashed_and_settings_are_private(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Path(temp_dir) / "settings.json"
            with patch.object(admin_auth.config, "SETTINGS_FILE", settings):
                ok, message = admin_auth.set_admin_password("novasigurnalozinka")
                self.assertTrue(ok, message)
                self.assertNotIn("novasigurnalozinka", settings.read_text(encoding="utf-8"))
                self.assertTrue(admin_auth.verify_admin_password("novasigurnalozinka"))

    def test_password_rejects_digits_and_spaces(self):
        self.assertFalse(admin_auth.validate_admin_password("admin12345")[0])
        self.assertFalse(admin_auth.validate_admin_password("admin lozinka")[0])
        self.assertFalse(admin_auth.validate_admin_password("администратор")[0])

    def test_hash_comparison_uses_compare_digest(self):
        encoded = admin_auth.hash_admin_password("sigurnalozinka", salt=b"fixed-test-salt")
        with patch.object(admin_auth.hmac, "compare_digest", wraps=admin_auth.hmac.compare_digest) as compare:
            self.assertTrue(admin_auth.verify_admin_password("sigurnalozinka", encoded))
        compare.assert_called_once()

    def test_lockout_after_five_failures_and_recovery_after_sixty_seconds(self):
        guard = admin_auth.AdminLoginGuard(5, 60)
        with patch.object(admin_auth, "verify_admin_password", return_value=False):
            for index in range(4):
                attempt = guard.attempt("pogresna", now=float(index))
                self.assertTrue(attempt.allowed)
                self.assertEqual(attempt.remaining_attempts, 4 - index)
            locked = guard.attempt("pogresna", now=4.0)
            self.assertEqual(locked.lock_seconds, 60)
            self.assertFalse(guard.attempt("bilo-sta", now=63.9).allowed)
        with patch.object(admin_auth, "verify_admin_password", return_value=True):
            self.assertTrue(guard.attempt("ispravna", now=64.0).authenticated)

    def test_secret_mask_toggles_without_exposing_value(self):
        self.assertEqual(admin_auth.toggled_secret_mask("●"), "")
        self.assertEqual(admin_auth.toggled_secret_mask(""), "●")

    def test_wifi_keyboard_defines_common_password_symbols(self):
        from project.gui.virtual_keyboard import VirtualKeyboard

        symbols = {token for row in VirtualKeyboard.SYMBOL_ROWS for token in row}
        self.assertTrue({"!", "@", "#", "$", "%", "&", "*", "?", "-", "_", ".", "/"}.issubset(symbols))


class ConnectivityTests(unittest.TestCase):
    def test_gate_requires_two_matching_results(self):
        gate = ConnectivityGate(2)
        self.assertFalse(gate.observe(False).blocked)
        self.assertTrue(gate.observe(False).blocked)
        self.assertTrue(gate.observe(True).blocked)
        self.assertFalse(gate.observe(True).blocked)

    def test_nmcli_escaped_fields(self):
        self.assertEqual(_split_nmcli_escaped(r"*:Skola\:Uprava:82:WPA2"), ["*", "Skola:Uprava", "82", "WPA2"])

    def test_scan_parses_active_open_and_protected_networks(self):
        output = "*:Uprava:88:WPA2\n:Gost:63:--"
        with (
            patch.object(network_status.shutil, "which", return_value="/usr/bin/nmcli"),
            patch.object(network_status, "_run", return_value=(True, output)),
        ):
            items, error = network_status.scan_wifi_networks()
        self.assertEqual(error, "")
        self.assertEqual(items[0], {"active": True, "ssid": "Uprava", "signal": 88, "security": "WPA2"})
        self.assertEqual(items[1]["security"], "--")

    def test_missing_nmcli_disables_scan_and_connect(self):
        with patch.object(network_status.shutil, "which", return_value=None):
            self.assertIn("nmcli", network_status.scan_wifi_networks()[1])
            self.assertIn("nmcli", network_status.connect_wifi("Uprava", "tajna")[1])

    def test_wifi_password_is_stdin_only(self):
        completed = SimpleNamespace(returncode=0, stdout="connected vrloTajnaLozinka")
        with (
            patch.object(network_status.shutil, "which", return_value="/usr/bin/nmcli"),
            patch.object(network_status, "active_wifi_details", return_value={"connection_name": "Stara"}),
            patch.object(network_status.subprocess, "run", return_value=completed) as run,
            patch.object(network_status, "check_internet", return_value=(True, "OK", "ok")),
        ):
            ok, _message = network_status.connect_wifi("Nova", "vrloTajnaLozinka")
        self.assertTrue(ok)
        self.assertNotIn("vrloTajnaLozinka", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["input"], "vrloTajnaLozinka\n")
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertNotIn("vrloTajnaLozinka", _message)
        self.assertIn("[REDACTED]", _message)

    def test_active_wifi_status_reads_connection_ssid_and_signal(self):
        responses = [
            (True, "Skolska mreza:802-11-wireless"),
            (True, "*:Skola:76"),
        ]
        with (
            patch.object(network_status.shutil, "which", return_value="/usr/bin/nmcli"),
            patch.object(network_status, "_run", side_effect=responses),
        ):
            details = network_status.active_wifi_details()
        self.assertEqual(details, {"connection_name": "Skolska mreza", "ssid": "Skola", "signal": 76})

    def test_failed_activation_rolls_back_previous_connection(self):
        completed = SimpleNamespace(returncode=10, stdout="activation failed")
        with (
            patch.object(network_status.shutil, "which", return_value="/usr/bin/nmcli"),
            patch.object(network_status, "active_wifi_details", return_value={"connection_name": "Stara"}),
            patch.object(network_status.subprocess, "run", return_value=completed),
            patch.object(network_status, "_run", return_value=(True, "restored")) as runner,
        ):
            ok, message = network_status.connect_wifi("Nova", "tajna")
        self.assertFalse(ok)
        runner.assert_called_once_with(["nmcli", "connection", "up", "Stara"], timeout=45)
        self.assertIn("враћена", message)

    def test_wifi_timeout_is_controlled(self):
        with (
            patch.object(network_status.shutil, "which", return_value="/usr/bin/nmcli"),
            patch.object(network_status, "active_wifi_details", return_value={"connection_name": ""}),
            patch.object(network_status.subprocess, "run", side_effect=network_status.subprocess.TimeoutExpired("nmcli", 60)),
        ):
            ok, message = network_status.connect_wifi("Nova", "tajna")
        self.assertFalse(ok)
        self.assertIn("предуго", message)


class AdminFlowTests(unittest.TestCase):
    def test_start_and_form_both_expose_admin_entry(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("goto_admin", (root / "project/gui/screens/a_start.py").read_text(encoding="utf-8"))
        self.assertIn("_open_admin", (root / "project/gui/screens/c_form.py").read_text(encoding="utf-8"))

    def test_partial_form_snapshot_preserves_values(self):
        form = object.__new__(FormScreen)
        entry = lambda text: SimpleNamespace(get=lambda: text)
        form.ime_entry = entry("Ана Анић")
        form.roditelj_entry = entry("Петар")
        form.mjesto_entry = entry("Касиндо")
        form.opstina_entry = entry("Источна Илиџа")
        form.razred_var = SimpleNamespace(get=lambda: "ПРВИ")
        form.struka_var = SimpleNamespace(get=lambda: "Електротехника")
        form.razlog_var = SimpleNamespace(get=lambda: "Превоз")
        form.dan_var = SimpleNamespace(get=lambda: "1")
        form.mjesec_var = SimpleNamespace(get=lambda: "2")
        form.godina_var = SimpleNamespace(get=lambda: "20")
        data = FormScreen._snapshot_form_data(form)
        self.assertEqual(data["ime"], "Ана Анић")
        self.assertEqual(data["godina"], "20")

    def test_idle_logout_clears_session_and_password(self):
        admin = object.__new__(AdminScreen)
        admin.manager = SimpleNamespace(state={"admin_return_screen": "Form"}, show_frame=Mock())
        admin._authenticated = True
        admin.password_var = SimpleNamespace(set=Mock())
        AdminScreen.on_idle_timeout(admin)
        self.assertFalse(admin._authenticated)
        admin.password_var.set.assert_called_once_with("")
        admin.manager.show_frame.assert_called_once_with("Form")

    def test_busy_guard_rejects_parallel_admin_operation(self):
        admin = object.__new__(AdminScreen)
        admin._busy = True
        admin.status_var = SimpleNamespace(set=Mock())
        target = Mock()
        AdminScreen._worker(admin, "Test", target, Mock())
        target.assert_not_called()
        admin.status_var.set.assert_called_once()

    def test_restart_and_shutdown_require_confirmation(self):
        admin = object.__new__(AdminScreen)
        admin._show_confirmation = Mock()
        AdminScreen._confirm_restart(admin)
        self.assertEqual(admin._show_confirmation.call_args.args[0], "ПОТВРДА ПОНОВНОГ ПОКРЕТАЊА")
        admin._show_confirmation.reset_mock()
        AdminScreen._confirm_shutdown(admin)
        self.assertEqual(admin._show_confirmation.call_args.args[0], "ПОТВРДА ГАШЕЊА")

    def test_printer_selection_sets_cups_and_runtime_choice(self):
        admin = object.__new__(AdminScreen)
        admin._worker = Mock()
        AdminScreen._select_printer(admin, "USB_Printer")
        _name, target, _done = admin._worker.call_args.args
        with (
            patch("project.gui.screens.g_admin.set_cups_default_printer", return_value=(True, "OK", "USB_Printer")),
            patch("project.gui.screens.g_admin.set_selected_printer") as save,
        ):
            self.assertEqual(target(), (True, "OK", "USB_Printer"))
        save.assert_called_once_with("USB_Printer")

    def test_self_test_notifies_telegram_only_on_failure(self):
        successful = SelfTestReport((SelfTestCheck("OK", True, "ok"),), 0.1)
        failed = SelfTestReport((SelfTestCheck("Printer", False, "offline"),), 0.1)
        with patch("project.gui.screens.g_admin.notify_telegram_async") as notify:
            self.assertFalse(notify_admin_self_test_failure(successful))
            notify.assert_not_called()
            self.assertTrue(notify_admin_self_test_failure(failed))
            notify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
