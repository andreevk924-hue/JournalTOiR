from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QCheckBox,
    QProgressBar,
)


class ImportDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Импорт данных")
        self.resize(700, 520)

        self.create_ui()

    # ------------------------------------------------------------------

    def create_ui(self):

        root = QVBoxLayout(self)

        form = QFormLayout()

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)

        self.btn_select = QPushButton("Выбрать")

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.btn_select)

        form.addRow("Файл", file_layout)

        root.addLayout(form)

        self.import_equipment = QCheckBox("Импортировать технику")
        self.import_equipment.setChecked(True)

        self.import_work = QCheckBox("Импортировать ремонты")
        self.import_work.setChecked(True)

        self.import_components = QCheckBox("Импортировать компоненты")
        self.import_components.setChecked(True)

        root.addWidget(self.import_equipment)
        root.addWidget(self.import_work)
        root.addWidget(self.import_components)

        title = QLabel("Журнал импорта")
        title.setStyleSheet(
            "font-size:16px;font-weight:bold;"
        )

        root.addWidget(title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        root.addWidget(self.log)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        root.addWidget(self.progress)

        buttons = QHBoxLayout()

        buttons.addStretch()

        self.btn_import = QPushButton("Импорт")
        self.btn_close = QPushButton("Закрыть")

        buttons.addWidget(self.btn_import)
        buttons.addWidget(self.btn_close)

        root.addLayout(buttons)

        self.btn_close.clicked.connect(self.reject)
        self.btn_select.clicked.connect(self.select_file)

    # ------------------------------------------------------------------

    def select_file(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл",
            "",
            "Excel (*.xlsx *.xls);;CSV (*.csv);;Все файлы (*.*)",
        )

        if filename:
            self.file_path.setText(filename)

    # ------------------------------------------------------------------

    def append_log(self, text):

        self.log.append(text)

    # ------------------------------------------------------------------

    def clear_log(self):

        self.log.clear()

    # ------------------------------------------------------------------

    def set_progress(self, value):

        self.progress.setValue(value)

    # ------------------------------------------------------------------

    def get_data(self):

        return {
            "file_path": self.file_path.text().strip(),
            "equipment": self.import_equipment.isChecked(),
            "work": self.import_work.isChecked(),
            "components": self.import_components.isChecked(),
        }

    # ------------------------------------------------------------------

    def clear(self):

        self.file_path.clear()

        self.import_equipment.setChecked(True)

        self.import_work.setChecked(True)

        self.import_components.setChecked(True)

        self.progress.setValue(0)

        self.log.clear()
