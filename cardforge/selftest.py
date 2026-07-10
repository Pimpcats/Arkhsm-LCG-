#!/usr/bin/env python3
"""CardForge acceptance self-test (HANDOFF_cardforge §3, dry-run gates).

No GPU/backend needed: P0 is exercised via --dry-run payload files (the owner's
rig does the live smoke test). Run from the repo root:
    python3 cardforge/selftest.py
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardforge import runner
from cardforge.compose import compose, is_text_only
from cardforge.ledger import Ledger
from cardforge.resolver import CharacterResolver

ROOT = runner.repo_root()
PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    print("  [{}] {}".format("PASS" if cond else "FAIL", name))
    PASS, FAIL = (PASS + 1, FAIL) if cond else (PASS, FAIL + 1)


def clean(campaign):
    shutil.rmtree(os.path.join(ROOT, "out", campaign), ignore_errors=True)
    ledger = os.path.join(ROOT, "state", campaign + ".ledger.json")
    if os.path.exists(ledger):
        os.remove(ledger)


print("== P1: composition over the full still_hour manifest ==")
camp = runner.load_campaign("still_hour")
profiles = runner.load_profiles()
resolver = CharacterResolver(os.path.join(runner.campaign_dir("still_hour"), "characters.json"))
manifest = runner.load_manifest("still_hour")
composed, skipped = [], []
for job in manifest:
    if is_text_only(job):
        skipped.append(job["id"])
        continue
    char = resolver.resolve(job["character"]) if job.get("character") else None
    pos, neg, params = compose(job, camp, profiles, char)
    composed.append((job["id"], pos, neg, params))
check("36 jobs compose, 5 text-only skip", len(composed) == 36 and len(skipped) == 5)
sample = dict((c[0], c) for c in composed)["sthr-lamp"]
check("positive = scene + type framing + house style",
      "storm-lantern" in sample[1] and "still-life" in sample[1] and "cosmic horror" in sample[1])
check("negative = house negative + type negative",
      "watermark" in sample[2] and "people" in sample[2])
gold = os.path.join(ROOT, "prompts.json")
if os.path.exists(gold):
    golden = json.load(open(gold))
    ours = {cid: pos for cid, pos, _, _ in composed}
    diff = [k for k, v in golden.items() if " ".join(ours.get(k, "").split()) != " ".join(v.split())]
    check("golden fixtures (prompts.json) match", not diff)
else:
    print("  [SKIP] prompts.json golden fixtures not in repo (owner has them) — "
          "composed prompts are in the dry-run payloads for comparison")

print("== P2: character resolver ==")
elias = dict(resolver.resolve("elias"))
elias["lora"] = "elias_v1"          # as if the LoRA were trained
pos, _, _ = compose({"id": "sthr-elias", "art_type": "investigator_portrait",
                     "scene": "x", "seed": 1}, camp, profiles, elias)
check("LoRA token composes with weight", "<lora:elias_v1:0.8>" in pos)
check("trigger words ride along", "eliaswarde" in pos)
pos2, _, _ = compose({"id": "sthr-lamp", "art_type": "asset", "scene": "x", "seed": 1},
                     camp, profiles, elias)
check("character ignored where profile forbids it (asset)", "<lora:" not in pos2)

print("== P3: runner + ledger resume (dry-run, starter manifest) ==")
clean("still_hour")
r1 = runner.run_generate("still_hour", starter=True, dry_run=True,
                         only={"sthr-elias", "sthr-lamp"})
made_first = len(r1["generated"])
check("partial run generated something", made_first > 0)
r2 = runner.run_generate("still_hour", starter=True, dry_run=True)
check("resume run skipped all completed work",
      len(r2["skipped_ledger"]) == made_first)
check("resume run finished the rest (incl. the Appointed)",
      any(g["id"] == "sthr-appointed" for g in r2["generated"]))
check("text-only face skipped, never an error",
      "sthr-elias-back" in r2["skipped_text_only"])
payloads = os.listdir(os.path.join(ROOT, "out", "still_hour", "payloads"))
check("P0 dry-run payloads on disk (exact HTTP bodies)", len(payloads) >= 5)
body = json.load(open(os.path.join(ROOT, "out", "still_hour", "payloads", sorted(payloads)[0])))
check("a1111 payload shape (prompt/steps/override_settings)",
      "prompt" in body and "steps" in body and "override_settings" in body)

print("== P4: report ==")
rep = json.load(open(os.path.join(ROOT, "out", "still_hour", "report.json")))
check("report.json has per-face status", len(rep["generated"]) > 0 and "dry_run" in rep)

print("== P4b: contact sheets ==")
runner.run_contact("still_hour")
sheets = [f for f in os.listdir(os.path.join(ROOT, "out", "still_hour"))
          if f.startswith("contact_")]
check("one contact sheet per art type present", len(sheets) >= 2)

print("== P5: index.json ==")
idx = runner.run_index("still_hour")
check("index maps every generated card id", "sthr-elias" in idx and "sthr-appointed" in idx)
check("index excludes payloads/seeds dirs", "payloads" not in idx and "seeds" not in idx)

print("== P6: demo campaign runs with zero code changes ==")
clean("demo")
rd = runner.run_generate("demo", dry_run=True)
check("3 demo cards generated (variants expand per profile: 7 files)",
      len({g["id"] for g in rd["generated"]}) == 3 and len(rd["generated"]) == 7)
check("demo house style composed (not still_hour's)",
      "gothic ink" in json.load(open(os.path.join(
          ROOT, "out", "demo", "payloads", sorted(os.listdir(
              os.path.join(ROOT, "out", "demo", "payloads")))[0])))["prompt"])

print("== Comfy path: workflow injection (offline) ==")
from cardforge.backends.comfy import ComfyBackend
cb = ComfyBackend("http://x", workflows_dir=os.path.join(ROOT, "cardforge", "workflows"),
                  dry_run=True, payload_dir=os.path.join(ROOT, "out", "still_hour", "payloads"))
imgs = cb.generate("POS", "NEG", {"comfy_workflow": "workflows/txt2img_scene.json",
                                  "checkpoint": "ck.safetensors", "width": 768, "height": 1024,
                                  "steps": 30, "cfg": 5.0, "sampler": "dpmpp_2m_sde", "seed": 42},
                   "comfy_probe")
graph = json.load(open(os.path.join(ROOT, "out", "still_hour", "payloads",
                                    "comfy_probe.comfy.json")))["prompt"]
inj = {n["_meta"]["title"]: n for n in graph.values() if "_meta" in n}
check("comfy graph injected by _meta.title tags",
      inj["CF_POSITIVE"]["inputs"]["text"] == "POS"
      and inj["CF_SAMPLER"]["inputs"]["seed"] == 42
      and inj["CF_CHECKPOINT"]["inputs"]["ckpt_name"] == "ck.safetensors")
check("dry-run returns stub image bytes", imgs and imgs[0][:4] == b"\x89PNG")

print("\nCARDFORGE SELFTEST: {} passed, {} failed".format(PASS, FAIL))
sys.exit(1 if FAIL else 0)
