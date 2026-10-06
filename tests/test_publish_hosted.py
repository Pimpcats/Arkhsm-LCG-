"""Publishing one campaign never removes another campaign's hosted images.

pipeline/publish_hosted.py cleans dist/cards/ of images from earlier builds.
It must only remove the campaign being published (its card-id prefix and its
own chaos token), so publishing a second campaign leaves The Still Hour's
images, and therefore its published URLs, intact (and the other way round).

Runs publish() in-process against a temporary folder: no rendering, no
rebuild scripts and no git (every subprocess call is faked and checked)."""
import json
import os
import subprocess
import sys

import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import campaign_config  # noqa: E402
import publish_hosted as ph  # noqa: E402

STILL_HOUR_FILES = ("sthr-loc-square", "sthr-loc-square-back", "sthrelias", "sthrelias-back",
                    "sthr-static-token", "player_back", "encounter_back")


def png(path, color=(40, 60, 60)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (96, 96), color).save(path)


@pytest.fixture
def table(tmp_path, monkeypatch):
    """A tiny repository: two campaigns' faces and an earlier publish of each."""
    root = tmp_path
    for cid, prefix in (("still_hour", "sthr"), ("zz_test", "zztt"), ("short_one", "sth")):
        d = root / "campaigns" / cid
        d.mkdir(parents=True)
        (d / "build.json").write_text(json.dumps({"prefix": prefix}))
    faces = root / "art" / "faces"
    for name in ("sthr-loc-square", "sthr-loc-square-back", "sthrelias", "sthrelias-back",
                 "zztt-loc-a", "zztt-loc-a-back", "sth-loc-x"):
        png(str(faces / (name + ".png")))
    for name in ("player_back", "encounter_back"):
        png(str(root / "assets" / "backs" / (name + ".png")))
    cards = root / "dist" / "cards"
    cards.mkdir(parents=True)
    # an earlier publish of every campaign, plus stale images of each
    for name in STILL_HOUR_FILES + ("zztt-loc-a", "zztt-gone", "sth-loc-x", "sth-gone"):
        png(str(cards / (name + ".jpg")))

    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        assert cmd[0] != "git", "the test must never run git"
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(ph, "ROOT", str(root))
    monkeypatch.setattr(ph, "FACES", str(faces))
    monkeypatch.setattr(ph, "OUT", str(cards))
    # SHEETS_OUT is computed from OUT when the module loads: without this the stale-sheet cleanup
    # of a publish run here deletes the repository's real dist/cards/sheets
    monkeypatch.setattr(ph, "SHEETS_OUT", str(cards / "sheets"))
    monkeypatch.setattr(ph, "GUIDE", str(root / "dist" / "guide" / "none.pdf"))
    monkeypatch.setattr(ph, "build_guide", lambda: None)
    monkeypatch.setattr(ph, "render_static_token", lambda path: png(path, (90, 20, 20)))
    monkeypatch.setattr(ph.subprocess, "run", fake_run)
    return root, calls


def select(monkeypatch, root, cid, prefix, token=None):
    cfg = campaign_config.Config(id=cid, prefix=prefix, art_urls=str(root / "out" / cid / "art_urls.json"),
                                 out_dir=str(root / "out" / cid), slug=cid)
    monkeypatch.setattr(ph, "CFG", cfg)
    monkeypatch.setattr(ph, "PREFIX", prefix)
    monkeypatch.setattr(ph, "STATIC_TOKEN", token)
    # these tests are about the per-card images; sprite sheets have their own test below
    monkeypatch.setattr(ph, "pack_sheet_images", lambda: ([], {}))


def names(root):
    return sorted(os.path.splitext(f)[0] for f in os.listdir(str(root / "dist" / "cards")))


