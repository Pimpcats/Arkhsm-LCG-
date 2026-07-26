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
import time
import traceback
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardforge import installer, rig, runner, se_bridge  # noqa: E402

PORT = 8570
ROOT = runner.repo_root()
# children (pipeline scripts) always read/write the repo's files as UTF-8,
# whatever the OS locale says (Windows defaults to cp1252 otherwise)
os.environ.setdefault("PYTHONUTF8", "1")

_log = []                 # (seq, line)
_log_lock = threading.Lock()
_busy = threading.Event()
# serialize read-modify-write of the shared override JSONs + their recompose,
# so two concurrent saves can't lose an update or read a half-written file
_state_lock = threading.RLock()


def _write_json_atomic(path, obj):
    """Write JSON so a concurrent reader (incl. the render subprocess) never
    sees a truncated file: write a temp beside it, then atomic os.replace."""
    import tempfile
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


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


_STARTED = time.time()
APP_VERSION = "1.4.0"


def build_stamp():
    """Version + git commit + this file's timestamp, so the header can PROVE
    which build is actually running (a git pull does nothing until the server
    is restarted — this makes that obvious instead of guesswork)."""
    commit = ""
    try:
        head = os.path.join(ROOT, ".git", "HEAD")
        ref = open(head, encoding="utf-8").read().strip()
        if ref.startswith("ref: "):
            rp = os.path.join(ROOT, ".git", ref[5:])
            commit = open(rp, encoding="utf-8").read().strip()[:7] \
                if os.path.exists(rp) else ""
        else:
            commit = ref[:7]
    except OSError:
        commit = ""
    try:
        mt = os.path.getmtime(os.path.abspath(__file__))
        built = time.strftime("%Y-%m-%d %H:%M", time.localtime(mt))
    except OSError:
        built = "?"
    return {"version": APP_VERSION, "commit": commit, "built": built,
            "started": time.strftime("%H:%M", time.localtime(_STARTED))}


LAST_JOB = {}


def run_job(name, fn, *args, **kw):
    """Run a pipeline step on the worker thread, teeing prints into the log.
    The outcome is recorded in LAST_JOB so the UI can SHOW a failure instead of
    silently dropping back to idle."""
    if _busy.is_set():
        return False
    def work():
        _busy.set()
        LAST_JOB.clear()
        LAST_JOB.update({"name": name, "state": "running", "error": ""})
        log("=== {} started ===".format(name))
        try:
            with redirect_stdout(_Tee()):
                fn(*args, **kw)
            log("=== {} finished ===".format(name))
            LAST_JOB.update({"state": "ok", "error": ""})
        except SystemExit as e:
            log("=== {} exited: {} ===".format(name, e))
            LAST_JOB.update({"state": "ok", "error": ""})
        except Exception as e:  # noqa: BLE001 - reported to the owner, not raised
            for line in traceback.format_exc().splitlines():
                log(line)
            log("=== {} FAILED ===".format(name))
            LAST_JOB.update({"state": "failed", "error": str(e)[:400]})
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
    seed_offset = 0
    if p.get("reroll"):
        import time as _t
        seed_offset = int(_t.time()) % 900000    # fresh seeds, still resumable
    param_overrides = {k: p[k] for k in runner.GEN_PARAM_KEYS if p.get(k)}
    return run_job("generate", _backend_first(
        campaign, dry, runner.run_generate, campaign,
        only=set(p["only"].split()) if p.get("only") else None,
        variants_override=int(p["variants"]) if p.get("variants") else None,
        dry_run=dry, starter=bool(p.get("starter")), seed_offset=seed_offset,
        param_overrides=param_overrides or None))


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


def act_backend_set(p):
    """Switch the campaign between the A1111 and ComfyUI backends. Krea 2 /
    FLUX-family checkpoints don't load in classic A1111, so a Comfy setup needs
    to be selectable from the app rather than hand-edited."""
    campaign = p.get("campaign", "still_hour")
    kind = (p.get("backend") or "").strip().lower()
    if kind not in ("a1111", "comfy"):
        return {"ok": False, "message": "backend must be a1111 or comfy"}
    path = os.path.join(runner.campaign_dir(campaign), "campaign.json")
    camp = json.load(open(path, encoding="utf-8"))
    camp["backend"] = kind
    with open(path, "w", encoding="utf-8") as f:
        json.dump(camp, f, indent=2)
    log("backend -> " + kind)
    return {"ok": True, "backend": kind}


def act_models(p):
    """List checkpoints installed on the campaign's backend (model picker)."""
    camp = runner.load_campaign(p.get("campaign", "still_hour"))
    backend = runner.make_backend(camp, dry_run=bool(p.get("dry_run")))
    try:
        models = backend.list_models()
        active = backend.current_model() if hasattr(backend, "current_model") else None
    except Exception as e:  # noqa: BLE001 - backend down is a normal state
        return {"ok": False, "models": [], "current": camp.get("checkpoint"),
                "active": None,
                "message": "couldn't list models — is the backend running? ({})".format(e)}
    return {"ok": True, "models": models, "active": active,
            "current": camp.get("checkpoint")}


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


def act_prompt_get(p):
    """The exact prompt a card would generate with: composed from character +
    scene + type framing + house style, plus any saved override."""
    campaign = p.get("campaign", "still_hour")
    card = p["card"]
    from cardforge.compose import compose, is_text_only
    from cardforge.resolver import CharacterResolver
    camp = runner.load_campaign(campaign)
    job = next((j for j in runner.load_manifest(campaign) if j["id"] == card), None)
    if job is None or is_text_only(job):
        return {"ok": False, "message": "no illustrated face for " + card}
    character = None
    if job.get("character"):
        character = CharacterResolver(os.path.join(
            runner.campaign_dir(campaign), "characters.json")).resolve(job["character"])
    positive, negative, params = compose(job, camp, runner.load_profiles(), character)
    ov = runner.load_prompt_overrides(campaign).get(card) or {}
    return {"ok": True, "positive": positive, "negative": negative,
            "override": ov, "seed": params["seed"],
            "checkpoint": params["checkpoint"]}


def act_prompt_save(p):
    """Save (or clear, when both boxes match the composed default/empty) a
    per-card prompt override. Batch runs honor it too."""
    entry = runner.save_prompt_override(
        p.get("campaign", "still_hour"), p["card"],
        p.get("positive", ""), p.get("negative", ""))
    log("prompt override {} for {}".format("saved" if entry else "cleared", p["card"]))
    return {"ok": True, "override": entry}


def act_gen_settings(p):
    """Campaign-wide generation defaults (Advanced tab) — steps/cfg/sampler
    applied to every art type via campaign.json 'overrides_all'."""
    campaign = p.get("campaign", "still_hour")
    path = os.path.join(runner.campaign_dir(campaign), "campaign.json")
    camp = json.load(open(path, encoding="utf-8"))
    ov = camp.get("overrides_all", {})
    for k, cast in (("steps", int), ("cfg", float), ("sampler", str)):
        v = p.get(k)
        if v in (None, ""):
            ov.pop(k, None)
        else:
            ov[k] = cast(v)
    if ov:
        camp["overrides_all"] = ov
    else:
        camp.pop("overrides_all", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(camp, f, indent=2)
    log("generation defaults: {}".format(ov or "profile defaults"))
    return {"ok": True, "overrides_all": ov}


def act_lora_save(p):
    """Per-character LoRA name / strength / trigger (Advanced tab) into
    characters.json — refs and descriptions are preserved."""
    campaign = p.get("campaign", "still_hour")
    path = os.path.join(runner.campaign_dir(campaign), "characters.json")
    chars = json.load(open(path, encoding="utf-8"))
    for name, entry in (p.get("characters") or {}).items():
        cur = chars.setdefault(name, {})
        for k in ("lora", "trigger"):
            if k in entry:
                v = (entry[k] or "").strip()
                if v:
                    cur[k] = v
                else:
                    cur.pop(k, None)
        if "weight" in entry and entry["weight"] not in (None, ""):
            cur["weight"] = max(0.0, min(2.0, float(entry["weight"])))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chars, f, indent=2)
    log("LoRA settings saved for {} character(s)".format(len(p.get("characters") or {})))
    return {"ok": True}


def act_style_save(p):
    """Edit the campaign house style (the ART_SPEC block every batch prompt
    ends with) from the app."""
    campaign = p.get("campaign", "still_hour")
    path = os.path.join(runner.campaign_dir(campaign), "campaign.json")
    camp = json.load(open(path, encoding="utf-8"))
    for k in ("style_positive", "style_negative", "style_lora",
              "style_lora_weight", "style_trigger"):
        if p.get(k) is None:
            continue
        v = p[k]
        if k == "style_lora_weight":          # numeric, not text
            try:
                camp[k] = max(0.0, min(2.0, float(v)))
            except (TypeError, ValueError):
                camp[k] = 0.8
        else:
            camp[k] = str(v).strip()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(camp, f, indent=2)
    log("house style updated")
    return {"ok": True}


def act_inpaint_frames(p):
    """Rebuild the blank frames: SD-inpaint the text regions of each template
    into empty card material (the owner's select-and-generate-over idea)."""
    from cardforge import inpaint
    return run_job("inpaint-blank-frames", inpaint.rebuild_blank_frames,
                   p.get("campaign", "still_hour"),
                   dry_run=bool(p.get("dry_run")))


def campaign_of(card, default="still_hour"):
    """Which campaign actually owns this card id.

    An edit has to be written into its own campaign's folder, because that is
    the folder the compiler reads. Trusting the client's idea of the current
    campaign would silently strand the edit if the two ever disagreed."""
    if card in {c.get("id") for path in spec_files(default)
                if os.path.exists(path)
                for c in _load_json_list(path)}:
        return default
    camp_root = os.path.join(ROOT, "campaigns")
    for name in sorted(os.listdir(camp_root)) if os.path.isdir(camp_root) else []:
        if name == default or not os.path.isdir(os.path.join(camp_root, name)):
            continue
        for path in spec_files(name):
            if os.path.exists(path) and any(
                    c.get("id") == card for c in _load_json_list(path)):
                return name
    return default


