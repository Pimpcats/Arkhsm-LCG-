# Card anatomy — the target (official reference cards)

Six cards straight from the game (this folder) define what the finished Still
Hour cards must look like. Per layout, the fields the frame stage needs — this
is the checklist `pipeline/stillhour_print_text.json` + the specs must satisfy
and the Strange Eons components must be fed.

## Investigator FRONT (`ref_investigator_front.png`, landscape)
class icon (top-left) · name banner + subtitle · **4 skill values** in colored
plates (wil/int/com/agi order) · portrait left · body box: **traits** (bold
italic) → **ability text** (reaction/action icons inline) → **elder-sign
effect** · *flavor quote* · **health (red) + sanity (blue)** bottom ·
illustrator + © footer.

## Investigator BACK (`ref_investigator_back.jpeg`, landscape)
portrait thumbnail · name banner + subtitle · **Deck Size** · **Deckbuilding
Options** (class glyphs inline, level ranges) · **Deckbuilding Requirements**
(signatures + random basic weakness) · long *bio* flavor block.

## Treachery (`ref_treachery.png`, `ref_weakness_treachery.jpeg`, portrait)
art top (full-bleed) · encounter-set icon in the keyhole · **TREACHERY** banner
· name banner · (weakness variant: **BASIC WEAKNESS** banner) · *trait line* ·
**Revelation —** rules text (test icons inline) · (weakness: **Forced —**
clause) · *flavor italic* · illustrator + © + set number footer.

## Enemy (`ref_enemy_victory.png`, `ref_enemy_elite.png`, portrait)
name banner top · **fight / health / evade** in three plates (health center,
star-backed) · *traits bold italic* (Elite included here) · keyword line
(**Spawn**/**Prey**/Hunter. Retaliate.) · *flavor italic* · **Victory X.** ·
**ENEMY** banner + encounter-set icons · **damage/horror** pips · art bottom ·
illustrator + © + set number footer.

## What this implies for our data (the print layer)
GMNotes stays mechanics-only (SCED rule); everything printed above comes from
`pipeline/stillhour_print_text.json` at frame time:
`{id: {text, flavor, back_text?, fight?, health?, evade?, damage?, horror?}}`
— rules text in the repo's `[wil]`-style markup (converted to plugin tags or
glyph letters at frame time), enemy combat stats as data (they exist nowhere
else), investigator backs' deckbuilding text, and flavor.
