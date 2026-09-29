"""Draw Global's XML UI (TTS screen-space UI) over rendered shots (assistant tool).

TTS lays its XML UI out on a 1920x1080 reference canvas (scaled to the
screen), with Unity UI rules. This draws a practical subset with Pillow:
Defaults (by tag and class), active/visibility (as the host seated at White),
rectAlignment + offsetXY + width/height, scale, position, Panel,
Vertical/Horizontal/Grid/TableLayout (padding, spacing, preferred sizes,
childForceExpand), Button (color, text, icon), Text, Image, InputField,
Toggle, outline and color (#rgb[a], rgba(), named). Unknown elements are laid
out like a Panel. Scroll views, masks, tooltips, animations and fonts other
than a stand-in are not reproduced.
"""
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

REF_W, REF_H = 1920, 1080
FONT_FILES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
FONT_SERIF = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]

NAMED = {"white": (255, 255, 255, 255), "black": (0, 0, 0, 255), "grey": (128, 128, 128, 255),
         "gray": (128, 128, 128, 255), "red": (219, 26, 24, 255), "green": (49, 179, 43, 255),
         "blue": (31, 135, 255, 255), "yellow": (231, 229, 44, 255), "orange": (244, 100, 29, 255),
         "purple": (160, 32, 240, 255), "pink": (245, 112, 206, 255), "teal": (33, 177, 155, 255),
         "brown": (113, 59, 23, 255), "clear": (0, 0, 0, 0)}