def _load_json_list(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (ValueError, OSError):
        return []


def act_card_save(p):
    """Persist owner content edits (name/text/stats/pips) for one card into
    that campaign's own campaigns/<id>/card_overrides.json, then recompose its
    face. Empty string clears a field back to the authored value."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    card = os.path.basename(str(p.get("card", "")).strip())
    if not card:
        return {"ok": False, "message": "no card given"}
    campaign = campaign_of(card, campaign)

    def clean(k, v):
        """Type each field to what the renderer expects, so no editor input can
        crash the recompose: pips are bounded ints, stat plates are ints or a
        short token like 'X', text is length-capped."""
        if v in ("", None):
            return None                             # clears the field
        if k in rp.OV_PIP_KEYS:
            s = str(v).strip()
            if not s.lstrip("-").isdigit():
                return None                         # junk -> clear to authored
            return rp.pip_count(s)                  # else 0..MAX_PIPS int
        if k in rp.OV_NUMERIC_KEYS:
            s = str(v).strip()
            if s.lstrip("-").isdigit():
                return int(s)
            return s[:3] if s else None             # allow "X"/"—", never junk
        return str(v)[:1200]                        # text: cap, never int-cast

    def clean_connections(v):
        """A connection list -> [{symbol, color}], each a short string; caps at
        6 (the frame's Connection1..6). Junk entries are dropped, never crash."""
        out = []
        if isinstance(v, list):
            for it in v[:6]:
                if isinstance(it, dict):
                    sym = str(it.get("symbol", "")).strip()[:16]
                    col = str(it.get("color", "")).strip()[:16]
                else:
                    sym, col = str(it).strip()[:16], ""
                if sym:
                    out.append({"symbol": sym, "color": col} if col
                               else {"symbol": sym})
        return out

    with _state_lock:
        ov = rp.load_card_overrides(campaign)
        entry = dict(ov.get(card, {}))
        for k in rp.OV_SPEC_KEYS + rp.OV_PT_KEYS:
            if k not in p:
                continue
            cv = clean(k, p[k])
            if cv is None:
                entry.pop(k, None)
            else:
                entry[k] = cv
        # location element swaps: own symbol, colour, per-investigator, links
        if "icons" in p:
            iv = str(p["icons"]).strip()[:16]
            if iv:
                entry["icons"] = iv
            else:
                entry.pop("icons", None)
        if "color" in p:
            cv = str(p["color"]).strip()[:16]
            if cv:
                entry["color"] = cv
            else:
                entry.pop("color", None)
        if "clues_per_investigator" in p:
            entry["clues_per_investigator"] = bool(p["clues_per_investigator"])
        # the rest of what an official card carries — class, elite/unique marks,
        # act & agenda numbering, encounter set, quantity, uses… so nothing on
        # a real card needs a JSON edit to reproduce
        for k in rp.OV_FLAG_KEYS:
            if k in p and k != "clues_per_investigator":
                entry[k] = bool(p[k])
                if not entry[k]:
                    entry.pop(k)      # false is the authored default
        for k in rp.OV_COUNT_KEYS:
            if k in p:
                s = str(p[k]).strip()
                if s.lstrip("-").isdigit():
                    entry[k] = int(s)
                else:
                    entry.pop(k, None)
        for k in rp.OV_PROP_KEYS:
            if k == "signatures" or k not in p:
                continue
            s = str(p[k]).strip()[:200]
            if s:
                entry[k] = s
            else:
                entry.pop(k, None)
        # signatures are structured (card id -> how many copies), so they get a
        # row editor rather than a text box that would print "[object Object]"
        if "signatures" in p:
            sig = {}
            src = p["signatures"]
            if isinstance(src, list):
                for it in src[:12]:
                    if isinstance(it, dict):
                        for cid, n in it.items():
                            sig[os.path.basename(str(cid))[:64]] = \
                                max(1, min(9, int(n or 1)))
            elif isinstance(src, dict):
                for cid, n in list(src.items())[:12]:
                    sig[os.path.basename(str(cid))[:64]] = \
                        max(1, min(9, int(n or 1)))
            if sig:
                entry["signatures"] = [sig]
            else:
                entry.pop("signatures", None)
        if "connections" in p:
            conns = clean_connections(p["connections"])
            if conns:
                entry["connections"] = conns
            else:
                entry.pop("connections", None)
        if "tokens" in p:
            toks = []
            if isinstance(p["tokens"], list):
                for t in p["tokens"][:8]:
                    if isinstance(t, dict):
                        tok = str(t.get("token", "")).strip().lower()[:16]
                        txt = str(t.get("text", ""))[:400]
                        if tok or txt:
                            toks.append({"token": tok, "text": txt})
            if toks:
                entry["tokens"] = toks
            else:
                entry.pop("tokens", None)
        if entry:
            ov[card] = entry
        else:
            ov.pop(card, None)
        # Changing a location's own identifier changes what its neighbours have
        # to print, so their rows are rebuilt from the connection graph too.
        also = _resync_neighbours(campaign, card, ov) if "icons" in p else []
        _write_json_atomic(rp.overrides_path(campaign), ov)
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                        "--only", card] + also, check=True, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
    log("card content saved: {} ({} field(s) overridden{})".format(
        card, len(entry),
        ", {} neighbour(s) resynced".format(len(also)) if also else ""))
    return {"ok": True, "overrides": entry, "resynced": also}


def _resync_neighbours(campaign, card, ov):
    """After a location's own symbol changes, rewrite the connection rows of
    every location it is joined to, in every scenario it appears in."""
    import render_placeholders as rp
    apath = os.path.join(ROOT, "campaigns", campaign,
                         "scenario_assignments.json")
    if not os.path.exists(apath):
        return []
    try:
        board = json.load(open(apath, encoding="utf-8"))
    except ValueError:
        return []
    spec_by_id = {}
    for path in spec_files(campaign):
        try:
            for sc in json.load(open(path, encoding="utf-8")):
                spec_by_id[sc["id"]] = sc
        except (ValueError, OSError):
            continue
    if spec_by_id.get(card, {}).get("type") != "Location":
        return []
    ident = {cid: _loc_identity(cid, spec_by_id, ov) for cid in spec_by_id
             if spec_by_id[cid].get("type") == "Location"}
    touched = []
    for sid, box in board.items():
        locs = box.get("locations")
        if not isinstance(locs, list) or card not in locs:
            continue
        printed = {}
        for cid in locs:
            mc, _ = rp.apply_card_overrides(spec_by_id.get(cid, {}), {},
                                            ov.get(cid))
            printed[cid] = [str(c.get("symbol") if isinstance(c, dict) else c
                                ).strip().lower()
                            for c in (mc.get("connections") or [])]
        links = scenario_links(board, sid, locs, ident, printed)
        for cid in rebuild_connections(campaign, locs, links, ident,
                                       spec_by_id, ov):
            if cid != card and cid not in touched:
                touched.append(cid)
    return touched




SCENARIO_STACKS = ("locations", "act_deck", "agenda_deck", "encounter",
                   "named", "reference", "setup_aside")
ASSIGNMENTS_PATH = os.path.join(ROOT, "campaigns", "still_hour",
                                "scenario_assignments.json")
IMPORTED_SPEC_PATH = os.path.join(ROOT, "pipeline",
                                  "stillhour_imported_spec.json")


def load_assignments():
    if os.path.exists(ASSIGNMENTS_PATH):
        try:
            return json.load(open(ASSIGNMENTS_PATH, encoding="utf-8"))
        except ValueError:
            return {}
    return {}




def act_scenario_new(p):
    """Add a scenario box to a campaign. A campaign built from scratch starts
    with no scenarios, so this is how the board gets its boxes."""
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    name = str(p.get("name") or "").strip()[:60]
    if not name:
        return {"ok": False, "message": "name the scenario"}
    if not os.path.isdir(os.path.join(ROOT, "campaigns", campaign)):
        return {"ok": False, "message": "no campaign called '{}'".format(campaign)}
    # A campaign made before scenarios existed has no manifest yet. It is still
    # a real campaign — seed one rather than refusing, or a campaign in the
    # picker can never take its first scenario box.
    mpath = os.path.join(ROOT, "campaigns", campaign, "scenario_manifest.json")
    with _state_lock:
        try:
            m = json.load(open(mpath, encoding="utf-8"))
        except (OSError, ValueError):
            m = {"scenarios": []}
        scen = m.setdefault("scenarios", [])
        slug = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
        slug = "_".join(x for x in slug.split("_") if x)[:40] or "scenario"
        taken = {s.get("id") for s in scen}
        sid, n = slug, 2
        while sid in taken:
            sid, n = "{}_{}".format(slug, n), n + 1
        scen.append({"id": sid, "name": name,
                     "order": max([s.get("order", 0) for s in scen] or [-1]) + 1,
                     "stacks": {}})
        _write_json_atomic(mpath, m)
    log("scenario added: {} ({})".format(name, sid))
    return {"ok": True, "id": sid, "name": name}


def act_scenario_delete(p):
    """Remove a scenario box and its board assignments."""
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    sid = str(p.get("scenario") or "").strip()
    mpath = os.path.join(ROOT, "campaigns", campaign, "scenario_manifest.json")
    apath = os.path.join(ROOT, "campaigns", campaign, "scenario_assignments.json")
    if not os.path.exists(mpath):
        return {"ok": False, "message": "this campaign has no scenarios yet"}
    with _state_lock:
        m = json.load(open(mpath, encoding="utf-8"))
        before = len(m.get("scenarios", []))
        m["scenarios"] = [s for s in m.get("scenarios", []) if s.get("id") != sid]
        if len(m["scenarios"]) == before:
            return {"ok": False, "message": "no scenario called '{}'".format(sid)}
        _write_json_atomic(mpath, m)
        if os.path.exists(apath):
            try:
                a = json.load(open(apath, encoding="utf-8"))
                a.pop(sid, None)
                _write_json_atomic(apath, a)
            except ValueError:
                pass
    log("scenario removed: " + sid)
    return {"ok": True, "id": sid}


def act_scenario_rename(p):
    """Rename a scenario box."""
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    sid = str(p.get("scenario") or "").strip()
    name = str(p.get("name") or "").strip()[:60]
    mpath = os.path.join(ROOT, "campaigns", campaign, "scenario_manifest.json")
    if not name or not os.path.exists(mpath):
        return {"ok": False, "message": "need a scenario and a new name"}
    with _state_lock:
        m = json.load(open(mpath, encoding="utf-8"))
        hit = False
        for sc in m.get("scenarios", []):
            if sc.get("id") == sid:
                sc["name"] = name
                hit = True
        if not hit:
            return {"ok": False, "message": "no scenario called '{}'".format(sid)}
        _write_json_atomic(mpath, m)
    return {"ok": True, "id": sid, "name": name}





# The TTS location map: the black bordered slot grid you see when a scenario is
# laid out. Columns/rows map 1:1 onto table coordinates measured from the real
# SCED box (columns 6.6 apart, rows 7.65 apart, locations rotated 270).
MAP_GRID = {"x0": -30.24, "dx": 6.60, "z0": 11.46, "dz": -7.65,
            "cols": 5, "rows": 5, "y": 1.53, "rot": 270,
            # a location card's own footprint on the table, in the same units
            "cw": 2.63, "ch": 3.68}

# The rest of the table, at the coordinates the real box uses. These are not
# slots you can drop a location on — they are what the map has to fit around,
# and the reason the grid stops at four columns: a fifth would land on the
# encounter deck at x -3.85.
MAP_FURNITURE = [
    {"key": "encounter", "label": "Encounter deck", "x": -3.85, "z": 5.72,
     "rot": 270},
    {"key": "agenda_deck", "label": "Agenda", "x": -2.94, "z": 0.36,
     "rot": 180},
    {"key": "act_deck", "label": "Act", "x": -1.79, "z": -5.02, "rot": 0},
    {"key": "named", "label": "Named / story", "x": -3.85, "z": -10.39,
     "rot": 270},
    {"key": "reference", "label": "Scenario reference", "x": -12.22,
     "z": -8.90, "rot": 90},
    {"key": "setup_aside", "label": "Set-aside", "x": 1.69, "z": 14.24,
     "rot": 225},
]


def has_face(cid):
    """Is this card's face actually composed? A render killed part-way leaves a
    zero-byte PNG, which every plain exists() check happily counted as done."""
    path = os.path.join(ROOT, "art", "faces", str(cid) + ".png")
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def rp_keys():
    """Every card field the editor can set by hand — the one list the card
    editor, the campaign feed and the by-hand rebuild all agree on."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    return (rp.OV_SPEC_KEYS + rp.OV_PT_KEYS + rp.OV_LOC_KEYS
            + rp.OV_FLAG_KEYS + rp.OV_COUNT_KEYS + rp.OV_PROP_KEYS
            + ("tokens",))


def map_xz(col, row):
    """Table position of a grid slot."""
    return (round(MAP_GRID["x0"] + col * MAP_GRID["dx"], 3),
            round(MAP_GRID["z0"] + row * MAP_GRID["dz"], 3))


def act_map_save(p):
    """Save where each location card sits on a scenario's map grid.

    Body: {campaign, scenario, slots: {card_id: [col, row]}}. Stored beside the
    board so the compiler can script exactly the layout you arranged.
    """
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    sid = str(p.get("scenario") or "").strip()
    slots = p.get("slots")
    if not sid or not isinstance(slots, dict):
        return {"ok": False, "message": "need a scenario and slots"}
    clean = {}
    for cid, rc in slots.items():
        if (isinstance(rc, (list, tuple)) and len(rc) == 2
                and all(isinstance(v, int) for v in rc)):
            col = max(0, min(MAP_GRID["cols"] - 1, rc[0]))
            row = max(0, min(MAP_GRID["rows"] - 1, rc[1]))
            clean[os.path.basename(str(cid))[:64]] = [col, row]
    apath = os.path.join(ROOT, "campaigns", campaign,
                         "scenario_assignments.json")
    with _state_lock:
        board = {}
        if os.path.exists(apath):
            try:
                board = json.load(open(apath, encoding="utf-8"))
            except ValueError:
                board = {}
        box = board.setdefault(sid, {})
        if clean:
            box["_map"] = clean
        else:
            box.pop("_map", None)
        _write_json_atomic(apath, board)
    log("map saved: {} ({} placed)".format(sid, len(clean)))
    return {"ok": True, "scenario": sid, "slots": clean,
            "grid": dict(MAP_GRID)}



# Auto-assigned identity for a location that has no symbol yet. Arkham gives
# every location on a map its own symbol+colour so the connection icons printed
# on its neighbours read at a glance; these are the plugin's own symbols in the
# order the official maps tend to use them.
CONN_POOL = [("circle", "red"), ("square", "blue"), ("triangle", "green"),
             ("diamond", "purple"), ("moon", "teal"), ("star", "gold"),
             ("heart", "pink"), ("hourglass", "orange"), ("cross", "brown"),
             ("quote", "grey"), ("slash", "yellow"), ("doubleslash", "red"),
             ("spade", "blue"), ("clover", "green"), ("t", "purple")]


def _loc_identity(cid, spec_by_id, ov):
    """A location's own (symbol, colour) as it renders today."""
    import render_placeholders as rp
    mc, _ = rp.apply_card_overrides(spec_by_id.get(cid, {}), {}, ov.get(cid))
    return (str(mc.get("icons") or "").strip().lower(),
            str(mc.get("color") or "").strip())


def _norm_edge(a, b):
    return tuple(sorted((a, b)))


def scenario_links(board, sid, locs=None, ident=None, conns=None):
    """The scenario's connections as a plain edge list.

    The edge list is the truth; the symbols printed along a card's bottom edge
    are derived from it. A campaign authored before this existed has no list,
    so the first read reconstructs one from what the cards currently print.
    """
    box = board.get(sid) or {}
    raw = box.get("_links")
    if isinstance(raw, list):
        seen, out = set(), []
        for e in raw:
            if isinstance(e, (list, tuple)) and len(e) == 2:
                a = os.path.basename(str(e[0]))[:64]
                b = os.path.basename(str(e[1]))[:64]
                if a and b and a != b and _norm_edge(a, b) not in seen:
                    seen.add(_norm_edge(a, b))
                    out.append([a, b])
        return out
    if not locs or ident is None or conns is None:
        return []
    by_sym = {}
    for cid in locs:
        sym = (ident.get(cid) or ("", ""))[0]
        if sym:
            by_sym.setdefault(sym, []).append(cid)
    seen, out = set(), []
    for cid in locs:
        for sym in conns.get(cid) or []:
            for other in by_sym.get(sym, []):
                if other == cid or _norm_edge(cid, other) in seen:
                    continue
                seen.add(_norm_edge(cid, other))
                out.append([cid, other])
    return out


def rebuild_connections(campaign, locs, links, ident, spec_by_id, ov):
    """Rewrite every location's printed connection row from the edge list.

    This is the whole point of keeping a graph: a card's bottom row is exactly
    the symbols of the locations it is joined to, recomputed from scratch every
    time, so moving a connector from one location to another moves the symbol
    with it. A card can never print its OWN symbol down there, because a card
    is never its own neighbour.
    """
    import render_placeholders as rp
    nb = {cid: [] for cid in locs}
    for a, b in links:
        if a in nb and b in nb:
            nb[a].append(b)
            nb[b].append(a)
    touched = []
    for cid in locs:
        own = (ident.get(cid) or ("", ""))[0]
        want = []
        for other in nb.get(cid, []):
            sym, col = ident.get(other) or ("", "")
            if not sym or sym == own:      # never its own symbol, ever
                continue
            if any(c["symbol"] == sym for c in want):
                continue
            want.append({"symbol": sym, "color": col} if col
                        else {"symbol": sym})
        want = want[:6]                    # the frame carries Connection1..6
        base, _ = rp.apply_card_overrides(spec_by_id.get(cid, {}), {},
                                          ov.get(cid))
        have = [{"symbol": str(c.get("symbol") if isinstance(c, dict) else c
                               ).lower(),
                 "color": str((c.get("color") if isinstance(c, dict) else "")
                              or "")}
                for c in (base.get("connections") or [])]
        if have == [{"symbol": c["symbol"], "color": c.get("color", "")}
                    for c in want]:
            continue                       # already right, no re-render
        entry = dict(ov.get(cid, {}))
        if want:
            entry["connections"] = want
        else:
            entry.pop("connections", None)
        if entry:
            ov[cid] = entry
        else:
            ov.pop(cid, None)
        touched.append(cid)
    return touched


def act_map_connect(p):
    """Join, separate, or MOVE a connection between locations.

    Body: {campaign, scenario, a, b}            join a and b
          {campaign, scenario, a, b, remove}    separate them
          {campaign, scenario, a, b, move_from} detach a's connector from
                                                move_from and attach it to b

    The scenario keeps an edge list and every affected card's printed symbols
    are rebuilt from it, so a connector that moves takes its symbol with it —
    off the location it left, onto the one it landed on.
    """
    import render_placeholders as rp
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    a = os.path.basename(str(p.get("a") or ""))[:64]
    b = os.path.basename(str(p.get("b") or ""))[:64]
    remove = bool(p.get("remove"))
    move_from = os.path.basename(str(p.get("move_from") or ""))[:64]
    if not a or not b or a == b:
        return {"ok": False, "message": "pick two different locations"}

    spec_by_id = {}
    for path in spec_files(campaign):
        try:
            for sc in json.load(open(path, encoding="utf-8")):
                spec_by_id[sc["id"]] = sc
        except (ValueError, OSError):
            continue
    for x in (a, b) + ((move_from,) if move_from else ()):
        if x not in spec_by_id:
            return {"ok": False, "message": "unknown location"}
        if spec_by_id[x].get("type") != "Location":
            return {"ok": False, "message": "connections join two locations"}

    sid = str(p.get("scenario") or "").strip()
    apath = os.path.join(ROOT, "campaigns", campaign,
                         "scenario_assignments.json")

    with _state_lock:
        board = {}
        if os.path.exists(apath):
            try:
                board = json.load(open(apath, encoding="utf-8"))
            except ValueError:
                board = {}
        here = (board.get(sid) or {}).get("locations")
        locs = list(here) if isinstance(here, list) and here else []
        for x in (a, b, move_from):
            if x and x not in locs:
                locs.append(x)

        ov = rp.load_card_overrides(campaign)
        ident = {cid: _loc_identity(cid, spec_by_id, ov) for cid in spec_by_id
                 if spec_by_id[cid].get("type") == "Location"}
        printed = {}
        for cid in locs:
            mc, _ = rp.apply_card_overrides(spec_by_id.get(cid, {}), {},
                                            ov.get(cid))
            printed[cid] = [str(c.get("symbol") if isinstance(c, dict) else c
                                ).strip().lower()
                            for c in (mc.get("connections") or [])]
        links = scenario_links(board, sid, locs, ident, printed)

        # a symbol only has to be unique on one map, as in the printed game
        taken = {ident[cid][0] for cid in locs
                 if cid in ident and ident[cid][0]}

        def identity(cid):
            """This location's own symbol, minting one if it has none yet.
            Its identifier never changes once set — only the row below does."""
            sym, col = ident.get(cid) or ("", "")
            if sym:
                return sym, col
            for s, c in CONN_POOL:
                if s not in taken:
                    sym, col = s, c
                    break
            else:                                   # >15 locations: reuse
                sym, col = CONN_POOL[len(taken) % len(CONN_POOL)]
            taken.add(sym)
            ident[cid] = (sym, col)
            entry = dict(ov.get(cid, {}))
            entry["icons"] = sym
            entry.setdefault("color", col)
            ov[cid] = entry
            return sym, col

        def drop(x, y):
            key = _norm_edge(x, y)
            return [e for e in links if _norm_edge(e[0], e[1]) != key]

        if move_from:
            if _norm_edge(a, move_from) not in {_norm_edge(*e) for e in links}:
                return {"ok": False,
                        "message": "those two are not connected"}
            links = drop(a, move_from)
            if _norm_edge(a, b) not in {_norm_edge(*e) for e in links}:
                identity(a)
                identity(b)
                links.append([a, b])
        elif remove:
            links = drop(a, b)
        else:
            identity(a)
            identity(b)
            if _norm_edge(a, b) not in {_norm_edge(*e) for e in links}:
                links.append([a, b])

        touched = rebuild_connections(campaign, locs, links, ident,
                                      spec_by_id, ov)
        _write_json_atomic(rp.overrides_path(campaign), ov)
        if sid:
            board.setdefault(sid, {})["_links"] = links
            _write_json_atomic(apath, board)
        if touched:
            subprocess.run([sys.executable,
                            os.path.join(ROOT, "pipeline",
                                         "render_placeholders.py"),
                            "--only"] + touched,
                           check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    log("{} {} <-> {} ({} card(s) re-rendered)".format(
        "moved" if move_from else ("unlinked" if remove else "linked"),
        a, b, len(touched)))
    return {"ok": True, "a": a, "b": b, "removed": remove,
            "moved_from": move_from or None, "links": links,
            "rerendered": touched,
            "symbols": {cid: ident[cid][0] for cid in locs if cid in ident}}


def act_scenario_save(p):
    """Persist the deck-builder board: which card ids sit in which stack of
    which scenario. Body: {assignments: {scenario_id: {stack: [ids]}}} replaces
    the whole board (the UI always sends its full state)."""
    a = p.get("assignments")
    if not isinstance(a, dict):
        return {"ok": False, "message": "assignments must be an object"}
    clean = {}
    for sid, stacks in a.items():
        if not isinstance(stacks, dict):
            continue
        cs = {}
        for st, ids in stacks.items():
            if st in SCENARIO_STACKS and isinstance(ids, list):
                cs[st] = [os.path.basename(str(i))[:64] for i in ids][:60]
        if stacks.get("_locked"):
            cs["_locked"] = True
        if isinstance(stacks.get("_map"), dict):
            cs["_map"] = stacks["_map"]
        if isinstance(stacks.get("_links"), list):
            cs["_links"] = stacks["_links"]
        if cs:
            clean[str(sid)[:64]] = cs
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    apath = os.path.join(ROOT, "campaigns", campaign,
                         "scenario_assignments.json")
    with _state_lock:
        # The board UI only knows about stacks, so it sends stacks. The map
        # layout and the connection graph belong to the same scenario and must
        # survive a card being dragged between stacks — carry them over unless
        # the caller is deliberately replacing them.
        old = {}
        if os.path.exists(apath):
            try:
                old = json.load(open(apath, encoding="utf-8"))
            except ValueError:
                old = {}
        for sid, cs in clean.items():
            prev = old.get(sid) or {}
            for keep in ("_map", "_links"):
                if keep not in cs and keep in prev:
                    cs[keep] = prev[keep]
        _write_json_atomic(apath, clean)
    log("scenario board saved ({} scenario(s))".format(len(clean)))
    return {"ok": True, "assignments": clean}






CARD_TYPES = ("Investigator", "Asset", "Event", "Skill", "Treachery", "Enemy",
              "Location", "Agenda", "Act", "Scenario", "Story", "CampaignLog")
CARD_CLASSES = ("Guardian", "Seeker", "Rogue", "Mystic", "Survivor", "Neutral",
                "Mythos")

# Recommended shape of a fresh scenario, measured off The Still Hour's prologue
# (its biggest box) so a seeded campaign starts life looking like the real one:
# (stack, card type, count). Two encounter rows because a real encounter deck is
# a mix of Treachery and Enemy (9 + 4 = 13). Everything is a blank placeholder
# on its true template — rename or delete to taste; nothing here is locked in.
RECOMMENDED_SEED = (
    ("locations",   "Location",  4),
    ("act_deck",    "Act",       2),
    ("agenda_deck", "Agenda",    9),
    ("encounter",   "Treachery", 9),
    ("encounter",   "Enemy",     4),
    ("reference",   "Story",     1),
)


def _blank_card_spec(cid, ctype, name, cls=""):
    """The blank-card spec used both by the hand editor and the campaign seeder:
    a card on its real template with sensible per-type starting stats."""
    card = {"id": cid, "type": ctype, "name": name}
    if cls:
        card["class"] = cls
    if ctype in ("Enemy", "Treachery", "Location", "Agenda", "Act",
                 "Scenario", "Story"):
        card.setdefault("class", cls or "Mythos")
        card["encounter"] = True
    if ctype == "Location":
        card.update({"shroud": 2, "clues": 1, "clues_per_investigator": True})
    if ctype == "Enemy":
        card.update({"fight": 2, "health": 2, "evade": 2,
                     "damage": 1, "horror": 0})
    if ctype == "Investigator":
        # every new investigator starts at 1 everywhere — click the value up
        # from there rather than editing someone else's defaults
        card.update({"wil": 1, "int": 1, "com": 1, "agi": 1,
                     "health": 1, "sanity": 1, "class": cls or "Neutral"})
    if ctype in ("Asset", "Event", "Skill"):
        card.setdefault("class", cls or "Neutral")
    return card


def _seed_campaign(cid, name):
    """Give a brand-new campaign one starter scenario populated with blank
    placeholder cards at the recommended per-scenario counts, so the owner opens
    it to a board that already reads like a real scenario instead of a blank
    slate. Returns the list of created card ids (for a single render pass)."""
    prefix = "".join(w[0] for w in cid.split("_") if w)[:4] or "card"
    counters, created, assign = {}, [], {}
    spec = []
    for stack, ctype, count in RECOMMENDED_SEED:
        for _ in range(count):
            counters[ctype] = counters.get(ctype, 0) + 1
            n = counters[ctype]
            cname = "{} {}".format(ctype, n)
            ccid = "{}-{}-{}".format(prefix, ctype.lower(), n)
            spec.append(_blank_card_spec(ccid, ctype, cname))
            assign.setdefault(stack, []).append(ccid)
            created.append(ccid)
    dest = os.path.join(ROOT, "campaigns", cid)
    _write_json_atomic(own_spec_path(cid), spec)
    sid = "scenario_1"
    _write_json_atomic(os.path.join(dest, "scenario_manifest.json"),
                       {"campaign": {"id": cid, "name": name},
                        "scenarios": [{"id": sid, "name": "Scenario 1",
                                       "order": 0, "stacks": {}}]})
    _write_json_atomic(os.path.join(dest, "scenario_assignments.json"),
                       {sid: assign})
    return created


def act_card_new(p):
    """Create a blank card on its real template — the core of building a
    campaign by hand. No AI, no backend: pick a type and a name and the card
    exists immediately, ready to edit and to drag onto a scenario."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    ctype = str(p.get("type") or "").strip()
    name = str(p.get("name") or "").strip()[:80]
    if ctype not in CARD_TYPES:
        return {"ok": False, "message": "pick a card type"}
    if not name:
        return {"ok": False, "message": "give the card a name"}
    cls = str(p.get("class") or "").strip()
    if cls and cls not in CARD_CLASSES:
        cls = ""
    prefix = "".join(w[0] for w in campaign.split("_") if w)[:4] or "card"
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    slug = "-".join(x for x in slug.split("-") if x)[:32] or "card"
    base = "{}-{}".format(prefix, slug)

    path = own_spec_path(campaign)
    with _state_lock:
        cards = []
        if os.path.exists(path):
            try:
                cards = json.load(open(path, encoding="utf-8"))
            except ValueError:
                cards = []
        taken = set()
        for fp in spec_files(campaign):
            if os.path.exists(fp):
                try:
                    taken |= {c.get("id") for c in
                              json.load(open(fp, encoding="utf-8"))}
                except ValueError:
                    pass
        cid, n = base, 2
        while cid in taken:
            cid, n = "{}-{}".format(base, n), n + 1

        card = _blank_card_spec(cid, ctype, name, cls)
        cards.append(card)
        _write_json_atomic(path, cards)
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                        "--only", cid],
                       check=False, cwd=ROOT, stdout=subprocess.DEVNULL)
    log("card created: {} ({} {})".format(name, ctype, cid))
    return {"ok": True, "id": cid, "type": ctype, "name": name}


def act_card_delete(p):
    """Remove a hand-made card from this campaign's own spec."""
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    cid = os.path.basename(str(p.get("card") or ""))
    if not cid:
        return {"ok": False, "message": "no card given"}
    removed = False
    with _state_lock:
        for path in (own_spec_path(campaign),
                     os.path.join(ROOT, "pipeline",
                                  ("stillhour_imported_spec.json"
                                   if campaign == "still_hour"
                                   else campaign + "_imported_spec.json"))):
            if not os.path.exists(path):
                continue
            try:
                cards = json.load(open(path, encoding="utf-8"))
            except ValueError:
                continue
            keep = [c for c in cards if c.get("id") != cid]
            if len(keep) != len(cards):
                _write_json_atomic(path, keep)
                removed = True
        face = os.path.join(ROOT, "art", "faces", cid + ".png")
        if removed and os.path.exists(face):
            os.remove(face)
    if not removed:
        return {"ok": False,
                "message": "that card is part of the authored campaign, not a "
                           "card you made — edit it instead of deleting"}
    log("card deleted: " + cid)
    return {"ok": True, "id": cid}



def act_campaign_new(p):
    """Create a brand-new campaign folder so a written campaign can be imported
    into its own space instead of merging into The Still Hour.

    Seeds campaign.json (inheriting the current house style + backend), an
    empty scenario manifest and the override files the editor writes to."""
    name = str(p.get("name") or "").strip()
    cid = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")
    cid = "_".join(x for x in cid.split("_") if x)[:40]
    if not cid:
        return {"ok": False, "message": "give the campaign a name"}
    dest = os.path.join(ROOT, "campaigns", cid)
    if os.path.exists(dest):
        return {"ok": False, "message": "a campaign called '{}' already exists"
                                        .format(cid)}
    src = os.path.join(ROOT, "campaigns", "still_hour", "campaign.json")
    base = {}
    if os.path.exists(src):
        try:
            base = json.load(open(src, encoding="utf-8"))
        except ValueError:
            base = {}
    os.makedirs(dest)
    camp = {
        "backend": base.get("backend", "a1111"),
        "base_url": base.get("base_url"),
        "checkpoint": base.get("checkpoint", "SET_ME.safetensors"),
        "output_dir": "out/" + cid,
        "name": name,
        # inherit the locked house style so a new campaign looks like the rest
        "style_positive": base.get("style_positive", ""),
        "style_negative": base.get("style_negative", ""),
        "style_lora": base.get("style_lora", ""),
        "style_lora_weight": base.get("style_lora_weight", 0.8),
        "style_trigger": base.get("style_trigger", ""),
    }
    _write_json_atomic(os.path.join(dest, "campaign.json"), camp)
    _write_json_atomic(os.path.join(dest, "card_overrides.json"), {})
    _write_json_atomic(os.path.join(dest, "font_overrides.json"), {})
    _write_json_atomic(os.path.join(dest, "scenario_assignments.json"), {})
    _write_json_atomic(os.path.join(dest, "characters.json"), {})
    _write_json_atomic(os.path.join(dest, "scenario_manifest.json"),
                       {"campaign": {"id": cid, "name": name},
                        "scenarios": []})
    # the art manifests the illustrate/frame steps read — empty, but present,
    # so a brand-new campaign never crashes anything that expects them
    _write_json_atomic(os.path.join(dest, "manifest.json"), [])
    _write_json_atomic(os.path.join(dest, "manifest_starter.json"), [])
    _write_json_atomic(os.path.join(dest, "prompt_overrides.json"), {})
    os.makedirs(os.path.join(ROOT, "out", cid), exist_ok=True)
    seeded = 0
    if p.get("seed"):
        ids = _seed_campaign(cid, name)
        seeded = len(ids)
        # one render pass for every seeded card, not one subprocess each
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                        "--only", *ids],
                       check=False, cwd=ROOT, stdout=subprocess.DEVNULL)
        log("seeded {} with {} placeholder card(s)".format(cid, seeded))
    log("campaign created: {} ({})".format(name, cid))
    return {"ok": True, "id": cid, "name": name, "seeded": seeded}



def act_campaign_import(p):
    """Campaign feed: pour a written campaign (JSON) into the same data the
    manual editor edits. Existing card ids become editor overrides; unknown ids
    become new cards in the imported spec; scenario assignments merge into the
    deck-builder board. Everything remains hand-editable afterwards."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    camp_dir = os.path.join(ROOT, "campaigns", campaign)
    if not os.path.isdir(camp_dir):
        return {"ok": False, "message": "no campaign called '{}'".format(campaign)}
    assignments_path = os.path.join(camp_dir, "scenario_assignments.json")
    imported_spec = os.path.join(ROOT, "pipeline",
                                 "stillhour_imported_spec.json" if campaign == "still_hour"
                                 else "{}_imported_spec.json".format(campaign))
    overrides_path = os.path.join(camp_dir, "card_overrides.json")
    data = p.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as e:
            return {"ok": False, "message": "bad JSON: {}".format(e)}
    if not isinstance(data, dict):
        return {"ok": False, "message": "campaign must be a JSON object"}
    cards = data.get("cards") or []
    known = set()
    for spec_file in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json",
                      "stillhour_scenario_spec.json", "stillhour_imported_spec.json"):
        fp = os.path.join(ROOT, "pipeline", spec_file)
        if os.path.exists(fp):
            try:
                known |= {c.get("id") for c in json.load(open(fp, encoding="utf-8"))}
            except ValueError:
                pass
    # a feed can set anything the hand editor can set — same key list, so the
    # two paths never drift apart
    OVERRIDE_FIELDS = (rp.OV_SPEC_KEYS + rp.OV_PT_KEYS + rp.OV_LOC_KEYS
                       + rp.OV_FLAG_KEYS + rp.OV_COUNT_KEYS + rp.OV_PROP_KEYS
                       + ("tokens",))
    SPEC_FIELDS = ("id", "type") + OVERRIDE_FIELDS
    created, updated, skipped = [], [], []
    with _state_lock:
        imported = []
        if os.path.exists(imported_spec):
            try:
                imported = json.load(open(imported_spec, encoding="utf-8"))
            except ValueError:
                imported = []
        ov = rp.load_card_overrides(campaign)
        for c in cards:
            if not isinstance(c, dict) or not c.get("id"):
                skipped.append(str(c)[:40])
                continue
            cid = os.path.basename(str(c["id"]))[:64]
            entry = dict(ov.get(cid, {}))
            for k in OVERRIDE_FIELDS:
                if k in c and c[k] not in (None, ""):
                    entry[k] = c[k]
            if entry:
                ov[cid] = entry
            if cid in known:
                updated.append(cid)
            else:
                spec = {k: c[k] for k in SPEC_FIELDS if k in c}
                spec["id"] = cid
                spec.setdefault("type", "Asset")
                spec.setdefault("name", cid)
                imported = [x for x in imported if x.get("id") != cid] + [spec]
                created.append(cid)
        _write_json_atomic(imported_spec, imported)
        _write_json_atomic(overrides_path, ov)
        assign = data.get("assignments") or data.get("scenarios_board")
        if isinstance(assign, dict):
            cur = {}
            if os.path.exists(assignments_path):
                try:
                    cur = json.load(open(assignments_path, encoding="utf-8"))
                except ValueError:
                    cur = {}
            for sid, stacks in assign.items():
                if isinstance(stacks, dict):
                    dst = cur.setdefault(str(sid)[:64], {})
                    for st, ids in stacks.items():
                        if st in SCENARIO_STACKS and isinstance(ids, list):
                            dst[st] = [os.path.basename(str(i))[:64]
                                       for i in ids][:60]
            _write_json_atomic(assignments_path, cur)
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    log("campaign imported: {} new, {} updated, {} skipped".format(
        len(created), len(updated), len(skipped)))
    return {"ok": True, "created": created, "updated": updated,
            "skipped": skipped}





def act_campaign_compile(p):
    """Phase 3 — compile the Scenarios board into a scripted SCED campaign box
    (CampaignBox > ScenarioBox per scenario > a deck per stack, plus the
    campaign log token and guide). Requires every scenario locked in unless
    force is set."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import compile_campaign as cc
    campaign = os.path.basename(str(p.get("campaign") or "still_hour"))
    out = os.path.join(ROOT, "dist",
                       "the_still_hour_campaign.json" if campaign == "still_hour"
                       else campaign + "_campaign.json")
    with _state_lock:
        try:
            r = cc.compile_campaign(out, require_locked=not p.get("force"),
                                    campaign=campaign)
        except Exception as e:  # noqa: BLE001 - report, never kill the thread
            return {"ok": False, "message": "compile failed: {}".format(e)}
    if r.get("ok"):
        log("campaign box compiled: {} scenario(s), {} card(s) -> {}".format(
            r["scenarios"], r["cards"], r["out"]))
    else:
        log("compile blocked: " + r.get("message", ""))
    return r



def act_art_remove(p):
    """Remove a card's chosen art: back to the bare template."""
    campaign = p.get("campaign", "still_hour")
    card = p["card"]
    camp = runner.load_campaign(campaign)
    out_dir = runner.out_dir_for(camp)
    chosen = os.path.join(out_dir, card, "chosen.txt")
    if os.path.exists(chosen):
        os.remove(chosen)
    index_path = os.path.join(out_dir, "index.json")
    if os.path.exists(index_path):
        index = json.load(open(index_path, encoding="utf-8"))
        if card in index:
            del index[card]
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--only", card], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    log("art removed from " + card)
    return {"ok": True}


def act_tts_spawn(p):
    """Drop a finished card onto the RUNNING Tabletop Simulator table
    (External Editor API, localhost:39999 — any TTS game, any SCED version)."""
    from cardforge import tts_link
    try:
        name = tts_link.spawn_card(p["card"], p.get("campaign", "still_hour"))
    except OSError as e:
        return {"ok": False,
                "message": "TTS not reachable ({}) — is Tabletop Simulator "
                           "open with a game loaded?".format(e)}
    log("dropped into TTS: " + name)
    return {"ok": True, "message": name + " dropped onto the TTS table"}


def act_plugin_update(p):
    """Re-extract frames/regions from assets/plugins/*.seext — drop a newer
    Arkham plugin build in that folder and every template refreshes."""
    plug_dir = os.path.join(ROOT, "assets", "plugins")
    seexts = sorted((f for f in os.listdir(plug_dir) if f.endswith(".seext")),
                    key=lambda f: os.path.getmtime(os.path.join(plug_dir, f)))
    if not seexts:
        return {"ok": False, "message": "no .seext in assets/plugins/"}
    newest = os.path.join(plug_dir, seexts[-1])
    def refresh():
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "extract_se_plugin.py"),
                        newest], check=True, cwd=ROOT)
        log("plugin assets refreshed from " + os.path.basename(newest))
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        log("all faces recomposed on the refreshed templates")
    return run_job("plugin-update", refresh)


