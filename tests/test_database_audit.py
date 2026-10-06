"""Structural audit of the shipped TTS / SCED "database" (tools/audit_database.py).

Three layers, all fast (the whole file runs in a few seconds, no network):

  * the real audit of dist/ must report no ERROR (the owner's game crashes when
    a scenario box's Place spawns its decks, so any structural defect in the
    shipped objects, images or scripts is a regression);
  * the auditor itself is exercised on small synthetic objects: every defect
    class it claims to catch is injected and must come back as an ERROR, and a
    clean object must stay clean (an audit that cannot fail proves nothing);
  * helpers: JPEG header parsing, JSON hygiene, determinism, the exit status.

Checks that compare with the official data (.cache/official, fetched by the
SCED harness) are skipped when that data is absent.
"""
import base64
import copy
import hashlib
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import audit_database as A  # noqa: E402

OFFICIAL_MENU = os.path.join(ROOT, ".cache", "official", "tts_menu")
HAVE_REFERENCE = os.path.isdir(OFFICIAL_MENU) and os.path.exists(os.path.join(OFFICIAL_MENU, "library.json"))
needs_reference = pytest.mark.skipif(not HAVE_REFERENCE, reason=".cache/official not present (official data)")
HAVE_DIST = os.path.exists(os.path.join(ROOT, "dist", "saved_object_the_still_hour.json"))

# ERRORs the audit reports on dist/ today that are understood and wait for the
# next publish of dist/ (pipeline/publish_hosted.py).  Everything else must be
# clean.  Each entry has to keep firing: once the defect is fixed the entry is
# removed (test_known_errors_still_fire fails otherwise), so a waiver cannot
# outlive its defect.
KNOWN_ERRORS = {}

# a 10x14 baseline and a progressive JPEG (made with PIL, 632 and 521 bytes)
BASELINE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkzODdASFxOQERXRTc4UG1RV19iZ2hnPk1xeXBk"
    "eFxlZ2P/2wBDARESEhgVGC8aGi9jQjhCY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2P/wAARCAAOAAoD"
    "ASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKB"
    "kaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
    "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQF"
    "BgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5"
    "OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX"
    "2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDOooor3DpP/9k=")
PROGRESSIVE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkzODdASFxOQERXRTc4UG1RV19iZ2hnPk1xeXBk"
    "eFxlZ2P/2wBDARESEhgVGC8aGi9jQjhCY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2P/wgARCAAOAAoD"
    "ASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAT/xAAVAQEBAAAAAAAAAAAAAAAAAAADBP/aAAwDAQACEAMQAAABmFyf/8QAFBABAAAAAAAA"
    "AAAAAAAAAAAAIP/aAAgBAQABBQIf/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEB"
    "PwF//8QAFBABAAAAAAAAAAAAAAAAAAAAIP/aAAgBAQAGPwIf/8QAFBABAAAAAAAAAAAAAAAAAAAAIP/aAAgBAQABPyEf/9oADAMBAAIAAwAAABD3"
    "/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPxB//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPxB//8QAFBABAAAAAAAAAAAAAAAA"
    "AAAAIP/aAAgBAQABPxAf/9k=")


# --------------------------------------------------------------------------
# 1. the real dist/
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dist_audit():
    if not HAVE_DIST:
        pytest.skip("dist/ is not built")
    t0 = time.time()
    report, aud = A.audit(root=ROOT)
    return report, aud, time.time() - t0


def test_dist_audit_is_fast(dist_audit):
    """About 2 s on an idle machine; the bound only catches accidental quadratic behaviour."""
    report, aud, seconds = dist_audit
    assert seconds < 25, "audit took %.1f s" % seconds
    assert aud.docs, "no dist files were audited"


def test_dist_has_no_unexpected_errors(dist_audit):
    """No ERROR finding on the shipped files beyond the documented waivers."""
    report, _aud, _t = dist_audit
    errors = [f for f in report.findings if f.severity == A.ERROR and f.code not in KNOWN_ERRORS]
    assert not errors, "\n".join(
        "%s %s: %s [%s]" % (f.code, f.where, f.message, f.evidence) for f in errors[:10])


