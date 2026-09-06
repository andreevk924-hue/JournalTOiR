from pathlib import Path

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Не найден фрагмент для {label}")
    return text.replace(old, new, 1)

# ============================================================
# DATABASE MIGRATIONS
# ============================================================
p = Path("database/migrations.py")
s = p.read_text(encoding="utf-8")
marker = '''        # ======================================================
        # COMMIT
        # ======================================================
'''
block = '''        # ======================================================
        # ESTAR / WARRANTY / HOUR METER EXTENSIONS
        # ======================================================

        _add_column_if_missing(
            cursor, "equipment", "meter_hours", "REAL"
        )
        _add_column_if_missing(
            cursor, "equipment", "supply_contract_number", "TEXT"
        )
        cursor.execute(
            """
            UPDATE equipment
            SET meter_hours = current_hours
            WHERE meter_hours IS NULL
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment_hour_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                reset_date TEXT NOT NULL,
                hours_before_reset REAL NOT NULL DEFAULT 0,
                hours_after_reset REAL NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT,
                FOREIGN KEY(equipment_id)
                    REFERENCES equipment(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_equipment_hour_resets_equipment
            ON equipment_hour_resets(equipment_id, reset_date)
            """
        )

        _add_column_if_missing(
            cursor, "work_records", "is_warranty", "INTEGER DEFAULT 0"
        )
        _add_column_if_missing(
            cursor, "work_records", "warranty_claim_date", "TEXT"
        )
        _add_column_if_missing(
            cursor, "work_records", "warranty_claim_response", "TEXT"
        )

'''
s = replace_once(s, marker, block + marker, "migrations ESTAR")
p.write_text(s, encoding="utf-8")

# ============================================================
# REPOSITORY EXTENSIONS
# ============================================================
p = Path("database/repository.py")
s = p.read_text(encoding="utf-8")
append = r'''

    # ==========================================================
    # ESTAR: WARRANTY WORKS / HOUR METER RESETS
    # ==========================================================

    def get_equipment_hour_resets(self, equipment_id):
        return self._fetchall(
            """
            SELECT *
            FROM equipment_hour_resets
            WHERE equipment_id = ?
            ORDER BY reset_date ASC, id ASC
            """,
            (int(equipment_id),),
        )

    def get_hour_reset_offset(self, equipment_id):
        row = self._fetchone(
            """
            SELECT COALESCE(
                SUM(hours_before_reset - hours_after_reset),
                0
            ) AS offset_hours
            FROM equipment_hour_resets
            WHERE equipment_id = ?
            """,
            (int(equipment_id),),
        )
        return float(row["offset_hours"] or 0) if row is not None else 0.0

    def set_equipment_extended_fields(
        self,
        equipment_id,
        meter_hours=None,
        supply_contract_number="",
    ):
        equipment = self._fetchone(
            "SELECT * FROM equipment WHERE id = ?",
            (int(equipment_id),),
        )
        if equipment is None:
            raise ValueError("Техника не найдена.")

        if meter_hours is None:
            meter_hours = equipment["current_hours"] or 0
        meter_hours = max(0.0, float(meter_hours or 0))
        total_hours = meter_hours + self.get_hour_reset_offset(equipment_id)

        self._execute(
            """
            UPDATE equipment
            SET meter_hours = ?,
                current_hours = ?,
                supply_contract_number = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                meter_hours,
                total_hours,
                str(supply_contract_number or "").strip(),
                self._now(),
                int(equipment_id),
            ),
        )
        return total_hours

    def update_equipment_total_hours(self, equipment_id, total_hours):
        total_hours = max(0.0, float(total_hours or 0))
        offset = self.get_hour_reset_offset(equipment_id)
        meter_hours = max(0.0, total_hours - offset)
        self._execute(
            """
            UPDATE equipment
            SET current_hours = ?,
                meter_hours = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (total_hours, meter_hours, self._now(), int(equipment_id)),
        )

    def add_equipment_hour_reset(
        self,
        equipment_id,
        reset_date,
        hours_before_reset,
        hours_after_reset=0,
        note="",
    ):
        if self._fetchone(
            "SELECT id FROM equipment WHERE id = ?",
            (int(equipment_id),),
        ) is None:
            raise ValueError("Техника не найдена.")

        reset_date = str(reset_date or "").strip()
        if not reset_date:
            raise ValueError("Укажите дату сброса.")

        before = max(0.0, float(hours_before_reset or 0))
        after = max(0.0, float(hours_after_reset or 0))
        if before < after:
            raise ValueError(
                "Наработка до сброса не может быть меньше показания после сброса."
            )

        cursor = self._execute(
            """
            INSERT INTO equipment_hour_resets (
                equipment_id, reset_date,
                hours_before_reset, hours_after_reset,
                note, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(equipment_id), reset_date, before, after,
                str(note or "").strip(), self._now(),
            ),
        )

        equipment = self._fetchone(
            "SELECT meter_hours FROM equipment WHERE id = ?",
            (int(equipment_id),),
        )
        meter = float(equipment["meter_hours"] or 0) if equipment else 0.0
        self.set_equipment_extended_fields(
            equipment_id,
            meter_hours=meter,
            supply_contract_number=(
                self._fetchone(
                    "SELECT supply_contract_number FROM equipment WHERE id = ?",
                    (int(equipment_id),),
                )["supply_contract_number"] or ""
            ),
        )
        return cursor.lastrowid

    def delete_equipment_hour_reset(self, reset_id):
        row = self._fetchone(
            """
            SELECT equipment_id
            FROM equipment_hour_resets
            WHERE id = ?
            """,
            (int(reset_id),),
        )
        if row is None:
            return
        equipment_id = int(row["equipment_id"])
        self._execute(
            "DELETE FROM equipment_hour_resets WHERE id = ?",
            (int(reset_id),),
        )
        equipment = self._fetchone(
            "SELECT meter_hours, supply_contract_number FROM equipment WHERE id = ?",
            (equipment_id,),
        )
        if equipment is not None:
            self.set_equipment_extended_fields(
                equipment_id,
                meter_hours=float(equipment["meter_hours"] or 0),
                supply_contract_number=equipment["supply_contract_number"] or "",
            )

    def set_work_warranty_details(
        self,
        work_id,
        is_warranty=False,
        warranty_claim_date="",
        warranty_claim_response="",
    ):
        is_warranty = bool(is_warranty)
        claim_date = str(warranty_claim_date or "").strip() if is_warranty else ""
        response = str(warranty_claim_response or "").strip() if is_warranty else ""
        self._execute(
            """
            UPDATE work_records
            SET is_warranty = ?,
                warranty_claim_date = ?,
                warranty_claim_response = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                1 if is_warranty else 0,
                claim_date,
                response,
                self._now(),
                int(work_id),
            ),
        )
'''
s = s.rstrip() + "\n" + append + "\n"
p.write_text(s, encoding="utf-8")

