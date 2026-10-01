#!/usr/bin/env python3
"""Scaffold a new campaign that builds, renders and tests like The Still Hour.

    python3 tools/new_campaign.py <id> "<Campaign Name>" [--prefix abcd]

Writes campaigns/<id>/ (build config, art config in the house Arkham style,
card specs with a small EXAMPLE scenario, overrides, scenario manifest and
assignments, art scenes, log layout, guide and design skeletons, production
tracker) and src/tts/<id>_control.lua (a working Control token: difficulty
presets, campaign chaos-bag changes, investigator count, save/load, tests).

Every file the example writes is marked EXAMPLE: the assistant replaces the
example scenario with the real campaign, following docs/CAMPAIGN_PLAYBOOK.md.
Then build with the campaign selected, e.g.:

    CAMPAIGN=<id> python3 pipeline/render_placeholders.py
    CAMPAIGN=<id> python3 pipeline/scenario_content.py
    CAMPAIGN=<id> python3 pipeline/build_cards.py --local
    CAMPAIGN=<id> python3 pipeline/bundle_mod.py --local
    CAMPAIGN=<id> python3 pipeline/compile_campaign.py
    lua5.4 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def example_cards(p, name):
    """A tiny but complete scenario (one investigator, two agendas, two acts,
    three locations, enemies incl. an elite, treacheries in the official mix)."""
    inv = p + "inv1"
    player = [
        {"id": inv, "type": "Investigator", "name": "Example Investigator", "subtitle": "EXAMPLE — replace",
         "class": "Guardian", "traits": "Detective.", "wil": 3, "int": 3, "com": 3, "agi": 3,
         "health": 8, "sanity": 7, "signatures": [{p + "-sig1": 1, p + "-weak1": 1}],
         "elderSign": "+1. Draw 1 card."},
        {"id": p + "-sig1", "type": "Asset", "name": "Example Signature", "subtitle": "", "class": "Guardian",
         "traits": "Item.", "cost": 2, "level": 0, "slot": "Hand"},
        {"id": p + "-weak1", "type": "Treachery", "name": "Example Weakness", "subtitle": "", "class": "Neutral",
         "traits": "Flaw.", "weakness": True},
    ]
    enc = [
        {"id": p + "-scn", "type": "Scenario", "name": name, "tokens": [
            {"token": "skull", "text": "-X. X is the number of enemies at your location."},
            {"token": "cultist", "text": "-2. If you fail, place 1 doom on the current agenda."},
            {"token": "tablet", "text": "-2. If there is an enemy at your location, take 1 horror."},
            {"token": "elderthing", "text": "-3. If you fail, discard 1 card at random."}]},
        {"id": p + "-agenda-1", "type": "Agenda", "name": "The Night Begins", "index": 1, "number": 1, "doom": 6},
        {"id": p + "-agenda-2", "type": "Agenda", "name": "The Night Closes In", "index": 2, "number": 2, "doom": 8},
        {"id": p + "-act-1", "type": "Act", "name": "Follow the Trail", "index": 1, "number": "1",
         "clues": 2, "clues_per_investigator": True},
        {"id": p + "-act-2", "type": "Act", "name": "Into the Dark", "index": 2, "number": "2",
         "clues": 3, "clues_per_investigator": True},
        {"id": p + "-loc-a", "type": "Location", "name": "The Station", "traits": "Town.", "shroud": 2, "clues": 1,
         "clues_per_investigator": True, "icons": "circle", "color": "#2d5b58", "connections": [{"symbol": "square", "color": "#2d5b58"}, {"symbol": "triangle", "color": "#2d5b58"}]},
        {"id": p + "-loc-b", "type": "Location", "name": "The Old Mill", "traits": "Town.", "shroud": 3, "clues": 1,
         "clues_per_investigator": True, "icons": "square", "color": "#2d5b58", "connections": [{"symbol": "circle", "color": "#2d5b58"}, {"symbol": "triangle", "color": "#2d5b58"}]},
        {"id": p + "-loc-c", "type": "Location", "name": "The Chapel", "traits": "Town.", "shroud": 3, "clues": 2,
         "clues_per_investigator": True, "icons": "triangle", "color": "#2d5b58", "connections": [{"symbol": "circle", "color": "#2d5b58"}, {"symbol": "square", "color": "#2d5b58"}],
         "victory": 1},
        {"id": p + "-enemy-1", "type": "Enemy", "name": "Example Lurker", "class": "Mythos", "traits": "Monster.",
         "encounter": True, "quantity": 2},
        {"id": p + "-elite-1", "type": "Enemy", "name": "Example Horror", "class": "Mythos",
         "traits": "Monster. Elite.", "encounter": True, "elite": True, "victory": 1},
        {"id": p + "-tr-1", "type": "Treachery", "name": "Creeping Dread", "class": "Mythos", "traits": "Terror.",
         "encounter": True, "quantity": 2},
        {"id": p + "-tr-2", "type": "Treachery", "name": "Grasping Mist", "class": "Mythos", "traits": "Hazard.",
         "encounter": True, "quantity": 2},
        {"id": p + "-tr-3", "type": "Treachery", "name": "Ancient Evils", "class": "Mythos", "traits": "Omen.",
         "encounter": True, "quantity": 2},
    ]
    text = {
        inv: {"text": "[reaction] After you defeat an enemy: Discover 1 clue at your location. Limit once per round.",
              "flavor": "EXAMPLE investigator — replace."},
        p + "-sig1": {"text": "Uses (3 charges).\n[action] Spend 1 charge: Fight. You get +2 [com] for this attack."},
        p + "-weak1": {"text": "Revelation – Take 1 horror. Shuffle Example Weakness into your deck."},
        p + "-agenda-1": {"text": "When reached: Each investigator takes 1 horror. Advance to the next agenda."},
        p + "-agenda-2": {"text": "When reached: The night is over. (→R2)"},
        p + "-act-1": {"text": "Objective – Investigators at The Old Mill may, as a group, spend 2 [perinv] clues to advance."},
        p + "-act-2": {"text": "Objective – Investigators at The Chapel may, as a group, spend 3 [perinv] clues to advance. (→R1)"},
        p + "-loc-a": {"text": "", "flavor": "EXAMPLE location."},
        p + "-loc-b": {"text": "", "flavor": "EXAMPLE location."},
        p + "-loc-c": {"text": "", "flavor": "EXAMPLE location."},
        p + "-enemy-1": {"fight": 3, "health": 3, "evade": 2, "damage": 1, "horror": 1, "text": "Hunter."},
        p + "-elite-1": {"fight": 4, "health": 5, "evade": 3, "damage": 2, "horror": 1,
                         "text": "Retaliate.\nSpawn – The Chapel."},
        p + "-tr-1": {"text": "Revelation – Test [wil] (3). If you fail, take 1 horror for each point you failed by (maximum 2)."},
        p + "-tr-2": {"text": "Revelation – Attach to your location. It gets +1 shroud.\n[action]: Test [agi] (3). If you succeed, discard Grasping Mist."},
        p + "-tr-3": {"text": "Revelation – Place 1 doom on the current agenda."},
    }
    return player, enc, text, inv


def manifest(cid, name, p, inv):
    return {
        "_note": "EXAMPLE scenario written by tools/new_campaign.py; replace with the real campaign "
                 "(docs/design/SCENARIO_SCHEMA.md, docs/CAMPAIGN_PLAYBOOK.md).",
        "campaign": {"id": cid, "name": name, "box_id": "CB-" + p.upper(), "investigators": [inv],
                     "encounter_sets": {"example_set": {"name": "Example Set", "cards": [
                         {"id": p + "-enemy-1", "name": "Example Lurker", "type": "Enemy", "qty": 2},
                         {"id": p + "-tr-1", "name": "Creeping Dread", "type": "Treachery", "qty": 2},
                         {"id": p + "-tr-2", "name": "Grasping Mist", "type": "Treachery", "qty": 2},
                         {"id": p + "-tr-3", "name": "Ancient Evils", "type": "Treachery", "qty": 2}]}},
                     "resolutions": []},
        "scenarios": [{
            "id": "example", "name": "Example Scenario", "order": 0,
            "reference": {"id": p + "-scn", "status": "authored"},
            "stacks": {
                "locations": {"template": "Location", "status": "authored", "cards": [
                    {"id": p + "-loc-a", "name": "The Station", "starting": True, "shroud": 2, "clues": 1},
                    {"id": p + "-loc-b", "name": "The Old Mill", "shroud": 3, "clues": 1},
                    {"id": p + "-loc-c", "name": "The Chapel", "shroud": 3, "clues": 2}]},
                "agenda_deck": {"template": "Agenda", "status": "authored", "cards": [
                    {"id": p + "-agenda-1", "name": "The Night Begins", "doom": 6},
                    {"id": p + "-agenda-2", "name": "The Night Closes In", "doom": 8}]},
                "act_deck": {"template": "Act", "status": "authored", "cards": [
                    {"id": p + "-act-1", "name": "Follow the Trail", "at": "The Old Mill",
                     "needs": {"clues": "card", "from": ["The Station", "The Old Mill", "The Chapel"]}},
                    {"id": p + "-act-2", "name": "Into the Dark", "at": "The Chapel",
                     "needs": {"clues": "card", "from": ["The Station", "The Old Mill", "The Chapel"]}}]},
                "encounter": {"sets": ["example_set"], "aside": []},
                "setup_aside": {"cards": [{"id": p + "-elite-1", "name": "Example Horror", "role": "elite"}]},
            },
            "setup": {"starting_location": "The Station"},
            "resolutions": [
                {"id": "R1", "name": "Out of the Dark", "condition": "act 2 advanced"},
                {"id": "R2", "name": "The Night Wins", "condition": "the last agenda advanced"},
                {"id": "NR", "name": "No Resolution", "condition": "every investigator resigned or was defeated"}],
        }],
    }


def assignments(p):
    return {"example": {
        "reference": [p + "-scn"],
        "agenda_deck": [p + "-agenda-1", p + "-agenda-2"],
        "act_deck": [p + "-act-1", p + "-act-2"],
        "locations": [p + "-loc-a", p + "-loc-b", p + "-loc-c"],
        "encounter": [p + "-enemy-1", p + "-enemy-1", p + "-tr-1", p + "-tr-1", p + "-tr-2", p + "-tr-2",
                      p + "-tr-3", p + "-tr-3"],
        "setup_aside": [p + "-elite-1"],
        "_map": {p + "-loc-a": [1, 1], p + "-loc-b": [2, 1], p + "-loc-c": [3, 1]},
    }}


LOG_LAYOUT = '''"""Campaign log layout for %(name)s (pipeline/campaign_log.py draws it and
generates the log token's Lua). EXAMPLE: one page with the official log's
blocks; add the campaign's own records (choices, Knowledge, hidden names) as
the design settles. Field types: cb checkbox, ct counter, tx text line,
rv text revealed when another field is ticked."""
NAME = %(name)r
PAGE_IDS = [%(p)r + "-log-page1"]
LOG_ID = %(P)r + "-LOG"
INVESTIGATORS = []        # (id, name) once the investigators exist
FACTS = []                # (id, name, scenario, layer, effect): recorded story facts


def pages(Page, K):
    W = K["PAGE_W"]
    p = Page(1, "Campaign Log")
    p.text(W // 2, 128, NAME + " — Campaign Log", size=62, style="title", fill=K["TEAL"], anchor="ms")
    y = 222
    p.text(90, y, "Difficulty:", size=24, style="bold")
    x = p.checkbox("diff_easy", 250, y, "Easy", group="diff")
    x = p.checkbox("diff_standard", x, y, "Standard", group="diff")
    x = p.checkbox("diff_hard", x, y, "Hard", group="diff")
    p.checkbox("diff_expert", x, y, "Expert", group="diff")
    p.header(300, "Investigators")
    y = 360
    for i in range(1, 5):
        p.text(90, y, "Investigator %%d" %% i, size=24, style="bold")
        p.line("inv%%d" %% i, 300, 760, y)
        p.text(790, y, "XP", size=24, style="bold")
        p.counter("xp%%d" %% i, 870, y - 9, 0, 99)
        p.text(930, y, "Trauma", size=22, style="bold")
        p.counter("trauma%%d" %% i, 1080, y - 9, 0, 9)
        y += 80
    p.header(y + 20, "Campaign Notes")
    p.line("notes", 90, 1190, y + 80, rows=6, row_h=40)
    y += 360
    p.header(y, "Chaos Bag Changes")
    p.line("bag", 90, 1190, y + 60, rows=2, row_h=40)
    p.header(y + 170, "Victory Display")
    p.line("victory", 90, 1190, y + 230, rows=3, row_h=40)
    return [p]
'''

GUIDE = '''# %(upper)s — CAMPAIGN GUIDE

EXAMPLE skeleton (tools/new_campaign.py). Keep the official guide order; spoilers
behind "Do not read until" lines; resolutions in ```resolution fences.

## HOW TO USE THIS GUIDE

## CAMPAIGN RULES

## CAMPAIGN SETUP

1. **Choose investigators.**
2. **Choose a difficulty** and assemble the chaos bag (the Control token's buttons do it).

| Difficulty | Chaos tokens |
|---|---|
| Easy | +1, +1, 0, 0, 0, −1, −1, −1, −2, −2, [skull], [skull], [cultist], [tablet], [autofail], [elder] |
| Standard | +1, 0, 0, −1, −1, −1, −2, −2, −3, −4, [skull], [skull], [cultist], [tablet], [autofail], [elder] |
| Hard | 0, 0, 0, −1, −1, −2, −2, −3, −3, −4, −5, [skull], [skull], [cultist], [tablet], [elderthing], [autofail], [elder] |
| Expert | 0, −1, −1, −2, −2, −3, −3, −4, −4, −5, −6, −8, [skull], [skull], [cultist], [tablet], [elderthing], [autofail], [elder] |

## EXAMPLE SCENARIO

**Do not read until you begin this scenario.**

> Intro text.

**Setup.** Put The Station into play. Gather the Example Set.

**Do not read until the end of the scenario.**

```resolution No Resolution
> No resolution text.
- Read Resolution 2.
```

```resolution Resolution 1 — Out of the Dark
> Resolution text.
- In your Campaign Log, record that *the investigators escaped*.
```

```resolution Resolution 2 — The Night Wins
> Resolution text.
- Each investigator suffers 1 mental trauma.
```

## DIFFICULTY AND PLAYER COUNT
'''

DESIGN = '''# %(name)s — design (SPOILERS)

Fill in during playbook step 3 (docs/CAMPAIGN_PLAYBOOK.md). EXAMPLE skeleton.

## Brief
(owner's theme, tone, players, length, must / never)

## Structure
Scenarios, their order and how they link.

## Core mechanic and currencies
Each resource the campaign trades in, what it costs and what it buys.

## Story graph
Every scenario: 2+ resolutions; recorded choices and where they echo; one finale, several endings.

## Campaign log
What is recorded; which names stay hidden until earned.

## Chaos-bag changes
Which story results add or remove a [cultist] / [tablet] / [elderthing] (official pattern; Elder Sign and Auto-fail almost never).

## XP
Victory per scenario and resolution bonuses; target 35–50 per investigator per campaign.

## Difficulty and player-count scaling

## Win-rate curve (owner)
Default: early scenarios 80%%, then 70 / 60 / 50, finale 40%% at three investigators; never above 80%%.

## Playtest checklist
'''

CONTROL = r'''-- %(upper)s — Control token. GENERATED STARTER (tools/new_campaign.py):
-- the campaign's bookkeeping on the table. Difficulty presets fill SCED's
-- chaos bag together with the campaign chaos-bag changes; investigators;
-- save/load; an in-engine test entry. Add the campaign's own rules here (or
-- as modules under src/<lua_dir>/ listed in build.json "lua_modules").

local state = { investigators = 3, difficulty = nil, bag = { cultist = 0, tablet = 0, elder = 0 } }

local DIFFICULTY = {
  { label = "Easy", bag = { "p1", "p1", "0", "0", "0", "m1", "m1", "m1", "m2", "m2",
                            "skull", "skull", "cultist", "tablet", "red", "blue" } },
  { label = "Standard", bag = { "p1", "0", "0", "m1", "m1", "m1", "m2", "m2", "m3", "m4",
                                "skull", "skull", "cultist", "tablet", "red", "blue" } },
  { label = "Hard", bag = { "0", "0", "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m5",
                            "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
  { label = "Expert", bag = { "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m4", "m5", "m6", "m8",
                              "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
}
local SYMBOLS = { { key = "cultist", name = "Cultist" }, { key = "tablet", name = "Tablet" },
                  { key = "elder", name = "Elder Thing" } }

local function announce(msg)
  if broadcastToAll then broadcastToAll("[%(name)s] " .. msg) else print(msg) end
end

--- A difficulty's tokens plus the campaign's chaos-bag changes (never below 0).
function bagFor(i)
  local d = DIFFICULTY[i]
  local out, count = {}, { cultist = 0, tablet = 0, elder = 0 }
  for _, t in ipairs(d.bag) do
    if count[t] ~= nil then count[t] = count[t] + 1 else out[#out + 1] = t end
  end
  for _, s in ipairs(SYMBOLS) do
    for _ = 1, math.max(0, count[s.key] + (state.bag[s.key] or 0)) do out[#out + 1] = s.key end
  end
  return out
end

local function fillBag()
  local i = state.difficulty
  if not i then return false end
  local ok = pcall(function() Global.call("setChaosBagState", bagFor(i)) end)
  return ok
end

local function refresh()
  if not self or not self.clearButtons then return end
  self.clearButtons()
  local function button(fn, label, x, z, w)
    self.createButton({ click_function = fn, function_owner = self, label = label,
      position = { x, 0.2, z }, width = w or 900, height = 260, font_size = 120 })
  end
  button("ctlInvestigators", "Investigators " .. state.investigators, 0, -1.2, 1400)
  for i, d in ipairs(DIFFICULTY) do button("ctlDifficulty" .. i, d.label, -1.8 + (i - 1) * 1.2, -0.6, 520) end
  button("ctlStatus", "Status", -0.8, 0)
  button("ctlRunTests", "Run Tests", 0.8, 0)
end

--- A story result adds (delta 1) or removes (delta -1) a symbol token for the
-- rest of the campaign: key "cultist", "tablet" or "elder".
function bagChange(key, delta)
  if state.bag[key] == nil then return false end
  state.bag[key] = state.bag[key] + delta
  local name = key
  for _, s in ipairs(SYMBOLS) do if s.key == key then name = s.name end end
  local filled = fillBag()
  announce(string.format("Campaign chaos-bag change: %%s 1 %%s token for the rest of the campaign%%s",
    delta > 0 and "add" or "remove", name, filled and " (done on the chaos bag)." or ". Change the bag by hand."))
  return true
end

function ctlInvestigators(_, _, alt)
  state.investigators = math.max(1, math.min(4, state.investigators + (alt and -1 or 1)))
  refresh()
end
function ctlDifficulty(i)
  state.difficulty = i
  if fillBag() then announce("Chaos bag set to " .. DIFFICULTY[i].label .. ".")
  else announce("Build the " .. DIFFICULTY[i].label .. " bag by hand (Campaign Setup).") end
end
function ctlDifficulty1() ctlDifficulty(1) end
function ctlDifficulty2() ctlDifficulty(2) end
function ctlDifficulty3() ctlDifficulty(3) end
function ctlDifficulty4() ctlDifficulty(4) end
function ctlStatus()
  announce(string.format("Investigators %%d · difficulty %%s · bag changes Cultist %%+d, Tablet %%+d, Elder Thing %%+d",
    state.investigators, state.difficulty and DIFFICULTY[state.difficulty].label or "not set",
    state.bag.cultist, state.bag.tablet, state.bag.elder))
end

function onSave() return JSON.encode(state) end
function onLoad(saved)
  if saved and saved ~= "" then
    local ok, s = pcall(JSON.decode, saved)
    if ok and type(s) == "table" then
      state = s
      state.bag = state.bag or { cultist = 0, tablet = 0, elder = 0 }
    end
  end
  refresh()
end

--- In-engine tests (also run by pipeline/verify_control.lua).
function %(tests)s()
  local P, F = 0, 0
  local function check(name, cond)
    if cond then P = P + 1 ; print("[PASS] " .. name) else F = F + 1 ; print("[FAIL] " .. name) end
  end
  local saved = JSON.encode(state)
  state = { investigators = 3, difficulty = 2, bag = { cultist = 0, tablet = 0, elder = 0 } }
  check("Standard bag has 16 tokens", #bagFor(2) == 16)
  state.bag.tablet = 1
  local n = 0
  for _, t in ipairs(bagFor(2)) do if t == "tablet" then n = n + 1 end end
  check("a campaign change adds a Tablet token", n == 2)
  state.bag.cultist = -1
  n = 0
  for _, t in ipairs(bagFor(2)) do if t == "cultist" then n = n + 1 end end
  check("a campaign change removes the Cultist token", n == 0)
  state.bag.cultist = -2
  n = 0
  for _, t in ipairs(bagFor(2)) do if t == "cultist" then n = n + 1 end end
  check("never below 0", n == 0)
  state = JSON.decode(saved)
  print(string.format("RESULT: %%d passed, %%d failed", P, F))
  return { passed = P, failed = F }
end
function ctlRunTests() return %(tests)s() end
'''


def scaffold(cid, name, prefix, force=False):
    if not re.match(r"^[a-z][a-z0-9_]*$", cid):
        raise SystemExit("campaign id: lower-case letters, digits and _ (e.g. drowned_bells)")
    cdir = os.path.join(ROOT, "campaigns", cid)
    if os.path.exists(cdir) and not force:
        raise SystemExit("campaigns/%s already exists (use --force to overwrite the scaffold files)" % cid)
    p = prefix or re.sub(r"[^a-z]", "", cid)[:4]
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    tag = "".join(w.capitalize() for w in cid.split("_"))
    house = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "campaign.json"), encoding="utf-8"))
    house["output_dir"] = "out/" + cid
    build = {
        "_doc": "Build names for this campaign (pipeline/campaign_config.py). Select it with CAMPAIGN=%s." % cid,
        "name": name, "upper_name": name.upper(), "box_name": name, "slug": slug, "prefix": p, "tag": tag,
        "lua_dir": tag, "lua_modules": [], "control_lua": "src/tts/%s_control.lua" % cid,
        "tests_entry": "runCampaignTests",
        "specs": ["campaigns/%s/specs/cards_spec.json" % cid, "campaigns/%s/specs/encounter_spec.json" % cid],
        "cards_spec": "campaigns/%s/specs/cards_spec.json" % cid,
        "encounter_spec": "campaigns/%s/specs/encounter_spec.json" % cid,
        "print_text": "campaigns/%s/specs/print_text.json" % cid,
        "guide_md": "campaigns/%s/guide.md" % cid,
        "log_layout": "campaigns/%s/log_layout.py" % cid,
        "log_pages": [p + "-log-page1"],
        "starter": [], "render_all_pipeline_specs": False,
        "skip_bags": ["Encounter Cards"],   # the loose encounter bag would spoil the scenarios
        # encounter-set symbols (pipeline/render_set_icons.py, encounter_sets.py)
        "encounter_symbols": {"_default": "example_set", "example": "example_set"},
        "set_icon_shapes": {"example_set": "eclipse"},
        "encounter_bag_name": name.upper() + " — Encounter Cards",
        "genre": "cosmic-horror", "art_setting": "1920s New England, cosmic horror, uncanny rather than gory",
        "box_hue": 168,
    }
    player, enc, text, inv = example_cards(p, name)
    for c in enc:
        c.setdefault("class", "Mythos")
    # TTS CustomDeck ids, one per card (The Still Hour uses 95xxx)
    base = 96000 + (sum(p.encode()) % 40) * 25
    for i, c in enumerate(player + enc):
        c["deck"] = base + i
    files = {
        "build.json": build,
        "campaign.json": house,
        "characters.json": {},
        "card_overrides.json": {},
        "prompt_overrides.json": {},
        "font_overrides.json": {},
        "art_placements.json": {},
        "scenario_manifest.json": manifest(cid, name, p, inv),
        "scenario_assignments.json": assignments(p),
        "specs/cards_spec.json": player,
        "specs/encounter_spec.json": enc,
        "specs/print_text.json": text,
        "art_scenes.json": {"_note": "EXAMPLE scenes (subject only; the house style is in campaign.json)",
                            "scenes": {c["id"]: "EXAMPLE: " + c["name"].lower() + ", 1920s New England"
                                       for c in player + enc if c["type"] not in ("Scenario",)},
                            "characters": {}, "text_only": {p + "-scn": "scenario reference"}},
        "log_layout.py": LOG_LAYOUT % {"name": name, "p": p, "P": p.upper()},
        "guide.md": GUIDE % {"upper": name.upper()},
        "design.md": DESIGN % {"name": name},
        "assistant/production.json": {
            "campaign": cid, "name": name, "stage": "scaffolded",
            "brief": {"theme": "", "tone": "", "players": "", "length": "", "must": [], "never": []},
            "curve": {"by_scenario_win_rate_3p": "80/80/70/70/60/60/50/50, finale 40; cap 80"},
            "next": ["Playbook step 2: brief and pitch (owner picks one of 2-3 non-spoiler pitches)"],
            "evidence": []},
    }
    for rel, data in files.items():
        dump(os.path.join(cdir, rel), data)
    dump(os.path.join(ROOT, "src", "tts", cid + "_control.lua"),
         CONTROL % {"upper": name.upper(), "name": name, "tests": build["tests_entry"]})
    return {"campaign": cid, "prefix": p, "slug": slug, "dir": os.path.relpath(cdir, ROOT),
            "control": "src/tts/%s_control.lua" % cid, "files": sorted(files)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("id", help="campaign id: lower-case, e.g. drowned_bells")
    ap.add_argument("name", help='display name, e.g. "The Drowned Bells"')
    ap.add_argument("--prefix", help="card id prefix (default: first 4 letters of the id)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    print(json.dumps(scaffold(a.id, a.name, a.prefix, a.force), indent=2))


if __name__ == "__main__":
    sys.exit(main())
