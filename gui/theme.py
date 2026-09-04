from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPalette


_RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
_ICON_ROOT = _RESOURCE_ROOT / "icons" / "tabler"

_ICON_MAP = {
    "home": "home.svg",
    "bell": "bell.svg",
    "notification": "bell.svg",
    "equipment": "truck.svg",
    "factory": "building-factory.svg",
    "supplier": "building-warehouse.svg",
    "distributor": "building-warehouse.svg",
    "component": "settings.svg",
    "cube": "settings.svg",
    "check_engine": "settings.svg",
    "work": "tools.svg",
    "repair": "tools.svg",
    "repair_alt": "tools.svg",
    "downtime": "tools.svg",
    "customer": "briefcase.svg",
    "customer_wrench": "briefcase.svg",
    "details": "list-details.svg",
    "maintenance": "calendar-check.svg",
    "schedule": "table.svg",
    "report": "chart-bar.svg",
    "chart": "chart-bar.svg",
    "settings": "settings.svg",
    "user": "user.svg",
    "search": "search.svg",
    "switch": "switch-horizontal.svg",
    "menu": "menu-2.svg",
    "mail": "mail.svg",
    "pin": "list-details.svg",
}


def create_app_icon() -> QIcon:
    for name in ("app_icon.ico", "app_icon.png"):
        path = _RESOURCE_ROOT / name
        if path.exists():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1F62BD"))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawEllipse(QRectF(19, 19, 26, 26))
    painter.end()
    return QIcon(pixmap)


def _tinted_svg(path: Path, color: QColor, size: int) -> QIcon:
    icon = QIcon(str(path))
    if icon.isNull():
        return QIcon()

    side = max(16, int(size))
    pixmap = icon.pixmap(side * 2, side * 2)
    pixmap.setDevicePixelRatio(2.0)

    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)


def create_nav_icon(kind: str, stroke_color="#B9C8DC", size=22) -> QIcon:
    filename = _ICON_MAP.get(str(kind or "").lower(), "settings.svg")
    path = _ICON_ROOT / filename
    if path.exists():
        icon = _tinted_svg(path, QColor(stroke_color), int(size))
        if not icon.isNull():
            return icon

    pixmap = QPixmap(int(size), int(size))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(QColor(stroke_color), max(1.5, int(size) / 12)))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QRectF(3, 3, int(size) - 6, int(size) - 6))
    painter.end()
    return QIcon(pixmap)


_COMMON = r"""
* { font-family:'Segoe UI Variable','Segoe UI','Arial'; font-size:12px; }
QPushButton { border-radius:7px; padding:6px 12px; min-height:20px; }
QPushButton[primary="true"] { color:white; font-weight:650; }
QPushButton[danger="true"] { color:#BC4050; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit,QTimeEdit {
    border-radius:7px; padding:6px 9px; min-height:20px;
}
QFrame#statCard,QFrame#contentCard,QFrame#homeCalendar,QFrame#quickActions,QFrame#card,QGroupBox {
    border-radius:9px;
}
QTableWidget,QTableView,QTreeWidget { border-radius:8px; }
QHeaderView::section { padding:8px 7px; font-weight:650; }
QScrollBar:vertical { width:9px; margin:2px; }
QScrollBar:horizontal { height:9px; margin:2px; }
QScrollBar::add-line,QScrollBar::sub-line { width:0; height:0; }
QLabel#pageTitle { font-size:24px; font-weight:700; }
QLabel#sectionTitle,QLabel#cardTitle { font-size:14px; font-weight:700; }
QLabel#kpiValue { font-size:28px; font-weight:700; }
QLabel#homeOrganization { font-size:23px; font-weight:700; }
QLabel#homeGreeting { font-size:17px; font-weight:650; }
"""

LIGHT_QSS = _COMMON + r"""
QMainWindow,QDialog,QWidget#appShell,QWidget#appBody,QStackedWidget { background:#F4F7FA; color:#17324D; }
QWidget { color:#17324D; }
QWidget#appTitleBar { background:#F4F7FA; border-bottom:1px solid #DCE4EC; }
QWidget#navPanel { background:#0B1D30; border-right:1px solid #17304B; }
QWidget#navPanel QLabel { color:#D4DFEB; }
QLabel#brandTitle { color:#FFFFFF; font-size:16px; font-weight:700; }
QLabel#brandMeta { color:#8FA4BC; font-size:10px; }
QWidget#navPanel QListWidget { background:transparent; border:none; outline:none; }
QWidget#navPanel QListWidget::item { min-height:38px; padding:2px 10px; margin:1px; border-radius:6px; color:#D4DFEB; }
QWidget#navPanel QListWidget::item:hover:enabled { background:#15324F; color:#FFFFFF; }
QWidget#navPanel QListWidget::item:selected:enabled { background:#0E4D91; color:#FFFFFF; }
QWidget#navPanel QListWidget::item:disabled { color:#7C96B0; background:transparent; font-size:9px; font-weight:700; }
QWidget#navPanel QPushButton { background:transparent; color:#CFDBE8; border:1px solid transparent; }
QWidget#navPanel QPushButton:hover { background:#15324F; color:#FFFFFF; }
QFrame#statCard,QFrame#contentCard,QFrame#homeCalendar,QFrame#quickActions,QFrame#card,QGroupBox {
    background:#FFFFFF; border:1px solid #DCE4EC;
}
QFrame#feedItem { background:#FBFCFD; border:1px solid #E4E9EF; border-radius:6px; }
QPushButton { background:#FFFFFF; border:1px solid #D6DFE8; color:#1D3551; }
QPushButton:hover { background:#F7F9FC; border-color:#AEBECC; }
QPushButton[primary="true"] { background:#1F62BD; border-color:#1F62BD; }
QPushButton[primary="true"]:hover { background:#1956AA; }
QPushButton[danger="true"] { background:#FFF7F8; border-color:#E9C8CD; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit,QTimeEdit {
    background:#FFFFFF; border:1px solid #D5DEE7; color:#17324D;
}
QListWidget { background:#FFFFFF; color:#1B324A; border:1px solid #D9E2EA; border-radius:8px; }
QTableWidget,QTableView,QTreeWidget {
    background:#FFFFFF; alternate-background-color:#FAFBFC; border:1px solid #DCE4EB;
    gridline-color:#E8EDF2; selection-background-color:#E3EEFB; selection-color:#153654;
}
QHeaderView::section { background:#F1F5F8; color:#53697F; border:none; border-right:1px solid #DEE6ED; border-bottom:1px solid #D8E1E9; }
QScrollBar::handle:vertical,QScrollBar::handle:horizontal { background:#C5D0DA; border-radius:4px; min-height:30px; min-width:30px; }
QStatusBar { background:#FFFFFF; border-top:1px solid #E0E6EC; color:#75869A; }
QToolTip { background:#10253D; color:white; border:1px solid #31506E; padding:5px; }
"""

