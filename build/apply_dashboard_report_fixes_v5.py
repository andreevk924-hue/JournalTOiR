from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Не найден фрагмент для правки: {label}")
    return text.replace(old, new, 1)


def replace_between(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Не найдено начало блока: {label}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Не найден конец блока: {label}")
    return text[:start] + replacement + text[end:]


# ============================================================
# HOME PAGE: five unambiguous equipment KPIs
# ============================================================
p = Path("gui/pages/home_page.py")
s = p.read_text(encoding="utf-8")

old_stats = '''        self.total_equipment_card = StatCard("Всего техники", icon_kind="equipment", accent="blue")
        self.customer_work_card = StatCard("Работы заказчика", icon_kind="customer_wrench", accent="violet")
        self.active_work_card = StatCard("Активные ремонты / простои", icon_kind="repair_alt", accent="amber")
        self.components_card = StatCard("Компоненты на контроле", icon_kind="check_engine", accent="green")
        for col, card in enumerate(
            (
                self.total_equipment_card,
                self.customer_work_card,
                self.active_work_card,
                self.components_card,
            )
        ):
'''
new_stats = '''        # Пять однозначных показателей парка. "Действующее" означает
        # всё оборудование, кроме списанного; "В эксплуатации" — действующее,
        # которое на текущую дату не находится в ремонте/ТО/простое.
        self.active_equipment_card = StatCard(
            "Действующее оборудование", icon_kind="equipment", accent="blue"
        )
        self.operating_equipment_card = StatCard(
            "В эксплуатации", icon_kind="equipment", accent="green"
        )
        self.downtime_equipment_card = StatCard(
            "В простое", icon_kind="repair_alt", accent="amber"
        )
        self.decommissioned_equipment_card = StatCard(
            "Списано", icon_kind="equipment", accent="violet"
        )
        self.total_equipment_card = StatCard(
            "Всего оборудования", icon_kind="equipment", accent="blue"
        )
        self.customer_work_card = StatCard(
            "Работы заказчика", icon_kind="customer_wrench", accent="violet"
        )
        self.components_card = StatCard(
            "Компоненты на контроле", icon_kind="check_engine", accent="green"
        )

        primary_cards = (
            self.active_equipment_card,
            self.operating_equipment_card,
            self.downtime_equipment_card,
            self.decommissioned_equipment_card,
            self.total_equipment_card,
        )
        for col, card in enumerate(primary_cards):
            stats.addWidget(card, 0, col)
            stats.setColumnStretch(col, 1)

        # Сохраняем два прежних полезных KPI, но отделяем их от показателей
        # состояния парка, чтобы они не смешивались с расчётом КТГ.
        stats.addWidget(self.customer_work_card, 1, 0, 1, 2)
        stats.addWidget(self.components_card, 1, 2, 1, 3)

        # Старый цикл ниже нейтрализуется пустой последовательностью.
        for col, card in enumerate(
            ()
        ):
'''
s = replace_once(s, old_stats, new_stats, "home equipment KPI cards")

s = replace_once(
    s,
    '''    def set_statistics(self, total_equipment, customer_work, active_work, components):
        self.total_equipment_card.set_value(total_equipment)
        self.customer_work_card.set_value(customer_work)
        self.active_work_card.set_value(active_work)
        self.components_card.set_value(components)
''',
    '''    def set_statistics(
        self,
        active_equipment,
        operating_equipment,
        downtime_equipment,
        decommissioned_equipment,
        total_equipment,
        customer_work=0,
        components=0,
    ):
        self.active_equipment_card.set_value(active_equipment)
        self.operating_equipment_card.set_value(operating_equipment)
        self.downtime_equipment_card.set_value(downtime_equipment)
        self.decommissioned_equipment_card.set_value(decommissioned_equipment)
        self.total_equipment_card.set_value(total_equipment)
        self.customer_work_card.set_value(customer_work)
        self.components_card.set_value(components)
''',
    "home set_statistics",
)
p.write_text(s, encoding="utf-8")


# ============================================================
# SETTINGS: wheel-safe selectors + section titles above frames
# ============================================================
p = Path("gui/pages/settings_page.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    "from PySide6.QtCore import Qt\n",
    "from PySide6.QtCore import Qt, QEvent\n",
    "settings QEvent import",
)

s = replace_once(
    s,
    '''    def __init__(self):
        super().__init__()
        self.create_ui()
''',
    '''    def __init__(self):
        super().__init__()
        self.create_ui()
        self._disable_wheel_changes()
''',
    "settings wheel init",
)

s = replace_once(
    s,
    '''        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
''',
    '''        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        self.settings_scroll = scroll
''',
    "settings scroll reference",
)

helper = '''    @staticmethod
    def _settings_section(group):
        """Заголовок секции находится НАД рамкой, а не в её границе."""
        title_text = str(group.title() or "").strip()
        group.setTitle("")
        if group.layout() is not None:
            group.layout().setContentsMargins(12, 12, 12, 12)

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("settingsSectionTitle")
        title.setStyleSheet(
            "font-size:15px;font-weight:700;margin-left:2px;margin-bottom:1px;"
        )
        shell_layout.addWidget(title)
        shell_layout.addWidget(group)
        return shell

    def _disable_wheel_changes(self):
        # Колесо прокручивает страницу настроек, но не меняет значения
        # закрытых combo/spin-полей.
        for widget in self.findChildren(QComboBox):
            widget.installEventFilter(self)
        for widget in self.findChildren(QSpinBox):
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(obj, (QComboBox, QSpinBox))
        ):
            # Значение поля не меняем; то же колесо двигает страницу.
            if hasattr(self, "settings_scroll"):
                bar = self.settings_scroll.verticalScrollBar()
                delta = event.angleDelta().y()
                if delta:
                    bar.setValue(bar.value() - delta)
            event.accept()
            return True
        return super().eventFilter(obj, event)

'''
marker = "    def create_ui(self):\n"
if marker not in s:
    raise RuntimeError("Не найден create_ui в SettingsPage")
s = s.replace(marker, helper + marker, 1)

for method in (
    "create_organization_group",
    "create_user_group",
    "create_security_group",
    "create_storage_group",
    "create_sync_group",
    "create_backup_group",
    "create_email_group",
    "create_quick_actions_group",
    "create_ui_group",
):
    old = f"self.body_layout.addWidget(self.{method}())"
    new = f"self.body_layout.addWidget(self._settings_section(self.{method}()))"
    s = replace_once(s, old, new, f"settings section {method}")

p.write_text(s, encoding="utf-8")


# ============================================================
# WORK DIALOG: adaptive upper area + default downtime in-progress
# ============================================================
p = Path("dialogs/edit_work_dialog.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''    QGridLayout,
    QGroupBox,
)
''',
    '''    QGridLayout,
    QGroupBox,
    QScrollArea,
    QWidget,
)
''',
    "work dialog scroll imports",
)

s = replace_once(
    s,
    '''        top.addLayout(side, 2)
        root.addLayout(top)

        if self.work_id is not None and self.repository is not None:
