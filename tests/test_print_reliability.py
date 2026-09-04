import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project.gui import screen_ids
from project.gui.screen_manager import ScreenManager
from project.gui.screens.e_printing import ERROR_RETURN_SECONDS, PrintingScreen
from project.services import print_job
from project.services.print_counters import CounterSnapshot
from project.utils.printing import printer_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "project" / "docs" / "template.docx"


def valid_form_data():
    return {
        "ime": "Ана Анић",
        "ime_ucenika": "Ана",
        "prezime": "Анић",
        "roditelj": "Милан",
        "mjesto": "Касиндо",
        "opstina": "Источна Илиџа",
        "razred": "I-1",
        "struka": "Гимназија",
        "razlog": "Превоз",
        "dan": "01",
        "mjesec": "09",
        "godina": "2009",
    }


def fake_pdf_converter(order):
    def convert(_docx_path, output_dir):
        order.append("pdf")
        result = Path(output_dir) / "output.pdf"
        result.write_bytes(b"%PDF-1.4\n%%EOF")
        return str(result)

    return convert


class PrintServiceReliabilityTests(unittest.TestCase):
    def test_normalization_rebuilds_full_name(self):
        normalized = print_job._normalize_form_data(
            {"ime": "  Ана   Марија   Анић  ", "mjesto": "  KASINDO  ", "opstina": "pogrešna"}
        )
        self.assertEqual(normalized["ime_ucenika"], "Ана")
        self.assertEqual(normalized["prezime"], "Марија Анић")
        self.assertEqual(normalized["ime"], "Ана Марија Анић")
        self.assertEqual(normalized["opstina"], "Источна Илиџа")

    def test_failure_reporting_is_best_effort(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(print_job, "_write_job_json", side_effect=OSError("disk")),
                patch.object(print_job, "_notify_job_failure", side_effect=OSError("offline")),
                patch.object(print_job, "check_storage_pressure_async", side_effect=RuntimeError("busy")),
                patch.object(print_job, "log_error"),
            ):
                result = print_job._fail(Path(temp_dir), {}, "job-1", "PRN_OFFLINE", "Printer nije dostupan.")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "PRN_OFFLINE")

    def test_outer_fail_safe_converts_unhandled_exception_to_result(self):
        with (
            patch.object(print_job, "_run_print_job_impl", side_effect=RuntimeError("boom")),
            patch.object(print_job, "log_error"),
        ):
            result = print_job.run_print_job(valid_form_data())
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "PRINT_PIPELINE_EXCEPTION")

    def test_local_docx_and_pdf_finish_before_printer_unavailable_result(self):
        order = []

        def unavailable_printer():
            order.append("printer")
            return False, "", "PRN_OFFLINE", "Printer nije dostupan.", "NetworkPrinter", 1

        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_dir = Path(temp_dir) / "jobs"
            with (
                patch.object(print_job.config, "JOBS_DIR", jobs_dir),
                patch.object(print_job.config, "TEMPLATE_FILE", TEMPLATE),
                patch.object(print_job.config, "is_within_working_hours", return_value=True),
                patch.object(print_job, "convert_docx_to_pdf", side_effect=fake_pdf_converter(order)),
                patch.object(print_job, "_resolve_ready_printer_for_job", side_effect=unavailable_printer),
                patch.object(print_job, "_notify_job_failure"),
                patch.object(print_job, "check_storage_pressure_async"),
                patch.object(print_job, "increment_print_counter") as counter,
            ):
                result = print_job.run_print_job(valid_form_data(), do_print=True)

            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, "PRN_OFFLINE")
            self.assertEqual(order, ["pdf", "printer"])
            self.assertTrue(Path(result.docx_path).is_file())
            self.assertTrue(Path(result.pdf_path).is_file())
            counter.assert_not_called()

    def test_telegram_and_status_callback_failures_do_not_change_success(self):
        order = []

        def broken_status(_code):
            raise RuntimeError("UI already closed")

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(print_job.config, "JOBS_DIR", Path(temp_dir) / "jobs"),
                patch.object(print_job.config, "TEMPLATE_FILE", TEMPLATE),
                patch.object(print_job.config, "is_within_working_hours", return_value=True),
                patch.object(print_job, "convert_docx_to_pdf", side_effect=fake_pdf_converter(order)),
                patch.object(print_job, "cleanup_print_job_documents", return_value={"documents_cleaned": False}),
                patch.object(print_job, "_notify_job_success", side_effect=OSError("offline")),
                patch.object(print_job, "check_storage_pressure_async", side_effect=RuntimeError("busy")),
                patch.object(print_job, "log_error"),
                patch.object(print_job, "increment_print_counter") as counter,
            ):
                result = print_job.run_print_job(valid_form_data(), on_status=broken_status, do_print=False)
        self.assertTrue(result.ok)
        counter.assert_not_called()

    def test_post_completion_bookkeeping_failure_does_not_invite_duplicate_print(self):
        order = []
        write_calls = 0

        original_write = print_job._write_job_json

        def fail_only_after_artifacts(job_dir, payload):
            nonlocal write_calls
            write_calls += 1
            if write_calls >= 7:
                raise OSError("disk became read-only after completion")
            return original_write(job_dir, payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(print_job.config, "JOBS_DIR", Path(temp_dir) / "jobs"),
                patch.object(print_job.config, "TEMPLATE_FILE", TEMPLATE),
                patch.object(print_job.config, "is_within_working_hours", return_value=True),
                patch.object(print_job, "convert_docx_to_pdf", side_effect=fake_pdf_converter(order)),
                patch.object(
                    print_job,
                    "_resolve_ready_printer_for_job",
                    return_value=(True, "USBPrinter", "OK", "", "USBPrinter", 1),
                ),
                patch.object(
                    print_job,
                    "print_with_hplip",
                    return_value=SimpleNamespace(ok=True, printer_name="USBPrinter", detail="accepted"),
                ) as print_command,
                patch.object(print_job, "_write_job_json", side_effect=fail_only_after_artifacts),
                patch.object(print_job, "cleanup_print_job_documents", side_effect=OSError("cleanup failed")),
                patch.object(print_job, "_notify_job_success"),
                patch.object(print_job, "check_storage_pressure_async"),
                patch.object(print_job, "log_error"),
                patch.object(
                    print_job,
                    "increment_print_counter",
                    return_value=CounterSnapshot({"Превоз": 11}),
                ) as counter,
            ):
                result = print_job.run_print_job(valid_form_data(), do_print=True)
        self.assertTrue(result.ok)
        print_command.assert_called_once()
        counter.assert_called_once()
        self.assertEqual(counter.call_args.args[0], "Превоз")
        self.assertTrue(counter.call_args.kwargs["job_id"])

    def test_counter_failure_after_accepted_print_is_best_effort(self):
        payload = {"form_data": {"razlog": "Превоз"}}
        with (
            patch.object(print_job, "increment_print_counter", side_effect=OSError("disk read-only")),
            patch.object(print_job, "notify_telegram_async") as notify,
            patch.object(print_job, "log_error"),
        ):
            print_job._record_successful_print("job-1", payload)
        self.assertIn("counter_error", payload)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["kind"], "error")

    def test_success_telegram_message_contains_reason_and_total_counts(self):
        payload = {
            "form_data": valid_form_data(),
            "printed": True,
            "printer_name": "USBPrinter",
            "reason_print_count": 8,
            "total_print_count": 21,
        }
        with (
            patch.object(print_job.config, "TELEGRAM_NOTIFY_PRINT_JOBS", True),
            patch.object(print_job, "notify_telegram_async") as notify,
        ):
            print_job._notify_job_success("job-1", payload)
        message = notify.call_args.args[0]
        self.assertIn("Број за овај разлог: 8", message)
        self.assertIn("Укупно одштампано: 21", message)

    def test_usb_device_check_does_not_require_network(self):
        with patch.object(printer_status.socket, "create_connection") as create_connection:
            ready, code, message = printer_status._check_network_device_available(
                "usb://HP/LaserJet?serial=123", "USBPrinter"
            )
        self.assertTrue(ready)
        self.assertEqual((code, message), ("OK", ""))
        create_connection.assert_not_called()


