"""Extract structured facts from grouped photos, clarify, and validate."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .provider import Provider, ProviderError, parse_json
from .prompts import prompt_for

CONDITIONS = {
    "new", "new_boxed", "used_excellent", "used_good", "used_fair", "used_poor",
}
CONFIDENCE_LOW = 0.5


def _to_float(v: Any) -> float:
    """Coerce model confidence (number or 'low'/'high'/'medium') to a float."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_price(v: Any) -> float | None:
    try:
        f = float(str(v).replace("$", "").replace(",", ""))
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


@dataclass
class ItemFacts:
    item_type: str = ""
    brand: str = "unknown"
    model: str = "unknown"
    color: str = ""
    size: str | None = None
    condition: str = "used_fair"
    price_hint: float | None = None
    shipping: bool | None = None
    is_bulky: bool | None = None
    flaws: list[str] = field(default_factory=list)
    included: list[str] = field(default_factory=list)
    visible_text: list[str] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    questions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _to_pil_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


async def extract_facts(
    provider: Provider, index: int, paths: list[str], notes: str = ""
) -> ItemFacts:
    raw = await provider.vision(
        images=[_to_pil_bytes(p) for p in paths],
        prompt=prompt_for("extract", n=len(paths), notes=notes),
        model="extract",
    )
    data = parse_json(raw)
    if not isinstance(data, dict):
        raise ProviderError(f"vision model returned non-object JSON: {type(data).__name__}")
    facts = ItemFacts(
        item_type=data.get("item_type", ""),
        brand=data.get("brand", "unknown") or "unknown",
        model=data.get("model", "unknown") or "unknown",
        color=data.get("color", ""),
        size=data.get("size"),
        condition=data.get("condition", "used_fair"),
        price_hint=_to_price(data.get("price_hint")),
        shipping=data.get("shipping") if isinstance(data.get("shipping"), bool) else None,
        is_bulky=data.get("is_bulky") if isinstance(data.get("is_bulky"), bool) else None,
        flaws=list(data.get("flaws", []) or []),
        included=list(data.get("included", []) or []),
        visible_text=list(data.get("visible_text", []) or []),
        confidence={k: _to_float(v) for k, v in (data.get("confidence") or {}).items()},
    )
    return facts


async def clarify(
    provider: Provider, facts: ItemFacts
) -> list[str]:
    questions = await provider.text(
        prompt=prompt_for("clarify", facts=json.dumps(_facts_to_ctx(facts))),
        model="clarify",
    )
    try:
        parsed = parse_json(questions)
        if isinstance(parsed, list):
            return [str(q) for q in parsed if q]
    except Exception:
        pass
    return []


async def validate(facts: ItemFacts) -> ValidationResult:
    problems: list[str] = []
    low_conf: list[str] = []

    if not facts.item_type:
        problems.append("item_type is empty")
    if facts.brand not in ("unknown", "") and facts.confidence.get("brand", 1) < CONFIDENCE_LOW:
        low_conf.append("brand confidence low")
    if facts.condition not in CONDITIONS:
        problems.append(f"invalid condition: {facts.condition!r}")

    questions: list[str] = []
    if facts.item_type == "":
        questions.append("What item is this?")
    if facts.model == "unknown" and not facts.confidence.get("model"):
        questions.append("What model is it?")
    if facts.size is None:
        questions.append("What are the size / dimensions?")
    if facts.shipping is None:
        questions.append("Can this item be shipped (small enough)?")
    if not facts.flaws:
        questions.append("Any visible defects or flaws?")

    if questions and len(questions) > 3:
        questions = questions[:3]

    return ValidationResult(valid=not problems, questions=questions, notes=low_conf)


def _facts_to_ctx(facts: ItemFacts) -> dict[str, Any]:
    return {
        "item_type": facts.item_type,
        "brand": facts.brand,
        "model": facts.model,
        "color": facts.color,
        "size": facts.size,
        "condition": facts.condition,
        "flaws": facts.flaws,
        "included": facts.included,
    }


def apply_clarification(facts: ItemFacts, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if value in (None, "", [], ""):
            continue
        if key in facts.__dict__ and not key == "confidence":
            setattr(facts, key, value)
