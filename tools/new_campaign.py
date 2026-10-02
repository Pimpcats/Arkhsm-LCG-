#!/usr/bin/env python3
"""Scaffold a new campaign that builds, renders and tests like The Still Hour.

    python3 tools/new_campaign.py <id> "<Campaign Name>" [--prefix abcd]

Writes campaigns/<id>/ (build config, art config in the house Arkham style,
card specs with a small EXAMPLE scenario, overrides, scenario manifest and
assignments, art scenes, log layout, guide and design skeletons, production
tracker) and src/tts/<id>_control.lua (a working Control token: difficulty
presets, campaign chaos-bag changes, investigator count, save/load, tests).
The example scenario follows the official shape (a clue act and a
take-and-deliver act with a story asset, Resign, agenda flavor, act and agenda
backs, unrevealed location sides, location rules text) in a neutral style.
The prefix must not be used by (or overlap) another campaign's.

Every file the example writes is marked EXAMPLE: the assistant replaces the
example scenario with the real campaign, following docs/CAMPAIGN_PLAYBOOK.md.
Then build with the campaign selected, e.g.:

    export CAMPAIGN=<id>
    python3 pipeline/render_set_icons.py
    python3 pipeline/scenario_content.py
    python3 pipeline/render_placeholders.py
    python3 pipeline/build_cards.py --local
    python3 pipeline/bundle_mod.py --local
    python3 pipeline/compile_campaign.py
    lua5.4 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
    lua5.2 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
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
    """A tiny scenario in the official shape (docs/design/CAMPAIGN_DESIGN_LESSONS.md
    section 1): one investigator; two agendas with flavor and story backs; two
    acts, one clue act and one take-and-deliver act with a set-aside story
    asset, both with backs; four locations with rules text (a Resign on the
    starting location, a thoroughfare at 0 clues, a Victory room at shroud 4)
    whose unrevealed sides carry flavor (one also rules); enemies incl. an
    elite; treacheries in the official mix (most test, one lingers)."""
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
    col = "#2d5b58"

    def link(*symbols):
        return [{"symbol": s, "color": col} for s in symbols]

    enc = [
        {"id": p + "-scn", "type": "Scenario", "name": name, "tokens": [
            {"token": "skull", "text": "-X. X is the number of enemies at your location."},
            {"token": "cultist", "text": "-2. If you fail, place 1 doom on the current agenda."},
            {"token": "tablet", "text": "-2. If there is an enemy at your location, take 1 horror."},
            {"token": "elderthing", "text": "-3. If you fail, discard 1 card at random."}]},
        {"id": p + "-agenda-1", "type": "Agenda", "name": "The Night Begins", "index": 1, "number": 1, "doom": 7},
        {"id": p + "-agenda-2", "type": "Agenda", "name": "The Night Closes In", "index": 2, "number": 2, "doom": 9},
        {"id": p + "-act-1", "type": "Act", "name": "Follow the Trail", "index": 1, "number": "1",
         "clues": 2, "clues_per_investigator": True},
        {"id": p + "-act-2", "type": "Act", "name": "Carry the Map", "index": 2, "number": "2",
         "clues": 1, "clues_per_investigator": True,
         "take": {"asset": p + "-story-1", "at": "The Old Mill", "deliver": "The Chapel"}},
        {"id": p + "-loc-a", "type": "Location", "name": "The Station", "traits": "Town.", "shroud": 2, "clues": 1,
         "clues_per_investigator": True, "icons": "circle", "color": col, "connections": link("diamond")},
        {"id": p + "-loc-x", "type": "Location", "name": "The Crossroads", "traits": "Town.", "shroud": 1, "clues": 0,
         "clues_per_investigator": True, "icons": "diamond", "color": col, "unrevealed": True,
         "connections": link("circle", "square", "triangle")},
        {"id": p + "-loc-b", "type": "Location", "name": "The Old Mill", "traits": "Town.", "shroud": 3, "clues": 1,
         "clues_per_investigator": True, "icons": "square", "color": col, "unrevealed": True,
         "connections": link("diamond", "triangle")},
        {"id": p + "-loc-c", "type": "Location", "name": "The Chapel", "traits": "Town. Sanctum.", "shroud": 4,
         "clues": 2, "clues_per_investigator": True, "icons": "triangle", "color": col, "unrevealed": True,
         "connections": link("diamond", "square"), "victory": 1},
        {"id": p + "-story-1", "type": "Asset", "name": "Old Survey Map", "class": "Neutral", "traits": "Item.",
         "encounter": True, "unique": True, "cost": "–", "quantity": 1},
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
        p + "-agenda-1": {"text": "Example Lurker gets +1 fight.",
                          "flavor": "EXAMPLE agenda flavor: the streetlamps go out one by one.",
                          "back_flavor": "EXAMPLE story: a bell rings somewhere in the dark.",
                          "back_text": "Each investigator takes 1 horror. Advance to agenda 2."},
        p + "-agenda-2": {"text": "Example Horror gets +1 fight and +1 evade.",
                          "flavor": "EXAMPLE agenda flavor: the night is nearly over.",
                          "back_flavor": "EXAMPLE story: the dark closes over the town.",
                          "back_text": "(→R2)"},
        p + "-act-1": {"text": "Objective – Investigators at The Old Mill may, as a group, spend 2 [perinv] clues "
                               "to advance.",
                       "flavor": "EXAMPLE act flavor: the trail leads out of town.",
                       "back_flavor": "EXAMPLE story: inside the mill, an old map is pinned to the wall.",
                       "back_text": "Put the set-aside Example Horror into play at The Chapel."},
        p + "-act-2": {"text": "[action] Investigators at The Old Mill spend 1 [perinv] clue, as a group: Take control "
                               "of the set-aside Old Survey Map. Only an investigator at The Old Mill may trigger "
                               "this ability.\nObjective – If the investigator who controls Old Survey Map is at "
                               "The Chapel, advance.",
                       "flavor": "EXAMPLE act flavor: the map marks the chapel.",
                       "back_flavor": "EXAMPLE story: the map matches the chapel floor.",
                       "back_text": "Remove Old Survey Map from the game. (→R1)"},
        p + "-loc-a": {"text": "[action]: Resign. You leave on the last train.",
                       "flavor": "EXAMPLE location."},
        p + "-loc-x": {"text": "Forced – After an enemy moves into The Crossroads: It exhausts.",
                       "flavor": "EXAMPLE thoroughfare.", "unrevealed_flavor": "EXAMPLE unrevealed side."},
        p + "-loc-b": {"text": "Forced – After you fail a skill test while investigating The Old Mill: Take 1 damage.",
                       "flavor": "EXAMPLE location.", "unrevealed_flavor": "EXAMPLE unrevealed side."},
        p + "-loc-c": {"text": "[action] Spend 1 clue: Heal 1 horror. Limit once per round.",
                       "flavor": "EXAMPLE Victory location.", "unrevealed_flavor": "EXAMPLE unrevealed side.",
                       "unrevealed_text": "Investigators cannot move into The Chapel while there are clues on "
                                          "The Old Mill."},
        p + "-story-1": {"text": "[fast] Exhaust Old Survey Map: You get +1 [int] for this skill test.\n"
                                 "Forced – When you are eliminated: Place Old Survey Map at your location.\n"
                                 "[action]: Take control of Old Survey Map while it is at your location with no "
                                 "controller.",
                         "flavor": "EXAMPLE story asset."},
        p + "-enemy-1": {"fight": 3, "health": 3, "evade": 2, "damage": 1, "horror": 1, "text": "Hunter."},
        p + "-elite-1": {"fight": 4, "health": 5, "evade": 3, "damage": 2, "horror": 1,
                         "text": "Retaliate.\nSpawn – The Chapel."},
        p + "-tr-1": {"text": "Revelation – Test [wil] (3). If you fail, take 1 horror for each point you failed by (maximum 2)."},
        p + "-tr-2": {"text": "Revelation – Attach to your location. It gets +1 shroud.\n[action]: Test [agi] (3). If you succeed, discard Grasping Mist."},
        p + "-tr-3": {"text": "Revelation – Place 1 doom on the current agenda."},
    }
    return player, enc, text, inv


LOCS = (("-loc-a", "The Station", 2, 1), ("-loc-x", "The Crossroads", 1, 0),
        ("-loc-b", "The Old Mill", 3, 1), ("-loc-c", "The Chapel", 4, 2))


def manifest(cid, name, p, inv):
    where = [n for _, n, _, _ in LOCS]
    locs = [{"id": p + s, "name": n, "shroud": sh, "clues": cl} for s, n, sh, cl in LOCS]
    locs[0]["starting"] = True
    return {
        "_note": "EXAMPLE scenario written by tools/new_campaign.py; replace with the real campaign "
                 "(docs/design/SCENARIO_SCHEMA.md, docs/CAMPAIGN_PLAYBOOK.md). Tiny on purpose: an official "
                 "scenario has about 12 locations and a 25-33 card encounter deck.",
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
                "locations": {"template": "Location", "status": "authored", "cards": locs},
                "agenda_deck": {"template": "Agenda", "status": "authored", "cards": [
                    {"id": p + "-agenda-1", "name": "The Night Begins", "doom": 7},
                    {"id": p + "-agenda-2", "name": "The Night Closes In", "doom": 9}]},
                "act_deck": {"template": "Act", "status": "authored", "cards": [
                    {"id": p + "-act-1", "name": "Follow the Trail", "at": "The Old Mill",
                     "needs": {"clues": "card", "from": where}},
                    {"id": p + "-act-2", "name": "Carry the Map", "at": "The Chapel",
                     "needs": {"clues": "card", "from": where},
                     "carry": {"asset": p + "-story-1", "take_at": "The Old Mill", "deliver_to": "The Chapel"}}]},
                "encounter": {"sets": ["example_set"], "aside": []},
                "setup_aside": {"cards": [{"id": p + "-elite-1", "name": "Example Horror", "role": "elite"},
                                          {"id": p + "-story-1", "name": "Old Survey Map",
                                           "role": "story asset (Carry the Map)"}]},
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
        "locations": [p + s for s, _, _, _ in LOCS],
        "encounter": [p + "-enemy-1", p + "-enemy-1", p + "-tr-1", p + "-tr-1", p + "-tr-2", p + "-tr-2",
                      p + "-tr-3", p + "-tr-3"],
        "setup_aside": [p + "-elite-1", p + "-story-1"],
        "_map": {p + "-loc-a": [1, 1], p + "-loc-x": [2, 1], p + "-loc-b": [3, 0], p + "-loc-c": [3, 2]},
    }}


# The house art style for a new campaign: the Arkham LCG painterly language the
# reference campaign settled on (1930s pulp oil), without that campaign's own
# motifs. The backend, checkpoint and negative prompt come from
# campaigns/still_hour/campaign.json; art_scenes.json adds the subjects.
HOUSE_STYLE_POSITIVE = (
    "1920s cosmic horror card illustration, hand-painted in oil on illustration board in the manner of a "
    "1930s weird-fiction pulp magazine interior painting, dramatic value design, bold simplified value "
    "masses, confident broad brush strokes, economical, workmanlike finish with visible simplification and "
    "occasional unfinished passages, restrained muted color, clearly hand-painted by a working commercial "
    "illustrator. Broad, economical brushwork with large quiet areas of thin, relatively flat paint; visible "
    "brush marks only where the illustrator needs them. Hand-painted irregularity comes from uneven drawing, "
    "drifting spacing, crooked architecture, varied silhouette shapes, lost edges, overworked focal passages "
    "and unfinished peripheral areas, not from texture on every surface")
HOUSE_DETAIL_HIERARCHY = (
    "Concentrate detail around the face, hands, and important prop. Keep clothing, architecture, landscape "
    "and sky simplified into large value masses. Background forms should dissolve quickly and should never "
    "compete with the focal subject.")


def house_style(cid):
    """campaigns/still_hour/campaign.json's backend settings with the neutral house style."""
    path = os.path.join(ROOT, "campaigns", "still_hour", "campaign.json")
    house = {k: v for k, v in json.load(open(path, encoding="utf-8")).items()
             if k != "_checkpoint_note"}
    house["output_dir"] = "out/" + cid
    house["style_positive"] = HOUSE_STYLE_POSITIVE
    guidance = dict(house.get("style_guidance") or {})
    guidance["DETAIL HIERARCHY"] = HOUSE_DETAIL_HIERARCHY
    house["style_guidance"] = guidance
    house["_style_note"] = ("House style for a new campaign (tools/new_campaign.py): the Arkham LCG painterly "
                            "language without any one campaign's motifs. Put this campaign's own subjects in "
                            "art_scenes.json.")
    return house


