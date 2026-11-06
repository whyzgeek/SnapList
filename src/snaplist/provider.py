"""AI routing behind one interface.

LiteLLM is the default router (Ollama / OpenAI-compatible / Anthropic / Gemini
behind ONE call shape). A MockProvider runs the whole flow offline with no keys,
so it is fully testable. The rest of the code only depends on the Provider
protocol; the router must not leak into it.
"""
from __future__ import annotations

import base64
import json

from .config import Settings


class ProviderError(RuntimeError):
    pass


def parse_json(text: str) -> Any:
    """Parse JSON from raw model output.

    Free-tier providers commonly wrap JSON in markdown code fences or prefix
    prose; strip those and fall back to extracting the first balanced array or
    object so callers get the same contract as the mock provider.
    """
    if not isinstance(text, str):
        raise ProviderError(f"model returned non-text output: {type(text).__name__}")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").lstrip("json").strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        pass
    for i, ch in enumerate(stripped):
        if ch in "{[":
            try:
                obj, _end = json.JSONDecoder().raw_decode(stripped, i)
                return obj
            except (json.JSONDecodeError, ValueError):
                continue
    raise ProviderError(f"model output was not valid JSON: {text[:200]!r}")


class Provider:
    """One call shape for two jobs: look at photos (vision) and write text."""

    async def vision(self, *, images: list[bytes], prompt: str, model: str) -> str:
        raise NotImplementedError

    async def text(self, *, prompt: str, model: str) -> str:
        raise NotImplementedError


def _b64_uri(image_bytes: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('ascii')}"


class LiteLLMProvider(Provider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _completion(self, *, messages, model: str, base_url=None, api_key=None):
        import litellm  # imported lazily so tests avoid heavy init

        kwargs: dict = {"model": model, "messages": messages, "temperature": 0.2}
        if base_url is None:
            base_url = self.settings.litellm_base_url
        if api_key is None:
            api_key = self.settings.litellm_api_key
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        # A bare alias on a custom OpenAI-compatible base (e.g. the local
        # llama.cpp router) has no provider prefix, so litellm can't infer one.
        # Prefixing "openai/" routes it through the compatible client while the
        # alias on the wire stays unchanged. Vision ids already carry a prefix.
        if base_url and "/" not in model:
            kwargs["model"] = "openai/" + model
        try:
            resp = await litellm.acompletion(**kwargs)
            return resp["choices"][0]["message"]["content"] or ""
        except Exception as exc:
            raise ProviderError(f"llm call failed: {exc}") from exc

    async def vision(self, *, images, prompt, model):
        parts = [{"type": "text", "text": prompt}]
        for raw in images:
            parts.append({"type": "image_url", "image_url": {"url": _b64_uri(raw)}})
        messages = [{"role": "user", "content": parts}]
        return await self._completion(messages=messages, model=self.settings.vision_model)

    async def text(self, *, prompt, model):
        messages = [{"role": "user", "content": prompt}]
        return await self._completion(
            messages=messages,
            model=self.settings.text_model,
            base_url=self.settings.text_base_url,
            api_key=self.settings.text_api_key,
        )


class MockProvider(Provider):
    """Deterministic offline provider. Routes by a marker in the prompt so tests
    and local runs return valid, parseable output with no network or keys."""

    FACTS = {
        "item_type": "stand mixer",
        "brand": "KitchenAid",
        "model": "unknown",
        "color": "red",
        "size": None,
        "condition": "used_good",
        "flaws": ["small scratch on bowl rim"],
        "included": ["bowl", "whisk"],
        "visible_text": ["KitchenAid", "5 Qt"],
        "confidence": {"brand": 0.95, "model": 0.2, "condition": 0.9},
    }

    async def vision(self, *, images, prompt, model):
        if "group" in prompt.lower():
            return json.dumps({"groups": [[i] for i in range(len(images))]})
        return json.dumps(self.FACTS)

    async def text(self, *, prompt, model):
        idx = prompt.find("__kind__:")
        kind = ""
        if idx != -1:
            rest = prompt[idx + len("__kind__:") :].strip()
            kind = rest.splitlines()[0].strip().split("__END__")[0].strip()
        if not kind:
            return json.dumps({"title": "Mock title", "description": "Mock body."})
        base = {
            "title": "KitchenAid Stand Mixer 5 Qt Red - Used Good Condition",
            "description": "Used KitchenAid stand mixer, red, 5 Qt. Includes bowl and "
            "whisk. Minor scratch on the bowl rim.",
        }
        if kind == "write_ebay":
            base["category"] = "Household > Kitchen > Small Kitchen Appliances > Mixers"
            return json.dumps(base)
        if kind == "write_facebook":
            base["price"] = 12000
            return json.dumps(base)
        if kind == "write_craigslist":
            base["price"] = 12000
            base["pickup"] = "Local pickup only"
            return json.dumps(base)
        if kind == "clarify":
            return json.dumps(["What model is it?", "What are the dimensions?"])
        return json.dumps(base)


def build_provider(settings: Settings) -> Provider:
    if settings.llm_provider == "mock":
        return MockProvider()
    if settings.llm_provider == "litellm":
        return LiteLLMProvider(settings)
    raise ProviderError(f"unknown llm_provider: {settings.llm_provider}")
