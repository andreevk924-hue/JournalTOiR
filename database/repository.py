# database/repository.py
# Часть 1/3

from datetime import datetime

from database.customer_manager import CustomerManager
from database.database import Database
from database.migrations import migrate


class Repository:
    def __init__(
        self,
        customer_name=None,
    ):
        self.customer_manager = CustomerManager()

        if customer_name:
            self.customer_name = (
                self.customer_manager
                .set_active_customer(
                    customer_name
                )
            )
        else:
            self.customer_name = (
                self.customer_manager
                .get_active_customer()
            )

        if not self.customer_name:
            raise RuntimeError(
                "Активный заказчик не выбран."
            )

        migrate(
            customer_name=self.customer_name
        )

        self.db = Database(
            customer_name=self.customer_name
        )

        self.connection = (
            self.db.connection
        )

    def close(self):
        if self.db:
            self.db.close()

    def _now(self):
        return datetime.now().isoformat(
            sep=" ",
            timespec="seconds",
        )

    def _fetchone(
        self,
        sql,
        params=(),
    ):
        cursor = self.connection.execute(
            sql,
            params,
        )

        return cursor.fetchone()

    def _fetchall(
        self,
        sql,
        params=(),
    ):
        cursor = self.connection.execute(
            sql,
            params,
        )

        return cursor.fetchall()

    def _execute(
        self,
        sql,
        params=(),
    ):
        cursor = self.connection.execute(
            sql,
            params,
        )

        self.connection.commit()
        try:
            command = str(sql or "").lstrip().split(None, 1)[0].upper()
            if command in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}:
                from services.app_settings import AppSettingsManager
                app_cfg = AppSettingsManager().load()
                AppSettingsManager().mark_dirty()
                if command in {"INSERT", "UPDATE", "DELETE", "REPLACE"} and "audit_log" not in str(sql).lower():
                    import re
                    match = re.search(r"(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\s+([A-Za-z_][A-Za-z0-9_]*)", str(sql), re.I)
                    entity = match.group(1) if match else ""
                    self.connection.execute(
                        "INSERT INTO audit_log(created_at,user_name,action,entity,details) VALUES(?,?,?,?,?)",
                        (self._now(), app_cfg.get("user", {}).get("full_name", ""), command, entity, "Изменение через интерфейс JournalTOiR"),
                    )
                    self.connection.commit()
        except Exception:
            pass

        return cursor

    # ==========================================================
    # CUSTOMER
    # ==========================================================

    def get_customer_name(self):
        return self.customer_name

    def get_database_path(self):
        return self.db.path

    # ==========================================================
    # MANUFACTURERS / DISTRIBUTORS
    # ==========================================================

    def get_manufacturers(self):
        return self._fetchall("SELECT * FROM manufacturers ORDER BY name COLLATE NOCASE")

    def add_manufacturer(self, name, country="", logo_path=""):
        name = str(name or "").strip()
        if not name:
            raise ValueError("Не указано наименование производителя.")
        return self._execute(
            "INSERT INTO manufacturers(name,country,logo_path,created_at,updated_at) VALUES(?,?,?,?,?)",
            (name, str(country or "").strip(), str(logo_path or "").strip(), self._now(), self._now()),
        ).lastrowid

    def update_manufacturer(self, item_id, name, country="", logo_path=""):
        self._execute(
            "UPDATE manufacturers SET name=?,country=?,logo_path=?,updated_at=? WHERE id=?",
            (str(name or "").strip(), str(country or "").strip(), str(logo_path or "").strip(), self._now(), item_id),
        )

    def delete_manufacturer(self, item_id):
        used = self._fetchone("SELECT COUNT(*) AS n FROM equipment WHERE manufacturer_id=?", (item_id,))
        if used and used["n"]:
            raise ValueError("Производитель используется в карточках техники.")
        self._execute("DELETE FROM manufacturers WHERE id=?", (item_id,))

    def get_distributors(self):
        return self._fetchall("SELECT * FROM distributors ORDER BY name COLLATE NOCASE")

    def add_distributor(self, name):
        name = str(name or "").strip()
        if not name:
            raise ValueError("Не указано наименование организации.")
        return self._execute(
            "INSERT INTO distributors(name,created_at,updated_at) VALUES(?,?,?)",
            (name, self._now(), self._now()),
        ).lastrowid

    def update_distributor(self, item_id, name):
        self._execute(
            "UPDATE distributors SET name=?,updated_at=? WHERE id=?",
            (str(name or "").strip(), self._now(), item_id),
        )

    def delete_distributor(self, item_id):
        used = self._fetchone("SELECT COUNT(*) AS n FROM equipment WHERE distributor_id=?", (item_id,))
        if used and used["n"]:
            raise ValueError("Дистрибьютор используется в карточках техники.")
        self._execute("DELETE FROM distributors WHERE id=?", (item_id,))

    # ==========================================================
    # EQUIPMENT STATUS
    #
    # Разрешенные состояния:
    #
    # В работе
    # В простое
    # Списан
    #
    # "В простое" устанавливается автоматически,
    # если у машины есть хотя бы одна активная работа.
    #
    # "Списан" имеет приоритет и автоматически
    # не изменяется.
    # ==========================================================

    def _has_active_work(
        self,
        equipment_id,
    ):
        row = self._fetchone(
            """
            SELECT 1
            FROM work_records
            WHERE
                equipment_id = ?
                AND in_progress = 1
                AND (
                    COALESCE(is_planned, 0) = 0
                    OR COALESCE(is_started, 0) = 1
                )
            LIMIT 1
            """,
            (equipment_id,),
        )

        return row is not None

    def sync_equipment_status(
        self,
        equipment_id,
    ):
        equipment = self._fetchone(
            """
            SELECT
                id,
                status
            FROM equipment
            WHERE id = ?
            """,
            (equipment_id,),
        )

        if equipment is None:
            return

        current_status = (
            equipment["status"]
            or "В работе"
        )

        if current_status == "Списан":
            return

        if self._has_active_work(
            equipment_id
        ):
            new_status = "В простое"
        else:
            new_status = "В работе"

        if new_status != current_status:
            self._execute(
                """
                UPDATE equipment
                SET
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    self._now(),
                    equipment_id,
                ),
            )

    def sync_all_equipment_statuses(self):
        rows = self._fetchall(
            """
            SELECT id
            FROM equipment
            """
        )

        for row in rows:
            self.sync_equipment_status(
                row["id"]
            )

    # ==========================================================
    # EQUIPMENT
    # ==========================================================

    def add_equipment(
        self,
        model,
        serial_number,
        garage_number,
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
        model = str(
            model or ""
        ).strip()

        serial_number = str(
            serial_number or ""
        ).strip()

        garage_number = str(
            garage_number or ""
        ).strip()

        if not model:
            raise ValueError(
                "Модель не указана."
            )

        if not serial_number:
            raise ValueError(
                "Серийный номер не указан."
            )

        if not garage_number:
            raise ValueError(
                "Гаражный номер не указан."
            )

        if status not in (
            "В работе",
            "Списан",
        ):
            status = "В работе"

        try:
            shift_hours_per_day = float(
                shift_hours_per_day
                or 22
            )
        except (
            TypeError,
            ValueError,
        ):
            shift_hours_per_day = 22.0

        if shift_hours_per_day <= 0:
            shift_hours_per_day = 22.0

        auto_maintenance = int(
            bool(
                auto_maintenance
            )
        )

        now = self._now()

        cursor = self._execute(
            """
            INSERT INTO equipment (
                model,
                serial_number,
                garage_number,
                registration_number,
                manufacture_year,
                current_hours,
                status,
                note,
                shift_hours_per_day,
                auto_maintenance,
                commissioning_date,
                warranty_years,
                warranty_hours,
                warranty_start_hours,
                photo_path,
                manufacturer_id,
                distributor_id,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                model,
                serial_number,
                garage_number,
                str(
                    registration_number
                    or ""
                ).strip(),
                manufacture_year,
                float(
                    current_hours or 0
                ),
                status,
                str(
                    note or ""
                ).strip(),
                shift_hours_per_day,
                auto_maintenance,
                str(commissioning_date or "").strip(),
                float(warranty_years or 0),
                float(warranty_hours or 0),
                float(warranty_start_hours or 0),
                str(photo_path or "").strip(),
                manufacturer_id,
                distributor_id,
                now,
                now,
            ),
        )

        equipment_id = (
            cursor.lastrowid
        )

        # Новая машина получает стандартные интервалы ТО.
        # Это НЕ создает сами работы ТО.
        default_intervals = (
            (50, "ТО-50", 10),
            (250, "ТО-250", 20),
            (500, "ТО-500", 30),
            (1000, "ТО-1000", 40),
            (2000, "ТО-2000", 50),
            (4000, "ТО-4000", 60),
        )

        for (
            interval_hours,
            interval_name,
            sort_order,
        ) in default_intervals:

            self._execute(
                """
                INSERT OR IGNORE INTO
                maintenance_intervals (
                    equipment_id,
                    interval_hours,
                    name,
                    active,
                    sort_order,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, 1, ?, ?, ?
                )
                """,
                (
                    equipment_id,
                    interval_hours,
                    interval_name,
                    sort_order,
                    now,
                    now,
                ),
            )

        return equipment_id

    def update_equipment(
        self,
        equipment_id,
        model,
        serial_number,
        garage_number,
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
        current = self.get_equipment(
            equipment_id
        )

        if current is None:
            raise ValueError(
                "Техника не найдена."
            )

        model = str(
            model or ""
        ).strip()

        serial_number = str(
            serial_number or ""
        ).strip()

        garage_number = str(
            garage_number or ""
        ).strip()

        if not model:
            raise ValueError(
                "Модель не указана."
            )

        if not serial_number:
            raise ValueError(
                "Серийный номер не указан."
            )

        if not garage_number:
            raise ValueError(
                "Гаражный номер не указан."
            )

        try:
            shift_hours_per_day = float(
                shift_hours_per_day
                or 22
            )
        except (
            TypeError,
            ValueError,
        ):
            shift_hours_per_day = 22.0

        if shift_hours_per_day <= 0:
            shift_hours_per_day = 22.0

        auto_maintenance = int(
            bool(
                auto_maintenance
            )
        )

        # "В простое" вручную не назначается.
        # Он определяется наличием активной работы.

        if status == "Списан":
            final_status = "Списан"

        elif (
            current["status"]
            == "Списан"
            and status != "Списан"
        ):
            if self._has_active_work(
                equipment_id
            ):
                final_status = "В простое"
            else:
                final_status = "В работе"

        elif self._has_active_work(
            equipment_id
        ):
            final_status = "В простое"

        else:
            final_status = "В работе"

        self._execute(
            """
            UPDATE equipment
            SET
                model = ?,
                serial_number = ?,
                garage_number = ?,
                registration_number = ?,
                manufacture_year = ?,
                current_hours = ?,
                status = ?,
                note = ?,
                shift_hours_per_day = ?,
                auto_maintenance = ?,
                commissioning_date = ?,
                warranty_years = ?,
                warranty_hours = ?,
                warranty_start_hours = ?,
                photo_path = ?,
                manufacturer_id = ?,
                distributor_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                model,
                serial_number,
                garage_number,
                str(
                    registration_number
                    or ""
                ).strip(),
                manufacture_year,
                float(
                    current_hours or 0
                ),
                final_status,
                str(
                    note or ""
                ).strip(),
                shift_hours_per_day,
                auto_maintenance,
                str(commissioning_date or "").strip(),
                float(warranty_years or 0),
                float(warranty_hours or 0),
                float(warranty_start_hours or 0),
                str(photo_path or "").strip(),
                manufacturer_id,
                distributor_id,
                self._now(),
                equipment_id,
            ),
        )

    def delete_equipment(
        self,
        equipment_id,
    ):
        self._execute(
            """
            DELETE FROM equipment
            WHERE id = ?
            """,
            (equipment_id,),
        )

    def get_equipment(
        self,
        equipment_id,
    ):
        self.sync_equipment_status(
            equipment_id
        )

        return self._fetchone(
            """
            SELECT *
            FROM equipment
            WHERE id = ?
            """,
            (equipment_id,),
        )

    def get_all_equipment(self):
        self.sync_all_equipment_statuses()

        return self._fetchall(
            """
            SELECT *
            FROM equipment
            ORDER BY
                model COLLATE NOCASE,
                garage_number COLLATE NOCASE
            """
        )

    def search_equipment(
        self,
        text,
    ):
        self.sync_all_equipment_statuses()

        text = str(
            text or ""
        ).strip()

        if not text:
            return self.get_all_equipment()

        pattern = f"%{text}%"

        return self._fetchall(
            """
            SELECT *
            FROM equipment
            WHERE
                model LIKE ?
                    COLLATE NOCASE
                OR serial_number LIKE ?
                    COLLATE NOCASE
                OR garage_number LIKE ?
                    COLLATE NOCASE
                OR registration_number LIKE ?
                    COLLATE NOCASE
            ORDER BY
                model COLLATE NOCASE,
                garage_number COLLATE NOCASE
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
            ),
        )

    def get_equipment_by_status(
        self,
        status,
    ):
        self.sync_all_equipment_statuses()

        if status not in (
            "В работе",
            "В простое",
            "Списан",
        ):
            return []

        return self._fetchall(
            """
            SELECT *
            FROM equipment
            WHERE status = ?
            ORDER BY
                model COLLATE NOCASE,
                garage_number COLLATE NOCASE
            """,
            (status,),
        )

    def find_equipment_by_garage_number(
        self,
        garage_number,
    ):
        return self._fetchall(
            """
            SELECT *
            FROM equipment
            WHERE garage_number = ?
                COLLATE NOCASE
            ORDER BY
                model COLLATE NOCASE,
                serial_number COLLATE NOCASE
            """,
            (
                str(
                    garage_number or ""
                ).strip(),
            ),
        )

    def find_equipment_by_garage_and_model(
        self,
        garage_number,
        model,
    ):
        return self._fetchone(
            """
            SELECT *
            FROM equipment
            WHERE
                garage_number = ?
                    COLLATE NOCASE
                AND model = ?
                    COLLATE NOCASE
            ORDER BY id
            LIMIT 1
            """,
            (
                str(
                    garage_number or ""
                ).strip(),
                str(
                    model or ""
                ).strip(),
            ),
        )

    def equipment_exists(
        self,
        model,
        serial_number,
        garage_number,
        exclude_id=None,
    ):
        sql = """
            SELECT id
            FROM equipment
            WHERE
                model = ?
                    COLLATE NOCASE
                AND serial_number = ?
                    COLLATE NOCASE
                AND garage_number = ?
                    COLLATE NOCASE
        """

        params = [
            str(
                model or ""
            ).strip(),
            str(
                serial_number or ""
            ).strip(),
            str(
                garage_number or ""
            ).strip(),
        ]

        if exclude_id is not None:
            sql += """
                AND id <> ?
            """

            params.append(
                exclude_id
            )

        sql += """
            LIMIT 1
        """

        return (
            self._fetchone(
                sql,
                tuple(params),
            )
            is not None
        )

    def update_equipment_hours(
        self,
        equipment_id,
        current_hours,
    ):
        self._execute(
            """
            UPDATE equipment
            SET
                current_hours = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                float(
                    current_hours or 0
                ),
                self._now(),
                equipment_id,
            ),
        )

    # ==========================================================
    # MAINTENANCE INTERVALS
    # ==========================================================

    def get_maintenance_intervals(
        self,
        equipment_id,
    ):
        """
        Возвращает все интервалы ТО для указанной машины.
        """

        return self._fetchall(
            """
            SELECT *
            FROM maintenance_intervals
            WHERE equipment_id = ?
            ORDER BY
                interval_hours ASC,
                id ASC
            """,
            (
                equipment_id,
            ),
        )

    def add_maintenance_interval(
        self,
        equipment_id,
        interval_hours,
        name="",
    ):
        """
        Добавляет новый интервал ТО для машины.
        """

        equipment = self.get_equipment(
            equipment_id
        )

        if equipment is None:
            raise ValueError(
                "Техника не найдена."
            )

        try:
            interval_hours = float(
                interval_hours
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                "Некорректный интервал ТО."
            )

        if interval_hours <= 0:
            raise ValueError(
                "Интервал ТО должен быть больше 0."
            )

        existing = self._fetchone(
            """
            SELECT id
            FROM maintenance_intervals
            WHERE
                equipment_id = ?
                AND interval_hours = ?
            LIMIT 1
            """,
            (
                equipment_id,
                interval_hours,
            ),
        )

        if existing is not None:
            raise ValueError(
                "Такой интервал ТО уже существует."
            )

        if not name:
            if interval_hours.is_integer():
                interval_text = str(
                    int(interval_hours)
                )
            else:
                interval_text = str(
                    interval_hours
                )

            name = (
                f"ТО-{interval_text}"
            )

        now = self._now()

        cursor = self._execute(
            """
            INSERT INTO maintenance_intervals (
                equipment_id,
                interval_hours,
                name,
                active,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, 1, ?, ?, ?
            )
            """,
            (
                equipment_id,
                interval_hours,
                str(name).strip(),
                int(interval_hours),
                now,
                now,
            ),
        )

        return cursor.lastrowid

    def update_maintenance_interval(
        self,
        interval_id,
        interval_hours,
        name="",
        active=True,
    ):
        """
        Изменяет существующий интервал ТО.
        """

        current = self._fetchone(
            """
            SELECT *
            FROM maintenance_intervals
            WHERE id = ?
            """,
            (
                interval_id,
            ),
        )

        if current is None:
            raise ValueError(
                "Интервал ТО не найден."
            )

        try:
            interval_hours = float(
                interval_hours
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                "Некорректный интервал ТО."
            )

        if interval_hours <= 0:
            raise ValueError(
                "Интервал ТО должен быть больше 0."
            )

        duplicate = self._fetchone(
            """
            SELECT id
            FROM maintenance_intervals
            WHERE
                equipment_id = ?
                AND interval_hours = ?
                AND id <> ?
            LIMIT 1
            """,
            (
                current["equipment_id"],
                interval_hours,
                interval_id,
            ),
        )

        if duplicate is not None:
            raise ValueError(
                "Такой интервал ТО уже существует."
            )

        if not name:
            if interval_hours.is_integer():
                interval_text = str(
                    int(interval_hours)
                )
            else:
                interval_text = str(
                    interval_hours
                )

            name = (
                f"ТО-{interval_text}"
            )

        self._execute(
            """
            UPDATE maintenance_intervals
            SET
                interval_hours = ?,
                name = ?,
                active = ?,
                sort_order = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                interval_hours,
                str(name).strip(),
                int(
                    bool(active)
                ),
                int(interval_hours),
                self._now(),
                interval_id,
            ),
        )

    def delete_maintenance_interval(
        self,
        interval_id,
    ):
        """
        Удаляет интервал ТО.

        Удаление интервала само по себе пока
        не удаляет историю уже выполненных ТО.
        """

        self._execute(
            """
            DELETE FROM maintenance_intervals
            WHERE id = ?
            """,
            (
                interval_id,
            ),
        )

    # ==========================================================
    # MAINTENANCE PLANNING
    # ==========================================================

    @staticmethod
    def _maintenance_number(value):
        value = float(value or 0)
        return int(value) if value.is_integer() else value

    def get_maintenance_plan(self, equipment_id=None):
        """Рассчитывает ближайшее ТО с учётом истории выполненных ТО."""
        params = []
        where = """
            WHERE COALESCE(e.status, 'В работе') <> 'Списан'
              AND COALESCE(e.auto_maintenance, 0) = 1
        """

        if equipment_id is not None:
            where += " AND e.id = ?"
            params.append(equipment_id)

        equipment_rows = self._fetchall(
            f"""
            SELECT e.id, e.model, e.serial_number, e.garage_number,
                   e.current_hours, e.status, e.auto_maintenance
            FROM equipment AS e
            {where}
            ORDER BY e.model COLLATE NOCASE,
                     e.garage_number COLLATE NOCASE, e.id
            """,
            tuple(params),
        )

        result = []

        for equipment in equipment_rows:
            intervals = self._fetchall(
                """
                SELECT id, interval_hours, name
                FROM maintenance_intervals
                WHERE equipment_id = ?
                  AND active = 1
                  AND interval_hours > 0
                ORDER BY interval_hours ASC, id ASC
                """,
                (equipment["id"],),
            )
            if not intervals:
                continue

            # Только фактически завершённые ТО с указанной наработкой.
            # Старшее ТО закрывает младшие интервалы: например ТО-1000
            # является новой точкой отсчёта и для ТО-500/250/50.
            completed_maintenance = self._fetchall(
                """
                SELECT id, maintenance_interval, machine_hours, date_end, date_start
                FROM work_records
                WHERE equipment_id = ?
                  AND repair_type = 'ТО'
                  AND COALESCE(in_progress, 1) = 0
                  AND COALESCE(is_planned, 0) = 0
                  AND maintenance_interval IS NOT NULL
                  AND maintenance_interval > 0
                  AND machine_hours IS NOT NULL
                  AND machine_hours > 0
                ORDER BY machine_hours DESC, COALESCE(date_end, date_start) DESC, id DESC
                """,
                (equipment["id"],),
            )

            current_hours = float(equipment["current_hours"] or 0)
            candidates = []

            for interval in intervals:
                interval_hours = float(interval["interval_hours"] or 0)
                if interval_hours <= 0:
                    continue

                anchor = None
                for work in completed_maintenance:
                    completed_interval = float(work["maintenance_interval"] or 0)
                    completed_hours = float(work["machine_hours"] or 0)
                    if completed_interval >= interval_hours and completed_hours > 0:
                        anchor = work
                        break

                if anchor is not None:
                    anchor_hours = float(anchor["machine_hours"] or 0)
                    target_hours = anchor_hours + interval_hours
                    anchor_work_id = anchor["id"]
                else:
                    # До появления первого фактического ТО сохраняем
                    # расчёт по кратности текущей наработки.
                    quotient = current_hours / interval_hours
                    rounded = round(quotient)
                    if current_hours > 0 and abs(quotient - rounded) < 1e-9:
                        target_hours = rounded * interval_hours
                    else:
                        target_hours = (int(quotient) + 1) * interval_hours
                    anchor_hours = None
                    anchor_work_id = None

                candidates.append({
                    "interval_id": interval["id"],
                    "interval_hours": interval_hours,
                    "name": str(interval["name"] or "").strip()
                            or f"ТО-{self._maintenance_number(interval_hours)}",
                    "target_hours": target_hours,
                    "anchor_hours": anchor_hours,
                    "anchor_work_id": anchor_work_id,
                })

            if not candidates:
                continue

            # Если несколько ТО уже просрочены, сначала показываем то,
            # у которого самая ранняя целевая наработка. При совпадении
            # выбираем старшее ТО.
            nearest_target = min(x["target_hours"] for x in candidates)
            same_target = [
                x for x in candidates
                if abs(x["target_hours"] - nearest_target) < 1e-9
            ]
            selected = max(same_target, key=lambda x: x["interval_hours"])
            remaining_raw = nearest_target - current_hours
            remaining_hours = max(0.0, remaining_raw)

            if remaining_raw <= 0:
                plan_status = "Наступило"
            elif remaining_raw <= 50:
                plan_status = "Скоро"
            else:
                plan_status = "Норма"

            planned_work = self._fetchone(
                """
                SELECT id, date_start, COALESCE(is_started, 0) AS is_started
                FROM work_records
                WHERE equipment_id = ?
                  AND repair_type = 'ТО'
                  AND COALESCE(is_planned, 0) = 1
                  AND COALESCE(in_progress, 1) = 1
                  AND maintenance_interval = ?
                  AND maintenance_target_hours = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    equipment["id"],
                    selected["interval_hours"],
                    nearest_target,
                ),
            )

            result.append({
                "equipment_id": equipment["id"],
                "model": equipment["model"],
                "serial_number": equipment["serial_number"],
                "garage_number": equipment["garage_number"],
                "equipment_status": equipment["status"],
                "auto_maintenance": bool(equipment["auto_maintenance"]),
                "current_hours": current_hours,
                "maintenance_interval": selected["interval_hours"],
                "maintenance_name": selected["name"],
                "target_hours": nearest_target,
                "remaining_hours": remaining_hours,
                "plan_status": plan_status,
                "maintenance_anchor_hours": selected["anchor_hours"],
                "maintenance_anchor_work_id": selected["anchor_work_id"],
                "planned_work_id": (
                    planned_work["id"]
                    if planned_work is not None
                    else None
                ),
                "planned_date": (
                    planned_work["date_start"]
                    if planned_work is not None
                    else None
                ),
                "maintenance_started": bool(
                    planned_work["is_started"]
                    if planned_work is not None
                    else False
                ),
            })

        return result

    def get_equipment_maintenance_plan(self, equipment_id):
        rows = self.get_maintenance_plan(equipment_id=equipment_id)
        return rows[0] if rows else None

    def schedule_maintenance(self, equipment_id, maintenance_interval, target_hours, planned_date):
        """Создаёт плановую запись ТО на выбранную дату."""
        equipment = self.get_equipment(equipment_id)
        if equipment is None:
            raise ValueError("Техника не найдена.")

        planned_date = str(planned_date or "").strip()
        if not planned_date:
            raise ValueError("Дата ТО не указана.")

        interval = float(maintenance_interval or 0)
        if interval <= 0:
            raise ValueError("Интервал ТО не указан.")

        target = float(target_hours or 0)
        existing = self._fetchone(
            """
            SELECT id FROM work_records
            WHERE equipment_id = ?
              AND repair_type = 'ТО'
              AND COALESCE(is_planned, 0) = 1
              AND COALESCE(in_progress, 1) = 1
              AND maintenance_interval = ?
              AND maintenance_target_hours = ?
            ORDER BY id DESC LIMIT 1
            """,
            (equipment_id, interval, target),
        )
        if existing is not None:
            raise ValueError("Это ТО уже запланировано. Сначала измените или удалите существующую плановую работу.")

        now = self._now()
        cursor = self._execute(
            """
            INSERT INTO work_records (
                equipment_id, request_number, repair_type, date_start, date_end,
                in_progress, machine_hours, description, executors,
                requires_report, report_completed, maintenance_interval,
                is_planned, is_started, is_auto_generated, maintenance_target_hours,
                source_maintenance_work_id, created_at, updated_at
            ) VALUES (?, '', 'ТО', ?, NULL, 1, 0, ?, '', 0, 0, ?, 1, 0, 0, ?, ?, ?, ?)
            """,
            (
                equipment_id, planned_date,
                f"Плановое ТО-{self._maintenance_number(interval)} на наработке {self._maintenance_number(target)} м/ч",
                interval, target, None, now, now,
            ),
        )
        return cursor.lastrowid

    def start_scheduled_maintenance(self, work_id, started_date=None):
        """Переводит запланированное ТО в фактически начатое.

        После этого работа начинает учитываться как активная и техника
        автоматически переводится в статус «В простое».
        """
        work = self._fetchone(
            """
            SELECT id, equipment_id, is_started
            FROM work_records
            WHERE id = ?
              AND repair_type = 'ТО'
              AND COALESCE(is_planned, 0) = 1
              AND COALESCE(in_progress, 1) = 1
            """,
            (work_id,),
        )
        if work is None:
            raise ValueError("Плановое ТО не найдено.")
        if bool(work["is_started"]):
            raise ValueError("Это ТО уже начато.")

        start_date = str(started_date or "").strip()
        if not start_date:
            from datetime import date
            start_date = date.today().isoformat()

        self._execute(
            """
            UPDATE work_records
            SET date_start = ?,
                is_started = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (start_date, self._now(), work_id),
        )
        self.sync_equipment_status(work["equipment_id"])

    def reschedule_maintenance(self, work_id, planned_date):
        """Переносит существующее плановое ТО на другую дату."""
        planned_date = str(planned_date or "").strip()
        if not planned_date:
            raise ValueError("Дата ТО не указана.")

        work = self._fetchone(
            """
            SELECT id, COALESCE(is_started, 0) AS is_started FROM work_records
            WHERE id = ?
              AND repair_type = 'ТО'
              AND COALESCE(is_planned, 0) = 1
            """,
            (work_id,),
        )
        if work is None:
            raise ValueError("Плановое ТО не найдено.")
        if bool(work["is_started"]):
            raise ValueError("Начатое ТО нельзя переносить. Сначала завершите его.")

        self._execute(
            """
            UPDATE work_records
            SET date_start = ?, date_end = NULL, updated_at = ?
            WHERE id = ?
            """,
            (planned_date, self._now(), work_id),
        )

    def cancel_scheduled_maintenance(self, work_id):
        """Удаляет только плановую запись ТО."""
        work = self._fetchone(
            """
            SELECT equipment_id, COALESCE(is_started, 0) AS is_started FROM work_records
            WHERE id = ?
              AND repair_type = 'ТО'
              AND COALESCE(is_planned, 0) = 1
            """,
            (work_id,),
        )
        if work is None:
            raise ValueError("Плановое ТО не найдено.")
        if bool(work["is_started"]):
            raise ValueError("Начатое ТО нельзя отменить как план. Завершите работу.")
        self._execute(
            "DELETE FROM work_records WHERE id = ?",
            (work_id,),
        )
        self.sync_equipment_status(work["equipment_id"])

    def complete_scheduled_maintenance(
        self,
        work_id,
        completed_date,
        machine_hours,
        description="",
        executors="",
    ):
        """Превращает плановое ТО в фактически выполненное."""
        work = self._fetchone(
            """
            SELECT * FROM work_records
            WHERE id = ?
              AND repair_type = 'ТО'
              AND COALESCE(is_planned, 0) = 1
            """,
            (work_id,),
        )
        if work is None:
            raise ValueError("Плановое ТО не найдено.")
        if not bool(work["is_started"]):
            raise ValueError("Сначала нажмите «Начать ТО».")

        completed_date = str(completed_date or "").strip()
        if not completed_date:
            raise ValueError("Дата выполнения не указана.")
        hours = float(machine_hours or 0)
        if hours <= 0:
            raise ValueError("Укажите фактическую наработку.")

        final_description = str(description or "").strip()
        if not final_description:
            final_description = (
                f"Выполнено ТО-{self._maintenance_number(work['maintenance_interval'])}"
            )

        self._execute(
            """
            UPDATE work_records
            SET date_start = ?,
                date_end = ?,
                in_progress = 0,
                machine_hours = ?,
                description = ?,
                executors = ?,
                is_planned = 0,
                is_started = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (
                completed_date,
                completed_date,
                hours,
                final_description,
                str(executors or "").strip(),
                self._now(),
                work_id,
            ),
        )

        equipment = self.get_equipment(work["equipment_id"])
        if equipment is not None:
            current_hours = float(equipment["current_hours"] or 0)
            if hours > current_hours:
                self.update_equipment_hours(
                    work["equipment_id"],
                    hours,
                )

        self.sync_equipment_status(work["equipment_id"])

    # ==========================================================
    # WORK REPORT ATTACHMENTS
    # ==========================================================

    def get_work_report_attachments(self, work_id):
        return self._fetchall(
            """
            SELECT * FROM work_report_attachments
            WHERE work_id = ?
            ORDER BY id DESC
            """,
            (work_id,),
        )

    def add_work_report_attachment(self, work_id, file_name, file_path):
        self._execute(
            """
            INSERT INTO work_report_attachments
            (work_id, file_name, file_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (work_id, file_name, file_path, self._now()),
        )

    def delete_work_report_attachment(self, attachment_id):
        self._execute(
            "DELETE FROM work_report_attachments WHERE id = ?",
            (attachment_id,),
        )

    # ==========================================================
    # WORK DAILY LOG
    # ==========================================================

    def get_work_daily_log(self, work_id):
        return self._fetchall(
            """
            SELECT *
            FROM work_daily_log
            WHERE work_id = ?
            ORDER BY work_date ASC, id ASC
            """,
            (work_id,),
        )

    def get_work_daily_for_period(self, date_from, date_to):
        return self._fetchall("""SELECT d.*, w.equipment_id, e.model, e.serial_number, e.garage_number, w.repair_type, w.description AS work_description FROM work_daily_log d JOIN work_records w ON w.id=d.work_id JOIN equipment e ON e.id=w.equipment_id WHERE d.work_date>=? AND d.work_date<=? ORDER BY d.work_date, e.model COLLATE NOCASE, e.garage_number COLLATE NOCASE""", (str(date_from),str(date_to)))

    def add_work_daily_entry(
        self,
        work_id,
        work_date,
        day_type,
        description="",
        executors="",
        machine_hours=0,
    ):
        work = self.get_work(work_id)
        if work is None:
            raise ValueError("Карточка простоя не найдена.")
        work_date = str(work_date or "").strip()
        if not work_date:
            raise ValueError("Дата не указана.")
        now = self._now()
        equipment = self.get_equipment(work["equipment_id"])
        current_equipment_hours = float(
            equipment["current_hours"] or 0
        ) if equipment is not None else 0.0
        current_work_hours = float(work["machine_hours"] or 0)
        entered_hours = float(machine_hours or 0)

        self._execute(
            """
            INSERT INTO work_daily_log (
                work_id, work_date, day_type, description,
                executors, machine_hours, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_id, work_date) DO UPDATE SET
                day_type = excluded.day_type,
                description = excluded.description,
                executors = excluded.executors,
                machine_hours = excluded.machine_hours,
                updated_at = excluded.updated_at
            """,
            (
                work_id, work_date, str(day_type or "Простой").strip(),
                str(description or "").strip(),
                str(executors or "").strip(),
                entered_hours, now, now,
            ),
        )

        # Рост наработки из дневной записи становится новым
        # актуальным показанием и для карточки ремонта, и для техники.
        if entered_hours > current_work_hours:
            self._execute(
                """
                UPDATE work_records
                SET machine_hours = ?, updated_at = ?
                WHERE id = ?
                """,
                (entered_hours, now, work_id),
            )
        if (
            equipment is not None
            and entered_hours > current_equipment_hours
        ):
            self._execute(
                """
                UPDATE equipment
                SET current_hours = ?, updated_at = ?
                WHERE id = ?
                """,
                (entered_hours, now, work["equipment_id"]),
            )

    def delete_work_daily_entry(self, entry_id):
        self._execute(
            "DELETE FROM work_daily_log WHERE id = ?",
            (entry_id,),
        )

    # ==========================================================
    # WORK RECORDS
    # ==========================================================

    def add_work(
        self,
        equipment_id,
        request_number="",
        repair_type="",
        date_start="",
        date_end=None,
        in_progress=True,
        machine_hours=0,
        description="",
        executors="",
        requires_report=False,
        report_completed=False,
        maintenance_interval=None,
    ):
        equipment = self.get_equipment(
            equipment_id
        )

        if equipment is None:
            raise ValueError(
                "Техника не найдена."
            )

        date_start = str(
            date_start or ""
        ).strip()

        if not date_start:
            raise ValueError(
                "Дата начала не указана."
            )

        if in_progress:
            date_end = None
        elif date_end:
            date_end = str(
                date_end
            ).strip()

            if date_end < date_start:
                raise ValueError(
                    "Дата окончания не может "
                    "быть раньше даты начала."
                )

        now = self._now()

        cursor = self._execute(
            """
            INSERT INTO work_records (
                equipment_id,
                request_number,
                repair_type,
                date_start,
                date_end,
                in_progress,
                machine_hours,
                description,
                executors,
                requires_report,
                report_completed,
                maintenance_interval,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                equipment_id,
                str(
                    request_number or ""
                ).strip(),
                str(
                    repair_type or ""
                ).strip(),
                date_start,
                date_end,
                int(
                    bool(in_progress)
                ),
                float(
                    machine_hours or 0
                ),
                str(
                    description or ""
                ).strip(),
                str(
                    executors or ""
                ).strip(),
                int(
                    bool(
                        requires_report
                    )
                ),
                int(
                    bool(
                        report_completed
                    )
                ),
                (
                    float(maintenance_interval)
                    if maintenance_interval is not None
                    else None
                ),
                now,
                now,
            ),
        )

        self.sync_equipment_status(
            equipment_id
        )

        return cursor.lastrowid

    def update_work(
        self,
        work_id,
        equipment_id,
        request_number="",
        repair_type="",
        date_start="",
        date_end=None,
        in_progress=True,
        machine_hours=0,
        description="",
        executors="",
        requires_report=False,
        report_completed=False,
        maintenance_interval=None,
    ):
        old_work = self._fetchone(
            """
            SELECT *
            FROM work_records
            WHERE id = ?
            """,
            (work_id,),
        )

        if old_work is None:
            raise ValueError(
                "Запись работы не найдена."
            )

        equipment = self.get_equipment(
            equipment_id
        )

        if equipment is None:
            raise ValueError(
                "Техника не найдена."
            )

        old_equipment_id = (
            old_work["equipment_id"]
        )

        date_start = str(
            date_start or ""
        ).strip()

        if not date_start:
            raise ValueError(
                "Дата начала не указана."
            )

        if in_progress:
            date_end = None
        elif date_end:
            date_end = str(
                date_end
            ).strip()

            if date_end < date_start:
                raise ValueError(
                    "Дата окончания не может "
                    "быть раньше даты начала."
                )

        self._execute(
            """
            UPDATE work_records
            SET
                equipment_id = ?,
                request_number = ?,
                repair_type = ?,
                date_start = ?,
                date_end = ?,
                in_progress = ?,
                machine_hours = ?,
                description = ?,
                executors = ?,
                requires_report = ?,
                report_completed = ?,
                maintenance_interval = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                equipment_id,
                str(
                    request_number or ""
                ).strip(),
                str(
                    repair_type or ""
                ).strip(),
                date_start,
                date_end,
                int(
                    bool(in_progress)
                ),
                float(
                    machine_hours or 0
                ),
                str(
                    description or ""
                ).strip(),
                str(
                    executors or ""
                ).strip(),
                int(
                    bool(
                        requires_report
                    )
                ),
                int(
                    bool(
                        report_completed
                    )
                ),
                (
                    float(maintenance_interval)
                    if maintenance_interval is not None
                    else None
                ),
                self._now(),
                work_id,
            ),
        )

        self.sync_equipment_status(
            equipment_id
        )

        if (
            old_equipment_id
            != equipment_id
        ):
            self.sync_equipment_status(
                old_equipment_id
            )

    def delete_work(
        self,
        work_id,
    ):
        work = self._fetchone(
            """
            SELECT equipment_id
            FROM work_records
            WHERE id = ?
            """,
            (work_id,),
        )

        if work is None:
            return

        equipment_id = (
            work["equipment_id"]
        )

        self._execute(
            """
            DELETE FROM work_records
            WHERE id = ?
            """,
            (work_id,),
        )

        self.sync_equipment_status(
            equipment_id
        )

    def get_work(
        self,
        work_id,
    ):
        return self._fetchone(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status
            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE w.id = ?
            """,
            (work_id,),
        )

    def get_all_work(self):
        return self._fetchall(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status
            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            ORDER BY
                w.in_progress DESC,
                w.date_start DESC,
                w.id DESC
            """
        )

    def get_work_by_equipment(
        self,
        equipment_id,
    ):
        return self._fetchall(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status
            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE
                w.equipment_id = ?

            ORDER BY
                w.date_start DESC,
                w.id DESC
            """,
            (equipment_id,),
        )

    def get_active_work(self):
        return self._fetchall(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status
            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE
                w.in_progress = 1

            ORDER BY
                w.date_start ASC,
                e.model COLLATE NOCASE,
                e.garage_number COLLATE NOCASE
            """
        )

    def search_work(
        self,
        text,
    ):
        text = str(
            text or ""
        ).strip()

        if not text:
            return self.get_all_work()

        pattern = f"%{text}%"

        return self._fetchall(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status
            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE
                w.request_number LIKE ?
                    COLLATE NOCASE

                OR e.model LIKE ?
                    COLLATE NOCASE

                OR e.serial_number LIKE ?
                    COLLATE NOCASE

                OR e.garage_number LIKE ?
                    COLLATE NOCASE

                OR w.repair_type LIKE ?
                    COLLATE NOCASE

                OR w.description LIKE ?
                    COLLATE NOCASE

                OR w.executors LIKE ?
                    COLLATE NOCASE

            ORDER BY
                w.in_progress DESC,
                w.date_start DESC,
                w.id DESC
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
            ),
        )

    def filter_work(
        self,
        text="",
        repair_type=None,
        in_progress=None,
        requires_report=None,
        report_completed=None,
        date_from=None,
        date_to=None,
    ):
        sql = """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.status AS equipment_status

            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE 1 = 1
        """

        params = []

        text = str(
            text or ""
        ).strip()

        if text:
            pattern = f"%{text}%"

            sql += """
                AND (
                    w.request_number LIKE ?
                        COLLATE NOCASE

                    OR e.model LIKE ?
                        COLLATE NOCASE

                    OR e.serial_number LIKE ?
                        COLLATE NOCASE

                    OR e.garage_number LIKE ?
                        COLLATE NOCASE

                    OR w.description LIKE ?
                        COLLATE NOCASE

                    OR w.executors LIKE ?
                        COLLATE NOCASE
                )
            """

            params.extend(
                [
                    pattern,
                    pattern,
                    pattern,
                    pattern,
                    pattern,
                    pattern,
                ]
            )

        if repair_type:
            if isinstance(repair_type, (list, tuple, set)):
                repair_types = [
                    str(value).strip()
                    for value in repair_type
                    if str(value or "").strip()
                ]
                if repair_types:
                    placeholders = ",".join("?" for _ in repair_types)
                    sql += f"\n                AND w.repair_type IN ({placeholders})\n            "
                    params.extend(repair_types)
            else:
                sql += """
                    AND w.repair_type = ?
                """
                params.append(repair_type)

        if in_progress is not None:
            sql += """
                AND w.in_progress = ?
            """

            params.append(
                int(
                    bool(in_progress)
                )
            )

        if requires_report is not None:
            sql += """
                AND w.requires_report = ?
            """

            params.append(
                int(
                    bool(
                        requires_report
                    )
                )
            )

        if report_completed is not None:
            sql += """
                AND w.report_completed = ?
            """

            params.append(
                int(
                    bool(
                        report_completed
                    )
                )
            )

        # Работа попадает в период,
        # если ее интервал пересекается
        # с выбранным периодом.

        if date_from:
            sql += """
                AND (
                    w.date_end IS NULL
                    OR w.date_end >= ?
                )
            """

            params.append(
                str(date_from)
            )

        if date_to:
            sql += """
                AND w.date_start <= ?
            """

            params.append(
                str(date_to)
            )

        sql += """
            ORDER BY
                w.in_progress DESC,
                w.date_start DESC,
                w.id DESC
        """

        return self._fetchall(
            sql,
            tuple(params),
        )

    def get_missing_reports(self):
        return self._fetchall(
            """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number

            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE
                w.requires_report = 1
                AND w.report_completed = 0
                AND w.in_progress = 0

            ORDER BY
                w.date_end DESC,
                w.id DESC
            """
        )

    def finish_work(
        self,
        work_id,
        date_end,
        machine_hours=None,
    ):
        work = self._fetchone(
            """
            SELECT
                equipment_id,
                date_start
            FROM work_records
            WHERE id = ?
            """,
            (work_id,),
        )

        if work is None:
            raise ValueError(
                "Запись работы не найдена."
            )

        date_end = str(
            date_end or ""
        ).strip()

        if not date_end:
            raise ValueError(
                "Дата окончания не указана."
            )

        if (
            date_end
            < work["date_start"]
        ):
            raise ValueError(
                "Дата окончания не может "
                "быть раньше даты начала."
            )

        equipment_id = (
            work["equipment_id"]
        )

        if machine_hours is None:
            self._execute(
                """
                UPDATE work_records
                SET
                    date_end = ?,
                    in_progress = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    date_end,
                    self._now(),
                    work_id,
                ),
            )

        else:
            machine_hours = float(
                machine_hours or 0
            )

            self._execute(
                """
                UPDATE work_records
                SET
                    date_end = ?,
                    in_progress = 0,
                    machine_hours = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    date_end,
                    machine_hours,
                    self._now(),
                    work_id,
                ),
            )

            if machine_hours > 0:
                equipment = (
                    self.get_equipment(
                        equipment_id
                    )
                )

                if equipment:
                    current_hours = float(
                        equipment[
                            "current_hours"
                        ]
                        or 0
                    )

                    if (
                        machine_hours
                        > current_hours
                    ):
                        self.update_equipment_hours(
                            equipment_id,
                            machine_hours,
                        )

        self.sync_equipment_status(
            equipment_id
        )

    # ==========================================================
    # COMPONENTS
    # ==========================================================

    def add_component(self,equipment_id,component_name,serial_number="",resource_hours=0,install_machine_hours=0,install_date="",part_number="",note=""):
        component_name=str(component_name or "").strip()
        if not component_name: raise ValueError("Компонент не указан.")
        if equipment_id is not None and self.get_equipment(equipment_id) is None: raise ValueError("Техника не найдена.")
        cur=self._execute("""INSERT INTO components(equipment_id,component_name,part_number,serial_number,resource_hours,install_machine_hours,install_date,note,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",(equipment_id,component_name,str(part_number or "").strip(),str(serial_number or "").strip(),float(resource_hours or 0),float(install_machine_hours or 0),str(install_date or "").strip(),str(note or "").strip(),self._now()))
        return cur.lastrowid

    def update_component(self,component_id,equipment_id,component_name,serial_number="",resource_hours=0,install_machine_hours=0,install_date="",part_number="",note=""):
        component_name=str(component_name or "").strip()
        if not component_name: raise ValueError("Компонент не указан.")
        if equipment_id is not None and self.get_equipment(equipment_id) is None: raise ValueError("Техника не найдена.")
        self._execute("""UPDATE components SET equipment_id=?,component_name=?,part_number=?,serial_number=?,resource_hours=?,install_machine_hours=?,install_date=?,note=? WHERE id=?""",(equipment_id,component_name,str(part_number or "").strip(),str(serial_number or "").strip(),float(resource_hours or 0),float(install_machine_hours or 0),str(install_date or "").strip(),str(note or "").strip(),component_id))

    def delete_component(self,component_id): self._execute("DELETE FROM components WHERE id=?",(component_id,))
    def get_component(self,component_id):
        return self._fetchone("""SELECT c.*,e.model,e.serial_number AS equipment_serial_number,e.garage_number,e.current_hours AS machine_current_hours FROM components c LEFT JOIN equipment e ON e.id=c.equipment_id WHERE c.id=?""",(component_id,))
    def get_components_by_equipment(self,equipment_id):
        return self._fetchall("""SELECT c.*,e.model,e.serial_number AS equipment_serial_number,e.garage_number,e.current_hours AS machine_current_hours,MAX(0,e.current_hours-c.install_machine_hours) AS worked_hours,(c.resource_hours-MAX(0,e.current_hours-c.install_machine_hours)) AS remaining_hours FROM components c JOIN equipment e ON e.id=c.equipment_id WHERE c.equipment_id=? ORDER BY c.component_name COLLATE NOCASE,c.install_date DESC,c.id DESC""",(equipment_id,))
    def get_all_components(self):
        return self._fetchall("""SELECT c.*,e.model,e.serial_number AS equipment_serial_number,e.garage_number,e.current_hours AS machine_current_hours,CASE WHEN e.id IS NULL THEN 0 ELSE MAX(0,e.current_hours-c.install_machine_hours) END AS worked_hours,CASE WHEN e.id IS NULL THEN c.resource_hours ELSE c.resource_hours-MAX(0,e.current_hours-c.install_machine_hours) END AS remaining_hours FROM components c LEFT JOIN equipment e ON e.id=c.equipment_id ORDER BY CASE WHEN e.id IS NULL THEN 1 ELSE 0 END,e.model COLLATE NOCASE,e.garage_number COLLATE NOCASE,c.component_name COLLATE NOCASE""")

    def get_components_over_resource(
        self,
    ):
        return self._fetchall(
            """
            SELECT
                c.*,
                e.model,
                e.serial_number
                    AS equipment_serial_number,
                e.garage_number,
                e.current_hours
                    AS machine_current_hours,

                MAX(
                    0,
                    e.current_hours
                    - c.install_machine_hours
                ) AS worked_hours,

                (
                    c.resource_hours
                    - MAX(
                        0,
                        e.current_hours
                        - c.install_machine_hours
                    )
                ) AS remaining_hours

            FROM components AS c

            JOIN equipment AS e
                ON e.id = c.equipment_id

            WHERE
                c.resource_hours > 0

                AND (
                    e.current_hours
                    - c.install_machine_hours
                ) >= c.resource_hours

            ORDER BY
                remaining_hours ASC
            """
        )

    def get_components_near_resource(
        self,
        warning_percent=10,
    ):
        warning_percent = max(
            0.0,
            min(
                float(
                    warning_percent
                ),
                100.0,
            ),
        )

        return self._fetchall(
            """
            SELECT
                c.*,
                e.model,
                e.serial_number
                    AS equipment_serial_number,
                e.garage_number,
                e.current_hours
                    AS machine_current_hours,

                MAX(
                    0,
                    e.current_hours
                    - c.install_machine_hours
                ) AS worked_hours,

                (
                    c.resource_hours
                    - MAX(
                        0,
                        e.current_hours
                        - c.install_machine_hours
                    )
                ) AS remaining_hours

            FROM components AS c

            JOIN equipment AS e
                ON e.id = c.equipment_id

            WHERE
                c.resource_hours > 0

                AND (
                    e.current_hours
                    - c.install_machine_hours
                ) >= 0

                AND (
                    e.current_hours
                    - c.install_machine_hours
                ) < c.resource_hours

                AND (
                    (
                        c.resource_hours
                        - (
                            e.current_hours
                            - c.install_machine_hours
                        )
                    )
                    / c.resource_hours
                    * 100
                ) <= ?

            ORDER BY
                remaining_hours ASC
            """,
            (warning_percent,),
        )

    # ==========================================================
    # PERIOD / SCHEDULE
    # ==========================================================

    def get_work_for_period(
        self,
        date_from,
        date_to,
        repair_type=None,
    ):
        sql = """
            SELECT
                w.*,
                e.model,
                e.serial_number,
                e.garage_number,
                e.current_hours,
                e.status AS equipment_status

            FROM work_records AS w

            JOIN equipment AS e
                ON e.id = w.equipment_id

            WHERE
                w.date_start <= ?

                AND (
                    w.date_end IS NULL
                    OR w.date_end >= ?
                )
        """

        params = [
            str(date_to),
            str(date_from),
        ]

        if repair_type:
            sql += """
                AND w.repair_type = ?
            """

            params.append(
                repair_type
            )

        sql += """
            ORDER BY
                e.model COLLATE NOCASE,
                e.garage_number
                    COLLATE NOCASE,
                w.date_start ASC,
                w.id ASC
        """

        return self._fetchall(
            sql,
            tuple(params),
        )

    # ==========================================================
    # DASHBOARD
    # ==========================================================

    def get_dashboard_statistics(self):
        self.sync_all_equipment_statuses()

        total_equipment = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM equipment
            """
        )["count"]

        active_work = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM work_records
            WHERE in_progress = 1
            """
        )["count"]

        downtime_equipment = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM equipment
            WHERE status = 'В простое'
            """
        )["count"]

        written_off = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM equipment
            WHERE status = 'Списан'
            """
        )["count"]

        components = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM components
            """
        )["count"]

        return {
            "total_equipment":
                total_equipment,
            "active_work":
                active_work,
            "downtime_equipment":
                downtime_equipment,
            "written_off":
                written_off,
            "components":
                components,
        }

    def get_customer_work_count(self):
        row = self._fetchone(
            """
            SELECT COUNT(
                DISTINCT equipment_id
            ) AS count

            FROM work_records

            WHERE
                in_progress = 1
                AND repair_type =
                    'Работы заказчика'
            """
        )

        return row["count"]

    # ==========================================================
    # NOTIFICATIONS
    # ==========================================================

    def get_notifications(
        self,
        component_warning_percent=10,
    ):
        notifications = []

        for row in (
            self.get_missing_reports()
        ):
            notifications.append(
                {
                    "type":
                        "missing_report",
                    "priority":
                        "warning",
                    "work_id":
                        row["id"],
                    "equipment_id":
                        row["equipment_id"],
                    "title":
                        "Требуется отчет",
                    "text": (
                        f"Требуется отчет: "
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                }
            )

        for row in (
            self.get_components_over_resource()
        ):
            notifications.append(
                {
                    "type":
                        "component_over_resource",
                    "priority":
                        "critical",
                    "component_id":
                        row["id"],
                    "equipment_id":
                        row["equipment_id"],
                    "title":
                        "Превышен ресурс компонента",
                    "text": (
                        f"Превышен ресурс: "
                        f"{row['component_name']} — "
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                    "remaining_hours":
                        row["remaining_hours"],
                }
            )

        for row in (
            self.get_components_near_resource(
                component_warning_percent
            )
        ):
            notifications.append(
                {
                    "type":
                        "component_near_resource",
                    "priority":
                        "warning",
                    "component_id":
                        row["id"],
                    "equipment_id":
                        row["equipment_id"],
                    "title":
                        "Заканчивается ресурс компонента",
                    "text": (
                        f"Остаток ресурса "
                        f"{row['component_name']}: "
                        f"{row['remaining_hours']:.0f} ч — "
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                    "remaining_hours":
                        row["remaining_hours"],
                }
            )

        # Уведомления по ближайшему ТО.
        # В таблице планирования цветовые предупреждения не используются:
        # сигнализация о приближении/наступлении ТО живёт здесь.
        for plan in self.get_maintenance_plan():
            if plan.get("planned_work_id"):
                continue

            remaining = float(
                plan.get("target_hours", 0)
                - plan.get("current_hours", 0)
            )

            if remaining <= 0:
                notifications.append(
                    {
                        "type": "maintenance_due",
                        "priority": "critical",
                        "equipment_id": plan["equipment_id"],
                        "title": "Наступило ТО",
                        "text": (
                            f"{plan['maintenance_name']}: "
                            f"{plan['model']} №{plan['garage_number']} — "
                            f"текущая наработка "
                            f"{self._maintenance_number(plan['current_hours'])} м/ч, "
                            f"ТО на "
                            f"{self._maintenance_number(plan['target_hours'])} м/ч"
                        ),
                        "remaining_hours": remaining,
                    }
                )
            elif remaining <= 50:
                notifications.append(
                    {
                        "type": "maintenance_near",
                        "priority": "warning",
                        "equipment_id": plan["equipment_id"],
                        "title": "Приближается ТО",
                        "text": (
                            f"{plan['maintenance_name']}: "
                            f"{plan['model']} №{plan['garage_number']} — "
                            f"осталось "
                            f"{self._maintenance_number(remaining)} м/ч "
                            f"(текущая "
                            f"{self._maintenance_number(plan['current_hours'])}, "
                            f"ТО на "
                            f"{self._maintenance_number(plan['target_hours'])} м/ч)"
                        ),
                        "remaining_hours": remaining,
                    }
                )

        return notifications

    # ==========================================================
    # NOTIFICATION CENTER / REMINDERS
    # ==========================================================

    def get_reminders(self, include_completed=True, limit=None):
        where = "" if include_completed else "WHERE is_completed = 0"
        sql = f"""
            SELECT * FROM reminders
            {where}
            ORDER BY is_completed ASC, datetime(remind_at) ASC, id DESC
        """
        params = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (int(limit),)
        return self._fetchall(sql, params)

    def get_reminder(self, reminder_id):
        return self._fetchone(
            "SELECT * FROM reminders WHERE id = ?",
            (int(reminder_id),),
        )

    def create_reminder(
        self, title, remind_at, description="", repeat_rule="once",
        priority="normal", windows_notify=True,
    ):
        now = self._now()
        cursor = self._execute(
            """
            INSERT INTO reminders (
                title, description, remind_at, repeat_rule, priority,
                windows_notify, is_completed, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                str(title or "").strip(), str(description or "").strip(),
                str(remind_at), str(repeat_rule or "once"),
                str(priority or "normal"), 1 if windows_notify else 0,
                now, now,
            ),
        )
        return cursor.lastrowid

    def update_reminder(
        self, reminder_id, title, remind_at, description="",
        repeat_rule="once", priority="normal", windows_notify=True,
    ):
        self._execute(
            """
            UPDATE reminders SET
                title = ?, description = ?, remind_at = ?, repeat_rule = ?,
                priority = ?, windows_notify = ?, is_completed = 0,
                completed_at = NULL, last_notified_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (
                str(title or "").strip(), str(description or "").strip(),
                str(remind_at), str(repeat_rule or "once"),
                str(priority or "normal"), 1 if windows_notify else 0,
                self._now(), int(reminder_id),
            ),
        )

    def delete_reminder(self, reminder_id):
        self._execute("DELETE FROM reminders WHERE id = ?", (int(reminder_id),))

    def set_reminder_completed(self, reminder_id, completed=True):
        self._execute(
            """
            UPDATE reminders SET
                is_completed = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                1 if completed else 0,
                self._now() if completed else None,
                self._now(), int(reminder_id),
            ),
        )

    def reschedule_reminder(self, reminder_id, remind_at):
        self._execute(
            """
            UPDATE reminders SET remind_at = ?, is_completed = 0,
                completed_at = NULL, last_notified_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (str(remind_at), self._now(), int(reminder_id)),
        )

    def reschedule_completed_reminder(self, reminder_id, remind_at):
        """Переносит повторяющуюся задачу на следующий срок, сохраняя её выполненной до этого срока."""
        now = self._now()
        self._execute(
            """
            UPDATE reminders SET remind_at = ?, is_completed = 1,
                completed_at = ?, last_notified_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (str(remind_at), now, now, int(reminder_id)),
        )

    def reactivate_due_recurring_reminders(self, now_iso):
        """Возвращает повторяющиеся выполненные задачи в активные, когда наступил новый срок."""
        self._execute(
            """
            UPDATE reminders
            SET is_completed = 0, completed_at = NULL, last_notified_at = NULL, updated_at = ?
            WHERE is_completed = 1
              AND repeat_rule <> 'once'
              AND datetime(remind_at) <= datetime(?)
            """,
            (self._now(), str(now_iso)),
        )

    def mark_reminder_notified(self, reminder_id):
        self._execute(
            "UPDATE reminders SET last_notified_at = ?, updated_at = ? WHERE id = ?",
            (self._now(), self._now(), int(reminder_id)),
        )

    # ==========================================================
    # SETTINGS
    # Только локальные настройки базы заказчика.
    # Организация, логотип и активный заказчик
    # хранятся через CustomerManager.
    # ==========================================================

    def get_settings(self):
        row = self._fetchone(
            """
            SELECT *
            FROM settings
            WHERE id = 1
            """
        )

        if row is None:
            self._execute(
                """
                INSERT INTO settings (
                    id,
                    backup_count
                )
                VALUES (
                    1,
                    30
                )
                """
            )

            row = self._fetchone(
                """
                SELECT *
                FROM settings
                WHERE id = 1
                """
            )

        return row

    def save_settings(
        self,
        backup_count=30,
        **kwargs,
    ):
        backup_count = max(
            1,
            int(
                backup_count or 30
            ),
        )

        self._execute(
            """
            INSERT INTO settings (
                id,
                backup_count
            )
            VALUES (
                1,
                ?
            )

            ON CONFLICT(id)
            DO UPDATE SET
                backup_count =
                    excluded.backup_count
            """,
            (backup_count,),
        )

    def get_audit_log(self, limit=200):
        return self._fetchall(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (max(1, int(limit or 200)),),
        )

    # ==========================================================
    # CONNECTION
    # ==========================================================

    def check_connection(self):
        return self.db.check_connection()    
