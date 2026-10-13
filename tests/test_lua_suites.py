"""The Still Hour's Lua suites, run from pytest so the full suite catches them.

pipeline/lua_smoketest.lua (the rules modules in src/), pipeline/verify_bundle.lua
(the published dist/stillhour_bundle.lua on a stubbed vanilla table) and
pipeline/verify_control.lua with the in-bundle runStillHourTests entry were run
by hand only; a rules change that broke one of them could pass pytest unseen.
Each runs on every installed Lua (5.2 and 5.4) in a few seconds.
"""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUAS = [lua for lua in ("lua5.2", "lua5.4") if shutil.which(lua)]
SUITES = {
    "smoketest": ["pipeline/lua_smoketest.lua"],
    "bundle": ["pipeline/verify_bundle.lua"],
    "control": ["pipeline/verify_control.lua", "dist/stillhour_bundle.lua", "runStillHourTests"],
}


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
@pytest.mark.parametrize("lua", LUAS or ["lua"])
@pytest.mark.parametrize("suite", sorted(SUITES))
def test_lua_suite(lua, suite):
    res = subprocess.run([lua] + SUITES[suite], cwd=ROOT, capture_output=True, text=True, timeout=300)
    out = res.stdout + res.stderr
    failed = [line.strip() for line in out.splitlines() if line.lstrip().startswith("FAIL")]
    assert res.returncode == 0 and not failed, "\n".join(failed) or out[-2000:]
