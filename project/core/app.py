from project.db.db_init import initialize_database
from project.gui.screen_manager import ScreenManager
from project.gui import screen_ids

from project.gui.screens.a_start import StartScreen
from project.gui.screens.b_tutorial import TutorialScreen
from project.gui.screens.c_form import FormScreen
from project.gui.screens.d_review import ReviewScreen
from project.gui.screens.e_printing import PrintingScreen
from project.gui.screens.f_done import DoneScreen
from project.gui.screens.g_admin import AdminScreen
from project.gui.screens.h_health import HealthScreen
from project.gui.screens.i_setup import SetupScreen
from project.gui.screens.j_network import NetworkScreen
from project.gui.screens.k_settings import SettingsScreen
from project.gui.screens.l_recovery import RecoveryScreen
from project.gui.screens.m_readiness import ReadinessScreen
from project.services.document_service import mark_interrupted_documents, record_system_event


def main() -> None:
    initialize_database()
    interrupted = mark_interrupted_documents()
    record_system_event("app_start", f"Application started. interrupted_recovered={interrupted}")

    manager = ScreenManager()

    manager.add_frame(screen_ids.START, StartScreen, manager=manager)
    manager.add_frame(screen_ids.TUTORIAL, TutorialScreen, manager=manager)
    manager.add_frame(screen_ids.FORM, FormScreen, manager=manager)
    manager.add_frame(screen_ids.REVIEW, ReviewScreen, manager=manager)
    manager.add_frame(screen_ids.PRINTING, PrintingScreen, manager=manager)
    manager.add_frame(screen_ids.DONE, DoneScreen, manager=manager)
    manager.add_frame(screen_ids.ADMIN, AdminScreen, manager=manager)
    manager.add_frame(screen_ids.HEALTH, HealthScreen, manager=manager)
    manager.add_frame(screen_ids.SETUP, SetupScreen, manager=manager)
    manager.add_frame(screen_ids.NETWORK, NetworkScreen, manager=manager)
    manager.add_frame(screen_ids.SETTINGS, SettingsScreen, manager=manager)
    manager.add_frame(screen_ids.RECOVERY, RecoveryScreen, manager=manager)
    manager.add_frame(screen_ids.READINESS, ReadinessScreen, manager=manager)

    manager.show_frame(screen_ids.HEALTH)
    manager.mainloop()


if __name__ == "__main__":
    main()
