from pathlib import Path

def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Не найден фрагмент для правки: {label}")
    return text.replace(old, new, 1)

# ---------- Settings page ----------
p = Path("gui/pages/settings_page.py")
s = p.read_text(encoding="utf-8")

# Сначала заменяем существующие формы, чтобы не затронуть helper, добавляемый ниже.
s = s.replace("layout = QFormLayout(group)", "layout = self._create_form_layout(group)")

s = replace_once(
    s,
    """    def __init__(self):
        super().__init__()
        self.create_ui()

""",
    """    def __init__(self):
        super().__init__()
        self.create_ui()

    @staticmethod
    def _create_form_layout(group):
        layout = QFormLayout(group)
        layout.setContentsMargins(12, 22, 12, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return layout

""",
    "settings form helper",
)

s = replace_once(
    s,
    '''        self.sync_status = QLabel("—"); self.sync_status.setObjectName("muted")
        self.last_sync = QLabel("—"); self.last_sync.setObjectName("muted")
''',
    '''        self.sync_status = QLabel("—"); self.sync_status.setObjectName("muted"); self.sync_status.setWordWrap(True); self.sync_status.setMinimumWidth(0)
        self.last_sync = QLabel("—"); self.last_sync.setObjectName("muted"); self.last_sync.setWordWrap(True); self.last_sync.setMinimumWidth(0)
''',
    "sync labels wrapping",
)

s = replace_once(
    s,
    """    def set_all_settings(self, cfg, customer, sync_status=None):
""",
    """    def set_sync_controls_enabled(self, enabled: bool):
        enabled = bool(enabled)
        self.btn_test_server.setEnabled(enabled)
        self.btn_sync_now.setEnabled(enabled)
        self.btn_sync_now.setText("Синхронизировать сейчас" if enabled else "Синхронизация…")

    def set_all_settings(self, cfg, customer, sync_status=None):
""",
    "sync controls method",
)
p.write_text(s, encoding="utf-8")

