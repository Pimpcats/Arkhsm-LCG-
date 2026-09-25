"""End-to-end test of tools/tts_relay against a fake TTS.

The fake speaks TTS's External Editor protocol and runs the real in-game runner
and the real bundled control-token script under Lua 5.2 (TTS's MoonSharp is a
5.2 implementation) with a mocked TTS API. A local bare repo stands in for
GitHub, so the clone -> test -> push-results loop runs for real.
"""
import json
import os
import shutil
import socket
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))
sys.path.insert(0, os.path.join(ROOT, "tests", "tts_fake"))

import relay  # noqa: E402
from fake_tts import FakeTTS, LUA  # noqa: E402
from sced_fixture import sced_table  # noqa: E402

pytestmark = pytest.mark.skipif(LUA is None, reason="lua5.2 not installed")

BRANCH = "relay-test"
JOB = json.load(open(os.path.join(ROOT, "tools", "tts_relay", "job.json"), encoding="utf-8"))
SNAPSHOT = [p["file"] for p in JOB["payloads"]] + ["tools/tts_relay/job.json",
                                                   "tools/tts_relay/ingame_runner.lua"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sh(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def remote(tmp_path):
    """Bare repo holding a snapshot of the current working tree's relay inputs."""
    src = tmp_path / "src"
    src.mkdir()
    for rel in SNAPSHOT:
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), dest)
    sh("git", "init", "-q", "-b", BRANCH, cwd=src)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=src)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "snap", cwd=src)
    bare = tmp_path / "remote.git"
    sh("git", "clone", "-q", "--bare", str(src), str(bare), cwd=tmp_path)
    return str(bare)


def run_relay(tmp_path, remote, preexisting=None, extra=()):
    tts_port, editor_port = free_port(), free_port()
    fake = FakeTTS(tts_port, editor_port, preexisting)
    fake.start()
    try:
        rc = relay.main(["--once", "--branch", BRANCH, "--remote", remote,
                         "--workdir", str(tmp_path / "work"), "--no-screenshots",
                         "--tts-port", str(tts_port), "--editor-port", str(editor_port)]
                        + list(extra))
    finally:
        fake.close()
    latest = json.load(open(tmp_path / "work" / "results" / "latest.json", encoding="utf-8"))
    return rc, latest, fake


def test_relay_runs_build_in_fake_tts_and_pushes_results(tmp_path, remote):
    rc, latest, fake = run_relay(tmp_path, remote)
    failed = [c for c in latest["checks"] if not c["ok"]]
    assert latest["lua_errors"] == [], latest["lua_errors"]
    assert failed == [], failed
    assert latest["verdict"] == "pass" and rc == 0
    names = {c["name"] for c in latest["checks"]}
    for expected in ("every payload finished spawning", "every card has consistent SCED metadata",
                     "in-engine rules tests all pass", "control token survives save+reload",
                     "state preserved across reload", "a card can be taken out and lands on the table"):
        assert expected in names
    for expected in ("campaign box shows Place and Recall", "Place lays out every remembered object",
                     "each lands on its remembered spot",
                     "every minicard follows SCED's minicard schema",
                     "guide is a Custom_PDF with GMNotes type CampaignGuide",
                     "log draws its checkboxes, counters and write-in fields",
                     "clicking a checkbox and a counter records them",
                     "log survives save+reload with its fields", "page 2 draws the Knowledge Track",
                     "log syncs from the campaign-state token",
                     "page 1 kept its fields across the page turn",
                     "Recall puts everything back in the box"):
        assert expected in names, expected
    assert latest["passed"] >= 30
    # results reached the "GitHub" remote on their own branch
    log = subprocess.run(["git", "log", "--oneline", relay.RESULTS_BRANCH], cwd=remote,
                         capture_output=True, text=True, check=True).stdout
    assert "passed" in log
    # runner source was sent verbatim after the RELAY header
    assert "local RELAY = {" in fake.executed[0]


BOARD_CHECKS = (
    "control shows Memory / Dissonance / Hour counters",
    "Memory counter +2",
    "Hour counter advances the Hourglass",
    "counters persist through save+reload",
    "board finds both campaign locations by metadata id",
    "a location with an unknown fact stays on its front",
    "a closed location is labelled CLOSED",
    "unlocking the flip fact turns the location to its back",
    "the CLOSED label comes off once every fact is known (Part II)",
    "it manifests at the location farthest from the investigators",
    "its card carries a Hold Back button",
    "Hold Back drops one stage and rewinds one Hour",
    "at Unseen it leaves the board",
    "it cannot be defeated: removed from play, it returns",
    "Emerging adds a Hunt button",
    "Hunt moves it one location toward its prey",
    "both investigators are found by card metadata",
    "each investigator card has a Memory button",
    "each investigator card shows Years",
    "the card's Memory button follows the count",
    "it manifests at the location away from both investigators",
    "it hunts the investigator with the most Memory (not merely the nearest)",
    "an investigator at its location holds it there (Rules Reference: Hunter)",
    "when another investigator has more Memory, the prey changes",
    "Age adds Years for defeat, danger and leaning (4)",
    "a second Age in the same interlude is refused",
    "the investigator card has both leaning tallies",
    "two Dissonance raises are not leaning",
    "4 Memory on loop powers is leaning",
    "the card shows the tallies",
    "the tallies clear when the next loop begins",
    "the next interlude reaches Weathered",
    "the investigator card shows Years and bracket",
    "Years persist through save+reload",
)

