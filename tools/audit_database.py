#!/usr/bin/env python3
"""audit_database.py - structural audit of the shipped TTS / SCED "database".

What it audits
    The Tabletop Simulator objects this repository ships (dist/): the Saved
    Object the owner loads, the download-box release asset and placeholder, the
    mod / campaign / table / starter saves, the hosted card images they point
    at and every Lua script embedded in them.  It checks them against what
    Tabletop Simulator (TTS) and the Arkham Horror LCG mod (SCED) expect, using
    the official data as ground truth when it is available locally.

Checks (finding codes start with the letter)
    A  TTS object invariants on every object tree: JSON hygiene, required
       keys per object Name, Deck/Card/CustomDeck consistency, URLs, GUIDs,
       Transform/ColorDiffuse, tags, texts, memory-bag `ml` lists, null /
       empty-container / number-type hazards for a Lua JSON round trip,
       deck-id <-> image mapping, SCED norms for card flags and scale.
    B  Image budget per Place (a box's Place spawns its memory-list children):
       distinct image URLs, CustomDeck ids, sheets per Deck, decoded texture
       memory, compared with the official boxes' distribution.
    C  Hosted image files: exist, valid JPEG, baseline vs progressive, colour
       model, EXIF, size, aspect; the pinned raw.githubusercontent.com commit
       holds the identical bytes (git), is reachable from a remote ref and, with
       --online, answers HTTP HEAD.
    D  SCED data model: GMNotes parsed and compared with the official key sets,
       value types and vocabulary per card type (id/type/class/slot/traits/
       cycle/icons, Location connections), ids vs the official ids, tags vs the
       tags SCED code treats specially.
    E  Lua: every LuaScript extracted and syntax-checked (luac 5.2 and 5.4 when
       installed), API use that TTS lacks, top-level globals, undefined global
       reads, scripts on objects inside bags, sizes, freshness against src/.
    F  Consistency between the shipped files (same cards / ids / images / box
       scripts) and the placeholder download box against SCED's placeholder.
    G  Everything else (tag/GUID collisions with SCED, URL cache-name length,
       file-level hygiene, ...).

Severity policy
    ERROR  the data breaks a TTS/SCED invariant that holds for every official
           object (or contradicts itself): a crash, a corrupted object, a wrong
           or missing image, or a value SCED code cannot read.  Exit code 1.
    WARN   a deviation from the official norm or a risk that cannot be proven
           from here (format and size choices, stale builds, unused fields).
    INFO   statistics, vocabulary notes and expected differences.
    Calibration: the A-rules were run over the 38 official boxes and the 4.9.2 save.  DeckIDs == contained
    CardIDs and "a card's CustomDeck is its own sheet" fail for 2 decks and 22 cards of ~13,000 official
    objects; the one-image-per-deck-id and one-CardID-per-card rules (A10) fail all over official data (sheets
    are reprinted and re-uploaded) but are certain defects for this campaign's one-card-per-sheet data.

Usage
    python3 tools/audit_database.py                  # default dist/ targets
    python3 tools/audit_database.py dist/foo.json --json
    python3 tools/audit_database.py --reference .cache/official --online

    Targets default to dist/saved_object_*.json, dist/downloads/*.json and
    dist/*.json.  --reference DIR (repeatable) names directories that hold the
    official data (tts_menu/*.json + library.json, sced_4.9.2/*.json, and/or a
    SCED checkout with src/); .cache/official and .cache/sced are used when
    present.  Without them the reference-dependent checks are skipped (INFO).
    Output is deterministic; network access happens only with --online.
    Exit status: 1 when any ERROR is reported (or any WARN with --strict),
    2 on usage errors, else 0.

Standard library only (no PIL: JPEG headers are parsed here).
"""
import argparse
import collections
import concurrent.futures
import glob
import hashlib
import json
import math
import os
import re
import shutil
import ssl
import statistics
import struct
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"
SEV_RANK = {ERROR: 0, WARN: 1, INFO: 2}
CHECK_TITLES = {
    "A": "TTS object invariants",
    "B": "Image budget per Place",
    "C": "Hosted image files and pinned commit",
    "D": "SCED data model (GMNotes, tags, ids)",
    "E": "Lua scripts",
    "F": "Consistency between shipped files",
    "G": "Other",
}

# --------------------------------------------------------------------------
# Constants describing TTS / SCED expectations
# --------------------------------------------------------------------------
INT32_MAX = 2 ** 31 - 1
LUA_SAFE_INT = 2 ** 53
TTS_MAX_GRID = (10, 7)                  # TTS custom decks: at most 10 x 7 cells
GUID_RE = re.compile(r"^[0-9a-f]{6}$")
TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")     # every official tag matches
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
TRAITS_RE = re.compile(r"^([^.]+\.)( [^.]+\.)*$")
ICON_TOKEN_RE = re.compile(r"^[A-Za-z]+(\|[A-Za-z]+)*$")   # SCED matches %a+

# Names TTS/SCED objects use (official boxes + the 4.9.2 save + common TTS ones)
KNOWN_NAMES = frozenset("""
Card CardCustom Deck Bag Infinite_Bag Custom_Model_Bag Custom_Model_Infinite_Bag
Custom_Model Custom_Token Custom_Token_Stack Custom_Tile Custom_PDF Custom_Board
Custom_Assetbundle Custom_Dice Custom_AssetBundle BlockSquare BlockRectangle
Notecard 3DText ScriptingTrigger HandTrigger FogOfWarTrigger Checker_white
Checker_black go_game_piece_white go_game_piece_black Chinese_Checkers_Piece
backgammon_piece_white backgammon_piece_brown Figurine_Custom Tileset_Custom
Digital_Clock Counter Tablet Quarter Die_6 Die_6_Rounded
""".split())

# keys whose JSON type TTS (and a Lua JSON round trip) depends on
FIELD_TYPES = {
    "Name": str, "Nickname": str, "Description": str, "GMNotes": str, "GUID": str,
    "LuaScript": str, "LuaScriptState": str, "XmlUI": str, "Memo": str,
    "Locked": bool, "Grid": bool, "Snap": bool, "IgnoreFoW": bool,
    "MeasureMovement": bool, "DragSelectable": bool, "Autoraise": bool,
    "Sticky": bool, "Tooltip": bool, "GridProjection": bool,
    "HideWhenFaceDown": bool, "Hands": bool, "SidewaysCard": bool,
    "Value": int, "LayoutGroupSortIndex": int, "CardID": int,
    "MaterialIndex": int, "MeshIndex": int,
    "Tags": list, "DeckIDs": list, "ContainedObjects": list, "CustomUIAssets": list,
    "Transform": dict, "ColorDiffuse": dict, "AltLookAngle": dict, "CustomDeck": dict,
    "CustomMesh": dict, "CustomImage": dict, "CustomPDF": dict, "Bag": dict,
    "States": dict,
}
# what a spawned object of this Name needs in order to exist at all
REQUIRED_KEYS = {
    "Card": ("GUID", "Name", "CardID", "CustomDeck"),
    "CardCustom": ("GUID", "Name", "CardID", "CustomDeck"),
    "Deck": ("GUID", "Name", "DeckIDs", "CustomDeck", "ContainedObjects"),
    "Custom_Model": ("GUID", "Name", "CustomMesh"),
    "Custom_Model_Bag": ("GUID", "Name", "CustomMesh"),
    "Custom_Model_Infinite_Bag": ("GUID", "Name", "CustomMesh"),
    "Custom_Token": ("GUID", "Name", "CustomImage"),
    "Custom_Tile": ("GUID", "Name", "CustomImage"),
    "Custom_Board": ("GUID", "Name", "CustomImage"),
    "Custom_PDF": ("GUID", "Name", "CustomPDF"),
}
URL_KEYS_REQUIRED = {"FaceURL", "BackURL", "ImageURL", "MeshURL", "PDFUrl"}
URL_KEYS_OPTIONAL = {"ImageSecondaryURL", "DiffuseURL", "NormalURL", "ColliderURL"}
URL_KEYS = URL_KEYS_REQUIRED | URL_KEYS_OPTIONAL
IMAGE_URL_KEYS = {"FaceURL", "BackURL", "ImageURL", "ImageSecondaryURL", "DiffuseURL", "NormalURL"}
# Hosts we expect: our own pinned GitHub raw URLs and SCED's Steam assets
HOST_FAMILIES = {
    "raw.githubusercontent.com": "github-raw",
    "steamusercontent-a.akamaihd.net": "steam",
    "cloud-3.steamusercontent.com": "steam",
    "steamusercontent-a.akamaihd.net:443": "steam",
}
PLACEHOLDER_HOSTS = ("placehold.co", "via.placeholder.com", "example.com")

# Lua: things TTS (MoonSharp, Lua 5.2 flavoured) does not give a script
LUA_FORBIDDEN_CALLS = {
    "io": "the io library is not available in TTS",
    "package": "package.* is not available in TTS",
    "debug": "the debug library is not available in TTS",
    "dofile": "dofile does not exist in TTS",
    "loadfile": "loadfile does not exist in TTS",
    "utf8": "utf8 is Lua 5.3+; MoonSharp has no utf8 library",
}
LUA_FORBIDDEN_OS = ("execute", "exit", "getenv", "remove", "rename", "tmpname", "setlocale")
LUA_53_LIBS = (("string", ("pack", "unpack", "packsize")),
               ("table", ("move",)),
               ("math", ("tointeger", "type", "ult")))
# globals TTS (and Lua 5.2) provide to an object script; used to spot typos and
# calls to things that only exist in other scripts' scope (e.g. SCED's GlobalApi)
TTS_API_GLOBALS = frozenset("""
_G _ENV _VERSION assert collectgarbage error getmetatable ipairs load loadstring next
pairs pcall print rawequal rawget rawlen rawset require select setmetatable tonumber
tostring type unpack xpcall bit32 coroutine math os string table
self Global JSON Wait Player Physics Time Turns Hands Notes Lighting Grid Backgrounds Tables
Info UI WebRequest Color Vector MusicPlayer Timer Counter Clock RPGFigurine TextTool Behavior
addContextMenuItem broadcastToAll broadcastToColor clearContextMenu copy destroyObject dump
flipTable getAllObjects getObjectFromGUID getObjects getObjectsWithAllTags
getObjectsWithAnyTags getObjectsWithTag getSeatedPlayers group log logStyle logString
paste printToAll printToColor sendExternalMessage setLookingForPlayers spawnObject
spawnObjectData spawnObjectJSON startLuaCoroutine stopLuaCoroutine stringColorToRGB
""".split())
# event handlers TTS calls on a script that defines them
TTS_EVENTS = frozenset("""
onLoad onSave onUpdate onFixedUpdate onDestroy onCollisionEnter onCollisionExit
onCollisionStay onObjectDestroy onObjectDrop onObjectPickUp onObjectSpawn onObjectRotate
onObjectFlick onObjectNumberTyped onObjectLeaveContainer onObjectEnterContainer
onObjectEnterZone onObjectLeaveZone onObjectSearchStart onObjectSearchEnd onObjectHover
onObjectStateChange onObjectRandomize onPlayerAction onPlayerChangeColor onPlayerConnect
onPlayerDisconnect onPlayerPing onPlayerTurn onPlayerChangeTeam onChat onExternalMessage
onScriptingButtonDown onScriptingButtonUp onBlindfold onZoneGroupSort tryObjectEnterContainer
tryObjectRandomize tryObjectRotate tryObjectStateChange onObjectPageChange
onGroupDrop onPlayerHoverObject onObjectTriggerEffect onObjectLoopingEffect
""".split())
TTS_GLOBALS = TTS_API_GLOBALS | TTS_EVENTS
# object-script event hooks TTS calls every frame: costly if defined on bag contents
LUA_FRAME_HOOKS = ("onUpdate", "onFixedUpdate")

DEFAULT_REFERENCE_DIRS = (".cache/official", ".cache/sced")
OFFICIAL_AUTHOR = "Fantasy Flight Games"


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------
class Finding(object):
    """One audit result."""
    __slots__ = ("severity", "check", "code", "where", "message", "evidence",
                 "fix", "count", "locations")

    def __init__(self, severity, code, where, message, evidence="", fix="",
                 count=1, locations=None):
        self.severity = severity
        self.code = code
        self.check = code[:1]
        self.where = where
        self.message = message
        self.evidence = evidence
        self.fix = fix
        self.count = count
        self.locations = list(locations or [])

    def to_dict(self):
        return {"severity": self.severity, "check": self.check, "code": self.code,
                "where": self.where, "message": self.message,
                "evidence": self.evidence, "fix": self.fix, "count": self.count,
                "locations": self.locations}

    def sort_key(self):
        return (SEV_RANK[self.severity], self.code, self.where, self.message)


class Group(object):
    """Many hits of one rule, reported as one finding with a count."""
    MAX_LOCS = 8
    MAX_EVID = 3

    def __init__(self, severity, code, message, fix=""):
        self.severity, self.code, self.message, self.fix = severity, code, message, fix
        self.count = 0
        self.locs = []
        self.evid = []

    def hit(self, where, evidence=None):
        self.count += 1
        if len(self.locs) < self.MAX_LOCS:
            self.locs.append(where)
        if evidence is not None and len(self.evid) < self.MAX_EVID \
                and str(evidence) not in self.evid:
            self.evid.append(str(evidence))
        return self

    def finding(self):
        return Finding(self.severity, self.code, self.locs[0] if self.locs else "",
                       self.message, "; ".join(self.evid), self.fix, self.count,
                       self.locs[1:])


class Report(object):
    def __init__(self):
        self.findings = []
        self.stats = collections.OrderedDict()
        self.notes = []                      # skipped checks and similar
        self._groups = collections.OrderedDict()

    def add(self, severity, code, where, message, evidence="", fix="", count=1,
            locations=None):
        self.findings.append(Finding(severity, code, where, message, evidence, fix,
                                     count, locations))

    def group(self, severity, code, message, fix=""):
        key = (severity, code, message)
        g = self._groups.get(key)
        if g is None:
            g = self._groups[key] = Group(severity, code, message, fix)
        return g

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def finish(self):
        for g in self._groups.values():
            if g.count:
                self.findings.append(g.finding())
        self._groups.clear()
        self.findings.sort(key=Finding.sort_key)
        return self

    def counts(self):
        c = collections.Counter(f.severity for f in self.findings)
        return {ERROR: c[ERROR], WARN: c[WARN], INFO: c[INFO]}

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def has_errors(self):
        return any(f.severity == ERROR for f in self.findings)

    def to_dict(self):
        return {"summary": self.counts(), "notes": self.notes,
                "findings": [f.to_dict() for f in self.findings],
                "stats": self.stats}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def is_num(v):
    """A finite JSON number (not a bool)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def hk(v):
    """A hashable stand-in for any JSON value (malformed data must not crash the audit)."""
    try:
        hash(v)
        return v
    except TypeError:
        try:
            return json.dumps(v, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return repr(v)


def tname(v):
    return "null" if v is None else type(v).__name__


def short(v, n=60):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 3] + "..."


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def dist_line(vals):
    """min / median / p90 / max of a list of numbers."""
    if not vals:
        return "n/a"
    v = sorted(vals)
    med = statistics.median(v)
    med = int(med) if float(med).is_integer() else round(med, 1)
    return "min %s / median %s / p90 %s / max %s" % (v[0], med, pct(v, 0.9), v[-1])


def fnum(x):
    """1.0 -> 1, 2.5 -> 2.5"""
    return int(x) if isinstance(x, float) and x.is_integer() else x


def dist_dict(vals):
    if not vals:
        return {}
    v = sorted(vals)
    return {"n": len(v), "min": v[0], "median": fnum(statistics.median(v)),
            "p90": pct(v, 0.9), "max": v[-1]}


def mib(n):
    return "%.0f MiB" % (n / 1048576.0)


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def rel(path, root):
    try:
        r = os.path.relpath(path, root)
    except ValueError:
        return path
    return path if r.startswith("..") else r.replace(os.sep, "/")


def try_json(s):
    try:
        return True, json.loads(s)
    except (ValueError, TypeError):
        return False, None


def parse_gmnotes(obj):
    """(ok, dict|None, raw) for an object's GMNotes."""
    raw = obj.get("GMNotes")
    if not isinstance(raw, str) or not raw.strip():
        return False, None, raw
    ok, val = try_json(raw)
    return ok, (val if isinstance(val, dict) else None), raw


def kids(o):
    """Dict children of an object's ContainedObjects (empty when it is missing or malformed)."""
    cs = o.get("ContainedObjects") if isinstance(o, dict) else None
    return [c for c in cs if isinstance(c, dict)] if isinstance(cs, list) else []


def taglist(o):
    """String tags of an object (empty when Tags is missing or malformed)."""
    t = o.get("Tags") if isinstance(o, dict) else None
    return [x for x in t if isinstance(x, str)] if isinstance(t, list) else []


# --------------------------------------------------------------------------
# JSON loading with the hygiene checks a plain json.load would hide
# --------------------------------------------------------------------------
class Loaded(object):
    def __init__(self, name, data, raw_size=0, problems=None):
        self.name = name
        self.data = data
        self.raw_size = raw_size
        self.problems = problems or []     # (severity, code, message, evidence)


def load_json_file(path, name):
    """Parse path; report duplicate keys, NaN/Infinity and BOM like TTS would see."""
    problems = []
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        return Loaded(name, None, 0, [(ERROR, "A00.read", "cannot read file", str(e))])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return Loaded(name, None, len(raw), [(ERROR, "A00.encoding", "file is not valid UTF-8", str(e))])
    if text.startswith("﻿"):
        problems.append((WARN, "A00.bom", "file starts with a UTF-8 byte order mark",
                         "TTS reads it, Lua/JSON tooling often does not"))
        text = text[1:]
    dups, consts = [], []

    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                dups.append(k)
            d[k] = v
        return d

    def const(tok):
        consts.append(tok)
        return float("nan") if tok == "NaN" else (float("inf") if tok == "Infinity" else float("-inf"))

    try:
        data = json.loads(text, object_pairs_hook=hook, parse_constant=const)
    except ValueError as e:
        return Loaded(name, None, len(raw), problems + [(ERROR, "A00.parse", "invalid JSON", str(e))])
    except RecursionError:
        return Loaded(name, None, len(raw), problems + [(ERROR, "A00.parse", "JSON is nested too deeply to parse",
                                                          "TTS objects nest a handful of levels")])
    if dups:
        problems.append((ERROR, "A00.duplicate-keys",
                         "JSON object repeats a key (parsers keep only one value)",
                         "%d repeated key(s), e.g. %s" % (len(dups), ", ".join(sorted(set(dups))[:5]))))
    if consts:
        problems.append((ERROR, "A00.nonfinite",
                         "file contains the non-standard literal NaN/Infinity",
                         ", ".join(sorted(set(consts)))))
    return Loaded(name, data, len(raw), problems)


# --------------------------------------------------------------------------
# Object tree walking
# --------------------------------------------------------------------------
class Node(object):
    __slots__ = ("path", "obj", "parent", "depth")

    def __init__(self, path, obj, parent, depth):
        self.path, self.obj, self.parent, self.depth = path, obj, parent, depth


def _label(o):
    for k in ("Nickname", "Name"):
        v = o.get(k)
        if isinstance(v, str) and v:
            return v
    return "?"


def _num_sort(k):
    return (0, int(k), "") if str(k).isdigit() else (1, 0, str(k))


def walk_tree(obj, path="", parent=None, depth=0, out=None):
    """Flatten an object tree (ContainedObjects and States) in document order."""
    out = [] if out is None else out
    out.append(Node(path, obj, parent, depth))
    cs = obj.get("ContainedObjects")
    if isinstance(cs, list):
        for i, c in enumerate(cs):
            if isinstance(c, dict):
                walk_tree(c, "%s/%s[%d]" % (path, _label(c), i), obj, depth + 1, out)
    st = obj.get("States")
    if isinstance(st, dict):
        for k in sorted(st, key=_num_sort):
            c = st[k]
            if isinstance(c, dict):
                walk_tree(c, "%s<state %s>" % (path, k), obj, depth + 1, out)
    return out


class Doc(object):
    """One shipped file: parsed JSON plus its flattened nodes."""

    def __init__(self, name, data, path=None, loaded=None):
        self.name = name                      # repo-relative name used in findings
        self.path = path
        self.data = data
        self.loaded = loaded
        if isinstance(data, dict) and isinstance(data.get("ObjectStates"), list):
            self.kind = "save"
            self.roots = [o for o in data["ObjectStates"] if isinstance(o, dict)]
        elif isinstance(data, dict):
            self.kind = "object"
            self.roots = [data]
        else:
            self.kind = "invalid"
            self.roots = []
        self.nodes = []
        for i, r in enumerate(self.roots):
            prefix = "" if self.kind == "object" else "/%s[%d]" % (_label(r), i)
            walk_tree(r, prefix, None, 0, self.nodes)
        base = os.path.basename(name)
        if self.kind == "save" and re.match(r"saved_object_", base):
            self.role = "saved"
        elif "downloads" in name.replace("\\", "/").split("/") and base.endswith("_box.json"):
            self.role = "placeholder"
        elif "downloads" in name.replace("\\", "/").split("/"):
            self.role = "release"
        elif base.endswith("_mod.json"):
            self.role = "mod"
        elif base.endswith("_campaign.json"):
            self.role = "campaign"
        elif base.endswith("_table.json"):
            self.role = "table"
        elif base.endswith("_encounter.json"):
            self.role = "encounter"
        elif base.endswith("_starter.json"):
            self.role = "starter"
        elif base.endswith(".json"):
            self.role = "player"
        else:
            self.role = "other"

    def where(self, node):
        return "%s::%s" % (self.name, node.path or "/")


def cards_of(doc):
    return [n for n in doc.nodes if n.obj.get("Name") in ("Card", "CardCustom")]


def card_id_of(obj):
    """The GMNotes id of a card (a string) or None."""
    ok, gm, _ = parse_gmnotes(obj)
    gid = gm.get("id") if gm else None
    return gid if isinstance(gid, str) else None


def sha1_text(s):
    return sha1(s.encode("utf-8", "surrogatepass"))


