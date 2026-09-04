from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QDialogButtonBox,
    QFormLayout, QDateEdit, QComboBox, QLineEdit, QDoubleSpinBox, QTextEdit,
    QMessageBox,
)


class DailyEntryDialog(QDialog):
    def __init__(self, parent=None, default_executors="", default_hours=0):
        super().__init__(parent)
        self.setWindowTitle("Запись за день")
        self.resize(760, 520)
        self.setMinimumSize(680, 460)
        form = QFormLayout(self)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignTop)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.day_type = QComboBox()
        self.day_type.addItems([
            "Аварийный ремонт",
            "Плановый ремонт",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
            "Простой",
        ])
        self.description = QTextEdit()
        self.description.setMinimumHeight(170)
        self.executors = QLineEdit(default_executors)
        self.hours = QDoubleSpinBox()
        self.hours.setMaximum(9999999)
        self.hours.setDecimals(1)
        self.hours.setValue(float(default_hours or 0))
        form.addRow("Дата", self.date)
        form.addRow("Состояние дня", self.day_type)
        form.addRow("Что происходило / выполнено", self.description)
        form.addRow("Исполнители", self.executors)
        form.addRow("Наработка", self.hours)
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        btn_save = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        buttons_row.addWidget(btn_save)
        buttons_row.addWidget(btn_cancel)
        form.addRow(buttons_row)

    def get_data(self):
        return {
            "work_date": self.date.date().toString("yyyy-MM-dd"),
            "day_type": self.day_type.currentText(),
            "description": self.description.toPlainText().strip(),
            "executors": self.executors.text().strip(),
            "machine_hours": self.hours.value(),
        }


class DowntimeCardDialog(QDialog):
    def __init__(self, repository, work_id, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.work_id = work_id
        self.setWindowTitle("Карточка простоя / ремонта")
        self.resize(950, 560)

        root = QVBoxLayout(self)
        work = repository.get_work(work_id)
        if work is None:
            raise ValueError("Карточка простоя не найдена.")

        title = QLabel(
            f"{work['model']} №{work['garage_number']}   |   "
            f"Заявка: {work['request_number'] or '—'}   |   "
            f"Начало: {work['date_start'] or '—'}"
        )
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel(
            "Одна карточка может содержать разные состояния по дням: "
            "ремонт, простой, работы заказчика и т.д."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Добавить / изменить день")
        self.btn_delete = QPushButton("Удалить день")
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_delete)
        buttons.addStretch()
        root.addLayout(buttons)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Состояние дня", "Описание",
            "Исполнители", "Наработка",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        root.addWidget(close)

        self.btn_add.clicked.connect(self.add_day)
        self.btn_delete.clicked.connect(self.delete_day)
        self.table.itemDoubleClicked.connect(lambda _item: self.add_day())
        self.refresh()

    def refresh(self):
        rows = self.repository.get_work_daily_log(self.work_id)
        self.table.setRowCount(0)
        for data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                data["work_date"], data["day_type"],
                data["description"] or "", data["executors"] or "",
                data["machine_hours"] or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, data["id"])
                self.table.setItem(row, col, item)

    def add_day(self):
        dialog = DailyEntryDialog(self)
        row = self.table.currentRow()
        if row >= 0:
            # Двойной клик/выбранная строка = редактирование этого дня.
            date_item = self.table.item(row, 0)
            type_item = self.table.item(row, 1)
            desc_item = self.table.item(row, 2)
            exec_item = self.table.item(row, 3)
            hours_item = self.table.item(row, 4)
            parsed = QDate.fromString(date_item.text(), "yyyy-MM-dd")
            if parsed.isValid():
                dialog.date.setDate(parsed)
            idx = dialog.day_type.findText(type_item.text())
            if idx >= 0:
                dialog.day_type.setCurrentIndex(idx)
            dialog.description.setText(desc_item.text())
            dialog.executors.setText(exec_item.text())
            try:
                dialog.hours.setValue(float(hours_item.text() or 0))
            except ValueError:
                pass
        if not dialog.exec():
            return
        data = dialog.get_data()
        self.repository.add_work_daily_entry(
            self.work_id, **data
        )
        self.refresh()

    def delete_day(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        entry_id = item.data(Qt.UserRole)
        if QMessageBox.question(
            self, "Удаление", "Удалить запись за этот день?"
        ) != QMessageBox.Yes:
            return
        self.repository.delete_work_daily_entry(entry_id)
        self.refresh()
