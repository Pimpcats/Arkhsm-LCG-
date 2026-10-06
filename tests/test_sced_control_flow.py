"""The Control token's flow on SCED's real table (tests/sced_real/control_flow.lua).

What needs the real table's objects: SCED's investigator counter and chaos bag, the campaign log with its
pages and memo, the campaign box's Place, and a scenario box laid out mid-loop. It plays the Control,
campaign log and box scripts rebuilt from src/ (run.candidate_payload) on SCED's real table; skipped when
SCED is not available. The stub-table half is tests/test_control_flow.py."""
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
def test_control_flow_on_the_real_sced_table(candidate):
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    if not os.environ.get("SCED_SAVE"):
        path, why = sced_table.find_sced(allow_fetch=False)
        if not path:
            pytest.skip("real SCED not available: %s" % why)
    r = harness.run(LUAS[0], "control_flow", payload=candidate)
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    checks = r["checks"]
    failed = [c for c in checks if not c["ok"]]
    assert r["done"] is not None, "the harness did not finish:\n" + r["stdout"][-3000:] + r["stderr"][-3000:]
    assert len(checks) >= 30, "the suite stopped early:\n" + r["stdout"][-3000:]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)
