"""A minimal SCED table for the fake TTS (tests only).

Returns the list of objects mock_tts.lua loads before running a chunk: SCED's
Global (tests/tts_fake/sced/Global.lua, as the "__Global__" pseudo-object), the
GUID reference handler at SCED's fixed GUID 123456, the Mythos objects its APIs
resolve (PlayArea, TokenSpawnTracker, InvestigatorCounter), one playermat (a
Still Hour investigator active on it) with its skill tracker, a campaign log and a
chaos bag holding ordinary SCED tokens (Custom_Tile, named like ID_URL_MAP)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def _scripts():
    text = open(os.path.join(HERE, "sced", "objects.lua"), encoding="utf-8").read()
    parts = re.split(r"^--@@ (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def _obj(name, nickname, guid, script="", tags=(), x=0.0, z=0.0, **extra):
    o = {"Name": name, "Nickname": nickname, "GUID": guid, "Tags": list(tags),
         "Transform": {"posX": x, "posY": 1, "posZ": z, "rotX": 0, "rotY": 0, "rotZ": 0},
         "LuaScript": script, "LuaScriptState": ""}
    o.update(extra)
    return o


def _token(nick, guid):
    return {"Name": "Custom_Tile", "Nickname": nick, "GUID": guid,
            "CustomImage": {"ImageURL": "https://example.invalid/t.png",
                            "CustomTile": {"Type": 2, "Thickness": 0.1, "Stretch": True}}}


def sced_table():
    s = _scripts()
    glob = open(os.path.join(HERE, "sced", "Global.lua"), encoding="utf-8").read()
    tokens = [_token(n, "cbt%03d" % i) for i, n in enumerate(
        ["+1", "0", "0", "-1", "-1", "-2", "-3", "Skull", "Skull", "Cultist", "Auto-fail", "Elder Sign"])]
    return [
        {"Name": "__Global__", "LuaScript": glob},
        _obj("BlockSquare", "GUID Reference Handler", "123456", s["GUIDReferenceHandler"], x=-60),
        _obj("Custom_Tile", "Play Area", "5ce0a1", s["PlayArea"], x=-30, z=0, Locked=True),
        _obj("Custom_Tile", "Token Spawn Tracker", "e3fa31", s["TokenSpawnTracker"], x=-60, z=5),
        _obj("Custom_Tile", "Investigator Counter", "f182ee", s["InvestigatorCounter"], x=-60, z=8),
        _obj("Custom_Tile", "White Playermat", "8b081b", s["Playermat"], tags=["Playermat"], x=-20, z=-25),
        _obj("Custom_Tile", "White Skill Tracker", "e598c2", s["InvestigatorSkillTracker"], x=-20, z=-30),
        _obj("Custom_Token", "Campaign Log", "c10901", tags=["CampaignLog"], x=-50, z=20,
             GMNotes='{"id":"STHR-LOG","type":"CampaignLog"}'),
        _obj("Bag", "Chaos Bag", "cb0001", tags=["ChaosBag"], x=-8, z=12,
             ContainedObjects=tokens),
    ]