def act_install_fonts(p):
    """Setup: fetch Arkhamic (OFL Teutonic extension) into assets/fonts."""
    return run_job("install-fonts", installer.install_fonts,
                   dry_run=bool(p.get("dry_run")))


def act_font_set(p):
    """Manual font override (title/stat/body) from the card editor. card can be
    a card id (that card only) or "_default" — the default font for EVERY card,
    which the per-card override still beats. Recomposes the affected faces."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    card = os.path.basename(str(p.get("card", "")).strip()) or "_default"
    entry = {}
    for k in ("title", "stat", "body"):
        v = os.path.basename((p.get(k) or "").strip())
        if v:
            entry[k] = v
    with _state_lock:
        ov = rp.load_font_overrides()
        if entry:
            ov[card] = entry
        else:
            ov.pop(card, None)
        _write_json_atomic(rp.FONT_OVERRIDES_PATH, ov)
        cmd = [sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py")]
        if card != "_default":                 # _default touches every card
            cmd += ["--only", card]
        subprocess.run(cmd, check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    where = "every card" if card == "_default" else card
    log("fonts for {}: {}".format(where, entry or "default stack"))
    return {"ok": True, "fonts": entry}


def spec_files(campaign="still_hour"):
    """The card-spec files for ONE campaign.

    The Still Hour keeps its authored stillhour_* specs; every other campaign
    reads and writes <campaign>_*_spec.json, so a campaign built from scratch
    starts genuinely empty instead of showing another campaign's cards.
    """
    if campaign == "still_hour":
        names = ("stillhour_cards_spec.json", "stillhour_encounter_spec.json",
                 "stillhour_scenario_spec.json", "stillhour_imported_spec.json")
    else:
        names = ("{}_cards_spec.json".format(campaign),
                 "{}_imported_spec.json".format(campaign))
    return [os.path.join(ROOT, "pipeline", n) for n in names]


def own_spec_path(campaign="still_hour"):
    """Where hand-made cards for this campaign are written."""
    return os.path.join(ROOT, "pipeline",
                        "stillhour_handmade_spec.json" if campaign == "still_hour"
                        else "{}_cards_spec.json".format(campaign))


TYPE_FIELDS = ("name", "subtitle", "traits", "text", "flavor", "victory", "stats")
LOG_FIELDS = ("player", "investigator1", "xp1", "investigator2", "xp2",
              "investigator3", "xp3")


def act_type_set(p):
    """Per-text-area typography override (font / size / bold / italic) for one
    editable area of a card. card can be a card id or "_default" (applies to
    every card; the per-card override still wins). Stored under the card's
    "fields" map in font_overrides.json; recomposes the affected faces."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    card = os.path.basename(str(p.get("card", "")).strip()) or "_default"
    field = str(p.get("field", "")).strip()
    if field not in TYPE_FIELDS:
        return {"ok": False, "message": "unknown text area: " + field}
    style = {}
    font = os.path.basename((p.get("font") or "").strip())
    if font:
        style["font"] = font
    try:
        size = float(p.get("size") or 1.0)
    except (TypeError, ValueError):
        size = 1.0
    size = max(0.5, min(2.0, size))
    if abs(size - 1.0) > 0.001:
        style["size"] = round(size, 3)
    if bool(p.get("bold")):
        style["bold"] = True
    if bool(p.get("italic")):
        style["italic"] = True
    with _state_lock:
        ov = rp.load_font_overrides()
        entry = dict(ov.get(card, {}))
        fields = dict(entry.get("fields", {}))
        # keep any drag offset the box already has — typography and position are
        # set by different controls and must not clobber each other
        for _k in ("dx", "dy"):
            if fields.get(field, {}).get(_k):
                style[_k] = fields[field][_k]
        if style:
            fields[field] = style
        else:
            fields.pop(field, None)          # reset this area to its default
        if fields:
            entry["fields"] = fields
        else:
            entry.pop("fields", None)
        if entry:
            ov[card] = entry
        else:
            ov.pop(card, None)
        _write_json_atomic(rp.FONT_OVERRIDES_PATH, ov)
        cmd = [sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py")]
        if card != "_default":
            cmd += ["--only", card]
        subprocess.run(cmd, check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    where = "every card" if card == "_default" else card
    log("text style [{}] on {}: {}".format(field, where, style or "reset"))
    return {"ok": True, "field": field, "style": style}


def act_field_pos(p):
    """Reposition one text area by dragging its box in the editor: store a pixel
    offset (dx, dy) on the field, preserving its typography. dx == dy == 0 clears
    the offset. Same store as type_set (font_overrides.json → fields)."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    card = os.path.basename(str(p.get("card", "")).strip()) or "_default"
    field = str(p.get("field", "")).strip()
    if field not in TYPE_FIELDS:
        return {"ok": False, "message": "unknown text area: " + field}

    def _clamp(v):
        try:
            return max(-600, min(600, int(round(float(v or 0)))))
        except (TypeError, ValueError):
            return 0
    dx, dy = _clamp(p.get("dx")), _clamp(p.get("dy"))
    with _state_lock:
        ov = rp.load_font_overrides()
        entry = dict(ov.get(card, {}))
        fields = dict(entry.get("fields", {}))
        st = dict(fields.get(field, {}))
        for k, v in (("dx", dx), ("dy", dy)):
            if v:
                st[k] = v
            else:
                st.pop(k, None)
        if st:
            fields[field] = st
        else:
            fields.pop(field, None)
        if fields:
            entry["fields"] = fields
        else:
            entry.pop("fields", None)
        if entry:
            ov[card] = entry
        else:
            ov.pop(card, None)
        _write_json_atomic(rp.FONT_OVERRIDES_PATH, ov)
        cmd = [sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py")]
        if card != "_default":
            cmd += ["--only", card]
        subprocess.run(cmd, check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    log("text moved [{}] on {}: dx={} dy={}".format(field, card, dx, dy))
    return {"ok": True, "field": field, "dx": dx, "dy": dy}


def act_upload_font(p):
    """Bring your own font: save an uploaded .ttf/.otf into assets/fonts/ so it
    appears in every font dropdown. Data comes as a data: URL from the browser."""
    import base64
    name = os.path.basename((p.get("name") or "").strip()) or "custom.ttf"
    if not name.lower().endswith((".ttf", ".otf")):
        return {"ok": False, "message": "font must be a .ttf or .otf file"}
    data = p.get("data_b64", "")
    if "," in data:
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    dest = os.path.join(ROOT, "assets", "fonts", name)
    with open(dest, "wb") as f:
        f.write(raw)
    # verify it actually loads as a font before advertising it
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    try:
        from PIL import ImageFont
        ImageFont.truetype(dest, 20)
    except OSError:
        os.remove(dest)
        return {"ok": False, "message": name + " is not a usable font file"}
    log("font uploaded: " + name)
    return {"ok": True, "file": name, "fonts": rp.list_fonts()}


def act_install_a1111(p):
    """Setup: self-contained Stable Diffusion into vendor/a1111."""
    return run_job("install-a1111", installer.install_a1111,
                   dry_run=bool(p.get("dry_run")))


def act_install_comfy(p):
    """Setup: self-contained ComfyUI into vendor/comfy (Windows portable)."""
    return run_job("install-comfy", installer.install_comfy,
                   dry_run=bool(p.get("dry_run")))


def act_install_checkpoint(p):
    """Setup: download the art model into vendor/models (self-contained)."""
    return run_job("install-checkpoint", installer.install_checkpoint,
                   p.get("campaign", "still_hour"),
                   token=p.get("token") or None,
                   dry_run=bool(p.get("dry_run")))


def act_install_se(p):
    """Setup: download Strange Eons into vendor/strange-eons (self-contained)."""
    return run_job("install-strange-eons", installer.install_strange_eons,
                   dry_run=bool(p.get("dry_run")))


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


def act_compose_furniture(p):
    """Compose the card's FURNITURE overlay (<id>-furniture.png): frame + text +
    discs on a transparent art window. The editor lays this over the live,
    draggable art so the art reads behind the frame exactly as the render does.
    Synchronous; leaves the real face untouched."""
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                    "--furniture", "--only", p["card"]],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
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
                        "scale_y": max(0.2, min(6.0, float(p["scale_y"])))
                        if p.get("scale_y") else None,
                        "ox": float(p.get("ox", 0)), "oy": float(p.get("oy", 0))}
    placements[card] = {k: v for k, v in placements[card].items() if v is not None}
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
    _add_deck_backs(urls)
    with open(os.path.join(ROOT, "pipeline", "art_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2)
    log("art_urls.json: {} card(s), local file:/// mode".format(len(urls)))
    for script in ("build_cards.py", "bundle_mod.py", "package_download.py"):
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", script)],
                       check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        log("rebuilt: pipeline/" + script)


def _add_deck_backs(urls, hosted_base=None):
    """Campaign-wide deck backs (assets/backs/*.png) ride along in every
    art_urls.json write as _player_back / _encounter_back."""
    for key, fname in (("_player_back", "player_back.png"),
                       ("_encounter_back", "encounter_back.png")):
        p = os.path.join(ROOT, "assets", "backs", fname)
        if os.path.exists(p):
            urls[key] = (hosted_base + "/" + fname) if hosted_base \
                else "file:///" + p.replace(os.sep, "/").lstrip("/")


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
        _add_deck_backs(urls)
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
    _add_deck_backs(urls, hosted_base=base if mode == "hosted" else None)
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
    return {"ok": True,
            "cards": len([k for k in urls if not k.startswith("_")])}


# ------------------------------------------------------------------- status --

def _scenario_board(campaign="still_hour"):
    """The deck-builder board: scenario list from the manifest + saved
    card-to-stack assignments."""
    mpath = os.path.join(ROOT, "campaigns", campaign, "scenario_manifest.json")
    scen = []
    try:
        m = json.load(open(mpath, encoding="utf-8"))
        for sc in m.get("scenarios", []):
            stacks = sc.get("stacks", {}) or {}
            req = {}
            loc = (stacks.get("locations", {}) or {}).get("cards", [])
            if loc:
                req["locations"] = [c.get("name", "?") for c in loc]
            act = (stacks.get("act_deck", {}) or {}).get("cards", [])
            if act:
                req["act_deck"] = [c.get("name", "?") for c in act]
            enc = (stacks.get("encounter", {}) or {})
            sets = enc.get("sets", [])
            if sets:
                req["encounter"] = [str(x) for x in sets]
            aside = enc.get("aside", [])
            if aside:
                req["setup_aside"] = [str(x) for x in aside]
            scen.append({"id": sc.get("id"), "name": sc.get("name"),
                         "order": sc.get("order", 99), "req": req})
        scen.sort(key=lambda x: x["order"])
    except (ValueError, OSError):
        pass
    apath = os.path.join(ROOT, "campaigns", campaign,
                         "scenario_assignments.json")
    assigns = {}
    if os.path.exists(apath):
        try:
            assigns = json.load(open(apath, encoding="utf-8"))
        except ValueError:
            assigns = {}
    return {"scenarios": scen, "stacks": list(SCENARIO_STACKS),
            "assignments": assigns, "grid": dict(MAP_GRID),
            "furniture": [dict(f) for f in MAP_FURNITURE]}


def status(campaign="still_hour"):
    camp = runner.load_campaign(campaign)
    out_dir = runner.out_dir_for(camp)
    report = {}
    rp = os.path.join(out_dir, "report.json")
    if os.path.exists(rp):
        try:
            r = json.load(open(rp, encoding="utf-8"))
            report = {"generated": len(r["generated"]), "failed": len(r["failed"]),
                      "warnings": r["warnings"], "dry_run": r.get("dry_run")}
        except (ValueError, KeyError, TypeError):
            report = {}    # mid-write / partial / garbage — next poll recovers
    gallery = []
    if os.path.isdir(out_dir):
        for cid in sorted(os.listdir(out_dir)):
            cdir = os.path.join(out_dir, cid)
            if not os.path.isdir(cdir) or cid in ("payloads", "seeds"):
                continue
            pngs = sorted(f for f in os.listdir(cdir) if f.endswith(".png"))
            # dry-run stubs are 1x1 markers (~100 bytes) — flag them so the
            # UI can hide the confusing grey tiles once real art exists
            stubs = [f for f in pngs
                     if os.path.getsize(os.path.join(cdir, f)) < 2048]
            chosen_path = os.path.join(cdir, "chosen.txt")
            chosen = open(chosen_path, encoding="utf-8").read().strip() if os.path.exists(chosen_path) \
                else (pngs[0] if pngs else None)
            face = has_face(cid)
            gallery.append({"id": cid, "variants": pngs, "stubs": stubs,
                            "chosen": chosen, "face": face})
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
    for p in spec_files(campaign):
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
        if c["type"] in ("Location", "Agenda", "Act", "Scenario", "Story"):
            return "Scenario cards"
        if c.get("encounter"):
            return "Encounter — The Named" if "Named" in c.get("traits", "") \
                else "Encounter — The Appointed"
        if c["type"] == "Investigator":
            return "Investigators"
        if "Recollection" in c.get("traits", "") and c.get("class") == "Neutral":
            return "Recollections"
        return "Signatures & Weaknesses"
    catalog = []
    for path in spec_files(campaign):
        if not os.path.exists(path):
            continue
        for c in json.load(open(path, encoding="utf-8")):
            cdir = os.path.join(out_dir, c["id"])
            variants = sorted(f for f in os.listdir(cdir) if f.endswith(".png")) \
                if os.path.isdir(cdir) else []
            vstubs = [f for f in variants
                      if os.path.getsize(os.path.join(cdir, f)) < 2048]
            chosen_path = os.path.join(cdir, "chosen.txt")
            chosen = open(chosen_path, encoding="utf-8").read().strip() if os.path.exists(chosen_path) \
                else (variants[0] if variants else None)
            catalog.append({
                "id": c["id"], "name": c["name"], "type": c["type"],
                "class": c.get("class", ""), "group": group_for(c),
                "face": has_face(c["id"]),
                "spoiler": bool(c.get("encounter")),
                "variants": variants, "stubs": vstubs, "chosen": chosen,
            })
    font_overrides = rp.load_font_overrides()
    card_overrides = rp.load_card_overrides(campaign)
    print_text = se_bridge._load_print_text()
    spec_by_id = {}
    for p2 in spec_files(campaign):
        if os.path.exists(p2):
            for sc in json.load(open(p2, encoding="utf-8")):
                spec_by_id[sc["id"]] = sc
    for c in catalog:
        if c["id"] in boxes:
            c["artbox"] = boxes[c["id"]]
            c["placement"] = placements.get(c["id"], {"scale": 1.0, "ox": 0, "oy": 0})
        c["fonts"] = font_overrides.get(c["id"], {})
        mc, mpt = rp.apply_card_overrides(
            spec_by_id.get(c["id"], {}), print_text.get(c["id"], {}),
            card_overrides.get(c["id"]))
        health = mpt.get("health") if c["type"] == "Enemy" else mc.get("health")
        c["content"] = {
            "name": mc.get("name", ""), "subtitle": mc.get("subtitle", ""),
            "traits": mc.get("traits", ""), "cost": mc.get("cost"),
            "level": mc.get("level"), "victory": mc.get("victory"),
            "wil": mc.get("wil"), "int": mc.get("int"),
            "com": mc.get("com"), "agi": mc.get("agi"),
            "health": health, "sanity": mc.get("sanity"),
            "slot": mc.get("slot", ""),
            "text": mpt.get("text", ""), "flavor": mpt.get("flavor", ""),
            "fight": mpt.get("fight"), "evade": mpt.get("evade"),
            "damage": mpt.get("damage") or 0, "horror": mpt.get("horror") or 0,
            "shroud": mc.get("shroud"), "clues": mc.get("clues"),
            "doom": mc.get("doom"),
            "back_text": mpt.get("back_text", ""),
            "back_flavor": mpt.get("back_flavor", ""),
            "player": mpt.get("player", ""),
            "investigator1": mpt.get("investigator1", ""), "xp1": mpt.get("xp1", ""),
            "investigator2": mpt.get("investigator2", ""), "xp2": mpt.get("xp2", ""),
            "investigator3": mpt.get("investigator3", ""), "xp3": mpt.get("xp3", ""),
            "tokens": mc.get("tokens") or [],
            "icons": mc.get("icons", ""), "color": mc.get("color", ""),
            "clues_per_investigator": bool(mc.get("clues_per_investigator")),
            "connections": mc.get("connections") or [],
        }
        for _k in rp.OV_FLAG_KEYS:
            c["content"][_k] = bool(mc.get(_k))
        for _k in rp.OV_COUNT_KEYS + rp.OV_PROP_KEYS:
            c["content"][_k] = mc.get(_k) if mc.get(_k) is not None else ""
        c["regions"] = rp.content_regions(c["type"])
        c["overridden"] = sorted(card_overrides.get(c["id"], {}).keys())
        # per-text-area typography: global defaults with this card's on top
        _fd = font_overrides.get("_default", {}).get("fields", {})
        _fc = font_overrides.get(c["id"], {}).get("fields", {})
        c["type_styles"] = {k: dict(_fd.get(k, {}), **_fc.get(k, {}))
                            for k in set(_fd) | set(_fc)}
    campaigns = sorted(d for d in os.listdir(os.path.join(ROOT, "campaigns"))
                       if os.path.isdir(os.path.join(ROOT, "campaigns", d)))
    # Where the app lands when the browser has no remembered choice: the newest
    # campaign that isn't the finished Still Hour reference set, so opening the
    # app drops you into what you're actually building. Still Hour stays in the
    # picker. Falls back to still_hour only when nothing else exists.
    _others = [c for c in campaigns if c != "still_hour"]
    default_campaign = (max(_others, key=lambda c: os.path.getmtime(
        os.path.join(ROOT, "campaigns", c))) if _others else "still_hour")
    faces_dir_abs = os.path.join(ROOT, "art", "faces")
    faces_ver = 0
    if os.path.isdir(faces_dir_abs):
        faces_ver = int(max((os.path.getmtime(os.path.join(faces_dir_abs, f))
                             for f in os.listdir(faces_dir_abs)), default=0))
    return {"busy": _busy.is_set(), "last_job": dict(LAST_JOB),
            "build": build_stamp(),
            "campaign": campaign, "campaigns": campaigns,
            "campaign_name": camp.get("name") or campaign,
            "default_campaign": default_campaign,
            "backend": camp.get("backend"), "checkpoint": camp.get("checkpoint"),
            "style": {"lora": camp.get("style_lora", ""),
                      "lora_weight": camp.get("style_lora_weight", 0.8),
                      "trigger": camp.get("style_trigger", ""),
                      "positive": camp.get("style_positive", ""),
                      "negative": camp.get("style_negative", "")},
            "report": report, "gallery": gallery,
            "rig": {k: v for k, v in rig.load_rig().items() if k != "_note"},
            "vendor": installer.vendor_status(),
            "seeds": seeds, "cards": catalog, "faces_ver": faces_ver,
            "gen": camp.get("overrides_all", {}),
            "fonts": rp.list_fonts(),
            "default_fonts": font_overrides.get("_default", {}),
            "default_type_styles": font_overrides.get("_default", {}).get("fields", {}),
            "characters": {n: {"lora": (v or {}).get("lora", ""),
                               "weight": (v or {}).get("weight", 0.8),
                               "trigger": (v or {}).get("trigger", "")}
                           for n, v in chars.items() if not n.startswith("_")},
            "scenarios": _scenario_board(campaign),
            "se": {"config": se_bridge.load_config(),
                   "bundle_exists": os.path.exists(
                       os.path.join(se_bridge.se_dir(), "frame_cards.js")),
                   "coverage": se_bridge.coverage(campaign)}}


# --------------------------------------------------------------------- http --

ACTIONS = {"generate": act_generate, "seeds": act_seeds, "contact": act_contact,
           "index": act_index, "backend_check": act_backend_check,
           "rig_save": act_rig_save, "backend_launch": act_backend_launch,
           "seed_pick": act_seed_pick,
           "models": act_models, "backend_set": act_backend_set, "model_set": act_model_set,
           "install_checkpoint": act_install_checkpoint,
           "install_se": act_install_se, "install_a1111": act_install_a1111,
           "install_comfy": act_install_comfy,
           "install_fonts": act_install_fonts, "font_set": act_font_set,
           "type_set": act_type_set, "field_pos": act_field_pos,
           "upload_font": act_upload_font,
           "tts_spawn": act_tts_spawn, "plugin_update": act_plugin_update,
           "card_save": act_card_save, "art_remove": act_art_remove,
           "scenario_save": act_scenario_save, "map_save": act_map_save,
           "map_connect": act_map_connect,
           "scenario_new": act_scenario_new,
           "scenario_delete": act_scenario_delete,
           "scenario_rename": act_scenario_rename, "campaign_import": act_campaign_import, "campaign_new": act_campaign_new,
           "card_new": act_card_new, "card_delete": act_card_delete,
           "campaign_compile": act_campaign_compile,
           "prompt_get": act_prompt_get, "prompt_save": act_prompt_save,
           "style_save": act_style_save, "inpaint_frames": act_inpaint_frames,
           "gen_settings": act_gen_settings, "lora_save": act_lora_save,
           "choose": act_choose, "se_save_config": act_se_save_config,
           "se_bundle": act_se_bundle, "se_launch": act_se_launch,
           "render_placeholders": act_render_placeholders, "apply": act_apply,
           "place": act_place, "auto": act_auto, "upload_art": act_upload_art,
           "compose_one": act_compose_one,
           "compose_furniture": act_compose_furniture,
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
        try:
            self._do_get()
        except Exception as e:  # noqa: BLE001 - a bad read must answer, not drop
            try:
                # keep the keys every poller relies on, so one bad read shows
                # up as an error instead of breaking the whole UI loop
                self._json({"error": str(e), "busy": _busy.is_set(),
                            "cards": [], "campaigns": []}, 500)
            except Exception:  # noqa: BLE001 - client already gone
                pass

    def _do_get(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            # a dev tool that reloads on pull — never let the browser serve a
            # stale page, or new UI silently won't appear after an update
            self.send_header("Cache-Control", "no-store")
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
            allowed = (os.path.join(ROOT, "out"), os.path.join(ROOT, "art"),
                       os.path.join(ROOT, "assets", "branding"))
            if not path.startswith(allowed) or not os.path.exists(path):
                self._json({"error": "not found"}, 404)
                return
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif u.path == "/favicon.ico":
            path = os.path.join(ROOT, "assets", "branding", "cardforge.ico")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                self._json({"error": "not found"}, 404)
                return
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif u.path == "/font":
            # serve a font file from assets/fonts (for the symbol palette's
            # @font-face so buttons show the real Arkham glyphs)
            name = os.path.basename(q.get("f", ""))
            path = os.path.join(ROOT, "assets", "fonts", name)
            if not name.lower().endswith((".ttf", ".otf")) \
                    or not os.path.exists(path):
                self._json({"error": "not found"}, 404)
                return
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
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
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        try:
            params = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(params, dict):
                raise ValueError("body must be a JSON object")
        except ValueError as e:
            self._json({"ok": False, "message": "bad request body: " + str(e)}, 400)
            return
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
<title>CardForge Studio</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/art?p=assets/branding/banner.png">
<link rel=icon href="data:,">
<style>
:root{--bg:#0e0e13;--surface:#17171f;--surface2:#1e1e28;--line:rgba(255,255,255,.08);
--ink:#f2efe6;--dim:#9a97a3;--accent:#d9a648;--accent-ink:#1a1408;--good:#5fc47e;--bad:#e0716a;
--r:14px;--shadow:0 8px 30px rgba(0,0,0,.45)}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
-webkit-font-smoothing:antialiased}
/* the banner (assets/branding/banner.png, 2048x512) rides behind the header.
   The overlay is graded — darker at the edges where the title and buttons sit,
   lighter across the middle so the art reads. If the banner isn't there yet the
   image layer simply doesn't paint and the base tone shows. */
header{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:14px;
padding:18px 26px;min-height:66px;
background:linear-gradient(90deg,rgba(14,14,19,.9),rgba(14,14,19,.6) 50%,rgba(14,14,19,.9)),
url('/art?p=assets/branding/banner.png') center/cover no-repeat,rgba(14,14,19,.92);
backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
header h1{font-size:17px;font-weight:600;letter-spacing:.2px;text-shadow:0 1px 6px rgba(0,0,0,.7)}
header .sub{color:var(--dim);font-size:13px;text-shadow:0 1px 5px rgba(0,0,0,.7)}
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
.stepbox{display:flex;flex-direction:column;gap:6px;margin:10px 0}
.step{display:flex;align-items:baseline;gap:10px;font-size:13.5px;color:var(--dim)}
.step b{color:var(--ink);font-weight:600}
.step .n{flex:none;width:22px;height:22px;border-radius:50%;display:inline-flex;
align-items:center;justify-content:center;font-size:12px;border:1px solid var(--line);
background:var(--surface2);transform:translateY(4px)}
.step.done .n{background:var(--good);color:#08150c;border-color:transparent}
.step.done{color:var(--dim);text-decoration:none}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 4px}
.chip{padding:6px 14px;border-radius:999px;border:1px solid var(--line);
background:var(--surface2);color:var(--dim);cursor:pointer;font-size:13px;
transition:all .15s}
.chip:hover{color:var(--ink)}
.chip.on{background:var(--accent);color:var(--accent-ink);border-color:transparent;font-weight:600}
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
.okpill{color:#7fd18c;font-weight:600}
.badpill{color:#e2707a;font-weight:600}
.warnpill{color:#e8b24a;font-weight:600}
#editor{display:none;animation:fade .2s ease}
#ed_toolbar{position:sticky;top:0;z-index:6;background:var(--surface);
padding:8px 10px;margin:-6px -10px 6px;border-bottom:1px solid var(--line);border-radius:0 0 10px 10px}
@font-face{font-family:'ArkhamGlyph';src:url('/font?f=ArkhamFontWithCodex.ttf')}
.symbtn{display:inline-flex;flex-direction:column;align-items:center;gap:1px;
cursor:pointer;background:var(--surface2);border:1px solid var(--line);
border-radius:7px;padding:4px 7px;min-width:44px}
.symbtn:hover{border-color:var(--accent)}
.symbtn .gly{font-family:'ArkhamGlyph';font-size:20px;line-height:1;color:#e9e2d0}
.symbtn small{font-size:9px;color:var(--dim);letter-spacing:.2px}
#zoom{display:none;position:fixed;inset:0;z-index:10;background:rgba(8,8,12,.8);
backdrop-filter:blur(10px);animation:fade .2s ease;align-items:center;justify-content:center}
#zoom_box{background:var(--surface);border:1px solid var(--line);border-radius:18px;
box-shadow:var(--shadow);padding:14px;max-width:92vw}
#zoom_img{display:block;max-width:88vw;max-height:78vh;border-radius:10px;margin:0 auto}
#ed_sheet{background:var(--surface2);border:1px solid var(--line);border-radius:18px;
box-shadow:var(--shadow);margin:14px 0;padding:18px 20px}
/* Photoshop-style editor: the card canvas on the left, a properties panel on
   the right that acts on whichever text area is selected on the card */
#ed_main{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}
#ed_left{flex:0 0 auto}
#ed_side{flex:1 1 250px;min-width:230px;max-width:340px;position:sticky;top:12px;
background:rgba(120,150,190,.10);border:1px solid rgba(120,150,190,.28);
border-radius:12px;padding:12px 14px}
#ed_side .ed_side_grp{margin:6px 0}
#ed_side .ed_side_grp label{display:block;margin-bottom:2px}
#ed_stage{position:relative;margin:12px auto;overflow:hidden;border-radius:10px;
border:1px solid var(--line);background:#14151b}
#ed_face{display:block;user-select:none;pointer-events:none}
#ed_win{position:absolute;overflow:hidden;cursor:grab;outline:2px dashed var(--accent);
outline-offset:-2px;border-radius:2px;z-index:1}
#ed_art{position:absolute;user-select:none}
/* the furniture overlay: frame + text + discs on a transparent art window, laid
   OVER the live art so the art reads behind the frame exactly as the render */
#ed_furniture{position:absolute;top:0;left:0;pointer-events:none;display:none;z-index:2}
/* draggable text-box handles sit on top of everything and take the clicks */
#ed_regions{position:absolute;inset:0;z-index:3;pointer-events:none}
.ed_rg{position:absolute;pointer-events:auto;cursor:move;border:1px dashed transparent;
border-radius:3px;transition:border-color .12s,background .12s}
.ed_rg:hover{border-color:rgba(232,178,74,.75);background:rgba(232,178,74,.10)}
.ed_rg.sel{border-color:var(--accent);background:rgba(232,178,74,.14)}
#ed_strip{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
#ed_strip img{height:74px;border-radius:8px;cursor:pointer;border:2px solid transparent;
transition:all .15s}
#ed_strip img:hover{transform:translateY(-2px)}
#ed_strip img.on{border-color:var(--accent)}
/* --- scenario deck-builder board --- */
/* the board scrolls sideways; the wrapper fades both edges so it is obvious
   there is more campaign off-screen than fits */
#board_wrap{position:relative}
#board_wrap::before,#board_wrap::after{content:'';position:absolute;top:0;bottom:18px;
width:38px;pointer-events:none;z-index:2;opacity:0;transition:opacity .18s}
#board_wrap::before{left:0;background:linear-gradient(90deg,var(--surface),transparent)}
#board_wrap::after{right:0;background:linear-gradient(270deg,var(--surface),transparent)}
#board_wrap.more-l::before{opacity:1}
#board_wrap.more-r::after{opacity:1}
#scen_board{display:flex;gap:14px;overflow-x:auto;padding:6px 2px 18px;align-items:stretch}
/* every column the same height, with its own scroll, so the row has a baseline
   and one fat scenario cannot stretch the whole board */
