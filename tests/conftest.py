"""The suite tests The Still Hour (the reference campaign) and the replication
kit, whatever campaign the shell has selected.

The new-campaign runbook ends with `export CAMPAIGN=<id>` and then
`python3 -m pytest -q tests`. Pipeline modules read $CAMPAIGN when they are
imported and every build script a test starts inherits it, so the Still Hour
tests pin it to still_hour here, before any test module is imported. The kit
test (test_new_campaign.py) sets its own CAMPAIGN for the campaign it
scaffolds. The campaign the shell selected is kept in $SELECTED_CAMPAIGN for
tests/test_selected_campaign.py, which audits that campaign read-only.
"""
import os

os.environ.setdefault("SELECTED_CAMPAIGN", os.environ.get("CAMPAIGN") or "still_hour")
os.environ["CAMPAIGN"] = "still_hour"
