# database/migrations.py

from database.database import Database


# ==============================================================
# HELPERS
# ==============================================================


def _column_exists(
    cursor,
    table_name,
    column_name,
):
    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    return any(
        row["name"] == column_name
        for row in cursor.fetchall()
    )


def _add_column_if_missing(
    cursor,
    table_name,
    column_name,
    column_definition,
):
    if not _column_exists(
        cursor,
        table_name,
        column_name,
    ):
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name}
            {column_definition}
            """
        )


def migrate(
    customer_name=None,
    db_path=None,
):
    db = Database(
        customer_name=customer_name,
        db_path=db_path,
    )

    cursor = db.cursor()

    try:

        # ======================================================
        # EQUIPMENT
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                model TEXT NOT NULL,
                serial_number TEXT NOT NULL,
                garage_number TEXT NOT NULL,

                registration_number TEXT,
                manufacture_year INTEGER,

                current_hours REAL DEFAULT 0,

                status TEXT DEFAULT 'В работе',

                note TEXT,

                shift_hours_per_day REAL DEFAULT 22,

                auto_maintenance INTEGER DEFAULT 0,

                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        # Дополнительные данные карточки техники
        _add_column_if_missing(cursor, "equipment", "commissioning_date", "TEXT")
        _add_column_if_missing(cursor, "equipment", "warranty_years", "REAL DEFAULT 0")
        _add_column_if_missing(cursor, "equipment", "warranty_hours", "REAL DEFAULT 0")
        _add_column_if_missing(cursor, "equipment", "warranty_start_hours", "REAL DEFAULT 0")
        _add_column_if_missing(cursor, "equipment", "photo_path", "TEXT")

        # Справочники производителей и дистрибьюторов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                country TEXT,
                logo_path TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distributors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        _add_column_if_missing(cursor, "equipment", "manufacturer_id", "INTEGER")
        _add_column_if_missing(cursor, "equipment", "distributor_id", "INTEGER")

        # ======================================================
        # WORK RECORDS
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS work_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                equipment_id INTEGER NOT NULL,

                request_number TEXT,

                repair_type TEXT,

                date_start TEXT NOT NULL,
                date_end TEXT,

                in_progress INTEGER DEFAULT 1,

                machine_hours REAL DEFAULT 0,

                description TEXT,
                executors TEXT,

                requires_report INTEGER DEFAULT 0,
                report_completed INTEGER DEFAULT 0,

                is_planned INTEGER DEFAULT 0,
                is_started INTEGER DEFAULT 0,

                is_auto_generated INTEGER DEFAULT 0,

                maintenance_interval REAL,

                maintenance_target_hours REAL,

                maintenance_anchor_work_id INTEGER,

                source_maintenance_work_id INTEGER,

                created_at TEXT,
                updated_at TEXT,

                FOREIGN KEY (
                    equipment_id
                )
                REFERENCES equipment(id)
                ON DELETE CASCADE,

                FOREIGN KEY (
                    maintenance_anchor_work_id
                )
                REFERENCES work_records(id)
                ON DELETE SET NULL
            )
            """
        )

        # Для импортированной исторической сводки дневной график может быть
        # источником истины с определённой даты. До этой даты действует
        # обычная логика шапки work_records; начиная с неё в график/отчёты
        # попадают только дни, присутствующие в work_daily_log.
        _add_column_if_missing(
            cursor,
            "work_records",
            "daily_log_authoritative_from",
            "TEXT",
        )

        # ======================================================
        # MAINTENANCE INTERVALS
        #
        # Интервалы ТО задаются отдельно для каждой машины.
        #
        # По умолчанию позже будут создаваться:
        #
        # 50
        # 250
        # 500
        # 1000
        # 2000
        # 4000
        #
        # Пользователь сможет добавлять свои интервалы.
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS
            maintenance_intervals (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                equipment_id INTEGER NOT NULL,

                interval_hours REAL NOT NULL,

                name TEXT,

                active INTEGER DEFAULT 1,

                sort_order INTEGER DEFAULT 0,

                created_at TEXT,
                updated_at TEXT,

                FOREIGN KEY (
                    equipment_id
                )
                REFERENCES equipment(id)
                ON DELETE CASCADE
            )
            """
        )

        # ======================================================
        # WORK ATTACHMENTS
        #
        # Здесь хранится информация о файлах,
        # приложенных к карточке ремонта / ТО / простоя.
        #
        # Сам файл физически будет находиться:
        #
        # папка заказчика
        #   / Отчеты о ремонтах
        #       / Модель
        #           / Единица техники
        #               / файл
        #
        # В базе сохраняем относительный путь.
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS
            work_attachments (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                work_id INTEGER NOT NULL,

                file_name TEXT NOT NULL,

                relative_path TEXT NOT NULL,

                attachment_type TEXT
                    DEFAULT 'Отчет о ремонте',

                created_at TEXT,

                FOREIGN KEY (
                    work_id
                )
                REFERENCES work_records(id)
                ON DELETE CASCADE
            )
            """
        )

        # ======================================================
        # COMPONENTS
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS components (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                equipment_id INTEGER NOT NULL,

                component_name TEXT NOT NULL,

                serial_number TEXT,

                resource_hours REAL DEFAULT 0,

                install_machine_hours REAL DEFAULT 0,

                install_date TEXT,

                created_at TEXT,

                FOREIGN KEY (
                    equipment_id
                )
                REFERENCES equipment(id)
                ON DELETE CASCADE
            )
            """
        )

        # Разрешаем компоненты без обязательной привязки к машине и расширяем карточку.
        component_columns = {row[1]: row for row in cursor.execute("PRAGMA table_info(components)").fetchall()}
        equipment_col = component_columns.get("equipment_id")
        if equipment_col and int(equipment_col[3] or 0) == 1:
            cursor.execute("ALTER TABLE components RENAME TO components_old_optional_link")
            cursor.execute("""
                CREATE TABLE components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER, component_name TEXT NOT NULL,
                    part_number TEXT, serial_number TEXT, resource_hours REAL DEFAULT 0, install_machine_hours REAL DEFAULT 0,
                    install_date TEXT, note TEXT, created_at TEXT,
                    FOREIGN KEY(equipment_id) REFERENCES equipment(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("""INSERT INTO components(id,equipment_id,component_name,serial_number,resource_hours,install_machine_hours,install_date,created_at) SELECT id,equipment_id,component_name,serial_number,resource_hours,install_machine_hours,install_date,created_at FROM components_old_optional_link""")
            cursor.execute("DROP TABLE components_old_optional_link")
        else:
            _add_column_if_missing(cursor,"components","part_number","TEXT")
            _add_column_if_missing(cursor,"components","note","TEXT")

        # ======================================================
        # COMPONENT ATTACHMENTS
        #
        # Вложения к компонентам.
        # В первую очередь:
        # "Дефектная ведомость".
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS
            component_attachments (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                component_id INTEGER NOT NULL,

                file_name TEXT NOT NULL,

                relative_path TEXT NOT NULL,

                attachment_type TEXT
                    DEFAULT 'Дефектная ведомость',

                created_at TEXT,

                FOREIGN KEY (
                    component_id
                )
                REFERENCES components(id)
                ON DELETE CASCADE
            )
            """
        )

        # Старые версии могли сохранить внешний ключ на временную
        # таблицу components_old_optional_link после миграции components.
        # Если это произошло, безопасно пересоздаём таблицу вложений,
        # сохраняя все существующие записи.
        attachment_fks = cursor.execute(
            "PRAGMA foreign_key_list(component_attachments)"
        ).fetchall()
        if any(row[2] != "components" for row in attachment_fks):
            cursor.execute(
                """
                CREATE TABLE component_attachments_fixed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    attachment_type TEXT DEFAULT 'Дефектная ведомость',
                    created_at TEXT,
                    FOREIGN KEY(component_id)
                        REFERENCES components(id)
                        ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO component_attachments_fixed (
                    id, component_id, file_name, relative_path,
                    attachment_type, created_at
                )
                SELECT
                    id, component_id, file_name, relative_path,
                    attachment_type, created_at
                FROM component_attachments
                """
            )
            cursor.execute("DROP TABLE component_attachments")
            cursor.execute(
                "ALTER TABLE component_attachments_fixed "
                "RENAME TO component_attachments"
            )

        # ======================================================
        # CUSTOMER SETTINGS
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (

                id INTEGER PRIMARY KEY
                    CHECK (id = 1),

                backup_count INTEGER DEFAULT 30
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_name TEXT,
                action TEXT NOT NULL,
                entity TEXT,
                details TEXT
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)"
        )
                
        # ======================================================
        # EQUIPMENT MIGRATIONS
        # ======================================================

        _add_column_if_missing(
            cursor,
            "equipment",
            "registration_number",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "manufacture_year",
            "INTEGER",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "current_hours",
            "REAL DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "status",
            "TEXT DEFAULT 'В работе'",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "note",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "shift_hours_per_day",
            "REAL DEFAULT 22",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "auto_maintenance",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "created_at",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "equipment",
            "updated_at",
            "TEXT",
        )

        # ======================================================
        # WORK RECORDS MIGRATIONS
        # ======================================================

        _add_column_if_missing(
            cursor,
            "work_records",
            "request_number",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "repair_type",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "date_start",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "date_end",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "in_progress",
            "INTEGER DEFAULT 1",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "machine_hours",
            "REAL DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "description",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "executors",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "requires_report",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "report_completed",
            "INTEGER DEFAULT 0",
        )

        # ------------------------------------------------------
        # Планирование работ и ТО
        # ------------------------------------------------------

        _add_column_if_missing(
            cursor,
            "work_records",
            "is_planned",
            "INTEGER DEFAULT 0",
        )

        # Плановая запись сама по себе не означает фактический простой.
        # is_started становится 1 только после команды «Начать ТО».
        _add_column_if_missing(
            cursor,
            "work_records",
            "is_started",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "is_auto_generated",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "maintenance_interval",
            "REAL",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "maintenance_target_hours",
            "REAL",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "maintenance_anchor_work_id",
            "INTEGER",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "source_maintenance_work_id",
            "INTEGER",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "created_at",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "work_records",
            "updated_at",
            "TEXT",
        )

        # ======================================================
        # COMPONENT MIGRATIONS
        # ======================================================

        _add_column_if_missing(
            cursor,
            "components",
            "component_name",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "components",
            "serial_number",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "components",
            "resource_hours",
            "REAL DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "components",
            "install_machine_hours",
            "REAL DEFAULT 0",
        )

        _add_column_if_missing(
            cursor,
            "components",
            "install_date",
            "TEXT",
        )

        _add_column_if_missing(
            cursor,
            "components",
            "created_at",
            "TEXT",
        )

        # ======================================================
        # SETTINGS MIGRATION
        # ======================================================

        _add_column_if_missing(
            cursor,
            "settings",
            "backup_count",
            "INTEGER DEFAULT 30",
        )

        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (
                id,
                backup_count
            )
            VALUES (
                1,
                30
            )
            """
        )

        # ======================================================
        # NORMALIZE EXISTING EQUIPMENT
        #
        # Старые машины после миграции получают сменность
        # 22 м/ч в сутки, но автоматический расчет ТО
        # остается выключенным.
        # ======================================================

        cursor.execute(
            """
            UPDATE equipment
            SET shift_hours_per_day = 22
            WHERE shift_hours_per_day IS NULL
               OR shift_hours_per_day <= 0
            """
        )

        cursor.execute(
            """
            UPDATE equipment
            SET auto_maintenance = 0
            WHERE auto_maintenance IS NULL
            """
        )

        # ======================================================
        # DEFAULT MAINTENANCE INTERVALS
        #
        # Для каждой существующей машины создаем стандартный
        # набор интервалов.
        #
        # Это НЕ создает работы ТО.
        # Автоматические ТО появятся только после:
        #
        # 1. включения "Автоматически рассчитывать ТО";
        # 2. ручного создания первого фактического ТО.
        # ======================================================

        default_intervals = (
            (50, "ТО-50", 10),
            (250, "ТО-250", 20),
            (500, "ТО-500", 30),
            (1000, "ТО-1000", 40),
            (2000, "ТО-2000", 50),
            (4000, "ТО-4000", 60),
        )

        cursor.execute(
            """
            SELECT id
            FROM equipment
            """
        )

        equipment_rows = (
            cursor.fetchall()
        )

        for equipment_row in equipment_rows:
            equipment_id = (
                equipment_row["id"]
            )

            for (
                interval_hours,
                interval_name,
                sort_order,
            ) in default_intervals:

                cursor.execute(
                    """
                    SELECT id
                    FROM maintenance_intervals
                    WHERE equipment_id = ?
                      AND interval_hours = ?
                    LIMIT 1
                    """,
                    (
                        equipment_id,
                        interval_hours,
                    ),
                )

                existing_interval = (
                    cursor.fetchone()
                )

                if existing_interval is not None:
                    continue

                cursor.execute(
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
                        ?,
                        ?,
                        ?,
                        1,
                        ?,
                        datetime('now'),
                        datetime('now')
                    )
                    """,
                    (
                        equipment_id,
                        interval_hours,
                        interval_name,
                        sort_order,
                    ),
                )                       

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_equipment_garage_number
            ON equipment(garage_number)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_equipment_model
            ON equipment(model)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_equipment_serial_number
            ON equipment(serial_number)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_equipment_status
            ON equipment(status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_equipment_id
            ON work_records(equipment_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_date_start
            ON work_records(date_start)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_date_end
            ON work_records(date_end)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_in_progress
            ON work_records(in_progress)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_repair_type
            ON work_records(repair_type)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_planned
            ON work_records(is_planned)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_auto_generated
            ON work_records(is_auto_generated)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_maintenance_target
            ON work_records(
                equipment_id,
                maintenance_target_hours
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_maintenance_intervals_equipment
            ON maintenance_intervals(
                equipment_id
            )
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_maintenance_interval_unique
            ON maintenance_intervals(
                equipment_id,
                interval_hours
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_attachments_work
            ON work_attachments(
                work_id
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_components_equipment_id
            ON components(
                equipment_id
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_component_attachments_component
            ON component_attachments(
                component_id
            )
            """
        )

        # ======================================================
        # WORK DAILY LOG
        # Ежедневное состояние внутри одной карточки ремонта.
        # ======================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS work_daily_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                day_type TEXT NOT NULL DEFAULT 'Простой',
                description TEXT,
                executors TEXT,
                machine_hours REAL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(work_id)
                    REFERENCES work_records(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_work_daily_log_unique_day
            ON work_daily_log(work_id, work_date)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_work_daily_log_date
            ON work_daily_log(work_date)
            """
        )

        # Безопасная миграция старой истории: для каждой существующей
        # карточки создаём исходную дневную запись на дату начала.
        cursor.execute(
            """
            INSERT OR IGNORE INTO work_daily_log (
                work_id, work_date, day_type, description,
                executors, machine_hours, created_at, updated_at
            )
            SELECT
                id,
                date_start,
                CASE
                    WHEN repair_type = 'Аварийный' THEN 'Аварийный ремонт'
                    WHEN repair_type = 'Плановый' THEN 'Плановый ремонт'
                    WHEN repair_type = 'Работы заказчика' THEN 'Работы заказчика'
                    ELSE COALESCE(NULLIF(repair_type, ''), 'Простой')
                END,
                description,
                executors,
                machine_hours,
                created_at,
                updated_at
            FROM work_records
            WHERE date_start IS NOT NULL
              AND TRIM(date_start) <> ''
            """
        )

        # ======================================================
        # WORK REPORT ATTACHMENTS
        # ======================================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS work_report_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY(work_id) REFERENCES work_records(id)
                    ON DELETE CASCADE
            )
            """
        )

        # ======================================================
        # NOTIFICATION CENTER / USER REMINDERS
        # ======================================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                remind_at TEXT NOT NULL,
                repeat_rule TEXT NOT NULL DEFAULT 'once',
                priority TEXT NOT NULL DEFAULT 'normal',
                windows_notify INTEGER NOT NULL DEFAULT 1,
                is_completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                last_notified_at TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reminders_active_time
            ON reminders(is_completed, remind_at)
            """
        )

        # ======================================================
        # COMMIT
        # ======================================================

        db.commit()

        return db.path

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
