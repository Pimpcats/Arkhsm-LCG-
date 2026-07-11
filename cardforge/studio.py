#!/usr/bin/env python3
"""CardForge Studio — the all-in-one local app for the card-art pipeline.

    python3 -m cardforge.studio          # serves http://127.0.0.1:8570

Three tabs, one flow:
  ILLUSTRATE  drive the CardForge batch (seeds/starter/full, dry-run, backend
              check), watch the live log, browse the gallery, curate variants.
  FRAME       the Strange Eons stage: setup links, the two owner-config seams
              (class-map + setting keys), write the frame bundle, launch SE,
              track exported-face coverage.
  APPLY       push framed faces into the TTS mod: writes pipeline/art_urls.json
              (file:/// for local testing or a hosted base URL) and rebuilds
              cards -> mod -> download package.

Zero dependencies beyond the repo's (stdlib http.server; Pillow only for
contact sheets, as before). Long jobs run on a worker thread; the UI polls the
log. Single user, localhost only — it's a workbench, not a website.
"""
import io
import json
import os
import shlex
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardforge import rig, runner, se_bridge  # noqa: E402

PORT = 8570
ROOT = runner.repo_root()
# children (pipeline scripts) always read/write the repo's files as UTF-8,
# whatever the OS locale says (Windows defaults to cp1252 otherwise)
os.environ.setdefault("PYTHONUTF8", "1")

_log = []                 # (seq, line)
_log_lock = threading.Lock()
_busy = threading.Event()


def log(line):
    with _log_lock:
        _log.append((len(_log), line))


def log_since(seq):
    with _log_lock:
        return [{"seq": s, "line": l} for s, l in _log if s >= seq]


class _Tee(io.TextIOBase):
    def write(self, s):
        for part in s.splitlines():
            if part.strip():
                log(part)
        return len(s)


def run_job(name, fn, *args, **kw):
    """Run a pipeline step on the worker thread, teeing prints into the log."""
    if _busy.is_set():
        return False
    def work():
        _busy.set()
        log("=== {} started ===".format(name))
        try:
            with redirect_stdout(_Tee()):
                fn(*args, **kw)
            log("=== {} finished ===".format(name))
        except SystemExit as e:
            log("=== {} exited: {} ===".format(name, e))
        except Exception:
            for line in traceback.format_exc().splitlines():
                log(line)
            log("=== {} FAILED ===".format(name))
        finally:
            _busy.clear()
    threading.Thread(target=work, daemon=True).start()
    return True


# ------------------------------------------------------------------ actions --

def _backend_first(_campaign, _dry, fn, *args, **kw):
    """A GPU job as one unit of work: make sure the backend is up (launching
    it per rig.json if needed), then run the batch. Dry-run skips the check.
    (Leading underscores keep these names clear of the wrapped fn's kwargs.)"""
    def work():
        rig.ensure_up(runner.load_campaign(_campaign), dry_run=_dry)
        fn(*args, **kw)
    return work


def act_generate(p):
    campaign = p.get("campaign", "still_hour")
    dry = bool(p.get("dry_run"))
    return run_job("generate", _backend_first(
        campaign, dry, runner.run_generate, campaign,
        only=set(p["only"].split()) if p.get("only") else None,
        dry_run=dry, starter=bool(p.get("starter"))))


def act_seeds(p):
    campaign = p.get("campaign", "still_hour")
    dry = bool(p.get("dry_run"))
    return run_job("seeds", _backend_first(
        campaign, dry, runner.run_seeds, campaign,
        variants=int(p.get("variants", 4)), dry_run=dry))


def act_contact(p):
    return run_job("contact", runner.run_contact, p.get("campaign", "still_hour"))


def act_index(p):
    return run_job("index", runner.run_index, p.get("campaign", "still_hour"))


def act_backend_check(p):
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    ok, msg = runner.make_backend(camp).check()
    return {"ok": ok, "message": "[{}] {}".format(camp.get("backend", "a1111"), msg)}


def act_rig_save(p):
    """Persist the backend rig fields (folder / launch command) for the
    campaign's backend kind into rig.json."""
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    kind = camp.get("backend", "a1111")
    cfg = rig.load_rig()
    entry = cfg.setdefault(kind, {})
    for k in ("cwd", "command"):
        if p.get(k) is not None:
            entry[k] = p[k]
    if p.get("startup_timeout"):
        entry["startup_timeout"] = int(p["startup_timeout"])
    rig.save_rig(cfg)
    return {"ok": True, "rig": {k: v for k, v in cfg.items() if k != "_note"}}


def act_models(p):
    """List checkpoints installed on the campaign's backend (model picker)."""
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    backend = runner.make_backend(camp, dry_run=bool(p.get("dry_run")))
    try:
        models = backend.list_models()
    except Exception as e:  # noqa: BLE001 - backend down is a normal state
        return {"ok": False, "models": [], "current": camp.get("checkpoint"),
                "message": "couldn't list models — is the backend running? ({})".format(e)}
    return {"ok": True, "models": models, "current": camp.get("checkpoint")}


def act_model_set(p):
    """Write the chosen checkpoint into campaigns/<name>/campaign.json."""
    campaign = p.get("campaign", "still_hour")
    checkpoint = (p.get("checkpoint") or "").strip()
    if not checkpoint:
        return {"ok": False, "message": "empty checkpoint"}
    path = os.path.join(runner.campaign_dir(campaign), "campaign.json")
    camp = json.load(open(path, encoding="utf-8"))
    camp["checkpoint"] = checkpoint
    with open(path, "w", encoding="utf-8") as f:
        json.dump(camp, f, indent=2)
    log("campaign checkpoint set: " + checkpoint)
    return {"ok": True, "checkpoint": checkpoint}


def act_seed_pick(p):
    """Mark a Step-0 seed portrait as a character's canonical look — stored
    as refs[0] in characters.json (the reference the LoRA/IPAdapter path and
    the owner's LoRA training start from)."""
    campaign = p.get("campaign", "still_hour")
    ch, fname = p["character"], p["file"]
    camp = runner.load_campaign(campaign)
    seed_path = os.path.join(runner.out_dir_for(camp), "seeds", ch, fname)
    if not os.path.exists(seed_path):
        return {"ok": False, "message": "no such seed image: {}/{}".format(ch, fname)}
    rel = os.path.relpath(seed_path, ROOT).replace(os.sep, "/")
    chars_path = os.path.join(runner.campaign_dir(campaign), "characters.json")
    chars = json.load(open(chars_path, encoding="utf-8"))
    entry = chars.setdefault(ch, {})
    entry["refs"] = [rel] + [r for r in entry.get("refs", []) if r != rel]
    with open(chars_path, "w", encoding="utf-8") as f:
        json.dump(chars, f, indent=2)
    log("canonical portrait for {}: {}".format(ch, fname))
    return {"ok": True, "picked": fname}


