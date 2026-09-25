"""Table presence: minicards, campaign guide PDF, campaign log token and the
scenario/campaign memory-bag boxes, each checked against the real SCED object
the owner exported (docs/art_reference/sced_objects/)."""
import copy
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import campaign_log as L  # noqa: E402
import compile_campaign as cc  # noqa: E402
import table_presence as T  # noqa: E402

GT = os.path.join(ROOT, "docs", "art_reference", "sced_objects")
TABLE = os.path.join(ROOT, "dist", "the_still_hour_table.json")
RELEASE = os.path.join(ROOT, "dist", "downloads", "the_still_hour.json")


def gt(name):
    return json.load(open(os.path.join(GT, name), encoding="utf-8"))["ObjectStates"][0]


def table_box():
    return json.load(open(TABLE, encoding="utf-8"))["ObjectStates"][0]


def by_name(box, name):
    return [o for o in box["ContainedObjects"] if o["Name"] == name]


def missing_keys(truth, ours, skip=()):
    return sorted(k for k in truth if k not in ours and k not in skip)


# ------------------------------------------------------------- minicards --
def test_minicards_follow_sced_minicard():
    truth = gt("minicard.json")
    deck = T.build_minicard_deck()
    cards = deck["ContainedObjects"]
    ids = {c["id"] for c in T.investigator_specs()}
    assert len(cards) == len(ids) == 5
    for c in cards:
        assert missing_keys(truth, c) == []
        md = json.loads(c["GMNotes"])
        assert set(md) == set(json.loads(truth["GMNotes"])) == {"id", "type"}
        assert md["type"] == "Minicard" and md["id"].endswith("-m")
        assert md["id"][:-2] in ids
        assert c["Name"] == truth["Name"] == "CardCustom"
        assert c["Tags"] == truth["Tags"] == ["Minicard"]
        assert c["Transform"]["scaleX"] == truth["Transform"]["scaleX"] == 0.6
        (deck_id, cd), = c["CustomDeck"].items()
        assert c["CardID"] == int(deck_id + "00")
        tcd = next(iter(truth["CustomDeck"].values()))
        assert {k: cd[k] for k in ("NumWidth", "NumHeight", "BackIsHidden", "UniqueBack")} == \
            {k: tcd[k] for k in ("NumWidth", "NumHeight", "BackIsHidden", "UniqueBack")}
    assert len({c["CardID"] for c in cards}) == 5


def test_minicard_faces_render_on_the_plugin_template(tmp_path):
    import render_placeholders as rp
    from PIL import Image
    assert os.path.exists(os.path.join(ROOT, "assets", "frames", "se", "templates",
                                       "AHLCG-MiniInvestigator.png"))
    assert rp.se_reg("MiniInvestigator", "Portrait-portrait-clip") == (0, 0, 488, 750)
    inv = T.investigator_specs()[0]
    f, b = str(tmp_path / "f.png"), str(tmp_path / "b.png")
    assert rp.s_minicard(inv, f, b)
    assert Image.open(f).size == Image.open(b).size == (488, 750)


# ---------------------------------------------------------------- guide --
def test_guide_object_follows_sced_campaign_guide():
    truth = gt("campaign_guide_pdf.json")
    g = T.build_guide()
    assert missing_keys(truth, g) == []
    assert g["Name"] == "Custom_PDF" and g["Tags"] == ["CampaignGuide"]
    assert json.loads(g["GMNotes"])["type"] == "CampaignGuide"
    assert set(g["CustomPDF"]) == set(truth["CustomPDF"])
    assert g["Transform"]["scaleX"] == truth["Transform"]["scaleX"]


def test_committed_guide_is_hosted_and_current():
    pdf = os.path.join(ROOT, "dist", "guide", "the_still_hour_campaign_guide.pdf")
    data = open(pdf, "rb").read()
    assert data.startswith(b"%PDF")
    url = by_name(table_box(), "Custom_PDF")[0]["CustomPDF"]["PDFUrl"]
    m = re.match(r"https://raw\.githubusercontent\.com/[^?]+/dist/guide/"
                 r"the_still_hour_campaign_guide\.pdf\?v=([0-9a-f]{10})$", url)
    assert m, url
    assert m.group(1) == hashlib.sha1(data).hexdigest()[:10], "stale guide URL"