# --------------------------------------------------------------------------
# Image headers (stdlib only: no PIL)
# --------------------------------------------------------------------------
SOF_NAMES = {0xC0: "baseline", 0xC1: "extended-sequential", 0xC2: "progressive",
             0xC3: "lossless", 0xC5: "differential-sequential",
             0xC6: "differential-progressive", 0xC7: "differential-lossless",
             0xC9: "arithmetic-sequential", 0xCA: "arithmetic-progressive",
             0xCB: "arithmetic-lossless", 0xCD: "arithmetic-differential",
             0xCE: "arithmetic-differential-progressive", 0xCF: "arithmetic-differential-lossless"}


def parse_jpeg(data):
    """Header facts of a JPEG: dict with ok, width, height, sof, progressive,
    ncomp, precision, sampling, scans, orientation, icc, adobe_transform, eoi."""
    info = {"ok": False, "kind": "jpeg", "app": [], "scans": 0, "eoi": False}
    n = len(data)
    if n < 4 or data[:2] != b"\xff\xd8":
        info["err"] = "no JPEG SOI marker"
        return info
    i = 2
    while i < n:
        if data[i] != 0xFF:
            info["err"] = "expected a marker at byte %d" % i
            return info
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        m = data[i]
        i += 1
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            continue
        if m == 0xD9:
            info["eoi"] = True
            break
        if i + 2 > n:
            info["err"] = "truncated segment length"
            return info
        length = struct.unpack(">H", data[i:i + 2])[0]
        seg = data[i + 2:i + length]
        if m == 0xDA:                                   # start of scan
            info["scans"] += 1
            j = i + length
            while True:                                 # skip the entropy-coded data up to the next marker
                j = data.find(b"\xff", j)
                if j < 0 or j + 1 >= n:
                    j = n
                    break
                nxt = data[j + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:  # stuffed byte / restart marker
                    j += 2
                elif nxt == 0xFF:                        # fill byte
                    j += 1
                else:
                    break
            i = j
            continue
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            try:
                prec, h, w, nf = struct.unpack(">BHHB", seg[:6])
                comps = []
                for k in range(nf):
                    cid, hv, tq = struct.unpack(">BBB", seg[6 + 3 * k:9 + 3 * k])
                    comps.append((cid, hv >> 4, hv & 15, tq))
            except struct.error:
                info["err"] = "truncated SOF segment"
                return info
            info.update(sof=m, sof_name=SOF_NAMES.get(m, "sof%02X" % m),
                        progressive=m in (0xC2, 0xC6, 0xCA, 0xCE),
                        precision=prec, height=h, width=w, ncomp=nf,
                        sampling="".join("%dx%d," % (c[1], c[2]) for c in comps).rstrip(","))
        elif m == 0xE0 and seg[:4] == b"JFIF":
            info["app"].append("JFIF")
        elif m == 0xE1 and seg[:6] == b"Exif\0\0":
            info["app"].append("EXIF")
            t = seg[6:]
            try:
                end = "<" if t[:2] == b"II" else ">"
                off = struct.unpack(end + "I", t[4:8])[0]
                cnt = struct.unpack(end + "H", t[off:off + 2])[0]
                for k in range(cnt):
                    e = t[off + 2 + 12 * k:off + 14 + 12 * k]
                    tag, _typ, _c = struct.unpack(end + "HHI", e[:8])
                    if tag == 0x0112:
                        info["orientation"] = struct.unpack(end + "H", e[8:10])[0]
            except (struct.error, IndexError):
                info["exif_error"] = True
        elif m == 0xE2 and seg[:12] == b"ICC_PROFILE\0":
            info["app"].append("ICC")
        elif m == 0xEE and seg[:5] == b"Adobe":
            info["app"].append("Adobe")
            info["adobe_transform"] = seg[11] if len(seg) > 11 else None
        i += length
    info["ok"] = "sof" in info
    if not info["ok"] and "err" not in info:
        info["err"] = "no SOF marker"
    return info


def parse_png(data):
    info = {"ok": False, "kind": "png"}
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 33:
        info["err"] = "no PNG signature"
        return info
    w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", data[16:29])
    info.update(ok=True, width=w, height=h, precision=depth, color_type=ctype,
                interlaced=bool(interlace), progressive=bool(interlace))
    return info


def image_info(path, data):
    """Header facts for a hosted image file (dict; kind unknown for other types)."""
    if data[:2] == b"\xff\xd8":
        info = parse_jpeg(data)
    elif data[:4] == b"\x89PNG":
        info = parse_png(data)
    else:
        info = {"ok": False, "kind": "unknown", "err": "not a JPEG or PNG"}
    info["bytes"] = len(data)
    info["sha1"] = sha1(data)
    info["path"] = path
    return info


def decoded_bytes(info, mipmaps=True):
    """RGBA32 texture memory TTS needs for this image (estimate)."""
    if not info or not info.get("ok"):
        return 0
    b = info["width"] * info["height"] * 4
    return int(b * 4 / 3) if mipmaps else b


# --------------------------------------------------------------------------
# Lua source scanning (no Lua parser: a small lexer is enough for these checks)
# --------------------------------------------------------------------------
LUA_KEYWORDS = frozenset("and break do else elseif end false for function goto if in local "
                         "nil not or repeat return then true until while".split())


def lua_tokens(src):
    """List of (kind, text, line); kinds: name kw op num str. Comments dropped."""
    toks = []
    i, n, line = 0, len(src), 1
    name_re = re.compile(r"[A-Za-z_]\w*")
    num_re = re.compile(r"0[xX][0-9a-fA-F.]+(?:[pP][+-]?\d+)?|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?")
    long_re = re.compile(r"\[(=*)\[")
    ops3 = ("...",)
    ops2 = ("..", "==", "~=", "<=", ">=", "::", "//", "<<", ">>")
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if src.startswith("--", i):
            m = long_re.match(src, i + 2)
            if m:
                close = "]" + m.group(1) + "]"
                j = src.find(close, i)
                j = n if j < 0 else j + len(close)
                line += src.count("\n", i, j)
                i = j
            else:
                j = src.find("\n", i)
                i = n if j < 0 else j
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                if j < n and src[j] == "\n":
                    line += 1
                j += 1
            toks.append(("str", src[i:j + 1], line))
            i = j + 1
            continue
        m = long_re.match(src, i)
        if m:
            close = "]" + m.group(1) + "]"
            j = src.find(close, i)
            j = n if j < 0 else j + len(close)
            toks.append(("str", "[[...]]", line))
            line += src.count("\n", i, j)
            i = j
            continue
        m = name_re.match(src, i)
        if m:
            w = m.group(0)
            toks.append(("kw" if w in LUA_KEYWORDS else "name", w, line))
            i += len(w)
            continue
        m = num_re.match(src, i)
        if m and (c.isdigit() or c == "."):
            toks.append(("num", m.group(0), line))
            i += len(m.group(0))
            continue
        for op in ops3 + ops2:
            if src.startswith(op, i):
                toks.append(("op", op, line))
                i += len(op)
                break
        else:
            toks.append(("op", c, line))
            i += 1
    return toks


def lua_toplevel(toks):
    """(global function names, global assignment names) defined at chunk level."""
    depth = brace = paren = 0
    funcs, assigns = [], []
    prev = None
    n = len(toks)
    for i, (k, t, _l) in enumerate(toks):
        if k == "kw":
            if t == "function":
                if depth == brace == paren == 0 and (prev is None or prev[1] not in
                                                    ("local", "=", ",", "(", "return", ":", "{")):
                    j, nm = i + 1, []
                    while j < n and (toks[j][0] == "name" or toks[j][1] in (".", ":")):
                        nm.append(toks[j][1])
                        j += 1
                    funcs.append("".join(nm))
                depth += 1
            elif t in ("if", "do", "repeat"):
                depth += 1
            elif t in ("end", "until"):
                depth -= 1
        elif k == "op":
            if t == "{":
                brace += 1
            elif t == "}":
                brace -= 1
            elif t == "(":
                paren += 1
            elif t == ")":
                paren -= 1
        elif k == "name" and depth == brace == paren == 0:
            if i + 1 < n and toks[i + 1][1] == "=" and (prev is None or prev[1] not in
                                                        ("local", ".", ":", ",")):
                assigns.append(t)
        prev = toks[i]
    return funcs, assigns


def lua_api_use(toks):
    """Hits of APIs TTS does not provide: list of (rule, detail, line)."""
    hits = []
    n = len(toks)
    for i, (k, t, line) in enumerate(toks):
        if k != "name":
            continue
        nxt = toks[i + 1][1] if i + 1 < n else ""
        prev = toks[i - 1][1] if i else ""
        if prev in (".", ":"):
            continue
        if t in LUA_FORBIDDEN_CALLS and nxt in (".", "(", ":"):
            hits.append(("forbidden-lib", t, line))
        elif t == "os" and nxt == "." and i + 2 < n and toks[i + 2][1] in LUA_FORBIDDEN_OS:
            hits.append(("forbidden-os", "os." + toks[i + 2][1], line))
        elif t == "require" and nxt in ("(", ):
            arg = toks[i + 2][1] if i + 2 < n and toks[i + 2][0] == "str" else "?"
            hits.append(("require", arg.strip("\"'"), line))
        elif t == "require" and i + 1 < n and toks[i + 1][0] == "str":
            hits.append(("require", toks[i + 1][1].strip("\"'"), line))
        else:
            for lib, fns in LUA_53_LIBS:
                if t == lib and nxt == "." and i + 2 < n and toks[i + 2][1] in fns:
                    hits.append(("lua53-lib", "%s.%s" % (lib, toks[i + 2][1]), line))
    for (k, t, line) in toks:
        if k == "op" and t in ("//", "<<", ">>", "&", "|", "~"):
            hits.append(("lua53-syntax", t, line))
        elif k == "kw" and t == "goto":
            hits.append(("goto", "goto", line))
    return hits


SPAWN_NAMES = ("spawnObjectData", "spawnObject", "spawnObjectJSON")


def lua_spawn_loops(toks):
    """Loops that spawn objects without ever waiting: [(line, call)]. A spawn burst
    puts all texture loads into one frame."""
    hits = []
    stack = []                       # (kind, start index)
    pending_loop = False
    n = len(toks)
    for i, (k, t, line) in enumerate(toks):
        if k == "kw":
            if t in ("for", "while"):
                pending_loop = True
            elif t == "do":
                stack.append(("loop" if pending_loop else "do", i))
                pending_loop = False
            elif t in ("function", "if", "repeat"):
                stack.append((t, i))
            elif t in ("end", "until") and stack:
                kind, start = stack.pop()
                if kind == "loop":
                    body = toks[start:i]
                    names = [x[1] for x in body if x[0] == "name"]
                    spawn = [x for x in body if x[0] == "name" and x[1] in SPAWN_NAMES]
                    waits = any(x in ("Wait", "startLuaCoroutine", "coroutine", "yield") for x in names)
                    if spawn and not waits:
                        hits.append((spawn[0][2], spawn[0][1]))
    return hits


def find_luac():
    """{'5.2': path, '5.4': path, ...} of the luac binaries installed."""
    found = collections.OrderedDict()
    for cand in ("luac5.2", "luac5.3", "luac5.4", "luac"):
        p = shutil.which(cand)
        if not p:
            continue
        try:
            out = subprocess.run([p, "-v"], capture_output=True, timeout=10)
            m = re.search(rb"Lua (\d\.\d)", out.stdout + out.stderr)
        except (OSError, subprocess.SubprocessError):
            continue
        if m and m.group(1).decode() not in found:
            found[m.group(1).decode()] = p
    return found


def run_luac(path, source, listing=False):
    args = [path] + (["-l"] if listing else []) + ["-p", "-"] if not listing else [path, "-l", "-p", "-"]
    try:
        p = subprocess.run(args, input=source.encode("utf-8", "replace"), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return -1, "", str(e)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


LUAC_ENV_RE = re.compile(r"\[(\d+)\]\s+(GETTABUP|SETTABUP)\b.*;\s*_ENV\s+\"([^\"]+)\"")


def luac_global_access(listing):
    """(reads {name: first line}, writes set) of _ENV accesses in a luac -l listing."""
    reads, writes = {}, set()
    for m in LUAC_ENV_RE.finditer(listing):
        line, op, name = int(m.group(1)), m.group(2), m.group(3)
        if op == "SETTABUP":
            writes.add(name)
        else:
            reads.setdefault(name, line)
    return reads, writes


# --------------------------------------------------------------------------
# Asset accounting shared by the audited files and the official boxes
# --------------------------------------------------------------------------
BAG_NAMES = ("Bag", "Custom_Model_Bag", "Infinite_Bag", "Custom_Model_Infinite_Bag")


class Assets(object):
    def __init__(self):
        self.images = set()
        self.deck_ids = set()
        self.meshes = set()
        self.pdfs = set()
        self.ui_assets = set()
        self.ui_refs = 0
        self.cards = 0
        self.objects = 0
        self.max_sheets = 0


def collect_assets(o, acc, top=True):
    """Assets TTS has to load when this object is instantiated.  A bag's
    contents stay inside it, so only Decks and States are searched."""
    if not isinstance(o, dict):
        return acc
    acc.objects += 1
    name = o.get("Name")
    cd = o.get("CustomDeck")
    if isinstance(cd, dict):
        for k, v in cd.items():
            if isinstance(v, dict):
                acc.deck_ids.add(str(k))
                for u in (v.get("FaceURL"), v.get("BackURL")):
                    if isinstance(u, str) and u:
                        acc.images.add(u)
        if name == "Deck":
            acc.max_sheets = max(acc.max_sheets, len(cd))
    if name in ("Card", "CardCustom"):
        acc.cards += 1
    for key in ("ImageURL", "ImageSecondaryURL"):
        ci = o.get("CustomImage")
        if isinstance(ci, dict) and isinstance(ci.get(key), str) and ci[key]:
            acc.images.add(ci[key])
    cm = o.get("CustomMesh")
    if isinstance(cm, dict):
        for key in ("DiffuseURL", "NormalURL"):
            if isinstance(cm.get(key), str) and cm[key]:
                acc.images.add(cm[key])
        if isinstance(cm.get("MeshURL"), str) and cm["MeshURL"]:
            acc.meshes.add(cm["MeshURL"])
    cp = o.get("CustomPDF")
    if isinstance(cp, dict) and isinstance(cp.get("PDFUrl"), str) and cp["PDFUrl"]:
        acc.pdfs.add(cp["PDFUrl"])
    ua = o.get("CustomUIAssets")
    if isinstance(ua, list):
        for a in ua:
            if isinstance(a, dict):
                acc.ui_assets.add((hk(a.get("Name")), hk(a.get("URL"))))
                acc.ui_refs += 1
    if name not in BAG_NAMES:
        for c in kids(o):
            collect_assets(c, acc, False)
    st = o.get("States")
    if isinstance(st, dict):
        for c in st.values():
            collect_assets(c, acc, False)
    return acc


def memory_list(box):
    """The box's LuaScriptState `ml` dict, or None."""
    raw = box.get("LuaScriptState")
    if not isinstance(raw, str) or not raw.strip():
        return None
    ok, val = try_json(raw)
    if ok and isinstance(val, dict) and isinstance(val.get("ml"), dict):
        return val["ml"]
    return None


def place_children(box):
    """The children a Place click spawns: ml-listed ones (all if there is no ml)."""
    children = kids(box)
    ml = memory_list(box)
    if ml is None:
        return children
    return [c for c in children if isinstance(c.get("GUID"), str) and c.get("GUID") in ml]


def place_assets(box):
    acc = Assets()
    for c in place_children(box):
        collect_assets(c, acc)
    return acc


# --------------------------------------------------------------------------
# Reference (official) data
# --------------------------------------------------------------------------
class RefStats(object):
    """Everything computed from the official boxes and the SCED save."""

    def __init__(self):
        self.sources = []
        self.n_boxes = 0
        self.n_objects = 0
        self.names = collections.Counter()
        self.guid_total = self.guid_hex6 = 0
        self.guid_set = set()
        self.tags_by_name = collections.defaultdict(collections.Counter)
        self.tags_by_gmtype = collections.defaultdict(collections.Counter)
        self.gmtype_count = collections.Counter()
        self.gm_keys = collections.defaultdict(collections.Counter)    # card type -> key -> n
        self.gm_card_count = collections.Counter()
        self.gm_key_types = collections.defaultdict(collections.Counter)   # key -> type name -> n
        self.gm_vals = collections.defaultdict(collections.Counter)    # vocabulary keys -> value -> n
        self.int_range = {}
        self.ids = set()
        self.card_ids = set()
        self.deck_pairs = collections.defaultdict(set)                # deck id -> {(face, back)}
        self.cd_flags = collections.Counter()                          # (UniqueBack, BackIsHidden, Type)
        self.cd_keysets = collections.Counter()
        self.card_scale = collections.Counter()
        self.deck_hands = collections.Counter()
        self.deck_sidesways_mixed = collections.Counter()
        self.deck_sheets = []
        self.deck_cards = []
        self.scenario_assets = []                                      # dict per ScenarioBox
        self.campaign_assets = []
        self.ml_x, self.ml_y, self.ml_z = [], [], []
        self.top_x, self.top_y, self.top_z = [], [], []
        self.lua_sizes = []
        self.lua_by_name = collections.Counter()
        self.contained_by_name = collections.Counter()
        self.card_with_ui_assets = 0
        self.cards_total = 0
        self.card_hosts = collections.Counter()
        self.mesh_urls = set()
        self.card_flag_hands = collections.Counter()
        self.loc_symbols = collections.Counter()
        self.lua_object_calls = set()
        self.max_card_id = 0
        self.official_deck_cd_mismatch = 0
        self.tagset_by_type = collections.defaultdict(collections.Counter)   # card type -> tagset -> n
        self.lua_contained_sizes = []
        self.token_names = collections.Counter()
        self.uses_keys = collections.Counter()
        self.use_pairs = collections.Counter()               # (type, token) of uses entries
        self.cards_with_ui = 0

    # -- ingestion ----------------------------------------------------
    def ingest(self, root_obj, is_box=False):
        for node in walk_tree(root_obj):
            self._object(node)
        if is_box:
            self.n_boxes += 0   # counted by caller

    def _object(self, node):
        o = node.obj
        name = o.get("Name")
        self.n_objects += 1
        self.names[name] += 1
        g = o.get("GUID")
        if isinstance(g, str):
            self.guid_total += 1
            self.guid_hex6 += bool(GUID_RE.match(g))
            self.guid_set.add(g)
        ok, gm, _raw = parse_gmnotes(o)
        gtype = gm.get("type") if gm else None
        tags = taglist(o)
        for t in tags:
            self.tags_by_name[name][t] += 1
            if gtype:
                self.tags_by_gmtype[gtype][t] += 1
        if gtype:
            self.gmtype_count[gtype] += 1
        sz = o.get("LuaScript")
        if isinstance(sz, str) and sz.strip():
            self.lua_sizes.append(len(sz))
            self.lua_by_name[(name, node.depth > 0)] += 1
            if node.depth > 0:
                self.lua_contained_sizes.append(len(sz))
        if node.depth > 0:
            self.contained_by_name[name] += 1
        tr = o.get("Transform")
        if node.depth == 0 and isinstance(tr, dict) and is_num(tr.get("posX")):
            self.top_x.append(tr["posX"])
            self.top_y.append(tr.get("posY", 0))
            self.top_z.append(tr.get("posZ", 0))
        if name in ("Card", "CardCustom", "Deck"):
            cd = o.get("CustomDeck") if isinstance(o.get("CustomDeck"), dict) else {}
            for k, v in cd.items():
                if not isinstance(v, dict):
                    continue
                self.cd_flags[(v.get("UniqueBack"), v.get("BackIsHidden"), v.get("Type"))] += 1
                self.cd_keysets[tuple(sorted(v.keys()))] += 1
                self.deck_pairs[str(k)].add((v.get("FaceURL"), v.get("BackURL")))
                for u in (v.get("FaceURL"), v.get("BackURL")):
                    if isinstance(u, str):
                        self.card_hosts[urllib.parse.urlsplit(u).netloc] += 1
            if name == "Deck":
                cards = kids(o)
                self.deck_sheets.append(len(cd))
                self.deck_cards.append(len(cards))
                self.deck_hands[o.get("Hands")] += 1
                sw = {bool(c.get("SidewaysCard")) for c in cards}
                self.deck_sidesways_mixed[(bool(o.get("SidewaysCard")), tuple(sorted(sw)))] += 1
            if name in ("Card", "CardCustom"):
                self.cards_total += 1
                self.card_hands_flag(o)
                if isinstance(o.get("CustomUIAssets"), list) and o.get("CustomUIAssets"):
                    self.cards_with_ui += 1
                    if not o.get("XmlUI") and not o.get("LuaScript"):
                        self.card_with_ui_assets += 1
                trs = o.get("Transform") if isinstance(o.get("Transform"), dict) else {}
                self.card_scale[(trs.get("scaleX"), trs.get("scaleZ"))] += 1
                cid = o.get("CardID")
                if is_int(cid):
                    self.card_ids.add(cid)
                    self.max_card_id = max(self.max_card_id, cid)
        if name in ("Card", "CardCustom") and gm:
            gid = gm.get("id")
            if isinstance(gid, str):
                self.ids.add(gid)
            gtyp = gm.get("type") if isinstance(gm.get("type"), str) else None
            self.gm_card_count[gtyp] += 1
            self.tagset_by_type[gtyp][tuple(sorted(t for t in tags if isinstance(t, str)))] += 1
            tk = gm.get("tokens")
            if isinstance(tk, dict):
                for side in ("front", "back"):
                    if isinstance(tk.get(side), dict):
                        for tn in tk[side]:
                            self.token_names[tn] += 1
            for ulist in [gm.get("uses")] + [gm[sd].get("uses") for sd in ("locationFront", "locationBack")
                                              if isinstance(gm.get(sd), dict)]:
                if isinstance(ulist, list):
                    for u in ulist:
                        if isinstance(u, dict):
                            self.uses_keys[tuple(sorted(u.keys()))] += 1
                            self.use_pairs[(u.get("type"), u.get("token"))] += 1
            for k, v in gm.items():
                self.gm_keys[gtyp][k] += 1
                self.gm_key_types[k][tname(v)] += 1
                if is_int(v) and not isinstance(v, bool):
                    lo, hi = self.int_range.get(k, (v, v))
                    self.int_range[k] = (min(lo, v), max(hi, v))
                if k in ("class", "slot", "cycle", "type") and isinstance(v, str):
                    self.gm_vals[k][v] += 1
            for side in ("locationFront", "locationBack"):
                s = gm.get(side)
                if isinstance(s, dict) and isinstance(s.get("icons"), str):
                    for tok in re.findall(r"[A-Za-z]+", s["icons"]):
                        self.loc_symbols[tok] += 1
        if name in BAG_NAMES + ("Custom_Model",) and isinstance(o.get("CustomMesh"), dict):
            mu = o["CustomMesh"].get("MeshURL")
            if isinstance(mu, str):
                self.mesh_urls.add(mu)
        ml = memory_list(o)
        if ml:
            for e in ml.values():
                p = e.get("pos") if isinstance(e, dict) else None
                if isinstance(p, dict) and all(is_num(p.get(a)) for a in "xyz"):
                    self.ml_x.append(p["x"])
                    self.ml_y.append(p["y"])
                    self.ml_z.append(p["z"])
        if gtype in ("ScenarioBox", "CampaignBox"):
            a = place_assets(o)
            d = {"images": len(a.images), "deck_ids": len(a.deck_ids), "cards": a.cards,
                 "objects": a.objects, "max_sheets": a.max_sheets}
            (self.scenario_assets if gtype == "ScenarioBox" else self.campaign_assets).append(d)

    def card_hands_flag(self, o):
        self.card_flag_hands[o.get("HideWhenFaceDown")] += 1

    def required_keys(self, gtype, threshold=0.9):
        n = self.gm_card_count.get(gtype, 0)
        if n < 30:
            return set()
        return {k for k, c in self.gm_keys[gtype].items() if c / float(n) >= threshold}


class SrcStats(object):
    """What SCED's own source reads and treats specially."""

    def __init__(self):
        self.special_tags = collections.Counter()
        self.object_calls = set()
        self.getvars = set()
        self.md_keys = set()
        self.global_functions = set()
        self.files = 0


TAG_CALL_RE = re.compile(r"(?:hasTag|getObjectsWithTag|addTag|removeTag)\(\s*[\"']([A-Za-z_][\w]*)[\"']")
TAGS_ANY_RE = re.compile(r"(?:getObjectsWithAnyTags|getObjectsWithAllTags)\(\s*\{([^}]*)\}")
OBJ_CALL_RE = re.compile(r"\.call\(\s*[\"'](\w+)[\"']")
GETVAR_RE = re.compile(r"\.(?:getVar|setVar)\(\s*[\"'](\w+)[\"']")
MD_KEY_RE = re.compile(r"\b(?:md|metadata|meta|cardMetadata|cardMeta|cardMd|miniMd)\.([A-Za-z_]\w*)")
GLOBAL_FN_RE = re.compile(r"^function\s+([A-Za-z_]\w*)\s*\(", re.M)


def load_src_stats(src_dir):
    s = SrcStats()
    for path in sorted(glob.glob(os.path.join(src_dir, "**", "*.ttslua"), recursive=True)):
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        s.files += 1
        for m in TAG_CALL_RE.finditer(text):
            s.special_tags[m.group(1)] += 1
        for m in TAGS_ANY_RE.finditer(text):
            for t in re.findall(r"[\"']([\w]+)[\"']", m.group(1)):
                s.special_tags[t] += 1
        s.object_calls.update(OBJ_CALL_RE.findall(text))
        s.getvars.update(GETVAR_RE.findall(text))
        s.md_keys.update(MD_KEY_RE.findall(text))
        if os.path.basename(path) == "Global.ttslua":
            s.global_functions.update(GLOBAL_FN_RE.findall(text))
    return s


def discover_reference(dirs, root):
    """Find official boxes, the SCED save and the SCED source under `dirs`."""
    out = {"box_files": [], "save_file": None, "src_dir": None, "dirs": [], "library": None}
    seen_boxes = set()
    for d in dirs:
        d = d if os.path.isabs(d) else os.path.join(root, d)
        if not os.path.isdir(d):
            continue
        out["dirs"].append(d)
        menus = [os.path.join(d, "tts_menu")]
        if os.path.exists(os.path.join(d, "library.json")):
            menus.append(d)
        for menu in menus:
            if not os.path.isdir(menu):
                continue
            names = None
            lib = os.path.join(menu, "library.json")
            if os.path.exists(lib):
                try:
                    content = json.load(open(lib, encoding="utf-8"))["content"]
                    names = {e["filename"] for e in content
                             if e.get("author") == OFFICIAL_AUTHOR
                             and e.get("type") in ("campaign", "scenario")}
                    out["library"] = lib
                except (ValueError, KeyError, TypeError, OSError):
                    names = None
            for f in sorted(glob.glob(os.path.join(menu, "*.json"))):
                stem = os.path.basename(f)[:-5]
                if stem == "library" or f in seen_boxes:
                    continue
                if names is None or stem in names:
                    seen_boxes.add(f)
                    out["box_files"].append(f)
        for sd in sorted(glob.glob(os.path.join(d, "sced_*"))):
            for f in sorted(glob.glob(os.path.join(sd, "*.json"))):
                out["save_file"] = out["save_file"] or f
        for cand in [d] + sorted(glob.glob(os.path.join(d, "*"))):
            if os.path.isfile(os.path.join(cand, "src", "Global", "Global.ttslua")):
                out["src_dir"] = out["src_dir"] or os.path.join(cand, "src")
    return out


def load_reference(dirs, root, report):
    """(RefStats|None, SrcStats|None); notes the report when data is missing."""
    found = discover_reference(dirs, root)
    ref = src = None
    if found["box_files"] or found["save_file"]:
        ref = RefStats()
        for f in found["box_files"]:
            try:
                data = json.load(open(f, encoding="utf-8"))
            except (OSError, ValueError):
                report.note("reference box unreadable: " + rel(f, root))
                continue
            for r in (data["ObjectStates"] if isinstance(data, dict) and "ObjectStates" in data else [data]):
                if isinstance(r, dict):
                    ref.ingest(r, True)
            ref.n_boxes += 1
        if found["save_file"]:
            try:
                data = json.load(open(found["save_file"], encoding="utf-8"))
                for r in data.get("ObjectStates", []):
                    if isinstance(r, dict):
                        ref.ingest(r)
                ref.sources.append("SCED save " + os.path.basename(found["save_file"]))
            except (OSError, ValueError, AttributeError):
                report.note("reference save unreadable: " + rel(found["save_file"], root))
        if ref.n_boxes:
            ref.sources.insert(0, "%d official campaign/scenario boxes" % ref.n_boxes)
        if not ref.n_objects:
            ref = None
    if found["src_dir"]:
        src = load_src_stats(found["src_dir"])
    if ref is None:
        report.note("official data not found (looked in %s): reference-dependent checks skipped"
                    % ", ".join(dirs))
    if src is None:
        report.note("SCED source not found: tag/API usage checks use built-in lists only")
    return ref, src


# --------------------------------------------------------------------------
# The auditor
# --------------------------------------------------------------------------
class Auditor(object):
    """Holds the loaded files, the reference data and the report."""

    def __init__(self, root=ROOT, ref=None, src=None, report=None, online=False,
                 campaign=None, checks="ABCDEFG", luac=True):
        self.root = root
        self.ref = ref
        self.src = src
        self.report = report or Report()
        self.online = online
        self.checks = checks
        self.use_luac = luac
        self.docs = []
        self.images = {}                 # repo-relative path -> image info
        self.campaign = campaign or {}   # build.json of the campaign, if found
        self.url_refs = []               # (doc, key, url, where); filled by collect_url_refs()
        self._urls_done = False
        self.pinned = {}                 # (repo, ref) -> count
        self.primary = []                # the files the owner loads (census rules look only at these)

    # -- helpers ----------------------------------------------------------
    def add(self, sev, code, where, msg, evidence="", fix="", **kw):
        self.report.add(sev, code, where, msg, evidence, fix, **kw)

    def grp(self, sev, code, msg, fix=""):
        return self.report.group(sev, code, msg, fix)

    def want(self, letter):
        return letter in self.checks

    def add_doc(self, doc):
        self.docs.append(doc)
        if doc.loaded:
            for sev, code, msg, ev in doc.loaded.problems:
                self.add(sev, code, doc.name, msg, ev)
        return doc

    # -- A: TTS object invariants ----------------------------------------
    def check_a(self):
        for doc in self.docs:
            if doc.kind == "invalid":
                if doc.data is not None:               # an unparseable file was already reported (A00)
                    self.add(ERROR, "A01.shape", doc.name, "top-level JSON is neither an object nor a save",
                             "type %s" % tname(doc.data), "Write a TTS object or a {ObjectStates:[...]} save.")
                continue
            self.a_file_shape(doc)
            self.a_nodes(doc)
            self.a_guids(doc)
            self.a_deck_map(doc)
            self.a_ml(doc)
            self.a_decks(doc)
        self.a_cross_reference()
        self.a_flags_vs_official()

    def a_file_shape(self, doc):
        if doc.kind == "save" and not doc.roots:
            self.add(ERROR, "A01.shape", doc.name, "ObjectStates is empty", "",
                     "A saved object needs at least one object.")
        if doc.role == "release" and doc.kind != "object":
            self.add(ERROR, "A01.release-shape", doc.name,
                     "release asset is a save with ObjectStates, not a single object",
                     "SCED's contentDownloadCallback hands the file to spawnObjectJSON as one object",
                     "Write the campaign box object itself (no ObjectStates wrapper).")
        if doc.role == "saved" and doc.kind == "save":
            miss = [k for k in ("SaveName", "ObjectStates") if k not in doc.data]
            if miss:
                self.add(ERROR, "A01.save-keys", doc.name, "saved object lacks %s" % ", ".join(miss))
        if doc.loaded and doc.loaded.raw_size > 16 * 1048576:
            self.add(WARN, "A01.size", doc.name, "file is larger than 16 MiB",
                     "%s" % mib(doc.loaded.raw_size), "Split the content or host big assets as images.")

    def a_nodes(self, doc):
        scale_hist = collections.Counter()
        for node in doc.nodes:
            try:
                self.a_node(doc, node, scale_hist)
            except Exception as e:                           # malformed data must never stop the audit
                self.grp(ERROR, "A99.audit-crash", "the audit itself failed on this object (its data is malformed in a "
                         "way no check anticipated)", "Inspect the object.").hit(
                    doc.where(node), "%s: %s" % (type(e).__name__, str(e)[:80]))
        self.a_nodes_finish(doc, scale_hist)

    def a_node(self, doc, node, scale_hist):
        ref = self.ref
        o, where = node.obj, doc.where(node)
        name = o.get("Name")
        if not isinstance(name, str) or not name:
            self.grp(ERROR, "A01.name", "object has no Name (TTS cannot create it)",
                     "Give every object a Name such as Card, Deck, Bag.").hit(where)
            return
        if name not in KNOWN_NAMES and not (ref and name in ref.names):
            self.grp(WARN, "A01.name-unknown", "object Name is not one TTS/SCED data uses",
                     "Check the spelling against TTS object names.").hit(where, name)
        for key in REQUIRED_KEYS.get(name, ()):
            if key not in o:
                self.grp(ERROR, "A01.required-key",
                         "object lacks a key TTS needs to create a %s" % name,
                         "Add the key.").hit(where, key)
        for key, typ in FIELD_TYPES.items():
            if key not in o:
                continue
            v = o[key]
            good = (is_int(v) if typ is int else isinstance(v, bool) if typ is bool
                    else isinstance(v, typ) and not isinstance(v, bool))
            if not good:
                self.grp(ERROR, "A01.field-type",
                         "field has the wrong JSON type (TTS/Lua read it as another type)",
                         "Write %s as JSON %s." % (key, typ.__name__)).hit(
                    where, "%s is %s (%s), expected %s" % (key, tname(v), short(v, 30), typ.__name__))
        if is_int(o.get("CardID")) and not 0 <= o["CardID"] <= INT32_MAX:
            self.grp(ERROR, "A04.cardid-range", "CardID outside int32 (TTS stores card ids as int32)",
                     "Keep deckId*100+index below 2147483647.").hit(where, o["CardID"])
        self.a_required_subkeys(o, where, name)
        self.a_transform(o, where, name, scale_hist)
        self.a_color(o, where)
        self.a_text_fields(o, where, name, node, doc)
        self.a_tags(o, where)
        self.a_urls(o, where, doc)
        self.a_ui_assets(o, where, doc)
        if name in ("Card", "CardCustom"):
            self.a_card(o, where, node, doc)
        self.a_roundtrip(o, where)

    def a_nodes_finish(self, doc, scale_hist):
        # overall scale census (compared with the official norm in a_flags_vs_official)
        doc.scale_hist = scale_hist
        fam = collections.Counter()
        for d, key, url, where in self.collect_url_refs():
            if d is doc and key in ("FaceURL", "BackURL") and isinstance(url, str) and url:
                host = urllib.parse.urlsplit(url).netloc.lower()
                fam[HOST_FAMILIES.get(host, host)] += 1
        doc.card_hosts = fam
        if len(fam) > 1:
            self.add(WARN, "A05.host-mix", doc.name, "card images come from %d different hosts" % len(fam),
                     ", ".join("%s x%d" % kv for kv in fam.most_common(4)),
                     "Host every card image in one place (mixed hosts fail independently).")

    # required sub-keys: mesh / image / pdf URLs
    def a_required_subkeys(self, o, where, name):
        sub = {"CustomMesh": "MeshURL", "CustomImage": "ImageURL", "CustomPDF": "PDFUrl"}
        for key, url_key in sub.items():
            v = o.get(key)
            if isinstance(v, dict):
                u = v.get(url_key)
                if not isinstance(u, str) or not u:
                    self.grp(ERROR, "A05.url-missing",
                             "required URL is missing or empty (the object loads blank)",
                             "Set %s." % url_key).hit(where, "%s.%s" % (key, url_key))

    def a_transform(self, o, where, name, scale_hist):
        tr = o.get("Transform")
        if tr is None:
            return
        if not isinstance(tr, dict):
            return                                    # reported as a field-type error
        for key in ("posX", "posY", "posZ", "rotX", "rotY", "rotZ", "scaleX", "scaleY", "scaleZ"):
            if key not in tr:
                continue
            v = tr[key]
            if not is_num(v):
                self.grp(ERROR, "A06.transform-nonfinite",
                         "Transform value is not a finite number (NaN/Infinity/string/null)",
                         "Write finite numbers; TTS can crash or place the object at the origin.").hit(
                    where, "%s=%s" % (key, short(v, 20)))
                continue
            if key.startswith("scale"):
                if v <= 0:
                    self.grp(ERROR, "A06.scale", "scale is zero or negative (degenerate / mirrored mesh)",
                             "Use a positive scale.").hit(where, "%s=%s" % (key, v))
                elif v > 20 or v < 0.05:
                    self.grp(WARN, "A06.scale-range", "scale is outside the plausible 0.05-20 range",
                             "Check the scale.").hit(where, "%s=%s" % (key, v))
            elif key.startswith("pos"):
                lim = 1000 if key != "posY" else 500
                if abs(v) > lim:
                    self.grp(ERROR, "A06.position", "position is absurdly far from the table",
                             "TTS drops objects outside its world bounds.").hit(where, "%s=%s" % (key, v))
            elif abs(v) > 720:
                self.grp(WARN, "A06.rotation", "rotation is beyond two turns", "Normalise the angle.").hit(
                    where, "%s=%s" % (key, v))
        if name in ("Card", "CardCustom", "Deck") and all(is_num(tr.get(k)) for k in ("scaleX", "scaleZ")):
            scale_hist[(round(tr["scaleX"], 3), round(tr["scaleZ"], 3))] += 1

    def a_color(self, o, where):
        cd = o.get("ColorDiffuse")
        if not isinstance(cd, dict):
            return
        for ch in "rgb":
            v = cd.get(ch)
            if not is_num(v) or not 0 <= v <= 1:
                self.grp(ERROR, "A06.color", "ColorDiffuse channel is missing or outside 0..1",
                         "Write r,g,b as floats from 0 to 1.").hit(where, "%s=%s" % (ch, short(v, 20)))
        a = cd.get("a")
        if a is not None and (not is_num(a) or not 0 <= a <= 1):
            self.grp(ERROR, "A06.color", "ColorDiffuse channel is missing or outside 0..1",
                     "Write r,g,b as floats from 0 to 1.").hit(where, "a=%s" % short(a, 20))

    def a_text_fields(self, o, where, name, node, doc):
        for key in ("Nickname", "Description", "Memo"):
            v = o.get(key)
            if isinstance(v, str):
                if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", v):
                    self.grp(ERROR, "A07.control-chars", "text field holds control characters",
                             "Strip them.").hit(where, key)
                if self._bad_surrogate(v):
                    self.grp(ERROR, "A07.surrogate", "text holds an unpaired UTF-16 surrogate",
                             "Re-encode the text.").hit(where, key)
                if len(v) > 400 and key == "Nickname":
                    self.grp(WARN, "A07.long-name", "Nickname is very long", "Shorten it.").hit(where, len(v))
        gm = o.get("GMNotes")
        if isinstance(gm, str) and gm.strip():
            ok, val = try_json(gm)
            if not ok:
                self.grp(ERROR if name in ("Card", "CardCustom") else WARN, "A07.gmnotes-json",
                         "GMNotes is not valid JSON (SCED decodes it on every card event)",
                         "Write the metadata as a JSON object.").hit(where, short(gm, 50))
            elif not isinstance(val, dict):
                self.grp(ERROR, "A07.gmnotes-shape",
                         "GMNotes JSON is not an object (SCED indexes it like a table)",
                         "Use a JSON object.").hit(where, short(gm, 50))
        elif name in ("Card", "CardCustom") and node.depth >= 0:
            self.grp(WARN, "A07.gmnotes-empty", "card has no GMNotes metadata (SCED lists it as missing data)",
                     "Give every card id/type metadata.").hit(where)
        st = o.get("LuaScriptState")
        if isinstance(st, str) and st.strip():
            ok, val = try_json(st)
            if not ok:
                self.grp(WARN, "A07.state-json", "LuaScriptState is not JSON (scripts here decode it)",
                         "Write JSON or clear it.").hit(where, short(st, 40))
            elif isinstance(val, dict) and "ml" in val and not isinstance(val["ml"], dict):
                if val["ml"] == []:
                    pass            # a Lua empty table round-trips to []
                else:
                    self.grp(ERROR, "A08.ml-type", "memory list `ml` is not an object",
                             "ml maps GUID -> {pos, rot, lock}.").hit(where, tname(val["ml"]))

    @staticmethod
    def _bad_surrogate(s):
        return any(0xD800 <= ord(ch) <= 0xDFFF for ch in s)

    def a_tags(self, o, where):
        tags = o.get("Tags")
        if tags is None or not isinstance(tags, list):
            return
        seen = set()
        for t in tags:
            if not isinstance(t, str) or not t:
                self.grp(ERROR, "A07.tag-type", "tag is not a non-empty string",
                         "Tags are strings.").hit(where, short(t, 20))
                continue
            if not TAG_RE.match(t):
                self.grp(WARN, "A07.tag-chars", "tag has characters no official tag uses",
                         "Use letters, digits and underscores (SCED tags are identifiers).").hit(where, t)
            if t in seen:
                self.grp(WARN, "A07.tag-dup", "tag listed twice", "Remove the duplicate.").hit(where, t)
            seen.add(t)

    # URLs --------------------------------------------------------------
    def iter_urls(self, o):
        cd = o.get("CustomDeck")
        if isinstance(cd, dict):
            for k, v in cd.items():
                if isinstance(v, dict):
                    for key in ("FaceURL", "BackURL"):
                        yield key, v.get(key), "CustomDeck[%s]" % k
        for blk, keys in (("CustomImage", ("ImageURL", "ImageSecondaryURL")),
                          ("CustomMesh", ("MeshURL", "DiffuseURL", "NormalURL", "ColliderURL")),
                          ("CustomPDF", ("PDFUrl",))):
            v = o.get(blk)
            if isinstance(v, dict):
                for key in keys:
                    if key in v:
                        yield key, v.get(key), blk
        ua = o.get("CustomUIAssets")
        if isinstance(ua, list):
            for i, a in enumerate(ua):
                if isinstance(a, dict) and "URL" in a:
                    yield "URL", a.get("URL"), "CustomUIAssets[%d]" % i

    def collect_url_refs(self):
        """Every URL the audited objects carry (done once, whichever check needs it first)."""
        if self._urls_done:
            return self.url_refs
        self._urls_done = True
        for doc in self.docs:
            for node in doc.nodes:
                try:
                    for key, url, _sub in self.iter_urls(node.obj):
                        self.url_refs.append((doc, key, url, doc.where(node)))
                except Exception:                       # malformed nodes are reported by check A
                    continue
        return self.url_refs

    def a_urls(self, o, where, doc):
        for key, url, sub in self.iter_urls(o):
            if not isinstance(url, str):
                self.grp(ERROR, "A05.url-type", "URL is not a string", "Write the URL as a string.").hit(
                    where, "%s.%s=%s" % (sub, key, tname(url)))
                continue
            if not url:
                if key in URL_KEYS_REQUIRED:
                    self.grp(ERROR, "A05.url-missing", "required URL is missing or empty (the object loads blank)",
                             "Set %s." % key).hit(where, "%s.%s" % (sub, key))
                continue
            self.check_url(url, key, where)

    def check_url(self, url, key, where):
        ev = "%s: %s" % (key, short(url, 70))
        if re.search(r"[\x00-\x20\x7f]", url):
            self.grp(ERROR, "A05.url-chars", "URL contains spaces or control characters",
                     "Percent-encode them.").hit(where, ev)
        if "\\" in url:
            self.grp(ERROR, "A05.url-chars", "URL contains a backslash", "Use forward slashes.").hit(where, ev)
        if any(ord(c) > 127 for c in url):
            self.grp(WARN, "A05.url-nonascii", "URL contains non-ASCII characters",
                     "Percent-encode them.").hit(where, ev)
        if re.search(r"%(?![0-9A-Fa-f]{2})", url):
            self.grp(ERROR, "A05.url-percent", "URL has a malformed percent escape", "Fix the escape.").hit(where, ev)
        try:
            sp = urllib.parse.urlsplit(url)
        except ValueError:
            self.grp(ERROR, "A05.url-parse", "URL does not parse", "Fix the URL.").hit(where, ev)
            return
        if sp.scheme == "file":
            self.grp(ERROR, "A05.url-local", "machine-local file:/// URL (other PCs cannot read it)",
                     "Publish hosted images (pipeline/publish_hosted.py).").hit(where, ev)
            return
        if sp.scheme not in ("http", "https"):
            self.grp(ERROR, "A05.url-scheme", "URL scheme is not http(s)", "Use https.").hit(where, ev)
            return
        if sp.scheme == "http":
            self.grp(WARN, "A05.url-http", "URL uses plain http", "Use https.").hit(where, ev)
        if not sp.netloc:
            self.grp(ERROR, "A05.url-host", "URL has no host", "Fix the URL.").hit(where, ev)
            return
        if "@" in sp.netloc:
            self.grp(WARN, "A05.url-userinfo", "URL embeds credentials", "Remove them.").hit(where, ev)
        if sp.fragment:
            self.grp(WARN, "A05.url-fragment", "URL has a #fragment (TTS cache keys include it)",
                     "Drop the fragment.").hit(where, ev)
        if len(url) > 2000:
            self.grp(WARN, "A05.url-length", "URL is longer than 2000 characters", "Shorten it.").hit(where, len(url))
        host = sp.netloc.lower()
        if any(host == h or host.endswith("." + h) for h in PLACEHOLDER_HOSTS):
            self.grp(ERROR, "A05.url-placeholder", "placeholder image URL in a shipped file",
                     "Rebuild with hosted art (publish_hosted.py).").hit(where, ev)
        if host == "raw.githubusercontent.com":
            parts = sp.path.split("/")
            if len(parts) >= 5 and not HEX40_RE.match(parts[3]):
                self.grp(WARN, "A05.url-unpinned",
                         "raw.githubusercontent.com URL names a branch, not a commit "
                         "(every image breaks when the branch is deleted)",
                         "Pin the URL to a commit sha.").hit(where, ev)
            qs = urllib.parse.parse_qs(sp.query, keep_blank_values=True)
            extra = sorted(k for k in qs if k != "v")
            if extra or (sp.query and "v" not in qs):
                self.grp(WARN, "A05.url-query", "unexpected query string on a hosted URL",
                         "Only ?v=<content hash> is used.").hit(where, ev)
            elif "v" in qs and not re.fullmatch(r"[0-9a-f]{6,40}", qs["v"][0]):
                self.grp(WARN, "A05.url-query", "?v= is not a lowercase hex content hash",
                         "Use the file's sha1 prefix.").hit(where, ev)

    def a_ui_assets(self, o, where, doc):
        ua = o.get("CustomUIAssets")
        if not isinstance(ua, list):
            return
        for a in ua:
            if not isinstance(a, dict) or not isinstance(a.get("Name"), str) or not isinstance(a.get("URL"), str) \
                    or not is_int(a.get("Type")):
                self.grp(ERROR, "A11.ui-asset", "CustomUIAssets entry needs Name (str), Type (int), URL (str)",
                         "Fix the entry.").hit(where, short(a, 50))
        if doc in self.primary and o.get("Name") in ("Card", "CardCustom") and ua and not o.get("XmlUI") \
                and not o.get("LuaScript"):
            kinds = sorted({"%s(Type %s)" % (a.get("Name"), a.get("Type")) for a in ua if isinstance(a, dict)})
            self.grp(WARN, "A11.ui-assets-unused",
                     "the shipped card declares CustomUIAssets (a font AssetBundle, Type 1) but has no XmlUI/LuaScript "
                     "to use it; TTS has to register that bundle for every card it spawns. Official cards carry it "
                     "only with a UI (4 of 11,414 box cards)",
                     "build_cards.py no longer writes it (349a6bf); rebuild and publish dist/ so the shipped "
                     "objects lose it.").hit(
                where, ", ".join(kinds))

    # null / empty / precision hazards for a Lua JSON round trip
    def a_roundtrip(self, o, where):
        def scan(v, key, path):
            if v is None:
                self.grp(ERROR, "A09.null", "JSON null (Lua drops the key / truncates the array)",
                         "Remove the null.").hit(where, "%s%s" % (path, key))
            elif isinstance(v, bool) or isinstance(v, str):
                return
            elif isinstance(v, int):
                if abs(v) > LUA_SAFE_INT:
                    self.grp(WARN, "A09.bigint", "integer beyond 2^53 (Lua numbers are doubles)",
                             "Keep ids below 2^53.").hit(where, "%s%s=%s" % (path, key, v))
            elif isinstance(v, float):
                if not math.isfinite(v):
                    self.grp(ERROR, "A09.nonfinite", "NaN/Infinity value", "Write a finite number.").hit(
                        where, "%s%s" % (path, key))
            elif isinstance(v, dict):
                if not v and key not in ("TabStates",):
                    self.grp(WARN, "A09.empty-object",
                             "empty {} (a Lua round trip writes it back as [])",
                             "Omit the key or make sure the script never re-serialises it.").hit(
                        where, "%s%s" % (path, key))
                for k, x in v.items():
                    scan(x, k, path + key + "." if key else path)
            elif isinstance(v, list):
                if not v and key not in ("Tags",):
                    self.grp(WARN, "A09.empty-array", "empty [] (a Lua round trip cannot tell it from {})",
                             "Omit the key.").hit(where, "%s%s" % (path, key))
                for x in v:
                    scan(x, key, path)

        for k, v in o.items():
            if k in ("ContainedObjects", "States"):
                continue                       # the children are scanned as their own nodes
            if k in ("LuaScript", "GMNotes", "LuaScriptState", "XmlUI"):
                continue
            scan(v, k, "")

    # Card / CustomDeck ---------------------------------------------------
    CD_KEYS = ("FaceURL", "BackURL", "NumWidth", "NumHeight", "Type", "UniqueBack", "BackIsHidden")

    def a_customdeck_entry(self, doc, entry, deck, where, idx=None):
        if not isinstance(entry, dict):
            self.grp(ERROR, "A04.customdeck-type", "CustomDeck entry is not an object",
                     "Each entry is {FaceURL, BackURL, NumWidth, NumHeight, ...}.").hit(where, deck)
            return
        nw, nh = entry.get("NumWidth"), entry.get("NumHeight")
        if not (is_int(nw) and is_int(nh)):
            self.grp(ERROR, "A04.grid-type", "NumWidth/NumHeight must be integers",
                     "Write ints (a 1x1 sheet is 1 and 1).").hit(where, "deck %s: %s x %s" % (deck, short(nw, 12), short(nh, 12)))
        else:
            if not (1 <= nw <= TTS_MAX_GRID[0] and 1 <= nh <= TTS_MAX_GRID[1]):
                self.grp(ERROR, "A04.grid-range", "sheet grid is outside TTS's 10 x 7 maximum",
                         "Use a grid of at most 10 columns by 7 rows.").hit(where, "deck %s: %dx%d" % (deck, nw, nh))
            elif idx is not None and idx >= nw * nh:
                self.grp(ERROR, "A04.index-range", "CardID%100 is past the last cell of its sheet",
                         "CardID = deckId*100 + cell index (< NumWidth*NumHeight).").hit(
                    where, "deck %s index %d, grid %dx%d" % (deck, idx, nw, nh))
        for key in ("UniqueBack", "BackIsHidden"):
            if key in entry and not isinstance(entry[key], bool):
                self.grp(ERROR, "A04.customdeck-flag", "%s must be a boolean" % key, "Write true/false.").hit(
                    where, "deck %s: %s" % (deck, short(entry[key], 12)))
        if "Type" in entry and not is_int(entry["Type"]):
            self.grp(ERROR, "A04.customdeck-type-field", "CustomDeck Type must be an integer", "Use 0.").hit(where, deck)
        extra = sorted(k for k in entry if k not in self.CD_KEYS)
        if extra:
            self.grp(WARN, "A04.customdeck-keys", "CustomDeck entry has keys TTS does not define",
                     "Remove them.").hit(where, ", ".join(extra))
        doc.cd_entries.setdefault(str(deck), (entry.get("UniqueBack"), entry.get("BackIsHidden"),
                                              entry.get("Type"), nw, nh, where))

    def a_card(self, o, where, node, doc):
        if not hasattr(doc, "cd_entries"):
            doc.cd_entries = {}
        cid, cd = o.get("CardID"), o.get("CustomDeck")
        if not is_int(cid):
            return
        deck, idx = str(cid // 100), cid % 100
        if not isinstance(cd, dict) or not cd:
            self.grp(ERROR, "A04.no-customdeck", "card has a CardID but no CustomDeck (TTS cannot find its image)",
                     "Add the CustomDeck entry for deck %s." % deck).hit(where, "CardID %s" % cid)
            return
        for k in cd:
            if not str(k).isdigit():
                self.grp(ERROR, "A04.customdeck-key", "CustomDeck key is not a decimal deck id",
                         "Keys are deck ids such as \"97534\".").hit(where, k)
        if deck not in cd:
            self.grp(ERROR, "A04.deck-missing", "CustomDeck lacks the entry CardID//100 points at (blank card)",
                     "Key the entry by %s." % deck).hit(where, "CardID %s -> deck %s, have %s" % (cid, deck, ", ".join(sorted(cd))))
        else:
            self.a_customdeck_entry(doc, cd[deck], deck, where, idx)
        extra = [k for k in cd if k != deck]
        if extra:
            self.grp(WARN, "A04.customdeck-extra",
                     "card carries CustomDeck entries other than its own (official cards carry exactly one)",
                     "Keep only the entry for CardID//100.").hit(where, "extra %s" % ", ".join(extra[:4]))

    def a_decks(self, doc):
        if not hasattr(doc, "cd_entries"):
            doc.cd_entries = {}
        sheets = []
        for node in doc.nodes:
            o = node.obj
            if o.get("Name") != "Deck":
                continue
            where = doc.where(node)
            cards = o.get("ContainedObjects")
            if not isinstance(cards, list):
                continue
            if len(cards) == 0:
                self.grp(ERROR, "A03.deck-empty", "Deck holds no cards", "Remove it or add its cards.").hit(where)
                continue
            if len(cards) == 1:
                self.grp(WARN, "A03.deck-single", "Deck holds one card (TTS expects 2+; official decks never do)",
                         "Emit a Card instead of a one-card Deck.").hit(where)
            bad_children = [i for i, c in enumerate(cards)
                            if not isinstance(c, dict) or c.get("Name") not in ("Card", "CardCustom")]
            if bad_children:
                self.grp(ERROR, "A03.deck-child", "Deck contains something other than cards",
                         "Only Card/CardCustom objects belong in a Deck.").hit(where, "indices %s" % bad_children[:5])
                continue
            ids = [c.get("CardID") for c in cards]
            dids = o.get("DeckIDs")
            if not isinstance(dids, list) or not all(is_int(x) for x in dids):
                self.grp(ERROR, "A03.deckids-type", "DeckIDs must be a list of integers",
                         "Write ints.").hit(where, short(dids, 40))
            elif dids != ids:
                first = next((i for i, (a, b) in enumerate(zip(dids, ids)) if a != b), min(len(dids), len(ids)))
                self.grp(ERROR, "A03.deckids",
                         "Deck.DeckIDs differs from the contained CardIDs (TTS builds the deck from DeckIDs)",
                         "DeckIDs must be [c.CardID for c in ContainedObjects], in order.").hit(
                    where, "len %d vs %d, first difference at index %d" % (len(dids), len(ids), first))
            if not all(is_int(x) for x in ids):
                continue
            need = {str(x // 100) for x in ids}
            dcd = o.get("CustomDeck")
            if not isinstance(dcd, dict):
                continue
            missing = sorted(need - set(dcd))
            extra = sorted(set(dcd) - need)
            if missing:
                self.grp(ERROR, "A03.customdeck-missing",
                         "Deck.CustomDeck lacks sheets its cards use (those cards render blank)",
                         "Add one entry per CardID//100.").hit(where, "missing %s" % ", ".join(missing[:5]))
            if extra:
                self.grp(WARN, "A03.customdeck-extra", "Deck.CustomDeck lists sheets no card uses",
                         "Remove unused entries (TTS still loads their textures).").hit(
                    where, "extra %s" % ", ".join(extra[:5]))
            for k, entry in dcd.items():
                self.a_customdeck_entry(doc, entry, k, where)
            for i, c in enumerate(cards):
                ccd = c.get("CustomDeck") if isinstance(c.get("CustomDeck"), dict) else {}
                own = str(c["CardID"] // 100)
                if set(ccd) != {own}:
                    self.grp(ERROR if own not in ccd else WARN, "A03.card-customdeck",
                             "a contained card's CustomDeck is not exactly its own sheet",
                             "Each card carries only the entry for its CardID//100.").hit(
                        where + "[%d]" % i, "own %s, has %s" % (own, ", ".join(sorted(ccd)) or "none"))
                elif own in dcd and ccd[own] != dcd[own]:
                    self.grp(ERROR, "A03.card-vs-deck",
                             "a card's CustomDeck entry differs from the Deck's (TTS draws the Deck's)",
                             "Make the entries identical.").hit(where + "[%d]" % i, "deck %s" % own)
            if o.get("Hands") is True:
                self.grp(WARN, "A03.deck-hands", "Deck.Hands is true (all 1145 official box decks are false)",
                         "Set Hands false on decks.").hit(where)
            sw = {bool(c.get("SidewaysCard")) for c in cards}
            if True in sw and not o.get("SidewaysCard"):
                self.grp(WARN, "A03.deck-sideways", "cards are sideways but the Deck is not flagged SidewaysCard",
                         "Official decks with any sideways card carry SidewaysCard true.").hit(where)
            sheets.append((len(dcd), where, len(cards)))
        doc.deck_sheets = sheets

    # GUIDs -----------------------------------------------------------------
    def a_guids(self, doc):
        by = collections.defaultdict(list)
        for node in doc.nodes:
            g = node.obj.get("GUID")
            if not isinstance(g, str):
                continue
            by[g].append(node)
            if not GUID_RE.match(g):
                self.grp(WARN, "A02.guid-format", "GUID is not 6 lowercase hex digits (TTS's own format)",
                         "Use 6 hex digits.").hit(doc.where(node), g)
        distinct_dups, copy_dups, cross_dups = 0, 0, 0
        for g, nodes in by.items():
            if len(nodes) < 2:
                continue
            distinct_dups += 1
            sig = {tuple(hk(n.obj.get(k)) for k in ("CardID", "Name", "Nickname", "GMNotes")) for n in nodes}
            parents = {id(n.parent) for n in nodes}
            if len(sig) == 1:
                copy_dups += 1
            if len(parents) > 1:
                cross_dups += 1
            siblings = collections.defaultdict(list)
            for n in nodes:
                siblings[id(n.parent)].append(n)
            for plist in siblings.values():
                if len(plist) < 2:
                    continue
                psig = {tuple(hk(n.obj.get(k)) for k in ("CardID", "Name", "Nickname", "GMNotes")) for n in plist}
                parent = plist[0].parent
                keyed = False
                if parent is not None:
                    ml = memory_list(parent)
                    keyed = bool(ml) and g in ml
                if keyed:
                    self.grp(ERROR, "A02.guid-ml-collision",
                             "two children of a memory bag share a GUID that the bag's ml places "
                             "(Place can only act on one of them)",
                             "Give contained objects unique GUIDs.").hit(doc.where(plist[0]), g)
                elif len(psig) > 1:
                    self.grp(WARN, "A02.guid-distinct-siblings",
                             "different objects in one container share a GUID",
                             "Give distinct objects distinct GUIDs.").hit(doc.where(plist[0]), g)
        doc.guid_stats = {"objects": sum(len(v) for v in by.values()), "distinct": len(by),
                          "duplicated_guids": distinct_dups, "identical_copies": copy_dups,
                          "across_containers": cross_dups}
        per_box = {}
        for root_node in [n for n in doc.nodes if n.depth == 0]:
            for box in kids(root_node.obj):
                if isinstance(box.get("ContainedObjects"), list):
                    c = collections.Counter(hk(n.obj.get("GUID")) for n in walk_tree(box))
                    per_box[_label(box)] = {"objects": sum(c.values()), "distinct": len(c),
                                            "repeated_guids": sum(1 for v in c.values() if v > 1)}
        self.report.stats.setdefault("guid_by_box", {})[doc.name] = per_box
        if distinct_dups and doc in self.primary:
            ref = self.ref
            norm = ("official data reuses GUIDs heavily: %d of %d official GUID slots are repeats"
                    % (ref.guid_total - len(ref.guid_set), ref.guid_total)) if ref else "official data reuses GUIDs"
            self.add(INFO, "A02.guid-reuse", doc.name,
                     "%d of %d GUIDs appear more than once (%d are identical copies of one card, %d span containers)"
                     % (distinct_dups, len(by), copy_dups, cross_dups),
                     norm + "; TTS regenerates a GUID on spawn when it is taken",
                     "Nothing needed; SCED's MemoryBag Place compares names as well as GUIDs.")

    # deck id <-> image mapping ------------------------------------------------
    def a_deck_map(self, doc):
        pairs = collections.defaultdict(dict)       # deck id -> {(face, back, flags): where}
        card_ids = collections.defaultdict(set)     # gm id -> {CardID}
        id_of_card = collections.defaultdict(set)   # CardID -> {gm id}
        for node in doc.nodes:
            o = node.obj
            cd = o.get("CustomDeck")
            if isinstance(cd, dict):
                for k, v in cd.items():
                    if isinstance(v, dict):
                        flags = tuple(hk(v.get(f)) for f in ("NumWidth", "NumHeight", "UniqueBack",
                                                              "BackIsHidden", "Type"))
                        pairs[str(k)].setdefault((hk(v.get("FaceURL")), hk(v.get("BackURL")), flags),
                                                 doc.where(node))
            if o.get("Name") in ("Card", "CardCustom") and is_int(o.get("CardID")):
                gid = card_id_of(o)
                if gid is not None:
                    card_ids[gid].add(o["CardID"])
                    id_of_card[o["CardID"]].add(gid)
        for k, variants in pairs.items():
            if len(variants) > 1:
                locs = list(variants.values())
                self.add(ERROR, "A10.deckid-two-images", locs[0],
                         "deck id %s maps to %d different image pairs in one file (TTS identifies a sheet by its "
                         "id: when such cards meet in one Deck or are copied, one of the images shows on the "
                         "other card)" % (k, len(variants)),
                         "; ".join(short(v[0], 60) for v in variants), "Give each distinct image its own deck id.",
                         count=len(variants), locations=locs[1:4])
        by_pair = collections.defaultdict(set)
        for k, variants in pairs.items():
            for (face, back, flags) in variants:
                by_pair[(face, back)].add(k)
        shared = {p: ids for p, ids in by_pair.items() if len(ids) > 1}
        if shared:
            p, ids = sorted(shared.items(), key=lambda kv: sorted(kv[1]))[0]
            self.add(WARN, "A10.pair-two-ids", doc.name,
                     "%d image pair(s) are registered under more than one deck id" % len(shared),
                     "e.g. ids %s -> %s" % (", ".join(sorted(ids)), short(p[0], 60)),
                     "Reuse one deck id per image pair (unless the duplication is intended).", count=len(shared))
        for gid, ids in card_ids.items():
            if len(ids) > 1:
                self.grp(ERROR, "A10.id-two-cardids", "one card id has several CardIDs in a file (copies would show "
                         "different art)", "One card id, one CardID.").hit(doc.name, "%s -> %s" % (gid, sorted(ids)))
        for cid, gids in id_of_card.items():
            if len(gids) > 1:
                self.grp(ERROR, "A10.cardid-two-ids", "one CardID belongs to several card ids (TTS shows one image)",
                         "One CardID per card.").hit(doc.name, "%s -> %s" % (cid, sorted(gids)))
        doc.deck_pairs = pairs
        doc.id_to_cardid = {g: sorted(v)[0] for g, v in card_ids.items()}

    # memory lists ---------------------------------------------------------------
    def a_ml(self, doc):
        official = self.ref
        for node in doc.nodes:
            o = node.obj
            raw = o.get("LuaScriptState")
            if not isinstance(raw, str) or not raw.strip():
                continue
            ok, val = try_json(raw)
            if not ok or not isinstance(val, dict) or "ml" not in val:
                continue
            ml = val["ml"]
            if not isinstance(ml, dict):
                continue
            where = doc.where(node)
            children = kids(o)
            kid_guids = {hk(c.get("GUID")) for c in children}
            deep = {hk(n.obj.get("GUID")) for n in walk_tree(o)[1:]}
            boxy = parse_gmnotes(o)[1] or {}
            is_book = boxy.get("type") in ("ScenarioBox", "CampaignBox")
            if not ml and children:
                self.grp(WARN, "A08.ml-empty", "memory list is empty although the bag holds objects (Place does nothing)",
                         "Rebuild the box layout.").hit(where)
            pos_seen = {}
            for g, e in ml.items():
                if not isinstance(g, str) or not GUID_RE.match(g):
                    self.grp(WARN, "A08.ml-key", "ml key is not a 6-hex GUID", "Use contained objects' GUIDs.").hit(where, g)
                if g not in kid_guids:
                    if g in deep:
                        self.grp(INFO, "A08.ml-nested", "ml key names an object inside a nested bag "
                                 "(SCED's 'Internal' action merges these)", "").hit(where, g)
                    else:
                        self.grp(WARN, "A08.ml-orphan", "ml key names no contained object: nothing is placed for it "
                                 "(SCED's Place skips it silently; ~1,000 official ml keys are stale the same way)",
                                 "Regenerate ml from the contained objects.").hit(where, g)
                if not isinstance(e, dict):
                    self.grp(ERROR, "A08.ml-entry", "ml entry is not an object", "Use {pos, rot, lock}.").hit(where, g)
                    continue
                for field in ("pos", "rot"):
                    v = e.get(field)
                    if not isinstance(v, dict) or not all(is_num(v.get(a)) for a in "xyz"):
                        self.grp(ERROR, "A08.ml-vector", "ml %s is not an {x,y,z} of finite numbers (Place would "
                                 "set a nil/NaN position)" % field, "Write finite x, y, z.").hit(where, "%s: %s" % (g, short(v, 40)))
                if "lock" in e and not isinstance(e["lock"], bool):
                    self.grp(ERROR, "A08.ml-lock", "ml lock must be a boolean", "Write true/false.").hit(where, g)
                p = e.get("pos")
                if isinstance(p, dict) and all(is_num(p.get(a)) for a in "xyz"):
                    x, y, z = p["x"], p["y"], p["z"]
                    if max(abs(x), abs(z)) > 1000 or abs(y) > 500:
                        self.grp(ERROR, "A08.ml-bounds", "ml position is far outside any table",
                                 "TTS discards objects beyond its world bounds.").hit(where, "%s: %s,%s,%s" % (g, x, y, z))
                    elif official and official.ml_x:
                        lo_x, hi_x = min(official.ml_x), max(official.ml_x)
                        lo_z, hi_z = min(official.ml_z), max(official.ml_z)
                        mx, mz = 0.25 * (hi_x - lo_x), 0.25 * (hi_z - lo_z)
                        if not (lo_x - mx <= x <= hi_x + mx and lo_z - mz <= z <= hi_z + mz):
                            self.grp(WARN, "A08.ml-range", "ml position is outside the area official boxes use "
                                     "(x %.0f..%.0f, z %.0f..%.0f, +25%%)" % (lo_x, hi_x, lo_z, hi_z),
                                     "Keep Place spots on the SCED table.").hit(where, "%s: %s,%s" % (g, x, z))
                    if y < 1.3:
                        self.grp(WARN, "A08.ml-low", "ml y is below the SCED table surface (~1.48): the object "
                                 "spawns inside the table", "Use y >= 1.5.").hit(where, "%s: y=%s" % (g, y))
                    key = (round(x, 1), round(z, 1))
                    if key in pos_seen:
                        self.grp(WARN, "A08.ml-overlap", "two ml entries place objects on the same spot "
                                 "(spawned on top of each other)", "Offset one of them.").hit(
                            where, "%s and %s at %s,%s" % (pos_seen[key], g, x, z))
                    pos_seen[key] = g
            if is_book:
                unplaced = [c for c in children if hk(c.get("GUID")) not in ml]
                if unplaced:
                    self.grp(WARN, "A08.ml-unplaced", "box holds objects its memory list never places",
                             "Add them to ml or remove them.").hit(where, ", ".join(_label(c) for c in unplaced[:4]))

    # cross-file and reference checks -----------------------------------------------
    def a_cross_reference(self):
        ref = self.ref
        mine = collections.defaultdict(dict)       # deck id -> {(face, back): doc}
        for doc in self.docs:
            for k, variants in getattr(doc, "deck_pairs", {}).items():
                for (face, back, _flags) in variants:
                    mine[k].setdefault((face, back), doc.name)
        for k, variants in sorted(mine.items()):
            if len(variants) > 1:
                names = sorted(set(variants.values()))
                self.add(ERROR, "A10.deckid-two-images-across-files", names[0],
                         "deck id %s maps to different images in different shipped files (loading both "
                         "in one game shows the wrong art)" % k,
                         "; ".join("%s: %s" % (v, short(p[0], 40)) for p, v in sorted(variants.items(), key=str))[:200],
                         "Derive deck ids from the image so they never clash.")
        if not ref:
            self.report.note("A: deck-id/CardID collisions with official data skipped (no reference)")
            return
        hits = []
        for k, variants in mine.items():
            if k in ref.deck_pairs:
                hits.append(k)
        if hits:
            self.add(ERROR, "A10.deckid-official-collision", self.docs[0].name if self.docs else "",
                     "%d deck id(s) are also used by official SCED boxes/save: TTS identifies a sheet by its id, so "
                     "cards of both would show each other's art when combined in one Deck" % len(hits), "e.g. %s" % ", ".join(sorted(hits)[:6]),
                     "Pick deck ids outside the official range.", count=len(hits))
        else:
            self.add(INFO, "A10.deckid-official", "(all files)",
                     "none of our %d deck ids collides with the %d official deck ids"
                     % (len(mine), len(ref.deck_pairs)), "", "")

    def a_flags_vs_official(self):
        ref = self.ref
        for doc in self.primary:
            ents = getattr(doc, "cd_entries", {})
            if not ents:
                continue
            n = len(ents)
            bih_false = [k for k, v in ents.items() if v[1] is False]
            bih_missing = [k for k, v in ents.items() if v[1] is None]
            if ref and (bih_false or bih_missing):
                t = sum(c for (u, b, ty), c in ref.cd_flags.items() if b is True)
                tot = sum(ref.cd_flags.values())
                self.add(WARN, "A12.back-is-hidden", doc.name,
                         "%d of %d CustomDeck entries have BackIsHidden %s; SCED forces it to true "
                         "(CardBackEnhancer, AllEncounterCardsBag) and %d of %d official entries are true"
                         % (len(bih_false) + len(bih_missing), n, "false" if bih_false else "unset", t, tot),
                         "e.g. deck ids %s" % ", ".join(sorted(bih_false + bih_missing)[:4]),
                         "Write BackIsHidden true like every official deck (build_cards.py).",
                         count=len(bih_false) + len(bih_missing))
            hist = getattr(doc, "scale_hist", {})
            if ref and hist:
                off = ref.card_scale
                off_total = sum(off.values()) or 1
                big = sum(c for s, c in hist.items() if abs(s[0] - 1.0) > 0.05 and s[0] > 0.9)
                if big:
                    s_big = sorted(((c, s) for s, c in hist.items() if abs(s[0] - 1.0) > 0.05 and s[0] > 0.9),
                                   reverse=True)[0]
                    self.add(WARN, "A12.card-scale", doc.name,
                             "%d of %d cards/decks use scale %s; %.1f%% of official box cards use 1.0 "
                             "(1.15 only on %d)" % (big, sum(hist.values()), s_big[1][0],
                                                   100.0 * off.get((1, 1), 0) / off_total, off.get((1.15, 1.15), 0)),
                             "cards are 15% larger than the 1.0 cards SCED's mats, snap points and location spacing are laid out for",
                             "Use scale 1.0 for cards and decks (transform() in build_cards.py).", count=big)

    # -- images ------------------------------------------------------------
    @staticmethod
    def hosted_parts(url):
        """(owner/repo, ref, repo-relative path, query dict) for a raw.githubusercontent.com URL."""
        sp = urllib.parse.urlsplit(url)
        if sp.netloc.lower() != "raw.githubusercontent.com":
            return None
        parts = sp.path.split("/")
        if len(parts) < 5:
            return None
        return ("%s/%s" % (parts[1], parts[2]), parts[3],
                urllib.parse.unquote("/".join(parts[4:])), urllib.parse.parse_qs(sp.query))

    def image_for(self, url):
        """Image header facts of a hosted file in the working tree (cached) or None."""
        hp = self.hosted_parts(url) if isinstance(url, str) else None
        if not hp:
            return None
        path = hp[2]
        if path not in self.images:
            full = os.path.join(self.root, path)
            if not os.path.isfile(full):
                self.images[path] = None
            else:
                try:
                    self.images[path] = image_info(path, open(full, "rb").read())
                except OSError:
                    self.images[path] = None
        return self.images[path]

    # -- B: image budget per Place ----------------------------------------------
    def check_b(self):
        ref = self.ref
        rows = []
        for doc in self.primary:
            for node in doc.nodes:
                o = node.obj
                ml = memory_list(o)
                if ml is None:
                    continue
                gm = parse_gmnotes(o)[1] or {}
                kind = gm.get("type") or o.get("Name")
                acc = place_assets(o)
                infos = [self.image_for(u) for u in sorted(acc.images)]
                known = [i for i in infos if i]
                row = {"file": doc.name, "box": o.get("Nickname") or o.get("Name"), "kind": kind,
                       "where": doc.where(node), "placed_objects": len(place_children(o)),
                       "images": len(acc.images), "deck_ids": len(acc.deck_ids), "cards": acc.cards,
                       "max_sheets_in_a_deck": acc.max_sheets, "ui_asset_refs": acc.ui_refs,
                       "ui_assets": len(acc.ui_assets), "pdfs": len(acc.pdfs),
                       "texture_mib_est": round(sum(decoded_bytes(i) for i in known) / 1048576.0, 1),
                       "download_mib": round(sum(i["bytes"] for i in known) / 1048576.0, 2),
                       "images_without_local_file": len(infos) - len(known)}
                rows.append(row)
        merged = collections.OrderedDict()
        for row in rows:
            key = (hk(row["box"]), hk(row["kind"]), row["placed_objects"], row["images"], row["deck_ids"], row["cards"],
                   row["max_sheets_in_a_deck"], row["texture_mib_est"])
            if key in merged:
                merged[key]["files"].append(row["file"])
            else:
                row["files"] = [row["file"]]
                merged[key] = row
        rows = list(merged.values())
        for row in rows:
            row.pop("file", None)
        self.report.stats["place_units"] = rows
        if not rows:
            return
        if ref:
            sc = ref.scenario_assets
            cb = ref.campaign_assets
            self.report.stats["official_place_units"] = {
                "scenario_boxes": {"n": len(sc), "images": dist_dict([d["images"] for d in sc]),
                                   "deck_ids": dist_dict([d["deck_ids"] for d in sc]),
                                   "cards": dist_dict([d["cards"] for d in sc]),
                                   "max_sheets_in_a_deck": dist_dict([d["max_sheets"] for d in sc])},
                "campaign_boxes": {"n": len(cb), "images": dist_dict([d["images"] for d in cb]),
                                   "deck_ids": dist_dict([d["deck_ids"] for d in cb]),
                                   "cards": dist_dict([d["cards"] for d in cb])},
                "decks_sheets": dist_dict(ref.deck_sheets), "deck_cards": dist_dict(ref.deck_cards),
            }
        for row in rows:
            kind = row["kind"]
            off = None
            if ref:
                off = {"ScenarioBox": ref.scenario_assets, "CampaignBox": ref.campaign_assets}.get(kind)
            line = ("Place of '%s' spawns %d object(s): %d images, %d deck ids, %d cards, deepest Deck uses %d sheets, "
                    "~%.0f MiB decoded textures (RGBA32+mipmaps), %.1f MiB download"
                    % (row["box"], row["placed_objects"], row["images"], row["deck_ids"], row["cards"],
                       row["max_sheets_in_a_deck"], row["texture_mib_est"], row["download_mib"]))
            sev = INFO
            ev = ""
            if off:
                mi = max(d["images"] for d in off)
                md = max(d["deck_ids"] for d in off)
                ev = "official %s: images %s; deck ids %s" % (
                    kind, dist_line([d["images"] for d in off]), dist_line([d["deck_ids"] for d in off]))
                if row["images"] > mi or row["deck_ids"] > md:
                    sev = WARN
            tex = row["texture_mib_est"]
            if tex > 1536:
                sev = ERROR
            elif tex > 512 and sev == INFO:
                sev = WARN
            fix = ""
            if sev != INFO:
                fix = ("Pack faces into sprite sheets (up to 10x7 cells per image) the way SCED does, or at least one "
                       "sheet per Deck; fewer, larger images and fewer CustomDeck ids per Place.")
            self.add(sev, "B01.place-budget", row["where"], line, ev, fix)
            if ref and row["max_sheets_in_a_deck"] > max(ref.deck_sheets or [0]):
                self.add(WARN, "B02.deck-sheets", row["where"],
                         "a Deck in '%s' mixes %d sheets; no official Deck uses more than %d (median %s)"
                         % (row["box"], row["max_sheets_in_a_deck"], max(ref.deck_sheets),
                            fnum(statistics.median(ref.deck_sheets))),
                         "official decks: sheets/deck %s" % dist_line(ref.deck_sheets),
                         "Put a Deck's cards on one sprite sheet (CardID = sheetId*100 + cell).")
        if ref:
            n_cards_per_image = []
            self.report.stats["official_cards_per_image"] = (
                "official boxes: %.1f card objects per distinct deck id (sheet)"
                % (ref.cards_total / float(max(1, len(ref.deck_pairs)))))
        # the same Place measured on the Control/other scripts' UI assets
        refs = sum(r["ui_asset_refs"] for r in rows)
        if refs:
            self.add(INFO, "B03.ui-assets", rows[0]["where"],
                     "%d object(s) in Place units carry CustomUIAssets entries" % refs, "", "")

    # -- C: image files and the pinned commit ------------------------------------------
    def git(self, *args, **kw):
        try:
            return subprocess.run(["git"] + list(args), cwd=self.root, capture_output=True, timeout=60, **kw)
        except (OSError, subprocess.SubprocessError):
            return None

    def check_c(self):
        hosted = collections.OrderedDict()         # url -> [(key, where)]
        external = collections.Counter()
        for doc, key, url, where in self.collect_url_refs():
            if not isinstance(url, str) or not url:
                continue
            if self.hosted_parts(url):
                hosted.setdefault(url, []).append((key, where))
            elif key in IMAGE_URL_KEYS or key == "PDFUrl":
                external[urllib.parse.urlsplit(url).netloc] += 1
        self.report.stats["hosted_urls"] = len(hosted)
        self.report.stats["external_image_hosts"] = dict(external)
        if not hosted:
            return
        origin = None
        r = self.git("remote", "get-url", "origin", text=True)
        if r is not None and r.returncode == 0:
            origin = r.stdout.strip()
        repos = collections.Counter(self.hosted_parts(u)[0] for u in hosted)
        refs = collections.Counter(self.hosted_parts(u)[1] for u in hosted)
        self.report.stats["pinned"] = {"repos": dict(repos), "refs": dict(refs)}
        if origin:
            mine = re.sub(r"(\.git)?/?$", "", origin).split("github.com")[-1].strip("/:")
            for repo in repos:
                if repo.lower() != mine.lower():
                    self.add(WARN, "C03.repo-mismatch", "(urls)",
                             "images are hosted in %s but this checkout's origin is %s" % (repo, mine),
                             "", "Point hosted URLs at the repository that actually holds the files.")
        # 1. files in the working tree
        probs = collections.defaultdict(list)
        stale_v = []
        for url, uses in hosted.items():
            repo, ref, path, q = self.hosted_parts(url)
            first_where = uses[0][1]
            is_pdf = path.lower().endswith(".pdf")
            full = os.path.join(self.root, path)
            if not os.path.isfile(full):
                self.grp(ERROR, "C01.missing-file", "hosted file is not in the working tree (the URL points at nothing "
                         "this repository can serve)", "Re-run publish_hosted.py or fix the URL.").hit(first_where, path)
                continue
            data = open(full, "rb").read()
            v = (q.get("v") or [None])[0]
            if v and sha1(data)[:len(v)] != v:
                stale_v.append(path)
            if is_pdf:
                if not data.startswith(b"%PDF-"):
                    self.grp(ERROR, "C02.pdf", "guide file is not a PDF (no %PDF- header)",
                             "Rebuild the guide.").hit(first_where, path)
                continue
            info = self.image_for(url)
            self.c_image_facts(info, path, first_where, uses)
        if stale_v:
            self.add(WARN, "C03.stale-cache-buster", stale_v[0],
                     "%d URL(s) carry a ?v= hash that does not match the file now in the working tree" % len(stale_v),
                     "e.g. %s" % ", ".join(stale_v[:3]),
                     "Re-run publish_hosted.py so ?v= tracks the content (TTS caches images by URL).",
                     count=len(stale_v), locations=stale_v[1:6])
        self.c_pinned(hosted)
        if self.online:
            self.c_online(hosted)
        self.c_orphans(hosted)
        self.c_orientation()
        self.c_sheets()

    def c_image_facts(self, info, path, where, uses):
        """Format / size / orientation rules for one hosted image."""
        if not info or not info.get("ok"):
            self.grp(ERROR, "C02.bad-image", "hosted file is not a decodable JPEG/PNG (TTS shows a blank texture "
                     "or fails to load it)", "Re-encode the image.").hit(where, "%s: %s" % (path, (info or {}).get("err")))
            return
        kind, w, h = info["kind"], info["width"], info["height"]
        if kind == "jpeg":
            if not info.get("eoi"):
                self.grp(ERROR, "C02.truncated", "JPEG ends without an EOI marker (truncated upload)",
                         "Re-publish the image.").hit(where, path)
            if info.get("progressive"):
                self.grp(WARN, "C02.progressive",
                         "JPEG is progressive (SOF2); TTS guides advise baseline JPEGs and Unity's decoder support "
                         "for progressive scans is not guaranteed",
                         "Save baseline JPEGs: Image.save(..., progressive=False) in pipeline/publish_hosted.py.").hit(
                    where, "%s (%d scans)" % (path, info.get("scans", 0)))
            if info.get("sof_name") not in ("baseline", "progressive", "extended-sequential"):
                self.grp(ERROR, "C02.codec", "JPEG uses a codec Unity cannot decode (arithmetic/lossless)",
                         "Re-encode as baseline Huffman JPEG.").hit(where, "%s: %s" % (path, info.get("sof_name")))
            if info.get("precision") != 8:
                self.grp(ERROR, "C02.precision", "JPEG is not 8 bits per sample", "Re-encode as 8-bit.").hit(
                    where, "%s: %s-bit" % (path, info.get("precision")))
            if info.get("ncomp") == 4 or info.get("adobe_transform") in (2,):
                self.grp(ERROR, "C02.cmyk", "JPEG is CMYK/YCCK (Unity cannot decode it)", "Convert to RGB.").hit(
                    where, path)
            elif info.get("ncomp") == 1:
                self.grp(WARN, "C02.grayscale", "JPEG is single-channel greyscale", "Convert to RGB.").hit(where, path)
            if info.get("orientation") not in (None, 1):
                self.grp(WARN, "C02.exif-orientation", "EXIF orientation is set (Unity ignores it, the art shows "
                         "rotated)", "Bake the rotation into the pixels and strip EXIF.").hit(
                    where, "%s: orientation %s" % (path, info["orientation"]))
            if "ICC" in info.get("app", []):
                self.grp(INFO, "C02.icc", "JPEG embeds an ICC profile (ignored by Unity)", "").hit(where, path)
        elif kind == "png" and info.get("interlaced"):
            self.grp(WARN, "C02.interlaced-png", "PNG is interlaced (some TTS builds fail to read it)",
                     "Save non-interlaced PNGs.").hit(where, path)
        if max(w, h) > 4096:
            self.grp(ERROR if max(w, h) > 16384 else WARN, "C02.dimensions",
                     "image side exceeds 4096 px (a %.0f MiB decoded texture; TTS may downsize it, and above 16384 "
                     "Unity cannot create it)" % (w * h * 4 * 4 / 3.0 / 1048576.0),
                     "Keep sprite sheets within 4096 px on a side.").hit(where, "%s: %dx%d" % (path, w, h))
        if info["bytes"] > 4 * 1048576:
            self.grp(WARN, "C02.filesize", "image file is larger than 4 MiB", "Compress it.").hit(
                where, "%s: %.1f MiB" % (path, info["bytes"] / 1048576.0))
        if w < 8 or h < 8:
            self.grp(ERROR, "C02.tiny", "image is a stub (under 8 px)", "Publish the real art.").hit(where, path)

    def c_pinned(self, hosted):
        """git: does the pinned commit hold exactly these bytes, and is it reachable?"""
        by_ref = collections.defaultdict(list)
        for url in hosted:
            repo, ref, path, q = self.hosted_parts(url)
            by_ref[ref].append(path)
        for ref, paths in sorted(by_ref.items()):
            paths = sorted(set(paths))
            if not HEX40_RE.match(ref):
                self.add(WARN, "C04.unpinned-ref", "(urls)", "hosted URLs use ref '%s', not a commit sha" % ref,
                         "", "Pin the URLs to a commit.")
                continue
            exists = self.git("cat-file", "-e", ref + "^{commit}")
            if exists is None:
                self.report.note("C: git is not available; pinned-commit contents not verified")
                return
            if exists.returncode != 0:
                self.add(WARN, "C04.commit-unknown", "(urls)",
                         "pinned commit %s is not in this clone (cannot verify its files)" % ref[:12],
                         "", "git fetch origin, or verify with --online.")
                continue
            proc = self.git("cat-file", "--batch-check", input=("\n".join("%s:%s" % (ref, p) for p in paths) + "\n").encode())
            lines = proc.stdout.decode("utf-8", "replace").splitlines() if proc else []
            missing, differs, same = [], [], 0
            for p, line in zip(paths, lines):
                if line.endswith(" missing") or " blob " not in line:
                    missing.append(p)
                    continue
                oid = line.split()[0]
                full = os.path.join(self.root, p)
                if os.path.isfile(full) and oid != git_blob_sha(open(full, "rb").read()):
                    differs.append(p)
                else:
                    same += 1
            if missing:
                self.add(ERROR, "C04.pinned-missing", "(urls)",
                         "%d hosted file(s) are not in pinned commit %s: raw.githubusercontent.com answers 404 and "
                         "the card shows blank" % (len(missing), ref[:12]), "e.g. %s" % ", ".join(missing[:3]),
                         "Commit dist/cards and re-pin (publish_hosted.py), then push.", count=len(missing),
                         locations=missing[1:6])
            if differs:
                self.add(WARN, "C04.pinned-differs", "(urls)",
                         "%d hosted file(s) differ between the working tree and pinned commit %s (the owner's TTS "
                         "gets the pinned bytes)" % (len(differs), ref[:12]), "e.g. %s" % ", ".join(differs[:3]),
                         "Re-publish so the pin holds the current images.", count=len(differs), locations=differs[1:6])
            if same:
                self.add(INFO, "C04.pinned-ok", "(urls)",
                         "%d hosted file(s) are byte-identical in the working tree and pinned commit %s"
                         % (same, ref[:12]), "", "")
            rb = self.git("branch", "-r", "--contains", ref, text=True)
            if rb is not None and rb.returncode == 0:
                branches = [b.strip() for b in rb.stdout.splitlines() if b.strip() and "->" not in b]
                if branches:
                    self.add(INFO, "C04.pinned-reachable", "(urls)",
                             "pinned commit %s is on remote ref(s): %s" % (ref[:12], ", ".join(branches[:4])), "", "")
                else:
                    self.add(WARN, "C04.pinned-unpushed", "(urls)",
                             "pinned commit %s is on no remote-tracking branch (raw URLs 404 until it is pushed)" % ref[:12],
                             "", "git push the commit.")

    def c_online(self, hosted):
        ctx = ssl.create_default_context()

        def head(url):
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "audit_database"})
            try:
                with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                    return url, r.status, r.headers.get("Content-Type") or ""
            except urllib.error.HTTPError as e:
                return url, e.code, ""
            except Exception as e:                     # network policy, DNS, TLS ...
                return url, "ERR " + type(e).__name__, str(e)[:80]

        urls = sorted(hosted)
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(head, urls))
        codes = collections.Counter(r[1] for r in res)
        bad = [r for r in res if r[1] != 200]
        self.report.stats["online_head"] = {str(k): v for k, v in codes.items()}
        if bad:
            for url, code, ct in bad[:50]:
                self.grp(ERROR, "C05.http", "hosted URL does not answer HTTP 200 (TTS shows a blank texture)",
                         "Push the pinned commit / fix the URL.").hit(hosted[url][0][1], "%s -> %s %s" % (short(url, 60), code, ct))
        else:
            self.add(INFO, "C05.http-ok", "(urls)", "all %d hosted URLs answered HTTP 200 to HEAD" % len(res),
                     ", ".join("%s x%d" % (k, v) for k, v in sorted(codes.items(), key=str)), "")
        ctypes = collections.Counter(r[2] for r in res if r[1] == 200)
        self.report.stats["online_content_types"] = dict(ctypes)
        wrong = [r for r in res if r[1] == 200 and r[0].split("?")[0].lower().endswith((".jpg", ".jpeg"))
                 and not r[2].startswith("image/")]
        if wrong:
            self.add(WARN, "C05.content-type", wrong[0][0], "%d image URL(s) are not served as image/*" % len(wrong))
        sample = [u for u in urls if u.split("?")[0].lower().endswith((".jpg", ".jpeg", ".pdf"))][:4]
        for u in sample:
            path = self.hosted_parts(u)[2]
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "audit_database"}),
                                            timeout=60, context=ctx) as r:
                    body = r.read()
            except Exception as e:
                self.add(WARN, "C05.get", u, "GET failed", str(e)[:80])
                continue
            full = os.path.join(self.root, path)
            if os.path.isfile(full) and sha1(body) != sha1(open(full, "rb").read()):
                self.add(ERROR, "C05.bytes", u, "served bytes differ from the working-tree file (wrong art in TTS)",
                         path, "Re-publish and re-pin.")

    def c_orphans(self, hosted):
        used = {self.hosted_parts(u)[2] for u in hosted}
        cards_dir = os.path.join(self.root, "dist", "cards")
        if not os.path.isdir(cards_dir) or not any(d.role == "saved" for d in self.docs):
            return
        extra = sorted(f for f in os.listdir(cards_dir) if f.lower().endswith((".jpg", ".png"))
                       and "dist/cards/" + f not in used)
        if extra:
            self.add(INFO, "C06.orphans", "dist/cards",
                     "%d image(s) in dist/cards are referenced by none of the audited files" % len(extra),
                     "e.g. %s" % ", ".join(extra[:4]),
                     "Delete them or ignore (they only cost repository size).", count=len(extra))

    # -- C (continued): card image orientation and aspect --------------------------------
    def c_orientation(self):
        """Card faces/backs on 1x1 sheets must be landscape iff the card is sideways."""
        seen = set()
        aspects = collections.Counter()
        for doc in self.docs:
            for node in cards_of(doc):
                o = node.obj
                cd = o.get("CustomDeck")
                if not isinstance(cd, dict):
                    continue
                side = bool(o.get("SidewaysCard"))
                ok, gm, _ = parse_gmnotes(o)
                is_mini = bool(gm) and gm.get("type") == "Minicard"
                for deck, e in cd.items():
                    if not isinstance(e, dict) or e.get("NumWidth") != 1 or e.get("NumHeight") != 1:
                        continue
                    if (doc.name, deck) in seen:
                        continue
                    seen.add((doc.name, deck))
                    for key in ("FaceURL", "BackURL"):
                        if key == "BackURL" and not e.get("UniqueBack"):
                            continue
                        info = self.image_for(e.get(key))
                        if not info or not info.get("ok"):
                            continue
                        w, h = info["width"], info["height"]
                        landscape = w > h
                        if landscape != side:
                            self.grp(WARN, "C07.orientation",
                                     "image orientation does not match SidewaysCard (TTS stretches it onto the card mesh)",
                                     "Render sideways cards landscape and upright cards portrait.").hit(
                                doc.where(node), "%s %dx%d, SidewaysCard %s" % (key, w, h, side))
                            continue
                        ratio = min(w, h) / float(max(w, h))
                        aspects[(round(ratio, 3), is_mini)] += 1
                        if abs(ratio - 5.0 / 7.0) > 0.075 * (5.0 / 7.0):
                            self.grp(INFO if is_mini else WARN, "C07.aspect",
                                     "image aspect differs from the 5:7 card shape by more than 7% (stretched on the card)",
                                     "Render at 5:7 (750x1050).").hit(doc.where(node), "%s %dx%d (%.3f)" % (key, w, h, ratio))
        self.report.stats["card_image_aspects"] = {"%.3f%s" % (k[0], " (minicard)" if k[1] else ""): v
                                                    for k, v in sorted(aspects.items())}

    def c_sheets(self):
        """Sprite sheets (NumWidth x NumHeight > 1): the image must divide into 5:7 cells and a unique-back
        sheet needs a back image of the same size (otherwise cards are cropped or stretched)."""
        seen = set()
        sheets = 0
        for doc in self.primary:
            for node in doc.nodes:
                cd = node.obj.get("CustomDeck")
                if not isinstance(cd, dict):
                    continue
                for deck, e in cd.items():
                    if not isinstance(e, dict) or (doc.name, deck) in seen:
                        continue
                    nw, nh = e.get("NumWidth"), e.get("NumHeight")
                    if not (is_int(nw) and is_int(nh)) or nw * nh <= 1 or nw < 1 or nh < 1:
                        continue
                    seen.add((doc.name, deck))
                    sheets += 1
                    face = self.image_for(e.get("FaceURL"))
                    if not face or not face.get("ok"):
                        continue
                    cw, ch = face["width"] / float(nw), face["height"] / float(nh)
                    ratio = min(cw, ch) / max(cw, ch)
                    if abs(ratio - 5.0 / 7.0) > 0.05 * (5.0 / 7.0):
                        self.grp(WARN, "C08.sheet-grid",
                                 "sprite sheet cells are not 5:7 (the grid does not match the image: cards come out "
                                 "cropped or stretched)", "Make width/NumWidth : height/NumHeight = 5 : 7.").hit(
                            doc.where(node), "deck %s: %dx%d px in a %dx%d grid = %.0fx%.0f cells (%.3f)" % (
                                deck, face["width"], face["height"], nw, nh, cw, ch, ratio))
                    if e.get("UniqueBack") is True:
                        back = self.image_for(e.get("BackURL"))
                        if back and back.get("ok") and (back["width"], back["height"]) != (face["width"], face["height"]):
                            self.grp(WARN, "C08.sheet-back", "UniqueBack sheet: the back image is not the size of the "
                                     "face image (backs are read with the same grid)", "Render the back sheet at "
                                     "the face sheet's size.").hit(doc.where(node), "deck %s: face %dx%d, back %dx%d" % (
                                         deck, face["width"], face["height"], back["width"], back["height"]))
        self.report.stats["sprite_sheets"] = sheets

    # -- D: SCED data model -----------------------------------------------------------
    def check_d(self):
        ref, src = self.ref, self.src
        uniq = collections.OrderedDict()           # (card id, canonical GMNotes) -> (doc, node, gm)
        for doc in self.docs:
            for node in cards_of(doc):
                ok, gm, raw = parse_gmnotes(node.obj)
                if not gm:
                    continue
                key = (gm.get("id") if isinstance(gm.get("id"), str) else id(node), json.dumps(gm, sort_keys=True))
                uniq.setdefault(key, (doc, node, gm))
        self.d_cards(uniq, ref, src)
        self.d_special_objects(ref, src)
        self.d_locations(uniq, ref)
        self.d_relations(uniq, ref)
        self.d_tags_vs_sced(ref, src)

    def d_cards(self, uniq, ref, src):
        cycles = collections.Counter()
        unknown_keys = collections.defaultdict(set)
        known_types = set(ref.gm_card_count) if ref else set()
        for (cid, _sig), (doc, node, gm) in uniq.items():
            where = doc.where(node)
            typ = gm.get("type")
            if not isinstance(gm.get("id"), str) or not gm.get("id"):
                self.grp(ERROR, "D01.id", "GMNotes has no string id (SCED indexes cards by md.id)",
                         "Write a unique id string.").hit(where)
            if not isinstance(typ, str):
                self.grp(ERROR if typ is not None else WARN, "D01.type", "GMNotes type is missing or not a string",
                         "Use an official type such as Asset, Enemy, Location.").hit(where, short(typ))
            elif ref and typ not in known_types and typ is not None:
                folded = {t.lower(): t for t in known_types if isinstance(t, str)}
                if typ.lower() in folded:
                    self.grp(ERROR, "D01.type-case", "GMNotes type differs from the official spelling only by case "
                             "(SCED compares exact strings: md.type == \"%s\")" % folded[typ.lower()],
                             "Use %s." % folded[typ.lower()]).hit(where, typ)
                else:
                    self.grp(WARN, "D01.type-unknown", "GMNotes type is not one the official data uses",
                             "Use an official type.").hit(where, typ)
            if "cycle" in gm:
                cycles[gm["cycle"]] += 1
            if not ref:
                continue
            for k, v in gm.items():
                kt = ref.gm_key_types.get(k)
                if kt is None:
                    unknown_keys[k].add(hk(gm.get("id")))
                    continue
                if tname(v) not in kt:
                    self.grp(ERROR, "D01.value-type",
                             "GMNotes value has a type no official card uses for this key (SCED code compares/indexes it)",
                             "Write %s as %s (or omit it)." % (k, "/".join(sorted(kt)))).hit(
                        where, "%s=%s (%s); official: %s" % (k, short(v, 24), tname(v),
                                                             ", ".join("%s x%d" % kv for kv in kt.most_common(2))))
            req = ref.required_keys(typ) if isinstance(typ, str) else set()
            miss = sorted(k for k in req if k not in gm)
            if miss:
                self.grp(WARN, "D01.missing-keys",
                         "GMNotes lacks keys ≥90%% of official %s cards carry" % typ,
                         "Add them.").hit(where, ", ".join(miss))
            cls = gm.get("class")
            if isinstance(cls, str):
                vocab = ref.gm_vals["class"]
                if cls not in vocab:
                    low = {v.lower(): v for v in vocab}
                    self.grp(ERROR if cls.lower() in low else WARN, "D01.class",
                             "class is not an official value (SCED compares class strings exactly)",
                             "Use Guardian, Seeker, Rogue, Mystic, Survivor, Neutral, Mythos (| for dual class).").hit(
                        where, cls)
            slot = gm.get("slot")
            if isinstance(slot, str) and slot not in ref.gm_vals["slot"]:
                self.grp(WARN, "D01.slot", "slot is not an official value", "Use e.g. Hand, Hand x2, Arcane, Ally, "
                         "Accessory, Body.").hit(where, slot)
            tr = gm.get("traits")
            if isinstance(tr, str) and (not tr.strip() or not TRAITS_RE.match(tr.strip())):
                self.grp(WARN, "D01.traits", "traits are not 'Trait. Trait.' formatted (official data always is)",
                         "Write 'Item. Weapon.'.").hit(where, short(tr, 40))
            for k in ("level", "cost", "health", "sanity", "willpowerIcons", "intellectIcons", "combatIcons",
                      "agilityIcons", "wildIcons", "doomThreshold", "victory"):
                v = gm.get(k)
                if is_int(v) and k in ref.int_range:
                    lo, hi = ref.int_range[k]
                    if not lo <= v <= hi:
                        self.grp(WARN, "D01.range", "numeric value outside the range seen in official data",
                                 "Check it.").hit(where, "%s=%s (official %s..%s)" % (k, v, lo, hi))
            use_lists = [("uses", gm.get("uses"))] + [(sd + ".uses", gm[sd].get("uses")) for sd in
                                                      ("locationFront", "locationBack") if isinstance(gm.get(sd), dict)]
            tokens_ok = {t for (_ty, t) in ref.use_pairs}
            for label, u in use_lists:
                if not isinstance(u, list):
                    continue
                for e in u:
                    if not isinstance(e, dict) or not ("count" in e or "countPerInvestigator" in e or "replenish" in e) \
                            or not isinstance(e.get("type"), str) or not isinstance(e.get("token"), str):
                        self.grp(WARN, "D01.uses", "uses entry is not {count|countPerInvestigator, type, token}",
                                 "Follow SCED's uses shape.").hit(where, short(e, 50))
                    elif e["token"] not in tokens_ok:
                        self.grp(WARN, "D01.uses-token",
                                 "uses.token names no token template SCED has (TokenManager raises 'Unknown token type' "
                                 "when it has to spawn one; official Secret/Charge/Supply/... uses all say token "
                                 "'resource')", "Use token 'resource' with the use name in `type` "
                                 "(official tokens: %s)." % ", ".join(sorted(tokens_ok))).hit(
                            where, "%s: type=%s token=%s count=%s" % (label, e.get("type"), e["token"], e.get("count")))
        if unknown_keys:
            keys = sorted(unknown_keys)
            self.add(INFO, "D01.custom-keys", "(GMNotes)",
                     "GMNotes keys no official card uses (harmless to SCED, read only by this campaign's scripts)",
                     "; ".join("%s x%d" % (k, len(unknown_keys[k])) for k in keys),
                     "", count=sum(len(v) for v in unknown_keys.values()))
        if cycles:
            if len(cycles) > 1:
                self.add(WARN, "D06.cycle", "(GMNotes)", "cards carry %d different cycle values" % len(cycles),
                         ", ".join("%s x%d" % kv for kv in cycles.most_common(4)),
                         "Use one cycle value per campaign.")
            elif ref:
                c = next(iter(cycles))
                if c not in ref.gm_vals["cycle"]:
                    self.add(INFO, "D06.cycle", "(GMNotes)",
                             "cycle '%s' is not an official cycle name (fine for a fan campaign)" % c, "", "")

    def d_special_objects(self, ref, src):
        """GMNotes/tags of box, log, guide objects."""
        shape = {"CampaignBox": ("id", "type", "filename"), "ScenarioBox": ("id", "type"),
                 "CampaignLog": ("id", "type"), "CampaignGuide": ("id", "type")}
        seen_ids = collections.defaultdict(list)
        for doc in self.primary:
            for node in doc.nodes:
                o = node.obj
                if o.get("Name") in ("Card", "CardCustom", "Deck"):
                    continue
                ok, gm, raw = parse_gmnotes(o)
                if not gm or gm.get("type") not in shape:
                    continue
                typ = gm["type"]
                where = doc.where(node)
                for k in shape[typ]:
                    if not isinstance(gm.get(k), str) or not gm[k]:
                        self.grp(ERROR if typ == "CampaignBox" and k == "filename" else WARN, "D08.box-gmnotes",
                                 "%s GMNotes lacks a string '%s' (SCED reads it)" % (typ, k),
                                 "Add it.").hit(where)
                seen_ids[(typ, gm.get("id"))].append(where)
                want_tags = {"CampaignBox": {"CampaignBox"}, "CampaignLog": {"CampaignLog"},
                             "CampaignGuide": {"CampaignGuide"}}.get(typ, set())
                tags = set(taglist(o))
                for t in sorted(want_tags - tags):
                    self.grp(ERROR, "D03.tag-missing",
                             "object lacks the tag SCED looks it up by (%s)" % t,
                             "Add the tag.").hit(where, t)
                if typ == "CampaignBox" and "Reloadable" not in tags:
                    self.grp(INFO, "D03.reloadable", "campaign box lacks 'Reloadable' (no 'Redownload this' menu)",
                             "").hit(where)
                if ref:
                    n = ref.gmtype_count.get(typ, 0)
                    for t, c in ref.tags_by_gmtype.get(typ, {}).items():
                        if n and c / float(n) >= 0.5 and t not in tags:
                            special = bool(src and t in src.special_tags)
                            self.grp(WARN if special else INFO, "D03.tag-official",
                                     "%s objects in official boxes usually carry tag '%s'%s" % (
                                         typ, t, " (SCED code checks it)" if special else ""),
                                     "Add the tag to the %s." % typ).hit(where, "%s on %d%% of %d official" % (
                                         t, 100 * c // n, n))
        # GMNotes ids of boxes must not collide with official ones
        if ref:
            for (typ, ident), locs in seen_ids.items():
                if ident in ref.ids:
                    self.add(ERROR, "D02.id-collision", locs[0], "%s id '%s' is also an official card/object id" % (typ, ident))

    def d_locations(self, uniq, ref):
        """Connection symbols: SCED pairs letters-only icon tokens (PlayArea gmatch %a+)."""
        icons = collections.defaultdict(set)         # token -> {(doc, id)}
        for (cid, _sig), (doc, node, gm) in uniq.items():
            if gm.get("type") != "Location":
                continue
            where = doc.where(node)
            for side in ("locationFront", "locationBack"):
                s = gm.get(side)
                if s is None:
                    self.grp(WARN, "D04.location-side", "Location lacks %s (SCED tracks the side that is face up)" % side,
                             "Give both sides (they may be identical).").hit(where)
                    continue
                if not isinstance(s, dict):
                    self.grp(ERROR, "D04.location-side", "%s is not an object" % side, "").hit(where)
                    continue
                for field in ("icons", "connections"):
                    v = s.get(field)
                    if v is None:
                        continue
                    if not isinstance(v, str) or (v and not ICON_TOKEN_RE.match(v)):
                        self.grp(ERROR, "D04.icon-format",
                                 "icons/connections must be letters-only symbols joined by '|' (SCED splits on %a+; "
                                 "digits and punctuation vanish)", "Use e.g. 'Circle|Square'.").hit(
                            where, "%s.%s=%s" % (side, field, short(v, 40)))
                        continue
                    toks = [t for t in v.split("|") if t]
                    if field == "icons":
                        for t in toks:
                            icons[t].add(cid)
                if "uses" in s and not isinstance(s["uses"], list):
                    self.grp(ERROR, "D04.location-uses", "locationFront/Back.uses must be a list", "").hit(where)
        dangling = collections.Counter()
        first = {}
        for (cid, _sig), (doc, node, gm) in uniq.items():
            if gm.get("type") != "Location":
                continue
            for side in ("locationFront", "locationBack"):
                s = gm.get(side)
                if isinstance(s, dict) and isinstance(s.get("connections"), str):
                    for t in s["connections"].split("|"):
                        if t and t not in icons:
                            dangling[t] += 1
                            first.setdefault(t, doc.where(node))
        if dangling:
            t = sorted(dangling)[0]
            self.add(WARN, "D04.connection-dangling",  first[t],
                     "%d connection symbol(s) match no location's icons (the line is never drawn)" % len(dangling),
                     ", ".join("%s x%d" % kv for kv in sorted(dangling.items())[:5]),
                     "Every connection token must appear in some location's icons.", count=len(dangling))
        if ref and icons:
            def base_of(t):
                b = re.sub(r"[A-Z][a-z]+$", "", t)
                return b or t
            ours_base = {base_of(t) for t in icons}
            unknown = sorted(ours_base - set(ref.loc_symbols))
            if unknown:
                self.add(INFO, "D04.symbol-vocabulary", "(locations)",
                         "symbol base names no official location uses (SCED only matches letter strings, so any name "
                         "works; the trailing colour word is this campaign's disambiguator)",
                         "%s (official: %s)" % (", ".join(unknown), ", ".join(sorted(ref.loc_symbols)[:8]) + ", ..."), "")
        self.report.stats["location_symbols"] = len(icons)

    def d_relations(self, uniq, ref):
        """Investigator signatures, minicards, id hygiene, collisions with official ids."""
        by_doc = collections.defaultdict(dict)
        for (cid, _sig), (doc, node, gm) in uniq.items():
            if isinstance(gm.get("id"), str):
                by_doc[doc.name][gm["id"]] = (doc, node, gm)
        all_ids = {}
        for name, d in by_doc.items():
            all_ids.update(d)
        if ref:
            hit = sorted(i for i in all_ids if i in ref.ids)
            if hit:
                self.add(ERROR, "D02.id-collision", "(GMNotes)",
                         "%d card id(s) are also official SCED card ids (SCED's AllCardsBag and deck importer would "
                         "resolve them to the wrong card)" % len(hit), ", ".join(hit[:6]),
                         "Prefix ids with the campaign code.", count=len(hit))
            else:
                self.add(INFO, "D02.ids-official", "(GMNotes)",
                         "none of our %d card ids collides with the %d official ids (save + boxes)"
                         % (len(all_ids), len(ref.ids)), "", "")
        prefixes = collections.Counter(re.split(r"[-_]", i)[0] for i in all_ids)
        self.report.stats["id_prefixes"] = dict(prefixes.most_common(5))
        for dname, d in by_doc.items():
            ids = set(d)
            for gid, (doc, node, gm) in d.items():
                where = doc.where(node)
                typ = gm.get("type")
                if typ == "Investigator":
                    if gid + "-m" not in all_ids:
                        self.grp(WARN, "D05.minicard", "Investigator has no Minicard with id '<id>-m' (SCED finds the "
                                 "minicard that way)", "Ship the minicard.").hit(where, gid)
                    sigs = gm.get("signatures")
                    if isinstance(sigs, list):
                        for entry in sigs:
                            if not isinstance(entry, dict):
                                self.grp(ERROR, "D05.signatures", "signatures entry is not {id: count}", "").hit(where)
                                continue
                            for sid, n in entry.items():
                                if not is_int(n) or n < 1:
                                    self.grp(ERROR, "D05.signatures", "signature count must be a positive integer",
                                             "").hit(where, "%s=%s" % (sid, short(n)))
                                if sid not in all_ids and not (ref and sid in ref.ids):
                                    self.grp(WARN, "D05.signature-dangling", "signature id is on no card in the audited files "
                                             "(deck building cannot add it)", "Ship the card.").hit(where, sid)
                    elif sigs is not None:
                        self.grp(ERROR, "D05.signatures", "signatures must be a list", "").hit(where)
                    es = gm.get("elderSignEffect")
                    if isinstance(es, dict):
                        if not isinstance(es.get("description"), str):
                            self.grp(WARN, "D05.elder-sign", "elderSignEffect lacks a description string", "").hit(where)
                        if "modifier" in es and not is_int(es["modifier"]):
                            self.grp(ERROR, "D05.elder-sign", "elderSignEffect.modifier must be an integer", "").hit(where)
                if typ == "ScenarioReference":
                    tk = gm.get("tokens")
                    if isinstance(tk, dict):
                        for side, toks in tk.items():
                            if side not in ("front", "back") or not isinstance(toks, dict):
                                self.grp(ERROR, "D06.tokens", "tokens must be {front:{...}, back:{...}}", "").hit(where, side)
                                continue
                            for tn, tv in toks.items():
                                if ref and tn not in ref.token_names:
                                    self.grp(WARN, "D06.token-name", "chaos token name is not one official reference "
                                             "cards use", "Use Skull, Cultist, Tablet, Elder Thing.").hit(where, tn)
                                if not isinstance(tv, dict) or not isinstance(tv.get("description"), str) \
                                        or not is_int(tv.get("modifier")):
                                    self.grp(ERROR, "D06.token-shape", "token entry must be {description:str, modifier:int}",
                                             "").hit(where, "%s.%s" % (side, tn))
                    elif tk is not None:
                        self.grp(ERROR, "D06.tokens", "tokens must be an object", "").hit(where)
                if typ == "Minicard" and gid.endswith("-m") and gid[:-2] not in all_ids and not (ref and gid[:-2] in ref.ids):
                    self.grp(WARN, "D05.minicard-orphan", "Minicard belongs to no investigator in the audited files",
                             "").hit(where, gid)

    def d_tags_vs_sced(self, ref, src):
        """Card tag sets against the official norm for the same type; SCED's special tags."""
        used = collections.Counter()
        for doc in self.docs:
            for node in doc.nodes:
                for t in taglist(node.obj):
                    used[t] += 1
        self.report.stats["tags_used"] = dict(sorted(used.items()))
        if src:
            self.report.stats["sced_special_tags"] = dict(src.special_tags.most_common())
            special = {t: src.special_tags[t] for t in used if t in src.special_tags}
            self.report.stats["tags_used_that_sced_checks"] = dict(sorted(special.items()))
            ours_only = sorted(t for t in used if t not in src.special_tags and (not ref or t not in
                                                                                ref.tags_by_name.get("Card", {}) and
                                                                                not any(t in c for c in ref.tags_by_name.values())))
            if ours_only:
                self.add(INFO, "D03.tags-custom", "(tags)", "tags no SCED code or official object uses (campaign-internal)",
                         ", ".join(ours_only), "")
        if not ref:
            return
        for doc in self.primary:
            for node in cards_of(doc):
                o = node.obj
                ok, gm, _ = parse_gmnotes(o)
                if not gm or not isinstance(gm.get("type"), str):
                    continue
                tset = tuple(sorted(taglist(o)))
                counts = ref.tagset_by_type.get(gm["type"])
                if not counts or sum(counts.values()) < 20:
                    continue
                total = sum(counts.values())
                if counts.get(tset, 0) / float(total) < 0.01:
                    nearest = min(counts, key=lambda k: (len(set(tset) ^ set(k)), -counts[k], k))
                    diff = set(tset) ^ set(nearest)
                    special = bool(src and any(t in src.special_tags for t in diff))
                    self.grp(WARN if special else INFO, "D03.tagset",
                             "card tag set is not one official %s cards use (>=1%%)%s" % (
                                 gm["type"], "; the difference includes a tag SCED code checks" if special else
                                 "; SCED code checks none of the differing tags"),
                             "Official: %s" % ", ".join("[%s] %d%%" % (",".join(k), 100 * c // total)
                                                         for k, c in counts.most_common(2))).hit(
                        doc.where(node), "[%s]" % ", ".join(tset))
                tags = set(tset)
                if gm["type"] == "Location" and "Location" not in tags:
                    self.grp(WARN, "D03.location-tag", "Location card lacks the 'Location' tag SCED's play area needs "
                             "to track pick-ups", "Tag it Location + ScenarioCard.").hit(doc.where(node))
                if gm["type"] == "Minicard" and "Minicard" not in tags:
                    self.grp(WARN, "D03.minicard-tag", "Minicard lacks the 'Minicard' tag SCED finds minicards by",
                             "Tag it Minicard.").hit(doc.where(node))
                both = {"PlayerCard", "ScenarioCard"} <= tags
                if both:
                    self.grp(WARN, "D03.both-deck-tags", "card has both PlayerCard and ScenarioCard "
                             "(CardBackEnhancer cannot pick its back)", "Keep one.").hit(doc.where(node))

    # -- E: Lua ------------------------------------------------------------------------
    def collect_scripts(self):
        scripts = collections.OrderedDict()
        for doc in self.docs:
            for node in doc.nodes:
                s = node.obj.get("LuaScript")
                if isinstance(s, str) and s.strip():
                    h = sha1_text(s)[:12]
                    e = scripts.setdefault(h, {"hash": h, "text": s, "uses": [], "names": collections.Counter(),
                                               "min_depth": 99, "files": set()})
                    e["uses"].append((doc, node))
                    e["names"][node.obj.get("Name")] += 1
                    e["min_depth"] = min(e["min_depth"], node.depth)
                    e["files"].add(doc.name)
        return scripts

    @staticmethod
    def script_label(e):
        doc, node = e["uses"][0]
        return "%s '%s' (%s, +%d more)" % (node.obj.get("Name"), node.obj.get("Nickname") or "", doc.name,
                                          len(e["uses"]) - 1) if len(e["uses"]) > 1 else "%s '%s' (%s)" % (
            node.obj.get("Name"), node.obj.get("Nickname") or "", doc.name)

    def check_e(self):
        scripts = self.collect_scripts()
        luacs = find_luac() if self.use_luac else {}
        ref, src = self.ref, self.src
        inventory = []
        if not scripts:
            self.add(INFO, "E00.none", "(files)", "no LuaScript found in the audited files")
            return
        if not luacs:
            self.report.note("E: luac not found (or disabled): syntax checked by the built-in lexer only")
        for e in scripts.values():
            text = e["text"]
            where = self.script_where(e)
            toks = lua_tokens(text)
            funcs, assigns = lua_toplevel(toks)
            e["funcs"], e["assigns"] = funcs, assigns
            row = {"hash": e["hash"], "chars": len(text), "bytes": len(text.encode("utf-8", "replace")),
                   "lines": text.count("\n") + 1, "objects": len(e["uses"]), "names": dict(e["names"]),
                   "min_depth": e["min_depth"], "syntax": {}, "files": sorted(e["files"])}
            # syntax with every luac we have; MoonSharp is Lua 5.2 flavoured
            syntax_ok = {}
            for ver, path in luacs.items():
                rc, out, err = run_luac(path, text)
                syntax_ok[ver] = rc == 0
                row["syntax"][ver] = "ok" if rc == 0 else err.strip().splitlines()[0][:120] if err.strip() else "failed"
            if luacs:
                if "5.2" in luacs and not syntax_ok["5.2"]:
                    self.grp(ERROR, "E01.syntax", "Lua does not compile under 5.2 (TTS's MoonSharp is 5.2-flavoured): "
                             "the object's script fails to load", "Fix the syntax.").hit(where, row["syntax"]["5.2"])
                elif "5.2" not in luacs and not any(syntax_ok.values()):
                    self.grp(ERROR, "E01.syntax", "Lua does not compile (%s)" % ", ".join(sorted(luacs)),
                             "Fix the syntax.").hit(where, "; ".join(row["syntax"].values())[:150])
                elif "5.2" in luacs and any(not v for v in syntax_ok.values()):
                    self.grp(INFO, "E01.syntax-newer", "compiles under 5.2 but not under another installed Lua",
                             "").hit(where, str(row["syntax"]))
            # API use TTS lacks
            hits = lua_api_use(toks)
            own_require = any(f in ("require",) for f in funcs) or "require" in assigns or \
                bool(re.search(r"\blocal\s+function\s+require\b|\blocal\s+require\s*=", text))
            by_rule = collections.defaultdict(list)
            for rule, detail, line in hits:
                if rule == "require" and own_require:
                    continue
                by_rule[rule].append((detail, line))
            msgs = {
                "forbidden-lib": (ERROR, "script uses a library TTS does not provide", "Remove it."),
                "forbidden-os": (ERROR, "script calls an os function TTS removes", "Remove it."),
                "require": (ERROR, "script require()s a module that does not exist at runtime in a saved object "
                            "(TTS has no module path here; SCED bundles modules at build time)",
                            "Inline the module (luabundle-style) before saving."),
                "lua53-lib": (ERROR, "script uses a Lua 5.3+ library function MoonSharp lacks", "Use 5.2 APIs."),
                "lua53-syntax": (ERROR, "script uses Lua 5.3+ operators MoonSharp lacks", "Use 5.2 syntax."),
                "goto": (INFO, "script uses goto (MoonSharp support is partial)", ""),
            }
            for rule, items in by_rule.items():
                sev, msg, fix = msgs[rule]
                self.grp(sev, "E02." + rule, msg, fix).hit(where, ", ".join(
                    sorted({"%s@%d" % (d, l) for d, l in items})[:4]))
            # globals defined at chunk level
            bursts = lua_spawn_loops(toks)
            row["spawn_bursts"] = [{"line": ln, "call": c} for ln, c in bursts]
            if bursts:
                self.grp(INFO, "E06.spawn-burst", "script spawns objects inside a loop with no Wait/coroutine: every "
                         "object (and its textures) is created in one frame",
                         "Stage spawns with Wait.frames when a Place spawns many objects.").hit(
                    where, ", ".join("%s@%d" % (c, ln) for ln, c in bursts[:3]))
            row["globals"] = sorted(set(funcs) | set(assigns))
            for g in sorted(set(funcs) | set(assigns)):
                base = g.split(".")[0].split(":")[0]
                if base in TTS_API_GLOBALS:
                    self.grp(WARN, "E03.shadows-tts", "script redefines a TTS built-in at chunk level (breaks every "
                             "call to it from this script)", "Rename it.").hit(where, base)
            frames = [f for f in funcs if f in LUA_FRAME_HOOKS]
            if frames and e["min_depth"] > 0:
                self.grp(WARN, "E03.frame-hook", "script defines onUpdate/onFixedUpdate on an object that spawns "
                         "from inside a bag (runs every frame once placed)", "Use Wait.* timers.").hit(where, ", ".join(frames))
            if src:
                api = sorted(set(g.split(".")[0] for g in funcs) & src.object_calls)
                row["implements_sced_object_api"] = api
                shadow = sorted(set(g.split(".")[0] for g in set(funcs) | set(assigns)) & src.global_functions
                                - TTS_GLOBALS)
                row["same_name_as_sced_global"] = shadow
            # undefined global reads (typos, or names that only exist in another script's scope)
            lc = luacs.get("5.2") or (next(iter(luacs.values())) if luacs else None)
            if lc:
                rc, listing, err = run_luac(lc, text, listing=True)
                if rc == 0:
                    reads, writes = luac_global_access(listing)
                    defined = set(writes) | {g.split(".")[0].split(":")[0] for g in funcs} | set(assigns)
                    undefined = {n: l for n, l in reads.items() if n not in TTS_GLOBALS and n not in defined}
                    row["undefined_globals"] = sorted(undefined)
                    for n, line in sorted(undefined.items()):
                        sev = WARN
                        msg = ("script reads global '%s' that is neither defined in it nor provided by TTS "
                               "(nil at runtime; SCED's own modules are file-local, not globals)" % n)
                        fix = "Define it, or call SCED through Global.call(...)."
                        self.grp(sev, "E04.undefined-global", msg, fix).hit(where, "line %d" % line)
            inventory.append(row)
        self.report.stats["lua_scripts"] = inventory
        # scripts inside bags vs official
        contained = collections.Counter()
        biggest = (0, "")
        for e in scripts.values():
            for doc, node in e["uses"]:
                if node.depth > 0:
                    contained[node.obj.get("Name")] += 1
            if len(e["text"]) > biggest[0]:
                biggest = (len(e["text"]), e)
        self.report.stats["lua_on_contained_objects"] = dict(contained)
        if ref and ref.lua_contained_sizes:
            mx = max(ref.lua_contained_sizes)
            n, e = biggest
            if n > mx:
                self.add(WARN, "E05.script-size", self.script_where(e),
                         "script of %d chars on a contained object is larger than any in official boxes (max %d, median %d)"
                         % (n, mx, statistics.median(ref.lua_contained_sizes)),
                         "TTS reparses it on every spawn/load; a 200 KB script on a placed object is slow to start",
                         "Keep heavy logic in one scene object, not one per spawn.")
            by_name = {k: v for k, v in contained.items()}
            card_scripts = by_name.get("Card", 0) + by_name.get("Deck", 0) + by_name.get("CardCustom", 0)
            if card_scripts:
                self.add(WARN, "E05.card-scripts", "(scripts)", "%d Card/Deck object(s) inside bags carry a LuaScript "
                         "(official: %d of %d contained cards)" % (card_scripts, ref.lua_by_name.get(("Card", True), 0),
                                                                    ref.contained_by_name.get("Card", 0)), "", "")
            else:
                self.add(INFO, "E05.card-scripts", "(scripts)",
                         "no Card/Deck inside any bag carries a LuaScript (official: %d of %d contained cards do)"
                         % (ref.lua_by_name.get(("Card", True), 0), ref.contained_by_name.get("Card", 0)), "", "")
        self.add(INFO, "E00.inventory", "(scripts)",
                 "%d distinct LuaScript(s): %s" % (len(inventory), "; ".join(
                     "%s %d chars x%d [%s]" % (r["hash"][:6], r["chars"], r["objects"],
                                               "/".join("%s %s" % (k, v if v == "ok" else "FAIL")
                                                        for k, v in sorted(r["syntax"].items()))) for r in inventory)), "", "")
        self.e_freshness(scripts)

    @staticmethod
    def script_where(e):
        doc, node = e["uses"][0]
        return doc.where(node)

    def src_text(self, rel_path):
        p = os.path.join(self.root, rel_path)
        try:
            return open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            return None

    def apply_names(self, s):
        c = self.campaign
        if not c:
            return s
        for old, new in (("THE STILL HOUR", c.get("upper_name")), ("The Still Hour", c.get("name")),
                         ("the_still_hour", c.get("slug")), ("StillHour", c.get("tag")),
                         ("sthrLog_", (c.get("prefix") or "") + "Log_"), ("Still Hour", c.get("box_name"))):
            if new and old != new:
                s = s.replace(old, new)
        return s

    def e_freshness(self, scripts):
        """Do the embedded scripts match the sources the build is made from?"""
        roles = [("src/tts/memory_bag.lua", "campaign box (SCED MemoryBag)", lambda gm, o: gm.get("type") == "CampaignBox"
                  and o.get("Name") == "Custom_Model_Bag"),
                 ("src/tts/loop_box.lua", "scenario box (replayable Place)", lambda gm, o: gm.get("type") == "ScenarioBox"),
                 ("src/tts/download_box.lua", "placeholder download box",
                  lambda gm, o: gm.get("type") == "CampaignBox" and o.get("Name") == "Bag")]
        for rel_path, label, pick in roles:
            srctext = self.src_text(rel_path)
            if srctext is None:
                continue
            want = self.apply_names(srctext)
            found = []
            for e in scripts.values():
                for doc, node in e["uses"]:
                    ok, gm, _ = parse_gmnotes(node.obj)
                    if gm and pick(gm, node.obj):
                        found.append((doc, node, e))
            for doc, node, e in found[:1]:
                if e["text"] != want:
                    sf = set(lua_toplevel(lua_tokens(want))[0])
                    ef = set(lua_toplevel(lua_tokens(e["text"]))[0])
                    only_src = sorted(sf - ef)
                    only_emb = sorted(ef - sf)
                    burst_emb = bool(lua_spawn_loops(lua_tokens(e["text"])))
                    burst_src = bool(lua_spawn_loops(lua_tokens(want)))
                    import difflib
                    dl = list(difflib.unified_diff(e["text"].splitlines(), want.splitlines(), lineterm="", n=0))
                    added = sum(1 for l in dl if l.startswith("+") and not l.startswith("+++"))
                    removed = sum(1 for l in dl if l.startswith("-") and not l.startswith("---"))
                    self.add(WARN, "E07.stale-script", doc.where(node),
                             "the %s script embedded in the shipped data differs from %s (the build is stale: source "
                             "changes after the last publish are not in the files the owner loads)" % (label, rel_path),
                             "embedded %d chars vs source %d chars (source adds %d lines, drops %d)%s; files: %s"
                             % (len(e["text"]), len(want), added, removed,
                                ("; the embedded script spawns every object in one frame, the source does not"
                                 if burst_emb and not burst_src else ""), ", ".join(sorted(e["files"]))),
                             "Rebuild and publish dist (pipeline/publish_hosted.py) if this source is meant to ship.")
        # the bundled Control script against the module sources
        c = self.campaign
        if not c:
            return
        mods = c.get("lua_modules") or []
        ctl_path = c.get("control_lua") or "src/tts/control.lua"
        ctl = None
        for e in scripts.values():
            if "__modules" in e["text"][:3000] and "-- ===== control entry script =====" in e["text"]:
                ctl = e
        if ctl is None or not mods:
            return
        stale = []
        bundle = ctl["text"]
        placeholder = (c.get("static_token") or {}).get("placeholder", "__STATIC_TOKEN_URL__")

        def present(body):
            parts = body.split(placeholder)
            pos = bundle.find(parts[0])
            if pos < 0:
                return False
            for nxt in parts[1:]:
                nxt_pos = bundle.find(nxt, pos + len(parts[0]) if False else pos)
                if nxt_pos < 0 or nxt_pos - pos > len(parts[0]) + 600:
                    return False
                pos = nxt_pos
            return True

        for m in mods:
            body = self.src_text("src/%s/%s.ttslua" % (c.get("lua_dir", "StillHour"), m))
            if body is not None and not present(body):
                stale.append(m)
        ctl_src = self.src_text(ctl_path)
        if ctl_src is not None and not present(ctl_src):
            stale.append(os.path.basename(ctl_path))
        if stale:
            self.add(WARN, "E07.stale-bundle", self.script_where(ctl),
                     "the Control token's bundled script is stale: %d source file(s) differ from what was bundled"
                     % len(stale), ", ".join(stale),
                     "Re-run pipeline/bundle_mod.py (the release build does) and publish.", count=len(stale))
        else:
            self.add(INFO, "E07.bundle-fresh", self.script_where(ctl),
                     "the Control token's bundle contains every current module and control.lua verbatim")

    # -- F: consistency between the shipped files -----------------------------------------
    def doc_by_role(self, role):
        return [d for d in self.docs if d.role == role]

    @staticmethod
    def first_diff(a, b, path="", ignore=()):
        """Path of the first difference between two JSON values (top-level `ignore` keys skipped)."""
        if type(a) is not type(b):
            return path or "/"
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b)):
                if not path and k in ignore:
                    continue
                if k not in a or k not in b:
                    return "%s/%s" % (path, k)
                d = Auditor.first_diff(a[k], b[k], "%s/%s" % (path, k), ignore)
                if d:
                    return d
            return None
        if isinstance(a, list):
            if len(a) != len(b):
                return "%s (length %d vs %d)" % (path or "/", len(a), len(b))
            for i, (x, y) in enumerate(zip(a, b)):
                d = Auditor.first_diff(x, y, "%s[%d]" % (path, i), ignore)
                if d:
                    return d
            return None
        return None if a == b else (path or "/")

    @staticmethod
    def card_signature(o):
        ok, gm, _ = parse_gmnotes(o)
        cd = o.get("CustomDeck") if isinstance(o.get("CustomDeck"), dict) else {}
        return {"CardID": o.get("CardID"), "GMNotes": json.dumps(gm, sort_keys=True) if gm else o.get("GMNotes"),
                "CustomDeck": json.dumps(cd, sort_keys=True), "Nickname": o.get("Nickname"),
                "Tags": sorted(taglist(o)), "SidewaysCard": hk(o.get("SidewaysCard"))}

    def check_f(self):
        saved = self.doc_by_role("saved")
        release = self.doc_by_role("release")
        rows = []
        if saved and release:
            a, b = saved[0].roots[0] if saved[0].roots else None, release[0].roots[0] if release[0].roots else None
            if a is not None and b is not None:
                d = self.first_diff(a, b)
                if d:
                    self.add(ERROR, "F01.saved-vs-release", saved[0].name,
                             "the saved object's box differs from the release asset (they must be the same box)",
                             "first difference at %s" % d, "Rebuild with pipeline/package_download.py.")
                else:
                    rows.append("saved object box == release asset (byte-equal JSON)")
        if saved:
            sbox = saved[0].roots[0] if saved[0].roots else None
            skids = {hk(c.get("GUID")): c for c in kids(sbox)} if sbox else {}
            for role, label in (("campaign", "campaign file"), ("table", "table-presence file")):
                for d in self.doc_by_role(role):
                    box = d.roots[0] if d.roots else None
                    if not box:
                        continue
                    diffs, missing = [], []
                    for c in kids(box):
                        other = skids.get(hk(c.get("GUID")))
                        if other is None:
                            missing.append(c.get("Nickname") or c.get("GUID"))
                        elif self.first_diff(c, other, ignore=("Transform",)):
                            diffs.append("%s at %s" % (c.get("Nickname"), self.first_diff(c, other, ignore=("Transform",))))
                    if missing or diffs:
                        self.add(ERROR, "F01.%s-vs-saved" % role, d.name,
                                 "%s objects are missing from or differ in the saved object's box (a stale %s "
                                 "ships different data)" % (label, label),
                                 "; ".join((["missing: " + ", ".join(missing[:3])] if missing else []) +
                                           (["differs: " + ", ".join(diffs[:3])] if diffs else [])),
                                 "Rebuild dist (publish_hosted.py rebuilds every file).")
                    else:
                        rows.append("%s: all %d box objects identical to the saved object's" % (
                            label, len(kids(box))))
            mods = self.doc_by_role("mod")
            for d in mods:
                for o in d.roots:
                    if o.get("Name") == "BlockSquare":
                        other = skids.get(hk(o.get("GUID")))
                        if other is None or self.first_diff(o, other, ignore=("Transform",)):
                            self.add(ERROR, "F01.mod-control-vs-saved", d.name,
                                     "the mod's Control token differs from the one in the saved object",
                                     (self.first_diff(o, other or {}, ignore=("Transform",)) if other else "missing"),
                                     "Rebuild dist.")
                        else:
                            rows.append("mod Control token == saved object's Control token")
                    elif o.get("Name") == "Custom_Tile":
                        other = skids.get(hk(o.get("GUID")))
                        if other is None or self.first_diff(o, other, ignore=("Transform",)):
                            self.add(WARN, "F01.mod-static-vs-saved", d.name,
                                     "the mod's static chaos token differs from the saved object's",
                                     "", "Rebuild dist.")
                    elif o.get("Name") == "Bag" and "Player Cards" in (o.get("Nickname") or ""):
                        other = skids.get(hk(o.get("GUID")))
                        if other is None:
                            self.add(ERROR, "F01.mod-bag-missing", d.name, "player-card bag is missing from the saved object")
                        else:
                            ours = {hk(card_id_of(c)): self.card_signature(c) for c in kids(o)}
                            theirs = {hk(card_id_of(c)): self.card_signature(c) for c in kids(other)}
                            bad = sorted(i for i in ours if theirs.get(i) != ours[i])
                            if bad:
                                self.add(ERROR, "F01.player-bag", d.name, "%d card(s) of the mod's player bag differ "
                                         "from the saved object's" % len(bad), ", ".join(map(str, bad[:4])), "Rebuild dist.")
                            else:
                                extra = len(kids(other)) - len(kids(o))
                                rows.append("player-card bag: all %d mod cards identical in the saved object (+%d "
                                            "shared-pool copies there)" % (len(ours), extra))
                    elif o.get("Name") == "Bag":
                        if hk(o.get("GUID")) not in skids:
                            self.add(INFO, "F01.mod-extra-bag", d.name,
                                     "mod bag '%s' is not in the saved object (left out on purpose by skip_bags)"
                                     % o.get("Nickname"), "", "")
        # the standalone player-card bag and starter against the mod / each other
        player = self.doc_by_role("player")
        starter = self.doc_by_role("starter")
        if player and starter:
            pcards = {card_id_of(c): self.card_signature(c) for c in kids(player[0].roots[0])} \
                if player[0].roots else {}
            bad = []
            for c in kids(starter[0].roots[0]) if starter[0].roots else []:
                if pcards.get(card_id_of(c)) != self.card_signature(c):
                    bad.append(card_id_of(c))
            if bad:
                self.add(ERROR, "F01.starter-vs-player", starter[0].name, "starter cards differ from the player bag's",
                         ", ".join(map(str, bad)), "Rebuild dist.")
            else:
                rows.append("starter slice cards identical to the player bag's")
        # every card id means one card everywhere
        by_id = collections.defaultdict(dict)       # id -> signature json -> docs
        for d in self.docs:
            for n in cards_of(d):
                cid = card_id_of(n.obj)
                if cid is None:
                    continue
                by_id[cid].setdefault(json.dumps(self.card_signature(n.obj), sort_keys=True), set()).add(d.name)
        clash = {i: v for i, v in by_id.items() if len(v) > 1}
        if clash:
            i = sorted(clash)[0]
            sigs = [json.loads(s) for s in clash[i]]
            keys = sorted({k for s in sigs for k in s if any(s[k] != t[k] for t in sigs)})
            sev = ERROR if any(k in ("CardID", "CustomDeck") for k in keys) else WARN
            self.add(sev, "F01.card-copies", "(all files)",
                     "%d card id(s) differ between shipped files (same card, different data)" % len(clash),
                     "e.g. %s differs in %s" % (i, ", ".join(keys)), "Rebuild dist so every copy comes from one spec.",
                     count=len(clash))
        else:
            rows.append("every card id has identical id/CardID/CustomDeck/GMNotes/tags in all %d files "
                        "(%d card ids)" % (len(self.docs), len(by_id)))
        # box scripts: every scenario box carries the same script in every file
        hashes = collections.defaultdict(set)
        for d in self.docs:
            for n in d.nodes:
                ok, gm, _ = parse_gmnotes(n.obj)
                if gm and gm.get("type") in ("ScenarioBox", "CampaignBox") and n.obj.get("Name") == "Custom_Model_Bag" \
                        and isinstance(n.obj.get("LuaScript"), str):
                    hashes[gm["type"]].add(sha1_text(n.obj["LuaScript"])[:8])
        for typ, hs in hashes.items():
            if len(hs) > 1:
                self.add(ERROR, "F01.box-scripts", "(all files)", "%s scripts differ between shipped files" % typ,
                         ", ".join(sorted(hs)), "Rebuild dist.")
            else:
                rows.append("%s script identical everywhere (%s)" % (typ, next(iter(hs))))
        # bundle file vs embedded control script
        for path in sorted(glob.glob(os.path.join(self.root, "dist", "*_bundle.lua"))):
            try:
                text = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            ctl = [o for d in self.docs for o in (n.obj for n in d.nodes) if o.get("Name") == "BlockSquare"
                   and isinstance(o.get("LuaScript"), str)]
            if ctl:
                if all(o["LuaScript"] != text for o in ctl):
                    self.add(ERROR, "F03.bundle-vs-control", rel(path, self.root),
                             "dist bundle file differs from the Control script embedded in the JSON files",
                             "", "Rebuild with bundle_mod.py.")
                else:
                    rows.append("%s == embedded Control script" % rel(path, self.root))
        self.report.stats["consistency"] = rows
        for r in rows:
            self.add(INFO, "F01.ok", "(files)", r)
        for d in self.doc_by_role("placeholder"):
            self.f_placeholder(d, release)

    def f_placeholder(self, doc, release_docs):
        """The download box against what SCED's placeholder_download expects."""
        o = doc.roots[0] if doc.roots else None
        if not o:
            return
        where = doc.where(doc.nodes[0]) if doc.nodes else doc.name
        ok, gm, raw = parse_gmnotes(o)
        stem = None
        if release_docs:
            stem = os.path.splitext(os.path.basename(release_docs[0].name))[0]
        if not gm or not isinstance(gm.get("filename"), str):
            self.add(ERROR, "F02.filename", where, "placeholder GMNotes has no 'filename' (SCED downloads "
                     "{SOURCE_REPO}{filename}.json)", short(raw), "GMNotes {\"filename\": \"<release asset name>\"}.")
        elif stem and gm["filename"] != stem:
            self.add(ERROR, "F02.filename", where, "placeholder filename '%s' does not match the release asset "
                     "'%s.json'" % (gm["filename"], stem), "", "Make them equal.")
        if o.get("Name") != "Custom_Model":
            self.add(WARN, "F02.shape", where,
                     "placeholder is a %s; SCED's own placeholders are Custom_Model boxes (mesh + box art, tinted alpha "
                     "71/255) built by onClick_spawnPlaceholder" % o.get("Name"),
                     "an empty Bag also looks like a campaign box to SCED's exporter when tagged CampaignBox",
                     "Spawn it as Custom_Model with SCED's box mesh and art.")
        tags = set(taglist(o))
        if "CampaignBox" in tags and o.get("Name") in ("Bag", "Custom_Model_Bag"):
            self.add(WARN, "F02.tags", where,
                     "an EMPTY Bag tagged CampaignBox is what SCED's campaign exporter treats as 'the campaign box with "
                     "all objects placed' (CampaignImporterExporter: Bag + CampaignBox tag + 0 objects): with the real "
                     "box also empty after Place it reports 'Multiple empty campaign boxes'",
                     "tags %s" % sorted(tags), "Leave the placeholder untagged (SCED's are); the downloaded box gets "
                     "CampaignBox/Reloadable itself.")
        if "Reloadable" in tags:
            self.add(INFO, "F02.reloadable", where, "placeholder carries 'Reloadable' (adds 'Redownload this' to it)")
        lua = o.get("LuaScript")
        if isinstance(lua, str):
            toks = lua_tokens(lua)
            defined_local = bool(re.search(r"\blocal\s+GlobalApi\s*=", lua)) or "placeholder_download" in lua
            uses_api = any(t == "GlobalApi" for k, t, _ in toks if k == "name")
            if uses_api and not defined_local:
                self.add(WARN, "F02.script", where,
                         "placeholder script calls GlobalApi, which is not a global in an object's scope; SCED's "
                         "DownloadBox does `local GlobalApi = require(\"Global/GlobalApi\")` (bundled) and "
                         "GlobalApi.placeholderDownload runs Global.call(\"placeholder_download\", ...). As shipped the "
                         "click can only print its fallback message",
                         "script uses `GlobalApi and GlobalApi.placeholderDownload`",
                         "Call Global.call(\"placeholder_download\", {filename=..., player=Player[color], replace=self.guid}).")
            if not re.search(r"\bplayer\b|\bplayerColor\b|replace", lua):
                self.add(INFO, "F02.replace", where, "placeholder does not pass `replace` (the box is not swapped out "
                         "for the download: SCED spawns the content at a free spot instead)")
        else:
            self.add(ERROR, "F02.script", where, "placeholder has no LuaScript (no Download button)")
        self.add(INFO, "F02.source-repo", where,
                 "SCED downloads from SOURCE_REPO=github.com/Chr1Z93/SCED-downloads releases; our release asset is "
                 "not hosted there, so the download cannot succeed until it is (or SOURCE_REPO is changed)",
                 "", "Ship the Saved Object instead (the owner's path) or publish the asset in that repository.")

    # -- G: everything else ------------------------------------------------------------------
    def check_g(self):
        ref = self.ref
        urls = set()
        for doc, key, url, where in self.collect_url_refs():
            if isinstance(url, str) and url and (key in IMAGE_URL_KEYS or key == "PDFUrl"):
                urls.add(url)
        if urls:
            names = sorted(((len(re.sub(r"[^A-Za-z0-9]", "", u)), u) for u in urls), reverse=True)
            longest = names[0][0]
            steam = [n for n, u in names if "steamusercontent" in u]
            line = ("longest URL maps to a %d-character cache file name (letters and digits only, as TTS names "
                    "Mods/Images/ files)%s" % (longest, "; Steam URLs: ~%d" % max(steam) if steam else ""))
            if longest > 170:
                self.add(WARN, "G01.cache-name", names[0][1], line,
                         "Windows MAX_PATH is 260 and Documents/My Games/Tabletop Simulator/Mods/Images adds ~80-110",
                         "Shorten the URL (a shorter repo path or a short alias).")
            else:
                self.add(INFO, "G01.cache-name", names[0][1], line,
                         "budget ~170 under Windows MAX_PATH (260) with a typical Documents path", "")
        if ref and ref.guid_set:
            mine = set()
            for doc in self.docs:
                for node in doc.nodes:
                    g = node.obj.get("GUID")
                    if isinstance(g, str):
                        mine.add(g)
            both = sorted(mine & ref.guid_set)
            self.add(INFO, "G02.guid-vs-sced", "(all files)",
                     "%d of our %d distinct GUIDs also occur in official boxes / the SCED save"
                     % (len(both), len(mine)), ", ".join(both[:6]),
                     "TTS reassigns a taken GUID on spawn, so this is harmless.", count=len(both))
        for doc in self.docs:
            for node in doc.nodes:
                ok, gm, _ = parse_gmnotes(node.obj)
                if gm and gm.get("type") == "CampaignBox" and "Reloadable" in taglist(node.obj) \
                        and node.depth == 0 and doc.role in ("saved", "release"):
                    self.add(INFO, "G03.redownload", doc.where(node),
                             "the campaign box is tagged Reloadable with filename '%s': SCED's 'Redownload this' menu "
                             "item will request SCED-downloads/releases/latest/download/%s.json (404 for a fan "
                             "campaign) and then do nothing" % (gm.get("filename"), gm.get("filename")), "",
                             "Harmless; drop the tag if the menu entry is unwanted.")
                    break
        # git state of dist/
        st = self.git("status", "--porcelain", "--", "dist", text=True)
        if st is not None and st.returncode == 0:
            dirty = [l for l in st.stdout.splitlines() if l.strip()]
            if dirty:
                self.add(WARN, "G04.dist-dirty", "dist/", "%d file(s) under dist/ differ from the last commit" % len(dirty),
                         "; ".join(dirty[:4]), "Commit (or revert) before publishing: raw URLs serve committed bytes only.",
                         count=len(dirty))
            else:
                diff = self.git("diff", "--stat", "origin/main", "--", "dist", text=True)
                if diff is not None and diff.returncode == 0:
                    self.add(INFO, "G04.dist-published", "dist/",
                             "dist/ is identical to origin/main (the published build)" if not diff.stdout.strip()
                             else "dist/ differs from origin/main: %s" % diff.stdout.strip().splitlines()[-1], "", "")
        files = []
        for doc in self.docs:
            cards = len(cards_of(doc))
            files.append({"file": doc.name, "role": doc.role, "kind": doc.kind,
                          "bytes": doc.loaded.raw_size if doc.loaded else None, "objects": len(doc.nodes),
                          "cards": cards})
        self.report.stats["files"] = files

    # -- run -------------------------------------------------------------------------------------
    def pick_primary(self):
        saved = [d for d in self.docs if d.role == "saved"]
        self.primary = saved or list(self.docs)

    def run(self):
        self.pick_primary()
        steps = (("A", self.check_a), ("B", self.check_b), ("C", self.check_c), ("D", self.check_d),
                 ("E", self.check_e), ("F", self.check_f), ("G", self.check_g))
        for letter, fn in steps:
            if self.want(letter):
                try:
                    fn()
                except Exception as e:                       # a bug or hostile data: report, never crash
                    import traceback
                    frames = traceback.extract_tb(sys.exc_info()[2])[-2:]
                    self.add(ERROR, "A99.audit-crash", "(check %s)" % letter,
                             "check %s stopped with %s: %s" % (letter, type(e).__name__, str(e)[:100]),
                             " <- ".join("%s:%d" % (f.name, f.lineno) for f in reversed(frames)),
                             "Report this audit bug; findings after it are missing.")
        return self.report.finish()


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
def default_targets(root=ROOT):
    dist = os.path.join(root, "dist")
    found = []
    for pat in ("saved_object_*.json", os.path.join("downloads", "*.json"), "*.json"):
        for f in sorted(glob.glob(os.path.join(dist, pat))):
            if f not in found:
                found.append(f)
    return found


def load_campaign(root, campaign=None, targets=()):
    """campaigns/<id>/build.json: the explicit id, else the one whose slug names a target."""
    ids = [campaign] if campaign else []
    if not ids:
        for p in sorted(glob.glob(os.path.join(root, "campaigns", "*", "build.json"))):
            try:
                cfg = json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            slug = cfg.get("slug")
            if slug and any(os.path.basename(t).startswith(slug) or os.path.basename(t).endswith("_" + slug + ".json")
                            or ("saved_object_" + slug) in os.path.basename(t) for t in targets):
                ids.append(os.path.basename(os.path.dirname(p)))
    for cid in ids:
        p = os.path.join(root, "campaigns", cid, "build.json")
        try:
            cfg = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cfg.setdefault("id", cid)
        name = cfg.get("name") or cid.replace("_", " ").title()
        cfg.setdefault("upper_name", name.upper())
        cfg.setdefault("box_name", name)
        cfg.setdefault("tag", "".join(w.capitalize() for w in cid.split("_")))
        cfg.setdefault("lua_dir", cfg["tag"])
        cfg.setdefault("control_lua", "src/tts/control.lua")
        return cfg
    return {}


def audit_documents(named_data, root=ROOT, ref=None, src=None, campaign=None, checks="ABCDEFG",
                    online=False, luac=True):
    """Audit in-memory JSON values: [(name, parsed_json), ...] -> Report."""
    a = Auditor(root, ref, src, Report(), online, campaign, checks, luac)
    for name, data in named_data:
        a.add_doc(Doc(name, data))
    return a.run()


def audit(paths=None, root=ROOT, reference_dirs=None, checks="ABCDEFG", online=False, campaign_id=None,
          use_reference=True, luac=True):
    """Audit the shipped files at `paths` (default: dist/). Returns (Report, Auditor)."""
    report = Report()
    paths = list(paths) if paths else default_targets(root)
    ref = src = None
    if use_reference:
        dirs = list(reference_dirs) if reference_dirs else list(DEFAULT_REFERENCE_DIRS)
        ref, src = load_reference(dirs, root, report)
        if ref:
            report.stats["reference"] = {"sources": ref.sources, "official_card_ids": len(ref.ids),
                                         "official_deck_ids": len(ref.deck_pairs),
                                         "official_objects": ref.n_objects}
    campaign = load_campaign(root, campaign_id, paths)
    a = Auditor(root, ref, src, report, online, campaign, checks, luac)
    for p in paths:
        loaded = load_json_file(p, rel(p, root))
        try:
            doc = Doc(loaded.name, loaded.data, p, loaded)
        except RecursionError:
            report.add(ERROR, "A00.parse", loaded.name, "object tree is nested too deeply to audit")
            continue
        a.add_doc(doc)
    if not a.docs:
        report.add(ERROR, "A00.no-files", "(args)", "no JSON files to audit",
                   "looked in dist/", "Pass file paths or build dist/ first.")
    a.run()
    return report, a


# --------------------------------------------------------------------------
# Text output
# --------------------------------------------------------------------------
def render_text(report, auditor=None, min_severity=INFO, stats=True, width=100):
    lines = []
    c = report.counts()
    head = "audit_database: %d file(s)" % (len(auditor.docs) if auditor else 0)
    ref = report.stats.get("reference")
    if ref:
        head += " | reference: " + ", ".join(ref["sources"])
    lines.append(head)
    for n in report.notes:
        lines.append("note: " + n)
    lines.append("")
    keep = SEV_RANK[min_severity]
    current = None
    for f in report.findings:
        if SEV_RANK[f.severity] > keep:
            continue
        if f.check != current:
            current = f.check
            lines.append("== %s  %s ==" % (f.check, CHECK_TITLES.get(f.check, "")))
        cnt = " (x%d)" % f.count if f.count > 1 else ""
        lines.append("%-5s %s%s  %s" % (f.severity, f.code, cnt, f.where))
        lines.append("      %s" % f.message)
        if f.evidence:
            lines.append("      evidence: %s" % f.evidence)
        if f.locations:
            lines.append("      also at: %s%s" % ("; ".join(f.locations[:3]), " ..." if f.count > len(f.locations) + 1 else ""))
        if f.fix:
            lines.append("      fix: %s" % f.fix)
    if stats:
        lines.extend(render_stats(report))
    lines.append("")
    lines.append("Summary: %d ERROR, %d WARN, %d INFO" % (c[ERROR], c[WARN], c[INFO]))
    return "\n".join(lines)


def render_stats(report):
    s = report.stats
    out = []
    units = s.get("place_units")
    if units:
        out.append("")
        out.append("== Stats: Place units (what one Place click spawns) ==")
        out.append("%-28s %-11s %5s %6s %7s %5s %7s %9s" % ("box", "kind", "objs", "images", "deckids", "cards",
                                                              "sheets", "tex MiB"))
        for u in units:
            out.append("%-28s %-11s %5d %6d %7d %5d %7d %9.0f" % (
                str(u["box"])[:28], str(u["kind"])[:11], u["placed_objects"], u["images"], u["deck_ids"], u["cards"],
                u["max_sheets_in_a_deck"], u["texture_mib_est"]))
    off = s.get("official_place_units")
    if off:
        sb, cb = off["scenario_boxes"], off["campaign_boxes"]
        for label, d in (("official scenario boxes (%d)" % sb["n"], sb), ("official campaign boxes (%d)" % cb["n"], cb)):
            out.append("%s: images min %s / median %s / p90 %s / max %s; deck ids min %s / median %s / p90 %s / max %s"
                       % (label, d["images"]["min"], d["images"]["median"], d["images"]["p90"], d["images"]["max"],
                          d["deck_ids"]["min"], d["deck_ids"]["median"], d["deck_ids"]["p90"], d["deck_ids"]["max"]))
        ds = off["decks_sheets"]
        out.append("official Decks: sheets per Deck min %s / median %s / p90 %s / max %s; %s" % (
            ds["min"], ds["median"], ds["p90"], ds["max"], s.get("official_cards_per_image", "")))
    scripts = s.get("lua_scripts")
    if scripts:
        out.append("")
        out.append("== Stats: Lua scripts ==")
        for r in scripts:
            out.append("%s  %7d chars  %5d lines  x%-3d depth>=%d  syntax %s" % (
                r["hash"][:8], r["chars"], r["lines"], r["objects"], r["min_depth"],
                ", ".join("%s %s" % (k, "ok" if v == "ok" else "FAIL") for k, v in sorted(r["syntax"].items())) or "n/a"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Structural audit of the shipped TTS/SCED database (see module docstring).")
    ap.add_argument("targets", nargs="*", help="JSON files to audit (default: dist/saved_object_*.json, "
                                                "dist/downloads/*.json, dist/*.json)")
    ap.add_argument("--reference", action="append", metavar="DIR",
                    help="directory with the official data (repeatable); default .cache/official and .cache/sced")
    ap.add_argument("--no-reference", action="store_true", help="skip every reference-dependent check")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--online", action="store_true",
                    help="also HEAD every hosted URL (and GET a few) through the environment's proxy")
    ap.add_argument("--checks", default="ABCDEFG", help="letters of the checks to run (default all)")
    ap.add_argument("--campaign", help="campaign id (campaigns/<id>/build.json) for freshness checks")
    ap.add_argument("--min-severity", choices=(ERROR, WARN, INFO), default=INFO)
    ap.add_argument("--strict", action="store_true", help="exit 1 on WARN as well")
    ap.add_argument("--no-stats", action="store_true", help="omit the statistics tables")
    ap.add_argument("--no-luac", action="store_true", help="do not run luac")
    ap.add_argument("--root", default=ROOT, help="repository root (default: this checkout)")
    args = ap.parse_args(argv)
    try:                                   # card names hold dashes and macrons: never die on a legacy console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    root = os.path.abspath(args.root)
    paths = [os.path.abspath(p) for p in args.targets] or None
    for p in paths or []:
        if not os.path.isfile(p):
            print("error: no such file: %s" % p, file=sys.stderr)
            return 2
    report, aud = audit(paths, root, args.reference, args.checks.upper(), args.online, args.campaign,
                        not args.no_reference, not args.no_luac)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=False, ensure_ascii=False))
    else:
        print(render_text(report, aud, args.min_severity, not args.no_stats))
    c = report.counts()
    if c[ERROR] or (args.strict and c[WARN]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
