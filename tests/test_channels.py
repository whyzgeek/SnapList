from snaplist.channels import clipboard_queue_path, enqueue_craigslist, copy_packet
from snaplist.listing import ChannelListing
from snaplist.models import Listing


def test_enqueue_and_read_back(tmp_path):
    qd = str(tmp_path)
    path = enqueue_craigslist(qd, ChannelListing(channel="craigslist", title="T",
                                                 description="D", price=12000))
    assert path.endswith("queue.json")
    import json
    with open(path) as fh:
        data = json.load(fh)
    assert data[0]["title"] == "T"
    assert data[0]["price"] == 12000


def test_enqueue_appends(tmp_path):
    qd = str(tmp_path)
    enqueue_craigslist(qd, ChannelListing(channel="craigslist", title="A", description="a"))
    enqueue_craigslist(qd, ChannelListing(channel="craigslist", title="B", description="b"))
    import json
    with open(str(tmp_path) + "/queue.json") as fh:
        assert len(json.load(fh)) == 2


def test_copy_packet_filters_channel():
    listings = [ChannelListing(channel="ebay", title="EB", description="ebay body"),
                ChannelListing(channel="facebook", title="FB", description="fb body", price=12000)]
    packet = copy_packet(listings, "facebook")
    assert "FB" in packet and "fb body" in packet
    assert "EB" not in packet
