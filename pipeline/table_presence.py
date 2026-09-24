#!/usr/bin/env python3
"""table_presence.py — the objects that make the campaign sit on the SCED
table like an official one, each built to the exact schema of the real SCED
object the owner exported (docs/art_reference/sced_objects/):

  minicards      CardCustom, Tags [Minicard], GMNotes {id: <inv>-m, type:
                 Minicard}, scale 0.6, unique back          (minicard.json)
  campaign guide Custom_PDF, Tags [CampaignGuide], GMNotes type CampaignGuide,
                 PDF hosted from dist/guide/                (campaign_guide_pdf.json)
  campaign log   Custom_Token, Tags [CampaignLog], GMNotes type CampaignLog,
                 one State per page, scripted fields        (campaign_log_token.json)
  campaign box   Custom_Model_Bag on SCED's box mesh, Tags [CampaignBox,
                 Reloadable], GMNotes {filename, id, type: CampaignBox}, SCED's
                 MemoryBag script with Place/Recall         (campaign_box_memory_bag.json)
  scenario box   the same memory bag on the small box mesh, GMNotes type
                 ScenarioBox                                (scenario_box_memory_bag.json)

compile_campaign.py puts the scenario boxes into the campaign box built here;
until every scenario is locked in, this module ships the campaign box with the
table-presence objects alone (dist/the_still_hour_table.json), which is also
what the TTS relay spawns to test them.

Image/PDF URLs come from pipeline/art_urls.json (publish_hosted.py writes the
hosted raw.githubusercontent URLs there).

Run: python3 pipeline/table_presence.py      -> dist/the_still_hour_table.json
"""
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_cards as B          # noqa: E402
import campaign_log as L          # noqa: E402

CAMPAIGN = "The Still Hour"
FILENAME = "the_still_hour"        # SCED download key (GMNotes filename)
OUT = os.path.join(ROOT, "dist", "the_still_hour_table.json")
GUIDE_PDF = os.path.join(ROOT, "dist", "guide", "the_still_hour_campaign_guide.pdf")
MEMORY_BAG_LUA = os.path.join(ROOT, "src", "tts", "memory_bag.lua")
BOX_TEXTURE_ID = "sthr-box"

# SCED's own box meshes (src/Global/Global.ttslua meshTable; the same URLs the
# exported campaign/scenario boxes carry) and their scales.
MESH_BIG = ("https://steamusercontent-a.akamaihd.net/ugc/62583916778515295/"
            "AFB8F257CE1E4973F4C06160A2E156C147AEE1E3/")
MESH_SMALL = ("https://steamusercontent-a.akamaihd.net/ugc/62583916778515333/"
              "9F0BE0C211BE3BD1725B4B855F5D3C9C0D020394/")
SCALE_BIG = (1.0, 0.14, 1.0)
SCALE_SMALL = (2.21, 0.46, 2.42)

WHITE = {"r": 1.0, "g": 1.0, "b": 1.0}

# Where Place lays things out: the spots the real campaign box uses
# (campaign_box_memory_bag.json ml): scenario books in a column at x 12.25,
# the log at the lower table edge, the guide at the upper, story decks in a
# row at z -36.385.
PLACE_LOG = {"x": -1.353, "y": 1.581, "z": -26.603}
PLACE_GUIDE = {"x": -1.5, "y": 1.481, "z": 51.0}
PLACE_MINIS = {"x": -0.796, "y": 1.546, "z": -36.385}
CAMPAIGN_BOX_POS = {"x": 63.0, "y": 2.5, "z": 8.0}


def scenario_box_slot(i):
    """Nth scenario book: x 12.25, z 36, 28, 20, ... (the real box's column)."""
    return {"x": 12.25, "y": 1.481, "z": 36.0 - 8.0 * i}


def guid(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]


