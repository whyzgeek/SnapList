"""Publish-channel helpers: clipboard queue (Craigslist) and copy packets
(Facebook + eBay). No posting happens in Phase 1 -- only offline artifacts."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .listing import ChannelListing


@dataclass
class ClipboardQueueItem:
    channel: str
    title: str
    body: str
    price: int | None = None


def clipboard_queue_path(base_dir: str) -> str:
    path = os.path.join(base_dir, "clipboard_queue")
    os.makedirs(path, exist_ok=True)
    return path


def enqueue_craigslist(queue_dir: str, item: ChannelListing) -> str:
    """Append a Craigslist ad entry to the JSON clipboard queue."""
    os.makedirs(queue_dir, exist_ok=True)
    path = os.path.join(queue_dir, "queue.json")
    data: list[ClipboardQueueItem] = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = [ClipboardQueueItem(**d) for d in json.load(fh)]
        except Exception:
            data = []
    data.append(ClipboardQueueItem(
        channel=item.channel,
        title=item.title,
        body=item.description,
        price=item.price,
    ))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(
            [d.__dict__ for d in data],
            fh,
            indent=2,
            default=str,
        )
    return path


def copy_packet(listings: list[ChannelListing], channel: str) -> str:
    """Return a text packet for a single channel to copy/paste into the site."""
    lines: list[str] = []
    for ln in listings:
        if ln.channel != channel or ln.errors:
            continue
        lines.append(f"=== {ln.title} ===")
        if ln.price is not None:
            lines.append(f"Price: {ln.price / 100:.2f}")
        if ln.category:
            lines.append(f"Category: {ln.category}")
        if ln.pickup:
            lines.append(ln.pickup)
        lines.append("")
        lines.append(ln.description)
        lines.append("\n" + "-" * 40 + "\n")
    if not lines:
        return ""
    return "\n".join(lines).rstrip() + "\n"
