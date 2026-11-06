# SnapList

Open-source, local-first tool that turns product photos into ready-to-post
marketplace listings. Group photos, auto-generate listings, approve, then publish
to your chosen marketplaces — everything runs on your machine.

## Phase 1

Phase 1 covers **bulk upload + auto-grouping**, extraction/validation, listing
generation, an approval screen, and offline publish helpers (clipboard queue +
copy packets). Posting to live marketplaces is deferred to later phases.

- **Frontend:** vanilla HTML/CSS/JS (no build step required).
- **AI routing:** one interface; LiteLLM is the default router, with a built-in
  `mock` provider that runs the whole flow offline (no API keys, no GPU).
- **Data:** SQLite via SQLAlchemy. Secrets via OS keyring with env fallback.
- **Publishing:** offline-only in Phase 1 — Craigslist clipboard queue and
  Facebook/eBay copy packets. No data leaves the machine.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Run offline (mock provider, default):

```bash
snaplist serve
```

Or point LiteLLM at a local Ollama server via `.env` / environment variables.

## Development

Run the test suite (offline):

```bash
pip install -e ".[test]"
pytest
```

## Layout

- `src/snaplist/` — backend package (`provider.py`, `extract.py`, `grouping.py`,
  `listing.py`, `channels.py`, `queue.py`, `app.py`).
- `frontend/` — static web UI.
- `tests/` — offline test suite.

## License

Apache-2.0.
