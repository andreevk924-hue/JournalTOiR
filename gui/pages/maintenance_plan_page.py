# gui/pages/maintenance_plan_page.py

from PySide6.QtCore import Qt, Signal
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
    QWidget,
)


class MaintenancePlanPage(QWidget):

    plan_requested = Signal(dict)
    reschedule_requested = Signal(dict)
    cancel_requested = Signal(dict)
    start_requested = Signal(dict)
    complete_requested = Signal(dict)

    HEADERS = [
        "Модель",
        "Гаражный №",
        "Текущая наработка",
        "Следующее ТО",
        "На наработке",
        "Осталось, м/ч",
        "Статус",
        "Плановая дата",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._rows = []

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        title = QLabel("Планирование ТО")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 600;"
        )
        main_layout.addWidget(title)

        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Поиск по модели или гаражному номеру..."
        )
        self.search.setClearButtonEnabled(True)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            [
                "Все",
                "Норма",
                "Скоро",
                "Наступило",
            ]
        )
        self.status_filter.setMinimumWidth(150)

        self.btn_plan = QPushButton("Запланировать ТО")
        self.btn_reschedule = QPushButton("Перенести")
        self.btn_start = QPushButton("Начать ТО")
        self.btn_complete = QPushButton("Выполнить")
        self.btn_cancel = QPushButton("Отменить план")

        for button in (
            self.btn_plan,
            self.btn_reschedule,
            self.btn_start,
            self.btn_complete,
            self.btn_cancel,
        ):
            button.setEnabled(False)

        filters_layout.addWidget(self.search, 1)
        filters_layout.addWidget(self.status_filter)
        filters_layout.addWidget(self.btn_plan)
        filters_layout.addWidget(self.btn_reschedule)
        filters_layout.addWidget(self.btn_start)
        filters_layout.addWidget(self.btn_complete)
        filters_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(filters_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            0,
            QHeaderView.Stretch,
        )

        main_layout.addWidget(self.table, 1)

        self.summary = QLabel("Всего: 0")
        main_layout.addWidget(self.summary)

    def _connect_signals(self):
        self.search.textChanged.connect(
            self._apply_filters
        )
        self.status_filter.currentTextChanged.connect(
            self._apply_filters
        )
        self.table.itemSelectionChanged.connect(
            self._selection_changed
        )
        self.table.itemDoubleClicked.connect(
            lambda _item: self._request_plan()
        )
        self.btn_plan.clicked.connect(self._request_plan)
        self.btn_reschedule.clicked.connect(self._request_reschedule)
        self.btn_start.clicked.connect(self._request_start)
        self.btn_complete.clicked.connect(self._request_complete)
        self.btn_cancel.clicked.connect(self._request_cancel)

    @staticmethod
    def _format_hours(value):
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return str(value or "")

        if number.is_integer():
            return f"{int(number):,}".replace(",", " ")

        return (
            f"{number:,.1f}"
            .replace(",", " ")
        )

    def set_rows(self, rows):
        self._rows = [
            dict(row)
            for row in (rows or [])
        ]
        self._apply_filters()

    def clear(self):
        self._rows = []
        self.table.setRowCount(0)
        self.summary.setText("Всего: 0")

    def _apply_filters(self):
        search_text = (
            self.search.text().strip().lower()
        )
        status = self.status_filter.currentText()

        filtered = []

        for row in self._rows:
            model = str(
                row.get("model") or ""
            )
            garage_number = str(
                row.get("garage_number") or ""
            )
            plan_status = str(
                row.get("plan_status") or ""
            )

            haystack = (
                f"{model} {garage_number}".lower()
            )

            if (
                search_text
                and search_text not in haystack
            ):
                continue

            if (
                status != "Все"
                and plan_status != status
            ):
                continue

            filtered.append(row)

        self._fill_table(filtered)

    def _fill_table(self, rows):
        sorting_enabled = (
            self.table.isSortingEnabled()
        )
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for data in rows:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)

            values = [
                data.get("model") or "",
                data.get("garage_number") or "",
                self._format_hours(
                    data.get("current_hours")
                ),
                data.get("maintenance_name") or "",
                self._format_hours(
                    data.get("target_hours")
                ),
                self._format_hours(
                    data.get("remaining_hours")
                ),
                (
                    (
                        "Выполняется"
                        if data.get("maintenance_started")
                        else "Запланировано"
                    )
                    if data.get("planned_work_id")
                    else (data.get("plan_status") or "")
                ),
                data.get("planned_date") or "",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in (2, 4, 5):
                    raw_key = {
                        2: "current_hours",
                        4: "target_hours",
                        5: "remaining_hours",
                    }[column]

                    try:
                        sort_value = float(
                            data.get(raw_key) or 0
                        )
                    except (TypeError, ValueError):
                        sort_value = 0

                    item.setData(
                        Qt.UserRole,
                        sort_value,
                    )
                    item.setTextAlignment(
                        Qt.AlignRight
                        | Qt.AlignVCenter
                    )

                if data.get("planned_work_id"):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    if data.get("maintenance_started"):
                        item.setToolTip(
                            "ТО начато "
                            + str(data.get("planned_date") or "")
                            + ". Техника находится в простое."
                        )
                    else:
                        item.setToolTip(
                            "ТО запланировано на "
                            + str(data.get("planned_date") or "")
                        )

                if column == 0:
                    item.setData(
                        Qt.UserRole + 1,
                        data.get("equipment_id"),
                    )
                    item.setData(
                        Qt.UserRole + 2,
                        dict(data),
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.table.setSortingEnabled(
            sorting_enabled
        )

        self.summary.setText(
            f"Показано: {len(rows)} из {len(self._rows)}"
        )

    def _selection_changed(self):
        plan = self.get_selected_plan()
        has_selection = plan is not None
        is_planned = bool(plan and plan.get("planned_work_id"))
        is_started = bool(plan and plan.get("maintenance_started"))
        self.btn_plan.setEnabled(has_selection and not is_planned)
        self.btn_reschedule.setEnabled(is_planned and not is_started)
        self.btn_start.setEnabled(is_planned and not is_started)
        self.btn_complete.setEnabled(is_planned and is_started)
        self.btn_cancel.setEnabled(is_planned and not is_started)

    def get_selected_plan(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole + 2)
        return dict(data) if data else None

    def _request_plan(self):
        plan = self.get_selected_plan()
        if plan is not None:
            self.plan_requested.emit(plan)

    def _request_reschedule(self):
        plan = self.get_selected_plan()
        if plan and plan.get("planned_work_id"):
            self.reschedule_requested.emit(plan)

    def _request_start(self):
        plan = self.get_selected_plan()
        if (
            plan
            and plan.get("planned_work_id")
            and not plan.get("maintenance_started")
        ):
            self.start_requested.emit(plan)

    def _request_complete(self):
        plan = self.get_selected_plan()
        if plan and plan.get("planned_work_id"):
            self.complete_requested.emit(plan)

    def _request_cancel(self):
        plan = self.get_selected_plan()
        if plan and plan.get("planned_work_id"):
            self.cancel_requested.emit(plan)

    def get_selected_equipment_id(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(row, 0)

        if item is None:
            return None

        return item.data(Qt.UserRole + 1)
