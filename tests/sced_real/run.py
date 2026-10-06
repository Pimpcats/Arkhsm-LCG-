"""Run the headless SCED harness (tests only).

    python3 tests/sced_real/run.py                 # real SCED, both suites, lua5.2
    python3 tests/sced_real/run.py --lua lua5.4 --suite playthrough
    python3 tests/sced_real/run.py --fake          # the minimal SCED stand-in

"sced" mode boots SCED's real table (tests/sced_real/sced_table.py finds and
assembles it); "fake" mode boots tests/tts_fake/sced (the stand-in the relay
test uses), with its objects moved to where SCED keeps them, so the emulator
and the playthrough can be exercised without SCED.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests", "tts_fake"))

import sced_table  # noqa: E402

SUITES = ("playthrough", "runner")
# not in "all": the SCED-only demo for tools/godot_table's review renders, and
# the story-resolution suite (tests/test_sced_resolutions.py runs it on a
# payload built from src/, see candidate_payload) and the boxes' Place / Recall
# suite (tests/test_sced_place.py, the same way)
EXTRA_SUITES = ("demo", "resolutions", "place_state")

PLAY_AREA_STAND_IN = """
local enabled = false
function onLoad() Wait.time(function() enabled = true end, 1) end
function isInPlayArea(object)
  local b = self.getBounds()
  local p = object.getPosition()
  return p.x > b.center.x - b.size.x / 2 and p.x < b.center.x + b.size.x / 2
     and p.z > b.center.z - b.size.z / 2 and p.z < b.center.z + b.size.z / 2
end
function onCollisionEnter(info)
  local card = info.collision_object
  if not enabled or card.type ~= "Card" then return end
  local md = JSON.decode(card.getGMNotes())
  if md == nil then return end
  if md.type == "Location" or md.type == "Enemy" or md.type == "Treachery" or md.weakness then
    Global.call("callTable", { { "TokenManager", "spawnForCard" }, { card = card } })
  end