.scenbox{min-width:250px;max-width:250px;max-height:66vh;display:flex;flex-direction:column;
background:var(--surface2);border:1px solid var(--line);
border-radius:12px;padding:10px}
.scenbox h3{margin:0 0 8px;font-size:14px}
/* the scrolling middle of a column: stacks live here, the title above and the
   lock button below stay put */
.stacks{flex:1;overflow-y:auto;overflow-x:hidden;padding-right:2px}
.stack{margin-bottom:8px;border:1px dashed rgba(255,255,255,.14);border-radius:9px;padding:6px;min-height:34px;transition:border-color .15s,background .15s}
.stack.over{border-color:var(--accent);background:rgba(232,178,74,.08)}
.stack small{display:block;color:var(--dim);margin-bottom:4px;letter-spacing:.3px;text-transform:uppercase;font-size:10px}
/* an empty stack is still a drop target, but it collapses to a thin labelled
   rail instead of costing as much room as a full one */
.stack.empty{min-height:0;padding:3px 7px;margin-bottom:5px;opacity:.6}
.stack.empty small{margin:0;display:inline}
.stack.empty:hover,.stack.empty.over{opacity:1}
/* requirements sit in their own strip ABOVE the cards — sharing one inline
   flow with them was what shattered the stacks */
.stack .reqs{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:5px}
.stack .cards{display:flex;flex-wrap:wrap;gap:4px;align-content:flex-start}
.dcard{display:inline-block;width:52px;margin:2px;cursor:grab;position:relative;
transition:transform .16s ease,box-shadow .16s ease}
.dcard img{width:100%;border-radius:4px;display:block;box-shadow:0 1px 4px rgba(0,0,0,.5)}
.dcard:hover{transform:translateY(-6px) scale(1.5) rotate(.5deg);z-index:5;box-shadow:0 8px 18px rgba(0,0,0,.6)}
.dcard.dragging{opacity:.45;transform:scale(.95) rotate(-3deg)}
.dcard.justdropped{animation:settle .28s ease}
@keyframes settle{0%{transform:translateY(-10px) scale(1.12)}70%{transform:translateY(2px) scale(.98)}100%{transform:none}}
#mapwrap{display:none;margin:10px 0;padding:14px;border-radius:12px;
background:#0a0a0c;border:1px solid rgba(201,162,74,.30)}
#mapstage{position:relative}
/* The real table leaves about one and a half card widths between locations.
   The default here is close to that so connections read at a glance, and the
   Spacing slider moves it — the layout you save is the same either way, since
   slots are grid positions, not pixels. */
#mapgrid{display:grid;gap:var(--mapgap,86px);justify-content:center}
#maplines{position:absolute;inset:0;pointer-events:none;z-index:6}
.mslot{width:104px;height:146px;border:2px dashed rgba(255,255,255,.16);
border-radius:8px;display:flex;align-items:center;justify-content:center;
position:relative;transition:border-color .15s,background .15s}
.mslot.over{border-color:var(--accent);background:rgba(232,178,74,.10)}
.mslot .co{position:absolute;top:2px;left:4px;font-size:9px;color:rgba(255,255,255,.30)}
.mslot img{width:100%;height:100%;object-fit:cover;border-radius:6px;cursor:grab;
position:relative;z-index:4}
#mapwrap.linking .mslot img{cursor:crosshair}
#mapwrap.linking .mslot img.sel{outline:3px solid var(--accent);
outline-offset:-3px;box-shadow:0 0 14px rgba(232,178,74,.55)}
/* a location's OWN identifier, top-left, exactly where the card prints it —
   this one never moves and never appears in the row below */
