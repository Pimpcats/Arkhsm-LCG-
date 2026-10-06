"""tools/library/synergy_scan.py: the card x investigator synergy scan (designer tooling).

All fast (a few seconds, no network). Three layers:

  * synthetic data: the markdown parser, the deckbuilding-option vocabulary ("other" options
    only take cards that fall in no other category, no-level cards are never legal, dual-class
    cards count as either class), the feature regexes on card texts quoted from the printed
    cards (each regression the first hand review found), the hooks, the table writer and its
    determinism, and the starter-deck check including a negative control (a check that cannot
    fail proves nothing);
  * the five fronts and backs as they are built (tracked files, always present): every back
    must parse into the options PORTABLE_INVESTIGATORS.md describes;
  * the real library (library/ and the SCED save are not committed; skipped when absent):
    pool sizes, pool invariants and the starter decks of docs/STARTER_DECKS.md.
"""
import csv
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "library"))

import synergy_quant as Q  # noqa: E402
import synergy_scan as S  # noqa: E402

HAVE_LIBRARY = os.path.isdir(os.path.join(ROOT, "library", "cards", "player"))
needs_library = pytest.mark.skipif(not HAVE_LIBRARY, reason="library/ is not built (tools/library/build_library.py)")


# --------------------------------------------------------------------------- helpers
def card(name, cls, level, typ, text="", **kw):
    """A library-shaped card for synthetic pools."""
    c = {"name": name, "subname": "", "unique": False, "type": typ, "code": kw.pop("code", name.lower().replace(" ", "-")),
         "pack": "synthetic", "level": level, "cost": kw.pop("cost", 1), "slot": "", "icons": {}, "traits": kw.pop("traits", []),
         "text": text, "classes": kw.pop("classes", [cls]), "weakness": False, "basic_weakness": False, "exceptional": False,
         "myriad": False, "permanent": False, "exile": False, "restrictions": "", "bonded_to": "", "customizable": False,
         "deck_limit": 2, "limit_per": None, "taboo": None, "sced_ids": [], "file": "synthetic"}
    c.update(kw)
    return c


def flags(text, typ="event", **kw):
    return S.tag_card(card("x", "neutral", 0, typ, text, **kw))


class StubDB(object):
    """What Scan needs from OfficialDB, without the library."""

    def __init__(self, cards):
        self.cards = cards
        self.taboo = {}
        self.taboo_title = "stub"
        self.sced = []
        self.sced_unmapped = []


@pytest.fixture(scope="module")
def camp():
    return S.load_campaign_cards()


@pytest.fixture(scope="module")
def synthetic_scan(camp):
    cards = [
        card("Guardian Basic", "guardian", 0, "asset", "Soak.", code="g0"),
        card("Guardian Five", "guardian", 5, "asset", "Heavy.", code="g5"),
        card("Survivor Zero", "survivor", 0, "event", "Fast. Gain 2 resources.", code="s0"),
        card("Survivor Three", "survivor", 3, "event", "Fast. Gain 3 resources.", code="s3"),
        card("Neutral Skill", "neutral", 0, "skill", "Draw 1 card.", code="n0"),
        card("Rogue Event", "rogue", 1, "event", "Fast. Gain 1 resource.", code="r1"),
        card("Dual Seeker Survivor", "seeker", 2, "asset", "Dual.", code="d2", classes=["seeker", "survivor"]),
        card("Signature Without Level", "guardian", None, "asset", "Signature.", code="sig"),
        card("Weakness", "neutral", 0, "treachery", "Revelation.", code="w", weakness=True),
        card("Sorcerer Only", "neutral", 3, "asset", "Sorcerer deck only.", code="so", restrictions="trait:dreamer, trait:sorcerer"),
        card("Somebody Else's Signature", "guardian", 0, "asset", "Signature.", code="sig2", restrictions="investigator:01001"),
    ]
    return S.Scan(db=StubDB(cards), camp=camp, fan=[])


# --------------------------------------------------------------------------- parser
MD = """# Level 0

### Working a Hunch
*Event · class seeker · level 0 · cost 2 · copies 2 · icons [int] [int]* · code 01037 · Core Set
**Insight.**
Fast. Play only during your turn. Discover 1 clue at your location.
*Flavor:* A feeling.

### ✷ Roland's .38 Special — Cover
*Asset · class guardian · level 0 · cost 3 · slot Hand · copies 1 · icons [wild]* · code 01006 · Core Set
**Item. Weapon. Firearm.**
*exceptional: 1*
*restrictions: investigator:01001*
Uses (4 ammo). [action] Spend 1 ammo: **Fight.**
"""


