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
