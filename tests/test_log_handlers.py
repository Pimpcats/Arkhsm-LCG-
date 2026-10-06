"""The campaign log's buttons and inputs call global functions that exist in its script.

Tabletop Simulator finds a click_function / input_function by name in the object's script. The log first made
these at run time with self.setVar(name, function): the hover text appeared and a click did nothing. The
generated script now defines one global function per field (the way the Control token's buttons are made)."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import campaign_log as L  # noqa: E402


def test_every_clickable_field_has_a_global_handler():
    for page in range(1, len(L.layout()) + 1):
        script = L.lua_script(page)
        fields = L.layout()[page - 1]["fields"]
        for i, f in enumerate(fields, 1):
            has = re.search(r"^function sthrLog_%d\(" % i, script, re.M) is not None
            assert has == (f["t"] in ("cb", "ct", "tx")), (page, i, f["k"], f["t"])
        assert "self.setVar(" not in script, "the log must not make its handlers with setVar"


def test_inputs_and_clicks_reach_the_dispatchers():
    script = L.lua_script(1)
    assert re.search(r"^function sthrLog_\d+\(_, _, value, selected\) fieldInput\(\d+, value, selected\) end", script, re.M)
    assert re.search(r"^function sthrLog_\d+\(_, _, alt\) fieldClick\(\d+, alt\) end", script, re.M)
