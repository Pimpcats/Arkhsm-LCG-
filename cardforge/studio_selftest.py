#!/usr/bin/env python3
"""CardForge Studio acceptance test — boots the real server and drives the
full illustrate -> frame -> apply flow over HTTP (dry-run; no GPU/SE needed).
Run from the repo root: python3 cardforge/studio_selftest.py
"""
import json
import os
import shutil
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardforge import studio, runner, se_bridge
from http.server import ThreadingHTTPServer

ROOT = runner.repo_root()
BASE = "http://127.0.0.1:8571"
PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    print("  [{}] {}".format("PASS" if cond else "FAIL", name))
    PASS, FAIL = (PASS + 1, FAIL) if cond else (PASS, FAIL + 1)


def wait_idle(timeout=30):
    for _ in range(timeout * 4):
        if not requests.get(BASE + "/api/status").json()["busy"]:
            return True
        time.sleep(0.25)
    return False


# fresh slate — but NEVER destroy the owner's real work: everything the test
# wipes is moved aside first and restored on exit (success, failure, or crash),
# so chosen art, placements and composed faces survive a selftest run.
import atexit

_BACKUPS = []


def _sideline(path):
    if os.path.exists(path):
        bak = path + ".pretest-backup"
        shutil.rmtree(bak, ignore_errors=True)
        if os.path.isfile(bak):
            os.remove(bak)
        os.rename(path, bak)
        _BACKUPS.append((path, bak))


_SNAPSHOTS = []


def _snapshot(path):
    """Keep a copy of something the test edits IN PLACE (the app needs the
    real file present while it runs). Restored even if the run is killed
    part-way — a half-finished test must never leave the owner's campaign
    pointing at a stub checkpoint."""
    if os.path.isdir(path):
        bak = path + ".pretest-copy"
        shutil.rmtree(bak, ignore_errors=True)
        shutil.copytree(path, bak)
        _SNAPSHOTS.append((path, bak, True))
    elif os.path.isfile(path):
        bak = path + ".pretest-copy"
        shutil.copy2(path, bak)
        _SNAPSHOTS.append((path, bak, False))


def _restore_owner_state():
    for path, bak in _BACKUPS:
        if os.path.exists(bak):
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.remove(path)
            os.rename(bak, path)
    for path, bak, isdir in _SNAPSHOTS:
        if not os.path.exists(bak):
            continue
        if isdir:
            shutil.rmtree(path, ignore_errors=True)
            os.rename(bak, path)
        else:
            shutil.copy2(bak, path)
            os.remove(bak)
    if _BACKUPS or _SNAPSHOTS:
        print("owner state restored ({} path(s))"
              .format(len(_BACKUPS) + len(_SNAPSHOTS)))


atexit.register(_restore_owner_state)

_sideline(os.path.join(ROOT, "out", "still_hour"))
for f in ("state/still_hour.ledger.json", "pipeline/art_urls.json"):
    _sideline(os.path.join(ROOT, f))
# these the app must keep seeing while the test runs, so copy rather than move
_snapshot(os.path.join(ROOT, "campaigns", "still_hour"))
_snapshot(os.path.join(ROOT, "dist"))
shutil.rmtree(se_bridge.se_dir(), ignore_errors=True)
faces_dir = os.path.join(ROOT, "art", "faces")
_sideline(faces_dir)

server = ThreadingHTTPServer(("127.0.0.1", 8571), studio.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

print("== app boots, tabs render ==")
page = requests.get(BASE + "/").text
check("single page serves", "CardForge Studio" in page)
check("workflow tabs present in flow order",
      all(t in page for t in ("1 &middot; Setup", "2 &middot; Illustrate",
                              "3 &middot; Cards", "4 &middot; Frame",
                              "5 &middot; Play in TTS"))
      and page.index("1 &middot; Setup") < page.index("2 &middot; Illustrate")
      < page.index("3 &middot; Cards"))
check("Strange Eons links wired in",
      "strangeeons.cgjennings.ca" in page and "github.com/CGJennings/strange-eons" in page)

print("== ILLUSTRATE: dry-run batch through the API ==")
r = requests.post(BASE + "/api/generate",
                  json={"campaign": "still_hour", "starter": True, "dry_run": True}).json()
check("starter batch accepted", r.get("started"))
check("job completes", wait_idle())
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("report shows generated faces", s["report"]["generated"] >= 5 and s["report"]["dry_run"])
check("gallery lists cards with variants",
      any(g["id"] == "sthr-appointed" and g["variants"] for g in s["gallery"]))
gal = next(g for g in s["gallery"] if g["id"] == "sthr-elias")
r = requests.post(BASE + "/api/choose",
                  json={"campaign": "still_hour", "card": "sthr-elias",
                        "file": gal["variants"][-1]}).json()
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("variant curation sticks (chosen.txt)",
      next(g for g in s["gallery"] if g["id"] == "sthr-elias")["chosen"] == gal["variants"][-1])
check("choosing a variant instantly composes the card face",
      r.get("composed") and next(g for g in s["gallery"] if g["id"] == "sthr-elias")["face"]
      and os.path.exists(os.path.join(faces_dir, "sthr-elias.png")))
check("composed face serves from /art",
      requests.get(BASE + "/art?p=art/faces/sthr-elias.png").status_code == 200)
check("gallery carries art-window geometry + placement for the editor",
      "artbox" in next(g for g in s["gallery"] if g["id"] == "sthr-elias")
      and next(g for g in s["gallery"] if g["id"] == "sthr-elias")["placement"]["scale"] == 1.0)
# stub art is uniform grey (placement would be invisible) — swap in a gradient
from PIL import Image as _Img
grad = _Img.new("RGB", (400, 300))
grad.putdata([(x % 256, (x * 7) % 256, (x * 13) % 256) for x in range(400 * 300)])
grad.save(os.path.join(ROOT, "out", "still_hour", "sthr-elias", gal["variants"][-1]))
requests.post(BASE + "/api/choose",
              json={"campaign": "still_hour", "card": "sthr-elias", "file": gal["variants"][-1]})
size_before = os.path.getsize(os.path.join(faces_dir, "sthr-elias.png"))
r = requests.post(BASE + "/api/place",
                  json={"card": "sthr-elias", "scale": 1.8, "ox": 30, "oy": -12}).json()
check("drag/zoom placement saves and recomposes", r.get("composed"))
placements = json.load(open(os.path.join(ROOT, "out", "still_hour", "placements.json"), encoding="utf-8"))
check("placement stored as data (scale 1.8, pan 30/-12)",
      placements["sthr-elias"]["scale"] == 1.8 and placements["sthr-elias"]["ox"] == 30)
check("recomposite actually changed the face",
      os.path.getsize(os.path.join(faces_dir, "sthr-elias.png")) != size_before)
requests.post(BASE + "/api/index", json={"campaign": "still_hour"})
wait_idle()
img = requests.get(BASE + "/art?p=out/still_hour/sthr-elias/" + gal["variants"][0])
check("gallery image serves", img.status_code == 200 and img.content[:4] == b"\x89PNG")
check("art endpoint refuses paths outside out/",
      requests.get(BASE + "/art?p=pipeline/build_cards.py").status_code == 404)

print("== FRAME: config, bundle, coverage ==")
cm = json.dumps(dict(se_bridge.DEFAULT_CONFIG["classmap"], asset="arkham-asset-v3"))
r = requests.post(BASE + "/api/se_save_config",
                  json={"launch_command": "echo SE {script}", "classmap": cm}).json()
check("SE config saves", r.get("ok"))
r = requests.post(BASE + "/api/se_bundle", json={"campaign": "still_hour"}).json()
check("bundle writes script + jobs (41 faces)", r.get("job_count") == 41
      and os.path.exists(r["script"]) and os.path.exists(r["jobs"]))
script = open(r["script"], encoding="utf-8").read()
check("jobs embedded in the SE script (no file IO in SE)",
      '"sthr-appointed"' in script and "createDefaultSheets" in script)
jobs = json.load(open(r["jobs"], encoding="utf-8"))
appointed = next(j for j in jobs if j["id"] == "sthr-appointed")
elias_back = next(j for j in jobs if j["id"] == "sthr-elias-back")
check("jobs carry the print layer (rules text, enemy stats, back text)",
      "Hold Back" in appointed["text"] and appointed.get("fight") == 4
      and appointed.get("damage") == 2
      and "Deck Size: 30" in elias_back["text"])
check("owner classmap edit landed in the script", "arkham-asset-v3" in script)
check("illustration paths flow from the index",
      json.load(open(r["jobs"], encoding="utf-8"))[0].get("illustration") is not None
      or any(j.get("illustration") for j in json.load(open(r["jobs"], encoding="utf-8"))))
r = requests.post(BASE + "/api/se_launch", json={}).json()
check("launch runs the configured command", r.get("ok"))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("coverage: only the click-composed card (front + investigator back)",
      set(s["se"]["coverage"]["framed"]) == {"sthr-elias", "sthr-elias-back"}
      and s["se"]["coverage"]["total"] == 41)

print("== GLYPHS: placeholder renderer through the app ==")
from cardforge.glyphs import glyphify, statline_runs
runs = glyphify("Test [wil] against [static] and [elder].")
check("glyphify maps known markup and passes unknown through",
      (True, "A") in runs and (True, "Q") in runs
      and any("[static]" in c for g, c in runs if not g))
check("statline interleaves numbers and glyphs",
      statline_runs(3, 2, 4, 3)[1] == (True, "A"))
r = requests.post(BASE + "/api/render_placeholders", json={}).json()
check("render action accepted", r.get("started") or r.get("ok"))
check("render completes", wait_idle(60))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("all 41 faces covered by glyph placeholders",
      len(s["se"]["coverage"]["framed"]) == 41 and not s["se"]["coverage"]["missing"])
from PIL import Image
check("rendered investigator uses the SE plugin per-class frame at 2x",
      Image.open(os.path.join(faces_dir, "sthr-elias.png")).size == (1050, 750))

print("== APPLY: framed faces -> art_urls.json -> rebuilt mod ==")
# reset to just three faces so the apply-count assertions below stay exact
shutil.rmtree(faces_dir)
os.makedirs(faces_dir, exist_ok=True)
from cardforge.backends.base import STUB_PNG
for fid in ("sthr-elias", "sthr-elias-back", "sthr-lamp"):
    with open(os.path.join(faces_dir, fid + ".png"), "wb") as f:
        f.write(STUB_PNG)
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("coverage sees the exported faces", len(s["se"]["coverage"]["framed"]) == 3)
r = requests.post(BASE + "/api/apply", json={"mode": "local"}).json()
check("apply accepted ({} cards)".format(r.get("cards")), r.get("ok") and r.get("cards") == 2)
check("rebuild completes", wait_idle(60))
urls = json.load(open(os.path.join(ROOT, "pipeline", "art_urls.json"), encoding="utf-8"))
check("art_urls.json: face + back for elias, face for lamp",
      urls["sthr-elias"]["face"].startswith("file:///")
      and "back" in urls["sthr-elias"] and "sthr-lamp" in urls)
mod = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_mod.json"), encoding="utf-8"))
bags = [o for o in mod["ObjectStates"] if o.get("ContainedObjects")]
elias = next(c for b in bags for c in b["ContainedObjects"] if c["Nickname"] == "Elias Warde")
lamp = next(c for b in bags for c in b["ContainedObjects"] if c["Nickname"] == "The Ambergrove Lamp")
check("mod carries the real face URL for Elias (incl. unique back)",
      elias["CustomDeck"]["95010"]["FaceURL"].startswith("file:///")
      and elias["CustomDeck"]["95010"]["BackURL"].startswith("file:///"))
check("unframed cards keep placeholders",
      "placehold.co" in next(c for b in bags for c in b["ContainedObjects"]
                             if c["Nickname"] == "The Appointed")["CustomDeck"]["95040"]["FaceURL"])
check("lamp face real, lamp back = the campaign player back",
      lamp["CustomDeck"]["95011"]["FaceURL"].startswith("file:///")
      and lamp["CustomDeck"]["95011"]["BackURL"].endswith("player_back.png"))

print("== CARDS CATALOG (the placement section) ==")
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("catalog lists the full card set with art boxes (45 authored + imports)",
      len(s["cards"]) >= 45 and all("artbox" in c for c in s["cards"]))
groups = {c["group"] for c in s["cards"]}
check("six deck groups (incl. Scenario cards)",
      groups == {"Investigators", "Signatures & Weaknesses", "Recollections",
                 "Scenario cards", "Encounter — The Appointed", "Encounter — The Named"})
check("group names byte-match the page's order list (em dashes)",
      all(g in page for g in groups))
check("faces_ver present for image cache-busting", isinstance(s["faces_ver"], int))
r = requests.post(BASE + "/api/compose_one", json={"card": "sthr-bell"}).json()
check("compose_one renders a single face on demand",
      r.get("composed") and os.path.exists(os.path.join(faces_dir, "sthr-bell.png")))
import base64 as _b64
from cardforge.backends.base import STUB_PNG as _stub
r = requests.post(BASE + "/api/upload_art",
                  json={"card": "sthr-bell",
                        "data_b64": "data:image/png;base64," + _b64.b64encode(_stub).decode()}).json()
check("manual upload becomes the chosen art and recomposes",
      r.get("file") == "upload_1.png"
      and json.load(open(os.path.join(ROOT, "out", "still_hour", "index.json"), encoding="utf-8"))
      ["sthr-bell"].endswith("upload_1.png"))

print("== CONTENT EDITOR: in-place text / stat / pip editing ==")
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
appt = next(c for c in s["cards"] if c["id"] == "sthr-appointed")
check("catalog ships editable content + clickable field regions",
      appt["content"]["name"] == "The Appointed" and appt["content"]["fight"] == 4
      and appt["content"]["damage"] == 2
      and {"name", "text", "fight", "damage", "horror"} <= set(appt["regions"]))
ov_path = os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json")
ov_backup = open(ov_path, encoding="utf-8").read() if os.path.exists(ov_path) else None
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-appointed", "fight": "7", "damage": "4",
                        "text": "Owner-typed rules text."}).json()
