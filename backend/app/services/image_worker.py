"""Subprocess-isolated image processing worker.

Run as: python -m app.services.image_worker <auto|min>
Reads raw image bytes from stdin, writes processed JPEG bytes to stdout.

Exit codes:
  0  success
  2  undecodable image data
  1  unexpected failure (possibly a native crash in Pillow)

Running Pillow in a child process ensures a native crash (e.g. the
Linux-only segfault triggered by JPEGs carrying EXIF metadata) can only
kill the worker, never the uvicorn server.
"""
import io
import sys

from fastapi import HTTPException


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    data = sys.stdin.buffer.read()

    from app.services import image_service

    try:
        if mode == "min":
            clean, _ = image_service.strip_exif(data)
            out = image_service._process_image_safe(clean or data, None)
        else:
            clean, orientation = image_service.strip_exif(data)
            if clean is None:
                out = image_service._process_image(data)
            else:
                out = image_service._process_image_safe(clean, orientation)
    except HTTPException:
        return 2
    except Exception:
        return 1

    sys.stdout.buffer.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
