import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from database.database import APP_ROOT, DATA_DIR


APP_CONFIG_FILE = DATA_DIR / "app_config.json"


class AppSettingsManager:
    """Локальные настройки приложения, не зависящие от БД заказчика."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not APP_CONFIG_FILE.exists():
            self.save(self.default_config())

    def default_config(self):
        return {
            "setup_complete": False,
            "organization_name": "",
            "user": {
                "full_name": "",
                "position": "",
                "email": "",
                "phone": "",
            },
            "security": {
                "pin_enabled": False,
                "pin_salt": "",
                "pin_hash": "",
                "remember_device": False,
            },
            "storage": {
                "server_root": "",
                "local_root": str((APP_ROOT / "data").resolve()),
                "backup_root": str((APP_ROOT / "data" / "backups").resolve()),
                "backup_count": 20,
            },
            "sync": {
                "enabled": True,
                "dirty": False,
                "last_sync": "",
                "last_error": "",
                "last_server_seen": "",
            },
            "ui": {
                "theme": "light",
                "animations": True,
                "compact": False,
                "last_page": 0,
                "sidebar_pinned": True,
                "sidebar_expanded": True,
                "quick_actions": ["add_equipment", "add_work", "reports", "settings"],
            },
            "email": {
                "provider": "outlook",
                "customer_templates": {},
            },
            "active_customer": "",
            "recent_customers": [],
        }

    def load(self):
        default = self.default_config()
        try:
            with APP_CONFIG_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, TypeError):
            data = {}
        return self._merge(default, data)

    def _merge(self, base, override):
        result = dict(base)
        for key, value in (override or {}).items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = self._merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self, config):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = APP_CONFIG_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=4)
        tmp.replace(APP_CONFIG_FILE)

    def update(self, **sections):
        config = self.load()
        for key, value in sections.items():
            if isinstance(config.get(key), dict) and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value
        self.save(config)
        return config

    def set_setup_complete(self, complete=True):
        return self.update(setup_complete=bool(complete))

    def set_active_customer(self, customer):
        customer = str(customer or "").strip()
        config = self.load()
        config["active_customer"] = customer
        recent = [x for x in config.get("recent_customers", []) if x != customer]
        if customer:
            recent.insert(0, customer)
        config["recent_customers"] = recent[:5]
        self.save(config)


    def migrate_local_root(self, old_root, new_root):
        old_root = Path(str(old_root or "")).expanduser()
        new_root = Path(str(new_root or "")).expanduser()
        if not str(new_root):
            return
        new_root.mkdir(parents=True, exist_ok=True)
        if old_root.resolve() == new_root.resolve():
            return
        source = old_root / "customers"
        destination = new_root / "customers"
        if not source.exists():
            destination.mkdir(parents=True, exist_ok=True)
            return
        import shutil
        destination.mkdir(parents=True, exist_ok=True)
        for customer in source.iterdir():
            if not customer.is_dir():
                continue
            target = destination / customer.name
            if not target.exists():
                shutil.copytree(customer, target)
            else:
                # Ничего не перезаписываем автоматически: существующая папка может быть актуальнее.
                for file in customer.iterdir():
                    dst = target / file.name
                    if file.is_file() and not dst.exists():
                        shutil.copy2(file, dst)

    def set_pin(self, pin=None, enabled=False):
        config = self.load()
        security = config["security"]
        security["pin_enabled"] = bool(enabled)
        if enabled:
            pin = str(pin or "")
            if not pin.isdigit() or not 4 <= len(pin) <= 6:
                raise ValueError("PIN должен содержать от 4 до 6 цифр.")
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 180_000)
            security["pin_salt"] = salt.hex()
            security["pin_hash"] = digest.hex()
        else:
            security["pin_salt"] = ""
            security["pin_hash"] = ""
        self.save(config)

    def verify_pin(self, pin):
        security = self.load()["security"]
        if not security.get("pin_enabled"):
            return True
        try:
            salt = bytes.fromhex(security.get("pin_salt", ""))
            expected = bytes.fromhex(security.get("pin_hash", ""))
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", str(pin or "").encode("utf-8"), salt, 180_000
        )
        return hmac.compare_digest(digest, expected)

    def get_email_template(self, customer, report_name=None):
        """Возвращает eMail-шаблон для конкретного отчёта."""
        config = self.load()
        customer = str(customer or "").strip()
        report_name = str(report_name or "").strip()
        templates = config.get("email", {}).get("customer_templates", {})
        stored = dict(templates.get(customer, {}) or {})
        if not stored:
            return {}

        # Совместимость со старым плоским форматом.
        if "reports" not in stored and "default" not in stored:
            return dict(stored)

        if report_name:
            specific = dict((stored.get("reports", {}) or {}).get(report_name, {}) or {})
            if specific:
                return specific
        return dict(stored.get("default", {}) or {})

    def set_email_template(self, customer, template, report_name=None):
        customer = str(customer or "").strip()
        report_name = str(report_name or "").strip()
        if not customer:
            raise ValueError("Не выбран заказчик.")

        config = self.load()
        email = config.setdefault("email", {})
        templates = email.setdefault("customer_templates", {})
        current = dict(templates.get(customer, {}) or {})

        if current and "reports" not in current and "default" not in current:
            current = {"default": current, "reports": {}}
        else:
            current.setdefault("default", {})
            current.setdefault("reports", {})

        if report_name:
            current["reports"][report_name] = dict(template or {})
        else:
            current["default"] = dict(template or {})

        templates[customer] = current
        email["provider"] = "outlook"
        self.save(config)
        return dict(template or {})

    def has_specific_email_template(self, customer, report_name):
        config = self.load()
        templates = config.get("email", {}).get("customer_templates", {})
        stored = dict(templates.get(str(customer or "").strip(), {}) or {})
        return bool((stored.get("reports", {}) or {}).get(str(report_name or "").strip()))

    def mark_dirty(self):
        self.update(sync={"dirty": True})

    def clear_dirty(self, when="", server_seen=""):
        self.update(sync={
            "dirty": False,
            "last_sync": when,
            "last_server_seen": server_seen or when,
            "last_error": "",
        })

    def set_sync_error(self, error):
        self.update(sync={"last_error": str(error or "")})
