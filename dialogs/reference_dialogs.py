from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog,QFormLayout,QVBoxLayout,QLineEdit,QLabel,QPushButton,QFileDialog,QDialogButtonBox

class ManufacturerDialog(QDialog):
    def __init__(self,parent=None,name="",country="",logo_path=""):
        super().__init__(parent); self.setWindowTitle("Производитель"); self.resize(560,420); self.logo_path=logo_path or ""
        layout=QVBoxLayout(self); form=QFormLayout(); self.name=QLineEdit(name); self.country=QLineEdit(country)
        self.preview=QLabel("Логотип не добавлен"); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumHeight(160)
        btn=QPushButton("Добавить / заменить логотип"); btn.clicked.connect(self.pick_logo)
        form.addRow("Наименование:",self.name); form.addRow("Страна:",self.country); form.addRow("Логотип:",self.preview); form.addRow("",btn); layout.addLayout(form)
        box=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); box.accepted.connect(self.accept); box.rejected.connect(self.reject); layout.addWidget(box); self.refresh()
    def pick_logo(self):
        p,_=QFileDialog.getOpenFileName(self,"Выберите логотип","","Изображения (*.png *.jpg *.jpeg *.webp)")
        if p:self.logo_path=p; self.refresh()
    def refresh(self):
        if self.logo_path and Path(self.logo_path).exists():
            self.preview.setPixmap(QPixmap(self.logo_path).scaled(300,150,Qt.KeepAspectRatio,Qt.SmoothTransformation)); self.preview.setText("")
    def data(self): return self.name.text().strip(),self.country.text().strip(),self.logo_path

class DistributorDialog(QDialog):
    def __init__(self,parent=None,name=""):
        super().__init__(parent); self.setWindowTitle("Дистрибьютор (поставщик)"); self.resize(500,160)
        layout=QVBoxLayout(self); form=QFormLayout(); self.name=QLineEdit(name); form.addRow("Наименование организации:",self.name); layout.addLayout(form)
        box=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); box.accepted.connect(self.accept); box.rejected.connect(self.reject); layout.addWidget(box)
    def data(self): return self.name.text().strip()