# ============================================================
# EQUIPMENT DIALOG
# ============================================================
p = Path("dialogs/equipment_dialog.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''    QScrollArea,
    QSpinBox,
    QSizePolicy,
''',
    '''    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
''',
    "equipment imports",
)

s = replace_once(
    s,
    '''        self.create_ui()
        self.load_maintenance_intervals()
''',
    '''        self.create_ui()
        self.load_maintenance_intervals()
        self.load_hour_resets()
''',
    "equipment init hour resets",
)

s = replace_once(
    s,
    '''        self.current_hours = QDoubleSpinBox()
        self.current_hours.setRange(0, 100_000_000)
        self.current_hours.setDecimals(1)

        self.commissioning_date = QDateEdit()
''',
    '''        # Текущее физическое показание счётчика. Общая наработка
        # рассчитывается с учётом зарегистрированных сбросов.
        self.current_hours = QDoubleSpinBox()
        self.current_hours.setRange(0, 100_000_000)
        self.current_hours.setDecimals(1)

        self.total_hours_label = QLabel("0.0 м/ч")
        self.total_hours_label.setStyleSheet(
            "font-size: 15px; font-weight: 700;"
        )

        self.supply_contract_number = QLineEdit()

        self.commissioning_date = QDateEdit()
''',
    "equipment meter fields",
)

s = replace_once(
    s,
    '''        form.addRow("Дата ввода в эксплуатацию:", self.commissioning_date)
        form.addRow("Текущая наработка:", self.current_hours)
        form.addRow("Срок гарантии:", self.warranty_years)
''',
    '''        form.addRow("Дата ввода в эксплуатацию:", self.commissioning_date)
        form.addRow("Договор поставки:", self.supply_contract_number)
        form.addRow("Показание счётчика:", self.current_hours)
        form.addRow("Общая наработка:", self.total_hours_label)
        self.btn_hour_resets = QPushButton("История сбросов счётчика…")
        form.addRow("Сбросы наработки:", self.btn_hour_resets)
        form.addRow("Срок гарантии:", self.warranty_years)
''',
    "equipment form rows",
)

s = replace_once(
    s,
    '''        self.add_interval_button.clicked.connect(self.add_maintenance_interval)
        self.delete_interval_button.clicked.connect(self.delete_maintenance_interval)

        self.current_hours.valueChanged.connect(self.update_service_status)
''',
    '''        self.add_interval_button.clicked.connect(self.add_maintenance_interval)
        self.delete_interval_button.clicked.connect(self.delete_maintenance_interval)
        self.btn_hour_resets.clicked.connect(self.manage_hour_resets)

        self.current_hours.valueChanged.connect(self.update_service_status)
''',
    "equipment reset signal",
)

s = replace_once(
    s,
    '''        current_hours = float(self.current_hours.value())

        date_valid = True
''',
    '''        current_hours = float(self.calculated_total_hours())
        self.total_hours_label.setText(f"{current_hours:,.1f} м/ч".replace(",", " "))

        date_valid = True
''',
    "service total hours",
)

s = replace_once(
    s,
    '''            "current_hours": self.current_hours.value(),
            "commissioning_date": self.commissioning_date.date().toString("yyyy-MM-dd"),
''',
    '''            "meter_hours": self.current_hours.value(),
            "current_hours": self.calculated_total_hours(),
            "supply_contract_number": self.supply_contract_number.text().strip(),
            "commissioning_date": self.commissioning_date.date().toString("yyyy-MM-dd"),
''',
    "equipment get data",
)

s = replace_once(
    s,
    '''        current_hours=0,
        status="В работе",
''',
    '''        current_hours=0,
        meter_hours=None,
        supply_contract_number="",
        status="В работе",
''',
    "equipment set_data signature",
)

s = replace_once(
    s,
    '''        self.current_hours.setValue(float(current_hours or 0))

        parsed_date = QDate.fromString(str(commissioning_date or ""), "yyyy-MM-dd")
''',
    '''        if meter_hours is None:
            meter_hours = current_hours
        self.current_hours.setValue(float(meter_hours or 0))
        self.supply_contract_number.setText(str(supply_contract_number or ""))

        parsed_date = QDate.fromString(str(commissioning_date or ""), "yyyy-MM-dd")
''',
    "equipment set meter data",
)

append_eq = r'''

    # ==========================================================
    # HOUR METER RESET HISTORY
    # ==========================================================

    def hour_reset_offset(self):
        if self.repository is None or self.equipment_id is None:
            return 0.0
        try:
            return float(
                self.repository.get_hour_reset_offset(self.equipment_id)
                or 0
            )
        except Exception:
            return 0.0

    def calculated_total_hours(self):
        return max(
            0.0,
            float(self.current_hours.value()) + self.hour_reset_offset(),
        )

    def load_hour_resets(self):
        if not hasattr(self, "btn_hour_resets"):
            return
        self.btn_hour_resets.setEnabled(
            self.repository is not None and self.equipment_id is not None
        )
        self.update_service_status()

    def manage_hour_resets(self):
        if self.repository is None or self.equipment_id is None:
            QMessageBox.information(
                self,
                "Сбросы наработки",
                "Сначала сохраните карточку техники.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("История сбросов счётчика наработки")
        dialog.resize(760, 430)
        root = QVBoxLayout(dialog)

        info = QLabel(
            "Общая наработка = текущее показание счётчика + "
            "сумма наработки, потерянной при сбросах."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            "Дата",
            "До сброса",
            "После сброса",
            "Добавка к общей",
            "Примечание",
        ])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.Stretch
        )
        root.addWidget(table, 1)

        def refresh():
            rows = self.repository.get_equipment_hour_resets(
                self.equipment_id
            )
            table.setRowCount(0)
            for row in rows:
                rr = table.rowCount()
                table.insertRow(rr)
                qd = QDate.fromString(
                    str(row["reset_date"] or "")[:10],
                    "yyyy-MM-dd",
                )
                values = [
                    qd.toString("dd.MM.yyyy") if qd.isValid() else row["reset_date"],
                    f"{float(row['hours_before_reset'] or 0):.1f}",
                    f"{float(row['hours_after_reset'] or 0):.1f}",
                    f"{float(row['hours_before_reset'] or 0) - float(row['hours_after_reset'] or 0):.1f}",
                    row["note"] or "",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if col == 0:
                        item.setData(Qt.UserRole, row["id"])
                    table.setItem(rr, col, item)

        actions = QHBoxLayout()
        btn_add = QPushButton("Добавить сброс")
        btn_delete = QPushButton("Удалить выбранный")
        btn_close = QPushButton("Закрыть")
        actions.addWidget(btn_add)
        actions.addWidget(btn_delete)
        actions.addStretch()
        actions.addWidget(btn_close)
        root.addLayout(actions)

        def add_reset():
            d = QDialog(dialog)
            d.setWindowTitle("Сброс счётчика")
            f = QFormLayout(d)
            reset_date = QDateEdit()
            reset_date.setCalendarPopup(True)
            reset_date.setDisplayFormat("dd.MM.yyyy")
            reset_date.setDate(QDate.currentDate())
            before = QDoubleSpinBox()
            before.setRange(0, 100_000_000)
            before.setDecimals(1)
            before.setSuffix(" м/ч")
            after = QDoubleSpinBox()
            after.setRange(0, 100_000_000)
            after.setDecimals(1)
            after.setSuffix(" м/ч")
            note = QLineEdit()
            f.addRow("Дата сброса:", reset_date)
            f.addRow("Наработка до сброса:", before)
            f.addRow("Показание после сброса:", after)
            f.addRow("Примечание:", note)
            box = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel
            )
            box.accepted.connect(d.accept)
            box.rejected.connect(d.reject)
            f.addRow(box)
            if not d.exec():
                return
            try:
                self.repository.add_equipment_hour_reset(
                    self.equipment_id,
                    reset_date.date().toString("yyyy-MM-dd"),
                    before.value(),
                    after.value(),
                    note.text().strip(),
                )
            except Exception as error:
                QMessageBox.warning(d, "Сброс наработки", str(error))
                return
            refresh()
            self.update_service_status()

        def delete_reset():
            row = table.currentRow()
            if row < 0:
                return
            item = table.item(row, 0)
            if item is None:
                return
            if QMessageBox.question(
                dialog,
                "Сброс наработки",
                "Удалить выбранную запись о сбросе?",
            ) != QMessageBox.Yes:
                return
            self.repository.delete_equipment_hour_reset(
                item.data(Qt.UserRole)
            )
            refresh()
            self.update_service_status()

        btn_add.clicked.connect(add_reset)
        btn_delete.clicked.connect(delete_reset)
        btn_close.clicked.connect(dialog.accept)
        refresh()
        dialog.exec()
        self.update_service_status()
