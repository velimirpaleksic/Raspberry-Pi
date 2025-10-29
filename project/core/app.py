# core/app.py
from project.gui.screen_manager import ScreenManager
from project.gui.screens.a_start import StartScreen
from project.gui.screens.b_tutorial import TutorialScreen
from project.gui.screens.c_form import FormScreen
from project.gui.screens.d_printing_status import PrintingStatusScreen
from project.gui.screens.e_finished import FinishedPrintingScreen

if __name__ == "__main__":
    manager = ScreenManager()

    manager.add_frame("StartScreen", StartScreen, manager=manager)
    manager.add_frame("TutorialScreen", TutorialScreen, manager=manager)
    manager.add_frame("FormScreen", FormScreen, manager=manager)
    manager.add_frame("StatusScreen", PrintingStatusScreen, manager=manager)
    manager.add_frame("SuccessScreen", FinishedPrintingScreen, manager=manager)

    manager.show_frame("StartScreen")  # start from start screen
    manager.mainloop()