def act_backend_launch(p):
    """Launch the campaign's backend now (saving any rig fields sent along)
    and wait on the worker thread until its API answers."""
    if p.get("cwd") is not None or p.get("command") is not None:
        act_rig_save(p)
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    return run_job("backend-launch", rig.ensure_up, camp)


def _choose_art(campaign, card, filename):
    """Point a card at an art file and recompose its face (synchronous, fast)."""
    camp = runner.load_campaign(campaign)
    out_dir = runner.out_dir_for(camp)
    with open(os.path.join(out_dir, card, "chosen.txt"), "w", encoding="utf-8") as f:
        f.write(filename)
    index_path = os.path.join(out_dir, "index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    index[card] = os.path.relpath(os.path.join(out_dir, card, filename), ROOT)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--only", card], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)


def act_choose(p):
    """Pick a variant AND immediately re-compose that card's face with it."""
    _choose_art(p.get("campaign", "still_hour"), p["card"], p["file"])
    return {"ok": True, "composed": True}


def act_compose_one(p):
    """Compose one card's face (template + current art/placement), synchronous."""
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--only", p["card"]], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return {"ok": True, "composed": True}


def act_upload_art(p):
    """Manual art: accept a base64 image for a card, store it as a variant,
    make it the chosen art, recompose. Lets the owner place art from ANY
    source, not just CardForge output."""
    import base64
    campaign = p.get("campaign", "still_hour")
    card = p["card"]
    camp = runner.load_campaign(campaign)
    card_dir = os.path.join(runner.out_dir_for(camp), card)
    os.makedirs(card_dir, exist_ok=True)
    existing = [f for f in os.listdir(card_dir) if f.startswith("upload_")]
    fname = "upload_{}.png".format(len(existing) + 1)
    raw = base64.b64decode(p["data_b64"].split(",", 1)[-1])
    with open(os.path.join(card_dir, fname), "wb") as f:
        f.write(raw)
    _choose_art(campaign, card, fname)
    return {"ok": True, "composed": True, "file": fname}


def act_place(p):
    """Save an art placement (drag/zoom) and recompose that card from the
    original image — placement is data, so quality never degrades."""
    card = p["card"]
    placements_path = os.path.join(ROOT, "out", "still_hour", "placements.json")
    placements = json.load(open(placements_path, encoding="utf-8")) if os.path.exists(placements_path) else {}
    placements[card] = {"scale": max(0.2, min(6.0, float(p.get("scale", 1.0)))),
                        "ox": float(p.get("ox", 0)), "oy": float(p.get("oy", 0))}
    os.makedirs(os.path.dirname(placements_path), exist_ok=True)
    with open(placements_path, "w", encoding="utf-8") as f:
        json.dump(placements, f, indent=2)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--only", card], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return {"ok": True, "composed": True}


def act_se_save_config(p):
    cfg = se_bridge.load_config()
    for k in ("launch_command", "faces_dir"):
        if p.get(k):
            cfg[k] = p[k]
    if p.get("export_dpi"):
        cfg["export_dpi"] = int(p["export_dpi"])
    if p.get("classmap"):
        cfg["classmap"] = json.loads(p["classmap"])
    if p.get("keys"):
        cfg["keys"] = json.loads(p["keys"])
    se_bridge.save_config(cfg)
    return {"ok": True}


def act_se_bundle(p):
    result = se_bridge.write_bundle(p.get("campaign", "still_hour"))
    log("SE bundle written: {} jobs -> {}".format(result["job_count"], result["script"]))
    return result


def act_se_launch(p):
    cfg = se_bridge.load_config()
    script = os.path.join(se_bridge.se_dir(), "frame_cards.js")
    if not os.path.exists(script):
        return {"ok": False, "message": "write the bundle first"}
    cmd = cfg["launch_command"].replace("{script}", script)
    try:
        subprocess.Popen(shlex.split(cmd), cwd=ROOT)
        log("launched: " + cmd)
        return {"ok": True, "message": "launched: " + cmd}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": "launch failed ({}) — run manually: {}".format(e, cmd)}


def act_render_placeholders(p):
    """Glyph-grade placeholder faces (Arkham font statlines/icons) into the
    faces dir — they flow through coverage -> Apply like any framed face."""
    def render():
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT)
        log("glyph placeholder faces rendered into art/faces/")
    return run_job("render-placeholders", render)


def act_auto(p):
    """Hands-off: generate all art -> auto-pick a variant per card -> compose
    onto the real frames -> local file:/// URLs -> rebuild the TTS mod. No
    curation step, so the owner never has to LOOK at spoiler cards; the drag
    editor remains available afterwards for any card worth adjusting."""
    campaign = p.get("campaign", "still_hour")
    dry = bool(p.get("dry_run"))
    def chain():
        rig.ensure_up(runner.load_campaign(campaign), dry_run=dry)
        runner.run_generate(campaign, dry_run=dry)
        runner.run_index(campaign)          # auto-picks lowest seed unless curated
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT)
        log("cards composed on the official frames")
        _apply_local_and_rebuild(campaign)
        log("AUTO-BUILD DONE — load dist/the_still_hour_mod.json in TTS")
    return run_job("auto-build", chain)


def _apply_local_and_rebuild(campaign):
    cov = se_bridge.coverage(campaign)
    faces_dir = os.path.join(ROOT, cov["faces_dir"])
    urls = {}
    for face_id in cov["framed"]:
        if face_id.endswith("-back"):
            continue
        urls[face_id] = {"face": "file:///" + os.path.join(faces_dir, face_id + ".png")
                         .replace(os.sep, "/").lstrip("/")}
        back = os.path.join(faces_dir, face_id + "-back.png")
        if os.path.exists(back):
            urls[face_id]["back"] = "file:///" + back.replace(os.sep, "/").lstrip("/")
    with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2)
    log("art_urls.json: {} card(s), local file:/// mode".format(len(urls)))
    for script in ("build_cards.py", "bundle_mod.py", "package_download.py"):
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", script)],
                       check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        log("rebuilt: pipeline/" + script)