'''
s = s.rstrip() + "\n" + append_eq + "\n"
p.write_text(s, encoding="utf-8")

# ============================================================
# WORK DIALOG: WARRANTY BLOCK
# ============================================================
p = Path("dialogs/edit_work_dialog.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''        self.requires_report = QCheckBox("Требуется отчёт")
        self.report_completed = QCheckBox("Отчёт выполнен")

        top = QHBoxLayout()
''',
    '''        self.requires_report = QCheckBox("Требуется отчёт")
        self.report_completed = QCheckBox("Отчёт выполнен")

        self.is_warranty = QCheckBox("Гарантийная работа")
        self.is_warranty.toggled.connect(self.on_warranty_toggled)
        self.claim_registered = QCheckBox("АР оформлен")
        self.warranty_claim_date = QDateEdit()
        self.warranty_claim_date.setCalendarPopup(True)
        self.warranty_claim_date.setDisplayFormat("dd.MM.yyyy")
        self.warranty_claim_date.setDate(QDate.currentDate())
        self.claim_registered.toggled.connect(
            self.warranty_claim_date.setEnabled
        )
        self.warranty_claim_response = QTextEdit()
        self.warranty_claim_response.setMinimumHeight(70)

        top = QHBoxLayout()
''',
    "work warranty controls",
)

