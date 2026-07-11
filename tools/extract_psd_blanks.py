#!/usr/bin/env python3
"""Extract blank card frames + text-region maps from the AHTCG template PSDs.

The community template pack (BGG "Hi-res blank templates…", the OPTIONS doc's
A2 source) ships one layered PSD per card layout. Every piece of example
content is a named TYPE layer (Character Name, Ability Text, stat numbers…)
over pixel frame art, so:

  blank frame  = composite with all type layers (and example-art groups) hidden
  region map   = each type layer's name -> bbox, i.e. exact text placement

Outputs, per PSD:
  assets/frames/psd/<layout>.png            hi-res true-blank frame
  assets/frames/psd/<layout>_regions.json   {layer name: [x0,y0,x1,y1], "_size":[w,h]}

Usage:  python3 tools/extract_psd_blanks.py <dir-with-AHTCG_*.psd>
Needs:  pip install psd-tools
"""
import json
import os
import re
import sys

from PIL import Image
from psd_tools import PSDImage

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "frames", "psd")

# groups holding example ART (not frame) — hidden alongside the type layers
ART_GROUPS = {"character art", "art", "example art"}


def layout_name(fname):
    base = os.path.splitext(os.path.basename(fname))[0]
    base = re.sub(r"^[0-9a-f]{8}-", "", base)          # upload hash prefix
    base = re.sub(r"^AHTCG_", "", base)
    base = re.sub(r"_v[0-9.]+$", "", base)
    return base.lower().replace(" ", "_")


def is_content(layer, parents):
    if layer.kind == "type":
        return True
    # NOTE: char front's 'Backgrounds' smartobject IS the whole frame
    # (scroll, plates, parchment, backdrop in one) — it must stay. Only the
    # 'Character Art' group is example content there.
    return any(p.name.lower() in ART_GROUPS for p in parents)


def extract(psd_path):
    psd = PSDImage.open(psd_path)
    name = layout_name(psd_path)
    regions = {"_size": list(psd.size)}

    def walk(layers, parents):
        for l in layers:
            if l.is_group():
                walk(l, parents + [l])
            elif l.kind == "type":
                # bbox is the layer's rendered extent — our text region
                key = l.name
                i = 2
                while key in regions:              # duplicate layer names
                    key = "{} {}".format(l.name, i)
                    i += 1
                regions[key] = list(l.bbox)
    walk(psd, [])

    def keep(layer):
        # exclude content layers (and anything inside an art group);
        # keep every visible frame/decoration pixel layer
        parents = []
        p = layer.parent
        while p is not None and hasattr(p, "name"):
            parents.append(p)
            p = getattr(p, "parent", None)
        return layer.is_visible() and not is_content(layer, parents)

    # RGBA: transparent regions ARE the art windows — the renderer lays card
    # art underneath and composites this frame on top
    img = psd.composite(layer_filter=keep)
    if img.convert("RGBA").getchannel("A").getextrema() == (255, 255):
        # CMYK docs composite onto an opaque canvas; recover alpha by
        # compositing on white AND black and diffing (a = 255 - (w - b))
        import numpy as np
        w = np.asarray(psd.composite(layer_filter=keep, color=1.0)
                       .convert("RGB"), dtype=np.int16)
        b = np.asarray(psd.composite(layer_filter=keep, color=0.0)
                       .convert("RGB"), dtype=np.int16)
        alpha = (255 - (w - b).mean(axis=2)).clip(0, 255).astype(np.uint8)
        rgb = b.astype(np.float32)
        a = np.maximum(alpha, 1).astype(np.float32)[..., None]
        rgb = (rgb * 255.0 / a).clip(0, 255).astype(np.uint8)
        out = np.dstack([rgb, alpha])
        img = Image.fromarray(out, "RGBA")
    else:
        img = img.convert("RGBA")
    os.makedirs(OUT_DIR, exist_ok=True)
    img.save(os.path.join(OUT_DIR, name + ".png"))
    with open(os.path.join(OUT_DIR, name + "_regions.json"), "w",
              encoding="utf-8") as f:
        json.dump(regions, f, indent=2)
    print("OK  {:32} {}x{}  {} text region(s)".format(
        name, img.width, img.height, len(regions) - 1))
    return name


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    psds = sorted(f for f in os.listdir(src) if f.lower().endswith(".psd"))
    if not psds:
        raise SystemExit("no .psd files in " + src)
    for f in psds:
        extract(os.path.join(src, f))
    print("blanks + region maps -> assets/frames/psd/")
