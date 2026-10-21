"""The play engine (tools/play_engine): The Still Hour played on the emulated
SCED table by a rules layer and an AI party (designer tooling).

  * every scenario card a box lays out has an entry in the engine's effects
    table (always runs; needs lua5.2);
  * one short game (2 rounds) of every scenario on the owner's SCED save,
    with no Lua error from SCED, the campaign or the engine. Skipped when the
    save is absent or SCED_REAL=0 (like tests/test_sced_real.py).

Every run must leave the working tree untouched (outputs go to .cache/).
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "tools", "play_engine")
sys.path.insert(0, ENGINE)

SAVE = os.environ.get("SCED_SAVE", "/home/user/sce480/Arkham SCE 4.8.0.json")


def _engine_run():
    # tests/sced_real/run.py is also a module called "run" (test_sced_resolutions):
    # load the engine's under its own name
    import importlib.util
    spec = importlib.util.spec_from_file_location("play_engine_run", os.path.join(ENGINE, "run.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
LUA = shutil.which("lua5.2")


@pytest.mark.parametrize("script", ["play_engine_regressions.lua", "play_engine_independent.lua", "play_engine_upgrades.lua",
                                    "play_engine_final_independent.lua", "play_engine_objective_windows.lua",
                                    "play_engine_balance_costs.lua", "play_engine_encounter_draws.lua",
                                    "play_engine_starter_cards.lua"])
@pytest.mark.parametrize("lua", ["lua5.2", "lua5.4"])
def test_campaign_rules_interactions(script, lua):
    exe = shutil.which(lua)
    if not exe:
        pytest.skip("no " + lua + " installed")
    out = subprocess.run([exe, os.path.join(ROOT, "tests", script)],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr


def _porcelain():
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout


@pytest.fixture
def clean_tree():
    before = _porcelain()
    yield
    assert _porcelain() == before, "the play engine changed tracked files"


COVERAGE_LUA = r"""
local R, T = {}, { E = {}, J = {} }
local FX = dofile(arg[1] .. "/effects.lua")(R, T)
local ids = {}
for id in pairs(FX.COVERAGE) do ids[#ids + 1] = id end
table.sort(ids)
io.write(table.concat(ids, "\n"))
"""


@pytest.mark.skipif(not LUA, reason="no lua5.2 installed")
def test_effects_table_covers_every_scenario_card(tmp_path):
    import cards
    all_cards, assign = cards.load_cards()
    wanted = cards.scenario_card_ids(assign)
    script = tmp_path / "cov.lua"
    script.write_text(COVERAGE_LUA)
    out = subprocess.run([LUA, str(script), os.path.join(ENGINE, "lua")], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    have = set(out.stdout.split())
    missing = sorted(wanted - have)
    assert not missing, "scenario cards with no entry in the effects table: %s" % missing
    unknown = sorted(i for i in have if i not in all_cards)
    assert not unknown, "effects for cards the campaign does not have: %s" % unknown


CODED_LUA = r"""
local R, T = {}, { E = {}, J = {} }
local P = dofile(arg[1] .. "/players.lua")(R, T)
local names = {}
for n in pairs(P.CODED) do names[#names + 1] = n end
io.write(table.concat(names, "\n"))
"""


def _starter_doc_cards():
    """{investigator heading: {card names}} from docs/STARTER_DECKS.md's list tables."""
    import re
    out, inv = {}, None
    for line in open(os.path.join(ROOT, "docs", "STARTER_DECKS.md"), encoding="utf-8"):
        if line.startswith("## "):
            inv = line[3:].strip()
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(Asset|Event|Skill)\s*\|", line)
        if m and inv:
            name = m.group(2).split(" \u2014 ")[0]          # "Jim Culver — Haunted Musician": the subtitle is not the name
            out.setdefault(inv, {})[name.replace("\u201c", '"').replace("\u201d", '"')] = int(m.group(1))
    return out


def test_engine_plays_the_seated_starter_decks():
    import re
    # decks.py reads the ids the Control seats from, so the engine's decks cannot drift from them
    import decks
    seated = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "starter_decks.json"), encoding="utf-8"))
    assert decks.LISTS == {inv: [(cid, n) for cid, n in rows] for inv, rows in seated.items()}
    assert set(decks.LISTS) == {"sthrelias", "sthrayako", "sthrcass", "sthrbirdie", "sthrseraphine"}
    assert all(sum(n for _, n in rows) == 30 for rows in decks.LISTS.values())
    doc = _starter_doc_cards()
    assert len(doc) == 5 and all(sum(d.values()) == 30 for d in doc.values()), doc
    who = {"Elias": "sthrelias", "Ayako": "sthrayako", "Cass": "sthrcass", "Birdie": "sthrbirdie", "Seraphine": "sthrseraphine"}
    by_inv = {next(i for k, i in who.items() if k in heading): cards for heading, cards in doc.items()}
    assert set(by_inv) == set(seated)
    for inv, cards in by_inv.items():
        # every row of a list resolves to one id with the same number of copies
        assert sorted(cards.values()) == sorted(n for _, n in seated[inv]), inv
        # every XP upgrade replaces a card the deck holds (or an upgrade bought before it)
        held = set(cards)
        for _xp, old, new, _n in decks.UPGRADES[inv]:
            assert old in held, (inv, old, new)
            held |= {new, re.sub(r" \(\d\)$", "", new)}