def test_guide_text_is_cleaned_of_designer_asides():
    import build_guide_pdf as G
    text = G.clean(open(G.SOURCE, encoding="utf-8").read())
    for bad in ("v0.", "CO-00", "Design note", "finale you asked for",
                "All values provisional"):
        assert bad not in text, bad
    assert "`" not in text.replace("```", "")
    kinds = [k for k, _ in G.parse(open(G.SOURCE, encoding="utf-8").read())]
    assert "map" in kinds and "table" in kinds and "quote" in kinds
    # CO-001 contest target survives the clean-up
    assert "4 × investigators (12 at three players)" in text


def test_guide_reads_like_an_official_guide():
    # intro boxes, numbered setup, "Do not read until..." dividers and a
    # resolution box for every resolution the manifest and the cards name
    import build_guide_pdf as G
    blocks = G.parse(open(G.SOURCE, encoding="utf-8").read())
    heads = [p[0] for k, p in blocks if k == "res"]
    divs = [p for k, p in blocks if k == "p" and p.strip("*").startswith("Do not read")]
    assert len(divs) >= 3                       # Prologue, loop, finale
    manifest = json.load(open(os.path.join(ROOT, "campaigns", "still_hour",
                                           "scenario_manifest.json"), encoding="utf-8"))
    names = [r["name"] for s in manifest["scenarios"] for r in s.get("resolutions", [])]
    names += [r["name"] for r in manifest["campaign"].get("loop_resolutions", [])]
    names += ["Take Its Place", "Let It In, On Your Terms", "Close the Door",
              "Break Through", "Seal by Force", "Next Time", "The Loop Wins"]
    for n in names:
        assert any(n in h for h in heads), n
    h2 = [p for k, p in blocks if k == "h2"]
    for sec in ("CAMPAIGN SETUP", "PROLOGUE", "THE LOOP", "BETWEEN LOOPS",
                "THE DISTRICTS", "FINALE"):
        assert any(sec in h for h in h2), sec


try:
    import reportlab  # noqa: F401
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False


@pytest.mark.skipif(not HAVE_REPORTLAB, reason="reportlab not installed")
def test_guide_builds(tmp_path):
    import build_guide_pdf as G
    r = G.build(str(tmp_path / "g.pdf"), log_pages=False)
    assert r["pages"] >= 5
    assert open(tmp_path / "g.pdf", "rb").read(4) == b"%PDF"


# ------------------------------------------------------------------ log --
def test_log_token_follows_sced_campaign_log():
    truth = gt("campaign_log_token.json")
    log = T.build_log()
    assert missing_keys(truth, log) == []
    assert log["Name"] == "Custom_Token" and log["Tags"] == ["CampaignLog"]
    assert set(log["CustomImage"]) == set(truth["CustomImage"])
    assert log["Transform"]["scaleX"] == truth["Transform"]["scaleX"]
    pages = [log] + [log["States"][k] for k in sorted(log["States"])]
    assert len(pages) == 3 and sorted(log["States"]) == ["2", "3"]
    for n, p in enumerate(pages, start=1):
        md = json.loads(p["GMNotes"])
        assert md == {"id": "STHR-LOG{}".format(n), "type": "CampaignLog"}
        assert p["Description"] == "Page {}".format(n)
        assert "PAGE = {}".format(n) in p["LuaScript"]
        assert "function onSave" in p["LuaScript"]
    assert len({p["GUID"] for p in pages}) == 3


def test_log_layout_is_sane_and_matches_campaign_state_ids():
    lay = L.layout()
    for page in lay:
        keys = [f["k"] for f in page["fields"]]
        assert len(keys) == len(set(keys)), "duplicate field key"
        for f in page["fields"]:
            assert 0.02 < f["u"] < 0.98 and 0.02 < f["v"] < 0.98, f
            assert f["t"] in ("cb", "ct", "tx", "dv")
    src = open(os.path.join(ROOT, "src", "StillHour", "Knowledge.ttslua"), encoding="utf-8").read()
    fact_ids = set(re.findall(r'\["([a-z-]+)"\]\s*=\s*\{ name', src))
    assert {f[0] for f in L.FACTS} == fact_ids
    enc = json.load(open(os.path.join(ROOT, "pipeline", "stillhour_encounter_spec.json"), encoding="utf-8"))
    enc_ids = {c["id"] for c in enc if "victory" in c}
    assert {n[0] for n in L.NAMED} <= enc_ids
    inv_ids = {c["id"] for c in T.investigator_specs()}
    assert {i for i, _ in L.INVESTIGATORS} == inv_ids


