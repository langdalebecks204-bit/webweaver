from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import auth, devices, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if settings.enable_scheduler:
        from app.inspector.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown()


app = FastAPI(title="织网 WebWeaver", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
