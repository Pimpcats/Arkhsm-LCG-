# THE STILL HOUR — SCED Build Brief (for Claude Code)
### v1.0 · engineering handoff to implement the campaign in Tabletop Simulator (SCED)

You are implementing an original Arkham Horror LCG campaign, **The Still Hour**, as a module for the SCED (Super Complete Edition) Tabletop Simulator mod. The *design is finished and frozen* — it lives in six markdown specs (below). Your job is the build: card content as data, plus the custom Lua that makes the campaign's novel systems work.

## 0. Source of truth
The design is authoritative in these files (read them first, in order):
1. `THE_STILL_HOUR_design.md` — concept + the five novel systems.
2. `THE_STILL_HOUR_cards_v0.2.md` — investigators, signatures, weaknesses, Recollections, with exact wording.
3. `THE_STILL_HOUR_aging_3p_v0.3.md` — the Aging system + 3-player constants.
4. `THE_STILL_HOUR_encounter_v0.4.md` — encounter deck, the Occultation clock, the Latecomer.
5. `THE_STILL_HOUR_campaign_guide_v0.5.md` — every scenario, interludes, the finale generator.
6. `THE_STILL_HOUR_log_sheet.md` — the persistent campaign log fields.

Where this brief and a design doc disagree, **the design doc wins** — flag the conflict, don't silently resolve it.

