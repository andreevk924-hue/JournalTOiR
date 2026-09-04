# database/database.py

import re
import sqlite3
import sys
from pathlib import Path


def _application_root() -> Path:
    """Папка для рабочих данных.

    В исходниках это корень проекта. В собранной portable EXE — папка,
    в которой лежит Journal_TOiR.exe. Ресурсы PyInstaller при этом остаются
    внутри EXE и распаковываются во временную служебную папку автоматически.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_ROOT = _application_root()

DATA_DIR = APP_ROOT / "data"
CUSTOMERS_DIR = DATA_DIR / "customers"
ASSETS_DIR = DATA_DIR / "assets"


def get_local_data_root() -> Path:
    """Рабочая локальная папка. Читается из app_config без импорта services, чтобы не создавать циклы."""
    config_file = DATA_DIR / "app_config.json"
    try:
        import json
        with config_file.open("r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        value = str(cfg.get("storage", {}).get("local_root", "") or "").strip()
        if value:
            return Path(value).expanduser().resolve()
    except Exception:
        pass
    return DATA_DIR


def get_customers_dir() -> Path:
    return get_local_data_root() / "customers"

ORGANIZATION_CONFIG = DATA_DIR / "organization.json"

DEFAULT_CUSTOMER = "Основной заказчик"


def sanitize_folder_name(name: str) -> str:
    name = str(name or "").strip()

    if not name:
        raise ValueError(
            "Наименование заказчика не указано."
        )

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name,
    )

    name = name.rstrip(". ")

    if not name:
        raise ValueError(
            "Некорректное наименование заказчика."
        )

    return name


def get_customer_dir(
    customer_name: str,
) -> Path:
    folder_name = sanitize_folder_name(
        customer_name
    )

    return get_customers_dir() / folder_name


def get_customer_db_path(
    customer_name: str,
) -> Path:
    return (
        get_customer_dir(customer_name)
        / "journaltoir.db"
    )


def get_customer_backup_dir(
    customer_name: str,
) -> Path:
    return (
        get_customer_dir(customer_name)
        / "backups"
    )


class Database:
    def __init__(
        self,
        customer_name: str | None = None,
        db_path: str | Path | None = None,
    ):
        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        get_customers_dir().mkdir(
            parents=True,
            exist_ok=True,
        )

        ASSETS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        if db_path is not None:
            self.db_path = Path(
                db_path
            ).resolve()

            self.customer_name = (
                customer_name or ""
            )

        else:
            self.customer_name = (
                customer_name
                or DEFAULT_CUSTOMER
            )

            self.db_path = (
                get_customer_db_path(
                    self.customer_name
                )
            )

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.db_path
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self.connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        self.connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        self.connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        self.connection.execute(
            "PRAGMA busy_timeout = 5000"
        )

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def backup_to(
        self,
        destination,
    ):
        destination = Path(
            destination
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        backup_connection = (
            sqlite3.connect(
                destination
            )
        )

        try:
            self.connection.backup(
                backup_connection
            )

        finally:
            backup_connection.close()

    def check_connection(self):
        try:
            cursor = (
                self.connection.execute(
                    "SELECT 1"
                )
            )

            row = cursor.fetchone()

            return (
                row is not None
                and row[0] == 1
            )

        except sqlite3.Error:
            return False

    @property
    def path(self) -> Path:
        return self.db_path

    @property
    def backup_dir(self) -> Path:
        if self.customer_name:
            return get_customer_backup_dir(
                self.customer_name
            )

        return (
            self.db_path.parent
            / "backups"
        )

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

        self.close()