s = replace_once(
    s,
    '''        side.addWidget(description_box, 2)

        report_box = QGroupBox("Отчёт")
''',
    '''        side.addWidget(description_box, 2)

        side.addWidget(self.is_warranty, 0)

        self.warranty_box = QGroupBox("Гарантийная работа / АР")
        warranty_layout = QFormLayout(self.warranty_box)
        warranty_layout.addRow("", self.claim_registered)
        warranty_layout.addRow("Дата АР", self.warranty_claim_date)
        warranty_layout.addRow("Ответ на АР", self.warranty_claim_response)
        self.warranty_claim_date.setEnabled(False)
        self.warranty_box.setVisible(False)
        side.addWidget(self.warranty_box, 0)

        report_box = QGroupBox("Отчёт")
''',
    "work warranty group",
)

s = replace_once(
    s,
    '''        maintenance_interval=None,
    ):

        self.request_number.setText(request_number)
''',
    '''        maintenance_interval=None,
        is_warranty=False,
        warranty_claim_date="",
        warranty_claim_response="",
    ):

        self.request_number.setText(request_number)
''',
    "work set_data warranty signature",
)

s = replace_once(
    s,
    '''        self.report_completed.setChecked(report_completed)

    # ------------------------------------------------------------------

    def get_data(self):
''',
    '''        self.report_completed.setChecked(report_completed)

        self.is_warranty.setChecked(bool(is_warranty))
        claim_date = QDate.fromString(
            str(warranty_claim_date or "")[:10],
            "yyyy-MM-dd",
        )
        self.claim_registered.setChecked(claim_date.isValid())
        if claim_date.isValid():
            self.warranty_claim_date.setDate(claim_date)
        self.warranty_claim_response.setPlainText(
            str(warranty_claim_response or "")
        )
        self.on_warranty_toggled(bool(is_warranty))

    # ------------------------------------------------------------------

    def on_warranty_toggled(self, checked):
        checked = bool(checked)
        self.warranty_box.setVisible(checked)
        self.claim_registered.setEnabled(checked)
        self.warranty_claim_date.setEnabled(
            checked and self.claim_registered.isChecked()
        )
        self.warranty_claim_response.setEnabled(checked)

    # ------------------------------------------------------------------

    def get_data(self):
''',
    "work set warranty data",
)