.msym{position:absolute;top:2px;left:4px;font-size:10px;z-index:5;
color:#e8b24a;background:rgba(0,0,0,.6);border-radius:4px;padding:0 3px}
/* the row below: one chip per location this one connects to. Grab a chip and
   drop it on another location to move that connection there. */
.mrow{position:absolute;bottom:-9px;left:0;right:0;z-index:7;display:flex;
gap:3px;justify-content:center;pointer-events:none}
.mchip{pointer-events:auto;cursor:grab;font-size:10px;line-height:1;
min-width:16px;text-align:center;border-radius:5px;padding:2px 3px;
background:#14141a;border:1px solid rgba(0,0,0,.6);
box-shadow:0 1px 3px rgba(0,0,0,.55)}
.mchip:active{cursor:grabbing}
.mchip.moving{opacity:.35}
/* the connector you grab: a coloured nub in the card's own connection colour,
   dragged onto another location to link them */
.mnub{position:absolute;top:-11px;left:50%;transform:translateX(-50%);
width:24px;height:13px;border-radius:7px;z-index:7;cursor:grab;
border:1px solid rgba(0,0,0,.55);box-shadow:0 1px 3px rgba(0,0,0,.5)}
.mnub:active{cursor:grabbing}
.mslot.linkable{border-color:var(--accent);border-style:solid;
background:rgba(232,178,74,.10)}
#mappreview{display:none;margin-top:12px;padding:12px;border-radius:10px;
background:#07070a;border:1px solid rgba(201,162,74,.25)}
#pvstage{position:relative;margin:0 auto;background:#0b0b0f;border-radius:8px;
overflow:hidden}
#pvstage .pvcard{position:absolute;border-radius:3px;object-fit:fill;
box-shadow:0 2px 6px rgba(0,0,0,.6)}
#pvstage .pvbox{position:absolute;border-radius:4px;display:flex;
align-items:center;justify-content:center;text-align:center;
border:1px dashed rgba(255,255,255,.28);color:rgba(255,255,255,.55);
font-size:9px;line-height:1.1;padding:2px;background:rgba(255,255,255,.03)}
#pvstage .pvclash{outline:2px solid #d05050;outline-offset:1px}
#pvstage svg{position:absolute;inset:0;pointer-events:none;z-index:2}
#mapwrap h4{margin:0 0 10px;font-size:13px;color:#d8c9a6}
#scen_pool{border:1px solid var(--line);border-radius:12px;padding:8px;margin-bottom:10px;background:var(--surface2)}
.reqchip{display:inline-block;font-size:10px;color:var(--dim);border:1px dashed rgba(255,255,255,.22);
border-radius:5px;padding:1px 6px;letter-spacing:.2px;white-space:nowrap}
.reqchip.met{color:#7fbf7f;border-style:solid;border-color:rgba(127,191,127,.4);text-decoration:line-through}
.scenbox.locked{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.scenbox.locked .stack{border-style:solid;opacity:.85}
.lockbtn{width:100%;margin-top:8px;flex:none}
#camp_bar{display:flex;gap:10px;align-items:center;border:1px solid var(--line);
border-radius:12px;padding:10px 14px;margin-bottom:10px;background:var(--surface2)}
#camp_bar .slot{border:1px dashed rgba(255,255,255,.2);border-radius:8px;padding:4px 10px;font-size:12px;color:var(--dim)}
.hint{color:var(--dim);font-size:12px}
hr{border:none;border-top:1px solid var(--line);margin:16px 0}
</style></head><body>
<header><h1>CardForge Studio</h1><span class=sub id=hdr_sub>fan content</span>
<span id=build class=stat title="the build actually running right now — if this doesn't match your latest pull, restart the app">v…</span>
<span class=spacer></span>
<span id=busy class=stat><span class=dot id=busydot></span><span id=busytext>idle</span></span>
<button class=btn onclick=refresh() title="refresh the gallery and cards">&#8635;</button>
<label>campaign</label><select id=campaign onchange=campPick()></select>
<button class=btn onclick=campNew() title="start a new campaign, seeded with a recommended starter scenario">+ New</button>
<button class="btn primary" onclick="post('auto',{dry_run:dry()})" title="generate &rarr; place &rarr; compose &rarr; TTS, hands-off">&#9889; Auto-build ALL &rarr; TTS</button>
</header>
<nav>
<button id=tab-setup class=on onclick="tab('setup')">1 &middot; Setup</button>
<button id=tab-illustrate onclick="tab('illustrate')">2 &middot; Illustrate</button>
<button id=tab-cards onclick="tab('cards')">3 &middot; Cards</button>
<button id=tab-scenarios onclick="tab('scenarios');scenBuild()">4 &middot; Campaign / scenarios</button>
<button id=tab-apply onclick="tab('apply')">5 &middot; Play in TTS</button>
<button id=tab-advanced onclick="tab('advanced')">&#9881; Advanced</button>
</nav><main>
<div id=joberr style="display:none;margin:10px auto;max-width:1100px;padding:10px 14px;
border:1px solid rgba(226,112,122,.45);background:rgba(226,112,122,.10);
border-radius:10px;color:#f0c9cd;font-size:13px"></div>

<section id=scenarios><div class=panel>
<div class=row><b>Scenario builder</b>
<span class=hint>drag cards from the pool into each scenario&rsquo;s stacks &mdash; the board saves itself and feeds the TTS compiler</span>
<span class=spacer></span>
<button class=btn onclick="document.getElementById('feed_file').click()" title="pour a written campaign (JSON) into the editor: existing cards become overrides, new cards are created, the board pre-fills">&#128229; Import campaign JSON&hellip;</button>
<input type=file id=feed_file accept=".json,application/json" style="display:none" onchange=feedImport(this)>
<span id=feed_info class=hint></span></div>
<div class=row style="margin-bottom:8px">
<b style="font-size:12px">New scenario box</b>
<input id=ns_name size=26 placeholder="scenario name" onkeydown="if(event.key==='Enter')scenNew()">
<button class="btn primary" onclick=scenNew()>+ Add scenario</button>
<span class=hint>each box holds its own locations, act/agenda, encounter set and set-aside cards</span>
</div>
<div id=camp_bar>
<b>Campaign box</b><span id=camp_progress class=stat>0/0 locked</span>
<span class=slot>&#128214; Campaign guide &mdash; PDF slot (Phase 3)</span>
<button class="btn slot" onclick="tab('cards');openEditor('sthr-campaign-log')" title="open the campaign log sheet: player, investigators, XP, notes">&#128221; Campaign log / notes</button>
<span class=spacer></span>
<button class="btn primary" id=camp_spawn disabled onclick=campCompile()
title="compiles every locked scenario into one scripted SCED campaign box (dist/the_still_hour_campaign.json) — load it in TTS as a saved object">&#128230; Spawn campaign box &rarr; TTS</button>
<span id=camp_out class=hint></span>
</div>
<div id=scen_pool><small class=hint>UNASSIGNED CARDS &mdash; drag onto the board</small><div id=scen_pool_cards></div></div>
<div class=row style="margin:2px 0 4px"><span class=hint id=board_hint></span></div>
<div id=board_wrap><div id=scen_board></div></div>
<div id=mapwrap>
<div class=row><h4 id=maptitle>Location map</h4>
<span class=hint>this is the black map border you see in TTS &mdash; slots are the real table positions</span>
<span class=spacer></span>
<button class="btn primary" id=map_mode_move onclick="mapMode('move')"
title="drag location cards between slots">&#10021; Arrange</button>
<button class=btn id=map_mode_link onclick="mapMode('link')"
title="click one location then another to connect them — each card gets the other's symbol printed on it">&#128279; Connect</button>
<span class=spacer></span>
<label style="font-size:11px;color:var(--dim)">spacing</label>
<input type=range id=map_gap min=16 max=190 step=2 value=86 style="width:110px"
title="how far apart the slots sit — only how the map is drawn here, never what gets saved"
oninput="mapGap(this.value)">
<button class=btn id=map_pv onclick=pvToggle()
title="see the whole scenario laid out to scale — exactly where every object lands on the table — before you send anything to TTS">&#128065; Table preview</button>
<button class=btn onclick=mapSave()>Save layout</button>
<button class=btn onclick="document.getElementById('mapwrap').style.display='none'">Close</button></div>
<div id=mapstage><div id=mapgrid></div><svg id=maplines></svg></div>
<div class=row style="margin-top:10px"><span class=hint id=mapinfo></span></div>
<div class=row style="margin-top:6px"><span class=hint id=maplegend></span></div>
<div id=mappreview>
<div class=row><b style="font-size:12px">Table preview</b>
<span class=hint>every object at its real table position and size &mdash; this is the layout the campaign box will spawn</span>
<span class=spacer></span><span class=hint id=pvinfo></span></div>
<div id=pvstage></div>
</div>
</div>
</div></section>
<section id=advanced><div class=panel>
<h2>Generate any card <small>pick a card, tune the prompt and settings, generate</small></h2>
<div class=row>
<select id=adv_card onchange=advLoad() style="max-width:340px">
<option value="">&mdash; pick a card &mdash;</option></select>
<label>steps</label><input type=number id=adv_steps style="width:70px" placeholder="auto">
<label>CFG</label><input type=number step=0.5 id=adv_cfg style="width:70px" placeholder="auto">
<label>sampler</label><input type=text id=adv_sampler size=16 placeholder="profile default">
<label>variants</label><input type=number id=adv_variants style="width:60px" value=2 min=1 max=8>
<label><input type=checkbox id=adv_reroll checked> new seeds</label>
</div>
<label>prompt</label><textarea id=adv_pos rows=3 spellcheck=false></textarea>
<label>negative prompt</label><textarea id=adv_neg rows=2 spellcheck=false></textarea>
<div class=row style="margin-top:6px">
<button class="btn primary" onclick=advGenerate()>Generate</button>
<button class=btn onclick="const c=document.getElementById('adv_card').value;if(c)post('tts_spawn',{card:c})"
title="drop the selected card onto the live TTS table">&#9654; Drop into TTS</button>
<span id=adv_info class=hint></span>
</div>
<p class=hint>&#128274;-marked cards are encounter cards (spoilers) — they generate fine, and the
shield still hides the result until you tap it. Prompt edits here are saved as that card&rsquo;s
override, same as the Cards-tab editor.</p>
<hr>
<h2>Generation defaults <small>applied to EVERY batch, Auto-build, and seed run</small></h2>
<div class=row>
<label>steps</label><input type=number id=gen_steps style="width:70px" placeholder="profile">
<label>CFG</label><input type=number step=0.5 id=gen_cfg style="width:70px" placeholder="profile">
<label>sampler</label><input type=text id=gen_sampler size=18 placeholder="profile default">
<button class=btn onclick=genSave()>Save defaults</button>
<span class=hint>leave blank to use each art type&rsquo;s tuned profile</span>
</div>
<hr>
<h2>Character LoRAs <small>consistency per investigator — strength 0&ndash;2, applied as &lt;lora:name:strength&gt;</small></h2>
<div id=lora_rows></div>
<div class=row style="margin-top:6px"><button class=btn onclick=loraSave()>Save LoRAs</button>
<span class=hint>no LoRA yet? leave empty — the character renders from description + trigger words.
Train LoRAs on the SAME checkpoint you generate with (MoodyKrea2Mix).</span></div>
</div></section>

<section id=setup class=on><div class=panel>
<h2>Make this folder self-contained <small>everything installs INTO the app folder and is found again wherever the folder moves</small></h2>
<div id=steps_setup class=stepbox></div>
<hr>
<div class=row>
<b style="min-width:180px">1 &middot; Stable Diffusion</b>
<button class="btn primary" onclick="post('install_a1111')">Install A1111 into this folder</button>
<span id=vendor_a1111 class=hint></span>
</div>
<div class=row style="margin-top:6px">
<b style="min-width:180px">1b &middot; ComfyUI <small style="color:var(--dim)">(Windows)</small></b>
<button class="btn primary" id=btn_comfy onclick="post('install_comfy')">Install ComfyUI into this folder</button>
<span id=vendor_comfy class=hint></span>
</div>
<p class=hint>Downloads the official <b>Windows portable</b> package (its own embedded Python &mdash;
nothing touches your system) into <code>vendor/comfy/</code>, writes a headless launcher with the
API on <code>:8188</code>, and shares <code>vendor/models/</code> so a checkpoint installed above is
visible to both backends. Krea&nbsp;2 and FLUX-family checkpoints need this path &mdash; classic
A1111 will not load them. Pick which one a campaign uses in <b>2 &middot; Illustrate &rarr; Backend</b>.</p>
<p class=hint>Downloads the official standalone package (bundled Python) into <code>vendor/a1111/</code>
with the API already switched on, and points the launcher at it. Already run A1111 elsewhere
(e.g. <code>C:\SD\SDXL</code>)? Skip this — the Illustrate tab&rsquo;s Backend row keeps using yours.
First launch self-installs its dependencies (one-time, several GB).</p>
<hr>
<div class=row>
<b style="min-width:180px">2 &middot; Art model</b>
<input type=password id=civitai_token size=28 placeholder="Civitai API key (needed to download)">
<button class="btn primary" onclick="post('install_checkpoint',{token:document.getElementById('civitai_token').value})">Install MoodyKrea2Mix v4.0</button>
<span id=vendor_model class=hint></span>
</div>
<p class=hint>Downloads <b>MoodyKrea2Mix v4.0</b> &mdash; the campaign&rsquo;s art checkpoint &mdash; into <code>vendor/models/</code>, points the
campaign at it, and launches A1111 with <code>--ckpt-dir vendor/models</code> so it&rsquo;s found wherever this
folder lives. Get a free API key at civitai.com &rarr; account settings. Already have the file? Just drop
the .safetensors into <code>vendor/models/</code> instead.</p>
<hr>
<div class=row>
<b style="min-width:180px">2b &middot; Title font</b>
<button class=btn onclick="post('install_fonts')">Install Arkhamic</button>
<span id=vendor_font class=hint></span>
<span class=hint>the community&rsquo;s OFL extension of Teutonic (the official title face) — from
<a href="https://github.com/javnik36/arkhamic" target=_blank>javnik36/arkhamic</a>; the renderer
prefers it automatically once installed</span>
</div>
<hr>
<div class=row><b>Thanks to</b></div>
<p class=hint>This app is built on work generously shared with the fan community.
<b>Strange Eons</b> by <a href="https://strangeeons.cgjennings.ca" target=_blank>Christopher G. Jennings</a>
&mdash; the card-design tool this whole ecosystem grew around. The <b>Arkham Horror LCG plugin</b> by
<b>jaqenZann</b> (building on <b>Tokeeto</b>&rsquo;s work) &mdash; its authentic frames, regions and
overlays ship inside this folder and every card here is drawn on them. And the <b>SCED</b> team, whose
Tabletop Simulator structure this campaign box is built to match.<br>
Fan project &mdash; free, never for sale. Arkham Horror: The Card Game is &copy; Fantasy Flight Games.</p>
</div></section>

<section id=cards>
<div class=panel><div class=row>
<span class=hint>Every card in the campaign, on its real frame. Click a card to place its art —
drag to position, scroll to size. Encounter cards stay hidden behind the
<b>spoiler shield</b> so building the campaign doesn&rsquo;t spoil playing it.</span>
<span class=spacer></span>
<label><input type=checkbox id=spoilshield checked onchange=refresh()> spoiler shield</label>
<button class=btn onclick="post('render_placeholders')">Compose all faces</button>
<button class=btn onclick="post('inpaint_frames',{dry_run:dry()})"
title="Stable Diffusion regenerates each template's text regions into empty card material (select-and-generate-over); composed faces then sit on real texture instead of flat fills">&#10024; Rebuild blank frames</button>
</div>
<div id=steps_cards class=stepbox></div>
<details class=panel id=defaultfonts style="margin-bottom:10px;padding:10px 16px">
<summary style="cursor:pointer"><b>Default fonts</b> <span class=hint>&mdash; applied to <b>every</b> card; click to open. A single card&rsquo;s own override still wins.</span></summary>
<div class=row style="margin-top:8px">
<label>title / cost</label><select id=df_title onchange=dfSet()></select>
<label>stat numerals</label><select id=df_stat onchange=dfSet()></select>
<label>body text</label><select id=df_body onchange=dfSet()></select>
<button class=btn style="font-size:12px;padding:5px 12px" onclick="document.getElementById('df_fontfile').click()">Upload font&hellip;</button>
<input type=file id=df_fontfile accept=".ttf,.otf" style="display:none" onchange=dfFontUpload(this)>
<span id=df_info class=hint></span>
</div></details>
<div class=row style="margin:6px 0 10px;padding:10px;border:1px solid var(--line);border-radius:9px">
<b style="font-size:12px">New card</b>
<select id=nc_type onchange=ncClassVis()>
<option>Location</option><option>Enemy</option><option>Treachery</option>
<option>Asset</option><option>Event</option><option>Skill</option>
<option>Investigator</option><option>Agenda</option><option>Act</option>
<option>Scenario</option><option>Story</option></select>
<select id=nc_class title="class / faction — only player cards carry a class">
<option value="">class…</option><option>Guardian</option><option>Seeker</option>
<option>Rogue</option><option>Mystic</option><option>Survivor</option>
<option>Neutral</option><option>Mythos</option></select>
<input id=nc_name size=24 placeholder="card name" onkeydown="if(event.key==='Enter')cardNew()">
<button class="btn primary" onclick=cardNew()>+ Create card</button>
<span class=hint>appears instantly on its real template, ready to edit &amp; drag onto a scenario</span>
</div>
<div id=chips_cards class=chips></div>
<div id=cardgroups></div>
<div id=editor>
<div id=ed_sheet>
<div class="row" id=ed_toolbar><button class=btn onclick=edClose()>&#8592; All cards</button>
<b id=ed_title style="font-size:15px"></b>
<span class=hint>drag art in the window &middot; scroll to size &middot; click a text area to edit it in the panel &middot; drag the name / rules box to move it</span>
<span class=spacer></span>
<label>width</label><input type=range id=ed_scale min=0.5 max=6 step=0.02 style="width:120px" oninput=edPreview()>
<label>height</label><input type=range id=ed_scaley min=0.5 max=6 step=0.02 style="width:120px" oninput=edPreview()>
<button class="btn primary" onclick=edSave()>Save</button>
<button class=btn onclick="post('tts_spawn',{card:ed.g.id})"
title="drop this card onto the table of your RUNNING Tabletop Simulator — appears instantly, any game/mod">&#9654; Drop into TTS</button>
<button class=btn onclick=edDelete() style="color:#e06a5a;border-color:rgba(224,106,90,.4)"
title="delete this card (hand-made cards only)">&#128465; Delete</button>
<button class=btn onclick=edClose()>Done</button></div>
<div id=ed_main>
<div id=ed_left>
<div id=ed_stage>
<img id=ed_face><div id=ed_win><img id=ed_art draggable=false></div><img id=ed_furniture><div id=ed_regions></div>
</div>
<div class=row><span class=hint>art for this card — pick one, or bring your own:</span>
<button class=btn style="font-size:12px;padding:5px 12px" onclick="document.getElementById('ed_file').click()">Upload image&hellip;</button>
<button class=btn style="font-size:12px;padding:5px 12px" onclick=edArtRemove()>Remove image</button>
<input type=file id=ed_file accept="image/*" style="display:none" onchange=edUpload(this)>
</div>
<div id=ed_strip></div>
</div>
<div id=ed_side>
<b style="font-size:13px">Selected area</b>
<div style="margin:3px 0 8px"><b id=ty_field style="color:var(--accent)">click an area on the card</b></div>
<div id=ed_side_textwrap style="display:none;margin-bottom:10px">
<label style="display:block;margin-bottom:3px">text</label>
<textarea id=ed_side_text rows=3 spellcheck=false style="width:100%;box-sizing:border-box;resize:vertical" oninput=edSideText()></textarea>
<div class=hint style="margin-top:3px">type here, or drag the box on the card to move it</div>
</div>
<div class=ed_side_grp>
<label>font</label><select id=ty_font onchange=tySet() style="width:100%"></select>
</div>
<div class=ed_side_grp>
<label>size <span id=ty_pct class=stat>100%</span></label>
<input type=range id=ty_size min=0.6 max=1.8 step=0.02 value=1 style="width:100%" oninput="ty_pct.textContent=Math.round(this.value*100)+'%'" onchange=tySet()>
</div>
<div class=row style="gap:12px;margin:2px 0">
<label style="cursor:pointer"><input type=checkbox id=ty_bold onchange=tySet()> <b>B</b></label>
<label style="cursor:pointer"><input type=checkbox id=ty_italic onchange=tySet()> <i>I</i></label>
<label style="cursor:pointer" title="apply this text style to EVERY card, not just this one"><input type=checkbox id=ty_all onchange=tySet()> all cards</label>
</div>
<div class=row style="gap:6px;flex-wrap:wrap;margin-top:4px">
<button class=btn style="font-size:11px;padding:4px 10px" onclick="tyBind('stats')" title="style ALL stat numerals on this card (cost, skills, shroud, doom...)">stat numbers</button>
<button class=btn style="font-size:11px;padding:4px 10px" onclick=tyReset()>Reset style</button>
<button class=btn style="font-size:11px;padding:4px 10px" onclick=edMoveReset() title="return this text box to its authored position">Reset position</button>
</div>
<hr style="margin:10px 0;border-color:rgba(120,150,190,.28)">
<b style="font-size:12px">Card fonts</b>
<span class=hint style="display:block;margin:2px 0 4px">whole-card override &mdash; &ldquo;default&rdquo; follows the official stack</span>
<div class=ed_side_grp><label>title</label><select id=ed_font_title onchange=edFontSet() style="width:100%"></select></div>
<div class=ed_side_grp><label>stat</label><select id=ed_font_stat onchange=edFontSet() style="width:100%"></select></div>
<div class=ed_side_grp><label>body</label><select id=ed_font_body onchange=edFontSet() style="width:100%"></select></div>
<button class=btn style="font-size:12px;padding:5px 12px;margin-top:4px" onclick="document.getElementById('ed_fontfile').click()">Upload font&hellip;</button>
<input type=file id=ed_fontfile accept=".ttf,.otf" style="display:none" onchange=edFontUpload(this)>
</div>
</div>
<div style="margin-top:14px"><h2>Card content <small>type directly — blank returns a field to the authored version; saves affect THIS card only</small></h2>
<div class=row>
<label>name</label><input id=cc_name size=20 onfocus="tyBind('name')">
<label>subtitle</label><input id=cc_subtitle size=16 onfocus="tyBind('subtitle')">
<label>traits</label><input id=cc_traits size=18 onfocus="tyBind('traits')">
</div>
<div class=row id=cc_stats></div>
<div id=cc_props style="margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:8px">
<b style="font-size:12px">Card properties</b>
<span class=hint>class &middot; encounter set &middot; act/agenda numbering &middot; the marks a real card carries &mdash; only what this card type uses is shown</span>
<div class=row id=cc_props_row style="margin-top:6px"></div>
<div id=cc_sigs style="display:none;margin-top:8px">
<b style="font-size:12px">Signature cards</b>
<span class=hint>the cards that always come with this investigator &mdash; pick one of your own cards and how many copies</span>
<div id=sig_rows></div>
<button class=btn style="font-size:11px;padding:4px 10px" onclick=sigAdd()>+ signature card</button>
</div>
</div>
<div id=cc_loc style="display:none;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:8px">
<b style="font-size:12px">Location elements</b> <span class=hint>own symbol &middot; colour &middot; per-investigator clues &middot; connections (all render instantly on save)</span>
<div class=row style="margin-top:6px">
<label>own symbol</label><select id=le_icon></select>
<label>colour</label><input type=color id=le_color value="#25807a" style="width:44px;height:28px;padding:1px;border-radius:6px;border:1px solid var(--line);background:none">
<label style="cursor:pointer"><input type=checkbox id=le_perinv> clues per investigator</label>
</div>
<div id=le_conns></div>
<button class=btn style="font-size:11px;padding:4px 10px" onclick=leAddConn()>+ connection</button>
</div>
<div id=cc_tokens style="display:none;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:8px">
<b style="font-size:12px">Chaos-token rows</b> <span class=hint>the scenario reference table &mdash; token + its modifier text</span>
<div id=tok_rows></div>
<button class=btn style="font-size:11px;padding:4px 10px" onclick=tokAdd()>+ token row</button>
</div>
<div id=cc_log style="display:none;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:8px">
<b style="font-size:12px">Campaign log</b> <span class=hint>who&rsquo;s playing, each investigator and their XP &mdash; the notes box below is the log itself</span>
<div class=row style="margin-top:6px"><label>player</label><input id=cl_player size=18></div>
<div class=row><label>investigator 1</label><input id=cl_investigator1 size=18><label>XP</label><input id=cl_xp1 size=4></div>
<div class=row><label>investigator 2</label><input id=cl_investigator2 size=18><label>XP</label><input id=cl_xp2 size=4></div>
<div class=row><label>investigator 3</label><input id=cl_investigator3 size=18><label>XP</label><input id=cl_xp3 size=4></div>
</div>
<div id=cc_back_wrap style="display:none">
<label>back / deck-building text</label><textarea id=cc_back rows=4 spellcheck=false onfocus="glyphTarget('cc_back')"></textarea>
<label>back flavor</label><textarea id=cc_backflavor rows=2 spellcheck=false onfocus="glyphTarget('cc_backflavor')"></textarea>
</div>
<div class=row id=ed_symbols style="margin:2px 0 4px;gap:5px;flex-wrap:nowrap;overflow-x:auto;align-items:center">
<span class=hint>insert symbol&nbsp;&mdash;&nbsp;click into rules/flavor first:</span></div>
<label>rules text</label><textarea id=cc_text rows=5 spellcheck=false onfocus="tyBind('text');glyphTarget('cc_text')"></textarea>
<label>flavor</label><textarea id=cc_flavor rows=2 spellcheck=false onfocus="tyBind('flavor');glyphTarget('cc_flavor')"></textarea>
<div class=row style="margin-top:6px">
<span class=hint>use <b>Save</b> at the top — it saves the text, the art and the layout together</span>
<span id=cc_info class=hint></span>
</div></div>
<details id=ed_promptbox style="margin-top:12px">
<summary style="cursor:pointer;color:var(--dim)">Prompt &mdash; generate art for THIS card (A1111-style boxes)</summary>
<label>prompt</label><textarea id=ed_pos rows=3 spellcheck=false></textarea>
<label>negative prompt</label><textarea id=ed_neg rows=2 spellcheck=false></textarea>
<div class=row style="margin-top:6px">
<button class="btn primary" onclick=edGenerate()>Generate 2 variants</button>
<button class=btn onclick=edReroll() title="same prompt, brand-new seeds — different images every click">&#127922; Reroll (new seeds)</button>
<button class=btn onclick=edPromptSave()>Save prompt</button>
<button class=btn onclick=edPromptReset()>Reset to composed</button>
<span id=ed_prompt_info class=hint></span>
</div>
<p class=hint>Pre-filled with the composed prompt (character + scene + card-type framing + house style).
Edit and Save &mdash; batch runs use your version too. Reset returns to the composed default.
New variants land in the strip above and the gallery when the job finishes.</p>
</details>
</div></div>
</div></section>

<section id=illustrate><div class=panel>
<div id=steps_illustrate class=stepbox></div>
<hr>
<div class=row>
<b>Backend</b>
<select id=rig_kind onchange="post('backend_set',{backend:this.value}).then(()=>refresh())"
title="A1111 runs SD1.5/SDXL checkpoints. Krea 2 / FLUX-family models need ComfyUI.">
<option value=a1111>A1111 (SD1.5 / SDXL)</option>
<option value=comfy>ComfyUI (Krea 2 / FLUX)</option></select>
<label>folder</label><input type=text id=rig_cwd size=22 placeholder="C:\SD\SDXL" onchange=rigSave()>
<label>start with</label><input type=text id=rig_cmd size=18 onchange=rigSave()>
<button class="btn primary" onclick=rigLaunch()>&#9655; Launch backend</button>
<button class=btn onclick="post('backend_check')">Check</button>
</div>
<div class=row style="background:var(--surface2);border:1px solid var(--line);border-radius:12px;padding:10px 14px">
<b>Checkpoint</b>
<select id=model onchange=modelSet() style="max-width:340px">
<option value="">&mdash; start the backend, then &#8635; &mdash;</option></select>
<button class=btn onclick=modelsLoad() title="ask the running backend which checkpoints it has">&#8635; Refresh</button>
<span id=modelinfo class=hint></span>
</div>
<p id=model_active class=hint style="margin:4px 0 8px"></p>
<details style="margin:6px 0">
<summary style="cursor:pointer;color:var(--dim)">House style &mdash; the ART_SPEC block every batch prompt ends with</summary>
<div class=row style="margin-bottom:6px">
<label>style LoRA</label><input type=text id=style_lora size=26 placeholder="filename without .safetensors">
<label>weight</label><input type=number id=style_lw step=0.05 min=0 max=2 style="width:75px" value=0.8>
<label>trigger</label><input type=text id=style_trig size=18 placeholder="trigger words, if any">
</div>
<p class=hint style="margin:0 0 6px">A style LoRA here is applied to <b>every</b> card in the campaign,
so the whole set matches. Per-character LoRAs (Illustrate &rarr; Characters) still stack on top.</p>
<label>style (appended to every prompt)</label><textarea id=style_pos rows=2 spellcheck=false></textarea>
<label>negative (start of every negative prompt)</label><textarea id=style_neg rows=2 spellcheck=false></textarea>
<div class=row style="margin-top:6px"><button class=btn onclick=styleSave()>Save house style</button>
<span class=hint>per-card prompts live in each card&rsquo;s editor (Cards tab)</span></div>
</details>
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
<label title="rehearsal mode: writes tiny grey stub images instead of using the GPU"><input type=checkbox id=dryrun> dry-run (test without GPU)</label>
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
<span class=legend>dry-run stubs are hidden automatically</span>
</div>
<div id=chips_gal class=chips></div>
<div id=gallery class=gal></div>
</div></section>

<section id=apply><div class=panel>
<div id=steps_apply class=stepbox></div>
<hr>
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
let seq=0, cur='setup', ed=null, ST=null;
window.revealed=window.revealed||new Set();
function tab(t){cur=t;for(const x of ['setup','cards','illustrate','apply','scenarios','advanced']){
document.getElementById(x).classList.toggle('on',x===t);
document.getElementById('tab-'+x).classList.toggle('on',x===t);}
if(t==='illustrate'&&!modelsLoadedOnce){modelsLoadedOnce=true;modelsLoad();}}
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
o.text=j.current+' (not on backend!)';o.selected=true;sel.add(o);}
const el=document.getElementById('model_active');
if(!j.ok){el.innerHTML='&#9888; backend not reachable — Launch it above, then hit &#8635;';}
else{const match=j.active&&j.current&&(j.active===j.current||j.active.startsWith(j.current)||j.current.startsWith(j.active.split(' ')[0]));
el.innerHTML='backend has loaded: <b>'+(j.active||'?')+'</b> &middot; every generation forces: <b>'+(j.current||'?')+'</b>'+
(match?' &#10003;':' — generations will switch it to yours automatically');}}
let modelsLoadedOnce=false;
function modelSet(){const v=document.getElementById('model').value;
if(v)post('model_set',{checkpoint:v});}
function styleSave(){post('style_save',{
style_lora:document.getElementById('style_lora').value,
style_lora_weight:parseFloat(document.getElementById('style_lw').value)||0.8,
style_trigger:document.getElementById('style_trig').value,
style_positive:document.getElementById('style_pos').value,
style_negative:document.getElementById('style_neg').value});}
let ADV_COMPOSED=null;
async function advLoad(){const card=document.getElementById('adv_card').value;
ADV_COMPOSED=null;const info=document.getElementById('adv_info');
if(!card){info.textContent='';return;}
const j=await post('prompt_get',{card});
if(!j.ok){info.textContent='this face is text-only (no illustration)';
document.getElementById('adv_pos').value='';document.getElementById('adv_neg').value='';return;}
ADV_COMPOSED={positive:j.positive,negative:j.negative};
document.getElementById('adv_pos').value=(j.override&&j.override.positive)||j.positive;
document.getElementById('adv_neg').value=(j.override&&j.override.negative)||j.negative;
info.textContent='base seed '+j.seed+' · '+j.checkpoint;}
async function advGenerate(){const card=document.getElementById('adv_card').value;
if(!card){addlog('pick a card first');return;}
const p=document.getElementById('adv_pos').value.trim(),
n=document.getElementById('adv_neg').value.trim();
await post('prompt_save',{card,
positive:ADV_COMPOSED&&p===ADV_COMPOSED.positive.trim()?'':p,
negative:ADV_COMPOSED&&n===ADV_COMPOSED.negative.trim()?'':n});
await post('generate',{only:card,dry_run:dry(),
variants:parseInt(document.getElementById('adv_variants').value)||2,
reroll:document.getElementById('adv_reroll').checked,
steps:document.getElementById('adv_steps').value,
cfg:document.getElementById('adv_cfg').value,
sampler:document.getElementById('adv_sampler').value});}
function genSave(){post('gen_settings',{steps:document.getElementById('gen_steps').value,
cfg:document.getElementById('gen_cfg').value,
sampler:document.getElementById('gen_sampler').value});}
function loraSave(){const chars={};
for(const row of document.querySelectorAll('#lora_rows [data-char]')){
const c=row.getAttribute('data-char');chars[c]=chars[c]||{};
chars[c][row.getAttribute('data-field')]=row.value;}
post('lora_save',{characters:chars});}
let ZOOMFN=null;
function zoomOpen(src,cap,actLabel,actFn){ZOOMFN=actFn||null;
document.getElementById('zoom_img').src=src;
document.getElementById('zoom_cap').textContent=cap||'';
const b=document.getElementById('zoom_act');
b.textContent=actLabel||'';b.style.display=actLabel?'':'none';
document.getElementById('zoom').style.display='flex';}
function zoomClose(){document.getElementById('zoom').style.display='none';ZOOMFN=null;}
function zoomDo(){const f=ZOOMFN;zoomClose();if(f)f();}
function openEditor(id){const c=((LS&&LS.cards)||[]).find(x=>x.id===id);
if(!c){addlog('open the Cards tab for '+id);return;}
tab('cards');editArt(c);}
async function useAndEdit(id,v){await post('choose',{card:id,file:v});
const c=((LS&&LS.cards)||[]).find(x=>x.id===id);
if(c){tab('cards');editArt(Object.assign({},c,{chosen:v,face:true}));}}
document.addEventListener('keydown',e=>{if(e.key==='Escape')zoomClose();});
// last campaign the owner had open, so the app reopens it instead of always
// dumping you back in the finished Still Hour set
let START_CAMP='';try{START_CAMP=localStorage.getItem('cf_campaign')||'';}catch(_){}
let CAMP_INIT=false;
function camp(){return document.getElementById('campaign').value||START_CAMP||'still_hour'}
function campPick(){const v=document.getElementById('campaign').value;
START_CAMP=v;try{localStorage.setItem('cf_campaign',v);}catch(_){}
if(typeof ed!=='undefined'&&ed)edClose();refresh();}
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

let GROUP='All', LS=null;
const GROUP_ORDER=['Investigators','Signatures & Weaknesses','Recollections','Scenario cards',
'Encounter — The Appointed','Encounter — The Named'];
function setGroup(g){GROUP=g;if(LS)renderAll(LS);}
function renderChips(s){
const present=GROUP_ORDER.filter(g=>s.cards.some(c=>c.group===g));
const html=['All'].concat(present).map(g=>
`<button class="chip${g===GROUP?' on':''}" onclick="setGroup('${g.replace(/'/g,"\\'")}')">${g}</button>`).join('');
for(const id of ['chips_cards','chips_gal']){
const el=document.getElementById(id);if(el)el.innerHTML=html;}}
function renderCards(s){
const groups={};
for(const c of s.cards)if(GROUP==='All'||c.group===GROUP)
(groups[c.group]=groups[c.group]||[]).push(c);
document.getElementById('cardgroups').innerHTML=GROUP_ORDER.filter(g=>groups[g]).map(g=>
`<h2>${g}<small>${groups[g].length} card${groups[g].length>1?'s':''}</small></h2>`+
`<div class=grid>${groups[g].map(cardTile).join('')}</div>`).join('')
||'<span class=hint>no cards in this category</span>';}

function galleryTile(g,s,nameOf){
const shield=document.getElementById('spoilshield').checked;
if(shield&&g.spoiler&&!window.revealed.has(g.id))
 return `<div class=card style="width:150px"><div class=cid>&#128274; encounter card</div>`+
 `<div class=veil style="height:110px;border-radius:6px;display:flex;align-items:center;`+
 `justify-content:center;font-size:11px;color:var(--dim);cursor:pointer;`+
 `background:repeating-linear-gradient(45deg,#15151d,#15151d 8px,#1b1b25 8px,#1b1b25 16px)" `+
 `onclick="window.revealed.add('${g.id}');refresh()">tap to reveal</div></div>`;
const real=g.variants.filter(v=>!(g.stubs||[]).includes(v));
return `<div class=card style="width:150px"><div class=cid title="${g.id}">${nameOf[g.id]||g.id}</div>`+
(g.face?`<img style="outline:2px solid var(--good)" title="composed card — click to adjust art placement" `+
`src="/art?p=art/faces/${g.id}.png&ts=${ST}" `+
`onclick="zoomOpen(this.src,'${g.id} — composed face','Move / resize art',()=>openEditor('${g.id}'))">`:'')+
real.map(v=>`<img loading=lazy class="${v===g.chosen?'chosen':''}" title="click to view large" `+
`src="/art?p=out/${s.campaign}/${g.id}/${v}" `+
`onclick="zoomOpen(this.src,'${g.id} — ${v}','Use on this card &amp; place it',()=>useAndEdit('${g.id}','${v}'))">`).join('')+
(!real.length?`<div class=hint style="font-size:11px">no real art yet`+
((g.stubs||[]).length?' (dry-run stubs hidden)':'')+`</div>`:'')+
`</div>`;}
function renderGallery(s){
const groupOf={};for(const c of s.cards)groupOf[c.id]=c.group;
const nameOf={};for(const c of s.cards)nameOf[c.id]=c.name;
const groups={};
for(const g of s.gallery){const grp=groupOf[g.id]||'Other';
if(GROUP==='All'||grp===GROUP)(groups[grp]=groups[grp]||[]).push(g);}
document.getElementById('gallery').innerHTML=
GROUP_ORDER.concat(['Other']).filter(x=>groups[x]).map(x=>
`<div style="width:100%"><h2>${x}<small>${groups[x].length}</small></h2></div>`+
groups[x].sort((a,b)=>a.id.localeCompare(b.id)).map(g=>galleryTile(g,s,nameOf)).join('')).join('')
||'<span class=hint>nothing in this category yet — run Step 0 &middot; Seeds, then a batch</span>';}
function step(done,html){return `<div class="step${done?' done':''}">`+
`<span class=n>${done?'&#10003;':''}</span><span>${html}</span></div>`;}
function renderSteps(s){
const v=s.vendor||{},cov=(s.se&&s.se.coverage)||{framed:[],total:0};
const hasModel=(v.models||[]).length>0||(s.checkpoint&&s.checkpoint!=='SET_ME.safetensors');
const seedsDone=Object.keys(s.seeds||{}).length>0;
const picksDone=seedsDone&&Object.values(s.seeds).every(x=>x.picked);
const gen=s.report&&s.report.generated>0&&!s.report.dry_run;
const allFramed=cov.total>0&&cov.framed.length===cov.total;
const el=(id,html)=>{const e=document.getElementById(id);if(e)e.innerHTML=html;};
el('steps_setup',
 step(v.a1111_installed||v.comfy_installed,'<b>1.</b> Install a backend into this folder — A1111, or ComfyUI for Krea 2 / FLUX checkpoints — skip if you already run one elsewhere')+
 step(hasModel,'<b>2.</b> Install the art model (needs a free Civitai API key), or drop your .safetensors into <code>vendor/models/</code>')+
 step(false,'Then work the tabs left to right: <b>2 &middot; Illustrate</b> &rarr; <b>3 &middot; Cards</b> &rarr; <b>4 &middot; Campaign / scenarios</b> &rarr; <b>5 &middot; Play in TTS</b>'));
el('steps_cards',
 step(true,'<b>Pick a category</b> below, click a card to open it')+
 step(true,'<b>Drag</b> the art to position, <b>scroll</b> to size, <b>Save</b> — the placement is kept and used by every export')+
 step(true,'Cards render here onto the plugin&rsquo;s own frames — what you see is what goes into TTS'));
el('steps_illustrate',
 step(false,'<b>1.</b> <b>&#9655; Launch backend</b>, wait for the drawer to say it&rsquo;s up, then hit <b>&#8635;</b> on the Checkpoint row and pick <b>MoodyKrea2Mix</b> — the line below tells you what the backend actually has loaded')+
 step(seedsDone,'<b>2.</b> <b>Step 0 · Seeds</b> — 4 portrait candidates per investigator appear below')+
 step(picksDone,'<b>3.</b> Click each investigator&rsquo;s best portrait &rarr; <b>Make canonical</b>')+
 step(gen,'<b>4.</b> <b>Starter batch</b> to check the look &rarr; then <b>&#9889; Auto-build ALL</b> (top right) does every card')+
 step(true,'<b>5.</b> Don&rsquo;t like a result? Open the card in <b>3 &middot; Cards</b> &rarr; &#127922; Reroll gives new takes'));
el('steps_apply',
 step(false,'<b>1.</b> <b>Compose cards &amp; Export to TTS</b> — writes local file:/// art and rebuilds the mod')+
 step(false,'<b>2.</b> Copy <code>dist/the_still_hour_mod.json</code> to <code>Documents/My Games/Tabletop Simulator/Saves/</code>')+
 step(false,'<b>3.</b> In TTS: Games &rarr; Save &amp; Load &rarr; THE STILL HOUR (Run Tests on the Control token should pass 23/23)'));}
