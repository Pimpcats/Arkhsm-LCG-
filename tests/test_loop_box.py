"""The scenario box's Place script (src/tts/loop_box.lua) on the fake Tabletop Simulator.

The box lays its objects out again every loop with the GUIDs they had before (self.clone, then
takeObject by GUID on the copy). What that needs to get right, one box at a time and without the
Control token (tests/test_sced_place.py plays the same on the whole emulated SCED table):

  * SCED's Token Spawn Tracker forgets the GUIDs about to be laid out before anything comes out
  * the Control token is told which box it was and what came out
  * Recall (and the Control's Clear Board) stop a Place that is still running
  * Recall takes the tokens resting on the cards it removes, and only those
  * a copy left on the table by a save taken during a Place destroys itself; the live one does not
  * one error in one step cannot leave the box "placing" for good
  * a Place is refused while other boxes' objects lie where it lays out, and never for boxes
    that share a loop's board
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))

import compile_campaign as cc  # noqa: E402
import relay  # noqa: E402
import table_presence as T  # noqa: E402

LUA = shutil.which("lua5.2")
needs_lua = pytest.mark.skipif(not LUA, reason="lua5.2 not installed")
LOOP_BOX = os.path.join(ROOT, "src", "tts", "loop_box.lua")
CONTROL = os.path.join(ROOT, "src", "tts", "control.lua")


@pytest.fixture(scope="module")
def books(tmp_path_factory):
    """The campaign's scenario boxes as the build makes them, by id."""
    out = tmp_path_factory.mktemp("campaign") / "c.json"
    assert cc.compile_campaign(str(out))["ok"]
    box = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    return {json.loads(b["GMNotes"])["id"]: b for b in box["ContainedObjects"]
            if b.get("Name") == "Custom_Model_Bag" and json.loads(b["GMNotes"]).get("type") == "ScenarioBox"}


# ------------------------------------------------------------------ the fake table --
PRELUDE = r"""
local BOX = @BOX@
local TAG = @TAG@
local out = {}
local msgs = {}
local failAt            -- a broadcast with exactly this text raises an error (a step that goes wrong)
local G = getmetatable(_ENV).__index
local realBroadcast = G.broadcastToAll
G.broadcastToAll = function(msg, color)
  msgs[#msgs + 1] = tostring(msg)
  if failAt ~= nil and msg == failAt then error("injected failure") end
  return realBroadcast(msg, color)
end
local box = spawnObjectJSON({ json = BOX })
local function count(tag)
  local n = 0
  for _, o in ipairs(getObjects()) do
    if o ~= box and o.hasTag(tag) then n = n + (o.type == "Deck" and #o.getObjects() or 1) end
  end
  return n
end
local function strays()
  local n = 0
  for _, o in ipairs(getObjects()) do
    if tostring(o.getName()):find("(placing)", 1, true) then n = n + 1 end
  end
  return n
end
local function say(pattern)
  for _, m in ipairs(msgs) do if m:find(pattern, 1, true) then return true end end
  return false
end
local function done() out.msgs = msgs ; print("@@OUT " .. JSON.encode(out)) end
"""