end
"""


def fake_table():
    """The relay test's SCED stand-in, laid out like SCED's real table."""
    from sced_fixture import sced_table as fixture
    objs = fixture()
    save = {"LuaScript": "", "LuaScriptState": "", "ObjectStates": [], "SizeOverride": {}}
    for o in objs:
        if o["Name"] == "__Global__":
            save["LuaScript"] = o["LuaScript"]
            continue
        if o.get("Tags") == ["CampaignLog"]:
            continue                      # the campaign brings its own log
        t = o["Transform"]
        if o["Nickname"] == "Chaos Bag":  # SCED keeps it on the mythos mat's corner snap
            t.update(posX=1.6, posY=1.587, posZ=-13.75, rotY=315)
        if o["Nickname"] == "Play Area":  # SCED's play area (objects/PlayArea.721ba2.json)
            t.update(posX=-27.94, posY=1.47, posZ=0, rotY=270, scaleX=10, scaleY=1, scaleZ=10)
            # like SCED's PlayArea: bounds-based isInPlayArea, and a card
            # (location / enemy / treachery / weakness) landing on the play
            # area gets its tokens spawned
            o["LuaScript"] = PLAY_AREA_STAND_IN
            save["SizeOverride"][o["GUID"]] = [3.6, 0.1, 3.6]
        if o["Nickname"] == "White Playermat":
            t.update(posX=-55, posY=1.45, posZ=16.1, rotY=270, scaleX=6.43, scaleY=1, scaleZ=6.43)
            save["SizeOverride"][o["GUID"]] = [4.2, 0.1, 2.0]
        save["ObjectStates"].append(o)
    # two loose SCED pieces that lie in its play area on a fresh table
    # (objects/LeadInvestigator.acaa93.json, objects/SCEDTour.0e5aa8.json)
    for nick, guid, x, z, scale, tags in (("Lead Investigator", "acaa93", -45, 0, 0.61, ["CleanUpHelper_ignore"]),
                                          ("SCED Tour", "0e5aa8", -24.5, 0, 4, [])):
        save["ObjectStates"].append({"Name": "Custom_Token", "Nickname": nick, "GUID": guid, "Tags": tags,
                                     "Transform": {"posX": x, "posY": 1.6, "posZ": z, "rotY": 270,
                                                   "scaleX": scale, "scaleY": 1, "scaleZ": scale}})
    return save


def candidate_payload(dest_dir):
    """dist/'s Saved Object with the Control's, the campaign log's and the scenario
    boxes' scripts rebuilt from src/ (pipeline/bundle_mod.py, campaign_log.py,
    table_presence.py), and the loop tags on what the boxes hold, so a suite plays
    the current code without a publish run. Returns its path."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import bundle_mod  # noqa: E402
    import campaign_log  # noqa: E402
    import table_presence  # noqa: E402
    d = json.load(open(os.path.join(ROOT, "dist", "saved_object_the_still_hour.json"), encoding="utf-8"))
    bundle = bundle_mod.build_bundle(ROOT)

    def walk(o):
        yield o
        for c in o.get("ContainedObjects") or []:
            yield from walk(c)
        for c in (o.get("States") or {}).values():
            yield from walk(c)
    swapped = {"control": 0, "log": 0, "boxes": 0}
    for o in walk(d["ObjectStates"][0]):
        tags = o.get("Tags") or []
        gm = {}
        try:
            gm = json.loads(o.get("GMNotes") or "{}")
        except ValueError:
            pass
        if o.get("Nickname", "").endswith("Control") and "StillHour" in tags:
            o["LuaScript"] = bundle
            swapped["control"] += 1
        elif "CampaignLog" in tags:
            page = int(gm.get("id", "STHR-LOG1")[-1])
            o["LuaScript"] = campaign_log.lua_script(page)
            swapped["log"] += 1
        elif isinstance(gm, dict) and gm.get("type") == "ScenarioBox":
            # the scenario boxes' Place script and the loop tags on what they hold
            o["LuaScript"] = table_presence.loop_box_script()
            table_presence.tag_loop_objects(o.get("ContainedObjects") or [], gm["id"])
            swapped["boxes"] += 1
    assert swapped["control"] == 1 and swapped["log"] == 3 and swapped["boxes"] >= 1, swapped
    path = os.path.join(dest_dir, "candidate_saved_object.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return path


def find_lua(name):
    return shutil.which(name)


def run(lua="lua5.2", suite="playthrough", fake=False, echo=False, verbose=False, timeout=600, payload=None, save=None,
        snapshots=None):
    """Run one suite; returns dict(checks=[...], rc=, stdout=, stderr=, skipped=reason)."""
    exe = find_lua(lua)
    if not exe:
        return {"skipped": lua + " not installed"}
    cmd = [exe, os.path.join(HERE, "run.lua"), "--suite", suite]
    tmp = None
    if fake:
        tmp = tempfile.mkdtemp(prefix="sced_fake_")
        path = os.path.join(tmp, "fake_table.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fake_table(), f)
        cmd += ["--fixture", path]
    elif save or os.environ.get("SCED_SAVE"):
        # the owner's own SCED save (scripts already bundled): the exact version they play
        table, _ = sced_table.build_table_from_save(save or os.environ["SCED_SAVE"])
        src, _c = sced_table.find_sced(allow_fetch=False)
        cmd += ["--table", table, "--src", os.path.join(src, "src") if src else ROOT]
    else:
        src, commit = sced_table.find_sced()
        if not src:
            return {"skipped": commit}
        table = sced_table.build_table(src, commit)
        cmd += ["--table", table, "--src", os.path.join(src, "src")]
    if echo:
        cmd += ["--echo", "1"]
    if payload:
        cmd += ["--payload", os.path.abspath(payload)]
    if verbose:
        cmd += ["--verbose", "1"]
    if snapshots:
        # a JSON snapshot of the table after boot and after every step
        # (tools/godot_table renders them); the folder must be gitignored
        os.makedirs(snapshots, exist_ok=True)
        cmd += ["--snapshots", os.path.abspath(snapshots)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=ROOT)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    checks, done, snaps = [], None, []
    for line in p.stdout.splitlines():
        if line.startswith("@@SNAPSHOT "):
            snaps.append(json.loads(line[11:]))
        elif line.startswith("@@CHECK "):
            rec = json.loads(line[8:])
            if "name" in rec:
                checks.append(rec)
            elif rec.get("done"):
                done = rec
    return {"checks": checks, "done": done, "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "snapshots": snaps}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lua", default="lua5.2")
    ap.add_argument("--suite", choices=SUITES + EXTRA_SUITES + ("all",), default="all")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--echo", action="store_true", help="print the table's chat as it happens")
    ap.add_argument("--full", action="store_true", help="print the whole log, not just the checks")
    ap.add_argument("--payload", help="a candidate Saved Object to load instead of dist/saved_object_the_still_hour.json")
    ap.add_argument("--from-src", action="store_true",
                    help="load dist's Saved Object with the Control and campaign log scripts rebuilt from src/")
    ap.add_argument("--save", help="boot the owner's own SCED save (e.g. 'Arkham SCE 4.8.0.json') instead of the git checkout")
    ap.add_argument("--snapshots", help="write a table snapshot (JSON) after boot and every step into this folder "
                    "(one subfolder per suite; keep it under .cache/)")
    a = ap.parse_args(argv)
    suites = SUITES if a.suite == "all" else (a.suite,)
    tmp = tempfile.mkdtemp(prefix="sced_candidate_") if a.from_src else None
    try:
        return _run_suites(a, suites, candidate_payload(tmp) if tmp else a.payload)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _run_suites(a, suites, payload):
    failed = 0
    for s in suites:
        r = run(a.lua, s, a.fake, a.echo, payload=payload, save=a.save,
                snapshots=os.path.join(a.snapshots, s) if a.snapshots else None)
        if r.get("skipped"):
            print("SKIPPED:", r["skipped"])
            return 0
        if a.full:
            print(r["stdout"])
        else:
            for line in r["stdout"].splitlines():
                if not line.startswith("@@"):
                    print(line)
        if r["stderr"].strip():
            print(r["stderr"][-4000:], file=sys.stderr)
        n_fail = sum(1 for c in r["checks"] if not c["ok"])
        failed += n_fail + (0 if r["done"] else 1)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