def prefixes_in_use(skip=None):
    """{prefix: campaign id} for every campaign folder (build.json "prefix",
    else campaign_config's default: the first four characters of the id)."""
    used = {}
    base = os.path.join(ROOT, "campaigns")
    for cid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if cid == skip or cid.startswith((".", "_")) or not os.path.isdir(os.path.join(base, cid)):
            continue
        p = cid[:4]
        build = os.path.join(base, cid, "build.json")
        if os.path.exists(build):
            try:
                p = json.load(open(build, encoding="utf-8")).get("prefix") or p
            except ValueError:
                pass
        used[p] = cid
    return used


def check_prefix(p, cid):
    """Card ids, hosted image names and table GUIDs all start with the prefix:
    refuse one another campaign uses, or one that starts or is started by
    another campaign's (publish and render steps select files by prefix)."""
    if not re.match(r"^[a-z][a-z0-9]{2,7}$", p):
        raise SystemExit("prefix: 3-8 lower-case letters or digits, starting with a letter (e.g. drbl)")
    for other, owner in prefixes_in_use(skip=cid).items():
        if p == other:
            raise SystemExit("prefix '%s' is already used by campaigns/%s; choose another --prefix" % (p, owner))
        if p.startswith(other) or other.startswith(p):
            raise SystemExit("prefix '%s' overlaps '%s' (campaigns/%s); choose a prefix that neither starts "
                             "with nor begins another campaign's" % (p, other, owner))


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

**Setup.** Gather the Example Set. Put The Station into play revealed and the other locations
unrevealed. Set Example Horror and the Old Survey Map story asset aside. Each investigator begins at
The Station.

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
    check_prefix(p, cid)
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    tag = "".join(w.capitalize() for w in cid.split("_"))
    house = house_style(cid)
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
