# THE STILL HOUR — Art Handoff
*Everything the art pass needs, current as of this repo state. Supersedes the
inventory assumptions in `ART_PIPELINE_BRIEF` / `CARDFORGE_BRIEF` (both still
define the tooling); reflects CO-001/CO-002 (the boss is **The Appointed**) and
the Victory elites.*

## What exists right now

| Piece | State |
|---|---|
| `pipeline/art_manifest.json` | ✅ **complete scene-mode manifest — 41 faces** (36 illustrated + 5 text-only investigator backs), derived from the card specs with an authored scene per card. Regenerate any time: `python3 pipeline/build_art_manifest.py` (fails loudly if a spec card lacks a scene). |
| `pipeline/art_manifest_starter.json` | ✅ 6-face first-milestone subset (Elias slice + the Appointed). |
| `docs/design/art_profiles.json`* / `cardforge_stub.py`* | Provided tooling seeds — profiles per art type, validated composition/ledger skeleton. (*shipped in the project zip; copy beside CardForge when you build it.*) |
| CardForge itself | ✅ **built** — `cardforge/` (A1111 + ComfyUI backends, seeds/generate/contact/index CLI, resume ledger, dry-run mode; 20-check selftest). Runbook: `cardforge/README.md`. Live-backend smoke still needs your GPU. |
| Strange Eons framing script | ⏳ not built — `ART_PIPELINE_BRIEF` Stage 2. |
| Card faces today | placehold.co placeholders; the mod loads and plays with them. |

**Art blocks nothing.** The playtest path is independent; art can run last, in parallel.

## Face inventory

- **Now (in the manifest): 41** — 5 investigators (+5 text-only backs), 10 signatures, 5 weaknesses, 10 Recollections, 3 Appointed boss cards, 3 Named Victory elites.
- **Later (~64, after the content data pass):** 9 Occultation Hour cards (`agenda` type, landscape), ~26 encounter-spine cards, ~25 locations (front/back variants for the Lantern Room and Town Hall Steps), ~14 node-set cards. Add scenes to `SCENES` in `build_art_manifest.py` as those cards land in the specs — the generator enforces coverage.

## The five stages (who does what)

1. **Illustrate** *(your GPU / Krea — unattended overnight)*: build CardForge per its brief (or drive A1111/Comfy by hand for the starter), point it at `art_manifest.json`. Composition = character LoRA/ref + scene + type framing + house style (style strings live in the campaign config / `cardforge_stub.py`). **Human seed needed once:** 5 canonical investigator portraits → LoRA or reference images (`elias/ayako/cass/sera/birdie` — descriptions in the old manifest generator's character bible, preserved in git history, and in `ART_SPEC.md`).
2. **Frame** *(Strange Eons + Arkham plugin, your machine)*. Get the tools:
   Strange Eons 3 → strangeeons.cgjennings.ca (downloads page; source at
   github.com/CGJennings/strange-eons) · the Arkham
   plugin (current external version) → linked from the Barnaby Files guide (ask
   on the Mythos Busters Discord if the link moves) · the AH font pack → Mythos
   Busters Discord · optional hi-res raw blanks for reference/one-offs → the BGG
   thread "Hi-res blank templates for custom investigator cards". Then: script creates each component from `stillhour_cards_spec.json` + `stillhour_encounter_spec.json` (title/traits/cost/icons/stats) + the illustration, exports `faces/{id}.png`. Card **rules text comes from `cards_v0.2` / `encounter_v0.4 §5/§5b`** — GMNotes carries mechanics only, never printed text.
3. **Pack** *(Pillow)*: faces → TTS grid sheets per deck; `CardID = deckId×100 + gridIndex`. Today every card is its own 1×1 deck (ids 95010–95045), so a first pass can skip packing entirely and host single faces.
4. **Host**: any public URL (S3/GCS/GitHub raw — not Steam-only). TTS just needs a fetchable image.
5. **Rewrite**: swap the `placehold.co` URLs for hosted ones. Cleanest: add a `faceURL`/`backURL` override per card in the specs and teach `build_cards.py`'s `face_ph` fallback to prefer them (3-line change), then `build_cards.py && bundle_mod.py && package_download.py` regenerates everything.

## Direction guardrails (from ART_SPEC)
Muted, desaturated, painterly, 1920s New England, starless folding sky; uncanny not gory. **The Appointed is the key image** — "a tall wrong silhouette… not quite arriving"; restraint is the point, never fully resolve it. The negative prompt (no text/borders/modern/cheerful) is in the campaign style config.

## Acceptance
- Starter milestone: 6 starter faces end-to-end (illustrate → frame → host → rewrite → reload in TTS showing real art on the Elias slice).
- Full pass: all 41; every face loads in TTS; investigators sideways with distinct deckbuilding backs; a contact sheet per art type for morning QA.

## What only you can do
1. The 5 canonical portraits + LoRA training (creative seed, once).
2. Running the GPU batch (this container has no GPU/Steam).
3. Morning QA — re-roll bad faces by bumping that card's `seed` in the manifest and re-running (the ledger only redoes that card).
