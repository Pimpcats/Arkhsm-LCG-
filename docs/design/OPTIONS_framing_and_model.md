# THE STILL HOUR — Framing Options & Model Config (for Claude Code)
### Companion to `HANDOFF_cardforge.md`. Two decision areas: (A) how card faces get framed, (B) which model/checkpoint CardForge drives. Owner's picks are marked ★.

---

## A. FRAMING — where the blank card templates come from

Four options, best-first. The framing stage (ART_PIPELINE Stage 2) consumes CardForge's `index.json` and produces finished faces.

### ★ A1. Strange Eons 3 + the Arkham Horror LCG plugin (RECOMMENDED)
The community-standard toolkit. The plugin contains **every card type as a live, fillable template** — investigator front + deckbuilding back, minicard, asset/event/skill, treachery, enemy, location, act/agenda — with stat boxes, icon slots, and text regions as data fields. Widely considered the simplest and most-used way to make custom Arkham cards, and it's **scriptable** (JS console; batch create + PNG export), which is what makes Stage-2 automation possible.

**Setup gotchas (important):**
1. Install Strange Eons 3 from strangeeons.cgjennings.ca.
2. **Do NOT use the plugin from the in-app catalog — it's outdated.** The maintained version (by jaqenZann) is distributed externally; current link is in the Barnaby Files guide "Strange Eons: How to Make an Investigator" (barnabyfiles.wordpress.com, May 2025) — a full walkthrough of the exact workflow.
3. Install the **AH font family** or cards render in a Times-like font; the pack is available via the Mythos Busters Discord (not directly linkable).
4. Inspect the plugin's component names (open one card of each type) and map our `art_type`/card `type` fields to them before scripting.

**Build:** a SE script reads `stillhour_cards_spec.json` + encounter spec + CardForge's `index.json`, fills each component (title/traits/cost/icons/stats + illustration), exports `faces/{id}.png`. Rules text comes from `cards_v0.2` / `encounter_v0.4` — never from GMNotes.

### A2. Raw hi-res blank PNG/PSD templates (fallback / reference)
Literal empty frames to composite onto with Pillow/Photoshop. Sources: the BoardGameGeek thread "Hi-res blank templates for custom investigator cards" (boardgamegeek.com/thread/2426599); older FFG-forum packs (e.g. a location template with toggleable connection/shroud/clue symbols) predate the plugin and are mostly superseded.
**Use only if** SE scripting proves intractable: all stat/icon/text placement becomes our code (a layout engine per card type) — significant work the plugin already does. Reasonable for one-off mockups.

### A3. Full programmatic rendering (Pillow/HTML→PNG, no SE)
Own the entire frame in code. Maximum automation, zero desktop dependency — but we'd be rebuilding Arkham's card layouts (fonts, icon sets, textures) from scratch, and it will look "close but off" without serious effort. **Not recommended** for v1.

### A4. Hybrid (pragmatic first-milestone path)
Frame the **6-face starter batch by hand** in the SE GUI (fast, proves look), while the SE batch script is developed for the full 41+. Recommended sequencing if scripting SE stalls.

**Decision for Claude Code:** target **A1**; use A4 sequencing if needed; A2 only as fallback. The SE script is a separate deliverable from CardForge (CardForge ends at `index.json` — per its handoff).

---

## B. MODEL — what checkpoint CardForge's profiles point at

Owner runs ComfyUI and/or A1111 locally (RTX 4080, 16 GB VRAM — SDXL-class models run comfortably). Fill `art_profiles.json`'s `checkpoint` placeholders with the pick below.

### ★ B1. Primary: **Painter's Checkpoint v1.1** (SDXL, Civitai model 240154)
A deliberately narrow model: "not a comprehensive art style — a very specific painterly look. Alla prima, gestural, atmospheric; detailed enough to be called realist" — and the v1.1 merge specifically improved contrast and **night/dark scenes**. That is almost a description of Arkham card art, and this campaign is entirely night scenes. Two more fits: no special prompting needed (our composed prompts work as-is; keep "painting/painterly" early in the prompt), and the author notes it's also excellent as an **upscaler-stage model to preserve the painterly feel** — so use it in the hires pass even for images generated elsewhere.

### B2. Alternates (worth a bake-off on the 5 seed portraits)
- **ZavyChromaXL** (SDXL) — "the sweet spot between photorealism and artistic stylization … high-end concept art or cinematic stills"; more polished/cinematic, slightly less oil-paint.
- **DreamShaper XL** (SDXL) — versatile fantasy/concept-art workhorse, handles complex scene descriptions well; a good safety net for tricky compositions (crowd scenes, the Appointed's abstract geometry).
- SDXL remains the right base family: for LoRA/ControlNet/community-resource dependence — which we have, per-character LoRAs — SDXL's ecosystem is still unmatched.

### B3. Procedure (encode in the runbook)
1. Bake-off: render the 5 canonical seed portraits + `sthr-appointed` on B1 and one alternate; pick per-art-type if results differ (profiles support per-type checkpoints — e.g. Painter's for locations/enemies, ZavyChroma for portraits).
2. Train the 5 character LoRAs **on the chosen portrait checkpoint** (LoRAs are checkpoint-family-bound; train on what you'll generate with).
3. Set chosen checkpoint(s) in `art_profiles.json`; hires/upscale stage uses Painter's Checkpoint regardless (per B1's note).

### B4. Prompt (already built — do not re-engineer)
The composed prompts in `prompts.json` / `PROMPT_SHEET.md` are the production prompts: `{character bible} + {scene} + {type framing} + {house style}` with the shared negative. One tweak for B1: ensure the style block leads with "painting"-adjacent terms — our house style already opens with "cosmic horror **illustration, painterly**…", which satisfies it. If a face drifts too photographic, prepend the word `painting, ` to that face's positive rather than rewriting the block.

---

## C. Summary of owner's picks
- **Framing:** Strange Eons + external (jaqenZann) Arkham plugin + MB-Discord font pack; hybrid sequencing allowed; CardForge stays decoupled (ends at `index.json`).
- **Checkpoint:** Painter's Checkpoint v1.1 primary, ZavyChromaXL / DreamShaper XL as bake-off alternates; per-type overrides allowed; Painter's for the upscale pass.
- **Prompts:** use `prompts.json` as-is (golden fixtures for CardForge composition tests).