function renderAll(s){renderChips(s);renderCards(s);renderGallery(s);renderSteps(s);}
async function refresh(){const r=await fetch('/api/status?campaign='+camp());const s=await r.json();
ST=s.faces_ver;
const sel=document.getElementById('campaign');
if(sel.options.length!==s.campaigns.length){sel.innerHTML='';
for(const c of s.campaigns){const o=document.createElement('option');o.value=o.text=c;
if(c===s.campaign)o.selected=true;sel.add(o);}}
// header subtitle follows the campaign you're actually in, not a fixed title
{const hs=document.getElementById('hdr_sub');
if(hs)hs.textContent=((s.campaign_name||s.campaign||'')+' · fan content');}
// first paint only: land on the remembered campaign, or the server's default
// (newest non-Still-Hour) — never override a live manual switch afterwards
if(!CAMP_INIT){CAMP_INIT=true;
let want=(START_CAMP&&s.campaigns.includes(START_CAMP))?START_CAMP:(s.default_campaign||s.campaign);
if(want&&s.campaigns.includes(want)&&want!==s.campaign){
START_CAMP=want;sel.value=want;return refresh();}}
document.getElementById('busydot').className='dot'+(s.busy?' busy':'');
const kind=s.backend||'a1111';{const rk=document.getElementById('rig_kind');if(rk&&document.activeElement!==rk)rk.value=kind;}
const rg=(s.rig||{})[kind]||{};
for(const [id,val] of [['rig_cwd',rg.cwd||''],['rig_cmd',rg.command||'']]){
const el=document.getElementById(id);if(el&&document.activeElement!==el)el.value=val;}
document.getElementById('modelinfo').innerHTML=s.checkpoint?
('current: <b>'+s.checkpoint+'</b>'+(s.checkpoint==='SET_ME.safetensors'?
' — load the list and pick your model':'')):'';
for(const [id,val] of [['style_pos',(s.style||{}).positive||''],
['style_neg',(s.style||{}).negative||''],
['style_lora',(s.style||{}).lora||''],
['style_lw',(s.style||{}).lora_weight||0.8],
['style_trig',(s.style||{}).trigger||''],
['gen_steps',(s.gen||{}).steps||''],['gen_cfg',(s.gen||{}).cfg||''],
['gen_sampler',(s.gen||{}).sampler||'']]){
const el=document.getElementById(id);if(el&&document.activeElement!==el)el.value=val;}
const advSel=document.getElementById('adv_card');
if(advSel&&advSel.options.length<=1){
for(const grp of GROUP_ORDER){const cards=s.cards.filter(c=>c.group===grp);
if(!cards.length)continue;
const og=document.createElement('optgroup');og.label=grp;
for(const c of cards){const o=document.createElement('option');
o.value=c.id;o.text=(c.spoiler?'🔒 ':'')+c.name;og.appendChild(o);}
advSel.appendChild(og);}}
const lr=document.getElementById('lora_rows');
if(lr&&!lr.contains(document.activeElement)){
lr.innerHTML=Object.entries(s.characters||{}).map(([n,c])=>
`<div class=row style="margin-bottom:4px">`+
`<b style="min-width:90px;text-transform:capitalize">${n}</b>`+
`<label>LoRA</label><input type=text size=22 data-char="${n}" data-field=lora value="${(c.lora||'').replace(/"/g,'&quot;')}" placeholder="none trained yet">`+
`<label>strength</label><input type=number step=0.05 min=0 max=2 style="width:75px" data-char="${n}" data-field=weight value="${c.weight}">`+
`<label>trigger</label><input type=text size=18 data-char="${n}" data-field=trigger value="${(c.trigger||'').replace(/"/g,'&quot;')}">`+
`</div>`).join('');}
const bd=s.build||{};const be=document.getElementById('build');
if(be){be.innerHTML='v'+(bd.version||'?')+(bd.commit?(' · '+bd.commit):'')+
' · built '+(bd.built||'?');
be.title='Running build: v'+(bd.version||'?')+' commit '+(bd.commit||'?')+
', file dated '+(bd.built||'?')+', server started '+(bd.started||'?')+
'. A git pull does NOT change the running app — restart it, then hard-refresh (Ctrl+F5).';}
const v=s.vendor||{};
const fs=v.fonts||{};const fe=document.getElementById('vendor_font');
if(fe)fe.innerHTML=(fs.arkhamic||[]).length?
('<span class=okpill>&#10003; installed: '+fs.arkhamic.join(', ')+'</span>'):
((fs.teutonic||[]).length?'<span class=warnpill>using Teutonic &mdash; click to add Arkhamic</span>':
'not installed yet');
const pl=v.plugin||{};const pe=document.getElementById('vendor_plugin');
if(pe)pe.innerHTML=(pl.templates&&pl.regions)?
('<span class=okpill>&#10003; '+pl.templates+' frames, '+pl.overlays+' overlays, '+pl.icons+
' icons, '+pl.regions+' regions extracted</span>'):
'<span class=badpill>&#10007; frames missing &mdash; click Re-extract</span>';
const _set=(id,html)=>{const e=document.getElementById(id);if(e)e.innerHTML=html;};
_set('vendor_a1111',v.a1111_installed?
'<span class=okpill>&#10003; installed &amp; verified in vendor/a1111</span>':
(v.a1111_partial?'<span class=badpill>&#10007; install incomplete &mdash; vendor/a1111 exists but has no usable webui; click Install again</span>':
'not installed (fine if you already run A1111 elsewhere)'));
_set('vendor_comfy',v.comfy_installed?
'<span class=okpill>&#10003; installed &amp; verified in vendor/comfy</span>':
(v.comfy_partial?'<span class=badpill>&#10007; install incomplete &mdash; vendor/comfy exists but has no usable ComfyUI; click Install again</span>':
(v.comfy_windows_only?'<span class=warnpill>Windows only for now &mdash; on this OS install ComfyUI yourself and point the Backend row at it</span>':
'not installed (fine if you already run ComfyUI elsewhere)')));
const _cb=document.getElementById('btn_comfy');
if(_cb)_cb.disabled=!!v.comfy_windows_only;
_set('vendor_model',(v.models||[]).length?
'<span class=okpill>&#10003; installed: '+v.models.join(', ')+'</span>':
(v.has_token?'<span class=warnpill>key saved &mdash; ready to install</span>':'not installed yet'));
_set('vendor_se',v.se_installed?
'<span class=okpill>&#10003; installed at '+v.se_path+'</span>':
((v.se_downloads||[]).length?
'<span class=warnpill>downloaded: '+v.se_downloads.join(', ')+' &mdash; run the installer to finish</span>':
'not installed yet'));
const lj=s.last_job||{};
const bt=document.getElementById('busytext');
if(s.busy){bt.textContent='working…';bt.className='';}
else if(lj.state==='failed'){bt.innerHTML='<span class=badpill>'+(lj.name||'job')+' failed</span>';}
else{bt.textContent='idle';bt.className='';}
const je=document.getElementById('joberr');
if(je){if(!s.busy&&lj.state==='failed'&&lj.error){
je.style.display='block';
je.innerHTML='<b>'+(lj.name||'job')+' failed:</b> '+String(lj.error).replace(/</g,'&lt;')+
' <span class=hint>(full details in Activity, bottom of the page)</span>';}
else je.style.display='none';}
renderCards(s);
const rep=s.report.generated!==undefined?
`<span class=stat>generated <b>${s.report.generated}</b></span>`+
`<span class=stat>failed <b style="color:${s.report.failed?'var(--bad)':'var(--good)'}">${s.report.failed}</b></span>`+
(s.report.dry_run?'<span class=stat>dry-run</span>':'')+
(s.report.warnings||[]).map(w=>`<div class=hint>&#9888; ${w}</div>`).join(''):
'<span class=stat>no batch run yet</span>';
document.getElementById('repline').innerHTML=rep;
LS=s;renderChips(s);renderGallery(s);
if(!['df_title','df_stat','df_body'].includes((document.activeElement||{}).id))dfFill();
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
const cov=(s.se&&s.se.coverage)||{framed:[],total:0};
document.getElementById('applyinfo').innerHTML=
`<span class=stat>faces ready: <b>${cov.framed.filter(f=>!f.endsWith('-back')).length}</b></span>`;}

