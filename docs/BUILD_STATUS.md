# THE STILL HOUR — SCED build status

Tracks the `SCED_BUILD_BRIEF.md` priorities. This session delivered the
**card pipeline (all player cards)** and the **campaign state manager core**
(P1–P4 + the P6/P7 data models), all runnable and tested offline.

## Priority ladder

| # | System | Status | Where |
|---|--------|--------|-------|
| P0 | Vertical slice loads (Elias + 2 sig + weakness) | ✅ generated + loadable mod | `dist/stillhour_starter.json`; full loadable save `dist/the_still_hour_mod.json` (`pipeline/bundle_mod.py`) |
| P1 | Card pipeline → all player cards | ✅ done | `pipeline/build_cards.py`, `pipeline/stillhour_cards_spec.json`, `dist/the_still_hour.json` (30 cards) |
| P2 | Campaign state manager (Memory/Dissonance/Hourglass/Years/Knowledge/flags) + persistence | ✅ core done | `src/StillHour/CampaignState.ttslua` |
| P3 | `[static]` token + Dissonance bands + chaos-bag banding | ✅ done | `src/StillHour/Dissonance.ttslua`, `Constants.ttslua` |
| P4 | Once-per-loop + per-loop test-type flags across node travel | ✅ done | `src/StillHour/LoopFlags.ttslua` (+ CampaignState) |
| P5 | The Appointed (staged Approach, undefeatable / Hold Back / hunts most-Memory) | ✅ done (CO-002) | `src/StillHour/Appointed.ttslua`, `CampaignState.ttslua`, clock/band drivers; cards `dist/the_still_hour_encounter.json` |
| P6 | Occultation clock + location fact-toggles | ✅ done | `src/StillHour/Hourglass.ttslua`, `Locations.ttslua`, `Knowledge.ttslua` |
| P7 | Aging bracket drift + interlude | ✅ logic done; demo UI in control token | `src/StillHour/Aging.ttslua` (`applyDriftToStats`), `Interlude.ttslua` |
| P8 | Package as `the_still_hour.json` download-box asset | ✅ built; upload + API-verify remain | `pipeline/package_download.py` → `dist/downloads/` + `src/tts/download_box.lua` |

Legend: ✅ done · 🟡 partial · ⏳ not started

## What runs today (offline, no TTS)

```bash
python3 pipeline/build_cards.py            # 30-card player deck + The Appointed encounter set
python3 pipeline/bundle_mod.py             # loadable TTS save (dist/the_still_hour_mod.json)
lua5.4  pipeline/lua_smoketest.lua         # 99 assertions across P2/P3/P4/P5/P6/P7
lua5.4  pipeline/verify_bundle.lua         # drive the mod bundle in a stubbed TTS env
```

The smoke test exercises the brief's acceptance criteria directly: state
survives node travel and a reset, Dissonance drops to the scar, bands add/remove
the right `[static]` count, revealing `[static]` bumps Dissonance, once-per-loop
flags clear on reset, Muscle Memory reads the previous loop, a big Skip resolves
intervening Hours, "The Hour Was Wrong" removes Hour IV, Aging brackets drift, and
(P5) the Appointed's Approach ratchets up on the clock/bands, Hold Back drops one
stage + rewinds an Hour, and no effect defeats it.

## Flagged design-doc conflicts (owner to resolve)

The brief says: *where the brief and a design doc disagree, the design doc wins —
flag the conflict, don't silently resolve.* These are conflicts **within/between
the design docs themselves**. Resolution applied is noted; change if wrong.

1. **Contest target — `3 × investigators` vs "12 at three players". ✅ RESOLVED
   (CO-001).** The "12 at three players" prose was intended; `3 × 3 = 9` was an
   arithmetic slip. Now `contestTarget = 4 * n` (8 / 12 / 16 at 2 / 3 / 4p). Guide
   §9/§10 wording corrected; smoke test asserts 8/12/16.

2. **Memory soft cap — 10 → 15 → 18. ✅ RESOLVED.** design v0.1 (10) → cards v0.2
   (15) → aging v0.3 / guide v0.5 (18 = 6 × investigators). Implemented the latest
   (`memoryCap = 6 * n`); confirmed correct by CO-001. Stale "15" wording in
   cards v0.2 §A corrected to 18 while editing that line.

2a. **Memory = experience (economy). ✅ RESOLVED (CO-001).** Memory is a general
   experience currency, not Recollections-only: it buys normal card level-ups at
   **1 Memory per card level** (like XP) **and** Recollections at their
   `memoryCost`. Benchmark: total campaign spend ~120–140 shared (~**42–47 per
   investigator**) matches official Arkham XP (~40–50/investigator); the 18/loop
   carryover cap remains the governor. `CampaignState` spend path generalized
   (`purchaseUpgrade(level)` / `purchaseRecollection(memoryCost)`); design §1.1,
   cards §A, and guide interlude step 3 reworded.

3. **Dissonance thresholds — 8/12 → 12/18.** cards v0.2 §A uses absolute 8/12
   (its own note says those were the 1–2p numbers); encounter v0.4 / aging v0.3 /
   guide v0.5 use `4× / 6× investigators` (12/18 at 3p). Implemented the
   player-count-correct formula.

4. **Seraphine elder sign — "set Dissonance to 3" vs "reduce by the amount it
   added (max +5)".** design v0.1 vs cards v0.2. Implemented cards v0.2 wording
   (the errata-grade pass supersedes). This is card text (on art), not code, but
   noted for the framing stage.