def test_parse_card_blocks():
    cards = S.parse_cards_text(MD, "player/seeker/level_0.md")
    assert [c["name"] for c in cards] == ["Working a Hunch", "Roland's .38 Special"]
    a, b = cards
    assert (a["type"], a["class"], a["level"], a["cost"], a["code"]) == ("event", "seeker", 0, 2, "01037")
    assert a["icons"]["int"] == 2 and a["icons"]["wild"] == 0
    assert a["traits"] == ["insight"]
    assert "Discover 1 clue" in a["text"] and "Flavor" not in a["text"]
    assert b["unique"] and b["subname"] == "Cover" and b["slot"] == "Hand"
    assert b["traits"] == ["item", "weapon", "firearm"]
    assert b["attrs"]["exceptional"] == "1" and b["attrs"]["restrictions"].startswith("investigator")


def test_parse_ignores_non_card_blocks():
    assert S.parse_cards_text("# Title only\n\nsome prose\n") == []
    assert S.parse_card_block("### Broken\nno meta line") is None


def test_norm_name_drops_taboo_and_punctuation():
    assert S.norm_name("\"I've had worse...\" (taboo)") == S.norm_name("I've had worse")
    assert S.norm_name("Dodge — Eagle") == "dodge"      # the library prints 'Name — Subtitle'
    assert S.norm_name("Dodge (2)") == "dodge"


# --------------------------------------------------------------------------- the five backs as built
EXPECTED_BACKS = {
    # investigator: (own class, free class options, limited option: (limit, classes, min level, max level))
    "elias": ("guardian", {"guardian", "neutral"}, (5, {"survivor"}, 0, 2)),
    "ayako": ("seeker", {"seeker", "neutral"}, (5, {"mystic"}, 0, 2)),
    "cass": ("rogue", {"rogue", "neutral"}, (5, {"guardian", "seeker", "mystic", "survivor"}, 0, 0)),
    "birdie": ("survivor", {"survivor", "neutral"}, (5, {"guardian", "mystic", "rogue", "seeker"}, 0, 1)),
    "seraphine": ("mystic", {"mystic", "neutral"}, (5, {"seeker"}, 0, 2)),
}


@pytest.mark.parametrize("key", S.INVESTIGATORS)
def test_back_text_parses_to_the_designed_options(camp, key):
    own, free, (limit, classes, lo, hi) = EXPECTED_BACKS[key]
    c = camp[S.INV_ID[key]]
    assert c["class"].lower() == own
    p = S.parse_back_text(c["back_text"], own)
    assert p["deck_size"] == 30
    unlimited = [o for o in p["options"] if not o.get("limit") and o.get("bucket") != "recollection"]
    limited = [o for o in p["options"] if o.get("limit")]
    recollection = [o for o in p["options"] if o.get("bucket") == "recollection"]
    assert {f for o in unlimited for f in o["faction"]} == free
    assert all(o["level"] == {"min": 0, "max": 5} for o in unlimited)
    assert len(limited) == 1
    lim = limited[0]
    assert lim["limit"] == limit and set(lim["faction"]) == classes
    assert (lim["level"]["min"], lim["level"]["max"]) == (lo, hi)
    assert len(recollection) == 1 and recollection[0]["trait"] == ["recollection"]
    # four signature cards (counting the quest card) are named as requirements, and nothing else
    assert len(p["requirements"]) == 4
    assert all(not r.lower().startswith("1 random") for r in p["requirements"])


def test_requirements_resolve_to_campaign_cards(camp):
    names = {c["name"] for c in camp.values()}
    for key in S.INVESTIGATORS:
        p = S.parse_back_text(camp[S.INV_ID[key]]["back_text"], camp[S.INV_ID[key]]["class"].lower())
        for r in p["requirements"]:
            assert r in names, "%s: %s is not a campaign card" % (key, r)


# --------------------------------------------------------------------------- pools
OPTS = S.parse_back_text(
    "Deck Size: 30.\nDeckbuilding Options: Guardian cards level 0-5, Neutral cards level 0-5, "
    "up to 5 Survivor cards level 0-2, any number of Recollection cards.\n"
    "Deckbuilding Requirements (do not count toward deck size): X, 1 random basic weakness.", "guardian")["options"]