def test_known_errors_still_fire(dist_audit):
    """A waiver must not outlive its defect."""
    report, _aud, _t = dist_audit
    if not report.stats.get("reference"):
        pytest.skip("official data absent: reference-dependent findings cannot fire")
    fired = {f.code for f in report.findings if f.severity == A.ERROR}
    stale = [c for c in KNOWN_ERRORS if c not in fired]
    assert not stale, "defect fixed? remove from KNOWN_ERRORS: %s" % stale


def test_dist_audit_covers_every_shipped_file(dist_audit):
    _report, aud, _t = dist_audit
    names = {os.path.basename(d.name) for d in aud.docs}
    for want in ("saved_object_the_still_hour.json", "the_still_hour.json", "the_still_hour_box.json",
                 "stillhour_starter.json"):
        assert want in names, want


def test_dist_images_and_pin_verified(dist_audit):
    """Every hosted image exists, parses as a JPEG and is byte-identical in the pinned commit."""
    report, _aud, _t = dist_audit
    assert report.stats.get("hosted_urls", 0) >= 190
    bad = [f for f in report.findings if f.code.startswith(("C01", "C02")) and f.severity == A.ERROR]
    assert not bad, bad[0].message
    pinned = [f for f in report.findings if f.code == "C04.pinned-ok"]
    # the pin can only be checked when git and the commit are here; otherwise the report says so
    assert pinned or any(f.code == "C04.commit-unknown" for f in report.findings) \
        or any("git is not available" in n for n in report.notes)


@needs_reference
def test_dist_reference_checks_ran(dist_audit):
    report, _aud, _t = dist_audit
    ref = report.stats["reference"]
    assert ref["official_card_ids"] > 5000 and ref["official_deck_ids"] > 1000
    assert any(f.code == "A10.deckid-official" for f in report.findings)
    assert any(f.code == "D02.ids-official" for f in report.findings)


# --------------------------------------------------------------------------
# 2. the auditor on synthetic objects
# --------------------------------------------------------------------------
PIN = "9d4b3ce2a18429d31b072becae7dc9f72954775b"


def url(name, v="0123456789"):
    return "https://raw.githubusercontent.com/o/r/%s/dist/cards/%s.jpg?v=%s" % (PIN, name, v)


def tr(x=0.0, z=0.0, scale=1.0):
    return {"posX": x, "posY": 1.5, "posZ": z, "rotX": 0.0, "rotY": 180.0, "rotZ": 0.0,
            "scaleX": scale, "scaleY": 1.0, "scaleZ": scale}


def card(n, nickname=None, extra_gm=None):
    deck = "950%02d" % n
    gm = {"id": "t-%d" % n, "type": "Treachery", "class": "Mythos", "traits": "Static.", "cycle": "T"}
    gm.update(extra_gm or {})
    return {"Name": "Card", "Nickname": nickname or "Card %d" % n, "Description": "", "GUID": "c%05x" % n,
            "CardID": int(deck + "00"), "SidewaysCard": False, "Tags": ["ScenarioCard"], "LuaScript": "",
            "LuaScriptState": "", "ColorDiffuse": {"r": 0.713, "g": 0.713, "b": 0.713}, "Hands": True,
            "HideWhenFaceDown": True, "GMNotes": json.dumps(gm), "Transform": tr(),
            "CustomDeck": {deck: {"FaceURL": url("face%d" % n), "BackURL": url("back"), "NumWidth": 1,
                                  "NumHeight": 1, "Type": 0, "UniqueBack": False, "BackIsHidden": True}}}


