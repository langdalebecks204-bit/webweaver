import io
import os
import subprocess
import sys
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
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
IMAGE_PROCESS_TIMEOUT = 45


def _save_jpeg(img, exif=None) -> bytes:
    quality = 85
    while True:
        buf = io.BytesIO()
        kwargs = {"quality": quality, "optimize": True}
        if exif is not None:
            kwargs["exif"] = exif
        img.save(buf, format="JPEG", **kwargs)
        if buf.tell() <= MAX_BYTES or quality <= 20:
            return buf.getvalue()
        quality -= 10


def _parse_orientation_tiff(tiff: bytes) -> int | None:
    if len(tiff) < 8:
        return None
    endian = "little" if tiff[:2] == b"II" else "big" if tiff[:2] == b"MM" else None
    if endian is None or int.from_bytes(tiff[2:4], endian) != 42:
        return None
    ifd_off = int.from_bytes(tiff[4:8], endian)
    if ifd_off + 2 > len(tiff):
        return None
    count = int.from_bytes(tiff[ifd_off : ifd_off + 2], endian)
    for i in range(count):
        e = ifd_off + 2 + i * 12
        if e + 12 > len(tiff):
            return None
        tag = int.from_bytes(tiff[e : e + 2], endian)
        typ = int.from_bytes(tiff[e + 2 : e + 4], endian)
        if tag == 0x0112 and typ == 3:
            return int.from_bytes(tiff[e + 8 : e + 10], endian)
    return None


def strip_exif(data: bytes) -> tuple[bytes | None, int | None]:
    """Remove JPEG APP1/Exif segments (pure Python). Returns (clean, orientation)
    when EXIF is present, else (None, None)."""
    if not data.startswith(b"\xff\xd8"):
        return None, None
    out = bytearray(b"\xff\xd8")
    found = False
    orientation = None
    pos = 2
    while pos < len(data):
        if pos + 4 > len(data):
            out += data[pos:]
            break
        if data[pos] != 0xFF:
            out += data[pos:]
            break
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            out += data[pos : pos + 2]
            pos += 2
            continue
        seg_len = int.from_bytes(data[pos + 2 : pos + 4], "big")
        if seg_len < 2 or pos + 2 + seg_len > len(data):
            out += data[pos:]
            break
        payload = pos + 4
        if marker == 0xE1 and data[payload : payload + 6] == b"Exif\x00\x00":
            found = True
            orientation = _parse_orientation_tiff(data[payload + 6 : pos + 2 + seg_len])
            pos += 2 + seg_len
            continue
        out += data[pos : pos + 2 + seg_len]
        pos += 2 + seg_len
    if not found:
        return None, None
    return bytes(out), orientation


def _process_image(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))
        if img.width > MAX_EDGE or img.height > MAX_EDGE:
            try:
                img.draft("RGB", (MAX_EDGE, MAX_EDGE))
            except Exception:
                pass
        img.load()
    except Exception:
        raise HTTPException(status_code=422, detail="无法解码图片")
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    return _save_jpeg(img)


def _process_image_safe(data: bytes, orientation: int | None) -> bytes:
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        if img.width > MAX_EDGE or img.height > MAX_EDGE:
            try:
                img.draft("RGB", (MAX_EDGE, MAX_EDGE))
            except Exception:
                pass
        img.load()
    except Exception:
        raise HTTPException(status_code=422, detail="无法解码图片")
    img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    exif = None
    if orientation not in (None, 1):
        exif = Image.Exif()
        exif[0x0112] = orientation
    return _save_jpeg(img, exif=exif)


def _run_worker(mode: str, data: bytes) -> bytes | None:
    env = os.environ.copy()
    env["PYTHONFAULTHANDLER"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.services.image_worker", mode],
            input=data,
            capture_output=True,
            timeout=IMAGE_PROCESS_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode == 2:
        raise HTTPException(status_code=422, detail="无法解码图片")
    if proc.returncode != 0:
        return None
    return proc.stdout


def upload_image(device_id: int, file: UploadFile) -> str:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="仅支持 jpeg/png/webp/heic 图片")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="图片过大，请上传小于 30MB 的图片")
    if not raw:
        raise HTTPException(status_code=422, detail="空文件")

    processed = _run_worker("auto", raw)
    if processed is None:
        processed = _run_worker("min", raw)
    if processed is None:
        raise HTTPException(status_code=422, detail="图片处理失败")

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