def run_chunk(tmp_path, book, body, extra=None):
    """Run PRELUDE + body in the fake TTS with `book` spawned as `box`; returns its `out` table."""
    sid = json.loads(book["GMNotes"])["id"]
    prelude = (PRELUDE.replace("@BOX@", relay.lua_long_string(json.dumps(book, ensure_ascii=False)))
               .replace("@TAG@", json.dumps(T.loop_tags(sid)[1])))
    path = tmp_path / "chunk.lua"
    path.write_text(prelude + (extra or "") + body, encoding="utf-8")
    r = subprocess.run([LUA, os.path.join(ROOT, "tests", "tts_fake", "mock_tts.lua"), str(path)],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    outs, errors = [], []
    for ln in r.stdout.splitlines():
        if ln.startswith("@@MSG "):
            m = json.loads(ln[6:])
            if m.get("message", "").startswith("@@OUT "):
                outs.append(m["message"][6:])
            if m.get("messageID") == 3:
                errors.append(m.get("error"))
    assert outs, r.stdout[-2000:] + r.stderr[-2000:]
    return json.loads(outs[-1]), errors


def objects_in(book):
    return len(book["ContainedObjects"])


# ------------------------------------------------------------------- the spawn tracker --
SCED_STAND_IN = r"""
-- the two SCED objects the box reaches: its GUID reference handler and its Token Spawn Tracker
local function mk(guid, nick, script)
  return spawnObjectJSON({ json = JSON.encode({ Name = "Custom_Token", GUID = guid, Nickname = nick,
    LuaScript = script, Transform = { posX = 0, posY = 1.5, posZ = 40 } }) })
end
local tracker = mk("e3fa31", "Token Spawn Tracker", [[
local spawned = {}
function hasSpawnedTokens(g) return spawned[g] == true end
function markTokensSpawned(g) spawned[g] = true end
function resetTokensSpawned(g) spawned[g] = nil end
]])
mk("123456", "GUID handler", [[
function getObjectByOwnerAndType(p) return getObjectFromGUID("e3fa31") end
]])
"""


@needs_lua
def test_place_makes_the_spawn_tracker_forget_the_guids_before_anything_comes_out(books, tmp_path):
    body = r"""
Wait.frames(function()
  local guids = {}
  for _, e in ipairs(box.getObjects()) do
    guids[#guids + 1] = e.guid
    tracker.call("markTokensSpawned", e.guid)
  end
  out.objects = #guids
  local known = function()
    local n = 0
    for _, g in ipairs(guids) do if tracker.call("hasSpawnedTokens", g) then n = n + 1 end end
    return n
  end
  out.knownBefore = known()
  box.call("buttonClick_place")
  out.knownAtOnce = known()        -- the very moment Place returns: nothing has been taken out yet
  out.onTableAtOnce = count(TAG)
  Wait.frames(function() out.onTable = count(TAG) ; done() end, 300)
end, 10)
"""
    out, errors = run_chunk(tmp_path, books["district_church"], body, SCED_STAND_IN)
    assert not errors, errors[:2]
    assert out["knownBefore"] == out["objects"] > 0
    assert out["knownAtOnce"] == 0 and out["onTableAtOnce"] == 0
    assert out["onTable"] > 0


@needs_lua
def test_a_table_without_sced_places_all_the_same(books, tmp_path):
    body = r"""
Wait.frames(function()
  out.pressed = box.call("buttonClick_place")
  Wait.frames(function() out.onTable = count(TAG) ; done() end, 300)
end, 10)
"""
    out, errors = run_chunk(tmp_path, books["district_church"], body)
    assert not errors, errors[:2]
    assert out["pressed"] == objects_in(books["district_church"]) and out["onTable"] > 0


# ------------------------------------------------------- what the Control token is told --
FAKE_CONTROL = r"""
local ctl = spawnObjectJSON({ json = JSON.encode({ Name = "Custom_Token", Nickname = "THE STILL HOUR — Control",
  Tags = { "StillHour" }, Transform = { posX = 0, posY = 1.5, posZ = 44 }, LuaScript = [[
local last
function shApiSyncBoardStaged(p) last = p ; return true end
function lastInfo() return last end
]] }) })
"""


@needs_lua
def test_the_control_token_is_told_which_box_it_was_and_what_came_out(books, tmp_path):
    book = books["district_church"]
    body = r"""
Wait.frames(function()
  box.call("buttonClick_place")
  Wait.frames(function()
    out.info = ctl.call("lastInfo")
    out.names = {}
    for _, o in ipairs(getObjects()) do
      if o ~= box and o.hasTag(TAG) then out.names[#out.names + 1] = o.getGUID() end
    end
    done()
  end, 400)
end, 10)
"""
    out, errors = run_chunk(tmp_path, book, body, FAKE_CONTROL)
    assert not errors, errors[:2]
    info = out["info"]
    assert info["box"] == "district_church" and info["name"] == book["Nickname"]
    assert len(info["guids"]) == objects_in(book)
    assert set(info["guids"]) == set(out["names"]), "the GUIDs it reports are the objects on the table"


# ------------------------------------------------------------- Recall stops a running Place --
@needs_lua
def test_recall_stops_a_place_that_is_still_running(books, tmp_path):
    book = books["district_church"]
    body = r"""
Wait.frames(function()
  out.pressed = box.call("buttonClick_place")
  Wait.frames(function()                       -- a few objects are out, the working copy holds the rest
    out.midOut = count(TAG)
    out.midPlacing = box.call("isPlacing")
    box.call("buttonClick_recall")
    out.placingAfter = box.call("isPlacing")
    out.saidStopped = say("the Place in progress was stopped")
    Wait.frames(function()
      out.later = count(TAG)                   -- nothing more comes out
      out.copies = strays()
      out.again = box.call("buttonClick_place")
      Wait.frames(function()
        out.full = count(TAG)
        out.copiesAfter = strays()
        out.refused = say("already laid out")
        box.call("buttonClick_recall")
        out.saidStoppedAgain = false
        Wait.frames(function() out.empty = count(TAG) ; done() end, 5)
      end, 400)
    end, 400)
  end, 20)
end, 10)
"""
    out, errors = run_chunk(tmp_path, book, body)
    assert not errors, errors[:2]
    assert out["midPlacing"] is True and 0 < out["midOut"]
    assert out["placingAfter"] is False and out["saidStopped"] is True
    assert out["later"] == 0, "objects kept arriving after Recall"
    assert out["copies"] == 0
    assert out["again"] == objects_in(book) and out["refused"] is False, "the next Place was refused"
    assert out["full"] > out["midOut"] and out["copiesAfter"] == 0
    assert out["empty"] == 0


@needs_lua
def test_clear_boards_cancel_leaves_no_half_layout(books, tmp_path):
    # what the Control token's Clear Board calls on every box before it clears the table
    book = books["district_church"]
    body = r"""
Wait.frames(function()
  box.call("buttonClick_place")
  Wait.frames(function()
    out.stopped = box.call("cancelPlace")
    out.stoppedTwice = box.call("cancelPlace")      -- nothing running any more
    for _, o in ipairs(getObjects()) do             -- the Control's Clear Board takes what is out
      if o ~= box and o.hasTag(TAG) then o.destruct() end
    end
    Wait.frames(function()
      out.later = count(TAG)
      out.copies = strays()
      out.again = box.call("buttonClick_place")
      Wait.frames(function() out.full = count(TAG) ; done() end, 400)
    end, 400)
  end, 20)
end, 10)
"""
    out, errors = run_chunk(tmp_path, book, body)
    assert not errors, errors[:2]
    assert out["stopped"] is True and out["stoppedTwice"] is False
    assert out["later"] == 0 and out["copies"] == 0
    assert out["again"] == objects_in(book) and out["full"] > 0


# ------------------------------------------------------------------------- tokens on cards --
@needs_lua
def test_recall_takes_the_tokens_resting_on_its_cards_and_only_those(books, tmp_path):
    body = r"""
Wait.frames(function()
  box.call("buttonClick_place")
  Wait.frames(function()
    local card
    for _, o in ipairs(getObjects()) do
      if o.type == "Card" and o.hasTag(TAG) then card = o ; break end
    end
    local p = card.getPosition()
    local function token(dx, dz, tags, locked)
      return spawnObjectJSON({ json = JSON.encode({ Name = "Custom_Token", Tags = tags, Locked = locked,
        Transform = { posX = p.x + dx, posY = p.y + 0.5, posZ = p.z + dz, scaleX = 0.3, scaleY = 0.3, scaleZ = 0.3 } }) })
    end
    local resting = token(0.2, 0, {}, false)             -- a clue on the card
    local away = token(14, 14, {}, false)                -- on no card of this box
    local pinned = token(-0.2, 0, {}, true)              -- locked: somebody else's piece
    local ignored = token(0, 0.2, { "CleanUpHelper_ignore" }, false)   -- what SCED keeps out of a clean-up
    Wait.frames(function()
      box.call("buttonClick_recall")
      Wait.frames(function()
        out.restingGone = resting.isDestroyed()
        out.awayKept = not away.isDestroyed()
        out.pinnedKept = not pinned.isDestroyed()
        out.ignoredKept = not ignored.isDestroyed()
        out.cardGone = card.isDestroyed()
        out.said = say("and 1 token(s) removed from the table.")
        done()
      end, 3)
    end, 5)
  end, 400)
end, 10)
"""
    out, errors = run_chunk(tmp_path, books["district_church"], body)
    assert not errors, errors[:2]
    assert out["cardGone"] and out["restingGone"], "a token resting on a removed card stays behind"
    assert out["awayKept"] and out["pinnedKept"] and out["ignoredKept"], "a token that is not the box's was taken"
    assert out["said"], out["msgs"][-3:]


def _function_text(path, name):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"local function %s\(.*?\nend\n" % name, src, re.S)
    assert m, (path, name)
    body = re.sub(r"--.*", "", m.group(0))           # comments differ, code does not
    return re.sub(r"\s+", " ", body).strip()


