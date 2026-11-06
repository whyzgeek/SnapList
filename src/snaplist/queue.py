"""Persisted job queue with an asyncio worker.

Jobs survive restarts: on startup the worker reschedules any 'running' jobs back
to 'pending'. This is the offline-testable scheduler; publishing stays in
channels.py (no network in Phase 1).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .db import session_scope
from .models import Job, Item
from .provider import Provider
from .extract import extract_facts, clarify, validate
from .listing import build_listings
from .site_rules import suggest_sites


class JobError(RuntimeError):
    pass


def create_job(kind: str, params: dict, batch_id: int | None = None) -> int:
    job_id = uuid.uuid4()
    with session_scope() as s:
        row = Job(
            id=str(job_id),
            kind=kind,
            batch_id=batch_id,
            status="pending",
            params=json.dumps(params),
        )
        s.add(row)
    return str(job_id)


async def run_job(job_id: str, provider: Provider) -> dict[str, Any]:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise JobError(f"unknown job {job_id}")
        if job.status == "running":
            # Resume a job that was interrupted before finishing.
            job.status = "pending"
        job.status = "running"
        s.flush()
        try:
            result = await _dispatch(job, provider)
            if job.kind == "extract":
                _persist_facts(s, job, result)
            job.status = "completed"
            job.result = json.dumps(result)
            job.updated_at = datetime.now(timezone.utc)
            s.flush()
            return result
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.updated_at = datetime.now(timezone.utc)
            # Persist the failure before re-raising: session_scope rolls back
            # on exception, so commit here or the 'failed' status is lost and
            # the job resurfaces as 'pending' on the next drain.
            s.flush()
            s.commit()
            raise JobError(str(exc)) from exc


async def _dispatch(job: Job, provider: Provider) -> dict[str, Any]:
    params = json.loads(job.params or "{}")
    if job.kind == "extract":
        return await _extract(params, provider)
    if job.kind == "clarify":
        return {"questions": await clarify(provider, _facts_from_params(params))}
    if job.kind == "generate_listings":
        return await _generate(params, provider)
    if job.kind == "suggest_sites":
        return _suggest(params)
    raise JobError(f"unknown job kind: {job.kind}")


def _suggest(params: dict) -> dict[str, Any]:
    site = suggest_sites(
        is_bulky=params.get("is_bulky", False),
        weight_kg=params.get("weight_kg"),
        largest_cm=params.get("largest_cm"),
        price_cents=params.get("price_cents"),
    )
    return {"sites": site.sites, "ad_type": site.ad_type}


async def _extract(params: dict, provider: Provider) -> dict[str, Any]:
    index = params["index"]
    paths = params["paths"]
    facts = await extract_facts(provider, index, paths)
    result = facts.__dict__
    result["validation"] = (await validate(facts)).__dict__
    return result


async def _generate(params: dict, provider: Provider) -> dict[str, Any]:
    facts = _facts_from_params(params)
    channels = params.get("channels", [])
    listings = await build_listings(provider, facts, channels)
    return {"listings": [l.__dict__ for l in listings]}


def _persist_facts(s, job, result):
    from .extract import ItemFacts
    data = {k: v for k, v in result.items() if k in ItemFacts.__annotations__}
    if job.item_id is None:
        return
    item = s.get(Item, job.item_id)
    if item is not None:
        item.facts = json.dumps(data)



def _facts_from_params(params: dict):
    from .extract import ItemFacts
    data = dict(params)
    for skip in ("index", "paths", "channels", "item_id", "batch_id"):
        data.pop(skip, None)
    return ItemFacts(**{k: v for k, v in data.items()
                        if k in ItemFacts.__annotations__})


def reschedule_running(s: Any) -> int:
    """On startup: move interrupted 'running' jobs back to 'pending'."""
    with session_scope() as db:
        running = db.query(Job).filter(Job.status == "running").all()
        for job in running:
            job.status = "pending"
        return len(running)


async def drain(provider: Provider) -> int:
    """Run every pending job to completion. Returns jobs processed.

    A job that fails is recorded and skipped: one bad job must not stall the
    rest of the queue (which would leave the UI stuck in "processing")."""
    with session_scope() as s:
        jobs = s.query(Job).filter(Job.status == "pending").all()
        job_ids = [job.id for job in jobs]
    count = 0
    for job_id in job_ids:
        try:
            await run_job(job_id, provider)
        except JobError:
            # run_job already flips the job to 'failed' and sets job.error.
            continue
        count += 1
    return count
