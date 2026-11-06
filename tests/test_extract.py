from snaplist.extract import (
    ItemFacts, extract_facts, validate, clarify, apply_clarification,
)


async def test_extract_facts_parses(provider, sample_photos):
    facts = await extract_facts(provider, 0, sample_photos[:3])
    assert facts.item_type  # mock returns a mixer
    assert facts.condition in {
        "new", "new_boxed", "used_excellent", "used_good", "used_fair", "used_poor",
    }


async def test_validate_missing_item_type_is_invalid():
    v = await validate(ItemFacts())
    assert not v.valid
    assert any("item is this" in q for q in v.questions)


async def test_validate_valid_item():
    v = await validate(ItemFacts(item_type="widget", condition="used_good", model="x"))
    assert v.valid


async def test_clarify_returns_questions(provider):
    q = await clarify(provider, ItemFacts(item_type="widget"))
    assert isinstance(q, list)


def test_apply_clarification_updates_fields():
    f = ItemFacts(item_type="widget")
    apply_clarification(f, {"size": "10cm", "flaws": ["chip"]})
    assert f.size == "10cm"
    assert f.flaws == ["chip"]