def make_doc():
    """A clean scenario box: a 2-card Deck and a loose card, laid out by a memory list."""
    c1, c2, loose = card(1), card(2), card(3)
    deck = {"Name": "Deck", "Nickname": "Deck", "Description": "", "GUID": "d00001", "Tags": ["ScenarioCard"],
            "SidewaysCard": False, "Hands": False, "Transform": tr(),
            "ColorDiffuse": {"r": 0.713, "g": 0.713, "b": 0.713},
            "DeckIDs": [c1["CardID"], c2["CardID"]],
            "CustomDeck": {k: v for c in (c1, c2) for k, v in c["CustomDeck"].items()},
            "ContainedObjects": [c1, c2]}
    ml = {"d00001": {"lock": False, "pos": {"x": -3.0, "y": 1.6, "z": 0.0}, "rot": {"x": 0, "y": 180, "z": 0}},
          loose["GUID"]: {"lock": False, "pos": {"x": -3.0, "y": 1.6, "z": 5.0}, "rot": {"x": 0, "y": 180, "z": 0}}}
    box = {"Name": "Custom_Model_Bag", "Nickname": "Box", "Description": "", "GUID": "b00001",
           "GMNotes": json.dumps({"id": "t-box", "type": "ScenarioBox"}), "Transform": tr(12.0, 36.0),
           "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0}, "Bag": {"Order": 0},
           "CustomMesh": {"MeshURL": "https://steamusercontent-a.akamaihd.net/ugc/1/2/", "DiffuseURL": url("box"),
                          "NormalURL": "", "ColliderURL": "", "Convex": True, "MaterialIndex": 3, "TypeIndex": 6},
           "LuaScript": "", "LuaScriptState": json.dumps({"ml": ml}), "ContainedObjects": [deck, loose]}
    return {"SaveName": "t", "ObjectStates": [box]}


def parts(doc):
    box = doc["ObjectStates"][0]
    deck, loose = box["ContainedObjects"]
    return box, deck, loose


def run(doc, checks="A", ref=None, root=ROOT, name="mem/saved_object_t.json", luac=True):
    return A.audit_documents([(name, doc)], root=root, ref=ref, checks=checks, luac=luac)


def codes(report, severity=A.ERROR):
    return {f.code for f in report.findings if f.severity == severity}


def test_clean_synthetic_object_has_no_errors_or_warnings():
    rep = run(make_doc(), "A")
    assert not [f for f in rep.findings if f.severity in (A.ERROR, A.WARN)], \
        [(f.code, f.message) for f in rep.findings if f.severity != A.INFO]


def _set_deckids(doc):
    parts(doc)[1]["DeckIDs"] = list(reversed(parts(doc)[1]["DeckIDs"]))


def _drop_deck_sheet(doc):
    deck = parts(doc)[1]
    deck["CustomDeck"].pop(next(iter(deck["CustomDeck"])))


def _card_no_customdeck(doc):
    parts(doc)[2].pop("CustomDeck")


def _deck_card_wrong_sheet(doc):
    c = parts(doc)[1]["ContainedObjects"][0]
    c["CustomDeck"] = {"99999": next(iter(c["CustomDeck"].values()))}


def _same_deck_id_two_images(doc):
    box, deck, loose = parts(doc)
    loose["CardID"] = deck["ContainedObjects"][0]["CardID"]
    loose["CustomDeck"] = {str(loose["CardID"] // 100): dict(
        next(iter(loose["CustomDeck"].values())), FaceURL=url("other"))}


def _nan_scale(doc):
    parts(doc)[2]["Transform"]["scaleX"] = float("nan")


def _negative_scale(doc):
    parts(doc)[1]["Transform"]["scaleZ"] = -1.0