s = replace_once(
    s,
    '''            "report_completed": self.report_completed.isChecked(),
        }
''',
    '''            "report_completed": self.report_completed.isChecked(),
            "is_warranty": self.is_warranty.isChecked(),
            "warranty_claim_date": (
                self.warranty_claim_date.date().toString("yyyy-MM-dd")
                if self.is_warranty.isChecked()
                and self.claim_registered.isChecked()
                else ""
            ),
            "warranty_claim_response": (
                self.warranty_claim_response.toPlainText().strip()
                if self.is_warranty.isChecked()
                else ""
            ),
        }
''',
    "work get warranty data",
)

s = replace_once(
    s,
    '''        self.report_completed.setChecked(False)
''',
    '''        self.report_completed.setChecked(False)
        self.is_warranty.setChecked(False)
        self.claim_registered.setChecked(False)
        self.warranty_claim_response.clear()
        self.on_warranty_toggled(False)
''',
    "work clear warranty",
)

p.write_text(s, encoding="utf-8")

# ============================================================
# SCHEDULE: WARRANTY COLOR
# ============================================================
p = Path("gui/pages/schedule_page.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''    COLOR_FUTURE = QColor(230, 150, 60)

    COLOR_TODAY = QColor(255, 245, 200)
''',
    '''    COLOR_FUTURE = QColor(230, 150, 60)
    # Отдельный цвет гарантийных работ, не совпадающий с существующими.
    COLOR_WARRANTY = QColor(226, 76, 154)       # #E24C9A

    COLOR_TODAY = QColor(255, 245, 200)
''',
    "schedule warranty color",
)

s = replace_once(
    s,
    '''            (self.COLOR_FUTURE, "Будущие работы"),
        ]
''',
    '''            (self.COLOR_FUTURE, "Будущие работы"),
            (self.COLOR_WARRANTY, "Гарантийная работа"),
        ]
''',
    "schedule warranty legend",
)

s = replace_once(
    s,
    '''        if "модерн" in normalized or "сборк" in normalized or "гарант" in normalized:
            return "Модернизация"
''',
    '''        if "гарант" in normalized:
            return "Гарантийная работа"
        if "модерн" in normalized or "сборк" in normalized:
            return "Модернизация"
