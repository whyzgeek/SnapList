"""Photo storage: normalized copies on persistent disk plus lazy thumbnails."""
from __future__ import annotations

import io
import os
import uuid

from PIL import Image, ImageOps

MAX_EDGE = 1600
THUMB_EDGE = 360
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class BadImage(ValueError):
    pass


def save_photo(photo_dir: str, batch_id: int, raw: bytes) -> str:
    """Decode, auto-rotate, strip EXIF (incl. GPS), downscale, save as JPEG."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
    except Exception as exc:
        raise BadImage(f"not a readable image: {exc}") from exc
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    folder = os.path.join(photo_dir, f"batch_{batch_id}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{uuid.uuid4().hex}.jpg")
    img.save(path, "JPEG", quality=88)
    return path


def thumb_path(path: str) -> str:
    base, _ = os.path.splitext(path)
    return base + ".thumb.jpg"


def ensure_thumb(path: str) -> str:
    tp = thumb_path(path)
    if not os.path.exists(tp):
        img = Image.open(path).convert("RGB")
        img.thumbnail((THUMB_EDGE, THUMB_EDGE))
        img.save(tp, "JPEG", quality=80)
    return tp


def remove_photo_files(path: str) -> None:
    for p in (path, thumb_path(path)):
        try:
            os.remove(p)
        except OSError:
            pass