5. **"I've Done This Before" traits.** The provided starter JSON tags it
   `Innate. Recollection.`; it is a signature skill (Elias-only), so the
   Recollection trait is harmless here but atypical. Kept as provided for
   consistency with the starter; flag if the trait should be dropped.

6. **Act I vs the Appointed's clock drivers (open — owner's call).** Guide v0.5
   originally said "Act I: the Appointed sleeps," but CO-002's Approach drivers
   (Hour V → Sensed, VII → Emerging, VIII → Arrived) run every loop with no Act
   gating, and the code implements CO-002. The guide's Act I line has been
   reworded to match CO-002 (Whispers stay Act-gated; the Approach does not). If
   Act I should cap the Approach (e.g. at Sensed), that's a small gate in
   `Hourglass.ttslua`/`Dissonance.ttslua` — say the word.

**Version precedence used for numeric constants:** design v0.1 → cards v0.2 →
aging/3p v0.3 → encounter v0.4 → guide v0.5 (latest wins).

## Path to the table (what stands between now and a playable campaign)

Everything below the line is done and tested offline; the ordered gaps to an
actual play session:

1. **In-TTS load test** (~an evening, needs your PC): load
   `dist/the_still_hour_mod.json`, click **Run Tests** (expect 39/39), poke the
   demo buttons. First real-engine validation.
2. **Board wiring** (the biggest remaining build item): connect the logic
   modules to physical objects — the Appointed's manifest/move/Hold-Back button
   on its card, location cards flipping per `Locations.activeFace` and gating
   clues on `isOpen`, Memory/Dissonance/Hourglass counters players can touch,
   and the interlude buy panel. All logic exists; this is TTS plumbing.
3. **Playable content minimum**: the Prologue + district locations exist as
   *rules text* in the guide but not yet as location/objective **cards** in the
   spec (only the 33 player/boss cards are generated). Generating the ~25
   location cards + 6 district node sets + the 26-card shared encounter spine
   from `encounter v0.4` through the existing pipeline is data entry, not new
   code.
4. **Chaos-bag integration**: wire `Dissonance.syncBag` to SCED's real bag
   manager (adapter stub documented in INTEGRATION §3) and add a physical
   `[static]` token.
5. **Art** (cosmetic — placeholders load today): see **`docs/ART_HANDOFF.md`** —
   complete 41-face scene-mode manifest is ready; CardForge build + GPU batch +
   Strange Eons framing are the remaining (machine-side) work.
6. **P8 last mile**: upload `dist/downloads/the_still_hour.json` to a release
   URL and verify `placeholderDownload` in the fork.

A *rules-complete tabletop playtest* needs 1–3. Items 4–6 make it shippable.

## CardForge (art batch tool)

✅ Built per `CARDFORGE_BRIEF` + `HANDOFF_cardforge`: `cardforge/` package with
A1111 + ComfyUI adapters (tagged-node workflow injection), prompt composition,
character resolver (JSON now; interface ready for the character-select tool),
crash-safe resume ledger, variants, report, contact sheets, `index.json`, a
`seeds` step-0 command, and a `--dry-run` mode that emits exact HTTP payloads.
Campaigns are plug-in folders (`campaigns/<name>/`) — the `demo` campaign proves
zero-code reuse. Acceptance: `python3 cardforge/selftest.py` (20 checks, green).
**Needs the owner's rig:** live P0 smoke on both backends, checkpoint config,
Step-0 seed curation + LoRA training. Golden prompt fixtures (`prompts.json`)
auto-compare when dropped at the repo root.

## Next steps (in brief order)

- **P5 Appointed** — ✅ done (CO-002). Staged Approach (Unseen→Sensed→Emerging→
  Arrived) in `Appointed.ttslua`, ratcheted by the clock (Hours V/VII/VIII) and
  Dissonance bands (Glitch/Noticed); Hold Back (`[wil]`/`[com]` 4) pushes it back
  one stage + rewinds an Hour; undefeatable via the defeat-replacement. Board
  effects delegate to `ctx`. Remaining board wiring: hook the enemy card's Hold
  Back button and the manifest/place-at-farthest callbacks to the real SCED board.
- **P6 location toggles** — ✅ done. `Locations.ttslua` decides each location's
  active face (front/back off a Knowledge flip-fact) and sealed/open state;
  `Knowledge.ttslua` is the fact registry + Act II / finale-assembly gates.
  Remaining board wiring: flip the physical location card to the chosen face and
  gate its clues on `isOpen`.
- **P7 interlude** — ✅ logic done. `Aging.applyDriftToStats` returns the drifted
  stat line (skills floor at 1); `Interlude.ttslua` orchestrates age → bank →
  spend (Recollections at `memoryCost`, level-ups at `=level`) → `beginNextLoop`
  (soft cap). The control token has an **Interlude Demo** button + `shBuy(id)`
  console helper. Remaining: a full point-and-click buy panel and applying the
  drift to the physical investigator sheet.
- **P8 download box** — ✅ built. `package_download.py` emits the release asset
  `dist/downloads/the_still_hour.json` (campaign box: player + encounter bags +
  Control token) and the placeholder `the_still_hour_box.json` (GMNotes
  `{"filename":"the_still_hour"}` + `download_box.lua`). Remaining: upload the
  release asset to a releases URL the mod's `SOURCE_REPO` resolves, and verify
  `GlobalApi.placeholderDownload`'s signature in your fork (the box has a fallback
  if it's absent).
- **Remaining**: the in-TTS load test, and per-system board wiring (Appointed
  board callbacks, location card flips, interlude panel). Host wiring: attach
  `CampaignState` to a state token and register its `onSave`/`onLoad` with SCED's
  campaign save — see `docs/INTEGRATION.md`.
