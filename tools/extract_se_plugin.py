#!/usr/bin/env python3
"""Extract frames + exact region maps from the Arkham SE plugin (.seext).

The jaqenZann/Tokeeto plugin (assets/plugins/ArkhamHorrorLCG.seext — fan use
only, per its own license text) contains, for EVERY card type:

  templates/*.jp2      the authentic blank frames (RGBA, windowed art)
  settings/*.settings  exact element geometry as `Key-region = x,y,w,h`
  overlays/, icons/    skill boxes, slot icons, class symbols, …

This tool unpacks that into renderer-ready form:

  assets/frames/se/templates/<name>.png     converted frames (player set)
  assets/frames/se/regions.json             {settings-file: {key: [x,y,w,h]}}
  assets/frames/se/overlays/… icons/…       the overlay/icon PNGs we use

Usage: python3 tools/extract_se_plugin.py [path/to/ArkhamHorrorLCG.seext]
"""
import json
import os
import re
import sys
import zipfile
from io import BytesIO

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SEEXT = os.path.join(ROOT, "assets", "plugins", "ArkhamHorrorLCG.seext")
OUT = os.path.join(ROOT, "assets", "frames", "se")

# frames converted to PNG now (the player-card set + shared backs);
# everything else stays extractable from the .seext on demand
TEMPLATES = [
    "AHLCG-Asset-G", "AHLCG-Asset-K", "AHLCG-Asset-R", "AHLCG-Asset-M",
    "AHLCG-Asset-V", "AHLCG-Asset-N", "AHLCG-Asset-W",
    "AHLCG-Event-G", "AHLCG-Event-K", "AHLCG-Event-R", "AHLCG-Event-M",
    "AHLCG-Event-V", "AHLCG-Event-N", "AHLCG-Event-W",
    "AHLCG-Skill-G", "AHLCG-Skill-K", "AHLCG-Skill-R", "AHLCG-Skill-M",
    "AHLCG-Skill-V", "AHLCG-Skill-N", "AHLCG-Skill-W",
    "AHLCG-PlayerBack", "AHLCG-EncounterBack",
]
OVERLAY_PREFIXES = ("AHLCG-SkillBox-", "AHLCG-SkillIcon-", "AHLCG-NoLevel",
                    "AHLCG-Slot-")
ICON_PREFIXES = ("AHLCG-Slot", "AHLCG-Level")

REGION_RE = re.compile(r"^\s*([A-Za-z0-9#_.-]+)-region\s*=\s*"
                       r"(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)")


def main(seext):
    z = zipfile.ZipFile(seext)
    names = z.namelist()
    os.makedirs(os.path.join(OUT, "templates"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "overlays"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "icons"), exist_ok=True)

    done = 0
    for t in TEMPLATES:
        for ext in (".jp2", ".png"):
            path = "resources/ArkhamHorrorLCG/templates/" + t + ext
            if path in names:
                img = Image.open(BytesIO(z.read(path))).convert("RGBA")
                img.save(os.path.join(OUT, "templates", t + ".png"))
                done += 1
                break
    print("templates converted:", done)

    grabbed = 0
    for n in names:
        base = os.path.basename(n)
        if "/overlays/" in n and base.startswith(OVERLAY_PREFIXES):
            sub = "overlays"
        elif "/icons/" in n and base.startswith(ICON_PREFIXES):
            sub = "icons"
        else:
            continue
        img = Image.open(BytesIO(z.read(n))).convert("RGBA")
        img.save(os.path.join(OUT, sub, os.path.splitext(base)[0] + ".png"))
        grabbed += 1
    print("overlays/icons:", grabbed)

    regions = {}
    for n in names:
        if n.endswith(".settings"):
            group = os.path.splitext(os.path.basename(n))[0]
            entries = {}
            for line in z.read(n).decode("utf-8", "replace").splitlines():
                if line.lstrip().startswith("#"):
                    continue
                m = REGION_RE.match(line)
                if m:
                    x, y, w, h = (int(m.group(i)) for i in range(2, 6))
                    entries[m.group(1)] = [x, y, w, h]
            if entries:
                regions[group] = entries
    with open(os.path.join(OUT, "regions.json"), "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=1, sort_keys=True)
    print("region groups:", len(regions),
          "| total regions:", sum(len(v) for v in regions.values()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SEEXT)
