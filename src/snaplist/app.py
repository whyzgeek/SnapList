"""FastAPI application.

Serves the local web UI and the API: upload batches, review/edit the AI's items,
photos and listings, approve, then copy out. Binds to 127.0.0.1 by default.
Publishing to live marketplaces is not implemented; approved items are exported
as copy packets.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .channels import clipboard_queue_path, copy_packet, enqueue_craigslist
from .config import get_settings
from .db import init_db, session_scope
from .extract import CONDITIONS, ItemFacts
from .listing import ChannelListing
from .models import (
    APPROVED, DRAFT, FAILED, L_DRAFT, PROCESSING, READY, Batch, Item, ItemQuestion, Listing, Photo,
)
from .photos import BadImage, ensure_thumb, remove_photo_files, save_photo
from .pipeline import TITLE_MAX, facts_from_item, process_batch, process_item, recover_interrupted, spawn, write_listings
from .provider import build_provider

app = FastAPI(title="SnapList", version="0.2.0")

_PROVIDER = None
FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
MAX_UPLOAD_BYTES = 40 * 1024 * 1024
CHANNELS = ("ebay", "facebook", "craigslist")


def get_provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = build_provider(get_settings())
    return _PROVIDER


def _now():
    return datetime.now(timezone.utc)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    recover_interrupted()


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "llm": s.llm_provider, "bind": s.host}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "index.html"), media_type="text/html; charset=utf-8",
                        headers={"Cache-Control": "no-store"})


@app.get("/static/{filename}")
def static(filename: str) -> FileResponse:
    full = os.path.abspath(os.path.join(FRONTEND, filename))
    if os.path.dirname(full) != FRONTEND or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(full, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- serializers

def approval_problems(item: Item) -> list[str]:
    problems = []
    facts = json.loads(item.facts or "{}")
    if not item.photos:
        problems.append("no photos")
    if not facts.get("item_type"):
        problems.append("item type is empty")
    if not item.price:
        problems.append("price is not set")
    if not item.listings:
        problems.append("no listings written yet")
    for l in item.listings:
        if not (l.title or "").strip() or not (l.body or "").strip():
            problems.append(f"{l.channel}: title or description is empty")
        elif len(l.title) > TITLE_MAX.get(l.channel, 999):
            problems.append(f"{l.channel}: title is {len(l.title)} chars (max {TITLE_MAX[l.channel]})")
    return problems


def _listing_json(l: Listing) -> dict:
    fields = json.loads(l.fields or "{}")
    return {"id": l.id, "channel": l.channel, "title": l.title or "", "body": l.body or "",
            "status": l.status, "errors": fields.get("errors", []),
            "title_max": TITLE_MAX.get(l.channel)}


def _item_json(item: Item) -> dict:
    photos = sorted(item.photos, key=lambda p: (p.position, p.id))
    return {
        "id": item.id, "batch_id": item.batch_id, "status": item.status, "error": item.error,
        "facts": json.loads(item.facts or "{}"),
        "price": None if item.price is None else item.price / 100,
        "notes": item.notes or "",
        "sites": json.loads(item.chosen_sites or "[]"),
        "photos": [{"id": p.id, "is_cover": bool(p.is_cover)} for p in photos],
        "questions": [{"id": q.id, "question": q.question, "answer": q.answer} for q in item.questions],
        "listings": [_listing_json(l) for l in sorted(item.listings, key=lambda l: l.id)],
        "problems": approval_problems(item) if item.status in (READY, APPROVED, DRAFT, FAILED) else [],
    }


def _get_item(s, item_id: int) -> Item:
    item = s.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


def _fit_title(title: str, channel: str) -> str:
    limit = TITLE_MAX.get(channel, 999)
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0]
    return (cut if len(cut) > limit // 2 else title[:limit]).rstrip(" -,")


def _edited(item: Item) -> None:
    """Any content edit invalidates a previous approval."""
    if item.status == APPROVED:
        item.status = READY


# -------------------------------------------------------------------- batches

@app.get("/batches")
def list_batches() -> dict:
    with session_scope() as s:
        out = []
        for b in s.query(Batch).order_by(Batch.id.desc()).all():
            items = b.items
            first = next((p for i in items for p in i.photos), None)
            busy = sum(1 for i in items if i.status == PROCESSING)
            out.append({
                "id": b.id, "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
                "status": "processing" if busy or (b.status == "processing" and not items) else "ready",
                "items": len(items), "processing": busy,
                "approved": sum(1 for i in items if i.status == APPROVED),
                "failed": sum(1 for i in items if i.status == FAILED),
                "cover_photo": first.id if first else None,
            })
        return {"batches": out}


@app.post("/batches")
async def create_batch(files: list[UploadFile] = File(...)) -> dict:
    settings = get_settings()
    with session_scope() as s:
        batch = Batch(status="processing")
        s.add(batch)
        s.flush()
        batch_id = batch.id
    saved: list[str] = []
    skipped: list[str] = []
    for f in files:
        raw = await f.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            skipped.append(f"{f.filename}: too large")
            continue
        try:
            saved.append(save_photo(settings.photo_dir, batch_id, raw))
        except BadImage as exc:
            skipped.append(f"{f.filename}: {exc}")
    if not saved:
        with session_scope() as s:
            s.query(Batch).filter(Batch.id == batch_id).delete()
        raise HTTPException(status_code=400, detail="no readable images in upload: " + "; ".join(skipped))
    spawn(process_batch(batch_id, saved, get_provider()))
    return {"batch_id": batch_id, "photos": len(saved), "skipped": skipped}


@app.get("/batches/{batch_id}")
def batch_detail(batch_id: int) -> dict:
    with session_scope() as s:
        batch = s.get(Batch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="batch not found")
        items = sorted(batch.items, key=lambda i: i.id)
        # derive from items so a stale stored value can never leave the UI "processing"
        if items:
            batch.status = "processing" if any(i.status == PROCESSING for i in items) else "ready"
        return {"id": batch.id, "status": batch.status, "items": [_item_json(i) for i in items]}


@app.delete("/batches/{batch_id}")
def delete_batch(batch_id: int) -> dict:
    with session_scope() as s:
        batch = s.get(Batch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="batch not found")
        paths = [p.path for i in batch.items for p in i.photos]
        s.delete(batch)
    for p in paths:
        remove_photo_files(p)
    return {"deleted": batch_id}


# ---------------------------------------------------------------------- items

@app.get("/items/{item_id}")
def item_detail(item_id: int) -> dict:
    with session_scope() as s:
        return _item_json(_get_item(s, item_id))


class ItemPatch(BaseModel):
    facts: dict[str, Any] | None = None
    price: float | None = None
    clear_price: bool = False
    notes: str | None = None
    sites: list[str] | None = None


@app.patch("/items/{item_id}")
def patch_item(item_id: int, body: ItemPatch) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        if item.status == PROCESSING:
            raise HTTPException(status_code=409, detail="item is being processed; try again in a moment")
        if body.facts is not None:
            cur = json.loads(item.facts or "{}")
            for k, v in body.facts.items():
                if k not in ItemFacts.__annotations__ or k == "confidence":
                    raise HTTPException(status_code=422, detail=f"unknown fact: {k}")
                if k == "condition" and v not in CONDITIONS:
                    raise HTTPException(status_code=422, detail=f"condition must be one of {sorted(CONDITIONS)}")
                if k in ("flaws", "included", "visible_text"):
                    if not isinstance(v, list):
                        raise HTTPException(status_code=422, detail=f"{k} must be a list")
                    v = [str(x).strip() for x in v if str(x).strip()]
                cur[k] = v
            item.facts = json.dumps(cur)
        if body.clear_price:
            item.price = None
        elif body.price is not None:
            if body.price < 0 or body.price > 1_000_000:
                raise HTTPException(status_code=422, detail="price out of range")
            item.price = int(round(body.price * 100))
        if body.notes is not None:
            item.notes = body.notes
        if body.sites is not None:
            if any(x not in CHANNELS for x in body.sites):
                raise HTTPException(status_code=422, detail=f"sites must be from {CHANNELS}")
            item.chosen_sites = json.dumps(body.sites)
            # unticked sites lose their listing; newly ticked ones get a free copy of an
            # existing listing (no AI call). "Rewrite text" is the optional AI version.
            for l in [l for l in item.listings if l.channel not in body.sites]:
                s.delete(l)
            s.flush()
            s.expire(item)
            have = {l.channel for l in item.listings}
            src = next((l for l in sorted(item.listings, key=lambda l: l.id) if l.title and l.body), None)
            for c in body.sites:
                if c not in have and src is not None:
                    s.add(Listing(item_id=item.id, channel=c, title=_fit_title(src.title, c),
                                  body=src.body, fields="{}", status=L_DRAFT))
            s.flush()
            s.expire(item)
        _edited(item)
        return _item_json(item)


class AnswerBody(BaseModel):
    question_id: int
    answer: str


@app.post("/items/{item_id}/answer")
def answer_item(item_id: int, body: AnswerBody) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        q = s.get(ItemQuestion, body.question_id)
        if q is None or q.item_id != item_id:
            raise HTTPException(status_code=404, detail="question not found")
        q.answer = body.answer.strip() or None
        q.answered_at = _now() if q.answer else None
        _edited(item)
        return _item_json(item)


@app.post("/items/{item_id}/reanalyze")
async def reanalyze(item_id: int) -> dict:
    """Re-run vision on the item's CURRENT photos + notes, then rewrite listings."""
    with session_scope() as s:
        item = _get_item(s, item_id)
        if item.status == PROCESSING:
            raise HTTPException(status_code=409, detail="already processing")
        item.status, item.error = PROCESSING, None
    spawn(process_item(item_id, get_provider(), reextract=True))
    return {"item_id": item_id, "status": PROCESSING}


