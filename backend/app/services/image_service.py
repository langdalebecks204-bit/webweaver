import io
import os
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

ALLOWED_MIME = {
    "image/jpeg": (".jpg", "JPEG"),
    "image/png": (".png", "PNG"),
    "image/webp": (".webp", "WEBP"),
    "image/heic": (".jpg", "JPEG"),
    "image/heif": (".jpg", "JPEG"),
}

MAX_EDGE = 1600
MAX_BYTES = 300 * 1024


def _process_image(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(status_code=422, detail="无法解码图片")
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_BYTES or quality <= 20:
            return buf.getvalue()
        quality -= 10


def upload_image(device_id: int, file: UploadFile) -> str:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="仅支持 jpeg/png/webp/heic 图片")
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="空文件")
    processed = _process_image(raw)

    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = f"{device_id}.jpg"
    Path(settings.upload_dir, filename).write_bytes(processed)
    return f"/uploads/{filename}"


def delete_image_file(device_id: int) -> None:
    path = Path(settings.upload_dir, f"{device_id}.jpg")
    if path.is_file():
        path.unlink()


def clear_all_images() -> None:
    if not os.path.isdir(settings.upload_dir):
        return
    for name in os.listdir(settings.upload_dir):
        if name.endswith(".jpg"):
            try:
                os.remove(os.path.join(settings.upload_dir, name))
            except OSError:
                pass