def _cardid_int32(doc):
    c = parts(doc)[2]
    c["CardID"] = 2 ** 31 * 2
    c["CustomDeck"] = {str(c["CardID"] // 100): next(iter(c["CustomDeck"].values()))}


def _cardid_float(doc):
    parts(doc)[2]["CardID"] = float(parts(doc)[2]["CardID"])


def _index_past_sheet(doc):
    c = parts(doc)[2]
    c["CardID"] += 5


def _ml_orphan(doc):
    state = json.loads(parts(doc)[0]["LuaScriptState"])
    state["ml"]["aaaaaa"] = dict(state["ml"]["d00001"])
    parts(doc)[0]["LuaScriptState"] = json.dumps(state)


def _ml_nonfinite(doc):
    state = json.loads(parts(doc)[0]["LuaScriptState"])
    state["ml"]["d00001"]["pos"]["x"] = "left"
    parts(doc)[0]["LuaScriptState"] = json.dumps(state)


def _ml_far(doc):
    state = json.loads(parts(doc)[0]["LuaScriptState"])
    state["ml"]["d00001"]["pos"]["z"] = 5000
    parts(doc)[0]["LuaScriptState"] = json.dumps(state)


def _null_value(doc):
    parts(doc)[2]["Tags"] = ["ScenarioCard", None]


def _url_space(doc):
    c = parts(doc)[2]
    next(iter(c["CustomDeck"].values()))["FaceURL"] = "https://raw.githubusercontent.com/o/r/%s/dist/cards/a b.jpg" % PIN


def _url_file(doc):
    c = parts(doc)[2]
    next(iter(c["CustomDeck"].values()))["FaceURL"] = "file:///C:/art/x.jpg"


def _url_placeholder(doc):
    c = parts(doc)[2]
    next(iter(c["CustomDeck"].values()))["BackURL"] = "https://placehold.co/419x600/png"


def _url_empty(doc):
    c = parts(doc)[2]
    next(iter(c["CustomDeck"].values()))["FaceURL"] = ""


def _gm_not_json(doc):
    parts(doc)[2]["GMNotes"] = "{not json"


def _gm_not_object(doc):
    parts(doc)[2]["GMNotes"] = "[1, 2]"


def _tags_dict(doc):
    parts(doc)[2]["Tags"] = {}


def _hands_dict(doc):
    parts(doc)[2]["Hands"] = {"x": 1}


def _customdeck_list(doc):
    parts(doc)[2]["CustomDeck"] = []


def _color_range(doc):
    parts(doc)[2]["ColorDiffuse"]["r"] = 1.7


def _grid_range(doc):
    c = parts(doc)[2]
    next(iter(c["CustomDeck"].values()))["NumWidth"] = 11


def _deck_empty(doc):
    d = parts(doc)[1]
    d["ContainedObjects"], d["DeckIDs"], d["CustomDeck"] = [], [], {}


def _deck_with_non_card(doc):
    parts(doc)[1]["ContainedObjects"].append({"Name": "Bag", "GUID": "eeeeee"})


def _siblings_same_guid_in_ml(doc):
    box, deck, loose = parts(doc)
    loose["GUID"] = deck["GUID"]
    state = json.loads(box["LuaScriptState"])
    state["ml"].pop("c00003", None)
    box["LuaScriptState"] = json.dumps(state)


def _missing_mesh(doc):
    parts(doc)[0]["CustomMesh"]["MeshURL"] = ""


def _no_name(doc):
    parts(doc)[2].pop("Name")


def _guid_type(doc):
    parts(doc)[2]["GUID"] = 123456


MUTATIONS = [
    ("DeckIDs reordered", _set_deckids, "A03.deckids"),
    ("Deck.CustomDeck lacks a sheet", _drop_deck_sheet, "A03.customdeck-missing"),
    ("card without CustomDeck", _card_no_customdeck, "A01.required-key"),
    ("contained card on a foreign sheet", _deck_card_wrong_sheet, "A03.card-customdeck"),
    ("one deck id, two images", _same_deck_id_two_images, "A10.deckid-two-images"),
    ("NaN scale", _nan_scale, "A06.transform-nonfinite"),
    ("negative scale", _negative_scale, "A06.scale"),
    ("CardID beyond int32", _cardid_int32, "A04.cardid-range"),
    ("CardID stored as float", _cardid_float, "A01.field-type"),
    ("cell index past the sheet", _index_past_sheet, "A04.index-range"),
    ("ml position not a number", _ml_nonfinite, "A08.ml-vector"),
    ("ml position off the world", _ml_far, "A08.ml-bounds"),
    ("null in an array", _null_value, "A09.null"),
    ("URL with a space", _url_space, "A05.url-chars"),
    ("machine-local file URL", _url_file, "A05.url-local"),
    ("placeholder image URL", _url_placeholder, "A05.url-placeholder"),
    ("empty FaceURL", _url_empty, "A05.url-missing"),
    ("GMNotes not JSON", _gm_not_json, "A07.gmnotes-json"),
    ("GMNotes JSON not an object", _gm_not_object, "A07.gmnotes-shape"),
    ("Tags as an object", _tags_dict, "A01.field-type"),
    ("Hands as an object", _hands_dict, "A01.field-type"),
    ("CustomDeck as an array", _customdeck_list, "A01.field-type"),
    ("ColorDiffuse out of range", _color_range, "A06.color"),
    ("sheet grid beyond 10x7", _grid_range, "A04.grid-range"),
    ("empty Deck", _deck_empty, "A03.deck-empty"),
    ("non-card inside a Deck", _deck_with_non_card, "A03.deck-child"),
    ("placed siblings share a GUID", _siblings_same_guid_in_ml, "A02.guid-ml-collision"),
    ("bag without mesh URL", _missing_mesh, "A05.url-missing"),
    ("object without Name", _no_name, "A01.name"),
    ("GUID is a number", _guid_type, "A01.field-type"),
]


@pytest.mark.parametrize("label,mutate,expected", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_injected_defect_is_an_error(label, mutate, expected):
    doc = make_doc()
    mutate(doc)
    rep = run(doc, "A")
    assert expected in codes(rep), "%s: wanted %s, got %s" % (label, expected, sorted(codes(rep)))


def test_ml_key_without_an_object_is_flagged():
    """Official boxes carry ~1,000 stale ml keys and SCED skips them, so this is a warning."""
    doc = make_doc()
    _ml_orphan(doc)
    rep = run(doc, "A")
    assert "A08.ml-orphan" in codes(rep, A.WARN) and "A08.ml-orphan" not in codes(rep)


def test_malformed_values_never_crash_the_audit():
    """Hostile shapes become findings, not exceptions."""
    doc = make_doc()
    box, deck, loose = parts(doc)
    loose["CustomUIAssets"] = [["not", "a", "dict"], {"Name": ["x"], "URL": {}}]
    loose["Transform"] = {"posX": [1], "scaleX": {}}
    deck["CustomDeck"][next(iter(deck["CustomDeck"]))] = ["x"]
    box["CustomMesh"] = ["nope"]
    rep = run(doc, "ABCDEFG", luac=False)
    assert rep.has_errors
    assert "A99.audit-crash" not in {f.code for f in rep.findings}


def test_output_is_identical_across_hash_seeds(tmp_path):
    """No set/dict ordering may leak into the report (PYTHONHASHSEED varies the order of string sets)."""
    import subprocess
    doc = make_doc()
    _box, deck, _loose = parts(doc)
    deck["ContainedObjects"][0]["GMNotes"] = json.dumps({"id": "t-1", "type": "Treachery", "zeta": 1, "alpha": 2})
    f = tmp_path / "saved_object_seed.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    outs = []
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "audit_database.py"), str(f), "--json",
                            "--root", str(tmp_path), "--checks", "ABDFG"], capture_output=True, env=env, timeout=120)
        assert p.returncode in (0, 1), p.stderr
        outs.append(p.stdout)
    assert outs[0] == outs[1] == outs[2]