@app.post("/items/{item_id}/regenerate")
async def regenerate(item_id: int) -> dict:
    """Rewrite listing text from the current (edited) facts; no vision call."""
    with session_scope() as s:
        item = _get_item(s, item_id)
        if item.status == PROCESSING:
            raise HTTPException(status_code=409, detail="already processing")
        item.status, item.error = PROCESSING, None
    spawn(process_item(item_id, get_provider(), reextract=False))
    return {"item_id": item_id, "status": PROCESSING}


@app.post("/items/{item_id}/approve")
def approve(item_id: int) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        if item.status == PROCESSING:
            raise HTTPException(status_code=409, detail="item is still processing")
        problems = approval_problems(item)
        if problems:
            raise HTTPException(status_code=422, detail="cannot approve: " + "; ".join(problems))
        item.status = APPROVED
        return _item_json(item)


@app.post("/items/{item_id}/unapprove")
def unapprove(item_id: int) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        if item.status == APPROVED:
            item.status = READY
        return _item_json(item)


class MergeBody(BaseModel):
    into: int


@app.post("/items/{item_id}/merge")
def merge_item(item_id: int, body: MergeBody) -> dict:
    """Move all photos of this item into another item (same batch) and delete this one."""
    if body.into == item_id:
        raise HTTPException(status_code=422, detail="cannot merge an item into itself")
    with session_scope() as s:
        src, dst = _get_item(s, item_id), _get_item(s, body.into)
        if PROCESSING in (src.status, dst.status):
            raise HTTPException(status_code=409, detail="wait for processing to finish")
        nxt = max((p.position for p in dst.photos), default=-1) + 1
        for p in sorted(src.photos, key=lambda p: (p.position, p.id)):
            p.item_id, p.position, p.is_cover = dst.id, nxt, 0
            nxt += 1
        s.flush()
        s.expire(src)
        s.delete(src)
        s.expire(dst)
        _edited(dst)
        return _item_json(dst)


