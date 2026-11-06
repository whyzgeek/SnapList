# SnapList – Open-Source AI Listing Tool: Research & Build Plan

Oct 6, 2026 · @Amin

## Summary

SnapList (working name) is a free, open-source app that runs on your own computer: upload a batch of photos, AI groups them into items and writes every listing, you approve once, and it does the rest. eBay posts automatically, Facebook opens prefilled for you to click Publish, and Craigslist is a quick clipboard paste. Each item goes only to the sites you pick.

Key decisions:

- **Bulk in, one approval out.** Drop a folder or camera roll; several photos per item are grouped automatically; one screen to review and "Approve all".
- **Per-item sites.** Each item card has eBay, Facebook and Craigslist toggles. AI suggests a default from size, value and shippability; you can change any item or a selection at once.
- **eBay is fully automatic.** It is the only one of the three with an official listing API, so SnapList posts and ends listings there on its own.
- **Facebook is prefilled (opt-in).** A browser extension fills the whole form, photos included; you click Publish. Commercial tools do the same, but it still bends Facebook's automation rule, so each user turns it on knowingly.
- **Craigslist is a clipboard queue.** Its terms ban posting software, including form fillers, and set damages for anyone who distributes one. SnapList loads each field to your clipboard in turn; you paste.
- **Bring your own AI and run locally.** One setting switches between a local model (Ollama, free and private) and a cloud provider. One Python app, a SQLite file and a photos folder.

## Competitor landscape

Only one tool posts to Craigslist (Ivy Flip), and it skips eBay; every tool with good AI charts a monthly fee or AI credits. Prices and counts below are from each tool's own pages or Crosslist's September 2026 comparison, which is written by a competitor and reads as biased.

**Commercial**