''',
    '''        top.addLayout(side, 2)

        # Верхняя часть карточки может стать выше из-за гарантийного блока
        # или масштабирования Windows. Отдельный scroll гарантирует, что
        # элементы не перекрывают друг друга при неполноэкранном окне.
        top_container = QWidget()
        top_container.setLayout(top)
        self.top_scroll = QScrollArea()
        self.top_scroll.setWidgetResizable(True)
        self.top_scroll.setFrameShape(QFrame.NoFrame)
        self.top_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.top_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.top_scroll.setWidget(top_container)
        self.top_scroll.setMinimumHeight(250)
        root.addWidget(self.top_scroll, 2)

        if self.work_id is not None and self.repository is not None:
''',
    "work dialog adaptive top",
)

s = replace_once(
    s,
    '''            self.daily_table.setMinimumHeight(300)
            journal.addWidget(self.daily_table, 1)
            root.addWidget(journal_box, 1)
''',
    '''            self.daily_table.setMinimumHeight(180)
            self.daily_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.daily_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            journal.addWidget(self.daily_table, 1)
            journal_box.setMinimumHeight(230)
            root.addWidget(journal_box, 3)
''',
    "work dialog daily table sizing",
)

s = replace_once(
    s,
    '''        self.maintenance_interval.setVisible(
            is_maintenance
        )

    # ------------------------------------------------------------------
''',
    '''        self.maintenance_interval.setVisible(
            is_maintenance
        )

        # При создании именно простоя техника по смыслу сразу находится
        # в простое, поэтому флаг включается автоматически.
        if (
            self.work_id is None
            and str(repair_type or "").strip() == "Простой"
        ):
            self.in_progress.setChecked(True)

    # ------------------------------------------------------------------
''',
    "downtime in progress default",
)

p.write_text(s, encoding="utf-8")


# ============================================================
# REPORT SERVICE: waiting-without-executors = downtime + categories
# ============================================================
p = Path("services/report_service.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''                    machine_hours = self._number(self._value(daily, "machine_hours", 0))

                facts.append({
''',
    '''                    machine_hours = self._number(self._value(daily, "machine_hours", 0))

                # Унифицированное правило импорта/ручной хронологии:
                # ожидание без исполнителей является простым простоем.
                if (
                    not executors.strip()
                    and "ожид" in description.casefold()
                ):
                    state = "Простой"

                facts.append({
''',
    "waiting without executors is downtime",
)