''',
    "schedule normalize warranty",
)

s = replace_once(
    s,
    '''            "Будущие работы": self.COLOR_FUTURE,
        }.get(normalized)
''',
    '''            "Будущие работы": self.COLOR_FUTURE,
            "Гарантийная работа": self.COLOR_WARRANTY,
        }.get(normalized)
''',
    "schedule status map warranty",
)

s = replace_once(
    s,
    '''            plan_only_maintenance = is_maintenance and is_planned and not is_started

            # --------------------------------------------------
''',
    '''            plan_only_maintenance = is_maintenance and is_planned and not is_started
            try:
                is_warranty_work = bool(work["is_warranty"])
            except (KeyError, IndexError):
                is_warranty_work = False

            # --------------------------------------------------
''',
    "schedule warranty flag",
)

s = replace_once(
    s,
    '''                    if daily is not None:
                        cell_status = self.normalize_status(effective_type)
                    elif is_future_work:
''',
    '''                    if is_warranty_work:
                        cell_status = "Гарантийная работа"
                    elif daily is not None:
                        cell_status = self.normalize_status(effective_type)
                    elif is_future_work:
''',
    "schedule warranty override",
)

# Tooltip: append warranty details before description.
s = replace_once(
    s,
    '''        # ------------------------------------------------------
        # DESCRIPTION
        # ------------------------------------------------------
''',
    '''        # ------------------------------------------------------
        # WARRANTY / CLAIM
        # ------------------------------------------------------

        if "is_warranty" in keys and bool(work["is_warranty"]):
            lines.append("Гарантийная работа: Да")
            if "warranty_claim_date" in keys:
                claim_date = str(work["warranty_claim_date"] or "").strip()
                if claim_date:
                    lines.append("Дата АР: " + claim_date)
            if "warranty_claim_response" in keys:
                response = str(work["warranty_claim_response"] or "").strip()
                if response:
                    lines.append("Ответ на АР: " + response)

        # ------------------------------------------------------
        # DESCRIPTION
        # ------------------------------------------------------
''',
    "schedule warranty tooltip",
)

p.write_text(s, encoding="utf-8")

# ============================================================
# WORK PAGE: VISIBLE WARRANTY COLUMN
# ============================================================
p = Path("gui/pages/work_page.py")
s = p.read_text(encoding="utf-8")
s = replace_once(s, "self.table.setColumnCount(10)", "self.table.setColumnCount(11)", "work column count")
s = replace_once(
    s,
    '''            "Отчет выполнен",
        ])
''',
    '''            "Отчет выполнен",
            "Гарантия",
        ])
''',
    "work warranty header",
)
s = replace_once(
    s,
    '''        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        return self.table
''',
    '''        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)

        return self.table
''',
    "work warranty resize",
)
s = replace_once(
    s,
    '''        report_completed,
    ):
''',
    '''        report_completed,
        is_warranty=False,
    ):
''',
    "work page add signature",
)
s = replace_once(
    s,
    '''            "Да" if report_completed else "Нет",
        ]
''',
    '''            "Да" if report_completed else "Нет",
            "Да" if is_warranty else "Нет",
        ]
''',
    "work page warranty value",
)
p.write_text(s, encoding="utf-8")

# ============================================================
# MAIN WINDOW: SAVE/LOAD EXTENDED FIELDS + PDF WARRANTY COLOR
# ============================================================
p = Path("gui/main_window.py")
s = p.read_text(encoding="utf-8")

# Add equipment: capture id and persist extended fields.
s = replace_once(
    s,
    '''        self.repository.add_equipment(
            model=data["model"],
''',
    '''        equipment_id = self.repository.add_equipment(
            model=data["model"],
''',
    "main add equipment id",
)
s = replace_once(
    s,
    '''            distributor_id=data.get("distributor_id"),
        )

        self.refresh_all()
''',
    '''            distributor_id=data.get("distributor_id"),
        )
        self.repository.set_equipment_extended_fields(
            equipment_id,
            meter_hours=data.get("meter_hours", data.get("current_hours", 0)),
            supply_contract_number=data.get("supply_contract_number", ""),
        )

        self.refresh_all()
