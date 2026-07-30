# ChatGPT extraction spec — official location cards (calibration reference)

Hand ChatGPT one or more **official location card images** (e.g. Scarlet Keys)
plus this spec. It returns a JSON array that drops straight into CardForge's
location data, and gives us the exact colors/proportions to calibrate our
renderer against the official cards (per THE HARD RULE).

Everything below the line is the prompt to paste. Attach the card images with
it.

---

You are extracting reference data from official Arkham Horror LCG **location
cards**. For each card image I give you, output one JSON object. Return a
single JSON array of all of them, and **nothing else** — no prose.

**Do not clean up, average, or round the colors.** I want exact pixel hex
values sampled from the image.

For each location card, extract:

```json
{
  "name": "Rainy London Streets",
  "subtitle": "",
  "traits": "London.",
  "shroud": 1,
  "clues": 2,
  "clues_per_investigator": true,
  "victory": null,
  "revealed": false,

  "icons": "doubleslash",
  "color": "#0A0C2E",

  "connections": [
    { "symbol": "circle",   "color": "#E0A81E" },
    { "symbol": "square",   "color": "#C0202A" },
    { "symbol": "triangle", "color": "#2A5A9A" },
    { "symbol": "slash",    "color": "#3A3730" }
  ],

  "text": "Rainy London Streets gets +X shroud. X is the current act number.\n\n[Forced] – If there are no clues on Rainy London Streets: Add clues to it until it has 1 [per_investigator] clues on it.\n\n[action]: Resign.",
  "flavor": "We should wait for Inspector Flint…",

  "illustrator": "Borja Pindado",
  "collection_number": "10/19"
}
```

### Field rules

- **shroud / clues** — the plain numbers in the two discs (shroud = left disc,
  clues = right disc). If a value is a printed dash "–", use `null`.
- **clues_per_investigator** — `true` if the clue disc shows the little
  per-investigator "agent/hat" marker next to the number, else `false`.
- **victory** — the "Victory X." number if the card has one (usually on a
  revealed back), else `null`.
- **revealed** — `true` if this is the revealed/back side (full rules), `false`
  for the unrevealed front (flavor only).
- **icons** — the location's OWN symbol (shown top-left, in the location's own
  color). Name it from the symbol vocabulary below.
- **color** — the location's own color, sampled as **exact hex** from the
  CENTER of that top-left own-symbol disc (avoid the white symbol itself). This
  is the location's map color.
- **connections[]** — one entry per disc in the BOTTOM row that has a symbol in
  it (skip the empty gold wells). For each: the symbol name (from the vocab) and
  the **exact hex** sampled from the center of that disc (avoid the cream/white
  symbol). Order them left→right.
- **text** — the rules text. Replace game icons with bracket tokens:
  `[per_investigator]`, `[action]`, `[reaction]`, `[free]`, `[willpower]`,
  `[intellect]`, `[combat]`, `[agility]`, `[wild]`, `[skull]`, `[cultist]`,
  `[tablet]`, `[elderthing]`, `[auto_fail]`, `[elder_sign]`, `[bless]`,
  `[curse]`, `[frost]`. Bold keywords like **Forced**, **Revelation** as
  `[Forced]`. Preserve paragraph breaks with `\n\n`.
- **flavor** — the italic flavor line (no quotes).
- **illustrator / collection_number** — from the footer, if legible.

### Symbol vocabulary (use these exact names)

`circle`, `square`, `triangle`, `diamond`, `moon`, `star`, `heart`,
`hourglass`, `cross`, `quote`, `slash`, `doubleslash`, `spade`, `clover`, `t`.

If a symbol truly isn't in this list, use `"symbol": "unknown"` and add a
`"symbol_note"` field describing it (e.g. "two vertical bars", "wavy line").

### One-time layout measurements (do this ONCE, from any one clear card)

Also return a top-level `"_layout"` object (once, not per card) with pixel
measurements taken on the card at its native resolution:

```json
"_layout": {
  "card_px": [750, 1050],
  "shroud_disc_diameter_px": 119,
  "clue_disc_diameter_px": 119,
  "connection_disc_diameter_px": 64,
  "own_marker_diameter_px": 72,
  "shroud_number_height_px": 66,
  "connection_symbol_height_px": 34
}
```

Report the numbers you actually measure — these let me match our disc sizes to
the official card to the pixel.