## 1. Repo & environment
- **Fork `argonui/SCED`.** It is developed as *source* (Lua under `src/`, object JSON, XML UI) and **bundled** into the single TTS save via its build tooling (luabundle + the repo's build scripts). **Do not hand-edit the 11 MB save JSON** — work in source and rebuild. Confirm the exact build/watch commands from the repo README before writing code.
- State that reaches TTS is a save file plus Steam-hosted assets. Custom campaign content is distributed as **download-box placeholders**: a `Custom_Model` with `GMNotes={"filename":"..."}` whose Lua calls `GlobalApi.placeholderDownload(filename)`, pulling `{filename}.json` from `SOURCE_REPO` (`https://github.com/Chr1Z93/SCED-downloads/releases/latest/download/`). Our campaign ships the same way (a `the_still_hour.json` release asset + a placeholder box).
- Useful existing surface (verify signatures in-repo): `GlobalApi.placeholderDownload`, `GlobalApi.drawBorderAroundCard`, the chaos-bag/bless-curse manager, the campaign save/import-export, and the metadata-driven token spawner.

## 2. Data model (verified against Arkham SCE 4.8.0)
Every card is a TTS `Card` object:
- `Name="Card"`, `Tags=[<Type>,"PlayerCard"]` (or `[<Type>,"EncounterCard"]`), `SidewaysCard=true` **only** for Investigators.
- `CardID = int(deckId + 2-digit gridIndex)`; art lives in `CustomDeck[deckId]` as `FaceURL`/`BackURL` on a `NumWidth×NumHeight` sheet. Investigators use `UniqueBack=true` (separate deckbuilding back).
- **`GMNotes`** is a JSON string holding *mechanical metadata only* — printed rules text lives on the **art**, never here. The mod's Global reads `GMNotes` to drive tokens, upgrades, doom, etc.

**GMNotes schema (authoritative field list, reverse-engineered from the 2,322-card base):**
`id, type, class, traits, cycle` (all cards); plus by type —
- Investigator: `willpowerIcons, intellectIcons, combatIcons, agilityIcons, health, sanity, signatures ([{id:count}]), elderSignEffect ({description}), extraToken`.
- Asset/Event/Skill: `cost, level, willpowerIcons/intellectIcons/combatIcons/agilityIcons/wildIcons, slot, uses ([{count,type,token}]), permanent, startsInPlay, bonded, customizations`.
- Weakness/encounter: `weakness (bool)`, and for enemies the fight/health/evade live on the art; metadata carries `type, traits, class`.

Types in use: `Investigator, Asset, Event, Skill, Enemy, Treachery, Location, Story, Minicard, UpgradeSheet`.

## 3. What to build — the `StillHour` module
Card content is **data** (see §4). Everything below is the custom Lua. Priorities are ordered; each has an acceptance test.

**P0 — Load the vertical slice.** Import `stillhour_starter.json` (Elias + 2 signatures + weakness). *Accept:* all four spawn, display, and the mod reads their metadata (right class colour, deckbuilding recognizes the signatures via the `signatures` field).

**P1 — Card pipeline.** Stand up the generator (`build_cards.py`, provided) as the authoring path: spec → SCED objects. Extend the spec to all player cards, then encounter cards. *Accept:* the full player-card set generates and loads; ArkhamDB-style deck import is not required (campaign box distributes them).

**P2 — Campaign state manager (the core; hardest).** One persistent state object storing: **banked Memory** (cap 18), **Dissonance** (0–18, with scar-on-reset), the **Hourglass** (Hour I–IX), **Years** per investigator, the **Knowledge Track** flags, and **once-per-loop / per-loop test-type flags**. Persist via the mod's campaign save so it **survives node travel *and* resets**. *Accept:* set values, travel between "nodes," trigger a reset — Memory/Knowledge/Years persist; Dissonance drops to scar; once-per-loop flags clear; Hourglass resets.

**P3 — The `[static]` token + Dissonance bands.** Add a `[static]` chaos token (−3; on reveal, raise Dissonance by 1). Band logic = thirds of the reset threshold (Calm/Glitch/Noticed), auto-managing baseline `[static]` count. *Accept:* raising Dissonance across a band boundary adds/removes the right tokens; revealing `[static]` bumps Dissonance.

**P4 — Loop bookkeeping across nodes.** Implement "once per loop" and "did you perform test-type X last loop" (for `Muscle Memory`) as flags that persist across node transitions within a loop and clear on reset. *Accept:* an ability marked once-per-loop used at node A is unavailable at node B of the same loop, available again after a reset.

**P5 — The Latecomer.** Elite enemy that cannot be defeated/attacked/evaded; only **Hold Back** (an action test) exhausts it and rewinds the Hourglass; it attacks 2/2 and raises Dissonance; enters at the Noticed band or Hour VIII. *Accept:* no effect removes it; Hold Back works; it hunts the highest-Memory investigator.

**P6 — Occultation clock + location toggles.** The Hour deck (fixed I–IX) resolves "when reached" effects as the Hourglass advances (resolving each skipped Hour in order); Knowledge facts edit specific Hours and flip location fronts/backs. *Accept:* a big Skip resolves intermediate Hours; flagging "The Hour Was Wrong" removes Hour IV.

**P7 — Aging.** Apply bracket drift to investigator base stats at the interlude (physical −1 / mental +1/+2, health/sanity deltas, floors at 1), and an interlude UI to add Years, bank Memory, and buy Recollections. *Accept:* crossing into Weathered applies the locked drift; Elder/Ancient apply health/sanity deltas; 18 Years ages out.

**P8 — Package.** Ship as a `the_still_hour.json` download-release asset + a placeholder campaign box, matching the mod's distribution pattern.

## 4. Card authoring pipeline (provided)
- `build_cards.py` — generator: reads a spec, emits valid `Card` objects (correct `GMNotes`, `CustomDeck`, `CardID`, `GUID`, `Tags`, `SidewaysCard`). Already produces the validated `stillhour_starter.json`.
- `stillhour_cards_spec.json` — the spec format to extend (one dict per card).
- **Art (do last, per the owner):** render frames in **Strange Eons** (Arkham LCG plugin) from the card text in `cards_v0.2`/`encounter_v0.4`; generate illustration on the owner's local Stable Diffusion rig; pack faces onto sheets; host on Steam Cloud; replace the `placehold.co` URLs in the spec with the Steam URLs. The starter uses placeholders so it loads today.

## 5. State-persistence design note (read before P2)
This is the make-or-break system. TTS Lua state does not automatically survive scene changes; SCED already persists **campaign** state through its save/load and import/export. Build the StillHour state as **one owned object** that (a) serializes to its `onSave`/`LuaScriptState`, and (b) registers with the mod's campaign save so a reset (board wipe) and node travel both preserve it. Everything in P4/P6/P7 reads/writes through this one manager — do not scatter state across cards. A card asks the manager ("is my once-per-loop flag set?"), never stores loop state itself.

## 6. Conventions & gotchas
- Work in source; rebuild the save with the repo's tooling. Keep Lua modular; the mod bundles with luabundle.
- GUIDs must be unique; the mod has a GUID reference handler — don't hardcode collisions.
- Chaos-bag edits go through the existing bag manager, not by mutating the bag object directly.
- Test at **3 investigators** (the tuned baseline); the constants are `4×/6× investigators` for Dissonance and `6× investigators` for the Memory cap.
- Don't put printed rules text in `GMNotes`; it belongs on the art.

## 7. Testing
- Unit-ish: drive the state manager via console (`/execute`) — set Dissonance, advance the Hourglass, trigger resets, assert persistence.
- Integration: play the Prologue → first reset → Loop 1, verifying Memory carry-over and the interlude.
- Regression: after each phase, reload the save and confirm campaign state restores.

## 8. Definition of done for the first milestone
Vertical slice playable: Elias's deck imports with his signatures/weakness recognized; a working Dissonance track with the `[static]` token; Memory that banks across one manual reset; and the campaign box downloads the starter content. That proves the whole spine end-to-end; the rest is content plus the remaining systems in priority order.

---
### Files in this handoff
- `SCED_BUILD_BRIEF.md` (this file)
- `stillhour_starter.json` — validated Elias slice, loadable today
- `build_cards.py` — the card generator
- `stillhour_cards_spec.json` — the spec format to extend
- the six design docs (source of truth)