def test_log_script_parses_under_lua52(tmp_path):
    lua = __import__("shutil").which("lua5.2")
    if not lua:
        pytest.skip("lua5.2 not installed")
    for page in (1, 2, 3):
        path = str(tmp_path / "log_page{}.lua".format(page))
        open(path, "w", encoding="utf-8").write(L.lua_script(page))
        r = subprocess.run([lua, "-e", "assert(loadfile('{}'))".format(path.replace("\\", "/"))],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------- boxes --
def _memory_bag_module():
    s = gt("scenario_box_memory_bag.json")["LuaScript"]
    m = re.search(r'__bundle_register\("MemoryBag", function\(require, _LOADED, '
                  r'__bundle_register, __bundle_modules\)\n(.*?)\nend\)\n__bundle_register\("__root"',
                  s, re.S)
    return m.group(1)


def test_memory_bag_script_is_scEDs_verbatim():
    ours = open(T.MEMORY_BAG_LUA, encoding="utf-8").read()
    assert _memory_bag_module().strip() in ours


def _check_memory_bag(box, truth):
    assert missing_keys(truth, box, skip=("AttachedDecals", "Tags")) == []
    assert "buttonClick_place" in box["LuaScript"] and "buttonClick_recall" in box["LuaScript"]
    ml = json.loads(box["LuaScriptState"])["ml"]
    guids = [o["GUID"] for o in box["ContainedObjects"]]
    assert len(guids) == len(set(guids))
    assert set(ml) <= set(guids)
    for e in ml.values():
        assert set(e) == {"lock", "pos", "rot"}
        assert set(e["pos"]) == set(e["rot"]) == {"x", "y", "z"}
    assert box["CustomMesh"]["MeshURL"] == truth["CustomMesh"]["MeshURL"]
    return ml


def test_table_campaign_box_follows_sced_campaign_box():
    truth = gt("campaign_box_memory_bag.json")
    box = table_box()
    ml = _check_memory_bag(box, truth)
    assert box["Tags"] == truth["Tags"] == ["CampaignBox", "Reloadable"]
    md = json.loads(box["GMNotes"])
    assert set(md) == set(json.loads(truth["GMNotes"]))
    assert md["type"] == "CampaignBox" and md["filename"] == "the_still_hour"
    names = sorted(o["Name"] for o in box["ContainedObjects"])
    assert names == ["Custom_PDF", "Custom_Token", "Deck"]
    assert set(ml) == {o["GUID"] for o in box["ContainedObjects"]}
    assert "file:///" not in json.dumps(box)
    have = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "dist", "cards", "*.jpg"))}
    for url in re.findall(r"/dist/cards/([^\"?/]+\.jpg)", json.dumps(box)):
        assert url in have, url


def test_compile_campaign_with_fixture(tmp_path, monkeypatch):
    """Two locked fixture scenarios compile into ScenarioBoxes (memory bags on
    the small box mesh) inside the campaign box, beside minicards/log/guide —
    without touching the real campaign's lock-in state."""
    real = cc.campaign_paths("still_hour")
    cards = cc.load_cards(real)
    locs = [c for c, v in cards.items() if v.get("type") == "Location"][:3]
    others = [c for c, v in cards.items() if v.get("type") in ("Treachery", "Enemy")][:4]
    assert locs and others
    manifest = {"scenarios": [{"id": "fixture-a", "name": "Fixture A", "order": 0},
                              {"id": "fixture-b", "name": "Fixture B", "order": 1}]}
    assign = {"fixture-a": {"_locked": True, "locations": locs, "encounter": others},
              "fixture-b": {"_locked": True, "locations": locs[:1],
                            "_map": {locs[0]: [2, 2]}}}
    (tmp_path / "m.json").write_text(json.dumps(manifest))
    (tmp_path / "a.json").write_text(json.dumps(assign))
    paths = dict(real, manifest=str(tmp_path / "m.json"),
                 assignments=str(tmp_path / "a.json"))
    monkeypatch.setattr(cc, "campaign_paths", lambda campaign="still_hour": paths)
    out = tmp_path / "campaign.json"
    r = cc.compile_campaign(str(out), require_locked=True)
    assert r["ok"] and r["scenarios"] == 2
    box = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    _check_memory_bag(box, gt("campaign_box_memory_bag.json"))
    sboxes = [o for o in box["ContainedObjects"] if o["Name"] == "Custom_Model_Bag"]
    assert [s["Nickname"] for s in sboxes] == ["Fixture A", "Fixture B"]
    truth_sb = gt("scenario_box_memory_bag.json")
    for sb in sboxes:
        ml = _check_memory_bag(sb, truth_sb)
        assert json.loads(sb["GMNotes"])["type"] == "ScenarioBox"
        assert "Tags" not in sb                      # like the exported books
        assert (sb["Transform"]["scaleX"], sb["Transform"]["scaleZ"]) == \
            (truth_sb["Transform"]["scaleX"], truth_sb["Transform"]["scaleZ"])
        assert set(ml) == {o["GUID"] for o in sb["ContainedObjects"]}
    # fixture-b's hand-placed location lands on grid slot (2, 2)
    mlb = json.loads(sboxes[1]["LuaScriptState"])["ml"]
    (only,) = mlb.values()
    assert (only["pos"]["x"], only["pos"]["z"]) == cc.slot_xz(2, 2)
    kinds = sorted(o["Name"] for o in box["ContainedObjects"])
    assert kinds == ["Custom_Model_Bag", "Custom_Model_Bag", "Custom_PDF", "Custom_Token", "Deck"]
    # unlocked scenarios still refuse
    assign["fixture-b"]["_locked"] = False
    (tmp_path / "a.json").write_text(json.dumps(assign))
    assert not cc.compile_campaign(str(tmp_path / "x.json"), require_locked=True)["ok"]


