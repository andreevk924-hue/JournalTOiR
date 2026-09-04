from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from services.app_settings import AppSettingsManager


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = AppSettingsManager()
        self.setWindowTitle("Первоначальная настройка Журнал ТОиР")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(680, 500)
        self._build()
        self._update_step()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 28)
        root.setSpacing(18)

        self.title = QLabel("Добро пожаловать в Журнал ТОиР")
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel("Настроим организацию, пользователя и хранение данных.")
        self.subtitle.setObjectName("muted")
        root.addWidget(self.title)
        root.addWidget(self.subtitle)

        self.steps = QStackedWidget()
        root.addWidget(self.steps, 1)
        self.steps.addWidget(self._organization_page())
        self.steps.addWidget(self._user_page())
        self.steps.addWidget(self._security_page())
        self.steps.addWidget(self._storage_page())

        buttons = QHBoxLayout()
        self.back = QPushButton("Назад")
        self.next = QPushButton("Далее")
        self.next.setProperty("primary", True)
        self.cancel = QPushButton("Отмена")
        buttons.addWidget(self.cancel)
        buttons.addStretch()
        buttons.addWidget(self.back)
        buttons.addWidget(self.next)
        root.addLayout(buttons)

        self.cancel.clicked.connect(self.reject)
        self.back.clicked.connect(self._back)
        self.next.clicked.connect(self._next)

    def _card(self, title, text):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)
        head = QLabel(title); head.setObjectName("sectionTitle")
        desc = QLabel(text); desc.setObjectName("muted"); desc.setWordWrap(True)
        card = QFrame(); card.setObjectName("card")
        card_layout = QVBoxLayout(card); card_layout.setContentsMargins(22, 20, 22, 20)
        layout.addWidget(head); layout.addWidget(desc); layout.addWidget(card, 1)
        return page, card_layout

    def _organization_page(self):
        page, layout = self._card(
            "Организация",
            "Укажите наименование организации и обязательно выберите логотип. "
            "Он будет использоваться на главной странице и в отчётах."
        )
        form = QFormLayout(); form.setSpacing(14)
        self.organization = QLineEdit(); self.organization.setPlaceholderText("Например: ООО «Сумитек Интернейшнл»")
        form.addRow("Наименование *", self.organization)

        self.organization_logo_path = ""
        self.organization_logo_preview = QLabel("Логотип не выбран")
        self.organization_logo_preview.setAlignment(Qt.AlignCenter)
        self.organization_logo_preview.setMinimumSize(260, 120)
        self.organization_logo_preview.setMaximumHeight(150)
        self.organization_logo_preview.setStyleSheet(
            "QLabel{border:1px dashed palette(mid);border-radius:10px;padding:8px;}"
        )
        self.organization_logo_button = QPushButton("Выбрать логотип")
        self.organization_logo_button.clicked.connect(self._choose_organization_logo)
        logo_box = QVBoxLayout()
        logo_box.setContentsMargins(0, 0, 0, 0)
        logo_box.setSpacing(8)
        logo_box.addWidget(self.organization_logo_preview)
        logo_box.addWidget(self.organization_logo_button, 0, Qt.AlignLeft)
        form.addRow("Логотип *", logo_box)

        layout.addLayout(form); layout.addStretch()
        return page

    def _choose_organization_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите логотип организации",
            str(Path.home()),
            "Изображения (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Логотип", "Не удалось прочитать выбранное изображение.")
            return
        self.organization_logo_path = path
        self.organization_logo_preview.setPixmap(
            pixmap.scaled(240, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.organization_logo_preview.setText("")

    def _user_page(self):
        page, layout = self._card("Учётная запись", "Эти данные используются в журнале действий и в интерфейсе программы. Роли пользователей не используются.")
        form = QFormLayout(); form.setSpacing(12)
        self.full_name = QLineEdit(); self.position = QLineEdit(); self.email = QLineEdit(); self.phone = QLineEdit()
        self.phone.setPlaceholderText("Необязательно")
        form.addRow("ФИО", self.full_name)
        form.addRow("Должность", self.position)
        form.addRow("Корпоративный email", self.email)
        form.addRow("Телефон", self.phone)
        layout.addLayout(form); layout.addStretch()
        return page

    def _security_page(self):
        page, layout = self._card("Защита входа", "При желании включите цифровой PIN-код. PIN хранится только в виде криптографического хэша.")
        self.pin_enabled = QCheckBox("Запрашивать PIN-код при запуске")
        self.pin = QLineEdit(); self.pin.setEchoMode(QLineEdit.Password); self.pin.setMaxLength(6); self.pin.setPlaceholderText("4–6 цифр")
        self.pin_confirm = QLineEdit(); self.pin_confirm.setEchoMode(QLineEdit.Password); self.pin_confirm.setMaxLength(6); self.pin_confirm.setPlaceholderText("Повторите PIN")
        form = QFormLayout(); form.addRow(self.pin_enabled); form.addRow("PIN", self.pin); form.addRow("Повтор", self.pin_confirm)
        layout.addLayout(form); layout.addStretch()
        self.pin_enabled.toggled.connect(self.pin.setEnabled)
        self.pin_enabled.toggled.connect(self.pin_confirm.setEnabled)
        self.pin.setEnabled(False); self.pin_confirm.setEnabled(False)
        return page

    def _path_row(self, edit, button):
        row = QHBoxLayout(); row.addWidget(edit, 1); row.addWidget(button); return row

    def _storage_page(self):
        page, layout = self._card("Хранение и синхронизация", "Программа всегда работает с локальной базой. При доступном сервере актуальная копия автоматически синхронизируется с серверной папкой.")
        cfg = self.settings.load()["storage"]
        self.server_root = QLineEdit(cfg.get("server_root", "")); self.server_root.setPlaceholderText("Сетевая папка, например Z:\\JournalTOiR")
        self.local_root = QLineEdit(cfg.get("local_root", ""))
        self.backup_root = QLineEdit(cfg.get("backup_root", ""))
        b1 = QPushButton("Выбрать"); b2 = QPushButton("Выбрать"); b3 = QPushButton("Выбрать")
        b1.clicked.connect(lambda: self._choose(self.server_root)); b2.clicked.connect(lambda: self._choose(self.local_root)); b3.clicked.connect(lambda: self._choose(self.backup_root))
        form = QFormLayout(); form.setSpacing(12)
        form.addRow("Папка на сервере", self._path_row(self.server_root, b1))
        form.addRow("Локальная папка", self._path_row(self.local_root, b2))
        form.addRow("Резервные копии", self._path_row(self.backup_root, b3))
        layout.addLayout(form)
        note = QLabel("Если сервер недоступен, работа продолжается локально. После восстановления доступа база автоматически отправляется на сервер.")
        note.setWordWrap(True); note.setObjectName("muted"); layout.addWidget(note); layout.addStretch()
        return page

    def _choose(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку", edit.text().strip() or str(Path.home()))
        if folder: edit.setText(folder)

    def _back(self):
        self.steps.setCurrentIndex(max(0, self.steps.currentIndex() - 1)); self._update_step()

    def _next(self):
        index = self.steps.currentIndex()
        if not self._validate(index): return
        if index < self.steps.count() - 1:
            self.steps.setCurrentIndex(index + 1); self._update_step(); return
        try:
            self._save()
        except Exception as exc:
            QMessageBox.critical(self, "Настройка", str(exc)); return
        self.accept()

    def _validate(self, index):
        if index == 0:
            if not self.organization.text().strip():
                QMessageBox.warning(self, "Настройка", "Укажите наименование организации."); return False
            if not self.organization_logo_path or not Path(self.organization_logo_path).exists():
                QMessageBox.warning(self, "Настройка", "Выберите логотип организации. Это обязательный шаг."); return False
        if index == 1:
            if not self.full_name.text().strip() or not self.position.text().strip() or not self.email.text().strip():
                QMessageBox.warning(self, "Настройка", "Заполните ФИО, должность и корпоративный email."); return False
            if "@" not in self.email.text().strip():
                QMessageBox.warning(self, "Настройка", "Проверьте адрес электронной почты."); return False
        if index == 2 and self.pin_enabled.isChecked():
            pin = self.pin.text()
            if not pin.isdigit() or not 4 <= len(pin) <= 6:
                QMessageBox.warning(self, "Настройка", "PIN должен содержать 4–6 цифр."); return False
            if pin != self.pin_confirm.text():
                QMessageBox.warning(self, "Настройка", "PIN-коды не совпадают."); return False
        if index == 3:
            if not self.local_root.text().strip() or not self.backup_root.text().strip():
                QMessageBox.warning(self, "Настройка", "Укажите локальную папку и папку резервных копий."); return False
        return True

    def _save(self):
        cfg = self.settings.load()
        old_local_root = cfg.get("storage", {}).get("local_root", "")
        cfg["organization_name"] = self.organization.text().strip()
        cfg["user"] = {
            "full_name": self.full_name.text().strip(),
            "position": self.position.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
        }
        cfg["storage"].update({
            "server_root": self.server_root.text().strip(),
            "local_root": self.local_root.text().strip(),
            "backup_root": self.backup_root.text().strip(),
        })
        cfg["setup_complete"] = True
        self.settings.migrate_local_root(old_local_root, cfg["storage"]["local_root"])
        self.settings.save(cfg)
        self.settings.set_pin(self.pin.text(), self.pin_enabled.isChecked())
        # Сохраняем также в старой конфигурации для совместимости с текущими отчётами/шапкой.
        from database.customer_manager import CustomerManager
        manager = CustomerManager()
        manager.set_organization_name(cfg["organization_name"])
        stored_logo = manager.set_organization_logo(self.organization_logo_path)
        cfg["organization_logo"] = stored_logo
        self.settings.save(cfg)
        Path(cfg["storage"]["local_root"]).expanduser().mkdir(parents=True, exist_ok=True)
        Path(cfg["storage"]["backup_root"]).expanduser().mkdir(parents=True, exist_ok=True)

    def _update_step(self):
        idx = self.steps.currentIndex()
        self.back.setEnabled(idx > 0)
        self.next.setText("Завершить" if idx == self.steps.count() - 1 else "Далее")
        self.subtitle.setText(f"Шаг {idx + 1} из {self.steps.count()}")