def test_classify_buckets_and_limits():
    assert S.classify(card("a", "guardian", 5, "asset"), OPTS) == ("main", None)
    assert S.classify(card("a", "neutral", 3, "asset"), OPTS) == ("neutral", None)
    assert S.classify(card("a", "survivor", 2, "asset"), OPTS) == ("secondary", 5)
    assert S.classify(card("a", "survivor", 3, "asset"), OPTS) is None          # above the secondary range
    assert S.classify(card("a", "rogue", 0, "asset"), OPTS) is None             # not an option at all
    assert S.classify(card("a", "guardian", None, "asset"), OPTS) is None       # no level: a signature, never legal
    assert S.classify(card("a", "neutral", 0, "asset", traits=["recollection"]), OPTS) == ("neutral", None)


def test_dual_class_card_takes_the_unlimited_option():
    # a Guardian|Survivor card counts as a Guardian card: it must not use one of the five Survivor slots
    dual = card("d", "guardian", 1, "asset", classes=["guardian", "survivor"])
    assert S.classify(dual, OPTS) == ("main", None)
    # a Seeker|Survivor card has no unlimited option, so it does use the limited one
    dual2 = card("d2", "seeker", 1, "asset", classes=["seeker", "survivor"])
    assert S.classify(dual2, OPTS) == ("secondary", 5)


def test_deck_legal_card_filters():
    assert S.deck_legal_card(card("a", "guardian", 0, "asset"))
    assert not S.deck_legal_card(card("a", "guardian", None, "asset"))
    assert not S.deck_legal_card(card("a", "neutral", 0, "treachery"))
    assert not S.deck_legal_card(card("a", "neutral", 0, "asset", weakness=True))
    assert not S.deck_legal_card(card("a", "guardian", 0, "asset", restrictions="investigator:01001"))
    assert not S.deck_legal_card(card("a", "guardian", 0, "asset", bonded_to="X"))
    # a 'Sorcerer deck only' card stays a candidate: whether an investigator may take it depends on traits
    assert S.deck_legal_card(card("a", "neutral", 3, "asset", restrictions="trait:sorcerer"))


def test_restriction_allows_by_trait():
    c = card("a", "neutral", 3, "asset", restrictions="trait:dreamer, trait:sorcerer")
    assert S.restriction_allows(c, {"sorcerer", "cursed"}, "mystic")           # any one listed trait is enough
    assert not S.restriction_allows(c, {"believer", "warden"}, "guardian")
    assert S.restriction_allows(card("a", "neutral", 0, "asset"), set(), "rogue")
    assert not S.restriction_allows(card("a", "guardian", 0, "asset", restrictions="investigator:01001"), {"x"}, "guardian")
    f = card("a", "neutral", 0, "asset", restrictions="faction:rogue")
    assert S.restriction_allows(f, set(), "rogue") and not S.restriction_allows(f, set(), "seeker")


def test_synthetic_pools(synthetic_scan):
    names = lambda key: sorted(c["name"] for c, _, _ in synthetic_scan.pool(key))  # noqa: E731
    elias = names("elias")
    assert "Guardian Five" in elias and "Neutral Skill" in elias and "Survivor Zero" in elias
    assert "Survivor Three" not in elias and "Rogue Event" not in elias
    assert "Signature Without Level" not in elias and "Weakness" not in elias
    assert "Somebody Else's Signature" not in elias
    assert "Sorcerer Only" not in elias and "Sorcerer Only" in names("seraphine")   # Seraphine is a Sorcerer, Elias is not
    assert "Dual Seeker Survivor" in elias                                         # a Survivor card at level 2
    birdie = names("birdie")
    assert "Survivor Three" in birdie and "Rogue Event" in birdie                  # level 1 other class
    assert "Guardian Five" not in birdie and "Guardian Basic" in birdie
    cass = names("cass")
    assert "Guardian Basic" in cass and "Guardian Five" not in cass and "Survivor Zero" in cass
    assert "Rogue Event" in cass                                                   # her own class, any level


# --------------------------------------------------------------------------- features (texts quoted from the printed cards)
def test_play_conditions_are_not_effects():
    ward = "Fast. Play when you draw a non-weakness treachery card. Cancel that card's revelation effect. Then, take 1 horror."
    f = flags(ward)
    assert "draw_cards" not in f and "cancel_revelation" in f and "fast_event" in f
    assert "draw_cards" in flags("Gain 2 resources and draw 1 card.")


