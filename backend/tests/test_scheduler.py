from app.inspector.scheduler import create_scheduler


def test_scheduler_has_inspection_job():
    scheduler = create_scheduler()
    try:
        job = scheduler.get_job("inspection")
        assert job is not None
        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_create_scheduler_reads_interval_from_db():
    from app.database import SessionLocal
    from app.services.setting_service import set_poll_interval

    with SessionLocal() as db:
        set_poll_interval(db, 10)

    scheduler = create_scheduler()
    try:
        job = scheduler.get_job("inspection")
        assert job is not None
        assert job.trigger.interval.seconds == 600
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_reschedule_interval_changes_job_trigger():
    from app.inspector.scheduler import reschedule_interval

    scheduler = create_scheduler()
    try:
        reschedule_interval(3)
        job = scheduler.get_job("inspection")
        assert job.trigger.interval.seconds == 180
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        from app.inspector.scheduler import _scheduler

        globals()["_scheduler"] = None


def test_collect_all_targets_filters():
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.inspector.scheduler import collect_all_targets
    from app.models import Device

    with SessionLocal() as db:
        root = Device(name="root", type="group")
        db.add(root)
        db.commit()
        db.add_all(
            [
                Device(name="sw1", type="switch", ip_address="10.0.0.1", parent_id=root.id),
                Device(name="sw2", type="switch", ip_address="10.0.0.2", parent_id=root.id),
                Device(name="noip", type="switch", parent_id=root.id),
                Device(name="sub", type="group", ip_address="10.0.0.9", parent_id=root.id),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        names = sorted(d.name for d in collect_all_targets(db))
        assert names == ["sub", "sw1", "sw2"]


def test_collect_external_targets_returns_all():
    from app.database import SessionLocal
    from app.inspector.scheduler import collect_external_targets
    from app.models import ExternalTarget

    with SessionLocal() as db:
        db.add_all(
            [
                ExternalTarget(name="t1", ip_address="8.8.8.8"),
                ExternalTarget(name="t2", domain="example.com"),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        assert len(collect_external_targets(db)) == 2
