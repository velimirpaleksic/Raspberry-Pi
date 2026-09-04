import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from project.core import config
from project.services import print_counters
from project.services.print_counters import (
    CounterSnapshot,
    CounterStoreError,
    format_print_counters,
    get_print_counters,
    increment_print_counter,
    reset_print_counters,
    resolve_reason_selector,
    set_print_counter,
)
from project.services.telegram_bot import TelegramControlBot


class PrintCounterStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.counter_file = Path(self.temp_dir.name) / "print_counters.json"
        self.path_patch = patch.object(print_counters.config, "PRINT_COUNTERS_FILE", self.counter_file)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_set_value_then_successful_jobs_increment_from_it_once_per_job(self):
        reason = config.RAZLOZI[0]
        snapshot = set_print_counter(reason, 40)
        self.assertEqual(snapshot.count_for(reason), 40)

        snapshot = increment_print_counter(reason, job_id="job-1")
        self.assertEqual(snapshot.count_for(reason), 41)
        snapshot = increment_print_counter(reason, job_id="job-1")
        self.assertEqual(snapshot.count_for(reason), 41)
        snapshot = increment_print_counter(reason, job_id="job-2")
        self.assertEqual(snapshot.count_for(reason), 42)
        self.assertEqual(get_print_counters().count_for(reason), 42)

        stored = json.loads(self.counter_file.read_text(encoding="utf-8"))
        self.assertEqual(stored["counts"][reason], 42)
        self.assertEqual(stored["recent_job_ids"], ["job-1", "job-2"])

    def test_reset_one_or_all_and_reason_selector(self):
        first, second = config.RAZLOZI[:2]
        set_print_counter(first, 7)
        set_print_counter(second, 9)
        self.assertEqual(resolve_reason_selector(" 2 "), second)
        self.assertEqual(resolve_reason_selector(first.lower()), first)

        one_reset = reset_print_counters(first)
        self.assertEqual(one_reset.count_for(first), 0)
        self.assertEqual(one_reset.count_for(second), 9)
        all_reset = reset_print_counters()
        self.assertEqual(all_reset.total, 0)

    def test_concurrent_increments_are_not_lost(self):
        reason = config.RAZLOZI[3]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda index: increment_print_counter(reason, job_id=f"job-{index}"), range(30)))
        self.assertEqual(get_print_counters().count_for(reason), 30)

    def test_corrupt_store_is_reported_and_not_overwritten(self):
        original = b"{not-json"
        self.counter_file.write_bytes(original)
        with self.assertRaises(CounterStoreError):
            increment_print_counter(config.RAZLOZI[0], job_id="job-1")
        self.assertEqual(self.counter_file.read_bytes(), original)

    def test_report_lists_configured_reasons_and_total(self):
        snapshot = CounterSnapshot({reason: index for index, reason in enumerate(config.RAZLOZI, start=1)})
        message = format_print_counters(snapshot)
        self.assertIn(f"Ukupno: {sum(range(1, len(config.RAZLOZI) + 1))}", message)
        for index, reason in enumerate(config.RAZLOZI, start=1):
            self.assertIn(f"{index}. {reason}: {index}", message)


class TelegramCounterCommandTests(unittest.TestCase):
    def test_countset_uses_numbered_reason_and_reports_new_total(self):
        bot = object.__new__(TelegramControlBot)
        bot._send_message = Mock()
        reason = config.RAZLOZI[1]
        snapshot = CounterSnapshot({item: (12 if item == reason else 0) for item in config.RAZLOZI})
        with patch("project.services.telegram_bot.set_print_counter", return_value=snapshot) as setter:
            bot._set_print_counter(123, "2 12")

        setter.assert_called_once_with(reason, 12)
        self.assertIn("Nova vrijednost: 12", bot._send_message.call_args.args[1])
        self.assertIn("Ukupno: 12", bot._send_message.call_args.args[1])

    def test_countreset_without_argument_resets_all(self):
        bot = object.__new__(TelegramControlBot)
        bot._send_message = Mock()
        empty = CounterSnapshot({reason: 0 for reason in config.RAZLOZI})
        with patch("project.services.telegram_bot.reset_print_counters", return_value=empty) as resetter:
            bot._reset_print_counter(123, "")
        resetter.assert_called_once_with()
        self.assertIn("Svi brojači", bot._send_message.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
