# CARDFORGE — Reusable Card-Art Batch Tool (Claude Code build brief)
### v1.0 · a backend-agnostic, config-driven art generator you point at ComfyUI or A1111 and run overnight

Build a **reusable** tool that turns a per-campaign art manifest into finished illustrations on your local GPU (ComfyUI or A1111), unattended. Art types are reusable profiles; a new campaign is just a config folder. The Still Hour is the first consumer; every future campaign reuses the same engine.

Provided to start from: `art_profiles.json` (the reusable art-type library), `cardforge_stub.py` (validated skeleton of the three tricky parts), and the existing art pipeline (`ART_PIPELINE_BRIEF.md`, `ART_SPEC.md`, `art_manifest_starter.json`) that this tool plugs into.

---

## 1. Design principles
- **Backend-agnostic.** One `Backend` interface; `ComfyBackend` and `A1111Backend` implement it. The rest of the tool never knows which is running. (A1111-compatible forks like Forge/reForge work through the A1111 adapter.)
- **Art types are profiles, not code.** `art_profiles.json` defines each type's model/workflow/dimensions/sampler/style framing/variants. Reusable across every campaign; overridable per campaign or per job.
- **Characters come from your existing tool.** Your Claude Code character-select tool becomes the **character resolver** — given a name, it returns `{lora, weight, trigger, refs}`. CardForge calls it; it doesn't reimplement character logic.
- **Crash-safe overnight.** A resume ledger means an interrupted run continues instead of restarting; completed work is never redone.
- **Campaigns are data.** `campaigns/{name}/` = a config + a manifest + a character map. Drop a folder, run.

---

## 2. Directory layout
```
cardforge/
  cardforge.py            # CLI entry
  backends/
    base.py               # Backend interface
    comfy.py              # ComfyBackend
    a1111.py              # A1111Backend
  profiles/art_profiles.json   # provided; reusable
  workflows/              # ComfyUI API-format workflow templates, one per art type
  post/                   # upscale, crop, organize
  characters/resolver.py  # thin wrapper over YOUR character-select tool
campaigns/
  still_hour/
    campaign.json         # backend, house style, output dir
    manifest.json         # scene-mode job list (see §5)
    characters.json       # name -> lora/trigger/refs (or delegates to your tool)
out/still_hour/           # illustrations + index.json (feeds framing)
state/still_hour.ledger   # resume ledger
```

## 3. Backend adapters (confirm endpoints against your installed versions)
**A1111** (`--api`): `POST /sdapi/v1/txt2img` with `{prompt, negative_prompt, steps, sampler_name, cfg_scale, width, height, seed, n_iter, override_settings:{sd_model_checkpoint}}`; switch model via `override_settings` (or `POST /sdapi/v1/options`); LoRA via `<lora:name:weight>` in the prompt; images return base64; progress via `/sdapi/v1/progress`.
**ComfyUI**: author one **API-format** workflow per art type (ComfyUI → Save (API Format)); `POST /prompt` with `{prompt:<graph>, client_id}`; **inject** the composed positive/negative, seed, width/height, checkpoint, and LoRA into tagged nodes (set a `_meta.title` on the text/sampler/loader nodes and locate them by title so edits survive graph changes); track via websocket `/ws?clientId=`; fetch outputs from `GET /view`.

Both implement `generate(positive, negative, params) -> [image_paths]`. The tool selects the backend from `campaign.json`.

## 4. Art-type profiles (provided)
`art_profiles.json` ships with 9 reusable types (investigator_portrait, asset, event, skill, treachery, enemy, location, agenda, minicard), each carrying dimensions, sampler/steps/cfg, a `comfy_workflow` ref, per-type positive/negative framing, `allow_character`, and `variants`. Set the `checkpoint`/`comfy_workflow` placeholders to your installed models. Extend with new types by adding entries — no code change.

## 5. Manifest (scene-mode) & prompt composition
A job = `{id, art_type, character?, scene, seed, overrides?}` — **scene text only**, not the full prompt. The tool composes the final prompt exactly as `cardforge_stub.py` does:
`<lora:..> {trigger}, {scene}, {profile.type_positive}, {campaign.style_positive}` / negative = `{campaign.style_negative}, {profile.type_negative}`.
→ **Update `build_art_manifest.py` to emit scene-mode** (store `scene` + `character` separately instead of pre-baking `STYLE`), so the tool owns composition and the same scenes render consistently across campaigns/style tweaks.

