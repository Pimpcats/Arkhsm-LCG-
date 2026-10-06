-- The Control token's flow on a stubbed Tabletop Simulator (tests only;
-- tests/test_control_flow.py runs it under lua5.2 and lua5.4):
--
--   lua5.2 tests/control_flow.lua <control bundle.lua> <repo root>
--
-- The bundle is the Control's script as TTS gets it (pipeline/bundle_mod.py
-- build_bundle, built from src/). The table is a vanilla one: no SCED, objects
-- are plain Lua tables with the members the Control reads. A test adds SCED's
-- investigator counter, a campaign log or location cards when it needs them.
-- It drives the owner's buttons (click by label) and the runner API, and checks
-- the state, the panel and what the table is told. The button labels and sizes
-- the panels draw are also printed ("@@LABEL <json>") for the fit check.

local BUNDLE, ROOT = arg[1], arg[2]
assert(BUNDLE and ROOT, "usage: control_flow.lua <bundle.lua> <repo root>")
local json = dofile(ROOT .. "/tests/tts_fake/json.lua")

local function readFile(path)
  local f = assert(io.open(path, "rb"))
  local s = f:read("*a")
  f:close()
  return s
end
local SOURCE = readFile(BUNDLE)

local failures, total = 0, 0
local function check(name, cond, detail)
  total = total + 1
  if cond then
    print("  ok    " .. name)
  else
    failures = failures + 1
    print("  FAIL  " .. name .. (detail ~= nil and ("  -- " .. tostring(detail)) or ""))
  end
end
local function section(title) print("== " .. title) end

------------------------------------------------------------------- the table --

local function newWorld()
  return { objects = {}, byGuid = {} }
end

