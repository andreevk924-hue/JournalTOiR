from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout
)


class PlanMaintenanceDialog(QDialog):
    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.plan = dict(plan or {})
        self.setWindowTitle("Запланировать ТО")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Техника", QLabel(self._equipment_text()))
        form.addRow("ТО", QLabel(str(self.plan.get("maintenance_name") or "ТО")))
        form.addRow("Текущая наработка", QLabel(self._hours(self.plan.get("current_hours"))))
        form.addRow("Целевая наработка", QLabel(self._hours(self.plan.get("target_hours"))))
        form.addRow("Осталось", QLabel(self._hours(self.plan.get("remaining_hours"))))

        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.date.setMinimumDate(QDate.currentDate())
        self.date.setDate(QDate.currentDate())
        form.addRow("Дата ТО", self.date)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Запланировать")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _equipment_text(self):
        model = str(self.plan.get("model") or "").strip()
        garage = str(self.plan.get("garage_number") or "").strip()
        return f"{model} — гаражный №{garage}" if garage else model

    @staticmethod
    def _hours(value):
        try:
            number = float(value or 0)
            text = str(int(number)) if number.is_integer() else f"{number:.1f}"
            return f"{text} м/ч"
        except (TypeError, ValueError):
            return str(value or "")

    def get_date(self):
        return self.date.date().toString("yyyy-MM-dd")
