#!/usr/bin/env python3
"""extract_se_frames.py — pull the card frame/template images out of the
Strange Eons Arkham LCG plugin.

SE plugin bundles (.seext / .seplugin / .separk) are zip archives; the card
frame graphics (the exact borders, parchment boxes, class banners, stat plates
— everything on a card except illustration and text) live inside as image
resources. This extracts every image into assets/frames/<plugin-name>/ so the
renderer / your reference folder can use them.

Usage:
    python3 tools/extract_se_frames.py /path/to/ArkhamHorrorLCG.seext
    python3 tools/extract_se_frames.py plugin.seext --list       # inventory only
    python3 tools/extract_se_frames.py plugin.seext --filter investigator

Notes:
- Find the plugin file in your Strange Eons plugin folder after installing it
  from the catalog (Toolbox > Manage Plug-ins shows the folder; typically
  ~/.StrangeEons3/plug-ins or the equivalent on Windows).
- .jp2 (JPEG-2000) resources are common in SE plugins; Pillow reads them if
  OpenJPEG support is present — this script converts them to PNG when it can
  and copies them raw when it can't.
- These are FFG's designs, community-recreated for personal fan use. Keep them
  out of anything sold or redistributed beyond the usual fan-content norms —
  which is also why assets/frames/ is gitignored by default.
"""
import argparse
import io
import os
import sys
import zipfile

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".jp2", ".gif", ".webp")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin", help="path to the SE plugin bundle (.seext/.seplugin)")
    ap.add_argument("--list", action="store_true", help="inventory only, no extraction")
    ap.add_argument("--filter", default="", help="only paths containing this substring")
    ap.add_argument("--out", default=None, help="output dir (default assets/frames/<plugin>)")
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    name = os.path.splitext(os.path.basename(a.plugin))[0]
    out_dir = a.out or os.path.join(root, "assets", "frames", name)

    with zipfile.ZipFile(a.plugin) as z:
        images = [n for n in z.namelist()
                  if n.lower().endswith(IMAGE_EXTS) and a.filter.lower() in n.lower()]
        print("{} image resource(s) in {}".format(len(images), os.path.basename(a.plugin)))
        if a.list:
            for n in sorted(images):
                print("  " + n)
            return
        os.makedirs(out_dir, exist_ok=True)
        converted = copied = 0
        for n in sorted(images):
            data = z.read(n)
            flat = n.replace("/", "__")
            base, ext = os.path.splitext(flat)
            if ext.lower() == ".jp2":
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(data))
                    img.save(os.path.join(out_dir, base + ".png"))
                    converted += 1
                    continue
                except Exception:
                    pass  # no JPEG-2000 support: copy raw below
            with open(os.path.join(out_dir, flat), "wb") as f:
                f.write(data)
            copied += 1
        print("extracted -> {}  ({} converted to PNG, {} copied raw)".format(
            os.path.relpath(out_dir, root), converted, copied))
        print("Tip: --list first, then --filter (e.g. 'investigator', 'treachery', "
              "'enemy') to find the frame sheets for each layout.")


if __name__ == "__main__":
    sys.exit(main())
