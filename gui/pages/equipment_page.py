from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QDoubleSpinBox,
    QWidget,
)


class EquipmentPage(QWidget):

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.create_ui()

    def create_ui(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        layout.setSpacing(12)

        title = QLabel(
            "Техника"
        )

        title.setObjectName("pageTitle")

        layout.addWidget(title)

        filters_layout = QHBoxLayout()

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Поиск по модели, S/N, "
            "гаражному или гос. номеру..."
        )

        self.search.setClearButtonEnabled(
            True
        )

        self.status_filter = QComboBox()

        self.status_filter.addItems(
            [
                "Все",
                "В работе",
                "В простое",
                "Списан",
            ]
        )

        filters_layout.addWidget(
            self.search,
            1,
        )

        filters_layout.addWidget(
            QLabel("Статус:")
        )

        filters_layout.addWidget(
            self.status_filter
        )

        layout.addLayout(filters_layout)

        advanced = QHBoxLayout()
        self.manufacturer_filter = QComboBox()
        self.manufacturer_filter.addItem("Все производители", None)
        self.distributor_filter = QComboBox()
        self.distributor_filter.addItem("Все дистрибьюторы", None)
        self.service_filter = QComboBox()
        self.service_filter.addItems(["Все по гарантии", "Гарантийное", "Постгарантийное"])
        self.hours_min = QDoubleSpinBox(); self.hours_min.setRange(0, 100000000); self.hours_min.setPrefix("от ")
        self.hours_max = QDoubleSpinBox(); self.hours_max.setRange(0, 100000000); self.hours_max.setSpecialValueText("без ограничения"); self.hours_max.setPrefix("до ")
        self.btn_reset_filters = QPushButton("Сбросить фильтры")
        advanced.addWidget(QLabel("Производитель:")); advanced.addWidget(self.manufacturer_filter)
        advanced.addWidget(QLabel("Поставщик:")); advanced.addWidget(self.distributor_filter)
        advanced.addWidget(QLabel("Обслуживание:")); advanced.addWidget(self.service_filter)
        advanced.addWidget(QLabel("Наработка:")); advanced.addWidget(self.hours_min); advanced.addWidget(self.hours_max)
        advanced.addWidget(self.btn_reset_filters)
        layout.addLayout(advanced)

        buttons_layout = QHBoxLayout()

        self.btn_add = QPushButton(
            "Добавить"
        )
        self.btn_add.setProperty("primary", True)

        self.btn_edit = QPushButton(
            "Редактировать"
        )

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setProperty("danger", True)
        self.btn_export_pdf = QPushButton("Выгрузить список в PDF")

        buttons_layout.addWidget(
            self.btn_add
        )

        buttons_layout.addWidget(
            self.btn_edit
        )

        buttons_layout.addWidget(self.btn_delete)
        buttons_layout.addWidget(self.btn_export_pdf)
        buttons_layout.addStretch()

        layout.addLayout(
            buttons_layout
        )

        self.table = QTableWidget()

        self.table.setColumnCount(11)

        self.table.setHorizontalHeaderLabels(
            [
                "Модель",
                "Серийный номер",
                "Гаражный номер",
                "Гос. номер",
                "Год",
                "Наработка",
                "Статус",
                "Примечание",
                "Производитель",
                "Дистрибьютор",
                "Статус обслуживания",
            ]
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.setSortingEnabled(
            True
        )

        self.table.verticalHeader().setVisible(
            False
        )

        header = self.table.horizontalHeader()

        # Пользователь может свободно менять ширину всех столбцов.
        header.setSectionResizeMode(
            QHeaderView.Interactive
        )
        header.setStretchLastSection(True)

        layout.addWidget(
            self.table,
            1,
        )

    def clear(self):
        sorting = self.table.isSortingEnabled()

        self.table.setSortingEnabled(
            False
        )

        self.table.setRowCount(0)

        self.table.setSortingEnabled(
            sorting
        )

    def add_equipment(
        self,
        model,
        serial_number,
        garage_number,
        registration_number,
        manufacture_year,
        current_hours,
        status,
        note,
        manufacturer="",
        distributor="",
        service_status="",
    ):
        sorting = self.table.isSortingEnabled()

        self.table.setSortingEnabled(
            False
        )

        row = self.table.rowCount()

        self.table.insertRow(row)

        values = [
            model,
            serial_number,
            garage_number,
            registration_number,
            manufacture_year,
            current_hours,
            status,
            note,
            manufacturer,
            distributor,
            service_status,
        ]

        for column, value in enumerate(values):
            if value is None:
                value = ""

            if column == 5:
                try:
                    number = float(value)

                    if number.is_integer():
                        text = str(
                            int(number)
                        )
                    else:
                        text = (
                            f"{number:.1f}"
                        )

                except (
                    TypeError,
                    ValueError,
                ):
                    text = str(value)

            else:
                text = str(value)

            item = QTableWidgetItem(
                text
            )

            if column in (
                4,
                5,
            ):
                item.setTextAlignment(
                    Qt.AlignCenter
                )

            self.table.setItem(
                row,
                column,
                item,
            )

        self.table.setSortingEnabled(
            sorting
        )

    def get_selected_row(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        return row