def test_extra_action_is_not_a_cost():
    assert "extra_action" not in flags("[action]: **Fight.** If you succeed, you may spend 1 additional action to deal +1 damage.", "asset")
    assert "extra_action" in flags("[free] During your turn: gain 1 additional action this turn.", "asset")
    assert "action_refund" in flags("Fast. Play immediately after an investigator finishes resolving an action. Undo that action.")


def test_damage_costs_are_split_by_who_pays():
    f = flags("[fast] Spend 1 supply, exhaust Smoking Pipe, and take 1 damage: Heal 1 horror.", "asset")
    assert "take_damage_cost" in f and "heal_horror" in f
    f2 = flags("[fast] Exhaust Agency Backup and deal 1 damage to it: Deal 1 damage to an enemy at your location.", "asset")
    assert "asset_damage_cost" in f2 and "take_damage_cost" not in f2


def test_token_features():
    assert "token_reroll" in flags("After revealing a chaos token for this skill test, you may take 1 damage to cancel that chaos token, return it to the chaos bag, and reveal a new one.", "skill")
    assert "token_cancel" in flags("Cancel that chaos token. (Do not reveal a new chaos token to replace it.)")
    assert "token_reveal_extra" in flags("[reaction] When you would reveal a chaos token, exhaust Olive: Reveal 3 chaos tokens instead of 1. Choose 2 to resolve.", "asset")
    assert "token_seal" in flags("Seal ([skull], [cultist], [tablet], or [elder_thing]).", "asset")


def test_fail_features():
    assert "if_fail" in flags("Fast. Play after you fail a skill test by 2 or less while investigating. Discover 2 clues at your location.")
    assert "fail_trigger" in flags("Fast. Play after you fail a skill test by 2 or less while investigating. Discover 2 clues at your location.")
    assert "discover_clue" in flags("Fast. Play only during your turn. Discover 1 clue at your location.")


def test_limits_and_exile_features():
    assert "limit_round" in flags("[reaction] After you succeed: gain 1 resource. (Limit once per round.)", "asset")
    assert "limit_game" in flags("Test [wil] (3). Max once per game.")
    assert "remove_from_game" in flags("Fast. Play when you would be defeated. Remove I Get Out from the game.")


def test_campaign_flags():
    assert "xp_effect" in flags("Permanent. When you purchase this card, gain 10 experience.", "asset")
    assert "trauma_effect" in flags("You are defeated and suffer 1 mental trauma.")
    assert "campaign_log_ref" in flags("Researched. Uses (3 charges).", "asset")
    assert "doom_on_card" in flags("[action] Exhaust: place 1 doom on it to get +1 skill value.", "asset")


def test_spell_engine_and_traits():
    f = flags("[reaction] After you activate an [action] ability on a Spell or Ritual asset, exhaust Sign Magick: Activate an [action] ability on a different Spell or Ritual asset you control (without paying its [action] cost).", "asset", traits=["spell"])
    assert "spell_engine" in f and "trait_spell" in f and "type_asset" in f


# --------------------------------------------------------------------------- hooks
def test_birdie_hooks():
    free = card("Hunch", "seeker", 0, "event", "Fast. Play only during your turn. Discover 1 clue at your location.")
    assert "B.free_engine_event" in S.hooks_for("birdie", free, S.tag_card(free))
    dead = card("Flux", "mystic", 0, "event", "Shuffle your discard pile into your deck. Remove Quantum Flux from the game.")
    h = S.hooks_for("birdie", dead, S.tag_card(dead))
    assert "B.dead_target" in h and "B.free_engine_event" not in h
    asset = card("Gun", "guardian", 0, "asset", "Fast. Gain 1 resource.")
    assert "B.event_target" not in S.hooks_for("birdie", asset, S.tag_card(asset))


def test_elias_and_seraphine_hooks():
    dodge = card("Dodge", "guardian", 0, "event", "Fast. Play when an enemy attacks an investigator at your location. Cancel that attack.")
    assert "E.mitigation" in S.hooks_for("elias", dodge, S.tag_card(dodge))
    ally = card("Beat Cop", "guardian", 0, "asset", "Ally. You get +1 combat.", traits=["ally"], sanity=2, health=2)
    h = S.hooks_for("seraphine", ally, S.tag_card(ally))
    assert "S.ally_soak_irrelevant" in h and "S.horror_offset" not in h            # soaking never pays her direct horror
    clarity = card("Clarity", "mystic", 0, "asset", "Uses (3 charges). [action] Spend 1 charge: Heal 1 horror from an investigator at your location.", traits=["spell"])
    assert "S.horror_offset" in S.hooks_for("seraphine", clarity, S.tag_card(clarity))


