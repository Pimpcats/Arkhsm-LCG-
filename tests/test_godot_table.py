"""The Godot table renderer's data path (tools/godot_table, docs/GODOT_TABLE.md).

Fast checks only: the harness's table snapshots (on the SCED stand-in), the
asset collection, the TTS camera conversion and the XML UI layout rules the
renderer was calibrated with. Rendering itself needs Godot and Xvfb and runs
only with GODOT_TABLE=1 (it downloads assets). Nothing here writes into the
repository.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))
sys.path.insert(0, os.path.join(ROOT, "tools", "godot_table"))

import run as harness  # noqa: E402
import fetch_assets  # noqa: E402
import render  # noqa: E402
import ui_overlay  # noqa: E402

LUA = shutil.which("lua5.2") or shutil.which("lua5.4")


def _porcelain():
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def stand_in_snapshots():
    if not LUA:
        pytest.skip("no lua5.2 / lua5.4")
    before = _porcelain()
    tmp = tempfile.mkdtemp(prefix="godot_snap_")
    try:
        r = harness.run(os.path.basename(LUA), "playthrough", fake=True, snapshots=tmp)
        files = sorted(glob.glob(os.path.join(tmp, "*.json")))
        data = [json.load(open(f)) for f in files]
        yield r, files, data
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        assert _porcelain() == before, "the snapshot run changed tracked files"


def test_a_snapshot_after_boot_and_every_step(stand_in_snapshots):
    r, files, data = stand_in_snapshots
    steps = [c for c in r["checks"] if c["name"].endswith(": no Lua errors (campaign or SCED)")]
    assert len(files) == len(steps) + 1, (len(files), len(steps))
    assert [s["index"] for s in r["snapshots"]] == list(range(len(files)))
    assert data[0]["meta"]["label"] == "the bare table after boot"


def test_snapshot_objects_carry_what_the_renderer_needs(stand_in_snapshots):
    _r, _files, data = stand_in_snapshots
    last = data[-1]
    objs = last["objects"]
    assert objs and all(len(o["pos"]) == 3 and len(o["rot"]) == 3 and len(o["scale"]) == 3 for o in objs)
    cards = [o for o in objs if o["name"] in ("Card", "CardCustom")]
    decks = [o for o in objs if o["type"] == "Deck"]
    assert cards and all((o["card"].get("CustomDeck") or {}).get("FaceURL") for o in cards)
    assert decks and all(d["deck"]["count"] >= 2 and d["deck"]["top"]["CustomDeck"] for d in decks)
    with_buttons = [o for o in objs if o.get("buttons")]
    assert with_buttons
    b = with_buttons[0]["buttons"][0]
    assert set(b) >= {"label", "position", "rotation", "scale", "width", "height", "font_size", "color", "font_color"}
    # scripts, script states and GM notes stay out of snapshots
    blob = json.dumps(last)
    assert "LuaScript" not in blob and "GMNotes" not in blob


def test_assets_collected_per_card_cell(tmp_path):
    snap = {"objects": [{"card": {"CardID": 12345, "CustomDeck": {
        "FaceURL": "{verifycache}http://cloud-3.steamusercontent.com/ugc/1/A/", "BackURL": "https://x/back.png",
        "NumWidth": 10, "NumHeight": 7, "UniqueBack": False}}},
        {"image": {"ImageURL": "https://x/tile.png", "ImageSecondaryURL": ""}},
        {"mesh": {"MeshURL": "https://x/m.obj", "DiffuseURL": "https://x/d.png"}},
        {"bundle": {"AssetbundleURL": "https://x/b.unity3d"}}]}
    p = tmp_path / "000.json"
    p.write_text(json.dumps(snap))
    need = fetch_assets.collect([str(p)])
    # CardID 12345: deck 123, cell 45 of the 10x7 sheet; old Steam host mapped
    assert need["crop"] == {("https://steamusercontent-a.akamaihd.net/ugc/1/A/", 10, 7, 45)}
    assert need["image"] == {"https://x/back.png", "https://x/tile.png", "https://x/d.png"}
    assert need["mesh"] == {"https://x/m.obj"} and need["bundle"] == {"https://x/b.unity3d"}


def test_camera_state_matches_tts_absolute_position():
    cs = {"Position": {"x": -22.26, "y": -2.5, "z": 5.26}, "Rotation": {"x": 64.34, "y": 90, "z": 0},
          "Distance": 104}
    cam = render.camera_state(cs)
    # TTS stores the eye as AbsolutePosition: (-67.6, 91.88, 5.52) for this state
    assert abs(cam["eye"][0] + 67.35) < 0.5 and abs(cam["eye"][1] - 91.2) < 1.0 and abs(cam["eye"][2] - 5.26) < 0.1


def test_xml_ui_layout_rules():
    xml = [{"tag": "Defaults", "children": [{"tag": "Button", "attributes": {"class": "nav", "color": "#000000"}}]},
           {"tag": "VerticalLayout", "attributes": {"rectAlignment": "LowerRight", "width": "800", "height": "1600",
                                                    "scale": "0.05 0.05 1", "offsetXY": "-1 80", "padding": "75 75 75 75"},
            "children": [{"tag": "Button", "attributes": {"class": "nav"}},
                         {"tag": "Button", "attributes": {"class": "nav"}}]},
           {"tag": "Panel", "attributes": {"active": "false", "width": "100", "height": "100"}},
           {"tag": "Panel", "attributes": {"visibility": "Black", "width": "100", "height": "100"}},
           {"tag": "Panel", "attributes": {"width": "200", "height": "100", "rotation": "0 0 180"},
            "children": [{"tag": "Text", "attributes": {"width": "50", "height": "20", "rectAlignment": "UpperLeft"},
                          "value": "x"}]}]
    boxes = ui_overlay.Layout(xml).run()
    tags = [b.tag for b in boxes]
    assert tags == ["VerticalLayout", "Button", "Button", "Panel", "Text"]   # hidden panels skipped
    vl = boxes[0].rect
    # 800x1600 scaled 0.05 = 40x80, anchored bottom-right, 80 up, 1 left
    assert [round(v) for v in vl] == [1879, 920, 1919, 1000]
    b1, b2 = boxes[1].rect, boxes[2].rect
    assert round(b1[3] - b1[1]) == 36 and round(b1[1]) == 924 and round(b2[1]) == 960
    assert ui_overlay.parse_color(boxes[1].a.get("color")) == (0, 0, 0, 255)
    # a 180-degree turn point-reflects the subtree: upper-left becomes lower-right
    panel, text = boxes[3].rect, boxes[4].rect
    assert round(text[2]) == round(panel[2]) and round(text[3]) == round(panel[3]) and boxes[4].flip


@pytest.mark.skipif(os.environ.get("GODOT_TABLE") != "1" or not render.find_godot() or not shutil.which("xvfb-run"),
                    reason="set GODOT_TABLE=1 (needs Godot 4, Xvfb and network for the assets)")
def test_godot_renders_the_stand_in(stand_in_snapshots, tmp_path):
    _r, files, _data = stand_in_snapshots
    snapdir = tmp_path / "snaps"
    snapdir.mkdir()
    shutil.copy(files[-1], snapdir / "000.json")
    save = tmp_path / "save.json"
    save.write_text(json.dumps({"CameraStates": [], "Lighting": {}}))
    out = tmp_path / "out"
    rc = render.main(["--save", str(save), "--snapshots", str(snapdir), "--cameras", "top", "--out", str(out),
                      "--width", "640", "--height", "360"])
    assert rc == 0 and (out / "000_top.png").is_file()