def test_audit_is_deterministic():
    doc = make_doc()
    first = json.dumps(run(copy.deepcopy(doc), "ABDEFG").to_dict(), sort_keys=True)
    second = json.dumps(run(copy.deepcopy(doc), "ABDEFG").to_dict(), sort_keys=True)
    assert first == second


# --- reference-dependent checks -----------------------------------------------------
@pytest.fixture(scope="module")
def reference():
    if not HAVE_REFERENCE:
        pytest.skip("official data absent")
    rep = A.Report()
    ref, src = A.load_reference(list(A.DEFAULT_REFERENCE_DIRS), ROOT, rep)
    if ref is None:
        pytest.skip("official data not loadable")
    return ref, src


def test_reference_statistics(reference):
    ref, src = reference
    assert ref.n_boxes >= 30                      # the official campaign and scenario boxes
    assert len(ref.ids) > 5000                    # 2,357 (save) + ~3,850 (boxes) distinct card ids
    assert max(ref.deck_sheets) <= 12             # no official Deck mixes more than a dozen sheets
    assert ref.cd_flags[(None, True, 0)] > 1000   # BackIsHidden is true on official sheets
    assert src is None or "ScenarioCard" in src.special_tags or src.files > 50


def _card_with_gm(**gm):
    doc = make_doc()
    loose = parts(doc)[2]
    loose["GMNotes"] = json.dumps(dict({"id": "t-3", "type": "Asset", "class": "Neutral", "traits": "Item.",
                                        "cycle": "T", "cost": 1}, **gm))
    return doc