def test_cass_hooks():
    c = card("Heavy Furs", "neutral", 0, "asset", "[reaction] After you reveal a non-[auto_fail] symbol on a chaos token during a skill test you are perfoming, deal 1 damage to Heavy Furs: Cancel that chaos token and return it to the bag. Reveal a new chaos token.")
    h = S.hooks_for("cass", c, S.tag_card(c))
    assert "C.token_cancel" in h and "C.symbol_reveal" in h


# --------------------------------------------------------------------------- tables
def test_rows_and_tables(synthetic_scan, tmp_path):
    n, nf = S.write_tables(synthetic_scan, str(tmp_path))
    assert n > 0 and nf == 0
    rows = list(csv.DictReader(open(str(tmp_path / "card_x_investigator.csv"), encoding="utf-8")))
    assert len(rows) == n
    assert list(rows[0].keys()) == S.CSV_COLUMNS
    assert {r["investigator"] for r in rows} == set(S.INVESTIGATORS)
    lines = open(str(tmp_path / "card_x_investigator.jsonl"), encoding="utf-8").read().splitlines()
    assert len(lines) == n and json.loads(lines[0])["investigator"] in S.INVESTIGATORS
    summary = json.load(open(str(tmp_path / "summary.json"), encoding="utf-8"))
    assert set(summary["investigators"]) == set(S.INVESTIGATORS)
    # Recollections are legal for all five investigators and are the only 'campaign' rows
    for key in S.INVESTIGATORS:
        assert summary["investigators"][key]["recollections_legal"] == 10
    assert {r["source"] for r in rows} == {"official", "campaign"}