def transform(pos=None, ry=270, scale=(1.0, 1.0, 1.0)):
    pos = pos or {"x": 0.0, "y": 1.5, "z": 0.0}
    return {"posX": pos["x"], "posY": pos["y"], "posZ": pos["z"],
            "rotX": 0.0, "rotY": float(ry), "rotZ": 0.0,
            "scaleX": scale[0], "scaleY": scale[1], "scaleZ": scale[2]}


def gmnotes(d):
    """SCED's exported objects carry pretty-printed GMNotes (2-space)."""
    return json.dumps(d, indent=2, ensure_ascii=False)


def _common(**kw):
    base = {"AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "LayoutGroupSortIndex": 0, "Value": 0, "Locked": False, "Grid": True,
            "Snap": True, "IgnoreFoW": False, "MeasureMovement": False,
            "DragSelectable": True, "Autoraise": True, "Sticky": True,
            "Tooltip": True, "GridProjection": False, "HideWhenFaceDown": False,
            "Hands": False, "LuaScript": "", "LuaScriptState": "", "XmlUI": ""}
    base.update(kw)
    return base


def _url(key, part="face"):
    v = B.ART_URLS.get(key)
    if isinstance(v, dict):
        return v.get(part) or ""
    return v or ""


# ------------------------------------------------------------- minicards --
def investigator_specs():
    spec = json.load(open(os.path.join(HERE, "stillhour_cards_spec.json"), encoding="utf-8"))
    return [c for c in spec if c.get("type") == "Investigator"]


def minicard_deck_id(mid):
    return 99000 + int(guid("minicard:" + mid), 16) % 900


def build_minicard(inv):
    mid = inv["id"] + "-m"
    deck = str(minicard_deck_id(mid))
    face = _url(mid, "face") or B.face_ph(inv["name"] + " (mini)")
    back = _url(mid, "back") or B.face_ph(inv["name"] + " (mini back)")
    return _common(
        GUID=guid(mid), Name="CardCustom",
        Transform=transform(ry=180, scale=(0.6, 1.0, 0.6)),
        Nickname=inv["name"], Description="",
        GMNotes=gmnotes({"id": mid, "type": "Minicard"}),
        ColorDiffuse=dict(B.COLOR_DIFFUSE), Tags=["Minicard"],
        Snap=False, HideWhenFaceDown=True, Hands=True,
        CardID=int(deck + "00"), SidewaysCard=False,
        CustomDeck={deck: {"FaceURL": face, "BackURL": back, "NumWidth": 1,
                           "NumHeight": 1, "BackIsHidden": True,
                           "UniqueBack": True, "Type": 0}},
    )


def build_minicard_deck(pos=None):
    cards = [build_minicard(c) for c in investigator_specs()]
    custom = {}
    for c in cards:
        custom.update(c["CustomDeck"])
    return _common(
        GUID=guid("deck:minicards"), Name="Deck",
        Transform=transform(pos, ry=270, scale=(0.6, 1.0, 0.6)),
        Nickname="Investigator Minicards", Description=CAMPAIGN,
        GMNotes="", ColorDiffuse=dict(B.COLOR_DIFFUSE), Tags=["Minicard"],
        Hands=False, SidewaysCard=False,
        DeckIDs=[c["CardID"] for c in cards], CustomDeck=custom,
        ContainedObjects=cards,
    )


# ---------------------------------------------------------------- guide --
def guide_url():
    url = _url("_campaign_guide")
    if url:
        return url
    if os.path.exists(GUIDE_PDF):
        return "file:///" + GUIDE_PDF.replace(os.sep, "/").lstrip("/")
    return ""


def build_guide(pos=None):
    return _common(
        GUID=guid("guide:the_still_hour"), Name="Custom_PDF",
        Transform=transform(pos, ry=270, scale=(2.2, 1.0, 2.2)),
        Nickname=CAMPAIGN + " - Campaign Guide", Description="",
        GMNotes=gmnotes({"id": "STHR-CG", "type": "CampaignGuide"}),
        ColorDiffuse=dict(WHITE), Tags=["CampaignGuide"],
        CustomPDF={"PDFUrl": guide_url(), "PDFPassword": "", "PDFPage": 0,
                   "PDFPageOffset": 0},
    )


