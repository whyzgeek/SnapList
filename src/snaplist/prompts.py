"""Prompt templates for each job.

Text prompts carry a machine marker `__kind__: <tag>` so the offline
MockProvider can route to canned output. Live models ignore it.
"""

GROUP_SYSTEM = "You group photos that belong to the same physical item."

GROUP_USER = """Look at these photos and group them into items.
Respond with JSON: {\"groups\": [[index, index, ...], ...]}.
Photos are numbered 0 to n-1 in the order shown. Use those numbers.
A group is one physical item (different angles, close-ups of labels, flaws and
accessories of the SAME item belong together). Every photo must appear in
exactly one group. Put singletons in their own group.

Photos: {n}"""

EXTRACT_SYSTEM = (
    "You inspect product photos and return structured facts. Be conservative: "
    "use \"unknown\" rather than guessing. Every claim must be visible in a photo."
)

EXTRACT_USER = """Return facts as JSON. Allowed fields:
item_type, brand, model (or \"unknown\"), color, size (or null), condition,
flaws[], included[], visible_text[], price_hint (typical used resale price in
US dollars as a number, or null), is_bulky (true if it needs local pickup),
shipping (true if small enough to ship), confidence{} (brand/model/condition).
All photos show the SAME item: combine details from every photo (labels, model
plates, flaws, accessories). If seller_notes are given, trust them.
condition must be one of: new, new_boxed, used_excellent, used_good, used_fair, used_poor.

Photos: {n}{notes}"""

WRITE_HEADER = "__kind__: {kind}__END__\n"

WRITE_EBAY = WRITE_HEADER.format(kind="write_ebay") + """Write an eBay listing from facts.
Respond with JSON: title (<=80 chars), description, category.
Every claim in the description must trace to a fact (including seller_notes and seller_answers); never invent specs.
facts: {facts}"""

WRITE_FACEBOOK = WRITE_HEADER.format(kind="write_facebook") + """Write a Facebook Marketplace listing from facts.
Respond with JSON: title (<=50 chars), price (integer cents), condition, description.
Every claim in the description must trace to a fact (including seller_notes and seller_answers); never invent specs.
facts: {facts}"""

WRITE_CRAIGSLIST = WRITE_HEADER.format(kind="write_craigslist") + """Write a full Craigslist ad from facts.
Respond with JSON: title (<=70 chars), price (integer cents), description, pickup.
Every claim in the description must trace to a fact (including seller_notes and seller_answers); never invent specs.
facts: {facts}"""

CLARIFY_SYSTEM = (
    "Ask at most 3 short questions to resolve missing or low-confidence facts."
)

CLARIFY_USER = "__kind__: clarify__END__\n" + """Return JSON list of up to 3 questions. Only ask about fields that
block a good listing (size, defects, included parts, whether it powers on).
facts: {facts}"""


def prompt_for(kind: str, **ctx) -> str:
    if kind == "group":
        return GROUP_USER.replace("{n}", str(ctx.get("n", 0)))
    if kind == "extract":
        notes = ctx.get("notes") or ""
        notes = f"\nseller_notes: {notes}" if notes else ""
        return EXTRACT_USER.replace("{n}", str(ctx.get("n", 0))).replace("{notes}", notes)
    if kind == "clarify":
        return CLARIFY_USER.replace("{facts}", ctx.get("facts", "{}"))
    if kind == "write_ebay":
        return WRITE_EBAY.replace("{facts}", ctx.get("facts", "{}"))
    if kind == "write_facebook":
        return WRITE_FACEBOOK.replace("{facts}", ctx.get("facts", "{}"))
    if kind == "write_craigslist":
        return WRITE_CRAIGSLIST.replace("{facts}", ctx.get("facts", "{}"))
    raise ValueError(f"unknown prompt kind: {kind}")


SYSTEMS = {
    "group": GROUP_SYSTEM,
    "extract": EXTRACT_SYSTEM,
    "clarify": CLARIFY_SYSTEM,
    "write_ebay": "You write marketplace listings from verified facts.",
    "write_facebook": "You write Marketplace listings from verified facts.",
    "write_craigslist": "You write Craigslist ads from verified facts.",
}
