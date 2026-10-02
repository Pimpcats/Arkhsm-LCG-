"""The replication kit works end to end: scaffold a new campaign with
tools/new_campaign.py and build it like The Still Hour (content check, card
bags, Control token, campaign box), in a throwaway copy of the repository so
the checkout is never touched."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPY = ("pipeline", "tools", "src", "assets", "cardforge")


@pytest.fixture(scope="module")
def repo():
    tmp = tempfile.mkdtemp(prefix="kit_test_")
    try:
        for d in COPY:
            if os.path.isdir(os.path.join(ROOT, d)):
                shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d),
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        os.makedirs(os.path.join(tmp, "campaigns", "still_hour"))
        for f in ("campaign.json", "build.json"):
            shutil.copy(os.path.join(ROOT, "campaigns", "still_hour", f),
                        os.path.join(tmp, "campaigns", "still_hour", f))
        os.makedirs(os.path.join(tmp, "dist"))
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run(repo, *args, lua=None):
    env = dict(os.environ, CAMPAIGN="kit_test")
    cmd = [lua] + list(args) if lua else [sys.executable] + list(args)
    r = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (args, r.stdout[-3000:], r.stderr[-3000:])
    return r.stdout


def test_scaffold_builds_and_passes(repo):
    out = json.loads(run(repo, "tools/new_campaign.py", "kit_test", "The Kit Test", "--prefix", "ktst"))
    assert out["prefix"] == "ktst" and out["slug"] == "the_kit_test"
    for f in ("build.json", "campaign.json", "scenario_manifest.json", "scenario_assignments.json",
              "specs/cards_spec.json", "specs/encounter_spec.json", "specs/print_text.json",
              "log_layout.py", "guide.md", "design.md", "assistant/production.json"):
        assert os.path.exists(os.path.join(repo, "campaigns", "kit_test", f)), f
    # the house art style comes along, without The Still Hour's own motifs
    house = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "campaign.json"), encoding="utf-8"))
    new = json.load(open(os.path.join(repo, "campaigns", "kit_test", "campaign.json"), encoding="utf-8"))
    assert new["style_negative"] == house["style_negative"] and new["checkpoint"] == house["checkpoint"]
    assert "hand-painted in oil" in new["style_positive"]
    style = json.dumps({k: new[k] for k in ("style_positive", "style_guidance", "_style_note")}).lower()
    for motif in ("echo", "afterimage", "sea", "still hour"):
        assert not re.search(r"\b" + motif + r"\b", style), motif

    # the example scenario has the official components
    enc = json.load(open(os.path.join(repo, "campaigns", "kit_test", "specs", "encounter_spec.json"),
                         encoding="utf-8"))
    text = json.load(open(os.path.join(repo, "campaigns", "kit_test", "specs", "print_text.json"),
                          encoding="utf-8"))
    acts = [c for c in enc if c["type"] == "Act"]
    assert sum(1 for c in acts if not c.get("take")) == 1 and sum(1 for c in acts if c.get("take")) == 1
    assert all(text[c["id"]].get("back_text") for c in acts)
    for c in (c for c in enc if c["type"] == "Agenda"):
        assert text[c["id"]].get("flavor") and text[c["id"]].get("back_text"), c["id"]
    locs = [c for c in enc if c["type"] == "Location"]
    assert all(text[c["id"]].get("text") for c in locs)
    assert any(c.get("unrevealed") for c in locs) and any(text[c["id"]].get("unrevealed_text") for c in locs)
    assert any("Resign" in text[c["id"]]["text"] for c in locs)
    assert any(c["type"] == "Asset" and c.get("encounter") for c in enc)

    report = run(repo, "pipeline/scenario_content.py", "--lock")
    assert "LOCKED   0 error(s)" in report, report

    run(repo, "pipeline/build_cards.py", "--local")
    run(repo, "pipeline/bundle_mod.py", "--local")
    comp = json.loads(run(repo, "pipeline/compile_campaign.py"))
    assert comp["ok"] and comp["scenarios"] == 1 and comp["cards"] > 10
    for f in ("the_kit_test.json", "the_kit_test_encounter.json", "the_kit_test_mod.json",
              "the_kit_test_bundle.lua", "the_kit_test_campaign.json"):
        assert os.path.exists(os.path.join(repo, "dist", f)), f
    mod = json.load(open(os.path.join(repo, "dist", "the_kit_test_mod.json"), encoding="utf-8"))
    assert any(o.get("Nickname") == "THE KIT TEST — Control" for o in mod["ObjectStates"])

    for name in ("lua5.4", "lua5.2"):
        lua = shutil.which(name)
        if lua:
            res = run(repo, "pipeline/verify_control.lua", "dist/the_kit_test_bundle.lua", "runCampaignTests",
                      lua=lua)
            assert "verify_control: OK" in res, (name, res)


def test_prefix_in_use_is_refused(repo):
    """A second campaign cannot reuse (or overlap) another campaign's card-id prefix."""
    env = dict(os.environ, CAMPAIGN="kit_test")
    for args in (["sthr_again", "Again", "--prefix", "sthr"],     # The Still Hour's
                 ["short_one", "Short", "--prefix", "sth"],       # begins "sthr"
                 ["long_one", "Long", "--prefix", "sthrx"]):      # begins with "sthr"
        r = subprocess.run([sys.executable, "tools/new_campaign.py"] + args, cwd=repo, env=env,
                           capture_output=True, text=True, timeout=120)
        assert r.returncode != 0 and "prefix" in (r.stderr + r.stdout), (args, r.stdout, r.stderr)
        assert not os.path.exists(os.path.join(repo, "campaigns", args[0])), args


def test_art_track(repo):
    """Scenes -> art manifest -> ChatGPT prompt pack, per campaign."""
    if not os.path.exists(os.path.join(repo, "campaigns", "kit_test")):
        run(repo, "tools/new_campaign.py", "kit_test", "The Kit Test", "--prefix", "ktst")
    run(repo, "pipeline/build_art_manifest.py")
    assert os.path.exists(os.path.join(repo, "campaigns", "kit_test", "manifest.json"))
    run(repo, "pipeline/chatgpt_art_pack.py")
    pack = open(os.path.join(repo, "campaigns", "kit_test", "art", "ART_PACK.md"), encoding="utf-8").read()
    assert "The Kit Test" in pack and "SHARED HOUSE STYLE" in pack


def test_still_hour_is_the_default(repo):
    out = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'pipeline');"
                          "from campaign_config import load; c = load('still_hour');"
                          "print(c.slug, c.prefix, c.box_id)"],
                         cwd=repo, capture_output=True, text=True, env={k: v for k, v in os.environ.items()
                                                                        if k != "CAMPAIGN"})
    assert out.stdout.split() == ["the_still_hour", "sthr", "CB-STHR"]