## 6. Runner / scheduler (the core)
- Load campaign + profiles + manifest; build the job queue (expand `variants` into seeds).
- **Resume:** skip jobs already in the ledger (`cardforge_stub.Ledger`); mark each on success. Interrupted runs continue.
- **Concurrency:** default serial for one GPU; a small pool if the backend/queue supports it.
- **Retry:** N attempts with backoff on failure/timeout.
- **Variants + curation:** generate `variants` per card into `out/.../{id}/{seed}.png`; the tool picks a default (or leaves all for QA).
- **Report:** write `out/{campaign}/report.json` and an optional **contact sheet** PNG per art type for morning review.
- **Output index:** `out/{campaign}/index.json` mapping `id -> chosen illustration path`, consumed by the Strange Eons framing stage.

## 7. Post-processing
Optional per profile: hires/upscale (Comfy node or A1111 `/sdapi/v1/extra-single-image`), auto-crop to the art window, save organized. Keep raw + processed.

## 8. CLI
```
cardforge generate --campaign still_hour                 # full batch (respects ledger)
cardforge generate --campaign still_hour --only sthr-elias
cardforge generate --campaign still_hour --resume        # continue overnight run
cardforge generate --campaign still_hour --art-type enemy --variants 4   # tune one type
cardforge contact  --campaign still_hour                 # build contact sheets for QA
cardforge profiles list   |   cardforge backends check   |   cardforge characters list
```

## 9. Overnight operation (the point of the tool)
Fire-and-forget: `cardforge generate --campaign still_hour` submits everything, the ledger makes it crash-safe, retries handle transient failures, per-job timeouts prevent hangs, a disk-space guard aborts cleanly, and `report.json` + contact sheets are ready for morning QA. Re-roll a bad card by bumping its seed and re-running (only that card regenerates). ~250 faces on a 4080 with a fast checkpoint (e.g. Krea 2 Turbo / SDXL-Lightning) is well under an hour of GPU time; overnight is ample even with big hires passes.

## 10. Reusability
A new campaign = a new `campaigns/{name}/` folder (campaign.json + manifest.json + characters.json). Profiles and backends are shared; the profile library grows once. Your character-select tool supplies consistency for any cast. Nothing about CardForge is Still-Hour-specific.

## 11. Fits the existing pipeline
CardForge **replaces Stage 1** (illustration batch) in `ART_PIPELINE_BRIEF.md` and emits `index.json` that **Stage 2 (Strange Eons framing)** consumes. Stages 3–5 (sheet packing → CDN → URL rewrite → `build_cards.py`) are unchanged. So this slots into everything already built.

## 12. Build phases (each with an acceptance test)
- **P0** — Backends: `A1111Backend` and `ComfyBackend` each generate one image from a hardcoded prompt. *Accept:* a PNG lands on disk from both.
- **P1** — Profiles + composition: load `art_profiles.json`, compose prompts per `cardforge_stub`. *Accept:* dry-run prints correct per-type prompts/params (the stub already does this).
- **P2** — Character resolver: wrap your character-select tool; names resolve to LoRA/trigger/refs. *Accept:* `sthr-elias` renders with the Elias LoRA.
- **P3** — Runner + ledger: batch the starter manifest; kill mid-run; resume. *Accept:* no completed card re-generates; the run finishes.
- **P4** — Variants + report + contact sheets. *Accept:* `report.json` + a contact sheet per art type.
- **P5** — Post-processing (upscale/crop) + `index.json`. *Accept:* `index.json` feeds a Strange Eons dry-run.
- **P6** — Second campaign smoke test: a throwaway `campaigns/demo/` with 3 jobs proves reusability. *Accept:* runs with zero code changes.

## 13. Provided files & first milestone
- `art_profiles.json` — reusable art-type library (validated).
- `cardforge_stub.py` — validated skeleton (composition + adapter interface + ledger).
- Extend `build_art_manifest.py` to scene-mode; wire your character tool into `characters/resolver.py`.

**First milestone:** run the 10-face Still Hour starter manifest end-to-end on your GPU (A1111 or Comfy), with the Elias LoRA, resumable, producing a contact sheet — then let the full manifest run overnight.
