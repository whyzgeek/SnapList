# SnapList — Phase 1 To-Do List

**Scope:** Phase 1 only. Bulk upload + auto-grouping, generation, approval screen,
and publish channels in scope (Craigslist clipboard queue + Facebook copy packet +
eBay copy packet). eBay developer setup, API comps and auto-post are deferred.

**Locked decisions**
- Scope: Phase 1 only · License: Apache-2.0 · Frontend: Vanilla HTML/CSS/JS (no build;
  Alpine.js/HTMX via script tag allowed if drag-to-fix or approval grid gets hairy)
- AI routing: LiteLLM behind a thin `Provider` protocol (vision + text job types).
   LiteLLM is the default router; it must not leak into the rest of the code beyond one
   adapter module. One call shape, independent vision/text model selection.
- Queue: persisted `job` table in SQLite + in-process asyncio worker loop that resumes
  unfinished jobs on startup (retry, progress, cancel) — no Celery/Redis
- DB layer: SQLAlchemy over SQLite
- Secrets: OS keyring (`keyring`) with env-var fallback — no machine-derived Fernet key
- AI providers: Ollama default; any OpenAI-compatible endpoint, Anthropic, Gemini opt-in.
  Vision and text providers are chosen independently. Cloud use is opt-in per job, and
  the UI shows which job sends photos/text off-machine.
- Pricing (Phase 1): AI-suggested range from facts + manual edit + one-click eBay
  sold-items search link. API comps arrive with eBay in a later phase.
- eBay in Phase 1: copy packet only. Craigslist ad type is therefore always the
  *full ad*; the pointer ad is enabled only once eBay posting exists.
- DB migrations: Alembic from day one (users keep real data in their SQLite file)
- Server security: bind 127.0.0.1 by default; LAN mode (for phone capture) is opt-in,
  requires a random access token, and sets strict CORS
- Reference: `fivefourtwo/ebay-tool` (FastAPI + vanilla JS, eBay OAuth+Inventory/Offer,
  Browse comps) and `kanke/sell-smart` (batch-group → write-from-metadata pipeline)

## P0 — Project foundation  [app boots, health check passes]
- [ ] Apache-2.0: git init, LICENSE, .gitignore, README skeleton
- [ ] pyproject: core = FastAPI, uvicorn, SQLAlchemy, Alembic, Pillow, httpx, litellm,
       keyring, python-dotenv, pydantic v2, pytest;
       extras: `cleanup` (rembg)
- [ ] Env: .env.example, env loader, secret wrapper (keyring → env fallback)
- [ ] Server security: localhost bind default, opt-in LAN mode with access token, CORS
- [ ] DB schema + first Alembic migration (see schema decisions below) + seed defaults
- [ ] pytest config + conftest; module layout mirroring ebay-tool (modules/)

**Schema decisions (settle before first migration)**
- Tables: `batch`, `item`, `photo`, `listing`, `price_comp`, `setting`, `job`
- `item.facts` (model output) separate from `item_question` (question, answer, answered_at)
  so user input never mixes with model output
- Item `status` is derived/authoritative at item level; `listing.status` is per channel
  and must not contradict it — document the state machine, test transitions
- Use `position`, not `order`, for photo ordering
- `job`: id, kind, batch_id/item_id, status, attempts, error, progress, updated_at

## P1 — Provider interface  [unit tests pass with mocked calls]
- [ ] `Provider` protocol, two job types: vision and text (one call shape)
- [ ] LiteLLM adapter as the default router (covers Ollama, LM Studio, llama.cpp, vLLM,
       OpenAI, Anthropic, Gemini); independent vision/text model selection
- [ ] Settings page: provider, model names, per-job swap, off-machine indicator
- [ ] Unit tests: mock LLM responses, assert request shaping + response parsing
- [ ] Job worker: persisted queue, resume on startup, retry/backoff, cancel, progress

## P2 — Photo intake, grouping, cleanup  [3–4 item and 30+ photo tests group correctly]
- [ ] Multi-file upload + mobile capture (`<input capture>`) + browser thumbnails (Pillow)
- [ ] Verify phone capture over LAN on real devices; add local HTTPS option (mkcert /
      self-signed) if the browser requires it
- [ ] Cleaning: auto-rotate, strip EXIF location (default), optional rembg → cleaned_path
- [ ] photo rows + is_cover/position; keep originals, cleaned copies for posting
- [ ] Grouping: pre-cluster by EXIF time / image embeddings, then vision call confirms or
      splits clusters in chunks (never all thumbnails in one call); persist item drafts
