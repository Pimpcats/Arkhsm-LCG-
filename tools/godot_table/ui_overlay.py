"""TTS XML UI layout and drawing (assistant tool): Global's screen UI over
rendered shots, and (with object_ui.py) objects' world-space UI.

TTS lays XML UI out with Unity UI rules; this reproduces a practical subset
with Pillow:
  * Defaults (by tag and by class), active / visibility (as the host seated
    at White)
  * rectAlignment, offsetXY, position, width/height (an element without a
    size fills its parent), scale (cumulative: children are laid out in the
    parent's scaled space), rotation about the UI normal in steps of 180
    degrees (the subtree is point-reflected and its text/images turned)
  * Panel, Vertical/HorizontalLayout (padding, spacing, preferred/min sizes,
    childForceExpand), GridLayout (cellSize, spacing), TableLayout (rows,
    cells, columnSpan), Vertical/HorizontalScrollView (content clipped to the
    view, scrolled to the top)
  * Button / Toggle / InputField / Dropdown (color or colors, text,
    textColor(s), icon), Text (color, fontSize, alignment,
    resizeTextForBestFit), Image (image asset, color, preserveAspect),
    outline / outlineSize
  * fonts: the save's own font asset bundles (fetch_assets extracts them);
    DejaVu otherwise
Screen UI uses a 1920x1080 reference canvas. Not reproduced: tooltips,
animations, masks other than scroll views, rich text tags, per-letter
effects.
"""
import json
import os
import re

from PIL import Image, ImageChops, ImageDraw, ImageFont

REF_W, REF_H = 1920, 1080
FONT_FILES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]

NAMED = {"white": (255, 255, 255, 255), "black": (0, 0, 0, 255), "grey": (128, 128, 128, 255),
         "gray": (128, 128, 128, 255), "red": (219, 26, 24, 255), "green": (49, 179, 43, 255),
         "blue": (31, 135, 255, 255), "yellow": (231, 229, 44, 255), "orange": (244, 100, 29, 255),
         "purple": (160, 32, 240, 255), "pink": (245, 112, 206, 255), "teal": (33, 177, 155, 255),
         "brown": (113, 59, 23, 255), "clear": (0, 0, 0, 0)}

LAYOUT_TAGS = ("panel", "verticallayout", "horizontallayout", "tablelayout", "gridlayout", "row", "cell",
               "verticalscrollview", "horizontalscrollview", "mask")


def parse_color(s, default=None):
    if s is None:
        return default
    s = str(s).strip()
    if "|" in s:                      # "normal|highlighted|pressed|disabled"
        s = s.split("|")[0].strip()
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
            return (int(v[0] * 255), int(v[1] * 255), int(v[2] * 255), int(min(1.0, a) * 255))
    except ValueError:
        pass
    return default


def _nums(s, n, default=0.0):
    try:
        v = [float(x) for x in str(s).replace(",", " ").split()]
    except ValueError:
        v = []
    if n == 4 and len(v) == 1:
        v = v * 4
    while len(v) < n:
        v.append(default)
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


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class Box:
    __slots__ = ("tag", "rect", "el", "a", "k", "flip", "clip")

    def __init__(self, tag, rect, el, a, k, flip=False, clip=None):
        self.tag, self.rect, self.el, self.a, self.k, self.flip, self.clip = tag, rect, el, a, k, flip, clip


