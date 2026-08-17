import json

from sqlalchemy.orm import Session

from app.models import Setting

BUILTIN_TYPES = [
    "group",
    "server",
    "switch",
    "terminal",
    "camera",
    "nvr",
    "router",
    "firewall",
    "ap",
    "printer",
    "nas",
    "ups",
    "unmanaged_switch",
]

CUSTOM_TYPES_KEY = "custom_device_types"


def get_custom_types(db: Session) -> list[str]:
    row = db.get(Setting, CUSTOM_TYPES_KEY)
    if row is None:
        return []
    try:
        value = json.loads(row.value)
    except (ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(x) for x in value]


def set_custom_types(db: Session, names: list[str]) -> None:
    row = db.get(Setting, CUSTOM_TYPES_KEY)
    if row is None:
        db.add(Setting(key=CUSTOM_TYPES_KEY, value=json.dumps(names)))
    else:
        row.value = json.dumps(names)
    db.commit()


def is_valid_type(db: Session, t: str) -> bool:
    return t in BUILTIN_TYPES or t in get_custom_types(db)