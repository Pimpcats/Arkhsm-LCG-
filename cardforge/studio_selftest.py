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


# fresh slate
shutil.rmtree(os.path.join(ROOT, "out", "still_hour"), ignore_errors=True)
for f in ("state/still_hour.ledger.json", "pipeline/art_urls.json"):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        os.remove(p)
shutil.rmtree(se_bridge.se_dir(), ignore_errors=True)
faces_dir = os.path.join(ROOT, "art", "faces")
shutil.rmtree(faces_dir, ignore_errors=True)

server = ThreadingHTTPServer(("127.0.0.1", 8571), studio.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

print("== app boots, tabs render ==")
page = requests.get(BASE + "/").text
check("single page serves", "CardForge Studio" in page)
check("all three tabs present",
      all(t in page for t in ("Illustrate", "Frame &mdash; Strange Eons", "Apply to Mod")))
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
requests.post(BASE + "/api/choose",
              json={"campaign": "still_hour", "card": "sthr-elias", "file": gal["variants"][-1]})
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("variant curation sticks (chosen.txt)",
      next(g for g in s["gallery"] if g["id"] == "sthr-elias")["chosen"] == gal["variants"][-1])
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
script = open(r["script"]).read()
check("jobs embedded in the SE script (no file IO in SE)",
      '"sthr-appointed"' in script and "createDefaultSheets" in script)
check("owner classmap edit landed in the script", "arkham-asset-v3" in script)
check("illustration paths flow from the index",
      json.load(open(r["jobs"]))[0].get("illustration") is not None
      or any(j.get("illustration") for j in json.load(open(r["jobs"]))))
r = requests.post(BASE + "/api/se_launch", json={}).json()
check("launch runs the configured command", r.get("ok"))
s = requests.get(BASE + "/api/status?campaign=still_hour").json()
check("coverage: nothing framed yet", s["se"]["coverage"]["framed"] == []
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
check("rendered investigator is landscape with glyph statline drawn",
      Image.open(os.path.join(faces_dir, "sthr-elias.png")).size == (750, 523))

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
urls = json.load(open(os.path.join(ROOT, "pipeline", "art_urls.json")))
check("art_urls.json: face + back for elias, face for lamp",
      urls["sthr-elias"]["face"].startswith("file:///")
      and "back" in urls["sthr-elias"] and "sthr-lamp" in urls)
mod = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_mod.json")))
bags = [o for o in mod["ObjectStates"] if o.get("ContainedObjects")]
elias = next(c for b in bags for c in b["ContainedObjects"] if c["Nickname"] == "Elias Warde")
lamp = next(c for b in bags for c in b["ContainedObjects"] if c["Nickname"] == "The Ambergrove Lamp")
check("mod carries the real face URL for Elias (incl. unique back)",
      elias["CustomDeck"]["95010"]["FaceURL"].startswith("file:///")
      and elias["CustomDeck"]["95010"]["BackURL"].startswith("file:///"))
check("unframed cards keep placeholders",
      "placehold.co" in next(c for b in bags for c in b["ContainedObjects"]
                             if c["Nickname"] == "The Appointed")["CustomDeck"]["95040"]["FaceURL"])
check("lamp face real, lamp back still shared player back",
      lamp["CustomDeck"]["95011"]["FaceURL"].startswith("file:///")
      and "placehold.co" in lamp["CustomDeck"]["95011"]["BackURL"])

# leave the repo clean: drop the overlay and rebuild placeholders
os.remove(os.path.join(ROOT, "pipeline", "art_urls.json"))
import subprocess
for scr in ("build_cards.py", "bundle_mod.py", "package_download.py"):
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", scr)],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
server.shutdown()

print("\nSTUDIO SELFTEST: {} passed, {} failed".format(PASS, FAIL))
sys.exit(1 if FAIL else 0)