def test_the_box_finds_the_tokens_on_a_card_as_the_control_token_does():
    # Recall and Clear Board are one rule: keep the box's copy of the function the Control's
    assert _function_text(LOOP_BOX, "tokensOn") == _function_text(CONTROL, "tokensOn")


# ----------------------------------------------------------------- a copy left by a save --
@needs_lua
def test_a_copy_left_on_the_table_by_a_save_destroys_itself_and_a_live_one_does_not(books, tmp_path):
    book = books["district_church"]
    stray = json.loads(json.dumps(book))
    stray.pop("GUID", None)
    stray["Nickname"] = book["Nickname"] + " (placing)"
    extra = "local STRAY = " + relay.lua_long_string(json.dumps(stray, ensure_ascii=False)) + "\n"
    body = r"""
Wait.frames(function()
  local copy = spawnObjectJSON({ json = STRAY })        -- what a load brings back after a save during a Place
  Wait.frames(function()
    out.strayGone = copy.isDestroyed()
    out.boxKept = not box.isDestroyed()
    out.pressed = box.call("buttonClick_place")          -- its own working copy has the same name: it must live
    Wait.frames(function()
      out.onTable = count(TAG)
      out.copies = strays()
      out.stillPlacing = box.call("isPlacing")
      done()
    end, 400)
  end, 120)
end, 10)
"""
    out, errors = run_chunk(tmp_path, book, body, extra)
    assert not errors, errors[:2]
    assert out["strayGone"] is True and out["boxKept"] is True
    assert out["pressed"] == objects_in(book) and out["onTable"] > 0
    assert out["copies"] == 0 and out["stillPlacing"] is False, "the live working copy was destroyed or never finished"
    assert any("%d object(s) placed." % objects_in(book) in m for m in out["msgs"])


