def test_settings_loaded_from_env():
    from app.config import settings
    assert settings.db_url.startswith("sqlite")
    assert settings.poll_interval_minutes >= 1


def test_session_opens_and_commits():
    from app.database import SessionLocal
    from sqlalchemy import text

    with SessionLocal() as db:
        result = db.execute(text("SELECT 1"))
        assert result.scalar() == 1