check("card_save stores overrides and recomposes the face", r.get("ok")
      and r["overrides"]["fight"] == 7 and r["overrides"]["damage"] == 4)
ov = json.load(open(ov_path, encoding="utf-8"))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
appt = next(c for c in s["cards"] if c["id"] == "sthr-appointed")
check("edits round-trip: overrides file + live catalog + overridden list",
      ov["sthr-appointed"]["fight"] == 7
      and appt["content"]["fight"] == 7 and appt["content"]["damage"] == 4
      and appt["content"]["text"] == "Owner-typed rules text."
      and set(appt["overridden"]) == {"fight", "damage", "text"})
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-appointed",
                        "fight": "", "damage": "", "text": ""}).json()
ov = json.load(open(ov_path, encoding="utf-8"))
check("empty fields clear back to the authored card",
      r.get("ok") and "sthr-appointed" not in ov)
r = requests.post(BASE + "/api/place",
                  json={"card": "sthr-bell", "scale": 1.4, "ox": 0, "oy": 0,
                        "scale_y": 2.0}).json()
placements = json.load(open(os.path.join(ROOT, "out", "still_hour",
                                         "placements.json"), encoding="utf-8"))
check("independent width/height art fit persists (scale_y)",
      r.get("composed") and placements["sthr-bell"]["scale_y"] == 2.0)
r = requests.post(BASE + "/api/art_remove", json={"card": "sthr-bell"}).json()
idx = json.load(open(os.path.join(ROOT, "out", "still_hour", "index.json"),
                     encoding="utf-8"))
check("Remove image strips the art and re-renders the bare frame",
      r.get("ok") and "sthr-bell" not in idx
      and not os.path.exists(os.path.join(ROOT, "out", "still_hour",
                                          "sthr-bell", "chosen.txt")))
check("expanded editor UI: content panel, pip steppers, size + remove controls",
      all(t in page for t in ("cc_stats", "ccSave", "Remove image",
                              "ed_scaley", "All cards", "ed_stage")))

# --- robustness: adversarial editor input must never crash the recompose ---
import http.client as _hc
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-appointed", "name": "100",
                        "traits": "42"}).json()
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
appt = next(c for c in s["cards"] if c["id"] == "sthr-appointed")
check("all-digit name/traits stay TEXT and recompose (no int-cast crash)",
      r.get("ok") and r["overrides"]["name"] == "100"
      and appt["content"]["name"] == "100")
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-appointed", "damage": "abc",
                        "horror": "999", "fight": "3.5"}).json()
check("junk pip / out-of-range / float stats are sanitized, not crashed",
      r.get("ok") and "damage" not in r["overrides"]        # 'abc' dropped
      and r["overrides"]["horror"] == 5                      # 999 clamped to MAX_PIPS
      and r["overrides"]["fight"] == "3.5")                  # kept as short token
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-appointed", "text": "z " * 5000}).json()
check("a huge rules string is length-capped, render survives", r.get("ok"))
requests.post(BASE + "/api/card_save", json={"card": "sthr-appointed"})  # clear
# malformed POST body -> 400, not a 500 / dropped connection
conn = _hc.HTTPConnection("127.0.0.1", 8571, timeout=10)
conn.request("POST", "/api/card_save", body=b"{bad json,,,",
             headers={"Content-Type": "application/json"})
resp = conn.getresponse(); resp.read()
check("malformed JSON body answers 400 (no thread crash)", resp.status == 400)
check("server still healthy after the abuse",
      requests.get(BASE + "/api/status").status_code == 200)

if ov_backup is None:
    if os.path.exists(ov_path):
        os.remove(ov_path)
else:
    with open(ov_path, "w", encoding="utf-8") as f:
        f.write(ov_backup)

print("== SCENARIO CARD TYPES (Location / Agenda / Act / Scenario / Story) ==")
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
by_type = {c["type"]: c for c in s["cards"]}
check("every scenario card type is in the catalog + editable",
      all(t in by_type for t in ("Location", "Agenda", "Act", "Scenario", "Story")))