# ----------------------------------------------------------------- one error, one step --
@needs_lua
def test_an_error_in_one_step_cannot_leave_the_box_placing(books, tmp_path):
    book = books["district_church"]
    n = objects_in(book)
    body = r"""
Wait.frames(function()
  failAt = "Placing 3/%d"                                -- step 3 raises an error
  out.pressed = box.call("buttonClick_place")
  Wait.frames(function()
    failAt = nil
    out.placing = box.call("isPlacing")
    out.copies = strays()
    out.onTable = count(TAG)
    out.saidPlaced = say("%d object(s) placed.")
    box.call("buttonClick_recall")
    Wait.frames(function()                                 -- (TTS removes what was destroyed at the end of the frame)
      out.again = box.call("buttonClick_place")           -- not refused: the box is free again
      Wait.frames(function()
        out.full = count(TAG)
        out.refused = say("still placing")
        done()
      end, 400)
    end, 3)
  end, 400)
end, 10)
""" % (n, n - 1)
    out, errors = run_chunk(tmp_path, book, body)
    assert not errors, errors[:2]
    assert out["pressed"] == n
    assert out["placing"] is False and out["copies"] == 0, "the chain stopped at the failing step"
    assert out["saidPlaced"] is True, "the other objects were placed and counted"
    assert out["again"] == n and out["refused"] is False and out["full"] > out["onTable"]