new_ktg = '''    def get_ktg(self, date_from, date_to):
        """КТГ по машино-дням на основе фактического состояния каждого дня."""
        start, end = self._normalize_period(date_from, date_to)
        equipment = list(self.repository.get_all_equipment())

        active_equipment = [
            e for e in equipment
            if str(self._value(e, "status", "") or "").strip().casefold()
            != "списан"
        ]
        equipment_ids = {self._value(e, "id") for e in active_equipment}
        total_equipment = len(active_equipment)
        period_days = (end - start).days + 1
        total_machine_days = total_equipment * period_days

        facts = [
            f for f in self.get_daily_timeline(start, end)
            if f["equipment_id"] in equipment_ids
        ]

        unavailable_by_day = defaultdict(set)
        customer_by_day = defaultdict(set)
        state_sets_by_day = defaultdict(lambda: defaultdict(set))

        # Для разбивки простоя используем одно приоритетное состояние на
        # машину/день, чтобы сумма категорий совпадала с общим простоем.
        downtime_priority = {
            "Простой": 0,
            "Аварийный ремонт": 1,
            "Плановый ремонт": 2,
            "ТО": 3,
            "Модернизация": 4,
        }
        downtime_state_by_day = defaultdict(dict)

        for fact in facts:
            day = fact["date"]
            equipment_id = fact["equipment_id"]
            state = fact["state"]
            state_sets_by_day[day][state].add(equipment_id)

            if state in self.UNAVAILABLE_STATES:
                unavailable_by_day[day].add(equipment_id)
                current_state = downtime_state_by_day[day].get(equipment_id)
                if (
                    current_state is None
                    or downtime_priority.get(state, 999)
                    < downtime_priority.get(current_state, 999)
                ):
                    downtime_state_by_day[day][equipment_id] = state
            elif state == "Работы заказчика":
                customer_by_day[day].add(equipment_id)

        daily = []
        unavailable_machine_days = 0
        customer_machine_days = 0
        day = start
        while day <= end:
            unavailable = len(unavailable_by_day.get(day, set()))
            customer = len(customer_by_day.get(day, set()))
            available = max(0, total_equipment - unavailable)
            unavailable_machine_days += unavailable
            customer_machine_days += customer

            state_counts = {
                state: len(ids)
                for state, ids in state_sets_by_day.get(day, {}).items()
            }
            downtime_categories = dict(
                Counter(downtime_state_by_day.get(day, {}).values())
            )

            daily.append({
                "date": day,
                "available": available,
                "unavailable": unavailable,
                "customer_work": customer,
                "state_counts": state_counts,
                "downtime_categories": downtime_categories,
                "ktg_percent": round(
                    (available / total_equipment * 100), 2
                ) if total_equipment else 0.0,
            })
            day += timedelta(days=1)

        available_machine_days = max(
            0, total_machine_days - unavailable_machine_days
        )
        last_day = daily[-1] if daily else {}
        return {
            "date_from": start,
            "date_to": end,
            "total_equipment": total_equipment,
            "available_equipment": last_day.get(
                "available", total_equipment
            ),
            "unavailable_equipment": last_day.get("unavailable", 0),
            "customer_work_equipment": last_day.get("customer_work", 0),
            "state_counts": last_day.get("state_counts", {}),
            "downtime_categories": last_day.get(
                "downtime_categories", {}
            ),
            "period_days": period_days,
            "total_machine_days": total_machine_days,
            "unavailable_machine_days": unavailable_machine_days,
            "available_machine_days": available_machine_days,
            "customer_machine_days": customer_machine_days,
            "ktg_percent": round(
                (available_machine_days / total_machine_days * 100), 2
            ) if total_machine_days else 0.0,
            "daily": daily,
        }

'''
s = replace_between(
    s,
    "    def get_ktg(self, date_from, date_to):\n",
    "    def get_downtime_report(self, date_from, date_to):\n",
    new_ktg,
    "report service get_ktg",
)
p.write_text(s, encoding="utf-8")


# ============================================================
# SCHEDULE: inventory KPIs + categorized downtime
# ============================================================
p = Path("gui/pages/schedule_page.py")
s = p.read_text(encoding="utf-8")

