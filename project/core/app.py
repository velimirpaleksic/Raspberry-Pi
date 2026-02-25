from project.gui.screen_manager import ScreenManager
from project.gui import screen_ids

from project.gui.screens.a_start import StartScreen
from project.gui.screens.b_tutorial import TutorialScreen
from project.gui.screens.c_form import FormScreen
from project.gui.screens.d_review import ReviewScreen
from project.gui.screens.e_printing import PrintingScreen
from project.gui.screens.f_done import DoneScreen


def main() -> None:
    manager = ScreenManager()

    manager.add_frame(screen_ids.START, StartScreen, manager=manager)
    manager.add_frame(screen_ids.TUTORIAL, TutorialScreen, manager=manager)
    manager.add_frame(screen_ids.FORM, FormScreen, manager=manager)
    manager.add_frame(screen_ids.REVIEW, ReviewScreen, manager=manager)
    manager.add_frame(screen_ids.PRINTING, PrintingScreen, manager=manager)
    manager.add_frame(screen_ids.DONE, DoneScreen, manager=manager)

    manager.show_frame(screen_ids.START)
    manager.mainloop()


if __name__ == "__main__":
    main()
