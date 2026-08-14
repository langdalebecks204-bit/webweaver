from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import auth, backup, device_types, devices, external, users
from app.routers import settings as settings_router


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
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(device_types.router, prefix="/api/settings", tags=["settings"])
app.include_router(external.router, prefix="/api/external", tags=["external"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    base = Path(os.environ.get("WEAVER_FRONTEND_DIR", "/app/frontend/dist"))
    if not base.is_dir():
        return Response(status_code=404)
    target = (base / full_path).resolve()
    if not str(target).startswith(str(base.resolve())):
        return Response(status_code=404)
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        target = base / "index.html"
    if not target.is_file():
        return Response(status_code=404)
    return FileResponse(target)
