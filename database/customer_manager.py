# database/customer_manager.py

import json
import shutil
from pathlib import Path

from database.database import (
    ASSETS_DIR,
    get_customers_dir,
    DATA_DIR,
    ORGANIZATION_CONFIG,
    get_customer_backup_dir,
    get_customer_db_path,
    get_customer_dir,
    sanitize_folder_name,
)


class CustomerManager:
    def __init__(self):
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

        self._ensure_config()

    # ==========================================================
    # CONFIG
    # ==========================================================

    def _default_config(self):
        return {
            "organization_name": "",
            "organization_logo": "",
            "active_customer": "",
        }

    def _ensure_config(self):
        if ORGANIZATION_CONFIG.exists():
            return

        self._save_config(
            self._default_config()
        )

    def _load_config(self):
        if not ORGANIZATION_CONFIG.exists():
            return self._default_config()

        try:
            with open(
                ORGANIZATION_CONFIG,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except (
            json.JSONDecodeError,
            OSError,
        ):
            data = self._default_config()

        default = self._default_config()

        for key, value in default.items():
            if key not in data:
                data[key] = value

        return data

    def _save_config(
        self,
        config,
    ):
        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_file = (
            ORGANIZATION_CONFIG
            .with_suffix(".tmp")
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                config,
                file,
                ensure_ascii=False,
                indent=4,
            )

        temp_file.replace(
            ORGANIZATION_CONFIG
        )

    # ==========================================================
    # ORGANIZATION
    # ==========================================================

    def get_organization_name(self):
        return (
            self._load_config()
            .get(
                "organization_name",
                "",
            )
        )

    def set_organization_name(
        self,
        name,
    ):
        config = self._load_config()

        config[
            "organization_name"
        ] = str(
            name or ""
        ).strip()

        self._save_config(config)

    def get_organization_logo(self):
        logo = (
            self._load_config()
            .get(
                "organization_logo",
                "",
            )
        )

        if not logo:
            return ""

        path = Path(logo)

        if not path.is_absolute():
            path = DATA_DIR / path

        if not path.exists():
            return ""

        return str(
            path.resolve()
        )

    def set_organization_logo(
        self,
        source_file,
    ):
        source = Path(
            source_file
        )

        if not source.exists():
            raise FileNotFoundError(
                f"Файл логотипа не найден: "
                f"{source}"
            )

        allowed_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".webp",
        }

        extension = (
            source.suffix.lower()
        )

        if extension not in (
            allowed_extensions
        ):
            raise ValueError(
                "Неподдерживаемый формат "
                "логотипа."
            )

        ASSETS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.remove_organization_logo(
            update_config=False
        )

        destination = (
            ASSETS_DIR
            / (
                "organization_logo"
                + extension
            )
        )

        shutil.copy2(
            source,
            destination,
        )

        relative_path = (
            destination.relative_to(
                DATA_DIR
            )
        )

        config = self._load_config()

        config[
            "organization_logo"
        ] = str(
            relative_path
        )

        self._save_config(config)

        return str(
            destination.resolve()
        )

    def remove_organization_logo(
        self,
        update_config=True,
    ):
        if ASSETS_DIR.exists():
            for file in (
                ASSETS_DIR.glob(
                    "organization_logo.*"
                )
            ):
                try:
                    file.unlink()
                except OSError:
                    pass

        if update_config:
            config = self._load_config()

            config[
                "organization_logo"
            ] = ""

            self._save_config(
                config
            )

    # ==========================================================
    # CUSTOMERS
    # ==========================================================

    def get_customers(self):
        customers = set()
        customers_dir = get_customers_dir()
        if customers_dir.exists():
            for path in customers_dir.iterdir():
                if path.is_dir() and not path.name.startswith("."):
                    customers.add(path.name)

        # Если сервер доступен, показываем также заказчиков, которые пока
        # отсутствуют на этом ПК. При открытии SyncService скачает их БД.
        try:
            from services.app_settings import AppSettingsManager
            cfg = AppSettingsManager().load()
            server_root = str(cfg.get("storage", {}).get("server_root", "") or "").strip()
            if server_root:
                server_customers = Path(server_root).expanduser() / "customers"
                if server_customers.exists():
                    for path in server_customers.iterdir():
                        if path.is_dir() and not path.name.startswith("."):
                            customers.add(path.name)
        except Exception:
            pass

        return sorted(customers, key=str.lower)

    def customer_exists(
        self,
        customer_name,
    ):
        folder = get_customer_dir(
            customer_name
        )

        return folder.exists()

    def create_customer(
        self,
        customer_name,
    ):
        customer_name = str(
            customer_name or ""
        ).strip()

        if not customer_name:
            raise ValueError(
                "Наименование заказчика "
                "не указано."
            )

        folder_name = (
            sanitize_folder_name(
                customer_name
            )
        )

        customer_dir = (
            get_customers_dir()
            / folder_name
        )

        if customer_dir.exists():
            raise ValueError(
                "Заказчик с таким "
                "наименованием уже существует."
            )

        customer_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        get_customer_backup_dir(
            folder_name
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        return folder_name

    def rename_customer(
        self,
        old_name,
        new_name,
    ):
        old_folder = (
            get_customer_dir(
                old_name
            )
        )

        if not old_folder.exists():
            raise FileNotFoundError(
                "Заказчик не найден."
            )

        new_folder_name = (
            sanitize_folder_name(
                new_name
            )
        )

        new_folder = (
            get_customers_dir()
            / new_folder_name
        )

        if new_folder.exists():
            raise ValueError(
                "Заказчик с таким "
                "наименованием уже существует."
            )

        old_folder.rename(
            new_folder
        )

        config = self._load_config()

        if (
            config.get(
                "active_customer"
            )
            == old_folder.name
        ):
            config[
                "active_customer"
            ] = new_folder_name

            self._save_config(
                config
            )

        return new_folder_name

    def delete_customer(
        self,
        customer_name,
    ):
        customer_dir = (
            get_customer_dir(
                customer_name
            )
        )

        if not customer_dir.exists():
            return False

        shutil.rmtree(
            customer_dir
        )

        config = self._load_config()

        if (
            config.get(
                "active_customer"
            )
            == customer_dir.name
        ):
            config[
                "active_customer"
            ] = ""

            self._save_config(
                config
            )

        return True

    # ==========================================================
    # ACTIVE CUSTOMER
    # ==========================================================

    def get_active_customer(self):
        config = self._load_config()

        customer = str(
            config.get(
                "active_customer",
                "",
            )
            or ""
        ).strip()

        if not customer:
            return ""

        customer_dir = (
            get_customer_dir(
                customer
            )
        )

        if not customer_dir.exists():
            config[
                "active_customer"
            ] = ""

            self._save_config(
                config
            )

            return ""

        return customer_dir.name

    def set_active_customer(
        self,
        customer_name,
    ):
        customer_dir = (
            get_customer_dir(
                customer_name
            )
        )

        if not customer_dir.exists():
            raise FileNotFoundError(
                "Заказчик не найден."
            )

        config = self._load_config()

        config[
            "active_customer"
        ] = customer_dir.name

        self._save_config(
            config
        )

        return customer_dir.name

    def clear_active_customer(self):
        config = self._load_config()

        config[
            "active_customer"
        ] = ""

        self._save_config(
            config
        )

    # ==========================================================
    # PATHS
    # ==========================================================

    def get_active_database_path(self):
        customer = (
            self.get_active_customer()
        )

        if not customer:
            return None

        return get_customer_db_path(
            customer
        )

    def get_active_customer_dir(self):
        customer = (
            self.get_active_customer()
        )

        if not customer:
            return None

        return get_customer_dir(
            customer
        )

    def get_active_backup_dir(self):
        customer = (
            self.get_active_customer()
        )

        if not customer:
            return None

        backup_dir = (
            get_customer_backup_dir(
                customer
            )
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return backup_dir