class ThreadSafeUiTests(unittest.TestCase):
    def test_worker_ui_callback_uses_manager_queue(self):
        queued = []
        fake_manager = SimpleNamespace(_is_closing=False, post_ui_action=queued.append)
        fake_screen = SimpleNamespace(manager=fake_manager)
        callback = lambda: None
        self.assertTrue(PrintingScreen._schedule_ui(fake_screen, callback))
        self.assertEqual(queued, [callback])

    def test_screen_manager_queues_worker_callback(self):
        actions = queue.Queue()
        fake_manager = SimpleNamespace(_is_closing=False, _ui_actions=actions)
        callback = lambda: None
        with patch("project.gui.screen_manager.threading.current_thread", return_value=object()):
            ScreenManager._run_on_ui_thread(fake_manager, callback)
        self.assertIs(actions.get_nowait(), callback)

    def test_busy_screen_does_not_start_second_job(self):
        marker = object()
        fake_screen = SimpleNamespace(_is_busy=True, _worker=marker)
        PrintingScreen.on_show(fake_screen)
        self.assertIs(fake_screen._worker, marker)

    def test_error_countdown_reaches_home(self):
        calls = []
        label = SimpleNamespace(config=lambda **kwargs: calls.append(kwargs["text"]))
        manager = SimpleNamespace(current_frame_name=screen_ids.PRINTING)
        fake_screen = SimpleNamespace(
            manager=manager,
            _error_countdown_after_id=None,
            _error_seconds_left=1,
            error_countdown=label,
            after=lambda _ms, _callback: "timer-1",
            _update_error_countdown=lambda: None,
            _go_home=lambda: calls.append("home"),
        )
        PrintingScreen._update_error_countdown(fake_screen)
        self.assertEqual(calls, ["Повратак на почетак за 1 с"])
        self.assertEqual(fake_screen._error_countdown_after_id, "timer-1")
        self.assertEqual(fake_screen._error_seconds_left, 0)
        PrintingScreen._update_error_countdown(fake_screen)
        self.assertEqual(calls[-1], "home")

    def test_error_countdown_is_ten_seconds(self):
        self.assertEqual(ERROR_RETURN_SECONDS, 10)

    def test_home_clears_job_state_and_returns_to_start(self):
        events = []
        manager = SimpleNamespace(
            state={"form_data": {"ime": "Ana"}, "last_print_error_code": "PRN_OFFLINE"},
            clear_state=lambda: manager.state.clear(),
            set_idle_suspended=lambda value: events.append(("idle", value)),
            show_frame=lambda name, **kwargs: events.append(("screen", name, kwargs)),
        )
        fake_screen = SimpleNamespace(manager=manager, _cancel_error_countdown=lambda: events.append(("timer", "cancel")))
        PrintingScreen._go_home(fake_screen)
        self.assertEqual(manager.state, {})
        self.assertIn(("screen", screen_ids.START, {"force": True}), events)

    def test_leaving_busy_screen_keeps_parallel_job_guard_active(self):
        fake_screen = SimpleNamespace(
            _is_busy=True,
            _run_token=4,
            _cancel_error_countdown=lambda: None,
        )
        PrintingScreen.on_hide(fake_screen)
        self.assertTrue(fake_screen._is_busy)
        self.assertEqual(fake_screen._run_token, 4)

    def test_hidden_worker_completion_clears_busy_without_changing_screen(self):
        result = print_job.PrintResult(False, "job-1", error_code="PRN_OFFLINE")
        manager = SimpleNamespace(current_frame_name=screen_ids.FORM)
        fake_screen = SimpleNamespace(
            manager=manager,
            _run_token=2,
            _is_busy=True,
            _last_result=None,
            winfo_exists=lambda: True,
        )
        PrintingScreen._finish_run_if_current(fake_screen, result, 2)
        self.assertFalse(fake_screen._is_busy)
        self.assertIs(fake_screen._last_result, result)


if __name__ == "__main__":
    unittest.main()
