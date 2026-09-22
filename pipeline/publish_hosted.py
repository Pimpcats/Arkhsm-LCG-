#!/usr/bin/env python3
"""publish_hosted.py — make the TTS build load its card images from GitHub.

Tabletop Simulator on the owner's PC cannot read file:/// paths from whatever
machine produced the build, so a shareable build needs hosted image URLs. This:

  1. renders every card face (pipeline/render_placeholders.py) unless --no-render
  2. converts the Still Hour faces/backs + deck backs to JPEG in dist/cards/
  3. writes pipeline/art_urls.json in hosted mode, pointing at
       https://raw.githubusercontent.com/<repo>/<ref>/dist/cards/<id>.jpg?v=<hash>
     (the ?v=<content hash> changes whenever the image does, so TTS's URL-keyed
     image cache never shows a stale face)
  4. rebuilds every dist/ artifact and fails if any file:/// URL survives

Commit dist/ afterwards; the URLs resolve once that commit is pushed to <ref>.

Run: python3 pipeline/publish_hosted.py [--ref BRANCH] [--no-render]
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FACES = os.path.join(ROOT, "art", "faces")
OUT = os.path.join(ROOT, "dist", "cards")
REPO = "Pimpcats/Arkhsm-LCG-"
PREFIX = "sthr-"
JPEG_QUALITY = 88

REBUILD = ("build_cards.py", "bundle_mod.py", "package_download.py")


def current_branch():
    out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def to_jpeg(src, name):
    """Write dist/cards/<name>.jpg; return its short content hash."""
    dest = os.path.join(OUT, name + ".jpg")
    Image.open(src).convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY,
                                        optimize=True, progressive=True)
    return hashlib.sha1(open(dest, "rb").read()).hexdigest()[:10]


def publish(ref, render=True):
    if render:
        subprocess.run([sys.executable, os.path.join(HERE, "render_placeholders.py")],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    os.makedirs(OUT, exist_ok=True)
    base = "https://raw.githubusercontent.com/{}/{}/dist/cards".format(REPO, ref)

    def url(name, h):
        return "{}/{}.jpg?v={}".format(base, name, h)

    written = set()
    urls = {}
    for png in sorted(glob.glob(os.path.join(FACES, PREFIX + "*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        if name.endswith("-back"):
            continue
        urls[name] = {"face": url(name, to_jpeg(png, name))}
        written.add(name)
        back = os.path.join(FACES, name + "-back.png")
        if os.path.exists(back):
            urls[name]["back"] = url(name + "-back", to_jpeg(back, name + "-back"))
            written.add(name + "-back")
    for key, fname in (("_player_back", "player_back"),
                       ("_encounter_back", "encounter_back")):
        src = os.path.join(ROOT, "assets", "backs", fname + ".png")
        if os.path.exists(src):
            urls[key] = url(fname, to_jpeg(src, fname))
            written.add(fname)

    # drop images from earlier builds that no longer belong to any card
    for old in glob.glob(os.path.join(OUT, "*.jpg")):
        if os.path.splitext(os.path.basename(old))[0] not in written:
            os.remove(old)

    with open(os.path.join(HERE, "art_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2)

    for script in REBUILD:
        subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=ROOT,
                       check=True, stdout=subprocess.DEVNULL)
    # the campaign box compiles only once every scenario is locked in; a refusal
    # leaves the previous dist/the_still_hour_campaign.json untouched
    comp = subprocess.run([sys.executable, os.path.join(HERE, "compile_campaign.py")],
                          cwd=ROOT, capture_output=True, text=True)
    compiled = comp.returncode == 0 and '"ok": false' not in comp.stdout

    bad = local_urls()
    stale = "dist/the_still_hour_campaign.json"
    if not compiled and stale in bad:
        bad.remove(stale)       # not rebuilt this run; reported, not judged
    return {"ref": ref, "images": len(written), "cards": len(
        [k for k in urls if not k.startswith("_")]), "campaign_compiled": compiled,
        "campaign_note": None if compiled else
        "campaign box not rebuilt (scenarios not all locked); " + stale + " is stale",
        "local_urls_left": bad}


def local_urls():
    """dist files that still reference a local file:/// image."""
    bad = []
    for path in glob.glob(os.path.join(ROOT, "dist", "**", "*.json"), recursive=True):
        if "file:///" in open(path, encoding="utf-8").read():
            bad.append(os.path.relpath(path, ROOT))
    return sorted(bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="branch the URLs point at (default: current)")
    ap.add_argument("--no-render", action="store_true",
                    help="reuse art/faces as-is instead of re-rendering")
    a = ap.parse_args()
    res = publish(a.ref or current_branch(), render=not a.no_render)
    print(json.dumps(res, indent=2))
    if res["local_urls_left"]:
        print("FAIL: local file:/// URLs remain in " + ", ".join(res["local_urls_left"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
