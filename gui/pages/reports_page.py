from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QDateEdit,
    QTextEdit,
)


class ReportsPage(QWidget):

    def __init__(self):
        super().__init__()

        self.create_ui()

    # ------------------------------------------------------------------

    def create_ui(self):

        root = QHBoxLayout(self)

        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(10)

        left = QVBoxLayout()

        title = QLabel("Отчеты")
        title.setObjectName("pageTitle")

        left.addWidget(title)

        self.report_list = QListWidget()
        self.report_list.setObjectName("reportList")

        reports = [
            "КТГ",
            "Простои",
            "Плановые ремонты",
            "Аварийные ремонты",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
            "Статистика исполнителей",
            "Статистика техники",
        ]

        for report in reports:
            self.report_list.addItem(QListWidgetItem(report))
        self.report_list.setCurrentRow(0)

        left.addWidget(self.report_list)

        period = QHBoxLayout()

        self.date_from = QDateEdit()
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))

        self.date_to = QDateEdit()
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())

        period.addWidget(QLabel("Период"))

        period.addWidget(self.date_from)
        period.addWidget(QLabel("-"))
        period.addWidget(self.date_to)

        left.addLayout(period)

        self.btn_generate = QPushButton("Сформировать")
        self.btn_export_excel = QPushButton("Экспорт Excel")
        self.btn_export_pdf = QPushButton("Экспорт PDF")
        self.btn_email = QPushButton("Рассылка по eMail")
        self.btn_print = QPushButton("Печать")

        left.addWidget(self.btn_generate)
        left.addWidget(self.btn_export_excel)
        left.addWidget(self.btn_export_pdf)
        left.addWidget(self.btn_email)
        left.addWidget(self.btn_print)
        left.addStretch()

        root.addLayout(left, 1)

        right = QVBoxLayout()

        preview_title = QLabel("Предварительный просмотр")
        preview_title.setObjectName("sectionTitle")

        right.addWidget(preview_title)

        frame = QFrame()
        frame.setObjectName("contentCard")

        frame_layout = QVBoxLayout(frame)

        self.preview = QTextEdit()
        self.preview.setObjectName("reportPreview")
        self.preview.setReadOnly(True)

        frame_layout.addWidget(self.preview)

        right.addWidget(frame)

        root.addLayout(right, 2)

        self.apply_visual_theme(
            str(QApplication.instance().property("appTheme") or "light")
        )

    def apply_visual_theme(self, theme="light"):
        light = str(theme or "light").lower() != "dark"
        if light:
            base, alt, text, border, selected = "#FFFFFF", "#F4F7FA", "#17324D", "#D8E2EB", "#E3EEFB"
        else:
            base, alt, text, border, selected = "#0D1928", "#111E2E", "#E5EDF6", "#283D54", "#214D83"

        self.report_list.setStyleSheet(
            f"""
            QListWidget#reportList {{
                background:{base}; color:{text}; border:1px solid {border};
                border-radius:8px; padding:5px; outline:none;
            }}
            QListWidget#reportList::item {{
                min-height:36px; padding:7px 9px; margin:1px; border-radius:6px;
            }}
            QListWidget#reportList::item:hover {{ background:{alt}; }}
            QListWidget#reportList::item:selected {{ background:{selected}; color:{text}; }}
            """
        )
        self.preview.setStyleSheet(
            f"QTextEdit#reportPreview{{background:{base};color:{text};border:1px solid {border};border-radius:8px;padding:8px;}}"
        )
        palette = self.preview.palette()
        palette.setColor(QPalette.Base, QColor(base))
        palette.setColor(QPalette.Text, QColor(text))
        self.preview.setPalette(palette)
        self.preview.viewport().setAutoFillBackground(True)

    # ------------------------------------------------------------------

    def clear_preview(self):

        self.preview.clear()

    # ------------------------------------------------------------------

    def set_preview(self, text):

        self.preview.setPlainText(text)

    def set_preview_html(self, html):
        self.preview.setHtml(html)

    def get_period(self):
        date_from = self.date_from.date()
        date_to = self.date_to.date()
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from.toString("yyyy-MM-dd"), date_to.toString("yyyy-MM-dd")

    # ------------------------------------------------------------------

    def current_report(self):

        item = self.report_list.currentItem()

        if item is None:
            return ""

        return item.text()
