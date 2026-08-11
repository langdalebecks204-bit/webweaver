from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_url: str = "sqlite:///./weaver.db"
    upload_dir: str = "./uploads"
    jwt_secret: str = "dev-secret-change-me"
    token_expire_minutes: int = 480
    poll_interval_minutes: int = 5
    probe_history_days: int = 30
    ping_concurrency: int = 100
    ping_timeout: float = 1.0
    tcp_timeout: float = 2.0
    default_admin: str = "admin"
    default_admin_password: str = "admin123"
    enable_scheduler: bool = True

    model_config = SettingsConfigDict(
        env_prefix="WEAVER_", env_file=".env", extra="ignore"
    )


settings = Settings()
