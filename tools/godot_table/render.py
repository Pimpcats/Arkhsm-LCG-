"""Render the emulated TTS/SCED table to screenshots (assistant tool).

    python3 tools/godot_table/render.py --save "/path/Arkham SCE 4.8.0.json"
    python3 tools/godot_table/render.py --save ... --steps 0,6,10-12 --cameras overview,play
    python3 tools/godot_table/render.py --save ... --suite demo --out .cache/godot_review/demo

1. runs the headless harness (tests/sced_real/run.py) with --snapshots: a
   JSON snapshot of the table after boot and after every step;
2. fetches and prepares every asset those snapshots use
   (tools/godot_table/fetch_assets.py, cached under .cache/godot_assets/);
3. renders each snapshot from several cameras with Godot 4
   (tools/godot_table, headless under Xvfb, OpenGL compatibility renderer);
4. draws Global's XML UI (SCED's screen panels) over the player-view shots;
5. writes an index.html contact sheet.

Output (gitignored): .cache/godot_shots/<run>/NNN_<camera>.png plus a .json
per shot (camera + every button's screen rectangle). Screenshots contain
campaign content: they are for the assistant only.
"""
import argparse
import datetime
import glob
import html
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import fetch_assets  # noqa: E402

GODOT_CANDIDATES = [os.environ.get("GODOT", ""), "/home/user/tools/godot/Godot_v4.3-stable_linux.x86_64",
                    shutil.which("godot4") or "", shutil.which("godot") or ""]

# TTS's own default camera: 60 degrees vertical field of view
TTS_FOV = 60.0


def find_godot():
    for c in GODOT_CANDIDATES:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def parse_steps(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return [i for i in out if 0 <= i < n]


# ----------------------------------------------------------------- cameras --

def camera_state(cs, fov=TTS_FOV):
    """A TTS CameraStates entry -> eye/target (TTS coordinates)."""
    tgt = cs["Position"]
    if cs.get("AbsolutePosition"):
        eye = cs["AbsolutePosition"]
        eye = [eye["x"], eye["y"], eye["z"]]
    else:
        pitch, yaw, dist = math.radians(cs["Rotation"]["x"]), math.radians(cs["Rotation"]["y"]), cs["Distance"]
        # Unity: forward = (sin yaw cos pitch, -sin pitch, cos yaw cos pitch)
        f = (math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch))
        eye = [tgt["x"] - f[0] * dist, tgt["y"] - f[1] * dist, tgt["z"] - f[2] * dist]
    return {"type": "persp", "eye": eye, "target": [tgt["x"], tgt["y"], tgt["z"]], "fov": fov}


def cameras_for(save, names):
    """Named cameras. The save's stored camera states come first (TTS's
    number keys 1..3 for this save)."""
    states = save.get("CameraStates") or []
    cams = {}
    if len(states) > 0 and states[0]:
        cams["overview"] = camera_state(states[0])
    if len(states) > 1 and states[1]:
        cams["play"] = camera_state(states[1])
    if len(states) > 2 and states[2]:
        cams["mythos"] = camera_state(states[2])
    # TTS's default seat camera for White (sits at -x on SCED's table):
    # above the player's side, looking over the play area
    cams["player"] = {"type": "persp", "eye": [-78.0, 42.0, 0.0], "target": [-26.0, 0.0, 0.0], "fov": TTS_FOV}
    # sitting at White's seat, looking at White's hand, playmat and the play area
    cams["seat"] = {"type": "persp", "eye": [-80.0, 21.0, 13.0], "target": [-48.0, 0.0, 10.0], "fov": TTS_FOV}
    # the whole table from above; screen up = TTS +x (away from the players)
    cams["top"] = {"type": "ortho", "eye": [-8.0, 150.0, 0.0], "target": [-8.0, 0.0, 0.0], "up": [1, 0, 0],
                   "size": 140.0, "far": 400.0}
    # close-ups from above (calibration and layout checks)
    for name, x, z, size in (("whitemat", -55.0, 16.1, 16.0), ("mythostop", -2.0, 0.0, 16.0),
                             ("importer", -20.5, 71.0, 26.0)):
        cams[name] = {"type": "ortho", "eye": [x, 100.0, z], "target": [x, 0.0, z], "up": [1, 0, 0],
                      "size": size, "far": 300.0}
    cams["playtop"] = {"type": "ortho", "eye": [-28.0, 120.0, 0.0], "target": [-28.0, 0.0, 0.0], "up": [1, 0, 0],
                       "size": 42.0, "far": 400.0}
    return {k: cams[k] for k in names if k in cams}


