"""Every story resolution of The Still Hour on the emulated SCED table.

tests/sced_real/resolutions.lua forces each resolution's trigger (Prologue,
loop, district, finale R1/R1b/R2-R6, the epilogue's inputs) through the owner's
buttons and the campaign log, records it as the guide instructs and checks the
Control, the log and the next loop. It plays dist/'s Saved Object with the
Control and campaign-log scripts rebuilt from src/ (run.candidate_payload), so
it tests the code in this checkout, not the last publish.

  * stand-in: the minimal SCED fixture (always runs)
  * real SCED: $SCED_SAVE (the owner's own save, e.g. "Arkham SCE 4.8.0.json")
    or SCED's checkout; skipped when SCED_REAL=0 or SCED cannot be found
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import run as harness  # noqa: E402
import sced_table  # noqa: E402

LUAS = [lua for lua in ("lua5.2", "lua5.4") if shutil.which(lua)]


def _porcelain():
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout


@pytest.fixture
def candidate():
    before = _porcelain()
    tmp = tempfile.mkdtemp(prefix="sced_candidate_")
    try:
        yield harness.candidate_payload(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert _porcelain() == before, "the harness changed tracked files"


def _judge(r, label):
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    checks = r["checks"]
    print("\n%s: %d checks" % (label, len(checks)))
    failed = [c for c in checks if not c["ok"]]
    for c in failed:
        print("FAIL " + c["name"] + (("  -- " + c["detail"]) if c.get("detail") else ""))
    assert r["done"] is not None, "the harness did not finish:\n" + r["stdout"][-3000:] + r["stderr"][-3000:]
    assert len(checks) > 250, "the suite stopped early:\n" + r["stdout"][-3000:]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
@pytest.mark.parametrize("lua", LUAS)
def test_resolutions_stand_in(lua, candidate):
    _judge(harness.run(lua, "resolutions", fake=True, payload=candidate), "SCED stand-in / resolutions / " + lua)


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
def test_resolutions_real_sced(candidate):
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    if not os.environ.get("SCED_SAVE"):
        path, why = sced_table.find_sced(allow_fetch=False)
        if not path:
            pytest.skip("real SCED not available: %s" % why)
    _judge(harness.run(LUAS[0], "resolutions", payload=candidate), "real SCED / resolutions / " + LUAS[0])
