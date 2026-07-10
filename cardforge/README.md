# CardForge

Reusable, backend-agnostic overnight card-art batch tool. Point it at ComfyUI or
AUTOMATIC1111, hand it a campaign folder, go to bed. Built to
`docs/design/CARDFORGE_BRIEF.md` + `HANDOFF_cardforge`.

**Nothing here is Still-Hour-specific.** A campaign (or any other Arkham mod's
art run) is a folder under `campaigns/<name>/`:

```
campaigns/<name>/
  campaign.json     backend, base_url, checkpoint, house style strings, output dir
  manifest.json     scene-mode job list: {id, art_type, scene, seed, character?}
  characters.json   name -> {lora, weight, trigger, refs[], description}
```

Drop a folder, run. That's the mod plug-in mechanism.

## CardForge Studio — the all-in-one app

```bash
python3 -m cardforge.studio        # opens http://127.0.0.1:8570
```

One window, three tabs, the whole pipeline:
- **Illustrate** — backend check, Step-0 seeds, starter/full batches (dry-run
  toggle), live log, gallery with click-to-curate variants, contact sheets.
- **Frame — Strange Eons** — setup links (strangeeons.cgjennings.ca /
  github.com/CGJennings/strange-eons / Arkham plugin / fonts), the two owner
  config seams (class-map + setting keys), one-click frame-bundle generation
  (SE script with your cards embedded), SE launch, exported-face coverage —
  plus **Render glyph placeholders**: instant faces with real Arkham symbols
  (`assets/fonts/ArkhamFontWithCodex.ttf` via `cardforge/glyphs.py`).
- **Apply to Mod** — writes `pipeline/art_urls.json` (local `file:///` mode for
  instant TTS testing, or a hosted base URL) and rebuilds cards → mod →
  download package.

Acceptance: `python3 cardforge/studio_selftest.py` (24 checks, drives the live
server end-to-end). The CLI below remains for headless/scripted use.

## Runbook (owner's rig)

```bash
pip install requests Pillow

# 1. Configure
#    - campaigns/still_hour/campaign.json: set "checkpoint" to your model file,
#      set "backend" ("a1111" | "comfy") and "base_url" if not default.
#    - Start your backend with its API on:  A1111: --api   ComfyUI: (default)
python3 -m cardforge.cardforge backends check --campaign still_hour

# 2. Step 0 — canonical portraits (the one creative seed)
python3 -m cardforge.cardforge seeds --campaign still_hour --variants 4
#    Curate out/still_hour/seeds/<char>/, train per-investigator LoRAs (or keep
#    refs), then fill "lora" in characters.json.

# 3. First milestone — the 6-face starter batch, end to end
python3 -m cardforge.cardforge generate --campaign still_hour --starter

# 4. The overnight run (crash-safe; rerun any time, done work is never redone)
python3 -m cardforge.cardforge generate --campaign still_hour

# 5. Morning QA
python3 -m cardforge.cardforge contact --campaign still_hour   # sheets per art type
#    Bad roll? bump that card's "seed" in pipeline/build_art_manifest.py, then:
python3 pipeline/build_art_manifest.py && python3 -m cardforge.cardforge sync --campaign still_hour
python3 -m cardforge.cardforge generate --campaign still_hour  # redoes only that card

# 6. Hand off to framing
python3 -m cardforge.cardforge index --campaign still_hour     # out/still_hour/index.json
```

Curation: to pick a specific variant for a card, write its filename into
`out/still_hour/<id>/chosen.txt` before running `index`.

## No GPU where you are?

`--dry-run` writes the **exact HTTP payloads** to `out/<campaign>/payloads/`
(A1111 JSON bodies / Comfy API-format graphs) plus stub PNGs, so the whole
pipeline — ledger, resume, report, contact sheets, index — runs and is testable
anywhere. `python3 cardforge/selftest.py` is the acceptance suite (20 checks).

## Design notes / deviations (flagged per the handoff)

- **Comfy progress**: polls `/history/{prompt_id}` instead of the `/ws`
  websocket (dependency-free; serial batch doesn't need live progress). Swap in
  websockets if you want a progress bar.
- **Endpoints** follow the current public docs for both engines but were only
  exercised in dry-run here — **verify on your installed versions** during the
  live P0 smoke (`backends check`, then a one-card `generate --only`).
- **Refs without LoRA**: the A1111 path renders without character consistency
  and says so in `report.json`; the Comfy path can take an IPAdapter workflow
  template later. LoRA is the primary consistency path.
- **Golden fixtures**: `prompts.json` / `seed_portraits.json` (owner-held)
  aren't in the repo; the selftest compares against them automatically if you
  drop `prompts.json` at the repo root.
- **Character resolver** is self-contained JSON now; the interface is one
  function so it can later delegate to `Pimpcats/Character-Select-SD-and-Video`.

## Where things land

```
out/<campaign>/<id>/<seed>.png     illustrations (variants per art-type profile)
out/<campaign>/payloads/           dry-run HTTP bodies
out/<campaign>/seeds/<char>/       Step-0 canonical portrait candidates
out/<campaign>/report.json         per-face status — the morning QA list
out/<campaign>/contact_<type>.png  QA contact sheets
out/<campaign>/index.json          id -> chosen path (framing stage input)
state/<campaign>.ledger.json       resume ledger
```
