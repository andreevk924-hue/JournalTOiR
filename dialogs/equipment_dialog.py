from datetime import datetime
from pathlib import Path

from services.builtin_manufacturers import get_all_manufacturers

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QFileDialog,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class EquipmentDialog(QDialog):

    def __init__(
        self,
        parent=None,
        repository=None,
        equipment_id=None,
    ):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)

        self.repository = repository
        self.equipment_id = equipment_id

        self.setWindowTitle(
            "Техника"
        )

        self.resize(
            560,
            720,
        )

        self.create_ui()
        self.load_maintenance_intervals()

    # ==========================================================
    # UI
    # ==========================================================

    def create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        self.resize(1180, 860)
        # The card must also be usable on 1366x768 screens. The editable body
        # scrolls instead of allowing lower controls to cover each other.
        self.setMinimumSize(900, 620)

        self.body_scroll = QScrollArea()
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(12)

        top = QHBoxLayout()
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setSpacing(10)

        self.model = QLineEdit()
        self.serial_number = QLineEdit()
        self.garage_number = QLineEdit()
        self.registration_number = QLineEdit()
        self.manufacturer = QComboBox()
        self.distributor = QComboBox()
        self._load_reference_lists()

        self.manufacture_year = QSpinBox()
        self.manufacture_year.setRange(1900, 2200)
        self.manufacture_year.setValue(datetime.now().year)

        self.current_hours = QDoubleSpinBox()
        self.current_hours.setRange(0, 100_000_000)
        self.current_hours.setDecimals(1)

        self.commissioning_date = QDateEdit()
        self.commissioning_date.setCalendarPopup(True)
        self.commissioning_date.setDisplayFormat("dd.MM.yyyy")
        self.commissioning_date.setDate(QDate.currentDate())

        self.warranty_years = QDoubleSpinBox()
        self.warranty_years.setRange(0, 100)
        self.warranty_years.setDecimals(1)
        self.warranty_years.setSuffix(" лет")

        self.warranty_hours = QDoubleSpinBox()
        self.warranty_hours.setRange(0, 100_000_000)
        self.warranty_hours.setDecimals(1)
        self.warranty_hours.setSuffix(" м/ч")

        self.warranty_start_hours = QDoubleSpinBox()
        self.warranty_start_hours.setRange(0, 100_000_000)
        self.warranty_start_hours.setDecimals(1)
        self.warranty_start_hours.setSuffix(" м/ч")

        self.service_status = QLabel("Постгарантийное")
        self.service_status.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.shift_hours_per_day = QDoubleSpinBox()
        self.shift_hours_per_day.setRange(0.1, 24.0)
        self.shift_hours_per_day.setDecimals(1)
        self.shift_hours_per_day.setSingleStep(0.5)
        self.shift_hours_per_day.setValue(22.0)
        self.shift_hours_per_day.setSuffix(" м/ч")

        self.auto_maintenance = QCheckBox("Автоматически рассчитывать ТО")
        self.auto_maintenance.setToolTip(
            "Расчет начинается после ручного создания первого ТО.\n"
            "Во время ремонта или простоя моточасы не начисляются."
        )

        self.status = QComboBox()
        self.status.addItems(["В работе", "Списан"])
        self.note = QPlainTextEdit()
        self.note.setFixedHeight(72)
        self.note.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        form.addRow("Модель *:", self.model)
        form.addRow("Серийный номер *:", self.serial_number)
        form.addRow("Гаражный номер *:", self.garage_number)
        form.addRow("Гос. номер:", self.registration_number)
        form.addRow("Производитель:", self.manufacturer)
        form.addRow("Дистрибьютор (поставщик):", self.distributor)
        form.addRow("Год выпуска:", self.manufacture_year)
        form.addRow("Дата ввода в эксплуатацию:", self.commissioning_date)
        form.addRow("Текущая наработка:", self.current_hours)
        form.addRow("Срок гарантии:", self.warranty_years)
        form.addRow("Гарантийный ресурс:", self.warranty_hours)
        form.addRow("Наработка при вводе:", self.warranty_start_hours)
        form.addRow("Статус обслуживания:", self.service_status)
        form.addRow("Сменность, м/ч в сутки:", self.shift_hours_per_day)
        form.addRow("", self.auto_maintenance)
        form.addRow("Статус техники:", self.status)
        form.addRow("Примечание:", self.note)
        top.addLayout(form, 3)

        photo_group = QGroupBox("Фото техники")
        photo_layout = QVBoxLayout(photo_group)
        self.photo_path = ""
        self.photo_preview = QLabel("Фото не добавлено")
        self.photo_preview.setAlignment(Qt.AlignCenter)
        self.photo_preview.setMinimumSize(300, 220)
        self.photo_preview.setStyleSheet(
            "border: 1px solid palette(mid); border-radius: 8px;"
        )
        self.photo_button = QPushButton("Добавить / заменить фото")
        self.photo_delete_button = QPushButton("Удалить фото")
        self.photo_button.clicked.connect(self.select_photo)
        self.photo_delete_button.clicked.connect(self.delete_photo)
        photo_layout.addWidget(self.photo_preview, 1)
        photo_layout.addWidget(self.photo_button)
        photo_layout.addWidget(self.photo_delete_button)
        top.addWidget(photo_group, 2)
        body_layout.addLayout(top)

        maintenance_group = QGroupBox("Интервалы ТО")
        maintenance_group.setContentsMargins(0, 14, 0, 0)
        maintenance_layout = QVBoxLayout(maintenance_group)
        info_label = QLabel(
            "Интервалы задаются в моточасах. "
            "Стандартно: 50, 250, 500, 1000, 2000, 4000."
        )
        info_label.setWordWrap(True)
        maintenance_layout.addWidget(info_label)
        self.maintenance_list = QListWidget()
        self.maintenance_list.setMinimumHeight(120)
        maintenance_layout.addWidget(self.maintenance_list)
        interval_controls = QHBoxLayout()
        self.interval_hours = QDoubleSpinBox()
        self.interval_hours.setRange(1, 100_000_000)
        self.interval_hours.setDecimals(0)
        self.interval_hours.setValue(50)
        self.interval_hours.setSuffix(" м/ч")
        self.add_interval_button = QPushButton("Добавить интервал")
        self.delete_interval_button = QPushButton("Удалить выбранный")
        interval_controls.addWidget(self.interval_hours)
        interval_controls.addWidget(self.add_interval_button)
        interval_controls.addWidget(self.delete_interval_button)
        maintenance_layout.addLayout(interval_controls)
        body_layout.addWidget(maintenance_group, 1)

        self.add_interval_button.clicked.connect(self.add_maintenance_interval)
        self.delete_interval_button.clicked.connect(self.delete_maintenance_interval)

        self.current_hours.valueChanged.connect(self.update_service_status)
        self.warranty_years.valueChanged.connect(self.update_service_status)
        self.warranty_hours.valueChanged.connect(self.update_service_status)
        self.warranty_start_hours.valueChanged.connect(self.update_service_status)
        self.commissioning_date.dateChanged.connect(self.update_service_status)

        body_layout.addStretch()
        self.body_scroll.setWidget(body)
        layout.addWidget(self.body_scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        save = QPushButton("Сохранить")
        cancel = QPushButton("Отмена")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _load_reference_lists(self):
        self.manufacturer.clear()
        self.distributor.clear()
        self.manufacturer.addItem("Не указан", None)
        self.distributor.addItem("Не указан", None)
        if self.repository is None:
            return
        for row in get_all_manufacturers(self.repository):
            self.manufacturer.addItem(row["name"], row["id"])
        for row in self.repository.get_distributors():
            self.distributor.addItem(row["name"], row["id"])

    def _select_combo_id(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def select_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите фото техники",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.photo_path = path
            self.refresh_photo()

    def delete_photo(self):
        self.photo_path = ""
        self.refresh_photo()

    def refresh_photo(self):
        if self.photo_path and Path(self.photo_path).exists():
            pixmap = QPixmap(self.photo_path)
            self.photo_preview.setPixmap(
                pixmap.scaled(
                    self.photo_preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self.photo_preview.setText("")
        else:
            self.photo_preview.setPixmap(QPixmap())
            self.photo_preview.setText("Фото не добавлено")

    def update_service_status(self):
        years = float(self.warranty_years.value())
        warranty_hours = float(self.warranty_hours.value())
        start_hours = float(self.warranty_start_hours.value())
        current_hours = float(self.current_hours.value())

        date_valid = True
        hours_valid = True
        has_limit = False

        if years > 0:
            has_limit = True
            end_date = self.commissioning_date.date().addMonths(
                int(round(years * 12))
            )
            date_valid = QDate.currentDate() < end_date

        if warranty_hours > 0:
            has_limit = True
            hours_valid = current_hours < (start_hours + warranty_hours)

        warranty = has_limit and date_valid and hours_valid
        self.service_status.setText(
            "Гарантийное" if warranty else "Постгарантийное"
        )

    # ==========================================================
    # MAINTENANCE INTERVALS
    # ==========================================================

    def load_maintenance_intervals(self):
        self.maintenance_list.clear()

        if (
            self.repository is None
            or self.equipment_id is None
        ):
            self.maintenance_list.addItem(
                "Интервалы будут доступны "
                "после сохранения новой техники."
            )

            self.add_interval_button.setEnabled(
                False
            )

            self.delete_interval_button.setEnabled(
                False
            )

            return

        self.add_interval_button.setEnabled(
            True
        )

        self.delete_interval_button.setEnabled(
            True
        )

        rows = (
            self.repository
            .get_maintenance_intervals(
                self.equipment_id
            )
        )

        for row in rows:
            hours = float(
                row["interval_hours"]
                or 0
            )

            if hours.is_integer():
                hours_text = str(
                    int(hours)
                )
            else:
                hours_text = str(
                    hours
                )

            name = (
                row["name"]
                or f"ТО-{hours_text}"
            )

            item_text = (
                f"{name} — {hours_text} м/ч"
            )

            self.maintenance_list.addItem(
                item_text
            )

            item = (
                self.maintenance_list
                .item(
                    self.maintenance_list.count()
                    - 1
                )
            )

            item.setData(
                256,
                row["id"],
            )

    def add_maintenance_interval(self):
        if (
            self.repository is None
            or self.equipment_id is None
        ):
            return

        interval_hours = (
            self.interval_hours.value()
        )

        try:
            self.repository.add_maintenance_interval(
                equipment_id=self.equipment_id,
                interval_hours=interval_hours,
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "Интервалы ТО",
                str(error),
            )

            return

        self.load_maintenance_intervals()

    def delete_maintenance_interval(self):
        if (
            self.repository is None
            or self.equipment_id is None
        ):
            return

        item = (
            self.maintenance_list
            .currentItem()
        )

        if item is None:
            QMessageBox.information(
                self,
                "Интервалы ТО",
                "Выберите интервал для удаления.",
            )

            return

        interval_id = item.data(
            256
        )

        if interval_id is None:
            return

        answer = QMessageBox.question(
            self,
            "Удаление интервала",
            (
                "Удалить выбранный интервал ТО?\n\n"
                "История уже выполненных ТО "
                "удалена не будет."
            ),
            QMessageBox.Yes
            | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.repository.delete_maintenance_interval(
            interval_id
        )

        self.load_maintenance_intervals()

    # ==========================================================
    # DATA
    # ==========================================================

    def get_data(self):
        return {
            "model": self.model.text().strip(),
            "serial_number": self.serial_number.text().strip(),
            "garage_number": self.garage_number.text().strip(),
            "registration_number": self.registration_number.text().strip(),
            "manufacture_year": self.manufacture_year.value(),
            "current_hours": self.current_hours.value(),
            "commissioning_date": self.commissioning_date.date().toString("yyyy-MM-dd"),
            "warranty_years": self.warranty_years.value(),
            "warranty_hours": self.warranty_hours.value(),
            "warranty_start_hours": self.warranty_start_hours.value(),
            "photo_path": self.photo_path,
            "manufacturer_id": self.manufacturer.currentData(),
            "distributor_id": self.distributor.currentData(),
            "shift_hours_per_day": self.shift_hours_per_day.value(),
            "auto_maintenance": 1 if self.auto_maintenance.isChecked() else 0,
            "status": self.status.currentText(),
            "note": self.note.toPlainText().strip(),
        }

    def set_data(
        self,
        model="",
        serial_number="",
        garage_number="",
        registration_number="",
        manufacture_year=None,
        current_hours=0,
        status="В работе",
        note="",
        shift_hours_per_day=22,
        auto_maintenance=0,
        commissioning_date="",
        warranty_years=0,
        warranty_hours=0,
        warranty_start_hours=0,
        photo_path="",
        manufacturer_id=None,
        distributor_id=None,
    ):
        self.model.setText(str(model or ""))
        self.serial_number.setText(str(serial_number or ""))
        self.garage_number.setText(str(garage_number or ""))
        self.registration_number.setText(str(registration_number or ""))

        if manufacture_year:
            self.manufacture_year.setValue(int(manufacture_year))

        self.current_hours.setValue(float(current_hours or 0))

        parsed_date = QDate.fromString(str(commissioning_date or ""), "yyyy-MM-dd")
        if parsed_date.isValid():
            self.commissioning_date.setDate(parsed_date)

        self.warranty_years.setValue(float(warranty_years or 0))
        self.warranty_hours.setValue(float(warranty_hours or 0))
        self.warranty_start_hours.setValue(float(warranty_start_hours or 0))
        self.photo_path = str(photo_path or "")
        self.refresh_photo()
        self._select_combo_id(self.manufacturer, manufacturer_id)
        self._select_combo_id(self.distributor, distributor_id)

        shift_hours = float(shift_hours_per_day or 22)
        if shift_hours <= 0:
            shift_hours = 22.0
        self.shift_hours_per_day.setValue(shift_hours)

        self.auto_maintenance.setChecked(bool(auto_maintenance))
        self.status.setCurrentText(
            "Списан" if status == "Списан" else "В работе"
        )
        self.note.setPlainText(str(note or ""))
        self.update_service_status()