loc = next(c for c in s["cards"] if c["id"] == "sthr-loc-keepersquarters")
check("location exposes shroud + clues content and clickable regions",
      loc["content"]["shroud"] == 2 and loc["content"]["clues"] == 2
      and {"shroud", "clues", "name", "text"} <= set(loc["regions"]))
ag = next(c for c in s["cards"] if c["type"] == "Agenda")
check("agenda exposes a doom value + region",
      ag["content"]["doom"] is not None and "doom" in ag["regions"])
# location connection symbols + per-investigator clues actually composite on
import render_placeholders as _rp
_sq = os.path.join(faces_dir, "sthr-loc-square.png")
requests.post(BASE + "/api/compose_one", json={"card": "sthr-loc-square"})
wait_idle()
_before = os.path.getsize(_sq)
check("location renders connection symbols + per-inv clues (plugin assets)",
      _rp.loc_symbol_img("Diamond") is not None
      and _rp._se_img("icons", "AHLCG-PerInvestigator") is not None
      and os.path.exists(_sq) and _before > 8000)
sov = os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json")
sov_bak = open(sov, encoding="utf-8").read() if os.path.exists(sov) else None
r = requests.post(BASE + "/api/card_save",
                  json={"card": "sthr-loc-keepersquarters",
                        "shroud": "5", "clues": "4"}).json()
check("editing a location's shroud/clues round-trips + recomposes",
      r.get("ok") and r["overrides"]["shroud"] == 5 and r["overrides"]["clues"] == 4)
requests.post(BASE + "/api/card_save", json={"card": "sthr-loc-keepersquarters"})
from PIL import Image as _Iscn
# APPLY wiped art/faces earlier; compose the two on demand to check the frames
requests.post(BASE + "/api/compose_one", json={"card": "sthr-loc-keepersquarters"})
requests.post(BASE + "/api/compose_one", json={"card": "sthr-agenda-hour1"})
wait_idle()
check("scenario faces render on the real plugin frames (portrait + landscape)",
      _Iscn.open(os.path.join(faces_dir, "sthr-loc-keepersquarters.png")).size == (750, 1050)
      and _Iscn.open(os.path.join(faces_dir, "sthr-agenda-hour1.png")).size == (1050, 750))
# HARD RULE (docs/design/FIDELITY_AUDIT.md): every card type must match the
# official printed aspect — portrait 0.714, landscape 1.400 (agenda/act).
_ASPECT = {"sthr-elias": 1.400, "sthr-appointed": 0.714, "sthr-lamp": 0.714,
           "sthr-loc-keepersquarters": 0.714, "sthr-scenario-lighthouse": 0.714,
           "sthr-story-firstdark": 0.714, "sthr-agenda-hour1": 1.400,
           "sthr-act-ninthdeath": 1.400}
for _cid in _ASPECT:
    requests.post(BASE + "/api/compose_one", json={"card": _cid})
wait_idle()
_bad = []
for _cid, _want in _ASPECT.items():
    _im = _Iscn.open(os.path.join(faces_dir, _cid + ".png"))
    if abs(_im.width / _im.height - _want) > 0.01:
        _bad.append("%s=%.3f(want %.3f)" % (_cid, _im.width / _im.height, _want))
check("HARD RULE: all card types match the official card aspect ratio"
      + (" — OFF: " + ", ".join(_bad) if _bad else ""), not _bad)
if sov_bak is None:
    if os.path.exists(sov):
        os.remove(sov)
else:
    open(sov, "w", encoding="utf-8").write(sov_bak)

print("== SPOILER SHIELD + AUTO-BUILD ==")
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("encounter cards flagged as spoilers",
      next(g for g in s["gallery"] if g["id"] == "sthr-appointed")["spoiler"] is True
      and next(g for g in s["gallery"] if g["id"] == "sthr-elias")["spoiler"] is False)
check("spoiler shield present in the UI", "spoiler shield" in page and "Auto-build ALL" in page)
r = requests.post(BASE + "/api/auto", json={"campaign": "still_hour", "dry_run": True}).json()
check("auto-build accepted", r.get("started"))
check("auto-build chain completes (generate->index->compose->apply->rebuild)", wait_idle(180))
auto_urls = json.load(open(os.path.join(ROOT, "pipeline", "art_urls.json"), encoding="utf-8"))
auto_cards = {k: v for k, v in auto_urls.items() if not k.startswith("_")}
check("auto-build produced a fully-arted mod with zero curation",
      len(auto_cards) == 36 and all(v["face"].startswith("file:///")
                                    for v in auto_cards.values()))
check("campaign deck backs ride along in every apply",
      auto_urls.get("_player_back", "").endswith("player_back.png")
      and auto_urls.get("_encounter_back", "").endswith("encounter_back.png"))

print("== ONE-CLICK: Compose & Export to TTS ==")
r = requests.post(BASE + "/api/export_tts", json={"campaign": "still_hour"}).json()
check("export chain accepted", r.get("started"))
check("export chain completes", wait_idle(120))
urls = json.load(open(os.path.join(ROOT, "pipeline", "art_urls.json"), encoding="utf-8"))
url_cards = {k: v for k, v in urls.items() if not k.startswith("_")}
check("all 36 cards exported with file:/// faces",
      len(url_cards) == 36 and all(v["face"].startswith("file:///")
                                   for v in url_cards.values()))
mod = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_mod.json"), encoding="utf-8"))
bags = [o for o in mod["ObjectStates"] if o.get("ContainedObjects")]
allcards = [c for b in bags for c in b["ContainedObjects"]]
check("every card in the mod carries a composed face",
      all(c["CustomDeck"][list(c["CustomDeck"])[0]]["FaceURL"].startswith("file:///")
          for c in allcards))
check("chosen art composited into the exported elias face",
      "sthr-elias" in urls and os.path.getsize(
          os.path.join(faces_dir, "sthr-elias.png")) > 8000)

print("== SEED PICKER: Step-0 portraits in the app ==")
chars_path = os.path.join(ROOT, "campaigns", "still_hour", "characters.json")
chars_backup = open(chars_path, encoding="utf-8").read()
r = requests.post(BASE + "/api/seeds",
                  json={"campaign": "still_hour", "dry_run": True, "variants": 4}).json()
check("seeds job accepted", r.get("started"))
check("seeds job completes", wait_idle(60))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("seed candidates surface in status (5 chars x 4)",
      len(s["seeds"]) == 5 and all(len(v["files"]) == 4 for v in s["seeds"].values()))
check("seed picker rendered in the UI", "seedblock" in page and "seed_pick" in page)
pick = s["seeds"]["elias"]["files"][2]
r = requests.post(BASE + "/api/seed_pick",
                  json={"campaign": "still_hour", "character": "elias",
                        "file": pick}).json()
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("picking a seed stores it as the character's canonical ref",
      r.get("ok") and s["seeds"]["elias"]["picked"] == pick
      and json.load(open(chars_path, encoding="utf-8"))
      ["elias"]["refs"][0].endswith(pick))
check("seed_pick rejects a bogus file",
      requests.post(BASE + "/api/seed_pick",
                    json={"character": "elias", "file": "nope.png"}).json()
      .get("ok") is False)
with open(chars_path, "w", encoding="utf-8") as f:
    f.write(chars_backup)

print("== MODEL PICKER: choose the checkpoint from the app ==")
camp_path = os.path.join(ROOT, "campaigns", "still_hour", "campaign.json")
camp_backup = open(camp_path, encoding="utf-8").read()
r = requests.post(BASE + "/api/models",
                  json={"campaign": "still_hour", "dry_run": True}).json()
check("models lists backend checkpoints (dry backend)",
      r.get("ok") and r["models"] == ["dry-model-a.safetensors",
                                      "dry-model-b.safetensors"])
check("models reports the campaign's current checkpoint",
      r.get("current") == json.load(open(camp_path, encoding="utf-8"))["checkpoint"])
r = requests.post(BASE + "/api/model_set",
                  json={"campaign": "still_hour",
                        "checkpoint": "dry-model-b.safetensors"}).json()
check("model_set writes campaign.json",
      r.get("ok") and json.load(open(camp_path, encoding="utf-8"))
      ["checkpoint"] == "dry-model-b.safetensors")
check("model_set survives a status round-trip",
      requests.get(BASE + "/api/status?campaign=still_hour").json()
      ["checkpoint"] == "dry-model-b.safetensors")
check("model_set rejects empty",
      requests.post(BASE + "/api/model_set", json={"checkpoint": " "}).json()
      .get("ok") is False)
check("models reports the backend's ACTIVE checkpoint (dry)",
      requests.post(BASE + "/api/models",
                    json={"campaign": "still_hour", "dry_run": True}).json()
      .get("active") == "dry-model-a.safetensors")
with open(camp_path, "w", encoding="utf-8") as f:
    f.write(camp_backup)
check("zoom lightbox + refresh button + model picker in the UI",
      all(x in page for x in ("zoomOpen", "zoom_img", "modelsLoad",
                              "refresh the gallery")))
