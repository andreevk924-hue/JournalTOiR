# gui/dialogs/customer_dialog.py

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database.customer_manager import CustomerManager
from services.app_settings import AppSettingsManager


class CustomerCardButton(QPushButton):
    doubleClicked = Signal(str)

    def __init__(self, customer_name, subtitle="", parent=None):
        super().__init__(parent)
        self.customer_name = str(customer_name)
        self.subtitle = str(subtitle or "")
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(76)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("customerCard", True)
        self._refresh_text()

    def _refresh_text(self):
        text = self.customer_name
        if self.subtitle:
            text += f"\n{self.subtitle}"
        self.setText(text)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.customer_name)
        super().mouseDoubleClickEvent(event)


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.customer_manager = CustomerManager()
        self.app_settings = AppSettingsManager()
        self.selected_customer = None
        self._selected_name = ""
        self._customer_buttons = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self.setWindowTitle("Выбор заказчика")
        self.resize(760, 560)
        self.setMinimumSize(620, 470)

        self.create_ui()
        self.connect_signals()
        self.apply_visual_theme()
        self.refresh_customers()

    def create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 20)
        main_layout.setSpacing(12)

        title = QLabel("Выберите заказчика")
        title.setObjectName("customerDialogTitle")
        main_layout.addWidget(title)

        organization = self.customer_manager.get_organization_name()
        self.organization_label = QLabel(
            f"Организация: {organization}" if organization else "Организация не указана"
        )
        self.organization_label.setObjectName("customerDialogOrganization")
        main_layout.addWidget(self.organization_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск заказчика…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(38)
        main_layout.addWidget(self.search)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QScrollArea.NoFrame)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_widget = QWidget()
        self.cards_widget.setObjectName("customerCardsViewport")
        self.cards_layout = QGridLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(10)
        self.cards_layout.setVerticalSpacing(10)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_scroll.setWidget(self.cards_widget)
        main_layout.addWidget(self.cards_scroll, 1)

        management_layout = QHBoxLayout()
        management_layout.setSpacing(8)
        self.btn_add = QPushButton("Добавить")
        self.btn_rename = QPushButton("Переименовать")
        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setProperty("danger", True)
        management_layout.addWidget(self.btn_add)
        management_layout.addWidget(self.btn_rename)
        management_layout.addWidget(self.btn_delete)
        management_layout.addStretch()
        main_layout.addLayout(management_layout)

        self.buttons = QDialogButtonBox()
        self.btn_open = self.buttons.addButton("Открыть", QDialogButtonBox.AcceptRole)
        self.btn_cancel = self.buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        self.btn_open.setDefault(True)
        self.btn_open.setProperty("primary", True)
        main_layout.addWidget(self.buttons)

    def apply_visual_theme(self):
        theme = str(QApplication.instance().property("appTheme") or "light").lower()
        if theme == "light":
            self.setStyleSheet(
                """
                QDialog { background:#F4F7FA; color:#17314D; }
                QLabel#customerDialogTitle { color:#102A46; font-size:24px; font-weight:700; }
                QLabel#customerDialogOrganization { color:#61758C; font-size:13px; }
                QWidget#customerCardsViewport { background:#F4F7FA; }
                QPushButton[customerCard="true"] {
                    background:#FFFFFF; color:#17314D; border:1px solid #D7E1EA;
                    border-radius:10px; text-align:left; padding:12px 14px;
                    font-size:13px; font-weight:600;
                }
                QPushButton[customerCard="true"]:hover {
                    background:#F7FAFD; border-color:#91B2D5;
                }
                QPushButton[customerCard="true"]:checked {
                    background:#EAF3FC; border:2px solid #2866B3; color:#123F72;
                }
                QScrollArea { background:#F4F7FA; border:none; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog { background:#0B1420; color:#E6EEF7; }
                QLabel#customerDialogTitle { color:#F3F7FC; font-size:24px; font-weight:700; }
                QLabel#customerDialogOrganization { color:#9FB0C2; font-size:13px; }
                QWidget#customerCardsViewport { background:#0B1420; }
                QPushButton[customerCard="true"] {
                    background:#111E2E; color:#E4EDF7; border:1px solid #263A50;
                    border-radius:10px; text-align:left; padding:12px 14px;
                    font-size:13px; font-weight:600;
                }
                QPushButton[customerCard="true"]:hover {
                    background:#162A42; border-color:#45698D;
                }
                QPushButton[customerCard="true"]:checked {
                    background:#15365B; border:2px solid #4C8BDA; color:#FFFFFF;
                }
                QScrollArea { background:#0B1420; border:none; }
                """
            )

    def connect_signals(self):
        self.btn_add.clicked.connect(self.add_customer)
        self.btn_rename.clicked.connect(self.rename_customer)
        self.btn_delete.clicked.connect(self.delete_customer)
        self.btn_open.clicked.connect(lambda _checked=False: self.open_customer())
        self.btn_cancel.clicked.connect(self.reject)
        self.search.textChanged.connect(lambda _text: self.refresh_customers())

    def _clear_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._button_group.removeButton(widget)
                widget.deleteLater()
        self._customer_buttons.clear()

    def _select_name(self, customer_name):
        customer_name = str(customer_name or "")
        if not customer_name or customer_name not in self._customer_buttons:
            self._selected_name = ""
            self.update_buttons()
            return
        self._selected_name = customer_name
        button = self._customer_buttons[customer_name]
        button.setChecked(True)
        self.update_buttons()

    def refresh_customers(self, select_customer=None):
        previous = str(select_customer or self._selected_name or "")
        self._clear_cards()

        filter_text = self.search.text().strip().lower()
        customers = self.customer_manager.get_customers()
        cfg = self.app_settings.load()
        recent = list(cfg.get("recent_customers", []) or [])
        order = {name: i for i, name in enumerate(recent)}
        customers.sort(key=lambda name: (order.get(name, 999), name.lower()))
        if filter_text:
            customers = [name for name in customers if filter_text in name.lower()]

        active_customer = self.customer_manager.get_active_customer()
        remembered_customer = cfg.get("active_customer", "")
        target_customer = previous or remembered_customer or active_customer

        for index, customer in enumerate(customers):
            subtitle = ""
            if customer == remembered_customer:
                subtitle = "Последний использованный"
            elif customer in recent:
                subtitle = "Недавний"

            button = CustomerCardButton(customer, subtitle)
            button.clicked.connect(
                lambda checked=False, name=customer: self._select_name(name)
            )
            button.doubleClicked.connect(self.open_customer)
            self._button_group.addButton(button)
            self._customer_buttons[customer] = button
            self.cards_layout.addWidget(button, index, 0)

        row_count = max(1, len(customers))
        self.cards_layout.setRowStretch(row_count, 1)

        if target_customer in self._customer_buttons:
            self._select_name(target_customer)
        elif customers:
            self._select_name(customers[0])
        else:
            self._selected_name = ""
            self.update_buttons()

    def update_buttons(self):
        has_selection = bool(self._selected_name)
        self.btn_open.setEnabled(has_selection)
        self.btn_rename.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def add_customer(self):
        name, accepted = QInputDialog.getText(
            self,
            "Новый заказчик",
            "Наименование заказчика:",
        )
        if not accepted:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование заказчика.")
            return
        try:
            customer_name = self.customer_manager.create_customer(name)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return
        self.refresh_customers(customer_name)

    def rename_customer(self):
        old_name = self._selected_name
        if not old_name:
            return
        new_name, accepted = QInputDialog.getText(
            self,
            "Переименование заказчика",
            "Новое наименование:",
            text=old_name,
        )
        if not accepted:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование заказчика.")
            return
        if new_name == old_name:
            return
        try:
            renamed_customer = self.customer_manager.rename_customer(old_name, new_name)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return
        self._selected_name = renamed_customer
        self.refresh_customers(renamed_customer)

    def delete_customer(self):
        customer_name = self._selected_name
        if not customer_name:
            return
        answer = QMessageBox.question(
            self,
            "Удаление заказчика",
            (
                f"Удалить заказчика «{customer_name}»?\n\n"
                "Будет удалена вся папка заказчика:\n"
                "• база данных;\n"
                "• техника;\n"
                "• история работ;\n"
                "• компоненты;\n"
                "• резервные копии.\n\n"
                "Отменить это действие будет невозможно."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        confirm_text, accepted = QInputDialog.getText(
            self,
            "Подтверждение удаления",
            "Для подтверждения введите точное наименование заказчика:",
        )
        if not accepted:
            return
        if confirm_text.strip() != customer_name:
            QMessageBox.warning(self, "Удаление отменено", "Наименование введено неверно.")
            return

        try:
            self.customer_manager.delete_customer(customer_name)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return

        self._selected_name = ""
        self.refresh_customers()

    def open_customer(self, customer_name=None):
        if isinstance(customer_name, bool) or customer_name is None:
            customer_name = self._selected_name
        customer_name = str(customer_name or "").strip()
        if not customer_name:
            return
        try:
            from services.sync_service import SyncService

            SyncService(customer_name).prepare_before_open()
            self.customer_manager.set_active_customer(customer_name)
            self.app_settings.set_active_customer(customer_name)
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))
            return

        self.selected_customer = customer_name
        self.accept()

    def get_selected_customer(self):
        return self.selected_customer

    def closeEvent(self, event):
        event.accept()
