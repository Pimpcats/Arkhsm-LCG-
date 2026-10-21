"""Every button in every panel state on SCED's real table (tests/sced_real/buttons.lua): the Control
token's panels from the Prologue to the finale, the investigator cards and each campaign log page, left
and right clicks, each from the same saved state. Skipped when SCED is not available."""
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import run as harness  # noqa: E402
import sced_table  # noqa: E402

LUAS = [lua for lua in ("lua5.4", "lua5.2") if shutil.which(lua)]


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
def test_every_button_in_every_panel_state():
    if os.environ.get("SCED_REAL") == "0":
        pytest.skip("SCED_REAL=0")
    path, why = sced_table.find_sced(allow_fetch=False)
    if not path:
        pytest.skip("real SCED not available: %s" % why)
    r = harness.run(LUAS[0], "buttons", timeout=3000)
    if r.get("skipped"):
        pytest.skip(r["skipped"])
    failed = [c for c in r["checks"] if not c["ok"]]
    assert not failed, "\n".join("%s -- %s" % (c["name"], c.get("detail")) for c in failed)
    assert r["rc"] == 0, r["stderr"][-2000:]
