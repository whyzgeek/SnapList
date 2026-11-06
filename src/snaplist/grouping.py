"""Photo grouping.

Pre-cluster by color similarity to bound the problem, then let the model group
each small chunk. Groups that overlap in a chunk are merged.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from statistics import mean

import numpy as np
from PIL import Image

from .provider import Provider, parse_json


@dataclass
class Group:
    indexes: list[int]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _mean_color(path: str) -> tuple[int, int, int]:
    img = Image.open(path).convert("RGB").resize((32, 32))
    data = np.array(img, dtype=int).reshape(-1, 3)
    r, g, b = mean(data[:, 0]), mean(data[:, 1]), mean(data[:, 2])
    return (int(r), int(g), int(b))


def _rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def pre_cluster(paths: list[str], threshold: float = 15000) -> list[list[int]]:
    """Bucket photos by dominant color similarity (indices into paths)."""
    buckets: list[tuple[int, int, int]] = []
    members: list[list[int]] = []
    for idx, path in enumerate(paths):
        color = _mean_color(path)
        for b_idx, center in enumerate(buckets):
            if _rgb_distance(color, center) <= threshold:
                members[b_idx].append(idx)
                break
        else:
            buckets.append(color)
            members.append([idx])
    return members


def _to_pil_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _thumb_bytes(path: str, edge: int = 512) -> bytes:
    """Small JPEG for the grouping call -- grouping doesn't need full-size photos."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((edge, edge))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=75)
    return buf.getvalue()


async def group_photos(provider: Provider, paths: list[str], max_per_chunk: int = 12) -> list[Group]:
    """Group photos in chunks of consecutive shots.

    The model sees each chunk numbered 0..n-1, so its answers are chunk-local and
    are mapped back to global indexes. Photos the model forgot become singletons
    so nothing is ever dropped. Items split across chunk boundaries are not merged
    automatically (the review UI lets you merge them)."""
    if not paths:
        return []

    from .prompts import prompt_for

    groups_out: list[list[int]] = []
    for start in range(0, len(paths), max_per_chunk):
        chunk_idx = list(range(start, min(start + max_per_chunk, len(paths))))
        try:
            raw = await provider.vision(
                images=[_thumb_bytes(paths[i]) for i in chunk_idx],
                prompt=prompt_for("group", n=len(chunk_idx)),
                model="group",
            )
            parsed = parse_json(raw).get("groups", [])
        except Exception:
            parsed = [[i] for i in range(len(chunk_idx))]

        seen: set[int] = set()
        for g in parsed:
            if not isinstance(g, list):
                continue
            local = sorted({x for x in g if isinstance(x, int) and 0 <= x < len(chunk_idx)} - seen)
            if not local:
                continue
            seen.update(local)
            merge_into(groups_out, [chunk_idx[x] for x in local])
        for x in range(len(chunk_idx)):
            if x not in seen:
                groups_out.append([chunk_idx[x]])

    return [Group(indexes=sorted(g)) for g in groups_out]


def merge_into(groups: list[list[int]], new: list[int]) -> None:
    """Merge new into existing groups that overlap; add it if disjoint."""
    hit = False
    for existing in groups:
        if any(x in existing for x in new):
            existing.extend(x for x in new if x not in existing)
            hit = True
    if not hit:
        groups.append(list(new))