# ------------------------------------------------------------- download --
def test_release_asset_is_one_hosted_campaign_box():
    rel = json.load(open(RELEASE, encoding="utf-8"))
    assert "ObjectStates" not in rel, "SCED spawns the release text as ONE object"
    assert rel["Name"] == "Custom_Model_Bag"
    md = json.loads(rel["GMNotes"])
    assert md["type"] == "CampaignBox" and md["filename"] == "the_still_hour"
    names = {o["Name"] for o in rel["ContainedObjects"]}
    assert {"Custom_PDF", "Custom_Token", "Deck", "Bag"} <= names
    assert "file:///" not in json.dumps(rel)
    ml = json.loads(rel["LuaScriptState"])["ml"]
    assert set(ml) == {o["GUID"] for o in rel["ContainedObjects"]}


def test_package_download_refuses_local_urls_when_hosted_required(tmp_path, monkeypatch):
    import package_download as P
    import build_cards as B
    fake = copy.deepcopy(B.ART_URLS)
    fake["_campaign_guide"] = "file:///tmp/guide.pdf"
    monkeypatch.setattr(B, "ART_URLS", fake)
    monkeypatch.setattr(P, "ROOT", str(tmp_path))
    (tmp_path / "dist").mkdir()
    (tmp_path / "src" / "tts").mkdir(parents=True)
    (tmp_path / "src" / "tts" / "download_box.lua").write_text(
        open(os.path.join(ROOT, "src", "tts", "download_box.lua"), encoding="utf-8").read())
    (tmp_path / "dist" / "the_still_hour_mod.json").write_text(json.dumps({"ObjectStates": []}))
    with pytest.raises(SystemExit):
        P.main(["--require-hosted"])
    P.main([])                                   # local solo testing still packages
    rel = json.load(open(tmp_path / "dist" / "downloads" / "the_still_hour.json", encoding="utf-8"))
    assert "file:///" in json.dumps(rel)


# ------------------------------------------------- log script in fake TTS --
SYNC_CHUNK = r"""
local LOG = %s
local STATE = %s
spawnObjectJSON({ json = JSON.encode({ Name = "BlockSquare", Nickname = "state",
  Transform = { posX = 9, posY = 1, posZ = 9 }, LuaScriptState = JSON.encode(STATE) }) })
local log = spawnObjectJSON({ json = LOG })
local out = {}
Wait.frames(function()
  local r1 = log.call("syncFromCampaignState")
  local v1 = log.call("getLogValues").values
  out.p1 = { ok = r1.ok, loops = v1.loops, banked = v1.banked, act2 = v1.act2,
             name1 = v1.inv1_name, years1 = v1.inv1_years, dcom = v1.inv1_dcom,
             dwil = v1.inv1_dwil }
  local labels = {}
  for _, b in ipairs(log.getButtons() or {}) do labels[#labels + 1] = b.label end
  out.labels = labels
  local p2 = log.setState(2)
  Wait.frames(function()
    local r2 = p2.call("syncFromCampaignState")
    local v2 = p2.call("getLogValues").values
    out.p2 = { ok = r2.ok, unstuck = v2["k:you-are-unstuck"], lamp = v2["k:the-lamp-was-never-lit"],
               bell = v2["v:sthr-bellringer"], banked = v2["vb:sthr-bellringer"],
               wheel = v2["k:the-wheel-still-turns"] == true }
    -- exclusive groups: ticking Hard clears Standard
    local p1 = p2.setState(1)
    Wait.frames(function()
      p1.call("setLogValue", { key = "diff_standard", value = true })
      p1.call("setLogValue", { key = "diff_hard", value = true })
      local v = p1.call("getLogValues").values
      out.group = { standard = v.diff_standard, hard = v.diff_hard, loops = v.loops }
      print("@@OUT " .. JSON.encode(out))
    end, 5)
  end, 5)
end, 5)
"""


