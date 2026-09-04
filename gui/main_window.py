# gui/main_window.py
# Часть 1/3

from pathlib import Path
from datetime import datetime
import sys

from PySide6.QtCore import (
    QDate, QTimer, Qt, QMarginsF, QSettings, QPropertyAnimation,
    QEasingCurve, QUrl, QParallelAnimationGroup, QSize
)
from PySide6.QtGui import QAction, QBrush, QColor, QPixmap, QTextDocument, QPageSize, QPageLayout, QFont, QDesktopServices
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QDateEdit,
    QDoubleSpinBox,
    QLineEdit,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
    QApplication,
    QGraphicsOpacityEffect,
    QToolButton,
    QSizePolicy,
    QSizeGrip,
    QSystemTrayIcon,
)

from database.customer_manager import CustomerManager
from database.repository import Repository
from dialogs.equipment_dialog import EquipmentDialog
from dialogs.component_dialog import ComponentDialog, MachineComponentsDialog
from dialogs.edit_work_dialog import EditWorkDialog
from dialogs.downtime_card_dialog import DowntimeCardDialog
from dialogs.plan_maintenance_dialog import PlanMaintenanceDialog
from gui.pages.components_page import ComponentsPage
from gui.pages.equipment_page import EquipmentPage
from gui.pages.reference_page import ReferencePage
from dialogs.reference_dialogs import ManufacturerDialog, DistributorDialog
from gui.pages.home_page import HomePage
from gui.pages.machine_page import MachinePage
from gui.pages.maintenance_plan_page import MaintenancePlanPage
from gui.pages.reports_page import ReportsPage
from gui.pages.schedule_page import SchedulePage
from gui.pages.settings_page import SettingsPage
from gui.pages.work_page import WorkPage
from gui.pages.notification_center_page import NotificationCenterPage, ReminderDialog
from services.backup_service import BackupService
from services.notification_service import NotificationService
from services.report_service import ReportService
from services.app_settings import AppSettingsManager
from services.sync_service import SyncService
from gui.dialogs.email_template_wizard import EmailTemplateWizard, DEFAULT_SUBJECT, DEFAULT_BODY
from gui.dialogs.profile_dialog import ProfileDialog
from gui.theme import apply_theme, create_app_icon, create_nav_icon
from services.outlook_service import OutlookService, OutlookIntegrationError
from services.builtin_manufacturers import (
    get_all_manufacturers, get_manufacturer, is_builtin_manufacturer
)


APP_VERSION = "1.0.0"


