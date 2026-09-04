from PySide6.QtCore import Qt
import os
import shutil
from pathlib import Path
from services.builtin_manufacturers import get_all_manufacturers
from PySide6.QtCore import Qt, QDate, QUrl, QMarginsF, QRectF
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QPdfWriter, QPainter, QFont, QFontMetricsF, QColor, QPen, QBrush, QPixmap, QImage
from PySide6.QtPrintSupport import QPrinter

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QFileDialog,
    QListWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
)


class EditWorkDialog(QDialog):

    def __init__(
        self,
        parent=None,
        repository=None,
        equipment_id=None,
        work_id=None,
    ):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)

        self.repository = repository
        self.equipment_id = equipment_id
        self.work_id = work_id
        self.equipment_rows = []

        self.setWindowTitle("Карточка работ / простоя")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 700)

        self.create_ui()
        self.load_equipment()
        self.load_maintenance_intervals()

    # ------------------------------------------------------------------

    def create_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        self.setStyleSheet("""
            QGroupBox {
                font-size: 15px;
                font-weight: 600;
                margin-top: 10px;
                padding-top: 12px;
            }
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                min-height: 32px;
                padding: 3px 8px;
                border-radius: 6px;
            }
            QTextEdit, QTableWidget, QListWidget {
                border-radius: 8px;
            }
            QPushButton {
                min-height: 34px;
                padding: 4px 14px;
                border-radius: 7px;
            }
        """)

        heading = QLabel("Карточка работ / простоя")
        heading.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(heading)

        self.request_number = QLineEdit()
        self.model = QLineEdit()
        self.equipment_select = QComboBox()
        self.equipment_select.addItem("— Выберите технику —", None)
        self.equipment_select.currentIndexChanged.connect(
            self.on_equipment_changed
        )
        self.garage_number = QLineEdit()
        self.garage_number.editingFinished.connect(
            self.select_equipment_by_garage
        )
        self.repair_type = QComboBox()
        self.repair_type.addItems([
            "Аварийный", "Плановый", "ТО",
            "Простой", "Работы заказчика",
            "Мониторинг состояния", "Модернизация",
        ])
        self.maintenance_interval = QComboBox()
        self.maintenance_interval_label = QLabel("Интервал ТО")
        self.maintenance_interval.setVisible(False)
        self.maintenance_interval_label.setVisible(False)
        self.repair_type.currentTextChanged.connect(
            self.on_repair_type_changed
        )
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("dd.MM.yyyy")
        self.date_start.setDate(QDate.currentDate())
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("dd.MM.yyyy")
        self.date_end.setDate(QDate.currentDate())
        self.in_progress = QCheckBox("Работа выполняется / техника в простое")
        self.machine_hours = QDoubleSpinBox()
        self.machine_hours.setDecimals(1)
        self.machine_hours.setMaximum(9999999)
        self.executors = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(105)
        self.requires_report = QCheckBox("Требуется отчёт")
        self.report_completed = QCheckBox("Отчёт выполнен")

        top = QHBoxLayout()
        top.setSpacing(14)

        basic_box = QGroupBox("Основные данные")
        basic = QGridLayout(basic_box)
        basic.setHorizontalSpacing(12)
        basic.setVerticalSpacing(8)
        fields = [
            ("№ заявки", self.request_number),
            ("Выбор техники", self.equipment_select),
            ("Модель", self.model),
            ("Гаражный №", self.garage_number),
            ("Тип работ", self.repair_type),
            ("Дата начала", self.date_start),
            ("Дата окончания", self.date_end),
            ("Наработка", self.machine_hours),
            ("Исполнители", self.executors),
        ]
        for i, (label, widget) in enumerate(fields):
            col = 0 if i < 5 else 2
            row = i if i < 5 else i - 5
            basic.addWidget(QLabel(label), row, col)
            basic.addWidget(widget, row, col + 1)
        basic.addWidget(
            self.maintenance_interval_label, 5, 0
        )
        basic.addWidget(self.maintenance_interval, 5, 1)
        basic.addWidget(self.in_progress, 5, 2, 1, 2)
        basic.setColumnStretch(1, 1)
        basic.setColumnStretch(3, 1)
        top.addWidget(basic_box, 3)

        side = QVBoxLayout()
        description_box = QGroupBox("Описание работ")
        description_layout = QVBoxLayout(description_box)
        description_layout.addWidget(self.description)
        side.addWidget(description_box, 2)

        report_box = QGroupBox("Отчёт")
        # The report block used to be squeezed by the right-hand column.
        # QListWidget then visually covered the buttons on Windows scaling >100%.
        # Give every control its own row and a guaranteed minimum height.
        # Reserve enough vertical space for two full button rows even with
        # Windows DPI scaling / larger application fonts.
        report_box.setMinimumHeight(275)
        report_layout = QVBoxLayout(report_box)
        report_layout.setContentsMargins(12, 16, 12, 12)
        report_layout.setSpacing(8)

        checks = QHBoxLayout()
        checks.setSpacing(14)
        checks.addWidget(self.requires_report)
        checks.addWidget(self.report_completed)
        checks.addStretch()
        report_layout.addLayout(checks)

        if self.work_id is not None and self.repository is not None:
            pdf_only_label = QLabel("Формат отчёта: только PDF")
            pdf_only_label.setStyleSheet("font-weight: 600;")
            report_layout.addWidget(pdf_only_label)

            self.report_files = QListWidget()
            self.report_files.setMinimumHeight(54)
            self.report_files.setMaximumHeight(68)
            self.report_files.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            report_layout.addWidget(self.report_files)

            self.btn_attach_report = QPushButton("Прикрепить PDF")
            self.btn_open_report = QPushButton("Открыть")
            self.btn_delete_report = QPushButton("Удалить")
            self.btn_instant_pdf = QPushButton("Мгновенный отчёт PDF")
            self.btn_instant_pdf.setProperty("primary", True)

            # Two independent rows are more reliable than QGridLayout here:
            # with Windows scaling the button size hint can be taller than the
            # grid row, which previously made neighbouring buttons overlap.
            for button in (
                self.btn_attach_report,
                self.btn_open_report,
                self.btn_delete_report,
                self.btn_instant_pdf,
            ):
                button.setMinimumHeight(40)

            report_actions = QVBoxLayout()
            report_actions.setContentsMargins(0, 0, 0, 0)
            report_actions.setSpacing(10)

            first_row = QHBoxLayout()
            first_row.setContentsMargins(0, 0, 0, 0)
            first_row.setSpacing(8)
            first_row.addWidget(self.btn_attach_report, 1)
            first_row.addWidget(self.btn_instant_pdf, 1)

            second_row = QHBoxLayout()
            second_row.setContentsMargins(0, 0, 0, 0)
            second_row.setSpacing(8)
            second_row.addWidget(self.btn_open_report, 1)
            second_row.addWidget(self.btn_delete_report, 1)

            report_actions.addLayout(first_row)
            report_actions.addLayout(second_row)
            report_layout.addLayout(report_actions)

            self.btn_attach_report.clicked.connect(self.attach_report)
            self.btn_open_report.clicked.connect(self.open_report)
            self.btn_delete_report.clicked.connect(self.delete_report)
            self.btn_instant_pdf.clicked.connect(self.generate_instant_pdf)
            self.refresh_report_files()
        side.addWidget(report_box, 0)
        top.addLayout(side, 2)
        root.addLayout(top)

        if self.work_id is not None and self.repository is not None:
            journal_box = QGroupBox("Ход работ по дням")
            journal = QVBoxLayout(journal_box)
            journal_buttons = QHBoxLayout()
            self.btn_add_day = QPushButton("Добавить день")
            self.btn_delete_day = QPushButton("Удалить день")
            journal_buttons.addWidget(self.btn_add_day)
            journal_buttons.addWidget(self.btn_delete_day)
            journal_buttons.addStretch()
            journal.addLayout(journal_buttons)

            self.daily_table = QTableWidget(0, 5)
            self.daily_table.setHorizontalHeaderLabels([
                "Дата", "Состояние дня",
                "Проделанная работа / причина простоя",
                "Исполнители", "Наработка",
            ])
            self.daily_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.daily_table.setSelectionMode(QTableWidget.SingleSelection)
            self.daily_table.setEditTriggers(QTableWidget.NoEditTriggers)
            header = self.daily_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(False)
            self.daily_table.setColumnWidth(0, 120)
            self.daily_table.setColumnWidth(1, 170)
            self.daily_table.setColumnWidth(2, 520)
            self.daily_table.setColumnWidth(3, 260)
            self.daily_table.setColumnWidth(4, 130)
            self.daily_table.setMinimumHeight(300)
            journal.addWidget(self.daily_table, 1)
            root.addWidget(journal_box, 1)

            self.btn_add_day.clicked.connect(self.add_daily_entry)
            self.btn_delete_day.clicked.connect(self.delete_daily_entry)
            self.daily_table.itemDoubleClicked.connect(
                lambda _item: self.add_daily_entry()
            )
            self.refresh_daily_log()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_cancel = QPushButton("Отмена")
        self.btn_save.setMinimumWidth(130)
        self.btn_cancel.setMinimumWidth(110)
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_cancel)
        root.addLayout(buttons)

    # ------------------------------------------------------------------

    def load_equipment(self):
        self.equipment_select.clear()

        self.equipment_select.addItem(
            "— Выберите технику —",
            None,
        )

        self.equipment_rows = []

        if self.repository is None:
            return

        rows = (
            self.repository
            .get_all_equipment()
        )

        for row in rows:
            self.equipment_rows.append(
                row
            )

            text = (
                f"{row['model']} — "
                f"гаражный №{row['garage_number']} — "
                f"S/N {row['serial_number']}"
            )

            self.equipment_select.addItem(
                text,
                row["id"],
            )

    # ------------------------------------------------------------------

    def select_equipment_by_garage(self):
        if self.repository is None:
            return
        garage = self.garage_number.text().strip().casefold()
        if not garage:
            return

        matches = []
        for index in range(1, self.equipment_select.count()):
            equipment_id = self.equipment_select.itemData(index)
            equipment = self.repository.get_equipment(equipment_id)
            if equipment is None:
                continue
            value = str(equipment["garage_number"] or "").strip().casefold()
            if value == garage:
                matches.append(index)

        if len(matches) == 1:
            self.equipment_select.setCurrentIndex(matches[0])

    def on_equipment_changed(
        self,
        index,
    ):
        equipment_id = (
            self.equipment_select.itemData(
                index
            )
        )

        if equipment_id is None:
            return

        self.equipment_id = equipment_id

        if self.repository is None:
            return

        equipment = (
            self.repository.get_equipment(
                equipment_id
            )
        )

        if equipment is None:
            return

        self.model.setText(
            equipment["model"] or ""
        )

        self.garage_number.setText(
            equipment["garage_number"] or ""
        )

        self.load_maintenance_intervals()

    # ------------------------------------------------------------------

    def load_maintenance_intervals(self):
        self.maintenance_interval.clear()

        if (
            self.repository is None
            or self.equipment_id is None
        ):
            return

        rows = (
            self.repository
            .get_maintenance_intervals(
                self.equipment_id
            )
        )

        for row in rows:
            if not row["active"]:
                continue

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

            self.maintenance_interval.addItem(
                name,
                hours,
            )

    # ------------------------------------------------------------------

    def on_repair_type_changed(
        self,
        repair_type,
    ):
        is_maintenance = (
            repair_type == "ТО"
        )

        self.maintenance_interval_label.setVisible(
            is_maintenance
        )

        self.maintenance_interval.setVisible(
            is_maintenance
        )

    # ------------------------------------------------------------------

    def set_data(
        self,
        request_number="",
        model="",
        garage_number="",
        repair_type="Аварийный",
        date_start=None,
        date_end=None,
        in_progress=True,
        machine_hours=0,
        executors="",
        description="",
        requires_report=False,
        report_completed=False,
        maintenance_interval=None,
    ):

        self.request_number.setText(request_number)

        self.model.setText(model)

        self.garage_number.setText(garage_number)

        display_type = str(repair_type or "").strip()
        low_type = display_type.lower().replace("ё", "е")
        if "авар" in low_type:
            display_type = "Аварийный"
        elif low_type == "то" or low_type.startswith("то-") or "плановые то" in low_type:
            display_type = "ТО"
        elif "полюс" in low_type or "заказ" in low_type:
            display_type = "Работы заказчика"
        elif "монитор" in low_type:
            display_type = "Мониторинг состояния"
        elif "модерн" in low_type or "сборк" in low_type or "гарант" in low_type:
            display_type = "Модернизация"
        elif "прост" in low_type or low_type == ">":
            display_type = "Простой"
        elif "план" in low_type:
            display_type = "Плановый"

        index = self.repair_type.findText(
            display_type,
            Qt.MatchExactly,
        )

        if index >= 0:
            self.repair_type.setCurrentIndex(index)

        if (
            repair_type == "ТО"
            and maintenance_interval is not None
        ):
            for i in range(
                self.maintenance_interval.count()
            ):
                interval_value = (
                    self.maintenance_interval.itemData(i)
                )

                if (
                    interval_value is not None
                    and float(interval_value)
                    == float(maintenance_interval)
                ):
                    self.maintenance_interval.setCurrentIndex(
                        i
                    )
                    break

        if date_start is not None:
            self.date_start.setDate(date_start)

        if date_end is not None:
            self.date_end.setDate(date_end)

        self.in_progress.setChecked(in_progress)

        self.machine_hours.setValue(machine_hours)

        self.executors.setText(executors)

        self.description.setPlainText(description)

        self.requires_report.setChecked(requires_report)

        self.report_completed.setChecked(report_completed)

    # ------------------------------------------------------------------

    def get_data(self):

        return {
            "request_number": self.request_number.text().strip(),
            "equipment_id": self.equipment_id,
            "model": self.model.text().strip(),
            "garage_number": self.garage_number.text().strip(),
            "repair_type": self.repair_type.currentText(),
            "maintenance_interval": (
                self.maintenance_interval.currentData()
                if self.repair_type.currentText() == "ТО"
                else None
            ),
            "date_start": self.date_start.date(),
            "date_end": self.date_end.date(),
            "in_progress": self.in_progress.isChecked(),
            "machine_hours": self.machine_hours.value(),
            "executors": self.executors.text().strip(),
            "description": self.description.toPlainText().strip(),
            "requires_report": self.requires_report.isChecked(),
            "report_completed": self.report_completed.isChecked(),
        }

    # ------------------------------------------------------------------

    def refresh_daily_log(self):
        if not hasattr(self, "daily_table"):
            return
        rows = self.repository.get_work_daily_log(self.work_id)
        self.daily_table.setRowCount(0)
        for data in rows:
            row = self.daily_table.rowCount()
            self.daily_table.insertRow(row)
            iso_date = str(data["work_date"] or "")
            parsed = QDate.fromString(iso_date, "yyyy-MM-dd")
            shown_date = (
                parsed.toString("dd.MM.yyyy")
                if parsed.isValid()
                else iso_date
            )
            values = [
                shown_date,
                data["day_type"],
                data["description"] or "",
                data["executors"] or "",
                data["machine_hours"] or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.UserRole, data["id"])
                    item.setData(Qt.UserRole + 1, iso_date)
                self.daily_table.setItem(row, column, item)

    def add_daily_entry(self):
        # Импорт здесь исключает циклическую зависимость.
        from dialogs.downtime_card_dialog import DailyEntryDialog
        row = self.daily_table.currentRow()
        is_editing = row >= 0
        default_executors = self.executors.text().strip()
        default_hours = self.machine_hours.value()

        # Для нового дня наследуем значения из последнего дня.
        if not is_editing and self.daily_table.rowCount() > 0:
            last = self.daily_table.rowCount() - 1
            default_executors = (
                self.daily_table.item(last, 3).text().strip()
                or default_executors
            )
            try:
                default_hours = float(
                    self.daily_table.item(last, 4).text()
                    or default_hours
                )
            except ValueError:
                pass

        dialog = DailyEntryDialog(
            self,
            default_executors,
            default_hours,
        )
        if is_editing:
            date_item = self.daily_table.item(row, 0)
            parsed = QDate.fromString(
                str(date_item.data(Qt.UserRole + 1) or ""),
                "yyyy-MM-dd",
            )
            if parsed.isValid():
                dialog.date.setDate(parsed)
            idx = dialog.day_type.findText(
                self.daily_table.item(row, 1).text()
            )
            if idx >= 0:
                dialog.day_type.setCurrentIndex(idx)
            dialog.description.setPlainText(
                self.daily_table.item(row, 2).text()
            )
            dialog.executors.setText(
                self.daily_table.item(row, 3).text()
            )
            try:
                dialog.hours.setValue(float(
                    self.daily_table.item(row, 4).text() or 0
                ))
            except ValueError:
                pass
        if not dialog.exec():
            return
        data = dialog.get_data()

        # Новое показание не должно незаметно откатывать наработку назад.
        current_hours = float(self.machine_hours.value() or 0)
        if (
            float(data["machine_hours"] or 0) < current_hours
            and float(data["machine_hours"] or 0) > 0
        ):
            answer = QMessageBox.warning(
                self,
                "Проверка наработки",
                (
                    f"Указана наработка {data['machine_hours']:.1f} м/ч, "
                    f"а текущая наработка {current_hours:.1f} м/ч.\n\n"
                    "Наработка меньше последней известной. "
                    "Сохранить это значение всё равно?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        self.repository.add_work_daily_entry(
            self.work_id,
            **data,
        )

        if float(data["machine_hours"] or 0) > current_hours:
            self.machine_hours.setValue(
                float(data["machine_hours"])
            )
        self.refresh_daily_log()

    def delete_daily_entry(self):
        row = self.daily_table.currentRow()
        if row < 0:
            return
        entry_id = self.daily_table.item(
            row, 0
        ).data(Qt.UserRole)
        if QMessageBox.question(
            self,
            "Удаление",
            "Удалить запись за этот день?",
        ) != QMessageBox.Yes:
            return
        self.repository.delete_work_daily_entry(entry_id)
        self.refresh_daily_log()

    def showEvent(self, event):
        super().showEvent(event)
        if self.work_id is not None:
            self.refresh_daily_log()

    def _report_storage_dir(self):
        base = Path.cwd() / "data" / "attachments" / "work_reports"
        base.mkdir(parents=True, exist_ok=True)
        return base / str(self.work_id)

    def refresh_report_files(self):
        if not hasattr(self, "report_files"):
            return
        self.report_files.clear()
        for row in self.repository.get_work_report_attachments(self.work_id):
            self.report_files.addItem(row["file_name"])
            item = self.report_files.item(self.report_files.count() - 1)
            item.setData(Qt.UserRole, row["id"])
            item.setData(Qt.UserRole + 1, row["file_path"])

    def attach_report(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите отчёт PDF", "", "PDF (*.pdf)"
        )
        if not path:
            return
        source = Path(path)
        if source.suffix.lower() != ".pdf":
            QMessageBox.warning(
                self,
                "Прикрепление отчёта",
                "Можно прикреплять только файлы PDF.",
            )
            return
        folder = self._report_storage_dir()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / source.name
        counter = 1
        while target.exists():
            target = folder / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        shutil.copy2(source, target)
        self.repository.add_work_report_attachment(
            self.work_id, target.name, str(target.resolve())
        )
        self.refresh_report_files()

    def open_report(self):
        item = self.report_files.currentItem()
        if item is None:
            return
        path = str(item.data(Qt.UserRole + 1) or "")
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "Отчёт", "Файл отчёта не найден.")
            return
        os.startfile(path)

    def delete_report(self):
        item = self.report_files.currentItem()
        if item is None:
            return
        if QMessageBox.question(
            self, "Удаление", "Удалить прикреплённый отчёт?"
        ) != QMessageBox.Yes:
            return
        attachment_id = item.data(Qt.UserRole)
        path = str(item.data(Qt.UserRole + 1) or "")
        self.repository.delete_work_report_attachment(attachment_id)
        try:
            if path and Path(path).exists():
                Path(path).unlink()
        except OSError:
            pass
        self.refresh_report_files()

    def generate_instant_pdf(self):
        """Компактный одностраничный/многостраничный PDF с фиксированной версткой QPainter."""
        if self.work_id is None or self.repository is None:
            QMessageBox.warning(self,"Мгновенный отчёт PDF","Сначала сохраните карточку ремонта."); return
        work=self.repository.get_work(self.work_id)
        if work is None:return
        from datetime import date, datetime
        import calendar
        import re
        equipment=self.repository.get_equipment(work["equipment_id"]) if work["equipment_id"] else None
        manufacturer_name=""; manufacturer_logo=""; machine_photo=""; service_status="Постгарантийное"
        if equipment is not None:
            machine_photo=str(equipment["photo_path"] or "")
            try:
                for m in get_all_manufacturers(self.repository):
                    if m["id"]==equipment["manufacturer_id"]:
                        manufacturer_name=str(m["name"] or ""); manufacturer_logo=str(m["logo_path"] or ""); break
            except Exception:pass
            years=float(equipment["warranty_years"] or 0); wh=float(equipment["warranty_hours"] or 0); start_h=float(equipment["warranty_start_hours"] or 0); cur=float(equipment["current_hours"] or 0); valid=True; has=False
            if years>0:
                has=True
                try:
                    d=date.fromisoformat(str(equipment["commissioning_date"])[:10]); months=int(round(years*12)); y=d.year+(d.month-1+months)//12; mo=(d.month-1+months)%12+1; endd=date(y,mo,min(d.day,calendar.monthrange(y,mo)[1])); valid=valid and date.today()<endd
                except Exception:valid=False
            if wh>0:has=True; valid=valid and cur<(start_h+wh)
            service_status="Гарантийное" if has and valid else "Постгарантийное"
        org_logo=""
        try:
            parent=self.parent()
            if parent is not None and hasattr(parent,"customer_manager"):org_logo=parent.customer_manager.get_organization_logo() or ""
        except Exception:pass
        daily=self.repository.get_work_daily_log(self.work_id)
        default=f"Сводная_информация_{work['model']}_{work['garage_number']}.pdf"
        path,_=QFileDialog.getSaveFileName(self,"Сохранить PDF",default,"PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith('.pdf'):path+='.pdf'
        def fmt(v):
            q=QDate.fromString(str(v or '')[:10],'yyyy-MM-dd'); return q.toString('dd.MM.yyyy') if q.isValid() else (str(v or '') or '—')
        def txt(v):return str(v or '')
        def compact(v):
            # Комментарии Excel нередко содержат несколько пустых строк.
            # В PDF они не несут смысла и только раздувают высоту строки.
            lines=[]
            for raw in txt(v).replace('\r\n','\n').replace('\r','\n').split('\n'):
                clean=re.sub(r'[ \t]+',' ',raw).strip()
                if clean:
                    lines.append(clean)
            return '\n'.join(lines)
        writer=QPdfWriter(path); writer.setResolution(150); writer.setPageSize(QPageSize(QPageSize.A4)); writer.setPageOrientation(QPageLayout.Landscape); writer.setPageMargins(QMarginsF(8,8,8,8),QPageLayout.Millimeter)
        painter=QPainter(writer); W=writer.width(); H=writer.height(); sx=W/1600.0; sy=H/1100.0
        def R(x,y,w,h):return QRectF(x*sx,y*sy,w*sx,h*sy)
        navy=QColor('#18324f'); blue=QColor('#2867b2'); light=QColor('#f7f9fc'); line=QColor('#d9e1ea'); muted=QColor('#64748b'); red=QColor('#c6283d'); orange=QColor('#e88318')
        def font(size,bold=False):f=QFont('Segoe UI'); f.setPointSizeF(size); f.setBold(bold); return f
        def draw_text(rect,text,size=10,bold=False,color=navy,align=Qt.AlignLeft|Qt.AlignVCenter,wrap=True):
            painter.setFont(font(size,bold)); painter.setPen(color); flags=align|(Qt.TextWordWrap if wrap else 0); painter.drawText(rect,flags,txt(text))
        def rounded(rect,fill=QColor('white'),stroke=line,r=10):painter.setPen(QPen(stroke,1.2)); painter.setBrush(QBrush(fill)); painter.drawRoundedRect(rect,r,r)
        def image_box(path,rect,placeholder='',clean_neutral_background=False):
            # Always paint a white base. Transparent PNGs therefore look clean in
            # PDF viewers and never inherit a checkerboard/transparency pattern.
            painter.fillRect(rect, QColor('white'))
            if path and Path(path).exists():
                pm=QPixmap(path)
                if not pm.isNull():
                    if clean_neutral_background:
                        # Some supplier/manufacturer logos are saved with the
                        # grey-white checker pattern baked into the PNG itself.
                        # Remove only bright neutral pixels, preserving coloured
                        # logo strokes (blue/red/etc.).
                        image = pm.toImage().convertToFormat(QImage.Format_ARGB32)
                        for iy in range(image.height()):
                            for ix in range(image.width()):
                                c = image.pixelColor(ix, iy)
                                mx = max(c.red(), c.green(), c.blue())
                                mn = min(c.red(), c.green(), c.blue())
                                if mx >= 180 and (mx - mn) <= 18:
                                    c.setAlpha(0)
                                    image.setPixelColor(ix, iy, c)
                        pm = QPixmap.fromImage(image)
                    scaled=pm.scaled(rect.size().toSize(),Qt.KeepAspectRatio,Qt.SmoothTransformation)
                    x=rect.x()+(rect.width()-scaled.width())/2
                    y=rect.y()+(rect.height()-scaled.height())/2
                    painter.drawPixmap(int(x),int(y),scaled)
                    return
            if placeholder:draw_text(rect,placeholder,8,False,muted,Qt.AlignCenter)
        # Header aligned logos
        image_box(org_logo,R(25,18,185,75),'ЛОГО ОРГАНИЗАЦИИ')
        draw_text(R(260,18,1080,48),'СВОДНАЯ ИНФОРМАЦИЯ ПО РЕМОНТУ',22,True,navy,Qt.AlignCenter)
        painter.setPen(QPen(blue,2)); painter.drawLine(int(560*sx),int(76*sy),int(1040*sx),int(76*sy))
        draw_text(R(500,78,600,26),f"{txt(work['model'])} · гаражный № {txt(work['garage_number'])}",10,False,blue,Qt.AlignCenter)
        image_box(manufacturer_logo,R(1390,18,185,75),'ЛОГОТИП\nПРОИЗВОДИТЕЛЯ',True)
        def logical_text_height(value, logical_width, size=8.1, bold=False, minimum=18.0):
            value=compact(value)
            if not value:
                return minimum
            painter.save()
            painter.setFont(font(size,bold))
            bounds=painter.boundingRect(
                R(0,0,max(20.0,logical_width),2000),
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                value,
            )
            painter.restore()
            return max(minimum,bounds.height()/max(sy,0.001))

        # top cards. Высота строк рассчитывается по содержимому, поэтому
        # многострочный статус/исполнители не прижимаются к разделителю.
        y=125; x1=25; w1=505; gap=20; x2=x1+w1+gap; w2=455; x3=x2+w2+gap; w3=1600-x3-25
        status='Работа выполняется / техника в простое' if work['in_progress'] else 'Работа завершена'
        left=[('Производитель',manufacturer_name),('Модель',work['model']),('Гаражный №',work['garage_number']),('Серийный №',work['serial_number']),('№ заявки',work['request_number']),('Тип ремонта',work['repair_type']),('Статус',status)]
        right=[('Дата начала',fmt(work['date_start'])),('Дата окончания',fmt(work['date_end']) if work['date_end'] else '—'),('Наработка (м/ч)',f"{float(work['machine_hours'] or 0):,.1f}".replace(',',' ')),('Исполнители',compact(work['executors'])),('Обслуживание',service_status)]

        def info_row_heights(width,data,base_height):
            heights=[]
            value_width=width*0.57-22
            for label,val in data:
                value_size=7.9 if label=='Статус' else 8.4
                required=logical_text_height(
                    val,value_width,value_size,label in ('Статус','Обслуживание')
                )+16.0
                minimum=50.0 if label=='Статус' else base_height
                if label=='Исполнители':
                    minimum=max(minimum,46.0)
                heights.append(max(minimum,required))
            return heights

        left_heights=info_row_heights(w1,left,37.0)
        right_heights=info_row_heights(w2,right,46.0)
        h=max(335.0,58.0+sum(left_heights)+18.0,58.0+sum(right_heights)+18.0)
        for rr in (R(x1,y,w1,h),R(x2,y,w2,h),R(x3,y,w3,h)):rounded(rr)
        draw_text(R(x1+22,y+15,w1-44,35),'ТЕХНИКА И РЕМОНТ',12,True,navy)
        draw_text(R(x2+22,y+15,w2-44,35),'ПЕРИОД И ПОКАЗАТЕЛИ',12,True,navy)

        def rows(base_x,base_y,width,data,row_heights):
            yy=base_y
            for (label,val),rowh in zip(data,row_heights):
                row_rect=R(base_x+16,yy,width-32,rowh)
                painter.save()
                painter.setClipRect(row_rect.adjusted(0,0,0,-1))
                draw_text(R(base_x+20,yy+4,width*0.36,rowh-8),label,8.0,False,muted)
                value_size=7.9 if label=='Статус' else 8.4
                draw_text(
                    R(base_x+width*0.39,yy+4,width*0.57-22,rowh-8),
                    val,value_size,label in ('Статус','Обслуживание'),
                    orange if label=='Обслуживание' and service_status=='Постгарантийное' else navy,
                    Qt.AlignLeft|Qt.AlignVCenter,True
                )
                painter.restore()
                painter.setPen(QPen(line,1))
                painter.drawLine(
                    int((base_x+18)*sx),int((yy+rowh)*sy),
                    int((base_x+width-18)*sx),int((yy+rowh)*sy)
                )
                yy+=rowh

        rows(x1,y+58,w1,left,left_heights)
        rows(x2,y+58,w2,right,right_heights)
        image_box(machine_photo,R(x3+12,y+12,w3-24,h-24),'ФОТО ТЕХНИКИ')

        # Description. Блок растёт по фактической высоте текста и полностью
        # отодвигает таблицу вниз — описание больше не обрезается.
        dy=y+h+20.0
        description_text=compact(work['description']) or '—'
        description_body_h=logical_text_height(description_text,1480,9.0,False,20.0)+8.0
        dh=max(115.0,45.0+description_body_h+16.0)
        rounded(R(25,dy,1550,dh),light)
        painter.setPen(QPen(blue,5))
        painter.drawLine(int(27*sx),int((dy+12)*sy),int(27*sx),int((dy+dh-12)*sy))
        draw_text(R(48,dy+12,1480,28),'ОПИСАНИЕ РЕМОНТА / НЕИСПРАВНОСТИ',11,True,navy)
        draw_text(R(48,dy+45,1480,dh-57),description_text,9,False,navy,Qt.AlignLeft|Qt.AlignTop,True)
        table_start_y=dy+dh+25.0
        # Table
        # Высота строк рассчитывается по реальному объёму текста. Исполнители
        # и описание могут занимать несколько строк; текст больше не должен
        # налезать на соседние строки. Если дневная история длинная, таблица
        # автоматически продолжается на следующих страницах.
        cols=[25,210,455,970,1260,1575]
        headers=['Дата','Состояние','Выполненные работы / причина простоя','Исполнители','Наработка (м/ч)']
        header_h=42

        prepared=[]
        for r in daily:
            description=compact(r['description'])
            executors=compact(r['executors'])
            values=[
                fmt(r['work_date']),
                compact(r['day_type']),
                description or '—',
                executors or '—',
                f"{float(r['machine_hours'] or 0):,.1f}".replace(',',' '),
            ]
            needed=max(
                55.0,
                logical_text_height(values[2],cols[3]-cols[2]-24,8.1,False)+14.0,
                logical_text_height(values[3],cols[4]-cols[3]-24,8.1,False)+14.0,
            )
            # Одна строка должна помещаться на странице. Очень длинные
            # комментарии всё равно получают значительно больше места, чем
            # прежние фиксированные 55 px.
            prepared.append((r,values,min(700.0,needed)))

        first_table_capacity=1015.0-(table_start_y+40.0+header_h)
        continuation_capacity=1015.0-(55.0+40.0+header_h)
        first_page_has_table=first_table_capacity>=55.0

        def split_pages(rows):
            # Первый элемент списка всегда относится к первой странице. Если
            # динамическое описание заняло почти весь лист, первая страница
            # остаётся без таблицы, а история начинается со второй страницы.
            pages=[[]]
            if not rows:
                return pages
            page_index=0
            used=0.0
            capacity=first_table_capacity if first_page_has_table else 0.0
            if not first_page_has_table:
                pages.append([])
                page_index=1
                capacity=continuation_capacity
            for item in rows:
                rh=item[2]
                if pages[page_index] and used+rh>capacity:
                    pages.append([])
                    page_index+=1
                    used=0.0
                    capacity=continuation_capacity
                pages[page_index].append(item)
                used+=rh
            return pages

        pages=split_pages(prepared)
        total_pages=max(1,len(pages))

        def table_header(ty,continuation=False):
            title='ХОД РАБОТ ПО ДНЯМ' + (' — ПРОДОЛЖЕНИЕ' if continuation else '')
            draw_text(R(25,ty,900,30),title,12,True,navy)
            ty+=40
            painter.fillRect(R(25,ty,1550,header_h),navy)
            for i,hdr in enumerate(headers):
                draw_text(R(cols[i]+8,ty,cols[i+1]-cols[i]-16,header_h),hdr,8.3,True,QColor('white'),Qt.AlignCenter)
            return ty+header_h

        def page_footer(page_no):
            draw_text(R(25,1040,900,28),f"Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",7.5,False,muted)
            draw_text(R(1320,1040,255,28),f'Страница {page_no} из {total_pages}',7.5,True,blue,Qt.AlignRight|Qt.AlignVCenter)

        def draw_day_row(ty,item,idx):
            r,vals,rowh=item
            painter.fillRect(R(25,ty,1550,rowh),QColor('#ffffff') if idx%2==0 else light)
            painter.setPen(QPen(line,1)); painter.drawRect(R(25,ty,1550,rowh))
            for i,v in enumerate(vals):
                draw_text(
                    R(cols[i]+8,ty+3,cols[i+1]-cols[i]-16,rowh-6),
                    v,8.1,i==1,
                    red if i==1 and 'авар' in txt(v).lower() else navy,
                    Qt.AlignCenter if i in (0,1,4) else Qt.AlignLeft|Qt.AlignVCenter,
                    True,
                )
            return ty+rowh

        if first_page_has_table:
            ty=table_header(table_start_y,False)
            for idx,item in enumerate(pages[0] if pages else []):
                ty=draw_day_row(ty,item,idx)
        page_footer(1)

        for page_no,page_rows in enumerate(pages[1:],start=2):
            writer.newPage()
            painter.fillRect(R(0,0,1600,1100),QColor('white'))
            ty=table_header(55,True)
            for idx,item in enumerate(page_rows):
                ty=draw_day_row(ty,item,idx)
            page_footer(page_no)
        painter.end()
        try:
            os.startfile(path)
        except OSError:
            pass
        QMessageBox.information(self,'Мгновенный отчёт PDF',f'PDF успешно создан и открыт:\n{path}')

    def clear(self):

        self.request_number.clear()

        self.model.clear()

        self.garage_number.clear()

        self.repair_type.setCurrentIndex(0)

        self.date_start.setDate(QDate.currentDate())

        self.date_end.setDate(QDate.currentDate())

        self.in_progress.setChecked(True)

        self.machine_hours.setValue(0)

        self.executors.clear()

        self.description.clear()

        self.requires_report.setChecked(False)

        self.report_completed.setChecked(False)
