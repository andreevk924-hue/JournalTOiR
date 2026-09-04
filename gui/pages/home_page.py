from pathlib import Path

from PySide6.QtCore import QDate, QRectF, QTime, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCalendarWidget,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)



from gui.theme import create_nav_icon

def _shadow(widget, blur=22, y=4, alpha=18):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(18, 43, 72, alpha))
    widget.setGraphicsEffect(effect)





class IndustrialBackdrop(QWidget):
    """Шапка главного экрана с готовым растровым industrial-баннером."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "industrial_header.png"
        )
        self._pixmap = QPixmap(str(self._image_path))
        self._dark_pixmap = QPixmap()
        self.setAttribute(Qt.WA_StyledBackground, True)

    def _pixmap_for_theme(self):
        theme = str(QApplication.instance().property("appTheme") or "light").lower()
        if theme != "dark":
            return self._pixmap
        if self._dark_pixmap.isNull() and not self._pixmap.isNull():
            self._dark_pixmap = self._pixmap.copy()
            tint = QPainter(self._dark_pixmap)
            tint.setCompositionMode(QPainter.CompositionMode_SourceIn)
            tint.fillRect(self._dark_pixmap.rect(), QColor("#E4EDF7"))
            tint.end()
        return self._dark_pixmap if not self._dark_pixmap.isNull() else self._pixmap

    def paintEvent(self, event):
        super().paintEvent(event)
        pixmap = self._pixmap_for_theme()
        if pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Картинка занимает правую часть шапки. Слева остаётся чистая зона
        # для приветствия, логотипа и названия организации.
        h = max(1, self.height() - 2)
        scaled = pixmap.scaled(
            max(520, int(self.width() * 0.62)),
            h,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        x = self.width() - scaled.width()
        y = (self.height() - scaled.height()) // 2
        painter.setOpacity(0.38 if str(QApplication.instance().property("appTheme") or "light").lower() == "light" else 0.18)
        painter.drawPixmap(x, y, scaled)
        painter.end()


class StatCard(QFrame):
    def __init__(self, title, value="0", icon_kind="equipment", accent="blue", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(90)
        self.setMaximumHeight(102)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        accent_colors = {
            "blue": "#2563C7",
            "violet": "#7357C7",
            "amber": "#C87818",
            "green": "#27825D",
        }
        accent_color = accent_colors.get(accent, "#2563C7")

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 13, 15, 13)
        root.setSpacing(10)

        # KPI-карточки намеренно без декоративных иконок: только данные.
        # Узкая акцентная линия помогает быстро различать категории и не
        # перегружает главный экран.
        accent_bar = QFrame()
        accent_bar.setFixedSize(4, 48)
        accent_bar.setStyleSheet(
            f"background:{accent_color};border:none;border-radius:2px;"
        )
        root.addWidget(accent_bar, 0, Qt.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("kpiTitle")
        self.title_label.setWordWrap(True)
        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("kpiValue")
        text.addWidget(self.title_label)
        text.addWidget(self.value_label)
        root.addLayout(text, 1)

        _shadow(self, blur=16, y=3, alpha=12)

    def set_value(self, value):
        self.value_label.setText(str(value))


class HomePage(QWidget):
    """Главная страница Industrial Premium."""

    reminder_completed = Signal(int)
    quick_action_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.create_ui()

    def create_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(11)

        header = IndustrialBackdrop()
        self.backdrop = header
        header.setObjectName("homeHeader")
        header.setMinimumHeight(170)
        header.setMaximumHeight(190)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)

        identity = QHBoxLayout()
        identity.setSpacing(14)
        identity.setContentsMargins(0, 10, 0, 0)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("organizationLogo")
        self.logo_label.setFixedSize(92, 92)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setScaledContents(False)
        self.logo_label.setStyleSheet(
            "QLabel#organizationLogo{background:rgba(255,255,255,235);"
            "border:1px solid #D9E3EC;border-radius:12px;padding:6px;}"
        )
        identity.addWidget(self.logo_label, 0, Qt.AlignTop)

        left = QVBoxLayout()
        left.setContentsMargins(0, 5, 0, 0)
        left.setSpacing(4)
        self.user_name = ""
        self.greeting_label = QLabel()
        self.greeting_label.setObjectName("homeGreeting")
        self.organization_label = QLabel("Организация не указана")
        self.organization_label.setObjectName("homeOrganization")
        self.organization_label.setWordWrap(True)
        self.customer_label = QLabel("Заказчик не выбран")
        self.customer_label.setObjectName("homeCustomer")
        self.customer_label.setWordWrap(True)
        self.page_title = QLabel("Журнал технического обслуживания и ремонтов")
        self.page_title.setObjectName("homeSubtitle")
        left.addWidget(self.greeting_label)
        left.addWidget(self.organization_label)
        left.addWidget(self.customer_label)
        left.addWidget(self.page_title)
        left.addStretch()
        identity.addLayout(left, 1)
        header_layout.addLayout(identity, 1)

        calendar_frame = QFrame()
        calendar_frame.setObjectName("homeCalendar")
        calendar_frame.setFixedWidth(234)
        calendar_frame.setMinimumHeight(150)
        calendar_layout = QVBoxLayout(calendar_frame)
        calendar_layout.setContentsMargins(10, 8, 10, 8)
        calendar_layout.setSpacing(3)
        self.current_time_label = QLabel()
        self.current_time_label.setObjectName("homeClock")
        self.current_time_label.setAlignment(Qt.AlignCenter)
        calendar_layout.addWidget(self.current_time_label)
        self.calendar = QCalendarWidget()
        self.calendar.setObjectName("homeCalendarWidget")
        self.calendar.setSelectedDate(QDate.currentDate())
        self.calendar.setGridVisible(False)
        self.calendar.setNavigationBarVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
        self.calendar.setMinimumSize(212, 112)
        self.calendar.setMaximumHeight(118)
        calendar_layout.addWidget(self.calendar)
        header_layout.addWidget(calendar_frame, 0, Qt.AlignTop | Qt.AlignRight)
        _shadow(calendar_frame, blur=18, y=3, alpha=12)

        root.addWidget(header)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(0)
        self.total_equipment_card = StatCard("Всего техники", icon_kind="equipment", accent="blue")
        self.customer_work_card = StatCard("Работы заказчика", icon_kind="customer_wrench", accent="violet")
        self.active_work_card = StatCard("Активные ремонты / простои", icon_kind="repair_alt", accent="amber")
        self.components_card = StatCard("Компоненты на контроле", icon_kind="check_engine", accent="green")
        for col, card in enumerate(
            (
                self.total_equipment_card,
                self.customer_work_card,
                self.active_work_card,
                self.components_card,
            )
        ):
            stats.addWidget(card, 0, col)
            stats.setColumnStretch(col, 1)
        root.addLayout(stats)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)

        downtimes_frame = self._content_panel("Текущие ремонты / простои")
        self.downtimes_scroll = QScrollArea()
        self.downtimes_scroll.setWidgetResizable(True)
        self.downtimes_scroll.setFrameShape(QFrame.NoFrame)
        self.downtimes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.downtimes_container = QWidget()
        self.downtimes_layout = QVBoxLayout(self.downtimes_container)
        self.downtimes_layout.setContentsMargins(0, 0, 0, 0)
        self.downtimes_layout.setSpacing(5)
        self.downtimes_layout.addStretch()
        self.downtimes_scroll.setWidget(self.downtimes_container)
        downtimes_frame.layout().addWidget(self.downtimes_scroll, 1)

        notifications_frame = self._content_panel("Уведомления")
        self.notifications_scroll = QScrollArea()
        self.notifications_scroll.setWidgetResizable(True)
        self.notifications_scroll.setFrameShape(QFrame.NoFrame)
        self.notifications_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setContentsMargins(0, 0, 0, 0)
        self.notifications_layout.setSpacing(5)
        self.notifications_layout.addStretch()
        self.notifications_scroll.setWidget(self.notifications_container)
        notifications_frame.layout().addWidget(self.notifications_scroll, 1)

        reminders_frame = self._content_panel("Напоминания")
        self.reminders_scroll = QScrollArea()
        self.reminders_scroll.setWidgetResizable(True)
        self.reminders_scroll.setFrameShape(QFrame.NoFrame)
        self.reminders_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reminders_container = QWidget()
        self.reminders_layout = QVBoxLayout(self.reminders_container)
        self.reminders_layout.setContentsMargins(0, 0, 0, 0)
        self.reminders_layout.setSpacing(5)
        self.reminders_layout.addStretch()
        self.reminders_scroll.setWidget(self.reminders_container)
        reminders_frame.layout().addWidget(self.reminders_scroll, 1)

        info_row.addWidget(downtimes_frame, 1)
        info_row.addWidget(notifications_frame, 1)
        info_row.addWidget(reminders_frame, 1)
        root.addLayout(info_row, 1)

        actions_frame = QFrame()
        actions_frame.setObjectName("quickActions")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(12, 9, 12, 9)
        actions_layout.setSpacing(8)
        title = QLabel("Быстрые действия")
        title.setObjectName("quickTitle")
        actions_layout.addWidget(title)
        actions_layout.addSpacing(4)

        self.quick_actions_layout = actions_layout
        self.quick_action_buttons = []
        for _ in range(4):
            button = QPushButton()
            button.setProperty("quickAction", True)
            button.setMinimumHeight(34)
            button.clicked.connect(
                lambda checked=False, b=button:
                self.quick_action_requested.emit(str(b.property("actionId") or ""))
            )
            self.quick_action_buttons.append(button)
            actions_layout.addWidget(button)
        actions_layout.addStretch()
        root.addWidget(actions_frame)

        self.apply_quick_actions(["add_equipment", "add_work", "reports", "settings"])

        self.organization = self.organization_label
        self.customer = self.customer_label

        self.apply_visual_theme(str(QApplication.instance().property("appTheme") or "light"))

    QUICK_ACTIONS = {
        "add_equipment": ("Добавить технику", "equipment"),
        "add_work": ("Добавить работу", "repair"),
        "reports": ("Сводка", "chart"),
        "schedule": ("График работ", "schedule"),
        "tasks": ("Менеджер задач", "bell"),
        "work_manager": ("Менеджер простоев", "downtime"),
        "maintenance": ("Планирование ТО", "maintenance"),
        "equipment": ("Техника", "equipment"),
        "settings": ("Настройки", "settings"),
    }

    def apply_quick_actions(self, action_ids):
        action_ids = list(action_ids or [])
        defaults = ["add_equipment", "add_work", "reports", "settings"]
        while len(action_ids) < 4:
            action_ids.append(defaults[len(action_ids)])
        for button, action_id in zip(self.quick_action_buttons, action_ids[:4]):
            title, icon_kind = self.QUICK_ACTIONS.get(action_id, self.QUICK_ACTIONS["settings"])
            button.setText(title)
            button.setIcon(create_nav_icon(icon_kind, "#225DB5", 18))
            button.setProperty("actionId", action_id)
            button.setToolTip(title)

    def _content_panel(self, title):
        frame = QFrame()
        frame.setObjectName("contentCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        _shadow(frame, blur=18, y=3, alpha=12)
        return frame

    def _display_first_name(self):
        parts = [p for p in str(self.user_name or "").strip().split() if p]
        if not parts:
            return ""
        # ФИО обычно хранится как «Фамилия Имя Отчество».
        return parts[1] if len(parts) >= 3 else parts[0]

    def _update_greeting(self, hour=None):
        hour = QTime.currentTime().hour() if hour is None else int(hour)
        if 5 <= hour < 12:
            greeting = "Доброе утро"
        elif 12 <= hour < 18:
            greeting = "Добрый день"
        elif 18 <= hour < 23:
            greeting = "Добрый вечер"
        else:
            greeting = "Доброй ночи"
        first_name = self._display_first_name()
        self.greeting_label.setText(
            f"{greeting}, {first_name}!" if first_name else f"{greeting}!"
        )

    def update_clock(self):
        now_date = QDate.currentDate()
        now_time = QTime.currentTime()
        self.current_time_label.setText(
            f"{now_time.toString('HH:mm:ss')}   ·   {now_date.toString('dd.MM.yyyy')}"
        )
        self.current_time_label.setAlignment(Qt.AlignCenter)
        self._update_greeting(now_time.hour())
        if getattr(self, "_clock_date", None) != now_date:
            self.calendar.setSelectedDate(now_date)
            self._clock_date = now_date

    def set_user_name(self, full_name):
        self.user_name = str(full_name or "").strip()
        self._update_greeting()

    def apply_visual_theme(self, theme="light"):
        """Изолирует календарь от системной палитры Windows."""
        light = str(theme or "light").lower() != "dark"
        if light:
            bg, fg, muted, hover, accent, grid = (
                "#FFFFFF",
                "#23384F",
                "#8A99AA",
                "#EEF4FA",
                "#1F62BD",
                "#E5EBF1",
            )
        else:
            bg, fg, muted, hover, accent, grid = (
                "#0F1B2A",
                "#E5EDF7",
                "#8497AD",
                "#182C45",
                "#2767C7",
                "#26394E",
            )
        self.calendar.setStyleSheet(
            f"""
            QCalendarWidget {{ background:{bg}; color:{fg}; border:none; }}
            QCalendarWidget QWidget {{ background:{bg}; color:{fg}; }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{ background:{bg}; }}
            QCalendarWidget QToolButton {{
                color:{fg}; background:{bg}; border:none; border-radius:5px;
                padding:2px 5px; font-size:10px; font-weight:600;
            }}
            QCalendarWidget QToolButton:hover {{ background:{hover}; }}
            QCalendarWidget QSpinBox {{ color:{fg}; background:{bg}; border:none; font-size:10px; }}
            QCalendarWidget QMenu {{ color:{fg}; background:{bg}; border:1px solid {grid}; }}
            QCalendarWidget QAbstractItemView:enabled {{
                color:{fg}; background:{bg}; selection-background-color:{accent};
                selection-color:#FFFFFF; outline:none; font-size:10px;
            }}
            QCalendarWidget QAbstractItemView:disabled {{ color:{muted}; background:{bg}; }}
            """
        )
        palette = self.calendar.palette()
        for role, hex_color in (
            (QPalette.Window, bg),
            (QPalette.Base, bg),
            (QPalette.AlternateBase, bg),
            (QPalette.Text, fg),
            (QPalette.WindowText, fg),
            (QPalette.Button, bg),
            (QPalette.ButtonText, fg),
            (QPalette.Highlight, accent),
        ):
            palette.setColor(role, QColor(hex_color))
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
        self.calendar.setPalette(palette)
        view = self.calendar.findChild(QAbstractItemView)
        if view is not None:
            view.setAutoFillBackground(True)
            view.setPalette(palette)
        if hasattr(self, "backdrop"):
            self.backdrop.update()

    def set_organization(self, organization):
        organization = str(organization or "").strip()
        self.organization_label.setText(organization or "Организация не указана")

    def set_customer(self, customer):
        customer = str(customer or "").strip()
        self.customer_label.setText(
            f"Заказчик: {customer}" if customer else "Заказчик не выбран"
        )

    def set_logo(self, logo_path):
        self.logo_label.clear()
        path = str(logo_path or "").strip()
        if not path or not Path(path).exists():
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        pixmap = pixmap.scaled(
            78,
            78,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.logo_label.setPixmap(pixmap)

    def set_statistics(self, total_equipment, customer_work, active_work, components):
        self.total_equipment_card.set_value(total_equipment)
        self.customer_work_card.set_value(customer_work)
        self.active_work_card.set_value(active_work)
        self.components_card.set_value(components)

    def clear_downtimes(self):
        while self.downtimes_layout.count() > 1:
            item = self.downtimes_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _feed_item(self, text, accent="#C47A1D"):
        shell = QFrame()
        shell.setObjectName("feedItem")
        row = QHBoxLayout(shell)
        row.setContentsMargins(9, 6, 9, 6)
        row.setSpacing(8)
        marker = QFrame()
        marker.setFixedWidth(3)
        marker.setStyleSheet(
            f"background:{accent};border:none;border-radius:1px;"
        )
        label = QLabel(str(text))
        label.setObjectName("feedText")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(marker)
        row.addWidget(label, 1)
        return shell

    def add_downtime(self, text):
        self.downtimes_layout.insertWidget(
            max(0, self.downtimes_layout.count() - 1),
            self._feed_item(text, "#C87818"),
        )

    def clear_notifications(self):
        while self.notifications_layout.count() > 1:
            item = self.notifications_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_notification(self, text):
        self.notifications_layout.insertWidget(
            max(0, self.notifications_layout.count() - 1),
            self._feed_item(text, "#225DB5"),
        )
    def clear_reminders(self):
        while self.reminders_layout.count() > 1:
            item = self.reminders_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_reminder(self, reminder_id, title, when_text="", overdue=False):
        shell = QFrame()
        shell.setObjectName("feedItem")
        row = QHBoxLayout(shell)
        row.setContentsMargins(9, 6, 9, 6)
        row.setSpacing(8)
        check = QCheckBox()
        check.setToolTip("Отметить выполненным")
        if int(reminder_id):
            # toggled(bool) надёжнее stateChanged(int): в PySide6 stateChanged
            # возвращает число, из-за чего сравнение с Qt.Checked могло не сработать.
            check.toggled.connect(
                lambda checked, rid=int(reminder_id): self.reminder_completed.emit(rid)
                if checked else None
            )
        else:
            check.setVisible(False)
        text = QLabel(
            (f"<b>{title}</b>" + (f"<br><span>{when_text}</span>" if when_text else ""))
        )
        text.setWordWrap(True)
        text.setObjectName("feedText")
        if overdue:
            text.setStyleSheet("color:#C94141;")
        row.addWidget(check, 0, Qt.AlignTop)
        row.addWidget(text, 1)
        self.reminders_layout.insertWidget(
            max(0, self.reminders_layout.count() - 1), shell
        )