def test_second_campaign_publish_keeps_still_hour_images(table, monkeypatch):
    root, calls = table
    cards = root / "dist" / "cards"
    before = {n: (cards / (n + ".jpg")).read_bytes() for n in STILL_HOUR_FILES if n not in
              ("player_back", "encounter_back")}
    select(monkeypatch, root, "zz_test", "zztt")
    res = ph.publish("deadbeef", render=False)
    left = names(root)
    # the other campaigns' images are untouched, byte for byte
    for n, data in before.items():
        assert (cards / (n + ".jpg")).read_bytes() == data, n
    assert "sth-loc-x" in left and "sth-gone" in left
    # this campaign's stale image went; its current ones were written
    assert "zztt-gone" not in left and "zztt-loc-a" in left and "zztt-loc-a-back" in left
    assert res["ref"] == "deadbeef" and not any(c[0] == "git" for c in calls)
    urls = json.load(open(str(root / "out" / "zz_test" / "art_urls.json"), encoding="utf-8"))
    assert urls["zztt-loc-a"]["face"].startswith(
        "https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/deadbeef/dist/cards/zztt-loc-a.jpg?v=")
    assert not any(k.startswith("sthr") for k in urls)


def test_still_hour_publish_keeps_other_campaign_images(table, monkeypatch):
    root, _ = table
    select(monkeypatch, root, "still_hour", "sthr", token="sthr-static-token")
    ph.publish("cafef00d", render=False)
    left = names(root)
    assert {"zztt-loc-a", "zztt-gone", "sth-loc-x", "sth-gone"} <= set(left)
    assert {"sthr-loc-square", "sthrelias", "sthr-static-token", "player_back"} <= set(left)


def test_shorter_prefix_never_claims_a_longer_one(table, monkeypatch):
    """A campaign with prefix "sth" must not remove The Still Hour's "sthr" images."""
    root, _ = table
    select(monkeypatch, root, "short_one", "sth")
    ph.publish("0badc0de", render=False)
    left = set(names(root))
    assert {"sthr-loc-square", "sthr-loc-square-back", "sthrelias", "sthr-static-token"} <= left
    assert "sth-gone" not in left and "sth-loc-x" in left


def test_sprite_sheets_are_hosted_pinned_and_cleaned(table, monkeypatch):
    """A release packs each box's cards into sheets (pipeline/pack_sheets.py): the sheet
    URLs, grids and cell lists go to art_urls.json, pinned to the commit like every image,
    and a sheet of an earlier build that no longer exists is removed."""
    root, _ = table
    select(monkeypatch, root, "zz_test", "zztt")
    sheets = root / "dist" / "cards" / "sheets"
    png(str(sheets / "oldbox-p-face.jpg"))                   # a stale sheet
    spec = {"key": "boxA-p", "box": "boxA", "deck": 99100, "sideways": False, "cols": 2, "rows": 1,
            "cell": [585, 819], "cells": ["zztt-loc-a", "zztt-loc-b"]}

    def fake_pack():
        png(str(sheets / "boxA-p-face.jpg"))
        png(str(sheets / "boxA-p-back.jpg"))
        return [spec], {"boxA-p": {"face": "aaaaaaaaaa", "back": "bbbbbbbbbb"}}
    monkeypatch.setattr(ph, "pack_sheet_images", fake_pack)
    monkeypatch.setattr(ph, "SHEETS_OUT", str(sheets))
    ph.publish("deadbeef", render=False)
    urls = json.load(open(str(root / "out" / "zz_test" / "art_urls.json"), encoding="utf-8"))
    entry = urls["_sheets"]["boxA-p"]
    base = "https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/deadbeef/dist/cards/sheets/"
    assert entry["face"] == base + "boxA-p-face.jpg?v=aaaaaaaaaa"
    assert entry["back"] == base + "boxA-p-back.jpg?v=bbbbbbbbbb"
    assert (entry["box"], entry["deck"], entry["cols"], entry["rows"]) == ("boxA", 99100, 2, 1)
    assert entry["cells"] == ["zztt-loc-a", "zztt-loc-b"] and entry["sideways"] is False
    assert sorted(os.listdir(str(sheets))) == ["boxA-p-back.jpg", "boxA-p-face.jpg"]   # the stale one went