def act_export_tts(p):
    """The smooth path: index -> compose all faces with chosen art -> apply
    (local file:/// URLs) -> rebuild the mod. One click to a loadable TTS save."""
    campaign = p.get("campaign", "still_hour")
    def chain():
        runner.run_index(campaign)
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT)
        log("faces composed with chosen art")
        cov = se_bridge.coverage(campaign)
        faces_dir = os.path.join(ROOT, cov["faces_dir"])
        urls = {}
        for face_id in cov["framed"]:
            if face_id.endswith("-back"):
                continue
            urls[face_id] = {"face": "file:///" + os.path.join(faces_dir, face_id + ".png")
                             .replace(os.sep, "/").lstrip("/")}
            back = os.path.join(faces_dir, face_id + "-back.png")
            if os.path.exists(back):
                urls[face_id]["back"] = "file:///" + back.replace(os.sep, "/").lstrip("/")
        with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w", encoding="utf-8") as f:
            json.dump(urls, f, indent=2)
        log("art_urls.json: {} card(s), local file:/// mode".format(len(urls)))
        for script in ("build_cards.py", "bundle_mod.py", "package_download.py"):
            subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", script)],
                           check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
            log("rebuilt: pipeline/" + script)
        log("DONE — load dist/the_still_hour_mod.json in Tabletop Simulator")
    return run_job("export-to-tts", chain)


def act_apply(p):
    """Write pipeline/art_urls.json from framed faces, then rebuild the mod."""
    mode = p.get("mode", "local")           # local (file://) | hosted
    base = p.get("base_url", "").rstrip("/")
    cov = se_bridge.coverage(p.get("campaign", "still_hour"))
    faces_dir = os.path.join(ROOT, cov["faces_dir"])
    urls = {}
    for face_id in cov["framed"]:
        if face_id.endswith("-back"):
            continue
        path = os.path.join(faces_dir, face_id + ".png")
        url = (base + "/" + face_id + ".png") if mode == "hosted" \
            else "file:///" + path.replace(os.sep, "/").lstrip("/")
        urls[face_id] = {"face": url}
        back = os.path.join(faces_dir, face_id + "-back.png")
        if os.path.exists(back):
            urls[face_id]["back"] = (base + "/" + face_id + "-back.png") if mode == "hosted" \
                else "file:///" + back.replace(os.sep, "/").lstrip("/")
    with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2)
    log("art_urls.json: {} card(s), mode={}".format(len(urls), mode))

    def rebuild():
        for script in ("build_cards.py", "bundle_mod.py", "package_download.py"):
            subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", script)],
                           check=True, cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            log("rebuilt: pipeline/" + script)
        log("mod rebuilt with {} real face(s) — load dist/the_still_hour_mod.json".format(len(urls)))
    run_job("apply-to-mod", rebuild)
    return {"ok": True, "cards": len(urls)}


# ------------------------------------------------------------------- status --

def status(campaign="still_hour"):
    camp = runner.load_campaign(campaign)
    out_dir = runner.out_dir_for(camp)
    report = {}
    rp = os.path.join(out_dir, "report.json")
    if os.path.exists(rp):
        r = json.load(open(rp, encoding="utf-8"))
        report = {"generated": len(r["generated"]), "failed": len(r["failed"]),
                  "warnings": r["warnings"], "dry_run": r.get("dry_run")}
    gallery = []
    if os.path.isdir(out_dir):
        for cid in sorted(os.listdir(out_dir)):
            cdir = os.path.join(out_dir, cid)
            if not os.path.isdir(cdir) or cid in ("payloads", "seeds"):
                continue
            pngs = sorted(f for f in os.listdir(cdir) if f.endswith(".png"))
            chosen_path = os.path.join(cdir, "chosen.txt")
            chosen = open(chosen_path, encoding="utf-8").read().strip() if os.path.exists(chosen_path) \
                else (pngs[0] if pngs else None)
            face = os.path.exists(os.path.join(ROOT, "art", "faces", cid + ".png"))
            gallery.append({"id": cid, "variants": pngs, "chosen": chosen, "face": face})
    # Step-0 seed portraits: candidates per character + the picked canonical
    seeds = {}
    chars_path = os.path.join(runner.campaign_dir(campaign), "characters.json")
    chars = json.load(open(chars_path, encoding="utf-8")) \
        if os.path.exists(chars_path) else {}
    seeds_dir = os.path.join(out_dir, "seeds")
    if os.path.isdir(seeds_dir):
        for ch in sorted(os.listdir(seeds_dir)):
            chdir = os.path.join(seeds_dir, ch)
            if not os.path.isdir(chdir):
                continue
            files = sorted(f for f in os.listdir(chdir) if f.endswith(".png"))
            refs = (chars.get(ch) or {}).get("refs") or []
            picked = os.path.basename(refs[0]) if refs else None
            seeds[ch] = {"files": files, "picked": picked,
                         "dir": os.path.relpath(chdir, ROOT).replace(os.sep, "/")}
    # art-window geometry + placements for the drag editor
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    specs = {}
    for spec_file in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json"):
        p = os.path.join(ROOT, "pipeline", spec_file)
        if os.path.exists(p):
            for c in json.load(open(p, encoding="utf-8")):
                specs[c["id"]] = c["type"]
    spoilers = set()
    enc_spec = os.path.join(ROOT, "pipeline", "stillhour_encounter_spec.json")
    if os.path.exists(enc_spec):
        spoilers = {c["id"] for c in json.load(open(enc_spec, encoding="utf-8"))}
    boxes = {cid: rp.art_box(t) for cid, t in specs.items()}
    placements = rp.load_placements()
    for g in gallery:
        if g["id"] in boxes:
            g["artbox"] = boxes[g["id"]]
            g["placement"] = placements.get(g["id"], {"scale": 1.0, "ox": 0, "oy": 0})
        g["spoiler"] = g["id"] in spoilers
    # full card catalog, grouped by deck (the Cards tab)
    def group_for(c):
        if c.get("encounter"):
            return "Encounter — The Named" if "Named" in c.get("traits", "") \
                else "Encounter — The Appointed"
        if c["type"] == "Investigator":
            return "Investigators"
        if "Recollection" in c.get("traits", "") and c.get("class") == "Neutral":
            return "Recollections"
        return "Signatures & Weaknesses"
    catalog = []
    for spec_file in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json"):
        path = os.path.join(ROOT, "pipeline", spec_file)
        if not os.path.exists(path):
            continue
        for c in json.load(open(path, encoding="utf-8")):
            cdir = os.path.join(out_dir, c["id"])
            variants = sorted(f for f in os.listdir(cdir) if f.endswith(".png")) \
                if os.path.isdir(cdir) else []
            chosen_path = os.path.join(cdir, "chosen.txt")
            chosen = open(chosen_path, encoding="utf-8").read().strip() if os.path.exists(chosen_path) \
                else (variants[0] if variants else None)
            catalog.append({
                "id": c["id"], "name": c["name"], "type": c["type"],
                "class": c.get("class", ""), "group": group_for(c),
                "face": os.path.exists(os.path.join(ROOT, "art", "faces", c["id"] + ".png")),
                "spoiler": bool(c.get("encounter")),
                "variants": variants, "chosen": chosen,
            })
    for c in catalog:
        if c["id"] in boxes:
            c["artbox"] = boxes[c["id"]]
            c["placement"] = placements.get(c["id"], {"scale": 1.0, "ox": 0, "oy": 0})
    campaigns = sorted(d for d in os.listdir(os.path.join(ROOT, "campaigns"))
                       if os.path.isdir(os.path.join(ROOT, "campaigns", d)))
    faces_dir_abs = os.path.join(ROOT, "art", "faces")
    faces_ver = 0
    if os.path.isdir(faces_dir_abs):
        faces_ver = int(max((os.path.getmtime(os.path.join(faces_dir_abs, f))
                             for f in os.listdir(faces_dir_abs)), default=0))
    return {"busy": _busy.is_set(), "campaign": campaign, "campaigns": campaigns,
            "backend": camp.get("backend"), "checkpoint": camp.get("checkpoint"),
            "report": report, "gallery": gallery,
            "rig": {k: v for k, v in rig.load_rig().items() if k != "_note"},
            "seeds": seeds, "cards": catalog, "faces_ver": faces_ver,
            "se": {"config": se_bridge.load_config(),
                   "bundle_exists": os.path.exists(
                       os.path.join(se_bridge.se_dir(), "frame_cards.js")),
                   "coverage": se_bridge.coverage(campaign)}}


