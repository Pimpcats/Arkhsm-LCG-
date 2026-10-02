# Hand-off — CardForge Studio / THE STILL HOUR

*Updated 2026-10-02. Spoiler-free.*

The current campaign handoff is [STILL_HOUR_HANDOFF.txt](STILL_HOUR_HANDOFF.txt).
It records the finishing fixes, current verification, difficulty results and
remaining human playtest work. The historical design reports are not current
balance approval.

Working branch: **`main`** (owner decision, 2026-09-22). Build from `main`;
inspect the current branch heads and recent commits before resuming. Current
counts, validation results and next actions live in
`campaigns/still_hour/assistant/production.json`; read `AGENTS.md` and
`docs/ASSISTANT_WORKFLOW.md` first.

## What this is

A fan-made Arkham LCG campaign (THE STILL HOUR) plus **CardForge Studio**, the
local app that builds it. Free, online-only, for the owner's group. No printing,
no sale. The owner plays it as a first-time player: no story spoilers in chat,
summaries, review labels or owner-facing docs.

Two rules that override convenience:

1. **Everything is checked against the official game.** The only permitted
   deviation is genuinely new custom content, which still uses the official
   template. When the plugin already ships an asset, use it — do not draw a
   lookalike.
2. **The app is a template organiser first.** It must be possible to build a
   whole campaign by hand at any moment, with no AI and no JSON editing. The
   image generation is secondary.

Run it: `python3 cardforge/studio.py` → http://127.0.0.1:8570

## Where things are

| | |
|---|---|
| App (single-file server + page) | `cardforge/studio.py` |
| Renderer (draws every card face) | `pipeline/render_placeholders.py` |
| Release build (hosted images + all of `dist/`) | `pipeline/publish_hosted.py` |
| TTS compiler | `pipeline/compile_campaign.py` |
| SCED object builder | `pipeline/build_cards.py` |
| Scenario readiness audit | `pipeline/scenario_content.py` |
| Setup / vendor installs | `cardforge/installer.py` |
| Selftests (sandboxed) | `cardforge/selftest.py` (fast), `cardforge/studio_selftest.py` (20–45 min) |
| Player quick reference (play aid) | `docs/QUICK_REFERENCE.md` |
| By-hand rebuild proof | `tools/rebuild_by_hand.py` |
| In-game test relay | `tools/tts_relay/` (`docs/TTS_RELAY.md`) |
| Ground-truth SCED objects | `docs/art_reference/sced_objects/` |

Campaign folders: `campaigns/still_hour` (the campaign), `hollow`, `demo`.
`art/` is gitignored — a fresh clone composes its faces on first run
(`ensure_faces`), and `publish_hosted.py` renders them before publishing.

## Pending (in order)

1. **Real TTS relay run on the current head** — owner, local PowerShell
   (`docs/TTS_RELAY.md`). The last real run passed on an older build.
2. **First playtest** — Prologue and Loop 1, then the complete campaign.
   Relay passes and model trials are not playtest approval. Record difficulty
   and campaign earnings against the current handoff.
3. **Calibration follow-up** — use the handoff's measured residuals and human
   results before approving the requested success curve. All campaign card
   illustrations are present; optional box-art variation can follow later.

## Release rules

- **Never squash- or rebase-merge a publish commit.** `publish_hosted.py`
  commits the card images ("Publish hosted card images") and pins every image
  URL to that commit hash. Merge with a normal merge or fast-forward; a
  rewritten commit makes every face in TTS go blank.
- The release `dist/` files carry hosted URLs only. `build_cards.py`,
  `bundle_mod.py`, `table_presence.py` and `package_download.py` refuse to
  write placeholder or `file:///` image URLs into `dist/` unless `--local` is
  passed (the Studio's local modes pass it; never commit such a build).
- Machine-specific backend settings live in `rig.local.json` (gitignored);
  `rig.json` is shared defaults only.

## Tabs

`1 Setup · 2 Illustrate · 3 Cards · 4 Campaign / scenarios · 5 Play in TTS · ⚙ Advanced`

The Frame tab (Strange Eons hand-off) was removed — every card is rendered on
the plugin's extracted frames. **The `se_*` endpoints still exist** and the
selftest still exercises them; only the UI is gone.

## Facts established by measurement (don't re-derive, don't guess)

- **The playmat grid is 5 × 5.** Step and origin measured off
  `scenario_box_memory_bag.json`: columns 6.60 from x −30.24, rows 7.65 from
  z 11.46. The outer column/row coordinates are *extrapolated* — exporting the
  playmat object would pin them via its snap points.
- **SCED draws connection lines itself** from the cards' GMNotes
  (`locationFront: {icons, connections}`), not from geometry. The memory bag's
  `onLoad` reads exactly two keys (`ml`, `setupButton`) and discards the rest.
- **40 of 50 templates are windowed** — art renders *behind* the frame. The 10
  opaque ones: `Investigator-G/K/V`, `Scenario`, `Story`, `Chaos`, `ActBack`,
  `AgendaBack`, `EncounterBack`, `PlayerBack`.
- **The plugin ships no number cutouts.** Numerals are drawn into the printed
  disc wells with the font, as the plugin does.

## Gotchas

- **Selftests run in a sandbox.** `cardforge/sandbox.py` copies the repository
  (without `.git`, `out/`, `state/`, `art/`, `se/`, `vendor/` and
  `pipeline/art_urls.json`) to a temporary folder, re-runs the test there and
  deletes the copy. The checkout is never touched, so `git status` is the same
  before and after. `CARDFORGE_SANDBOX_KEEP=1` keeps the copy for debugging.
- **The Studio selftest takes roughly 20–45 minutes** and re-renders every
  card several times. Run it in the background; don't poll it every turn. It
  picks a free port, so parallel runs in other checkouts don't collide.
- While a Studio job runs it redirects `sys.stdout` into the Studio log; the
  selftest writes results straight to the real stdout for that reason.
- Card overrides are **per campaign** (`campaigns/<id>/card_overrides.json`).
- Playwright's `drag_to` does not synthesise HTML5 drag-and-drop for these
  elements. Dispatch `dragstart` / `dragover` / `drop` / `dragend` manually.
- GitHub API is blocked from the sandbox for repos outside the session — match
  release assets by pattern, never by a pinned filename.
- GitHub access is not access to the owner's desktop app or Tabletop
  Simulator; the relay is the only in-game channel.