--- A card the Control reads: metadata in GMNotes, buttons it can add and remove.
local function newCard(W, name, md, tags)
  local o = { type = "Card", buttons = {}, tags = {}, destroyed = false, memo = "", rot = { 0, 180, 0 } }
  for _, t in ipairs(tags or {}) do o.tags[t] = true end
  o.getName = function() return name end
  o.getGMNotes = function() return json.encode(md) end
  o.getGUID = function() return name end
  o.getPosition = function() return { x = 0, y = 1, z = 0 } end
  o.getRotation = function() return { x = o.rot[1], y = o.rot[2], z = o.rot[3] } end
  o.setRotation = function(r) o.rot = { r[1] or r.x, r[2] or r.y, r[3] or r.z } ; o.is_face_down = o.rot[3] > 90 end
  o.hasTag = function(t) return o.tags[t] == true end
  o.isDestroyed = function() return o.destroyed end
  o.createButton = function(def) o.buttons[#o.buttons + 1] = def ; return true end
  o.clearButtons = function() o.buttons = {} ; return true end
  o.getButtons = function()
    local l = {}
    for i, b in ipairs(o.buttons) do l[i] = { label = b.label, index = i - 1 } end
    return l
  end
  o.removeButton = function(i) table.remove(o.buttons, i + 1) ; return true end
  o.is_face_down = false
  W.objects[#W.objects + 1] = o
  return o
end

local INVESTIGATORS = {
  sthrelias = "Elias Warde", sthrayako = "Dr. Ayako S\xC5\x8Dma", sthrcass = "Cass Lindqvist",
  sthrseraphine = "Seraphine Vale", sthrbirdie = '"Birdie" Okonkwo',
}
local function seat(W, id)
  return newCard(W, INVESTIGATORS[id], { id = id, type = "Investigator", willpowerIcons = 3, intellectIcons = 3,
    combatIcons = 3, agilityIcons = 3, health = 8, sanity = 8 }, { "Investigator" })
end

--- A location card (campaign locations are known by their metadata id).
local function location(W, id)
  return newCard(W, id, { id = id, type = "Location",
    locationFront = { icons = "Circle", connections = "Square" }, locationBack = { icons = "Circle", connections = "Square" } },
    { "Location" })
end

--- A campaign log object: a memo, a shown page's saved values, and the other
-- pages' State data (what getData() returns), as TTS keeps them.
local function newLog(W, fields)
  local o = { type = "Custom_Token", memo = "", script_state = "", destroyed = false, states = {} }
  for k, v in pairs(fields or {}) do o[k] = v end
  o.hasTag = function(t) return t == "CampaignLog" end
  o.getName = function() return "The Still Hour - Campaign Log" end
  o.isDestroyed = function() return o.destroyed end
  o.getData = function() return { States = o.states } end
  W.objects[#W.objects + 1] = o
  return o
end

--- SCED's investigator counter behind its GUID reference handler.
local function addCounter(W, val)
  local counter = { val = val, updates = {} }
  counter.obj = {
    getVar = function(k) if k == "val" then return counter.val end end,
    call = function(name, v)
      if name == "updateVal" then
        counter.updates[#counter.updates + 1] = v
        counter.val = math.max(1, math.min(4, v))      -- ActiveInvestigatorCounter: MIN_VALUE 1, MAX_VALUE 4
      end
    end,
  }
  W.byGuid["123456"] = { call = function(name, p)
    if name == "getObjectByOwnerAndType" and p.owner == "Mythos" and p.type == "InvestigatorCounter" then return counter.obj end
  end }
  W.global = { getVar = function(k) if k == "MOD_VERSION" then return "4.9.2" end end, call = function() return nil end }
  W.counter = counter
  return counter
end

--- A Control token running the bundle. opts.state = its saved state (onLoad).
local function newControl(W, opts)
  opts = opts or {}
  local T = { world = W, buttons = {}, say = {}, errors = {}, onLoadPrints = {} }
  local selfObj = {
    script_state = "", memo = "",
    createButton = function(def) T.buttons[#T.buttons + 1] = def ; return true end,
    clearButtons = function() T.buttons = {} ; return true end,
    getPosition = function() return { x = 3, y = 1, z = 0 } end,
    getName = function() return "THE STILL HOUR \xE2\x80\x94 Control" end,
    hasTag = function(_, t) return t == "StillHour" end,
  }
  T.self = selfObj
  local env = setmetatable({
    JSON = { encode = json.encode, decode = json.decode },
    print = function(...)
      local parts = {}
      for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
      local s = table.concat(parts, "\t")
      T.say[#T.say + 1] = s
      if s:find("board wiring skipped", 1, true) then T.errors[#T.errors + 1] = s end
    end,
    log = function() end,
    broadcastToAll = function(msg) T.say[#T.say + 1] = "(broadcast) " .. tostring(msg) end,
    getObjectFromGUID = function(g) return W.byGuid[g] end,
    getObjects = function()
      local l = {}
      for _, o in ipairs(W.objects) do if not (o.isDestroyed and o.isDestroyed()) then l[#l + 1] = o end end
      return l
    end,
    getObjectsWithTag = function(tag)
      local l = {}
      for _, o in ipairs(W.objects) do
        if o.hasTag and o.hasTag(tag) and not (o.isDestroyed and o.isDestroyed()) then l[#l + 1] = o end
      end
      return l
    end,
    Wait = { frames = function(fn) fn() end, time = function(fn) fn() end },
    self = selfObj,
    Global = W.global,
  }, { __index = _G })
  T.env = env
  assert(load(SOURCE, "=bundle", "t", env))()

  function T.begin(state) env.onLoad(state) ; return T end
  function T.st() return env.shApiState() end
  function T.clear() T.say = {} end
  function T.has(prefix)
    for _, b in ipairs(T.buttons) do
      if tostring(b.label):sub(1, #prefix) == prefix then return b end
    end
    return nil
  end
  function T.labels()
    local l = {}
    for _, b in ipairs(T.buttons) do l[#l + 1] = tostring(b.label):gsub("\n", " / ") end
    return table.concat(l, " | ")
  end
  --- click a button by label prefix (right-click with alt); false when there is no such button
  function T.click(prefix, alt)
    local b = T.has(prefix)
    if not b then return false end
    local fn = env[b.click_function]
    assert(type(fn) == "function", "no click function " .. tostring(b.click_function))
    fn(selfObj, "White", alt and true or false)
    return true
  end
  --- how many messages (chat or console) contain the text
  function T.count(text)
    local n = 0
    for _, s in ipairs(T.say) do if s:find(text, 1, true) then n = n + 1 end end
    return n
  end
  function T.said(text) return T.count(text) > 0 end
  function T.header() return T.buttons[1] and T.buttons[1].label end
  --- edit the decoded campaign state through the runner API (snapshot, change, restore)
  function T.patch(fn)
    local blob = json.decode(env.shApiSnapshot())
    fn(blob.campaign, blob)
    env.shApiRestore({ blob = json.encode(blob) })
  end
  --- the log ticks (or clears) a Knowledge box
  function T.tick(id) return env.shApiUnlockFact({ id = id }) end
  function T.untick(id) return env.shApiForgetFact({ id = id }) end
  --- Begin Next Loop the way a player does: it asks once when the interlude is unfinished
  function T.beginNextLoop()
    T.click("Begin Next Loop")
    if T.st().mode ~= "play" or T.st().loopEnded then T.click("Begin Next Loop") end
  end
  return T
end

local function fresh(opts)
  local W = newWorld()
  local T = newControl(W, opts)
  T.begin(nil)
  return T, W
end
--- a campaign whose Prologue is over: loop 1 under way
local function inLoop(opts)
  local T, W = fresh(opts)
  T.env.shApiEndPrologue()
  return T, W
end
local function state(T)
  local s = T.st()
  return string.format("hour %d diss %d loops %d prologue %s loopEnded %s mode %s", s.hour, s.dissonance, s.loops,
    tostring(s.prologue), tostring(s.loopEnded), s.mode)
end

local ASKED = "The loop is not over by the Control's count. Click Reset Loop again to end it now."

------------------------------------------------------ F-04: the first change --

section("F-04: the first chaos-bag change after a load is applied")
do
  local function chaosMessages(T) return T.count("Campaign chaos-bag change") end
  -- a session saved at the end of a Torn loop: the first thing done after the load is Reset Loop
  local A = inLoop()
  for _ = 1, 30 do A.click("Dissonance") end
  local blob = A.env.shApiSnapshot()
  local B = newControl(newWorld()).begin(blob)
  B.clear()
  B.click("Reset Loop")
  check("loaded at the reset value, the first Reset Loop is not asked about", B.st().loops == 1, state(B))
  check("the Torn loop's Cultist is announced as a change to the chaos bag", chaosMessages(B) == 1, B.count("chaos"))
  -- Part II starts at the end of loop 3: its Tablet
  local C = inLoop()
  C.patch(function(c) c.loopsCompleted = 2 end)
  local C2 = newControl(newWorld()).begin(C.env.shApiSnapshot())
  C2.clear()
  for _ = 1, 8 do C2.click("Hour") end
  C2.click("Reset Loop")
  check("Part II's Tablet is announced as the first change after a load", C2.st().partTwo == true and chaosMessages(C2) == 1,
    tostring(C2.st().partTwo) .. " / " .. chaosMessages(C2))
  -- a campaign loaded WITH its changes already in the bag announces nothing at load
  local D = newControl(newWorld()).begin(B.env.shApiSnapshot())
  check("a load announces no change by itself", chaosMessages(D) == 0, D.count("chaos"))
end

---------------------------------------------- F-01: Begin Next Loop needs a Reset --

section("F-01: Begin Next Loop does not start a night before Reset Loop")
do
  local T = inLoop()
  for _ = 1, 8 do T.click("Hour") end
  local before = state(T)
  T.click("Interlude")
  T.clear()
  T.click("Begin Next Loop")
  check("Begin Next Loop before Reset Loop says Reset Loop comes first",
    T.said("Click Reset Loop first: the loop is not over yet."), table.concat(T.say, " | "))
  check("...and starts nothing", state(T):gsub("mode %a+", "") == before:gsub("mode %a+", "") and T.st().mode == "interlude", state(T))
  T.click("Begin Next Loop")
  check("a second click does not start it either", T.st().loopEnded == false and T.st().hour == 9 and T.count("Click Reset Loop first") == 2,
    state(T))
  T.click("Back")
  T.click("Reset Loop")
  check("Reset Loop at Hour IX counts the loop", T.st().loops == 1 and T.st().loopEnded == true, state(T))
  T.click("Interlude")
  T.beginNextLoop()
  check("after Reset Loop the night begins", T.st().loopEnded == false and T.st().hour == 1 and T.st().mode == "play", state(T))
  -- the runner API's default still starts the night at once (it has its own order of calls)
  local R = inLoop()
  R.env.shApiBeginNextLoop()
  check("the runner API is not refused", R.st().mode == "play" and R.st().loopEnded == false)
  -- guard = true asks like the button
  R.env.shApiBeginNextLoop({ guard = true })
  check("...unless it asks like the button (guard)", R.said("Click Reset Loop first"))
  -- the Prologue leads to loop 1 the usual way
  local P = fresh()
  P.click("Interlude")
  P.clear()
  P.click("Begin Next Loop")
  check("in the Prologue too the night must be reset first", P.st().prologue == true and P.said("Click Reset Loop first"), state(P))
  P.click("Back")
  P.click("Reset Loop")
  P.click("Reset Loop")
  check("the Prologue's Reset Loop ends it without counting a loop", P.st().prologue == false and P.st().loops == 0
    and P.st().loopEnded == true, state(P))
  P.click("Interlude")
  P.beginNextLoop()
  check("...and Begin Next Loop starts Loop 1", P.st().loopEnded == false and P.st().loops == 0 and P.st().mode == "play"
    and P.header() == "THE STILL HOUR \xC2\xB7 loop 1", state(P) .. " / " .. tostring(P.header()))
end

--------------------------------------------- F-02: Between Loops is not a night --

section("F-02: after Reset Loop the panel is Between Loops, never 'loop N+1'")
do
  local T, W1 = inLoop()
  seat(W1, "sthrelias")
  T.env.shApiCounter({ name = "hour", delta = 0 })
  check("loop 1 is headed with its loop", T.header() == "THE STILL HOUR \xC2\xB7 loop 1", T.header())
  for _ = 1, 8 do T.click("Hour") end
  T.click("Reset Loop")
  check("after Reset Loop the header says Between Loops", T.header() == "BETWEEN LOOPS", T.header())
  check("it offers no Hour, Dissonance, [static] or Appointed to click", not T.has("Hour") and not T.has("Dissonance")
    and not T.has("[static]") and not T.has("Appointed"), T.labels())
  check("it offers the between-loops steps", T.has("Interlude") and T.has("Begin Next Loop") and T.has("Clear Board")
    and T.has("Investigators") and T.has("Memory"), T.labels())
  T.click("Interlude")
  check("the Interlude panel is open", T.st().mode == "interlude" and T.has("Back") ~= nil)
  T.click("Back")
  check("Back returns to Between Loops, not to a play panel headed loop 2", T.header() == "BETWEEN LOOPS" and not T.has("Hour"), T.labels())
  T.clear()
  T.click("Begin Next Loop")
  check("Begin Next Loop on that panel asks what is outstanding first, like the Interlude's",
    T.st().loopEnded == true and T.said("Not everything in the interlude is done") and T.said("Age has not been clicked"), table.concat(T.say, " | "))
  T.click("Begin Next Loop")
  check("a second click starts loop 2, headed so", T.st().loopEnded == false and T.header() == "THE STILL HOUR \xC2\xB7 loop 2"
    and T.has("Hour") ~= nil, tostring(T.header()))
  -- the Prologue's Reset Loop is Between Loops too
  local P = fresh()
  P.click("Reset Loop") ; P.click("Reset Loop")
  check("after the Prologue's Reset Loop: Between Loops", P.header() == "BETWEEN LOOPS", P.header())
  -- the party size can be set Between Loops (an investigator aged out)
  local n0 = P.st().investigators
  P.click("Investigators", true)
  check("Investigators can be changed Between Loops", P.st().investigators == n0 - 1, P.st().investigators)
end

----------------------------------------------------------- F-06: Reset Loop asks --

section("F-06: Reset Loop asks once when the loop is not over by the Control's count")
do
  local T = inLoop()
  for _ = 1, 3 do T.click("Hour") end
  for _ = 1, 9 do T.click("Dissonance") end
  local before = state(T)
  T.clear()
  T.click("Reset Loop")
  check("the first click only asks", T.said(ASKED) and state(T) == before, state(T))
  check("it does nothing else (no status, no new panel)", #T.say == 1, table.concat(T.say, " | "))
  T.click("Reset Loop")
  check("the second click ends the loop", T.st().loops == 1 and T.st().loopEnded == true and T.st().hour == 1, state(T))
  T.clear()
  T.click("Reset Loop")
  check("a third click is the usual 'already been reset' refusal, not another question",
    T.said("already been reset") and not T.said(ASKED) and T.st().loops == 1, table.concat(T.say, " | "))
  -- any other click withdraws the question
  local function withdrawn(name, other)
    local U = inLoop()
    for _ = 1, 3 do U.click("Hour") end
    U.clear()
    U.click("Reset Loop")
    other(U)
    U.click("Reset Loop")
    check("after " .. name .. " the next Reset Loop asks again", U.st().loops == 0 and U.count(ASKED) == 2,
      state(U) .. " / asked " .. U.count(ASKED))
  end
  withdrawn("Hour", function(U) U.click("Hour") end)
  withdrawn("Dissonance", function(U) U.click("Dissonance") end)
  withdrawn("Memory", function(U) U.click("Memory") end)
  withdrawn("Interlude and Back", function(U) U.click("Interlude") ; U.click("Back") end)
  withdrawn("Appointed", function(U) U.click("Appointed") end)
  withdrawn("Investigators", function(U) U.click("Investigators") end)
  withdrawn("Status", function(U) U.click("Status") end)
  withdrawn("Knowledge", function(U) U.click("Knowledge") end)
  withdrawn("Sync Board", function(U) U.click("Sync Board") end)
  withdrawn("Clear Board", function(U) U.click("Clear Board") end)
  withdrawn("a difficulty button", function(U) U.click("Standard") end)
  withdrawn("the Static button", function(U) U.click("[static]") end)
  -- the loop is over by the count: no question
  local H = inLoop()
  for _ = 1, 8 do H.click("Hour") end
  H.clear()
  H.click("Reset Loop")
  check("Hour IX: Reset Loop ends the loop at once", H.st().loops == 1 and not H.said(ASKED), state(H))
  local D = inLoop()
  for _ = 1, 24 do D.click("Dissonance") end
  D.clear()
  D.click("Reset Loop")
  check("Dissonance at the reset value: Reset Loop ends the loop at once", D.st().loops == 1 and not D.said(ASKED), state(D))
  local D2 = inLoop()
  for _ = 1, 23 do D2.click("Dissonance") end
  D2.click("Reset Loop")
  check("one below the reset value it asks", D2.st().loops == 0 and D2.said(ASKED), state(D2))
  -- the Prologue follows the same rule
  local P = fresh()
  P.click("Hour")
  P.clear()
  P.click("Reset Loop")
  check("the Prologue asks too", P.st().prologue == true and P.said(ASKED) and P.has("Prologue reward") ~= nil, state(P))
  P.click("Reset Loop")
  check("...and ends on the second click", P.st().prologue == false and P.st().loopEnded == true, state(P))
  local P2 = fresh()
  for _ = 1, 8 do P2.click("Hour") end
  P2.click("Reset Loop")
  check("the Prologue's Hour IX needs no second click", P2.st().prologue == false, state(P2))
  -- the finale ends the same way
  local F = inLoop()
  F.patch(function(c) c.knowledge["the-way-the-night-breaks"] = true end)
  F.click("Begin Finale")
  check("the finale has begun", F.st().finale == true)
  F.clear()
  F.click("Reset Loop")
  check("a finale that is not over by the count asks too", F.st().finale == true and F.said(ASKED), state(F))
  for _ = 1, 8 do F.click("Hour") end
  F.click("Reset Loop")
  check("a finale at Hour IX ends with the loop at once", F.st().loops == 1 and F.st().finale == false, state(F))
  -- the runner API ends it at once, and the console's reset call at the reset value too
  local R = inLoop()
  R.env.shApiReset()
  check("the runner API ends the loop without asking", R.st().loops == 1 and R.st().loopEnded == true)
  local C = inLoop()
  C.env.shRaiseDissonance = C.env.shRaiseDissonance
  C.patch(function(c) c.dissonance = 23 end)
  C.env.shRaiseDissonance()
  check("the console's Dissonance raise that reaches the reset value ends the loop", C.st().loops == 1, state(C))
end

---------------------------------------------- F-10: the finale's two loose ends --

section("F-10: Begin Finale in the Prologue; the finale's entry un-ticked during it")
do
  local P = fresh()
  P.patch(function(c) c.knowledge["the-way-the-night-breaks"] = true end)
  P.clear()
  P.env.shBeginFinale()
  check("Begin Finale is refused in the Prologue", P.st().finale == false and P.said("The finale cannot begin during the Prologue."),
    state(P) .. " / " .. table.concat(P.say, " | "))
  P.env.shApiSetFinale({ on = true })
  check("...and from the runner API too", P.st().finale == false)
  check("no Begin Finale button in the Prologue", P.has("Begin Finale") == nil)
  local T = inLoop()
  T.tick("the-vote-that-never-ends") ; T.tick("the-appointeds-name")
  check("the way is assembled", T.has("Begin Finale") ~= nil, T.labels())
  T.click("Begin Finale")
  check("the finale begins", T.st().finale == true)
  T.clear()
  T.untick("the-way-the-night-breaks")
  check("un-ticking the entry keeps the finale running", T.st().finale == true and T.has("Contest") ~= nil, state(T))
  check("...and says so in one sentence", T.count("The finale carries on") + T.count("the finale carries on") == 1,
    table.concat(T.say, " | "))
  -- a prerequisite un-ticked during the finale: the cascade must not remove it
  local U = inLoop()
  U.tick("the-vote-that-never-ends") ; U.tick("the-appointeds-name")
  U.click("Begin Finale")
  U.untick("the-vote-that-never-ends")
  check("un-ticking an input during the finale leaves the finale and the entry", U.st().finale == true)
end

----------------------------------------------------- F-05: the Sealed Study opens --

section("F-05: act 2a becomes current when the Almanac House is Placed with both entries recorded")
do
  local function study(T, W)
    local card = location(W, "sthr-loc-sealedstudy")
    location(W, "sthr-loc-readingroom")
    T.env.shSyncBoard()
    return card
  end
  local function closed(card)
    for _, b in ipairs(card.buttons) do if b.label == "CLOSED" then return true end end
    return false
  end
  local function partTwo(T, entries)
    T.patch(function(c)
      c.partTwo = true
      for _, e in ipairs(entries) do c.knowledge[e] = true end
    end)
  end
  -- the Vote is completed and recorded mid-loop; the Almanac House's own entry is from an earlier loop;
  -- the Almanac House is Placed afterwards (the guide allows a district's box later in the loop)
  local T, W = inLoop()
  partTwo(T, { "what-the-almanac-hid" })
  local card = study(T, W)
  check("the Sealed Study starts CLOSED", closed(card), T.labels())
  T.tick("the-vote-that-never-ends")
  check("the Vote recorded after act 1a's entry does not open it (that act deck is gone: guide, a district's act deck)",
    closed(card))
  T.env.shApiSyncBoardStaged({ box = "district_church", name = "The Drowned Church", guids = {} })
  check("another district's Place does not open it", closed(card))
  T.env.shApiSyncBoardStaged({ box = "district_almanac", name = "The Almanac House", guids = {} })
  check("the Almanac House's Place does: act 2a is its current act, the label is gone", not closed(card))
  check("...and Place leaves it flagged for the loop (a Sync keeps it open)", (T.env.shSyncBoard() or true) and not closed(card))
  -- act 1a advancing in Part II with the Vote recorded makes act 2a current (before this change too)
  local U, W2 = inLoop()
  partTwo(U, { "the-vote-that-never-ends" })
  local card2 = study(U, W2)
  U.tick("what-the-almanac-hid")
  check("act 1a advancing with the Vote recorded opens it at once", not closed(card2))
  -- Part I: nothing opens, at Place or otherwise
  local V, W3 = inLoop()
  V.patch(function(c) c.knowledge["what-the-almanac-hid"] = true ; c.knowledge["the-vote-that-never-ends"] = true end)
  local card3 = study(V, W3)
  V.env.shApiSyncBoardStaged({ box = "district_almanac", name = "The Almanac House", guids = {} })
  check("in Part I a Place does not open it", closed(card3))
  -- a Place that names no box: the Almanac locations on the table count
  local Y, W5 = inLoop()
  partTwo(Y, { "what-the-almanac-hid", "the-vote-that-never-ends" })
  local card5 = study(Y, W5)
  check("both entries, no act 2a yet: CLOSED", closed(card5))
  Y.env.shApiSyncBoardStaged()
  check("a Place that names no box counts the Almanac locations on the table", not closed(card5))
  -- without both entries the Place changes nothing
  local Z, W6 = inLoop()
  partTwo(Z, { "what-the-almanac-hid" })
  local card6 = study(Z, W6)
  Z.env.shApiSyncBoardStaged({ box = "district_almanac", name = "The Almanac House", guids = {} })
  check("without the Vote the Place leaves it CLOSED", closed(card6))
  -- the next loop: Begin Next Loop with both entries recorded makes act 2a current from the Place (as before)
  local N, W7 = inLoop()
  partTwo(N, { "what-the-almanac-hid", "the-vote-that-never-ends" })
  local card7 = study(N, W7)
  N.click("Reset Loop") ; N.click("Reset Loop") ; N.click("Interlude")
  N.beginNextLoop()
  check("Begin Next Loop in Part II with both entries opens it (the flag is set for the new loop)", not closed(card7))
end

-------------------------------------------------------------------- F-08: banner --

section("F-08: no investigator can continue")
do
  local function party(ids, years)
    local T, W = inLoop()
    for _, id in ipairs(ids) do seat(W, id) end
    T.env.shApiCounter({ name = "hour", delta = 0 })
    T.patch(function(c) for _, id in ipairs(ids) do c.years[id] = years[id] or 0 end end)
    T.click("Reset Loop") ; T.click("Reset Loop")
    T.click("Interlude")
    T.clear()
    T.beginNextLoop()
    return T
  end
  local BANNER = "No investigator can continue; see the guide, Age stories."
  local all = party({ "sthrelias", "sthrcass" }, { sthrelias = 18, sthrcass = 21 })
  check("every listed investigator aged out: the banner", all.said(BANNER), table.concat(all.say, " | "))
  check("...it informs, the night begins", all.st().mode == "play" and all.st().loopEnded == false)
  local some = party({ "sthrelias", "sthrcass" }, { sthrelias = 18, sthrcass = 6 })
  check("one can continue: no banner", not some.said(BANNER))
  local replaced = party({ "sthrelias", "sthrcass" }, { sthrelias = 18 })
  check("a replacement with no Years: no banner", not replaced.said(BANNER))
  local none = party({}, {})
  check("no investigator known to the Control: no banner", not none.said(BANNER))
end

---------------------------------------------------- G13: no developer button --

section("G13: no Run Tests button, message or description")
do
  local T, W = fresh()
  seat(W, "sthrelias")
  T.env.shApiCounter({ name = "hour", delta = 0 })
  local panels = {}
  panels["play"] = T.labels()
  T.click("Reset Loop") ; T.click("Reset Loop")
  panels["between"] = T.labels()
  T.click("Interlude")
  panels["interlude"] = T.labels()
  for name, l in pairs(panels) do
    check("the " .. name .. " panel has no Run Tests button", not l:find("Run Tests", 1, true), l)
  end
  check("the load message does not send the player to Run Tests", not T.said("Run Tests") and T.said("control ready"),
    table.concat(T.say, " | "))
  local res = T.env.runStillHourTests()
  check("runStillHourTests is still callable (the relay and the tests use it)", type(res) == "table" and res.passed > 0 and res.failed == 0,
    res and (tostring(res.passed) .. "/" .. tostring(res.failed)))
end

----------------------------------------------------------- G8: SCED's counter --

section("G8: SCED's investigator counter follows the Control's")
do
  local W = newWorld()
  local counter = addCounter(W, 2)
  local T = newControl(W).begin(nil)
  check("at load SCED's counter takes the Control's party size", counter.val == T.st().investigators and counter.val == 3, counter.val)
  T.click("Investigators")
  check("Investigators +1 sets SCED's counter", counter.val == 4 and T.st().investigators == 4, counter.val)
  T.click("Investigators", true)
  T.click("Investigators", true)
  check("Investigators -2 sets it too", counter.val == 2 and T.st().investigators == 2, counter.val)
  T.env.shApiCounter({ name = "investigators", delta = -1 })
  check("the runner API's change sets it", counter.val == 1, counter.val)
  T.click("Investigators", true)
  check("the Control stops at 1 and so does SCED's counter", counter.val == 1 and T.st().investigators == 1)
  local updates = #counter.updates
  T.click("Hour")
  check("nothing else touches it", #counter.updates == updates)
  -- one way: SCED's own change is not read back
  counter.val = 4
  T.click("Dissonance")
  check("a change made on SCED's counter is not read back into the Control", T.st().investigators == 1)
  -- a campaign restored from a save sets it too
  local blob = T.env.shApiSnapshot()
  local W2 = newWorld()
  local counter2 = addCounter(W2, 3)
  newControl(W2).begin(blob)
  check("a saved party size reaches SCED's counter at load", counter2.val == 1, counter2.val)
  -- no SCED: nothing is called, nothing is said
  local V = newControl(newWorld()).begin(nil)
  V.clear()
  V.click("Investigators")
  check("without SCED the button still works and says nothing", V.st().investigators == 4 and #V.say == 0 and #V.errors == 0,
    #V.say .. " message(s)")
  -- a table with SCED's handler but no counter
  local W3 = newWorld()
  addCounter(W3, 2)
  W3.byGuid["123456"].call = function() return nil end
  local K = newControl(W3).begin(nil)
  K.click("Investigators")
  check("SCED without its counter object does not raise an error", K.st().investigators == 4 and #K.errors == 0)
end

------------------------------------------------- F-03 / F-11: the log's mirror --

section("F-03 / F-11: the state mirror in the campaign log")
do
  local function memoOf(seq, blob) return json.encode({ stillHour = blob, seq = seq }) end
  -- the log is on page 1 when the Control writes; the player turns to page 3; the Control is replaced
  local W = newWorld()
  local log = newLog(W)
  local A = newControl(W).begin(nil)
  A.env.shApiEndPrologue()
  for _ = 1, 5 do A.click("Memory") end
  local seq = json.decode(log.memo).seq
  local blobA = json.decode(log.memo).stillHour
  check("the Control mirrors its state into the log's memo", seq >= 1 and json.decode(blobA).campaign.bankedMemory == 5, log.memo:sub(1, 80))
  -- page turn: a new object whose memo is empty; the old page's data is among its States
  local turned = newLog(W, { states = { ["1"] = { Memo = log.memo, LuaScriptState = "" } } })
  log.destroyed = true
  A.env.shApiCounter({ name = "memory", delta = 0 })
  local B = newControl(W).begin(nil)
  check("a new Control finds the newest mirror on any page and adopts it", B.st().memory == 5 and B.st().prologue == false
    and B.said("restored from the campaign log"), state(B) .. " memory " .. B.st().memory)
  -- the page shown holds an OLDER copy, another page the newest
  local W2 = newWorld()
  local old = newLog(W2, { memo = memoOf(2, json.encode({ v = 2, campaign = { version = 1, bankedMemory = 3, investigators = 3,
    loopsCompleted = 0, knowledge = {}, dissonance = 0, hourglass = 1 }, seq = 2 })),
    states = { ["2"] = { Memo = memoOf(9, json.encode({ v = 2, campaign = { version = 1, bankedMemory = 13, investigators = 3,
      loopsCompleted = 1, knowledge = {}, dissonance = 0, hourglass = 1 }, seq = 9 })) } } })
  local C = newControl(W2).begin(nil)
  check("the highest seq wins over the page that is showing (memory 13, not 3)", C.st().memory == 13, C.st().memory)
  local mirror = C.env.shApiLogMirror()
  check("shApiLogMirror reports the newest copy", mirror ~= nil and mirror.seq == 9, mirror and mirror.seq)

  -- a Control that starts blank beside a log with entries says so
  local W3 = newWorld()
  newLog(W3, { script_state = json.encode({ page = 1, values = { investigators = 3, loops = 2, banked = 7 } }) })
  local D = newControl(W3).begin(nil)
  check("a blank Control with a filled log says it starts a new campaign",
    D.said("The Campaign Log has entries, but no saved campaign was found for this Control token"), table.concat(D.say, " | "))
  local W4 = newWorld()
  newLog(W4, { script_state = json.encode({ page = 1, values = { investigators = 3 } }) })
  local E = newControl(W4).begin(nil)
  check("...but not beside a log with nothing recorded", not E.said("The Campaign Log has entries"))
  local W5 = newWorld()
  newLog(W5, { states = { ["3"] = { LuaScriptState = json.encode({ page = 3, values = { ["k:you-are-unstuck"] = true } }) } } })
  local F = newControl(W5).begin(nil)
  check("entries on another page count", F.said("The Campaign Log has entries"))
  -- a Control with its own state is not blank
  local W6 = newWorld()
  newLog(W6, { script_state = json.encode({ page = 1, values = { investigators = 3, loops = 2 } }) })
  local G = newControl(W6).begin(A.env.shApiSnapshot())
  check("a Control restored from its own save does not say it starts a new campaign", not G.said("The Campaign Log has entries"))

  -- two logs
  local W7 = newWorld()
  newLog(W7) ; newLog(W7)
  local H = newControl(W7).begin(nil)
  check("two logs on the table: one sentence says to delete the spare one",
    H.count("More than one Campaign Log is on the table") == 1, table.concat(H.say, " | "))
  H.clear()
  H.env.onObjectSpawn(W7.objects[2])
  check("...and again when a log spawns", H.count("More than one Campaign Log is on the table") == 1, table.concat(H.say, " | "))
  check("the Control keeps its state in neither log", W7.objects[1].memo == "" and W7.objects[2].memo == "")
  local W8 = newWorld()
  newLog(W8)
  local I = newControl(W8).begin(nil)
  check("one log: no warning", not I.said("More than one Campaign Log"))
  -- two logs, then the spare is deleted: the Control adopts the campaign the other one holds
  local W10 = newWorld()
  local keep = newLog(W10, { memo = memoOf(9, json.encode({ v = 2, campaign = { version = 1, bankedMemory = 21, investigators = 3,
    loopsCompleted = 2, knowledge = {}, dissonance = 0, hourglass = 1 }, seq = 9 })) })
  local spare = newLog(W10)
  local M = newControl(W10).begin(nil)
  check("with two logs the Control starts blank (it cannot tell which holds the campaign)", M.st().memory == 0 and M.st().loops == 0 and M.st().prologue)
  spare.destroyed = true
  M.clear()
  M.env.onObjectDestroy(spare)
  check("deleting the spare log: it adopts the campaign the other one holds", M.st().memory == 21 and M.st().loops == 2
    and M.said("restored from the campaign log"), state(M) .. " memory " .. M.st().memory)
  M.click("Memory")
  check("...and mirrors into that log from then on", json.decode(keep.memo).seq > 9, keep.memo:sub(1, 60))
  -- a log taken off the table that leaves nothing newer changes nothing
  local N = newControl(W10).begin(nil)
  local n0 = N.st().memory
  N.env.onObjectDestroy(newLog(newWorld(), { destroyed = true }))
  check("a log destroyed with nothing newer in the one left changes nothing", N.st().memory == n0)

  -- a log that holds a newer copy than the Control is not overwritten
  local W9 = newWorld()
  local J = newControl(W9).begin(nil)            -- no log yet: nothing to adopt, nothing to mirror into
  J.env.shApiEndPrologue()
  local newerMemo = memoOf(50, json.encode({ v = 2, campaign = { version = 1, bankedMemory = 40, investigators = 3,
    loopsCompleted = 5, knowledge = {}, dissonance = 0, hourglass = 1 }, seq = 50 }))
  local newer = newLog(W9, { memo = newerMemo })  -- a log with the real campaign arrives (no spawn event reaches the Control)
  J.click("Memory")
  check("a log that holds a newer seq than the Control's is left as it was", newer.memo == newerMemo, newer.memo:sub(1, 80))
  local older = newLog(newWorld(), { memo = memoOf(0, "{}") })
  local K = newControl({ objects = { older }, byGuid = {} }).begin(nil)
  K.env.shApiEndPrologue()
  check("a log that holds an older copy is written", json.decode(older.memo).seq >= 1)
end

------------------------------------------------------------- F-09: take-backs --

section("F-09: an un-ticked Victory refunds; a quest taken back below its goal is not met")
do
  local T = inLoop()
  T.env.shApiCounter({ name = "memory", delta = 0 })
  local m0 = T.st().memory
  local n = T.st().investigators
  check("claiming Victory pays 2 per investigator for the Bellringer", T.env.shApiClaimVictory({ id = "sthr-bellringer" }) == true
    and T.st().memory == m0 + 2 * n)
  check("claiming it again pays nothing", T.env.shApiClaimVictory({ id = "sthr-bellringer" }) == false and T.st().memory == m0 + 2 * n)
  T.clear()
  check("un-ticking it takes the payment back", T.env.shApiForgetVictory({ id = "sthr-bellringer" }) == true and T.st().memory == m0,
    T.st().memory)
  check("...and says so", T.said("removed: -" .. 2 * n .. " banked Memory"), table.concat(T.say, " | "))
  check("forgetting it twice refunds nothing more", T.env.shApiForgetVictory({ id = "sthr-bellringer" }) == false and T.st().memory == m0)
  check("it can be claimed again (net once)", T.env.shApiClaimVictory({ id = "sthr-bellringer" }) == true and T.st().memory == m0 + 2 * n)
  -- Memory already spent: only what is in the bank comes back, and a re-tick pays only that part
  local U = inLoop()
  U.env.shApiClaimVictory({ id = "sthr-wearssheriff" })
  local paid = U.st().memory
  U.patch(function(c) c.bankedMemory = 2 end)
  U.env.shApiForgetVictory({ id = "sthr-wearssheriff" })
  check("only what the bank still holds is taken back", U.st().memory == 0, U.st().memory)
  U.env.shApiClaimVictory({ id = "sthr-wearssheriff" })
  check("a re-tick pays only the part that was taken back", U.st().memory == 2, U.st().memory)
  check("an unknown id is refused", U.env.shApiForgetVictory({ id = "nobody" }) == false)
  -- a quest
  local Q, W = inLoop()
  seat(W, "sthrelias")
  Q.env.shApiCounter({ name = "hour", delta = 0 })
  local r = Q.env.shApiQuest({ id = "sthrelias", delta = 4 })
  check("the goal (4) meets the quest", r.unlocked == true and r.tally == 4 and r.just == true)
  Q.clear()
  r = Q.env.shApiQuest({ id = "sthrelias", delta = -1 })
  check("taken back below the goal, the quest is no longer met", r.tally == 3 and r.unlocked == false, J and "" or tostring(r.unlocked))
  check("...and the table is told to swap the card back", Q.said("Quest no longer met"), table.concat(Q.say, " | "))
  r = Q.env.shApiQuest({ id = "sthrelias", delta = 1 })
  check("meeting the goal again unlocks it again", r.unlocked == true and r.just == true)
  r = Q.env.shApiQuest({ id = "sthrelias", delta = 5 })
  check("above the goal a take-back that stays at or above it changes nothing", r.unlocked == true and r.tally == 9)
  r = Q.env.shApiQuest({ id = "sthrelias", delta = -1 })
  check("...it stays met at 8", r.unlocked == true and r.tally == 8)
  -- a quest unlocked by hand below its goal is not cleared by a take-back that does not cross the goal
  Q.env.shApiQuest({ id = "sthrelias", unlock = false })
  Q.env.shApiQuest({ id = "sthrelias", delta = -20 })
  Q.env.shApiQuest({ id = "sthrelias", delta = 2 })
  r = Q.env.shApiQuest({ id = "sthrelias", unlock = true })
  check("a quest unlocked by hand stays so while its tally is only taken back below the goal",
    Q.env.shApiQuest({ id = "sthrelias", delta = -1 }).unlocked == true)
end

--------------------------------------------------------- TXT-20: label sizes --

section("TXT-20: every label is sized to fit its button")
do
  local seen = {}
  local function dump(kind, defs)
    for _, b in ipairs(defs) do
      local w = tonumber(b.width) or 0
      if w > 0 then
        local key = kind .. "|" .. tostring(b.label) .. "|" .. w .. "|" .. tostring(b.font_size)
        if not seen[key] then
          seen[key] = true
          print("@@LABEL " .. json.encode({ kind = kind, label = b.label, width = w, font_size = b.font_size }))
        end
      end
    end
  end
  local T, W = inLoop()
  local cards = {}
  for id in pairs(INVESTIGATORS) do cards[#cards + 1] = seat(W, id) end
  T.env.shApiCounter({ name = "hour", delta = 0 })
  local function sweep(kind, setup)
    setup()
    dump(kind, T.buttons)
    for _, c in ipairs(cards) do dump("card", c.buttons) end
  end
  -- the play panel: every Hour, the three bands, the four stages, big Memory, every party size
  for n = 1, 4 do
    for hour = 1, 9 do
      for _, dis in ipairs({ 0, 6, 11, 24 }) do
        for stage = 0, 3 do
          sweep("play", function()
            T.patch(function(c)
              c.investigators = n ; c.hourglass = hour ; c.dissonance = math.min(dis, 8 * n) ; c.appointedStage = stage
              c.bankedMemory = (hour == 9) and 40 or hour
              c.knowledge["the-way-the-night-breaks"] = (stage == 3) or nil
            end)
          end)
        end
      end
    end
  end
  -- the Prologue and the finale
  local P = fresh()
  P.env.shApiCounter({ name = "investigators", delta = 1 })
  dump("prologue", P.buttons)
  T.patch(function(c) c.knowledge["the-way-the-night-breaks"] = true ; c.finale = true ; c.contest = 12 end)
  dump("finale", T.buttons)
  T.patch(function(c) c.finale = false end)
  -- Between Loops and the Interlude, with every kind of aging row
  T.patch(function(c) c.loopEnded = true ; c.loopsCompleted = 12 ; c.years = { sthrelias = 17, sthrayako = 5, sthrcass = 12, sthrbirdie = 16, sthrseraphine = 3 }
    c.brackets = { sthrayako = { bracket = "Weathered", physical = "combat", mental = "willpower" },
      sthrcass = { bracket = "Elder", physical = "agility", mental = "intellect" } }
    c.loopTallies = { sthrelias = { raises = 12, spent = 12 }, sthrcass = { raises = 3, spent = 4 } }
    c.pendingYears = { sthrelias = 12 }
    c.quest = { sthrelias = { tally = 3, unlocked = false }, sthrbirdie = { tally = 8, unlocked = true } } end)
  dump("between", T.buttons)
  for _, c in ipairs(cards) do dump("card", c.buttons) end
  T.click("Interlude")
  dump("interlude", T.buttons)
  T.env.shApiAge({ id = "sthrelias", defeated = true })
  dump("interlude", T.buttons)
  for _, id in ipairs({ "sthrayako", "sthrbirdie", "sthrseraphine", "sthrcass" }) do
    local U, W2 = inLoop()
    seat(W2, id)
    U.env.shApiCounter({ name = "hour", delta = 0 })
    U.patch(function(c) c.loopEnded = true ; c.loopsCompleted = 9 ; c.years = { [id] = 17 }
      c.brackets = { [id] = { bracket = "Ancient", physical = "agility", mental = "intellect" } } end)
    dump("between", U.buttons)
    U.click("Interlude")
    dump("interlude", U.buttons)
    U.env.shApiAge({ id = id, defeated = true })
    dump("interlude", U.buttons)
  end
  check("the label sweep ran", next(seen) ~= nil)
end

print(failures == 0 and ("control_flow: OK (" .. total .. " checks)") or ("control_flow: " .. failures .. " FAILURE(S) of " .. total))
os.exit(failures == 0 and 0 or 1)
