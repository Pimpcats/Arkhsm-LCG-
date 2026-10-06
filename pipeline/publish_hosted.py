#!/usr/bin/env python3
"""publish_hosted.py — make the TTS build load its card images from GitHub.

Tabletop Simulator on the owner's PC cannot read file:/// paths from whatever
machine produced the build, so a shareable build needs hosted image URLs. This:

  1. renders every card face (pipeline/render_placeholders.py) unless --no-render
  2. converts the campaign's faces/backs (<prefix>*) + the shared deck backs
     (and its chaos token face, pipeline/render_token.py) to JPEG in
     dist/cards/, removing only this campaign's images from earlier builds
     (other campaigns' hosted images are never touched; stale_images())
  2b. packs the faces and backs into a few sprite sheets per scenario box
     (pipeline/pack_sheets.py, dist/cards/sheets/), as SCED's own boxes are
     built: a box then loads about four textures instead of one per card
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
SHEETS_OUT = os.path.join(OUT, "sheets")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campaign_config import CFG  # noqa: E402
# every build step this script starts builds the same campaign
os.environ["CAMPAIGN"] = CFG.id

REPO = "Pimpcats/Arkhsm-LCG-"
PREFIX = CFG.prefix   # <prefix>-* cards and the hyphen-free investigator ids (sthrelias)
JPEG_QUALITY = 88
STATIC_TOKEN = (CFG.static_token or {}).get("id")   # campaign-specific chaos token, if any

# the one-investigator starter slice (dist/stillhour_starter.json) rebuilds too
STARTER = tuple(CFG.starter)
REBUILD = (("build_cards.py",),) + ((("build_cards.py", "--only") + STARTER,) if STARTER else ()) + (
           ("bundle_mod.py",), ("table_presence.py",),
           ("package_download.py", "--require-hosted"), ("place_test.py",))
GUIDE = os.path.join(ROOT, "dist", "guide", CFG.slug + "_campaign_guide.pdf")


def to_jpeg(src, name):
    """Write dist/cards/<name>.jpg; return its short content hash."""
    dest = os.path.join(OUT, name + ".jpg")
    Image.open(src).convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY,
                                        optimize=True, progressive=False)
    return hashlib.sha1(open(dest, "rb").read()).hexdigest()[:10]


def placeholder_art():
    """Chosen illustrations (CardForge's out/still_hour/index.json) that are
    dry-run stubs (1x1 PNGs) rather than real art. A test or dry-run leaves
    these behind; they must never be composited into a published face."""
    idx = os.path.join(CFG.path("out_dir"), "index.json")
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
    others = other_prefixes()
    for png in sorted(glob.glob(os.path.join(FACES, PREFIX + "*.png"))):
        name = os.path.splitext(os.path.basename(png))[0]
        if name.endswith("-back") or not owns_image(name, others):
            continue        # a back goes with its face; "sth*" never takes "sthr*" faces
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
    if STATIC_TOKEN:
        token_png = os.path.join(ROOT, "art", "tokens", STATIC_TOKEN + ".png")
        render_static_token(token_png)
        hashes[STATIC_TOKEN] = to_jpeg(token_png, STATIC_TOKEN)
        plan["_static_token"] = STATIC_TOKEN
    written = set(hashes)

    # sprite sheets: each scenario box's cards (and the player cards, and the
    # investigators) packed into a face sheet and a back sheet per card shape
    sheet_specs, sheet_hashes = [], {}
    if CFG.get("sprite_sheets", True):
        sheet_specs, sheet_hashes = pack_sheet_images()

    # drop this campaign's images from earlier builds that no longer belong to
    # any of its cards; every other campaign's hosted images stay untouched
    for old in stale_images(written):
        os.remove(old)
    for old in sorted(glob.glob(os.path.join(SHEETS_OUT, "*.jpg"))):
        if os.path.splitext(os.path.basename(old))[0] not in {
                s["key"] + k for s in sheet_specs for k in ("-face", "-back")}:
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
    if sheet_specs:
        sheet_base = base + "/sheets"
        urls["_sheets"] = {
            s["key"]: {"box": s["box"], "deck": s["deck"], "cols": s["cols"], "rows": s["rows"],
                       "sideways": s["sideways"], "cells": s["cells"],
                       "face": "{}/{}-face.jpg?v={}".format(sheet_base, s["key"], sheet_hashes[s["key"]]["face"]),
                       "back": "{}/{}-back.jpg?v={}".format(sheet_base, s["key"], sheet_hashes[s["key"]]["back"])}
            for s in sheet_specs}
    guide = guide_url(ref)
    if guide:
        urls["_campaign_guide"] = guide

    os.makedirs(os.path.dirname(CFG.path("art_urls")), exist_ok=True)
    with open(CFG.path("art_urls"), "w", encoding="utf-8") as f:
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
    stale = "dist/" + CFG.slug + "_campaign.json"
    if not compiled and stale in bad:
        bad.remove(stale)       # not rebuilt this run; reported, not judged
    return {"ref": ref, "images": len(written), "guide": guide, "cards": len(
        [k for k in urls if not k.startswith("_")]), "campaign_compiled": compiled,
        "campaign_note": None if compiled else
        "campaign box not rebuilt (scenarios not all locked); " + stale + " is stale",
        "local_urls_left": bad}


def pack_sheet_images():
    """Pack the freshly rendered faces into sprite sheets (pipeline/pack_sheets.py):
    returns (the planned sheets, {key: {face: hash, back: hash}})."""
    import pack_sheets
    boxes, cards = pack_sheets.membership(CFG.id)
    specs = pack_sheets.plan(boxes, pack_sheets.sideways_of_factory(cards))
    import compile_campaign as CC

    def face_path(cid):
        return os.path.join(FACES, cid + ".png")

    def back_path(box, cid):
        # the card's own printed back if it has one; else the shared back it is
        # built with (build_cards.build_card): a scenario box's cards are
        # encounter cards (compile_campaign.normalize), the player bag's are not
        own = os.path.join(FACES, cid + "-back.png")
        if os.path.exists(own):
            return own
        scenario = box not in ("player", "investigators")
        encounter = scenario and CC.normalize(cards[cid]).get("encounter")
        shared = "encounter_back" if encounter else "player_back"
        return os.path.join(ROOT, "assets", "backs", shared + ".png")
    return specs, pack_sheets.write_all(specs, SHEETS_OUT, face_path, back_path)


def other_prefixes():
    """Card-id prefixes of every other campaign with a campaigns/<id>/build.json."""
    out = set()
    for path in glob.glob(os.path.join(ROOT, "campaigns", "*", "build.json")):
        cid = os.path.basename(os.path.dirname(path))
        if cid == CFG.id:
            continue
        try:
            p = json.load(open(path, encoding="utf-8")).get("prefix") or cid[:4]
        except (OSError, ValueError):
            continue
        if p != PREFIX:
            out.add(p)
    return out


def owns_image(name, others=None):
    """True for a dist/cards image this campaign publishes: its <prefix>* card
    faces and backs and its own chaos token. A name that also starts with a
    longer prefix of another campaign (prefix "sth" vs "sthr") is not ours.
    The shared deck backs (player_back, encounter_back) belong to no single
    campaign and are never removed."""
    if STATIC_TOKEN and name == STATIC_TOKEN:
        return True
    if not name.startswith(PREFIX):
        return False
    others = other_prefixes() if others is None else others
    return not any(len(p) > len(PREFIX) and name.startswith(p) for p in others)


def stale_images(written):
    """dist/cards/*.jpg this campaign published earlier but did not write now."""
    stale, others = [], other_prefixes()
    for old in sorted(glob.glob(os.path.join(OUT, "*.jpg"))):
        name = os.path.splitext(os.path.basename(old))[0]
        if name not in written and owns_image(name, others):
            stale.append(old)
    return stale


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
    ap.add_argument("--campaign", help="campaign id (campaigns/<id>/build.json); default $CAMPAIGN or still_hour")
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