@needs_reference
@pytest.mark.parametrize("label,gm,expected", [
    ("string cost", {"cost": "–"}, "D01.value-type"),
    ("float level", {"level": 1.5}, "D01.value-type"),
    ("bool where int expected", {"cost": True}, "D01.value-type"),
    ("class with the wrong case", {"class": "guardian"}, "D01.class"),
    ("type with the wrong case", {"type": "asset"}, "D01.type-case"),
    ("id that is an official id", {"id": "01001"}, "D02.id-collision"),
    ("string where a list is expected", {"uses": "3 charges"}, "D01.value-type"),
], ids=lambda v: v if isinstance(v, str) else None)
def test_injected_gmnotes_defect_is_an_error(reference, label, gm, expected):
    ref, src = reference
    rep = run(_card_with_gm(**gm), "D", ref=ref)
    assert expected in codes(rep), "%s: %s" % (label, sorted(codes(rep)))


@needs_reference
def test_clean_gmnotes_card_passes(reference):
    ref, src = reference
    rep = run(_card_with_gm(), "D", ref=ref)
    assert not codes(rep), sorted(codes(rep))


@needs_reference
def test_deck_id_collision_with_official_data_is_an_error(reference):
    ref, src = reference
    doc = make_doc()
    c = parts(doc)[2]
    official_id = next(k for k in sorted(ref.deck_pairs) if k.isdigit())
    c["CardID"] = int(official_id) * 100
    c["CustomDeck"] = {official_id: next(iter(c["CustomDeck"].values()))}
    rep = run(doc, "A", ref=ref)
    assert "A10.deckid-official-collision" in codes(rep)


@needs_reference
def test_sced_norms_are_warnings_not_errors(reference):
    ref, src = reference
    doc = make_doc()
    for _box, deck, loose in [parts(doc)]:
        for c in deck["ContainedObjects"] + [loose]:
            next(iter(c["CustomDeck"].values()))["BackIsHidden"] = False
            c["Transform"]["scaleX"] = c["Transform"]["scaleZ"] = 1.15
            c["CustomUIAssets"] = [{"Name": "font_arkhamicons", "Type": 1, "URL": "https://x.test/f/"}]
    for c in parts(doc)[1]["ContainedObjects"]:
        next(iter(c["CustomDeck"].values()))["BackIsHidden"] = False
    deck = parts(doc)[1]
    for k in deck["CustomDeck"]:
        deck["CustomDeck"][k]["BackIsHidden"] = False
    rep = run(doc, "A", ref=ref)
    warn = codes(rep, A.WARN)
    assert {"A11.ui-assets-unused", "A12.back-is-hidden", "A12.card-scale"} <= warn
    assert not codes(rep)


# --- images ---------------------------------------------------------------------------
def _image_root(tmp_path, files):
    d = tmp_path / "dist" / "cards"
    d.mkdir(parents=True)
    for name, data in files.items():
        (d / name).write_bytes(data)
    return str(tmp_path)