check("category chips filter both the Cards grid and the gallery",
      all(x in page for x in ("chips_cards", "chips_gal", "setGroup",
                              "renderGallery")))

print("== PROMPT BOXES: per-card A1111-style prompts + house style ==")
ov_path = os.path.join(ROOT, "campaigns", "still_hour", "prompt_overrides.json")
if os.path.exists(ov_path):
    os.remove(ov_path)
r = requests.post(BASE + "/api/prompt_get",
                  json={"campaign": "still_hour", "card": "sthr-appointed"}).json()
check("prompt_get returns the composed prompt (scene + house style)",
      r.get("ok") and "silhouette" in r["positive"].lower()
      and "painterly" in r["positive"] and "watermark" in r["negative"])
check("prompt_get refuses text-only faces",
      requests.post(BASE + "/api/prompt_get",
                    json={"card": "sthr-elias-back"}).json().get("ok") is False)
r = requests.post(BASE + "/api/prompt_save",
                  json={"campaign": "still_hour", "card": "sthr-appointed",
                        "positive": "MY CUSTOM APPOINTED PROMPT",
                        "negative": ""}).json()
check("prompt override saves", r.get("ok")
      and json.load(open(ov_path, encoding="utf-8"))
      ["sthr-appointed"]["positive"] == "MY CUSTOM APPOINTED PROMPT")
pdir = os.path.join(ROOT, "out", "still_hour", "payloads")
# clean slate for this card: earlier sections already generated its seeds
os.remove(os.path.join(ROOT, "state", "still_hour.ledger.json"))
for f in list(os.listdir(pdir)):
    if f.startswith("sthr-appointed"):
        os.remove(os.path.join(pdir, f))
requests.post(BASE + "/api/generate",
              json={"campaign": "still_hour", "only": "sthr-appointed",
                    "variants": 1, "dry_run": True})
wait_idle(30)
pl = [json.load(open(os.path.join(pdir, f), encoding="utf-8"))
      for f in os.listdir(pdir) if f.startswith("sthr-appointed")]
check("batch generation uses the override verbatim",
      any(p.get("prompt") == "MY CUSTOM APPOINTED PROMPT" for p in pl))
r = requests.post(BASE + "/api/prompt_save",
                  json={"campaign": "still_hour", "card": "sthr-appointed",
                        "positive": "", "negative": ""}).json()
check("prompt override clears back to composed",
      r.get("ok") and "sthr-appointed" not in
      json.load(open(ov_path, encoding="utf-8")))
style_backup = json.load(open(camp_path, encoding="utf-8"))["style_positive"]
r = requests.post(BASE + "/api/style_save",
                  json={"campaign": "still_hour",
                        "style_positive": "TEST STYLE"}).json()
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("house style edits from the app and shows in status",
      r.get("ok") and s["style"]["positive"] == "TEST STYLE")
requests.post(BASE + "/api/style_save",
              json={"campaign": "still_hour", "style_positive": style_backup})
check("prompt boxes present in the UI",
      all(x in page for x in ("ed_pos", "ed_neg", "edGenerate",
                              "style_pos", "House style")))
requests.post(BASE + "/api/generate",
              json={"campaign": "still_hour", "only": "sthr-appointed",
                    "variants": 1, "dry_run": True, "reroll": True})
wait_idle(30)
seeds_seen = {json.load(open(os.path.join(pdir, f), encoding="utf-8"))["seed"]
              for f in os.listdir(pdir) if f.startswith("sthr-appointed")}
check("reroll generates with a fresh seed (not the fixed one)",
      len(seeds_seen) > 1)
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("gallery flags dry-run stubs so the UI can hide them",
      all("stubs" in g for g in s["gallery"])
      and any(g["stubs"] for g in s["gallery"]))
check("reroll + stub filtering in the UI",
      "Reroll" in page and "stubs" in page)
check("choosing art from the gallery opens the drag/resize editor",
      "useAndEdit" in page and "openEditor" in page
      and "Move / resize art" in page)

print("== ADVANCED: any-card generation, defaults, LoRA strengths ==")
chars_path2 = os.path.join(ROOT, "campaigns", "still_hour", "characters.json")
chars_backup2 = open(chars_path2, encoding="utf-8").read()
camp_backup3 = open(camp_path, encoding="utf-8").read()
r = requests.post(BASE + "/api/gen_settings",
                  json={"campaign": "still_hour", "steps": 7, "cfg": 3.5,
                        "sampler": ""}).json()
check("generation defaults save (overrides_all)",
      r.get("ok") and r["overrides_all"] == {"steps": 7, "cfg": 3.5})
for f in list(os.listdir(pdir)):
    if f.startswith("sthr-bell"):
        os.remove(os.path.join(pdir, f))
requests.post(BASE + "/api/generate",
              json={"campaign": "still_hour", "only": "sthr-bell",
                    "variants": 1, "dry_run": True, "reroll": True,
                    "cfg": 9.0}).json()
wait_idle(30)
pay = [json.load(open(os.path.join(pdir, f), encoding="utf-8"))
       for f in os.listdir(pdir) if f.startswith("sthr-bell")]
check("campaign defaults + one-off settings reach the payload "
      "(steps=7 default, cfg=9 override)",
      any(p["steps"] == 7 and p["cfg_scale"] == 9.0 for p in pay))
r = requests.post(BASE + "/api/lora_save",
                  json={"campaign": "still_hour",
                        "characters": {"elias": {"lora": "elias_v1",
                                                 "weight": 0.65}}}).json()
chars_now = json.load(open(chars_path2, encoding="utf-8"))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("LoRA name + strength persist and surface in status",
      r.get("ok") and chars_now["elias"]["lora"] == "elias_v1"
      and chars_now["elias"]["weight"] == 0.65
      and s["characters"]["elias"]["weight"] == 0.65
      and "description" in chars_now["elias"])
check("advanced tab present (card picker, settings, LoRA rows)",
      all(x in page for x in ("adv_card", "advGenerate", "gen_settings",
                              "lora_rows", "Advanced")))
with open(chars_path2, "w", encoding="utf-8") as f:
    f.write(chars_backup2)
with open(camp_path, "w", encoding="utf-8") as f:
    f.write(camp_backup3)

print("== SETUP: self-contained vendor installs (dry-run) ==")
import shutil as _sh
from cardforge import installer, se_bridge as _seb
camp_backup2 = open(camp_path, encoding="utf-8").read()
se_cfg_backup = json.dumps(_seb.load_config())
_sh.rmtree(os.path.join(ROOT, "vendor"), ignore_errors=True)
r = requests.post(BASE + "/api/install_checkpoint",
                  json={"campaign": "still_hour", "dry_run": True}).json()
check("checkpoint install job accepted", r.get("started"))
check("checkpoint install completes", wait_idle(30))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("stub checkpoint lands in vendor/models and campaign points at it",
      len(s["vendor"]["models"]) == 1
      and s["vendor"]["models"][0].endswith("_STUB.safetensors")
      and s["checkpoint"] == s["vendor"]["models"][0])
check("a1111 launch gains --ckpt-dir vendor/models",
      "--ckpt-dir" in installer.ckpt_dir_args()
      and "vendor" in installer.ckpt_dir_args())
from cardforge import rig as _rig
rig_backup_setup = open(_rig.rig_path(), encoding="utf-8").read()
r = requests.post(BASE + "/api/install_a1111", json={"dry_run": True}).json()
check("A1111 install job accepted", r.get("started"))
check("A1111 install completes", wait_idle(30))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
rig_after = json.load(open(_rig.rig_path(), encoding="utf-8"))
check("A1111 lands in vendor/ and the rig points at it",
      s["vendor"]["a1111_installed"]
      and rig_after["a1111"]["cwd"].endswith(os.path.join("vendor", "a1111"))
      and rig_after["a1111"]["command"] == "run.bat")
check("vendored webui-user.bat forces --api",
      "--api" in open(os.path.join(ROOT, "vendor", "a1111", "webui",
                                   "webui-user.bat"), encoding="utf-8").read())
with open(_rig.rig_path(), "w", encoding="utf-8") as f:
    f.write(rig_backup_setup)
r = requests.post(BASE + "/api/install_se", json={"dry_run": True}).json()
check("SE install job accepted", r.get("started"))
check("SE install completes", wait_idle(30))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("SE lands under vendor/ and the launch command points at it",
      s["vendor"]["se_installed"]
      and "vendor" in _seb.load_config()["launch_command"])
check("setup tab + per-tab steps in the UI",
      all(x in page for x in ("Setup", "steps_setup", "steps_illustrate",
                              "renderSteps", "vendor/models")))
_sh.rmtree(os.path.join(ROOT, "vendor"), ignore_errors=True)
with open(camp_path, "w", encoding="utf-8") as f:
    f.write(camp_backup2)
_seb.save_config(json.loads(se_cfg_backup))

print("== LEDGER: dry rehearsals never block real runs ==")
from cardforge.ledger import Ledger
led = Ledger(os.path.join(ROOT, "state", "_test.ledger.json"))
led.mark("card-x", 7, dry=True)
check("dry mark resumes dry runs but not real ones",
      led.is_done("card-x", 7, dry=True) and not led.is_done("card-x", 7))
