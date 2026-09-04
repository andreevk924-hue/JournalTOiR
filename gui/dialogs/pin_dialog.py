from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from services.app_settings import AppSettingsManager


class PinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = AppSettingsManager()
        cfg = self.settings.load()
        self.setWindowTitle("Вход — Журнал ТОиР")
        self.setModal(True)
        self.setFixedSize(440, 290)
        layout = QVBoxLayout(self); layout.setContentsMargins(34, 30, 34, 30); layout.setSpacing(14)
        title = QLabel(cfg.get("organization_name") or "Журнал ТОиР"); title.setObjectName("pageTitle"); title.setAlignment(Qt.AlignCenter); title.setWordWrap(True)
        subtitle = QLabel(cfg.get("user", {}).get("full_name", "")); subtitle.setObjectName("muted"); subtitle.setAlignment(Qt.AlignCenter)
        self.pin = QLineEdit(); self.pin.setEchoMode(QLineEdit.Password); self.pin.setMaxLength(6); self.pin.setAlignment(Qt.AlignCenter); self.pin.setPlaceholderText("Введите PIN"); self.pin.setMinimumHeight(44)
        row = QHBoxLayout(); cancel = QPushButton("Выход"); enter = QPushButton("Войти"); enter.setProperty("primary", True); row.addWidget(cancel); row.addStretch(); row.addWidget(enter)
        layout.addWidget(title); layout.addWidget(subtitle); layout.addStretch(); layout.addWidget(self.pin); layout.addStretch(); layout.addLayout(row)
        cancel.clicked.connect(self.reject); enter.clicked.connect(self._check); self.pin.returnPressed.connect(self._check)

    def _check(self):
        if self.settings.verify_pin(self.pin.text()):
            self.accept()
        else:
            self.pin.clear(); QMessageBox.warning(self, "Вход", "Неверный PIN-код."); self.pin.setFocus()
