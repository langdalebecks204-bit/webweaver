from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

POLL_INTERVAL_KEY = "poll_interval_minutes"
PROBE_HISTORY_DAYS_KEY = "probe_history_days"


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
