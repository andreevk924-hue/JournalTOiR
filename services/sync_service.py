from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

from services.app_settings import AppSettingsManager


class SyncService:
    """Local-first синхронизация SQLite для сценария один пользователь/заказчик."""

    def __init__(self, customer_name, repository=None):
        self.customer_name = str(customer_name or "").strip()
        self.repository = repository
        self.settings = AppSettingsManager()

    @staticmethod
    def _stamp():
        return datetime.now().isoformat(sep=" ", timespec="seconds")

    def config(self):
        return self.settings.load()

    def local_db_path(self):
        from database.database import get_customer_db_path
        return Path(get_customer_db_path(self.customer_name))

    def server_db_path(self):
        config = self.config()
        root = str(config["storage"].get("server_root", "") or "").strip()
        if not root:
            return None
        return Path(root).expanduser() / "customers" / self.customer_name / "journaltoir.db"

    def server_available(self):
        path = self.server_db_path()
        if path is None:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / ".journaltoir_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def prepare_before_open(self):
        """До открытия SQLite выбираем наиболее свежую целую копию."""
        config = self.config()
        if not config["sync"].get("enabled", True):
            return "disabled"
        server = self.server_db_path()
        local = self.local_db_path()
        if server is None or not self.server_available():
            return "offline"
        local.parent.mkdir(parents=True, exist_ok=True)
        if not server.exists():
            if local.exists():
                server.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local, server)
            return "server_created"
        if not local.exists():
            shutil.copy2(server, local)
            return "downloaded"
        # Если локально нет ожидающих изменений, сервер может быть источником истины.
        dirty = bool(config["sync"].get("dirty"))
        if not dirty and server.stat().st_mtime > local.stat().st_mtime + 1:
            shutil.copy2(server, local)
            return "downloaded"
        return "ready"

    def sync_now(self, force=False):
        config = self.config()
        if not config["sync"].get("enabled", True):
            return {"ok": True, "state": "disabled"}
        server = self.server_db_path()
        if server is None:
            return {"ok": False, "state": "not_configured", "error": "Серверная папка не настроена"}
        if not self.server_available():
            self.settings.set_sync_error("Сервер недоступен")
            return {"ok": False, "state": "offline", "error": "Сервер недоступен"}
        local = self.local_db_path()
        if not local.exists():
            return {"ok": False, "state": "no_local", "error": "Локальная база не найдена"}
        dirty = bool(config["sync"].get("dirty"))
        if not dirty and not force and server.exists():
            return {"ok": True, "state": "synced", "time": config["sync"].get("last_sync", "")}
        server.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.repository is not None and getattr(self.repository, "connection", None) is not None:
                destination = sqlite3.connect(server)
                try:
                    self.repository.connection.backup(destination)
                    destination.commit()
                finally:
                    destination.close()
            else:
                source = sqlite3.connect(local)
                destination = sqlite3.connect(server)
                try:
                    source.backup(destination)
                    destination.commit()
                finally:
                    source.close(); destination.close()
            now = self._stamp()
            self.settings.clear_dirty(now, now)
            return {"ok": True, "state": "synced", "time": now}
        except Exception as exc:
            self.settings.set_sync_error(exc)
            return {"ok": False, "state": "error", "error": str(exc)}

    def status(self):
        config = self.config()
        enabled = config["sync"].get("enabled", True)
        dirty = bool(config["sync"].get("dirty"))
        online = self.server_available() if enabled else False
        if not enabled:
            label = "Синхронизация выключена"
        elif not online:
            label = "Работа локально · сервер недоступен"
        elif dirty:
            label = "Есть изменения · ожидает синхронизации"
        else:
            label = "Синхронизировано"
        return {
            "enabled": enabled,
            "online": online,
            "dirty": dirty,
            "label": label,
            "last_sync": config["sync"].get("last_sync", ""),
            "last_error": config["sync"].get("last_error", ""),
        }