def test_log_script_syncs_from_campaign_state(tmp_path):
    import shutil
    lua = shutil.which("lua5.2")
    if not lua:
        pytest.skip("lua5.2 not installed")
    sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))
    import relay
    state = {"version": 1, "investigators": 3, "loopsCompleted": 4, "bankedMemory": 11,
             "dissonance": 2, "hourglass": 1,
             "knowledge": {"you-are-unstuck": True, "the-lamp-was-never-lit": True,
                           "the-thirteenth-toll": True, "the-road-remembers": True},
             "years": {"sthrelias": 7},
             "brackets": {"sthrelias": {"bracket": "Weathered", "physical": "combat",
                                         "mental": "willpower"}},
             "victoryLog": {"sthr-bellringer": True}}
    chunk = SYNC_CHUNK % (relay.lua_long_string(json.dumps(T.build_log(), ensure_ascii=False)),
                          "JSON.decode(" + relay.lua_quote(json.dumps(state)) + ")")
    path = tmp_path / "chunk.lua"
    path.write_text(chunk, encoding="utf-8")
    r = subprocess.run([lua, os.path.join(ROOT, "tests", "tts_fake", "mock_tts.lua"), str(path)],
                       capture_output=True, text=True, encoding="utf-8")
    msgs = [json.loads(ln[6:]) for ln in r.stdout.splitlines() if ln.startswith("@@MSG ")]
    errors = [m for m in msgs if m.get("messageID") == 3]
    assert not errors, errors
    outs = [m["message"][6:] for m in msgs if m.get("messageID") == 2
            and m.get("message", "").startswith("@@OUT ")]
    assert outs, r.stdout[-2000:]
    out = json.loads(outs[0])
    assert out["p1"] == {"ok": True, "loops": 4, "banked": 11, "act2": True,
                         "name1": "Elias Warde", "years1": 7, "dcom": True, "dwil": True}
    assert "✗" in out["labels"]                      # Weathered bracket ticked
    assert out["p2"] == {"ok": True, "unstuck": True, "lamp": True, "bell": True,
                         "banked": True, "wheel": False}
    assert out["group"] == {"standard": False, "hard": True, "loops": 4}


def sced_mini_id(base_id):
    """Port of SCED's Global.getMiniId (argonui/SCED src/Global/Global.ttslua)."""
    if "-" not in base_id:
        return base_id + "-m"
    if len(base_id) < 16:
        return base_id[:5] + "-m"
    return base_id + "-m"


def test_sced_derives_each_investigators_own_minicard_id():
    """SCED finds, moves and cleans up minicards by getMiniId(investigator id);
    a short hyphenated id would collapse every investigator to one miniId."""
    import json as _json
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = _json.load(open(os.path.join(root, "pipeline", "stillhour_cards_spec.json"), encoding="utf-8"))
    invs = [c["id"] for c in spec if c["type"] == "Investigator"]
    assert len(invs) == 5
    minis = {}

    def walk(o):
        md = _json.loads(o.get("GMNotes") or "{}")
        if md.get("type") == "Minicard":
            minis[md["id"]] = o
        for c in o.get("ContainedObjects") or []:
            walk(c)
    for rel in ("dist/the_still_hour_table.json", "dist/the_still_hour_campaign.json"):
        data = _json.load(open(os.path.join(root, rel), encoding="utf-8"))
        for o in data.get("ObjectStates") or [data]:
            walk(o)
    derived = [sced_mini_id(i) for i in invs]
    assert len(set(derived)) == len(invs), derived
    for d in derived:
        assert d in minis, "no minicard with SCED's id " + d


