# services/backup_service.py

from datetime import datetime
from pathlib import Path

from database.customer_manager import CustomerManager
from database.database import Database
from services.app_settings import AppSettingsManager


class BackupService:
    def __init__(
        self,
        customer_name=None,
        backup_count=30,
    ):
        self.customer_manager = CustomerManager()

        self.customer_name = (
            customer_name
            or self.customer_manager
            .get_active_customer()
        )

        if not self.customer_name:
            raise RuntimeError(
                "Активный заказчик не выбран."
            )

        self.backup_count = max(
            1,
            int(backup_count or 30),
        )

    def get_backup_dir(self):
        cfg = AppSettingsManager().load()
        root = str(cfg.get("storage", {}).get("backup_root", "") or "").strip()
        if root:
            backup_dir = Path(root).expanduser() / self.customer_name
        else:
            backup_dir = self.customer_manager.get_active_backup_dir()
        if backup_dir is None:
            raise RuntimeError("Не удалось определить папку резервных копий заказчика.")
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def create_backup(self):
        backup_dir = (
            self.get_backup_dir()
        )

        timestamp = (
            datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
        )

        backup_file = (
            backup_dir
            / f"JournalTOiR_{timestamp}.db"
        )

        counter = 1

        while backup_file.exists():
            backup_file = (
                backup_dir
                / (
                    f"JournalTOiR_"
                    f"{timestamp}_"
                    f"{counter}.db"
                )
            )

            counter += 1

        db = Database(
            customer_name=self.customer_name
        )

        try:
            integrity = db.connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                raise RuntimeError(f"Проверка целостности БД не пройдена: {integrity[0] if integrity else 'нет результата'}")
            db.backup_to(backup_file)

        finally:
            db.close()

        self.cleanup_old_backups()

        return backup_file

    def cleanup_old_backups(self):
        backups = self.get_backups()

        for backup in backups[
            self.backup_count:
        ]:
            try:
                backup.unlink()

            except OSError:
                pass

    def get_backups(self):
        backup_dir = (
            self.get_backup_dir()
        )

        backups = list(
            backup_dir.glob(
                "JournalTOiR_*.db"
            )
        )

        backups.sort(
            key=lambda path: (
                path.stat().st_mtime
            ),
            reverse=True,
        )

        return backups

    def get_latest_backup(self):
        backups = self.get_backups()

        if not backups:
            return None

        return backups[0]

    def restore_backup(
        self,
        backup_file,
    ):
        backup_file = Path(
            backup_file
        )

        if not backup_file.exists():
            raise FileNotFoundError(
                "Файл резервной копии "
                "не найден."
            )

        database_path = (
            self.customer_manager
            .get_active_database_path()
        )

        if database_path is None:
            raise RuntimeError(
                "Не удалось определить "
                "базу активного заказчика."
            )

        safety_backup = (
            self.create_backup()
        )

        source_db = Database(
            customer_name=(
                self.customer_name
            ),
            db_path=backup_file,
        )

        try:
            source_db.backup_to(
                database_path
            )

        except Exception:
            if (
                safety_backup
                and safety_backup.exists()
            ):
                recovery_db = Database(
                    customer_name=(
                        self.customer_name
                    ),
                    db_path=safety_backup,
                )

                try:
                    recovery_db.backup_to(
                        database_path
                    )

                finally:
                    recovery_db.close()

            raise

        finally:
            source_db.close()

        return database_path
