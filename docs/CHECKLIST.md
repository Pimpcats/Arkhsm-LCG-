# THE STILL HOUR — Master Checklist
*Updated 2026-07-11. ✅ done · 🔶 partly done / needs your action · ⬜ not started.*

## The campaign itself (all code-complete and tested)

- ✅ P1–P8: card pipeline, campaign state, Dissonance/[static], loop flags,
  the Appointed (staged Approach), Occultation clock, Aging + interlude,
  download-box packaging
- ✅ CO-001 (contest 4×n, Memory-as-XP) and CO-002 (The Appointed) applied
- ✅ Victory elites (3 Named enemies), once-per-campaign Victory log
- ✅ Balance simulated (success curves, XP spread, stress test) — honest flags
  recorded in docs/BALANCE.md
- ✅ Loadable vertical slice: dist/the_still_hour_mod.json (Control token
  passes its 23 in-TTS tests)
- ✅ Generated objects byte-aligned with real SCED (your 22 exported examples,
  vendored in docs/art_reference/sced_objects/)
- ⬜ Content data pass: ~64 more faces (9 Occultation Hour agendas, encounter
  spine, ~25 locations, node sets) — specs exist in the design docs, cards not
  yet in the pipeline
- ⬜ Table presence (schemas all in hand from your examples): investigator
  minicards, campaign guide as PDF object, interactive campaign-log token,
  scenario/campaign boxes with Place/Recall

## CardForge Studio (the app)

- ✅ Five workflow tabs + Advanced; numbered self-checking steps on each
- ✅ Backend rig: launches A1111 itself, auto-launch before every job
- ✅ Checkpoint dropdown with ground truth ("backend has loaded X / forces Y")
- ✅ Per-card prompt + negative boxes; house style editable; generation
  defaults (steps/CFG/sampler); 🎲 reroll (fresh seeds)
- ✅ LoRA table (name / strength / trigger per investigator)
- ✅ Seed-portrait picker; categorized gallery + Cards grid; zoom lightbox;
  spoiler shield; drag-to-place editor (lossless); stub hiding
- ✅ Expanded in-place card editor: click a card → full-width editor (no
  popup); click any text box / stat ON the card to jump to its field; type
  your own rules & flavor text; +/− steppers for fight/evade/cost/health;
  damage ❤️ and horror 🧠 pips added/removed by clicking; Upload image with
  independent width & height fit sliders + Remove image — every card type
- ✅ Setup installs INTO the folder: A1111, Painter's Checkpoint, Strange
  Eons, Arkhamic font — fully portable folder
- ✅ Per-card font picker (title/body) + official font stack
- ✅ Deck backs (your eclipse + lighthouse art) on every export
- ✅ 136-check selftest, Windows-safe (UTF-8 + race fixes)

## Card look ("identical to official")

- ✅ Fonts: Arkhamic/Teutonic titles, Arno/Minion body, icon font — wired
- ✅ True blank frames extracted from the PSD template pack (all 10 layouts)
  with auto-measured text regions — committed in assets/frames/psd/
- ✅ Inpaint fallback ("select & generate over") for the 6 scanned layouts
- ✅ OWNER DECISION: plugin templates for EVERYTHING. Investigators
  (per-class fronts AND backs), enemies, treacheries (+weakness variants),
  assets, events, skills all render on the SE plugin's authentic frames
  with its exact regions — real stat plates, cost circles, commit boxes,
  slot icons, damage/horror pips, stamina/sanity chits. PSD blanks kept
  as fallback only.
- ✅ Renderer v3 for assets/events/skills: the SE plugin's own per-class
  frames + exact region maps (586 regions extracted from the .seext) —
  cost circles, commit-icon boxes, slot icons, class frames, all authentic
- 🔶 Headless Strange Eons in-container: Java 21 + Xvfb ready, real
  classmap/keys filled from the plugin — still needs the SE jar (approve
  the CGJennings/strange-eons repo request, or upload the 'other
  platforms' .tar.gz / a fully-downloaded .deb)
- 🔶 Strange Eons path (pixel-perfect benchmark): app generates the script;
  you still install SE (one click) + jaqenZann plugin + verify the two
  config seams once

## Your to-dos (nobody else can)

- 🔶 Real art run: Launch backend → ↻ pick Painter's → Seeds → pick 5
  canonical portraits → Starter batch → ⚡ Auto-build (dry-run now defaults
  off; delete state/still_hour.ledger.json once if old stubs linger)
- ⬜ Setup tab: Install Arkhamic (one click)
- ⬜ Train the 5 investigator LoRAs on Painter's, enter them in Advanced →
  Character LoRAs (skippable for a first playthrough; faces just vary more)
- ⬜ Hunt Arno Pro Bold/Italic/BoldItalic (Discord) → drop in assets/fonts/
- ⬜ Load the mod in TTS and actually play loop 1 (Run Tests should say 23/23)
- ⬜ Strange Eons one-time setup, when you want print-identical cards
- ⬜ Send: an Act card WITH a clue threshold + a scenario reference card
  (last two schema gaps)

## Blocked / parked

- ⬜ Hosting for sharing with your group (GitHub release asset — the download
  box already points the SCED way; local file:/// covers solo play now)
- ⬜ Plugging Claude directly into the app (your stated later-goal, after the
  working examples exist)