# --------------------------------------------------------------------- http --

ACTIONS = {"generate": act_generate, "seeds": act_seeds, "contact": act_contact,
           "index": act_index, "backend_check": act_backend_check,
           "rig_save": act_rig_save, "backend_launch": act_backend_launch,
           "seed_pick": act_seed_pick,
           "models": act_models, "model_set": act_model_set,
           "choose": act_choose, "se_save_config": act_se_save_config,
           "se_bundle": act_se_bundle, "se_launch": act_se_launch,
           "render_placeholders": act_render_placeholders, "apply": act_apply,
           "place": act_place, "auto": act_auto, "upload_art": act_upload_art,
           "compose_one": act_compose_one,
           "export_tts": act_export_tts}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/status":
            self._json(status(q.get("campaign", "still_hour")))
        elif u.path == "/api/log":
            self._json(log_since(int(q.get("since", 0))))
        elif u.path == "/art":
            # serve an output image (gallery thumbnails)
            rel = os.path.normpath(q.get("p", "")).lstrip(os.sep)
            path = os.path.join(ROOT, rel)
            allowed = (os.path.join(ROOT, "out"), os.path.join(ROOT, "art"))
            if not path.startswith(allowed) or not os.path.exists(path):
                self._json({"error": "not found"}, 404)
                return
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._json({"error": "unknown path"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            self._json({"error": "unknown path"}, 404)
            return
        action = u.path[len("/api/"):]
        length = int(self.headers.get("Content-Length", 0))
        params = json.loads(self.rfile.read(length) or b"{}")
        fn = ACTIONS.get(action)
        if not fn:
            self._json({"error": "unknown action " + action}, 404)
            return
        try:
            result = fn(params)
            if result is True:
                self._json({"ok": True, "started": True})
            elif result is False:
                self._json({"ok": False, "message": "busy — a job is already running"}, 409)
            else:
                self._json(result)
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "message": str(e)}, 500)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CardForge Studio</title><style>
:root{--bg:#0e0e13;--surface:#17171f;--surface2:#1e1e28;--line:rgba(255,255,255,.08);
--ink:#f2efe6;--dim:#9a97a3;--accent:#d9a648;--accent-ink:#1a1408;--good:#5fc47e;--bad:#e0716a;
--r:14px;--shadow:0 8px 30px rgba(0,0,0,.45)}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
-webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:14px;
padding:14px 26px;background:rgba(14,14,19,.8);backdrop-filter:blur(18px);
border-bottom:1px solid var(--line)}
header h1{font-size:17px;font-weight:600;letter-spacing:.2px}
header .sub{color:var(--dim);font-size:13px}
.spacer{margin-left:auto}
select,input[type=text],input[type=number],input[type=range],textarea{
background:var(--surface2);border:1px solid var(--line);color:var(--ink);
padding:7px 12px;border-radius:10px;font:inherit;font-size:13px;outline:none;
transition:border-color .18s}
select:focus,input:focus,textarea:focus{border-color:var(--accent)}
textarea{width:100%;font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
button{font:inherit;cursor:pointer;transition:all .18s ease}
.btn{background:var(--surface2);border:1px solid var(--line);color:var(--ink);
padding:8px 16px;border-radius:10px;font-size:13.5px;font-weight:500}
.btn:hover{border-color:rgba(255,255,255,.22);transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-weight:600}
.btn.primary:hover{filter:brightness(1.08)}
nav{display:flex;gap:2px;margin:18px auto 0;width:fit-content;background:var(--surface);
border:1px solid var(--line);border-radius:12px;padding:3px}
nav button{background:none;border:none;color:var(--dim);padding:7px 20px;border-radius:9px;
font-size:13.5px;font-weight:500}
nav button.on{background:var(--surface2);color:var(--ink);box-shadow:0 1px 4px rgba(0,0,0,.35)}
main{max-width:1180px;margin:0 auto;padding:20px 26px 120px}
section{display:none;animation:fade .22s ease}
section.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
padding:20px;margin-top:16px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
h2{font-size:15px;font-weight:600;margin:22px 0 10px;letter-spacing:.2px}
h2 small{color:var(--dim);font-weight:400;margin-left:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));gap:14px}
.tile{background:var(--surface2);border:1px solid var(--line);border-radius:12px;
padding:8px;cursor:pointer;transition:all .18s ease}
.tile:hover{transform:translateY(-3px);box-shadow:var(--shadow);border-color:rgba(255,255,255,.18)}
.tile img{width:100%;border-radius:8px;display:block;aspect-ratio:419/600;object-fit:cover;
background:#101016}
.tile img.land{aspect-ratio:750/523}
.tile .nm{font-size:11.5px;font-weight:500;margin-top:7px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.tile .tp{font-size:10.5px;color:var(--dim)}
.tile.spoiler .veil{aspect-ratio:419/600;border-radius:8px;display:flex;flex-direction:column;
align-items:center;justify-content:center;gap:4px;color:var(--dim);font-size:11px;text-align:center;
background:repeating-linear-gradient(45deg,#15151d,#15151d 8px,#1b1b25 8px,#1b1b25 16px)}
.stat{display:inline-flex;align-items:center;gap:6px;background:var(--surface2);
border:1px solid var(--line);border-radius:9px;padding:5px 12px;margin-right:8px;font-size:12.5px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--good)}
.dot.busy{background:var(--accent);animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.35}}
label{color:var(--dim);font-size:12.5px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.gal .card{width:150px}
.gal{display:flex;flex-wrap:wrap;gap:12px}
.card{background:var(--surface2);border:1px solid var(--line);border-radius:12px;padding:8px}
.card img{width:100%;border-radius:6px;cursor:pointer;margin-top:4px}
.card img.chosen{outline:2px solid var(--accent)}
.seedthumb{width:96px;height:96px;object-fit:cover;border-radius:8px;cursor:pointer;
outline:2px solid transparent;transition:outline-color .15s}
.seedthumb:hover{outline-color:var(--dim)}
.seedthumb.chosen{outline:2px solid var(--accent)}
.legend{display:inline-flex;align-items:center;gap:6px;margin-right:14px;color:var(--dim);font-size:12px}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
.card .cid{font-size:11px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#drawer{position:fixed;left:0;right:0;bottom:0;z-index:6;background:rgba(16,16,22,.92);
backdrop-filter:blur(16px);border-top:1px solid var(--line);transition:height .25s ease;height:34px;overflow:hidden}
#drawer.open{height:220px}
#drawer .bar{display:flex;align-items:center;gap:10px;padding:7px 26px;cursor:pointer;
font-size:12px;color:var(--dim)}
#log{padding:0 26px 12px;height:176px;overflow-y:auto;
font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;color:#c9c5bb}
#editor{display:none;position:fixed;inset:0;z-index:9;background:rgba(8,8,12,.72);
backdrop-filter:blur(8px);animation:fade .2s ease}
#zoom{display:none;position:fixed;inset:0;z-index:10;background:rgba(8,8,12,.8);
backdrop-filter:blur(10px);animation:fade .2s ease;align-items:center;justify-content:center}
#zoom_box{background:var(--surface);border:1px solid var(--line);border-radius:18px;
box-shadow:var(--shadow);padding:14px;max-width:92vw}
#zoom_img{display:block;max-width:88vw;max-height:78vh;border-radius:10px;margin:0 auto}
#ed_sheet{background:var(--surface);border:1px solid var(--line);border-radius:18px;
box-shadow:var(--shadow);max-width:900px;margin:3.5vh auto;padding:18px 20px;max-height:93vh;overflow:auto}
#ed_stage{position:relative;margin:12px auto;overflow:hidden;border-radius:10px;
border:1px solid var(--line)}
#ed_face{display:block;user-select:none;pointer-events:none}
#ed_win{position:absolute;overflow:hidden;cursor:grab;outline:2px dashed var(--accent);
outline-offset:-2px;border-radius:2px}
#ed_art{position:absolute;user-select:none}
#ed_strip{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
#ed_strip img{height:74px;border-radius:8px;cursor:pointer;border:2px solid transparent;
transition:all .15s}
#ed_strip img:hover{transform:translateY(-2px)}
#ed_strip img.on{border-color:var(--accent)}
.hint{color:var(--dim);font-size:12px}
hr{border:none;border-top:1px solid var(--line);margin:16px 0}
</style></head><body>
<header><h1>CardForge Studio</h1><span class=sub>THE STILL HOUR · fan content</span>
<span class=spacer></span>
<span id=busy class=stat><span class=dot id=busydot></span><span id=busytext>idle</span></span>
<button class=btn onclick=refresh() title="refresh the gallery and cards">&#8635;</button>
<label>campaign</label><select id=campaign onchange=refresh()></select>
<button class="btn primary" onclick="post('auto',{dry_run:dry()})" title="generate &rarr; place &rarr; compose &rarr; TTS, hands-off">&#9889; Auto-build ALL &rarr; TTS</button>
</header>
<nav>
<button id=tab-cards class=on onclick="tab('cards')">Cards</button>
<button id=tab-illustrate onclick="tab('illustrate')">Illustrate</button>
<button id=tab-frame onclick="tab('frame')">Frame &mdash; Strange Eons</button>
<button id=tab-apply onclick="tab('apply')">Apply to Mod</button>
</nav><main>

