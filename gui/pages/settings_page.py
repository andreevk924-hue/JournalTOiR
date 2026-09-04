from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QGroupBox, QCheckBox, QComboBox, QScrollArea,
)


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.create_ui()

    def create_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(14)
        title = QLabel("Настройки"); title.setObjectName("pageTitle")
        subtitle = QLabel("Организация, пользователь, безопасность, хранилище, синхронизация и внешний вид."); subtitle.setObjectName("muted")
        root.addWidget(title); root.addWidget(subtitle)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget(); self.body_layout = QVBoxLayout(body); self.body_layout.setContentsMargins(0, 6, 8, 6); self.body_layout.setSpacing(14)
        self.body_layout.addWidget(self.create_organization_group())
        self.body_layout.addWidget(self.create_user_group())
        self.body_layout.addWidget(self.create_security_group())
        self.body_layout.addWidget(self.create_storage_group())
        self.body_layout.addWidget(self.create_sync_group())
        self.body_layout.addWidget(self.create_backup_group())
        self.body_layout.addWidget(self.create_email_group())
        self.body_layout.addWidget(self.create_quick_actions_group())
        self.body_layout.addWidget(self.create_ui_group())
        self.body_layout.addStretch()
        scroll.setWidget(body); root.addWidget(scroll, 1)

        buttons = QHBoxLayout(); buttons.addStretch()
        self.btn_cancel = QPushButton("Отменить изменения")
        self.btn_save = QPushButton("Сохранить настройки"); self.btn_save.setProperty("primary", True)
        buttons.addWidget(self.btn_cancel); buttons.addWidget(self.btn_save)
        root.addLayout(buttons)

    def create_organization_group(self):
        group = QGroupBox("Организация")
        layout = QFormLayout(group)
        self.organization_name = QLineEdit()
        self.customer_name = QLineEdit(); self.customer_name.setReadOnly(True)
        self.logo_path = QLineEdit(); self.logo_path.setReadOnly(True)
        self.btn_logo = QPushButton("Выбрать логотип")
        logo = QHBoxLayout(); logo.addWidget(self.logo_path, 1); logo.addWidget(self.btn_logo)
        layout.addRow("Наименование", self.organization_name)
        layout.addRow("Текущий заказчик", self.customer_name)
        layout.addRow("Логотип", logo)
        return group

    def create_user_group(self):
        group = QGroupBox("Учётная запись")
        layout = QFormLayout(group)
        self.user_full_name = QLineEdit(); self.user_position = QLineEdit(); self.user_email = QLineEdit(); self.user_phone = QLineEdit()
        self.user_phone.setPlaceholderText("Необязательно")
        layout.addRow("ФИО", self.user_full_name)
        layout.addRow("Должность", self.user_position)
        layout.addRow("Корпоративный email", self.user_email)
        layout.addRow("Телефон", self.user_phone)
        return group

    def create_security_group(self):
        group = QGroupBox("Безопасность")
        layout = QFormLayout(group)
        self.pin_enabled = QCheckBox("Запрашивать PIN при запуске")
        self.new_pin = QLineEdit(); self.new_pin.setEchoMode(QLineEdit.Password); self.new_pin.setMaxLength(6); self.new_pin.setPlaceholderText("Оставьте пустым, чтобы не менять текущий PIN")
        self.pin_confirm = QLineEdit(); self.pin_confirm.setEchoMode(QLineEdit.Password); self.pin_confirm.setMaxLength(6); self.pin_confirm.setPlaceholderText("Повтор нового PIN")
        layout.addRow(self.pin_enabled); layout.addRow("Новый PIN", self.new_pin); layout.addRow("Повтор", self.pin_confirm)
        return group

    @staticmethod
    def _path_row(edit, button):
        row = QHBoxLayout(); row.addWidget(edit, 1); row.addWidget(button); return row

    def create_storage_group(self):
        group = QGroupBox("Хранилище")
        layout = QFormLayout(group)
        self.server_root = QLineEdit(); self.local_root = QLineEdit(); self.backup_root = QLineEdit()
        self.btn_server_root = QPushButton("Выбрать")
        self.btn_local_root = QPushButton("Выбрать")
        self.btn_backup_root = QPushButton("Выбрать")
        layout.addRow("Папка на сервере", self._path_row(self.server_root, self.btn_server_root))
        layout.addRow("Локальная папка", self._path_row(self.local_root, self.btn_local_root))
        layout.addRow("Папка резервных копий", self._path_row(self.backup_root, self.btn_backup_root))
        note = QLabel("Изменение локальной папки применяется после перезапуска программы."); note.setObjectName("muted"); note.setWordWrap(True)
        layout.addRow("", note)
        return group

    def create_sync_group(self):
        group = QGroupBox("Синхронизация")
        layout = QFormLayout(group)
        self.sync_enabled = QCheckBox("Автоматически поддерживать локальную и серверную базы актуальными")
        self.sync_status = QLabel("—"); self.sync_status.setObjectName("muted")
        self.last_sync = QLabel("—"); self.last_sync.setObjectName("muted")
        self.btn_test_server = QPushButton("Проверить сервер")
        self.btn_sync_now = QPushButton("Синхронизировать сейчас")
        row = QHBoxLayout(); row.addWidget(self.btn_test_server); row.addWidget(self.btn_sync_now); row.addStretch()
        layout.addRow(self.sync_enabled); layout.addRow("Состояние", self.sync_status); layout.addRow("Последняя синхронизация", self.last_sync); layout.addRow("", row)
        return group

    def create_backup_group(self):
        group = QGroupBox("Резервное копирование")
        layout = QFormLayout(group)
        self.backup_count = QSpinBox(); self.backup_count.setRange(3, 365); self.backup_count.setValue(20)
        self.btn_backup_now = QPushButton("Создать резервную копию сейчас")
        self.btn_check_db = QPushButton("Проверить целостность БД")
        row = QHBoxLayout(); row.addWidget(self.btn_backup_now); row.addWidget(self.btn_check_db); row.addStretch()
        layout.addRow("Хранить последних копий", self.backup_count); layout.addRow("", row)
        return group


    def create_email_group(self):
        group = QGroupBox("Рассылка по eMail")
        layout = QFormLayout(group)

        self.email_report_combo = QComboBox()
        for report in (
            "Ежедневная сводка по работам",
            "КТГ",
            "Простои",
            "Плановые ремонты",
            "Аварийные ремонты",
            "Работы заказчика",
            "Мониторинг состояния",
            "Модернизация",
            "Статистика исполнителей",
            "Статистика техники",
        ):
            self.email_report_combo.addItem(report, report)

        self.email_status = QLabel("—")
        self.email_status.setObjectName("muted")
        self.email_status.setWordWrap(True)
        self.btn_email_template = QPushButton("Настроить шаблон выбранного отчёта")

        note = QLabel(
            "Для каждого отчёта хранится собственный список получателей, тема и текст письма. "
            "Письмо открывается в Classic Outlook как готовый черновик с PDF-вложением."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)

        layout.addRow("Отчёт", self.email_report_combo)
        layout.addRow("Шаблон", self.email_status)
        layout.addRow("", self.btn_email_template)
        layout.addRow("", note)
        return group

    def create_quick_actions_group(self):
        group = QGroupBox("Быстрые действия")
        layout = QFormLayout(group)

        self.quick_action_choices = (
            ("add_equipment", "Добавить технику"),
            ("add_work", "Добавить работу"),
            ("reports", "Сводка"),
            ("schedule", "График работ"),
            ("tasks", "Менеджер задач"),
            ("work_manager", "Менеджер простоев"),
            ("maintenance", "Планирование ТО"),
            ("equipment", "Техника"),
            ("settings", "Настройки"),
        )

        self.quick_action_combos = []
        for i in range(4):
            combo = QComboBox()
            for action_id, title in self.quick_action_choices:
                combo.addItem(title, action_id)
            self.quick_action_combos.append(combo)
            layout.addRow(f"Кнопка {i + 1}", combo)

        note = QLabel(
            "Выберите четыре действия, которые будут отображаться на Главной. "
            "Порядок кнопок соответствует порядку выше."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addRow("", note)
        return group

    def create_ui_group(self):
        group = QGroupBox("Интерфейс")
        layout = QFormLayout(group)
        self.theme = QComboBox(); self.theme.addItem("Тёмная", "dark"); self.theme.addItem("Светлая", "light")
        self.animations = QCheckBox("Плавные переходы и анимации")
        self.compact = QCheckBox("Компактный режим")
        layout.addRow("Тема", self.theme); layout.addRow(self.animations); layout.addRow(self.compact)
        return group

    def set_all_settings(self, cfg, customer, sync_status=None):
        self.organization_name.setText(cfg.get("organization_name", ""))
        self.customer_name.setText(customer or "")
        user = cfg.get("user", {})
        self.user_full_name.setText(user.get("full_name", "")); self.user_position.setText(user.get("position", "")); self.user_email.setText(user.get("email", "")); self.user_phone.setText(user.get("phone", ""))
        security = cfg.get("security", {}); self.pin_enabled.setChecked(bool(security.get("pin_enabled"))); self.new_pin.clear(); self.pin_confirm.clear()
        storage = cfg.get("storage", {}); self.server_root.setText(storage.get("server_root", "")); self.local_root.setText(storage.get("local_root", "")); self.backup_root.setText(storage.get("backup_root", "")); self.backup_count.setValue(int(storage.get("backup_count", 20) or 20))
        sync = cfg.get("sync", {}); self.sync_enabled.setChecked(bool(sync.get("enabled", True))); self.last_sync.setText(sync.get("last_sync") or "Ещё не выполнялась")
        ui = cfg.get("ui", {}); idx = self.theme.findData(ui.get("theme", "light")); self.theme.setCurrentIndex(max(0, idx)); self.animations.setChecked(bool(ui.get("animations", True))); self.compact.setChecked(bool(ui.get("compact", False)))
        quick_actions = list(ui.get("quick_actions", ["add_equipment", "add_work", "reports", "settings"]) or [])
        defaults = ["add_equipment", "add_work", "reports", "settings"]
        while len(quick_actions) < 4:
            quick_actions.append(defaults[len(quick_actions)])
        for combo, action_id in zip(self.quick_action_combos, quick_actions[:4]):
            qidx = combo.findData(action_id)
            combo.setCurrentIndex(qidx if qidx >= 0 else 0)
        if sync_status: self.sync_status.setText(sync_status.get("label", "—"))

    def get_all_settings(self):
        return {
            "organization_name": self.organization_name.text().strip(),
            "user": {"full_name": self.user_full_name.text().strip(), "position": self.user_position.text().strip(), "email": self.user_email.text().strip(), "phone": self.user_phone.text().strip()},
            "security": {"pin_enabled": self.pin_enabled.isChecked(), "new_pin": self.new_pin.text(), "pin_confirm": self.pin_confirm.text()},
            "storage": {"server_root": self.server_root.text().strip(), "local_root": self.local_root.text().strip(), "backup_root": self.backup_root.text().strip(), "backup_count": self.backup_count.value()},
            "sync": {"enabled": self.sync_enabled.isChecked()},
            "ui": {
                "theme": self.theme.currentData(),
                "animations": self.animations.isChecked(),
                "compact": self.compact.isChecked(),
                "quick_actions": [str(combo.currentData() or "") for combo in self.quick_action_combos],
            },
        }

    # Совместимость со старым MainWindow до сохранения/загрузки новой схемы.
    def set_settings(self, organization, customer, logo, backup_path, backup_count):
        self.organization_name.setText(organization); self.customer_name.setText(customer); self.logo_path.setText(logo); self.backup_count.setValue(int(backup_count or 20))

    def get_settings(self):
        data = self.get_all_settings(); return {"organization_name": data["organization_name"], "customer_name": self.customer_name.text(), "logo_path": self.logo_path.text(), "backup_path": self.backup_root.text(), "backup_count": data["storage"]["backup_count"]}