class FramelessTitleBar(QWidget):
    """Компактная frameless-панель без текста.

    Перетаскивание реализовано вручную, чтобы оно не зависело от
    нестабильного WM_NCLBUTTONDOWN у Qt frameless-окон. При отпускании
    у верхней/левой/правой границы сохраняем привычное Snap-поведение.
    """

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._dragging = False
        self._drag_start_global = None
        self._window_start_pos = None
        self._restore_ratio = 0.5
        self.setObjectName("appTitleBar")
        self.setFixedHeight(28)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 0, 0, 0)
        layout.setSpacing(0)

        icon = QLabel()
        icon.setObjectName("titleBarIcon")
        icon.setPixmap(create_app_icon().pixmap(16, 16))
        icon.setFixedSize(20, 20)
        icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(icon)
        layout.addStretch(1)

        self.min_button = QToolButton()
        self.max_button = QToolButton()
        self.close_button = QToolButton()
        for button, name, label in (
            (self.min_button, "titleMinButton", "—"),
            (self.max_button, "titleMaxButton", "□"),
            (self.close_button, "titleCloseButton", "×"),
        ):
            button.setObjectName(name)
            button.setText(label)
            button.setFixedSize(42, 28)
            button.setCursor(Qt.PointingHandCursor)
            layout.addWidget(button)

        self.min_button.clicked.connect(window.showMinimized)
        self.max_button.clicked.connect(self.toggle_max_restore)
        self.close_button.clicked.connect(window.close)

    def set_title(self, _title):
        # Заголовок окна остаётся системным свойством окна, но текст в
        # собственной рамке намеренно не показываем.
        return

    def toggle_max_restore(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_window_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Qt 6 передаёт перемещение самой Windows. Так сохраняются обычное
            # перетаскивание, Aero Snap и разворачивание у верхнего края.
            handle = self._window.windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                try:
                    if handle.startSystemMove():
                        self._dragging = False
                        event.accept()
                        return
                except Exception:
                    pass

            # Fallback для окружений, где startSystemMove недоступен.
            self._dragging = True
            self._drag_start_global = event.globalPosition().toPoint()
            self._window_start_pos = self._window.pos()
            self._restore_ratio = max(0.08, min(0.92, event.position().x() / max(1, self.width())))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging or not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        global_pos = event.globalPosition().toPoint()
        if self._window.isMaximized():
            normal = self._window.normalGeometry()
            width = max(normal.width(), 900)
            self._window.showNormal()
            self._window.move(
                int(global_pos.x() - width * self._restore_ratio),
                int(global_pos.y() - self.height() / 2),
            )
            self._drag_start_global = global_pos
            self._window_start_pos = self._window.pos()
        else:
            delta = global_pos - self._drag_start_global
            self._window.move(self._window_start_pos + delta)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            global_pos = event.globalPosition().toPoint()
            screen = QApplication.screenAt(global_pos)
            if screen is not None:
                area = screen.availableGeometry()
                edge = 8
                if global_pos.y() <= area.top() + edge:
                    self._window.showMaximized()
                elif global_pos.x() <= area.left() + edge:
                    self._window.showNormal()
                    self._window.setGeometry(
                        area.left(), area.top(), area.width() // 2, area.height()
                    )
                elif global_pos.x() >= area.right() - edge:
                    self._window.showNormal()
                    half = area.width() // 2
                    self._window.setGeometry(
                        area.left() + half, area.top(), area.width() - half, area.height()
                    )
            self.sync_window_state()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_max_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def sync_window_state(self):
        self.max_button.setText("❐" if self._window.isMaximized() else "□")
        self.max_button.setToolTip("Восстановить" if self._window.isMaximized() else "Развернуть")


class MainWindow(QMainWindow):

    def __init__(
        self,
        customer_name,
    ):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint, True)

        self.customer_manager = CustomerManager()

        self.customer_name = (
            self.customer_manager
            .set_active_customer(
                customer_name
            )
        )

        self.repository = Repository(
            customer_name=self.customer_name
        )
        self.report_service = ReportService(self.repository)
        self.app_settings = AppSettingsManager()
        self.app_settings.set_active_customer(self.customer_name)
        self.sync_service = SyncService(self.customer_name, self.repository)
        self.outlook_service = OutlookService()
        self._report_export = None

        self.setWindowTitle(
            "Журнал ТОиР"
        )
        self.setWindowIcon(create_app_icon())

        self.resize(
            1600,
            900,
        )

        self.setMinimumSize(
            1300,
            800,
        )

        self.create_actions()
        self.create_menu()
        self.create_statusbar()
        self.create_pages()
        self.create_central_widget()
        self.connect_signals()
        self._restore_ui_state()

        self.refresh_timer = QTimer(
            self
        )

        self.refresh_timer.timeout.connect(
            self.refresh_home
        )

        self.refresh_timer.start(
            60_000
        )

        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._background_sync)
        self.sync_timer.start(3_000)

        self._shown_system_notification_keys = set()
        self.tray_icon = QSystemTrayIcon(create_app_icon(), self)
        self.tray_icon.setToolTip("Журнал ТОиР")
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()
        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self.process_notification_center)
        self.notification_timer.start(30_000)

        self.load_settings()
        self.apply_header()
        self.refresh_all()

    # ==========================================================
    # UI
    # ==========================================================

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "title_bar"):
            self.title_bar.set_title(title)

    def create_actions(self):
        self.change_customer_action = QAction(
            "Сменить заказчика",
            self,
        )

        self.change_customer_action.triggered.connect(
            self.change_customer
        )

        self.exit_action = QAction(
            "Выход",
            self,
        )

        self.exit_action.triggered.connect(
            self.close
        )

        self.about_action = QAction(
            "О программе",
            self,
        )

        self.about_action.triggered.connect(
            self.show_about
        )

    def create_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu(
            "Файл"
        )

        file_menu.addAction(
            self.change_customer_action
        )
        file_menu.addSeparator()

        file_menu.addAction(
            self.exit_action
        )

        help_menu = menu.addMenu(
            "Справка"
        )

        help_menu.addAction(
            self.about_action
        )

        # В Industrial Premium старую строку «Файл / Справка» не показываем:
        # она визуально выбивалась из нового shell. Действия остаются QAction,
        # а основные команды продублированы в боковой панели.
        menu.setVisible(False)

    def create_pages(self):
        # ------------------------------------------------------------------
        # Industrial Premium navigation.
        # Только два устойчивых состояния: раскрыта или компактная (иконки).
        # Никакого авто-раскрытия по наведению — состояние меняется только
        # пользователем и запоминается между запусками.
        # ------------------------------------------------------------------
        self._sidebar_expanded_width = 244
        self._sidebar_collapsed_width = 68
        self.sidebar_expanded = bool(
            self.app_settings.load().get("ui", {}).get("sidebar_expanded", True)
        )

        self.navigation_container = QWidget()
        self.navigation_container.setObjectName("navPanel")
        self.navigation_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.navigation_container.setMinimumWidth(self._sidebar_expanded_width)
        self.navigation_container.setMaximumWidth(self._sidebar_expanded_width)

        nav_layout = QVBoxLayout(self.navigation_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(5)

        brand = QWidget()
        brand.setObjectName("navBrand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(7, 7, 7, 5)
        brand_layout.setSpacing(2)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.addStretch(1)
        self.sidebar_toggle_button = QToolButton()
        self.sidebar_toggle_button.setObjectName("navControl")
        self.sidebar_toggle_button.setIcon(create_nav_icon("menu", "#C7D6E7", 21))
        self.sidebar_toggle_button.setIconSize(QSize(21, 21))
        self.sidebar_toggle_button.setFixedSize(34, 30)
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        toggle_row.addWidget(self.sidebar_toggle_button, 0, Qt.AlignRight)
        brand_layout.addLayout(toggle_row)

        self.profile_button = QPushButton()
        self.profile_button.setObjectName("profileHeaderButton")
        self.profile_button.setCursor(Qt.PointingHandCursor)
        self.profile_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.profile_button.setMinimumHeight(40)
        self.profile_button.setIcon(create_nav_icon("user", "#C7D6E7", 22))
        self.profile_button.setIconSize(QSize(22, 22))
        self.profile_button.setToolTip("Открыть и изменить данные пользователя")
        brand_layout.addWidget(self.profile_button)
        nav_layout.addWidget(brand)

        self.navigation = QListWidget()
        self.navigation.setSpacing(2)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.navigation.setIconSize(QSize(22, 22))

        self._navigation_map = {}
        navigation_items = [
            ("Главная", 0, False, "home"),
            ("Менеджер задач", 11, False, "bell"),
            ("СПРАВОЧНИКИ", None, True, None),
            ("Техника", 1, False, "equipment"),
            ("Производители", 9, False, "factory"),
            ("Дистрибьюторы", 10, False, "distributor"),
            ("Компоненты", 4, False, "cube"),
            ("РАБОТА С БАЗОЙ ДАННЫХ", None, True, None),
            ("Менеджер простоев", 2, False, "downtime"),
            ("Детализация по машинам", 3, False, "details"),
            ("Планирование ТО", 6, False, "maintenance"),
            ("ОТЧЁТЫ", None, True, None),
            ("График работ", 5, False, "schedule"),
            ("Сводка", 7, False, "chart"),
        ]

        self._nav_items = []
        for text, stack_index, is_header, icon_kind in navigation_items:
            if icon_kind:
                item = QListWidgetItem(create_nav_icon(icon_kind, "#B9C8DC", 22), text)
            else:
                item = QListWidgetItem(text)
            row = self.navigation.count()
            item.setData(Qt.UserRole, text)
            item.setData(Qt.UserRole + 1, bool(is_header))
            item.setData(Qt.UserRole + 2, icon_kind or "")
            item.setToolTip(text if not is_header else "")
            if is_header:
                item.setFlags(Qt.NoItemFlags)
                font = item.font()
                font.setBold(True)
                font.setPointSize(9)
                item.setFont(font)
                item.setForeground(QBrush(QColor("#7188A5")))
            else:
                self._navigation_map[row] = stack_index
            self.navigation.addItem(item)
            self._nav_items.append(item)

        nav_layout.addWidget(self.navigation, 1)

        # Крупные сервисные действия выглядят как обычные пункты навигации.
        self.customer_button = QPushButton("Изменить заказчика")
        self.customer_button.setObjectName("navActionButton")
        self.customer_button.setIcon(create_nav_icon("switch", "#B9C8DC", 25))
        self.customer_button.setIconSize(QSize(25, 25))
        self.customer_button.setMinimumHeight(40)
        self.customer_button.setProperty("navButton", True)
        self.customer_button.setToolTip("Изменить заказчика")
        nav_layout.addWidget(self.customer_button)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setObjectName("navActionButton")
        self.settings_button.setIcon(create_nav_icon("settings", "#B9C8DC", 25))
        self.settings_button.setIconSize(QSize(25, 25))
        self.settings_button.setMinimumHeight(40)
        self.settings_button.setProperty("navButton", True)
        self.settings_button.setToolTip("Настройки")
        nav_layout.addWidget(self.settings_button)

        self.stack = QStackedWidget()
        self.home_page = HomePage()
        self.equipment_page = EquipmentPage()
        self.work_page = WorkPage()
        self.machine_page = MachinePage()
        self.components_page = ComponentsPage()
        self.schedule_page = SchedulePage()
        self.maintenance_plan_page = MaintenancePlanPage()
        self.reports_page = ReportsPage()
        self.settings_page = SettingsPage()
        self.manufacturers_page = ReferencePage("Производители", ["Наименование", "Страна", "Логотип"])
        self.distributors_page = ReferencePage("Дистрибьюторы (поставщики)", ["Наименование организации"])
        self.notification_center_page = NotificationCenterPage()

        for page in (
            self.home_page,
            self.equipment_page,
            self.work_page,
            self.machine_page,
            self.components_page,
            self.schedule_page,
            self.maintenance_plan_page,
            self.reports_page,
            self.settings_page,
            self.manufacturers_page,
            self.distributors_page,
            self.notification_center_page,
        ):
            self.stack.addWidget(page)

        self.navigation.currentRowChanged.connect(self._navigation_changed)
        self.profile_button.clicked.connect(self.open_profile)
        self.customer_button.clicked.connect(self.change_customer)
        self.settings_button.clicked.connect(self.open_settings)
        self.navigation.setCurrentRow(0)

        self.set_sidebar_expanded(self.sidebar_expanded, animate=False, persist=False)

    def _update_navigation_icons(self, selected_row=None):
        if selected_row is None:
            selected_row = self.navigation.currentRow()
        for row, item in enumerate(self._nav_items):
            if bool(item.data(Qt.UserRole + 1)):
                continue
            icon_kind = str(item.data(Qt.UserRole + 2) or "")
            if icon_kind:
                item.setIcon(create_nav_icon(
                    icon_kind,
                    "#FFFFFF" if row == selected_row else "#B9C8DC",
                    22,
                ))

    def _set_nav_collapsed_visuals(self, collapsed):
        self.navigation_container.setProperty("collapsed", bool(collapsed))
        self.navigation_container.style().unpolish(self.navigation_container)
        self.navigation_container.style().polish(self.navigation_container)

        for item in self._nav_items:
            text = str(item.data(Qt.UserRole) or "")
            is_header = bool(item.data(Qt.UserRole + 1))
            if is_header:
                item.setHidden(collapsed)
            else:
                item.setHidden(False)
                if collapsed:
                    item.setText("")
                elif text == "Менеджер задач":
                    badge_count = int(item.data(Qt.UserRole + 3) or 0)
                    item.setText(f"{text}   {badge_count}" if badge_count else text)
                else:
                    item.setText(text)
                item.setTextAlignment(
                    Qt.AlignCenter if collapsed else (Qt.AlignLeft | Qt.AlignVCenter)
                )

        self.profile_button.setText(self._profile_button_text(collapsed))
        self.profile_button.setToolTip(
            self.app_settings.load().get("user", {}).get("full_name", "") or "Мой профиль"
        )

        for button, text in (
            (self.customer_button, "Изменить заказчика"),
            (self.settings_button, "Настройки"),
        ):
            button.setText("" if collapsed else text)
            button.setProperty("collapsedNav", bool(collapsed))
            button.style().unpolish(button)
            button.style().polish(button)

        self.sidebar_toggle_button.setToolTip(
            "Развернуть боковую панель" if collapsed else "Свернуть боковую панель"
        )

    def _profile_button_text(self, collapsed=False):
        # В свёрнутой панели остаётся только понятная иконка пользователя.
        if collapsed:
            return ""
        user = self.app_settings.load().get("user", {})
        full_name = str(user.get("full_name", "") or "").strip()
        return full_name or "Мой профиль"

    def open_profile(self):
        cfg = self.app_settings.load()
        dialog = ProfileDialog(cfg.get("user", {}), self)
        if dialog.exec() != QDialog.Accepted:
            return
        cfg["user"] = dialog.user_data()
        self.app_settings.save(cfg)
        # Синхронизируем форму настроек, приветствие и подписи интерфейса.
        self.load_settings()
        self.refresh_home()
        if hasattr(self, "profile_button"):
            self.profile_button.setText(self._profile_button_text(not self.sidebar_expanded))
            self.profile_button.setToolTip(cfg["user"].get("full_name", "") or "Мой профиль")
        self.status.showMessage("Профиль пользователя сохранён.", 3500)

    def set_sidebar_expanded(self, expanded, animate=True, persist=True):
        expanded = bool(expanded)
        self.sidebar_expanded = expanded
        target = self._sidebar_expanded_width if expanded else self._sidebar_collapsed_width
        self._set_nav_collapsed_visuals(not expanded)

        if animate and self.app_settings.load().get("ui", {}).get("animations", True):
            start = self.navigation_container.width()
            group = QParallelAnimationGroup(self)
            for prop in (b"minimumWidth", b"maximumWidth"):
                animation = QPropertyAnimation(self.navigation_container, prop, group)
                animation.setDuration(190)
                animation.setStartValue(start)
                animation.setEndValue(target)
                animation.setEasingCurve(QEasingCurve.OutCubic)
                group.addAnimation(animation)
            self._sidebar_animation = group
            group.start()
        else:
            self.navigation_container.setMinimumWidth(target)
            self.navigation_container.setMaximumWidth(target)

        if persist:
            self.app_settings.update(ui={"sidebar_expanded": expanded})

    def toggle_sidebar(self):
        self.set_sidebar_expanded(not self.sidebar_expanded)

    def _navigation_changed(self, row):
        stack_index = self._navigation_map.get(row)
        if stack_index is None:
            return
        self.stack.setCurrentIndex(stack_index)
        self._update_navigation_icons(row)
        self._animate_current_page()
        self.page_changed(stack_index)
        self.app_settings.update(ui={"last_page": stack_index})

    def create_central_widget(self):
        central = QWidget()
        central.setObjectName("appShell")
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = FramelessTitleBar(self)
        self.title_bar.set_title(self.windowTitle())
        outer.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("appBody")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.navigation_container)
        layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

    def create_statusbar(self):
        self.status = QStatusBar()
        self.status.setSizeGripEnabled(True)

        self.setStatusBar(
            self.status
        )

        self.status_customer = QLabel()

        self.status_database = QLabel()
        self.status_sync = QLabel()
        self.status_user = QLabel()

        self.status_version = QLabel(
            f"Версия: {APP_VERSION}"
        )

        self.status.addPermanentWidget(
            self.status_customer
        )

        self.status.addPermanentWidget(
            QLabel("|")
        )

        self.status.addPermanentWidget(
            self.status_database
        )

        self.status.addPermanentWidget(QLabel("|"))
        self.status.addPermanentWidget(self.status_sync)
        self.status.addPermanentWidget(QLabel("|"))
        self.status.addPermanentWidget(self.status_user)
        self.status.addPermanentWidget(QLabel("|"))
        self.status.addPermanentWidget(
            self.status_version
        )

        self.update_statusbar()

    # ==========================================================
    # SIGNALS
    # ==========================================================

    def connect_signals(self):
        self.home_page.quick_action_requested.connect(
            self.handle_quick_action
        )
        self.home_page.reminder_completed.connect(self.complete_reminder)
        self.notification_center_page.add_reminder_requested.connect(self.add_reminder)
        self.notification_center_page.edit_reminder_requested.connect(self.edit_reminder)
        self.notification_center_page.delete_reminder_requested.connect(self.delete_reminder)
        self.notification_center_page.complete_reminder_requested.connect(self.complete_reminder)
        self.notification_center_page.refresh_requested.connect(self.refresh_notification_center)

        self.equipment_page.btn_add.clicked.connect(
            self.add_equipment
        )

        self.equipment_page.btn_edit.clicked.connect(
            self.edit_equipment
        )
        self.equipment_page.table.itemDoubleClicked.connect(
            lambda _item: self.edit_equipment()
        )

        self.equipment_page.btn_delete.clicked.connect(
            self.delete_equipment
        )
        self.equipment_page.btn_export_pdf.clicked.connect(self.export_equipment_pdf)
        self.equipment_page.manufacturer_filter.currentIndexChanged.connect(self.refresh_equipment)
        self.equipment_page.distributor_filter.currentIndexChanged.connect(self.refresh_equipment)
        self.equipment_page.service_filter.currentIndexChanged.connect(self.refresh_equipment)
        self.equipment_page.hours_min.valueChanged.connect(self.refresh_equipment)
        self.equipment_page.hours_max.valueChanged.connect(self.refresh_equipment)
        self.equipment_page.btn_reset_filters.clicked.connect(self.reset_equipment_filters)
        self.manufacturers_page.btn_add.clicked.connect(self.add_manufacturer)
        self.manufacturers_page.btn_edit.clicked.connect(self.edit_manufacturer)
        self.manufacturers_page.btn_delete.clicked.connect(self.delete_manufacturer)
        self.manufacturers_page.table.itemDoubleClicked.connect(
            lambda _item: self.edit_manufacturer()
        )
        self.manufacturers_page.table.itemSelectionChanged.connect(
            self._update_manufacturer_actions
        )
        self.distributors_page.btn_add.clicked.connect(self.add_distributor)
        self.distributors_page.btn_edit.clicked.connect(self.edit_distributor)
        self.distributors_page.btn_delete.clicked.connect(self.delete_distributor)
        self.distributors_page.table.itemDoubleClicked.connect(
            lambda _item: self.edit_distributor()
        )

        self.equipment_page.search.textChanged.connect(
            self.refresh_equipment
        )

        self.equipment_page.status_filter.currentTextChanged.connect(
            self.refresh_equipment
        )

        self.work_page.btn_add.clicked.connect(
            self.add_work
        )

        self.work_page.btn_edit.clicked.connect(
            self.edit_work
        )
        self.work_page.table.itemDoubleClicked.connect(
            lambda _item: self.edit_work()
        )

        self.work_page.btn_delete.clicked.connect(
            self.delete_work
        )

        self.work_page.btn_refresh.clicked.connect(
            self.refresh_work
        )

        self.work_page.search.textChanged.connect(
            self.refresh_work
        )

        self.work_page.type_filter.currentTextChanged.connect(
            self.refresh_work
        )

        self.work_page.progress_filter.currentTextChanged.connect(
            self.refresh_work
        )

        self.work_page.report_filter.currentTextChanged.connect(
            self.refresh_work
        )

        self.work_page.period_filter.currentTextChanged.connect(
            self.refresh_work
        )

        self.work_page.btn_reset_filters.clicked.connect(
            self.reset_work_filters
        )

        self.settings_page.btn_logo.clicked.connect(
            self.select_logo
        )

        self.settings_page.btn_save.clicked.connect(
            self.save_settings
        )

        self.settings_page.btn_cancel.clicked.connect(
            self.load_settings
        )
        self.settings_page.btn_server_root.clicked.connect(lambda: self._select_settings_folder(self.settings_page.server_root))
        self.settings_page.btn_local_root.clicked.connect(lambda: self._select_settings_folder(self.settings_page.local_root))
        self.settings_page.btn_backup_root.clicked.connect(lambda: self._select_settings_folder(self.settings_page.backup_root))
        self.settings_page.btn_test_server.clicked.connect(self.test_server_connection)
        self.settings_page.btn_sync_now.clicked.connect(lambda: self.sync_now(show_message=True, force=True))
        self.settings_page.btn_backup_now.clicked.connect(self._manual_backup)
        self.settings_page.btn_check_db.clicked.connect(self._check_database_integrity)
        self.settings_page.btn_email_template.clicked.connect(self.configure_email_template)
        self.settings_page.email_report_combo.currentIndexChanged.connect(
            lambda *_: self._refresh_email_settings_status()
        )

        self.machine_page.equipment_selected.connect(
        self.load_machine_details
        )

        self.machine_page.btn_components.clicked.connect(
            self.open_machine_components
        )
        self.components_page.btn_add.clicked.connect(self.add_component)
        self.components_page.btn_edit.clicked.connect(self.edit_component)
        self.components_page.btn_delete.clicked.connect(self.delete_component)
        self.components_page.btn_refresh.clicked.connect(self.refresh_components)
        self.components_page.search.textChanged.connect(self.refresh_components)
        self.components_page.equipment_filter.currentIndexChanged.connect(self.refresh_components)
        self.components_page.table.itemDoubleClicked.connect(lambda _item: self.edit_component())

        self.schedule_page.period_changed.connect(
            self.refresh_schedule
        )
        self.schedule_page.export_pdf_requested.connect(self.export_daily_work_summary_pdf)
        self.schedule_page.email_requested.connect(self.email_daily_work_summary)

        self.reports_page.btn_generate.clicked.connect(self.generate_selected_report)
        self.reports_page.btn_export_excel.clicked.connect(self.export_selected_report_excel)
        self.reports_page.btn_export_pdf.clicked.connect(self.export_selected_report_pdf)
        self.reports_page.btn_email.clicked.connect(self.email_selected_report)
        self.reports_page.btn_print.clicked.connect(self.print_selected_report)
        self.reports_page.report_list.itemDoubleClicked.connect(
            lambda _item: self.generate_selected_report()
        )

        self.maintenance_plan_page.plan_requested.connect(
            self.plan_maintenance
        )
        self.maintenance_plan_page.reschedule_requested.connect(
            self.reschedule_maintenance
        )
        self.maintenance_plan_page.cancel_requested.connect(
            self.cancel_maintenance_plan
        )
        self.maintenance_plan_page.start_requested.connect(
            self.start_maintenance_plan
        )
        self.maintenance_plan_page.complete_requested.connect(
            self.complete_maintenance_plan
        )

    # ==========================================================
    # HEADER
    # ==========================================================

    def apply_header(self):
        organization = (
            self.customer_manager
            .get_organization_name()
        )

        logo_path = (
            self.customer_manager
            .get_organization_logo()
        )

        if organization:
            self.setWindowTitle(
                f"Журнал ТОиР — {organization}"
            )
        else:
            self.setWindowTitle(
                "Журнал ТОиР"
            )

        organization_text = (
            organization
            if organization
            else "Организация не указана"
        )

        customer_text = (
            self.customer_name
            if self.customer_name
            else "Заказчик не выбран"
        )

        ui_config = self.app_settings.load()
        user_full_name = str(ui_config.get("user", {}).get("full_name", "") or "")
        if hasattr(self.home_page, "set_user_name"):
            self.home_page.set_user_name(user_full_name)
        if hasattr(self.home_page, "apply_visual_theme"):
            self.home_page.apply_visual_theme(ui_config.get("ui", {}).get("theme", "light"))
        for page in (getattr(self, "schedule_page", None), getattr(self, "reports_page", None)):
            if page is not None and hasattr(page, "apply_visual_theme"):
                page.apply_visual_theme(ui_config.get("ui", {}).get("theme", "light"))

        if hasattr(self, "profile_button"):
            self.profile_button.setText(self._profile_button_text(not self.sidebar_expanded))
            user_full = str(self.app_settings.load().get("user", {}).get("full_name", "") or "")
            self.profile_button.setToolTip(user_full or "Мой профиль")

        for attribute in (
            "organization_label",
            "organization",
        ):
            widget = getattr(
                self.home_page,
                attribute,
                None,
            )

            if widget is not None:
                widget.setText(
                    organization_text
                )

        for attribute in (
            "customer_label",
            "customer",
        ):
            widget = getattr(
                self.home_page,
                attribute,
                None,
            )

            if widget is not None:
                widget.setText(
                    f"Заказчик: {customer_text}"
                )

        if hasattr(self.home_page, "set_logo"):
            self.home_page.set_logo(logo_path)

    # ==========================================================
    # REFRESH
    # ==========================================================

    def refresh_all(self):
        self.refresh_equipment()
        self.refresh_work()
        self.refresh_maintenance_plan()
        self.refresh_components()
        self.refresh_home()
        self.apply_header()
        self.update_statusbar()

    def refresh_home(self):
        statistics = (
            self.repository
            .get_dashboard_statistics()
        )

        customer_work = (
            self.repository
            .get_customer_work_count()
        )

        self.home_page.set_statistics(
            statistics[
                "total_equipment"
            ],
            customer_work,
            statistics[
                "active_work"
            ],
            statistics[
                "components"
            ],
        )

        # Возвращаем на Главную текущие ремонты и простои отдельным блоком.
        self.home_page.clear_downtimes()
        active_rows = list(self.repository.get_active_work())
        if not active_rows:
            self.home_page.add_downtime("Текущих ремонтов и простоев нет.")
        else:
            for row in active_rows[:6]:
                # get_active_work() возвращает поля work_records (repair_type)
                # и equipment_status. Ключей work_type/status в этом SELECT нет.
                # Используем реальные имена колонок, чтобы sqlite3.Row не
                # выбрасывал IndexError при запуске.
                work_type = str(row["repair_type"] or "Работа")
                model = str(row["model"] or "")
                garage = str(row["garage_number"] or "")
                equipment_status = str(row["equipment_status"] or "")
                suffix = f" · {equipment_status}" if equipment_status else ""
                self.home_page.add_downtime(
                    f"{model} №{garage} · {work_type}{suffix}"
                )

        service = NotificationService(repository=self.repository)
        notifications = service.get_notifications()

        self.home_page.clear_notifications()
        if not notifications:
            self.home_page.add_notification("Уведомлений нет.")
        else:
            for notification in notifications[:6]:
                self.home_page.add_notification(notification["text"])

        self.home_page.clear_reminders()
        reminders = list(service.get_reminders(include_completed=False, limit=6))
        if not reminders:
            self.home_page.add_reminder(0, "Активных напоминаний нет.", "")
        else:
            now = datetime.now()
            repeat_labels = {
                "once": "Один раз", "daily": "Ежедневно",
                "weekdays": "По рабочим дням", "weekly": "Еженедельно",
                "monthly": "Ежемесячно",
            }
            for reminder in reminders:
                try:
                    due = datetime.fromisoformat(str(reminder["remind_at"]))
                    when = due.strftime("%d.%m.%Y · %H:%M")
                    overdue = due < now
                except Exception:
                    when = str(reminder["remind_at"] or "")
                    overdue = False
                rule = str(reminder["repeat_rule"] or "once")
                if rule != "once":
                    when += f" · {repeat_labels.get(rule, rule)}"
                self.home_page.add_reminder(
                    reminder["id"], reminder["title"], when, overdue
                )

        self.refresh_notification_badge(notifications, reminders)
        if hasattr(self, "notification_center_page"):
            self.notification_center_page.set_notifications(notifications)
            self.notification_center_page.set_reminders(service.get_reminders(include_completed=True))

        self.apply_header()
        self.update_statusbar()

    def _service_status_for(self, row):
        from datetime import date
        years=float(row["warranty_years"] or 0); limit=float(row["warranty_hours"] or 0)
        start=float(row["warranty_start_hours"] or 0); current=float(row["current_hours"] or 0)
        valid=True; has=False
        if years>0:
            has=True
            try:
                d=date.fromisoformat(str(row["commissioning_date"])[:10])
                months=int(round(years*12)); y=d.year+(d.month-1+months)//12; m=(d.month-1+months)%12+1
                import calendar
                end=date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
                valid=valid and date.today()<end
            except Exception: valid=False
        if limit>0:
            has=True; valid=valid and current<(start+limit)
        return "Гарантийное" if has and valid else "Постгарантийное"

    def _reference_name(self, rows, item_id):
        for r in rows:
            if r["id"]==item_id:return r["name"]
        return ""

    def reset_equipment_filters(self):
        self.equipment_page.search.clear(); self.equipment_page.status_filter.setCurrentIndex(0)
        self.equipment_page.manufacturer_filter.setCurrentIndex(0); self.equipment_page.distributor_filter.setCurrentIndex(0)
        self.equipment_page.service_filter.setCurrentIndex(0); self.equipment_page.hours_min.setValue(0); self.equipment_page.hours_max.setValue(0)
        self.refresh_equipment()

    def refresh_reference_pages(self):
        mans = get_all_manufacturers(self.repository)
        dists = self.repository.get_distributors()
        manufacturer_rows = []
        current_theme = str(QApplication.instance().property("appTheme") or "light").lower()
        for row in mans:
            logo_path = row.get("logo_path", "")
            if current_theme == "dark" and row.get("logo_dark_path"):
                logo_path = row.get("logo_dark_path")
            manufacturer_rows.append((
                [
                    row["name"],
                    row["country"],
                    {"text": "", "icon": logo_path},
                ],
                row["id"],
                {"builtin": is_builtin_manufacturer(row["id"])},
            ))
        self.manufacturers_page.set_rows(manufacturer_rows)
        self.distributors_page.set_rows([([r["name"]], r["id"]) for r in dists])
        self._update_manufacturer_actions()

        for combo, rows, label in [
            (self.equipment_page.manufacturer_filter, mans, "Все производители"),
            (self.equipment_page.distributor_filter, dists, "Все дистрибьюторы"),
        ]:
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, None)
            for r in rows:
                combo.addItem(r["name"], r["id"])
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _selected_manufacturer_id(self):
        row = self.manufacturers_page.table.currentRow()
        if row < 0:
            return None
        item = self.manufacturers_page.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _update_manufacturer_actions(self):
        item_id = self._selected_manufacturer_id()
        builtin = is_builtin_manufacturer(item_id)
        has_selection = item_id is not None
        self.manufacturers_page.btn_edit.setEnabled(has_selection and not builtin)
        self.manufacturers_page.btn_delete.setEnabled(has_selection and not builtin)
        hint = "Встроенный производитель нельзя изменить или удалить." if builtin else ""
        self.manufacturers_page.btn_edit.setToolTip(hint)
        self.manufacturers_page.btn_delete.setToolTip(hint)

    def add_manufacturer(self):
        d = ManufacturerDialog(self)
        if d.exec():
            try:
                self.repository.add_manufacturer(*d.data())
                self.refresh_reference_pages()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def edit_manufacturer(self):
        item_id = self._selected_manufacturer_id()
        if item_id is None:
            return
        if is_builtin_manufacturer(item_id):
            QMessageBox.information(
                self, "Производитель",
                "Это встроенный производитель. Его наименование, страна и логотип защищены от изменения."
            )
            return
        source = next((r for r in self.repository.get_manufacturers() if r["id"] == item_id), None)
        if not source:
            return
        d = ManufacturerDialog(self, source["name"], source["country"], source["logo_path"])
        if d.exec():
            try:
                self.repository.update_manufacturer(item_id, *d.data())
                self.refresh_reference_pages()
                self.refresh_equipment()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def delete_manufacturer(self):
        item_id = self._selected_manufacturer_id()
        if item_id is None:
            return
        if is_builtin_manufacturer(item_id):
            QMessageBox.information(
                self, "Производитель",
                "Встроенные производители являются частью программы и не удаляются из базы."
            )
            return
        try:
            self.repository.delete_manufacturer(item_id)
            self.refresh_reference_pages()
        except Exception as e:
            QMessageBox.warning(self, "Удаление", str(e))

    def add_distributor(self):
        d=DistributorDialog(self)
        if d.exec():
            try:self.repository.add_distributor(d.data()); self.refresh_reference_pages()
            except Exception as e:QMessageBox.warning(self,"Ошибка",str(e))
    def edit_distributor(self):
        row=self.distributors_page.table.currentRow()
        if row<0:return
        item_id=self.distributors_page.table.item(row,0).data(Qt.UserRole)
        source=next((r for r in self.repository.get_distributors() if r["id"]==item_id),None)
        if not source:return
        d=DistributorDialog(self,source["name"])
        if d.exec():
            try:self.repository.update_distributor(item_id,d.data()); self.refresh_reference_pages(); self.refresh_equipment()
            except Exception as e:QMessageBox.warning(self,"Ошибка",str(e))
    def delete_distributor(self):
        row=self.distributors_page.table.currentRow()
        if row<0:return
        try:self.repository.delete_distributor(self.distributors_page.table.item(row,0).data(Qt.UserRole)); self.refresh_reference_pages()
        except Exception as e:QMessageBox.warning(self,"Удаление",str(e))

    def refresh_equipment(self):
        self.refresh_reference_pages()
        text=self.equipment_page.search.text().strip().casefold()
        status=self.equipment_page.status_filter.currentText()
        man_id=self.equipment_page.manufacturer_filter.currentData()
        dist_id=self.equipment_page.distributor_filter.currentData()
        service=self.equipment_page.service_filter.currentText()
        hmin=self.equipment_page.hours_min.value(); hmax=self.equipment_page.hours_max.value()
        mans=get_all_manufacturers(self.repository); dists=self.repository.get_distributors()
        rows=[]
        for row in self.repository.get_all_equipment():
            hay=" ".join(str(row[k] or "") for k in ("model","serial_number","garage_number","registration_number")).casefold()
            if text and text not in hay:continue
            if status!="Все" and row["status"]!=status:continue
            if man_id is not None and row["manufacturer_id"]!=man_id:continue
            if dist_id is not None and row["distributor_id"]!=dist_id:continue
            ss=self._service_status_for(row)
            if service!="Все по гарантии" and ss!=service:continue
            hours=float(row["current_hours"] or 0)
            if hours<hmin or (hmax>0 and hours>hmax):continue
            rows.append(row)
        self.equipment_page.clear()
        for row in rows:
            self.equipment_page.add_equipment(
                row["model"],row["serial_number"],row["garage_number"],row["registration_number"] or "",
                row["manufacture_year"] or "",row["current_hours"] or 0,row["status"] or "",row["note"] or "",
                self._reference_name(mans,row["manufacturer_id"]),self._reference_name(dists,row["distributor_id"]),self._service_status_for(row))
            item=self.equipment_page.table.item(self.equipment_page.table.rowCount()-1,0)
            if item:item.setData(Qt.UserRole,row["id"])

    def export_equipment_pdf(self):
        path,_=QFileDialog.getSaveFileName(self,"Выгрузить реестр техники","Реестр_техники.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        table=self.equipment_page.table
        headers=[table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        rows=[]
        for r in range(table.rowCount()):
            rows.append([table.item(r,c).text() if table.item(r,c) else "" for c in range(table.columnCount())])
        import html
        body="".join("<tr>"+"".join(f"<td>{html.escape(v)}</td>" for v in row)+"</tr>" for row in rows)
        head="".join(f"<th>{html.escape(v)}</th>" for v in headers)
        doc=QTextDocument(); doc.setHtml(f"<h1>Реестр техники</h1><p>Дата формирования: {QDate.currentDate().toString('dd.MM.yyyy')}</p><table border='1' cellspacing='0' cellpadding='4'><tr>{head}</tr>{body}</table>")
        printer=QPrinter(QPrinter.HighResolution); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.A4)); printer.setPageOrientation(QPageLayout.Landscape); doc.print_(printer)
        self._open_exported_file(path)

    def reset_work_filters(self):
        """Сбрасывает менеджер к наиболее полезному рабочему виду."""
        widgets = (
            self.work_page.search,
            self.work_page.type_filter,
            self.work_page.progress_filter,
            self.work_page.report_filter,
            self.work_page.period_filter,
        )
        for widget in widgets:
            widget.blockSignals(True)

        try:
            self.work_page.search.clear()
            self.work_page.type_filter.setCurrentText("Все типы работ")
            self.work_page.progress_filter.setCurrentText("В работе")
            self.work_page.report_filter.setCurrentText("Все отчёты")
            self.work_page.period_filter.setCurrentText("Все даты")
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self.refresh_work()

    def refresh_work(self):
        text = self.work_page.search.text().strip()

        repair_type_text = self.work_page.type_filter.currentText()
        repair_type_aliases = {
            "Аварийный ремонт": ("Аварийный", "Аварийный ремонт"),
            "Плановый ремонт": ("Плановый", "Плановый ремонт"),
            "ТО": ("ТО", "Плановые ТО"),
            "Простой": ("Простой",),
            "Работы заказчика": ("Работы заказчика", "Воздействия Полюс"),
            "Мониторинг состояния": ("Мониторинг состояния",),
            "Модернизация": (
                "Модернизация",
                "Модернизация/сборка/гарантия",
                "Модернизация / сборка / гарантия",
            ),
            "Будущие работы": ("Будущие работы", "Планируемые работы"),
        }
        repair_type = repair_type_aliases.get(repair_type_text)

        progress = self.work_page.progress_filter.currentText()
        if progress == "В работе":
            in_progress = True
        elif progress == "Завершено":
            in_progress = False
        else:
            in_progress = None

        report_mode = self.work_page.report_filter.currentText()
        requires_report = None
        report_completed = None
        if report_mode == "Требуется отчёт":
            requires_report = True
        elif report_mode == "Отчёт не требуется":
            requires_report = False
        elif report_mode == "Отчёт выполнен":
            report_completed = True
        elif report_mode == "Отчёт не выполнен":
            requires_report = True
            report_completed = False

        date_from = None
        date_to = None
        period = self.work_page.period_filter.currentText()
        today = QDate.currentDate()

        if period == "Сегодня":
            date_from = today
            date_to = today
        elif period == "Последние 7 дней":
            date_from = today.addDays(-6)
            date_to = today
        elif period == "Последние 30 дней":
            date_from = today.addDays(-29)
            date_to = today
        elif period == "Текущий месяц":
            date_from = QDate(today.year(), today.month(), 1)
            date_to = today
        elif period == "Текущий год":
            date_from = QDate(today.year(), 1, 1)
            date_to = today

        if date_from is not None:
            date_from = date_from.toString("yyyy-MM-dd")
        if date_to is not None:
            date_to = date_to.toString("yyyy-MM-dd")

        rows = self.repository.filter_work(
            text=text,
            repair_type=repair_type,
            in_progress=in_progress,
            requires_report=requires_report,
            report_completed=report_completed,
            date_from=date_from,
            date_to=date_to,
        )

        self.work_page.clear()

        for row in rows:
            self.work_page.add_work(
                row["request_number"] or "",
                row["model"],
                row["garage_number"],
                row["repair_type"] or "",
                row["date_start"] or "",
                row["date_end"] or "",
                bool(row["in_progress"]),
                row["machine_hours"] or 0,
                bool(row["requires_report"]),
                bool(row["report_completed"]),
            )

            table_row = self.work_page.table.rowCount() - 1
            item = self.work_page.table.item(table_row, 0)
            if item:
                item.setData(Qt.UserRole, row["id"])

    def page_changed(
        self,
        index,
    ):
        if index == 0:
            self.refresh_home()

        elif index == 1:
            self.refresh_equipment()

        elif index == 2:
            self.refresh_work()

        elif index == 3:
            self.refresh_machine_page()

        elif index == 5:
            self.refresh_schedule()

        elif index == 6:
            self.refresh_maintenance_plan()

        elif index == 11:
            self.refresh_notification_center()

    def refresh_machine_page(self):
        equipment = (
            self.repository
            .get_all_equipment()
        )

        self.machine_page.set_equipment(
            equipment
        )

        equipment_id = (
            self.machine_page
            .get_selected_equipment_id()
        )

        if equipment_id is not None:
            self.load_machine_details(
                equipment_id
            )  

    def refresh_schedule(self):
        date_from, date_to = (
            self.schedule_page
            .get_period()
        )

        equipment = (
            self.repository
            .get_all_equipment()
        )

        work = (
            self.repository
            .get_work_for_period(
                date_from=date_from,
                date_to=date_to,
            )
        )

        daily = self.repository.get_work_daily_for_period(date_from, date_to)
        self.schedule_page.build_schedule(equipment_rows=equipment, work_rows=work, daily_rows=daily)

    def _create_daily_work_summary_pdf(self, output_path=None, open_after=True, show_message=True):
        """Экспорт ежедневной сводки в PDF.

        PDF намеренно повторяет экранный «График работ»: слева три
        фиксированные колонки, справа календарь. Источник данных —
        семантический снимок двух таблиц SchedulePage. Тема приложения
        (светлая/тёмная) на PDF не влияет: фон отчёта всегда белый.
        """
        from datetime import date, timedelta, datetime
        from pathlib import Path

        from PySide6.QtCore import Qt, QRectF, QMarginsF, QSizeF
        from PySide6.QtGui import (
            QColor, QFont, QFontMetricsF, QPainter, QPen, QBrush,
            QPageLayout, QPageSize, QPixmap,
        )
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        date_from, date_to = self.schedule_page.get_period()
        start_date = date.fromisoformat(date_from)
        end_date = date.fromisoformat(date_to)
        # Дата отчёта — фактическая дата формирования PDF, а не конец выбранного периода.
        report_day = datetime.now().date()
        report_date = report_day.strftime("%d.%m.%Y")

        dates = []
        cursor = start_date
        while cursor <= end_date:
            dates.append(cursor)
            cursor += timedelta(days=1)

        # Берём именно то, что построено в двух таблицах графика на экране.
        snapshot = self.schedule_page.get_schedule_snapshot()
        snapshot_dates = list(snapshot.get("dates", []) or [])
        if snapshot_dates != dates:
            self.refresh_schedule()
            snapshot = self.schedule_page.get_schedule_snapshot()
            snapshot_dates = list(snapshot.get("dates", []) or [])

        schedule_rows = list(snapshot.get("rows", []) or [])
        fixed_rows = int(snapshot.get("fixed_row_count", 0) or 0)
        calendar_rows = int(snapshot.get("calendar_row_count", 0) or 0)
        calendar_cols = int(snapshot.get("calendar_column_count", 0) or 0)
        snapshot_valid = (
            snapshot_dates == dates
            and fixed_rows == calendar_rows == len(schedule_rows)
            and calendar_cols == len(snapshot_dates)
            and all(len(row.get("cells", [])) == len(snapshot_dates) for row in schedule_rows)
        )
        if not snapshot_valid:
            QMessageBox.critical(
                self,
                "Ежедневная сводка",
                "Левая и календарная таблицы графика рассинхронизированы. "
                "Нажмите «Обновить» и повторите экспорт.",
            )
            return

        works = self.repository.get_work_for_period(date_from, date_to)
        daily = self.repository.get_work_daily_for_period(date_from, date_to)

        # Ежедневная сводка показывает только технику, у которой в выбранном
        # периоде есть работа / ТО / простой ИЛИ запланированная будущая работа.
        # Полностью пустые строки всего парка в PDF не выводятся.
        STATUS_ORDER = [
            "Аварийный ремонт",
            "Плановый ремонт",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
            "Простой",
            "ТО",
            "Будущие работы",
        ]
        STATUS_HEX = {
            "Аварийный ремонт": "#E05258",
            "Плановый ремонт": "#A87955",
            "Работы заказчика": "#8F67BC",
            # Точные цвета легенды исходного Excel.
            "Мониторинг состояния": "#FFFF00",
            "Модернизация": "#00B0F0",
            "Простой": "#B8BDC4",
            "ТО": "#56B36B",
            "Будущие работы": "#EE9B35",
        }

        def normalized_status(raw):
            return self.schedule_page.normalize_status(raw)

        # Состояния ячеек храним отдельно от визуального цвета Qt.
        # PDF никогда не читает background()/QBrush экранной темы.
        status_matrix = []
        for machine in schedule_rows:
            row_statuses = []
            for cell in machine.get("cells", []):
                status = normalized_status(cell.get("status", ""))
                row_statuses.append(status if status in STATUS_ORDER else "")
            status_matrix.append(row_statuses)

        # В PDF не нужен весь парк с пустыми строками. Оставляем только
        # машины, у которых в выбранном периоде есть хотя бы один день
        # работы / ТО / простоя или будущая запланированная работа.
        filtered_schedule = [
            (machine, statuses)
            for machine, statuses in zip(schedule_rows, status_matrix)
            if any(statuses)
        ]
        schedule_rows = [item[0] for item in filtered_schedule]
        status_matrix = [item[1] for item in filtered_schedule]
        active_equipment_ids = {
            machine.get("equipment_id")
            for machine in schedule_rows
            if machine.get("equipment_id") is not None
        }

        # Фактическая дневная хронология нужна для завершённых/текущих работ.
        # Будущие планы добавляются ниже отдельно из work_records, потому что
        # ReportService намеренно не считает их фактической эксплуатацией.
        actual_facts = [
            fact for fact in self.report_service.get_daily_timeline(date_from, date_to)
            if fact.get("state") in STATUS_ORDER
            and fact.get("equipment_id") in active_equipment_ids
        ]
        actual_work_ids = {fact.get("work_id") for fact in actual_facts}
        actual_day_keys = {
            (fact.get("work_id"), fact.get("date").isoformat())
            for fact in actual_facts
            if fact.get("work_id") is not None and fact.get("date") is not None
        }

        def source_value(row, key, default=None):
            try:
                value = row[key]
            except Exception:
                return default
            return default if value is None else value

        def is_future_plan(work):
            state = normalized_status(source_value(work, "repair_type", ""))
            if state == "Будущие работы":
                return True
            try:
                work_start = date.fromisoformat(str(source_value(work, "date_start", ""))[:10])
            except Exception:
                work_start = None
            if work_start is not None and work_start > date.today():
                return True
            is_planned = bool(source_value(work, "is_planned", 0))
            is_started = bool(source_value(work, "is_started", 0))
            return state == "ТО" and is_planned and not is_started

        future_work_ids = {
            source_value(work, "id")
            for work in works
            if source_value(work, "equipment_id") in active_equipment_ids
            and is_future_plan(work)
        }
        included_work_ids = actual_work_ids | future_work_ids

        works = [
            work for work in works
            if source_value(work, "id") in included_work_ids
        ]
        daily = [
            row for row in daily
            if (
                (
                    source_value(row, "work_id"),
                    str(source_value(row, "work_date", ""))[:10],
                ) in actual_day_keys
                or source_value(row, "work_id") in future_work_ids
            )
        ]

        # Показатели для верхних карточек ежедневной сводки.
        # «Всего техники» повторяет главную страницу и включает весь реестр,
        # а КТГ/ремонты/работы заказчика считаются именно на дату отчёта.
        try:
            total_equipment_kpi = len(list(self.repository.get_all_equipment()))
        except Exception:
            total_equipment_kpi = 0
        try:
            day_ktg = self.report_service.get_ktg(
                report_day.isoformat(), report_day.isoformat()
            )
        except Exception:
            day_ktg = {}
        customer_work_kpi = int(day_ktg.get("customer_work_equipment", 0) or 0)
        active_repairs_kpi = int(day_ktg.get("unavailable_equipment", 0) or 0)
        ktg_percent_kpi = float(day_ktg.get("ktg_percent", 0.0) or 0.0)

        default_name = f"Ежедневная сводная по работам ({report_date}).pdf"
        if output_path:
            path = str(output_path)
        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Ежедневная сводка по работам",
                default_name,
                "PDF (*.pdf)",
            )
            if not path:
                return None
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # График в ежедневной сводке НЕ переносим на следующую строку.
        # Для длинного периода PDF получает динамически широкую страницу:
        # это сохраняет все даты в одной непрерывной календарной таблице и
        # не превращает подписи в микроскопический текст.
        BASE_PAGE_W = 1120.0
        PAGE_H = 760.0
        FIXED_SCHEDULE_W = 142.0 + 108.0 + 82.0
        MIN_DAY_W = 52.0
        SIDE_PADDING = 32.0
        schedule_required_w = SIDE_PADDING + FIXED_SCHEDULE_W + max(1, len(snapshot_dates)) * MIN_DAY_W
        PAGE_W = max(BASE_PAGE_W, schedule_required_w)

        # A4 landscape = 297 мм. Увеличиваем только ширину страницы
        # пропорционально логической ширине отчёта, высоту оставляем A4.
        page_width_mm = 297.0 * (PAGE_W / BASE_PAGE_W)
        page_height_mm = 210.0

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        # Передаём custom-size в «портретной» форме и разворачиваем layout:
        # так Qt стабильно получает итоговый лист page_width_mm × 210 мм.
        printer.setPageSize(
            QPageSize(
                QSizeF(page_height_mm, page_width_mm),
                QPageSize.Millimeter,
                "DailyScheduleWide",
            )
        )
        printer.setPageOrientation(QPageLayout.Landscape)
        printer.setPageMargins(QMarginsF(7, 7, 7, 7), QPageLayout.Millimeter)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "PDF", "Не удалось открыть PDF для записи.")
            return

        try:
            page = printer.pageRect(QPrinter.DevicePixel)
            painter.setViewport(
                int(round(page.x())),
                int(round(page.y())),
                max(1, int(round(page.width()))),
                max(1, int(round(page.height()))),
            )
            painter.setWindow(0, 0, int(PAGE_W), int(PAGE_H))

            LEFT, RIGHT = 16.0, PAGE_W - 16.0
            CONTENT_W = RIGHT - LEFT
            BOTTOM = PAGE_H - 28.0

            C_WHITE = QColor("#FFFFFF")
            C_NAVY = QColor("#102A4C")
            C_NAVY_2 = QColor("#163A62")
            C_BLUE = QColor("#2F6FC6")
            C_TEXT = QColor("#17263A")
            C_MUTED = QColor("#718096")
            C_LINE = QColor("#D5DEE8")
            C_LIGHT = QColor("#F7F9FC")
            C_LIGHT_BLUE = QColor("#EAF3FF")
            C_VIOLET = QColor("#7657D5")
            C_AMBER = QColor("#D9871B")
            C_GREEN = QColor("#3A9F5F")

            # Явно белый фон страницы. PDF не наследует dark theme приложения.
            painter.fillRect(QRectF(0, 0, PAGE_W, PAGE_H), QBrush(C_WHITE))

            def qfont(size, bold=False):
                font = QFont("Segoe UI")
                font.setPixelSize(max(1, int(round(size))))
                font.setBold(bold)
                return font

            def draw_text(rect, text, size=9, bold=False, color=C_TEXT,
                          align=Qt.AlignLeft | Qt.AlignVCenter, wrap=False):
                painter.save()
                painter.setFont(qfont(size, bold))
                painter.setPen(QPen(color))
                painter.setBrush(Qt.NoBrush)
                flags = align | (Qt.TextWordWrap if wrap else Qt.TextSingleLine)
                painter.drawText(rect, flags, str(text or ""))
                painter.restore()

            def fill_rect(rect, color):
                painter.save()
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawRect(rect)
                painter.restore()

            def stroke_rect(rect, color=C_LINE, width=1):
                # ВАЖНО: drawRect() рисует и кистью, и пером. В старом коде
                # активная кисть от KPI/диаграммы повторно заливала все ячейки
                # фиолетово-синим. Здесь кисть всегда выключена.
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, width))
                painter.drawRect(rect)
                painter.restore()

            def rounded(rect, radius=7, fill=C_WHITE, border=C_LINE, width=1):
                painter.save()
                painter.setPen(QPen(border, width))
                painter.setBrush(QBrush(fill))
                painter.drawRoundedRect(rect, radius, radius)
                painter.restore()

            def status_color(status):
                return QColor(STATUS_HEX.get(status, "#FFFFFF"))

            def status_text_color(status):
                if status in ("Мониторинг состояния", "Модернизация", "Простой"):
                    return C_TEXT
                return C_WHITE

            def text_height(text, width, size=9, bold=False):
                font = qfont(size, bold)
                fm = QFontMetricsF(font)
                rect = fm.boundingRect(
                    QRectF(0, 0, max(1.0, width), 10000),
                    Qt.TextWordWrap,
                    str(text or ""),
                )
                return max(fm.height(), rect.height())

            page_no = 0
            y = 0.0

            def draw_footer():
                footer_y = PAGE_H - 19
                painter.save()
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(C_LINE, 1))
                painter.drawLine(LEFT, footer_y - 5, RIGHT, footer_y - 5)
                painter.restore()
                draw_text(
                    QRectF(LEFT, footer_y, 600, 12),
                    f"Данные актуальны на {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    7.3,
                    False,
                    C_MUTED,
                )
                draw_text(
                    QRectF(RIGHT - 130, footer_y, 130, 12),
                    f"Страница {page_no}",
                    7.3,
                    False,
                    C_MUTED,
                    Qt.AlignRight | Qt.AlignVCenter,
                )

            def new_page(first=False):
                nonlocal page_no, y
                if not first:
                    draw_footer()
                    printer.newPage()
                    # QPrinter создаёт белую страницу, но заполняем явно,
                    # чтобы результат не зависел от состояния QPainter.
                    fill_rect(QRectF(0, 0, PAGE_W, PAGE_H), C_WHITE)
                page_no += 1
                y = 12.0

            def ensure(height, continuation=None):
                nonlocal y
                if y + height <= BOTTOM:
                    return
                new_page(False)
                if continuation:
                    draw_text(QRectF(LEFT, y, CONTENT_W, 24), continuation, 14, True, C_NAVY)
                    y += 30

            def draw_section_title(title, subtitle=""):
                nonlocal y
                ensure(34)
                draw_text(QRectF(LEFT, y, CONTENT_W, 21), title, 14, True, C_NAVY)
                if subtitle:
                    draw_text(QRectF(LEFT, y + 19, CONTENT_W, 14), subtitle, 7.4, False, C_MUTED)
                    y += 36
                else:
                    y += 27

            def row_value(row, key, default=""):
                try:
                    value = row[key]
                    return default if value is None else value
                except Exception:
                    return default

            # ------------------------- HEADER -------------------------
            new_page(True)

            organization = ""
            try:
                organization = str(self.customer_manager.get_organization_name() or "")
            except Exception:
                pass

            logo_path = ""
            try:
                logo_path = str(self.customer_manager.get_organization_logo() or "")
            except Exception:
                pass
            if not logo_path or not Path(logo_path).exists():
                root = Path(__file__).resolve().parents[1]
                candidates = list((root / "data" / "assets").glob("organization_logo.*"))
                if candidates:
                    logo_path = str(candidates[0])
            logo = QPixmap(logo_path) if logo_path and Path(logo_path).exists() else QPixmap()

            header_h = 64.0
            logo_w = 122.0
            if not logo.isNull():
                target = QRectF(LEFT + 2, y + 3, logo_w - 12, header_h - 7)
                scaled = logo.scaled(
                    int(target.width()),
                    int(target.height()),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                painter.drawPixmap(
                    int(target.x() + (target.width() - scaled.width()) / 2),
                    int(target.y() + (target.height() - scaled.height()) / 2),
                    scaled,
                )
            else:
                rounded(QRectF(LEFT + 4, y + 8, 94, 43), 6, C_LIGHT_BLUE, C_LINE)
                draw_text(QRectF(LEFT + 4, y + 8, 94, 43), "ТОиР", 15, True, C_NAVY, Qt.AlignCenter)

            title_x = LEFT + logo_w
            draw_text(
                QRectF(title_x, y + 1, 710, 31),
                "ЕЖЕДНЕВНАЯ СВОДКА ПО РАБОТАМ",
                23,
                True,
                C_NAVY,
            )
            draw_text(
                QRectF(title_x, y + 31, 710, 17),
                f"Период: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}",
                9.3,
                False,
                C_MUTED,
            )
            organization_line = organization or "Организация"
            draw_text(
                QRectF(title_x, y + 47, 710, 14),
                f"{organization_line}  •  Заказчик: {self.customer_name}",
                7.8,
                False,
                C_MUTED,
            )
            draw_text(
                QRectF(RIGHT - 180, y + 10, 180, 15),
                "ДАТА ОТЧЁТА",
                7.2,
                True,
                C_MUTED,
                Qt.AlignRight | Qt.AlignVCenter,
            )
            draw_text(
                QRectF(RIGHT - 180, y + 26, 180, 28),
                report_date,
                17,
                True,
                C_NAVY,
                Qt.AlignRight | Qt.AlignVCenter,
            )
            y += header_h
            fill_rect(QRectF(LEFT, y, CONTENT_W, 3), C_BLUE)
            y += 10

            # ------------------------- LEGEND -------------------------
            legend_h = 34.0
            rounded(QRectF(LEFT, y, CONTENT_W, legend_h), 6, C_WHITE, C_LINE)
            item_w = CONTENT_W / len(STATUS_ORDER)
            for index, status in enumerate(STATUS_ORDER):
                x = LEFT + index * item_w
                painter.save()
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(status_color(status)))
                painter.drawRoundedRect(QRectF(x + 9, y + 11, 11, 11), 2.5, 2.5)
                painter.restore()
                legend_font = 6.5 if len(STATUS_ORDER) > 6 else 7.1
                draw_text(QRectF(x + 26, y + 3, item_w - 32, 28), status, legend_font, True, C_TEXT)
            y += legend_h + 12

            # ------------------------- KPI -------------------------
            # Четыре компактных показателя, как на главной странице программы.
            # Значения относятся к фактической дате формирования отчёта.
            kpi_h = 64.0
            kpi_gap = 10.0
            kpi_w = (CONTENT_W - kpi_gap * 3) / 4.0
            kpi_items = [
                ("Всего техники", str(total_equipment_kpi), C_BLUE),
                ("Работы заказчика", str(customer_work_kpi), C_VIOLET),
                ("Активные ремонты / простои", str(active_repairs_kpi), C_AMBER),
                (f"КТГ за {report_date}", f"{ktg_percent_kpi:.1f}%", C_GREEN),
            ]
            for index, (label, value, accent) in enumerate(kpi_items):
                x = LEFT + index * (kpi_w + kpi_gap)
                card = QRectF(x, y, kpi_w, kpi_h)
                rounded(card, 7, C_WHITE, C_LINE)
                fill_rect(QRectF(x, y + 11, 4, kpi_h - 22), accent)
                draw_text(
                    QRectF(x + 14, y + 8, kpi_w - 25, 18),
                    label, 7.6, True, C_MUTED, Qt.AlignLeft | Qt.AlignVCenter, True
                )
                draw_text(
                    QRectF(x + 14, y + 27, kpi_w - 25, 29),
                    value, 18.0, True, C_NAVY, Qt.AlignLeft | Qt.AlignVCenter
                )
            y += kpi_h + 15

            # ------------------------- SCHEDULE -------------------------
            draw_section_title("ГРАФИК РАБОТ")

            # ВАЖНО: одна непрерывная календарная таблица.
            # Никаких date_chunks и переноса периода на следующие строки.
            # Ширина PDF уже была рассчитана выше по количеству дат.
            fixed_widths = [142.0, 108.0, 82.0]
            fixed_headers = ["Модель", "S/N", "Г/н"]
            fixed_total = sum(fixed_widths)
            row_h = 31.0
            head_h = 38.0
            day_w = (CONTENT_W - fixed_total) / max(1, len(snapshot_dates))
            # Не пытаемся заранее уместить ВЕСЬ парк на одной странице.
            # Таблица переносится вертикально по машинам, но календарные даты
            # всегда остаются одной непрерывной строкой. Заголовок повторяется
            # на каждой следующей странице.
            ensure(head_h + row_h + 10)

            def draw_schedule_header():
                nonlocal y
                x = LEFT
                for title, width in zip(fixed_headers, fixed_widths):
                    rect = QRectF(x, y, width, head_h)
                    fill_rect(rect, C_NAVY)
                    stroke_rect(rect, QColor("#315474"), 1)
                    draw_text(rect.adjusted(4, 0, -4, 0), title, 8.4, True, C_WHITE, Qt.AlignCenter)
                    x += width

                for day in snapshot_dates:
                    rect = QRectF(x, y, day_w, head_h)
                    fill_rect(rect, C_NAVY_2 if day == date.today() else C_NAVY)
                    stroke_rect(rect, QColor("#315474"), 1)
                    if day == date.today():
                        draw_text(
                            QRectF(x + 2, y + 3, day_w - 4, 16),
                            day.strftime("%d.%m"),
                            8.0,
                            True,
                            C_WHITE,
                            Qt.AlignCenter,
                        )
                        draw_text(
                            QRectF(x + 2, y + 19, day_w - 4, 14),
                            "Сегодня",
                            6.1,
                            True,
                            QColor("#A9CCFF"),
                            Qt.AlignCenter,
                        )
                    else:
                        draw_text(
                            rect.adjusted(2, 0, -2, 0),
                            day.strftime("%d.%m"),
                            7.8,
                            True,
                            C_WHITE,
                            Qt.AlignCenter,
                        )
                    x += day_w
                y += head_h

            draw_schedule_header()

            if not schedule_rows:
                rect = QRectF(LEFT, y, CONTENT_W, row_h)
                fill_rect(rect, C_WHITE)
                stroke_rect(rect)
                draw_text(
                    rect,
                    "За выбранный период работы, простои и будущие планы отсутствуют",
                    8.5,
                    False,
                    C_MUTED,
                    Qt.AlignCenter,
                )
                y += row_h
            else:
                for row_index, machine in enumerate(schedule_rows):
                    if y + row_h > BOTTOM:
                        new_page(False)
                        draw_text(
                            QRectF(LEFT, y, CONTENT_W, 24),
                            "ГРАФИК РАБОТ — ПРОДОЛЖЕНИЕ",
                            14,
                            True,
                            C_NAVY,
                        )
                        y += 30
                        draw_schedule_header()

                    x = LEFT
                    fixed_values = [
                        str(machine.get("model", "") or ""),
                        str(machine.get("serial_number", "") or ""),
                        str(machine.get("garage_number", "") or ""),
                    ]
                    for value_text, width in zip(fixed_values, fixed_widths):
                        rect = QRectF(x, y, width, row_h)
                        fill_rect(rect, C_WHITE)
                        stroke_rect(rect)
                        draw_text(rect.adjusted(6, 0, -6, 0), value_text, 8.0, False, C_TEXT)
                        x += width

                    cells = list(machine.get("cells", []) or [])
                    statuses = status_matrix[row_index] if row_index < len(status_matrix) else []
                    for position, day in enumerate(snapshot_dates):
                        cell = cells[position] if position < len(cells) else {}
                        status = statuses[position] if position < len(statuses) else ""
                        rect = QRectF(x, y, day_w, row_h)

                        # Нет статуса -> чистая белая ячейка.
                        fill = status_color(status) if status else C_WHITE
                        fill_rect(rect, fill)
                        stroke_rect(rect)

                        cell_text = str(cell.get("text", "") or "").strip()
                        if cell_text:
                            text_color = status_text_color(status) if status else C_TEXT
                            draw_text(
                                rect.adjusted(2, 1, -2, -1),
                                cell_text,
                                6.8,
                                True,
                                text_color,
                                Qt.AlignCenter,
                                True,
                            )
                        x += day_w
                    y += row_h

            y += 16

            # ------------------------- DETAILS -------------------------
            if works:
                ensure(42, "РАБОТЫ / ПРОСТОИ / ПЛАНЫ")
                draw_section_title(
                    "РАБОТЫ / ПРОСТОИ / ПЛАНЫ",
                    "Дневная детализация по работам, простоям и будущим планам",
                )

            def work_period(work):
                try:
                    work_start = date.fromisoformat(str(row_value(work, "date_start"))[:10])
                except Exception:
                    return None, None
                raw_end = row_value(work, "date_end")
                if raw_end:
                    try:
                        work_end = date.fromisoformat(str(raw_end)[:10])
                    except Exception:
                        work_end = work_start
                elif bool(row_value(work, "in_progress", False)):
                    work_end = min(date.today(), end_date)
                else:
                    work_end = work_start
                return work_start, max(work_start, work_end)

            for work in works:
                work_start, work_end = work_period(work)
                if work_start is None:
                    continue

                state = normalized_status(row_value(work, "repair_type"))
                if row_value(work, "id") in future_work_ids:
                    state = "Будущие работы"
                elif state not in STATUS_HEX:
                    state = str(row_value(work, "repair_type") or "Работа")
                accent = status_color(state) if state in STATUS_HEX else C_BLUE

                detail_rows = [
                    row for row in daily
                    if row_value(row, "work_id") == row_value(work, "id")
                    and date_from <= str(row_value(row, "work_date"))[:10] <= date_to
                ]
                detail_rows.sort(key=lambda row: str(row_value(row, "work_date")))

                model_text = f"{row_value(work, 'model')} №{row_value(work, 'garage_number')}"
                period_text = (
                    work_start.strftime("%d.%m.%Y")
                    if work_end == work_start
                    else f"{work_start.strftime('%d.%m.%Y')} — {work_end.strftime('%d.%m.%Y')}"
                )

                card_header_h = 50.0
                table_header_h = 27.0
                # Детализация выровнена по той же сетке, что и график работ:
                # одна общая ширина от LEFT до RIGHT без внутренних «ступенек».
                inner_x = LEFT
                inner_w = CONTENT_W
                col_widths = [96.0, 154.0, inner_w - 96.0 - 154.0 - 184.0 - 98.0, 184.0, 98.0]
                titles = ["Дата", "Состояние", "Работы / причина простоя", "Исполнители", "Наработка"]

                row_heights = []
                for detail in detail_rows:
                    description = str(row_value(detail, "description") or "")
                    executors = str(row_value(detail, "executors") or "")
                    row_height = max(
                        29.0,
                        text_height(description, col_widths[2] - 12, 7.5) + 8,
                        text_height(executors, col_widths[3] - 12, 7.5) + 8,
                    )
                    row_heights.append(min(58.0, row_height))
                if not detail_rows:
                    row_heights = [31.0]

                total_h = card_header_h + table_header_h + sum(row_heights) + 12
                if y + min(total_h, 220) > BOTTOM:
                    new_page(False)
                    draw_section_title("РАБОТЫ / ПРОСТОИ / ПЛАНЫ — ПРОДОЛЖЕНИЕ")

                header_rect = QRectF(LEFT, y, CONTENT_W, card_header_h)
                rounded(header_rect, 6, C_WHITE, C_LINE)
                fill_rect(QRectF(LEFT, y, 5, card_header_h), accent)
                draw_text(QRectF(LEFT + 16, y + 4, CONTENT_W - 330, 21), model_text, 12, True, C_NAVY)
                draw_text(
                    QRectF(LEFT + 16, y + 26, CONTENT_W - 330, 16),
                    row_value(work, "description") or "Без описания",
                    7.8,
                    False,
                    C_MUTED,
                )
                draw_text(
                    QRectF(RIGHT - 280, y + 5, 265, 18),
                    state,
                    8.3,
                    True,
                    accent,
                    Qt.AlignRight | Qt.AlignVCenter,
                )
                draw_text(
                    QRectF(RIGHT - 280, y + 26, 265, 15),
                    period_text,
                    7.0,
                    False,
                    C_MUTED,
                    Qt.AlignRight | Qt.AlignVCenter,
                )
                y += card_header_h

                def detail_header():
                    nonlocal y
                    x = inner_x
                    for title, width in zip(titles, col_widths):
                        rect = QRectF(x, y, width, table_header_h)
                        fill_rect(rect, C_LIGHT)
                        stroke_rect(rect)
                        draw_text(rect.adjusted(5, 0, -5, 0), title, 7.5, True, C_NAVY)
                        x += width
                    y += table_header_h

                detail_header()

                if not detail_rows:
                    row_height = row_heights[0]
                    rect = QRectF(inner_x, y, inner_w, row_height)
                    fill_rect(rect, C_WHITE)
                    stroke_rect(rect)
                    draw_text(rect, "Нет дневной детализации", 8, False, C_MUTED, Qt.AlignCenter)
                    y += row_height
                else:
                    for detail, row_height in zip(detail_rows, row_heights):
                        if y + row_height + 15 > BOTTOM:
                            new_page(False)
                            draw_section_title(f"{model_text} — ПРОДОЛЖЕНИЕ")
                            detail_header()

                        raw_date = str(row_value(detail, "work_date"))[:10]
                        try:
                            date_text = date.fromisoformat(raw_date).strftime("%d.%m.%Y")
                        except Exception:
                            date_text = raw_date

                        day_state = normalized_status(row_value(detail, "day_type"))
                        if day_state not in STATUS_HEX:
                            day_state = str(row_value(detail, "day_type") or state)

                        try:
                            raw_hours = row_value(detail, "machine_hours", None)
                            hours = "—" if raw_hours in (None, "") else f"{float(raw_hours):g} м/ч"
                        except Exception:
                            hours = str(row_value(detail, "machine_hours") or "—")

                        values = [
                            date_text,
                            day_state,
                            row_value(detail, "description") or "—",
                            row_value(detail, "executors") or "—",
                            hours,
                        ]

                        x = inner_x
                        for column_index, (value_text, width) in enumerate(zip(values, col_widths)):
                            rect = QRectF(x, y, width, row_height)
                            is_state_cell = column_index == 1 and day_state in STATUS_HEX
                            fill_rect(rect, status_color(day_state) if is_state_cell else C_WHITE)
                            stroke_rect(rect)
                            color = status_text_color(day_state) if is_state_cell else C_TEXT
                            align = (
                                Qt.AlignRight | Qt.AlignVCenter
                                if column_index == 4
                                else Qt.AlignLeft | Qt.AlignVCenter
                            )
                            draw_text(
                                rect.adjusted(5, 2, -5, -2),
                                value_text,
                                7.6,
                                column_index in (0, 1),
                                color,
                                align,
                                column_index in (2, 3),
                            )
                            x += width
                        y += row_height
                y += 11

            draw_footer()

        except Exception as exc:
            QMessageBox.critical(self, "PDF", f"Ошибка при формировании PDF:\n{exc}")
            return
        finally:
            painter.end()

        if open_after:
            self._open_exported_file(path)
        if show_message:
            QMessageBox.information(self, "PDF", "Ежедневная сводка сохранена и открыта.")
        return path

    def export_daily_work_summary_pdf(self):
        return self._create_daily_work_summary_pdf()

    def refresh_maintenance_plan(self):
        rows = (
            self.repository
            .get_maintenance_plan()
        )

        self.maintenance_plan_page.set_rows(
            rows
        )

    def plan_maintenance(self, plan):
        dialog = PlanMaintenanceDialog(
            plan,
            self,
        )
        if not dialog.exec():
            return

        try:
            self.repository.schedule_maintenance(
                equipment_id=plan.get("equipment_id"),
                maintenance_interval=plan.get("maintenance_interval"),
                target_hours=plan.get("target_hours"),
                planned_date=dialog.get_date(),
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Планирование ТО",
                str(error),
            )
            return

        self.refresh_maintenance_plan()
        self.refresh_schedule()
        self.refresh_work()
        QMessageBox.information(
            self,
            "Планирование ТО",
            "ТО добавлено в график работ.",
        )

    def reschedule_maintenance(self, plan):
        dialog = PlanMaintenanceDialog(plan, self)
        if plan.get("planned_date"):
            dialog.date.setDate(
                QDate.fromString(plan["planned_date"], "yyyy-MM-dd")
            )
        if not dialog.exec():
            return
        try:
            self.repository.reschedule_maintenance(
                plan["planned_work_id"],
                dialog.get_date(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Перенос ТО", str(error))
            return
        self.refresh_maintenance_plan()
        self.refresh_schedule()
        self.refresh_work()

    def cancel_maintenance_plan(self, plan):
        answer = QMessageBox.question(
            self,
            "Отмена планового ТО",
            f"Отменить {plan.get('maintenance_name', 'ТО')} "
            f"для {plan.get('model', '')} №{plan.get('garage_number', '')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.repository.cancel_scheduled_maintenance(
                plan["planned_work_id"]
            )
        except Exception as error:
            QMessageBox.warning(self, "Отмена ТО", str(error))
            return
        self.refresh_maintenance_plan()
        self.refresh_schedule()
        self.refresh_work()

    def start_maintenance_plan(self, plan):
        answer = QMessageBox.question(
            self,
            "Начать ТО",
            f"Начать {plan.get('maintenance_name', 'ТО')} "
            f"для {plan.get('model', '')} №{plan.get('garage_number', '')}?\n\n"
            "После начала техника будет автоматически переведена в статус «В простое».",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.repository.start_scheduled_maintenance(
                work_id=plan["planned_work_id"],
                started_date=QDate.currentDate().toString("yyyy-MM-dd"),
            )
        except Exception as error:
            QMessageBox.warning(self, "Начало ТО", str(error))
            return

        self.refresh_maintenance_plan()
        self.refresh_schedule()
        self.refresh_work()
        self.refresh_equipment()
        QMessageBox.information(
            self,
            "Начало ТО",
            "ТО начато. Техника переведена в статус «В простое».",
        )

    def complete_maintenance_plan(self, plan):
        dialog = QDialog(self)
        dialog.setWindowTitle(
            f"Выполнить {plan.get('maintenance_name', 'ТО')}"
        )
        form = QFormLayout(dialog)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())

        hours = QDoubleSpinBox()
        hours.setDecimals(1)
        hours.setMaximum(9999999)
        hours.setValue(float(plan.get("current_hours") or 0))

        description = QLineEdit()
        description.setText(
            f"Выполнено {plan.get('maintenance_name', 'ТО')}"
        )
        executors = QLineEdit()

        form.addRow("Дата выполнения", date_edit)
        form.addRow("Фактическая наработка", hours)
        form.addRow("Описание", description)
        form.addRow("Исполнители", executors)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if not dialog.exec():
            return

        try:
            self.repository.complete_scheduled_maintenance(
                work_id=plan["planned_work_id"],
                completed_date=date_edit.date().toString("yyyy-MM-dd"),
                machine_hours=hours.value(),
                description=description.text(),
                executors=executors.text(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Выполнение ТО", str(error))
            return

        self.refresh_maintenance_plan()
        self.refresh_schedule()
        self.refresh_work()
        self.refresh_equipment()
        QMessageBox.information(
            self,
            "Выполнение ТО",
            "ТО отмечено как фактически выполненное.",
        )

    def load_machine_details(
        self,
        equipment_id,
    ):
        equipment = (
            self.repository
            .get_equipment(
                equipment_id
            )
        )

        if equipment is None:
            self.machine_page.clear_machine()
            return

        history = (
            self.repository
            .get_work_by_equipment(
                equipment_id
            )
        )

        self.machine_page.set_machine(
            equipment
        )

        self.machine_page.set_history(
            history
        )

    def refresh_components(self):
        page=self.components_page; current=page.equipment_filter.currentData(); page.equipment_filter.blockSignals(True); page.equipment_filter.clear(); page.equipment_filter.addItem("Все компоненты",None); page.equipment_filter.addItem("Без привязки к технике",-1)
        for e in self.repository.get_all_equipment(): page.equipment_filter.addItem(f"{e['model']} — № {e['garage_number']}",e['id'])
        idx=page.equipment_filter.findData(current); page.equipment_filter.setCurrentIndex(idx if idx>=0 else 0); page.equipment_filter.blockSignals(False)
        query=page.search.text().strip().casefold(); filt=page.equipment_filter.currentData(); page.clear()
        for r in self.repository.get_all_components():
            if filt==-1 and r['equipment_id'] is not None: continue
            if filt not in (None,-1) and r['equipment_id']!=filt: continue
            machine=(f"{r['model']} — № {r['garage_number']}" if r['equipment_id'] is not None else "Без привязки")
            hay=" ".join(str(x or "") for x in (machine,r['component_name'],r['part_number'],r['serial_number'],r['note'])).casefold()
            if query and query not in hay: continue
            row=page.table.rowCount(); page.table.insertRow(row); vals=[machine,r['component_name'],r['part_number'] or "",r['serial_number'] or "",f"{float(r['resource_hours'] or 0):.1f}",f"{float(r['install_machine_hours'] or 0):.1f}",f"{float(r['worked_hours'] or 0):.1f}",f"{float(r['remaining_hours'] or 0):.1f}",(QDate.fromString(str(r['install_date'] or '')[:10], 'yyyy-MM-dd').toString('dd.MM.yyyy') if QDate.fromString(str(r['install_date'] or '')[:10], 'yyyy-MM-dd').isValid() else str(r['install_date'] or '')),r['note'] or ""]
            for c,v in enumerate(vals):
                item=QListWidgetItem() if False else None
                from PySide6.QtWidgets import QTableWidgetItem
                cell=QTableWidgetItem(str(v));
                if c==0:cell.setData(Qt.UserRole,r['id'])
                page.table.setItem(row,c,cell)
    def add_component(self):
        d=ComponentDialog(self,repository=self.repository)
        if d.exec():
            x=d.get_data(); self.repository.add_component(x['equipment_id'],x['component_name'],x['serial_number'],x['resource'],x['install_hours'],x['install_date'],x['part_number'],x['note']); self.refresh_components(); self.refresh_home()
    def edit_component(self):
        cid=self.components_page.selected_id()
        if not cid:return
        r=self.repository.get_component(cid); d=ComponentDialog(self,repository=self.repository); d.set_data(r['equipment_id'],r['component_name'],r['part_number'],r['serial_number'],r['install_machine_hours'],r['resource_hours'],r['install_date'],r['note'])
        if d.exec():
            x=d.get_data(); self.repository.update_component(cid,x['equipment_id'],x['component_name'],x['serial_number'],x['resource'],x['install_hours'],x['install_date'],x['part_number'],x['note']); self.refresh_components()
    def delete_component(self):
        cid=self.components_page.selected_id()
        if not cid:return
        if QMessageBox.question(self,"Удаление","Удалить выбранный компонент?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.repository.delete_component(cid); self.refresh_components(); self.refresh_home()

    def open_machine_components(self):
        """Открывает компоненты выбранной машины в отдельном окне."""
        equipment_id = self.machine_page.get_selected_equipment_id()
        if equipment_id is None:
            QMessageBox.information(self, "Компоненты", "Сначала выберите технику.")
            return

        dialog = MachineComponentsDialog(
            self, repository=self.repository, equipment_id=equipment_id
        )
        dialog.exec()

        # После закрытия отдельного окна синхронизируем общую страницу и главную.
        self.refresh_components()
        self.refresh_home()

    # ==========================================================
    # EQUIPMENT CRUD
    # ==========================================================

    def add_equipment(self):
        dialog = EquipmentDialog(self, repository=self.repository)

        if not dialog.exec():
            return

        data = dialog.get_data()

        if not data["model"]:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не указана модель.",
            )
            return

        if not data["serial_number"]:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не указан серийный номер.",
            )
            return

        if not data["garage_number"]:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не указан гаражный номер.",
            )
            return

        if self.repository.equipment_exists(
            model=data["model"],
            serial_number=data["serial_number"],
            garage_number=data["garage_number"],
        ):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такая техника уже существует.",
            )
            return

        status = data.get(
            "status",
            "В работе",
        )

        if status not in (
            "В работе",
            "Списан",
        ):
            status = "В работе"

        self.repository.add_equipment(
            model=data["model"],
            serial_number=data["serial_number"],
            garage_number=data["garage_number"],
            registration_number=data.get(
                "registration_number",
                "",
            ),
            manufacture_year=data.get(
                "manufacture_year"
            ),
            current_hours=data.get(
                "current_hours",
                0,
            ),
            status=status,
            note=data.get(
                "note",
                "",
            ),
            shift_hours_per_day=data.get(
                "shift_hours_per_day",
                22,
            ),
            auto_maintenance=data.get(
                "auto_maintenance",
                0,
            ),            commissioning_date=data.get("commissioning_date", ""),
            warranty_years=data.get("warranty_years", 0),
            warranty_hours=data.get("warranty_hours", 0),
            warranty_start_hours=data.get("warranty_start_hours", 0),
            photo_path=data.get("photo_path", ""),
            manufacturer_id=data.get("manufacturer_id"),
            distributor_id=data.get("distributor_id"),
        )

        self.refresh_all()

        self.status.showMessage(
            "Техника добавлена.",
            3000,
        )

    def edit_equipment(self):
        equipment_id = (
            self.get_selected_equipment_id()
        )

        if equipment_id is None:
            QMessageBox.information(
                self,
                "Техника",
                "Выберите технику.",
            )
            return

        row = self.repository.get_equipment(
            equipment_id
        )

        if row is None:
            return

        dialog = EquipmentDialog(
            self,
            repository=self.repository,
            equipment_id=equipment_id,
        )

        dialog.set_data(
            model=row["model"] or "",
            serial_number=(
                row["serial_number"] or ""
            ),
            garage_number=(
                row["garage_number"] or ""
            ),
            registration_number=(
                row["registration_number"]
                or ""
            ),
            manufacture_year=(
                row["manufacture_year"]
            ),
            current_hours=(
                row["current_hours"] or 0
            ),
            status=(
                row["status"]
                if row["status"]
                in (
                    "В работе",
                    "Списан",
                )
                else "В работе"
            ),
            note=row["note"] or "",
            shift_hours_per_day=(
                row["shift_hours_per_day"]
                or 22
            ),
            auto_maintenance=(
                row["auto_maintenance"]
                or 0
            ),            commissioning_date=row["commissioning_date"] or "",
            warranty_years=row["warranty_years"] or 0,
            warranty_hours=row["warranty_hours"] or 0,
            warranty_start_hours=row["warranty_start_hours"] or 0,
            photo_path=row["photo_path"] or "",
            manufacturer_id=row["manufacturer_id"],
            distributor_id=row["distributor_id"],
        )

        if not dialog.exec():
            return

        data = dialog.get_data()

        if (
            not data["model"]
            or not data["serial_number"]
            or not data["garage_number"]
        ):
            QMessageBox.warning(
                self,
                "Ошибка",
                (
                    "Модель, серийный номер "
                    "и гаражный номер обязательны."
                ),
            )
            return

        if self.repository.equipment_exists(
            model=data["model"],
            serial_number=data["serial_number"],
            garage_number=data["garage_number"],
            exclude_id=equipment_id,
        ):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такая техника уже существует.",
            )
            return

        status = data.get(
            "status",
            "В работе",
        )

        if status not in (
            "В работе",
            "Списан",
        ):
            status = "В работе"

        self.repository.update_equipment(
            equipment_id=equipment_id,
            model=data["model"],
            serial_number=data["serial_number"],
            garage_number=data["garage_number"],
            registration_number=data.get(
                "registration_number",
                "",
            ),
            manufacture_year=data.get(
                "manufacture_year"
            ),
            current_hours=data.get(
                "current_hours",
                0,
            ),
            status=status,
            note=data.get(
                "note",
                "",
            ),
            shift_hours_per_day=data.get(
                "shift_hours_per_day",
                22,
            ),
            auto_maintenance=data.get(
                "auto_maintenance",
                0,
            ),            commissioning_date=data.get("commissioning_date", ""),
            warranty_years=data.get("warranty_years", 0),
            warranty_hours=data.get("warranty_hours", 0),
            warranty_start_hours=data.get("warranty_start_hours", 0),
            photo_path=data.get("photo_path", ""),
            manufacturer_id=data.get("manufacturer_id"),
            distributor_id=data.get("distributor_id"),
        )

        self.refresh_all()

        self.status.showMessage(
            "Данные техники обновлены.",
            3000,
        )

    def delete_equipment(self):
        equipment_id = (
            self.get_selected_equipment_id()
        )

        if equipment_id is None:
            QMessageBox.information(
                self,
                "Техника",
                "Выберите технику.",
            )
            return

        row = self.repository.get_equipment(
            equipment_id
        )

        if row is None:
            return

        answer = QMessageBox.question(
            self,
            "Удаление техники",
            (
                f"Удалить {row['model']} "
                f"№{row['garage_number']}?\n\n"
                "Будут удалены все связанные "
                "работы и компоненты."
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.repository.delete_equipment(
            equipment_id
        )

        self.refresh_all()

        self.status.showMessage(
            "Техника удалена.",
            3000,
        )

    def get_selected_equipment_id(self):
        row = (
            self.equipment_page
            .table
            .currentRow()
        )

        if row < 0:
            return None

        item = (
            self.equipment_page
            .table
            .item(
                row,
                0,
            )
        )

        if item is None:
            return None

        return item.data(
            Qt.UserRole
        )

    # ==========================================================
    # WORK CRUD
    # ==========================================================

    def open_downtime_card(self):
        work_id = self.get_selected_work_id()
        if work_id is None:
            return
        try:
            dialog = DowntimeCardDialog(
                self.repository,
                work_id,
                self,
            )
            dialog.exec()
        except Exception as error:
            QMessageBox.warning(
                self,
                "Менеджер простоев",
                str(error),
            )
        self.refresh_all()

    def add_work(self):
        dialog = EditWorkDialog(
            self,
            repository=self.repository,
        )
        if not dialog.exec():
            return

        data = dialog.get_data()

        equipment_id = data.get(
            "equipment_id"
        )

        if equipment_id is None:
            equipment_id = (
                self.resolve_equipment(
                    garage_number=data[
                        "garage_number"
                    ],
                    model=data.get(
                        "model",
                        "",
                    ),
                )
            )

        if equipment_id is None:
            return

        date_start = (
            data["date_start"]
            .toString("yyyy-MM-dd")
        )

        date_end = None

        if not data["in_progress"]:
            date_end = (
                data["date_end"]
                .toString("yyyy-MM-dd")
            )

            if date_end < date_start:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    (
                        "Дата окончания не может "
                        "быть раньше даты начала."
                    ),
                )
                return

        work_id = self.repository.add_work(
            equipment_id=equipment_id,
            request_number=data.get(
                "request_number",
                "",
            ),
            repair_type=data.get(
                "repair_type",
                "",
            ),
            date_start=date_start,
            date_end=date_end,
            in_progress=data[
                "in_progress"
            ],
            machine_hours=data.get(
                "machine_hours",
                0,
            ),
            description=data.get(
                "description",
                "",
            ),
            executors=data.get(
                "executors",
                "",
            ),
            requires_report=data.get(
                "requires_report",
                False,
            ),
            report_completed=data.get(
                "report_completed",
                False,
            ),
            maintenance_interval=data.get(
                "maintenance_interval"
            ),
        )

        machine_hours = float(
            data.get(
                "machine_hours",
                0,
            )
            or 0
        )

        if machine_hours > 0:
            self.update_machine_hours_if_newer(
                equipment_id,
                machine_hours,
            )

        self.repository.sync_equipment_status(
            equipment_id
        )

        self.refresh_all()

        self.status.showMessage(
            f"Работа №{work_id} добавлена.",
            3000,
        )

    def edit_work(self):
        work_id = (
            self.get_selected_work_id()
        )

        if work_id is None:
            QMessageBox.information(
                self,
                "Работы",
                "Выберите запись.",
            )
            return

        row = self.repository.get_work(
            work_id
        )

        if row is None:
            return

        dialog = EditWorkDialog(
            self,
            repository=self.repository,
            equipment_id=row["equipment_id"],
            work_id=work_id,
        )

        date_start = QDate.fromString(
            row["date_start"],
            "yyyy-MM-dd",
        )

        if not date_start.isValid():
            date_start = QDate.currentDate()

        date_end = QDate.currentDate()

        if row["date_end"]:
            parsed_end = QDate.fromString(
                row["date_end"],
                "yyyy-MM-dd",
            )

            if parsed_end.isValid():
                date_end = parsed_end

        dialog.set_data(
            request_number=(
                row["request_number"] or ""
            ),
            model=row["model"] or "",
            garage_number=(
                row["garage_number"] or ""
            ),
            repair_type=(
                row["repair_type"] or ""
            ),
            date_start=date_start,
            date_end=date_end,
            in_progress=bool(
                row["in_progress"]
            ),
            machine_hours=(
                row["machine_hours"] or 0
            ),
            executors=(
                row["executors"] or ""
            ),
            description=(
                row["description"] or ""
            ),
            requires_report=bool(
                row["requires_report"]
            ),
            report_completed=bool(
                row["report_completed"]
            ),
            maintenance_interval=(
                row["maintenance_interval"]
            ),
        )

        if not dialog.exec():
            return

        data = dialog.get_data()

        equipment_id = (
            self.resolve_equipment(
                garage_number=data[
                    "garage_number"
                ],
                model=data.get(
                    "model",
                    "",
                ),
            )
        )

        if equipment_id is None:
            return

        date_start = (
            data["date_start"]
            .toString("yyyy-MM-dd")
        )

        date_end = None

        if not data["in_progress"]:
            date_end = (
                data["date_end"]
                .toString("yyyy-MM-dd")
            )

            if date_end < date_start:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    (
                        "Дата окончания не может "
                        "быть раньше даты начала."
                    ),
                )
                return

        self.repository.update_work(
            work_id=work_id,
            equipment_id=equipment_id,
            request_number=data.get(
                "request_number",
                "",
            ),
            repair_type=data.get(
                "repair_type",
                "",
            ),
            date_start=date_start,
            date_end=date_end,
            in_progress=data[
                "in_progress"
            ],
            machine_hours=data.get(
                "machine_hours",
                0,
            ),
            description=data.get(
                "description",
                "",
            ),
            executors=data.get(
                "executors",
                "",
            ),
            requires_report=data.get(
                "requires_report",
                False,
            ),
            report_completed=data.get(
                "report_completed",
                False,
            ),
            maintenance_interval=data.get(
                "maintenance_interval"
            ),
        )

        machine_hours = float(
            data.get(
                "machine_hours",
                0,
            )
            or 0
        )

        if machine_hours > 0:
            self.update_machine_hours_if_newer(
                equipment_id,
                machine_hours,
            )

        self.repository.sync_equipment_status(
            equipment_id
        )

        self.refresh_all()

        self.status.showMessage(
            "Работа обновлена.",
            3000,
        )

    def delete_work(self):
        work_id = (
            self.get_selected_work_id()
        )

        if work_id is None:
            QMessageBox.information(
                self,
                "Работы",
                "Выберите запись.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление работы",
            "Удалить выбранную запись?",
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.repository.delete_work(
            work_id
        )

        self.refresh_all()

        self.status.showMessage(
            "Работа удалена.",
            3000,
        )

    def get_selected_work_id(self):
        row = (
            self.work_page
            .table
            .currentRow()
        )

        if row < 0:
            return None

        item = (
            self.work_page
            .table
            .item(
                row,
                0,
            )
        )

        if item is None:
            return None

        return item.data(
            Qt.UserRole
        )

    # ==========================================================
    # EQUIPMENT RESOLUTION
    # ==========================================================

    def resolve_equipment(
        self,
        garage_number,
        model="",
    ):
        garage_number = str(
            garage_number or ""
        ).strip()

        model = str(
            model or ""
        ).strip()

        if not garage_number:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Укажите гаражный номер.",
            )
            return None

        rows = (
            self.repository
            .find_equipment_by_garage_number(
                garage_number
            )
        )

        if not rows:
            QMessageBox.warning(
                self,
                "Техника не найдена",
                (
                    "Техника с гаражным номером "
                    f"{garage_number} не найдена."
                ),
            )
            return None

        if len(rows) == 1:
            return rows[0]["id"]

        if model:
            row = (
                self.repository
                .find_equipment_by_garage_and_model(
                    garage_number,
                    model,
                )
            )

            if row is not None:
                return row["id"]

        models = "\n".join(
            (
                f"• {row['model']} — "
                f"S/N {row['serial_number']}"
            )
            for row in rows
        )

        QMessageBox.warning(
            self,
            "Найдено несколько машин",
            (
                f"Гаражный №{garage_number} "
                "используется у нескольких машин.\n\n"
                "Укажите модель:\n\n"
                f"{models}"
            ),
        )

        return None

    def update_machine_hours_if_newer(
        self,
        equipment_id,
        machine_hours,
    ):
        row = self.repository.get_equipment(
            equipment_id
        )

        if row is None:
            return

        current_hours = float(
            row["current_hours"] or 0
        )

        new_hours = float(
            machine_hours or 0
        )

        if new_hours > current_hours:
            self.repository.update_equipment_hours(
                equipment_id,
                new_hours,
            )
            # Наработка влияет на ближайшее ТО: обновляем план и
            # уведомления сразу, не дожидаясь повторного открытия страницы.
            self.refresh_maintenance_plan()
            self.refresh_home()
    
    # ==========================================================
    # SETTINGS
    # ==========================================================

    def load_settings(self):
        cfg = self.app_settings.load()
        # Совместимость со старыми проектами, где организация хранилась только в organization.json.
        organization = cfg.get("organization_name") or self.customer_manager.get_organization_name()
        if organization and organization != cfg.get("organization_name"):
            cfg["organization_name"] = organization
            self.app_settings.save(cfg)
        self.settings_page.logo_path.setText(self.customer_manager.get_organization_logo())
        self.settings_page.set_all_settings(cfg, self.customer_name, self.sync_service.status())
        if hasattr(self.home_page, "apply_quick_actions"):
            self.home_page.apply_quick_actions(
                cfg.get("ui", {}).get("quick_actions", ["add_equipment", "add_work", "reports", "settings"])
            )
        self._refresh_email_settings_status()
        self.apply_header()
        self.update_statusbar()

    def save_settings(self):
        data = self.settings_page.get_all_settings()
        if not data["organization_name"]:
            QMessageBox.warning(self, "Настройки", "Укажите наименование организации.")
            return
        if not data["user"]["full_name"] or not data["user"]["position"] or not data["user"]["email"]:
            QMessageBox.warning(self, "Настройки", "Заполните ФИО, должность и корпоративный email.")
            return
        if "@" not in data["user"]["email"]:
            QMessageBox.warning(self, "Настройки", "Проверьте корпоративный email.")
            return
        security = data["security"]
        if security["pin_enabled"] and security["new_pin"]:
            if not security["new_pin"].isdigit() or not 4 <= len(security["new_pin"]) <= 6:
                QMessageBox.warning(self, "Настройки", "PIN должен содержать 4–6 цифр.")
                return
            if security["new_pin"] != security["pin_confirm"]:
                QMessageBox.warning(self, "Настройки", "PIN-коды не совпадают.")
                return
        cfg = self.app_settings.load()
        old_local_root = cfg.get("storage", {}).get("local_root", "")
        old_pin_enabled = bool(cfg.get("security", {}).get("pin_enabled"))
        cfg["organization_name"] = data["organization_name"]
        cfg["user"] = data["user"]
        cfg["storage"].update(data["storage"])
        cfg["sync"].update(data["sync"])
        cfg["ui"].update(data["ui"])
        cfg["setup_complete"] = True
        try:
            self.app_settings.migrate_local_root(old_local_root, data["storage"]["local_root"])
        except Exception as exc:
            QMessageBox.critical(self, "Настройки", f"Не удалось подготовить новую локальную папку:\n{exc}")
            return
        self.app_settings.save(cfg)
        if security["pin_enabled"]:
            if security["new_pin"]:
                self.app_settings.set_pin(security["new_pin"], True)
            elif not old_pin_enabled:
                QMessageBox.warning(self, "Настройки", "Чтобы включить PIN, задайте новый PIN-код.")
                cfg["security"]["pin_enabled"] = False
                self.app_settings.save(cfg)
        else:
            self.app_settings.set_pin(enabled=False)
        self.customer_manager.set_organization_name(data["organization_name"])
        self.repository.save_settings(backup_count=data["storage"]["backup_count"])
        apply_theme(QApplication.instance(), data["ui"]["theme"])
        if hasattr(self.home_page, "apply_visual_theme"):
            self.home_page.apply_visual_theme(data["ui"]["theme"])
        self.refresh_reference_pages()
        self.load_settings()
        self.refresh_home()
        self.status.showMessage("Настройки сохранены. Изменение локальной папки применяется после перезапуска.", 5000)

    def _select_settings_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку", edit.text().strip())
        if folder:
            edit.setText(folder)

    def test_server_connection(self):
        # Используем значения прямо из формы, не требуя предварительного сохранения.
        original = self.app_settings.load()
        temp = self.app_settings.load()
        temp["storage"]["server_root"] = self.settings_page.server_root.text().strip()
        self.app_settings.save(temp)
        try:
            ok = self.sync_service.server_available()
        finally:
            self.app_settings.save(original)
        QMessageBox.information(self, "Сервер", "Серверная папка доступна для чтения и записи." if ok else "Серверная папка недоступна.")

    def sync_now(self, show_message=False, force=False):
        result = self.sync_service.sync_now(force=force)
        self.update_statusbar()
        if hasattr(self.settings_page, "sync_status"):
            status = self.sync_service.status()
            self.settings_page.sync_status.setText(status["label"])
            self.settings_page.last_sync.setText(status.get("last_sync") or "Ещё не выполнялась")
        if show_message:
            if result.get("ok"):
                QMessageBox.information(self, "Синхронизация", "Локальная и серверная базы синхронизированы.")
            else:
                QMessageBox.warning(self, "Синхронизация", result.get("error") or "Синхронизация не выполнена.")
        return result

    def _background_sync(self):
        try:
            self.sync_now(show_message=False)
        except Exception:
            self.update_statusbar()

    def _manual_backup(self):
        try:
            path = self.create_backup()
            QMessageBox.information(self, "Резервная копия", f"Резервная копия создана:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Резервная копия", str(exc))

    def _check_database_integrity(self):
        try:
            row = self.repository.connection.execute("PRAGMA integrity_check").fetchone()
            text = row[0] if row else "Нет результата"
            QMessageBox.information(self, "Проверка БД", f"Результат проверки: {text}")
        except Exception as exc:
            QMessageBox.critical(self, "Проверка БД", str(exc))

    def select_logo(self):
        filename, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Выберите логотип организации",
                "",
                (
                    "Изображения "
                    "(*.png *.jpg *.jpeg "
                    "*.bmp *.webp)"
                ),
            )
        )

        if not filename:
            return

        try:
            logo_path = (
                self.customer_manager
                .set_organization_logo(
                    filename
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка",
                str(error),
            )
            return

        if hasattr(
            self.settings_page,
            "logo_path",
        ):
            self.settings_page.logo_path.setText(
                logo_path
            )

        self.apply_header()

        self.status.showMessage(
            "Логотип организации сохранен.",
            3000,
        )

    # ==========================================================
    # CUSTOMER SWITCH
    # ==========================================================

    def change_customer(self):
        from gui.dialogs.customer_dialog import (
            CustomerDialog,
        )

        dialog = CustomerDialog(
            self
        )

        if not dialog.exec():
            return

        new_customer = (
            dialog.get_selected_customer()
        )

        if not new_customer:
            return

        if new_customer == self.customer_name:
            return

        try:
            self.sync_now(show_message=False, force=True)
        except Exception:
            pass
        try:
            self.repository.close()
        except Exception:
            pass

        try:
            SyncService(new_customer).prepare_before_open()
        except Exception:
            pass

        self.customer_name = (
            self.customer_manager
            .set_active_customer(
                new_customer
            )
        )

        self.repository = Repository(
            customer_name=self.customer_name
        )
        self.report_service = ReportService(self.repository)
        self.app_settings = AppSettingsManager()
        self.app_settings.set_active_customer(self.customer_name)
        self.sync_service = SyncService(self.customer_name, self.repository)
        self.outlook_service = OutlookService()
        self._report_export = None

        self.load_settings()
        self.refresh_all()

        self.status.showMessage(
            (
                "Открыт заказчик: "
                f"{self.customer_name}"
            ),
            4000,
        )

    # ==========================================================
    # FILE OPEN / EMAIL
    # ==========================================================

    def _open_exported_file(self, path):
        """Открыть сохранённый PDF/Excel системным приложением по умолчанию."""
        if not path:
            return False
        file_path = Path(str(path)).expanduser()
        if not file_path.exists():
            return False
        try:
            return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.resolve()))))
        except Exception:
            return False

    def _selected_email_report_name(self):
        if hasattr(self.settings_page, "email_report_combo"):
            return str(self.settings_page.email_report_combo.currentData() or "").strip()
        return ""

    def _refresh_email_settings_status(self):
        if not hasattr(self.settings_page, "email_status"):
            return
        report_name = self._selected_email_report_name()
        template = self.app_settings.get_email_template(self.customer_name, report_name)
        specific = self.app_settings.has_specific_email_template(self.customer_name, report_name)
        if not template:
            self.settings_page.email_status.setText(f"Для «{report_name}» шаблон не настроен")
            return
        if not template.get("enabled", True):
            self.settings_page.email_status.setText(f"Для «{report_name}» рассылка отключена")
            return
        recipients = str(template.get("to", "") or "").strip()
        source = "отдельный шаблон" if specific else "используется общий шаблон"
        self.settings_page.email_status.setText(
            source + (f" · {recipients}" if recipients else " · получатели не указаны")
        )

    def configure_email_template(self, report_name=None):
        report_name = str(report_name or self._selected_email_report_name() or "").strip()
        template = self.app_settings.get_email_template(self.customer_name, report_name)
        wizard = EmailTemplateWizard(
            config=template,
            customer=self.customer_name,
            report_name=report_name,
            outlook_service=self.outlook_service,
            parent=self,
        )
        if wizard.exec() != QDialog.Accepted:
            return False
        data = wizard.settings()
        if data.get("enabled") and not data.get("to"):
            QMessageBox.warning(self, "Рассылка по eMail", "Укажите хотя бы одного получателя в поле «Кому».")
            return False
        self.app_settings.set_email_template(self.customer_name, data, report_name=report_name)
        self._refresh_email_settings_status()
        self.status.showMessage(f"Шаблон eMail для «{report_name}» сохранён.", 3500)
        return True

    def _email_template(self, report_name):
        report_name = str(report_name or "").strip()
        template = self.app_settings.get_email_template(self.customer_name, report_name)
        if not self.app_settings.has_specific_email_template(self.customer_name, report_name):
            if not self.configure_email_template(report_name):
                return None
            template = self.app_settings.get_email_template(self.customer_name, report_name)
        if not template or not template.get("to"):
            if not self.configure_email_template(report_name):
                return None
            template = self.app_settings.get_email_template(self.customer_name, report_name)
        if not template.get("enabled", True):
            QMessageBox.information(self, "Рассылка по eMail", f"Рассылка для отчёта «{report_name}» отключена.")
            return None
        return template

    @staticmethod
    def _render_email_text(template, values):
        class SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        try:
            return str(template or "").format_map(SafeDict(values))
        except Exception:
            return str(template or "")

    def _email_context(self, report_name, date_from, date_to):
        cfg = self.app_settings.load()
        user = cfg.get("user", {})
        organization = cfg.get("organization_name") or self.customer_manager.get_organization_name() or ""
        return {
            "report": str(report_name or "Отчёт"),
            "customer": str(self.customer_name or ""),
            "organization": str(organization or ""),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "period_from": self._format_report_date(date_from),
            "period_to": self._format_report_date(date_to),
            "user_fio": str(user.get("full_name", "") or ""),
            "user_position": str(user.get("position", "") or ""),
            "user_email": str(user.get("email", "") or ""),
        }

    def _email_export_dir(self):
        cfg = self.app_settings.load()
        local_root = cfg.get("storage", {}).get("local_root", "")
        root = Path(local_root).expanduser() if local_root else Path.cwd() / "data"
        folder = root / "exports" / "email"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _open_outlook_draft(self, template, context, attachment):
        subject = self._render_email_text(
            template.get("subject", DEFAULT_SUBJECT), context
        )
        body = self._render_email_text(
            template.get("body", DEFAULT_BODY), context
        )
        try:
            self.outlook_service.create_draft(
                to=template.get("to", ""),
                cc=template.get("cc", ""),
                subject=subject,
                body=body,
                attachments=[attachment],
            )
        except OutlookIntegrationError as exc:
            QMessageBox.critical(
                self,
                "Outlook",
                f"Не удалось открыть письмо в Outlook:\n{exc}\n\n"
                f"PDF уже сформирован и сохранён здесь:\n{attachment}",
            )
            return False
        self.status.showMessage("Письмо подготовлено и открыто в Outlook.", 5000)
        return True

    def email_daily_work_summary(self):
        report_name = "Ежедневная сводка по работам"
        template = self._email_template(report_name)
        if not template:
            return
        date_from, date_to = self.schedule_page.get_period()
        report_date = datetime.now().strftime("%d.%m.%Y")
        path = self._email_export_dir() / f"Ежедневная сводная по работам ({report_date}).pdf"
        created = self._create_daily_work_summary_pdf(
            output_path=str(path),
            open_after=False,
            show_message=False,
        )
        if not created:
            return
        context = self._email_context(
            report_name, date_from, date_to
        )
        self._open_outlook_draft(template, context, created)

    def _create_analytical_report_pdf(self, payload, path):
        path = str(path)
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        printer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Millimeter)
        doc = QTextDocument()
        base_font = QFont("Segoe UI")
        base_font.setPointSizeF(10.0)
        doc.setDefaultFont(base_font)
        doc.setDocumentMargin(0)
        doc.setPageSize(printer.pageRect(QPrinter.Point).size())
        doc.setHtml(self._report_html(payload))
        doc.print_(printer)
        return path

    def email_selected_report(self):
        try:
            payload = self._ensure_report_payload()
            template = self._email_template(payload["title"])
            if not template:
                return
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = str(payload["title"]).replace("/", "_").replace("\\", "_")
            path = self._email_export_dir() / f"{safe_title}_{stamp}.pdf"
            created = self._create_analytical_report_pdf(payload, path)
            context = self._email_context(
                payload["title"], payload["date_from"], payload["date_to"]
            )
            self._open_outlook_draft(template, context, created)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Рассылка по eMail",
                f"Не удалось подготовить отчёт для отправки:\n{exc}",
            )

    # ==========================================================
    # REPORTS
    # ==========================================================

    @staticmethod
    def _report_value(row, key, default=""):
        try:
            value = row[key]
        except Exception:
            try:
                value = row.get(key, default)
            except Exception:
                value = default
        return default if value is None else value

    def _build_report_payload(self, report_name, date_from, date_to):
        from datetime import date

        service = self.report_service
        name = str(report_name or "КТГ")
        summary = []
        headers = []
        rows = []

        if name == "КТГ":
            data = service.get_ktg(date_from, date_to)
            summary = [
                ("КТГ", f"{data['ktg_percent']:.2f}%"),
                ("Единиц техники", data["total_equipment"]),
                ("Машино-дней в периоде", data["total_machine_days"]),
                ("Машино-дней простоя", data["unavailable_machine_days"]),
            ]
            headers = ["Дата", "Доступно", "Недоступно", "КТГ, %"]
            rows = [
                [item["date"].strftime("%d.%m.%Y"), item["available"], item["unavailable"], f"{item['ktg_percent']:.2f}"]
                for item in data["daily"]
            ]
        elif name == "Простои":
            data = service.get_downtime_report(date_from, date_to)
            headers = ["Техника", "Гаражный №", "Заявка", "Тип", "Начало", "Окончание", "Дней", "Описание", "Исполнители"]
            for r in data:
                rows.append([
                    self._report_value(r, "model"), self._report_value(r, "garage_number"),
                    self._report_value(r, "request_number"), self._report_value(r, "repair_type"),
                    r["date_start"].strftime("%d.%m.%Y") if r.get("date_start") else "",
                    r["date_end"].strftime("%d.%m.%Y") if r.get("date_end") else "В работе",
                    self._report_value(r, "downtime_days", 0), self._report_value(r, "description"),
                    self._report_value(r, "executors"),
                ])
            summary = [("Записей", len(rows)), ("Дней простоя", sum(int(r[6] or 0) for r in rows))]
        elif name in (
            "Плановые ремонты",
            "Аварийные ремонты",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
        ):
            # Отчёты строятся по фактическим состояниям КАЖДОГО дня.
            # Поэтому смена состояния внутри одной карточки корректно попадает
            # в соответствующую сводку, а не определяется только шапкой работы.
            repair_type = {
                "Плановые ремонты": "Плановый ремонт",
                "Аварийные ремонты": "Аварийный ремонт",
                "Работы заказчика": "Работы заказчика",
                "Мониторинг состояния": "Мониторинг состояния",
                "Модернизация": "Модернизация",
            }[name]
            data = service.get_state_segments(date_from, date_to, repair_type)
            headers = ["Техника", "Гаражный №", "Заявка", "Начало", "Окончание", "Дней", "Наработка", "Описание", "Исполнители"]
            for r in data:
                rows.append([
                    self._report_value(r, "model"), self._report_value(r, "garage_number"),
                    self._report_value(r, "request_number"), self._format_report_date(self._report_value(r, "date_start")),
                    self._format_report_date(self._report_value(r, "date_end")), self._report_value(r, "days", 0),
                    self._report_value(r, "machine_hours", 0), self._report_value(r, "description"),
                    self._report_value(r, "executors"),
                ])
            summary = [("Интервалов", len(rows)), ("Фактических дней", sum(int(r[5] or 0) for r in rows))]
        elif name == "Статистика исполнителей":
            data = service.get_executor_statistics(date_from, date_to)
            headers = ["Исполнитель", "Карточек работ", "Дней участия"]
            rows = [[r["executor"], r["work_count"], r["work_days"]] for r in data]
            summary = [("Исполнителей", len(rows)), ("Дней участия", sum(int(r[2]) for r in rows))]
        elif name == "Статистика техники":
            data = service.get_equipment_statistics(date_from, date_to)
            headers = ["Модель", "Гаражный №", "Серийный №", "Карточек", "Дней работ", "Дни простоя", "Активных"]
            rows = [[r["model"], r["garage_number"], r["serial_number"], r["work_count"], r["work_days"], r["downtime_days"], r["active_count"]] for r in data]
            summary = [("Техники с работами", len(rows)), ("Дней работ", sum(int(r[4]) for r in rows)), ("Дни простоя", sum(int(r[5]) for r in rows))]
        else:
            raise ValueError(f"Неизвестный отчёт: {name}")

        return {"title": name, "date_from": date_from, "date_to": date_to, "summary": summary, "headers": headers, "rows": rows}

    @staticmethod
    def _format_report_date(value):
        from datetime import date, datetime
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        raw = str(value)[:10]
        try:
            return date.fromisoformat(raw).strftime("%d.%m.%Y")
        except Exception:
            return raw

    def _report_html(self, payload):
        """HTML preview/PDF for analytical reports.

        Вся страница строится на одной широкой сетке: KPI и основная
        таблица имеют одинаковую ширину и заполняют печатную область.
        Без декоративных диаграмм — акцент на читаемых таблицах.
        """
        import html

        title = html.escape(str(payload["title"]))
        period = (
            f"{self._format_report_date(payload['date_from'])} — "
            f"{self._format_report_date(payload['date_to'])}"
        )
        try:
            organization = str(self.customer_manager.get_organization_name() or "")
        except Exception:
            organization = ""

        summary_items = list(payload.get("summary", []))

        # В книжном A4 три карточки в строке получаются слишком узкими:
        # длинные подписи переносятся, а четвёртая карточка падает отдельным
        # маленьким блоком. Делаем устойчивую сетку 2 x N на всю ширину.
        # Если карточек нечётное число, последняя занимает всю строку.
        card_rows = []
        index = 0
        while index < len(summary_items):
            chunk = summary_items[index:index + 2]
            cells = []
            for key, value in chunk:
                cells.append(
                    "<td class='kpi'>"
                    f"<div class='kpi-label'>{html.escape(str(key))}</div>"
                    f"<div class='kpi-value'>{html.escape(str(value))}</div>"
                    "</td>"
                )
            if len(chunk) == 1:
                # QTextDocument надёжно поддерживает colspan; так нечётный
                # последний KPI выглядит намеренно, а не как пустая дырка.
                cells = [cells[0].replace("<td class='kpi'>", "<td class='kpi kpi-wide' colspan='2'>", 1)]
            card_rows.append("<tr>" + "".join(cells) + "</tr>")
            index += 2
        cards = "".join(card_rows)

        head = "".join(f"<th>{html.escape(str(h))}</th>" for h in payload["headers"])
        body_rows = []
        for row in payload["rows"]:
            cells = "".join(
                f"<td>{html.escape(str(v if v is not None else ''))}</td>"
                for v in row
            )
            body_rows.append(f"<tr>{cells}</tr>")
        body = "".join(body_rows) or (
            f"<tr><td colspan='{max(1, len(payload['headers']))}' "
            "class='empty'>Нет данных за выбранный период</td></tr>"
        )

        context = ""
        if organization:
            context += html.escape(organization)
        if self.customer_name:
            context += (" • " if context else "") + "Заказчик: " + html.escape(str(self.customer_name))

        generated = datetime.now().strftime("%d.%m.%Y")

        return f"""
        <html><head><style>
        body {{ font-family:'Segoe UI'; color:#17263a; font-size:10.5pt; margin:0; padding:0; background:#ffffff; }}
        .page {{ width:100%; margin:0 auto; }}
        .top {{ width:100%; border-collapse:collapse; margin:0 0 3pt 0; }}
        .top td {{ border:none; padding:0; vertical-align:bottom; }}
        .top-right {{ text-align:right; width:28%; color:#6e8098; font-size:9.5pt; }}
        h1 {{ color:#112d4e; font-size:26pt; line-height:1.05; margin:0 0 4pt 0; }}
        .period {{ color:#5f7189; font-size:11pt; margin-bottom:2pt; }}
        .context {{ color:#8290a2; font-size:9.5pt; margin-bottom:10pt; }}
        .rule {{ background:#2f6fc6; height:3px; margin:0 0 11pt 0; }}
        table {{ border-collapse:collapse; width:100%; margin-left:auto; margin-right:auto; }}
        .summary {{ width:100%; table-layout:fixed; border-spacing:7pt; border-collapse:separate; margin:0 auto 13pt auto; }}
        .kpi {{ width:50%; min-height:58pt; padding:10pt 12pt; border:1px solid #d2dce8; background:#f7faff; vertical-align:middle; }}
        .kpi-wide {{ width:100%; }}
        .kpi-label {{ color:#657a94; font-size:9.3pt; line-height:1.15; font-weight:600; }}
        .kpi-value {{ color:#112d4e; font-size:19pt; line-height:1.05; font-weight:700; margin-top:5pt; }}
        .subhead {{ color:#112d4e; font-size:13pt; font-weight:700; margin:4pt 0 6pt 0; }}
        .data {{ width:100%; table-layout:auto; margin:0 auto; }}
        th {{ background:#112d4e; color:white; font-size:9.8pt; font-weight:700; padding:7.5pt 7pt; border:1px solid #315373; text-align:left; }}
        td {{ font-size:9.5pt; padding:6.5pt 7pt; border:1px solid #d8e1eb; vertical-align:top; }}
        .data tr:nth-child(even) td {{ background:#f8fafc; }}
        .empty {{ text-align:center; color:#6e8098; padding:18pt; }}
        </style></head><body>
        <div class='page'>
        <table class='top' width='100%'><tr>
          <td>
            <h1>{title}</h1>
            <div class='period'>Период: {html.escape(period)}</div>
            <div class='context'>{context}</div>
          </td>
          <td class='top-right'>Дата отчёта<br><b>{generated}</b></td>
        </tr></table>
        <div class='rule'></div>
        <table class='summary' width='100%'>{cards}</table>
        <div class='subhead'>Детализация</div>
        <table class='data' width='100%'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
        </div>
        </body></html>"""

    def generate_selected_report(self):
        report_name = self.reports_page.current_report() or "КТГ"
        date_from, date_to = self.reports_page.get_period()
        try:
            payload = self._build_report_payload(report_name, date_from, date_to)
        except Exception as exc:
            QMessageBox.critical(self, "Отчёты", f"Не удалось сформировать отчёт:\n{exc}")
            return
        self._report_export = payload
        self.reports_page.set_preview_html(self._report_html(payload))
        self.status.showMessage(f"Отчёт «{report_name}» сформирован.", 3000)

    def _ensure_report_payload(self):
        report_name = self.reports_page.current_report() or "КТГ"
        date_from, date_to = self.reports_page.get_period()
        if not self._report_export or self._report_export.get("title") != report_name or self._report_export.get("date_from") != date_from or self._report_export.get("date_to") != date_to:
            self._report_export = self._build_report_payload(report_name, date_from, date_to)
            self.reports_page.set_preview_html(self._report_html(self._report_export))
        return self._report_export

    def export_selected_report_excel(self):
        try:
            payload = self._ensure_report_payload()
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
            safe_title = str(payload["title"]).replace("/", "_")
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт отчёта Excel", f"{safe_title}.xlsx", "Excel (*.xlsx)")
            if not path:
                return
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            wb = Workbook(); ws = wb.active; ws.title = "Отчёт"
            ws.append([payload["title"]]); ws.append([f"Период: {self._format_report_date(payload['date_from'])} — {self._format_report_date(payload['date_to'])}"])
            for key, value in payload.get("summary", []): ws.append([key, value])
            ws.append([]); ws.append(payload["headers"])
            header_row = ws.max_row
            for row in payload["rows"]: ws.append(list(row))
            for cell in ws[header_row]:
                cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="18324F"); cell.alignment = Alignment(vertical="center", wrap_text=True)
            for col in range(1, ws.max_column + 1):
                width = max(10, min(45, max((len(str(ws.cell(r, col).value or "")) for r in range(1, ws.max_row + 1)), default=10) + 2))
                ws.column_dimensions[get_column_letter(col)].width = width
            ws.freeze_panes = f"A{header_row + 1}"; ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
            wb.save(path)
            self._open_exported_file(path)
            QMessageBox.information(self, "Отчёты", "Excel-файл успешно сохранён и открыт.")
        except Exception as exc:
            QMessageBox.critical(self, "Отчёты", f"Ошибка экспорта Excel:\n{exc}")

    def export_selected_report_pdf(self):
        try:
            payload = self._ensure_report_payload()
            safe_title = str(payload["title"]).replace("/", "_")
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт отчёта PDF", f"{safe_title}.pdf", "PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setPageOrientation(QPageLayout.Portrait)
            printer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Millimeter)

            doc = QTextDocument()
            base_font = QFont("Segoe UI")
            base_font.setPointSizeF(10.0)
            doc.setDefaultFont(base_font)
            doc.setDocumentMargin(0)
            # Без явного pageSize QTextDocument иногда рассчитывает HTML на
            # узкой виртуальной странице, из-за чего таблицы в PDF занимают
            # только часть листа. Привязываем документ к печатной области.
            doc.setPageSize(printer.pageRect(QPrinter.Point).size())
            doc.setHtml(self._report_html(payload))
            doc.print_(printer)
            self._open_exported_file(path)
            QMessageBox.information(self, "Отчёты", "PDF успешно сохранён и открыт.")
        except Exception as exc:
            QMessageBox.critical(self, "Отчёты", f"Ошибка экспорта PDF:\n{exc}")

    def print_selected_report(self):
        try:
            payload = self._ensure_report_payload()
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setPageOrientation(QPageLayout.Portrait)
            printer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Millimeter)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QDialog.Accepted:
                doc = QTextDocument()
                base_font = QFont("Segoe UI")
                base_font.setPointSizeF(10.0)
                doc.setDefaultFont(base_font)
                doc.setDocumentMargin(0)
                doc.setPageSize(printer.pageRect(QPrinter.Point).size())
                doc.setHtml(self._report_html(payload))
                doc.print_(printer)
        except Exception as exc:
            QMessageBox.critical(self, "Отчёты", f"Ошибка печати:\n{exc}")

    # ==========================================================
    # NAVIGATION
    # ==========================================================

    def _select_navigation_index(self, stack_index):
        self.stack.setCurrentIndex(stack_index)
        self.page_changed(stack_index)
        for row, index in self._navigation_map.items():
            if index == stack_index:
                self.navigation.setCurrentRow(row)
                break

    def handle_quick_action(self, action_id):
        actions = {
            "add_equipment": self.add_equipment,
            "add_work": self.add_work,
            "reports": self.open_reports,
            "schedule": lambda: self._select_navigation_index(5),
            "tasks": lambda: self._select_navigation_index(11),
            "work_manager": lambda: self._select_navigation_index(2),
            "maintenance": lambda: self._select_navigation_index(6),
            "equipment": lambda: self._select_navigation_index(1),
            "settings": self.open_settings,
        }
        action = actions.get(str(action_id or ""))
        if action:
            action()

    def open_reports(self):
        self.stack.setCurrentIndex(7)
        self.page_changed(7)
        # "Сводка" в новом меню.
        for row, index in self._navigation_map.items():
            if index == 7:
                self.navigation.setCurrentRow(row)
                break
        self.generate_selected_report()

    # ==========================================================
    # NOTIFICATION CENTER
    # ==========================================================

    def refresh_notification_center(self):
        service = NotificationService(repository=self.repository)
        notifications = service.get_notifications()
        reminders = service.get_reminders(include_completed=True)
        self.notification_center_page.set_notifications(notifications)
        self.notification_center_page.set_reminders(reminders)
        self.refresh_notification_badge(
            notifications, [r for r in reminders if not r["is_completed"]]
        )

    def _notification_nav_item(self):
        for item in self._nav_items:
            if str(item.data(Qt.UserRole) or "") == "Менеджер задач":
                return item
        return None

    def refresh_notification_badge(self, notifications=None, reminders=None):
        notifications = list(notifications or [])
        reminders = list(reminders or [])
        now = datetime.now()
        due_count = 0
        for reminder in reminders:
            if reminder["is_completed"]:
                continue
            try:
                if datetime.fromisoformat(str(reminder["remind_at"])) <= now:
                    due_count += 1
            except Exception:
                pass
        count = len(notifications) + due_count
        item = self._notification_nav_item()
        if item is not None:
            base = "Менеджер задач"
            item.setData(Qt.UserRole, base)
            item.setData(Qt.UserRole + 3, count)
            item.setText("" if not self.sidebar_expanded else (f"{base}   {count}" if count else base))
            item.setToolTip(f"{base}: {count}" if count else base)

    def add_reminder(self):
        dialog = ReminderDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.reminder_data()
        self.repository.create_reminder(**data)
        self.refresh_home()
        self.refresh_notification_center()
        self.status.showMessage("Задача создана.", 3000)

    def edit_reminder(self, reminder_id):
        row = self.repository.get_reminder(reminder_id)
        if row is None:
            return
        dialog = ReminderDialog(dict(row), self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.reminder_data()
        self.repository.update_reminder(reminder_id, **data)
        self.refresh_home()
        self.refresh_notification_center()
        self.status.showMessage("Задача изменена.", 3000)

    def delete_reminder(self, reminder_id):
        row = self.repository.get_reminder(reminder_id)
        if row is None:
            return
        answer = QMessageBox.question(
            self, "Удалить задачу",
            f"Удалить задачу «{row['title']}»?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.repository.delete_reminder(reminder_id)
        self.refresh_home()
        self.refresh_notification_center()

    def complete_reminder(self, reminder_id):
        if not reminder_id:
            return
        service = NotificationService(repository=self.repository)
        service.complete_reminder(reminder_id)
        self.refresh_home()
        self.refresh_notification_center()
        self.status.showMessage("Задача выполнена.", 2500)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showNormal()
            self.raise_()
            self.activateWindow()
            for row, item in enumerate(self._nav_items):
                if str(item.data(Qt.UserRole) or "") == "Менеджер задач":
                    self.navigation.setCurrentRow(row)
                    break

    def _show_windows_notification(self, title, text, critical=False):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QSystemTrayIcon.Critical if critical else QSystemTrayIcon.Information
        self.tray_icon.showMessage(str(title), str(text), icon, 9000)

    def _system_notification_key(self, item):
        return "|".join(str(item.get(k, "")) for k in (
            "type", "work_id", "component_id", "equipment_id", "title", "text"
        ))

    def process_notification_center(self):
        service = NotificationService(repository=self.repository)

        for item in service.get_notifications():
            key = self._system_notification_key(item)
            if key in self._shown_system_notification_keys:
                continue
            self._shown_system_notification_keys.add(key)
            self._show_windows_notification(
                item.get("title") or "Журнал ТОиР",
                item.get("text") or "",
                item.get("priority") == "critical",
            )

        for reminder in service.get_due_reminders():
            if reminder["windows_notify"]:
                text = str(reminder["description"] or "").strip()
                self._show_windows_notification(
                    reminder["title"], text or "Запланированное напоминание",
                    str(reminder["priority"] or "") == "critical",
                )
            self.repository.mark_reminder_notified(reminder["id"])

        if self.stack.currentIndex() in (0, 11):
            self.refresh_home() if self.stack.currentIndex() == 0 else self.refresh_notification_center()

    def open_settings(self):
        # Настройки находятся вне QListWidget. Важно сбросить именно currentRow,
        # а не только визуальное выделение: иначе, если до настроек была открыта
        # «Главная», повторный клик по «Главной» не вызывает currentRowChanged.
        self.navigation.setCurrentRow(-1)
        self.navigation.clearSelection()
        self.stack.setCurrentIndex(8)
        self.page_changed(8)

    # ==========================================================
    # STATUS BAR
    # ==========================================================

    def update_statusbar(self):
        self.status_customer.setText(
            (
                "Заказчик: "
                f"{self.customer_name}"
            )
        )

        if self.repository.check_connection():
            self.status_database.setText("Локальная БД: активна")
        else:
            self.status_database.setText("Локальная БД: ошибка")
        sync = self.sync_service.status()
        marker = "●" if sync["online"] else "○"
        self.status_sync.setText(f"{marker} {sync['label']}")
        user = self.app_settings.load().get("user", {})
        self.status_user.setText(user.get("full_name") or "Пользователь не указан")

    # ==========================================================
    # BACKUP
    # ==========================================================

    def create_backup(self):
        settings = (
            self.repository
            .get_settings()
        )

        backup_count = 30

        if settings is not None:
            backup_count = (
                settings["backup_count"]
                or 30
            )

        service = BackupService(
            customer_name=self.customer_name,
            backup_count=backup_count,
        )

        return service.create_backup()

    # ==========================================================
    # ABOUT
    # ==========================================================

    def show_about(self):
        organization = (
            self.customer_manager
            .get_organization_name()
        )

        text = (
            "Журнал ТОиР\n\n"
            f"Версия {APP_VERSION}\n\n"
        )

        if organization:
            text += (
                f"Организация: "
                f"{organization}\n"
            )

        text += (
            f"Заказчик: "
            f"{self.customer_name}\n\n"
            "Система учета ремонтов, "
            "простоев, компонентов "
            "и технического состояния "
            "оборудования."
        )

        QMessageBox.about(
            self,
            "О программе",
            text,
        )

    # ==========================================================
    def _animate_current_page(self):
        if not self.app_settings.load().get("ui", {}).get("animations", True):
            return
        widget = self.stack.currentWidget()
        if widget is None:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.25)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._page_animation = animation
        animation.start()

    def _restore_ui_state(self):
        state = QSettings("JournalTOiR", "JournalTOiR")
        geometry = state.value("main/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        last_page = int(self.app_settings.load().get("ui", {}).get("last_page", 0) or 0)
        for row, index in getattr(self, "_navigation_map", {}).items():
            if index == last_page:
                self.navigation.setCurrentRow(row)
                break

    def _save_ui_state(self):
        state = QSettings("JournalTOiR", "JournalTOiR")
        state.setValue("main/geometry", self.saveGeometry())

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "title_bar"):
            self.title_bar.sync_window_state()


    def closeEvent(
        self,
        event,
    ):
        self._save_ui_state()
        try:
            self.sync_now(show_message=False, force=True)
        except Exception:
            pass
        try:
            self.create_backup()

        except Exception as error:
            answer = QMessageBox.question(
                self,
                "Ошибка резервного копирования",
                (
                    "Не удалось создать "
                    "резервную копию:\n\n"
                    f"{error}\n\n"
                    "Закрыть программу без "
                    "новой резервной копии?"
                ),
                QMessageBox.Yes
                | QMessageBox.No,
                QMessageBox.No,
            )

            if answer != QMessageBox.Yes:
                event.ignore()
                return

        try:
            self.repository.close()

        except Exception:
            pass

        event.accept()
