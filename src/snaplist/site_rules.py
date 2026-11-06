"""Site suggestion rules.

Suggest which marketplaces an item goes to from size, value and shippability,
and pick the Craigslist / Facebook ad type. Overridable per item.
"""

from dataclasses import dataclass

EBAY = "ebay"
FACEBOOK = "facebook"
CRAIGSLIST = "craigslist"


@dataclass
class SiteSuggestion:
    sites: list[str]
    ad_type: str  # "full" or "pointer"


# A bulky/heavy flag or a large volume implies local pickup, not shipping.
BULKY_MIN_WEIGHT_KG = 10.0
BULKY_MIN_DIMENSION_CM = 75.0
LOW_VALUE_CENTS = 1500
HIGH_VALUE_SHIP_CENTS = 2000


def suggest_sites(
    *,
    is_bulky: bool = False,
    weight_kg: float | None = None,
    largest_cm: float | None = None,
    price_cents: int | None = None,
) -> SiteSuggestion:
    price = price_cents  # None = not priced yet; don't treat as "low value"

    weight_heavy = bool(weight_kg) and weight_kg >= BULKY_MIN_WEIGHT_KG
    dim_bulky = bool(largest_cm) and largest_cm >= BULKY_MIN_DIMENSION_CM
    if is_bulky or weight_heavy or dim_bulky:
        return SiteSuggestion(sites=[FACEBOOK, CRAIGSLIST], ad_type="full")

    if price is not None and price < LOW_VALUE_CENTS:
        return SiteSuggestion(sites=[FACEBOOK], ad_type="full")

    # Small and worth shipping.
    return SiteSuggestion(
        sites=[EBAY, FACEBOOK, CRAIGSLIST], ad_type="pointer"
    )
