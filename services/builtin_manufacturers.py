from pathlib import Path


_RESOURCES = Path(__file__).resolve().parents[1] / "resources" / "manufacturers"

# Встроенный справочник. Эти записи намеренно не хранятся в SQLite:
# их нельзя случайно удалить вместе с данными конкретного заказчика.
# Отрицательные ID зарезервированы только для встроенных производителей.
BUILTIN_MANUFACTURERS = (
    {
        "id": -1001,
        "name": "Komatsu",
        "country": "Япония",
        "logo_path": str(_RESOURCES / "komatsu.png"),
        "logo_dark_path": str(_RESOURCES / "komatsu_dark.png"),
        "builtin": True,
    },
    {
        "id": -1002,
        "name": "Caterpillar",
        "country": "США",
        "logo_path": str(_RESOURCES / "caterpillar.png"),
        "logo_dark_path": str(_RESOURCES / "caterpillar_dark.png"),
        "builtin": True,
    },
    {
        "id": -1003,
        "name": "Hitachi Construction Machinery",
        "country": "Япония",
        "logo_path": str(_RESOURCES / "hitachi.png"),
        "logo_dark_path": str(_RESOURCES / "hitachi_dark.png"),
        "builtin": True,
    },
    {
        "id": -1004,
        "name": "Liebherr",
        "country": "Германия",
        "logo_path": str(_RESOURCES / "liebherr.png"),
        "logo_dark_path": str(_RESOURCES / "liebherr_dark.png"),
        "builtin": True,
    },
    {
        "id": -1006,
        "name": "BELAZ",
        "country": "Беларусь",
        "logo_path": str(_RESOURCES / "belaz.png"),
        "logo_dark_path": str(_RESOURCES / "belaz_dark.png"),
        "builtin": True,
    },
    {
        "id": -1007,
        "name": "XCMG",
        "country": "Китай",
        "logo_path": str(_RESOURCES / "xcmg.png"),
        "logo_dark_path": str(_RESOURCES / "xcmg_dark.png"),
        "builtin": True,
    },
    {
        "id": -1008,
        "name": "SANY",
        "country": "Китай",
        "logo_path": str(_RESOURCES / "sany.png"),
        "logo_dark_path": str(_RESOURCES / "sany_dark.png"),
        "builtin": True,
    },
    {
        "id": -1009,
        "name": "LiuGong",
        "country": "Китай",
        "logo_path": str(_RESOURCES / "liugong.png"),
        "logo_dark_path": str(_RESOURCES / "liugong_dark.png"),
        "builtin": True,
    },
    {
        "id": -1010,
        "name": "ЧЕТРА",
        "country": "Россия",
        "logo_path": str(_RESOURCES / "chetra.png"),
        "logo_dark_path": str(_RESOURCES / "chetra_dark.png"),
        "builtin": True,
    },
)


def get_builtin_manufacturers():
    return [dict(item) for item in BUILTIN_MANUFACTURERS]


def is_builtin_manufacturer(item_id):
    try:
        value = int(item_id)
    except (TypeError, ValueError):
        return False
    return any(item["id"] == value for item in BUILTIN_MANUFACTURERS)


def get_builtin_manufacturer(item_id):
    try:
        value = int(item_id)
    except (TypeError, ValueError):
        return None
    for item in BUILTIN_MANUFACTURERS:
        if item["id"] == value:
            return dict(item)
    return None


def get_all_manufacturers(repository=None):
    result = get_builtin_manufacturers()
    if repository is None:
        return result
    try:
        for row in repository.get_manufacturers():
            result.append({
                "id": row["id"],
                "name": row["name"],
                "country": row["country"],
                "logo_path": row["logo_path"],
                "logo_dark_path": row["logo_path"],
                "builtin": False,
            })
    except Exception:
        pass
    return result


def get_manufacturer(repository, item_id):
    builtin = get_builtin_manufacturer(item_id)
    if builtin is not None:
        return builtin
    if repository is None:
        return None
    try:
        for row in repository.get_manufacturers():
            if row["id"] == item_id:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "country": row["country"],
                "logo_path": row["logo_path"],
                "logo_dark_path": row["logo_path"],
                "builtin": False,
                }
    except Exception:
        pass
    return None