def _doc_for_images(names):
    doc = make_doc()
    box, deck, loose = parts(doc)
    for c in [loose] + deck["ContainedObjects"]:
        e = next(iter(c["CustomDeck"].values()))
        e["FaceURL"] = url("face", v=hashlib.sha1(BASELINE_JPEG).hexdigest()[:10])
        e["BackURL"] = url("back", v=hashlib.sha1(BASELINE_JPEG).hexdigest()[:10])
    for k, e in deck["CustomDeck"].items():
        e["FaceURL"] = url("face", v=hashlib.sha1(BASELINE_JPEG).hexdigest()[:10])
        e["BackURL"] = url("back", v=hashlib.sha1(BASELINE_JPEG).hexdigest()[:10])
    box["CustomMesh"]["DiffuseURL"] = url("face", v=hashlib.sha1(BASELINE_JPEG).hexdigest()[:10])
    return doc


def test_jpeg_header_parser():
    b = A.parse_jpeg(BASELINE_JPEG)
    assert b["ok"] and (b["width"], b["height"]) == (10, 14) and not b["progressive"] and b["eoi"]
    p = A.parse_jpeg(PROGRESSIVE_JPEG)
    assert p["ok"] and p["progressive"] and p["scans"] > 1 and p["ncomp"] == 3
    assert not A.parse_jpeg(b"not a jpeg")["ok"]
    assert A.parse_jpeg(BASELINE_JPEG[:-2])["eoi"] is False


def test_real_dist_images_parse():
    path = os.path.join(ROOT, "dist", "cards")
    if not os.path.isdir(path):
        pytest.skip("dist/cards absent")
    names = sorted(os.listdir(path))[:6]
    for n in names:
        info = A.image_info(n, open(os.path.join(path, n), "rb").read())
        assert info["ok"] and info["width"] > 0 and info["eoi"], n


def test_hosted_image_checks(tmp_path):
    root = _image_root(tmp_path, {"face.jpg": BASELINE_JPEG, "back.jpg": BASELINE_JPEG})
    rep = run(_doc_for_images(["face", "back"]), "C", root=root)
    assert not codes(rep), sorted(codes(rep))
    assert "C02.progressive" not in codes(rep, A.WARN)


def test_progressive_jpeg_is_flagged(tmp_path):
    root = _image_root(tmp_path, {"face.jpg": PROGRESSIVE_JPEG, "back.jpg": PROGRESSIVE_JPEG})
    doc = _doc_for_images(["face", "back"])
    rep = run(doc, "C", root=root)
    assert "C02.progressive" in codes(rep, A.WARN)


def test_missing_and_corrupt_images_are_errors(tmp_path):
    root = _image_root(tmp_path, {"face.jpg": b"\xff\xd8garbage"})       # back.jpg is missing
    rep = run(_doc_for_images(["face", "back"]), "C", root=root)
    assert {"C01.missing-file", "C02.bad-image"} <= codes(rep)


def test_sprite_sheet_grid_must_match_the_image(tmp_path):
    """A 10x14 px image cannot be a 2x1 grid of 5:7 cells."""
    root = _image_root(tmp_path, {"face.jpg": BASELINE_JPEG, "back.jpg": BASELINE_JPEG})
    doc = _doc_for_images(["face", "back"])
    loose = parts(doc)[2]
    entry = next(iter(loose["CustomDeck"].values()))
    entry["NumWidth"], entry["NumHeight"] = 2, 1
    rep = run(doc, "C", root=root)
    assert "C08.sheet-grid" in codes(rep, A.WARN)
    entry["NumWidth"], entry["NumHeight"] = 1, 1
    assert "C08.sheet-grid" not in codes(run(doc, "C", root=root), A.WARN)


def test_stale_cache_buster_is_flagged(tmp_path):
    root = _image_root(tmp_path, {"face.jpg": BASELINE_JPEG, "back.jpg": BASELINE_JPEG + b"\x00"})
    rep = run(_doc_for_images(["face", "back"]), "C", root=root)
    assert "C03.stale-cache-buster" in codes(rep, A.WARN)


