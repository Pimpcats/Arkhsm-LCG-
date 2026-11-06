"""The play engine's official-campaign benchmark (tools/play_engine/official, lua/official).

  * the Dunwich modules load on every installed Lua and leave The Still Hour's
    engine files alone (they are separate files; this checks they parse);
  * every card SCED's 1a/1b boxes hold has an effects-table entry, and one
    short game of each scenario plays without a Lua error. Both need the
    downloaded official data (.cache/official, gitignored) and the SCED
    checkout; skipped without them.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFICIAL = os.path.join(ROOT, "tools", "play_engine", "official")
LUA_DIR = os.path.join(ROOT, "tools", "play_engine", "lua", "official")
DATA = os.path.join(ROOT, ".cache", "official", "dwl_sced.json")
sys.path.insert(0, OFFICIAL)


@pytest.mark.parametrize("lua", ["lua5.2", "lua5.4"])
def test_official_modules_parse(lua, tmp_path):
    exe = shutil.which(lua)
    if not exe:
        pytest.skip("no " + lua)
    check = tmp_path / "parse.lua"
    check.write_text("assert(loadfile(arg[1]))\n")
    for name in sorted(os.listdir(LUA_DIR)):
        if name.endswith(".lua"):
            out = subprocess.run([exe, str(check), os.path.join(LUA_DIR, name)], capture_output=True, text=True)
            assert out.returncode == 0, name + ": " + out.stderr


COVERAGE_LUA = r"""
local R, T = {}, { E = {}, J = {} }
T.drawToken = function() end
local FX = dofile(arg[1] .. "/dwl_effects.lua")(R, T)
local ids = {}
for id in pairs(FX.COVERAGE) do ids[#ids + 1] = id end
table.sort(ids)
io.write(table.concat(ids, "\n"))
"""


@pytest.mark.skipif(not os.path.isfile(DATA) or not shutil.which("lua5.2"), reason="no downloaded Dunwich data or lua5.2")
def test_dwl_effects_cover_every_box_card(tmp_path):
    import dwl_data
    wanted = set()
    for ids in dwl_data.scenario_ids().values():
        wanted |= set(ids)
    script = tmp_path / "cov.lua"
    script.write_text(COVERAGE_LUA)
    out = subprocess.run(["lua5.2", str(script), LUA_DIR], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    have = set(out.stdout.split())
    assert not (wanted - have), "not encoded: %s" % sorted(wanted - have)


@pytest.mark.skipif(not os.path.isfile(DATA) or not shutil.which("lua5.2") or os.environ.get("SCED_REAL") == "0",
                    reason="no downloaded Dunwich data, lua5.2, or SCED_REAL=0")
@pytest.mark.parametrize("scenario", ["1a", "1b"])
def test_dwl_short_game(scenario):
    import dwl
    run = dwl._engine_run()
    save = run.DEFAULT_SAVE if os.path.isfile(run.DEFAULT_SAVE) else run.save_from_checkout()
    if not save:
        pytest.skip("no SCED save or checkout")
    dwl.prepare(save)
    r = dwl.run_batch(save, scenario, 2, 1, 777, extra={"maxRounds": 3}, timeout=600)
    assert r["games"], r["stderr"] + r["stdout_tail"]
    g = r["games"][0]
    assert not dwl.invalid(g), json.dumps({k: g.get(k) for k in ("engine_error", "lua_errors", "table_notes")})
    assert not r["failed_checks"], r["failed_checks"]
    cov = r["coverage"] or {}
    assert not cov.get("missing"), cov.get("missing")
