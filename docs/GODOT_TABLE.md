# Godot table: seeing the emulated TTS table (assistant-facing)

The headless harness (tests/sced_real) plays the campaign on SCED's real table
inside a TTS emulator, but only reports checks. tools/godot_table renders that
table state as Tabletop-Simulator-like screenshots, so the assistant can look
at layouts, cards, tokens and buttons without the owner. Godot is only the
renderer: every rule, script and position comes from the Lua emulator. (This
replaces the Unity plan in docs/UNITY_TABLE_PLAN.md.)

Screenshots show campaign content: they are for the assistant only and stay
in gitignored folders. Never put them, card names or mechanics in owner-facing
text.

## Run

    python3 tools/godot_table/render.py --save "/home/user/sce480/Arkham SCE 4.8.0.json"
    python3 tools/godot_table/render.py --save ... --steps 0,6,10-12 --cameras overview,play,mythos
    python3 tools/godot_table/render.py --save ... --closeup box=-28,0,20 --debug
    python3 tools/godot_table/review.py --save ...     # spoiler-free SCED-only review set

render.py runs the playthrough with snapshots, fetches the assets, renders,
draws the XML UI and writes `.cache/godot_shots/<run>/`: `NNN_<camera>.png`,
a `.json` per shot (the camera and every button's screen rectangle, whether it
is visible, its label) and `index.html`. `--snapshots <dir>` renders existing
snapshots; `--suite demo` renders the SCED-only demo; `--debug` draws snap
points (magenta), scripting zones and every button's rectangle on top.
review.py writes `.cache/godot_review/` (see its docstring): nothing from the
campaign, safe for the lead to publish for the owner.

Cameras: `overview`, `play`, `mythos` are the save's own CameraStates (TTS keys
1-3), `player`/`seat` sit at White's side, `top`/`playtop`/`whitemat`/
`mythostop`/`importer` look straight down. TTS's default field of view (60
degrees vertical) and 1920x1080.

Needs: Godot 4.3 (`/home/user/tools/godot/Godot_v4.3-stable_linux.x86_64` or
`$GODOT`), xvfb-run, Pillow, UnityPy and imageio-ffmpeg (`pip install UnityPy
imageio-ffmpeg`), PyMuPDF for PDF pages, network access to the Steam CDN and
raw.githubusercontent.com. Godot runs headless under Xvfb with the OpenGL
compatibility renderer (Mesa llvmpipe).

## Pieces

- `tests/sced_real/snapshot.lua` + `run.lua --snapshots <dir>` (`run.py
  --snapshots`): a JSON snapshot after boot and after every step (a suite can
  call `H.snapshot(label)` any time). Per object: GUID, TTS type, nickname,
  transform, lock, tint, card/deck (CustomDeck entry, CardID, top and bottom
  card, count), CustomImage (tile/token), CustomMesh, asset bundle, PDF, 3D
  text, snap points, decals, buttons and inputs as created, its XML UI as a
  table and the UI assets it names, the hand it was dealt to. Global: its XML UI, snap points, decals.
  Scripts, script states and GM notes are left out.
- `tools/godot_table/fetch_assets.py`: every URL the snapshots use, 8
  downloads at a time with retries, into `.cache/godot_assets/` (raw, PNG
  images capped at 4096 px, card faces/backs cropped from the deck sheets by
  CardID, OBJ meshes, asset bundles extracted with UnityPy into OBJ + PNG +
  transforms, PDF first pages, the save's UI fonts from its font bundles) and
  `manifest.json` (url -> files, failures).
- `tools/godot_table/` Godot project (`scripts/main.gd`, `tts.gd`,
  `obj_loader.gd`): builds the table per snapshot and renders each camera.
- `ui_overlay.py` / `object_ui.py`: TTS XML UI layout (Defaults, alignment,
  scale, 180-degree turns, layout groups, scroll views, SCED's own fonts and
  UI sprite bundles);
  Global's UI over the screen shots, objects' UI as quads on the objects.
- `tests/sced_real/demo.lua` (suite `demo`): the SCED-only "acts like TTS"
  demo (investigator from SCED's card bag, a deck on the playmat, SCED's draw
  and upkeep, flip/exhaust, SCED's counters, infinite token bag, chaos token
  draw/return, bag take/put).

## TTS conventions it relies on (calibrated)

- Space: TTS is Unity (left-handed, y up). Godot = (-x, y, z); a TTS rotation
  (degrees, applied z, x, y) becomes Ry(-y) Rx(x) Rz(-z). OBJ files (and
  UnityPy exports) are already mirrored, so vertices are used as-is.
- Flat images: top towards local -z, right towards local -x (TTS). A card's
  back is its u-mirrored bottom face. A sideways card keeps the card shape; its
  landscape image is turned onto it.
- Custom_Tile at scale 1: the image's short side is 2 units, the long side by
  aspect (SCED's playmat and mythos snap points land on the printed slots;
  the emulator's playmat size was corrected to 4.2 x 2 from this).
  Custom_Token: the long side is 3.7 (play-area grid). Cards 2.2 x 3.1.
- Buttons: size = units x 0.002 x object scale x button scale; a button's
  frame is mirrored in x against the object (position x and the y/z
  rotations change sign). Verified on SCED's playmat encounter/chaos
  hot-spots and the Deck Importer's option buttons. A button at y = 0 inside a
  tile is hidden by the tile, as in TTS.
- Object XML UI: 100 UI units = 1 local unit, UI x/y along local x/z,
  position z = height (negative is up).
- A deck's list runs from its local -y face (top when face down) to +y.
- Cards dealt to a hand stand in that color's hand zone, facing the seat.

## What it cannot show

- No physics: objects rest where the emulator put them (its "landing" is a
  bounds approximation), no stacking jitter, no tumbling dice.
- TTS's own interface (menu bar, chat, hover tooltips, context menus, the
  hand's private view for other colors) is not drawn; only the save's XML UI.
- XML UI is a subset (see ui_overlay.py): no animations, rich text,
  tooltips, masks other than scroll views; rotations only in 180-degree steps.
- Asset bundles are shown by their meshes and main textures (no shaders,
  particle effects or animations); a bundle with no mesh (sound/effects only)
  is a labelled placeholder. Token extrusion is approximated by stacked
  alpha-cut layers. Lighting is tuned by eye, not TTS's exact shaders.
- The emulator's own gaps apply (e.g. deal() puts cards in a hand without a
  real hand transform).

## Timing and outputs

A full playthrough render (23 snapshots x 5 cameras, 115 shots) takes about
4-5 minutes on the container (llvmpipe: harness ~15 s, assets ~20 s the first
time, Godot ~3 min, UI drawing ~40 s); the review set about 2-3 minutes.
`--steps` and `--cameras` cut it down. Assets are cached, so later runs skip
downloads.
