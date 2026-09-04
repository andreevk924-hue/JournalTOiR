from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QLabel


class GlobalSearchDialog(QDialog):
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.result = None
        self.setWindowTitle("Глобальный поиск")
        self.resize(720, 520)
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 22, 22, 22); layout.setSpacing(12)
        title = QLabel("Поиск по базе"); title.setObjectName("pageTitle")
        self.search = QLineEdit(); self.search.setPlaceholderText("Модель, S/N, гаражный номер, компонент, описание работы…"); self.search.setMinimumHeight(42)
        self.list = QListWidget()
        layout.addWidget(title); layout.addWidget(self.search); layout.addWidget(self.list, 1)
        self.search.textChanged.connect(self.refresh); self.list.itemDoubleClicked.connect(self._open)
        self.refresh("")

    def refresh(self, text):
        q = str(text or "").strip().lower(); self.list.clear();
        equipment = self.repository.get_all_equipment()
        for row in equipment:
            hay = " ".join(str(row[k] or "") for k in ("model", "serial_number", "garage_number", "registration_number"))
            if not q or q in hay.lower():
                item = QListWidgetItem(f"🚜  {row['model']} · S/N {row['serial_number'] or '—'} · № {row['garage_number'] or '—'}")
                item.setData(Qt.UserRole, ("equipment", row["id"])); self.list.addItem(item)
        for row in self.repository.get_all_components():
            hay = " ".join(str(row[k] or "") for k in ("component_name", "serial_number", "part_number"))
            if q and q not in hay.lower(): continue
            item = QListWidgetItem(f"🔩  {row['component_name']} · {row['serial_number'] or row['part_number'] or 'без номера'}")
            item.setData(Qt.UserRole, ("component", row["id"])); self.list.addItem(item)
        if q:
            for row in self.repository.search_work(q):
                item = QListWidgetItem(f"🔧  {row['model']} №{row['garage_number']} · {row['repair_type']} · {row['description'] or ''}")
                item.setData(Qt.UserRole, ("work", row["id"])); self.list.addItem(item)

    def _open(self, item):
        self.result = item.data(Qt.UserRole); self.accept()
