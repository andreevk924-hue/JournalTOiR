from pathlib import Path

# ======================================================
# Основные пути проекта
# ======================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
RESOURCES_DIR = BASE_DIR / "resources"

# Создание необходимых папок
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
RESOURCES_DIR.mkdir(exist_ok=True)

# ======================================================
# База данных
# ======================================================

DATABASE_NAME = "journal.db"
DATABASE_PATH = DATA_DIR / DATABASE_NAME

# ======================================================
# Программа
# ======================================================

APP_NAME = "Журнал ТОиР"
APP_VERSION = "0.1.0"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 850
