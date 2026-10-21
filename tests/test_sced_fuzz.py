"""A few randomized whole-campaign playthroughs on SCED's real table (tests/sced_real/fuzz.lua): a random
party, difficulty and order of clicks, the table checked after every action. tools/fuzz_campaign.py runs
hundreds; FUZZ_SEEDS=<n> runs more here. Skipped when SCED is not available."""
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import run as harness  # noqa: E402
import sced_table  # noqa: E402

LUAS = [lua for lua in ("lua5.2", "lua5.4") if shutil.which(lua)]
SEEDS = list(range(1, 1 + int(os.environ.get("FUZZ_SEEDS", "1"))))


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
@pytest.mark.parametrize("lua", LUAS)
@pytest.mark.parametrize("seed", SEEDS)
def test_random_campaign_keeps_the_table_sound(lua, seed):
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    path, why = sced_table.find_sced(allow_fetch=False)
    if not path:
        pytest.skip("real SCED not available: %s" % why)
    r = harness.run(lua, "fuzz", extra={"seed": seed, "actions": 80})
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    failed = [c for c in r["checks"] if not c["ok"]]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)
    assert r["rc"] == 0, r["stderr"][-2000:]
