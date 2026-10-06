"""The scenario boxes' Place and Recall on the emulated SCED table.

tests/sced_real/place_state.lua presses the owner's buttons (the boxes' Place and Recall, the Control
token's Clear Board and Sync Board) and checks what a box that lays its objects out again every loop,
with the GUIDs they had before, must get right:

  * a location spawns its clues in loop 2 as in loop 1 (SCED's Token Spawn Tracker forgets the GUIDs
    a Place lays out, before anything comes out of the box)
  * the CLOSED label is read off the card: a new card gets it, Sync Board repairs a lost one
  * Recall and Clear Board stop a Place that is still running (no half layout, no wrong refusal)
  * Recall takes the tokens resting on the cards it removes, and nothing else
  * a save taken during a Place leaves no second, Place-able box behind
  * a box that is out of context is laid out and the chat says so, once
  * a Place is refused while another box's cards (or an older build's) lie where it lays out

It plays dist/'s Saved Object with the Control, campaign log and box scripts rebuilt from src/
(run.candidate_payload), so it tests the code in this checkout, not the last publish.

  * stand-in: the minimal SCED fixture (always runs)
  * real SCED: $SCED_SAVE (the owner's own save) or SCED's checkout; skipped when SCED_REAL=0 or
    SCED cannot be found
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
SUITE = "place_state"


def _porcelain():
    # what the harness reads (dist/) must come out as it went in; the rest of the tree is other
    # people's work in progress, and the payload is built in a temporary folder
    return subprocess.run(["git", "status", "--porcelain", "--", "dist"], cwd=ROOT, capture_output=True,
                          text=True).stdout


@pytest.fixture
def candidate():
    before = _porcelain()
    tmp = tempfile.mkdtemp(prefix="sced_candidate_")
    try:
        yield harness.candidate_payload(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert _porcelain() == before, "the harness changed files under dist/"


def _judge(r, label):
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    checks = r["checks"]
    print("\n%s: %d checks" % (label, len(checks)))
    failed = [c for c in checks if not c["ok"]]
    for c in failed:
        print("FAIL " + c["name"] + (("  -- " + c["detail"]) if c.get("detail") else ""))
    assert r["done"] is not None, "the harness did not finish:\n" + r["stdout"][-3000:] + r["stderr"][-3000:]
    assert len(checks) > 60, "the suite stopped early:\n" + r["stdout"][-3000:]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
@pytest.mark.parametrize("lua", LUAS)
def test_place_state_stand_in(lua, candidate):
    _judge(harness.run(lua, SUITE, fake=True, payload=candidate), "SCED stand-in / %s / %s" % (SUITE, lua))


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
def test_place_state_real_sced(candidate):
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    if not os.environ.get("SCED_SAVE"):
        path, why = sced_table.find_sced(allow_fetch=False)
        if not path:
            pytest.skip("real SCED not available: %s" % why)
    _judge(harness.run(LUAS[0], SUITE, payload=candidate), "real SCED / %s / %s" % (SUITE, LUAS[0]))
