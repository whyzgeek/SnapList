from snaplist import queue
from snaplist.queue import create_job, run_job, drain, reschedule_running


async def test_extract_job_completes(provider, tmp_db):
    job_id = create_job("extract", {"index": 0, "paths": []})
    result = await run_job(job_id, provider)
    assert result["item_type"]


def test_reschedule_running_moves_back(tmp_db):
    job_id = create_job("extract", {"index": 0, "paths": []})
    from snaplist.db import session_scope
    from snaplist.models import Job
    with session_scope() as s:
        s.get(Job, job_id).status = "running"
    n = reschedule_running(None)
    assert n == 1


async def test_drain_processes_all(provider, tmp_db):
    for i in range(3):
        create_job("extract", {"index": i, "paths": []})
    n = await drain(provider)
    assert n == 3


async def test_generate_job_lists(provider, tmp_db):
    from snaplist.extract import ItemFacts
    facts = ItemFacts(item_type="mixer", brand="KitchenAid", condition="used_good")
    job_id = create_job("generate_listings", {"channels": ["ebay", "facebook"],
                                              "item_type": facts.item_type,
                                              "brand": facts.brand,
                                              "condition": facts.condition})
    result = await run_job(job_id, provider)
    channels = {l["channel"] for l in result["listings"]}
    assert channels == {"ebay", "facebook"}
