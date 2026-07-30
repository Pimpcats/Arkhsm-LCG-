# CardForge Studio — UI redesign handoff

How to let a designer (e.g. Claude design / an Artifact mockup) rebuild the
Studio UI with a better visual system **without breaking any of the wiring**.

The whole app is one file: `cardforge/studio.py`. The UI is a big embedded
`PAGE` string — HTML + CSS + vanilla JS. The JS talks to the DOM by **element
id, a few class names, and `data-*` attributes**. As long as those survive, the
JS keeps working no matter how the markup around them changes.

So the redesign has exactly one rule.

## The one rule

**Preserve the contract below. Restyle/relayout everything else freely.**

- Every id in the contract must still exist, on an element of a compatible kind
  (an `<input>` stays an input, a container stays a container that can hold
  injected children, an `<img>` stays an img).
- The listed class names and `data-*` attributes must stay on the elements the
  JS builds or reads.
- You may change: layout, grouping, wrappers, order, spacing, color, type,
  component look, tabs vs. panels, icons, animation — the entire visual system.
- You may add new elements/classes freely; just don't rename or drop contract
  ones.

If a hook genuinely needs to move or merge, flag it — that's a JS change on our
side, not something to silently rename.

## Workflow

1. **Snapshot.** Run the app (`python3 cardforge/studio.py`, open
   `http://127.0.0.1:8570`) and screenshot each area, or hand the designer the
   current `PAGE` markup as a static `.html`.
2. **Give the designer this doc** — the contract is the "don't touch these
   hooks" list, plus the screenshots as the "here are the functional areas."
3. **Designer returns a static HTML/CSS mockup** (no JS needed) that keeps every
   contract id/class/data-attr and reorganizes the rest for better flow. An
   Artifact is ideal — it renders live and is self-contained.
4. **Port back.** We replace the markup/CSS inside `PAGE` with the new version,
   leaving the `<script>` untouched. Because the hooks are preserved, the wiring
   just works.
5. **Guardrail.** `studio_selftest.py` asserts every contract id is present in
   `PAGE` (see "Guardrail" below). Run it after the port; a dropped hook fails
   the test instead of silently breaking a button.

## The contract (auto-extracted from the JS)

Regenerate anytime with the snippet at the bottom, so this never drifts.

### Element ids the JS reads/writes (must all exist)

**Card editor** — the live edit surface
`editor`, `ed_stage`, `ed_face`, `ed_win`, `ed_art`, `ed_furniture`,
`ed_regions`, `ed_strip`, `ed_file`, `ed_symbols`, `ed_title`, `ed_pos`,
`ed_neg`, `ed_scale`, `ed_scaley`, `ed_prompt_info`, `ed_promptbox`,
`ed_side_text`, `ed_side_textwrap`, `ed_font_title`, `ed_font_body`,
`ed_font_stat`, `ed_fontfile`

**Card content form** — name/stats/type panels
`cc_name`, `cc_subtitle`, `cc_traits`, `cc_text`, `cc_flavor`, `cc_stats`,
`cc_info`, `cc_props`, `cc_props_row`, `cc_loc`, `cc_tokens`, `cc_log`,
`cc_sigs`, `cc_back`, `cc_back_wrap`, `cc_backflavor`
plus dynamic ids built at runtime: `cc_<field>`, `ccp_<field>` (pip readout),
`cp_<prop>` (card property), `cl_<logfield>`

**Location elements** `le_icon`, `le_color`, `le_perinv`, `le_conns`
**Scenario tokens** `tok_rows` · **Signatures** `sig_rows`, `seedrows`
**Typography controls** `ty_all`, `ty_field`, `ty_font`, `ty_size`, `ty_bold`,
`ty_italic`, `ty_pct`, `df_title`, `df_body`, `df_stat`, `df_fontfile`,
`df_info`, `vendor_font`

**New-card / new-scenario** `nc_name`, `nc_type`, `nc_class`, `ns_name`
**Campaign bar** `campaign`, `hdr_sub`, `camp_out`, `camp_progress`,
`camp_spawn`
**Cards grid + gallery** `cardgroups`, `chips_cards`, `gallery`, `zoom`,
`zoom_img`, `zoom_cap`, `zoom_act`
**Scenario map** `mapwrap`, `mapstage`, `mapgrid`, `maplines`, `maplegend`,
`maptitle`, `mapinfo`, `mappreview`, `map_pv`, `map_gap`, `map_mode_move`,
`map_mode_link`, `board_wrap`, `board_hint`, `scen_board`, `scen_pool`,
`scen_pool_cards`
**AI art / model** `model`, `model_active`, `modelinfo`, `gen_cfg`,
`gen_steps`, `gen_sampler`, `adv_card`, `adv_cfg`, `adv_steps`, `adv_sampler`,
`adv_pos`, `adv_neg`, `adv_variants`, `adv_reroll`, `adv_info`, `style_pos`,
`style_neg`, `style_trig`, `style_lora`, `style_lw`, `lora_rows`, `dryrun`,
`seedblock`, `spoilshield`, `civitai_token`, `baseurl`, `vendor_plugin`,
`feed_file`, `feed_info`, `rig_cmd`, `rig_cwd`, `rig_kind`, `btn_comfy`,
`build`, `repline`, `pvstage`, `pvinfo`
**Status/misc** `log`, `joberr`, `busydot`, `busytext`, `applyinfo`,
`applymode`, `spoilshield`

### Class names the JS selects on (keep on the built elements)
`cards`, `dcard`, `ed_rg`, `ed_inline`, `stack`, `scenbox`, `reqs`

### `data-*` attributes the JS reads (keep them)
`data-key` (editor regions), `data-cid`, `data-sid`, `data-stack`, `data-rc`,
`data-edges`, `data-links`, `data-built`

## Guardrail

`studio_selftest.py` now checks that every contract id above is present in
`PAGE`. After porting a redesign, run:

```
python3 cardforge/studio_selftest.py
```

A redesign that drops or renames a hook fails the `UI contract` check with the
exact missing id — so you find it before a user does, not after.

## Regenerate this contract

If the JS changes, refresh the lists above:

```python
import re
src = open('cardforge/studio.py').read()
ids  = sorted(set(re.findall(r"getElementById\(['\"]([a-zA-Z0-9_]+)['\"]\)", src)))
cls  = sorted(set(re.findall(r"querySelector(?:All)?\(['\"]\.([\w\- ]+)['\"]", src)))
data = sorted(set(re.findall(r"dataset\.([a-zA-Z0-9_]+)", src)))
print(len(ids), "ids;", cls, data)
```
