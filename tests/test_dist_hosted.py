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
