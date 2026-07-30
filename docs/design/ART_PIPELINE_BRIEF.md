# THE STILL HOUR — Art Pipeline & Setup Brief (for Claude Code)
### v1.0 · install, then build the overnight art harness that fills every card's art and inserts it into the SCED build

Goal: turn `art_manifest_starter.json` (and its full extension) into finished, framed card faces hosted on a CDN, with their URLs written back into the card spec — as an **unattended overnight batch**. The human supplies reference images and does morning QA; everything else automates.

Read first: `ART_SPEC.md` (direction), `SCED_BUILD_BRIEF.md` (card data model), and the manifest/generator (`art_manifest_starter.json`, `build_art_manifest.py`).

---

## PART A — SETUP (do once)

### A1. Strange Eons + the Arkham plugin (the framer)
1. Install **Strange Eons 3** (the community card-design app; free, cross-platform, JVM-based).
2. In Strange Eons: **Toolbox → Manage Plug-ins → Catalog**, install the **Arkham Horror LCG** card plug-in (community-maintained; provides the investigator/asset/event/skill/treachery/enemy/location/agenda templates used by fan cards). Confirm the exact plug-in name in the catalog before scripting against it.
3. Verify Strange Eons **scripting** works: SE has a JavaScript scripting console and supports **batch card creation + PNG export** via scripts. This is the automation seam — you'll drive card creation and face export from a script, not the GUI.
4. Note the template/component names the plug-in exposes (open one card of each type, inspect its component keys) — the frame-render stage maps our `frame` field to these.

### A2. Krea (the illustrator) — pick ONE
- **Hosted API (simplest):** create a Krea account → **API Tokens** → make a key. The API is REST at `https://api.krea.ai`: POST to a generate endpoint with `{prompt, width, height, steps, model}`, receive a `job_id`, then either poll `GET /jobs/{job_id}` or pass an `X-Webhook-URL` header to be notified on completion. Failed jobs aren't billed. Krea 2 Medium (~$0.03/img) suits illustration; it takes up to 10 weighted reference images and supports LoRAs.
- **Local (free, uses the 4080):** download **Krea 2 Turbo/Raw open weights** (community license) and run them in **ComfyUI**. Same manifest drives it; the runner calls the local endpoint instead of the API. Turbo generates in ~2s, so ~250 faces is well under an hour of GPU time.

### A3. Hosting — skip Steam
TTS accepts **any** image URL. Use an **S3/GCS bucket or CDN** (or GitHub raw). Krea's API can PUT output directly to a presigned S3/GCS/Azure URL, so hosting can be fully automated — no Steam uploader.

### A4. Repo & deps
Work in the SCED fork from `SCED_BUILD_BRIEF.md`. Add an `/art` workspace: `art/manifest.json`, `art/refs/` (reference images/LoRAs), `art/illustrations/`, `art/faces/`, `art/sheets/`. Python deps: `requests`, `Pillow` (compositing/packing), plus the Krea SDK or raw HTTP.

---

## PART B — THE PIPELINE (five stages)

### Stage 1 — Illustration batch **(the overnight, unattended job)**
A runner iterates the manifest and, for each entry with a non-null `prompt`:
- Submits a Krea job (`prompt`, `negative`, `gen_size`, `seed`, and the `reference`/`lora` for character consistency).
- Respects concurrency (Krea auto-queues a backlog; cap parallel submits, e.g. 4–8).
- Collects results via **webhook** (preferred) or polling; **retries** failures (they aren't billed); writes each illustration to `art/illustrations/{id}.png` (or has Krea PUT it to the bucket).
- Emits `art/report.json`: per-card status, seed, cost, URL — the morning QA list.
- **Unattended design:** submit-all → collect-via-webhook → retry-failed → report. No human in the loop until QA. Optionally a `--review-gate` that pauses framing until a human approves `report.json`.
*Accept:* running the 10-entry starter manifest produces 9 illustrations (1 is text-only) with a clean report.

### Stage 2 — Frame render (Strange Eons)
A Strange Eons script reads the **card spec** (`stillhour_cards_spec.json`, extended) + `art/illustrations/` and, per card: creates the component of the matching `frame`, sets title/traits/cost/stats/text/icons from the spec, drops in the illustration, and **exports the finished face** to `art/faces/{id}.png`. Investigator backs and other text-only faces are rendered here with no illustration.
*Accept:* every card in the spec yields a framed `faces/{id}.png` with correct stats and text.

### Stage 3 — Sheet packing (Pillow)
Pack faces into TTS grid sheets (`NumWidth×NumHeight`, e.g. 7×3), one sheet per deck, emitting a `{card_id → (deckId, gridIndex)}` map. Respect `CardID = deckId×100 + gridIndex`. Investigator unique backs get their own single-card decks.
*Accept:* sheets in `art/sheets/`, plus a deck-index map consumed by Stage 5.

### Stage 4 — Hosting
Upload each sheet to the bucket/CDN (or have Krea presign-upload the composited sheets). Produce `{deckId → FaceURL/BackURL}`.
*Accept:* every sheet has a public URL that loads in a browser.

### Stage 5 — URL insertion → regenerate cards
Rewrite the card spec's `CustomDeck` FaceURL/BackURL and `CardID` grid indices from the Stage 3 map + Stage 4 URLs, then run `build_cards.py` to regenerate `stillhour_starter.json` / the full deck with real art.
*Accept:* the regenerated bag loads in SCED showing framed, illustrated cards — no placeholders.

---

## PART C — What still needs a human
1. **Reference images / LoRA** per investigator (once): generate the 5 canonical portraits, then train a LoRA or save them as reference images (§2 of `ART_SPEC.md`). This is the only creative seed the batch needs.
2. **Art QA:** review `art/report.json` in the morning; re-queue any card with a bad roll (bump its seed). This is curation, not labor.
3. Everything else — submission, collection, retries, framing, packing, hosting, URL insertion — is automated.

---

## PART D — First milestone
Run the **10-entry starter manifest** end-to-end: Krea batch → Strange Eons frames → one packed sheet → CDN → rewrite → reload in SCED. That proves the whole art pipeline on the Elias slice before scaling to the full ~250 faces. Then extend the manifest (per `ART_SPEC.md §5`) and let it run overnight.

---

### Files in this handoff
- `ART_PIPELINE_BRIEF.md` (this file) · `ART_SPEC.md` (direction)
- `build_art_manifest.py` · `art_manifest_starter.json` (the job list)
- + the card-build handoff (`SCED_BUILD_BRIEF.md`, `build_cards.py`, `stillhour_cards_spec.json`) and the six design docs.
