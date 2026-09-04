from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView
class ComponentsPage(QWidget):
    def __init__(self): super().__init__(); self.create_ui()
    def create_ui(self):
        root=QVBoxLayout(self); root.setContentsMargins(20,20,20,20); root.setSpacing(12); title=QLabel("Компоненты"); title.setObjectName("pageTitle"); root.addWidget(title)
        bar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Поиск по компоненту, каталожному/серийному № или технике..."); self.equipment_filter=QComboBox(); self.equipment_filter.addItem("Все компоненты",None); self.btn_add=QPushButton("Добавить"); self.btn_edit=QPushButton("Редактировать"); self.btn_delete=QPushButton("Удалить"); self.btn_refresh=QPushButton("Обновить");
        for w in (self.search,self.equipment_filter,self.btn_add,self.btn_edit,self.btn_delete,self.btn_refresh):bar.addWidget(w); root.addLayout(bar)
        self.table=QTableWidget(); self.table.setColumnCount(10); self.table.setHorizontalHeaderLabels(["Техника","Компонент","Каталожный №","Серийный №","Ресурс","Установлен при","Наработка компонента","Остаток","Дата установки","Примечание"]); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.SingleSelection); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive); self.table.horizontalHeader().setStretchLastSection(True); self.table.setAlternatingRowColors(True); root.addWidget(self.table,1)
    def clear(self):self.table.setRowCount(0)
    def selected_id(self):
        r=self.table.currentRow(); return self.table.item(r,0).data(Qt.UserRole) if r>=0 and self.table.item(r,0) else None
    def select_equipment(self,equipment_id):
        i=self.equipment_filter.findData(equipment_id); self.equipment_filter.setCurrentIndex(i if i>=0 else 0)
