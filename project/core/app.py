from __future__ import annotations

import os
import sys
import traceback

from project.utils.logging_utils import log_error


def _has_display() -> bool:
    """Tk on Linux needs an X display (normally provided by the desktop session)."""
    return bool(os.environ.get("DISPLAY"))


def main() -> int:
    if not _has_display():
        sys.stderr.write(
            "[ERROR] GUI display is not available.\n"
            "Open the Raspberry Pi desktop first, then run the launcher from the desktop/menu or a desktop terminal.\n"
            "If you are in SSH/TTY, Tkinter cannot open without a desktop X display.\n"
        )
        return 2

    try:
        from tkinter import TclError
        from project.gui.screen_manager import ScreenManager
        from project.gui import screen_ids
        from project.gui.screens.a_start import StartScreen
        from project.gui.screens.c_form import FormScreen
        from project.gui.screens.d_review import ReviewScreen
        from project.gui.screens.e_printing import PrintingScreen
        from project.gui.screens.f_done import DoneScreen
        from project.services.telegram_bot import start_telegram_control_bot

        telegram_bot = None
        manager = ScreenManager()
        manager.add_frame(screen_ids.START, StartScreen, manager=manager)
        manager.add_frame(screen_ids.FORM, FormScreen, manager=manager)
        manager.add_frame(screen_ids.REVIEW, ReviewScreen, manager=manager)
        manager.add_frame(screen_ids.PRINTING, PrintingScreen, manager=manager)
        manager.add_frame(screen_ids.DONE, DoneScreen, manager=manager)
        try:
            telegram_bot = start_telegram_control_bot(manager=manager)
            manager.show_frame(screen_ids.START)
            manager.mainloop()
        finally:
            if telegram_bot is not None:
                telegram_bot.stop()
        return 0
    except TclError as exc:
        sys.stderr.write(f"[ERROR] Failed to open GUI display: {exc}\n")
        return 3
    except Exception:
        msg = traceback.format_exc()
        log_error(msg)
        sys.stderr.write(msg)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
