# Hand-off — CardForge Studio / THE STILL HOUR

Branch `claude/new-session-r230bz`, tip `cc13421`, working tree clean, pushed.

## What this is

A fan-made Arkham LCG campaign (THE STILL HOUR) plus **CardForge Studio**, the
local app that builds it. Free, online-only, for the owner's group. No printing,
no sale.

Two rules that override convenience:

1. **Everything is checked against the official game.** The only permitted
   deviation is genuinely new custom content, which still uses the official
   template. When the plugin already ships an asset, use it — do not draw a
   lookalike. (This was violated twice and caught both times: an invented chaos
   symbol, and a hand-drawn location disc stamped over the template's own.)
2. **The app is a template organiser first.** It must be possible to build a
   whole campaign by hand at any moment, with no AI and no JSON editing. The
   image generation is secondary.

Run it: `python3 cardforge/studio.py` → http://127.0.0.1:8570

## Where things are

| | |
|---|---|
| App (single-file server + page) | `cardforge/studio.py` |
| Renderer (draws every card face) | `pipeline/render_placeholders.py` |
| TTS compiler | `pipeline/compile_campaign.py` |
| SCED object builder | `pipeline/build_cards.py` |
| Setup / vendor installs | `cardforge/installer.py` |
| Selftest (~45 min, 243 checks) | `cardforge/studio_selftest.py` |
| By-hand rebuild proof | `tools/rebuild_by_hand.py` |
| Ground-truth SCED objects | `docs/art_reference/sced_objects/` |
| Campaign feed + map docs | `docs/design/CAMPAIGN_FEED.md` |

Current state: 99 Still Hour cards, 8 scenario boxes, 104 composed faces,
3 campaigns (`still_hour`, `hollow`, `demo`).

`art/` is gitignored — a fresh clone composes its faces on first run
(`ensure_faces`).

## Tabs

`1 Setup · 2 Illustrate · 3 Cards · 4 Campaign / scenarios · 5 Play in TTS · ⚙ Advanced`

The Frame tab (Strange Eons hand-off) was removed — we render every card
ourselves on the plugin's extracted frames. **The `se_*` endpoints still exist**
and the selftest still exercises them; only the UI is gone.

## Facts established by measurement (don't re-derive, don't guess)

- **The playmat grid is 5 × 5.** Step and origin measured off
  `scenario_box_memory_bag.json`: columns 6.60 from x −30.24, rows 7.65 from
  z 11.46. The 5×5 extent came from the owner reading the TTS playmat. The
  outer column/row coordinates are *extrapolated* — exporting the playmat
  object would pin them via its snap points.
- **SCED draws connection lines itself.** From the cards' GMNotes
  (`locationFront: {icons, connections}`), not from geometry. That is why a
  line stretches when you drag a card and vanishes when it leaves the mat.
  Nothing about lines needs compiling into the box; the memory bag's `onLoad`
  reads exactly two keys (`ml`, `setupButton`) and discards everything else.
- **40 of 50 templates are windowed** — art already renders *behind* the frame.
  The 10 opaque ones: `Investigator-G/K/V`, `Scenario`, `Story`, `Chaos`,
  `ActBack`, `AgendaBack`, `EncounterBack`, `PlayerBack`.
- **The plugin ships no number cutouts.** The location template prints both
  disc wells; the numeral is drawn into them with the font, as the plugin does.
  The only real asset in that composite is `AHLCG-PerInvestigator`.

## Proven end to end

`tools/rebuild_by_hand.py` rebuilds a whole campaign through nothing but the
editor's own endpoints and diffs it against the original. Last run:

```
cards typed in: 99/99      scenario boxes: 8/8
locations placed: 22       connections clicked in: 40/40
fields compared: 756       mismatched: 0
compiled to TTS: True
VERDICT: the whole campaign is reproducible by hand
```

## Do this first

**Run the selftest.** It has not been run since the disc change and the Frame
removal. One assertion is known-stale:

- `studio_selftest.py:118` still requires `"4 &middot; Frame"` in the page.
  Update to `4 &middot; Campaign / scenarios` and `5 &middot; Play in TTS`.

Everything else is expected to pass — the disc test asserts on the plugin
assets and file size, not on our drawn circle.

## Open work, in the order the owner asked for it

1. **Card editor rework** — one coherent piece, not five tweaks:
   - card preview at half its current size (`editArt`: `Math.min(1, 820/cw)`)
   - edit text *in place on the image* instead of jumping to the form below
     (today `#ed_stage`'s click handler does `scrollIntoView` to a field)
   - a Photoshop-style side panel for text and font
   - drag the text box itself to reposition it
   - **art behind the frame furniture in the live preview** — the *render* is
     already correct; the editor layers `#ed_art` over `#ed_face`. The fix is a
     furniture overlay (frame + text + discs composed with the art window
     transparent), not a renderer rewrite.
   - There is also an unreproduced report: typed text "shows up on the top left
     and you can't see it". Ask which field on which card type before chasing.

2. **Default to a new campaign on startup** rather than `still_hour`.

3. **Seed a new campaign with recommended card counts per scenario**, derived
   from the existing campaigns (Still Hour's 8 boxes are the obvious source:
   locations 3–4, agenda 9, encounter 13, act 2, reference 1).

4. **Cthulhu banner art.** Request is written and ready to hand to Krea — style
   block, negative block, five scenes, selection rule. Target
   `assets/branding/banner.png`, 2048×512. The header is ~50px tall behind
   `rgba(14,14,19,.8)` + 18px blur, so it needs either a taller header or a
   lower overlay before art will read. `assets/branding/cardforge.ico` is a
   0-byte placeholder.

## Gotchas

- **The selftest takes ~45 minutes** and re-renders all 99 cards several times.
  Run it in the background; don't poll it every turn.
- It sidelines/snapshots owner state and restores at exit — but a run killed
  part-way can leave things behind. It once left the campaign pointing at a
  stub checkpoint, and a truncated render left a **zero-byte face PNG** that
  every `exists()` check counted as composed. Face checks are size-aware now
  (`studio.has_face`).
- Card overrides are **per campaign** (`campaigns/<id>/card_overrides.json`).
  They used to all land in `still_hour`, which made them invisible to the
  compiler for every other campaign. A startup migration moves stranded ones.
- Playwright's `drag_to` does not synthesise HTML5 drag-and-drop for these
  elements. Dispatch `dragstart` / `dragover` / `drop` / `dragend` manually.
- GitHub API is blocked from the sandbox for repos outside the session — match
  release assets by pattern, never by a pinned filename.
- Commits on this branch are unsigned (no signing key in the environment). The
  committer email is correct; amending won't add a signature.