<section id=cards class=on>
<div class=panel><div class=row>
<span class=hint>Every card in the campaign, on its real frame. Click a card to place its art —
drag to position, scroll to size. Encounter cards stay hidden behind the
<b>spoiler shield</b> so building the campaign doesn&rsquo;t spoil playing it.</span>
<span class=spacer></span>
<label><input type=checkbox id=spoilshield checked onchange=refresh()> spoiler shield</label>
<button class=btn onclick="post('render_placeholders')">Compose all faces</button>
</div>
<div id=cardgroups></div>
</div></section>

<section id=illustrate><div class=panel>
<div class=row>
<b>Backend</b> <span id=rig_kind class=stat></span>
<label>folder</label><input type=text id=rig_cwd size=22 placeholder="C:\SD\SDXL" onchange=rigSave()>
<label>start with</label><input type=text id=rig_cmd size=18 onchange=rigSave()>
<button class="btn primary" onclick=rigLaunch()>&#9655; Launch backend</button>
<button class=btn onclick="post('backend_check')">Check</button>
</div>
<div class=row>
<label>model</label><select id=model onchange=modelSet() style="max-width:320px">
<option value="">&mdash; load list from the backend &mdash;</option></select>
<button class=btn onclick=modelsLoad() title="fetch the checkpoint list from the running backend">&#8635; Load models</button>
<span id=modelinfo class=hint></span>
</div>
<p class=hint style="margin:2px 0 10px">The Studio starts your image backend itself and waits for its
API &mdash; and every generate job below does the same automatically if it&rsquo;s not already running.
A1111 note: <code>webui.bat --api</code> guarantees the API; if you rely on custom
<code>COMMANDLINE_ARGS</code>, point this at <code>webui-user.bat</code> and add <code>--api</code> there.</p>
<hr>
<div class=row>
<button class=btn onclick="post('seeds',{dry_run:dry()})">Step 0 · Seeds</button>
<button class=btn onclick="post('generate',{starter:true,dry_run:dry()})">Starter batch</button>
<button class=btn onclick="post('generate',{dry_run:dry()})">Full batch</button>
<button class=btn onclick="post('contact')">Contact sheets</button>
<label><input type=checkbox id=dryrun checked> dry-run (no GPU)</label>
</div>
<div id=repline class=row></div>
<div id=seedblock style="display:none">
<h2>Seed portraits <small>Step-0 output &mdash; click each investigator&rsquo;s canonical look; it becomes their reference for every card they appear on</small></h2>
<div id=seedrows></div>
</div>
<h2>Generated art <small>click a variant to slot it into its card</small></h2>
<div style="margin:2px 0 8px">
<span class=legend><i style="outline:2px solid var(--good);outline-offset:-2px"></i> composed card face</span>
<span class=legend><i style="outline:2px solid var(--accent);outline-offset:-2px"></i> chosen art for this card</span>
<span class=legend>grey tiles = dry-run stubs, replaced when you run for real</span>
</div>
<div id=gallery class=gal></div>
</div></section>