@app.delete("/items/{item_id}")
def delete_item(item_id: int) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        paths = [p.path for p in item.photos]
        s.delete(item)
    for p in paths:
        remove_photo_files(p)
    return {"deleted": item_id}


# --------------------------------------------------------------------- photos

def _get_photo(s, photo_id: int) -> Photo:
    p = s.get(Photo, photo_id)
    if p is None or not os.path.isfile(p.path):
        raise HTTPException(status_code=404, detail="photo not found")
    return p


@app.get("/photos/{photo_id}/file")
def photo_file(photo_id: int) -> FileResponse:
    with session_scope() as s:
        path = _get_photo(s, photo_id).path
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@app.get("/photos/{photo_id}/thumb")
def photo_thumb(photo_id: int) -> FileResponse:
    with session_scope() as s:
        path = _get_photo(s, photo_id).path
    return FileResponse(ensure_thumb(path), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600"})


@app.post("/items/{item_id}/photos")
async def add_photos(item_id: int, files: list[UploadFile] = File(...)) -> dict:
    settings = get_settings()
    with session_scope() as s:
        item = _get_item(s, item_id)
        batch_id = item.batch_id
    saved, skipped = [], []
    for f in files:
        raw = await f.read()
        try:
            if len(raw) > MAX_UPLOAD_BYTES:
                raise BadImage("too large")
            saved.append(save_photo(settings.photo_dir, batch_id, raw))
        except BadImage as exc:
            skipped.append(f"{f.filename}: {exc}")
    if not saved:
        raise HTTPException(status_code=400, detail="no readable images: " + "; ".join(skipped))
    with session_scope() as s:
        item = _get_item(s, item_id)
        nxt = max((p.position for p in item.photos), default=-1) + 1
        for path in saved:
            s.add(Photo(item_id=item_id, path=path, position=nxt, is_cover=1 if nxt == 0 else 0))
            nxt += 1
        s.flush()
        s.expire(item)
        _edited(item)
        out = _item_json(item)
    out["skipped"] = skipped
    return out


@app.delete("/photos/{photo_id}")
def delete_photo(photo_id: int) -> dict:
    with session_scope() as s:
        photo = s.get(Photo, photo_id)
        if photo is None:
            raise HTTPException(status_code=404, detail="photo not found")
        item = s.get(Item, photo.item_id)
        if len(item.photos) <= 1:
            raise HTTPException(status_code=409, detail="an item needs at least one photo; delete the item instead")
        was_cover, path = photo.is_cover, photo.path
        s.delete(photo)
        s.flush()
        s.expire(item)
        _renumber(item, make_first_cover=bool(was_cover))
        _edited(item)
        out = _item_json(item)
    remove_photo_files(path)
    return out


def _renumber(item: Item, make_first_cover: bool = False) -> None:
    photos = sorted(item.photos, key=lambda p: (p.position, p.id))
    for i, p in enumerate(photos):
        p.position = i
        if make_first_cover or not any(x.is_cover for x in photos):
            p.is_cover = 1 if i == 0 else 0


@app.post("/photos/{photo_id}/cover")
def set_cover(photo_id: int) -> dict:
    with session_scope() as s:
        photo = _get_photo(s, photo_id)
        item = s.get(Item, photo.item_id)
        others = sorted((p for p in item.photos if p.id != photo.id), key=lambda p: (p.position, p.id))
        for i, p in enumerate([photo] + others):
            p.position, p.is_cover = i, 1 if i == 0 else 0
        s.flush()
        s.expire(item)
        _edited(item)
        return _item_json(item)


class MoveBody(BaseModel):
    item_id: int | None = None  # None => split into a new item


@app.post("/photos/{photo_id}/move")
async def move_photo(photo_id: int, body: MoveBody) -> dict:
    """Move a photo to another item, or split it out into a new item. Both
    affected items must be re-analyzed (Re-analyze) to reflect the change."""
    new_item_id = None
    with session_scope() as s:
        photo = _get_photo(s, photo_id)
        src = s.get(Item, photo.item_id)
        if PROCESSING == src.status:
            raise HTTPException(status_code=409, detail="wait for processing to finish")
        if body.item_id is None:
            if len(src.photos) <= 1:
                raise HTTPException(status_code=422, detail="photo is already alone in its item")
            dst = Item(batch_id=src.batch_id, status=DRAFT)
            s.add(dst)
            s.flush()
            new_item_id = dst.id
        else:
            dst = _get_item(s, body.item_id)
            if dst.id == src.id:
                raise HTTPException(status_code=422, detail="photo is already in that item")
            if dst.status == PROCESSING:
                raise HTTPException(status_code=409, detail="wait for processing to finish")
        photo.item_id = dst.id
        photo.position = max((p.position for p in dst.photos), default=-1) + 1
        photo.is_cover = 1 if photo.position == 0 else 0
        s.flush()
        s.expire(src)
        s.expire(dst)
        src_id, dst_id = src.id, dst.id
        if not src.photos:
            s.delete(src)
        else:
            _renumber(src, make_first_cover=True)
            _edited(src)
        _edited(dst)
        dst_json = _item_json(dst)
    if new_item_id is not None:
        # a brand-new item has no facts yet: analyze it right away
        spawn(process_item(new_item_id, get_provider(), reextract=True))
    return {"from": src_id, "to": dst_id, "item": dst_json}


# ------------------------------------------------------------------- listings

class ListingPatch(BaseModel):
    title: str | None = None
    body: str | None = None


@app.patch("/listings/{listing_id}")
def patch_listing(listing_id: int, body: ListingPatch) -> dict:
    with session_scope() as s:
        l = s.get(Listing, listing_id)
        if l is None:
            raise HTTPException(status_code=404, detail="listing not found")
        if body.title is not None:
            l.title = body.title.strip()
        if body.body is not None:
            l.body = body.body
        if l.title and l.body and l.status != L_DRAFT:
            l.status = L_DRAFT
        _edited(s.get(Item, l.item_id))
        return _listing_json(l)


# ------------------------------------------------------------ copy-out packets

def _packet_text(item: Item, channel: str) -> str:
    listings = []
    for l in item.listings:
        raw = json.loads(l.fields or "{}")
        cl = ChannelListing(channel=l.channel, title=l.title, description=l.body)
        cl.price = item.price  # one source of truth: the item's price (cents)
        cl.category = raw.get("category", "")
        cl.pickup = raw.get("pickup", "")
        cl.raw = raw
        listings.append(cl)
    return copy_packet(listings, channel)


@app.get("/channels/{item_id}/{channel}/packet")
def channel_packet(item_id: int, channel: str):
    from fastapi.responses import PlainTextResponse
    with session_scope() as s:
        item = _get_item(s, item_id)
        return PlainTextResponse(_packet_text(item, channel))


@app.post("/craigslist/{item_id}/queue")
def craigslist_enqueue(item_id: int) -> dict:
    with session_scope() as s:
        item = _get_item(s, item_id)
        listings = [l for l in item.listings if l.channel == "craigslist"]
        cls = [ChannelListing(channel=l.channel, title=l.title, description=l.body, price=item.price)
               for l in listings]
    queue_dir = clipboard_queue_path(os.path.dirname(get_settings().photo_dir))
    for cl in cls:
        enqueue_craigslist(queue_dir, cl)
    return {"item_id": item_id, "queue_path": queue_dir, "enqueued": len(cls)}


__all__ = ["app", "get_provider"]
