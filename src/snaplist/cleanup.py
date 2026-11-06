"""Photo cleanup: rotate, strip location metadata, optional background removal.

Background removal (rembg) is an optional extra and lazily imported so the core
runs without it. Location data is always stripped before any photo is posted.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image


@dataclass
class CleanedPhoto:
    path: str          # output path on disk
    background_removed: bool = False


def strip_location(input_path: str, output_path: str) -> str:
    """Copy the image without GPS / location EXIF using Pillow (no external dep)."""
    img = Image.open(input_path)
    img = img.copy()
    try:
        exif = img.getexif()
        exif.pop("GPSInfo", None)
        clean_exif = exif.tobytes() if len(exif) else None
        img.save(output_path, exif=clean_exif if clean_exif else None)
    except Exception:
        img.save(output_path)
    return output_path


def auto_rotate(input_path: str, output_path: str) -> str:
    img = Image.open(input_path)
    img = Image.exif_transpose(img)
    img.save(output_path)
    return output_path


def remove_background(input_path: str, output_path: str) -> CleanedPhoto:
    """Lazy rembg import. Falls back to a location-stripped copy if unavailable."""
    try:
        from rembg import remove  # type: ignore
    except Exception:
        strip_location(input_path, output_path)
        return CleanedPhoto(path=output_path, background_removed=False)
    with Image.open(input_path) as im:
        out = remove(im.convert("RGBA"))
        out.convert("RGB").save(output_path)
    return CleanedPhoto(path=output_path, background_removed=True)


def prepare_output_dir(base_dir: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    return base_dir
