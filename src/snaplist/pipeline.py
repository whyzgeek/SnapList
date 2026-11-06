"""Background processing: group a batch, extract facts per item, write listings.

Runs in-process as asyncio tasks. Every failure is recorded on the item
(``status="failed"`` + ``error``) so the review UI can show it and retry; nothing
is silently swallowed. Interrupted work is marked failed on startup (see
``recover_interrupted``) rather than silently resumed.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from .db import session_scope
from .extract import ItemFacts, extract_facts, validate
from .grouping import group_photos
from .listing import build_listings
from .models import (
    FAILED, L_DRAFT, L_FAILED, PROCESSING, READY, Batch, Item, ItemQuestion, Listing, Photo,
)
from .provider import Provider
from .site_rules import suggest_sites

log = logging.getLogger("snaplist.pipeline")

# Max chars per channel title; validated again before approval.
TITLE_MAX = {"ebay": 80, "facebook": 99, "craigslist": 70}

_SEM = asyncio.Semaphore(2)
_TASKS: set[asyncio.Task] = set()
_RUNNING_ITEMS: set[int] = set()


def spawn(coro) -> asyncio.Task:
    task = asyncio.get_running_loop().create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


def facts_from_item(item: Item) -> ItemFacts:
    data = json.loads(item.facts or "{}")
    return ItemFacts(**{k: v for k, v in data.items() if k in ItemFacts.__annotations__})


def photo_paths(s, item_id: int) -> list[str]:
    rows = s.query(Photo).filter(Photo.item_id == item_id).order_by(Photo.position, Photo.id).all()
    return [p.path for p in rows]


def recover_interrupted() -> None:
    with session_scope() as s:
        for item in s.query(Item).filter(Item.status == PROCESSING).all():
            item.status = FAILED
            item.error = "Interrupted by a restart. Use Re-analyze to retry."
        for b in s.query(Batch).filter(Batch.status == "processing").all():
            b.status = "ready"


def _refresh_batch_status(s, batch_id: int) -> None:
    batch = s.get(Batch, batch_id)
    if batch is None:
        return
    s.flush()  # session has autoflush off: make pending item statuses visible to the count
    busy = s.query(Item).filter(Item.batch_id == batch_id, Item.status == PROCESSING).count()
    batch.status = "processing" if busy else "ready"


async def process_batch(batch_id: int, paths: list[str], provider: Provider) -> None:
    try:
        groups = await group_photos(provider, paths)
    except Exception as exc:  # grouping failure must not lose the photos
        log.exception("grouping failed")
        groups = []
        err = f"Auto-grouping failed ({exc}); photos were kept as one item each."
    else:
        err = None
    if not groups:
        groups_idx = [[i] for i in range(len(paths))]
    else:
        groups_idx = [g.indexes for g in groups]

    item_ids: list[int] = []
    with session_scope() as s:
        for idxs in groups_idx:
            item = Item(batch_id=batch_id, status=PROCESSING, error=err)
            s.add(item)
            s.flush()
            for pos, i in enumerate(idxs):
                s.add(Photo(item_id=item.id, path=paths[i], position=pos, is_cover=1 if pos == 0 else 0))
            item_ids.append(item.id)
    await asyncio.gather(*(process_item(i, provider) for i in item_ids))


async def process_item(item_id: int, provider: Provider, reextract: bool = True,
                       only_missing: bool = False) -> None:
    """(Re)analyze an item's photos and (re)write its listings."""
    if item_id in _RUNNING_ITEMS:
        return
    _RUNNING_ITEMS.add(item_id)
    try:
        async with _SEM:
            with session_scope() as s:
                item = s.get(Item, item_id)
                if item is None:
                    return
                item.status = PROCESSING
                item.error = None
                _refresh_batch_status(s, item.batch_id)
                paths, notes = photo_paths(s, item_id), item.notes or ""
            try:
                if reextract:
                    if not paths:
                        raise ValueError("item has no photos")
                    facts = await extract_facts(provider, 0, paths, notes=notes)
                    verdict = await validate(facts)
                    with session_scope() as s:
                        item = s.get(Item, item_id)
                        item.facts = json.dumps(asdict(facts))
                        if item.price is None and facts.price_hint:
                            item.price = int(round(facts.price_hint * 100))
                        have = {q.question for q in item.questions}
                        for q in verdict.questions:
                            if q not in have:
                                s.add(ItemQuestion(item_id=item_id, question=q))
                await write_listings(item_id, provider, only_missing=only_missing)
                final, error = READY, None
            except Exception as exc:
                log.exception("item %s failed", item_id)
                final, error = FAILED, str(exc) or exc.__class__.__name__
            with session_scope() as s:
                item = s.get(Item, item_id)
                if item is not None:
                    item.status, item.error = final, error
                    _refresh_batch_status(s, item.batch_id)
    finally:
        _RUNNING_ITEMS.discard(item_id)


async def write_listings(item_id: int, provider: Provider, only_missing: bool = False) -> None:
    """Replace the item's listings with freshly written ones from current facts.

    With only_missing, keep existing listings (and their manual edits) and write
    just the chosen channels that have none yet."""
    with session_scope() as s:
        item = s.get(Item, item_id)
        facts = facts_from_item(item)
        if not facts.item_type:
            raise ValueError("no item type identified yet; edit the details or add photos, then retry")
        chosen = json.loads(item.chosen_sites or "[]")
        site = suggest_sites(is_bulky=bool(facts.is_bulky), price_cents=item.price)
        item.suggested_sites = json.dumps(site.sites)
        if not chosen:
            chosen = site.sites
            item.chosen_sites = json.dumps(chosen)
        extra = {
            "seller_notes": item.notes or "",
            "seller_answers": {q.question: q.answer for q in item.questions if q.answer},
        }
        if item.price:
            extra["asking_price_usd"] = round(item.price / 100, 2)
        if only_missing:
            have = {l.channel for l in item.listings}
            chosen = [c for c in chosen if c not in have]
    listings = await build_listings(provider, facts, chosen, extra)
    with session_scope() as s:
        if only_missing:
            keep = set(json.loads(s.get(Item, item_id).chosen_sites or "[]"))
            s.query(Listing).filter(Listing.item_id == item_id, Listing.channel.notin_(keep)).delete(synchronize_session=False)
        else:
            s.query(Listing).filter(Listing.item_id == item_id).delete()
        for l in listings:
            failed = bool(l.errors) or not l.title
            fields = dict(l.raw or {})
            if l.errors:
                fields["errors"] = l.errors
            s.add(Listing(
                item_id=item_id, channel=l.channel, title=l.title, body=l.description,
                fields=json.dumps(fields), status=L_FAILED if failed else L_DRAFT,
            ))