class Layout:
    def __init__(self, xml_table, assets=None, seat="White", admin=True):
        self.assets = assets or {}
        self.seat = seat
        self.admin = admin
        self.tag_defaults = {}
        self.class_defaults = {}
        self.boxes = []
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

    # ------------------------------------------------------------ layout --

    def place(self, el, parent_rect, k=1.0, forced=None, clip=None):
        """Place el in parent_rect (canvas px, y down); k: the cumulative scale
        of the parent's space. forced: the rect a layout group assigned."""
        a = self.attrs(el)
        if not self.visible(a):
            return
        tag = (el.get("tag") or "").lower()
        if forced is not None:
            rect = forced
        else:
            px0, py0, px1, py1 = parent_rect
            pw, ph = px1 - px0, py1 - py0
            w = _num(a.get("width"))
            h = _num(a.get("height"))
            w = w * k if w is not None else pw
            h = h * k if h is not None else ph
            align = str(a.get("rectAlignment", "MiddleCenter"))
            ox, oy = _nums(a.get("offsetXY", "0 0"), 2)
            if a.get("position"):
                pxy = _nums(a["position"], 3)
                ox, oy = ox + pxy[0], oy + pxy[1]
            ox, oy = ox * k, oy * k
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
        # own scale about the pivot (the anchored edge for aligned elements)
        sc = _nums(a.get("scale", "1 1 1"), 3, 1.0)
        s = sc[0] if sc[0] > 0 else 1.0
        if abs(s - 1.0) > 1e-6 or abs(sc[1] - 1.0) > 1e-6:
            sy = sc[1] if sc[1] > 0 else s
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            hw, hh = (rect[2] - rect[0]) / 2 * s, (rect[3] - rect[1]) / 2 * sy
            if forced is None:
                align = str(a.get("rectAlignment", "MiddleCenter"))
                if "Right" in align:
                    cx = rect[2] - hw
                elif "Left" in align:
                    cx = rect[0] + hw
                if align.startswith("Lower"):
                    cy = rect[3] - hh
                elif align.startswith("Upper"):
                    cy = rect[1] + hh
            rect = (cx - hw, cy - hh, cx + hw, cy + hh)
        kk = k * s
        start = len(self.boxes)
        self.boxes.append(Box(el.get("tag"), rect, el, a, kk, False, clip))
        child_clip = clip
        if tag in ("verticalscrollview", "horizontalscrollview", "mask"):
            child_clip = _intersect(clip, rect)
        self.layout_children(el, a, rect, kk, child_clip)
        # rotation about the UI normal: 180 degrees point-reflects the subtree
        rot = _nums(a.get("rotation", "0 0 0"), 3)[2] % 360.0
        if abs(rot - 180.0) < 1.0:
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            for b in self.boxes[start:]:
                r = b.rect
                b.rect = (2 * cx - r[2], 2 * cy - r[3], 2 * cx - r[0], 2 * cy - r[1])
                b.flip = not b.flip
                # clips from inside the turned subtree turn with it; an
                # ancestor's (a scroll view's viewport) does not
                if b.clip is not None and b.clip is not clip:
                    c = b.clip
                    b.clip = (2 * cx - c[2], 2 * cy - c[3], 2 * cx - c[0], 2 * cy - c[1])

    def layout_children(self, el, a, rect, k, clip):
        kids = [c for c in _children(el) if isinstance(c, dict) and c.get("tag")]
        kids = [c for c in kids if self.visible(self.attrs(c))]
        if not kids:
            return
        tag = (el.get("tag") or "").lower()
        pad = _nums(a.get("padding", "0 0 0 0"), 4)   # left right top bottom
        x0, y0, x1, y1 = rect[0] + pad[0] * k, rect[1] + pad[2] * k, rect[2] - pad[1] * k, rect[3] - pad[3] * k
        if tag in ("verticalscrollview", "horizontalscrollview"):
            # the content keeps its own size, anchored at the top (scrolled to the start)
            for c in kids:
                ca = self.attrs(c)
                w = _num(ca.get("width"))
                h = _num(ca.get("height"))
                w = w * k if w is not None else (x1 - x0)
                h = h * k if h is not None else (y1 - y0)
                r = (x0, y0, x0 + w, y0 + h)
                self.place(c, r, k, forced=r, clip=clip)
            return
        if tag in ("verticallayout", "horizontallayout"):
            vertical = tag == "verticallayout"
            sp = _num(str(a.get("spacing", "0")).split()[0], 0.0) * k
            total = (y1 - y0) if vertical else (x1 - x0)
            n = len(kids)
            prefs = []
            for c in kids:
                ca = self.attrs(c)
                key = "preferredHeight" if vertical else "preferredWidth"
                alt = "minHeight" if vertical else "minWidth"
                v = _num(ca.get(key), None)
                if v is None:
                    v = _num(ca.get(alt), None)
                if v is None and not _truthy(a.get("childForceExpandHeight" if vertical else "childForceExpandWidth"), True):
                    v = _num(ca.get("height" if vertical else "width"), None)
                prefs.append(v * k if v is not None else None)
            fixed = sum(p for p in prefs if p is not None)
            free = [i for i, p in enumerate(prefs) if p is None]
            avail = total - sp * (n - 1) - fixed
            each = avail / len(free) if free else 0
            sizes = [p if p is not None else max(0, each) for p in prefs]
            expand = _truthy(a.get("childForceExpandHeight" if vertical else "childForceExpandWidth"), True)
            if expand and not free and fixed + sp * (n - 1) < total:
                extra = (total - sp * (n - 1) - fixed) / n
                sizes = [z + extra for z in sizes]
            pos = y0 if vertical else x0
            for c, z in zip(kids, sizes):
                r = (x0, pos, x1, pos + z) if vertical else (pos, y0, pos + z, y1)
                self.place(c, r, k, forced=r, clip=clip)
                pos += z + sp
        elif tag == "tablelayout":
            sp = _num(str(a.get("cellSpacing", a.get("spacing", "0"))).split()[0], 0.0) * k
            rows = [c for c in kids if (c.get("tag") or "").lower() == "row"]
            n = max(1, len(rows))
            prefs = []
            for r_ in rows:
                v = _num(self.attrs(r_).get("preferredHeight"), None)
                prefs.append(v * k if v is not None else None)
            fixed = sum(p for p in prefs if p is not None)
            free = [p for p in prefs if p is None]
            each = ((y1 - y0) - fixed - sp * (n - 1)) / len(free) if free else 0
            cols = 0
            for r_ in rows:
                cols = max(cols, sum(int(_num(self.attrs(c).get("columnSpan"), 1) or 1)
                                     for c in _children(r_) if isinstance(c, dict)))
            cols = max(1, cols)
            pos = y0
            for r_, p in zip(rows, prefs):
                z = p if p is not None else each
                rr = (x0, pos, x1, pos + z)
                ra = self.attrs(r_)
                if self.visible(ra):
                    self.boxes.append(Box("Row", rr, r_, ra, k, False, clip))
                    cw = ((x1 - x0) - sp * (cols - 1)) / cols
                    ci = 0
                    for cell in [c for c in _children(r_) if isinstance(c, dict)]:
                        span = int(_num(self.attrs(cell).get("columnSpan"), 1) or 1)
                        cr = (x0 + ci * (cw + sp), pos, x0 + ci * (cw + sp) + cw * span + sp * (span - 1), pos + z)
                        self.place(cell, cr, k, forced=cr, clip=clip)
                        ci += span
                pos += z + sp
        elif tag == "gridlayout":
            cs = _nums(a.get("cellSize", "100 100"), 2)
            cs = (cs[0] * k, cs[1] * k)
            spx = _nums(a.get("spacing", "0 0"), 2)
            spx = (spx[0] * k, spx[1] * k)
            cols = max(1, int(((x1 - x0) + spx[0]) // max(1e-6, cs[0] + spx[0])))
            fixed = str(a.get("constraint", "")).lower()
            if fixed == "fixedcolumncount":
                cols = int(_num(a.get("constraintCount"), cols) or cols)
            for i, c in enumerate(kids):
                cx, cy = x0 + (i % cols) * (cs[0] + spx[0]), y0 + (i // cols) * (cs[1] + spx[1])
                r = (cx, cy, cx + cs[0], cy + cs[1])
                self.place(c, r, k, forced=r, clip=clip)
        else:
            for c in kids:
                self.place(c, (x0, y0, x1, y1), k, clip=clip)

    def run(self, width=REF_W, height=REF_H):
        for el in self.roots:
            self.place(el, (0, 0, width, height))
        return self.boxes


def _intersect(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


# -------------------------------------------------------------- drawing --

_font_cache = {}


def _font(size, name=None, fonts=None):
    size = max(4, int(round(size)))
    path = None
    if name and fonts:
        path = fonts.get(name) or fonts.get(str(name).split("/")[0])
    k = (size, path)
    if k not in _font_cache:
        f = None
        for p in ([path] if path else []) + FONT_FILES:
            if p and os.path.isfile(p):
                try:
                    f = ImageFont.truetype(p, size)
                    break
                except OSError:
                    continue
        _font_cache[k] = f or ImageFont.load_default()
    return _font_cache[k]


def _text_img(text, a, k, rect, fonts, default_size=14, default_color=(50, 50, 50, 255), color_key="color"):
    """RGBA image of the text laid out in rect's size (unrotated)."""
    w, h = int(round(rect[2] - rect[0])), int(round(rect[3] - rect[1]))
    if not text or w < 1 or h < 1:
        return None
    size = (_num(a.get("fontSize"), default_size) or default_size) * k
    name = a.get("font")
    lines = str(text).split("\n")
    if _truthy(a.get("resizeTextForBestFit"), False):
        mx = (_num(a.get("resizeTextMaxSize"), 40) or 40) * k
        mn = (_num(a.get("resizeTextMinSize"), 10) or 10) * k
        size = mx
        while size > mn:
            font = _font(size, name, fonts)
            tw = max(font.getlength(ln) for ln in lines)
            if tw <= w * 0.98 and size * 1.15 * len(lines) <= h * 1.02:
                break
            size *= 0.9
    if size < 1.5:
        return None
    font = _font(size, name, fonts)
    col = parse_color(a.get(color_key), default_color)
    if col is None or col[3] == 0:
        return None
    align = str(a.get("alignment") or a.get("textAlignment") or "MiddleCenter")
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lh = size * 1.15
    th = lh * len(lines)
    if align.startswith("Upper"):
        ty = 0
    elif align.startswith("Lower"):
        ty = h - th
    else:
        ty = h / 2 - th / 2
    for ln in lines:
        tw = font.getlength(ln)
        if "Left" in align:
            tx = 2
        elif "Right" in align:
            tx = w - tw - 2
        else:
            tx = w / 2 - tw / 2
        d.text((tx, ty + (lh - size) / 2), ln, font=font, fill=col)
        ty += lh
    return img


def _paste(over, im, rect, flip, clip, sx, sy):
    if im is None:
        return
    if flip:
        im = im.rotate(180)
    x0, y0 = int(round(rect[0] * sx)), int(round(rect[1] * sy))
    if im.size != (max(1, int(round((rect[2] - rect[0]) * sx))), max(1, int(round((rect[3] - rect[1]) * sy)))):
        im = im.resize((max(1, int(round((rect[2] - rect[0]) * sx))), max(1, int(round((rect[3] - rect[1]) * sy)))))
    if clip is not None:
        cx0, cy0, cx1, cy1 = (int(round(clip[0] * sx)), int(round(clip[1] * sy)),
                              int(round(clip[2] * sx)), int(round(clip[3] * sy)))
        l, t = max(0, cx0 - x0), max(0, cy0 - y0)
        r, b = min(im.size[0], cx1 - x0), min(im.size[1], cy1 - y0)
        if r <= l or b <= t:
            return
        im = im.crop((l, t, r, b))
        x0, y0 = x0 + l, y0 + t
    # alpha_composite needs the destination inside the canvas
    W, H = over.size
    l, t = max(0, -x0), max(0, -y0)
    r, b = min(im.size[0], W - x0), min(im.size[1], H - y0)
    if r <= l or b <= t:
        return
    if (l, t, r, b) != (0, 0, im.size[0], im.size[1]):
        im = im.crop((l, t, r, b))
    over.alpha_composite(im, (x0 + l, y0 + t))


def _rect_img(size, fill, radius=0, outline=None, width=1):
    w, h = size
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if radius > 0:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=outline, width=width)
    else:
        d.rectangle((0, 0, w - 1, h - 1), fill=fill, outline=outline, width=width)
    return im


def draw(img, boxes, assets, sx=1.0, sy=1.0, fonts=None):
    """Draw laid-out boxes on a PIL RGBA image; returns how many drew."""
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    icon_cache = {}

    def icon(name):
        if not name:
            return None
        if name in icon_cache:
            return icon_cache[name]
        f = assets.get(name)
        im = None
        if f and os.path.isfile(f):
            try:
                im = Image.open(f).convert("RGBA")
            except Exception:
                im = None
        icon_cache[name] = im
        return im

    drawn = 0
    for b in boxes:
        tag = (b.tag or "").lower()
        a, r, k = b.a, b.rect, b.k
        W, H = int(round((r[2] - r[0]) * sx)), int(round((r[3] - r[1]) * sy))
        if W < 1 or H < 1:
            continue
        if tag in LAYOUT_TAGS:
            c = parse_color(a.get("color"), None)
            oc = parse_color(a.get("outline"), None)
            if (c and c[3] > 0) or (oc and oc[3] > 0):
                ow = max(1, int(_nums(a.get("outlineSize", "1 1"), 2)[0] * k * sx))
                _paste(over, _rect_img((W, H), c if (c and c[3] > 0) else None, 0,
                                       oc if (oc and oc[3] > 0) else None, min(ow, 8)), r, False, b.clip, sx, sy)
                drawn += 1
            if a.get("image"):
                im = icon(a["image"])
                if im is not None:
                    _paste(over, im, r, b.flip, b.clip, sx, sy)
        elif tag in ("button", "toggle", "inputfield", "dropdown", "togglebutton"):
            default = (255, 255, 255, 255) if tag != "toggle" else None
            c = parse_color(a.get("colors") or a.get("color"), default)
            if c and c[3] > 0:
                _paste(over, _rect_img((W, H), c, max(1, int(min(W, H) * 0.1))), r, False, b.clip, sx, sy)
                drawn += 1
            ic = a.get("icon") or a.get("image")
            if ic:
                im = icon(ic)
                if im is not None:
                    _paste(over, im, r, b.flip, b.clip, sx, sy)
                    drawn += 1
            text = b.el.get("value") if isinstance(b.el.get("value"), str) else a.get("text", "")
            if tag == "inputfield" and not text:
                text = a.get("placeholder", "")
            ck = "textColors" if a.get("textColors") and not a.get("textColor") else "textColor"
            sr = (r[0] * sx, r[1] * sy, r[2] * sx, r[3] * sy)
            ti = _text_img(text, a, k * sy, sr, fonts, 14, (50, 50, 50, 255), ck)
            if ti is not None:
                _paste(over, ti, r, b.flip, b.clip, sx, sy)
                drawn += 1
        elif tag == "text":
            text = b.el.get("value") if isinstance(b.el.get("value"), str) else a.get("text", "")
            sr = (r[0] * sx, r[1] * sy, r[2] * sx, r[3] * sy)
            ti = _text_img(text, a, k * sy, sr, fonts, 14, (50, 50, 50, 255), "color")
            if ti is not None:
                _paste(over, ti, r, b.flip, b.clip, sx, sy)
                drawn += 1
        elif tag == "image":
            im = icon(a.get("image", ""))
            c = parse_color(a.get("color"), (255, 255, 255, 255))
            if im is not None:
                if c[:3] != (255, 255, 255) or c[3] < 255:
                    im = ImageChops.multiply(im, Image.new("RGBA", im.size, c))
                _paste(over, im, r, b.flip, b.clip, sx, sy)
                drawn += 1
            elif c[3] > 0 and not a.get("image"):
                _paste(over, _rect_img((W, H), c), r, False, b.clip, sx, sy)
                drawn += 1
    img.alpha_composite(over)
    return drawn


# --------------------------------------------------------------- assets --

def asset_files_for(save, man):
    out = {}
    for a in save.get("CustomUIAssets") or []:
        u = a.get("URL")
        rec = (man.get("images") or {}).get(u)
        if rec and rec.get("file"):
            out[a.get("Name")] = rec["file"]
    return out


def font_files_for(man):
    """asset name (and asset/font) -> font file, from fetch_assets' font extraction."""
    return dict(man.get("fonts") or {})


def overlay_shot(png_path, xml_table, assets, fonts=None, out_path=None):
    img = Image.open(png_path).convert("RGBA")
    lay = Layout(xml_table, assets)
    boxes = lay.run()
    n = draw(img, boxes, assets, img.size[0] / REF_W, img.size[1] / REF_H, fonts)
    img.convert("RGB").save(out_path or png_path)
    return n


def overlay_job(job, save, man, cameras=("overview", "player", "seat")):
    """Draw the Global UI on the job's screen-like shots (in place)."""
    assets = asset_files_for(save, man)
    fonts = font_files_for(man)
    n = 0
    for r in job["renders"]:
        snap = json.load(open(r["snapshot"], encoding="utf-8"))
        xt = (snap.get("global") or {}).get("xml_table")
        if not xt:
            continue
        for s in r["shots"]:
            if s["name"] in cameras and os.path.isfile(s["out"]):
                overlay_shot(s["out"], xt, assets, fonts)
                n += 1
    return n