async function editArt(c){
if(!c.face){await post('compose_one',{card:c.id});c.face=true;}
ed={g:c,scale:(c.placement||{scale:1}).scale,ox:(c.placement||{ox:0}).ox,
oy:(c.placement||{oy:0}).oy,natW:0,natH:0,disp:1};
const[cw,ch,x0,y0,x1,y1]=c.artbox;
// half the old size — the card sits beside the properties panel now
const disp=Math.min(1,410/cw);ed.disp=disp;
const stage=document.getElementById('ed_stage');
stage.style.width=(cw*disp)+'px';stage.style.height=(ch*disp)+'px';
const face=document.getElementById('ed_face');
face.src='/art?p=art/faces/'+c.id+'.png&ts='+Date.now();
face.style.width=(cw*disp)+'px';
const win=document.getElementById('ed_win');
win.style.left=(x0*disp)+'px';win.style.top=(y0*disp)+'px';
win.style.width=((x1-x0)*disp)+'px';win.style.height=((y1-y0)*disp)+'px';
const furn=document.getElementById('ed_furniture');
furn.style.width=(cw*disp)+'px';furn.style.display='none';
face.style.display='block';  // shown as the placeholder until furniture loads
document.getElementById('ed_title').textContent=c.name;
document.getElementById('ed_scale').value=ed.scale;
for(const [id,cur] of [['ed_font_title',(c.fonts||{}).title||''],
['ed_font_stat',(c.fonts||{}).stat||''],
['ed_font_body',(c.fonts||{}).body||'']]){
fillFontSel(id,cur);}
document.getElementById('ed_scale').value=ed.scale;
document.getElementById('ed_scaley').value=(c.placement||{}).scale_y||ed.scale;
ccFill(c);
document.getElementById('ty_all').checked=false;tyBind('name');
edStrip();edLoadArt();edPromptLoad(c.id);edRegions();edFurnitureRefresh();
document.getElementById('chips_cards').style.display='none';
document.getElementById('cardgroups').style.display='none';
document.getElementById('editor').style.display='block';
window.scrollTo({top:0});}
let CC_NUM=[];
function ccPips(f,v){const el=document.getElementById('ccp_'+f);if(!el)return;
const n=parseInt(v)||0;
el.textContent=(f==='damage'?'\u2764\ufe0f':'\ud83e\udde0').repeat(Math.max(0,Math.min(n,5)));}
function ccStep(f,d){const el=document.getElementById('cc_'+f);
const cap=(f==='damage'||f==='horror')?5:99;
let v=parseInt(el.value);if(isNaN(v))v=0;v=Math.max(0,Math.min(cap,v+d));el.value=v;ccPips(f,v);}
function ccNum(f,label,pips){
// left-click the value to add 1, right-click to take 1 away — you can still
// type straight into it
return `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px">`+
`<label>${label}</label>`+
`<input id=cc_${f} class=stepper style="width:52px;text-align:center;cursor:pointer" `+
`title="left-click +1 · right-click −1 · or type" `+
`oninput="ccPips('${f}',this.value)" `+
`onclick="ccStep('${f}',1)" `+
`oncontextmenu="ccStep('${f}',-1);return false">`+
(pips?`<span id=ccp_${f} style="font-size:15px;letter-spacing:1px"></span>`:'')+
`</span>`;}
function ccFill(c){const ct=c.content||{};
document.getElementById('cc_name').value=ct.name||'';
document.getElementById('cc_subtitle').value=ct.subtitle||'';
document.getElementById('cc_traits').value=ct.traits||'';
document.getElementById('cc_text').value=ct.text||'';
document.getElementById('cc_flavor').value=ct.flavor||'';
const t=c.type;let defs=[];
if(t==='Investigator')defs=[['wil','[wil]'],['int','[int]'],['com','[com]'],['agi','[agi]'],['health','health'],['sanity','sanity']];
else if(t==='Enemy')defs=[['fight','fight'],['health','health'],['evade','evade'],['damage','damage',1],['horror','horror',1]];
else if(t==='Asset')defs=[['cost','cost'],['level','level'],['health','health'],['sanity','sanity'],['victory','victory']];
else if(t==='Event')defs=[['cost','cost'],['level','level'],['victory','victory']];
else if(t==='Location')defs=[['shroud','shroud'],['clues','clues'],['victory','victory']];
else if(t==='Agenda')defs=[['doom','doom']];
else if(t==='Act')defs=[['clues','clues']];
else if(t==='Scenario'||t==='Story'||t==='Treachery'||t==='Skill')defs=[];
else defs=[['level','level'],['victory','victory']];
CC_NUM=defs.map(d=>d[0]);
document.getElementById('cc_stats').innerHTML=defs.map(d=>ccNum(d[0],d[1],d[2])).join('');
for(const f of CC_NUM){const el=document.getElementById('cc_'+f);
el.value=(ct[f]===null||ct[f]===undefined)?'':ct[f];ccPips(f,el.value);}
document.getElementById('cc_info').textContent=
(c.overridden&&c.overridden.length)?('edited: '+c.overridden.join(', ')):'';
// per-type panels: location elements / chaos-token rows / investigator back
document.getElementById('cc_loc').style.display=(t==='Location')?'block':'none';
document.getElementById('cc_tokens').style.display=(t==='Scenario')?'block':'none';
document.getElementById('cc_back_wrap').style.display=(t==='Investigator')?'block':'none';
if(t==='Location'){
  const SYMS_L=['circle','square','triangle','diamond','moon','star','heart','hourglass','cross','quote','slash','doubleslash','spade','clover','t'];
  const sel=document.getElementById('le_icon');sel.innerHTML='<option value="">—</option>';
  for(const n of SYMS_L){const o=document.createElement('option');o.value=o.text=n;sel.add(o);}
  sel.value=String(ct.icons||'').toLowerCase();
  const N2H={red:'#960e12',orange:'#b85418',yellow:'#be9428',green:'#2c663c',teal:'#1a605e',blue:'#204884',purple:'#5c246e',pink:'#a83870',brown:'#6c482e',grey:'#625e64',gray:'#625e64',gold:'#aa8e46'};
  const col=N2H[String(ct.color||'').toLowerCase()]||String(ct.color||'');
  document.getElementById('le_color').value=/^#[0-9a-fA-F]{6}$/.test(col)?col:'#25807a';
  document.getElementById('le_perinv').checked=!!ct.clues_per_investigator;
LE_CONNS=(ct.connections||[]).map(x=>{const o=typeof x==='string'?{symbol:x,color:''}:{symbol:x.symbol||'',color:x.color||''};
o.symbol=String(o.symbol).toLowerCase();o.color=N2H[String(o.color).toLowerCase()]||o.color;return o;});

  leDraw();}
if(t==='Scenario'){TOK_ROWS=(ct.tokens||[]).map(x=>({token:x.token||'',text:x.text||''}));tokDraw();}
if(t==='Investigator'){document.getElementById('cc_back').value=ct.back_text||'';
document.getElementById('cc_backflavor').value=ct.back_flavor||'';}
document.getElementById('cc_log').style.display=(t==='CampaignLog')?'block':'none';
if(t==='CampaignLog')for(const f of LOG_F)document.getElementById('cl_'+f).value=ct[f]||'';
ccPropsDraw(t,ct);}
// ---- card properties: everything an official card carries beyond its stats.
// Per type, so a Location editor never shows "elite" and an Act never shows
// "cost". Nothing here needs a JSON edit any more.
const CLASSES=['Guardian','Seeker','Rogue','Mystic','Survivor','Neutral','Mythos'];
const CC_PROPS={
Investigator:[['class','class','sel',CLASSES],
  ['deck','ArkhamDB deck id','txt'],
  ['elderSign','elder sign [elder] effect','txt']],
Asset:[['class','class','sel',CLASSES],['uses','uses (e.g. 3 supplies)','txt'],
  ['memoryCost','memory cost','num'],['permanent','permanent','chk']],
Event:[['class','class','sel',CLASSES],['memoryCost','memory cost','num']],
Skill:[['class','class','sel',CLASSES],['wildIcons','wild icons','num'],
  ['memoryCost','memory cost','num']],
Enemy:[['class','class','sel',CLASSES],['encounter','encounter set','txt'],
  ['quantity','copies in deck','num'],['elite','elite','chk'],
  ['unique','unique','chk'],['weakness','weakness','chk']],
Treachery:[['class','class','sel',CLASSES],['encounter','encounter set','txt'],
  ['quantity','copies in deck','num'],['weakness','weakness','chk']],
Story:[['class','class','sel',CLASSES],['encounter','encounter set','txt'],
  ['quantity','copies in deck','num']],
Agenda:[['index','prints as “Agenda …”','txt'],
  ['number','encounter number (1/9)','txt']],
Act:[['index','prints as “Act …”','txt'],
  ['number','encounter number (2/9)','txt']],
Scenario:[['number','encounter number','txt'],
  ['difficulty','difficulty line','txt']],
CampaignLog:[['campaign_name','campaign name','txt']],
Location:[]};
let CC_PROP_F=[];
function ccPropsDraw(t,ct){
const defs=CC_PROPS[t]||[];CC_PROP_F=defs;
const wrap=document.getElementById('cc_props');
wrap.style.display=(defs.length||t==='Investigator')?'block':'none';
document.getElementById('cc_sigs').style.display=
(t==='Investigator')?'block':'none';
if(t==='Investigator'){SIG_ROWS=[];
for(const grp of (ct.signatures||[]))
for(const k in (grp||{}))SIG_ROWS.push({id:k,n:grp[k]});
sigDraw();}
document.getElementById('cc_props_row').innerHTML=defs.map(d=>{
const[f,label,kind,opts]=d;const v=ct[f];
if(kind==='chk')return `<label style="cursor:pointer;margin-right:14px">`+
`<input type=checkbox id=cp_${f} ${v?'checked':''}> ${label}</label>`;
if(kind==='sel')return `<span style="margin-right:12px"><label>${label}</label> `+
`<select id=cp_${f}>`+['<option value="">—</option>',
...opts.map(o=>`<option ${String(v)===o?'selected':''}>${o}</option>`)].join('')+
`</select></span>`;
if(kind==='num')return `<span style="margin-right:12px"><label>${label}</label> `+
`<input id=cp_${f} value="${v===0||v?v:''}" style="width:56px;text-align:center"></span>`;
return `<span style="margin-right:12px"><label>${label}</label> `+
`<input id=cp_${f} value="${String(v==null?'':v).replace(/"/g,'&quot;')}" size=18></span>`;
}).join('');}
let SIG_ROWS=[];
function sigDraw(){
const pick=((LS&&LS.cards)||[]).filter(c=>
['Asset','Event','Skill','Treachery'].indexOf(c.type)>=0);
document.getElementById('sig_rows').innerHTML=SIG_ROWS.map((r,i)=>
`<div class=row style="margin-top:4px"><select onchange="SIG_ROWS[${i}].id=this.value">`+
['<option value="">— pick a card —</option>',
 ...pick.map(c=>`<option value="${c.id}" ${r.id===c.id?'selected':''}>`+
 `${String(c.name).replace(/</g,'&lt;')} (${c.type})</option>`),
 (r.id&&!pick.some(c=>c.id===r.id))?`<option value="${r.id}" selected>${r.id}</option>`:''
].join('')+`</select>`+
`<label>copies</label><input value="${r.n||1}" style="width:44px;text-align:center" `+
`onchange="SIG_ROWS[${i}].n=this.value">`+
`<button class=btn style="font-size:11px;padding:3px 9px" `+
`onclick="SIG_ROWS.splice(${i},1);sigDraw()">&times;</button></div>`).join('');}
function sigAdd(){if(SIG_ROWS.length<12){SIG_ROWS.push({id:'',n:1});sigDraw();}}
const LOG_F=['player','investigator1','xp1','investigator2','xp2','investigator3','xp3'];
let LE_CONNS=[],TOK_ROWS=[];
function leDraw(){const SY=['circle','square','triangle','diamond','moon','star','heart','hourglass','cross','quote','slash','doubleslash','spade','clover','t'];
document.getElementById('le_conns').innerHTML=LE_CONNS.map((c,i)=>
`<div class=row style="margin-top:4px"><label>#${i+1}</label>`+
`<select onchange="LE_CONNS[${i}].symbol=this.value">`+
['<option value="">—</option>',...SY.map(n=>`<option ${c.symbol===n?'selected':''}>${n}</option>`)].join('')+
`</select><input type=color value="${/^#[0-9a-fA-F]{6}$/.test(c.color)?c.color:'#b09b4a'}" `+
`onchange="LE_CONNS[${i}].color=this.value" style="width:40px;height:26px;padding:1px;border-radius:6px;border:1px solid var(--line);background:none">`+
`<button class=btn style="font-size:11px;padding:3px 9px" onclick="LE_CONNS.splice(${i},1);leDraw()">&times;</button></div>`).join('');}
function leAddConn(){if(LE_CONNS.length<6){LE_CONNS.push({symbol:'circle',color:'#b09b4a'});leDraw();}}
function tokDraw(){const TOKS=['skull','cultist','tablet','elderthing'];
document.getElementById('tok_rows').innerHTML=TOK_ROWS.map((t,i)=>
`<div class=row style="margin-top:4px"><select onchange="TOK_ROWS[${i}].token=this.value">`+
TOKS.map(n=>`<option ${t.token===n?'selected':''}>${n}</option>`).join('')+
`</select><input type=text size=46 value="${(t.text||'').replace(/"/g,'&quot;')}" `+
`onchange="TOK_ROWS[${i}].text=this.value">`+
`<button class=btn style="font-size:11px;padding:3px 9px" onclick="TOK_ROWS.splice(${i},1);tokDraw()">&times;</button></div>`).join('');}
function tokAdd(){if(TOK_ROWS.length<8){TOK_ROWS.push({token:'skull',text:'-1.'});tokDraw();}}
async function ccSave(){const p={card:ed.g.id,
name:document.getElementById('cc_name').value,
subtitle:document.getElementById('cc_subtitle').value,
traits:document.getElementById('cc_traits').value,
text:document.getElementById('cc_text').value,
flavor:document.getElementById('cc_flavor').value};
for(const f of CC_NUM)p[f]=document.getElementById('cc_'+f).value;
const t=ed.g.type;
if(t==='Location'){p.icons=document.getElementById('le_icon').value;
p.color=document.getElementById('le_color').value;
p.clues_per_investigator=document.getElementById('le_perinv').checked;
p.connections=LE_CONNS.filter(c=>c.symbol);}
if(t==='Scenario')p.tokens=TOK_ROWS.filter(r=>r.token||r.text);
if(t==='Investigator'){p.back_text=document.getElementById('cc_back').value;
p.back_flavor=document.getElementById('cc_backflavor').value;}
if(t==='CampaignLog')for(const f of LOG_F)p[f]=document.getElementById('cl_'+f).value;
for(const d of CC_PROP_F){const el=document.getElementById('cp_'+d[0]);
if(el)p[d[0]]=(d[2]==='chk')?el.checked:el.value;}
if(t==='Investigator')p.signatures=SIG_ROWS.filter(r=>r.id)
.map(r=>({[r.id]:Number(r.n)||1}));
const j=await post('card_save',p);
if(j.ok){document.getElementById('cc_info').textContent='saved \u2713';edFaceRefresh();}}
async function edArtRemove(){await post('art_remove',{card:ed.g.id});
ed.g.chosen=null;edStrip();edLoadArt();edFaceRefresh();}
function fillFontSel(id,cur){const sel=document.getElementById(id);if(!sel)return;
sel.innerHTML='';
const d=document.createElement('option');d.value='';d.text='default';sel.add(d);
for(const f of (LS&&LS.fonts)||[]){const o=document.createElement('option');
o.value=o.text=f;if(f===cur)o.selected=true;sel.add(o);}}
async function edFontSet(){
await post('font_set',{card:ed.g.id,
title:document.getElementById('ed_font_title').value,
stat:document.getElementById('ed_font_stat').value,
body:document.getElementById('ed_font_body').value});
edFaceRefresh();}
// ---- per-text-area typography (font / size / bold / italic per field) ----
let TY_FIELD=null;
const TY_LABEL={name:'name / title',subtitle:'subtitle',traits:'traits',
text:'rules text',flavor:'flavor',victory:'victory',stats:'stat numbers'};
function tyBind(field){if(!ed)return;TY_FIELD=field;
document.getElementById('ty_field').textContent=TY_LABEL[field]||field;
const st=((ed.g.type_styles||{})[field])||{};
fillFontSel('ty_font',st.font||'');
const sz=st.size||1;document.getElementById('ty_size').value=sz;
document.getElementById('ty_pct').textContent=Math.round(sz*100)+'%';
document.getElementById('ty_bold').checked=!!st.bold;
document.getElementById('ty_italic').checked=!!st.italic;
// mirror the selected area's text into the side panel (name/subtitle/traits/
// rules/flavor have a text field; stats/victory don't)
const wrap=document.getElementById('ed_side_textwrap');
const cc=FIELD_CC[field];
if(wrap){if(cc){const dst=document.getElementById(cc);
document.getElementById('ed_side_text').value=dst?dst.value:'';
wrap.style.display='';}else{wrap.style.display='none';}}}
async function tySet(){if(!ed||!TY_FIELD)return;
const all=document.getElementById('ty_all').checked;
const body={card:all?'_default':ed.g.id,field:TY_FIELD,
font:document.getElementById('ty_font').value,
size:parseFloat(document.getElementById('ty_size').value)||1,
bold:document.getElementById('ty_bold').checked,
italic:document.getElementById('ty_italic').checked};
const j=await post('type_set',body);
if(j.ok){if(!all){ed.g.type_styles=ed.g.type_styles||{};
if(j.style&&Object.keys(j.style).length)ed.g.type_styles[TY_FIELD]=j.style;
else delete ed.g.type_styles[TY_FIELD];}
edFaceRefresh();addlog('text style ['+TY_FIELD+']'+(all?' (all cards)':'')+' updated');
if(all)setTimeout(refresh,600);}}
function tyReset(){if(!TY_FIELD)return;
document.getElementById('ty_font').value='';
document.getElementById('ty_size').value=1;
document.getElementById('ty_pct').textContent='100%';
document.getElementById('ty_bold').checked=false;
document.getElementById('ty_italic').checked=false;tySet();}
// ---- symbol palette: insert Arkham glyph tokens into the text areas ----
// token, glyph letter (ArkhamFontWithCodex maps A-V to symbols), caption
const SYMS=[['[action]','E','action'],['[fast]','F','fast'],['[reaction]','G','reaction'],
['[wil]','A','will'],['[int]','B','intel'],['[com]','C','combat'],['[agi]','D','agility'],
['[wild]','U','wild'],['[perinv]','T','per inv'],['[unique]','S','unique'],
['[skull]','M','skull'],['[cultist]','N','cultist'],['[tablet]','R','tablet'],
['[elderthing]','H','elder thing'],['[elder]','Q','elder sign'],['[autofail]','O','auto-fail'],
['[codex]','V','codex']];
let GLYPH_TARGET='cc_text';
function glyphTarget(id){GLYPH_TARGET=id;}
function symInit(){const el=document.getElementById('ed_symbols');if(!el||el.dataset.built)return;
for(const [tok,gly,cap] of SYMS){const b=document.createElement('button');
b.type='button';b.className='symbtn';b.title=tok;
b.innerHTML='<span class=gly>'+gly+'</span><small>'+cap+'</small>';
b.onclick=()=>symInsert(tok);el.appendChild(b);}
el.dataset.built='1';}
function symInsert(tok){const el=document.getElementById(GLYPH_TARGET)||document.getElementById('cc_text');
if(!el)return;const s=el.selectionStart==null?el.value.length:el.selectionStart;
const e=el.selectionEnd==null?el.value.length:el.selectionEnd;
el.value=el.value.slice(0,s)+tok+el.value.slice(e);
const pos=s+tok.length;el.focus();el.setSelectionRange(pos,pos);}
async function edFontUpload(input){const f=input.files[0];if(!f)return;
const rd=new FileReader();
rd.onload=async()=>{const j=await post('upload_font',{name:f.name,data_b64:rd.result});
if(j.ok){LS.fonts=j.fonts;
fillFontSel('ed_font_title',(ed.g.fonts||{}).title||'');
fillFontSel('ed_font_stat',(ed.g.fonts||{}).stat||'');
document.getElementById('ed_font_body').innerHTML='';
fillFontSel('ed_font_body',(ed.g.fonts||{}).body||'');
document.getElementById('ed_font_title').value=j.file;edFontSet();
addlog('font added: '+j.file);}
else addlog('font upload failed: '+(j.message||''));};
rd.readAsDataURL(f);input.value='';}
function dfFill(){const df=(LS&&LS.default_fonts)||{};
for(const [id,key] of [['df_title','title'],['df_stat','stat'],['df_body','body']])
fillFontSel(id,df[key]||'');
const on=Object.keys(df).length;
document.getElementById('df_info').textContent=on?('active on every card: '+
Object.entries(df).map(([k,v])=>k+' '+v).join(', ')):'official stack (default)';}
async function dfSet(){const j=await post('font_set',{card:'_default',
title:document.getElementById('df_title').value,
stat:document.getElementById('df_stat').value,
body:document.getElementById('df_body').value});
if(j.ok){LS.default_fonts=j.fonts;dfFill();refresh();addlog('default fonts set for every card');}}
async function dfFontUpload(input){const f=input.files[0];if(!f)return;
const rd=new FileReader();
rd.onload=async()=>{const j=await post('upload_font',{name:f.name,data_b64:rd.result});
if(j.ok){LS.fonts=j.fonts;dfFill();document.getElementById('df_title').value=j.file;dfSet();
addlog('font added: '+j.file);}
else addlog('font upload failed: '+(j.message||''));};
rd.readAsDataURL(f);input.value='';}
let ED_COMPOSED=null;
async function edPromptLoad(card){ED_COMPOSED=null;
const box=document.getElementById('ed_promptbox');
const j=await post('prompt_get',{card});
if(!j.ok){box.style.display='none';return;}
box.style.display='block';
ED_COMPOSED={positive:j.positive,negative:j.negative};
document.getElementById('ed_pos').value=(j.override&&j.override.positive)||j.positive;
document.getElementById('ed_neg').value=(j.override&&j.override.negative)||j.negative;
document.getElementById('ed_prompt_info').textContent=
(j.override&&(j.override.positive||j.override.negative)?'override active · ':'')+
'seed '+j.seed+' · '+j.checkpoint;}
function edPromptVals(){const p=document.getElementById('ed_pos').value.trim(),
n=document.getElementById('ed_neg').value.trim();
return{positive:ED_COMPOSED&&p===ED_COMPOSED.positive.trim()?'':p,
negative:ED_COMPOSED&&n===ED_COMPOSED.negative.trim()?'':n};}
async function edPromptSave(){const v=edPromptVals();
await post('prompt_save',{card:ed.g.id,positive:v.positive,negative:v.negative});
edPromptLoad(ed.g.id);}
async function edPromptReset(){
await post('prompt_save',{card:ed.g.id,positive:'',negative:''});
edPromptLoad(ed.g.id);}
async function edGenerate(reroll){const v=edPromptVals();
await post('prompt_save',{card:ed.g.id,positive:v.positive,negative:v.negative});
await post('generate',{only:ed.g.id,variants:2,dry_run:dry(),reroll:!!reroll});}
function edReroll(){edGenerate(true);}
function edLoadArt(){const art=document.getElementById('ed_art');
if(ed.g.chosen){art.style.display='block';
art.onload=()=>{ed.natW=art.naturalWidth;ed.natH=art.naturalHeight;edPreview();};
art.src='/art?p=out/'+camp()+'/'+ed.g.id+'/'+ed.g.chosen+'&ts='+Date.now();}
else{art.style.display='none';}}
function edStrip(){const el=document.getElementById('ed_strip');
const real=(ed.g.variants||[]).filter(v=>!(ed.g.stubs||[]).includes(v));
el.innerHTML=real.map(v=>
`<img class="${v===ed.g.chosen?'on':''}" src="/art?p=out/${camp()}/${ed.g.id}/${v}" `+
`onclick="edUse('${v}')">`).join('')||
'<span class=hint>no real art yet — hit Generate below, or upload an image above</span>';}
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
function edFaceRefresh(){if(!ed)return;
document.getElementById('ed_face').src=
'/art?p=art/faces/'+ed.g.id+'.png&ts='+Date.now();
edFurnitureRefresh();}
function edPreview(){if(!ed||!ed.natW)return;
ed.scale=parseFloat(document.getElementById('ed_scale').value);
ed.scaleY=parseFloat(document.getElementById('ed_scaley').value)||ed.scale;
const[cw,ch,x0,y0,x1,y1]=ed.g.artbox;const bw=x1-x0,bh=y1-y0;
const base=Math.max(bw/ed.natW,bh/ed.natH)*ed.disp;
const w=ed.natW*base*ed.scale, h=ed.natH*base*ed.scaleY;
const art=document.getElementById('ed_art');
art.style.width=w+'px';art.style.height=h+'px';
art.style.left=(-(w-(bw*ed.disp))/2+ed.ox*ed.disp)+'px';
art.style.top =(-(h-(bh*ed.disp))/2+ed.oy*ed.disp)+'px';}
(function(){const win=document.getElementById('ed_win');let drag=null;
win.addEventListener('mousedown',e=>{if(!ed)return;
drag={x:e.clientX,y:e.clientY,ox:ed.ox,oy:ed.oy};win.style.cursor='grabbing';e.preventDefault();});
window.addEventListener('mousemove',e=>{if(!drag||!ed)return;
ed.ox=drag.ox+(e.clientX-drag.x)/ed.disp;ed.oy=drag.oy+(e.clientY-drag.y)/ed.disp;edPreview();});
window.addEventListener('mouseup',()=>{drag=null;win.style.cursor='grab';});
win.addEventListener('wheel',e=>{e.preventDefault();const s=document.getElementById('ed_scale');
s.value=Math.max(0.5,Math.min(6,parseFloat(s.value)-e.deltaY*0.0012));edPreview();});})();
// ---- live furniture overlay: frame + text + discs on a transparent window,
// composed by the server and laid over the draggable art so art reads BEHIND
// the frame exactly as the finished card does ----
async function edFurnitureRefresh(){if(!ed)return;const id=ed.g.id;
const furn=document.getElementById('ed_furniture');
const face=document.getElementById('ed_face');
try{await post('compose_furniture',{card:id});}catch(_){}
if(!ed||ed.g.id!==id)return;
// once the furniture overlay (frame+text+discs, transparent window) is up we
// HIDE the baked face — otherwise its baked-in art shows behind the live art
// and reads as a duplicate when you drag or scroll. Furniture failing falls
// back to the baked face so the preview is never blank.
furn.onload=()=>{furn.style.display='block';face.style.display='none';};
furn.onerror=()=>{furn.style.display='none';face.style.display='block';};
furn.src='/art?p=art/faces/'+id+'-furniture.png&ts='+Date.now();
edRegions();}
// ---- editable text boxes ON the card. name and rules text can be dragged to
// reposition (saved as a per-field offset the renderer honours); every text
// area selects into the side panel. Stat numerals select but don't drag. ----
const FIELD_CC={name:'cc_name',subtitle:'cc_subtitle',traits:'cc_traits',
text:'cc_text',flavor:'cc_flavor'};
function edRegionField(key){
// which saved text field a clicked region maps to
if(key==='name'||key==='text')return {field:key,drag:true};
return {field:'stats',drag:false};}
let ED_SEL=null;
function edRegions(){const host=document.getElementById('ed_regions');if(!host)return;
host.innerHTML='';if(!ed||!ed.g.regions)return;
for(const key in ed.g.regions){const b=ed.g.regions[key];if(!b)continue;
const rf=edRegionField(key);const st=(ed.g.type_styles||{})[rf.field]||{};
const dx=(rf.drag?(st.dx||0):0),dy=(rf.drag?(st.dy||0):0);
const el=document.createElement('div');el.className='ed_rg'+(ED_SEL===key?' sel':'');
el.dataset.key=key;
el.style.left=((b[0]+dx)*ed.disp)+'px';el.style.top=((b[1]+dy)*ed.disp)+'px';
el.style.width=((b[2]-b[0])*ed.disp)+'px';el.style.height=((b[3]-b[1])*ed.disp)+'px';
if(!rf.drag)el.style.cursor='pointer';
el.title=rf.drag?'drag to move · click to edit':'click to style';
host.appendChild(el);}}
(function(){let rdrag=null;
document.getElementById('ed_regions').addEventListener('mousedown',e=>{
const el=e.target.closest('.ed_rg');if(!el||!ed)return;e.preventDefault();
const key=el.dataset.key;const rf=edRegionField(key);
edSelectRegion(key);
if(!rf.drag)return;
const st=(ed.g.type_styles||{})[rf.field]||{};
rdrag={el,key,field:rf.field,x:e.clientX,y:e.clientY,
dx0:st.dx||0,dy0:st.dy||0,base:{l:parseFloat(el.style.left),t:parseFloat(el.style.top)},moved:false};});
window.addEventListener('mousemove',e=>{if(!rdrag)return;
const mx=e.clientX-rdrag.x,my=e.clientY-rdrag.y;
if(Math.abs(mx)+Math.abs(my)>2)rdrag.moved=true;
rdrag.el.style.left=(rdrag.base.l+mx)+'px';rdrag.el.style.top=(rdrag.base.t+my)+'px';});
window.addEventListener('mouseup',async e=>{if(!rdrag)return;const d=rdrag;rdrag=null;
if(!d.moved||!ed)return;
const ndx=Math.round(d.dx0+(e.clientX-d.x)/ed.disp);
const ndy=Math.round(d.dy0+(e.clientY-d.y)/ed.disp);
const j=await post('field_pos',{card:ed.g.id,field:d.field,dx:ndx,dy:ndy});
if(j.ok){ed.g.type_styles=ed.g.type_styles||{};
const cur=Object.assign({},ed.g.type_styles[d.field]||{});
if(ndx)cur.dx=ndx;else delete cur.dx;if(ndy)cur.dy=ndy;else delete cur.dy;
if(Object.keys(cur).length)ed.g.type_styles[d.field]=cur;else delete ed.g.type_styles[d.field];
edFaceRefresh();addlog('moved '+d.field);}});})();
function edSelectRegion(key){ED_SEL=key;
const rf=edRegionField(key);tyBind(rf.field);
for(const el of document.querySelectorAll('.ed_rg'))
el.classList.toggle('sel',el.dataset.key===key);}
function edMoveReset(){if(!ed||!ED_SEL)return;const rf=edRegionField(ED_SEL);
if(!rf.drag)return;
post('field_pos',{card:ed.g.id,field:rf.field,dx:0,dy:0}).then(j=>{if(!j.ok)return;
if(ed.g.type_styles&&ed.g.type_styles[rf.field]){
delete ed.g.type_styles[rf.field].dx;delete ed.g.type_styles[rf.field].dy;
if(!Object.keys(ed.g.type_styles[rf.field]).length)delete ed.g.type_styles[rf.field];}
edFaceRefresh();addlog('reset '+rf.field+' position');});}
// side-panel text editor mirrors the selected area's content field
let ED_TXT_T=null;
function edSideText(){const cc=FIELD_CC[TY_FIELD];if(!cc)return;
const src=document.getElementById('ed_side_text');const dst=document.getElementById(cc);
if(dst){dst.value=src.value;}
clearTimeout(ED_TXT_T);ED_TXT_T=setTimeout(()=>{if(ed)ccSave();},700);}
// one Save: writes the content fields AND the art placement, then recomposes
// so the preview reflects it immediately
async function edSave(){if(!ed)return;
await ccSave();
const body={card:ed.g.id,scale:ed.scale,ox:ed.ox,oy:ed.oy};
if(ed.scaleY&&Math.abs(ed.scaleY-ed.scale)>0.001)body.scale_y=ed.scaleY;
await post('place',body);
edFaceRefresh();addlog(ed.g.id+' saved');}
function edClose(){document.getElementById('editor').style.display='none';
document.getElementById('chips_cards').style.display='';
document.getElementById('cardgroups').style.display='';
ED_SEL=null;document.getElementById('ed_furniture').style.display='none';
ed=null;refresh();}
async function edDelete(){if(!ed)return;
if(!confirm('Delete "'+(ed.g.name||ed.g.id)+'"?\n\nThis removes the card from this campaign.'))return;
const j=await post('card_delete',{card:ed.g.id});
if(j.ok){addlog('card deleted: '+ed.g.id);edClose();}
else alert(j.message||'could not delete this card');}
function applyArt(){post('apply',{mode:document.getElementById('applymode').value,
base_url:document.getElementById('baseurl').value});}
// ---------------- scenario deck-builder ----------------
let SCEN_DRAG=null;
function scenAssignments(){const A={};
for(const box of document.querySelectorAll('.scenbox'))
{const sid=box.dataset.sid;A[sid]={};
if(box.classList.contains('locked'))A[sid]._locked=true;
for(const st of box.querySelectorAll('.stack')){
const ids=[...st.querySelectorAll('.dcard')].map(d=>d.dataset.cid);
if(ids.length)A[sid][st.dataset.stack]=ids;}}
return A;}
async function scenSave(){await post('scenario_save',{campaign:camp(),assignments:scenAssignments()});}
let MAP_SID=null,MAP_DRAG=null,MAP_MODE='move',MAP_SEL=null,MAP_LINK_FROM=null,
MAP_MOVE_FROM=null,MAP_PV=false;
const MAP_GLYPH={circle:'●',square:'■',triangle:'▲',
diamond:'◆',moon:'☽',star:'★',heart:'♥',
hourglass:'⧖',cross:'✚',quote:'”',slash:'/',
doubleslash:'//',spade:'♠',clover:'♣',t:'T'};
const MAP_HEX={red:'#960e12',orange:'#b85418',yellow:'#be9428',green:'#2c663c',
teal:'#1a605e',blue:'#204884',purple:'#5c246e',pink:'#a8386e',brown:'#6c482e',
grey:'#625e64',gray:'#625e64',gold:'#aa8e46'};
function mapColor(c){c=(c||'').trim();if(!c)return '#c9a24a';
return MAP_HEX[c.toLowerCase()]||c;}
function mapMode(m){MAP_MODE=m;MAP_SEL=null;
document.getElementById('mapwrap').classList.toggle('linking',m==='link');
document.getElementById('map_mode_move').className='btn'+(m==='move'?' primary':'');
document.getElementById('map_mode_link').className='btn'+(m==='link'?' primary':'');
mapDraw();}
// How far apart the slots are drawn. Purely visual: a slot is a grid position,
// so the saved layout and the scripted table coordinates never change with it.
function mapGap(px){
document.getElementById('mapgrid').style.setProperty('--mapgap',px+'px');
try{localStorage.setItem('cf_mapgap',px);}catch(_){}
// the cards moved, so the lines between them have to be redrawn
mapLines();}
function mapGapInit(){let v=86;
try{v=Number(localStorage.getItem('cf_mapgap'))||86;}catch(_){}
const el=document.getElementById('map_gap');if(el)el.value=v;
document.getElementById('mapgrid').style.setProperty('--mapgap',v+'px');}
function mapOpen(sid,name){MAP_SID=sid;
document.getElementById('maptitle').textContent='Location map — '+name;
document.getElementById('mapwrap').style.display='block';mapGapInit();mapMode('move');
document.getElementById('mapwrap').scrollIntoView({behavior:'smooth',block:'center'});}
function mapDraw(){const S=(LS&&LS.scenarios)||{};const g=S.grid||{cols:6,rows:4};
const A=(S.assignments||{})[MAP_SID]||{};
const placed=A._map||{};const locs=(A.locations||[]);
const grid=document.getElementById('mapgrid');
grid.style.gridTemplateColumns='repeat('+g.cols+',104px)';grid.innerHTML='';
const at={};for(const cid in placed)at[placed[cid].join(',')]=cid;
for(let r=0;r<g.rows;r++)for(let c=0;c<g.cols;c++){
const cell=document.createElement('div');cell.className='mslot';cell.dataset.rc=c+','+r;
const x=(g.x0+c*g.dx).toFixed(1),z=(g.z0+r*g.dz).toFixed(1);
cell.innerHTML='<span class=co>'+x+' / '+z+'</span>';
const cid=at[c+','+r];
if(cid)cell.appendChild(mapCard(cid));
cell.addEventListener('dragover',e=>{e.preventDefault();cell.classList.add('over');});
cell.addEventListener('dragleave',()=>cell.classList.remove('over'));
cell.addEventListener('drop',e=>{e.preventDefault();cell.classList.remove('over');
// a connector was dropped here -> link the two locations
if(MAP_LINK_FROM){const tgt=cell.querySelector('img');
const from=MAP_LINK_FROM,was=MAP_MOVE_FROM;
MAP_LINK_FROM=null;MAP_MOVE_FROM=null;
for(const s of document.querySelectorAll('#mapgrid .mslot'))
s.classList.remove('linkable');
if(tgt&&tgt.dataset.cid!==from&&tgt.dataset.cid!==was)
mapLink(from,tgt.dataset.cid,was);
return;}
if(!MAP_DRAG)return;
const src=MAP_DRAG.parentElement;
if(cell.querySelector('img')&&src&&src.classList.contains('mslot')){
src.appendChild(cell.querySelector('img'));}
cell.appendChild(MAP_DRAG);MAP_DRAG=null;mapBadges();mapInfo();mapLines();
pvDraw();});
grid.appendChild(cell);}
// unplaced locations sit under the grid
const un=locs.filter(i=>!(i in placed));
const tray=document.createElement('div');tray.style.cssText='grid-column:1/-1;display:flex;gap:8px;flex-wrap:wrap;margin-top:6px';
tray.innerHTML=un.length?'':'<span class=hint>every location in this scenario is on the map</span>';
for(const cid of un)tray.appendChild(mapCard(cid));
tray.addEventListener('dragover',e=>e.preventDefault());
tray.addEventListener('drop',e=>{e.preventDefault();if(MAP_LINK_FROM){MAP_LINK_FROM=null;return;}
if(MAP_DRAG){tray.appendChild(MAP_DRAG);MAP_DRAG=null;mapBadges();mapInfo();mapLines();pvDraw();}});
grid.appendChild(tray);mapBadges();mapInfo();mapLines();mapLegend();pvDraw();}
function mapFind(cid){return ((LS&&LS.cards)||[]).find(x=>x.id===cid);}
function mapSym(cid){const c=mapFind(cid);
return ((c&&c.content&&c.content.icons)||'').trim().toLowerCase();}
function mapConns(cid){const c=mapFind(cid);
return (((c&&c.content&&c.content.connections)||[])
.map(x=>(typeof x==='string'?x:(x.symbol||'')).toLowerCase()).filter(Boolean));}
function mapLinked(a,b){const sb=mapSym(b);
return !!sb&&mapConns(a).indexOf(sb)>=0;}
function mapCard(cid){const c=mapFind(cid);
const im=document.createElement('img');im.dataset.cid=cid;
im.draggable=(MAP_MODE==='move');
const sym=mapSym(cid);
im.title=(c?c.name:cid)+(MAP_MODE==='link'
?(MAP_SEL?' — click to link/unlink with '+(mapFind(MAP_SEL)||{}).name
:' — click to start a connection')
:' — drag to a slot')+(sym?'  ['+sym+']':'');
im.src='/art?p=art/faces/'+cid+'.png&ts='+((LS&&LS.faces_ver)||0);
im.addEventListener('dragstart',()=>{MAP_DRAG=im;});
if(MAP_MODE==='link'){if(MAP_SEL===cid)im.classList.add('sel');
im.addEventListener('click',()=>mapClick(cid));}
return im;}
// symbol badges and the drag-out connector live on the slot, not the card
// image, so dragging a card between slots can never leave a stray one behind
// Who is this location joined to, right now, on this board?
function mapNeighbours(cid){
const out=[];
for(const im of document.querySelectorAll('#mapgrid .mslot img')){
const o=im.dataset.cid;
if(o!==cid&&(mapLinked(cid,o)||mapLinked(o,cid)))out.push(o);}
return out;}
function mapBadges(){
for(const b of document.querySelectorAll('#mapgrid .msym, #mapgrid .mnub, #mapgrid .mrow'))
b.remove();
for(const im of document.querySelectorAll('#mapgrid .mslot img')){
const host=im.parentElement;if(!host)continue;
const cid=im.dataset.cid,c=mapFind(cid),sym=mapSym(cid);
const col=mapColor((c&&c.content&&c.content.color)||'');
// the connection row, one chip per neighbour, in that neighbour's colour —
// the card's own symbol is never among them, because it is never its own
// neighbour
const row=document.createElement('span');row.className='mrow';
for(const other of mapNeighbours(cid)){
const oc=mapFind(other),osym=mapSym(other);
const chip=document.createElement('span');chip.className='mchip';
chip.draggable=true;
chip.style.color=mapColor((oc&&oc.content&&oc.content.color)||'');
chip.textContent=MAP_GLYPH[osym]||osym||'?';
chip.title=((c&&c.name)||cid)+' connects to '+((oc&&oc.name)||other)+
'  —  drag this onto another location to move the connection there';
chip.addEventListener('dragstart',e=>{
MAP_LINK_FROM=cid;MAP_MOVE_FROM=other;MAP_DRAG=null;
chip.classList.add('moving');
e.dataTransfer.effectAllowed='move';
try{e.dataTransfer.setData('text/plain',cid);}catch(_){}
for(const s of document.querySelectorAll('#mapgrid .mslot'))
if(s.querySelector('img')&&s.querySelector('img').dataset.cid!==cid)
s.classList.add('linkable');});
chip.addEventListener('dragend',()=>{MAP_LINK_FROM=null;MAP_MOVE_FROM=null;
chip.classList.remove('moving');
for(const s of document.querySelectorAll('#mapgrid .mslot'))
s.classList.remove('linkable');});
row.appendChild(chip);}
if(row.children.length)host.appendChild(row);
// the connector: grab it and drop it on the location it connects to
const nub=document.createElement('span');nub.className='mnub';
nub.draggable=true;nub.style.background=col;
nub.title='drag this connector onto the location '+
((c&&c.name)||cid)+' connects to';
nub.addEventListener('dragstart',e=>{MAP_LINK_FROM=cid;MAP_DRAG=null;
e.dataTransfer.effectAllowed='link';
try{e.dataTransfer.setData('text/plain',cid);}catch(_){}
for(const s of document.querySelectorAll('#mapgrid .mslot'))
if(s.querySelector('img')&&s.querySelector('img').dataset.cid!==cid)
s.classList.add('linkable');});
nub.addEventListener('dragend',()=>{MAP_LINK_FROM=null;
for(const s of document.querySelectorAll('#mapgrid .mslot'))
s.classList.remove('linkable');});
host.appendChild(nub);
if(!sym)continue;
const bad=document.createElement('span');bad.className='msym';
bad.style.color=col;bad.textContent=MAP_GLYPH[sym]||sym;
host.appendChild(bad);}}
// linking two locations, however you got here: clicking both, or dragging a
// connector from one onto the other
async function mapLink(a,b,moveFrom){
// moveFrom set -> this connection is being moved off that location onto b
const rm=!moveFrom&&mapLinked(a,b)&&mapLinked(b,a);
const j=await post('map_connect',{campaign:camp(),scenario:MAP_SID,a:a,b:b,
remove:rm,move_from:moveFrom||''});
if(j.ok){addlog((moveFrom?('moved '+a+' → '+b+' (was '+moveFrom+')')
:((rm?'unlinked ':'linked ')+a+' ↔ '+b)));await refresh();mapDraw();}
else{alert(j.message||'could not change that connection');mapDraw();}}
async function mapClick(cid){
if(!MAP_SEL){MAP_SEL=cid;mapDraw();return;}
if(MAP_SEL===cid){MAP_SEL=null;mapDraw();return;}
const a=MAP_SEL;MAP_SEL=null;await mapLink(a,cid);}
// the connection lines: drawn from what the cards actually print, so the map
// and the rendered card can never disagree
function mapLines(){const svg=document.getElementById('maplines');
if(!svg)return;
const stage=document.getElementById('mapstage');
const sb=stage.getBoundingClientRect();
svg.setAttribute('width',sb.width);svg.setAttribute('height',sb.height);
svg.setAttribute('viewBox','0 0 '+sb.width+' '+sb.height);
svg.innerHTML='';
// only cards actually on the board take part — one dragged back to the tray
// drops its lines, the same way a location off the playmat does in TTS
const pts={};let size=[60,84];
for(const im of document.querySelectorAll('#mapgrid .mslot img')){
const r=im.getBoundingClientRect();
size=[r.width,r.height];
pts[im.dataset.cid]=[r.left-sb.left+r.width/2,r.top-sb.top+r.height/2];}
const ids=Object.keys(pts);let n=0;
for(let i=0;i<ids.length;i++)for(let j=i+1;j<ids.length;j++){
if(drawConn(svg,ids[i],ids[j],pts,size))n++;}
const li=document.getElementById('maplegend');
if(li)li.dataset.links=n;}
// ---- one connection, drawn the way TTS draws it -------------------------
// Runs from card edge to card edge, never centre to centre, and stretches to
// wherever the two cards happen to be — exactly like SCED, where a location
// stays connected as long as both cards are on the board. Ours adds the one
// thing SCED's plain white lines do not tell you: each half is coloured with
// the symbol printed at the FAR end, so following a colour off a card leads
// you to the location whose symbol that is.
function edgePoint(from,to,hw,hh){
const dx=to[0]-from[0],dy=to[1]-from[1];
const ad=Math.abs(dx),ay=Math.abs(dy);
if(ad<0.001&&ay<0.001)return from.slice();
const t=Math.min(ad>0.001?hw/ad:1e9, ay>0.001?hh/ay:1e9);
return [from[0]+dx*t, from[1]+dy*t];}
function drawConn(svg,a,b,pts,size){
if(!pts[a]||!pts[b])return false;                 // off the board -> no line
if(!(mapLinked(a,b)||mapLinked(b,a)))return false;
const one=!(mapLinked(a,b)&&mapLinked(b,a));      // only one side prints it
const hw=(size&&size[0]||60)/2, hh=(size&&size[1]||84)/2;
const A=edgePoint(pts[a],pts[b],hw,hh), B=edgePoint(pts[b],pts[a],hw,hh);
const M=[(A[0]+B[0])/2,(A[1]+B[1])/2];
const colA=mapColor(((mapFind(a)||{}).content||{}).color);
const colB=mapColor(((mapFind(b)||{}).content||{}).color);
const seg=(p,q,col,w,op,dash)=>{
const ln=document.createElementNS('http://www.w3.org/2000/svg','line');
ln.setAttribute('x1',p[0]);ln.setAttribute('y1',p[1]);
ln.setAttribute('x2',q[0]);ln.setAttribute('y2',q[1]);
ln.setAttribute('stroke',col);ln.setAttribute('stroke-width',w);
ln.setAttribute('stroke-linecap','round');ln.setAttribute('opacity',op);
if(dash)ln.setAttribute('stroke-dasharray','7 5');
svg.appendChild(ln);};
seg(A,B,'#000',5,'.45');                          // casing, as on the playmat
seg(A,M,colB,2.5,one?'.6':'.95',one);             // leaving A -> B's symbol
seg(M,B,colA,2.5,one?'.6':'.95',one);             // leaving B -> A's symbol
return true;}
function mapLegend(){const el=document.getElementById('maplegend');if(!el)return;
const S=(LS&&LS.scenarios)||{};const A=(S.assignments||{})[MAP_SID]||{};
const parts=[];
for(const cid of (A.locations||[])){const c=mapFind(cid);if(!c)continue;
const sym=mapSym(cid);if(!sym)continue;
parts.push('<span style="margin-right:12px"><b style="color:'
+mapColor((c.content||{}).color)+'">'+(MAP_GLYPH[sym]||sym)+'</b> '
+(c.name||cid)+'</span>');}
const n=Number(el.dataset.links||0);
el.innerHTML=(parts.length?parts.join(''):'<i>no location symbols yet — Connect two locations and they are assigned automatically</i>')
+'<br><span style="opacity:.7">'+n+' connection(s) drawn'
+' — a dashed line means only one side prints the other&rsquo;s symbol</span>';}
// ---- LIVE TABLE PREVIEW -------------------------------------------------
// The whole scenario drawn to scale from above, at the same table coordinates
// the campaign box scripts: locations where you put them, and the encounter /
// agenda / act / set-aside furniture they have to fit around. Overlaps are
// outlined in red, so a layout that will not work is visible before anything
// is sent to TTS.
function pvToggle(){MAP_PV=!MAP_PV;
document.getElementById('mappreview').style.display=MAP_PV?'block':'none';
document.getElementById('map_pv').className='btn'+(MAP_PV?' primary':'');
if(MAP_PV)pvDraw();}
function pvDraw(){if(!MAP_PV)return;
const S=(LS&&LS.scenarios)||{};const g=S.grid||{};
const stage=document.getElementById('pvstage');if(!stage)return;
const items=[];
// locations, at whatever slot they currently sit in on the grid above
for(const cell of document.querySelectorAll('#mapgrid .mslot')){
const img=cell.querySelector('img');if(!img)continue;
const[c,r]=cell.dataset.rc.split(',').map(Number);
const card=mapFind(img.dataset.cid);
items.push({kind:'card',cid:img.dataset.cid,
name:(card&&card.name)||img.dataset.cid,
x:g.x0+c*g.dx, z:g.z0+r*g.dz, w:g.cw||2.63, h:g.ch||3.68});}
// …and the fixed furniture, drawn as labelled footprints
for(const f of (S.furniture||[])){
const side=(f.rot===90||f.rot===270);
items.push({kind:'box',name:f.label,x:f.x,z:f.z,
w:side?(g.ch||3.68):(g.cw||2.63),
h:side?(g.cw||2.63):(g.ch||3.68)});}
if(!items.length){stage.innerHTML=
'<div class=hint style="padding:24px;text-align:center">place a location on the grid to see the table</div>';
stage.style.height='';document.getElementById('pvinfo').textContent='';return;}
// world bounds -> a stage that fits the panel
let x0=1e9,x1=-1e9,z0=1e9,z1=-1e9;
for(const it of items){x0=Math.min(x0,it.x-it.w/2);x1=Math.max(x1,it.x+it.w/2);
z0=Math.min(z0,it.z-it.h/2);z1=Math.max(z1,it.z+it.h/2);}
const pad=1.5;x0-=pad;x1+=pad;z0-=pad;z1+=pad;
const avail=Math.max(320,(stage.parentElement.clientWidth||900)-24);
const k=Math.min(avail/(x1-x0),620/(z1-z0));
const W=Math.round((x1-x0)*k),H=Math.round((z1-z0)*k);
stage.style.width=W+'px';stage.style.height=H+'px';stage.innerHTML='';
// +x runs right; +z runs AWAY from the player, so it draws upward
const px=it=>[(it.x-it.w/2-x0)*k,(z1-it.z-it.h/2)*k,it.w*k,it.h*k];
const clash=new Set();
for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
const a=items[i],b=items[j];
if(Math.abs(a.x-b.x)<(a.w+b.w)/2&&Math.abs(a.z-b.z)<(a.h+b.h)/2){
clash.add(i);clash.add(j);}}
const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
svg.setAttribute('width',W);svg.setAttribute('height',H);
stage.appendChild(svg);
const at={};
items.forEach((it,i)=>{const[l,t,w,h]=px(it);
if(it.kind==='card'){at[it.cid]=[l+w/2,t+h/2];
const im=document.createElement('img');im.className='pvcard';
im.src='/art?p=art/faces/'+it.cid+'.png&ts='+((LS&&LS.faces_ver)||0);
im.style.cssText='left:'+l+'px;top:'+t+'px;width:'+w+'px;height:'+h+'px';
im.title=it.name+'  (x '+it.x.toFixed(2)+' / z '+it.z.toFixed(2)+')';
if(clash.has(i))im.classList.add('pvclash');
stage.appendChild(im);}
else{const d=document.createElement('div');d.className='pvbox';
d.style.cssText='left:'+l+'px;top:'+t+'px;width:'+w+'px;height:'+h+'px';
d.textContent=it.name;d.title=it.name+'  (x '+it.x.toFixed(2)+' / z '+it.z.toFixed(2)+')';
if(clash.has(i))d.classList.add('pvclash');
stage.appendChild(d);}});
// the connections, drawn between the location centres
let links=0;const ids=Object.keys(at);
const csz=[(g.cw||2.63)*k,(g.ch||3.68)*k];
for(let i=0;i<ids.length;i++)for(let j=i+1;j<ids.length;j++){
if(drawConn(svg,ids[i],ids[j],at,csz))links++;}
document.getElementById('pvinfo').innerHTML=
Object.keys(at).length+' location(s) &middot; '+links+' connection(s) &middot; '+
((x1-x0).toFixed(1))+' &times; '+((z1-z0).toFixed(1))+' table units'+
(clash.size?' &mdash; <b style="color:#e08080">'+clash.size+
' object(s) overlap</b>':' &mdash; nothing overlaps');}
function mapSlots(){const out={};
for(const cell of document.querySelectorAll('#mapgrid .mslot')){
const img=cell.querySelector('img');
if(img){const[c,r]=cell.dataset.rc.split(',').map(Number);out[img.dataset.cid]=[c,r];}}
return out;}
function mapInfo(){const n=Object.keys(mapSlots()).length;
document.getElementById('mapinfo').textContent=MAP_MODE==='link'
?(MAP_SEL?'now click the location it connects to (click it again to unlink)'
:'click a location, then click the one it connects to — both cards get the other’s symbol printed on them straight away')
:n+' location(s) placed — Save layout writes these exact table positions into the scenario script';}
async function mapSave(){const j=await post('map_save',{campaign:camp(),scenario:MAP_SID,slots:mapSlots()});
if(j.ok){addlog('map layout saved for '+MAP_SID);await refresh();mapDraw();}}
async function scenNew(){const el=document.getElementById('ns_name');
const name=el.value.trim();if(!name){alert('Name the scenario first.');return;}
const j=await post('scenario_new',{campaign:camp(),name});
if(j.ok){el.value='';addlog('scenario added: '+j.name);await refresh();scenBuild();}
else alert(j.message||'could not add the scenario');}
async function scenDel(sid,name){if(!confirm('Remove the scenario box "'+name+'"?\nCards go back to the pool.'))return;
const j=await post('scenario_delete',{campaign:camp(),scenario:sid});
if(j.ok){addlog('scenario removed: '+name);await refresh();scenBuild();}}
async function scenRen(sid,cur){const name=prompt('Rename scenario:',cur);if(!name||name===cur)return;
const j=await post('scenario_rename',{campaign:camp(),scenario:sid,name});
if(j.ok){await refresh();scenBuild();}}
function dcardEl(cid){const c=((LS&&LS.cards)||[]).find(x=>x.id===cid);
const d=document.createElement('div');d.className='dcard';d.dataset.cid=cid;d.draggable=true;
d.title=(c?c.name:cid);
d.innerHTML=`<img src="/art?p=art/faces/${cid}.png&ts=${(LS&&LS.faces_ver)||0}" loading=lazy>`;
d.addEventListener('dragstart',e=>{SCEN_DRAG=d;d.classList.add('dragging');e.dataTransfer.setData('text',cid);});
d.addEventListener('dragend',()=>{d.classList.remove('dragging');SCEN_DRAG=null;});
return d;}
// Fade whichever edge has more board beyond it, and say how many boxes are
// off-screen — the row used to just stop with no sign the campaign continued.
function boardEdges(){
const b=document.getElementById('scen_board'),w=document.getElementById('board_wrap');
if(!b||!w)return;
const more=b.scrollWidth-b.clientWidth;
w.classList.toggle('more-l',b.scrollLeft>4);
w.classList.toggle('more-r',b.scrollLeft<more-4);
const h=document.getElementById('board_hint');if(!h)return;
const boxes=b.querySelectorAll('.scenbox').length;
if(!boxes){h.textContent='';return;}
const seen=Math.max(1,Math.round(b.clientWidth/264));
h.innerHTML=boxes+' scenario box'+(boxes===1?'':'es')+
(more>4?' &mdash; showing '+Math.min(seen,boxes)+', scroll sideways for the rest &rarr;':'');
if(!b.dataset.edges){b.dataset.edges='1';
b.addEventListener('scroll',boardEdges,{passive:true});
window.addEventListener('resize',boardEdges);}}
function stackDropify(el){
el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('over');});
el.addEventListener('dragleave',()=>el.classList.remove('over'));
el.addEventListener('drop',e=>{e.preventDefault();el.classList.remove('over');
if(!SCEN_DRAG)return;
const from=SCEN_DRAG.closest('.stack');
// land in the card grid so cards never interleave with the requirement chips
(el.querySelector(':scope > .cards')||el).appendChild(SCEN_DRAG);
SCEN_DRAG.classList.add('justdropped');
setTimeout(()=>SCEN_DRAG&&SCEN_DRAG.classList.remove('justdropped'),300);
// refresh the two stacks in place — a full reload on every drop would stall
// the drag and re-fetch the whole catalog for nothing
stackTouch(el);if(from&&from!==el)stackTouch(from);
scenSave();});}
// keep a stack's count badge and collapsed state true after a drop
function stackTouch(el){
if(!el||!el.classList.contains('stack'))return;
const n=el.querySelectorAll('.dcard').length;
const lbl=el.querySelector('small');
if(lbl){const base=(lbl.textContent||'').replace(/\s+\d+$/,'');
lbl.innerHTML=base+(n?' <b style="color:var(--dim)">'+n+'</b>':'');}
el.classList.toggle('empty',!n&&!el.querySelector('.reqs'));}
const STACK_LABEL={locations:'Locations',act_deck:'Act deck',agenda_deck:'Agenda deck',
encounter:'Encounter sets',named:'Named enemies',reference:'Scenario reference',setup_aside:'Set aside'};
function scenBuild(){const S=(LS&&LS.scenarios)||{scenarios:[],stacks:[],assignments:{}};
const board=document.getElementById('scen_board');board.innerHTML='';
const assigned=new Set();let locked=0;
const nameOf=cid=>{const c=((LS&&LS.cards)||[]).find(x=>x.id===cid);return c?String(c.name).toLowerCase():'';};
// a JS string literal safe to sit inside a double-quoted HTML attribute:
// without the escaping a scenario name with a space silently broke the
// rename / remove / map buttons
const jsAttr=v=>JSON.stringify(String(v)).replace(/&/g,'&amp;')
.replace(/"/g,'&quot;').replace(/</g,'&lt;');
for(const sc of S.scenarios){const A=S.assignments[sc.id]||{};
const isLocked=!!A._locked;if(isLocked)locked++;
const box=document.createElement('div');box.className='scenbox'+(isLocked?' locked':'');box.dataset.sid=sc.id;
box.innerHTML=`<h3>${isLocked?'&#128274; ':''}${sc.name||sc.id}</h3>`+
`<div class=row style="margin:-4px 0 6px"><button class=btn style="font-size:10px;padding:2px 7px" `+
`onclick="scenRen('${sc.id}',${jsAttr(sc.name||sc.id)})">rename</button>`+
`<button class=btn style="font-size:10px;padding:2px 7px" `+
`onclick="scenDel('${sc.id}',${jsAttr(sc.name||sc.id)})">remove</button>`+
`<button class=btn style="font-size:10px;padding:2px 7px" `+
`onclick="mapOpen('${sc.id}',${jsAttr(sc.name||sc.id)})">&#128506; map</button></div>`;
const mid=document.createElement('div');mid.className='stacks';
for(const st of S.stacks){const div=document.createElement('div');div.className='stack';div.dataset.stack=st;
const inStack=(A[st]||[]);
const names=inStack.map(nameOf);
// soft requirements: the manifest's template for this stack, struck through once met
const reqs=((sc.req||{})[st]||[]).map(r=>
`<span class="reqchip ${names.some(n=>n&&n.includes(String(r).toLowerCase().slice(0,12)))?'met':''}">${r}</span>`).join('');
// chips get their own strip; cards get their own grid. Sharing one flow was
// what made the stacks look shattered.
if(!inStack.length&&!reqs)div.classList.add('empty');
div.innerHTML=`<small>${STACK_LABEL[st]||st}${inStack.length?' <b style="color:var(--dim)">'+inStack.length+'</b>':''}</small>`+
(reqs?`<div class=reqs>${reqs}</div>`:'')+`<div class=cards></div>`;
const holder=div.querySelector('.cards');
for(const cid of inStack){holder.appendChild(dcardEl(cid));assigned.add(cid);}
if(!isLocked)stackDropify(div);
mid.appendChild(div);}
box.appendChild(mid);
const lb=document.createElement('button');lb.className='btn lockbtn'+(isLocked?'':' primary');
lb.innerHTML=isLocked?'&#128275; Unlock scenario':'&#128274; Lock in as finished';
lb.onclick=()=>{box.classList.toggle('locked');scenSave().then(()=>{refresh().then(scenBuild);});};
box.appendChild(lb);
board.appendChild(box);}
if(!S.scenarios.length)board.innerHTML=
'<div class=hint style="padding:16px">No scenario boxes yet &mdash; add one above, then drag cards from the pool into its stacks.</div>';
const total=S.scenarios.length;
boardEdges();
document.getElementById('camp_progress').textContent=locked+'/'+total+' locked';
document.getElementById('camp_spawn').disabled=!(total&&locked===total);
const pool=document.getElementById('scen_pool_cards');pool.innerHTML='';
for(const c of ((LS&&LS.cards)||[]))if(!assigned.has(c.id))pool.appendChild(dcardEl(c.id));
stackDropify(document.getElementById('scen_pool'));}
// only player cards carry a class/faction — hide the picker for encounter and
// mythos types (Enemy, Location, Treachery, Agenda, Act, Scenario, Story)
function ncClassVis(){const t=document.getElementById('nc_type').value;
const cls=document.getElementById('nc_class');
const show=['Investigator','Asset','Event','Skill'].includes(t);
cls.style.display=show?'':'none';if(!show)cls.value='';}
async function cardNew(){
const name=document.getElementById('nc_name').value.trim();
if(!name){alert('Give the card a name first.');return;}
const j=await post('card_new',{campaign:camp(),
type:document.getElementById('nc_type').value,
class:document.getElementById('nc_class').value,name});
if(j.ok){document.getElementById('nc_name').value='';
addlog('card created: '+j.name+' ('+j.type+')');
await refresh();openEditor(j.id);}
else alert(j.message||'could not create the card');}
async function campNew(){
const name=prompt('Name the new campaign (e.g. "The Hollow Winter"):');
if(!name)return;
const seed=confirm('Seed it with a starter scenario at the recommended card '
+'counts?\n\n(4 locations · 2 acts · 9 agendas · 13 encounter · 1 reference '
+'— blank placeholders on their real templates, all editable.)\n\n'
+'OK = seed · Cancel = empty campaign');
const j=await post('campaign_new',{name,seed});
if(j.ok){addlog('campaign created: '+j.name+(j.seeded?' (+'+j.seeded+' cards)':''));
const sel=document.getElementById('campaign');sel.value=j.id;campPick();
alert('Created "'+j.name+'".'+(j.seeded?('\n\nSeeded '+j.seeded+' placeholder cards into Scenario 1 '
+'— rename and edit them in 3 · Cards, or arrange them in 4 · Campaign / scenarios.')
:'\n\nUse 4 · Campaign / scenarios → Import campaign JSON to pour a written campaign into it.'));}
else alert(j.message||'could not create the campaign');}
async function campCompile(){const el=document.getElementById('camp_out');
el.textContent='compiling\u2026';
const j=await post('campaign_compile',{campaign:camp()});
if(j.ok){el.textContent=`\u2713 ${j.scenarios} scenarios, ${j.cards} cards \u2192 ${j.out}`;
addlog('campaign box compiled -> '+j.out+' (load it in TTS: Objects > Saved Objects)');}
else{el.textContent=j.message||'compile failed';addlog('compile blocked: '+(j.message||''));}}
async function feedImport(input){const f=input.files[0];if(!f)return;
const info=document.getElementById('feed_info');info.textContent='importing\u2026';
const rd=new FileReader();
rd.onload=async()=>{const j=await post('campaign_import',{data:rd.result,campaign:camp()});
if(j.ok){info.textContent=`imported \u2713 ${j.created.length} new, ${j.updated.length} updated`;
addlog('campaign feed: '+j.created.length+' new, '+j.updated.length+' updated, '+j.skipped.length+' skipped');
await refresh();scenBuild();}
else{info.textContent='import failed: '+(j.message||'');}};
rd.readAsText(f);input.value='';}
symInit();ncClassVis();refresh();poll();setInterval(refresh,4000);
</script></body></html>"""


def migrate_overrides():
    """Move each campaign's hand edits into its own folder.

    Card edits used to land in still_hour/card_overrides.json whatever campaign
    you were editing. Card ids are prefixed per campaign so nothing collided,
    but the compiler reads a campaign's own folder — so another campaign's
    edits were invisible to it. Runs once, then finds nothing to do."""
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import render_placeholders as rp
    home = os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json")
    if not os.path.exists(home):
        return 0
    try:
        shared = json.load(open(home, encoding="utf-8"))
    except ValueError:
        return 0
    camp_root = os.path.join(ROOT, "campaigns")
    moved = 0
    for name in sorted(os.listdir(camp_root)):
        if name == "still_hour" or not os.path.isdir(
                os.path.join(camp_root, name)):
            continue
        mine = set()
        for path in spec_files(name):
            if not os.path.exists(path):
                continue
            try:
                mine |= {c.get("id") for c in
                         json.load(open(path, encoding="utf-8"))}
            except ValueError:
                continue
        take = {cid: shared[cid] for cid in list(shared) if cid in mine}
        if not take:
            continue
        dest = rp.overrides_path(name)
        own = {}
        if os.path.exists(dest):
            try:
                own = json.load(open(dest, encoding="utf-8"))
            except ValueError:
                own = {}
        for cid, entry in take.items():
            own.setdefault(cid, entry)
            shared.pop(cid, None)
            moved += 1
        _write_json_atomic(dest, own)
    if moved:
        _write_json_atomic(home, shared)
        print("moved {} card edit(s) into their own campaign".format(moved))
    return moved


def ensure_faces(campaign="still_hour"):
    """Render every card face if they are missing.

    art/ is gitignored, so a fresh clone ships NO composed faces — without this
    the app opens completely empty: no card thumbnails, an empty scenario pool,
    nothing to click. Rendering needs no GPU and no backend (it draws the cards
    on the bundled frames), so it is safe to do on startup.
    """
    faces_dir = os.path.join(ROOT, "art", "faces")
    have = len([f for f in os.listdir(faces_dir)
                if f.endswith(".png") and has_face(f[:-4])]) \
        if os.path.isdir(faces_dir) else 0
    if have:
        return have
    print("first run: composing card faces (no GPU needed)…")
    try:
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py")],
                       check=True, cwd=ROOT)
    except (subprocess.CalledProcessError, OSError) as e:
        print("could not compose faces automatically: {}\n"
              "run this yourself:  python3 pipeline/render_placeholders.py"
              .format(e))
        return 0
    n = len([f for f in os.listdir(faces_dir)
             if f.endswith(".png") and has_face(f[:-4])]) \
        if os.path.isdir(faces_dir) else 0
    print("composed {} card face(s)".format(n))
    return n


def main():
    migrate_overrides()
    ensure_faces()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("CardForge Studio: http://127.0.0.1:{}  (Ctrl-C to stop)".format(PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