''',
    "main add equipment extended",
)

# Equipment edit set_data extended.
s = replace_once(
    s,
    '''            current_hours=(
                row["current_hours"] or 0
            ),
            status=(
''',
    '''            current_hours=(
                row["current_hours"] or 0
            ),
            meter_hours=(
                row["meter_hours"]
                if "meter_hours" in row.keys()
                and row["meter_hours"] is not None
                else row["current_hours"] or 0
            ),
            supply_contract_number=(
                row["supply_contract_number"]
                if "supply_contract_number" in row.keys()
                else ""
            ) or "",
            status=(
''',
    "main equipment set extended",
)

# After update_equipment (unique occurrence later) add extended update.
needle = '''            distributor_id=data.get("distributor_id"),
        )

        self.refresh_all()

        self.status.showMessage(
            "Данные техники обновлены.",
'''
if needle not in s:
    raise RuntimeError("Не найден блок edit equipment extended")
s = s.replace(
    needle,
    '''            distributor_id=data.get("distributor_id"),
        )
        self.repository.set_equipment_extended_fields(
            equipment_id,
            meter_hours=data.get("meter_hours", data.get("current_hours", 0)),
            supply_contract_number=data.get("supply_contract_number", ""),
        )

        self.refresh_all()

        self.status.showMessage(
            "Техника обновлена.",
''',
    1,
)

# Add work warranty details right after add_work.
s = replace_once(
    s,
    '''        machine_hours = float(
            data.get(
                "machine_hours",
''',
    '''        self.repository.set_work_warranty_details(
            work_id,
            is_warranty=data.get("is_warranty", False),
            warranty_claim_date=data.get("warranty_claim_date", ""),
            warranty_claim_response=data.get("warranty_claim_response", ""),
        )

        machine_hours = float(
            data.get(
                "machine_hours",
''',
    "main add work warranty",
)

# Edit work: load warranty fields.
s = replace_once(
    s,
    '''            maintenance_interval=(
                row["maintenance_interval"]
            ),
        )
''',
    '''            maintenance_interval=(
                row["maintenance_interval"]
            ),
            is_warranty=bool(
                row["is_warranty"]
                if "is_warranty" in row.keys()
                else 0
            ),
            warranty_claim_date=(
                row["warranty_claim_date"]
                if "warranty_claim_date" in row.keys()
                else ""
            ) or "",
            warranty_claim_response=(
                row["warranty_claim_response"]
                if "warranty_claim_response" in row.keys()
                else ""
            ) or "",
        )
''',
    "main edit work load warranty",
)

# After update_work, persist warranty. Anchor by second machine_hours block.
update_anchor = '''        machine_hours = float(
            data.get(
                "machine_hours",
                0,
            )
            or 0
        )

        if machine_hours > 0:
'''
first = s.find(update_anchor)
second = s.find(update_anchor, first + 1) if first >= 0 else -1
if second < 0:
    raise RuntimeError("Не найден второй блок machine_hours для edit_work")
s = s[:second] + '''        self.repository.set_work_warranty_details(
            work_id,
            is_warranty=data.get("is_warranty", False),
            warranty_claim_date=data.get("warranty_claim_date", ""),
            warranty_claim_response=data.get("warranty_claim_response", ""),
        )

''' + s[second:]

# When work hours update, preserve reset offset.
s = replace_once(
    s,
    '''            self.repository.update_equipment_hours(
                equipment_id,
                new_hours,
            )
''',
    '''            self.repository.update_equipment_total_hours(
                equipment_id,
                new_hours,
            )
''',
    "main total hours updater",
)

# Work manager receives warranty flag.
s = replace_once(
    s,
    '''                bool(row["report_completed"]),
            )
''',
    '''                bool(row["report_completed"]),
                bool(
                    row["is_warranty"]
                    if "is_warranty" in row.keys()
                    else 0
                ),
            )
''',
    "main work page warranty",
)

# Daily summary PDF semantic warranty color.
s = replace_once(
    s,
    '''            "Будущие работы",
        ]
        STATUS_HEX = {
''',
    '''            "Будущие работы",
            "Гарантийная работа",
        ]
        STATUS_HEX = {
''',
    "pdf warranty order",
)
s = replace_once(
    s,
    '''            "Будущие работы": "#EE9B35",
        }
''',
    '''            "Будущие работы": "#EE9B35",
            "Гарантийная работа": "#E24C9A",
        }
''',
    "pdf warranty hex",
)

p.write_text(s, encoding="utf-8")

print("ESTAR warranty/hour-meter features applied")
