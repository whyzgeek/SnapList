"""Generate per-channel listings from validated facts."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .provider import Provider, parse_json
from .prompts import prompt_for
from .extract import ItemFacts


@dataclass
class ChannelListing:
    channel: str
    title: str = ""
    description: str = ""
    price: int | None = None  # cents
    category: str = ""
    pickup: str = ""
    raw: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def _parse(provider: Provider, kind: str, facts: ItemFacts, extra: dict | None = None) -> ChannelListing:
    ctx = {**_facts_to_ctx(facts), **(extra or {})}
    payload = await provider.text(
        prompt=prompt_for(f"write_{kind}", facts=json.dumps(ctx)),
        model=f"write_{kind}",
    )
    listing = ChannelListing(channel=kind)
    try:
        data = parse_json(payload)
    except Exception as exc:
        listing.errors.append(f"could not parse {kind} output: {exc}")
        return listing
    listing.title = str(data.get("title", "")).strip()
    listing.description = str(data.get("description", "")).strip()
    if "price" in data and data["price"] is not None:
        listing.price = int(data["price"])
    listing.category = str(data.get("category", "")).strip()
    listing.pickup = str(data.get("pickup", "")).strip()
    listing.raw = data
    return listing


async def build_listings(
    provider: Provider, facts: ItemFacts, channels: list[str], extra: dict | None = None
) -> list[ChannelListing]:
    out: list[ChannelListing] = []
    for ch in channels:
        try:
            out.append(await _parse(provider, ch, facts, extra))
        except Exception as exc:
            out.append(ChannelListing(channel=ch, errors=[str(exc)]))
    return out


def _facts_to_ctx(facts: ItemFacts) -> dict:
    return {
        "item_type": facts.item_type,
        "brand": facts.brand,
        "model": facts.model,
        "color": facts.color,
        "size": facts.size,
        "condition": facts.condition,
        "flaws": facts.flaws,
        "included": facts.included,
        "visible_text": facts.visible_text,
    }
