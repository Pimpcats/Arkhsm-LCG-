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
check("rendered investigator uses the PSD blank at native res",
      Image.open(os.path.join(faces_dir, "sthr-elias.png")).size == (1048, 738))

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
check("catalog lists all 36 cards with art boxes",
      len(s["cards"]) == 36 and all("artbox" in c for c in s["cards"]))
groups = {c["group"] for c in s["cards"]}
check("five deck groups", groups == {"Investigators", "Signatures & Weaknesses",
      "Recollections", "Encounter — The Appointed", "Encounter — The Named"})
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
      s["vendor"]["models"] == ["paintersCheckpoint_v11_STUB.safetensors"]
      and s["checkpoint"] == "paintersCheckpoint_v11_STUB.safetensors")
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
check("Arno Pro picked up for body when present (never committed)",
      RP._font(20).getname()[0] in ("Arno Pro", "DejaVu Serif"))
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
r = requests.post(BASE + "/api/install_fonts", json={"dry_run": True}).json()
check("Arkhamic install job accepted", r.get("started"))
check("Arkhamic install completes", wait_idle(30))
arkhamic_stub = os.path.join(ROOT, "assets", "fonts", "Arkhamic.ttf")
check("Arkhamic lands in assets/fonts", os.path.exists(arkhamic_stub))
os.remove(arkhamic_stub)
check("font dropdowns in the card editor",
      "ed_font_title" in page and "edFontSet" in page)

print("== WINDOWS LOCALE: repo reads survive a non-UTF-8 default ==")
import subprocess
env = dict(os.environ, PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", LC_ALL="C",
           PYTHONPATH=ROOT)
r = subprocess.run(
    [sys.executable, "-c",
     "from cardforge import se_bridge, studio;"
     "assert len(se_bridge.build_jobs()) == 41;"
     "s = studio.status('still_hour');"
     "assert len(s['cards']) == 36 and s['campaigns']"],
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