led.mark("card-x", 7)
check("real mark satisfies both modes",
      led.is_done("card-x", 7) and led.is_done("card-x", 7, dry=True))
os.remove(os.path.join(ROOT, "state", "_test.ledger.json"))

print("== BACKEND RIG: auto launch/load ==")
from cardforge import rig
rig_backup = open(rig.rig_path(), encoding="utf-8").read()
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("status carries the rig (a1111 folder pre-configured)",
      s["rig"]["a1111"]["cwd"] == "C:/SD/SDXL"
      and "--api" in s["rig"]["a1111"]["command"])
check("rig controls in the UI", "Launch backend" in page and "rig_cwd" in page)
r = requests.post(BASE + "/api/rig_save",
                  json={"campaign": "still_hour", "cwd": "/tmp/xyz",
                        "command": "run.bat --api"}).json()
check("rig_save persists via the API",
      r.get("ok") and json.load(open(rig.rig_path(), encoding="utf-8"))
      ["a1111"]["cwd"] == "/tmp/xyz")
check("rig_save keeps the config note",
      "_note" in json.load(open(rig.rig_path(), encoding="utf-8")))
# full auto-launch loop against a fake A1111 API (stdlib server, self-exits)
fake = os.path.join(ROOT, "out", "fake_a1111.py")
with open(fake, "w", encoding="utf-8") as f:
    f.write("""import threading, os
from http.server import BaseHTTPRequestHandler, HTTPServer
threading.Timer(30, lambda: os._exit(0)).start()
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        b = b'[]'
        self.send_response(200)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass
HTTPServer(('127.0.0.1', 7899), H).serve_forever()
""")
cfg = rig.load_rig()
cfg["a1111"] = {"cwd": ROOT, "command": '"{}" "{}"'.format(sys.executable, fake),
                "startup_timeout": 20}
rig.save_rig(cfg)
rig.POLL_SECONDS = 1
lines = []
try:
    ok = rig.ensure_up({"backend": "a1111", "base_url": "http://127.0.0.1:7899",
                        "name": "still_hour", "output_dir": "out/still_hour"},
                       on_log=lines.append)
except RuntimeError as e:
    ok, lines = False, lines + [str(e)]
check("backend down -> rig launches it -> API answers -> proceed",
      ok and any("up after" in l for l in lines))
check("second ensure_up is a no-op (already reachable)",
      rig.ensure_up({"backend": "a1111", "base_url": "http://127.0.0.1:7899",
                     "name": "still_hour", "output_dir": "out/still_hour"},
                    on_log=lines.append))
with open(rig.rig_path(), "w", encoding="utf-8") as f:
    f.write(rig_backup)

print("== INPAINT: blank frames from the region maps (dry-run) ==")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import template_render as T
_sh.rmtree(os.path.join(ROOT, "vendor"), ignore_errors=True)
r = requests.post(BASE + "/api/inpaint_frames",
                  json={"campaign": "still_hour", "dry_run": True}).json()
check("inpaint job accepted", r.get("started"))
check("inpaint job completes", wait_idle(60))
blanks = os.listdir(os.path.join(ROOT, "vendor", "frames"))
check("all six layouts produce blank frames",
      sorted(blanks) == ["blank_enemy.png", "blank_enemy_elite.png",
                         "blank_investigator_back.png",
                         "blank_investigator_front.png",
                         "blank_treachery.png", "blank_treachery_weakness.png"])
pay = json.load(open(os.path.join(ROOT, "out", "still_hour", "payloads",
                                  "blank_enemy.a1111.json"), encoding="utf-8"))
check("img2img payload carries mask + blend settings",
      "bytes>" in pay["mask"] and pay["inpainting_fill"] == 1
      and pay["denoising_strength"] > 0 and "no text" in pay["prompt"])
r = requests.post(BASE + "/api/compose_one", json={"card": "sthr-elias"}).json()
T.open_template("treachery")   # module state is per-process; probe directly
check("faces recompose on the blank base (BLANK_MODE)",
      r.get("composed") and T.BLANK_MODE is True)
check("mask boxes exclude the art window",
      all(k != "art" for k, _ in T.inpaint_regions("enemy", 419, 600)))
check("Rebuild blank frames button in the UI", "inpaint_frames" in page)
_sh.rmtree(os.path.join(ROOT, "vendor"), ignore_errors=True)
requests.post(BASE + "/api/compose_one", json={"card": "sthr-elias"})

print("== FONTS: official stack (Teutonic titles, Arno Pro body) ==")
import render_placeholders as RP
check("Teutonic vendored (OFL) and used for titles",
      RP._font(20, title=True).getname()[0] in ("Teutonic", "Arkhamic")
      and os.path.exists(os.path.join(ROOT, "assets", "fonts", "Teutonic-OFL.txt")))
check("body font resolves (Nimbus default, or Arno if the owner dropped it in)",
      RP._font(20).getname()[0] in ("Nimbus Roman No9 L", "Arno Pro", "DejaVu Serif"))
check("Nimbus Roman is the committed default body family (all 4 styles)",
      all(os.path.exists(os.path.join(ROOT, "assets", "fonts", n)) for n in
          ("NimbusRomNo9L-Reg.otf", "NimbusRomNo9L-RegIta.otf",
           "NimbusRomNo9L-Med.otf", "NimbusRomNo9L-MedIta.otf"))
      and RP._font(20).getname() == ("Nimbus Roman No9 L", "Regular")
      and RP._font(20, italic=True).getname()[1].endswith("Italic")
      and RP._font(20, bold=True).getname()[1] == "Bold"
      and RP._font(20, bold=True, italic=True).getname()[1] == "Bold Italic")
check("Arkhamic vendored and preferred for titles (official title face)",
      os.path.exists(os.path.join(ROOT, "assets", "fonts", "Arkhamic.ttf"))
      and RP._font(20, title=True).getname()[0] == "Arkhamic")
check("Bolton drives the big stat numerals (official stat face)",
      os.path.exists(os.path.join(ROOT, "assets", "fonts", "BoltonBold.ttf"))
      and RP._font(20, stat=True).getname()[0].startswith("Bolton"))
check("font list serves text fonts, not the icon font",
      "Teutonic.ttf" in requests.get(BASE + "/api/status").json()["fonts"]
      and all("ArkhamFontWithCodex" not in f
              for f in requests.get(BASE + "/api/status").json()["fonts"]))
r = requests.post(BASE + "/api/font_set",
                  json={"card": "sthr-bell", "title": "Teutonic.ttf",
                        "body": ""}).json()
fo = json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8"))
check("per-card font override saves and recomposes",
      r.get("ok") and fo["sthr-bell"] == {"title": "Teutonic.ttf"}
      and requests.get(BASE + "/api/status").json()
      and os.path.exists(os.path.join(ROOT, "art", "faces", "sthr-bell.png")))
r = requests.post(BASE + "/api/font_set",
                  json={"card": "sthr-bell", "title": "", "body": ""}).json()
check("font override clears back to the default stack",
      r.get("ok") and "sthr-bell" not in
      json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8")))
# the real Arkhamic is vendored now — protect it from the dry-run stub
arkhamic_path = os.path.join(ROOT, "assets", "fonts", "Arkhamic.ttf")
arkhamic_real = open(arkhamic_path, "rb").read() \
    if os.path.exists(arkhamic_path) else None
r = requests.post(BASE + "/api/install_fonts", json={"dry_run": True}).json()
check("Arkhamic install job accepted", r.get("started"))
check("Arkhamic install completes", wait_idle(30))
check("Arkhamic lands in assets/fonts", os.path.exists(arkhamic_path))
if arkhamic_real is not None:
    with open(arkhamic_path, "wb") as f:
        f.write(arkhamic_real)
else:
    os.remove(arkhamic_path)
check("font dropdowns in the card editor",
      "ed_font_title" in page and "edFontSet" in page)
check("all three font roles overridable per card (title / stat / body)",
      "ed_font_title" in page and "ed_font_stat" in page
      and "ed_font_body" in page and "edFontUpload" in page)
# global default: one pick changes every card, per-card still wins
r = requests.post(BASE + "/api/font_set",
                  json={"card": "_default", "title": "Teutonic.ttf",
                        "stat": "Bolton.ttf"}).json()
fo = json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8"))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("default fonts apply to EVERY card (global override)",
      r.get("ok") and fo["_default"]["title"] == "Teutonic.ttf"
      and s["default_fonts"]["stat"] == "Bolton.ttf")
requests.post(BASE + "/api/font_set",
              json={"card": "sthr-bell", "title": "Arkhamic.ttf"})
fo = json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8"))
merged = dict(fo.get("_default", {}), **fo.get("sthr-bell", {}))
check("a card's own font override beats the global default",
      merged["title"] == "Arkhamic.ttf" and merged["stat"] == "Bolton.ttf")
