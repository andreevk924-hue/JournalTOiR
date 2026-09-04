from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QApplication,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class ScheduleCellDelegate(QStyledItemDelegate):
    """Рисует статусную заливку независимо от QSS и системной темы."""

    def __init__(self, schedule_page, parent=None):
        super().__init__(parent)
        self.schedule_page = schedule_page

    def paint(self, painter, option, index):
        status = str(index.data(SchedulePage.STATUS_ROLE) or "").strip()
        if not status:
            super().paint(painter, option, index)
            return

        color = self.schedule_page.get_status_color(status)
        if color is None:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.fillRect(option.rect, color)
        text = str(index.data(Qt.DisplayRole) or "")
        if text:
            painter.setPen(self.schedule_page.get_status_text_color(status))
            font = option.font
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(option.rect.adjusted(3, 1, -3, -1), Qt.AlignCenter, text)
        painter.restore()


class SchedulePage(QWidget):

    period_changed = Signal()
    export_pdf_requested = Signal()
    email_requested = Signal()

    # ==========================================================
    # COLORS
    # ==========================================================

    COLOR_EMERGENCY = QColor(220, 80, 80)
    COLOR_PLANNED = QColor(155, 110, 75)
    COLOR_CUSTOMER = QColor(150, 105, 190)
    # Цвета новых типов взяты из легенды исходного Excel.
    COLOR_MONITORING = QColor(255, 255, 0)      # #FFFF00
    COLOR_MODERNIZATION = QColor(0, 176, 240)   # #00B0F0
    COLOR_DOWNTIME = QColor(190, 190, 190)
    COLOR_MAINTENANCE = QColor(90, 180, 110)
    COLOR_FUTURE = QColor(230, 150, 60)

    COLOR_TODAY = QColor(255, 245, 200)
    COLOR_TODAY_HEADER = QColor(255, 210, 80)

    # Semantic cell state. PDF/Excel exports must use this role instead of
    # trying to reverse-engineer a status from the QBrush color.
    STATUS_ROLE = Qt.UserRole + 2

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.date_columns = {}

        self.create_ui()
        self.set_default_period()

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

        layout.setSpacing(10)

        # ------------------------------------------------------
        # TITLE
        # ------------------------------------------------------

        title = QLabel(
            "График работ"
        )

        title.setObjectName("pageTitle")

        layout.addWidget(
            title
        )

        # ------------------------------------------------------
        # LEGEND
        # ------------------------------------------------------

        legend_frame = QFrame()
        legend_frame.setObjectName("scheduleLegend")


        # Два ряда по четыре пункта: легенда не сжимает интерфейс даже
        # при уменьшенном окне и масштабировании Windows.
        legend_layout = QGridLayout(legend_frame)
        legend_layout.setContentsMargins(10, 6, 10, 6)
        legend_layout.setHorizontalSpacing(18)
        legend_layout.setVerticalSpacing(5)

        legend_items = [
            (self.COLOR_EMERGENCY, "Аварийный ремонт"),
            (self.COLOR_PLANNED, "Плановый ремонт"),
            (self.COLOR_CUSTOMER, "Работы заказчика"),
            (self.COLOR_MONITORING, "Мониторинг состояния"),
            (self.COLOR_MODERNIZATION, "Модернизация"),
            (self.COLOR_DOWNTIME, "Простой"),
            (self.COLOR_MAINTENANCE, "ТО"),
            (self.COLOR_FUTURE, "Будущие работы"),
        ]
        for index, (swatch, label) in enumerate(legend_items):
            self.add_legend_item(
                legend_layout,
                swatch,
                label,
                row=index // 4,
                column=index % 4,
            )
        for column in range(4):
            legend_layout.setColumnStretch(column, 1)

        layout.addWidget(
            legend_frame
        )

        # ------------------------------------------------------
        # PERIOD CONTROLS
        # ------------------------------------------------------

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(7)

        period_label = QLabel("Период:")

        self.date_from = QDateEdit()
        self.date_from.setDisplayFormat("dd.MM.yyyy")

        self.date_from.setCalendarPopup(
            True
        )

        self.date_from.setDisplayFormat(
            "dd.MM.yyyy"
        )

        self.date_to = QDateEdit()
        self.date_to.setDisplayFormat("dd.MM.yyyy")

        self.date_to.setCalendarPopup(
            True
        )

        self.date_to.setDisplayFormat(
            "dd.MM.yyyy"
        )

        self.btn_current_year = QPushButton(
            "Текущий год"
        )

        self.btn_refresh = QPushButton(
            "Обновить"
        )

        self.btn_export_pdf = QPushButton(
            "Ежедневная сводка по работам в PDF"
        )

        self.btn_email = QPushButton(
            "Рассылка по eMail"
        )

        # Две строки вместо одной длинной: кнопки больше не наезжают
        # друг на друга при уменьшении окна или повышенном DPI Windows.
        controls.addWidget(period_label, 0, 0)
        controls.addWidget(self.date_from, 0, 1)
        controls.addWidget(QLabel("—"), 0, 2)
        controls.addWidget(self.date_to, 0, 3)
        controls.addWidget(self.btn_current_year, 0, 4)
        controls.addWidget(self.btn_refresh, 0, 5)
        controls.setColumnStretch(6, 1)

        controls.addWidget(self.btn_export_pdf, 1, 0, 1, 4)
        controls.addWidget(self.btn_email, 1, 4, 1, 2)
        self.btn_export_pdf.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_email.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout.addLayout(controls)

        # ======================================================
        # TABLE AREA
        #
        # Левая таблица:
        # Модель | S/N | Г/н
        #
        # Правая таблица:
        # календарь
        # ======================================================

        tables_layout = QHBoxLayout()

        tables_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        tables_layout.setSpacing(
            0
        )

        # ------------------------------------------------------
        # FIXED TABLE
        # ------------------------------------------------------

        self.fixed_table = QTableWidget()
        self.fixed_table.setObjectName("scheduleFixedTable")

        self.fixed_table.setColumnCount(
            3
        )

        self.fixed_table.setHorizontalHeaderLabels(
            [
                "Модель",
                "S/N",
                "Г/н",
            ]
        )

        self.fixed_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.fixed_table.setSelectionMode(
            QAbstractItemView.NoSelection
        )

        self.fixed_table.setFocusPolicy(
            Qt.NoFocus
        )

        self.fixed_table.setWordWrap(
            False
        )

        self.fixed_table.setAlternatingRowColors(
            False
        )

        self.fixed_table.verticalHeader().setVisible(
            False
        )

        self.fixed_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        # Вертикальный scrollbar скрываем,
        # но сама таблица продолжает прокручиваться
        # синхронно с календарём.

        self.fixed_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.fixed_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.fixed_table.setVerticalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        # ------------------------------------------------------
        # CALENDAR TABLE
        # ------------------------------------------------------

        self.table = QTableWidget()
        self.table.setObjectName("scheduleCalendarTable")
        self.table.setItemDelegate(ScheduleCellDelegate(self, self.table))

        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.table.setSelectionMode(
            QAbstractItemView.NoSelection
        )

        self.table.setFocusPolicy(
            Qt.NoFocus
        )

        self.table.setWordWrap(
            False
        )

        self.table.setAlternatingRowColors(
            False
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setHorizontalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.table.setVerticalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        # ------------------------------------------------------
        # ADD TABLES
        # ------------------------------------------------------

        tables_layout.addWidget(
            self.fixed_table
        )

        tables_layout.addWidget(
            self.table,
            1,
        )

        layout.addLayout(
            tables_layout,
            1,
        )

        # ------------------------------------------------------
        # SYNCHRONIZED VERTICAL SCROLL
        # ------------------------------------------------------

        self.table.verticalScrollBar().valueChanged.connect(
            self.fixed_table
            .verticalScrollBar()
            .setValue
        )

        self.fixed_table.verticalScrollBar().valueChanged.connect(
            self.table
            .verticalScrollBar()
            .setValue
        )

        # ------------------------------------------------------
        # SIGNALS
        # ------------------------------------------------------

        self.btn_current_year.clicked.connect(
            self.set_current_year
        )

        self.btn_refresh.clicked.connect(
            self.period_changed.emit
        )
        self.btn_export_pdf.clicked.connect(
            self.export_pdf_requested.emit
        )

        self.btn_email.clicked.connect(
            self.email_requested.emit
        )

        self.date_from.dateChanged.connect(
            self.validate_period
        )

        self.date_to.dateChanged.connect(
            self.validate_period
        )

        self.apply_visual_theme(
            str(QApplication.instance().property("appTheme") or "light")
        )

    def apply_visual_theme(self, theme="light"):
        """Жёстко изолирует две таблицы графика от системной темы Windows."""
        light = str(theme or "light").lower() != "dark"
        if light:
            base, text, header, header_text, grid, border = (
                "#FFFFFF", "#17324D", "#EFF4F8", "#34516E", "#DFE7EE", "#D6E0E9"
            )
        else:
            base, text, header, header_text, grid, border = (
                "#0D1928", "#E4EDF6", "#14243A", "#C7D5E5", "#23374D", "#2A4058"
            )

        # QDateEdit создаёт отдельный popup-календарь. Его палитру задаём
        # явно, чтобы тёмная тема Windows не просачивалась в светлую тему
        # приложения и наоборот.
        cal_bg = base
        cal_text = text
        cal_hover = "#EEF4FA" if light else "#182C45"
        cal_accent = "#1F62BD" if light else "#2767C7"
        cal_style = f"""
            QCalendarWidget {{ background:{cal_bg}; color:{cal_text}; border:1px solid {border}; }}
            QCalendarWidget QWidget {{ background:{cal_bg}; color:{cal_text}; }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{ background:{header}; }}
            QCalendarWidget QToolButton {{ color:{cal_text}; background:{header}; border:none; padding:4px 7px; font-weight:600; }}
            QCalendarWidget QToolButton:hover {{ background:{cal_hover}; }}
            QCalendarWidget QSpinBox {{ color:{cal_text}; background:{header}; border:none; }}
            QCalendarWidget QMenu {{ color:{cal_text}; background:{cal_bg}; border:1px solid {border}; }}
            QCalendarWidget QAbstractItemView:enabled {{ color:{cal_text}; background:{cal_bg}; selection-background-color:{cal_accent}; selection-color:#FFFFFF; outline:none; }}
        """
        for edit in (self.date_from, self.date_to):
            calendar = edit.calendarWidget()
            if calendar is not None:
                calendar.setStyleSheet(cal_style)
                cp = calendar.palette()
                cp.setColor(QPalette.Window, QColor(cal_bg))
                cp.setColor(QPalette.Base, QColor(cal_bg))
                cp.setColor(QPalette.Text, QColor(cal_text))
                cp.setColor(QPalette.WindowText, QColor(cal_text))
                cp.setColor(QPalette.Button, QColor(header))
                cp.setColor(QPalette.ButtonText, QColor(cal_text))
                cp.setColor(QPalette.Highlight, QColor(cal_accent))
                cp.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
                calendar.setPalette(cp)

        table_qss = f"""
            QTableWidget {{
                background:{base}; color:{text}; border:1px solid {border};
                gridline-color:{grid}; outline:none;
            }}
            QTableWidget::item {{
                color:{text}; border:none;
            }}
            QHeaderView {{ background:{header}; }}
            QHeaderView::section {{
                background:{header}; color:{header_text}; border:none;
                border-right:1px solid {grid}; border-bottom:1px solid {grid};
                padding:7px 6px; font-weight:600;
            }}
            QTableCornerButton::section {{ background:{header}; border:none; }}
        """
        for table in (self.fixed_table, self.table):
            table.setStyleSheet(table_qss)
            palette = table.palette()
            palette.setColor(QPalette.Base, QColor(base))
            palette.setColor(QPalette.AlternateBase, QColor(base))
            palette.setColor(QPalette.Text, QColor(text))
            palette.setColor(QPalette.Window, QColor(base))
            table.setPalette(palette)
            table.viewport().setAutoFillBackground(True)
            vp = table.viewport().palette()
            vp.setColor(QPalette.Base, QColor(base))
            vp.setColor(QPalette.Window, QColor(base))
            vp.setColor(QPalette.Text, QColor(text))
            table.viewport().setPalette(vp)
            header_obj = table.horizontalHeader()
            if header_obj is not None:
                hp = header_obj.palette()
                hp.setColor(QPalette.Window, QColor(header))
                hp.setColor(QPalette.Base, QColor(header))
                hp.setColor(QPalette.Button, QColor(header))
                hp.setColor(QPalette.Text, QColor(header_text))
                header_obj.setPalette(hp)
                header_obj.viewport().setAutoFillBackground(True)
                header_obj.viewport().setPalette(hp)

        self.findChild(QFrame, "scheduleLegend").setStyleSheet(
            f"QFrame#scheduleLegend{{background:{base};border:1px solid {border};border-radius:7px;}}"
            f"QFrame#scheduleLegend QLabel{{background:transparent;color:{text};border:none;}}"
        )

    # ==========================================================
    # LEGEND
    # ==========================================================

    def add_legend_item(
        self,
        layout,
        swatch,
        text,
        row=None,
        column=None,
    ):
        container = QWidget()

        item_layout = QHBoxLayout(
            container
        )

        item_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        item_layout.setSpacing(
            5
        )

        color_box = QLabel()

        color_box.setFixedSize(
            14,
            14,
        )

        color_box.setStyleSheet(
            f"""
            background-color:
                rgb(
                    {swatch.red()},
                    {swatch.green()},
                    {swatch.blue()}
                );
            border: 1px solid #555;
            border-radius: 2px;
            """
        )

        text_label = QLabel(
            text
        )

        item_layout.addWidget(
            color_box
        )

        item_layout.addWidget(
            text_label
        )

        if row is None or column is None:
            layout.addWidget(container)
        else:
            layout.addWidget(container, row, column)

    # ==========================================================
    # PERIOD
    # ==========================================================

    def set_default_period(self):
        today = QDate.currentDate()
        self.date_from.setDate(today.addDays(-6))
        self.date_to.setDate(today)

    def set_current_year(self):
        self.set_default_period()

        self.period_changed.emit()

    def validate_period(self):
        if (
            self.date_to.date()
            < self.date_from.date()
        ):
            self.date_to.setDate(
                self.date_from.date()
            )

    def get_period(self):
        return (
            self.date_from.date().toString(
                "yyyy-MM-dd"
            ),
            self.date_to.date().toString(
                "yyyy-MM-dd"
            ),
        )

    def get_schedule_snapshot(self):
        """Возвращает точный снимок двух экранных таблиц.

        Важно: даты берутся из ``date_columns``, который создаётся тем же
        ``build_schedule`` при построении правой таблицы. Заголовки таблицы
        больше не парсятся обратно из текста ``dd.MM`` — именно это создавало
        лишнюю точку расхождения между экраном и PDF.
        """
        dates = [
            day
            for day, _column in sorted(
                self.date_columns.items(),
                key=lambda pair: pair[1],
            )
        ]

        row_count = min(
            self.fixed_table.rowCount(),
            self.table.rowCount(),
        )
        column_count = self.table.columnCount()

        rows = []
        for row in range(row_count):
            fixed_values = []
            for col in range(3):
                fixed_item = self.fixed_table.item(row, col)
                fixed_values.append(
                    fixed_item.text() if fixed_item is not None else ""
                )

            equipment_id = None
            first_item = self.fixed_table.item(row, 0)
            if first_item is not None:
                equipment_id = first_item.data(Qt.UserRole)

            cells = []
            for col in range(column_count):
                item = self.table.item(row, col)
                text = ""
                tooltip = ""
                has_work = False
                status = ""
                color = ""

                if item is not None:
                    text = item.text() or ""
                    tooltip = item.toolTip() or ""
                    status = str(item.data(self.STATUS_ROLE) or "").strip()
                    has_work = bool(status) or bool(item.data(Qt.UserRole + 1))
                    # Color is exported only as a convenience/debug value.
                    # The semantic status above is the source of truth.
                    if status:
                        semantic_color = self.get_status_color(status)
                        if semantic_color is not None:
                            color = semantic_color.name()

                cells.append({
                    "text": text,
                    "status": status,
                    "color": color,
                    "tooltip": tooltip,
                    "has_work": has_work,
                })

            rows.append({
                "equipment_id": equipment_id,
                "model": fixed_values[0],
                "serial_number": fixed_values[1],
                "garage_number": fixed_values[2],
                "cells": cells,
            })

        return {
            "dates": dates,
            "rows": rows,
            "fixed_row_count": self.fixed_table.rowCount(),
            "calendar_row_count": self.table.rowCount(),
            "calendar_column_count": column_count,
        }

    # ==========================================================
    # BUILD SCHEDULE
    # ==========================================================

    def build_schedule(
        self,
        equipment_rows,
        work_rows,
        daily_rows=None,
    ):
        date_from_text, date_to_text = (
            self.get_period()
        )

        date_from = date.fromisoformat(
            date_from_text
        )

        date_to = date.fromisoformat(
            date_to_text
        )

        if date_to < date_from:
            return

        # ------------------------------------------------------
        # DATES
        # ------------------------------------------------------

        dates = []

        current_date = date_from

        while current_date <= date_to:
            dates.append(
                current_date
            )

            current_date += timedelta(
                days=1
            )

        # Календарь теперь отдельная таблица,
        # поэтому первая дата находится в колонке 0.

        self.date_columns = {
            day: index
            for index, day
            in enumerate(dates)
        }

        # ------------------------------------------------------
        # CLEAR
        # ------------------------------------------------------

        self.fixed_table.clearContents()

        self.table.clear()

        self.fixed_table.setRowCount(
            len(equipment_rows)
        )

        self.fixed_table.setColumnCount(
            3
        )

        self.fixed_table.setHorizontalHeaderLabels(
            [
                "Модель",
                "S/N",
                "Г/н",
            ]
        )

        self.table.setRowCount(
            len(equipment_rows)
        )

        self.table.setColumnCount(
            len(dates)
        )

        # ------------------------------------------------------
        # DATE HEADERS
        # ------------------------------------------------------

        self.table.setHorizontalHeaderLabels(
            [
                day.strftime("%d.%m")
                for day in dates
            ]
        )

        # ------------------------------------------------------
        # EQUIPMENT
        # ------------------------------------------------------

        equipment_row_map = {}

        for row_index, equipment in enumerate(
            equipment_rows
        ):
            equipment_id = (
                equipment["id"]
            )

            equipment_row_map[
                equipment_id
            ] = row_index

            values = [
                equipment["model"] or "",
                equipment[
                    "serial_number"
                ]
                or "",
                equipment[
                    "garage_number"
                ]
                or "",
            ]

            # Закреплённые данные машины

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                if column == 0:
                    item.setData(
                        Qt.UserRole,
                        equipment_id,
                    )

                self.fixed_table.setItem(
                    row_index,
                    column,
                    item,
                )

            # Пустые календарные ячейки

            for day in dates:
                column = (
                    self.date_columns[
                        day
                    ]
                )

                item = QTableWidgetItem(
                    ""
                )

                item.setTextAlignment(
                    Qt.AlignCenter
                )
                item.setData(self.STATUS_ROLE, "")

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )
        # ======================================================
        # WORKS
        # ======================================================

        # Дневные записи имеют приоритет над общим типом ремонта.
        # Ключ: (work_id, date) -> запись конкретного дня.
        daily_map = {}
        for daily in (daily_rows or []):
            try:
                daily_day = date.fromisoformat(str(daily["work_date"])[:10])
                daily_map[(daily["work_id"], daily_day)] = daily
            except (TypeError, ValueError):
                continue

        today = date.today()

        for work in work_rows:
            equipment_id = (
                work["equipment_id"]
            )

            row_index = (
                equipment_row_map.get(
                    equipment_id
                )
            )

            if row_index is None:
                continue

            # --------------------------------------------------
            # START DATE
            # --------------------------------------------------

            try:
                work_start = (
                    date.fromisoformat(
                        work["date_start"]
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            # Тип нужен до расчёта конца периода: запланированное, но
            # ещё не начатое ТО показывается только в дату плана, а не как
            # непрерывный простой от даты планирования до сегодняшнего дня.
            repair_type = str(work["repair_type"] or "").strip()
            is_maintenance = self.is_maintenance(repair_type)
            try:
                is_planned = bool(work["is_planned"])
            except (KeyError, IndexError):
                is_planned = False
            try:
                is_started = bool(work["is_started"])
            except (KeyError, IndexError):
                is_started = False
            plan_only_maintenance = is_maintenance and is_planned and not is_started

            # --------------------------------------------------
            # END DATE
            # --------------------------------------------------

            if plan_only_maintenance:
                work_end = work_start
            elif work["date_end"]:
                try:
                    work_end = (
                        date.fromisoformat(
                            work["date_end"]
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    work_end = work_start

            elif work_start > today:
                # Будущая работа без даты окончания:
                # показываем хотя бы дату начала.

                work_end = work_start

            elif work["in_progress"]:
                # Текущая незавершённая работа:
                # показываем от начала до сегодня.

                work_end = min(
                    today,
                    date_to,
                )

            else:
                work_end = work_start

            # Защита от некорректного периода.

            if work_end < work_start:
                work_end = work_start

            # --------------------------------------------------
            # VISIBLE PERIOD
            # --------------------------------------------------

            visible_start = max(
                work_start,
                date_from,
            )

            visible_end = min(
                work_end,
                date_to,
            )

            if visible_end < visible_start:
                continue

            # --------------------------------------------------
            # WORK TYPE
            # --------------------------------------------------

            # Плановое ТО до «Начать ТО» визуально является планом,
            # даже если плановая дата уже наступила.
            is_future_work = (
                work_start > today
                or plan_only_maintenance
            )

            maintenance_interval = (
                self.get_maintenance_interval(
                    work
                )
            )

            # Импортированная историческая сводка может использовать
            # work_daily_log как точный дневной источник истины.
            # Это не влияет на обычные карточки, где поле пустое.
            daily_authoritative_from = None
            try:
                raw_authoritative_from = str(
                    work["daily_log_authoritative_from"] or ""
                ).strip()
                if raw_authoritative_from:
                    daily_authoritative_from = date.fromisoformat(
                        raw_authoritative_from[:10]
                    )
            except (KeyError, IndexError, TypeError, ValueError):
                daily_authoritative_from = None

            # --------------------------------------------------
            # CELL TEXT
            #
            # Обычные работы:
            # ничего не пишем.
            #
            # ТО:
            # ТО-50
            # ТО-250
            # ТО-500
            # и т.д.
            # --------------------------------------------------

            cell_text = ""

            if is_maintenance:
                if maintenance_interval:
                    cell_text = (
                        "ТО-"
                        + self.format_interval(
                            maintenance_interval
                        )
                    )

                else:
                    cell_text = "ТО"

            # --------------------------------------------------
            # TOOLTIP
            # --------------------------------------------------

            tooltip = self.build_tooltip(
                work
            )

            # --------------------------------------------------
            # FILL WORK PERIOD
            # --------------------------------------------------

            day = visible_start

            while day <= visible_end:
                column = (
                    self.date_columns.get(
                        day
                    )
                )

                if column is not None:
                    daily = daily_map.get((work["id"], day))

                    # Начиная с authoritative_from отсутствие дневной записи
                    # означает, что в исходном ежедневном графике работы
                    # на этот день не было. Не закрашиваем такую ячейку.
                    if (
                        daily is None
                        and daily_authoritative_from is not None
                        and day >= daily_authoritative_from
                    ):
                        day += timedelta(days=1)
                        continue

                    effective_type = (daily["day_type"] if daily is not None else repair_type) or repair_type
                    effective_description = (daily["description"] if daily is not None else "") or (work["description"] or "")
                    effective_executors = (daily["executors"] if daily is not None else "") or (work["executors"] or "")

                    item = self.table.item(
                        row_index,
                        column,
                    )

                    if item is None:
                        item = QTableWidgetItem(
                            ""
                        )

                        self.table.setItem(
                            row_index,
                            column,
                            item,
                        )

                    # ------------------------------------------
                    # TEXT
                    # ------------------------------------------

                    if cell_text:
                        existing = (
                            item.text().strip()
                        )

                        if not existing:
                            item.setText(
                                cell_text
                            )

                        elif (
                            cell_text
                            not in existing.split(
                                "/"
                            )
                        ):
                            item.setText(
                                f"{existing}/{cell_text}"
                            )

                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                    # Метка:
                    # в ячейке имеется работа.
                    #
                    # Используется при подсветке
                    # сегодняшнего дня.

                    item.setData(
                        Qt.UserRole + 1,
                        True,
                    )

                    # ------------------------------------------
                    # COLOR
                    # ------------------------------------------

                    if daily is not None:
                        cell_status = self.normalize_status(effective_type)
                    elif is_future_work:
                        cell_status = "Будущие работы"
                    elif is_maintenance:
                        cell_status = "ТО"
                    else:
                        cell_status = self.normalize_status(repair_type)

                    background = self.get_status_color(cell_status)
                    item.setData(self.STATUS_ROLE, cell_status if background is not None else "")

                    if background is not None:
                        item.setBackground(background)
                        # Статусный цвет — данные самой ячейки, а не тема интерфейса.
                        # Контрастный текст нужен для ТО-XX и других подписей.
                        item.setForeground(self.get_status_text_color(cell_status))

                    # ------------------------------------------
                    # TOOLTIP
                    # ------------------------------------------

                    if daily is not None:
                        day_tooltip = (
                            f"Дата: {day.strftime('%d.%m.%Y')}\n"
                            f"Состояние: {effective_type}\n"
                            f"Описание: {effective_description or '—'}\n"
                            f"Исполнители: {effective_executors or '—'}"
                        )
                        try:
                            hours = float(daily["machine_hours"] or 0)
                            if hours:
                                day_tooltip += f"\nНаработка: {hours:g} м/ч"
                        except (TypeError, ValueError):
                            pass
                    else:
                        day_tooltip = tooltip

                    old_tooltip = (
                        item.toolTip()
                    )

                    if old_tooltip:
                        item.setToolTip(
                            old_tooltip
                            + "\n\n"
                            + day_tooltip
                        )

                    else:
                        item.setToolTip(
                            day_tooltip
                        )

                day += timedelta(
                    days=1
                )

        # ======================================================
        # FINAL TABLE CONFIGURATION
        # ======================================================

        self.configure_table(
            dates
        )

        # Восстановить цвета после конфигурации/смены темы.
        base_color = QColor("#FFFFFF") if str(QApplication.instance().property("appTheme") or "light").lower() != "dark" else QColor("#0D1928")
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                status = str(item.data(self.STATUS_ROLE) or "").strip()
                color = self.get_status_color(status) if status else None
                if color is not None:
                    item.setBackground(color)
                    item.setForeground(QColor("#FFFFFF") if color.lightness() < 165 else QColor("#17324D"))
                else:
                    item.setBackground(base_color)
                    item.setForeground(QColor("#E4EDF6") if base_color.lightness() < 100 else QColor("#17324D"))
        self.scroll_to_today()

    # ==========================================================
    # TABLE CONFIGURATION
    # ==========================================================

    def configure_table(
        self,
        dates,
    ):
        # ------------------------------------------------------
        # FIXED TABLE HEADER
        # ------------------------------------------------------

        fixed_header = (
            self.fixed_table
            .horizontalHeader()
        )

        fixed_header.setSectionResizeMode(
            QHeaderView.Fixed
        )

        # Ширины закреплённых колонок.

        self.fixed_table.setColumnWidth(
            0,
            150,
        )

        self.fixed_table.setColumnWidth(
            1,
            130,
        )

        self.fixed_table.setColumnWidth(
            2,
            80,
        )

        # Ширина всей закреплённой области.
        #
        # + несколько пикселей на рамки таблицы.

        fixed_width = (
            self.fixed_table.columnWidth(0)
            + self.fixed_table.columnWidth(1)
            + self.fixed_table.columnWidth(2)
            + 4
        )

        self.fixed_table.setFixedWidth(
            fixed_width
        )

        # ------------------------------------------------------
        # CALENDAR HEADER
        # ------------------------------------------------------

        calendar_header = (
            self.table
            .horizontalHeader()
        )

        calendar_header.setSectionResizeMode(
            QHeaderView.Fixed
        )

        # Все календарные ячейки одинаковой ширины.

        for column in range(
            len(dates)
        ):
            self.table.setColumnWidth(
                column,
                72,
            )

        # ------------------------------------------------------
        # ROW HEIGHT SYNCHRONIZATION
        # ------------------------------------------------------

        for row in range(
            self.table.rowCount()
        ):
            self.table.setRowHeight(
                row,
                28,
            )

            self.fixed_table.setRowHeight(
                row,
                28,
            )

        # ------------------------------------------------------
        # HEADER HEIGHT SYNCHRONIZATION
        # ------------------------------------------------------

        # Header has two lines for today's column (date + "Сегодня").
        # Calculate the height explicitly; measuring it before changing the
        # header text was the reason the second line was clipped.
        header_height = max(
            48,
            self.table.horizontalHeader().sizeHint().height(),
            self.fixed_table.horizontalHeader().sizeHint().height(),
        )

        self.table.horizontalHeader().setFixedHeight(
            header_height
        )

        self.fixed_table.horizontalHeader().setFixedHeight(
            header_height
        )

        # ======================================================
        # TODAY HIGHLIGHT
        # ======================================================

        today = date.today()

        today_column = (
            self.date_columns.get(
                today
            )
        )

        if today_column is None:
            return

        # ------------------------------------------------------
        # TODAY HEADER
        # ------------------------------------------------------

        header_item = (
            self.table
            .horizontalHeaderItem(
                today_column
            )
        )

        if header_item is not None:
            header_item.setBackground(
                self.COLOR_TODAY_HEADER
            )

            font = (
                header_item.font()
            )

            font.setBold(
                True
            )

            header_item.setFont(
                font
            )

            # Добавляем слово "Сегодня",
            # чтобы текущая дата была заметна
            # даже при похожих цветах темы.

            original_text = (
                header_item.text()
            )

            if "Сегодня" not in original_text:
                header_item.setText(
                    original_text
                    + "\nСегодня"
                )

        # ------------------------------------------------------
        # TODAY COLUMN
        # ------------------------------------------------------

        for row in range(
            self.table.rowCount()
        ):
            item = self.table.item(
                row,
                today_column,
            )

            if item is None:
                item = QTableWidgetItem(
                    ""
                )

                self.table.setItem(
                    row,
                    today_column,
                    item,
                )

            # Если сегодня на машине уже есть работа,
            # её собственный цвет НЕ перекрываем.

            has_work = bool(
                item.data(
                    Qt.UserRole + 1
                )
            )

            # Пустую ячейку работающей техники не закрашиваем:
            # она наследует фон текущей темы приложения.
            # Цвет задаётся только реальному событию/работе.

    # ==========================================================
    # SCROLL TO TODAY
    # ==========================================================

    def scroll_to_today(
        self,
    ):
        today = date.today()

        column = (
            self.date_columns.get(
                today
            )
        )

        if column is None:
            return

        if self.table.rowCount() == 0:
            # Если техники нет,
            # просто двигаем горизонтальный scrollbar
            # примерно к сегодняшнему столбцу.

            target = max(
                0,
                column * 54
                - self.table.viewport().width()
                // 2
            )

            self.table.horizontalScrollBar().setValue(
                target
            )

            return

        item = self.table.item(
            0,
            column,
        )

        if item is not None:
            self.table.scrollToItem(
                item,
                QAbstractItemView.PositionAtCenter,
            )

    # ==========================================================
    # WORK DISPLAY HELPERS
    # ==========================================================

    @staticmethod
    def is_maintenance(
        repair_type,
    ):
        normalized = str(
            repair_type or ""
        ).strip().lower()

        return (
            normalized == "то"
            or normalized.startswith(
                "то-"
            )
            or normalized.startswith(
                "то "
            )
            or "плановые то" in normalized
            or (
                "техническое обслуживание"
                in normalized
            )
        )

    @staticmethod
    def get_maintenance_interval(
        work,
    ):
        try:
            keys = work.keys()

        except AttributeError:
            keys = []

        if (
            "maintenance_interval"
            not in keys
        ):
            return None

        value = work[
            "maintenance_interval"
        ]

        if value in (
            None,
            "",
        ):
            return None

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def format_interval(
        value,
    ):
        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return str(
                value
            )

        if number.is_integer():
            return str(
                int(number)
            )

        return (
            f"{number:.2f}"
            .rstrip("0")
            .rstrip(".")
        )

    @classmethod
    def normalize_status(cls, repair_type):
        normalized = str(repair_type or "").strip().lower()

        if normalized in ("аварийный", "аварийный ремонт") or "авар" in normalized:
            return "Аварийный ремонт"
        if normalized in ("работы заказчика", "работа заказчика", "заказчик") or "заказ" in normalized or "полюс" in normalized:
            return "Работы заказчика"
        if "монитор" in normalized:
            return "Мониторинг состояния"
        if "модерн" in normalized or "сборк" in normalized or "гарант" in normalized:
            return "Модернизация"
        if "прост" in normalized or normalized == ">":
            return "Простой"
        if cls.is_maintenance(repair_type):
            return "ТО"
        if "будущ" in normalized or "планируем" in normalized:
            return "Будущие работы"
        if normalized in ("плановый", "плановый ремонт") or "план" in normalized:
            return "Плановый ремонт"
        return str(repair_type or "").strip()

    def get_status_color(self, status):
        normalized = self.normalize_status(status)
        return {
            "Аварийный ремонт": self.COLOR_EMERGENCY,
            "Плановый ремонт": self.COLOR_PLANNED,
            "Работы заказчика": self.COLOR_CUSTOMER,
            "Мониторинг состояния": self.COLOR_MONITORING,
            "Модернизация": self.COLOR_MODERNIZATION,
            "Простой": self.COLOR_DOWNTIME,
            "ТО": self.COLOR_MAINTENANCE,
            "Будущие работы": self.COLOR_FUTURE,
        }.get(normalized)

    def get_work_color(self, repair_type):
        return self.get_status_color(repair_type)

    def get_status_text_color(self, status):
        normalized = self.normalize_status(status)
        if normalized in (
            "Мониторинг состояния",
            "Модернизация",
            "Простой",
        ):
            return QColor("#17324D")
        return QColor("#FFFFFF")
    # ==========================================================
    # TOOLTIP
    # ==========================================================

    @staticmethod
    def build_tooltip(
        work,
    ):
        try:
            keys = work.keys()

        except AttributeError:
            keys = []

        model = (
            work["model"]
            if "model" in keys
            else ""
        )

        garage_number = (
            work["garage_number"]
            if "garage_number" in keys
            else ""
        )

        repair_type = (
            work["repair_type"]
            if "repair_type" in keys
            else ""
        )

        date_start = (
            work["date_start"]
            if "date_start" in keys
            else ""
        )

        date_end = (
            work["date_end"]
            if "date_end" in keys
            else ""
        )

        description = (
            work["description"]
            if "description" in keys
            else ""
        )

        # ------------------------------------------------------
        # MAIN INFO
        # ------------------------------------------------------

        machine_title = (
            f"{model or ''} "
            f"№{garage_number or ''}"
        ).strip()

        lines = []

        if machine_title:
            lines.append(
                machine_title
            )

        lines.append(
            "Тип: "
            f"{repair_type or '—'}"
        )

        lines.append(
            "Начало: "
            f"{date_start or '—'}"
        )

        lines.append(
            "Окончание: "
            f"{date_end or 'В работе'}"
        )

        # ------------------------------------------------------
        # MAINTENANCE INTERVAL
        # ------------------------------------------------------

        if (
            SchedulePage.is_maintenance(
                repair_type
            )
            and (
                "maintenance_interval"
                in keys
            )
        ):
            interval = work[
                "maintenance_interval"
            ]

            if interval not in (
                None,
                "",
            ):
                lines.append(
                    "Интервал ТО: "
                    + SchedulePage
                    .format_interval(
                        interval
                    )
                    + " м/ч"
                )

        # ------------------------------------------------------
        # DESCRIPTION
        # ------------------------------------------------------

        description = str(
            description or ""
        ).strip()

        if description:
            lines.append(
                "Описание: "
                + description
            )

        # ------------------------------------------------------
        # EXECUTORS
        # ------------------------------------------------------

        if "executors" in keys:
            executors = str(
                work["executors"]
                or ""
            ).strip()

            if executors:
                lines.append(
                    "Исполнители: "
                    + executors
                )

        # ------------------------------------------------------
        # MACHINE HOURS
        # ------------------------------------------------------

        if "machine_hours" in keys:
            machine_hours = (
                work["machine_hours"]
            )

            if machine_hours not in (
                None,
                "",
                0,
                0.0,
            ):
                hours_text = (
                    SchedulePage
                    .format_interval(
                        machine_hours
                    )
                )

                lines.append(
                    "Наработка: "
                    + hours_text
                    + " м/ч"
                )

        # ------------------------------------------------------
        # STATUS
        # ------------------------------------------------------

        if "in_progress" in keys:
            if bool(
                work["in_progress"]
            ):
                lines.append(
                    "Статус: В работе"
                )

        return "\n".join(
            lines
        )
