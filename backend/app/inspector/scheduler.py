from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Device, ExternalTarget
from app.services.setting_service import get_poll_interval

_scheduler: AsyncIOScheduler | None = None


def collect_all_targets(db) -> list[Device]:
    return list(
        db.scalars(
            select(Device).where(Device.ip_address.is_not(None))
        )
    )


def collect_external_targets(db) -> list[ExternalTarget]:
    return list(db.scalars(select(ExternalTarget)))


async def scheduled_inspection() -> None:
    from app.inspector.engine import run_external_inspection, run_inspection

    with SessionLocal() as db:
        devices = collect_all_targets(db)
        if devices:
            await run_inspection(db, devices)
        targets = collect_external_targets(db)
        if targets:
            await run_external_inspection(db, targets)


def reschedule_interval(minutes: int) -> None:
    if _scheduler is not None:
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler.reschedule_job("inspection", trigger=IntervalTrigger(minutes=minutes))


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    with SessionLocal() as db:
        minutes = get_poll_interval(db)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_inspection,
        "interval",
        minutes=minutes,
        id="inspection",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler = scheduler
    return scheduler