# ------------------------------------------------------------ placement --
# SCED's own snap points (argonui/SCED objects/PlayArea.721ba2 location snaps and
# MythosArea.9f334f, converted to world coordinates). Place must land on them.
SCED_LOCATION_X = [-17.04, -20.34, -23.64, -26.94, -30.24, -33.54, -36.84, -40.14, -43.44]
SCED_LOCATION_Z = [15.3, 11.48, 7.65, 3.83, 0.0, -3.83, -7.65, -11.48, -15.3]
SCED_MYTHOS = {"encounter": (-3.85, 5.72), "agenda_deck": (-2.94, 0.36),
               "act_deck": (-2.94, -5.05), "reference": (-3.85, -10.39)}


def test_every_map_slot_is_a_sced_location_snap_off_the_mythos_mat():
    for col in range(cc.LOCATION_GRID["cols"]):
        for row in range(cc.LOCATION_GRID["rows"]):
            x, z = cc.slot_xz(col, row)
            assert any(abs(x - v) < 0.02 for v in SCED_LOCATION_X), (col, row, x)
            assert any(abs(z - v) < 0.02 for v in SCED_LOCATION_Z), (col, row, z)
            assert x < -10, "location slot runs onto the scenario mat"


def test_map_columns_run_across_and_rows_run_down():
    # a row authored left-to-right in the Studio stays a row at the table
    # (same x, z falling to the players' right), and row 0 sits nearest the mat
    xs = {cc.slot_xz(c, 2)[0] for c in range(5)}
    zs = [cc.slot_xz(c, 2)[1] for c in range(5)]
    assert len(xs) == 1 and zs == sorted(zs, reverse=True)
    assert cc.slot_xz(0, 0)[0] > cc.slot_xz(0, 4)[0]


def test_scenario_stacks_land_on_the_mythos_mat_snaps():
    for stack, (x, z) in SCED_MYTHOS.items():
        px, _, pz = cc.PLACE[stack]["pos"]
        assert (round(px, 2), round(pz, 2)) == (x, z), stack
    assert cc.PLACE["act_deck"]["rot"] == cc.PLACE["agenda_deck"]["rot"]
    # nothing else may take the scenario card's slot
    ref = cc.PLACE["reference"]["pos"]
    assert all(v["pos"] != ref for k, v in cc.PLACE.items() if k != "reference")


OFFICIAL = os.path.join(ROOT, "docs", "art_reference", "sced_objects",
                        "official_layout_drowned_city.json")


def test_mythos_anchors_match_the_official_drowned_city_boxes():
    """Where FFG's own boxes put the scenario card, agenda, act, encounter deck,
    set-aside bag and set-aside enemies, Place puts ours."""
    rows = [r for sc in json.load(open(OFFICIAL, encoding="utf-8"))["scenarios"].values()
            for r in sc]

    def spots(pred):
        return {(tuple(r["pos"]), r["rot"]) for r in rows if pred(r)}

    def ours(stack):
        x, _, z = cc.PLACE[stack]["pos"]
        return ((round(x, 2), round(z, 2)), cc.PLACE[stack]["rot"])

    assert ours("reference") in spots(lambda r: "ScenarioReference" in r["types"])
    assert ours("agenda_deck") in spots(lambda r: r["types"] == ["Agenda"])
    assert ours("act_deck") in spots(lambda r: r["types"] == ["Act"])
    assert ours("encounter") in spots(lambda r: r["name"] == "Encounter Deck")
    assert ours("setup_aside") in spots(lambda r: r["object"] == "Custom_Model_Bag")
    assert ours("named") in spots(lambda r: "Enemy" in r["types"])


def test_agenda_and_act_decks_lie_sideways_like_the_official_boxes():
    # TTS lays a deck out by the Deck object's own SidewaysCard flag; the
    # official agenda/act decks are SidewaysCard true, Hands false
    rel = json.load(open(os.path.join(ROOT, "dist", "downloads",
                                      "the_still_hour.json"), encoding="utf-8"))
    decks = []

    def walk(o):
        for c in o.get("ContainedObjects") or []:
            if c.get("Name") == "Deck" and all(
                    json.loads(k.get("GMNotes") or "{}").get("type") in ("Agenda", "Act")
                    for k in c["ContainedObjects"]):
                decks.append(c)
            walk(c)
    walk(rel)
    assert decks, "no agenda/act decks in the release box"
    for d in decks:
        assert d["SidewaysCard"] is True and d["Hands"] is False, d["Nickname"]