requests.post(BASE + "/api/font_set", json={"card": "sthr-bell"})
requests.post(BASE + "/api/font_set", json={"card": "_default"})
check("clearing the default returns every card to the official stack",
      "_default" not in json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8")))
check("Default fonts panel + upload controls in the UI",
      "Default fonts" in page and "dfSet" in page
      and "Upload font" in page and "upload_font" in page)
# per-text-area typography: font / size / bold / italic for one area of a card
r = requests.post(BASE + "/api/type_set",
                  json={"card": "sthr-bell", "field": "text",
                        "size": 1.3, "bold": True}).json()
fo = json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8"))
check("per-area text style saves (size + bold) under the card's fields",
      r.get("ok") and fo["sthr-bell"]["fields"]["text"]["size"] == 1.3
      and fo["sthr-bell"]["fields"]["text"]["bold"] is True)
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
bell = next(c for c in s["cards"] if c["id"] == "sthr-bell")
check("status exposes per-card type_styles for the editor",
      bell.get("type_styles", {}).get("text", {}).get("size") == 1.3)
r = requests.post(BASE + "/api/type_set",
                  json={"card": "_default", "field": "name",
                        "italic": True}).json()
check("a text area can be styled across EVERY card (_default)",
      r.get("ok") and json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8"))
      ["_default"]["fields"]["name"]["italic"] is True)
check("unknown text area is rejected",
      requests.post(BASE + "/api/type_set",
                    json={"card": "sthr-bell", "field": "bogus"}).json()
      .get("ok") is False)
requests.post(BASE + "/api/type_set", json={"card": "sthr-bell", "field": "text"})
requests.post(BASE + "/api/type_set", json={"card": "_default", "field": "name"})
check("resetting a text area clears it back to the default stack",
      "sthr-bell" not in json.load(open(RP.FONT_OVERRIDES_PATH, encoding="utf-8")))
# Phase 3: the campaign compiler
r = requests.post(BASE + "/api/campaign_compile", json={}).json()
check("compile is gated until every scenario is locked in",
      r.get("ok") is False and "locked" in r.get("message", ""))
r = requests.post(BASE + "/api/campaign_compile", json={"force": True}).json()
check("compile builds the campaign box (scenarios + cards)",
      r.get("ok") is True and r.get("scenarios", 0) >= 1 and r.get("cards", 0) >= 1)
_camp = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_campaign.json"),
                      encoding="utf-8"))
_top = _camp["ObjectStates"][0]
check("campaign box matches the SCED hierarchy (CampaignBox > ScenarioBox)",
      _top["Name"] == "Custom_Model_Bag"
      and "CampaignBox" in _top["Tags"] and "Reloadable" in _top["Tags"]
      and json.loads(_top["GMNotes"])["type"] == "CampaignBox"
      and any(json.loads(o["GMNotes"]).get("type") == "ScenarioBox"
              for o in _top["ContainedObjects"]
              if o["Name"] == "Custom_Model_Bag"))
check("campaign box carries memory-bag layout + log + guide",
      json.loads(_top["LuaScriptState"])["ml"]
      and any("CampaignLog" in (o.get("Tags") or []) for o in _top["ContainedObjects"])
      and any("CampaignGuide" in (o.get("Tags") or []) for o in _top["ContainedObjects"]))
# locked house style: one LoRA + framing rules drive EVERY card
_camp_cfg = json.load(open(os.path.join(ROOT, "campaigns", "still_hour",
                                        "campaign.json"), encoding="utf-8"))
check("house style locked in the campaign",
      "cosmic horror" in _camp_cfg["style_positive"]
      and "painted digital art" in _camp_cfg["style_positive"])
# the house style must describe the ARTIST'S HAND only — lighting, palette and
# environment vary per card, or all 100+ cards come out looking copy-pasted
_scene_words = ("lamp-gold", "single warm light source", "fog", "moonlight",
                "candlelit", "ochre, oxblood")
check("house style carries no fixed lighting / palette / environment",
      not any(w in _camp_cfg["style_positive"] for w in _scene_words))
_profs = json.load(open(os.path.join(ROOT, "cardforge", "profiles",
                                     "art_profiles.json"), encoding="utf-8"))
check("type framing carries no fixed lighting either",
      not any(w in v["type_positive"]
              for k, v in _profs.items() if not k.startswith("_")
              for w in ("warm rim light", "single warm light source",
                        "atmospheric depth and fog")))
check("every art profile carries the detail-hierarchy craft rules",
      all("detail concentrated on the focal point" in v["type_positive"]
          for k, v in _profs.items() if not k.startswith("_")))
import cardforge.compose as _cmp
_pos, _neg, _par = _cmp.compose(
    {"id": "t", "art_type": "enemy", "scene": "a test", "seed": 1},
    dict(_camp_cfg, style_lora="mylora", style_lora_weight=0.7),
    _profs, None)
check("a campaign style LoRA reaches every composed prompt",
      "<lora:mylora:0.7>" in _pos)
# the sweep needs a template for EVERY card type, not just player cards
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import build_art_manifest as _bam
check("every card type maps to its own art template",
      all(_bam.ART_TYPE.get(t) in _profs for t in
          ("Investigator", "Asset", "Event", "Skill", "Treachery", "Enemy",
           "Location", "Agenda", "Act", "Scenario", "Story")))
check("generation aspect matches each card's art window",
      _profs["investigator_portrait"]["aspect"] == "portrait"
      and _profs["enemy"]["aspect"] == "landscape"
      and _profs["location"]["aspect"] == "landscape")
# the backend must be switchable from the app: Krea 2 / FLUX checkpoints
# don't load in classic A1111, so a Comfy setup has to be selectable
_r = requests.post(BASE + "/api/backend_set", json={"backend": "comfy"}).json()
check("backend switches to ComfyUI from the app",
      _r.get("ok") and requests.get(
          BASE + "/api/status?campaign=still_hour").json()["backend"] == "comfy")
check("an unknown backend is rejected",
      requests.post(BASE + "/api/backend_set",
                    json={"backend": "nope"}).json().get("ok") is False)
requests.post(BASE + "/api/backend_set", json={"backend": "a1111"})
check("backend picker present in the UI", "backend_set" in page)
# a written campaign must be importable into its OWN space, not merged into
# whatever campaign happens to be open
import shutil as _sh
_r = requests.post(BASE + "/api/campaign_new", json={"name": "Selftest Camp"}).json()
_cid = _r.get("id")
check("a new campaign can be created from the app",
      _r.get("ok") and os.path.isdir(os.path.join(ROOT, "campaigns", _cid)))
check("creating the same campaign twice is refused",
      requests.post(BASE + "/api/campaign_new",
                    json={"name": "Selftest Camp"}).json().get("ok") is False)
_feed = json.dumps({"cards": [{"id": "st-x1", "type": "Location",
                               "name": "Test Place", "shroud": 1}]})
_r = requests.post(BASE + "/api/campaign_import",
                   json={"data": _feed, "campaign": _cid}).json()
check("a campaign feed imports into the chosen campaign",
      _r.get("ok") and "st-x1" in _r.get("created", []))
check("the import did not touch another campaign",
      "st-x1" not in open(os.path.join(
          ROOT, "campaigns", "still_hour", "card_overrides.json"),
          encoding="utf-8").read())
_sh.rmtree(os.path.join(ROOT, "campaigns", _cid), ignore_errors=True)
_sh.rmtree(os.path.join(ROOT, "out", _cid), ignore_errors=True)
for _f in (os.path.join(ROOT, "pipeline", _cid + "_imported_spec.json"),
           os.path.join(ROOT, "art", "faces", "st-x1.png")):
    if os.path.exists(_f):
        os.remove(_f)
check("New campaign button present in the UI", "campNew" in page)
# BUILD FROM SCRATCH, no AI: a new campaign starts empty and cards can be made
# by hand on their real templates
_r = requests.post(BASE + "/api/campaign_new", json={"name": "Scratch SelfTest"}).json()
_sc = _r.get("id")
check("a brand-new campaign starts genuinely empty",
      len(requests.get(BASE + "/api/status?campaign=" + _sc).json()["cards"]) == 0)
_made = []
for _t in ("Location", "Enemy", "Investigator", "Asset"):
    _c = requests.post(BASE + "/api/card_new",
                       json={"campaign": _sc, "type": _t,
                             "name": "Test " + _t}).json()
    if _c.get("ok"):
        _made.append(_c["id"])
check("cards can be created by hand, no AI or backend", len(_made) == 4)
_cards = requests.get(BASE + "/api/status?campaign=" + _sc).json()["cards"]
check("hand-made cards appear in their own campaign only",
      len(_cards) == 4
      and all(c["id"] not in [x["id"] for x in requests.get(
          BASE + "/api/status?campaign=still_hour").json()["cards"]]
          for c in _cards))
check("every hand-made card composed onto its real template",
      all(os.path.exists(os.path.join(ROOT, "art", "faces", i + ".png"))
          for i in _made))
check("a new investigator starts at 1 in every skill",
      all(_x["content"].get(_k) == 1
          for _x in _cards if _x["type"] == "Investigator"
          for _k in ("wil", "int", "com", "agi", "health", "sanity")))
