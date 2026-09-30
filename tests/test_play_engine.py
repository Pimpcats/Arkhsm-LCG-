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
    games = r["games"]
    assert len(games) == len(run.SCENARIOS), "played %d of %d: %s" % (len(games), len(run.SCENARIOS),
                                                                     r["stderr"][-3000:] or r["stdout_tail"])
    for g in games:
        errs = g.get("lua_errors") if isinstance(g.get("lua_errors"), list) else []
        assert not errs, "%s: Lua errors: %s" % (g["scenario"], errs[:3])
        assert not g.get("engine_error"), "%s: engine error: %s" % (g["scenario"], g["engine_error"])
    assert not r["failed_checks"], json.dumps(r["failed_checks"])[:2000]
