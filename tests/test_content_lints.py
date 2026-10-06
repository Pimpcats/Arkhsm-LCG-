"""Lints for the card data layers, from the 2026-10-06 content audit (docs/design/DATABASE_AUDIT.md).

The card data is built from four layers (spec, print text, the owner's overrides, the build); a value
changed in one layer can be silently ignored or contradicted by another. Each lint here is one way
that happened."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402
import render_placeholders as RP  # noqa: E402

CARDS = CC.load_cards(CC.campaign_paths())
SCED_TOKENS = {"resource", "doom", "damage", "horror", "clue", "universalActionAbility"}   # TokenManager


def test_every_override_key_is_consumed_by_the_renderer():
    # an override key no renderer reads is silently ignored (back_tokens was: the Hard / Expert side of the
    # scenario reference card kept its stale text)
    known = set(RP.OV_SPEC_KEYS + RP.OV_PT_KEYS + RP.OV_LOC_KEYS + RP.OV_FLAG_KEYS + RP.OV_COUNT_KEYS
                + RP.OV_PROP_KEYS) | {"tokens", "back_tokens"}
    ov = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json"), encoding="utf-8"))
    unused = {(cid, k) for cid, fields in ov.items() for k in fields if k not in known}
    assert not unused, sorted(unused)[:10]


def test_both_sides_of_the_scenario_reference_come_from_the_overrides():
    ov = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json"), encoding="utf-8"))
    ref = CARDS["sthr-scn-stillhour"]
    for side in ("tokens", "back_tokens"):
        assert ref[side] == ov["sthr-scn-stillhour"][side], side
    md = json.loads(B.build_gmnotes(CC.normalize(ref)))
    back = md["tokens"]["back"]
    assert back["Elder Thing"]["description"] == [t["text"] for t in ov["sthr-scn-stillhour"]["back_tokens"]
                                                  if t["token"] == "elderthing"][0]


def test_printed_uses_match_the_uses_in_the_metadata():
    # SCED spawns the tokens from the metadata; the card prints the number the player reads
    pt = json.load(open(os.path.join(ROOT, "pipeline", "stillhour_print_text.json"), encoding="utf-8"))
    ov = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json"), encoding="utf-8"))
    checked = 0
    for cid, c in CARDS.items():
        if not c.get("uses"):
            continue
        text = (ov.get(cid, {}).get("text") or pt.get(cid, {}).get("text") or "")
        m = re.search(r"Uses \((\d+)\s", text)
        if not m:
            continue
        checked += 1
        assert int(m.group(1)) == c["uses"][0]["count"], (cid, m.group(0), c["uses"])
    assert checked >= 2


def test_metadata_follows_the_sced_data_model():
    for cid, c in CARDS.items():
        md = json.loads(B.build_gmnotes(CC.normalize(c)))
        if "cost" in md:
            assert isinstance(md["cost"], int) and not isinstance(md["cost"], bool), (cid, md["cost"])
        for use in md.get("uses", []):
            assert use["token"] in SCED_TOKENS, (cid, use)             # TokenManager errors on any other
        if c["type"] in ("Asset", "Event", "Skill") and not c.get("weakness") and not c.get("encounter"):
            assert "level" in md, cid                                   # every official player card has one
