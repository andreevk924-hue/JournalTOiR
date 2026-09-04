from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)


DEFAULT_SUBJECT = "{report} — {customer} — {date}"
DEFAULT_BODY = (
    "Добрый день!\n\n"
    "Направляю {report} за период {period_from} — {period_to}.\n"
    "Заказчик: {customer}.\n\n"
    "С уважением,\n"
    "{user_fio}\n"
    "{user_position}"
)

VARIABLES = [
    ("{report}", "Название отчёта"),
    ("{customer}", "Заказчик"),
    ("{organization}", "Организация"),
    ("{date}", "Дата формирования"),
    ("{period_from}", "Начало периода"),
    ("{period_to}", "Конец периода"),
    ("{user_fio}", "ФИО пользователя"),
    ("{user_position}", "Должность пользователя"),
    ("{user_email}", "Email пользователя"),
]


class EmailTemplateWizard(QWizard):
    """Мастер настройки рассылки для текущего заказчика."""

    def __init__(self, config=None, customer="", outlook_service=None, report_name="", parent=None):
        super().__init__(parent)
        self.customer = str(customer or "")
        self.report_name = str(report_name or "").strip()
        self.outlook_service = outlook_service
        self.config = dict(config or {})

        title_suffix = f" — {self.report_name}" if self.report_name else ""
        self.setWindowTitle(f"Настройка рассылки по eMail{title_suffix}")
        self.setMinimumSize(760, 570)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self._add_recipients_page()
        self._add_template_page()
        self._add_outlook_page()
        self._load()

    def _add_recipients_page(self):
        page = QWizardPage()
        page.setTitle("Получатели")
        report_text = f" для отчёта «{self.report_name}»" if self.report_name else ""
        page.setSubTitle(
            f"Настройте адресатов{report_text} для заказчика «{self.customer}». "
            "Несколько адресов разделяйте точкой с запятой."
        )
        layout = QFormLayout(page)
        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("user1@company.ru; user2@company.ru")
        self.cc_edit = QLineEdit()
        self.cc_edit.setPlaceholderText("Необязательно")
        layout.addRow("Кому", self.to_edit)
        layout.addRow("Копия", self.cc_edit)
        self.addPage(page)

    def _add_template_page(self):
        page = QWizardPage()
        page.setTitle("Шаблон письма")
        page.setSubTitle(
            f"Этот шаблон используется только для отчёта «{self.report_name}»."
            if self.report_name else
            "Это общий шаблон по умолчанию."
        )
        root = QVBoxLayout(page)
        form = QFormLayout()
        self.subject_edit = QLineEdit()
        self.body_edit = QTextEdit()
        self.body_edit.setMinimumHeight(230)
        form.addRow("Тема письма", self.subject_edit)
        form.addRow("Текст письма", self.body_edit)
        root.addLayout(form)

        row = QHBoxLayout()
        row.addWidget(QLabel("Вставить переменную:"))
        self.variable_combo = QComboBox()
        for token, description in VARIABLES:
            self.variable_combo.addItem(f"{token} — {description}", token)
        self.btn_insert_subject = QPushButton("В тему")
        self.btn_insert_body = QPushButton("В текст")
        row.addWidget(self.variable_combo, 1)
        row.addWidget(self.btn_insert_subject)
        row.addWidget(self.btn_insert_body)
        root.addLayout(row)

        note = QLabel(
            "Переменные автоматически заменяются данными текущей организации, "
            "заказчика, пользователя и выбранного периода."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        root.addWidget(note)

        self.btn_insert_subject.clicked.connect(self._insert_subject_variable)
        self.btn_insert_body.clicked.connect(self._insert_body_variable)
        self.addPage(page)

    def _add_outlook_page(self):
        page = QWizardPage()
        page.setTitle("Outlook")
        page.setSubTitle(
            "Программа создаёт письмо с PDF-вложением и открывает его в Classic Outlook. "
            "Отправка выполняется пользователем вручную."
        )
        root = QVBoxLayout(page)
        self.enabled = QCheckBox("Включить рассылку по eMail")
        self.enabled.setChecked(True)
        root.addWidget(self.enabled)

        self.outlook_status = QLabel("Outlook ещё не проверялся.")
        self.outlook_status.setWordWrap(True)
        root.addWidget(self.outlook_status)

        self.btn_test_outlook = QPushButton("Проверить Outlook")
        self.btn_test_outlook.clicked.connect(self._test_outlook)
        root.addWidget(self.btn_test_outlook, alignment=Qt.AlignLeft)

        note = QLabel(
            "Режим безопасный: письмо не отправляется автоматически. "
            "Откроется готовый черновик с темой, текстом и PDF-вложением.\n\n"
            "Работает с Classic Outlook for Windows. Никакой отдельный pywin32 "
            "теперь устанавливать не нужно. Новый Outlook for Windows не поддерживает "
            "классический COM-интерфейс Outlook."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        root.addWidget(note)
        root.addStretch()
        self.addPage(page)

    def _insert_subject_variable(self):
        token = str(self.variable_combo.currentData() or "")
        pos = self.subject_edit.cursorPosition()
        text = self.subject_edit.text()
        self.subject_edit.setText(text[:pos] + token + text[pos:])
        self.subject_edit.setCursorPosition(pos + len(token))

    def _insert_body_variable(self):
        token = str(self.variable_combo.currentData() or "")
        self.body_edit.textCursor().insertText(token)
        self.body_edit.setFocus()

    def _test_outlook(self):
        if self.outlook_service is None:
            self.outlook_status.setText("Сервис Outlook не подключён.")
            return
        ok, message = self.outlook_service.check_available()
        self.outlook_status.setText(message)
        if ok:
            QMessageBox.information(self, "Outlook", message)
        else:
            QMessageBox.warning(self, "Outlook", message)

    def _load(self):
        self.to_edit.setText(str(self.config.get("to", "") or ""))
        self.cc_edit.setText(str(self.config.get("cc", "") or ""))
        self.subject_edit.setText(str(self.config.get("subject", DEFAULT_SUBJECT) or DEFAULT_SUBJECT))
        self.body_edit.setPlainText(str(self.config.get("body", DEFAULT_BODY) or DEFAULT_BODY))
        self.enabled.setChecked(bool(self.config.get("enabled", True)))

    def settings(self):
        return {
            "enabled": self.enabled.isChecked(),
            "to": self.to_edit.text().strip(),
            "cc": self.cc_edit.text().strip(),
            "subject": self.subject_edit.text().strip() or DEFAULT_SUBJECT,
            "body": self.body_edit.toPlainText().strip() or DEFAULT_BODY,
        }