# ------------------------------------------------------------------ log --
def _log_state(page, pos=None):
    pid = L.PAGE_IDS[page - 1]
    url = _url(pid) or B.face_ph("Campaign Log page {}".format(page))
    return _common(
        GUID=guid("campaignlog:page{}".format(page)), Name="Custom_Token",
        Transform=transform(pos, ry=270, scale=(3.4, 1.0, 3.4)),
        Nickname=CAMPAIGN + " - Campaign Log", Description="Page {}".format(page),
        GMNotes=gmnotes({"id": "{}{}".format(L.LOG_ID, page), "type": "CampaignLog"}),
        ColorDiffuse=dict(WHITE), Tags=["CampaignLog"],
        CustomImage={"ImageURL": url, "ImageSecondaryURL": "", "ImageScalar": 1.0,
                     "WidthScale": 0.0,
                     "CustomToken": {"Thickness": 0.2, "MergeDistancePixels": 15.0,
                                     "StandUp": False, "Stackable": False}},
        LuaScript=L.lua_script(page),
    )


def build_log(pos=None):
    log = _log_state(1, pos)
    states = {}
    for page in range(2, len(L.PAGE_IDS) + 1):
        st = _log_state(page, {"x": 0.0, "y": 0.0, "z": 0.0})
        states[str(page)] = st
    log["States"] = states
    return log


# ---------------------------------------------------------------- boxes --
def memory_bag_script():
    return open(MEMORY_BAG_LUA, encoding="utf-8").read()


def _mesh(url):
    return {"MeshURL": url, "DiffuseURL": _url(BOX_TEXTURE_ID), "NormalURL": "",
            "ColliderURL": "", "Convex": True, "MaterialIndex": 3, "TypeIndex": 6,
            "CustomShader": {"SpecularColor": dict(WHITE), "SpecularIntensity": 0.0,
                             "SpecularSharpness": 2.0, "FresnelStrength": 0.0},
            "CastShadows": True}


def ml_entry(pos, ry=270, rz=0):
    return {"lock": False, "pos": {k: round(float(v), 3) for k, v in pos.items()},
            "rot": {"x": 0, "y": ry, "z": rz}}


def memory_bag(name, gm, tags, mesh, scale, contained, ml, desc=""):
    box = _common(
        GUID=guid("box:" + gm.get("id", name)), Name="Custom_Model_Bag",
        Transform=transform(scale=scale), Nickname=name, Description=desc,
        GMNotes=gmnotes(gm) if gm.get("type") == "ScenarioBox" else
        json.dumps(gm, separators=(",", ":")),
        ColorDiffuse=dict(WHITE), Snap=True, MaterialIndex=-1, MeshIndex=-1,
        CustomMesh=_mesh(mesh), Bag={"Order": 0},
        LuaScript=memory_bag_script(),
        LuaScriptState=json.dumps({"ml": ml}, indent=2),
        ContainedObjects=contained,
    )
    if tags:
        box["Tags"] = list(tags)
    return box


def scenario_box(name, sid, contained, ml):
    """A scenario book: SCED's small box mesh + memory bag (Tags: none, as
    the exported scenario boxes have none; GMNotes {id, type: ScenarioBox})."""
    return memory_bag(name, {"id": sid, "type": "ScenarioBox"}, None,
                      MESH_SMALL, SCALE_SMALL, contained, ml)