summary_block = '''        # ------------------------------------------------------
        # EQUIPMENT / KTG SUMMARY
        # ------------------------------------------------------
        summary_frame = QFrame()
        summary_frame.setObjectName("scheduleLegend")
        summary_layout = QGridLayout(summary_frame)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setHorizontalSpacing(8)
        summary_layout.setVerticalSpacing(6)

        self.summary_values = {}
        main_metrics = (
            ("active", "Действующее оборудование"),
            ("operating", "В эксплуатации"),
            ("downtime", "В простое"),
            ("decommissioned", "Списано"),
            ("total", "Всего оборудования"),
            ("ktg", "КТГ"),
        )
        for column, (key, title_text) in enumerate(main_metrics):
            cell = QFrame()
            cell.setObjectName("scheduleMetric")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(8, 4, 8, 4)
            cell_layout.setSpacing(1)
            caption = QLabel(title_text)
            caption.setObjectName("muted")
            caption.setWordWrap(True)
            value = QLabel("0")
            value.setStyleSheet("font-size:17px;font-weight:700;")
            cell_layout.addWidget(caption)
            cell_layout.addWidget(value)
            summary_layout.addWidget(cell, 0, column)
            summary_layout.setColumnStretch(column, 1)
            self.summary_values[key] = value

        self.category_values = {}
        categories = (
            ("Аварийный ремонт", "Аварийный ремонт"),
            ("Плановый ремонт", "Плановый ремонт"),
            ("ТО", "ТО"),
            ("Модернизация", "Модернизация"),
            ("Простой", "Простой"),
            ("Работы заказчика", "Работы заказчика"),
            ("Мониторинг состояния", "Мониторинг"),
        )
        for column, (key, title_text) in enumerate(categories):
            caption = QLabel(title_text + ":")
            caption.setObjectName("muted")
            caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value = QLabel("0")
            value.setStyleSheet("font-weight:700;")
            pair = QWidget()
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(3, 0, 3, 0)
            pair_layout.setSpacing(5)
            pair_layout.addWidget(caption, 1)
            pair_layout.addWidget(value, 0)
            summary_layout.addWidget(pair, 1, column)
            self.category_values[key] = value

        layout.addWidget(summary_frame)

'''
anchor = '''        layout.addWidget(
            legend_frame
        )

        # ------------------------------------------------------
        # PERIOD CONTROLS
'''
replacement = '''        layout.addWidget(
            legend_frame
        )

''' + summary_block + '''        # ------------------------------------------------------
        # PERIOD CONTROLS
'''
s = replace_once(s, anchor, replacement, "schedule summary UI")

summary_method = '''    def set_equipment_statistics(
        self,
        *,
        active_equipment=0,
        operating_equipment=0,
        downtime_equipment=0,
        decommissioned_equipment=0,
        total_equipment=0,
        ktg_percent=0.0,
        categories=None,
    ):
        values = {
            "active": active_equipment,
            "operating": operating_equipment,
            "downtime": downtime_equipment,
            "decommissioned": decommissioned_equipment,
            "total": total_equipment,
            "ktg": f"{float(ktg_percent or 0):.1f}%",
        }
        for key, value in values.items():
            label = self.summary_values.get(key)
            if label is not None:
                label.setText(str(value))

        categories = dict(categories or {})
        for key, label in self.category_values.items():
            label.setText(str(int(categories.get(key, 0) or 0)))

'''
period_marker = "    # ==========================================================\n    # PERIOD\n"
if period_marker not in s:
    raise RuntimeError("Не найден PERIOD marker в SchedulePage")
s = s.replace(period_marker, summary_method + period_marker, 1)

old_effective = '''                    effective_type = (daily["day_type"] if daily is not None else repair_type) or repair_type
                    effective_description = (daily["description"] if daily is not None else "") or (work["description"] or "")
                    effective_executors = (daily["executors"] if daily is not None else "") or (work["executors"] or "")
'''
new_effective = '''                    if daily is not None:
                        # Пустые дневные поля — это осознанные значения и
                        # не должны подменяться шапкой карточки.
                        effective_type = (daily["day_type"] or repair_type)
                        effective_description = str(
                            daily["description"] or ""
                        )
                        effective_executors = str(
                            daily["executors"] or ""
                        )
                    else:
                        effective_type = repair_type
                        effective_description = str(
                            work["description"] or ""
                        )
                        effective_executors = str(
                            work["executors"] or ""
                        )

                    if (
                        not effective_executors.strip()
                        and "ожид" in effective_description.casefold()
                    ):
                        effective_type = "Простой"
'''
s = replace_once(
    s, old_effective, new_effective, "schedule effective daily values"
)

old_status = '''                    if is_warranty_work:
                        cell_status = "Гарантийная работа"
                    elif daily is not None:
                        cell_status = self.normalize_status(effective_type)
                    elif is_future_work:
                        cell_status = "Будущие работы"
                    elif is_maintenance:
                        cell_status = "ТО"
                    else:
                        cell_status = self.normalize_status(repair_type)
'''
new_status = '''                    effective_status = self.normalize_status(
                        effective_type
                    )
                    # Серый простой важнее гарантийной подсветки: если
                    # конкретный день является простоем, он должен выглядеть
                    # и считаться как простой.
                    if effective_status == "Простой":
                        cell_status = "Простой"
                    elif is_warranty_work:
                        cell_status = "Гарантийная работа"
                    elif daily is not None:
                        cell_status = effective_status
                    elif is_future_work:
                        cell_status = "Будущие работы"
                    elif is_maintenance:
                        cell_status = "ТО"
                    else:
                        cell_status = self.normalize_status(repair_type)

                    if cell_status == "Простой":
                        effective_executors = ""
'''
s = replace_once(s, old_status, new_status, "schedule downtime priority")

p.write_text(s, encoding="utf-8")


