from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

POLL_INTERVAL_KEY = "poll_interval_minutes"
PROBE_HISTORY_DAYS_KEY = "probe_history_days"
PING_COUNT_KEY = "ping_count"
PING_PACKET_SIZE_KEY = "ping_packet_size"


def get_probe_history_days(db: Session) -> int:
    row = db.get(Setting, PROBE_HISTORY_DAYS_KEY)
    if row is None:
        return settings.probe_history_days
    return int(row.value)


def set_probe_history_days(db: Session, days: int) -> int:
    row = db.get(Setting, PROBE_HISTORY_DAYS_KEY)
    if row is None:
        db.add(Setting(key=PROBE_HISTORY_DAYS_KEY, value=str(days)))
    else:
        row.value = str(days)
    db.commit()
    return days


def get_poll_interval(db: Session) -> int:
    row = db.get(Setting, POLL_INTERVAL_KEY)
    if row is None:
        return settings.poll_interval_minutes
    return int(row.value)


def set_poll_interval(db: Session, minutes: int) -> int:
    row = db.get(Setting, POLL_INTERVAL_KEY)
    if row is None:
        db.add(Setting(key=POLL_INTERVAL_KEY, value=str(minutes)))
    else:
        row.value = str(minutes)
    db.commit()
    return minutes


def get_ping_params(db: Session) -> tuple[int, int]:
    count_row = db.get(Setting, PING_COUNT_KEY)
    size_row = db.get(Setting, PING_PACKET_SIZE_KEY)
    count = int(count_row.value) if count_row is not None else settings.ping_count
    size = int(size_row.value) if size_row is not None else settings.ping_packet_size
    return count, size


def set_ping_params(db: Session, count: int, size: int) -> tuple[int, int]:
    for key, value in ((PING_COUNT_KEY, count), (PING_PACKET_SIZE_KEY, size)):
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
    db.commit()
    return count, size
