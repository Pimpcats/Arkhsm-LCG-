"""Objects' own XML UI (TTS world-space UI) as textured quads (assistant tool).

TTS draws an object's XML UI on the object: 100 UI units = 1 object-local
unit, the UI's x/y run along the object's local x/z (checked against SCED's
playmat, whose slot panels sit on its snap points), a position's z is the
height above the object (negative = up). Each top-level element is laid out
with ui_overlay.Layout (rotations, scales, layouts), drawn to a PNG, and
listed in a sidecar JSON next to the snapshot for the Godot renderer:

  [{"guid", "file", "center": [x, y, z] (object-local, TTS), "size": [w, h]}]
"""
import hashlib
import json
import os

from PIL import Image

import ui_overlay as U

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, ".cache", "godot_assets", "ui")
PX_PER_WORLD = 60.0
MAX_SIDE = 2048
VERSION = "4"


def layers_for(obj, assets, fonts=None):
    xt = obj.get("xml_table")
    if not xt:
        return []
    assets = object_assets(obj, assets)
    lay = U.Layout(xt, assets)
    out = []
    scale = abs(float((obj.get("scale") or [1, 1, 1])[0])) or 1.0
    ppu = max(0.5, min(10.0, PX_PER_WORLD * scale / 100.0))
    for el in lay.roots:
        a = lay.attrs(el)
        if not lay.visible(a):
            continue
        start = len(lay.boxes)
        lay.place(el, (-50.0, -50.0, 50.0, 50.0))
        boxes = lay.boxes[start:]
        # the extent of what can draw (clipped content excluded)
        rects = []
        for b in boxes:
            r = b.rect
            if b.clip is not None:
                r = U._intersect(r, b.clip)
            if r[2] - r[0] > 0.01 and r[3] - r[1] > 0.01:
                rects.append(r)
        if not rects:
            continue
        x0 = min(r[0] for r in rects)
        y0 = min(r[1] for r in rects)
        x1 = max(r[2] for r in rects)
        y1 = max(r[3] for r in rects)
        pos = U._nums(a.get("position", "0 0 0"), 3)
        f = ppu
        while max(x1 - x0, y1 - y0) * f > MAX_SIDE:
            f *= 0.5
        key = hashlib.sha1(json.dumps([VERSION, el, a, f, sorted(lay.tag_defaults.items(), key=str),
                                       sorted((str(k), v) for k, v in lay.class_defaults.items())],
                                      sort_keys=True, default=str).encode()).hexdigest()[:20]
        path = os.path.join(CACHE, key + ".png")
        if not os.path.isfile(path):
            w, h = max(1, int(round((x1 - x0) * f))), max(1, int(round((y1 - y0) * f)))
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            for b in boxes:
                b.rect = (b.rect[0] - x0, b.rect[1] - y0, b.rect[2] - x0, b.rect[3] - y0)
                if b.clip is not None:
                    b.clip = (b.clip[0] - x0, b.clip[1] - y0, b.clip[2] - x0, b.clip[3] - y0)
            U.draw(img, boxes, assets, f, f, fonts)
            # the image's columns run along TTS local +x and its rows along
            # local -z; the renderer's quad runs along Godot +x (TTS -x) and +z
            img = img.rotate(180)
            os.makedirs(CACHE, exist_ok=True)
            img.save(path)
        if Image.open(path).getbbox() is None:
            continue
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        out.append({"guid": obj.get("guid"), "file": path,
                    "center": [cx / 100.0, max(0.0, -pos[2] / 100.0), -cy / 100.0],
                    "size": [(x1 - x0) / 100.0, (y1 - y0) / 100.0]})
    return out


MANIFEST = {}


def object_assets(obj, assets):
    """Global's UI images plus the object's own (images, and sprites of its UI
    bundles as "<asset>/<sprite>")."""
    own = obj.get("ui_assets") or []
    if not own:
        return assets
    out = dict(assets)
    images = MANIFEST.get("images") or {}
    bundles = MANIFEST.get("uibundles") or {}
    for ua in own:
        name, url = ua.get("Name") or "", ua.get("URL") or ""
        from fetch_assets import norm_url
        url = norm_url(url)
        if int(ua.get("Type") or 0) == 0:
            rec = images.get(url) or {}
            if rec.get("file"):
                out[name] = rec["file"]
        else:
            for sprite, fp in (bundles.get(url) or {}).items():
                if sprite != "error":
                    out[name + "/" + sprite] = fp
    return out


def sidecar(snapshot_path, assets, fonts=None):
    snap = json.load(open(snapshot_path, encoding="utf-8"))
    items = []
    for o in snap.get("objects", []):
        try:
            items.extend(layers_for(o, assets, fonts))
        except Exception as e:  # a bad UI never stops a render
            items.append({"guid": o.get("guid"), "error": "%s: %s" % (type(e).__name__, str(e)[:200])})
    out = snapshot_path[:-5] + ".ui.json"
    json.dump(items, open(out, "w"))
    return out, items
