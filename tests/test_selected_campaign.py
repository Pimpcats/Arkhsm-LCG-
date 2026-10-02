"""When the shell selects another campaign (`export CAMPAIGN=<id>`, the
new-campaign runbook), check that campaign's scenarios read-only alongside
The Still Hour's suite: the readiness audit reports 0 errors for every
scenario. Skipped when The Still Hour is selected (its own tests cover it)."""
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECTED = os.environ.get("SELECTED_CAMPAIGN") or "still_hour"


@pytest.mark.skipif(SELECTED == "still_hour", reason="The Still Hour is covered by the rest of the suite")
def test_selected_campaign_scenarios_have_no_errors():
    assert os.path.exists(os.path.join(ROOT, "campaigns", SELECTED, "build.json")), \
        "CAMPAIGN={} has no campaigns/{}/build.json".format(SELECTED, SELECTED)
    r = subprocess.run([sys.executable, "pipeline/scenario_content.py", "--campaign", SELECTED],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    rows = re.findall(r"^(\S+)\s+(LOCKED|unlocked)\s+(\d+) error", r.stdout, re.M)
    assert rows, r.stdout[-3000:]
    assert all(int(n) == 0 for _, _, n in rows), r.stdout[-3000:]
