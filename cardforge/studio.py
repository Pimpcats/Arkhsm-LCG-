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

from cardforge import runner, se_bridge  # noqa: E402

PORT = 8570
ROOT = runner.repo_root()

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

def act_generate(p):
    campaign = p.get("campaign", "still_hour")
    return run_job("generate", runner.run_generate, campaign,
                   only=set(p["only"].split()) if p.get("only") else None,
                   dry_run=bool(p.get("dry_run")), starter=bool(p.get("starter")))


def act_seeds(p):
    return run_job("seeds", runner.run_seeds, p.get("campaign", "still_hour"),
                   variants=int(p.get("variants", 4)), dry_run=bool(p.get("dry_run")))


def act_contact(p):
    return run_job("contact", runner.run_contact, p.get("campaign", "still_hour"))


def act_index(p):
    return run_job("index", runner.run_index, p.get("campaign", "still_hour"))


def act_backend_check(p):
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    ok, msg = runner.make_backend(camp).check()
    return {"ok": ok, "message": "[{}] {}".format(camp.get("backend", "a1111"), msg)}


def act_choose(p):
    """Pick a variant AND immediately re-compose that card's face with it."""
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    out_dir = runner.out_dir_for(camp)
    card = p["card"]
    with open(os.path.join(out_dir, card, "chosen.txt"), "w") as f:
        f.write(p["file"])
    # update this card's index entry in place
    index_path = os.path.join(out_dir, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {}
    index[card] = os.path.relpath(os.path.join(out_dir, card, p["file"]), ROOT)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    # re-compose just this card (fast, synchronous)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--only", card], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return {"ok": True, "composed": True}


def act_place(p):
    """Save an art placement (drag/zoom) and recompose that card from the
    original image — placement is data, so quality never degrades."""
    card = p["card"]
    placements_path = os.path.join(ROOT, "out", "still_hour", "placements.json")
    placements = json.load(open(placements_path)) if os.path.exists(placements_path) else {}
    placements[card] = {"scale": max(0.2, min(6.0, float(p.get("scale", 1.0)))),
                        "ox": float(p.get("ox", 0)), "oy": float(p.get("oy", 0))}
    os.makedirs(os.path.dirname(placements_path), exist_ok=True)
    with open(placements_path, "w") as f:
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
        with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w") as f:
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
    with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w") as f:
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
        r = json.load(open(rp))
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
            chosen = open(chosen_path).read().strip() if os.path.exists(chosen_path) \
                else (pngs[0] if pngs else None)
            face = os.path.exists(os.path.join(ROOT, "art", "faces", cid + ".png"))
            gallery.append({"id": cid, "variants": pngs, "chosen": chosen, "face": face})
    # art-window geometry + placements for the drag editor
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    specs = {}
    for spec_file in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json"):
        p = os.path.join(ROOT, "pipeline", spec_file)
        if os.path.exists(p):
            for c in json.load(open(p)):
                specs[c["id"]] = c["type"]
    boxes = {cid: rp.art_box(t) for cid, t in specs.items()}
    placements = rp.load_placements()
    for g in gallery:
        if g["id"] in boxes:
            g["artbox"] = boxes[g["id"]]
            g["placement"] = placements.get(g["id"], {"scale": 1.0, "ox": 0, "oy": 0})
    campaigns = sorted(d for d in os.listdir(os.path.join(ROOT, "campaigns"))
                       if os.path.isdir(os.path.join(ROOT, "campaigns", d)))
    return {"busy": _busy.is_set(), "campaign": campaign, "campaigns": campaigns,
            "backend": camp.get("backend"), "report": report, "gallery": gallery,
            "se": {"config": se_bridge.load_config(),
                   "bundle_exists": os.path.exists(
                       os.path.join(se_bridge.se_dir(), "frame_cards.js")),
                   "coverage": se_bridge.coverage(campaign)}}


# --------------------------------------------------------------------- http --

ACTIONS = {"generate": act_generate, "seeds": act_seeds, "contact": act_contact,
           "index": act_index, "backend_check": act_backend_check,
           "choose": act_choose, "se_save_config": act_se_save_config,
           "se_bundle": act_se_bundle, "se_launch": act_se_launch,
           "render_placeholders": act_render_placeholders, "apply": act_apply,
           "place": act_place,
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
<title>CardForge Studio</title><style>
:root{--bg:#12121a;--panel:#1b1b26;--ink:#e8e2cf;--dim:#8a8a99;--gold:#e8b24a;--line:#2c2c3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 system-ui,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:baseline}
header h1{font-size:18px;margin:0;color:var(--gold)}header small{color:var(--dim)}
nav{display:flex;gap:4px;padding:10px 20px 0}
nav button{background:none;border:1px solid var(--line);border-bottom:none;color:var(--dim);
padding:8px 18px;border-radius:8px 8px 0 0;cursor:pointer;font-size:14px}
nav button.on{background:var(--panel);color:var(--gold)}
main{padding:16px 20px}section{display:none}section.on{display:block}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:0 10px 10px 10px;padding:16px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
button.act{background:#2a2338;border:1px solid #453a5e;color:var(--ink);padding:7px 14px;
border-radius:7px;cursor:pointer}button.act:hover{border-color:var(--gold)}
input,select,textarea{background:#12121a;border:1px solid var(--line);color:var(--ink);
padding:6px 9px;border-radius:6px;font:inherit}
textarea{width:100%;font-family:ui-monospace,monospace;font-size:12px}
#log{background:#0c0c12;border:1px solid var(--line);border-radius:8px;padding:10px;
height:200px;overflow-y:auto;font:12px ui-monospace,monospace;white-space:pre-wrap;margin-top:14px}
.gal{display:flex;flex-wrap:wrap;gap:10px}.card{background:#12121a;border:1px solid var(--line);
border-radius:8px;padding:8px;width:150px}.card img{width:100%;border-radius:4px;cursor:pointer}
.card img.chosen{outline:2px solid var(--gold)}.card .cid{font-size:11px;color:var(--dim);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stat{display:inline-block;background:#12121a;border:1px solid var(--line);border-radius:6px;
padding:4px 10px;margin-right:8px}.ok{color:#7dc87d}.warn{color:#e8b24a}.bad{color:#e87d7d}
a{color:var(--gold)}h3{margin:4px 0 10px}label{color:var(--dim);font-size:12px}
.cols{display:flex;gap:16px;flex-wrap:wrap}.cols>div{flex:1;min-width:320px}
</style></head><body>
<header><h1>CardForge Studio</h1><small>illustrate &rarr; frame &rarr; apply — THE STILL HOUR</small>
<span style="margin-left:auto"><label>campaign </label><select id=campaign onchange=refresh()></select>
<span id=busy class=warn></span></span></header>
<nav>
<button id=tab-illustrate class=on onclick="tab('illustrate')">Illustrate</button>
<button id=tab-frame onclick="tab('frame')">Frame &mdash; Strange Eons</button>
<button id=tab-apply onclick="tab('apply')">Apply to Mod</button>
</nav><main>

<section id=illustrate class=on><div class=panel>
<div class=row>
<button class=act onclick="post('backend_check')">Check backend</button>
<button class=act onclick="post('seeds',{dry_run:dry()})">Step 0: Seeds</button>
<button class=act onclick="post('generate',{starter:true,dry_run:dry()})">Starter batch</button>
<button class=act onclick="post('generate',{dry_run:dry()})">Full overnight batch</button>
<button class=act onclick="post('contact')">Contact sheets</button>
<button class=act onclick="post('index')">Build index</button>
<label><input type=checkbox id=dryrun checked> dry-run (no GPU)</label>
</div>
<div id=repline class=row></div>
<h3>Gallery <small style="color:var(--dim)">(click a variant to choose it for the index)</small></h3>
<div id=gallery class=gal></div>
</div></section>

<section id=frame><div class=panel>
<p>Strange Eons 3 is the framer: this tab generates the automation bundle, launches SE, and
tracks exported faces. Get the tools once:
<a href="https://strangeeons.cgjennings.ca" target=_blank>Strange Eons 3</a> ·
<a href="https://github.com/CGJennings/strange-eons" target=_blank>source (CGJennings/strange-eons)</a> ·
Arkham plugin: Toolbox &rarr; Manage Plug-ins &rarr; Catalog (current external build via the
Barnaby Files guide / Mythos Busters Discord, + the AH font pack) ·
hi-res blanks: BGG thread.</p>
<div class=cols><div>
<h3>Owner config (once per plugin version)</h3>
<div class=row><label>launch command</label><input id=se_cmd size=48></div>
<div class=row><label>faces dir</label><input id=se_faces size=20>
<label>export DPI</label><input id=se_dpi size=5></div>
<label>class-map keys (frame type &rarr; plugin component)</label>
<textarea id=se_classmap rows=9></textarea>
<label>setting keys (our field &rarr; plugin setting name)</label>
<textarea id=se_keys rows=6></textarea>
<div class=row><button class=act onclick=seSave()>Save config</button></div>
</div><div>
<h3>Run</h3>
<div class=row>
<button class=act onclick="post('se_bundle')">1 · Write frame bundle</button>
<button class=act onclick="post('se_launch')">2 · Launch Strange Eons</button>
<button class=act onclick="post('render_placeholders')" title="No SE yet? Render glyph-grade placeholder faces (Arkham font statlines) straight into the faces dir">or: Render glyph placeholders</button>
</div>
<p id=se_bundle_state class=warn></p>
<h3>Coverage</h3><div id=se_cov></div>
</div></div>
</div></section>

<section id=apply><div class=panel>
<div class=row><button class=act style="font-size:16px;border-color:var(--gold);color:var(--gold)"
onclick="post('export_tts')">★ Compose cards &amp; Export to TTS (one click)</button>
<span style="color:var(--dim)">index → compose faces with your chosen art → local file:/// URLs → rebuild the mod</span></div>
<hr style="border-color:var(--line)">
<p>Or step it manually: push framed faces into the TTS build: writes <code>pipeline/art_urls.json</code> and rebuilds
cards &rarr; mod &rarr; download package. <b>local</b> mode uses <code>file:///</code> URLs —
real art in TTS on this machine, no hosting. <b>hosted</b> swaps in your CDN base URL for sharing.</p>
<div class=row>
<select id=applymode><option value=local>local (file:///)</option><option value=hosted>hosted</option></select>
<input id=baseurl size=44 placeholder="hosted base URL, e.g. https://cdn.example/stillhour">
<button class=act onclick=applyArt()>Apply &amp; rebuild mod</button>
</div>
<div id=applyinfo></div>
</div></section>

<div id=editor style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:9">
<div style="background:var(--panel);border:1px solid var(--gold);border-radius:10px;max-width:860px;
margin:4vh auto;padding:14px">
<div class=row><b id=ed_title style="color:var(--gold)"></b>
<span style="color:var(--dim);font-size:12px">drag the art to pan &middot; wheel or slider to scale &middot; recomposited from the original at full quality</span>
<span style="margin-left:auto"><label>scale </label>
<input type=range id=ed_scale min=0.5 max=3 step=0.02 style="width:160px" oninput=edPreview()>
<button class=act onclick=edSave()>Save &amp; recompose</button>
<button class=act onclick="document.getElementById('editor').style.display='none'">Close</button></span></div>
<div id=ed_stage style="position:relative;margin:auto;overflow:hidden;border:1px solid var(--line)">
<img id=ed_face style="display:block;user-select:none;pointer-events:none">
<div id=ed_win style="position:absolute;overflow:hidden;cursor:grab;outline:2px dashed var(--gold)">
<img id=ed_art draggable=false style="position:absolute;user-select:none"></div></div>
</div></div>
<div id=log></div></main><script>
let seq=0, cur='illustrate';
function tab(t){cur=t;for(const s of ['illustrate','frame','apply']){
document.getElementById(s).classList.toggle('on',s===t);
document.getElementById('tab-'+s).classList.toggle('on',s===t);}}
function dry(){return document.getElementById('dryrun').checked}
function camp(){return document.getElementById('campaign').value||'still_hour'}
async function post(action,params){params=params||{};params.campaign=camp();
const r=await fetch('/api/'+action,{method:'POST',body:JSON.stringify(params)});
const j=await r.json();if(j.message)addlog(j.message);refresh();}
function addlog(l){const el=document.getElementById('log');
el.textContent+=l+'\n';el.scrollTop=el.scrollHeight;}
async function poll(){const r=await fetch('/api/log?since='+seq);
for(const e of await r.json()){addlog(e.line);seq=e.seq+1;}setTimeout(poll,1200);}
async function refresh(){const r=await fetch('/api/status?campaign='+camp());const s=await r.json();
const sel=document.getElementById('campaign');
if(sel.options.length!==s.campaigns.length){sel.innerHTML='';
for(const c of s.campaigns){const o=document.createElement('option');o.value=o.text=c;
if(c===s.campaign)o.selected=true;sel.add(o);}}
document.getElementById('busy').textContent=s.busy?'● working…':'';
const rep=s.report.generated!==undefined?
`<span class=stat>generated <b>${s.report.generated}</b></span>`+
`<span class=stat>failed <b class=${s.report.failed?'bad':'ok'}>${s.report.failed}</b></span>`+
(s.report.dry_run?'<span class="stat warn">dry-run</span>':'')+
(s.report.warnings||[]).map(w=>`<div class=warn>&#9888; ${w}</div>`).join(''):'<span class=stat>no report yet</span>';
document.getElementById('repline').innerHTML=rep;
document.getElementById('gallery').innerHTML=s.gallery.map(g=>
`<div class=card><div class=cid title="${g.id}">${g.id}</div>`+
(g.face?`<img loading=lazy style="outline:2px solid #7dc87d" title="composed card" `+
`src="/art?p=art/faces/${g.id}.png&ts=${Date.now()}">`+
(g.chosen&&g.artbox?`<button class=act style="width:100%;font-size:11px;padding:3px" `+
`onclick='editArt(${JSON.stringify(g).replaceAll("'","&#39;")})'>adjust art \u2921</button>`:''):'')+
`<div style="font-size:10px;color:var(--dim)">variants — click to slot into the card:</div>`+
g.variants.map(v=>`<img loading=lazy class="${v===g.chosen?'chosen':''}" `+
`src="/art?p=out/${s.campaign}/${g.id}/${v}" onclick="post('choose',{card:'${g.id}',file:'${v}'})">`).join('')+
`</div>`).join('')||'<span style="color:var(--dim)">nothing generated yet</span>';
const se=s.se;document.getElementById('se_cmd').value=se.config.launch_command;
document.getElementById('se_faces').value=se.config.faces_dir;
document.getElementById('se_dpi').value=se.config.export_dpi;
if(document.activeElement.id!=='se_classmap')
 document.getElementById('se_classmap').value=JSON.stringify(se.config.classmap,null,2);
if(document.activeElement.id!=='se_keys')
 document.getElementById('se_keys').value=JSON.stringify(se.config.keys,null,2);
document.getElementById('se_bundle_state').textContent=
 se.bundle_exists?'bundle ready: se/frame_cards.js':'no bundle yet — write it first';
const cov=se.coverage;document.getElementById('se_cov').innerHTML=
`<span class=stat>framed <b class=ok>${cov.framed.length}</b>/${cov.total}</span>`+
`<span class=stat>faces dir <code>${cov.faces_dir}</code></span>`+
(cov.missing.length?`<details><summary>${cov.missing.length} missing</summary>`+
`<small>${cov.missing.join(', ')}</small></details>`:'<div class=ok>all faces framed</div>');
document.getElementById('applyinfo').innerHTML=
`<span class=stat>framed faces ready: <b>${cov.framed.filter(f=>!f.endsWith('-back')).length}</b></span>`;
}
function seSave(){post('se_save_config',{launch_command:document.getElementById('se_cmd').value,
faces_dir:document.getElementById('se_faces').value,export_dpi:document.getElementById('se_dpi').value,
classmap:document.getElementById('se_classmap').value,keys:document.getElementById('se_keys').value});}
function applyArt(){post('apply',{mode:document.getElementById('applymode').value,
base_url:document.getElementById('baseurl').value});}
let ed=null;
function editArt(g){ed={g:g,scale:g.placement.scale,ox:g.placement.ox,oy:g.placement.oy,
natW:0,natH:0,disp:1};
const[cw,ch,x0,y0,x1,y1]=g.artbox;
const maxW=820, disp=Math.min(1,maxW/cw); ed.disp=disp;
const stage=document.getElementById('ed_stage');
stage.style.width=(cw*disp)+'px'; stage.style.height=(ch*disp)+'px';
const face=document.getElementById('ed_face');
face.src='/art?p=art/faces/'+g.id+'.png&ts='+Date.now();
face.style.width=(cw*disp)+'px';
const win=document.getElementById('ed_win');
win.style.left=(x0*disp)+'px'; win.style.top=(y0*disp)+'px';
win.style.width=((x1-x0)*disp)+'px'; win.style.height=((y1-y0)*disp)+'px';
const art=document.getElementById('ed_art');
art.onload=()=>{ed.natW=art.naturalWidth;ed.natH=art.naturalHeight;edPreview();};
art.src='/art?p=out/'+camp()+'/'+g.id+'/'+g.chosen;
document.getElementById('ed_title').textContent=g.id;
document.getElementById('ed_scale').value=ed.scale;
document.getElementById('editor').style.display='block';}
function edPreview(){if(!ed||!ed.natW)return;
ed.scale=parseFloat(document.getElementById('ed_scale').value);
const[cw,ch,x0,y0,x1,y1]=ed.g.artbox;const bw=x1-x0,bh=y1-y0;
const cover=Math.max(bw/ed.natW,bh/ed.natH)*ed.scale*ed.disp;
const art=document.getElementById('ed_art');
art.style.width=(ed.natW*cover)+'px';
art.style.left=(-((ed.natW*cover)-(bw*ed.disp))/2+ed.ox*ed.disp)+'px';
art.style.top =(-((ed.natH*cover)-(bh*ed.disp))/2+ed.oy*ed.disp)+'px';}
(function(){const win=document.getElementById('ed_win');let drag=null;
win.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,ox:ed.ox,oy:ed.oy};
win.style.cursor='grabbing';e.preventDefault();});
window.addEventListener('mousemove',e=>{if(!drag||!ed)return;
ed.ox=drag.ox+(e.clientX-drag.x)/ed.disp; ed.oy=drag.oy+(e.clientY-drag.y)/ed.disp; edPreview();});
window.addEventListener('mouseup',()=>{drag=null;win.style.cursor='grab';});
win.addEventListener('wheel',e=>{e.preventDefault();const s=document.getElementById('ed_scale');
s.value=Math.max(0.5,Math.min(3,parseFloat(s.value)-e.deltaY*0.0012));edPreview();});})();
async function edSave(){if(!ed)return;
await post('place',{card:ed.g.id,scale:ed.scale,ox:ed.ox,oy:ed.oy});
document.getElementById('ed_face').src='/art?p=art/faces/'+ed.g.id+'.png&ts='+Date.now();
addlog(ed.g.id+' recomposed with new placement');}
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