check("stat pips step on left-click and right-click in the UI",
      "ccStep(" in page and "oncontextmenu" in page
      and "left-click +1" in page)
# THE TTS LOCATION MAP: the black bordered slot grid, arranged then scripted
_ms = requests.post(BASE + "/api/scenario_new",
                    json={"campaign": _sc, "name": "Map Test"}).json()["id"]
_locs = []
for _n in ("Alpha Gate", "Beta Market", "Gamma Chapel"):
    _locs.append(requests.post(BASE + "/api/card_new",
                               json={"campaign": _sc, "type": "Location",
                                     "name": _n}).json()["id"])
requests.post(BASE + "/api/scenario_save",
              json={"campaign": _sc,
                    "assignments": {_ms: {"locations": _locs}}})
_r = requests.post(BASE + "/api/map_save",
                   json={"campaign": _sc, "scenario": _ms,
                         "slots": {_locs[0]: [1, 0], _locs[1]: [2, 0],
                                   _locs[2]: [1, 1]}}).json()
check("a map layout saves against the real TTS grid",
      _r.get("ok") and _r["slots"][_locs[0]] == [1, 0]
      and _r["grid"]["rot"] == 270)
check("grid slots resolve to the measured table coordinates",
      studio.map_xz(0, 0) == (-30.24, 11.46)
      and studio.map_xz(1, 1) == (-23.64, 3.81))
_r = requests.post(BASE + "/api/map_save",
                   json={"campaign": _sc, "scenario": _ms,
                         "slots": {_locs[0]: [99, 99]}}).json()
check("out-of-range slots are clamped, never crash",
      _r.get("ok") and _r["slots"][_locs[0]] == [3, 3])
# the map is four columns because a fifth lands on the encounter deck
_g = requests.get(BASE + "/api/status?campaign=" + _sc).json()["scenarios"]
check("the grid is the four columns the real table has room for",
      _g["grid"]["cols"] == 4 and _g["grid"]["rows"] == 4)
check("a fifth column would collide with the encounter deck",
      abs(studio.map_xz(4, 0)[0] -
          [f["x"] for f in _g["furniture"] if f["key"] == "encounter"][0]) < 1.0)
check("the preview knows the rest of the table, not just the map",
      {f["key"] for f in _g["furniture"]} >=
      {"encounter", "agenda_deck", "act_deck", "setup_aside"})
check("table preview + draggable connectors present in the UI",
      "pvDraw" in page and "pvToggle" in page and "mnub" in page
      and "MAP_LINK_FROM" in page and "pvclash" in page)
requests.post(BASE + "/api/map_save",
              json={"campaign": _sc, "scenario": _ms,
                    "slots": {_locs[0]: [1, 0], _locs[1]: [2, 0],
                              _locs[2]: [1, 1]}})
# CONNECTIONS: one click links two locations, both sides in one move
_r = requests.post(BASE + "/api/map_connect",
                   json={"campaign": _sc, "scenario": _ms,
                         "a": _locs[0], "b": _locs[1]}).json()
check("connecting two locations succeeds and mints their symbols",
      _r.get("ok") and _r["symbols"][_locs[0]]
      and _r["symbols"][_locs[0]] != _r["symbols"][_locs[1]])
_by = {c["id"]: c for c in
       requests.get(BASE + "/api/status?campaign=" + _sc).json()["cards"]}


def _conns(_i):
    return [x.get("symbol") for x in
            _by[_i]["content"].get("connections") or []]


check("both cards print the other's symbol, exactly as the game does",
      _conns(_locs[0]) == [_by[_locs[1]]["content"]["icons"]]
      and _conns(_locs[1]) == [_by[_locs[0]]["content"]["icons"]])
check("a location that had no symbol also got a colour",
      _by[_locs[0]]["content"].get("color"))
requests.post(BASE + "/api/map_connect",
              json={"campaign": _sc, "scenario": _ms,
                    "a": _locs[0], "b": _locs[2]})
_r = requests.post(BASE + "/api/map_connect",
                   json={"campaign": _sc, "scenario": _ms,
                         "a": _locs[0], "b": _locs[1],
                         "remove": True}).json()
_by = {c["id"]: c for c in
       requests.get(BASE + "/api/status?campaign=" + _sc).json()["cards"]}
check("unlinking drops the symbol from both sides only",
      _r.get("ok")
      and _by[_locs[1]]["content"]["icons"] not in _conns(_locs[0])
      and _by[_locs[2]]["content"]["icons"] in _conns(_locs[0]))
check("connecting a location to itself is refused",
      not requests.post(BASE + "/api/map_connect",
                        json={"campaign": _sc, "scenario": _ms,
                              "a": _locs[0], "b": _locs[0]}).json().get("ok"))
check("an unknown card id is refused, not rendered",
      not requests.post(BASE + "/api/map_connect",
                        json={"campaign": _sc, "scenario": _ms,
                              "a": _locs[0], "b": "no-such-card"})
      .json().get("ok"))
# CARD PROPERTIES: everything an official card carries beyond its stats,
# so a whole campaign can be typed in without ever opening a JSON file
_pc = requests.post(BASE + "/api/card_new",
                    json={"campaign": _sc, "type": "Enemy",
                          "name": "Prop Test"}).json()["id"]
requests.post(BASE + "/api/card_save",
              json={"campaign": _sc, "card": _pc, "class": "Mythos",
                    "elite": True, "unique": True, "weakness": False,
                    "encounter": "The Still Hour", "quantity": 3})
_p = {c["id"]: c for c in requests.get(
    BASE + "/api/status?campaign=" + _sc).json()["cards"]}[_pc]["content"]
check("class / elite / unique / encounter set / quantity save by hand",
      _p["class"] == "Mythos" and _p["elite"] is True
      and _p["unique"] is True and _p["encounter"] == "The Still Hour"
      and _p["quantity"] == 3)
check("an unticked flag returns to the authored default", not _p["weakness"])
_ag = requests.post(BASE + "/api/card_new",
                    json={"campaign": _sc, "type": "Agenda",
                          "name": "Prop Agenda"}).json()["id"]
requests.post(BASE + "/api/card_save",
              json={"campaign": _sc, "card": _ag, "index": "2",
                    "number": "1/9"})
_p = {c["id"]: c for c in requests.get(
    BASE + "/api/status?campaign=" + _sc).json()["cards"]}[_ag]["content"]
check("agenda numbering is hand-editable and keeps '1/9' as written",
      str(_p["index"]) == "2" and _p["number"] == "1/9")
check("every field the campaign's cards use has an editor control",
      not [k for c in json.load(open(os.path.join(
          ROOT, "pipeline", "stillhour_cards_spec.json"), encoding="utf-8"))
          for k in c
          if k not in set(studio.rp_keys()) | {"id", "type"}])
check("card properties panel present in the UI",
      "cc_props" in page and "ccPropsDraw" in page and "CC_PROPS" in page
      and "elderSign" in page and "wildIcons" in page)
_made += [_pc, _ag]
# a campaign's hand edits live in ITS folder — the compiler reads that folder,
# so anything written elsewhere would be invisible when the box is built
check("edits land in the campaign's own folder",
      _locs[0] in json.load(open(os.path.join(
          ROOT, "campaigns", _sc, "card_overrides.json"), encoding="utf-8")))
check("and nowhere near another campaign's",
      _locs[0] not in json.load(open(os.path.join(
          ROOT, "campaigns", "still_hour", "card_overrides.json"),
          encoding="utf-8")))
# the connections travel into the compiled box as drawable line segments
_lockable = requests.get(BASE + "/api/status?campaign=" + _sc).json()["scenarios"]
_asg = dict(_lockable["assignments"])
for _k in _asg:
    _asg[_k]["_locked"] = True
requests.post(BASE + "/api/scenario_save",
              json={"campaign": _sc, "assignments": _asg})
_cmp = requests.post(BASE + "/api/campaign_compile",
                     json={"campaign": _sc}).json()
check("a laid-out scenario compiles", _cmp.get("ok"))
_boxes = []


def _find_boxes(o):
    if isinstance(o, dict):
        if "ScenarioBox" in (o.get("Tags") or []):
            _boxes.append(o)
        for _v in o.values():
            _find_boxes(_v)
    elif isinstance(o, list):
        for _v in o:
            _find_boxes(_v)


if _cmp.get("ok"):
    _find_boxes(json.load(open(os.path.join(ROOT, _cmp["out"]),
                               encoding="utf-8")))
_states = [json.loads(b["LuaScriptState"]) for b in _boxes]
check("the compiled box scripts the arranged positions",
      any(s.get("ml") for s in _states))
check("and writes only what SCED's memory bag reads back (ml)",
      all(set(s) <= {"ml", "setupButton"} for s in _states))
# …and the cards themselves tell SCED they are connected, in its own shape
_lc = []


