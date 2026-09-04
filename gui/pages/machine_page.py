from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MachinePage(QWidget):

    equipment_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_equipment_id = None
        self.equipment_rows = []

        self.create_ui()
        self.connect_signals()

    # ==========================================================
    # UI
    # ==========================================================

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
            "Детализация по машинам"
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 24px;
                font-weight: 700;
            }
            """
        )

        layout.addWidget(title)

        # ======================================================
        # MACHINE SELECTION
        # ======================================================

        selection_frame = QFrame()

        selection_layout = QVBoxLayout(
            selection_frame
        )

        selection_layout.setContentsMargins(
            15,
            15,
            15,
            15,
        )

        selection_layout.setSpacing(10)

        selection_title = QLabel(
            "Выбор техники"
        )

        selection_title.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: 600;
            }
            """
        )

        selection_layout.addWidget(
            selection_title
        )

        filters_layout = QHBoxLayout()

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Поиск по модели, серийному, "
            "гаражному или гос. номеру..."
        )

        self.search.setClearButtonEnabled(
            True
        )

        self.model_filter = QComboBox()

        self.model_filter.setMinimumWidth(
            200
        )

        self.model_filter.addItem(
            "Все модели"
        )

        filters_layout.addWidget(
            self.search,
            1,
        )

        filters_layout.addWidget(
            QLabel("Модель:")
        )

        filters_layout.addWidget(
            self.model_filter
        )

        selection_layout.addLayout(
            filters_layout
        )

        # ======================================================
        # DIRECT MACHINE SELECTION
        # ======================================================

        combo_layout = QHBoxLayout()

        combo_layout.addWidget(
            QLabel("Выбрать машину:")
        )

        self.equipment_combo = QComboBox()

        self.equipment_combo.setMinimumWidth(
            450
        )

        self.equipment_combo.setMaxVisibleItems(
            25
        )

        combo_layout.addWidget(
            self.equipment_combo,
            1,
        )

        selection_layout.addLayout(
            combo_layout
        )

        # ======================================================
        # EQUIPMENT TABLE
        # ======================================================

        self.equipment_table = QTableWidget()

        self.equipment_table.setColumnCount(
            4
        )

        self.equipment_table.setHorizontalHeaderLabels(
            [
                "Модель",
                "Серийный номер",
                "Гаражный номер",
                "Статус",
            ]
        )

        self.equipment_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.equipment_table.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.equipment_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.equipment_table.setAlternatingRowColors(
            True
        )

        self.equipment_table.verticalHeader().setVisible(
            False
        )

        self.equipment_table.setMaximumHeight(
            230
        )

        header = (
            self.equipment_table
            .horizontalHeader()
        )

        header.setSectionResizeMode(
            QHeaderView.Stretch
        )

        selection_layout.addWidget(
            self.equipment_table
        )

        layout.addWidget(
            selection_frame
        )

        # ======================================================
        # MACHINE CARD
        # ======================================================

        self.machine_frame = QFrame()

        machine_layout = QVBoxLayout(
            self.machine_frame
        )

        machine_layout.setContentsMargins(
            15,
            15,
            15,
            15,
        )

        machine_layout.setSpacing(12)

        card_header = QHBoxLayout()

        self.machine_title = QLabel(
            "Машина не выбрана"
        )

        self.machine_title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: 700;
            }
            """
        )
        self.machine_title.setWordWrap(True)
        self.machine_title.setMinimumWidth(0)

        card_header.addWidget(
            self.machine_title,
            1,
        )

        self.btn_components = QPushButton(
            "Компоненты"
        )

        self.btn_components.setEnabled(
            False
        )
        self.btn_components.setMinimumWidth(120)

        card_header.addWidget(
            self.btn_components
        )

        machine_layout.addLayout(
            card_header
        )

        info_layout = QGridLayout()

        info_layout.setHorizontalSpacing(
            30
        )

        info_layout.setVerticalSpacing(
            8
        )

        self.model_value = QLabel("—")
        self.serial_value = QLabel("—")
        self.garage_value = QLabel("—")
        self.registration_value = QLabel("—")
        self.year_value = QLabel("—")
        self.hours_value = QLabel("—")
        self.status_value = QLabel("—")

        # Keep long machine data inside its own grid cells instead of letting
        # labels crowd/cover neighbouring interface elements.
        for value_label in (
            self.model_value,
            self.serial_value,
            self.garage_value,
            self.registration_value,
            self.year_value,
            self.hours_value,
            self.status_value,
        ):
            value_label.setWordWrap(True)
            value_label.setMinimumWidth(120)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        info_layout.setColumnStretch(0, 0)
        info_layout.setColumnStretch(1, 1)
        info_layout.setColumnStretch(2, 0)
        info_layout.setColumnStretch(3, 1)

        info_layout.addWidget(
            QLabel("Модель:"),
            0,
            0,
        )

        info_layout.addWidget(
            self.model_value,
            0,
            1,
        )

        info_layout.addWidget(
            QLabel("Серийный номер:"),
            0,
            2,
        )

        info_layout.addWidget(
            self.serial_value,
            0,
            3,
        )

        info_layout.addWidget(
            QLabel("Гаражный номер:"),
            1,
            0,
        )

        info_layout.addWidget(
            self.garage_value,
            1,
            1,
        )

        info_layout.addWidget(
            QLabel("Гос. номер:"),
            1,
            2,
        )

        info_layout.addWidget(
            self.registration_value,
            1,
            3,
        )

        info_layout.addWidget(
            QLabel("Год выпуска:"),
            2,
            0,
        )

        info_layout.addWidget(
            self.year_value,
            2,
            1,
        )

        info_layout.addWidget(
            QLabel("Наработка:"),
            2,
            2,
        )

        info_layout.addWidget(
            self.hours_value,
            2,
            3,
        )

        info_layout.addWidget(
            QLabel("Статус:"),
            3,
            0,
        )

        info_layout.addWidget(
            self.status_value,
            3,
            1,
            1,
            3,
        )

        machine_layout.addLayout(
            info_layout
        )

        self.note_label = QLabel()

        self.note_label.setWordWrap(
            True
        )

        self.note_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.note_label.hide()

        machine_layout.addWidget(
            self.note_label
        )

        layout.addWidget(
            self.machine_frame
        )

        # ======================================================
        # WORK HISTORY
        # ======================================================

        history_title = QLabel(
            "История работ"
        )

        history_title.setStyleSheet(
            """
            QLabel {
                font-size: 17px;
                font-weight: 600;
            }
            """
        )

        layout.addWidget(
            history_title
        )

        self.history_table = QTableWidget()

        self.history_table.setColumnCount(
            9
        )

        self.history_table.setHorizontalHeaderLabels(
            [
                "Заявка",
                "Тип",
                "Начало",
                "Окончание",
                "Состояние",
                "Наработка",
                "Описание",
                "Исполнители",
                "Отчет",
            ]
        )

        self.history_table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.history_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.history_table.setAlternatingRowColors(
            True
        )

        self.history_table.verticalHeader().setVisible(
            False
        )

        history_header = (
            self.history_table
            .horizontalHeader()
        )

        history_header.setSectionResizeMode(
            QHeaderView.ResizeToContents
        )

        history_header.setSectionResizeMode(
            6,
            QHeaderView.Stretch,
        )

        layout.addWidget(
            self.history_table,
            1,
        )

    # ==========================================================
    # SIGNALS
    # ==========================================================

    def connect_signals(self):
        self.search.textChanged.connect(
            self.apply_filters
        )

        self.model_filter.currentTextChanged.connect(
            self.apply_filters
        )

        self.equipment_combo.currentIndexChanged.connect(
            self.combo_selection_changed
        )

        self.equipment_table.itemSelectionChanged.connect(
            self.table_selection_changed
        )

    # ==========================================================
    # EQUIPMENT
    # ==========================================================

    def set_equipment(self, rows):
        selected_id = (
            self.current_equipment_id
        )

        self.equipment_rows = list(
            rows
        )

        models = sorted(
            {
                str(
                    row["model"] or ""
                ).strip()
                for row in self.equipment_rows
                if row["model"]
            },
            key=str.lower,
        )

        current_model = (
            self.model_filter.currentText()
        )

        self.model_filter.blockSignals(
            True
        )

        self.model_filter.clear()

        self.model_filter.addItem(
            "Все модели"
        )

        self.model_filter.addItems(
            models
        )

        index = self.model_filter.findText(
            current_model
        )

        if index >= 0:
            self.model_filter.setCurrentIndex(
                index
            )

        self.model_filter.blockSignals(
            False
        )

        self.apply_filters()

        if selected_id is not None:
            self.select_equipment(
                selected_id
            )

    # ==========================================================
    # FILTER
    # ==========================================================

    def apply_filters(self):
        search_text = (
            self.search
            .text()
            .strip()
            .lower()
        )

        model = (
            self.model_filter
            .currentText()
        )

        filtered = []

        for row in self.equipment_rows:

            if (
                model != "Все модели"
                and str(
                    row["model"] or ""
                ) != model
            ):
                continue

            searchable = " ".join(
                [
                    str(
                        row["model"] or ""
                    ),
                    str(
                        row["serial_number"]
                        or ""
                    ),
                    str(
                        row["garage_number"]
                        or ""
                    ),
                    str(
                        row["registration_number"]
                        or ""
                    ),
                ]
            ).lower()

            if (
                search_text
                and search_text
                not in searchable
            ):
                continue

            filtered.append(row)

        self.populate_equipment_table(
            filtered
        )

        self.populate_equipment_combo(
            filtered
        )

    # ==========================================================
    # TABLE
    # ==========================================================

    def populate_equipment_table(
        self,
        rows,
    ):
        self.equipment_table.blockSignals(
            True
        )

        self.equipment_table.setRowCount(
            0
        )

        for equipment in rows:

            row_index = (
                self.equipment_table
                .rowCount()
            )

            self.equipment_table.insertRow(
                row_index
            )

            values = [
                equipment["model"],
                equipment[
                    "serial_number"
                ],
                equipment[
                    "garage_number"
                ],
                equipment["status"],
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value or "")
                )

                if column == 0:
                    item.setData(
                        Qt.UserRole,
                        equipment["id"],
                    )

                self.equipment_table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.equipment_table.blockSignals(
            False
        )

    # ==========================================================
    # COMBO
    # ==========================================================

    def populate_equipment_combo(
        self,
        rows,
    ):
        selected_id = (
            self.current_equipment_id
        )

        self.equipment_combo.blockSignals(
            True
        )

        self.equipment_combo.clear()

        self.equipment_combo.addItem(
            "Выберите машину",
            None,
        )

        selected_index = 0

        for equipment in rows:

            text = (
                f"{equipment['model']} | "
                f"№{equipment['garage_number']} | "
                f"S/N {equipment['serial_number']}"
            )

            self.equipment_combo.addItem(
                text,
                equipment["id"],
            )

            if (
                equipment["id"]
                == selected_id
            ):
                selected_index = (
                    self.equipment_combo
                    .count()
                    - 1
                )

        self.equipment_combo.setCurrentIndex(
            selected_index
        )

        self.equipment_combo.blockSignals(
            False
        )

    # ==========================================================
    # SELECTION
    # ==========================================================

    def combo_selection_changed(
        self,
        index,
    ):
        equipment_id = (
            self.equipment_combo
            .itemData(index)
        )

        if equipment_id is None:
            return

        self.select_equipment(
            equipment_id
        )

        self.equipment_selected.emit(
            int(equipment_id)
        )

    def table_selection_changed(self):
        selected = (
            self.equipment_table
            .selectedItems()
        )

        if not selected:
            return

        row = selected[0].row()

        item = (
            self.equipment_table.item(
                row,
                0,
            )
        )

        if item is None:
            return

        equipment_id = item.data(
            Qt.UserRole
        )

        if equipment_id is None:
            return

        self.select_equipment(
            equipment_id
        )

        self.equipment_selected.emit(
            int(equipment_id)
        )

    def select_equipment(
        self,
        equipment_id,
    ):
        equipment_id = int(
            equipment_id
        )

        self.current_equipment_id = (
            equipment_id
        )

        self.equipment_combo.blockSignals(
            True
        )

        for index in range(
            self.equipment_combo.count()
        ):
            if (
                self.equipment_combo
                .itemData(index)
                == equipment_id
            ):
                self.equipment_combo.setCurrentIndex(
                    index
                )
                break

        self.equipment_combo.blockSignals(
            False
        )

        self.equipment_table.blockSignals(
            True
        )

        self.equipment_table.clearSelection()

        for row in range(
            self.equipment_table.rowCount()
        ):
            item = (
                self.equipment_table.item(
                    row,
                    0,
                )
            )

            if (
                item is not None
                and item.data(
                    Qt.UserRole
                )
                == equipment_id
            ):
                self.equipment_table.selectRow(
                    row
                )

                self.equipment_table.scrollToItem(
                    item
                )

                break

        self.equipment_table.blockSignals(
            False
        )

    # ==========================================================
    # MACHINE DETAILS
    # ==========================================================

    def set_machine(
        self,
        equipment,
    ):
        if equipment is None:
            self.clear_machine()
            return

        self.current_equipment_id = (
            equipment["id"]
        )

        model = (
            equipment["model"]
            or ""
        )

        garage_number = (
            equipment["garage_number"]
            or ""
        )

        self.machine_title.setText(
            f"{model} №{garage_number}"
        )

        self.model_value.setText(
            str(model or "—")
        )

        self.serial_value.setText(
            str(
                equipment["serial_number"]
                or "—"
            )
        )

        self.garage_value.setText(
            str(
                garage_number
                or "—"
            )
        )

        self.registration_value.setText(
            str(
                equipment[
                    "registration_number"
                ]
                or "—"
            )
        )

        self.year_value.setText(
            str(
                equipment[
                    "manufacture_year"
                ]
                or "—"
            )
        )

        hours = float(
            equipment["current_hours"]
            or 0
        )

        if hours.is_integer():
            hours_text = str(
                int(hours)
            )
        else:
            hours_text = (
                f"{hours:.1f}"
            )

        self.hours_value.setText(
            hours_text
        )

        self.status_value.setText(
            str(
                equipment["status"]
                or "—"
            )
        )

        note = str(
            equipment["note"]
            or ""
        ).strip()

        if note:
            self.note_label.setText(
                f"Примечание: {note}"
            )

            self.note_label.show()

        else:
            self.note_label.clear()
            self.note_label.hide()

        self.btn_components.setEnabled(
            True
        )

        self.select_equipment(
            equipment["id"]
        )

    def clear_machine(self):
        self.current_equipment_id = None

        self.machine_title.setText(
            "Машина не выбрана"
        )

        for label in (
            self.model_value,
            self.serial_value,
            self.garage_value,
            self.registration_value,
            self.year_value,
            self.hours_value,
            self.status_value,
        ):
            label.setText("—")

        self.note_label.clear()
        self.note_label.hide()

        self.btn_components.setEnabled(
            False
        )

        self.clear_history()

    # ==========================================================
    # HISTORY
    # ==========================================================

    def clear_history(self):
        self.history_table.setRowCount(
            0
        )

    def set_history(
        self,
        rows,
    ):
        self.clear_history()

        for work in rows:

            row = (
                self.history_table
                .rowCount()
            )

            self.history_table.insertRow(
                row
            )

            if work["in_progress"]:
                state = "В работе"
            else:
                state = "Завершено"

            if not work["requires_report"]:
                report = "Не требуется"

            elif work["report_completed"]:
                report = "Готов"

            else:
                report = "Требуется"

            hours = float(
                work["machine_hours"]
                or 0
            )

            if hours.is_integer():
                hours_text = str(
                    int(hours)
                )
            else:
                hours_text = (
                    f"{hours:.1f}"
                )

            values = [
                work["request_number"]
                or "",
                work["repair_type"]
                or "",
                work["date_start"]
                or "",
                work["date_end"]
                or "",
                state,
                hours_text,
                work["description"]
                or "",
                work["executors"]
                or "",
                report,
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                if column == 0:
                    item.setData(
                        Qt.UserRole,
                        work["id"],
                    )

                if column in (
                    2,
                    3,
                    4,
                    5,
                    8,
                ):
                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                self.history_table.setItem(
                    row,
                    column,
                    item,
                )

        self.history_table.resizeRowsToContents()

    # ==========================================================
    # CURRENT SELECTION
    # ==========================================================

    def get_selected_equipment_id(
        self,
    ):
        return self.current_equipment_id
