import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from project.services import self_test
from project.services.self_test import SelfTestCheck, SelfTestReport, format_self_test_report, run_self_test
from project.services.storage_cleanup import DiskInfo
from project.services.telegram_bot import TelegramControlBot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "project" / "docs" / "template.docx"


def _fake_pdf_converter(docx_path: str, output_dir: str) -> str:
    output = Path(output_dir) / (Path(docx_path).stem + ".pdf")
    output.write_bytes(b"%PDF-1.4\n1 0 obj <</Type /Page>> endobj\n%%EOF")
    return str(output)


class SelfTestServiceTests(unittest.TestCase):
    def test_complete_self_test_generates_and_removes_artifacts_without_printing(self):
        healthy_storage = {
            "root": DiskInfo("/", total=10_000_000_000, used=1_000_000_000, free=9_000_000_000, used_percent=10),
            "app_data": DiskInfo("/var/lib/app", total=10_000_000_000, used=1_000_000_000, free=9_000_000_000, used_percent=10),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(self_test.config, "TEMPLATE_FILE", TEMPLATE),
                patch.object(self_test.config, "VAR_DIR", Path(temp_dir)),
                patch.object(self_test.shutil, "which", side_effect=lambda name: f"/fake/{name}"),
                patch.object(self_test, "convert_docx_to_pdf", side_effect=_fake_pdf_converter),
                patch.object(self_test, "_pdf_page_count", return_value=1),
                patch.object(
                    self_test,
                    "collect_printer_diagnostics",
                    return_value={"ready": True, "resolved": "USB_Printer"},
                ),
                patch.object(self_test, "collect_storage_report", return_value=healthy_storage),
                patch.object(
                    self_test,
                    "collect_network_diagnostics",
                    return_value={"internet": True, "ssid": "School", "ip": "192.0.2.5"},
                ),
            ):
                report = run_self_test()

            self.assertTrue(report.ok)
            self.assertFalse(report.paper_printed)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])
            self.assertNotIn("print_with_hplip", Path(self_test.__file__).read_text(encoding="utf-8"))

    def test_failures_are_aggregated_into_telegram_ready_report(self):
        failed = SelfTestReport(
            checks=(
                SelfTestCheck("PDF generisanje", False, "LibreOffice nije pronađen"),
                SelfTestCheck("Printer/CUPS", False, "PRN_OFFLINE: printer nije spreman"),
            ),
            elapsed_seconds=1.25,
        )
        message = format_self_test_report(failed)
        self.assertFalse(failed.ok)
        self.assertIn("GREŠKA", message)
        self.assertIn("LibreOffice nije pronađen", message)
        self.assertIn("PRN_OFFLINE", message)
        self.assertIn("NIJE poslan na štampu", message)


class TelegramSelfTestCommandTests(unittest.TestCase):
    def test_selftest_command_runs_as_guarded_background_command(self):
        bot = TelegramControlBot()
        user_id = int(bot.allowed_user_id)
        update = {
            "message": {
                "from": {"id": user_id},
                "chat": {"id": user_id},
                "text": "/selftest",
            }
        }
        with patch.object(bot, "_start_background_command") as start:
            bot._handle_update(update)
        start.assert_called_once()
        name, chat_id, target = start.call_args.args
        self.assertEqual((name, chat_id), ("selftest", user_id))
        self.assertEqual(target, bot._run_self_test)

    def test_failed_selftest_is_sent_to_telegram_chat(self):
        failed = SelfTestReport(
            checks=(SelfTestCheck("Printer/CUPS", False, "PRN_OFFLINE"),),
            elapsed_seconds=0.5,
        )
        bot = object.__new__(TelegramControlBot)
        bot._send_message = Mock()
        with patch("project.services.telegram_bot.run_self_test", return_value=failed):
            bot._run_self_test(123)

        self.assertEqual(bot._send_message.call_count, 2)
        self.assertIn("No paper", bot._send_message.call_args_list[0].args[1])
        self.assertIn("GREŠKA", bot._send_message.call_args_list[1].args[1])
        self.assertIn("PRN_OFFLINE", bot._send_message.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
