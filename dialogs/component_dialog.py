from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QLabel, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)


class ComponentDialog(QDialog):
    def __init__(self,parent=None,repository=None):
        super().__init__(parent); self.repository=repository; self.setWindowTitle("Карточка компонента"); self.resize(720,620); self.create_ui(); self.load_equipment()
    def create_ui(self):
        root=QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(14)
        title=QLabel("Карточка компонента"); title.setStyleSheet("font-size:22px;font-weight:700;"); root.addWidget(title)
        form=QFormLayout(); form.setVerticalSpacing(10)
        self.equipment=QComboBox(); self.component_name=QLineEdit(); self.part_number=QLineEdit(); self.serial_number=QLineEdit()
        self.install_hours=QDoubleSpinBox(); self.install_hours.setRange(0,99999999); self.install_hours.setDecimals(1)
        self.resource=QDoubleSpinBox(); self.resource.setRange(0,99999999); self.resource.setDecimals(1)
        self.install_date=QDateEdit(); self.install_date.setCalendarPopup(True); self.install_date.setDisplayFormat("dd.MM.yyyy"); self.install_date.setDate(QDate.currentDate())
        self.note=QTextEdit(); self.note.setMinimumHeight(130)
        form.addRow("Привязка к технике:",self.equipment); form.addRow("Наименование компонента:",self.component_name); form.addRow("Каталожный №:",self.part_number); form.addRow("Серийный №:",self.serial_number); form.addRow("Наработка машины при установке, м/ч:",self.install_hours); form.addRow("Ресурс компонента, м/ч:",self.resource); form.addRow("Дата установки:",self.install_date); form.addRow("Примечание:",self.note); root.addLayout(form)
        row=QHBoxLayout(); row.addStretch(); self.btn_save=QPushButton("Сохранить"); self.btn_cancel=QPushButton("Отмена"); self.btn_save.clicked.connect(self.accept); self.btn_cancel.clicked.connect(self.reject); row.addWidget(self.btn_save); row.addWidget(self.btn_cancel); root.addLayout(row)
    def load_equipment(self):
        self.equipment.clear(); self.equipment.addItem("Без привязки к технике",None)
        if self.repository:
            for r in self.repository.get_all_equipment(): self.equipment.addItem(f"{r['model']} — гаражный № {r['garage_number']}",r['id'])
    def set_data(self,equipment_id=None,component_name="",part_number="",serial_number="",install_hours=0,resource=0,install_date="",note=""):
        i=self.equipment.findData(equipment_id); self.equipment.setCurrentIndex(i if i>=0 else 0); self.component_name.setText(str(component_name or "")); self.part_number.setText(str(part_number or "")); self.serial_number.setText(str(serial_number or "")); self.install_hours.setValue(float(install_hours or 0)); self.resource.setValue(float(resource or 0)); self.note.setPlainText(str(note or "")); d=QDate.fromString(str(install_date or "")[:10],"yyyy-MM-dd"); self.install_date.setDate(d if d.isValid() else QDate.currentDate())
    def lock_equipment(self, equipment_id):
        i = self.equipment.findData(equipment_id)
        if i >= 0:
            self.equipment.setCurrentIndex(i)
        self.equipment.setEnabled(False)
    def get_data(self):
        return {"equipment_id":self.equipment.currentData(),"component_name":self.component_name.text().strip(),"part_number":self.part_number.text().strip(),"serial_number":self.serial_number.text().strip(),"install_hours":self.install_hours.value(),"resource":self.resource.value(),"install_date":self.install_date.date().toString("yyyy-MM-dd"),"note":self.note.toPlainText().strip()}


class MachineComponentsDialog(QDialog):
    """Отдельное окно компонентов конкретной единицы техники.

    Окно намеренно не использует навигацию MainWindow: кнопка «Компоненты»
    из карточки машины всегда остаётся в контексте выбранной техники.
    """
    def __init__(self, parent=None, repository=None, equipment_id=None):
        super().__init__(parent)
        self.repository = repository
        self.equipment_id = equipment_id
        self.setWindowTitle("Компоненты техники")
        self.resize(1120, 620)
        self.setModal(True)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        machine = None
        if self.repository is not None and self.equipment_id is not None:
            try:
                machine = self.repository.get_equipment(self.equipment_id)
            except Exception:
                machine = None
        if machine is not None:
            title_text = f"Компоненты — {machine['model']} / г.№ {machine['garage_number']} / S/N {machine['serial_number']}"
        else:
            title_text = "Компоненты техники"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по наименованию, каталожному или серийному номеру...")
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")
        self.btn_refresh = QPushButton("Обновить")
        bar.addWidget(self.search, 1)
        for w in (self.btn_add, self.btn_edit, self.btn_delete, self.btn_refresh):
            bar.addWidget(w)
        root.addLayout(bar)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Компонент", "Каталожный №", "Серийный №", "Ресурс",
            "Установлен при", "Наработка", "Остаток", "Дата установки", "Примечание"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self.search.textChanged.connect(self.refresh)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_component)
        self.btn_edit.clicked.connect(self.edit_component)
        self.btn_delete.clicked.connect(self.delete_component)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_component())

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    @staticmethod
    def _fmt_date(value):
        d = QDate.fromString(str(value or "")[:10], "yyyy-MM-dd")
        return d.toString("dd.MM.yyyy") if d.isValid() else str(value or "")

    def refresh(self):
        self.table.setRowCount(0)
        if self.repository is None or self.equipment_id is None:
            return
        query = self.search.text().strip().casefold()
        rows = self.repository.get_components_by_equipment(self.equipment_id)
        for r in rows:
            hay = " ".join(str(r[k] or "") for k in ("component_name", "part_number", "serial_number", "note")).casefold()
            if query and query not in hay:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                r["component_name"] or "",
                r["part_number"] or "",
                r["serial_number"] or "",
                f"{float(r['resource_hours'] or 0):.1f}",
                f"{float(r['install_machine_hours'] or 0):.1f}",
                f"{float(r['worked_hours'] or 0):.1f}",
                f"{float(r['remaining_hours'] or 0):.1f}",
                self._fmt_date(r["install_date"]),
                r["note"] or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, r["id"])
                self.table.setItem(row, col, item)

    def add_component(self):
        d = ComponentDialog(self, repository=self.repository)
        d.lock_equipment(self.equipment_id)
        if not d.exec():
            return
        x = d.get_data()
        self.repository.add_component(
            self.equipment_id, x["component_name"], x["serial_number"],
            x["resource"], x["install_hours"], x["install_date"],
            x["part_number"], x["note"]
        )
        self.refresh()

    def edit_component(self):
        component_id = self._selected_id()
        if not component_id:
            return
        r = self.repository.get_component(component_id)
        if r is None:
            return
        d = ComponentDialog(self, repository=self.repository)
        d.set_data(
            self.equipment_id, r["component_name"], r["part_number"],
            r["serial_number"], r["install_machine_hours"],
            r["resource_hours"], r["install_date"], r["note"]
        )
        d.lock_equipment(self.equipment_id)
        if not d.exec():
            return
        x = d.get_data()
        self.repository.update_component(
            component_id, self.equipment_id, x["component_name"],
            x["serial_number"], x["resource"], x["install_hours"],
            x["install_date"], x["part_number"], x["note"]
        )
        self.refresh()

    def delete_component(self):
        component_id = self._selected_id()
        if not component_id:
            return
        if QMessageBox.question(
            self, "Удаление", "Удалить выбранный компонент?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self.repository.delete_component(component_id)
        self.refresh()
