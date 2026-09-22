#!/usr/bin/env python3
"""render_token.py — draw the [static] chaos token face.

A clean, round token in the chaos-token idiom: a bronze rim, a dark field and a
single pale symbol. The symbol is the campaign's own (there is no official
[static] token to reuse): a broken signal trace crossed by scattered noise,
drawn from primitives so no font or generated lettering is involved.

The image is square; TTS crops it to a circle (Custom_Tile, CustomTile Type 2,
the same shape SCED's own chaos tokens use).

Run: python3 pipeline/render_token.py [out.png]
(publish_hosted.py calls render_static_token() and hosts the JPEG.)
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
RIM = (206, 176, 118)
RIM_DARK = (104, 78, 42)
FIELD_IN = (38, 34, 58)
FIELD_OUT = (10, 9, 16)
SYMBOL = (226, 236, 240)


def _radial(size, inner, outer, radius):
    img = Image.new("RGB", (size, size), outer)
    px = img.load()
    c = (size - 1) / 2.0
    for y in range(size):
        for x in range(size):
            t = min(1.0, math.hypot(x - c, y - c) / radius)
            px[x, y] = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
    return img


def render_static_token(path, size=SIZE):
    s = size
    c = s / 2.0
    img = Image.new("RGB", (s, s), RIM_DARK)
    d = ImageDraw.Draw(img)

    # bronze rim: a light band between two dark hairlines
    d.ellipse([2, 2, s - 3, s - 3], fill=RIM_DARK)
    d.ellipse([s * 0.025, s * 0.025, s * 0.975, s * 0.975], fill=RIM)
    d.ellipse([s * 0.075, s * 0.075, s * 0.925, s * 0.925], fill=RIM_DARK)

    # dark field with a faint glow at the centre
    r_field = s * 0.415
    field = _radial(s, FIELD_IN, FIELD_OUT, r_field)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([c - r_field, c - r_field, c + r_field, c + r_field], fill=255)
    img.paste(field, (0, 0), mask)

    # symbol layer: noise specks + a broken, jagged signal trace
    sym = Image.new("L", (s, s), 0)
    sd = ImageDraw.Draw(sym)
    rnd = random.Random(1729)            # deterministic: same image every build
    for _ in range(140):
        a = rnd.uniform(0, 2 * math.pi)
        rr = r_field * math.sqrt(rnd.uniform(0.0, 0.78))
        x, y = c + rr * math.cos(a), c + rr * math.sin(a)
        w = rnd.choice((3, 4, 5, 7))
        sd.rectangle([x, y, x + w, y + 2], fill=rnd.randint(70, 150))
    # an oscilloscope trace: flat, then a burst of irregular spikes, then flat
    half = r_field * 0.80
    pts = []
    steps = 46
    for i in range(steps + 1):
        t = i / steps
        x = c - half + (2 * half) * t
        env = math.exp(-((t - 0.5) / 0.2) ** 2)          # burst in the middle
        amp = r_field * 0.62 * env * rnd.uniform(0.25, 1.0) * (1 if i % 2 else -1)
        pts.append((x, c + amp))
    stroke = max(4, s // 70)
    breaks = {14, 27, 33}                                  # the signal drops out
    for i in range(len(pts) - 1):
        if i in breaks:
            continue
        sd.line([pts[i], pts[i + 1]], fill=255, width=stroke, joint="curve")
    glow = sym.filter(ImageFilter.GaussianBlur(s / 64))
    img.paste(Image.new("RGB", (s, s), (120, 170, 190)), (0, 0), glow.point(lambda v: v // 2))
    img.paste(Image.new("RGB", (s, s), SYMBOL), (0, 0), sym)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "tokens", "sthr-static-token.png")
    print(render_static_token(out))