- [ ] Drag-to-fix UI (vanilla JS): merge/split groups before generation
- [ ] Tests: small mixed batch; 30+ photo batch; drag-to-fix persistence

## P3 — Extract → clarify → validate  [fixture facts pass all validators]
- [ ] Extract prompt: full-size photos per item → facts JSON (plan schema + confidence/unknown)
- [ ] Clarify: ≤3 questions when key fields unknown/low-confidence, stored in `item_question`
- [ ] Price suggestion: AI range from facts, editable, plus eBay sold-search link
- [ ] Validator (code): per-channel title lengths, price present, banned words,
      numeric/string claim matching against facts (explicit scope: catches invented
      numbers, sizes, model numbers); optional LLM "unsupported claim" check, off by default
- [ ] Unit tests: valid facts, invented-spec rejection, missing price

## P4 — Site rules + channel prompts  [rules + prompts render expected output]
- [ ] Site rules: big/heavy → FB+Craigslist; small+shippable → eBay+FB+Craigslist;
      low value (<~$15–20) → FB only
- [ ] Prompts (modules/prompts/): eBay copy packet (≤80 char title, desc, category/aspects),
      Facebook (title/price/condition/desc), Craigslist full ad (pickup details)
- [ ] Craigslist pointer ad prompt written but gated behind "eBay posting enabled" flag
- [ ] Default ad-type rules + editable-in-settings
- [ ] Tests: each rule bucket → suggested sites; pointer disabled in Phase 1

## P5 — Approval screen, listing rows, settings  [approve-all excludes risky cards]
- [ ] listing rows per channel per item on generation
- [ ] Approval UI: cards (photos/title/price/condition), channel tabs, per-item + bulk
      toggles, "Approve all"
- [ ] Approve-all safety: excludes low-confidence facts / open questions until answered
- [ ] Settings: providers/models, site rules, FB prefill toggle (stub), location,
      Craigslist template
- [ ] Tests: bulk-set behavior, approve-all exclusion logic, status transitions

## P6 — Publish channels in scope  [clipboard queue + copy packets work]
- [ ] Craigslist clipboard queue: title→price→description, opens photo folder, full ad
      only; never touches the Craigslist page
- [ ] Facebook copy packet: title/price/category/condition/desc + photo folder/download
- [ ] eBay copy packet: title/category/aspects/desc/price, same pattern
- [ ] Contribution guide + README clause refusing any Craigslist form-filler/auto-poster PR
- [ ] Face/address detection warning in the UI (not docs only), shown before cloud vision

## P7 — Integration, exit gate, packaging  [10-item end-to-end passes]
- [ ] Exit gate: 10 household items w/ expected facts; flow upload→group→generate→approve→clipboard/packets
- [ ] Model bake-off: 50 real household items across candidate local models; pick the
      default Ollama vision model from results, record in README
- [ ] End-to-end pytest over the persisted job queue, including restart-mid-batch resume
- [ ] README run instructions + packaging: `pipx`/pip install + Docker Compose w/ Ollama
- [ ] Docs: first-run flow, privacy note (location stripping, what leaves the machine),
      model names verified at build time

## P8 — eBay comps: suggested price + similar-item link  [not started; needs eBay dev keys]
- [ ] User creates a free eBay developer app; keys go in keyring/.env (client id + secret)
- [ ] eBay Browse API client: OAuth client-credentials token (cached), item_summary/search
      by brand + model + item_type (fall back to item_type + color), limit ~20
- [ ] Run automatically after "Re-analyze photos" / first analysis; store matches in `price_comp`
- [ ] Suggested price = median of matching active listings, shown with low-high range;
      one-click "use this price" (never overwrite a price the user typed)
- [ ] Show a sample similar item (title, price, link, thumbnail) on the item card
- [ ] No matches (or no keys configured) -> show "No similar items found" / "eBay comps not set up"
- [ ] Caveats to show in the UI: Browse API gives ACTIVE asking prices, not sold prices
      (sold data = Marketplace Insights API, restricted access); keep the one-click
      "eBay sold items" search link as the manual check
- [ ] Tests: mocked eBay responses (matches, empty, error, rate limit); price math

## Later (deferred)
- eBay OAuth + Inventory/Offer auto-post, API comps, end-listing, sold-sync
  (first resolve: shared app identity vs per-user keys, account-deletion endpoint,
  RuName redirect for a local app)
- Craigslist pointer ads once eBay posting exists (check CL rules on outbound links)
- Facebook prefill extension (Chrome/Firefox), off by default
- Voice notes, more marketplaces (OfferUp, Mercari, Poshmark), other eBay countries
- Non-developer installer/launcher