def test_tables_are_deterministic(synthetic_scan, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    S.write_tables(synthetic_scan, str(a))
    S.write_shortlists(synthetic_scan, str(a))
    S.write_tables(synthetic_scan, str(b))
    S.write_shortlists(synthetic_scan, str(b))
    for name in sorted(os.listdir(str(a))):
        assert open(str(a / name), "rb").read() == open(str(b / name), "rb").read(), name


# --------------------------------------------------------------------------- starter decks
STARTER = """## Elias Warde (Guardian)

| Qty | Card | Type | Class | Cost | Pack |
|---|---|---|---|---|---|
| 2 | Guardian Basic | Asset | Guardian | 1 | Synthetic |
| 2 | Survivor Zero | Event | Survivor | 0 | Synthetic |
| 2 | Survivor Three | Event | Survivor | 0 | Synthetic |
| 3 | Neutral Skill | Skill | Neutral | - | Synthetic |
"""


def test_starter_check_has_a_negative_control(synthetic_scan):
    problems = S.check_starter_decks(synthetic_scan, STARTER)
    text = " | ".join(problems)
    assert "Survivor Three is not a legal level 0 card" in text      # level 3 card in a starter list
    assert "3 copies of Neutral Skill" in text                       # over the copy limit
    assert "9 cards, deck size 30" in text                           # wrong size
    ok = "## Elias Warde (Guardian)\n\n| Qty | Card | Type | Class | Cost | Pack |\n|---|---|---|---|---|---|\n| 2 | Guardian Basic | Asset | Guardian | 1 | S |\n"
    assert any("deck size" in p for p in S.check_starter_decks(synthetic_scan, ok))   # 2 cards is not 30


def test_parse_starter_decks():
    d = S.parse_starter_decks(STARTER)
    assert list(d) == ["elias"] and d["elias"][0] == (2, "Guardian Basic", "Guardian")


# --------------------------------------------------------------------------- the real library
@pytest.fixture(scope="module")
def real_scan():
    return S.Scan()


@needs_library
def test_real_pools_are_sane(real_scan):
    s = real_scan.summary()
    assert s["official_deck_legal_base"] > 1000
    inv = s["investigators"]
    # same shape of options: Ayako and Seraphine share the Seeker/Mystic split, so their pools are about equal
    assert abs(inv["ayako"]["official_legal"] - inv["seraphine"]["official_legal"]) < 60
    assert inv["birdie"]["official_legal"] > inv["cass"]["official_legal"] > inv["elias"]["official_legal"]
    for key in S.INVESTIGATORS:
        assert inv[key]["recollections_legal"] == 10
        assert inv[key]["by_bucket"]["neutral"] > 50
        assert inv[key]["official_legal"] == sum(inv[key]["by_bucket"].values())


@needs_library
def test_real_pool_invariants(real_scan):
    for key in S.INVESTIGATORS:
        opts = real_scan.inv[key]["options"]
        for c, bucket, limit in real_scan.pool(key):
            assert c["level"] is not None and not c["weakness"] and not c["bonded_to"]
            assert S.restriction_allows(c, real_scan.inv[key]["traits"], real_scan.inv[key]["class"])
            assert S.classify(c, opts) == (bucket, limit)
            if bucket == "secondary":
                assert limit == 5


@needs_library
def test_investigator_traits_open_trait_restricted_cards(real_scan):
    """The traits printed on a front are deckbuilding: 'Sorcerer deck only' cards are legal for Seraphine."""
    inv = real_scan.summary()["investigators"]
    assert any(n.startswith("Captivating Performance") for n in inv["seraphine"]["trait_restricted_legal"])
    assert any(n.startswith("Sound Support") for n in inv["elias"]["trait_restricted_legal"])
    assert any(n.startswith("Name Your Price") for n in inv["cass"]["trait_restricted_legal"])
    assert any(n.startswith("True Awakening") for n in inv["birdie"]["trait_restricted_legal"])
    assert any(n.startswith("Inquisitive") for n in inv["ayako"]["trait_restricted_legal"])
    assert not any(n.startswith("Captivating Performance") for n in inv["elias"]["trait_restricted_legal"])


@needs_library
def test_no_investigator_can_take_its_own_signature_or_weakness_cards(real_scan, camp):
    sig = {c["name"] for c in camp.values() if c.get("class") and c["type"] != "Investigator"}
    for key in S.INVESTIGATORS:
        officials = {c["name"] for c, _, _ in real_scan.pool(key)}
        assert not (officials & {"The Eighth Grave", "Untranslatable", "The Debt of Hours", "Nobody Believes Her"})
        assert sig  # the campaign names exist


@needs_library
def test_starter_decks_are_legal(real_scan):
    text = open(os.path.join(ROOT, "docs", "STARTER_DECKS.md"), encoding="utf-8").read()
    assert S.check_starter_decks(real_scan, text) == []
    decks = S.parse_starter_decks(text)
    assert set(decks) == set(S.INVESTIGATORS)                        # all five investigators have a starter list
    assert all(sum(n for n, _, _ in d) == 30 for d in decks.values())


@needs_library
def test_real_known_cards_are_flagged(real_scan):
    by = {(r["name"], r["level"]): r for r in real_scan.rows("birdie")}
    hunch = by[("Working a Hunch", 0)]
    assert "B.free_engine_event" in hunch["hooks"] and "discover_clue" in hunch["flags"]
    flux = by[("Quantum Flux", 0)]
    assert "B.dead_target" in flux["hooks"]
    ward = {(r["name"], r["level"]): r for r in real_scan.rows("seraphine")}[("Ward of Protection", 0)]
    assert "draw_cards" not in ward["flags"]


# --------------------------------------------------------------------------- synergy_quant.py (exact or seeded numbers)
def test_quant_token_arithmetic_is_exact():
    assert len(Q.BAG) == 17
    assert Q.p_success(5, 3) == pytest.approx(12 / 17)          # skill 5 vs 3 with the Standard bag: all but -4, skull x2, ... fails
    assert Q.p_success(1, 4) == 0.0
    assert Q.p_any(0.5, 3) == pytest.approx(0.875)


def test_quant_investigator_tables_are_stable():
    assert Q.birdie()["p_fail=0.45"]["returns_per_round_if_all_spent"] == 0.63
    c = Q.cass()
    assert c["total_resources_per_round_range"][0] < c["total_resources_per_round_range"][1] < 1.2
    # the same seed gives the same answer (Monte Carlo is seeded)
    assert Q.elias(loops=200) == Q.elias(loops=200)
    assert Q.seraphine(loops=200) == Q.seraphine(loops=200)
    # more healing never makes her more likely to be defeated
    t = Q.seraphine(loops=400)
    assert t["use=1.0/round heal=1.0/round"] <= t["use=1.0/round heal=0.0/round"]


def test_quant_interactions_cover_all_five():
    i = Q.interactions()
    assert i["assumptions"]["returns_per_round_upper_bound"] == 0.63
    assert set(i) >= {"birdie_free_fast_events_per_round", "cass", "seraphine_per_use", "elias_per_use"}