<section id=frame><div class=panel>
<p class=hint>Strange Eons produces the pixel-perfect final cards; this tab drives it.
Tools: <a href="https://strangeeons.cgjennings.ca" target=_blank>Strange Eons 3</a> &middot;
<a href="https://github.com/CGJennings/strange-eons" target=_blank>source</a>.
<b>Plugin: skip the in-app catalog (outdated)</b> — use jaqenZann&rsquo;s external build via the
Barnaby Files guide; AH font pack via the Mythos Busters Discord.</p>
<div class=row style="align-items:flex-start">
<div style="flex:1;min-width:320px">
<h2>Owner config <small>once per plugin version</small></h2>
<div class=row><label>launch command</label><input type=text id=se_cmd size=42></div>
<div class=row><label>faces dir</label><input type=text id=se_faces size=16>
<label>DPI</label><input type=number id=se_dpi style="width:70px"></div>
<label>class-map keys</label><textarea id=se_classmap rows=8></textarea>
<label>setting keys</label><textarea id=se_keys rows=5></textarea>
<div class=row style="margin-top:8px"><button class=btn onclick=seSave()>Save config</button></div>
</div>
<div style="flex:1;min-width:280px">
<h2>Run</h2>
<div class=row>
<button class=btn onclick="post('se_bundle')">1 &middot; Write frame bundle</button>
<button class=btn onclick="post('se_launch')">2 &middot; Launch Strange Eons</button>
</div>
<p id=se_bundle_state class=hint></p>
<h2>Coverage</h2><div id=se_cov></div>
</div></div>
</div></section>

