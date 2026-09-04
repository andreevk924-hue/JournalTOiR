from datetime import datetime

from PySide6.QtCore import QDate, QTime, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


REPEAT_LABELS = {
    "once": "Один раз",
    "daily": "Ежедневно",
    "weekdays": "По рабочим дням",
    "weekly": "Еженедельно",
    "monthly": "Ежемесячно",
}
PRIORITY_LABELS = {
    "normal": "Обычный",
    "high": "Важный",
    "critical": "Критический",
}


class ReminderDialog(QDialog):
    def __init__(self, reminder=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Задача")
        self.setMinimumWidth(500)
        reminder = reminder or {}

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.title_edit = QLineEdit(str(reminder.get("title", "")))
        self.title_edit.setPlaceholderText("Например: отправить ежедневную сводку")
        form.addRow("Название *", self.title_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(90)
        self.description_edit.setPlainText(str(reminder.get("description", "") or ""))
        form.addRow("Описание", self.description_edit)

        due = datetime.now().replace(second=0, microsecond=0)
        raw_due = reminder.get("remind_at")
        if raw_due:
            try:
                due = datetime.fromisoformat(str(raw_due))
            except Exception:
                pass

        time_row = QWidget()
        time_layout = QHBoxLayout(time_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(8)
        self.date_edit = QDateEdit(QDate(due.year, due.month, due.day))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.time_edit = QTimeEdit(QTime(due.hour, due.minute))
        self.time_edit.setDisplayFormat("HH:mm")
        time_layout.addWidget(self.date_edit)
        time_layout.addWidget(self.time_edit)
        form.addRow("Дата и время *", time_row)

        self.repeat_combo = QComboBox()
        for key, label in REPEAT_LABELS.items():
            self.repeat_combo.addItem(label, key)
        idx = self.repeat_combo.findData(str(reminder.get("repeat_rule", "once")))
        self.repeat_combo.setCurrentIndex(max(0, idx))
        form.addRow("Повтор", self.repeat_combo)

        self.priority_combo = QComboBox()
        for key, label in PRIORITY_LABELS.items():
            self.priority_combo.addItem(label, key)
        idx = self.priority_combo.findData(str(reminder.get("priority", "normal")))
        self.priority_combo.setCurrentIndex(max(0, idx))
        form.addRow("Приоритет", self.priority_combo)

        self.windows_check = QCheckBox("Показывать уведомление Windows")
        self.windows_check.setChecked(bool(reminder.get("windows_notify", 1)))
        form.addRow("", self.windows_check)

        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Напоминание", "Укажите название напоминания.")
            return
        self.accept()

    def reminder_data(self):
        d = self.date_edit.date()
        t = self.time_edit.time()
        due = datetime(d.year(), d.month(), d.day(), t.hour(), t.minute())
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "remind_at": due.isoformat(sep=" ", timespec="minutes"),
            "repeat_rule": self.repeat_combo.currentData(),
            "priority": self.priority_combo.currentData(),
            "windows_notify": self.windows_check.isChecked(),
        }


class NotificationCenterPage(QWidget):
    add_reminder_requested = Signal()
    edit_reminder_requested = Signal(int)
    delete_reminder_requested = Signal(int)
    complete_reminder_requested = Signal(int)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reminders = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        title = QLabel("Менеджер задач")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("Уведомления программы и ваши рабочие задачи в одном месте.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # Notifications tab
        notifications_tab = QWidget()
        n_layout = QVBoxLayout(notifications_tab)
        n_layout.setContentsMargins(0, 10, 0, 0)
        n_head = QHBoxLayout()
        self.notification_count = QLabel("0 уведомлений")
        n_head.addWidget(self.notification_count)
        n_head.addStretch()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_requested)
        n_head.addWidget(refresh_btn)
        n_layout.addLayout(n_head)
        self.notifications_table = QTableWidget(0, 3)
        self.notifications_table.setHorizontalHeaderLabels(["Приоритет", "Событие", "Описание"])
        self.notifications_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notifications_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.notifications_table.verticalHeader().setVisible(False)
        self.notifications_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.notifications_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.notifications_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        n_layout.addWidget(self.notifications_table, 1)
        tabs.addTab(notifications_tab, "Уведомления")

        # Reminders tab
        reminders_tab = QWidget()
        r_layout = QVBoxLayout(reminders_tab)
        r_layout.setContentsMargins(0, 10, 0, 0)
        controls = QHBoxLayout()
        self.btn_add = QPushButton("+ Новая задача")
        self.btn_edit = QPushButton("Изменить")
        self.btn_complete = QPushButton("Выполнено")
        self.btn_delete = QPushButton("Удалить")
        controls.addWidget(self.btn_add)
        controls.addWidget(self.btn_edit)
        controls.addWidget(self.btn_complete)
        controls.addWidget(self.btn_delete)
        controls.addStretch()
        r_layout.addLayout(controls)

        self.reminders_table = QTableWidget(0, 6)
        self.reminders_table.setHorizontalHeaderLabels([
            "Статус", "Когда", "Задача", "Повтор", "Приоритет", "Windows",
        ])
        self.reminders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.reminders_table.setSelectionMode(QTableWidget.SingleSelection)
        self.reminders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.reminders_table.verticalHeader().setVisible(False)
        header = self.reminders_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        r_layout.addWidget(self.reminders_table, 1)
        tabs.addTab(reminders_tab, "Задачи")

        self.btn_add.clicked.connect(self.add_reminder_requested)
        self.btn_edit.clicked.connect(self._emit_edit)
        self.btn_complete.clicked.connect(self._emit_complete)
        self.btn_delete.clicked.connect(self._emit_delete)
        self.reminders_table.itemDoubleClicked.connect(lambda _item: self._emit_edit())

    def _selected_reminder_id(self):
        row = self.reminders_table.currentRow()
        if row < 0:
            return None
        item = self.reminders_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _emit_edit(self):
        reminder_id = self._selected_reminder_id()
        if reminder_id is not None:
            self.edit_reminder_requested.emit(int(reminder_id))

    def _emit_complete(self):
        reminder_id = self._selected_reminder_id()
        if reminder_id is not None:
            self.complete_reminder_requested.emit(int(reminder_id))

    def _emit_delete(self):
        reminder_id = self._selected_reminder_id()
        if reminder_id is not None:
            self.delete_reminder_requested.emit(int(reminder_id))

    def set_notifications(self, notifications):
        rows = list(notifications or [])
        self.notifications_table.setRowCount(len(rows))
        self.notification_count.setText(f"{len(rows)} уведомлений")
        priority_names = {"critical": "Критично", "warning": "Внимание", "normal": "Информация"}
        for r, item in enumerate(rows):
            priority = str(item.get("priority", "normal"))
            values = [
                priority_names.get(priority, priority),
                str(item.get("title", "")),
                str(item.get("text", "")),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if priority == "critical" and c == 0:
                    cell.setForeground(QBrush(QColor("#D84A52")))
                self.notifications_table.setItem(r, c, cell)
        self.notifications_table.resizeRowsToContents()

    def set_reminders(self, reminders):
        rows = list(reminders or [])
        self._reminders = {int(r["id"]): r for r in rows}
        self.reminders_table.setRowCount(len(rows))
        now = datetime.now()
        for r, row in enumerate(rows):
            try:
                due = datetime.fromisoformat(str(row["remind_at"]))
                due_text = due.strftime("%d.%m.%Y %H:%M")
            except Exception:
                due = now
                due_text = str(row["remind_at"] or "")
            completed = bool(row["is_completed"])
            overdue = (not completed) and due < now
            status = "Выполнено" if completed else ("Просрочено" if overdue else "Запланировано")
            title = str(row["title"] or "")
            desc = str(row["description"] or "").strip()
            if desc:
                title = f"{title}\n{desc}"
            values = [
                status,
                due_text,
                title,
                REPEAT_LABELS.get(str(row["repeat_rule"] or "once"), str(row["repeat_rule"] or "")),
                PRIORITY_LABELS.get(str(row["priority"] or "normal"), str(row["priority"] or "")),
                "Да" if row["windows_notify"] else "Нет",
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if c == 0:
                    cell.setData(Qt.UserRole, int(row["id"]))
                if completed:
                    cell.setForeground(QBrush(QColor("#7F8C9A")))
                elif overdue and c in (0, 1):
                    cell.setForeground(QBrush(QColor("#D84A52")))
                self.reminders_table.setItem(r, c, cell)
        self.reminders_table.resizeRowsToContents()
