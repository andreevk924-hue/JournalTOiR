from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QSizePolicy,
)


class WorkPage(QWidget):

    def __init__(self):
        super().__init__()
        self.create_ui()

    # ------------------------------------------------------------------

    def create_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(10)

        title = QLabel("Менеджер простоев")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        root.addWidget(title)

        root.addLayout(self.create_filters())
        root.addWidget(self.create_table())

    # ------------------------------------------------------------------

    @staticmethod
    def _filter_label(text):
        label = QLabel(text)
        label.setStyleSheet("font-size:11px;font-weight:600;")
        return label

    def create_filters(self):
        """Компактная панель фильтров с явными подписями.

        Фильтры разнесены на несколько строк, чтобы элементы не сжимались
        и не перекрывались при обычном масштабировании Windows.
        """
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = self._filter_label("Поиск")
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Заявка, модель, S/N, гаражный номер, описание, исполнитель..."
        )
        self.search.setClearButtonEnabled(True)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        search_row.addWidget(search_label)
        search_row.addWidget(self.search, 1)
        root.addLayout(search_row)

        filters = QGridLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setHorizontalSpacing(10)
        filters.setVerticalSpacing(4)

        self.type_filter = QComboBox()
        self.type_filter.addItems([
            "Все типы работ",
            "Аварийный ремонт",
            "Плановый ремонт",
            "ТО",
            "Простой",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
            "Будущие работы",
        ])

        self.progress_filter = QComboBox()
        self.progress_filter.addItems([
            "В работе",
            "Завершено",
            "Все статусы",
        ])
        # Основной рабочий сценарий менеджера — открытые работы.
        self.progress_filter.setCurrentText("В работе")

        self.report_filter = QComboBox()
        self.report_filter.addItems([
            "Все отчёты",
            "Требуется отчёт",
            "Отчёт не требуется",
            "Отчёт выполнен",
            "Отчёт не выполнен",
        ])

        self.period_filter = QComboBox()
        self.period_filter.addItems([
            "Все даты",
            "Сегодня",
            "Последние 7 дней",
            "Последние 30 дней",
            "Текущий месяц",
            "Текущий год",
        ])

        controls = (
            ("Тип работ", self.type_filter),
            ("Статус", self.progress_filter),
            ("Отчёт", self.report_filter),
            ("Период", self.period_filter),
        )
        for column, (label_text, widget) in enumerate(controls):
            filters.addWidget(self._filter_label(label_text), 0, column)
            filters.addWidget(widget, 1, column)
            filters.setColumnStretch(column, 1)

        self.btn_reset_filters = QPushButton("Сбросить фильтры")
        self.btn_reset_filters.setToolTip(
            "Вернуть фильтры к начальному виду: статус «В работе», остальные — без ограничений"
        )
        filters.addWidget(self._filter_label(" "), 0, 4)
        filters.addWidget(self.btn_reset_filters, 1, 4)
        filters.setColumnStretch(4, 0)

        root.addLayout(filters)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Изменить")
        self.btn_delete = QPushButton("Удалить")
        self.btn_refresh = QPushButton("Обновить")

        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        actions.addWidget(self.btn_refresh)
        root.addLayout(actions)

        return root

    # ------------------------------------------------------------------

    def create_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "№ заявки",
            "Модель",
            "Гаражный №",
            "Тип работ",
            "Дата начала",
            "Дата окончания",
            "В работе",
            "Наработка",
            "Требуется отчет",
            "Отчет выполнен",
        ])

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        return self.table

    # ------------------------------------------------------------------

    def clear(self):
        self.table.setRowCount(0)

    # ------------------------------------------------------------------

    def add_work(
        self,
        request,
        model,
        garage,
        repair_type,
        date_start,
        date_end,
        in_progress,
        hours,
        requires_report,
        report_completed,
    ):
        row = self.table.rowCount()
        self.table.insertRow(row)

        def display_date(value):
            text = str(value or "")
            parsed = QDate.fromString(text, "yyyy-MM-dd")
            return parsed.toString("dd.MM.yyyy") if parsed.isValid() else text

        values = [
            request,
            model,
            garage,
            repair_type,
            display_date(date_start),
            display_date(date_end),
            "Да" if in_progress else "Нет",
            hours,
            "Да" if requires_report else "Нет",
            "Да" if report_completed else "Нет",
        ]

        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, column, item)
