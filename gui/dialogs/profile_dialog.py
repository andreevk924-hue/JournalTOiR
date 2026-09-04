from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class ProfileDialog(QDialog):
    """Небольшое окно для просмотра и редактирования данных текущего пользователя."""

    def __init__(self, user=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мой профиль")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.resize(520, 330)
        self._user = dict(user or {})
        self._create_ui()
        self._load()

    def _create_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        title = QLabel("Мой профиль")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Личные данные используются в отчётах, письмах и подписи пользователя.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)

        self.full_name = QLineEdit()
        self.position = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Необязательно")

        form.addRow("ФИО", self.full_name)
        form.addRow("Должность", self.position)
        form.addRow("Корпоративный email", self.email)
        form.addRow("Телефон", self.phone)
        root.addLayout(form)
        root.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("Сохранить")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        self.buttons.button(QDialogButtonBox.Save).setProperty("primary", True)
        self.buttons.accepted.connect(self._accept_checked)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _load(self):
        self.full_name.setText(str(self._user.get("full_name", "") or ""))
        self.position.setText(str(self._user.get("position", "") or ""))
        self.email.setText(str(self._user.get("email", "") or ""))
        self.phone.setText(str(self._user.get("phone", "") or ""))

    def user_data(self):
        return {
            "full_name": self.full_name.text().strip(),
            "position": self.position.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
        }

    def _accept_checked(self):
        data = self.user_data()
        if not data["full_name"] or not data["position"] or not data["email"]:
            QMessageBox.warning(
                self,
                "Мой профиль",
                "Заполните ФИО, должность и корпоративный email.",
            )
            return
        if "@" not in data["email"] or data["email"].startswith("@") or data["email"].endswith("@"):
            QMessageBox.warning(self, "Мой профиль", "Проверьте корпоративный email.")
            return
        self.accept()
