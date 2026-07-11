"""Blank-frame inpainting — the owner's "select the region, generate over it".

For each card layout we ship as a template (the owner's official reference
scans), build a mask from the hand-calibrated region maps (every text/stat
region white, everything else black) and have Stable Diffusion regenerate
JUST those regions as empty card material — parchment panels, empty banner
scrolls — guided by the untouched frame around them. Results land in
vendor/frames/blank_<layout>.png; the renderer picks them up automatically
(template_render.open_template) and stops painting flat cover fills, so
our text sits on regenerated REAL texture instead of solid color.

The art window is left out of the mask on purpose: pasted art covers it
edge to edge. Dry-run (or no GPU) writes the local sampled-fill fallback
blanks plus the exact img2img payloads, so the flow is testable anywhere.

A1111 only in v1 (the Comfy path would need an inpaint workflow template).
"""
import io
import os
import sys

from PIL import Image, ImageDraw

from . import rig, runner

sys.path.insert(0, os.path.join(runner.repo_root(), "pipeline"))

POSITIVE = ("empty blank card frame regions, aged parchment panel, empty dark "
            "ornate banner scroll, weathered paper texture, clean, 1920s "
            "board game card frame, no text")
NEGATIVE = ("text, letters, numbers, words, writing, glyphs, symbols, logo, "
            "watermark, signature, portrait, face, people")

SEED = 20260711


def _mask_for(layout, w, h):
    import template_render as T
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for _key, box in T.inpaint_regions(layout, w, h):
        d.rectangle(list(box), fill=255)
    return mask


def _png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def rebuild_blank_frames(campaign="still_hour", dry_run=False, log=print):
    """Inpaint every template layout into a blank frame under vendor/frames/.
    Returns {layout: path}. Rerun any time — blanks are cheap to regenerate;
    delete vendor/frames/ to fall back to flat cover fills."""
    import template_render as T
    camp = runner.load_campaign(campaign)
    backend = runner.make_backend(camp, dry_run=dry_run)
    if backend.name != "a1111":
        raise RuntimeError("blank-frame inpainting drives A1111 (v1); switch "
                           "the campaign backend or add a Comfy inpaint workflow")
    if not dry_run:
        rig.ensure_up(camp, dry_run=dry_run, on_log=log)
    os.makedirs(T.VENDOR_BLANKS, exist_ok=True)
    done = {}
    for layout in T.LAYOUT_REGIONS:
        if not T.has_template(layout):
            log("SKIP {} (no template)".format(layout))
            continue
        base = Image.open(T.template_path(layout)).convert("RGB")
        w, h = base.size
        mask = _mask_for(layout, w, h)
        dest = T.blank_path(layout)
        if dry_run:
            # payload proves the request; the local fallback keeps renders real
            backend.inpaint(_png_bytes(base), _png_bytes(mask), POSITIVE,
                            NEGATIVE, {"width": w, "height": h,
                                       "checkpoint": camp.get("checkpoint"),
                                       "seed": SEED},
                            "blank_" + layout)
            T.make_local_blank(layout).save(dest)
            log("dry-run: local fallback blank -> vendor/frames/blank_{}.png"
                .format(layout))
        else:
            log("inpainting {} ({}x{})…".format(layout, w, h))
            images = backend.inpaint(_png_bytes(base), _png_bytes(mask),
                                     POSITIVE, NEGATIVE,
                                     {"width": w, "height": h,
                                      "checkpoint": camp.get("checkpoint"),
                                      "seed": SEED},
                                     "blank_" + layout)
            with open(dest, "wb") as f:
                f.write(images[0])
            log("OK  vendor/frames/blank_{}.png".format(layout))
        done[layout] = dest
    log("{} blank frame(s) ready — recompose faces to use them "
        "(Compose all faces / any Save in the card editor)".format(len(done)))
    return done