@pytest.mark.skipif(not LUA, reason="no lua5.2 installed")
def test_every_starter_deck_card_is_encoded(tmp_path):
    script = tmp_path / "coded.lua"
    script.write_text(CODED_LUA)
    out = subprocess.run([LUA, str(script), os.path.join(ENGINE, "lua")], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    coded = set(out.stdout.split("\n"))
    missing = sorted({n for cards in _starter_doc_cards().values() for n in cards} - coded)
    assert not missing, "starter deck cards the play engine does not encode: %s" % missing


USERDATA_LUA = r"""
local E = dofile(arg[1] .. "/tts_emu.lua")
E.srcDirs = {}
E.loadSave({ ObjectStates = {} }, "test")
local o = E.spawnData({ Name = "Card", Nickname = "probe", Transform = { posX = 0, posY = 1, posZ = 0 },
  LuaScript = "function probe(p) return { selfType = type(self), globalType = type(Global), " ..
              "listType = type({ self }), strType = type('x') } end" }, {}, "test")
E.run(0.2)
local r = o.call("probe", {})
io.write(r.selfType, " ", r.globalType, " ", r.listType, " ", r.strType)
"""


def test_no_truncating_list_copies():
    # { t and table.unpack(x) or unpack(x) } keeps only the first value (an
    # and/or expression is one value): the enemy phase once copied G.enemies
    # that way, and every enemy but the first skipped moving and attacking
    import re
    bad = re.compile(r"\{\s*table\.unpack\s+and\s+table\.unpack\(")
    hits = []
    for name in sorted(os.listdir(os.path.join(ENGINE, "lua"))):
        if name.endswith(".lua"):
            for i, line in enumerate(open(os.path.join(ENGINE, "lua", name), encoding="utf-8"), 1):
                if bad.search(line):
                    hits.append("%s:%d" % (name, i))
    assert not hits, "list copies that keep one element: %s" % hits


@pytest.mark.skipif(not LUA, reason="no lua5.2 installed")
def test_emulator_objects_are_userdata_to_scripts(tmp_path):
    # SCED tells an object from a list of objects by type() (DeckLib.parseObjectTable):
    # with objects reported as tables, SCED's encounter draw never moved the card
    script = tmp_path / "ud.lua"
    script.write_text(USERDATA_LUA)
    out = subprocess.run([LUA, str(script), os.path.join(ROOT, "tests", "sced_real")], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["userdata", "userdata", "table", "string"], out.stdout


def _real():
    if os.environ.get("SCED_REAL") == "0":
        return "SCED_REAL=0"
    if not os.path.isfile(SAVE):
        return "no SCED save at %s" % SAVE
    if not LUA:
        return "no lua5.2 installed"
    # the engine boots SCED's own scripts from the pinned checkout (run.table_for never fetches it): a fresh
    # checkout has none yet, so get it here (the real-SCED tests do the same) or skip
    sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))
    import sced_table
    src, why = sced_table.find_sced(allow_fetch=True)
    if not src:
        return "SCED source not available: %s" % why
    return None


def test_decks_are_legal():
    why = _real()
    if why:
        pytest.skip(why)
    run = _engine_run()
    import decks
    cpath, _ = run.prepare(SAVE)
    d = decks.build(SAVE, cpath)
    assert not d["problems"], d["problems"]
    for inv, deck in d["decks"].items():
        assert len(deck["cards"]) == 30, inv
        assert deck["offclass"] <= deck["limit"], inv
    for tier, party in d["tiers"].items():
        for inv, deck in party.items():
            assert sum(not c.get("permanent") for c in deck["cards"]) == 30, (tier, inv)


def test_one_short_game_per_scenario(clean_tree):
    why = _real()
    if why:
        pytest.skip(why)
    run = _engine_run()
    run.prepare(SAVE)
    jobs = [{"scenario": s, "runs": 1, "seed": 4242 + i} for i, s in enumerate(run.SCENARIOS)]
    r = run.run_batch(SAVE, None, 3, 0, 0, jobs=jobs, max_rounds=2, timeout=1800)
    assert r["coverage"] is not None, r["stderr"][-3000:]
    assert not r["coverage"]["missing"], r["coverage"]["missing"]
    assert not r["coverage"].get("player_missing"), r["coverage"]["player_missing"]
    games = r["games"]
    assert len(games) == len(run.SCENARIOS), "played %d of %d: %s" % (len(games), len(run.SCENARIOS),
                                                                     r["stderr"][-3000:] or r["stdout_tail"])
    for g in games:
        errs = g.get("lua_errors") if isinstance(g.get("lua_errors"), list) else []
        assert not errs, "%s: Lua errors: %s" % (g["scenario"], errs[:3])
        assert not g.get("engine_error"), "%s: engine error: %s" % (g["scenario"], g["engine_error"])
    assert not r["failed_checks"], json.dumps(r["failed_checks"])[:2000]


def test_finale_skip_stops_at_hour_five(clean_tree):
    # a finale begun before Hour V skips to Hour V (the engine once clicked a
    # fixed count and began the finale at Hour VI)
    why = _real()
    if why:
        pytest.skip(why)
    run = _engine_run()
    run.prepare(SAVE)
    r = run.run_batch(SAVE, "finale", 3, 1, 1000, trace=True, max_rounds=3, timeout=1800)
    games = r["games"]
    assert games, r["stderr"][-3000:] or r["stdout_tail"]
    trace = games[0].get("trace") or []
    skips = [line for line in trace if "(the finale begins)" in line and "Hourglass advances" in line]
    assert skips, "the finale did not begin with a Skip: %s" % trace[-20:]
    assert skips[-1].endswith("-> 5"), skips
