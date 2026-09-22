#!/usr/bin/env python3
"""import_art.py — bring finished illustrations (e.g. from ChatGPT) into the build.

Each image becomes assets/illustrations/still_hour/<card-id>.jpg, which
render_placeholders.py composites into that card's face on every machine
(a local CardForge pick in out/still_hour/index.json still overrides it).

A card is named by its id or by its ChatGPT art pack number (see
pipeline/chatgpt_art_pack.json), either as an argument or as the file name:

    python3 pipeline/import_art.py picture.png sthrelias
    python3 pipeline/import_art.py picture.png 7            # pack #007
    python3 pipeline/import_art.py --dir incoming/          # 007.png, sthr-lamp.jpg ...

Then: python3 pipeline/publish_hosted.py --ref main   (faces + dist/) and commit.
"""
import argparse
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEST = os.path.join(ROOT, "assets", "illustrations", "still_hour")
PACK = os.path.join(HERE, "chatgpt_art_pack.json")
# longest side kept: comfortably above the largest art window (1050px frames)
# while keeping ~120 committed illustrations small
MAX_SIDE = 1600
EXTS = (".png", ".jpg", ".jpeg", ".webp")


def card_ids():
    manifest = json.load(open(os.path.join(ROOT, "campaigns", "still_hour",
                                           "manifest.json"), encoding="utf-8"))
    return {j["id"] for j in manifest if j.get("scene") and not j.get("no_art")}


def pack_numbers():
    if not os.path.exists(PACK):
        return {}
    return {c["n"]: c["id"] for c in json.load(open(PACK, encoding="utf-8"))["cards"]}


def resolve(name, ids, numbers):
    """Card id from an id, a pack number ('7', '007', '#007'), or a file stem."""
    key = name.strip().lstrip("#")
    if key in ids:
        return key
    if key.isdigit() and int(key) in numbers:
        return numbers[int(key)]
    raise SystemExit("unknown card '{}': not a card id or art pack number".format(name))


def import_one(src, card):
    im = Image.open(src)
    im.load()
    if im.width < 512 or im.height < 512:
        raise SystemExit("{}: {}x{} is too small for a card".format(src, im.width, im.height))
    im = im.convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    os.makedirs(DEST, exist_ok=True)
    for ext in EXTS:                      # one file per card, whatever it was before
        old = os.path.join(DEST, card + ext)
        if os.path.exists(old):
            os.remove(old)
    out = os.path.join(DEST, card + ".jpg")
    im.save(out, quality=90, optimize=True)
    print("{:28} <- {}  ({}x{})".format(card, os.path.basename(src), im.width, im.height))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image", nargs="?")
    ap.add_argument("card", nargs="?", help="card id or art pack number")
    ap.add_argument("--dir", help="import every image in a folder, named by id or number")
    a = ap.parse_args(argv)
    ids, numbers = card_ids(), pack_numbers()
    if a.dir:
        files = sorted(f for f in os.listdir(a.dir) if f.lower().endswith(EXTS))
        if not files:
            raise SystemExit("no images in " + a.dir)
        for f in files:
            import_one(os.path.join(a.dir, f),
                       resolve(os.path.splitext(f)[0], ids, numbers))
    elif a.image and a.card:
        import_one(a.image, resolve(a.card, ids, numbers))
    else:
        ap.error("give IMAGE CARD, or --dir FOLDER")


if __name__ == "__main__":
    sys.exit(main())