DEFAULT_CAMERAS = ["overview", "player", "top", "play", "mythos"]


# ------------------------------------------------------------------ run --

def run_harness(save, suite, snap_dir, lua="lua5.2", payload=None, log=print):
    import run as harness
    t0 = time.time()
    r = harness.run(lua, suite, save=save, snapshots=snap_dir, payload=payload, timeout=1200)
    if r.get("skipped"):
        raise SystemExit("harness skipped: " + r["skipped"])
    passed = sum(1 for c in r["checks"] if c["ok"])
    failed = sum(1 for c in r["checks"] if not c["ok"])
    log("harness (%s, %s): %d passed, %d failed, %d snapshots, %.1fs" % (suite, lua, passed, failed,
                                                                          len(r["snapshots"]), time.time() - t0))
    return r


def write_job(path, snaps, cams, manifest, scene, width, height, out_dir, options):
    renders = []
    for s in snaps:
        stem = "%03d" % s["index"]
        shots = [{"out": os.path.join(out_dir, "%s_%s.png" % (stem, name)), "camera": cam, "name": name}
                 for name, cam in cams.items()]
        rec = {"snapshot": s["file"], "options": options, "shots": shots, "label": s.get("label", "")}
        if s.get("ui"):
            rec["ui"] = s["ui"]
        renders.append(rec)
    job = {"manifest": manifest, "scene": scene, "width": width, "height": height, "renders": renders}
    json.dump(job, open(path, "w"), indent=1)
    return job


def run_godot(job_path, log=print, timeout=1800):
    godot = find_godot()
    if not godot:
        raise SystemExit("Godot 4 not found (set GODOT=/path/to/godot)")
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", godot, "--path", HERE,
           "--rendering-driver", "opengl3", "--", "--job", job_path]
    if not shutil.which("xvfb-run"):
        cmd = cmd[4:]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=HERE)
    out = p.stdout + p.stderr
    errs = [ln for ln in out.splitlines() if ("ERROR" in ln or "SCRIPT ERROR" in ln) and "ALSA" not in ln
            and "audio" not in ln.lower()]
    for ln in out.splitlines():
        if ln.startswith(("DONE", "STATS")):
            log("godot: " + ln)
    if errs:
        log("godot reported %d error line(s); first: %s" % (len(errs), " | ".join(errs[:4])[:800]))
    log("godot: exit %s in %.1fs" % (p.returncode, time.time() - t0))
    return p.returncode, out


def scene_from_save(save):
    return {"sky_url": fetch_assets.norm_url(save.get("SkyURL") or ""), "lighting": save.get("Lighting") or {},
            "light_dir": [25.0, -80.0, 18.0]}


