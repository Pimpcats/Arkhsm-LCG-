#!/usr/bin/env python3
"""publish_hosted.py — make the TTS build load its card images from GitHub.

Tabletop Simulator on the owner's PC cannot read file:/// paths from whatever
machine produced the build, so a shareable build needs hosted image URLs. This:

  1. renders every card face (pipeline/render_placeholders.py) unless --no-render
  2. converts the Still Hour faces/backs + deck backs (and the [static] chaos
     token face, pipeline/render_token.py) to JPEG in dist/cards/
  3. writes pipeline/art_urls.json in hosted mode, pointing at
       https://raw.githubusercontent.com/<repo>/<commit>/dist/cards/<id>.jpg?v=<hash>
     where <commit> holds exactly these files (committed first if changed), so a
     merged-and-deleted branch never blanks the faces
     (the ?v=<content hash> changes whenever the image does, so TTS's URL-keyed
     image cache never shows a stale face)
  4. typesets the campaign guide PDF (pipeline/build_guide_pdf.py, when
     reportlab is installed; otherwise the committed dist/guide PDF is kept)
     and hosts it the same way (art_urls.json "_campaign_guide")
  5. rebuilds every dist/ artifact (cards, mod, table presence, download box)
     and fails if any file:/// URL survives

Commit dist/ afterwards; the URLs resolve once the pinned commit is pushed.

Run: python3 pipeline/publish_hosted.py [--ref REF] [--no-render]
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_token import render_static_token  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FACES = os.path.join(ROOT, "art", "faces")
OUT = os.path.join(ROOT, "dist", "cards")
REPO = "Pimpcats/Arkhsm-LCG-"
PREFIX = "sthr"   # sthr-* cards and the hyphen-free investigator ids (sthrelias)
JPEG_QUALITY = 88
STATIC_TOKEN = "sthr-static-token"

# the one-investigator starter slice (dist/stillhour_starter.json) rebuilds too
STARTER = ("sthrelias", "sthr-lamp", "sthr-donebefore", "sthr-eighthgrave")
REBUILD = (("build_cards.py",), ("build_cards.py", "--only") + STARTER,
           ("bundle_mod.py",), ("table_presence.py",),
           ("package_download.py", "--require-hosted"))
GUIDE = os.path.join(ROOT, "dist", "guide", "the_still_hour_campaign_guide.pdf")


def to_jpeg(src, name):
    """Write dist/cards/<name>.jpg; return its short content hash."""
    dest = os.path.join(OUT, name + ".jpg")
    Image.open(src).convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY,
                                        optimize=True, progressive=True)
    return hashlib.sha1(open(dest, "rb").read()).hexdigest()[:10]


def placeholder_art():
    """Chosen illustrations (CardForge's out/still_hour/index.json) that are
    dry-run stubs (1x1 PNGs) rather than real art. A test or dry-run leaves
    these behind; they must never be composited into a published face."""
    idx = os.path.join(ROOT, "out", "still_hour", "index.json")
    if not os.path.exists(idx):
        return []
    bad = []
    for cid, rel in json.load(open(idx, encoding="utf-8")).items():
        path = os.path.join(ROOT, rel)
        try:
            w, h = Image.open(path).size
        except (OSError, ValueError):
            bad.append(cid)
            continue
        if w < 64 or h < 64:
            bad.append(cid)
    return sorted(bad)


def publish(ref, render=True):
    stubs = placeholder_art()
    if stubs:
        raise SystemExit("refusing to publish: chosen art for {} is a dry-run stub "
                         "(out/still_hour/index.json). Remove out/still_hour or choose real "
                         "art first.".format(", ".join(stubs)))
    if render:
        subprocess.run([sys.executable, os.path.join(HERE, "render_placeholders.py")],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    os.makedirs(OUT, exist_ok=True)

    # phase 1: write every hosted file, remembering its content hash
    hashes = {}                      # image name -> content hash
    plan = {}                        # art_urls key -> image name or {face, back}
    for png in sorted(glob.glob(os.path.join(FACES, PREFIX + "*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        if name.endswith("-back"):
            continue
        hashes[name] = to_jpeg(png, name)
        plan[name] = {"face": name}
        back = os.path.join(FACES, name + "-back.png")
        if os.path.exists(back):
            hashes[name + "-back"] = to_jpeg(back, name + "-back")
            plan[name]["back"] = name + "-back"
    for key, fname in (("_player_back", "player_back"),
                       ("_encounter_back", "encounter_back")):
        src = os.path.join(ROOT, "assets", "backs", fname + ".png")
        if os.path.exists(src):
            hashes[fname] = to_jpeg(src, fname)
            plan[key] = fname

    # the [static] chaos token face (pipeline/render_token.py); bundle_mod.py
    # reads "_static_token" to give the control script and token object its URL
    token_png = os.path.join(ROOT, "art", "tokens", STATIC_TOKEN + ".png")
    render_static_token(token_png)
    hashes[STATIC_TOKEN] = to_jpeg(token_png, STATIC_TOKEN)
    plan["_static_token"] = STATIC_TOKEN
    written = set(hashes)

    # drop images from earlier builds that no longer belong to any card
    for old in glob.glob(os.path.join(OUT, "*.jpg")):
        if os.path.splitext(os.path.basename(old))[0] not in written:
            os.remove(old)
    build_guide()

    # phase 2: pin to the commit holding exactly these files (see pin_ref)
    if ref is None:
        ref = pin_ref()
    base = "https://raw.githubusercontent.com/{}/{}/dist/cards".format(REPO, ref)

    def url(name):
        return "{}/{}.jpg?v={}".format(base, name, hashes[name])

    urls = {}
    for key, v in plan.items():
        urls[key] = {k: url(n) for k, n in v.items()} if isinstance(v, dict) else url(v)
    guide = guide_url(ref)
    if guide:
        urls["_campaign_guide"] = guide

    with open(os.path.join(HERE, "art_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2)

    for script, *args in REBUILD:
        subprocess.run([sys.executable, os.path.join(HERE, script)] + args, cwd=ROOT,
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
    return {"ref": ref, "images": len(written), "guide": guide, "cards": len(
        [k for k in urls if not k.startswith("_")]), "campaign_compiled": compiled,
        "campaign_note": None if compiled else
        "campaign box not rebuilt (scenarios not all locked); " + stale + " is stale",
        "local_urls_left": bad}


def build_guide():
    """(Re)typeset the guide PDF when reportlab is available."""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return
    subprocess.run([sys.executable, os.path.join(HERE, "build_guide_pdf.py")],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def guide_url(ref):
    """The guide PDF's hosted URL (content-hashed like the images), or None."""
    if not os.path.exists(GUIDE):
        return None
    h = hashlib.sha1(open(GUIDE, "rb").read()).hexdigest()[:10]
    rel = os.path.relpath(GUIDE, ROOT).replace(os.sep, "/")
    return "https://raw.githubusercontent.com/{}/{}/{}?v={}".format(REPO, ref, rel, h)


HOSTED_PATHS = ["dist/cards", "dist/guide"]


def pin_ref():
    """The commit that holds exactly the hosted files now on disk.

    Branch URLs break the moment a branch is merged and deleted (every face in
    TTS goes blank), so URLs name a commit instead: immutable, and still
    reachable after a normal merge. Changed hosted files are committed first
    (message: "Publish hosted card images", plus $PUBLISH_COMMIT_TRAILER), and
    the URLs resolve once that commit is pushed."""
    def git(*a):
        return subprocess.run(["git"] + list(a), cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout
    git("add", "-A", "--", *HOSTED_PATHS)
    if git("diff", "--cached", "--name-only", "--", *HOSTED_PATHS).strip():
        msg = "Publish hosted card images"
        if os.environ.get("PUBLISH_COMMIT_TRAILER"):
            msg += "\n\n" + os.environ["PUBLISH_COMMIT_TRAILER"]
        git("commit", "-q", "-m", msg, "--", *HOSTED_PATHS)
    return git("log", "-1", "--format=%H", "--", *HOSTED_PATHS).strip()


def local_urls():
    """dist files that still reference a local file:/// image."""
    bad = []
    for path in glob.glob(os.path.join(ROOT, "dist", "**", "*.json"), recursive=True):
        if "file:///" in open(path, encoding="utf-8").read():
            bad.append(os.path.relpath(path, ROOT))
    return sorted(bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="branch/commit the URLs point at (default: pin to the "
                                  "commit holding the hosted files, committing them if changed)")
    ap.add_argument("--no-render", action="store_true",
                    help="reuse art/faces as-is instead of re-rendering")
    a = ap.parse_args()
    res = publish(a.ref, render=not a.no_render)
    print(json.dumps(res, indent=2))
    if res["local_urls_left"]:
        print("FAIL: local file:/// URLs remain in " + ", ".join(res["local_urls_left"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