# ------------------------------------------------- a Place refused for another box's cards --
def _spots(book):
    return [(e["pos"]["x"], e["pos"]["z"]) for e in json.loads(book["LuaScriptState"])["ml"].values()]


def _reach():
    return float(re.search(r"local SPOT_REACH = ([0-9.]+)", open(LOOP_BOX, encoding="utf-8").read()).group(1))


def test_boxes_that_share_a_loop_never_lie_where_another_lays_out_but_the_prologue_and_square_do(books):
    reach = _reach()
    manifest = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "scenario_manifest.json"), encoding="utf-8"))
    shared = [s["id"] for s in manifest["scenarios"]
              if s["id"] == "district_square" or s.get("shared_from") == "district_square"]
    assert "finale" in shared and len(shared) >= 6

    def close(a, b):
        return [(p, q) for p in _spots(books[a]) for q in _spots(books[b])
                if abs(p[0] - q[0]) < reach and abs(p[1] - q[1]) < reach]
    for i, a in enumerate(shared):
        for b in shared[i + 1:]:
            assert not close(a, b), (a, b, close(a, b)[:2])      # so the guard never refuses a valid loop
    # ...and the Prologue's box shares the mythos mat with the Square's: that is what the guard is for
    assert len(close("prologue", "district_square")) >= 3


@needs_lua
def test_a_place_is_refused_for_cards_of_a_box_laid_out_earlier_and_for_an_older_builds_leftovers(books, tmp_path):
    book = books["district_church"]
    spot = _spots(book)[0]
    body = r"""
local function leftover(tags, dx)
  return spawnObjectJSON({ json = JSON.encode({ Name = "Custom_Tile", Nickname = "leftover", Tags = tags,
    Transform = { posX = %f + dx, posY = 1.6, posZ = %f - dx } }) })
end
Wait.frames(function()
  out.results = {}
  local variants = { { "StillHourLoop" }, { "StillHourLoop", "StillHourBox_district_x" },
                     { "StillHourLoop", "StillHourBox:3c5e1a" }, { "StillHourBox:3c5e1a" } }
  local function try(i)
    if i > #variants then
      local o = leftover({ "SomethingElse" }, 0.1)                 -- not a box's: no objection
      Wait.frames(function()
        out.unrelated = box.call("buttonClick_place")
        Wait.frames(function() out.onTable = count(TAG) ; done() end, 300)
      end, 2)
      return
    end
    local o = leftover(variants[i], 0.1)
    Wait.frames(function()
      local mark = #msgs
      local pressed = box.call("buttonClick_place")
      local said = false
      for k = mark + 1, #msgs do
        if msgs[k]:find("Click Clear Board on the Control token first.", 1, true) then said = true end
      end
      out.results[i] = { pressed = pressed, onTable = count(TAG), said = said }
      o.destruct()
      Wait.frames(function() try(i + 1) end, 2)
    end, 2)
  end
  try(1)
end, 10)
""" % (spot[0], spot[1])
    out, errors = run_chunk(tmp_path, book, body)
    assert not errors, errors[:2]
    for i, r in enumerate(out["results"], 1):
        assert r["pressed"] == 0 and r["onTable"] == 0 and r["said"] is True, (i, r)
    assert out["unrelated"] == objects_in(book) and out["onTable"] > 0
    expected = ("%s: cards from a box laid out earlier are still on the table where this one lays out."
                " Click Clear Board on the Control token first." % book["Nickname"])
    assert expected in out["msgs"]


@needs_lua
def test_the_box_does_not_refuse_its_own_leftovers_twice_over(books, tmp_path):
    # its own objects on its own spots are the "already laid out" case, not the other box's
    book = books["district_church"]
    body = r"""
Wait.frames(function()
  box.call("buttonClick_place")
  Wait.frames(function()
    out.second = box.call("buttonClick_place")
    out.said = say("is already laid out.")
    out.other = say("cards from a box laid out earlier")
    done()
  end, 400)
end, 10)
"""
    out, errors = run_chunk(tmp_path, book, body)
    assert not errors, errors[:2]
    assert out["second"] == 0 and out["said"] is True and out["other"] is False
