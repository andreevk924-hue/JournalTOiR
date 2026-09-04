from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ReferencePage(QWidget):
    BUILTIN_ROLE = Qt.UserRole + 10

    def __init__(self, title, headers, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        label = QLabel(title)
        label.setObjectName("pageTitle")
        layout.addWidget(label)

        row = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_edit)
        row.addWidget(self.btn_delete)
        row.addStretch()
        layout.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setIconSize(QSize(150, 40))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def set_rows(self, rows):
        """Заполнить справочник.

        row может быть:
          (values, item_id)
          (values, item_id, {"builtin": bool})

        Значение ячейки может быть обычной строкой или словарём:
          {"text": "...", "icon": "/path/logo.png"}
        """
        self.table.setRowCount(0)
        for row_data in rows:
            if len(row_data) >= 3:
                values, item_id, metadata = row_data[0], row_data[1], (row_data[2] or {})
            else:
                values, item_id = row_data
                metadata = {}
            builtin = bool(metadata.get("builtin", False))

            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 48 if any(isinstance(v, dict) and v.get("icon") for v in values) else 32)

            for c, value in enumerate(values):
                item = QTableWidgetItem()
                if isinstance(value, dict):
                    item.setText(str(value.get("text", "") or ""))
                    icon_path = str(value.get("icon", "") or "")
                    if icon_path and Path(icon_path).exists():
                        item.setIcon(QIcon(icon_path))
                        item.setToolTip(Path(icon_path).name)
                else:
                    item.setText(str(value or ""))

                if c == 0:
                    item.setData(Qt.UserRole, item_id)
                    item.setData(self.BUILTIN_ROLE, builtin)
                    if builtin:
                        item.setToolTip(
                            "Встроенный производитель. Запись хранится в программе и не может быть удалена или изменена."
                        )
                self.table.setItem(r, c, item)
