from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Device


async def scheduled_inspection() -> None:
    from app.inspector.engine import run_inspection

    with SessionLocal() as db:
        devices = list(
            db.scalars(
                select(Device).where(
                    Device.ip_address.is_not(None), Device.type != "group"
                )
            )
        )
        if devices:
            await run_inspection(db, devices)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_inspection,
        "interval",
        minutes=settings.poll_interval_minutes,
        id="inspection",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
