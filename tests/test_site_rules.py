from snaplist.site_rules import suggest_sites, EBAY, FACEBOOK, CRAIGSLIST


def test_small_high_value_all_sites():
    s = suggest_sites(price_cents=50000)
    assert EBAY in s.sites
    assert s.ad_type == "pointer"


def test_low_value_only_facebook():
    s = suggest_sites(price_cents=1000)
    assert s.sites == [FACEBOOK]


def test_bulky_local_only():
    s = suggest_sites(is_bulky=True, price_cents=50000)
    assert EBAY not in s.sites
    assert s.ad_type == "full"


def test_heavy_and_large_flag_local():
    s = suggest_sites(largest_cm=100, price_cents=50000)
    assert EBAY not in s.sites


def test_weight_flag_local():
    s = suggest_sites(weight_kg=20, price_cents=50000)
    assert EBAY not in s.sites