def _find_locs(o):
    if isinstance(o, dict):
        if o.get("Name") == "Card" and o.get("GMNotes"):
            try:
                _md = json.loads(o["GMNotes"])
            except ValueError:
                _md = {}
            if _md.get("type") == "Location":
                _lc.append(_md)
        for _v in o.values():
            _find_locs(_v)
    elif isinstance(o, list):
        for _v in o:
            _find_locs(_v)


for _b in _boxes:
    _find_locs(_b)
check("locations carry SCED's own connection metadata (icons + connections)",
      any(m.get("locationFront", {}).get("connections") for m in _lc)
      and all(m["locationFront"]["icons"][:1].isupper()
              for m in _lc if m.get("locationFront", {}).get("icons")))
if _cmp.get("ok") and os.path.exists(os.path.join(ROOT, _cmp["out"])):
    os.remove(os.path.join(ROOT, _cmp["out"]))
check("map grid + connect mode present in the UI",
      "mapOpen" in page and "mapgrid" in page and "map_mode_link" in page
      and "mapConnect" in page.replace("map_connect", "mapConnect")
      and "maplines" in page)
check("scenario buttons survive a name with spaces (attribute escaping)",
      "jsAttr(sc.name" in page)
_made += _locs
check("a hand-made card can be deleted",
      requests.post(BASE + "/api/card_delete",
                    json={"campaign": _sc, "card": _made[0]}).json().get("ok"))
check("New card control present in the UI", "cardNew" in page and "nc_type" in page)
_sh.rmtree(os.path.join(ROOT, "campaigns", _sc), ignore_errors=True)
_sh.rmtree(os.path.join(ROOT, "out", _sc), ignore_errors=True)
for _f in [os.path.join(ROOT, "pipeline", _sc + "_cards_spec.json"),
           os.path.join(ROOT, "pipeline", _sc + "_imported_spec.json")] + \
          [os.path.join(ROOT, "art", "faces", i + ".png") for i in _made]:
    if os.path.exists(_f):
        os.remove(_f)
# connection edits land in the shared overrides file — take the test's back out
_ovp = os.path.join(ROOT, "campaigns", "still_hour", "card_overrides.json")
check("the test campaign left no edits in the owner's campaign",
      not any(_i in json.load(open(_ovp, encoding="utf-8")) for _i in _made))
# a FRESH CLONE ships no composed faces (art/ is gitignored) — the app must
# render them itself or it opens completely empty with nothing to click
import shutil as _sh
_fd = os.path.join(ROOT, "art", "faces")
_tmp = _fd + ".freshclone"
_sh.rmtree(_tmp, ignore_errors=True)
os.rename(_fd, _tmp)
try:
    _n = studio.ensure_faces()
    check("a fresh clone composes its card faces on first run", _n >= 45)
finally:
    _sh.rmtree(_fd, ignore_errors=True)
    os.rename(_tmp, _fd)
check("Spawn campaign box wired in the UI",
      "campCompile" in page and "campaign_compile" in page)
check("typography panel (font/size/bold/italic per area) in the UI",
      "ed_typebar" in page and "tyBind" in page and "ty_bold" in page
      and "ty_italic" in page and "ty_size" in page)
# symbol palette: insert Arkham glyph tokens into the text areas
check("symbol palette + insert wiring in the UI",
      "ed_symbols" in page and "symInsert" in page and "symInit" in page
      and "[action]" in page and "[fast]" in page and "[wil]" in page)
check("glyph font served for the palette (@font-face)",
      "@font-face" in page and "ArkhamGlyph" in page)
rf = requests.get(BASE + "/font?f=ArkhamFontWithCodex.ttf")
check("/font route serves the Arkham glyph font",
      rf.status_code == 200 and len(rf.content) > 1000)
check("/font route rejects non-font paths",
      requests.get(BASE + "/font?f=../studio.py").status_code == 404)
# the renderer turns [token] markup into glyph runs (sized with the text)
import cardforge.glyphs as _gly
_runs = _gly.glyphify("[fast] Test [wil] (3). [elder]")
check("markup splits into glyph runs the renderer draws at text size",
      any(g for g, _ in _runs) and _gly.MARKUP["[action]"] == "E")
# bring-your-own-font upload lands in assets/fonts and validates
import base64 as _b64f
good = _b64f.b64encode(open(os.path.join(ROOT, "assets", "fonts",
                                         "Bolton.ttf"), "rb").read()).decode()
r = requests.post(BASE + "/api/upload_font",
                  json={"name": "SelftestByo.ttf",
                        "data_b64": "data:font/ttf;base64," + good}).json()
check("upload your own font -> appears in the font list",
      r.get("ok") and "SelftestByo.ttf" in r["fonts"]
      and os.path.exists(os.path.join(ROOT, "assets", "fonts", "SelftestByo.ttf")))
os.remove(os.path.join(ROOT, "assets", "fonts", "SelftestByo.ttf"))
r = requests.post(BASE + "/api/upload_font",
                  json={"name": "NotAFont.ttf",
                        "data_b64": "data:," + _b64f.b64encode(b"nope").decode()}).json()
check("a non-font upload is rejected, not saved",
      r.get("ok") is False
      and not os.path.exists(os.path.join(ROOT, "assets", "fonts", "NotAFont.ttf")))

print("== TTS LIVE LINK + PLUGIN REFRESH ==")
import socket as _sock
_captured = []
def _fake_tts():
    srv = _sock.socket()
    srv.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 39999)); srv.listen(1)
    conn, _ = srv.accept()
    data = b""
    conn.settimeout(3)
    try:
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
    except OSError:
        pass
    _captured.append(data)
    conn.close(); srv.close()
_t = threading.Thread(target=_fake_tts, daemon=True); _t.start()
time.sleep(0.3)
r = requests.post(BASE + "/api/tts_spawn", json={"card": "sthr-elias"}).json()
_t.join(timeout=5)
msg = json.loads(_captured[0].decode()) if _captured else {}
check("one-click drop sends spawnObjectJSON to the live TTS socket",
      r.get("ok") and msg.get("messageID") == 3
      and "spawnObjectJSON" in msg.get("script", "")
      and "Elias Warde" in msg["script"])
check("card sent with the CURRENT composed face (file:/// URL)",
      'file:///' in msg.get("script", "") and "sthr-elias.png" in msg["script"])
r = requests.post(BASE + "/api/tts_spawn", json={"card": "sthr-elias"}).json()
check("graceful message when TTS is not running",
      r.get("ok") is False and "Tabletop Simulator" in r.get("message", ""))
r = requests.post(BASE + "/api/plugin_update", json={}).json()
check("plugin refresh job accepted", r.get("started"))
check("plugin refresh completes (re-extract + recompose)", wait_idle(180))
check("templates present after refresh",
      os.path.exists(os.path.join(ROOT, "assets", "frames", "se",
                                  "templates", "AHLCG-Investigator-G.png")))
from PIL import Image as _I2
ay = _I2.open(os.path.join(faces_dir, "sthr-ayako.png")).convert("RGB")
check("no black placeholder box on art-less investigators",
      ay.getpixel((100, 300)) not in ((34, 31, 42), (24, 22, 28)))


def _window_not_black(face, xy):
    px = _I2.open(os.path.join(faces_dir, face)).convert("RGB").getpixel(xy)
    return sum(px) > 120          # frame-toned fill, never a near-black slab
check("no black box in any art-less window (enemy / treachery / asset)",
      _window_not_black("sthr-appointed.png", (375, 250))
      and _window_not_black("sthr-bell.png", (375, 250))
      and _window_not_black("sthr-lamp.png", (375, 300)))
check("TTS drop buttons in the UI", page.count("Drop into TTS") >= 2)
# Setup no longer asks for Strange Eons or a plugin extraction: the frames ship
# with the app and the renderer needs no SE. Their authors are credited instead.
check("Setup drops the SE / plugin install steps",
      "post('install_se')" not in page and "post('plugin_update')" not in page)
check("Strange Eons + plugin authors credited",
      "Thanks to" in page and "Jennings" in page and "jaqenZann" in page)
check("plugin re-extract still available as a maintenance route",
      "plugin_update" in studio.ACTIONS)

print("== WINDOWS LOCALE: repo reads survive a non-UTF-8 default ==")
import subprocess
env = dict(os.environ, PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", LC_ALL="C",
           PYTHONPATH=ROOT)
r = subprocess.run(
    [sys.executable, "-c",
     "from cardforge import se_bridge, studio;"
     "assert len(se_bridge.build_jobs()) == 41;"
     "s = studio.status('still_hour');"
     "assert len(s['cards']) >= 45 and s['campaigns']"],
    env=env, cwd=ROOT, capture_output=True, text=True)
check("status()+build_jobs OK under a cp1252-like locale (Windows default)",
      r.returncode == 0)
if r.returncode:
    print(r.stderr[-600:])

# leave the repo clean: drop the overlay and rebuild placeholders
os.remove(os.path.join(ROOT, "pipeline", "art_urls.json"))
for scr in ("build_cards.py", "bundle_mod.py", "package_download.py"):
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", scr)],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
server.shutdown()

print("\nSTUDIO SELFTEST: {} passed, {} failed".format(PASS, FAIL))
sys.exit(1 if FAIL else 0)
