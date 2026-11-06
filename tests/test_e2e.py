"""End-to-end test via the FastAPI TestClient with the offline mock provider:
upload -> background group/extract/write -> review/edit -> photos -> approve -> packet."""
import io
import time

import pytest
from PIL import Image
from fastapi.testclient import TestClient

import snaplist.app as appmod
import snaplist.db as dbmod
import snaplist.config as cfgmod
from snaplist.config import Settings
from snaplist.provider import MockProvider


@pytest.fixture()
def client(tmp_path, monkeypatch):
    settings = Settings(db_path=str(tmp_path / "e2e.db"), llm_provider="mock")
    for mod in (dbmod, appmod):
        monkeypatch.setattr(mod, "get_settings", lambda: settings)
    appmod._PROVIDER = MockProvider()
    with TestClient(appmod.app) as c:
        yield c


def _files(n=3):
    out = []
    for i in range(n):
        buf = io.BytesIO()
        Image.new("RGB", (80, 80), color=(i * 20 % 256, 20, i * 10)).save(buf, format="PNG")
        buf.seek(0)
        out.append(("files", (f"photo_{i}.png", buf, "image/png")))
    return out


def _wait(client, batch_id, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        b = client.get(f"/batches/{batch_id}").json()
        if b["items"] and all(i["status"] != "processing" for i in b["items"]):
            return b
        time.sleep(0.1)
    raise AssertionError("batch did not finish processing")


def test_full_review_flow(client, tmp_path):
    r = client.post("/batches", files=_files(3))
    assert r.status_code == 200
    bid = r.json()["batch_id"]
    batch = _wait(client, bid)
    assert len(batch["items"]) == 3
    it = batch["items"][0]
    assert it["status"] == "ready" and it["facts"]["item_type"] and it["listings"]
    # photos are persisted outside /tmp-style scratch and are servable
    pid = it["photos"][0]["id"]
    assert client.get(f"/photos/{pid}/file").status_code == 200
    assert client.get(f"/photos/{pid}/thumb").headers["content-type"] == "image/jpeg"
    assert str(tmp_path) in __import__("snaplist.db", fromlist=["x"]).get_settings().photo_dir

    # cannot approve without price
    it = client.patch(f"/items/{it['id']}", json={"clear_price": True}).json()
    assert client.post(f"/items/{it['id']}/approve").status_code == 422

    # edit facts, price, listing -> approve
    it = client.patch(f"/items/{it['id']}", json={"facts": {"brand": "Acme", "flaws": ["dent", " "]}, "price": 45.5}).json()
    assert it["facts"]["brand"] == "Acme" and it["facts"]["flaws"] == ["dent"] and it["price"] == 45.5
    lid = it["listings"][0]["id"]
    assert client.patch(f"/listings/{lid}", json={"title": "My title"}).json()["title"] == "My title"
    assert client.post(f"/items/{it['id']}/approve").json()["status"] == "approved"
    # editing after approval drops approval
    assert client.patch(f"/listings/{lid}", json={"body": "new body"}).status_code == 200
    assert client.get(f"/items/{it['id']}").json()["status"] == "ready"
    client.post(f"/items/{it['id']}/approve")

    # invalid edits rejected
    assert client.patch(f"/items/{it['id']}", json={"facts": {"condition": "pristine"}}).status_code == 422
    assert client.patch(f"/items/{it['id']}", json={"facts": {"bogus": 1}}).status_code == 422

    # packet uses edited text + the item's price
    pkt = client.get(f"/channels/{it['id']}/{it['listings'][0]['channel']}/packet")
    assert "45.50" in pkt.text


def test_photo_management(client):
    bid = client.post("/batches", files=_files(3)).json()["batch_id"]
    a, b, c = _wait(client, bid)["items"]

    # merge b into a -> a has 2 photos, b is gone
    merged = client.post(f"/items/{b['id']}/merge", json={"into": a["id"]}).json()
    assert len(merged["photos"]) == 2
    assert client.get(f"/items/{b['id']}").status_code == 404

    # add a photo
    added = client.post(f"/items/{a['id']}/photos", files=_files(1)).json()
    assert len(added["photos"]) == 3

    # cover
    pid = added["photos"][2]["id"]
    covered = client.post(f"/photos/{pid}/cover").json()
    assert covered["photos"][0]["id"] == pid and covered["photos"][0]["is_cover"]

    # split one out into a new item (analyzed in the background)
    res = client.post(f"/photos/{pid}/move", json={"item_id": None}).json()
    assert res["to"] not in (a["id"], b["id"], c["id"])
    batch = _wait(client, bid)
    assert len(batch["items"]) == 3

    # move a photo into c; delete photo; last photo can't be deleted
    pa = batch["items"][0]["photos"][0]["id"]
    client.post(f"/photos/{pa}/move", json={"item_id": c["id"]})
    batch = _wait(client, bid)
    cc = next(i for i in batch["items"] if i["id"] == c["id"])
    assert len(cc["photos"]) == 2
    assert client.delete(f"/photos/{cc['photos'][1]['id']}").status_code == 200
    only = client.get(f"/items/{c['id']}").json()["photos"][0]["id"]
    assert client.delete(f"/photos/{only}").status_code == 409

    # reanalyze + regenerate run and come back ready; listings replaced not duplicated
    client.post(f"/items/{c['id']}/reanalyze")
    _wait(client, bid)
    client.post(f"/items/{c['id']}/regenerate")
    item = _wait(client, bid)["items"][-1] if False else client.get(f"/items/{c['id']}").json()
    n = len(item["listings"])
    client.post(f"/items/{c['id']}/regenerate")
    _wait(client, bid)
    assert len(client.get(f"/items/{c['id']}").json()["listings"]) == n


def test_bad_upload_rejected(client):
    r = client.post("/batches", files=[("files", ("x.png", io.BytesIO(b"not an image"), "image/png"))])
    assert r.status_code == 400
    assert client.get("/batches").json()["batches"] == []


def test_delete_item_and_batch_remove_files(client):
    import os
    bid = client.post("/batches", files=_files(2)).json()["batch_id"]
    batch = _wait(client, bid)
    folder = os.path.join(appmod.get_settings().photo_dir, f"batch_{bid}")
    assert os.listdir(folder)
    client.delete(f"/batches/{bid}")
    assert not [f for f in os.listdir(folder) if f.endswith(".jpg")]


def test_changing_sites_adds_and_removes_listings_without_ai(client, monkeypatch):
    bid = client.post("/batches", files=_files(1)).json()["batch_id"]
    it = _wait(client, bid)["items"][0]
    lid = it["listings"][0]["id"]
    client.patch(f"/listings/{lid}", json={"title": "hand edited " + "x" * 120})

    class Boom(MockProvider):
        async def text(self, **kw):
            raise AssertionError("AI must not be called when changing sites")
        async def vision(self, **kw):
            raise AssertionError("AI must not be called when changing sites")
    monkeypatch.setattr(appmod, "_PROVIDER", Boom())

    r = client.patch(f"/items/{it['id']}", json={"sites": ["ebay", "facebook", "craigslist"]}).json()
    assert r["status"] != "processing"
    by = {l["channel"]: l for l in r["listings"]}
    assert set(by) == {"ebay", "facebook", "craigslist"}
    assert all(l["body"] for l in r["listings"])
    assert all(len(l["title"]) <= l["title_max"] for l in r["listings"] if l["id"] != lid)

    r = client.patch(f"/items/{it['id']}", json={"sites": ["ebay"]}).json()
    assert [l["channel"] for l in r["listings"]] == ["ebay"]