def parse_color(s, default=None):
    if s is None:
        return default
    s = str(s).strip()
    if not s:
        return default
    lo = s.lower()
    if lo in NAMED:
        return NAMED[lo]
    m = re.match(r"rgba?\(([^)]*)\)", lo)
    if m:
        v = [float(x) for x in m.group(1).split(",")]
        if all(x <= 1.0 for x in v[:3]):
            v = [x * 255 for x in v[:3]] + v[3:]
        a = v[3] if len(v) > 3 else 1.0
        return (int(v[0]), int(v[1]), int(v[2]), int(a * 255 if a <= 1 else a))
    if lo.startswith("#"):
        h = lo[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            a = int(h[6:8], 16) if len(h) >= 8 else 255
            return (r, g, b, a)
        except ValueError:
            return default
    parts = s.replace(",", " ").split()
    try:
        v = [float(x) for x in parts]
        if len(v) >= 3:
            a = v[3] if len(v) > 3 else 1.0
            return (int(v[0] * 255), int(v[1] * 255), int(v[2] * 255), int(a * 255))
    except ValueError:
        pass
    return default


def _nums(s, n, default=0.0):
    try:
        v = [float(x) for x in str(s).replace(",", " ").split()]
    except ValueError:
        v = []
    while len(v) < n:
        v.append(v[-1] if v and n == 4 and len(v) == 1 else default)
    return v[:n]


def _children(el):
    c = el.get("children")
    return c if isinstance(c, list) else []


def _truthy(v, default=True):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("false", "0", "no")


class Layout:
    def __init__(self, xml_table, assets, seat="White", admin=True):
        self.assets = assets or {}
        self.seat = seat
        self.admin = admin
        self.tag_defaults = {}
        self.class_defaults = {}
        self.boxes = []          # drawn items: (kind, rect, el, attrs)
        self.roots = []
        for el in xml_table or []:
            if not isinstance(el, dict):
                continue
            if el.get("tag") == "Defaults":
                self._defaults(el)
            else:
                self.roots.append(el)

    def _defaults(self, el):
        for d in _children(el):
            if not isinstance(d, dict):
                continue
            a = dict(d.get("attributes") or {})
            cls = a.pop("class", None)
            tag = (d.get("tag") or "").lower()
            if cls:
                for c in str(cls).split():
                    self.class_defaults.setdefault((tag, c), {}).update(a)
            else:
                self.tag_defaults.setdefault(tag, {}).update(a)

    def attrs(self, el):
        tag = (el.get("tag") or "").lower()
        a = dict(self.tag_defaults.get(tag, {}))
        own = el.get("attributes") or {}
        for c in str(own.get("class", "")).split():
            a.update(self.class_defaults.get((tag, c), {}))
        a.update(own)
        return a

    def visible(self, a):
        if not _truthy(a.get("active"), True):
            return False
        vis = str(a.get("visibility", "") or "").strip()
        if vis:
            allowed = [v.strip() for v in vis.split("|") if v.strip()]
            ok = self.seat in allowed or (self.admin and ("Admin" in allowed or "Host" in allowed))
            if not ok:
                return False
        return True

    # ---- layout --

    def place(self, el, parent_rect, forced=None):
        """Place one element inside parent_rect (x0, y0, x1, y1 in canvas px,
        y down). forced: a rect a layout group assigned to it."""
        a = self.attrs(el)
        if not self.visible(a):
            return
        if forced is not None:
            rect = forced
        else:
            px0, py0, px1, py1 = parent_rect
            pw, ph = px1 - px0, py1 - py0
            w = float(a["width"]) if a.get("width") not in (None, "") else pw
            h = float(a["height"]) if a.get("height") not in (None, "") else ph
            align = str(a.get("rectAlignment", "MiddleCenter"))
            ox, oy = _nums(a.get("offsetXY", "0 0"), 2)
            if a.get("position"):
                pxy = _nums(a["position"], 3)
                ox, oy = ox + pxy[0], oy + pxy[1]
            if "Left" in align:
                x0 = px0
            elif "Right" in align:
                x0 = px1 - w
            else:
                x0 = px0 + (pw - w) / 2
            if align.startswith("Upper"):
                y0 = py0
            elif align.startswith("Lower"):
                y0 = py1 - h
            else:
                y0 = py0 + (ph - h) / 2
            x0 += ox
            y0 -= oy
            rect = (x0, y0, x0 + w, y0 + h)
        # scale about the element's pivot (its centre)
        sc = _nums(a.get("scale", "1 1 1"), 3, 1.0)
        if sc[0] != 1 or sc[1] != 1:
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            hw, hh = (rect[2] - rect[0]) / 2 * sc[0], (rect[3] - rect[1]) / 2 * sc[1]
            if forced is None:
                align = str(a.get("rectAlignment", "MiddleCenter"))
                # a scaled element keeps its anchored edge (Unity pivots follow the alignment)
                if "Right" in align:
                    cx = rect[2] - hw
                elif "Left" in align:
                    cx = rect[0] + hw
                if align.startswith("Lower"):
                    cy = rect[3] - hh
                elif align.startswith("Upper"):
                    cy = rect[1] + hh
            rect = (cx - hw, cy - hh, cx + hw, cy + hh)
        self.boxes.append((el.get("tag"), rect, el, a, sc[0]))
        self.layout_children(el, a, rect, sc[0])

    def layout_children(self, el, a, rect, scale):
        kids = [c for c in _children(el) if isinstance(c, dict) and c.get("tag")]
        kids = [c for c in kids if self.visible(self.attrs(c))]
        if not kids:
            return
        tag = (el.get("tag") or "").lower()
        pad = _nums(a.get("padding", "0 0 0 0"), 4)   # left right top bottom
        sp = float(_nums(a.get("spacing", "0"), 1)[0])
        s = scale
        x0, y0, x1, y1 = rect[0] + pad[0] * s, rect[1] + pad[2] * s, rect[2] - pad[1] * s, rect[3] - pad[3] * s
        if tag in ("verticallayout", "horizontallayout", "verticalscrollview", "horizontalscrollview"):
            vertical = tag.startswith("vertical")
            total = (y1 - y0) if vertical else (x1 - x0)
            n = len(kids)
            prefs = []
            for c in kids:
                ca = self.attrs(c)
                key = "preferredHeight" if vertical else "preferredWidth"
                alt = "minHeight" if vertical else "minWidth"
                v = ca.get(key) or ca.get(alt)
                prefs.append(float(v) * s if v not in (None, "") else None)
            fixed = sum(p for p in prefs if p is not None)
            free = [i for i, p in enumerate(prefs) if p is None]
            avail = total - sp * s * (n - 1) - fixed
            each = avail / len(free) if free else 0
            expand = _truthy(a.get("childForceExpandHeight" if vertical else "childForceExpandWidth"), True)
            sizes = [p if p is not None else max(0, each) for p in prefs]
            if expand and not free and fixed < total:
                extra = (total - sp * s * (n - 1) - fixed) / n
                sizes = [z + extra for z in sizes]
            pos = y0 if vertical else x0
            for c, z in zip(kids, sizes):
                r = (x0, pos, x1, pos + z) if vertical else (pos, y0, pos + z, y1)
                self.place(c, r, forced=r)
                pos += z + sp * s
        elif tag == "tablelayout":
            rows = [c for c in kids if (c.get("tag") or "").lower() == "row"]
            n = max(1, len(rows))
            prefs = []
            for r_ in rows:
                ra = self.attrs(r_)
                v = ra.get("preferredHeight")
                prefs.append(float(v) * s if v not in (None, "") else None)
            fixed = sum(p for p in prefs if p is not None)
            free = [p for p in prefs if p is None]
            each = ((y1 - y0) - fixed - sp * s * (n - 1)) / len(free) if free else 0
            pos = y0
            for r_, p in zip(rows, prefs):
                z = p if p is not None else each
                rr = (x0, pos, x1, pos + z)
                ra = self.attrs(r_)
                if self.visible(ra):
                    self.boxes.append(("Row", rr, r_, ra, s))
                    cells = [c for c in _children(r_) if isinstance(c, dict)]
                    cw = (x1 - x0) / max(1, len(cells))
                    for i, cell in enumerate(cells):
                        cr = (x0 + i * cw, pos, x0 + (i + 1) * cw, pos + z)
                        self.place(cell, cr, forced=cr)
                pos += z + sp * s
        elif tag == "gridlayout":
            cs = _nums(a.get("cellSize", "100 100"), 2)
            cs = (cs[0] * s, cs[1] * s)
            spx = _nums(a.get("spacing", "0 0"), 2)
            cols = max(1, int(((x1 - x0) + spx[0] * s) // (cs[0] + spx[0] * s)))
            for i, c in enumerate(kids):
                cx, cy = x0 + (i % cols) * (cs[0] + spx[0] * s), y0 + (i // cols) * (cs[1] + spx[1] * s)
                r = (cx, cy, cx + cs[0], cy + cs[1])
                self.place(c, r, forced=r)
        else:
            for c in kids:
                self.place(c, (x0, y0, x1, y1))

    def run(self, width=REF_W, height=REF_H):
        for el in self.roots:
            self.place(el, (0, 0, width, height))
        return self.boxes


_font_cache = {}


def _font(size, serif=False):
    size = max(6, int(round(size)))
    k = (size, serif)
    if k not in _font_cache:
        f = None
        for p in (FONT_SERIF if serif else []) + FONT_FILES:
            if os.path.isfile(p):
                f = ImageFont.truetype(p, size)
                break
        _font_cache[k] = f or ImageFont.load_default()
    return _font_cache[k]


def _text(draw, rect, text, a, scale, default_size=14, default_color=(50, 50, 50, 255)):
    if not text:
        return
    size = float(a.get("fontSize", default_size)) * scale
    serif = "teutonic" in str(a.get("font", "")).lower()
    font = _font(size, serif)
    col = parse_color(a.get("textColor") or a.get("color") if (a.get("_is_text")) else a.get("textColor"),
                      default_color)
    align = str(a.get("alignment", "MiddleCenter"))
    x0, y0, x1, y1 = rect
    lines = str(text).split("\n")
    lh = size * 1.15
    th = lh * len(lines)
    if align.startswith("Upper"):
        ty = y0
    elif align.startswith("Lower"):
        ty = y1 - th
    else:
        ty = (y0 + y1) / 2 - th / 2
    for ln in lines:
        tw = draw.textlength(ln, font=font)
        if "Left" in align:
            tx = x0 + 2
        elif "Right" in align:
            tx = x1 - tw - 2
        else:
            tx = (x0 + x1) / 2 - tw / 2
        draw.text((tx, ty), ln, font=font, fill=col)
        ty += lh


def draw(img, boxes, asset_files, sx=1.0, sy=1.0):
    """Draw laid-out boxes on a PIL image (RGBA overlay composited)."""
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    icon_cache = {}

    def icon(name):
        if name in icon_cache:
            return icon_cache[name]
        f = asset_files.get(name)
        im = None
        if f and os.path.isfile(f):
            try:
                im = Image.open(f).convert("RGBA")
            except Exception:
                im = None
        icon_cache[name] = im
        return im

    drawn = 0
    for tag, rect, el, a, scale in boxes:
        tag = (tag or "").lower()
        r = (rect[0] * sx, rect[1] * sy, rect[2] * sx, rect[3] * sy)
        if r[2] - r[0] < 1 or r[3] - r[1] < 1:
            continue
        ri = tuple(int(round(v)) for v in r)
        if tag in ("panel", "verticallayout", "horizontallayout", "tablelayout", "gridlayout", "row", "cell",
                   "verticalscrollview", "horizontalscrollview"):
            c = parse_color(a.get("color"), None)
            if tag in ("panel", "verticallayout", "horizontallayout", "tablelayout", "gridlayout") and c is None:
                c = None
            if c and c[3] > 0:
                d.rectangle(ri, fill=c)
                drawn += 1
            oc = parse_color(a.get("outline"), None)
            if oc and oc[3] > 0:
                ow = max(1, int(_nums(a.get("outlineSize", "1 1"), 2)[0] * scale * sx))
                d.rectangle(ri, outline=oc, width=min(ow, 6))
            if a.get("image"):
                im = icon(a["image"])
                if im is not None:
                    over.alpha_composite(im.resize((max(1, ri[2] - ri[0]), max(1, ri[3] - ri[1]))), (ri[0], ri[1]))
        elif tag == "button" or tag == "toggle" or tag == "inputfield" or tag == "dropdown":
            c = parse_color(a.get("color"), (255, 255, 255, 255) if tag != "toggle" else None)
            if c and c[3] > 0:
                d.rounded_rectangle(ri, radius=max(1, int(min(ri[2] - ri[0], ri[3] - ri[1]) * 0.12)), fill=c)
            ic = a.get("icon") or a.get("image")
            if ic:
                im = icon(ic)
                if im is not None:
                    w, h = ri[2] - ri[0], ri[3] - ri[1]
                    ic_c = parse_color(a.get("iconColor"), (255, 255, 255, 255))
                    im2 = im.resize((max(1, w), max(1, h)))
                    if ic_c[:3] != (255, 255, 255):
                        tint = Image.new("RGBA", im2.size, ic_c)
                        im2 = Image.composite(tint, im2, im2.getchannel("A")) if False else im2
                    over.alpha_composite(im2, (ri[0], ri[1]))
            text = el.get("value") if isinstance(el.get("value"), str) else a.get("text", "")
            a2 = dict(a)
            a2.setdefault("fontSize", 14)
            _text(d, r, text, a2, scale * sy, 14, parse_color(a.get("textColor"), (50, 50, 50, 255)))
            drawn += 1
        elif tag == "text":
            text = el.get("value") if isinstance(el.get("value"), str) else a.get("text", "")
            _text(d, r, text, dict(a, _is_text=True), scale * sy, 14,
                  parse_color(a.get("color"), (50, 50, 50, 255)))
            drawn += 1
        elif tag == "image":
            im = icon(a.get("image", ""))
            c = parse_color(a.get("color"), (255, 255, 255, 255))
            if im is not None:
                im2 = im.resize((max(1, ri[2] - ri[0]), max(1, ri[3] - ri[1])))
                over.alpha_composite(im2, (ri[0], ri[1]))
            elif c[3] > 0:
                d.rectangle(ri, fill=c)
            drawn += 1
    img.alpha_composite(over)
    return drawn


def asset_files_for(save, man):
    out = {}
    for a in save.get("CustomUIAssets") or []:
        u = a.get("URL")
        rec = (man.get("images") or {}).get(u)
        if rec and rec.get("file"):
            out[a.get("Name")] = rec["file"]
    return out


def overlay_shot(png_path, xml_table, assets, out_path=None):
    img = Image.open(png_path).convert("RGBA")
    lay = Layout(xml_table, assets)
    boxes = lay.run()
    n = draw(img, boxes, assets, img.size[0] / REF_W, img.size[1] / REF_H)
    img.convert("RGB").save(out_path or png_path)
    return n


def overlay_job(job, save, man, cameras=("overview", "player")):
    """Draw the Global UI on the job's screen-like shots (in place). Returns
    the number of shots drawn on."""
    assets = asset_files_for(save, man)
    n = 0
    for r in job["renders"]:
        snap = json.load(open(r["snapshot"], encoding="utf-8"))
        xt = (snap.get("global") or {}).get("xml_table")
        if not xt:
            continue
        for s in r["shots"]:
            if s["name"] in cameras and os.path.isfile(s["out"]):
                overlay_shot(s["out"], xt, assets)
                n += 1
    return n