# ============================================================
# MAIN WINDOW: inventory counts, schedule KPIs, PDF grouping
# ============================================================
p = Path("gui/main_window.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''        if name == "КТГ":
            data = service.get_ktg(date_from, date_to)
            summary = [
                ("КТГ", f"{data['ktg_percent']:.2f}%"),
                ("Единиц техники", data["total_equipment"]),
                ("Машино-дней в периоде", data["total_machine_days"]),
                ("Машино-дней простоя", data["unavailable_machine_days"]),
            ]
            headers = ["Дата", "Доступно", "Недоступно", "КТГ, %"]
            rows = [
                [item["date"].strftime("%d.%m.%Y"), item["available"], item["unavailable"], f"{item['ktg_percent']:.2f}"]
                for item in data["daily"]
            ]
''',
    '''        if name == "КТГ":
            data = service.get_ktg(date_from, date_to)
            all_equipment_rows = list(
                self.repository.get_all_equipment()
            )
            decommissioned = sum(
                1 for row in all_equipment_rows
                if str(self._report_value(row, "status", "") or "")
                .strip().casefold() == "списан"
            )
            summary = [
                ("КТГ", f"{data['ktg_percent']:.2f}%"),
                ("Действующее оборудование", data["total_equipment"]),
                (
                    "В эксплуатации на конец периода",
                    data["available_equipment"],
                ),
                (
                    "В простое на конец периода",
                    data["unavailable_equipment"],
                ),
                ("Списано", decommissioned),
                ("Всего оборудования", len(all_equipment_rows)),
                ("Машино-дней в периоде", data["total_machine_days"]),
                ("Машино-дней простоя", data["unavailable_machine_days"]),
            ]
            headers = [
                "Дата",
                "В эксплуатации",
                "В простое",
                "КТГ, %",
            ]
            rows = [
                [
                    item["date"].strftime("%d.%m.%Y"),
                    item["available"],
                    item["unavailable"],
                    f"{item['ktg_percent']:.2f}",
                ]
                for item in data["daily"]
            ]
''',
    "KTG report equipment labels",
)

refresh_home_start = '''    def refresh_home(self):
'''
refresh_home_marker = '''        # Возвращаем на Главную текущие ремонты и простои отдельным блоком.
'''
new_refresh_home_head = '''    def refresh_home(self):
        equipment_rows = list(self.repository.get_all_equipment())
        total_equipment = len(equipment_rows)
        decommissioned_equipment = sum(
            1 for row in equipment_rows
            if str(row["status"] or "").strip().casefold() == "списан"
        )
        active_equipment = max(
            0, total_equipment - decommissioned_equipment
        )

        today_text = datetime.now().date().isoformat()
        try:
            day_ktg = self.report_service.get_ktg(
                today_text, today_text
            )
        except Exception:
            day_ktg = {}

        downtime_equipment = int(
            day_ktg.get("unavailable_equipment", 0) or 0
        )
        operating_equipment = max(
            0, active_equipment - downtime_equipment
        )

        try:
            base_statistics = self.repository.get_dashboard_statistics()
        except Exception:
            base_statistics = {}
        try:
            customer_work = self.repository.get_customer_work_count()
        except Exception:
            customer_work = 0

        self.home_page.set_statistics(
            active_equipment,
            operating_equipment,
            downtime_equipment,
            decommissioned_equipment,
            total_equipment,
            customer_work,
            int(base_statistics.get("components", 0) or 0),
        )

'''
start = s.find(refresh_home_start)
marker_pos = s.find(refresh_home_marker, start)
if start < 0 or marker_pos < 0:
    raise RuntimeError("Не найден заголовок refresh_home")
s = s[:start] + new_refresh_home_head + s[marker_pos:]

new_refresh_schedule = '''    def refresh_schedule(self):
        date_from, date_to = self.schedule_page.get_period()

        all_equipment = list(
            self.repository.get_all_equipment()
        )
        active_equipment = [
            row for row in all_equipment
            if str(row["status"] or "").strip().casefold() != "списан"
        ]

        work = self.repository.get_work_for_period(
            date_from=date_from,
            date_to=date_to,
        )
        daily = self.repository.get_work_daily_for_period(
            date_from, date_to
        )

        # В графике отображается только действующий парк.
        self.schedule_page.build_schedule(
            equipment_rows=active_equipment,
            work_rows=work,
            daily_rows=daily,
        )

        today_text = datetime.now().date().isoformat()
        try:
            day_ktg = self.report_service.get_ktg(
                today_text, today_text
            )
        except Exception:
            day_ktg = {}

        downtime_categories = dict(
            day_ktg.get("downtime_categories", {}) or {}
        )
        state_counts = dict(
            day_ktg.get("state_counts", {}) or {}
        )
        categories = {
            "Аварийный ремонт": downtime_categories.get(
                "Аварийный ремонт", 0
            ),
            "Плановый ремонт": downtime_categories.get(
                "Плановый ремонт", 0
            ),
            "ТО": downtime_categories.get("ТО", 0),
            "Модернизация": downtime_categories.get(
                "Модернизация", 0
            ),
            "Простой": downtime_categories.get("Простой", 0),
            "Работы заказчика": state_counts.get(
                "Работы заказчика", 0
            ),
            "Мониторинг состояния": state_counts.get(
                "Мониторинг состояния", 0
            ),
        }

        active_count = len(active_equipment)
        downtime_count = int(
            day_ktg.get("unavailable_equipment", 0) or 0
        )
        self.schedule_page.set_equipment_statistics(
            active_equipment=active_count,
            operating_equipment=max(
                0, active_count - downtime_count
            ),
            downtime_equipment=downtime_count,
            decommissioned_equipment=(
                len(all_equipment) - active_count
            ),
            total_equipment=len(all_equipment),
            ktg_percent=float(
                day_ktg.get("ktg_percent", 0.0) or 0.0
            ),
            categories=categories,
        )

'''
s = replace_between(
    s,
    "    def refresh_schedule(self):\n",
    "    def _create_daily_work_summary_pdf",
    new_refresh_schedule,
    "main refresh_schedule",
)

old_kpi_calc_start = '''        # Показатели для верхних карточек ежедневной сводки.
'''
old_kpi_calc_end = '''        default_name = f"Ежедневная сводная по работам ({report_date}).pdf"
'''
kpi_start = s.find(old_kpi_calc_start)
kpi_end = s.find(old_kpi_calc_end, kpi_start)
if kpi_start < 0 or kpi_end < 0:
    raise RuntimeError("Не найден расчёт KPI ежедневной сводки")
new_kpi_calc = '''        # Парк в ежедневной сводке показываем без двусмысленного
        # «Всего техники»: отдельно действующее, эксплуатация, простой,
        # списанное и полный реестр.
        try:
            equipment_kpi_rows = list(
                self.repository.get_all_equipment()
            )
        except Exception:
            equipment_kpi_rows = []

        total_equipment_kpi = len(equipment_kpi_rows)
        decommissioned_equipment_kpi = sum(
            1 for row in equipment_kpi_rows
            if str(source_value(row, "status", "") or "").strip().casefold()
            == "списан"
        )
        active_equipment_kpi = max(
            0, total_equipment_kpi - decommissioned_equipment_kpi
        )

        try:
            day_ktg = self.report_service.get_ktg(
                report_day.isoformat(), report_day.isoformat()
            )
        except Exception:
            day_ktg = {}

        downtime_equipment_kpi = int(
            day_ktg.get("unavailable_equipment", 0) or 0
        )
        operating_equipment_kpi = max(
            0, active_equipment_kpi - downtime_equipment_kpi
        )
        ktg_percent_kpi = float(
            day_ktg.get("ktg_percent", 0.0) or 0.0
        )

'''
s = s[:kpi_start] + new_kpi_calc + s[kpi_end:]

old_kpi_block = '''            # ------------------------- KPI -------------------------
            # Четыре компактных показателя, как на главной странице программы.
            # Значения относятся к фактической дате формирования отчёта.
            kpi_h = 64.0
            kpi_gap = 10.0
            kpi_w = (CONTENT_W - kpi_gap * 3) / 4.0
            kpi_items = [
                ("Всего техники", str(total_equipment_kpi), C_BLUE),
                ("Работы заказчика", str(customer_work_kpi), C_VIOLET),
                ("Активные ремонты / простои", str(active_repairs_kpi), C_AMBER),
                (f"КТГ за {report_date}", f"{ktg_percent_kpi:.1f}%", C_GREEN),
            ]
'''
new_kpi_block = '''            # ------------------------- KPI -------------------------
            # Шесть однозначных показателей парка на дату отчёта.
            kpi_h = 64.0
            kpi_gap = 8.0
            kpi_w = (CONTENT_W - kpi_gap * 5) / 6.0
            kpi_items = [
                ("Действующее оборудование", str(active_equipment_kpi), C_BLUE),
                ("В эксплуатации", str(operating_equipment_kpi), C_GREEN),
                ("В простое", str(downtime_equipment_kpi), C_AMBER),
                ("Списано", str(decommissioned_equipment_kpi), C_VIOLET),
                ("Всего оборудования", str(total_equipment_kpi), C_BLUE),
                (f"КТГ за {report_date}", f"{ktg_percent_kpi:.1f}%", C_GREEN),
            ]
'''
s = replace_once(s, old_kpi_block, new_kpi_block, "daily PDF KPI block")

# Update the stepping expression for six KPI cards automatically via kpi_w/kpi_gap;
# loop itself already uses len(kpi_items), so no other change is required.

details_start = "            # ------------------------- DETAILS -------------------------\n"
details_end = "            draw_footer()\n"
new_details = '''            # ------------------------- DETAILS -------------------------
            if works:
                ensure(42, "РАБОТЫ / ПРОСТОИ / ПЛАНЫ")
                draw_section_title(
                    "РАБОТЫ / ПРОСТОИ / ПЛАНЫ",
                    "Детализация за полный период каждой карточки",
                )

            def work_period(work):
                try:
                    work_start = date.fromisoformat(
                        str(row_value(work, "date_start"))[:10]
                    )
                except Exception:
                    return None, None

                raw_end = row_value(work, "date_end")
                if raw_end:
                    try:
                        work_end = date.fromisoformat(str(raw_end)[:10])
                    except Exception:
                        work_end = work_start
                elif bool(row_value(work, "in_progress", False)):
                    # В детализации показываем всю карточку до текущего дня,
                    # а не обрезаем её выбранным периодом графика.
                    work_end = date.today()
                else:
                    work_end = work_start
                return work_start, max(work_start, work_end)

            def full_daily_rows(work):
                try:
                    return list(
                        self.repository.get_work_daily_log(
                            row_value(work, "id")
                        )
                    )
                except Exception:
                    return []

            def collapsed_daily_rows(work, state):
                rows = full_daily_rows(work)
                rows.sort(
                    key=lambda row: str(row_value(row, "work_date"))
                )
                result = []

                for raw in rows:
                    raw_date = str(
                        row_value(raw, "work_date")
                    )[:10]
                    try:
                        day_date = date.fromisoformat(raw_date)
                    except Exception:
                        continue

                    day_state = normalized_status(
                        row_value(raw, "day_type")
                    )
                    if day_state not in STATUS_HEX:
                        day_state = str(
                            row_value(raw, "day_type") or state
                        )

                    description = str(
                        row_value(raw, "description") or ""
                    ).strip()
                    executors = str(
                        row_value(raw, "executors") or ""
                    ).strip()

                    if (
                        not executors
                        and "ожид" in description.casefold()
                    ):
                        day_state = "Простой"

                    # В сером простое исполнителей не показываем даже если
                    # они ошибочно попали в импортированную дневную строку.
                    if day_state == "Простой":
                        executors = ""

                    try:
                        hours_value = float(
                            row_value(raw, "machine_hours", 0) or 0
                        )
                    except Exception:
                        hours_value = 0.0

                    current = {
                        "date_start": day_date,
                        "date_end": day_date,
                        "state": day_state,
                        "description": description,
                        "executors": executors,
                        "hours": hours_value,
                    }

                    # Схлопываем ТОЛЬКО простой и работы заказчика,
                    # только если описание одинаковое и дни идут подряд.
                    can_collapse = day_state in (
                        "Простой",
                        "Работы заказчика",
                    )
                    if result and can_collapse:
                        previous = result[-1]
                        contiguous = (
                            day_date
                            == previous["date_end"] + timedelta(days=1)
                        )
                        same_content = (
                            previous["state"] == day_state
                            and previous["description"] == description
                        )
                        if contiguous and same_content:
                            previous["date_end"] = day_date
                            previous["hours"] = max(
                                previous["hours"], hours_value
                            )
                            if day_state == "Работы заказчика":
                                existing = [
                                    item.strip()
                                    for item in previous["executors"].split(",")
                                    if item.strip()
                                ]
                                for name in [
                                    item.strip()
                                    for item in executors.replace(
                                        ";", ","
                                    ).split(",")
                                    if item.strip()
                                ]:
                                    if name not in existing:
                                        existing.append(name)
                                previous["executors"] = ", ".join(existing)
                            continue

                    result.append(current)

                return result

            for work in works:
                work_start, work_end = work_period(work)
                if work_start is None:
                    continue

                state = normalized_status(row_value(work, "repair_type"))
                if row_value(work, "id") in future_work_ids:
                    state = "Будущие работы"
                elif state not in STATUS_HEX:
                    state = str(
                        row_value(work, "repair_type") or "Работа"
                    )
                accent = (
                    status_color(state)
                    if state in STATUS_HEX
                    else C_BLUE
                )

                detail_rows = collapsed_daily_rows(work, state)

                model_text = (
                    f"{row_value(work, 'model')} "
                    f"№{row_value(work, 'garage_number')}"
                )
                period_text = (
                    work_start.strftime("%d.%m.%Y")
                    if work_end == work_start
                    else (
                        f"{work_start.strftime('%d.%m.%Y')} — "
                        f"{work_end.strftime('%d.%m.%Y')}"
                    )
                )

                card_header_h = 50.0
                table_header_h = 27.0
                inner_x = LEFT
                inner_w = CONTENT_W
                col_widths = [
                    118.0,
                    154.0,
                    inner_w - 118.0 - 154.0 - 184.0 - 98.0,
                    184.0,
                    98.0,
                ]
                titles = [
                    "Дата / период",
                    "Состояние",
                    "Работы / причина простоя",
                    "Исполнители",
                    "Наработка",
                ]

                row_heights = []
                for detail in detail_rows:
                    description = str(detail["description"] or "")
                    executors = str(detail["executors"] or "")
                    row_height = max(
                        29.0,
                        text_height(
                            description, col_widths[2] - 12, 7.5
                        ) + 8,
                        text_height(
                            executors, col_widths[3] - 12, 7.5
                        ) + 8,
                    )
                    row_heights.append(min(58.0, row_height))
                if not detail_rows:
                    row_heights = [31.0]

                total_h = (
                    card_header_h
                    + table_header_h
                    + sum(row_heights)
                    + 12
                )
                if y + min(total_h, 220) > BOTTOM:
                    new_page(False)
                    draw_section_title(
                        "РАБОТЫ / ПРОСТОИ / ПЛАНЫ — ПРОДОЛЖЕНИЕ"
                    )

                header_rect = QRectF(
                    LEFT, y, CONTENT_W, card_header_h
                )
                rounded(header_rect, 6, C_WHITE, C_LINE)
                fill_rect(
                    QRectF(LEFT, y, 5, card_header_h), accent
                )
                draw_text(
                    QRectF(
                        LEFT + 16,
                        y + 4,
                        CONTENT_W - 330,
                        21,
                    ),
                    model_text,
                    12,
                    True,
                    C_NAVY,
                )
                draw_text(
                    QRectF(
                        LEFT + 16,
                        y + 26,
                        CONTENT_W - 330,
                        16,
                    ),
                    row_value(work, "description") or "Без описания",
                    7.8,
                    False,
                    C_MUTED,
                )
                draw_text(
                    QRectF(RIGHT - 280, y + 5, 265, 18),
                    state,
                    8.3,
                    True,
                    accent,
                    Qt.AlignRight | Qt.AlignVCenter,
                )
                draw_text(
                    QRectF(RIGHT - 280, y + 26, 265, 15),
                    period_text,
                    7.0,
                    False,
                    C_MUTED,
                    Qt.AlignRight | Qt.AlignVCenter,
                )
                y += card_header_h

                def detail_header():
                    nonlocal y
                    x = inner_x
                    for title, width in zip(titles, col_widths):
                        rect = QRectF(
                            x, y, width, table_header_h
                        )
                        fill_rect(rect, C_LIGHT)
                        stroke_rect(rect)
                        draw_text(
                            rect.adjusted(5, 0, -5, 0),
                            title,
                            7.5,
                            True,
                            C_NAVY,
                        )
                        x += width
                    y += table_header_h

                detail_header()

                if not detail_rows:
                    row_height = row_heights[0]
                    rect = QRectF(
                        inner_x, y, inner_w, row_height
                    )
                    fill_rect(rect, C_WHITE)
                    stroke_rect(rect)
                    draw_text(
                        rect,
                        "Нет дневной детализации",
                        8,
                        False,
                        C_MUTED,
                        Qt.AlignCenter,
                    )
                    y += row_height
                else:
                    for detail, row_height in zip(
                        detail_rows, row_heights
                    ):
                        if y + row_height + 15 > BOTTOM:
                            new_page(False)
                            draw_section_title(
                                f"{model_text} — ПРОДОЛЖЕНИЕ"
                            )
                            detail_header()

                        start_text = detail[
                            "date_start"
                        ].strftime("%d.%m.%Y")
                        end_text = detail[
                            "date_end"
                        ].strftime("%d.%m.%Y")
                        date_text = (
                            start_text
                            if start_text == end_text
                            else f"{start_text} — {end_text}"
                        )

                        day_state = detail["state"]

                        hours_value = float(
                            detail["hours"] or 0
                        )
                        hours = (
                            "—"
                            if hours_value <= 0
                            else f"{hours_value:g} м/ч"
                        )

                        executors = (
                            ""
                            if day_state == "Простой"
                            else (detail["executors"] or "—")
                        )

                        values = [
                            date_text,
                            day_state,
                            detail["description"] or "—",
                            executors,
                            hours,
                        ]

                        x = inner_x
                        for column_index, (
                            value_text,
                            width,
                        ) in enumerate(zip(values, col_widths)):
                            rect = QRectF(
                                x, y, width, row_height
                            )
                            is_state_cell = (
                                column_index == 1
                                and day_state in STATUS_HEX
                            )
                            fill_rect(
                                rect,
                                status_color(day_state)
                                if is_state_cell
                                else C_WHITE,
                            )
                            stroke_rect(rect)
                            color = (
                                status_text_color(day_state)
                                if is_state_cell
                                else C_TEXT
                            )
                            align = (
                                Qt.AlignRight | Qt.AlignVCenter
                                if column_index == 4
                                else Qt.AlignLeft | Qt.AlignVCenter
                            )
                            draw_text(
                                rect.adjusted(5, 2, -5, -2),
                                value_text,
                                7.6,
                                column_index in (0, 1),
                                color,
                                align,
                                column_index in (2, 3),
                            )
                            x += width
                        y += row_height
                y += 11

'''
s = replace_between(
    s,
    details_start,
    details_end,
    new_details,
    "daily PDF details",
)

p.write_text(s, encoding="utf-8")

print("Dashboard/report/settings adaptive fixes v5 applied")