def test_boxes_sharing_the_loop_board_never_stack_on_each_other(tmp_path):
    # a loop Places the Square plus any districts (and the finale) onto one
    # board: no two of their stacks or cards may share a spot
    out = tmp_path / "c.json"
    assert cc.compile_campaign(str(out))["ok"]
    box = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    manifest = json.load(open(os.path.join(ROOT, "campaigns", "still_hour",
                                           "scenario_manifest.json"), encoding="utf-8"))
    shared = {s["name"] for s in manifest["scenarios"]
              if s["id"] == "district_square" or s.get("shared_from") == "district_square"}
    spots = []
    for sb in box["ContainedObjects"]:
        if sb.get("Name") != "Custom_Model_Bag" or sb["Nickname"] not in shared:
            continue
        for e in json.loads(sb["LuaScriptState"])["ml"].values():
            spots.append((sb["Nickname"], e["pos"]["x"], e["pos"]["z"]))
    assert len({s[0] for s in spots}) == len(shared)
    for i, a in enumerate(spots):
        for b in spots[i + 1:]:
            # cards are ~2.5 x 3.5: two stacks closer than that on both axes overlap
            assert abs(a[1] - b[1]) >= 2.5 or abs(a[2] - b[2]) >= 2.5, (a, b)


# ------------------------------------------ replayable scenario box (fake TTS) --
LOOP_BOX_CHUNK = r"""
local BOX = %s
local box = spawnObjectJSON({ json = BOX })
local out = {}
local function count(tag)
  local n = 0
  for _, o in ipairs(getObjects()) do
    if o ~= box and o.hasTag(tag) then
      n = n + (o.type == "Deck" and #o.getObjects() or 1)
    end
  end
  return n
end
Wait.frames(function()
  local inside = #box.getObjects()
  out.placed1 = box.call("buttonClick_place")
  out.onTable1 = count("StillHourLoop")
  -- play: draw a card off the placed deck and leave it on the table
  for _, o in ipairs(getObjects()) do
    if o.type == "Deck" and o.hasTag("StillHourLoop") then
      local c = o.takeObject({ index = 0, position = { 5, 2, 5 } })
      out.drawnTagged = c.hasTag("StillHourLoop")
      break
    end
  end
  out.recalled = box.call("buttonClick_recall")
  out.onTable2 = count("StillHourLoop")
  out.boxKept = #box.getObjects() == inside
  out.placed2 = box.call("buttonClick_place")
  out.onTable3 = count("StillHourLoop")
  print("@@OUT " .. JSON.encode(out))
end, 10)
"""


def test_scenario_box_places_fresh_every_loop(tmp_path):
    import shutil
    lua = shutil.which("lua5.2")
    if not lua:
        pytest.skip("lua5.2 not installed")
    sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))
    import relay
    camp = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_campaign.json"),
                          encoding="utf-8"))["ObjectStates"][0]
    books = [o for o in camp["ContainedObjects"] if o["Name"] == "Custom_Model_Bag"]
    book = next(b for b in books if json.loads(b["GMNotes"]).get("id") == "district_church")
    book = json.loads(json.dumps(book))
    book["LuaScript"] = T.loop_box_script()
    chunk = LOOP_BOX_CHUNK % relay.lua_long_string(json.dumps(book, ensure_ascii=False))
    path = tmp_path / "chunk.lua"
    path.write_text(chunk, encoding="utf-8")
    r = subprocess.run([lua, os.path.join(ROOT, "tests", "tts_fake", "mock_tts.lua"), str(path)],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    outs = []
    for ln in r.stdout.splitlines():
        if ln.startswith("@@MSG "):
            msg = json.loads(ln[6:]).get("message", "")
            if msg.startswith("@@OUT "):
                outs.append(msg[6:])
    assert outs, r.stdout[-2000:] + r.stderr[-2000:]
    out = json.loads(outs[-1])
    n = len(book["ContainedObjects"])
    assert out["placed1"] == n and out["placed2"] == n
    assert out["onTable1"] > 0 and out["drawnTagged"] is True
    assert out["onTable2"] == 0, "Recall must remove every placed copy, drawn cards too"
    assert out["boxKept"] is True, "the box never empties"
    assert out["onTable3"] == out["onTable1"]