# ---------- Main window ----------
p = Path("gui/main_window.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    """        self._sync_worker_thread = None
        self._sync_message_requested = False
        self._sync_bridge = _SyncSignalBridge(self)
""",
    """        self._sync_worker_thread = None
        self._sync_message_requested = False
        self._sync_started_at = None
        self._sync_bridge = _SyncSignalBridge(self)
""",
    "sync started field",
)

s = replace_once(
    s,
    """        self.settings_page.set_all_settings(cfg, self.customer_name, self.sync_service.status())
        if hasattr(self.home_page, "apply_quick_actions"):
""",
    """        self.settings_page.set_all_settings(cfg, self.customer_name, self.sync_service.status())
        self._refresh_sync_widgets()
        if hasattr(self.home_page, "apply_quick_actions"):
""",
    "refresh sync widgets on settings load",
)

s = replace_once(
    s,
    """    def test_server_connection(self):
""",
    """    def _refresh_sync_widgets(self, busy_text=None):
        if not hasattr(self, "settings_page"):
            return
        busy = self._sync_worker_thread is not None and self._sync_worker_thread.is_alive()
        self.settings_page.set_sync_controls_enabled(not busy)
        if busy:
            text = busy_text or "Идёт синхронизация…"
            self.settings_page.sync_status.setText(text)
            return
        status = self.sync_service.status()
        self.settings_page.sync_status.setText(status["label"])
        self.settings_page.last_sync.setText(status.get("last_sync") or "Ещё не выполнялась")

    def test_server_connection(self):
""",
    "sync widgets helper",
)

s = replace_once(
    s,
    """        finally:
            self.app_settings.save(original)
        QMessageBox.information(self, "Сервер", "Серверная папка доступна для чтения и записи." if ok else "Серверная папка недоступна.")
""",
    """        finally:
            self.app_settings.save(original)
        self.sync_service.set_online_cache(ok)
        self.update_statusbar()
        self._refresh_sync_widgets()
        QMessageBox.information(self, "Сервер", "Серверная папка доступна для чтения и записи." if ok else "Серверная папка недоступна.")
""",
    "server test status",
)

s = replace_once(
    s,
    """        if not force and not cfg.get("sync", {}).get("dirty"):
            self.update_statusbar()
            return {
""",
    """        if not force and not cfg.get("sync", {}).get("dirty"):
            self.update_statusbar()
            self._refresh_sync_widgets()
            return {
""",
    "sync no-op UI",
)

s = replace_once(
    s,
    """        if self._sync_worker_thread is not None and self._sync_worker_thread.is_alive():
            self._sync_message_requested = self._sync_message_requested or show_message
            return {"ok": True, "state": "busy"}
""",
    """        if self._sync_worker_thread is not None and self._sync_worker_thread.is_alive():
            self._sync_message_requested = self._sync_message_requested or show_message
            self._refresh_sync_widgets("Идёт синхронизация…")
            return {"ok": True, "state": "busy"}
""",
    "sync busy UI",
)

s = replace_once(
    s,
    """        self._sync_worker_thread = threading.Thread(
            target=worker,
            name=f"JournalTOiR-Sync-{customer_name}",
            daemon=True,
        )
        if hasattr(self, "status_sync"):
            self.status_sync.setText("↻ Синхронизация в фоне…")
        self._sync_worker_thread.start()
""",
    """        self._sync_worker_thread = threading.Thread(
            target=worker,
            name=f"JournalTOiR-Sync-{customer_name}",
            daemon=True,
        )
        self._sync_started_at = datetime.now()
        if hasattr(self, "status_sync"):
            self.status_sync.setText("↻ Идёт синхронизация…")
        self._refresh_sync_widgets("Идёт синхронизация…")
        self._sync_worker_thread.start()
""",
    "sync start UI",
)

s = replace_once(
    s,
    """    def _sync_finished(self, result):
        self._sync_worker_thread = None

""",
    """    def _sync_finished(self, result):
        self._sync_worker_thread = None
        self._sync_started_at = None

""",
    "sync finished state",
)

s = replace_once(
    s,
    """        if "online" in result:
            self.sync_service.set_online_cache(result.get("online"))

        self.update_statusbar()
        if hasattr(self.settings_page, "sync_status"):
            status = self.sync_service.status()
            self.settings_page.sync_status.setText(status["label"])
            self.settings_page.last_sync.setText(status.get("last_sync") or "Ещё не выполнялась")

""",
    """        if "online" in result:
            self.sync_service.set_online_cache(result.get("online"))

        if result.get("ok") and result.get("time"):
            self.app_settings.clear_dirty(result.get("time"), result.get("time"))

        self.update_statusbar()
        self._refresh_sync_widgets()

""",
    "sync finished UI and dirty clear",
)

s = replace_once(
    s,
    """        except Exception:
            # Ошибка фоновой синхронизации не должна мешать локальной работе.
            self.update_statusbar()

    def _manual_backup(self):
""",
    """        except Exception:
            # Ошибка фоновой синхронизации не должна мешать локальной работе.
            self.update_statusbar()
            self._refresh_sync_widgets()

    def _manual_backup(self):
""",
    "background sync error UI",
)

s = replace_once(
    s,
    """        sync = self.sync_service.status()
        marker = "●" if sync["online"] is True else "○"
        self.status_sync.setText(f"{marker} {sync['label']}")
        user = self.app_settings.load().get("user", {})
""",
    """        if self._sync_worker_thread is not None and self._sync_worker_thread.is_alive():
            self.status_sync.setText("↻ Идёт синхронизация…")
        else:
            sync = self.sync_service.status()
            marker = "●" if sync["online"] is True else "○"
            self.status_sync.setText(f"{marker} {sync['label']}")
        user = self.app_settings.load().get("user", {})
""",
    "status bar busy state",
)

p.write_text(s, encoding="utf-8")
print("sync UI v2 fixes applied")


# ============================================================
# V3: быстрый snapshot -> последовательная SMB-передача
# ============================================================

FINAL_SYNC_SERVICE = r'''from datetime import datetime
from pathlib import Path
import os
import shutil
import sqlite3
import tempfile
import time

from services.app_settings import AppSettingsManager


class SyncService:
    """Local-first синхронизация SQLite для сценария один пользователь/заказчик.

    Рабочая SQLite всегда остаётся локальной. На сервер передаётся готовый
    локальный snapshot одним последовательным файлом, после чего staging-файл
    атомарно заменяет серверную базу.
    """

    COPY_BUFFER_SIZE = 8 * 1024 * 1024

    def __init__(self, customer_name, repository=None):
        self.customer_name = str(customer_name or "").strip()
        self.repository = repository
        self.settings = AppSettingsManager()
        self._online_cache = None

    @staticmethod
    def _stamp():
        return datetime.now().isoformat(sep=" ", timespec="seconds")

    @staticmethod
    def _report(progress, phase, percent=None, detail=""):
        if progress is None:
            return
        payload = {
            "phase": str(phase or ""),
            "percent": None if percent is None else max(0, min(100, int(percent))),
            "detail": str(detail or ""),
        }
        try:
            progress(payload)
        except Exception:
            pass

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
            self._online_cache = False
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / ".journaltoir_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            self._online_cache = True
            return True
        except OSError:
            self._online_cache = False
            return False

    def set_online_cache(self, value):
        if value is None:
            return
        self._online_cache = bool(value)

    def prepare_before_open(self):
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
        dirty = bool(config["sync"].get("dirty"))
        if not dirty and server.stat().st_mtime > local.stat().st_mtime + 1:
            shutil.copy2(server, local)
            return "downloaded"
        return "ready"

    def _create_local_snapshot(self, local, progress=None):
        local.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".journaltoir_sync_",
            suffix=".db",
            dir=str(local.parent),
        )
        os.close(fd)
        snapshot = Path(tmp_name)

        source = None
        destination = None
        last_percent = -10
        try:
            source = sqlite3.connect(str(local), timeout=15)
            source.execute("PRAGMA busy_timeout = 15000")
            destination = sqlite3.connect(str(snapshot), timeout=15)

            def backup_progress(_status, remaining, total):
                nonlocal last_percent
                if total:
                    percent = int(((total - remaining) * 100) / total)
                else:
                    percent = 100 if remaining == 0 else 0
                if percent >= last_percent + 5 or remaining == 0:
                    last_percent = percent
                    self._report(
                        progress,
                        "snapshot",
                        percent,
                        "Создание локального снимка базы",
                    )

            source.backup(
                destination,
                pages=1024,
                progress=backup_progress,
                sleep=0.001,
            )
            destination.commit()
            row = destination.execute("PRAGMA quick_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                raise RuntimeError("Локальный снимок базы не прошёл проверку целостности")
            self._report(progress, "snapshot", 100, "Локальный снимок готов")
            return snapshot
        except Exception:
            try:
                snapshot.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            if destination is not None:
                destination.close()
            if source is not None:
                source.close()

    def _copy_snapshot_to_server(self, snapshot, server, progress=None):
        server.parent.mkdir(parents=True, exist_ok=True)
        staging = server.with_name(f".{server.name}.uploading")
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass

        total = int(snapshot.stat().st_size)
        copied = 0
        self._report(
            progress,
            "upload",
            0,
            f"Передача на сервер · 0 / {max(1, total // (1024 * 1024))} МБ",
        )

        try:
            with snapshot.open("rb") as src, staging.open("wb") as dst:
                while True:
                    block = src.read(self.COPY_BUFFER_SIZE)
                    if not block:
                        break
                    dst.write(block)
                    copied += len(block)
                    percent = 100 if total <= 0 else int(copied * 100 / total)
                    copied_mb = copied / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self._report(
                        progress,
                        "upload",
                        percent,
                        f"Передача на сервер · {copied_mb:.1f} / {total_mb:.1f} МБ",
                    )
                dst.flush()

            if staging.stat().st_size != total:
                raise IOError(
                    f"Размер переданного файла не совпадает: {staging.stat().st_size} вместо {total} байт"
                )

            self._report(progress, "publish", 100, "Публикация серверной копии")
            os.replace(str(staging), str(server))
            self._online_cache = True
            return total
        except Exception:
            try:
                staging.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def sync_now(self, force=False, progress=None):
        started = time.perf_counter()
        config = self.config()
        if not config["sync"].get("enabled", True):
            return {"ok": True, "state": "disabled", "online": None}

        dirty = bool(config["sync"].get("dirty"))
        if not dirty and not force:
            return {
                "ok": True,
                "state": "synced",
                "time": config["sync"].get("last_sync", ""),
                "online": self._online_cache,
            }

        server = self.server_db_path()
        if server is None:
            self._online_cache = False
            return {
                "ok": False,
                "state": "not_configured",
                "error": "Серверная папка не настроена",
                "online": False,
            }

        self._report(progress, "checking", None, "Проверка серверной папки")
        if not self.server_available():
            self.settings.set_sync_error("Сервер недоступен")
            return {
                "ok": False,
                "state": "offline",
                "error": "Сервер недоступен",
                "online": False,
            }

        local = self.local_db_path()
        if not local.exists():
            return {
                "ok": False,
                "state": "no_local",
                "error": "Локальная база не найдена",
                "online": True,
            }

        before_snapshot = self.config()
        generation = int(before_snapshot["sync"].get("dirty_generation", 0) or 0)

        snapshot = None
        try:
            snapshot = self._create_local_snapshot(local, progress=progress)
            transferred = self._copy_snapshot_to_server(snapshot, server, progress=progress)

            now = self._stamp()
            post_config = self.settings.clear_dirty(
                now,
                now,
                expected_generation=generation,
            )
            dirty_remaining = bool(post_config.get("sync", {}).get("dirty"))
            elapsed = max(0.0, time.perf_counter() - started)
            self._online_cache = True
            self._report(progress, "done", 100, "Синхронизация завершена")
            return {
                "ok": True,
                "state": "synced_pending" if dirty_remaining else "synced",
                "time": now,
                "online": True,
                "bytes": transferred,
                "elapsed": elapsed,
                "dirty_remaining": dirty_remaining,
            }
        except Exception as exc:
            self.settings.set_sync_error(exc)
            return {
                "ok": False,
                "state": "error",
                "error": str(exc),
                "online": self._online_cache,
                "elapsed": max(0.0, time.perf_counter() - started),
            }
        finally:
            if snapshot is not None:
                try:
                    snapshot.unlink(missing_ok=True)
                except OSError:
                    pass

    def status(self):
        config = self.config()
        enabled = config["sync"].get("enabled", True)
        dirty = bool(config["sync"].get("dirty"))
        last_sync = config["sync"].get("last_sync", "")
        last_error = config["sync"].get("last_error", "")

        online = self._online_cache
        if online is None:
            if last_error:
                online = False
            elif last_sync:
                online = True

        if not enabled:
            label = "Синхронизация выключена"
        elif dirty and online is False:
            label = "Есть изменения · сервер недоступен"
        elif dirty:
            label = "Есть изменения · ожидает синхронизации"
        elif online is False:
            label = "Работа локально · сервер недоступен"
        elif online is True:
            label = "Синхронизировано"
        else:
            label = "Сервер ещё не проверен"
        return {
            "enabled": enabled,
            "online": online,
            "dirty": dirty,
            "label": label,
            "last_sync": last_sync,
            "last_error": last_error,
        }
'''

Path("services/sync_service.py").write_text(FINAL_SYNC_SERVICE, encoding="utf-8")

# --- app_settings: generation + защита одновременной записи config ---
p = Path("services/app_settings.py")
s = p.read_text(encoding="utf-8")
s = replace_once(s, "import secrets\nfrom pathlib import Path\n", "import secrets\nimport threading\nfrom pathlib import Path\n", "settings threading import")
s = replace_once(s, 'APP_CONFIG_FILE = DATA_DIR / "app_config.json"\n', 'APP_CONFIG_FILE = DATA_DIR / "app_config.json"\n_CONFIG_LOCK = threading.RLock()\n', "config lock")
s = replace_once(
    s,
    '''            "sync": {
                "enabled": True,
                "dirty": False,
                "last_sync": "",
''',
    '''            "sync": {
                "enabled": True,
                "dirty": False,
                "dirty_generation": 0,
                "last_sync": "",
''',
    "dirty generation default",
)

start = s.index("    def load(self):\n")
end = s.index("    def set_setup_complete", start)
locked_methods = '''    def load(self):
        with _CONFIG_LOCK:
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
        with _CONFIG_LOCK:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = APP_CONFIG_FILE.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(config, fh, ensure_ascii=False, indent=4)
            tmp.replace(APP_CONFIG_FILE)

    def update(self, **sections):
        with _CONFIG_LOCK:
            config = self.load()
            for key, value in sections.items():
                if isinstance(config.get(key), dict) and isinstance(value, dict):
                    config[key].update(value)
                else:
                    config[key] = value
            self.save(config)
            return config

'''
s = s[:start] + locked_methods + s[end:]

old_dirty = '''    def mark_dirty(self):
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
'''
new_dirty = '''    def mark_dirty(self):
        with _CONFIG_LOCK:
            config = self.load()
            sync = config.setdefault("sync", {})
            sync["dirty"] = True
            sync["dirty_generation"] = int(sync.get("dirty_generation", 0) or 0) + 1
            self.save(config)
            return config

    def clear_dirty(self, when="", server_seen="", expected_generation=None):
        with _CONFIG_LOCK:
            config = self.load()
            sync = config.setdefault("sync", {})
            current_generation = int(sync.get("dirty_generation", 0) or 0)
            can_clear = expected_generation is None or current_generation == int(expected_generation)
            if can_clear:
                sync["dirty"] = False
            sync["last_sync"] = when
            sync["last_server_seen"] = server_seen or when
            sync["last_error"] = ""
            self.save(config)
            return config

    def set_sync_error(self, error):
        return self.update(sync={"last_error": str(error or "")})
'''
s = replace_once(s, old_dirty, new_dirty, "dirty generation methods")
p.write_text(s, encoding="utf-8")

# --- main_window: этапы/процент и безопасная обработка новых изменений ---
p = Path("gui/main_window.py")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '''class _SyncSignalBridge(QObject):
    """Передаёт результат Python-потока обратно в Qt UI-поток."""
    finished = Signal(object)
''',
    '''class _SyncSignalBridge(QObject):
    """Передаёт прогресс и результат Python-потока обратно в Qt UI-поток."""
    progress = Signal(object)
    finished = Signal(object)
''',
    "progress signal",
)

s = replace_once(
    s,
    '''        self._sync_bridge = _SyncSignalBridge(self)
        self._sync_bridge.finished.connect(self._sync_finished)
''',
    '''        self._sync_bridge = _SyncSignalBridge(self)
        self._sync_bridge.progress.connect(self._sync_progress)
        self._sync_bridge.finished.connect(self._sync_finished)
''',
    "progress signal connection",
)

old_worker = '''        def worker():
            try:
                # Отдельный SyncService не получает repository: он открывает своё
                # SQLite-соединение и не трогает соединение главного UI-потока.
                result = SyncService(customer_name).sync_now(force=force)
            except Exception as exc:
                result = {"ok": False, "state": "error", "error": str(exc)}
            result["customer_name"] = customer_name
            try:
                self._sync_bridge.finished.emit(result)
            except RuntimeError:
                # Окно уже закрыто — локальная БД всё равно остаётся актуальной.
                pass
'''
new_worker = '''        def worker():
            def report_progress(info):
                payload = dict(info or {})
                payload["customer_name"] = customer_name
                try:
                    self._sync_bridge.progress.emit(payload)
                except RuntimeError:
                    pass

            try:
                result = SyncService(customer_name).sync_now(
                    force=force,
                    progress=report_progress,
                )
            except Exception as exc:
                result = {"ok": False, "state": "error", "error": str(exc)}
            result["customer_name"] = customer_name
            try:
                self._sync_bridge.finished.emit(result)
            except RuntimeError:
                pass
'''
s = replace_once(s, old_worker, new_worker, "fast sync worker")

marker = "    def _sync_finished(self, result):\n"
progress_method = '''    def _sync_progress(self, info):
        if info.get("customer_name") != self.customer_name:
            return
        phase = str(info.get("phase") or "")
        percent = info.get("percent")
        detail = str(info.get("detail") or "").strip()

        if detail:
            text = detail
        elif phase == "checking":
            text = "Проверка серверной папки…"
        elif phase == "snapshot":
            text = "Создание локального снимка…"
        elif phase == "upload":
            text = "Копирование на сервер…"
        elif phase == "publish":
            text = "Завершение синхронизации…"
        else:
            text = "Идёт синхронизация…"

        if percent is not None and phase in {"snapshot", "upload"} and "%" not in text:
            text = f"{text} · {int(percent)}%"

        if hasattr(self, "status_sync"):
            self.status_sync.setText(f"↻ {text}")
        self._refresh_sync_widgets(text)

'''
if marker not in s:
    raise RuntimeError("Не найден _sync_finished")
s = s.replace(marker, progress_method + marker, 1)

duplicate_clear = '''        if result.get("ok") and result.get("time"):
            # Дублируем очистку dirty-флага в UI-потоке, чтобы статус страницы
            # настроек сразу переключался на «Синхронизировано».
            self.app_settings.clear_dirty(result.get("time"), result.get("time"))

'''
if duplicate_clear in s:
    s = s.replace(duplicate_clear, "", 1)

old_success = '''            if result.get("ok"):
                QMessageBox.information(
                    self,
                    "Синхронизация",
                    "Локальная и серверная базы синхронизированы.",
                )
'''
new_success = '''            if result.get("ok"):
                elapsed = result.get("elapsed")
                size = result.get("bytes")
                details = []
                if elapsed is not None:
                    details.append(f"Время: {float(elapsed):.1f} с")
                if size is not None:
                    details.append(f"Передано: {float(size) / (1024 * 1024):.1f} МБ")
                if result.get("dirty_remaining"):
                    details.append("Во время синхронизации появились новые изменения — они будут отправлены следующим циклом.")
                message = "Локальная и серверная базы синхронизированы."
                if details:
                    message += "\\n\\n" + "\\n".join(details)
                QMessageBox.information(
                    self,
                    "Синхронизация",
                    message,
                )
'''
s = replace_once(s, old_success, new_success, "manual sync details")
p.write_text(s, encoding="utf-8")

print("V3 fast snapshot sync applied")