def write_index(out_dir, job, title, notes=()):
    rows = []
    for r in job["renders"]:
        cells = []
        for s in r["shots"]:
            fn = os.path.basename(s["out"])
            if not os.path.isfile(s["out"]):
                continue
            cells.append('<figure><a href="%s"><img loading="lazy" src="%s"></a><figcaption>%s</figcaption></figure>'
                         % (fn, fn, html.escape(s["name"])))
        rows.append("<section><h2>%s</h2><div class=row>%s</div></section>" % (
            html.escape(os.path.basename(r["snapshot"]) + " - " + r.get("label", "")), "".join(cells)))
    page = """<!doctype html><meta charset=utf-8><title>%s</title>
<style>body{background:#111;color:#ddd;font:14px sans-serif;margin:16px}
.row{display:flex;flex-wrap:wrap;gap:8px}figure{margin:0}img{width:380px;border:1px solid #333}
figcaption{font-size:12px;color:#aaa}h2{font-size:15px;margin:18px 0 6px}</style>
<h1>%s</h1>%s%s""" % (html.escape(title), html.escape(title),
                       "".join("<p>%s</p>" % html.escape(n) for n in notes), "".join(rows))
    p = os.path.join(out_dir, "index.html")
    open(p, "w", encoding="utf-8").write(page)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", required=True, help="the SCED save the harness boots (e.g. 'Arkham SCE 4.8.0.json')")
    ap.add_argument("--suite", default="playthrough", help="harness suite (playthrough, runner, demo)")
    ap.add_argument("--lua", default="lua5.2")
    ap.add_argument("--payload", help="a candidate Saved Object instead of dist/'s")
    ap.add_argument("--steps", help="snapshot indexes to render, e.g. 0,6,10-12 (default: all)")
    ap.add_argument("--cameras", default=",".join(DEFAULT_CAMERAS),
                    help="comma list of: overview, player, play, mythos, top, playtop")
    ap.add_argument("--out", help="output folder (default .cache/godot_shots/<timestamp>)")
    ap.add_argument("--snapshots", help="render these existing snapshots (folder) instead of running the harness")
    ap.add_argument("--closeup", action="append", default=[],
                    help="extra top-down camera NAME=x,z,size (TTS coordinates), e.g. cleanup=8,-53,12")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--debug", action="store_true", help="draw snap points and scripting zones")
    ap.add_argument("--no-ui", action="store_true", help="skip the Global XML UI overlay")
    a = ap.parse_args(argv)
    t_start = time.time()
    save = json.load(open(a.save, encoding="utf-8"))
    out = a.out or os.path.join(ROOT, ".cache", "godot_shots", datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    if a.snapshots:
        files = sorted(f for f in glob.glob(os.path.join(a.snapshots, "*.json")) if not f.endswith(".ui.json"))
        snaps = []
        for f in files:
            meta = json.load(open(f)).get("meta", {})
            snaps.append({"index": int(meta.get("index", len(snaps))), "label": meta.get("label", ""),
                          "file": os.path.abspath(f)})
    else:
        snap_dir = os.path.join(out, "snapshots")
        r = run_harness(a.save, a.suite, snap_dir, a.lua, a.payload)
        snaps = r["snapshots"]
    chosen = set(parse_steps(a.steps, 10 ** 6))
    if a.steps:
        snaps = [s for s in snaps if s["index"] in chosen]
    print("rendering %d snapshot(s)" % len(snaps))
    man_path, man = fetch_assets.fetch([s["file"] for s in snaps], a.save)
    cams = cameras_for(save, [c.strip() for c in a.cameras.split(",") if c.strip()])
    for spec in a.closeup:
        name, _, nums = spec.partition("=")
        x, z, size = (float(v) for v in nums.split(","))
        cams[name] = {"type": "ortho", "eye": [x, 100.0, z], "target": [x, 0.0, z], "up": [1, 0, 0],
                      "size": size, "far": 300.0}
    options = {"snap_points": a.debug, "zones": a.debug, "global_snap_points": a.debug, "debug_buttons": a.debug}
    # objects' own XML UI panels, drawn per snapshot (sidecar JSON)
    try:
        import object_ui
        import ui_overlay
        ui_assets = ui_overlay.asset_files_for(save, man)
        ui_fonts = ui_overlay.font_files_for(man)
        object_ui.MANIFEST = man
        for s_ in snaps:
            s_["ui"], _items = object_ui.sidecar(s_["file"], ui_assets, ui_fonts)
    except Exception as e:  # never fatal
        print("object ui skipped:", e)
    job_path = os.path.join(out, "job.json")
    job = write_job(job_path, snaps, cams, man_path, scene_from_save(save), a.width, a.height, out, options)
    rc, log = run_godot(job_path)
    open(os.path.join(out, "godot.log"), "w").write(log)
    if not a.no_ui:
        try:
            import ui_overlay
            n = ui_overlay.overlay_job(job, save, man)
            print("xml ui overlay drawn on %d shot(s)" % n)
        except ImportError:
            pass
    idx = write_index(out, job, "Godot table renders", [
        "assets: %d urls, %d failed" % (man["stats"]["urls"], man["stats"]["failed"]),
        "total %.0fs" % (time.time() - t_start)])
    print("index:", idx)
    print("total %.1fs" % (time.time() - t_start))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
