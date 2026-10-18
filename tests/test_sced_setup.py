"""The Setup panel on SCED's real table (tests/sced_real/table_setup.lua): seating investigators from
SCED's own player cards, Set Up Prologue and Set Up Loop, with the Control, campaign log and box scripts
rebuilt from src/ (run.candidate_payload). Skipped when SCED is not available (it needs SCED's All
Player Cards bag)."""
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


@pytest.fixture
def candidate():
    tmp = tempfile.mkdtemp(prefix="sced_candidate_")
    try:
        yield harness.candidate_payload(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
def test_setup_panel_lays_the_table_out(candidate):
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    if not os.environ.get("SCED_SAVE"):
        path, why = sced_table.find_sced(allow_fetch=False)
        if not path:
            pytest.skip("real SCED not available: %s" % why)
    r = harness.run(LUAS[0], "table_setup", payload=candidate)
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    checks = r["checks"]
    failed = [c for c in checks if not c["ok"]]
    assert r["done"] is not None, "the harness did not finish:\n" + r["stdout"][-3000:] + r["stderr"][-3000:]
    assert len(checks) >= 10, "the suite stopped early:\n" + r["stdout"][-3000:]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)
