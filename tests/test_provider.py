from snaplist.provider import MockProvider, LiteLLMProvider, build_provider, ProviderError
from snaplist.config import Settings


def test_build_provider_mock():
    p = build_provider(Settings(llm_provider="mock"))
    assert isinstance(p, MockProvider)


def test_build_provider_litellm():
    p = build_provider(Settings(llm_provider="litellm"))
    assert isinstance(p, LiteLLMProvider)


def test_build_provider_rejects_unknown():
    import pytest
    with pytest.raises(ProviderError):
        build_provider(Settings(llm_provider="nope"))


async def test_mock_vision_returns_facts_and_groups(provider):
    import json
    facts = json.loads(await provider.vision(images=[b"x"], prompt="extract", model="m"))
    assert facts["item_type"]
    grouped = json.loads(await provider.vision(images=[b"x", b"y"], prompt="group photos", model="m"))
    assert isinstance(grouped["groups"], list)


async def test_mock_text_routes_on_kind(provider):
    import json
    out = json.loads(await provider.text(prompt="__kind__: write_ebay\n__END__\nx", model="m"))
    assert out.get("category")


async def test_mock_text_default(provider):
    import json
    out = json.loads(await provider.text(prompt="no marker", model="m"))
    assert out.get("title")


async def test_mock_clarify_returns_questions(provider):
    import json
    out = json.loads(await provider.text(prompt="__kind__: clarify\n__END__\nfacts={}", model="m"))
    assert isinstance(out, list)