# --- Lua ------------------------------------------------------------------------------------
def _lua_doc(source):
    doc = make_doc()
    parts(doc)[0]["LuaScript"] = source
    return doc


@pytest.mark.parametrize("source,expected", [
    ("function onLoad(\n", "E01.syntax"),
    ("local f = io.open('x')\n", "E02.forbidden-lib"),
    ("os.execute('ls')\n", "E02.forbidden-os"),
    ("local m = require('core/Missing')\n", "E02.require"),
    ("local x = 7 // 2\n", "E01.syntax"),
    ("local s = string.pack('i4', 1)\n", "E02.lua53-lib"),
])
def test_lua_defects_are_errors(source, expected):
    rep = run(_lua_doc(source), "E")
    got = codes(rep)
    # without luac 5.2 the syntax rule falls back to the token scan
    assert expected in got or (expected == "E01.syntax" and "E02.lua53-syntax" in got), sorted(got)


def test_clean_lua_passes_and_reads_undefined_globals():
    src = "function onLoad() print(JSON.encode({1})) end\nfunction buttonClick_place() return GlobalApi end\n"
    rep = run(_lua_doc(src), "E")
    assert not codes(rep)
    if A.find_luac():
        assert "E04.undefined-global" in codes(rep, A.WARN)       # GlobalApi is not a TTS global


def test_spawn_burst_detector():
    burst = "for i = 1, 3 do spawnObjectData({data = {}}) end\n"
    staged = "for i = 1, 3 do Wait.frames(function() spawnObjectData({data = {}}) end, i * 8) end\n"
    assert A.lua_spawn_loops(A.lua_tokens(burst))
    assert not A.lua_spawn_loops(A.lua_tokens(staged))


# --- file hygiene and exit status -------------------------------------------------------------
def test_json_text_hygiene(tmp_path):
    p = tmp_path / "dup.json"
    p.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    assert "A00.duplicate-keys" in {c for _s, c, _m, _e in A.load_json_file(str(p), "dup.json").problems}
    p.write_text('{"a": NaN}', encoding="utf-8")
    assert "A00.nonfinite" in {c for _s, c, _m, _e in A.load_json_file(str(p), "nan.json").problems}
    p.write_text('{"a": ', encoding="utf-8")
    assert A.load_json_file(str(p), "bad.json").problems[0][1] == "A00.parse"
    p.write_bytes(b"\xef\xbb\xbf{}")
    assert A.load_json_file(str(p), "bom.json").problems[0][1] == "A00.bom"
    p.write_bytes(b"\xff\xfe{}")
    assert A.load_json_file(str(p), "enc.json").problems[0][1] == "A00.encoding"


def test_exit_status_follows_errors(tmp_path):
    clean, dirty = make_doc(), make_doc()
    _nan = parts(dirty)[2]
    _nan["Transform"]["scaleY"] = -2
    a, b = tmp_path / "saved_object_clean.json", tmp_path / "saved_object_dirty.json"
    a.write_text(json.dumps(clean), encoding="utf-8")
    b.write_text(json.dumps(dirty), encoding="utf-8")
    base = ["--no-reference", "--checks", "A", "--root", str(tmp_path), "--no-stats"]
    assert A.main([str(a)] + base) == 0
    assert A.main([str(b)] + base) == 1
    assert A.main([str(tmp_path / "nope.json")] + base) == 2


def test_json_output_round_trips(capsys):
    a = os.path.join(ROOT, "dist", "stillhour_starter.json")
    if not os.path.exists(a):
        pytest.skip("dist/ is not built")
    A.main([a, "--json", "--checks", "A", "--no-reference"])
    data = json.loads(capsys.readouterr().out)
    assert set(data) >= {"summary", "findings", "stats", "notes"}
    assert {f["severity"] for f in data["findings"]} <= {"ERROR", "WARN", "INFO"}