def campaign_box(scenario_boxes=(), name=CAMPAIGN, filename=FILENAME,
                 box_id="CB-STHR", table=True):
    """The campaign box: scenario books (+ for The Still Hour: minicards, log,
    guide), each with a Place spot. Returns the Custom_Model_Bag object."""
    contained, ml = [], {}
    for i, sb in enumerate(scenario_boxes):
        sb = copy.deepcopy(sb)
        pos = scenario_box_slot(i)
        sb["Transform"] = transform(pos, 270, SCALE_SMALL)
        contained.append(sb)
        ml[sb["GUID"]] = ml_entry(pos)
    if table:
        for obj, pos in ((build_minicard_deck(PLACE_MINIS), PLACE_MINIS),
                         (build_log(PLACE_LOG), PLACE_LOG),
                         (build_guide(PLACE_GUIDE), PLACE_GUIDE)):
            contained.append(obj)
            ml[obj["GUID"]] = ml_entry(pos)
    box = memory_bag(name, {"filename": filename, "id": box_id,
                            "type": "CampaignBox"},
                     ["CampaignBox", "Reloadable"], MESH_BIG, SCALE_BIG,
                     contained, ml, desc="fan campaign — not for sale")
    # where it appears when spawned: the campaign-box area at the top of the
    # SCED table (the official box sits at x 63, z 16), beside it, dropping in
    # from above the surface — never on the scenario mat at the origin
    box["Transform"] = transform(CAMPAIGN_BOX_POS, 270, SCALE_BIG)
    return box


# ------------------------------------------------------------ box texture --
def render_box_texture(dest=None):
    """The box art on the plugin's BoxCover template (BoxCover.js paint
    order: portrait, the tinted band, the template, the name). Portrait = the
    campaign banner art; band re-hued from the template's red to night blue."""
    from PIL import Image, ImageDraw
    import render_placeholders as rp
    dest = dest or os.path.join(ROOT, "art", "faces", BOX_TEXTURE_ID + ".png")
    tdir = os.path.join(ROOT, "assets", "frames", "se", "templates")
    tpl = Image.open(os.path.join(tdir, "AHLCG-BoxCover.png")).convert("RGBA")
    band = Image.open(os.path.join(tdir, "AHLCG-BoxCoverTintable.png")).convert("RGBA")
    img = Image.new("RGBA", tpl.size, (8, 8, 14, 255))
    banner = os.path.join(ROOT, "assets", "branding", "banner.png")
    for x, y, w, h in ((420, 733, 781, 347), (1630, 420, 785, 785)):
        if os.path.exists(banner):
            rp.paste_cover(img, os.path.relpath(banner, ROOT), (x, y, x + w, y + h))
    hsv = band.convert("RGB").convert("HSV")
    hch, s, v = hsv.split()
    hch = hch.point(lambda _: 168)                      # ~0.66 turn: indigo
    s = s.point(lambda x: int(x * 0.55))
    v = v.point(lambda x: int(x * 0.8))
    band = Image.merge("RGBA", (*Image.merge("HSV", (hch, s, v)).convert("RGB").split(),
                                band.getchannel("A")))
    img.alpha_composite(band, (420, 420))
    img.alpha_composite(tpl)
    d = ImageDraw.Draw(img)
    rp._box_text(d, CAMPAIGN, (425, 1110, 425 + 767, 1110 + 53), title=True,
                 fill=(255, 255, 255), grow=1.2, max_size=80)
    img.convert("RGB").save(dest)
    return dest


# ------------------------------------------------------------------ main --
def build(out=OUT):
    box = campaign_box()
    # the table-presence-only box sits one box-width over from the compiled
    # campaign box: the relay spawns both, and two memory bags dropped on the
    # same spot put one inside the other
    box["Transform"]["posZ"] = CAMPAIGN_BOX_POS["z"] - 8.0
    save = {"SaveName": CAMPAIGN, "GameMode": CAMPAIGN, "ObjectStates": [box]}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(save, f, indent=2, ensure_ascii=False)
    d = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    kinds = sorted(o["Name"] for o in d["ContainedObjects"])
    return {"out": os.path.relpath(out, ROOT), "objects": kinds,
            "minicards": len(box["ContainedObjects"][0]["ContainedObjects"]),
            "log_pages": 1 + len(box["ContainedObjects"][1]["States"]),
            "guide_url": box["ContainedObjects"][2]["CustomPDF"]["PDFUrl"]}


def main():
    print(json.dumps(build(), indent=2))


if __name__ == "__main__":
    main()