SCED_CHECKS = (
    "SCED chaos bag found (ChaosBagApi.findChaosBag)",
    "entering Glitch puts 1 [static] in the chaos bag",
    "entering Noticed puts a 2nd [static] in the chaos bag",
    "SCED's own bag state still reads (ChaosBagApi.getChaosBagState)",
    "drawing a [static] from the bag raises Dissonance by 1",
    "back to Calm removes the [static] tokens again",
    "SCED clue spawn is held back while closed (TokenSpawnTrackerApi)",
    "SCED clue spawn is released for the opened location",
    "SCED skill tracker shows the aged skills (wil +1, com -1)",
    "state is mirrored into the campaign log",
    "the campaign log's saved data (what SCED exports) carries the state",
    "a fresh control token adopts the imported state",
)


def _assert_clean_pass(latest):
    failed = [c for c in latest["checks"] if not c["ok"]]
    assert latest["lua_errors"] == [], latest["lua_errors"]
    assert failed == [], failed
    assert latest["verdict"] == "pass"
    return {c["name"] for c in latest["checks"]}


def test_board_wiring_on_a_vanilla_table(tmp_path, remote):
    rc, latest, _ = run_relay(tmp_path, remote)
    names = _assert_clean_pass(latest)
    for expected in BOARD_CHECKS + ("vanilla table: [static] counted without touching any bag",):
        assert expected in names, expected
    assert not any(n in names for n in SCED_CHECKS)


def test_board_wiring_on_an_sced_table(tmp_path, remote):
    rc, latest, _ = run_relay(tmp_path, remote, preexisting=sced_table())
    names = _assert_clean_pass(latest)
    for expected in BOARD_CHECKS + SCED_CHECKS:
        assert expected in names, expected
    assert any("control sees SCED" in n for n in latest["notes"])
    assert any("SCED detected" in n for n in latest["notes"])
    assert rc == 0


def test_relay_only_removes_its_own_objects(tmp_path, remote):
    # SCED is recognised by its GUID reference handler (its playmats carry no
    # identifying tag: in real TTS a "Playermat" tag check never matched)
    owner_obj = {"Name": "BlockSquare", "Nickname": "GUID Reference Handler", "GUID": "123456",
                 "Transform": {"posX": 0, "posY": 1, "posZ": 0}}
    leftover = {"Name": "Custom_Token", "Nickname": "old relay object", "Tags": [relay.TAG],
                "Transform": {"posX": 5, "posY": 1, "posZ": 5}}
    rc, latest, _ = run_relay(tmp_path, remote, preexisting=[owner_obj, leftover])
    assert latest["verdict"] == "pass"
    assert any("removed 1 object" in n for n in latest["notes"])
    assert any("SCED detected" in n for n in latest["notes"])


def test_lua_error_in_runner_is_reported_not_hung(tmp_path, remote):
    work = tmp_path / "broken"
    sh("git", "clone", "-q", "--branch", BRANCH, remote, str(work), cwd=tmp_path)
    runner = work / "tools" / "tts_relay" / "ingame_runner.lua"
    runner.write_text("this is not lua (\n", encoding="utf-8")
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "break", cwd=work)
    sh("git", "push", "-q", "origin", BRANCH, cwd=work)
    rc, latest, _ = run_relay(tmp_path, remote)
    assert rc == 1
    assert latest["verdict"] == "incomplete"
    assert latest["lua_errors"], "syntax error should be captured from TTS"


def test_tts_not_running_waits_instead_of_failing(tmp_path, remote):
    rc = relay.main(["--once", "--branch", BRANCH, "--remote", remote,
                     "--workdir", str(tmp_path / "w"), "--no-push",
                     "--tts-port", str(free_port()), "--editor-port", str(free_port())])
    assert rc == 2


def test_lua_long_string_never_terminates_early():
    s = 'a]]b]=]c]==]d'
    lit = relay.lua_long_string(s)
    assert lit.startswith("[===[\n") and lit.endswith("]===]")


def test_lua_quote_keeps_utf8_for_lua52():
    q = relay.lua_quote('THE STILL HOUR — "Control"\n')
    assert "\\u" not in q and "—" in q and '\\"' in q and "\\n" in q


def test_relay_falls_back_to_main_when_the_branch_is_merged_and_deleted(tmp_path, remote):
    sh("git", "branch", "-m", BRANCH, relay.FALLBACK_BRANCH, cwd=remote)
    rc, latest, _ = run_relay(tmp_path, remote)
    assert latest["branch"] == relay.FALLBACK_BRANCH
    assert latest["verdict"] == "pass" and rc == 0