DARK_QSS = _COMMON + r"""
QMainWindow,QDialog,QWidget#appShell,QWidget#appBody,QStackedWidget { background:#0B1420; color:#E7EEF7; }
QWidget { color:#E7EEF7; }
QWidget#appTitleBar { background:#0B1420; border-bottom:1px solid #142537; }
QWidget#navPanel { background:#0B1D30; border-right:1px solid #17304B; }
QLabel#brandTitle { color:#FFFFFF; font-size:16px; font-weight:700; }
QLabel#brandMeta { color:#8FA4BC; font-size:10px; }
QWidget#navPanel QListWidget { background:transparent; border:none; outline:none; }
QWidget#navPanel QListWidget::item { min-height:38px; padding:2px 10px; margin:1px; border-radius:6px; color:#D0DCE9; }
QWidget#navPanel QListWidget::item:hover:enabled { background:#142D49; color:#FFFFFF; }
QWidget#navPanel QListWidget::item:selected:enabled { background:#1458A6; color:#FFFFFF; }
QWidget#navPanel QPushButton { background:transparent; color:#C8D6E6; border:1px solid transparent; }
QWidget#navPanel QPushButton:hover { background:#142D49; color:#FFFFFF; }
QFrame#statCard,QFrame#contentCard,QFrame#homeCalendar,QFrame#quickActions,QFrame#card,QGroupBox {
    background:#111E2E; border:1px solid #26394E;
}
QFrame#feedItem { background:#0E1927; border:1px solid #213349; border-radius:6px; }
QPushButton { background:#122238; border:1px solid #2B4058; color:#E6EEF8; }
QPushButton:hover { background:#172C46; border-color:#3A5879; }
QPushButton[primary="true"] { background:#2767C7; border-color:#2767C7; }
QPushButton[primary="true"]:hover { background:#3376DB; }
QPushButton[danger="true"] { background:#2B1921; border-color:#603344; color:#FF9AAA; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit,QTimeEdit {
    background:#0D1928; border:1px solid #2B3E54; color:#E6EEF8;
}
QListWidget { background:#0D1928; color:#DCE6F1; border:1px solid #273A50; border-radius:8px; }
QTableWidget,QTableView,QTreeWidget {
    background:#0D1928; alternate-background-color:#101D2D; border:1px solid #273A50;
    gridline-color:#223449; selection-background-color:#214D83; selection-color:#FFFFFF;
}
QHeaderView::section { background:#14253A; color:#AFC0D3; border:none; border-right:1px solid #293C52; border-bottom:1px solid #293C52; }
QScrollBar::handle:vertical,QScrollBar::handle:horizontal { background:#344B65; border-radius:4px; min-height:30px; min-width:30px; }
QStatusBar { background:#0B1420; border-top:1px solid #24364A; color:#8EA0B5; }
QToolTip { background:#10253D; color:white; border:1px solid #31506E; padding:5px; }
"""


def apply_theme(app, theme="dark"):
    theme = "light" if str(theme).lower() == "light" else "dark"
    app.setProperty("appTheme", theme)
    app.setStyle("Fusion")

    palette = QPalette()
    if theme == "light":
        window, base, alt, text, button, highlight, placeholder = (
            "#F4F7FA", "#FFFFFF", "#FAFBFC", "#17324D", "#FFFFFF", "#1F62BD", "#8A99AA"
        )
    else:
        window, base, alt, text, button, highlight, placeholder = (
            "#0B1420", "#0D1928", "#101D2D", "#E6EEF8", "#122238", "#2767C7", "#8497AD"
        )

    palette.setColor(QPalette.Window, QColor(window))
    palette.setColor(QPalette.WindowText, QColor(text))
    palette.setColor(QPalette.Base, QColor(base))
    palette.setColor(QPalette.AlternateBase, QColor(alt))
    palette.setColor(QPalette.Text, QColor(text))
    palette.setColor(QPalette.Button, QColor(button))
    palette.setColor(QPalette.ButtonText, QColor(text))
    palette.setColor(QPalette.Highlight, QColor(highlight))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipBase, QColor(base))
    palette.setColor(QPalette.ToolTipText, QColor(text))
    palette.setColor(QPalette.PlaceholderText, QColor(placeholder))
    app.setPalette(palette)
    app.setStyleSheet(LIGHT_QSS if theme == "light" else DARK_QSS)
