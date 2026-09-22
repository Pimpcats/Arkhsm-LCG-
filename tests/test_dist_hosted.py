"""The committed TTS build must load on any PC: no machine-local image paths,
and every hosted card image it references exists in dist/cards/."""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILT = ["dist/the_still_hour.json", "dist/the_still_hour_mod.json",
         "dist/the_still_hour_encounter.json", "dist/downloads/the_still_hour.json",
         "dist/the_still_hour_table.json"]
HOSTED = re.compile(r"https://raw\.githubusercontent\.com/[^\"]+?/dist/cards/([^\"?/]+\.jpg)")


def test_no_local_file_urls():
    for rel in BUILT:
        assert "file:///" not in open(os.path.join(ROOT, rel), encoding="utf-8").read(), rel


def test_hosted_images_exist():
    have = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "dist", "cards", "*.jpg"))}
    for rel in BUILT:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        missing = sorted(set(HOSTED.findall(text)) - have)
        assert not missing, "{} references missing images: {}".format(rel, missing[:5])


def test_job_payloads_exist():
    job = json.load(open(os.path.join(ROOT, "tools", "tts_relay", "job.json"), encoding="utf-8"))
    for p in job["payloads"]:
        assert os.path.exists(os.path.join(ROOT, p["file"])), p["file"]


def test_card_copies_agree_across_builds():
    """A card id means one card: every copy in every build carries the same
    SCED metadata (the player/encounter bags once skipped editor overrides)."""
    seen = {}

    def walk(o, where):
        if o.get("Name") in ("Card", "CardCustom"):
            md = json.loads(o.get("GMNotes") or "{}")
            seen.setdefault(md.get("id"), {}).setdefault(
                json.dumps(md, sort_keys=True), set()).add(where)
        for c in o.get("ContainedObjects") or []:
            walk(c, where)

    for rel in BUILT + ["dist/the_still_hour_campaign.json"]:
        data = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
        for o in data.get("ObjectStates") or [data]:
            walk(o, rel)
    clash = {i: v for i, v in seen.items() if len(v) > 1}
    assert not clash, clash
