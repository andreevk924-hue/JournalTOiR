import sys

# Windows taskbar/shortcut identity for the gear application icon.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JournalTOiR.Desktop")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from database.customer_manager import CustomerManager
from database.migrations import migrate
from gui.dialogs.customer_dialog import CustomerDialog
from gui.dialogs.pin_dialog import PinDialog
from gui.dialogs.setup_wizard import SetupWizard
from gui.main_window import MainWindow
from gui.theme import apply_theme, create_app_icon
from services.app_settings import AppSettingsManager
from services.sync_service import SyncService


def select_customer():
    dialog = CustomerDialog()
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.get_selected_customer()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Журнал ТОиР")
    app.setOrganizationName("JournalTOiR")
    app.setWindowIcon(create_app_icon())

    settings = AppSettingsManager()
    apply_theme(app, settings.load().get("ui", {}).get("theme", "light"))

    try:
        if not settings.load().get("setup_complete"):
            wizard = SetupWizard()
            if wizard.exec() != QDialog.Accepted:
                return 0
            apply_theme(app, settings.load().get("ui", {}).get("theme", "light"))

        if settings.load().get("security", {}).get("pin_enabled"):
            if PinDialog().exec() != QDialog.Accepted:
                return 0

        customer_name = select_customer()
        if not customer_name:
            return 0

        # До открытия SQLite подтягиваем серверную копию, если она свежее.
        SyncService(customer_name).prepare_before_open()
        CustomerManager().set_active_customer(customer_name)
        settings.set_active_customer(customer_name)

        migrate(customer_name=customer_name)
        window = MainWindow(customer_name=customer_name)
        window.show()
        return app.exec()

    except Exception as error:
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось запустить программу.\n\n{type(error).__name__}: {error}",
        )
        raise


if __name__ == "__main__":
    sys.exit(main())
