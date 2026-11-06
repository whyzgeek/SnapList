"""Shared pytest fixtures: in-memory/temp DB and the offline mock provider."""
from __future__ import annotations

import pytest

from snaplist.config import Settings
from snaplist.db import init_db, session_scope
from snaplist.provider import MockProvider, Provider


@pytest.fixture()
def tmp_db(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        llm_provider="mock",
    )
    init_db(settings)
    yield settings
    # session_scope closes per-transaction connections; nothing to tear down
    # for a temp file, but clear the lru_cache on settings between tests.


@pytest.fixture()
def provider():
    return MockProvider()


@pytest.fixture()
def sample_photos(tmp_path):
    from PIL import Image

    paths = []
    for i in range(6):
        p = tmp_path / f"photo_{i}.png"
        Image.new("RGB", (64, 64), color=(20 + i * 10, 10, 30)).save(p)
        paths.append(str(p))
    return paths
