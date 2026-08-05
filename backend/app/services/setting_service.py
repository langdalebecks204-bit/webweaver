from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

POLL_INTERVAL_KEY = "poll_interval_minutes"


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
