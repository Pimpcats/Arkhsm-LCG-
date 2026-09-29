"""A spoiler-free review set of the Godot table (assistant tool).

    python3 tools/godot_table/review.py --save "/path/Arkham SCE 4.8.0.json"

Nothing from this repository's campaign is on the table: the harness boots
the bare SCED save and runs tests/sced_real/demo.lua (SCED's own objects and
official cards, driven through SCED's real scripts). Output, in a gitignored
folder (.cache/godot_review/ by default):

  side_by_side.png   the save's own thumbnail next to a render of the bare
                     table from the save's first stored camera
  table_*.png        the bare table: the save's camera, top-down, seat view
  demo_NN.png        one frame per demo action (plus in-between frames)
  demo.mp4, demo.gif the frames as an animation
  index.html         every file and what it shows
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import render  # noqa: E402
import fetch_assets  # noqa: E402

STEP_SECONDS = 1.6       # an action's frame
MOVE_SECONDS = 0.35      # an in-between frame


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def make_video(frames, out_mp4, out_gif, log=print):
    """frames: [(png, seconds)]"""
    from PIL import Image
    made = []
    exe = ffmpeg_exe()
    if exe:
        lst = out_mp4 + ".txt"
        with open(lst, "w") as f:
            for p, d in frames:
                f.write("file '%s'\nduration %.3f\n" % (p, d))
            f.write("file '%s'\n" % frames[-1][0])
        cmd = [exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
               "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", out_mp4]
        p = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(lst)
        if p.returncode == 0:
            made.append(out_mp4)
        else:
            log("ffmpeg failed: " + p.stderr[-400:])
    else:
        log("no ffmpeg (pip install imageio-ffmpeg): mp4 skipped")
    ims = [Image.open(p).convert("RGB").resize((960, 540), Image.LANCZOS) for p, _ in frames]
    pal = [im.quantize(colors=200, method=Image.Quantize.MEDIANCUT) for im in ims]
    pal[0].save(out_gif, save_all=True, append_images=pal[1:], duration=[int(d * 1000) for _, d in frames],
                loop=0, optimize=True)
    made.append(out_gif)
    return made


def side_by_side(thumb, render_png, out):
    from PIL import Image, ImageDraw, ImageFont
    a = Image.open(thumb).convert("RGB")
    b = Image.open(render_png).convert("RGB")
    h = 720
    a = a.resize((int(a.size[0] * h / a.size[1]), h), Image.LANCZOS)
    b = b.resize((int(b.size[0] * h / b.size[1]), h), Image.LANCZOS)
    pad, top = 16, 44
    im = Image.new("RGB", (a.size[0] + b.size[0] + pad * 3, h + top + pad), (24, 24, 28))
    im.paste(a, (pad, top))
    im.paste(b, (a.size[0] + pad * 2, top))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        f = ImageFont.load_default()
    d.text((pad, 12), "The save's own thumbnail (TTS)", fill=(230, 230, 230), font=f)
    d.text((a.size[0] + pad * 2, 12), "Godot render: bare table, the save's first stored camera", fill=(230, 230, 230), font=f)
    im.save(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, ".cache", "godot_review"))
    ap.add_argument("--thumbnail", help="the save's thumbnail (default: the .png next to the save)")
    ap.add_argument("--lua", default="lua5.2")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = os.path.abspath(a.out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    work = os.path.join(out, "work")
    save = json.load(open(a.save, encoding="utf-8"))
    r = render.run_harness(a.save, "demo", os.path.join(work, "snapshots"), a.lua)
    fails = [c for c in r["checks"] if not c["ok"]]
    snaps = r["snapshots"]
    if not snaps:
        raise SystemExit("the demo wrote no snapshots")
    man_path, man = fetch_assets.fetch([s["file"] for s in snaps], a.save)
    import object_ui
    import ui_overlay
    ui_assets = ui_overlay.asset_files_for(save, man)
    ui_fonts = ui_overlay.font_files_for(man)
    object_ui.MANIFEST = man
    for s in snaps:
        s["ui"], _ = object_ui.sidecar(s["file"], ui_assets, ui_fonts)
    cams = render.cameras_for(save, ["overview", "top", "seat", "whitemat"])
    shots_dir = os.path.join(work, "shots")
    os.makedirs(shots_dir, exist_ok=True)
    renders = []
    for s in snaps:
        names = ["seat"] if s["index"] > 0 else ["overview", "top", "seat"]
        if s["index"] > 0 and "moving" not in s["label"]:
            names.append("whitemat")
        shots = [{"out": os.path.join(shots_dir, "%03d_%s.png" % (s["index"], n)), "camera": cams[n], "name": n}
                 for n in names]
        renders.append({"snapshot": s["file"], "options": {}, "shots": shots, "label": s["label"], "ui": s["ui"]})
    job = {"manifest": man_path, "scene": render.scene_from_save(save), "width": 1920, "height": 1080,
           "renders": renders}
    job_path = os.path.join(work, "job.json")
    json.dump(job, open(job_path, "w"), indent=1)
    rc, log = render.run_godot(job_path)
    open(os.path.join(work, "godot.log"), "w").write(log)
    ui_overlay.overlay_job(job, save, man, cameras=("overview", "seat"))

    files = []   # (file, description)
    base = renders[0]["shots"]
    names = {"overview": ("table_saved_camera.png", "The bare SCED 4.8.0 table from the save's first stored camera "
                                                     "(the view TTS restores), with SCED's screen buttons."),
             "top": ("table_top.png", "The whole bare table from straight above."),
             "seat": ("table_seat.png", "The bare table from White's seat.")}
    for s in base:
        fn, desc = names[s["name"]]
        shutil.copy(s["out"], os.path.join(out, fn))
        files.append((fn, desc))
    thumb = a.thumbnail or os.path.splitext(a.save)[0] + ".png"
    if os.path.isfile(thumb):
        side_by_side(thumb, os.path.join(out, "table_saved_camera.png"), os.path.join(out, "side_by_side.png"))
        files.insert(0, ("side_by_side.png", "Left: the thumbnail TTS stored in the save. Right: the Godot render of "
                                             "the bare table from the save's first stored camera. Note: this save's "
                                             "thumbnail is the mod's cover art, not a picture of the table."))
    frames = []
    n = 0
    for rr in renders[1:]:
        seat = [s for s in rr["shots"] if s["name"] == "seat"][0]
        moving = "moving" in rr["label"] or "picked up" in rr["label"] or "taken out" in rr["label"]
        n += 1
        fn = "demo_%02d.png" % n
        shutil.copy(seat["out"], os.path.join(out, fn))
        files.append((fn, "Seat view: " + rr["label"] + "."))
        frames.append((os.path.join(out, fn), MOVE_SECONDS if moving else STEP_SECONDS))
        for s in rr["shots"]:
            if s["name"] == "whitemat":
                fn2 = "demo_%02d_playmat.png" % n
                shutil.copy(s["out"], os.path.join(out, fn2))
                files.append((fn2, "White's playmat from above: " + rr["label"] + "."))
    frames.insert(0, (os.path.join(out, "table_seat.png"), STEP_SECONDS))
    made = make_video(frames, os.path.join(out, "demo.mp4"), os.path.join(out, "demo.gif"))
    for m in made:
        files.insert(1 if os.path.isfile(os.path.join(out, "side_by_side.png")) else 0,
                     (os.path.basename(m), "The demo as an animation (seat view): every action in order."))
    rows = "".join('<tr><td><a href="%s">%s</a></td><td>%s</td></tr>' % (html.escape(f), html.escape(f), html.escape(d))
                   for f, d in files)
    notes = ["Only SCED's own table and official content are shown; nothing from any custom campaign.",
             "Actions ran through SCED's real scripts on the headless TTS emulator; the pictures are rendered "
             "with Godot from the emulator's table state (not TTS itself: no physics simulation, TTS's own menus "
             "and chat are not drawn).",
             "Demo checks: %d passed, %d failed." % (len(r["checks"]) - len(fails), len(fails))]
    page = """<!doctype html><meta charset=utf-8><title>Godot table review</title>
<style>body{background:#111;color:#ddd;font:15px sans-serif;margin:20px;max-width:1100px}
td{padding:4px 10px;border-bottom:1px solid #333;vertical-align:top}a{color:#9cf}</style>
<h1>Godot table: review set</h1>%s<table>%s</table>""" % ("".join("<p>%s</p>" % html.escape(x) for x in notes), rows)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)
    with open(os.path.join(out, "index.txt"), "w", encoding="utf-8") as f:
        for x in notes:
            f.write(x + "\n")
        f.write("\n")
        for fn, d in files:
            f.write("%s\n    %s\n" % (fn, d))
    shutil.rmtree(work, ignore_errors=True)
    print("review set: %s (%d files, %.0fs)" % (out, len(files), time.time() - t0))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
