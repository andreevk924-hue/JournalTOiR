from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout


class JournalPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Журнал техники"))
        layout.addStretch()
