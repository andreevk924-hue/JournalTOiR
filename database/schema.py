"""
Структура базы данных Журнал ТОиР
Версия схемы: 0.1.0
"""

SCHEMA = [

    # -----------------------------------------
    # Заказчики
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT NOT NULL,
        folder TEXT NOT NULL,

        created_at TEXT
    );
    """,

    # -----------------------------------------
    # Пользователи
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        last_name TEXT,
        first_name TEXT,
        middle_name TEXT,

        position TEXT,

        active INTEGER DEFAULT 1,

        created_at TEXT
    );
    """,

    # -----------------------------------------
    # Техника
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        customer_id INTEGER,

        model TEXT,
        garage_number TEXT,
        serial_number TEXT,

        operating_hours INTEGER DEFAULT 0,

        notes TEXT,

        write_off_date TEXT,

        created_at TEXT,
        updated_at TEXT
    );
    """,

    # -----------------------------------------
    # Типы работ
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS work_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        name TEXT,
        color TEXT,

        affects_ktg INTEGER DEFAULT 1,

        sort_order INTEGER DEFAULT 0,

        active INTEGER DEFAULT 1
    );
    """,

    # -----------------------------------------
    # Ремонты
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        equipment_id INTEGER,
        work_type_id INTEGER,

        start_date TEXT,
        end_date TEXT,

        description TEXT,

        operating_hours INTEGER,

        performers TEXT,

        repair_report INTEGER DEFAULT 0,

        request_number TEXT,
        work_order_number TEXT,

        downtime_reason TEXT,
        downtime_reason_text TEXT,

        created_by INTEGER,
        updated_by INTEGER,

        created_at TEXT,
        updated_at TEXT
    );
    """,

    # -----------------------------------------
    # Настройки
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """,

    # -----------------------------------------
    # Журнал синхронизации
    # -----------------------------------------

    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        event_time TEXT,
        event_type TEXT,
        description TEXT
    );
    """
]
