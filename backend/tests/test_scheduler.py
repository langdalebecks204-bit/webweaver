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
