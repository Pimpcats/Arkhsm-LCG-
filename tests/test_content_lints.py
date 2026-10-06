"""Lints for the card data layers, from the 2026-10-06 content audit (docs/design/DATABASE_AUDIT.md).

The card data is built from four layers (spec, print text, the owner's overrides, the build); a value
changed in one layer can be silently ignored or contradicted by another. Each lint here is one way
that happened."""
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402
import render_placeholders as RP  # noqa: E402

CARDS = CC.load_cards(CC.campaign_paths())
SCED_TOKENS = {"resource", "doom", "damage", "horror", "clue", "universalActionAbility"}   # TokenManager


def _no_level_ids():
    """The cards official data prints with no level at all: an investigator's signature cards (the requirements
    on the back of the front card) and, here, the personal quest cards (locked and unlocked), which are
    requirements of the same kind."""
    ids = set()
    for c in CARDS.values():
        for group in c.get("signatures") or []:
            ids.update(group)
    ids |= {cid for cid, c in CARDS.items() if re.search(r"\bQuest\b", c.get("traits", ""))}
    return ids


NO_LEVEL = _no_level_ids()


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
            if cid in NO_LEVEL:
                # official signature cards carry no level (SCED's metadata has no "level" key for Roland's .38
                # Special or Daisy's Tote Bag; the FAQ says a signature card is not a level 0 card). A level 0 here
                # would let level-0 effects (Scrounge for Supplies, Hunter's Instinct, Respite, Memories of Another
                # Life, Versatile) fetch the investigator's own signature and quest cards.
                assert "level" not in md, cid
            else:
                assert "level" in md, cid                               # every other official player card has one


def test_signature_and_quest_cards_carry_no_level_and_the_rest_do():
    players = {cid for cid, c in CARDS.items() if c["type"] in ("Asset", "Event", "Skill") and not c.get("weakness")
               and not c.get("encounter")}
    assert len(NO_LEVEL & players) >= 20, sorted(NO_LEVEL & players)       # 2 signatures + quest + unlocked, x5
    for cid in sorted(NO_LEVEL & players):
        assert "level" not in CARDS[cid], cid                              # no layer of the spec sets one
    for cid in sorted(players - NO_LEVEL):
        assert CARDS[cid].get("level") is not None, cid                    # the Recollections stay level 0 cards


@pytest.mark.skipif(not RP.has_se_frames(), reason="Strange Eons frame kit not present")
def test_a_card_without_level_renders_like_a_level_zero_card(tmp_path):
    # the renderer stamps level pips only when the level is truthy, so dropping `level: 0` must not move a pixel;
    # a level 1 control proves the comparison can fail
    pt_all = json.load(open(RP.CFG.path("print_text"), encoding="utf-8"))

    def face(cid, kind, **change):
        c = {k: v for k, v in CARDS[cid].items() if k != "level"}
        c.update(change)
        dest = str(tmp_path / ("%s-%s.png" % (cid, "-".join("%s%s" % kv for kv in sorted(change.items())) or "none")))
        RP.CURRENT_CARD[0] = cid
        RP._AUDIT_RECS.clear()
        RP._CANVAS_FRAMES.clear()
        RP.s_player_card(kind, c, pt_all.get(cid, {}), dest)
        return hashlib.sha1(open(dest, "rb").read()).hexdigest()

    try:
        for cid, kind in (("sthr-lamp", "Asset"), ("sthr-igetout", "Event"), ("sthr-donebefore", "Skill")):
            assert face(cid, kind) == face(cid, kind, level=0), cid
        assert face("sthr-lamp", "Asset") != face("sthr-lamp", "Asset", level=1)
    finally:
        RP.CURRENT_CARD[0] = None