| Tool | Starts at | eBay / FB / Craigslist | How it posts | AI from photos | Notable |
| --- | --- | --- | --- | --- | --- |
| [HeroST (Hero Stuff)](https://apps.apple.com/us/app/hero-stuff-sell-anything/id6479718293) | Free (5 scans), then subscription | Yes / Yes / No | Phone app, one tap | Yes: ID, price, title, description | Video and voice listings; pricing from eBay sold and FB data; API and MCP access announced |
| [Crosslist](https://crosslist.com/blog/best-crosslisting-apps-for-resellers) | $29.99/mo + AI add-on | Yes / Yes / No | Background autoposting, browser extension for some sites | Yes, paid add-on | Single universal form; folder of photos becomes listings; auto-delist |
| Vendoo | $14.99/mo ($24.99 with AI) | Yes / Yes / No | Background autoposting | Limited | Common form plus a form per marketplace; reported autodelist bugs |
| List Perfectly | $29/mo | Yes / — / No | Form filler: opens a tab per site, you click Submit | Capped per plan | Cheapest plan fills only images, title, description, price |
| Nifty | $39.99/mo | Yes / No / No | Cloud, extension for some sites | Yes, credit-based | Strong analytics; 6 marketplaces |
| Flyp | $9/mo | Yes / Yes / No | Autoposting | No | 100-day trial; reported glitches |
| [Closo](https://help.closo.co/a/how-the-crosslister-works) | Free crosslisting; AI from $29/mo | Yes / — / No | Extension; paid server-side browser | Paid AI agents | Posts one marketplace at a time to avoid looking like a bot; remembers category mapping |
| PrimeLister | $49.99/mo | Yes / — / No | Form filler, manual confirm | — | Mainly a Poshmark bot |
| [Ivy Flip](https://extscope.org/extension/fehabgcnhaffbpdhebnbllkbnomfadmg) | — | No / Yes / Yes | Chrome extension | — | Only tool found posting to Craigslist; \~240 users |

**Open source and hobby projects**

| Project | What it does | Posts to | AI | Reusable for SnapList |
| --- | --- | --- | --- | --- |
| [Sell Smart](https://github.com/kanke/sell-smart) | Groups mixed photos into items, writes title, description, price, tags | Nothing (copy only) | Gemini 2.5 Flash | Two-step pipeline: batch image analysis, then text from metadata |
| [ebay-tool (Inserat-Tool)](https://github.com/fivefourtwo/ebay-tool) | Local FastAPI app: photos to German listings, price research | eBay via API; Kleinanzeigen via Playwright | Claude vision | Closest architecture: module layout, eBay OAuth and Inventory flow, Browse API comps |
| [cross-listing-ai](https://getclawkit.com/skills/official-aryanj-nyc-cross-listing-ai) | Agent skill: intake, extract, clarify, price, confirm, generate, revise | Nothing (copy only) | Any agent model | The seven-step flow and a reviewed-item record before anything is written |
| fb-to-ebay skill | Copies a listing between Facebook and eBay | eBay API; FB via Playwright | Agent model | Shows the FB automation route and its fragility |
| secondhand-mcp | Searches FB, eBay, Depop, Poshmark listings | Read only | n/a | Comp search across marketplaces |

## Ideas worth borrowing

Twelve features recur across the leaders; SnapList takes all of them, adapted to a free local tool.

| Idea | Seen in | How SnapList uses it |
| --- | --- | --- |
| One universal form that shows only the fields each site needs | Crosslist | One review screen per item; channel tabs show the eBay, FB and Craigslist versions |
| Drop a folder of photos, get one listing per item | Crosslist, Sell Smart | AI groups photos by item before writing anything |
| Analyze images once, write text from the extracted facts | Sell Smart | Two-step pipeline; cheaper and works with small local models |
| Clarify before writing; disclose flaws | cross-listing-ai | Up to 3 questions (size, defects, included parts) before the draft |
| Talk instead of type | HeroST | Optional voice note, transcribed locally, merged into the facts |
| Price from comparable listings | ebay-tool, HeroST | eBay Browse API comps (low, median, high) plus a one-click sold-items search |
| Remember category choices | Closo | Category mapping saved per item type and reused |
| Post one site at a time, slowly | Closo | Publishing queue with spacing; no bursts |
| Delist everywhere when sold | Crosslist, Vendoo, Flyp, Nifty | eBay ended via API; FB and Craigslist get a "mark as sold" reminder |
| Background removal and photo cleanup | Crosslist, HeroST | Local rembg, crop, auto-rotate, strip location data |
| Log in once in a visible browser | ebay-tool | Facebook prefill runs in your own logged-in browser; you click Publish |
| Default shipping and policy profiles | Crosslist | eBay business policies picked once in settings |

## Gaps and how SnapList differs

The gap is a free, private tool for someone clearing out a house, not a $30-a-month reseller suite.

| Gap in the market | Evidence | SnapList answer |
| --- | --- | --- |
| No tool covers eBay, FB and Craigslist together | Only Ivy Flip does Craigslist, and it has no eBay | All three from one item record |
| Good AI is paywalled or metered | Crosslist AI add-on, Nifty credits, Vendoo $24.99 tier, List Perfectly caps | Free; you pick the model, local costs nothing |
| Photos and data go to a vendor's cloud | Every commercial tool is hosted | Runs on your machine; local model keeps photos at home |
| Form fillers leave fields blank | List Perfectly and PrimeLister skip category, per Crosslist's review | eBay listings built through the API with category and aspects filled |
| Tools quietly automate sites that forbid it | FB and Craigslist automation risks your account | Facebook prefilled with you clicking Publish (opt-in); Craigslist kept to clipboard pastes |
| Built for volume sellers | Bulk bots, closet sharing, analytics tiers | Built for 1 to 50 items at a time; bulk works but is not the point |

## Platform rules

Only eBay permits software to post; Facebook and Craigslist both forbid it, so SnapList automates eBay and assists with the other two.

| Platform | Official route | Rule that matters | SnapList does |
| --- | --- | --- | --- |
| eBay | [Inventory API](https://developer.ebay.com/api-docs/sell/inventory/overview.html): inventory item + location + offer, then publishOffer | Seller must opt in to business policies (payment, return, fulfillment); [sold-price data](https://developer.ebay.com/api-docs/buy/marketplace-insights/static/overview.html) is a limited-release API most developers can't get | Full auto-post and end-listing; comps from active listings via the Browse API |
| Facebook Marketplace | No public listing API for personal sellers | [Terms 3.2.3](https://developers.facebook.com/docs/development/terms-and-policies/automated-data-collection/) bar automated access without permission; bursts of listings and bots trigger Marketplace restrictions | Opt-in extension prefills the whole form, photos included, one item at a time; you click Publish. Off by default, with the risk stated |
| Craigslist | None for individuals | [Terms of use](https://www.craigslist.org/about/terms.of.use) ban any software except their app and normal browsers for posting, and set $1,000 per violation for distributing software that facilitates it | Clipboard queue outside the page: title, price, description loaded in turn, photo folder opened. Pointer ad when the item is on eBay, full ad when not. No code touches the Craigslist page, not even a form filler |

The Craigslist rule also binds the project itself: a contributed "Craigslist auto-poster" would expose the maintainers, so the contribution guide should refuse one.

## Product scope and user flow

A whole batch goes from photos to live ads with two touches from you: one approval screen, then Publish on each Facebook form and a few pastes per Craigslist ad.

1. **Bulk upload.** Drop a folder, select many photos on the desktop, or shoot on your phone (SnapList opened in the phone browser on home Wi-Fi). Several photos per item is expected.
2. **Auto-group.** AI sorts the photos into items; drag a photo to fix a wrong grouping.
3. **Generate everything.** For each item, in the background: facts (brand, model, condition, flaws), price from eBay comps, suggested sites, and every listing version. Items the AI is unsure about get up to 3 questions on their card.
4. **Approve.** One screen of item cards: photos, title, price, condition, and eBay, Facebook and Craigslist toggles. Edit anything, answer any questions, set sites for a selection at once, then "Approve all" or approve card by card.
5. **eBay, automatic.** Approved items with eBay on are published through the API, spaced out, with no further clicks.
6. **Facebook, prefilled (opt-in).** A posting queue opens the Marketplace form for each item with title, price, category, condition, description and photos filled in. You check it, click Publish, and SnapList moves to the next item.
7. **Craigslist, clipboard queue.** SnapList shows the category to pick, then loads title, price and description to your clipboard one after another and opens the item's photo folder. You paste three times, drag a photo, and post.
8. **Track.** A dashboard shows each item's sites and status. Mark sold once: SnapList ends the eBay listing and lists the Facebook and Craigslist ads to delete.

**Default site rules** (suggested per item, editable in settings, overridable on any card):

| Item looks like | Suggested sites | Craigslist and FB ad type |
| --- | --- | --- |
| Big, heavy or bulky (furniture, appliances, exercise gear) | Facebook + Craigslist | Full ad, local pickup only |
| Small and worth shipping (electronics, collectibles, branded clothing) | eBay + Facebook + Craigslist | eBay is the main ad; Craigslist is a short pointer to it |
| Low value (under about $15 to $20) | Facebook only | Full ad |

The Craigslist pointer ad only exists when the item is on eBay; otherwise SnapList writes a full Craigslist ad with description, a few photos and pickup details.

**First release:** steps 1 to 4 and 7, with Facebook as a copy packet until the extension ships. **Later:** eBay posting, the Facebook prefill extension, voice notes, sold-sync from eBay orders, more marketplaces as copy packets (OfferUp, Mercari, Poshmark), other eBay countries.

## Architecture and tech stack

One Python process on your computer serves the web page, runs the AI calls and talks to eBay; nothing else needs to be hosted.

&#91;embedded content: SnapList architecture · 6 local parts, 4 outside services\]

Photos and data never leave the machine unless you choose a cloud AI or publish to eBay.

| Layer | Choice | Why |
| --- | --- | --- |
| Server | Python 3.12, FastAPI, background job queue | Same stack as ebay-tool, which already proves the eBay flow; the queue processes a whole batch while you wait |
| Storage | SQLite + photos folder | Zero setup; one folder to back up |
| Web UI | Installable web page (PWA), HTMX or Svelte | Phone camera and multi-photo upload work in the browser; no app store |
| Images | Pillow, rembg | Resize, rotate, strip location data, remove background locally |
| AI routing | Provider interface, e.g. LiteLLM | One call shape for Ollama, OpenAI-compatible servers, Anthropic, Gemini |
| eBay | OAuth + Inventory, Account, Taxonomy and Browse APIs | Official posting, policies, category suggestions, price comps |
| Facebook prefill | Browser extension (Chrome, Firefox) that asks the local server for the next approved item | Fills the Marketplace form in your own browser; never clicks Publish; off by default |
| Craigslist queue | A small page in the SnapList UI using the clipboard | Loads one field at a time; never touches the Craigslist site |
| Packaging | `pip install`, Docker Compose with Ollama | One-command start on Mac, Windows or Linux |

## AI layer

Every AI call goes through one provider interface with two jobs (look at photos, write text), so a local model and a cloud model are interchangeable per job.

**Providers.** Ollama for local models; any OpenAI-compatible server (LM Studio, llama.cpp, vLLM); Anthropic; Google Gemini; OpenAI. A routing library such as LiteLLM can cover these behind one call. Settings let you pick a different provider for vision and for writing, for example a local vision model plus a cloud writer.

**Pipeline (borrowed from Sell Smart and cross-listing-ai):**

1. *Group* — all thumbnails in one vision call; returns which photo indexes belong together.
2. *Extract* — full-size photos per item; returns structured facts (schema below), each with a confidence and "unknown" allowed.
3. *Clarify* — if key fields are unknown or low-confidence, generate at most 3 questions.
4. *Route and write — suggest sites from the default site rules, then a text-only call writes one output per chosen site from the facts plus answers*.
5. *Check* — code, not AI, validates lengths, banned words, price present, no invented specs (every claim must trace to a fact).

**Suggested models** (as of mid-2026 roundups; benchmark on your own photos):

| Hardware | Vision model | Notes |
| --- | --- | --- |
| No GPU or 4 GB VRAM | Gemma 3 4B (`gemma3:4b`) | About 3 GB; slow on CPU but works |
| 8 GB VRAM | Qwen3-VL 8B (`qwen3-vl:8b`) | Most-recommended local all-rounder |
| 20 to 24 GB VRAM | Qwen 3.6 27B or Gemma 4 31B | Best local brand recognition; Qwen 3.6 vision runs in llama.cpp or LM Studio, not yet Ollama |
| Any, cloud | Claude, Gemini Flash, GPT | Best accuracy on brands, labels, collectibles; costs per call |

**Item facts schema** (the contract between extract and write):

```json
{
  "item_type": "stand mixer",
  "brand": "KitchenAid",
  "model": "unknown",
  "color": "red",
  "size": null,
  "condition": "used_good",
  "flaws": ["scratch on bowl rim"],
  "included": ["bowl", "whisk"],
  "visible_text": ["KitchenAid", "5 Qt"],
  "confidence": {"brand": 0.95, "model": 0.2},
  "questions": ["Does it power on and run at all speeds?"]
}
```

**Channel outputs:** eBay title (80 characters max), description, category suggestion, item aspects; Facebook title, price, condition, description; Craigslist pointer ad (title with price, 3 to 5 lines, eBay link) when the item is on eBay, otherwise a full ad with pickup details.

## Data model

Five tables in one SQLite file hold everything, including which sites each item goes to; photos live as files beside it.

| Table | Key fields | Notes |
| --- | --- | --- |
| item | id, status (draft, ready, approved, listed, sold), facts JSON, price, suggested\_sites, chosen\_sites, batch\_id, created\_at | One physical thing for sale; the facts JSON follows the schema above |
| photo | id, item\_id, path, order, is\_cover, cleaned\_path | Originals kept; cleaned copies (background removed, location stripped) used for posting |
| listing | id, item\_id, channel (ebay, facebook, craigslist), title, body, fields JSON, external\_id, url, status, posted\_at | One row per channel; eBay stores SKU, offer id and listing id |
| price\_comp | id, item\_id, source, title, price, url, fetched\_at | Comparable listings shown on the price step |
| setting | key, value | Site rules, Facebook prefill on/off, providers, model names, eBay tokens (encrypted), business policy ids, location, Craigslist template |

## Roadmap and milestones

Phase 1 already does most of the work: a batch of photos in, every listing written and approved on one screen, with no eBay developer setup needed.

&#91;embedded content: SnapList roadmap · 5 phases, each with an exit gate\]

Each phase is usable on its own, so the project can stop after any gate and still be worth having. Phase 1 is a good first build to start this week:

- [ ] Repo skeleton: FastAPI app, SQLite models, settings page, job queue
- [ ] Provider interface with Ollama and one cloud provider
- [ ] Bulk upload and photo auto-grouping with drag-to-fix
- [ ] Extract prompt + facts schema + validation
- [ ] Site rules and per-item suggestions
- [ ] Write prompts for eBay, Facebook and Craigslist (pointer and full ad)
- [ ] Approval screen: item cards, site toggles, bulk set, "Approve all"
- [ ] Craigslist clipboard queue and Facebook copy packet
- [ ] Test set of 10 household items with expected facts

## Risks and open questions

The biggest risk is a wrong AI claim on a live eBay listing, so nothing publishes without your review.

| Risk | Mitigation |
| --- | --- |
| AI invents a model number, size or spec | Facts allow "unknown"; the check step blocks claims not in the facts; nothing posts before approval |
| "Approve all" lets a bad listing through | Cards with low-confidence facts or open questions are excluded from "Approve all" until answered |
| Local models misread brands or small labels | Ask for a close-up of the label; offer a cloud model for the vision step only |
| Wrong grouping merges two items into one listing | Grouping shown first as photo stacks; drag to fix before generation |
| Price comps skew high (active listings, not sold) | Show the range, default below median, link to eBay sold search |
| Facebook restricts accounts that use the prefill extension | Opt-in with the risk stated; one item at a time at human pace; you click Publish; easy to switch off |
| Facebook changes its form and the prefill breaks | Falls back to the copy packet; form selectors kept in one file for quick fixes |
| eBay setup is a hurdle (developer keys, business policies) | First-run wizard; a guide with screenshots; eBay can be skipped and used as copy packets |
| Requests to add a Craigslist form filler or auto-poster | State the rule in the README and contribution guide; decline those pull requests |
| Personal data in photos (faces, addresses, location metadata) | Strip location data by default; warn when the AI sees a face or address |

Open questions:

- [ ] Will each user register their own eBay developer keys, or will the project apply for one shared app identity?
- [ ] Phone experience: a web page on home Wi-Fi is enough, or is a native app wanted later?
- [ ] License: Apache-2.0 (easy reuse) or AGPL-3.0 (keeps forks open)?
- [ ] Which local vision model is the default, decided by a test on 50 real household items?

## Sources

- [Crosslist: Best 10 cross listing apps in 2026](https://crosslist.com/blog/best-crosslisting-apps-for-resellers) (competitor-written, updated Sep 30, 2026)
- [Hero Stuff on the App Store](https://apps.apple.com/us/app/hero-stuff-sell-anything/id6479718293) and [HeroST on G2](https://ai.g2.com/marketplace/tools/herost)
- [Closo: How the Crosslister works](https://help.closo.co/a/how-the-crosslister-works)
- [Ivy Crosslisting extension listing](https://extscope.org/extension/fehabgcnhaffbpdhebnbllkbnomfadmg)
- [Sell Smart on GitHub](https://github.com/kanke/sell-smart)
- [ebay-tool (Inserat-Tool) on GitHub](https://github.com/fivefourtwo/ebay-tool)
- [cross-listing-ai skill](https://getclawkit.com/skills/official-aryanj-nyc-cross-listing-ai)
- [eBay Inventory API overview](https://developer.ebay.com/api-docs/sell/inventory/overview.html) and [required fields for publishing](https://developer.ebay.com/api-docs/sell/static/inventory/publishing-offers.html)
- [eBay Marketplace Insights API (limited release)](https://developer.ebay.com/api-docs/buy/marketplace-insights/static/overview.html)
- [Meta: Automated data collection policy](https://developers.facebook.com/docs/development/terms-and-policies/automated-data-collection/)
- [Craigslist terms of use](https://www.craigslist.org/about/terms.of.use)
- [Best local vision language models 2026 (tinyweights.dev)](https://tinyweights.dev/posts/best-local-vision-language-models-2026/) and [InsiderLLM vision model guide](https://insiderllm.com/guides/vision-models-locally/)