<section id=apply><div class=panel>
<div class=row>
<button class="btn primary" onclick="post('export_tts')">Compose cards &amp; Export to TTS</button>
<span class=hint>compose faces with your placed art &rarr; local file:/// URLs &rarr; rebuild the mod</span>
</div>
<hr>
<div class=row>
<select id=applymode><option value=local>local (file:///)</option><option value=hosted>hosted</option></select>
<input type=text id=baseurl size=40 placeholder="hosted base URL (for sharing)">
<button class=btn onclick=applyArt()>Apply manually</button>
<span id=applyinfo></span>
</div>
</div></section>
</main>

<div id=editor onclick="if(event.target===this)edClose()">
<div id=ed_sheet>
<div class=row><b id=ed_title style="font-size:15px"></b>
<span class=hint>drag to position &middot; scroll or slider to size &middot; always recomposited from the original, full quality</span>
<span class=spacer></span>
<label>size</label><input type=range id=ed_scale min=0.5 max=3 step=0.02 style="width:150px" oninput=edPreview()>
<button class="btn primary" onclick=edSave()>Save</button>
<button class=btn onclick=edClose()>Done</button></div>
<div id=ed_stage>
<img id=ed_face><div id=ed_win><img id=ed_art draggable=false></div>
</div>
<div class=row><span class=hint>art for this card — pick one, or bring your own:</span>
<button class=btn style="font-size:12px;padding:5px 12px" onclick="document.getElementById('ed_file').click()">Upload image&hellip;</button>
<input type=file id=ed_file accept="image/*" style="display:none" onchange=edUpload(this)>
</div>
<div id=ed_strip></div>
</div></div>

<div id=zoom onclick="if(event.target===this)zoomClose()">
<div id=zoom_box><img id=zoom_img>
<div class=row style="margin-top:10px">
<span id=zoom_cap class=hint></span><span class=spacer></span>
<button class="btn primary" id=zoom_act onclick=zoomDo()></button>
<button class=btn onclick=zoomClose()>Close</button>
</div></div></div>

<div id=drawer><div class=bar onclick="this.parentNode.classList.toggle('open')">
<span>&#9650;</span> Activity</div><div id=log></div></div>

<script>
let seq=0, cur='cards', ed=null, ST=null;
window.revealed=window.revealed||new Set();
function tab(t){cur=t;for(const x of ['cards','illustrate','frame','apply']){
document.getElementById(x).classList.toggle('on',x===t);
document.getElementById('tab-'+x).classList.toggle('on',x===t);}}
function dry(){return document.getElementById('dryrun').checked}
function rigVals(){return {cwd:document.getElementById('rig_cwd').value,
command:document.getElementById('rig_cmd').value};}
function rigSave(){post('rig_save',rigVals());}
function rigLaunch(){post('backend_launch',rigVals());}
async function modelsLoad(){const j=await post('models');
const sel=document.getElementById('model');sel.innerHTML='';
for(const m of (j.models||[])){const o=document.createElement('option');
o.value=o.text=m;if(j.current&&(m===j.current||m.startsWith(j.current)))o.selected=true;sel.add(o);}
if(j.current&&![...sel.options].some(o=>o.selected)){
const o=document.createElement('option');o.value=j.current;
o.text=j.current+' (not on backend)';o.selected=true;sel.add(o);}}
function modelSet(){const v=document.getElementById('model').value;
if(v)post('model_set',{checkpoint:v});}
let ZOOMFN=null;
function zoomOpen(src,cap,actLabel,actFn){ZOOMFN=actFn||null;
document.getElementById('zoom_img').src=src;
document.getElementById('zoom_cap').textContent=cap||'';
const b=document.getElementById('zoom_act');
b.textContent=actLabel||'';b.style.display=actLabel?'':'none';
document.getElementById('zoom').style.display='flex';}
function zoomClose(){document.getElementById('zoom').style.display='none';ZOOMFN=null;}
function zoomDo(){const f=ZOOMFN;zoomClose();if(f)f();}
document.addEventListener('keydown',e=>{if(e.key==='Escape')zoomClose();});
function camp(){return document.getElementById('campaign').value||'still_hour'}
async function post(action,params){params=params||{};params.campaign=camp();
const r=await fetch('/api/'+action,{method:'POST',body:JSON.stringify(params)});
const j=await r.json();if(j.message)addlog(j.message);refresh();return j;}
function addlog(l){const el=document.getElementById('log');
el.textContent+=l+'\n';el.scrollTop=el.scrollHeight;}
let refreshQueued=false;
async function poll(){try{const r=await fetch('/api/log?since='+seq);
const lines=await r.json();
for(const e of lines){addlog(e.line);seq=e.seq+1;}
if(lines.length&&!refreshQueued){refreshQueued=true;   // live gallery updates
setTimeout(()=>{refreshQueued=false;refresh();},1500);}}catch(e){}
setTimeout(poll,1200);}

function cardTile(c){
const land=c.type==='Investigator';
if(document.getElementById('spoilshield').checked&&c.spoiler&&!window.revealed.has(c.id))
 return `<div class="tile spoiler" onclick="window.revealed.add('${c.id}');refresh()">`+
 `<div class=veil>&#128274;<div>spoiler hidden</div><small>auto-built for you<br>tap to reveal</small></div>`+
 `<div class=nm>encounter card</div><div class=tp>${c.group}</div></div>`;
const img=c.face?`<img loading=lazy class="${land?'land':''}" src="/art?p=art/faces/${c.id}.png&ts=${ST}">`
 :`<div class=veil style="aspect-ratio:${land?'750/523':'419/600'};background:#101016">no face yet</div>`;
return `<div class=tile onclick='editArt(${JSON.stringify(c).replaceAll("'","&#39;")})'>${img}`+
`<div class=nm title="${c.name}">${c.name}</div><div class=tp>${c.type} &middot; ${c.class}</div></div>`;}

function renderCards(s){
const groups={};
for(const c of s.cards)(groups[c.group]=groups[c.group]||[]).push(c);
const order=['Investigators','Signatures & Weaknesses','Recollections',
'Encounter — The Appointed','Encounter — The Named'];
document.getElementById('cardgroups').innerHTML=order.filter(g=>groups[g]).map(g=>
`<h2>${g}<small>${groups[g].length} card${groups[g].length>1?'s':''}</small></h2>`+
`<div class=grid>${groups[g].map(cardTile).join('')}</div>`).join('');}

async function refresh(){const r=await fetch('/api/status?campaign='+camp());const s=await r.json();
ST=s.faces_ver;
const sel=document.getElementById('campaign');
if(sel.options.length!==s.campaigns.length){sel.innerHTML='';
for(const c of s.campaigns){const o=document.createElement('option');o.value=o.text=c;
if(c===s.campaign)o.selected=true;sel.add(o);}}
document.getElementById('busydot').className='dot'+(s.busy?' busy':'');
const kind=s.backend||'a1111';document.getElementById('rig_kind').textContent=kind;
const rg=(s.rig||{})[kind]||{};
for(const [id,val] of [['rig_cwd',rg.cwd||''],['rig_cmd',rg.command||'']]){
const el=document.getElementById(id);if(el&&document.activeElement!==el)el.value=val;}
document.getElementById('modelinfo').innerHTML=s.checkpoint?
('current: <b>'+s.checkpoint+'</b>'+(s.checkpoint==='SET_ME.safetensors'?
' — load the list and pick your model':'')):'';
document.getElementById('busytext').textContent=s.busy?'working&hellip;'.replace('&hellip;','…'):'idle';
renderCards(s);
const rep=s.report.generated!==undefined?
`<span class=stat>generated <b>${s.report.generated}</b></span>`+
`<span class=stat>failed <b style="color:${s.report.failed?'var(--bad)':'var(--good)'}">${s.report.failed}</b></span>`+
(s.report.dry_run?'<span class=stat>dry-run</span>':'')+
(s.report.warnings||[]).map(w=>`<div class=hint>&#9888; ${w}</div>`).join(''):
'<span class=stat>no batch run yet</span>';
document.getElementById('repline').innerHTML=rep;
const seedChars=Object.keys(s.seeds||{});
document.getElementById('seedblock').style.display=seedChars.length?'':'none';
document.getElementById('seedrows').innerHTML=seedChars.map(ch=>{
const sd=s.seeds[ch];
return `<div class=row style="align-items:center;margin-bottom:6px">`+
`<b style="min-width:90px;text-transform:capitalize">${ch}</b>`+
sd.files.map(f=>`<img loading=lazy class="seedthumb${f===sd.picked?' chosen':''}" `+
`title="${f===sd.picked?'canonical portrait':'click to view large'}" `+
`src="/art?p=${sd.dir}/${f}&ts=${ST}" `+
`onclick="zoomOpen(this.src,'${ch} — ${f}','Make canonical',()=>post('seed_pick',{character:'${ch}',file:'${f}'}))">`).join('')+
(sd.picked?`<span class=hint>&#10003; ${sd.picked}</span>`:`<span class=hint>none picked yet</span>`)+
`</div>`;}).join('');
const shield=document.getElementById('spoilshield').checked;
document.getElementById('gallery').innerHTML=s.gallery.map(g=>{
if(shield&&g.spoiler&&!window.revealed.has(g.id))
 return `<div class=card style="width:150px"><div class=cid>&#128274; encounter card</div>`+
 `<div class=veil style="height:110px;border-radius:6px;display:flex;align-items:center;`+
 `justify-content:center;font-size:11px;color:var(--dim);cursor:pointer;`+
 `background:repeating-linear-gradient(45deg,#15151d,#15151d 8px,#1b1b25 8px,#1b1b25 16px)" `+
 `onclick="window.revealed.add('${g.id}');refresh()">tap to reveal</div></div>`;
return `<div class=card style="width:150px"><div class=cid title="${g.id}">${g.id}</div>`+
(g.face?`<img style="outline:2px solid var(--good)" title="composed card — click to view large" `+
`src="/art?p=art/faces/${g.id}.png&ts=${ST}" onclick="zoomOpen(this.src,'${g.id} — composed face')">`:'')+
g.variants.map(v=>`<img loading=lazy class="${v===g.chosen?'chosen':''}" title="click to view large" `+
`src="/art?p=out/${s.campaign}/${g.id}/${v}" `+
`onclick="zoomOpen(this.src,'${g.id} — ${v}','Use on this card',()=>post('choose',{card:'${g.id}',file:'${v}'}))">`).join('')+
`</div>`;}).join('')||'<span class=hint>nothing generated yet — run a batch, or upload art per card from the Cards tab</span>';
const se=s.se;document.getElementById('se_cmd').value=se.config.launch_command;
document.getElementById('se_faces').value=se.config.faces_dir;
document.getElementById('se_dpi').value=se.config.export_dpi;
if(document.activeElement.id!=='se_classmap')
 document.getElementById('se_classmap').value=JSON.stringify(se.config.classmap,null,2);
if(document.activeElement.id!=='se_keys')
 document.getElementById('se_keys').value=JSON.stringify(se.config.keys,null,2);
document.getElementById('se_bundle_state').textContent=
 se.bundle_exists?'bundle ready: se/frame_cards.js':'no bundle yet — write it first';
const cov=se.coverage;
document.getElementById('se_cov').innerHTML=
`<span class=stat>framed <b style="color:var(--good)">${cov.framed.length}</b>/${cov.total}</span>`+
`<span class=stat><code>${cov.faces_dir}</code></span>`;
document.getElementById('applyinfo').innerHTML=
`<span class=stat>faces ready: <b>${cov.framed.filter(f=>!f.endsWith('-back')).length}</b></span>`;}

async function editArt(c){
if(!c.face){await post('compose_one',{card:c.id});c.face=true;}
ed={g:c,scale:(c.placement||{scale:1}).scale,ox:(c.placement||{ox:0}).ox,
oy:(c.placement||{oy:0}).oy,natW:0,natH:0,disp:1};
const[cw,ch,x0,y0,x1,y1]=c.artbox;
const disp=Math.min(1,820/cw);ed.disp=disp;
const stage=document.getElementById('ed_stage');
stage.style.width=(cw*disp)+'px';stage.style.height=(ch*disp)+'px';
const face=document.getElementById('ed_face');
face.src='/art?p=art/faces/'+c.id+'.png&ts='+Date.now();
face.style.width=(cw*disp)+'px';
const win=document.getElementById('ed_win');
win.style.left=(x0*disp)+'px';win.style.top=(y0*disp)+'px';
win.style.width=((x1-x0)*disp)+'px';win.style.height=((y1-y0)*disp)+'px';
document.getElementById('ed_title').textContent=c.name;
document.getElementById('ed_scale').value=ed.scale;
edStrip();edLoadArt();
document.getElementById('editor').style.display='block';}
function edLoadArt(){const art=document.getElementById('ed_art');
if(ed.g.chosen){art.style.display='block';
art.onload=()=>{ed.natW=art.naturalWidth;ed.natH=art.naturalHeight;edPreview();};
art.src='/art?p=out/'+camp()+'/'+ed.g.id+'/'+ed.g.chosen+'&ts='+Date.now();}
else{art.style.display='none';}}
function edStrip(){const el=document.getElementById('ed_strip');
el.innerHTML=(ed.g.variants||[]).map(v=>
`<img class="${v===ed.g.chosen?'on':''}" src="/art?p=out/${camp()}/${ed.g.id}/${v}" `+
`onclick="edUse('${v}')">`).join('')||
'<span class=hint>no art yet for this card — upload an image above, or run a batch</span>';}
async function edUse(v){await post('choose',{card:ed.g.id,file:v});
ed.g.chosen=v;ed.scale=1;ed.ox=0;ed.oy=0;
document.getElementById('ed_scale').value=1;
edStrip();edLoadArt();edFaceRefresh();}
function edUpload(input){const f=input.files[0];if(!f)return;
const rd=new FileReader();
rd.onload=async()=>{const j=await post('upload_art',{card:ed.g.id,data_b64:rd.result});
if(j.file){ed.g.variants=(ed.g.variants||[]).concat([j.file]);ed.g.chosen=j.file;
ed.scale=1;ed.ox=0;ed.oy=0;document.getElementById('ed_scale').value=1;
edStrip();edLoadArt();edFaceRefresh();}};
rd.readAsDataURL(f);input.value='';}
function edFaceRefresh(){document.getElementById('ed_face').src=
'/art?p=art/faces/'+ed.g.id+'.png&ts='+Date.now();}
function edPreview(){if(!ed||!ed.natW)return;
ed.scale=parseFloat(document.getElementById('ed_scale').value);
const[cw,ch,x0,y0,x1,y1]=ed.g.artbox;const bw=x1-x0,bh=y1-y0;
const cover=Math.max(bw/ed.natW,bh/ed.natH)*ed.scale*ed.disp;
const art=document.getElementById('ed_art');
art.style.width=(ed.natW*cover)+'px';
art.style.left=(-((ed.natW*cover)-(bw*ed.disp))/2+ed.ox*ed.disp)+'px';
art.style.top =(-((ed.natH*cover)-(bh*ed.disp))/2+ed.oy*ed.disp)+'px';}
(function(){const win=document.getElementById('ed_win');let drag=null;
win.addEventListener('mousedown',e=>{if(!ed)return;
drag={x:e.clientX,y:e.clientY,ox:ed.ox,oy:ed.oy};win.style.cursor='grabbing';e.preventDefault();});
window.addEventListener('mousemove',e=>{if(!drag||!ed)return;
ed.ox=drag.ox+(e.clientX-drag.x)/ed.disp;ed.oy=drag.oy+(e.clientY-drag.y)/ed.disp;edPreview();});
window.addEventListener('mouseup',()=>{drag=null;win.style.cursor='grab';});
win.addEventListener('wheel',e=>{e.preventDefault();const s=document.getElementById('ed_scale');
s.value=Math.max(0.5,Math.min(3,parseFloat(s.value)-e.deltaY*0.0012));edPreview();});})();
async function edSave(){if(!ed)return;
await post('place',{card:ed.g.id,scale:ed.scale,ox:ed.ox,oy:ed.oy});
edFaceRefresh();addlog(ed.g.id+' recomposed');}
function edClose(){document.getElementById('editor').style.display='none';ed=null;refresh();}
function seSave(){post('se_save_config',{launch_command:document.getElementById('se_cmd').value,
faces_dir:document.getElementById('se_faces').value,export_dpi:document.getElementById('se_dpi').value,
classmap:document.getElementById('se_classmap').value,keys:document.getElementById('se_keys').value});}
function applyArt(){post('apply',{mode:document.getElementById('applymode').value,
base_url:document.getElementById('baseurl').value});}
refresh();poll();setInterval(refresh,4000);
</script></body></html>"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("CardForge Studio: http://127.0.0.1:{}  (Ctrl-C to stop)".format(PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
