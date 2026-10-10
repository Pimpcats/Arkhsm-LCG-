-- THE STILL HOUR — automated in-game test runner.
--
-- Sent into a running Tabletop Simulator game by tools/tts_relay/relay.py via
-- the External Editor API ("Execute Lua Code", messageID 3, guid -1). The relay
-- prepends one table before this file:
--
--   local RELAY = { run = "<run id>", payloads = { {name=, json=, role=}, ... },
--                   pause = <seconds between screenshots> }
--
-- Payloads without a role are the component builds: spawned together and
-- tested first. The payload with role "saved_object" is the exact file the
-- owner loads (dist/saved_object_the_still_hour.json); it is spawned on its
-- own once the component builds are cleared away (see "the saved object").
--
-- Everything here is local to the chunk; nothing leaks into Global. Results go
-- back to the relay with sendExternalMessage (messageID 4):
--   {relay="result", name, ok, detail}   one check
--   {relay="screenshot", name}           relay captures the TTS window now
--   {relay="done", passed, failed}       run finished
--
-- Only objects carrying the TAG below are ever destroyed, so the owner's own
-- table (SCED, their decks) is never touched.

local TAG = "StillHourRelay"
local P, F = 0, 0

local function send(t)
  t.run = RELAY.run
  sendExternalMessage(t)
end

local function check(name, ok, detail)
  if ok then P = P + 1 else F = F + 1 end
  print((ok and "[PASS] " or "[FAIL] ") .. name .. (detail and ("  -- " .. tostring(detail)) or ""))
  send({ relay = "result", name = name, ok = ok and true or false,
         detail = detail ~= nil and tostring(detail) or nil })
end

local function info(msg)
  print("[INFO] " .. msg)
  send({ relay = "info", message = msg })
end

-- Sequential steps chained through Wait callbacks: step(next) must call next()
-- exactly once. A step that errors is reported as a failure and the run moves on.
local steps, idx = {}, 0
local function step(name, fn) steps[#steps + 1] = { name = name, fn = fn } end

-- A destroyed (or mid-destruction) object throws a .NET NullReferenceException
-- on any access, and that escapes pcall and kills the run ("Object reference
-- not set to an instance of an object"). Check before touching an object that
-- can disappear: one put in a bag, merged into a deck, or removed by SCED.
local function alive(o)
  if o == nil then return false end
  local ok, dead = pcall(function() return o.isDestroyed() end)
  return ok and dead == false
end
-- the step now running, so an error in one of its delayed callbacks can be
-- charged to it and the run can move on
local currentName, currentGo = nil, nil

-- Delayed callbacks (Wait.frames / condition / time) run outside the step's
-- pcall: an error there used to kill the whole run ("incomplete", timed out).
-- This local Wait passes everything to TTS's Wait with each callback
-- protected: the error becomes a failed check naming the step, and the run
-- continues with the next step.
local TTSWait = Wait
local function protect(fn)
  if type(fn) ~= "function" then return fn end
  return function(...)
    local ok, err = pcall(fn, ...)
    if not ok then
      check("step '" .. tostring(currentName) .. "' ran without a Lua error", false, err)
      if currentGo then currentGo() end
    end
  end
end
local Wait = {
  frames = function(fn, n) return TTSWait.frames(protect(fn), n) end,
  time = function(fn, secs, reps) return TTSWait.time(protect(fn), secs, reps) end,
  condition = function(fn, cond, timeout, onTimeout)
    return TTSWait.condition(protect(fn), cond, timeout, protect(onTimeout))
  end,
  stop = function(id) return TTSWait.stop(id) end,
}

local function nextStep()
  idx = idx + 1
  local s = steps[idx]
  if not s then
    print(string.format("RELAY RESULT: %d passed, %d failed", P, F))
    send({ relay = "done", passed = P, failed = F })
    return
  end
  local called = false
  local function go()
    if called then return end
    called = true
    nextStep()
  end
  currentName, currentGo = s.name, go
  local ok, err = pcall(s.fn, go)
  if not ok then
    check("step '" .. s.name .. "' ran without a Lua error", false, err)
    go()
  end
end

-- Wait for cond() up to `timeout` seconds, then call done(true|false).
local function waitFor(cond, timeout, done)
  local finished = false
  local id
  id = Wait.condition(function()
    if finished then return end
    finished = true
    done(true)
  end, cond, timeout, function()
    if finished then return end
    finished = true
    done(false)
  end)
  return id
end

local function decode(s)
  if type(s) ~= "string" or s == "" then return nil end
  local ok, v = pcall(JSON.decode, s)
  if ok then return v end
  return nil
end

local function deepEqual(a, b)
  if type(a) ~= type(b) then return false end
  if type(a) ~= "table" then return a == b end
  for k, v in pairs(a) do if not deepEqual(v, b[k]) then return false end end
  for k in pairs(b) do if a[k] == nil then return false end end
  return true
end

local function hostPlayer()
  local all = {}
  for _, p in ipairs(Player.getPlayers() or {}) do all[#all + 1] = p end
  for _, p in ipairs(Player.getSpectators() or {}) do all[#all + 1] = p end
  for _, p in ipairs(all) do
    if p.host then return p end
  end
  return all[1]
end

local spawned = {}     -- name -> object
local byNick = {}      -- nickname -> object

local COMPONENTS, SAVED = {}, nil
for _, pl in ipairs(RELAY.payloads) do
  if pl.role == "saved_object" then SAVED = pl else COMPONENTS[#COMPONENTS + 1] = pl end
end

-- GUIDs already on the table when the run starts (after an earlier run's
-- leftovers are removed): the owner's and SCED's objects, GUID -> name. The
-- relay never tags or destroys one of them, and skips a campaign box's Place
-- when it would move one (see "campaign box: Place").
local OWNER = {}
local function isOwners(o)
  local ok, g = pcall(function() return o.getGUID() end)
  return ok and OWNER[g] ~= nil
end

------------------------------------------------------------------ the steps --

step("environment", function(go)
  local all = getObjects()
  info("table has " .. #all .. " object(s) before the run")
  -- SCED's GUID reference handler (src/core/GUIDReferenceApi.ttslua); its
  -- playmats carry no identifying tag, so this is the one reliable marker
  info(getObjectFromGUID("123456") ~= nil and "SCED detected (GUID reference handler)"
    or "SCED not detected: running on a non-SCED table")
  -- the owner's own campaign on this table (its Control token): the relay's
  -- Controls would write their test state into the owner's campaign log, and
  -- Clear Board would take the owner's laid-out cards. Run nothing.
  for _, o in ipairs(all) do
    if alive(o) and not o.hasTag(TAG)
       and (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) then
      check("the table holds no Still Hour campaign in progress", false,
        "a Still Hour Control token is on the table: the relay needs a fresh SCED table, not a campaign save")
      idx = #steps                    -- nothing else runs; the relay gets "done"
      return go()
    end
  end
  go()
end)

step("cleanup previous run", function(go)
  local old = getObjectsWithTag(TAG)
  for _, o in ipairs(old) do destroyObject(o) end
  info("removed " .. #old .. " object(s) left by an earlier relay run")
  Wait.frames(function()
    for _, o in ipairs(getObjects()) do
      if alive(o) then OWNER[o.getGUID()] = tostring(o.getName()) end
    end
    go()
  end, 10)
end)

step("spawn payloads", function(go)
  local pending = #COMPONENTS
  if pending == 0 then check("job has at least one payload", false) ; return go() end
  for _, pl in ipairs(COMPONENTS) do
    local ok, err = pcall(spawnObjectJSON, {
      json = pl.json,
      callback_function = function(o)
        spawned[pl.name] = o
        byNick[o.getName()] = o
        pending = pending - 1
      end,
    })
    if not ok then
      check("spawnObjectJSON accepts " .. pl.name, false, err)
      pending = pending - 1
    end
  end
  waitFor(function() return pending <= 0 end, 30, function(ok)
    local n = 0
    for _ in pairs(spawned) do n = n + 1 end
    check("every payload finished spawning", ok and n == #COMPONENTS,
      n .. "/" .. #COMPONENTS .. " spawned")
    Wait.frames(go, 30)       -- let onLoad scripts run
  end)
end)

-- every card in an object's data (decks, bags, boxes inside boxes): its SCED
-- metadata, and where its face and back images come from
local function scanCards(data, acc)
  acc = acc or { ids = {}, cards = 0, bad = {}, local_urls = 0, urls = 0, hosted = 0, unhosted = {} }
  if data.Name == "Card" or data.Name == "CardCustom" then
    acc.cards = acc.cards + 1
    local md = decode(data.GMNotes)
    if not md or type(md.id) ~= "string" then
      acc.bad[#acc.bad + 1] = tostring(data.GUID or "?") .. ": GMNotes not SCED JSON"
    elseif acc.ids[md.id] and not deepEqual(acc.ids[md.id], md) then
      -- copies of one card legitimately share an id; they must agree
      acc.bad[#acc.bad + 1] = md.id .. ": copies disagree on metadata"
    else
      acc.ids[md.id] = md
    end
    for _, d in pairs(data.CustomDeck or {}) do
      for _, u in ipairs({ d.FaceURL or "", d.BackURL or "" }) do
        acc.urls = acc.urls + 1
        if u:find("^file:") then acc.local_urls = acc.local_urls + 1 end
        -- published images are pinned to the commit that holds them
        -- (pipeline/publish_hosted.py): raw.githubusercontent.com/<owner>/<repo>/<40-hex sha>/
        local sha = u:match("^https://raw%.githubusercontent%.com/[^/]+/[^/]+/(%x+)/")
        if sha and #sha == 40 then
          acc.hosted = acc.hosted + 1
        elseif #acc.unhosted < 5 then
          acc.unhosted[#acc.unhosted + 1] = tostring(data.GUID or "?") .. " " .. u:sub(1, 48)
        end
      end
    end
  end
  for _, c in ipairs(data.ContainedObjects or {}) do scanCards(c, acc) end
  for _, st in pairs(data.States or {}) do scanCards(st, acc) end
  return acc
end

step("card metadata", function(go)
  local acc = scanCards({})
  for name, o in pairs(spawned) do
    if alive(o) then scanCards(o.getData(), acc) else info("payload '" .. name .. "' is gone (absorbed into a container?)") end
  end
  local bad = acc.bad
  check("spawned content contains cards", acc.cards > 0, acc.cards .. " card(s)")
  check("every card has consistent SCED metadata", #bad == 0,
    #bad == 0 and nil or table.concat(bad, "; ", 1, math.min(#bad, 8)))
  check("no card image points at a local file:/// path", acc.local_urls == 0,
    acc.local_urls .. " local URL(s)")
  go()
end)

step("control token", function(go)
  local ctl, ctlName
  for name, o in pairs(spawned) do
    if alive(o) and (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) then
      ctl, ctlName = o, name
    end
  end
  check("control token is present and scripted", ctl ~= nil)
  if not ctl then return go() end
  local buttons = ctl.getButtons() or {}
  check("control token created its buttons", #buttons >= 7, #buttons .. " button(s)")
  -- a fresh campaign opens in the Prologue (no Appointed); the board checks
  -- below exercise a loop, so end the Prologue first
  local okp, st = pcall(function() return ctl.call("shApiState") end)
  check("a new campaign opens in the Prologue", okp and type(st) == "table" and st.prologue == true)
  local oke, st2 = pcall(function() return ctl.call("shApiEndPrologue") end)
  check("ending the Prologue starts Loop 1 without counting a loop",
    oke and type(st2) == "table" and st2.prologue == false and st2.loops == 0)
  local ok, res = pcall(function() return ctl.call("runStillHourTests") end)
  check("in-engine rules tests ran", ok and type(res) == "table", (not ok) and res or nil)
  if ok and type(res) == "table" then
    check("in-engine rules tests all pass", (res.failed or 1) == 0,
      tostring(res.passed) .. " passed, " .. tostring(res.failed) .. " failed")
  end
  -- save/load round trip: reload() re-runs onLoad(script_state)
  -- script_state is only written when TTS saves the game; getData() runs
  -- onSave now, which is what a save or reload would store
  local state = ctl.getData().LuaScriptState
  check("control token saves its state", type(state) == "string" and #state > 0)
  local fresh = ctl.reload()
  Wait.frames(function()
    local nb = fresh and #(fresh.getButtons() or {}) or 0
    check("control token survives save+reload", fresh ~= nil and nb >= 7, nb .. " button(s) after reload")
    check("state preserved across reload",
      alive(fresh) and deepEqual(decode(fresh.getData().LuaScriptState), decode(state)))
    if fresh then spawned[ctlName] = fresh end
    go()
  end, 60)
end)

------------------------------------------------------------ board wiring --
-- These drive the control token the way a player would (every call below is
-- what a button click runs), then look at the physical objects. Each step
-- restores the campaign state it started from. Objects the steps create carry
-- the relay TAG, so the next run removes them.

local function findControl()
  for _, o in pairs(spawned) do
    if alive(o) and (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) then return o end
  end
  return nil
end

local function labelsOf(o)
  local out = {}
  for _, b in ipairs(o and o.getButtons() or {}) do out[#out + 1] = b.label end
  return table.concat(out, " | ")
end

local function hasButton(o, prefix)
  for _, b in ipairs(o and o.getButtons() or {}) do
    if (b.label or ""):sub(1, #prefix) == prefix then return true end
  end
  return false
end

local function dist(a, b)
  if not a or not b then return math.huge end
  local dx, dz = a.x - b.x, a.z - b.z
  return math.sqrt(dx * dx + dz * dz)
end

-- SCED's GUID reference handler (src/core/GUIDReferenceApi.ttslua)
local function scedObject(owner, t)
  local h = getObjectFromGUID("123456")
  if not h then return nil end
  local ok, o = pcall(function() return h.call("getObjectByOwnerAndType", { owner = owner, type = t }) end)
  return ok and o or nil
end

local snapshot, scedHere

step("board: touchable counters", function(go)
  local ctl = findControl()
  if not ctl then check("control token available for board steps", false) ; return go() end
  snapshot = ctl.call("shApiSnapshot")
  local s0 = ctl.call("shApiState")
  scedHere = s0.sced == true
  info("control sees " .. (scedHere and "SCED" or "a vanilla table") .. "; [static] mode " .. tostring(s0.static.mode))
  check("control shows Memory / Dissonance / Hour counters",
    hasButton(ctl, "Memory ") and hasButton(ctl, "Dissonance ") and hasButton(ctl, "Hour ")
    and hasButton(ctl, "Appointed: "), labelsOf(ctl))
  local s1 = ctl.call("shApiCounter", { name = "memory", delta = 2 })
  check("Memory counter +2", s1.memory == s0.memory + 2, s0.memory .. " -> " .. s1.memory)
  check("Memory button label follows", hasButton(ctl, "Memory " .. s1.memory .. " /"), labelsOf(ctl))
  local s2 = ctl.call("shApiCounter", { name = "hour", delta = 1 })
  check("Hour counter advances the Hourglass", s2.hour == s0.hour + 1, s0.hour .. " -> " .. s2.hour)
  local s3 = ctl.call("shApiCounter", { name = "hour", delta = -1 })
  check("Hour counter rewinds", s3.hour == s0.hour)
  local saved = ctl.getData().LuaScriptState     -- onSave now (script_state lags until a save)
  local fresh = ctl.reload()
  Wait.frames(function()
    local s4 = fresh and fresh.call("shApiState")
    check("counters persist through save+reload", s4 ~= nil and s4.memory == s1.memory,
      s4 and ("memory " .. s4.memory) or "no control after reload")
    for name, o in pairs(spawned) do if o == ctl then spawned[name] = fresh end end
    if fresh then fresh.call("shApiRestore", { blob = snapshot }) end
    check("save blob is non-empty", type(saved) == "string" and #saved > 0)
    go()
  end, 90)
end)

-- Dissonance band starts for the table's current investigator count (Constants.forCount:
-- reset 8n, 16 solo; Glitch from a third of it, Noticed from two-thirds)
local function bandStarts(ctl)
  local n = (ctl.call("shApiState") or {}).investigators or 3
  local reset = (n == 1) and 16 or 8 * n
  return math.floor(reset / 3), math.floor(2 * reset / 3)
end

local function staticInBag(bag)
  -- SCED respawns its chaos bag when a difficulty is set (setChaosBagState),
  -- so a bag found earlier can be gone: look it up again
  if not alive(bag) then bag = Global.call("findChaosBag") end
  if not alive(bag) then return 0 end
  local n = 0
  for _, e in ipairs(bag.getObjects() or {}) do
    for _, t in ipairs(e.tags or {}) do if t == "StillHourStatic" then n = n + 1 end end
  end
  return n
end

step("board: [static] in the chaos bag", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  if not scedHere then
    local s = ctl.call("shApiCounter", { name = "dissonance", delta = (bandStarts(ctl)) })
    check("vanilla table: [static] counted without touching any bag",
      s.static.target == 1 and s.static.mode ~= "sced", s.static.mode .. " target " .. s.static.target)
    ctl.call("shApiRestore", { blob = snapshot })
    return go()
  end
  local bag = Global.call("findChaosBag")
  check("SCED chaos bag found (ChaosBagApi.findChaosBag)", bag ~= nil)
  if not bag then return go() end
  local start = staticInBag(bag)
  local d0 = ctl.call("shApiState").dissonance
  local glitchAt, noticedAt = bandStarts(ctl)
  local toGlitch = math.max(0, glitchAt - d0)
  ctl.call("shApiCounter", { name = "dissonance", delta = toGlitch })
  waitFor(function() return staticInBag(bag) == 1 end, 15, function(ok1)
    check("entering Glitch puts 1 [static] in the chaos bag", ok1, start .. " -> " .. staticInBag(bag))
    ctl.call("shApiCounter", { name = "dissonance", delta = noticedAt - glitchAt })
    waitFor(function() return staticInBag(bag) == 2 end, 15, function(ok2)
      check("entering Noticed puts a 2nd [static] in the chaos bag", ok2, "in bag: " .. staticInBag(bag))
      local state = Global.call("getChaosBagState")
      check("SCED's own bag state still reads (ChaosBagApi.getChaosBagState)", type(state) == "table",
        type(state) == "table" and (#state .. " SCED token(s)") or tostring(state))
      -- a reveal: take one [static] out of the bag (what drawChaosToken does)
      local guid
      for _, e in ipairs(bag.getObjects()) do
        for _, t in ipairs(e.tags or {}) do if t == "StillHourStatic" then guid = e.guid end end
      end
      local before = ctl.call("shApiState").dissonance
      local pos = bag.getPosition()
      local token = bag.takeObject({ guid = guid, smooth = false, position = { pos.x, pos.y + 3, pos.z + 3 } })
      waitFor(function() return ctl.call("shApiState").static.pending == 1 end, 10, function(okPending)
      check("drawing a [static] waits for an explicit resolution", okPending and ctl.call("shApiState").dissonance == before)
      ctl.call("shApiResolveStatic", {guid=guid})
      waitFor(function() return ctl.call("shApiState").dissonance == before + 1 end, 10, function(ok3)
        check("resolving a [static] from the bag raises Dissonance by 1", ok3,
          before .. " -> " .. ctl.call("shApiState").dissonance)
        if token then bag.putObject(token) end
        ctl.call("shApiRestore", { blob = snapshot })
        waitFor(function() return staticInBag(bag) == 0 end, 15, function(ok4)
          check("back to Calm removes the [static] tokens again", ok4, "in bag: " .. staticInBag(bag))
          go()
        end)
      end)
      end)
    end)
  end)
end)

-- two connected campaign locations, off to the side of the control token
local LOC_A, LOC_B, LOC_C, MINI = {}, {}, nil, nil
local function locationJSON(id, name, icon, conn, x, z)
  return JSON.encode({
    Name = "Card", Nickname = name, Tags = { "Location", "ScenarioCard", TAG },
    Transform = { posX = x, posY = 1.5, posZ = z, rotX = 0, rotY = 180, rotZ = 0,
                  scaleX = 1, scaleY = 1, scaleZ = 1 },
    GMNotes = JSON.encode({ id = id, type = "Location", cycle = "The Still Hour",
      locationFront = { icons = icon, connections = conn,
                        uses = { { countPerInvestigator = 1, type = "Clue", token = "clue" } } },
      locationBack = { icons = icon, connections = conn } }),
    CardID = 990100, CustomDeck = { ["9901"] = {
      FaceURL = "https://placehold.co/750x1050/2b2233/e8d9a8.png?text=location",
      BackURL = "https://placehold.co/750x1050/1b1622/e8d9a8.png?text=back",
      NumWidth = 1, NumHeight = 1, BackIsHidden = true, UniqueBack = false, Type = 0 } },
  })
end

local function spawnJSON(json, done)
  spawnObjectJSON({ json = json, callback_function = function(o) o.addTag(TAG) ; done(o) end })
end

step("board: locations flip and seal", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  local base = ctl.getPosition()
  local pending = 3
  local function one() pending = pending - 1 end
  spawnJSON(locationJSON("sthr-loc-lanternroom", "Relay Location A", "Diamond", "Circle",
    base.x - 2, base.z + 9), function(o) LOC_A.obj = o ; one() end)
  spawnJSON(locationJSON("sthr-loc-sealedstudy", "Relay Location B", "Circle", "Diamond",
    base.x + 2, base.z + 9), function(o) LOC_B.obj = o ; one() end)
  spawnJSON(JSON.encode({ Name = "CardCustom", Nickname = "Relay Minicard", Tags = { "Minicard", TAG },
    GMNotes = JSON.encode({ id = "relay-m", type = "Minicard" }),
    -- a custom card without CustomDeck makes TTS open its blocking "Custom Card"
    -- import dialog (empty Face/Back), which stalls the whole relay run
    CardID = 990300, CustomDeck = { ["9903"] = {
      FaceURL = "https://placehold.co/500x700/2b2233/e8d9a8.png?text=minicard",
      BackURL = "https://placehold.co/500x700/1b1622/e8d9a8.png?text=back",
      NumWidth = 1, NumHeight = 1, BackIsHidden = true, UniqueBack = false, Type = 0 } },
    Transform = { posX = base.x - 2, posY = 2, posZ = base.z + 9, rotX = 0, rotY = 180, rotZ = 0,
                  scaleX = 0.6, scaleY = 1, scaleZ = 0.6 } }), function(o) MINI = o ; one() end)
  waitFor(function() return pending <= 0 end, 20, function(ok)
    check("test locations + minicard spawned", ok)
    if not ok then return go() end
    local rep = ctl.call("shApiSyncBoard")
    check("board finds both campaign locations by metadata id", (rep.seen or 0) >= 2, "seen " .. tostring(rep.seen))
    check("a location with an unknown fact stays on its front", LOC_A.obj.is_face_down == false)
    check("a closed location is labelled CLOSED", hasButton(LOC_B.obj, "CLOSED"), labelsOf(LOC_B.obj))
    if scedHere then
      local tracker = scedObject("Mythos", "TokenSpawnTracker")
      check("SCED clue spawn is held back while closed (TokenSpawnTrackerApi)",
        tracker ~= nil and tracker.call("hasSpawnedTokens", LOC_B.obj.getGUID()) == true)
    end
    ctl.call("shApiUnlockFact", { id = "the-lamp-was-never-lit" })
    Wait.frames(function()
      check("unlocking the flip fact turns the location to its back", LOC_A.obj.is_face_down == true)
      -- the Sealed Study opens when its act 2a becomes current: act 1a (What
      -- the Almanac Hid) advancing in Part II with the Vote already recorded
      ctl.call("shApiSetPartTwo", { on = true })
      ctl.call("shApiUnlockFact", { id = "the-vote-that-never-ends" })
      local r = ctl.call("shApiUnlockFact", { id = "what-the-almanac-hid" })
      -- button removals apply at the end of the frame: look a few frames later
      Wait.frames(function()
        check("the CLOSED label comes off once every fact is known (Part II)", not hasButton(LOC_B.obj, "CLOSED"),
          labelsOf(LOC_B.obj))
      end, 5)
      if scedHere then
        check("SCED clue spawn is released for the opened location",
          r ~= nil and r.report ~= nil and r.report.opened == 1, r and r.report and ("opened " .. tostring(r.report.opened)))
      end
      -- put the card face up again for the Appointed step (facts are rolled back)
      LOC_A.obj.setRotation({ 0, 180, 0 })
      ctl.call("shApiRestore", { blob = snapshot })
      go()
    end, 20)
  end)
end)

local function findAppointedCard()
  for _, o in ipairs(getObjects()) do
    if alive(o) and o.type == "Card" then
      local md = decode(o.getGMNotes())
      if md and md.id == "sthr-appointed" then return o end
    end
  end
  return nil
end

step("board: the Appointed", function(go)
  local ctl = findControl()
  if not ctl or not LOC_B.obj then check("locations available for the Appointed step", false) ; return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  -- the Appointed never appears at a closed location: open LOC_B first
  ctl.call("shApiSetPartTwo", { on = true })
  ctl.call("shApiUnlockFact", { id = "the-vote-that-never-ends" })
  ctl.call("shApiUnlockFact", { id = "what-the-almanac-hid" })
  local s = ctl.call("shApiCounter", { name = "appointed" })   -- a card advances it: Sensed
  check("a card advance makes it Sensed", s.stage == 1, "stage " .. tostring(s.stage))
  waitFor(function()
    local c = findAppointedCard()
    return c ~= nil and dist(c.getPosition(), LOC_B.obj.getPosition()) < 2
  end, 10, function(ok)
    local card = findAppointedCard()
    if card then card.addTag(TAG) end
    check("it manifests at the location farthest from the investigators", ok,
      card and string.format("%.1f from farthest", dist(card.getPosition(), LOC_B.obj.getPosition())) or "card not found")
    check("its card carries a Hold Back button", hasButton(card, "Hold Back"), labelsOf(card))
    local hourBefore = ctl.call("shApiCounter", { name = "hour", delta = 2 }).hour
    local stageAfter = ctl.call("shApiHoldBack")
    local s2 = ctl.call("shApiState")
    check("Hold Back drops one stage and rewinds one Hour", stageAfter == 0 and s2.hour == hourBefore - 1,
      "stage " .. tostring(stageAfter) .. ", hour " .. hourBefore .. " -> " .. s2.hour)
    Wait.frames(function()
      card = findAppointedCard()
      check("at Unseen it leaves the board", card ~= nil and dist(card.getPosition(), LOC_B.obj.getPosition()) > 3
        and not hasButton(card, "Hold Back"))
      ctl.call("shApiCounter", { name = "appointed" })        -- Sensed again, back at the farthest
      Wait.frames(function()
        card = findAppointedCard()
        -- it cannot be defeated: put it in a container and it comes back
        local bin
        for _, o in pairs(spawned) do if alive(o) and o.type == "Bag" then bin = o end end
        if card and bin then bin.putObject(card) end
        waitFor(function()
          local c = findAppointedCard()
          return c ~= nil and dist(c.getPosition(), LOC_B.obj.getPosition()) < 2
        end, 10, function(back)
          check("it cannot be defeated: removed from play, it returns", back)
          local c = findAppointedCard()
          if c then c.addTag(TAG) end
          ctl.call("shApiCounter", { name = "appointed" })    -- Emerging: Hunter
          check("Emerging adds a Hunt button", hasButton(findAppointedCard(), "Hunt"), labelsOf(findAppointedCard()))
          ctl.call("shApiHunt")
          c = findAppointedCard()
          check("Hunt moves it one location toward its prey",
            c ~= nil and dist(c.getPosition(), LOC_A.obj.getPosition()) < 2,
            c and string.format("%.1f from prey location", dist(c.getPosition(), LOC_A.obj.getPosition())))
          ctl.call("shApiRestore", { blob = snapshot })       -- Unseen: set aside
          if scedHere then
            local tracker = scedObject("Mythos", "TokenSpawnTracker")
            for _, l in ipairs({ LOC_A, LOC_B }) do
              if tracker and l.obj then pcall(function() tracker.call("resetTokensSpawned", l.obj.getGUID()) end) end
            end
          end
          Wait.frames(go, 10)
        end)
      end, 10)
    end, 10)
  end)
end)

local function investigatorJSON(id, name, stats, x, z)
  return JSON.encode({
    Name = "Card", Nickname = name, Tags = { "Investigator", "PlayerCard", TAG }, SidewaysCard = true,
    Transform = { posX = x, posY = 1.5, posZ = z, rotX = 0, rotY = 180, rotZ = 0, scaleX = 1, scaleY = 1, scaleZ = 1 },
    GMNotes = JSON.encode({ id = id, type = "Investigator", cycle = "The Still Hour",
      willpowerIcons = stats[1], intellectIcons = stats[2], combatIcons = stats[3], agilityIcons = stats[4],
      health = stats[5], sanity = stats[6] }),
    CardID = 990200, CustomDeck = { ["9902"] = {
      FaceURL = "https://placehold.co/1050x750/2b2233/e8d9a8.png?text=investigator",
      BackURL = "https://placehold.co/1050x750/1b1622/e8d9a8.png?text=back",
      NumWidth = 1, NumHeight = 1, BackIsHidden = true, UniqueBack = true, Type = 0 } },
  })
end

local function minicardJSON(id, pos)
  return JSON.encode({ Name = "CardCustom", Nickname = "Relay minicard " .. id, Tags = { "Minicard", TAG },
    GMNotes = JSON.encode({ id = id, type = "Minicard" }),
    CardID = 990300, CustomDeck = { ["9903"] = {
      FaceURL = "https://placehold.co/500x700/2b2233/e8d9a8.png?text=minicard",
      BackURL = "https://placehold.co/500x700/1b1622/e8d9a8.png?text=back",
      NumWidth = 1, NumHeight = 1, BackIsHidden = true, UniqueBack = false, Type = 0 } },
    Transform = { posX = pos.x, posY = pos.y + 1, posZ = pos.z, rotX = 0, rotY = 180, rotZ = 0,
                  scaleX = 0.6, scaleY = 1, scaleZ = 0.6 } })
end

local function appointedAt(loc)
  local c = findAppointedCard()
  return c ~= nil and loc ~= nil and dist(c.getPosition(), loc.getPosition()) < 2
end

local INV = {}
step("board: prey follows on-card Memory", function(go)
  local ctl = findControl()
  if not ctl or not LOC_A.obj or not LOC_B.obj then check("locations available for the prey step", false) ; return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  -- the Appointed never enters a closed location: open LOC_B first
  ctl.call("shApiSetPartTwo", { on = true })
  ctl.call("shApiUnlockFact", { id = "the-vote-that-never-ends" })
  ctl.call("shApiUnlockFact", { id = "what-the-almanac-hid" })
  -- the earlier step's minicard would count as a nearer investigator; move it off the map
  if MINI then MINI.destruct() ; MINI = nil end
  local base = ctl.getPosition()
  local pending = 5
  local function one() pending = pending - 1 end
  spawnJSON(investigatorJSON("sthrelias", "Relay Investigator E", { 3, 2, 4, 3, 9, 5 }, base.x - 3, base.z - 7),
    function(o) INV.elias = o ; one() end)
  spawnJSON(investigatorJSON("sthrbirdie", "Relay Investigator B", { 2, 3, 3, 5, 6, 7 }, base.x + 3, base.z - 7),
    function(o) INV.birdie = o ; one() end)
  spawnJSON(minicardJSON("sthrelias-m", LOC_A.obj.getPosition()), one)
  local miniB
  spawnJSON(minicardJSON("sthrbirdie-m", LOC_B.obj.getPosition()), function(o) miniB = o ; one() end)
  -- a third location joined to both, so "toward the prey" has two directions
  spawnJSON(locationJSON("sthr-loc-nave", "Relay Location C", "Moon", "Diamond|Circle", base.x, base.z + 14),
    function(o) LOC_C = o ; one() end)
  waitFor(function() return pending <= 0 end, 20, function(ok)
    check("investigator cards, minicards and a third location spawned", ok)
    if not ok then return go() end
    local list = ctl.call("shApiInvestigators")
    local seen = {}
    -- `list` is owned by the control's script: read its fields, never store
    -- its tables in ours (TTS: "Attempt to perform operations with resources
    -- owned by different scripts", runs ab136f1 / 02d733e)
    for _, i in ipairs(list or {}) do if i.hasCard then seen[i.id] = true end end
    check("both investigators are found by card metadata", seen["sthrelias"] ~= nil and seen["sthrbirdie"] ~= nil)
    check("each investigator card has a Memory button", hasButton(INV.elias, "Memory ")
      and hasButton(INV.birdie, "Memory "), labelsOf(INV.elias))
    check("each investigator card shows Years", hasButton(INV.birdie, "Years 0"), labelsOf(INV.birdie))
    ctl.call("shApiOnCardMemory", { id = "sthrbirdie", delta = 3 })
    ctl.call("shApiOnCardMemory", { id = "sthrelias", delta = 1 })
    check("the card's Memory button follows the count", hasButton(INV.birdie, "Memory 3"), labelsOf(INV.birdie))
    ctl.call("shApiCounter", { name = "appointed" })
    ctl.call("shApiCounter", { name = "appointed" })      -- Emerging: a Hunter
    Wait.frames(function()
      check("it manifests at the location away from both investigators", appointedAt(LOC_C))
      ctl.call("shApiHunt")
      check("it hunts the investigator with the most Memory (not merely the nearest)", appointedAt(LOC_B.obj))
      ctl.call("shApiOnCardMemory", { id = "sthrelias", delta = 4 })
      ctl.call("shApiHunt")
      check("the investigator it engaged holds it there after the prey changes (Rules Reference: Hunter)", appointedAt(LOC_B.obj))
      -- Birdie leaves; now it goes for the investigator with the most Memory
      if alive(miniB) then miniB.destruct() end
      Wait.frames(function()
        ctl.call("shApiHunt")
        check("when another investigator has more Memory, the prey changes", appointedAt(LOC_A.obj))
        go()
      end, 5)
    end, 20)
  end)
end)

local function trackerStats(matColor)
  local t = scedObject(matColor, "InvestigatorSkillTracker")
  if not t then return nil end
  return decode(t.script_state)
end

step("board: Aging on the investigator", function(go)
  local ctl = findControl()
  if not ctl or not INV.elias then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  local _, noticedAt = bandStarts(ctl)
  ctl.call("shApiCounter", { name = "dissonance", delta = noticedAt })
  ctl.call("shApiReset")                                   -- the loop ends in danger
  -- leaning is derived from the investigator's own tallies, clicked on the card
  local card = INV.elias
  check("the investigator card has both leaning tallies",
    hasButton(card, "Dissonance raised 0") and hasButton(card, "Loop-power Memory 0"), labelsOf(card))
  local t = ctl.call("shApiTally", { id = "sthrelias", kind = "raises", delta = 2 })
  check("two Dissonance raises are not leaning", t ~= nil and t.leaned == false)
  t = ctl.call("shApiTally", { id = "sthrelias", kind = "spent", delta = 4 })
  check("4 Memory on loop powers is leaning", t ~= nil and t.leaned == true)
  check("the card shows the tallies", hasButton(card, "Dissonance raised 2") and hasButton(card, "Loop-power Memory 4"),
    labelsOf(card))
  local r1 = ctl.call("shApiAge", { id = "sthrelias", defeated = true, physical = "combat", mental = "willpower" })
  check("Age adds Years for defeat, danger and leaning (4)", r1 ~= nil and r1.years == 4,
    r1 and ("years " .. r1.years) or "no result")
  check("a second Age in the same interlude is refused", ctl.call("shApiAge", { id = "sthrelias" }) == nil)
  ctl.call("shApiBeginNextLoop")
  check("the tallies clear when the next loop begins", hasButton(card, "Loop-power Memory 0"), labelsOf(card))
  ctl.call("shApiReset")
  local r2 = ctl.call("shApiAge", { id = "sthrelias", defeated = true, physical = "combat", mental = "willpower" })
  check("the next interlude reaches Weathered", r2 ~= nil and r2.bracket == "Weathered",
    r2 and (r2.years .. " " .. r2.bracket) or "no result")
  check("the investigator card shows Years and bracket", hasButton(INV.elias, "Years 6 · Weathered"),
    labelsOf(INV.elias))
  local seatedMat
  for _, i in ipairs(ctl.call("shApiInvestigators") or {}) do
    if i.id == "sthrelias" and i.matColor then seatedMat = i.matColor end
  end
  if scedHere and seatedMat then
    local stats = trackerStats(seatedMat)
    check("SCED skill tracker shows the aged skills (wil +1, com -1)",
      type(stats) == "table" and stats[1] == 4 and stats[2] == 2 and stats[3] == 3 and stats[4] == 3,
      type(stats) == "table" and table.concat(stats, "/") or tostring(stats))
  else
    info("no Still Hour investigator seated on a SCED mat: skill tracker not exercised")
  end
  -- persistence: save + reload keeps Years
  local fresh = ctl.reload()
  Wait.frames(function()
    local list = fresh and fresh.call("shApiInvestigators") or {}
    local years
    for _, i in ipairs(list) do if i.id == "sthrelias" then years = i.years end end
    check("Years persist through save+reload", years == 6, tostring(years))
    for name, o in pairs(spawned) do if o == ctl then spawned[name] = fresh end end
    go()
  end, 90)
end)

step("board: SCED campaign export carries the state", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  local logs = getObjectsWithTag("CampaignLog")
  if #logs ~= 1 then
    info(#logs .. " campaign log(s) on the table: export mirror not exercised (needs exactly one)")
    ctl.call("shApiRestore", { blob = snapshot })
    ctl.call("shApiSyncBoard")
    return go()
  end
  local m = ctl.call("shApiLogMirror")
  check("state is mirrored into the campaign log", m ~= nil and m.bytes > 0)
  -- SCED's export stores the log's getData() in the save coin (import respawns
  -- it); the log belongs to the owner's table, so it is read, never replaced
  local data = logs[1].getData()
  check("the campaign log's saved data (what SCED exports) carries the state",
    (data.Memo or ""):find("stillHour", 1, true) ~= nil)
  -- a freshly loaded control token (empty state) adopts it
  local cdata = ctl.getData()
  cdata.LuaScriptState = ""
  cdata.GUID = nil
  cdata.Transform.posZ = cdata.Transform.posZ - 8
  spawnObjectData({ data = cdata, callback_function = function(copy)
    copy.addTag(TAG)
    Wait.frames(function()
      local s = copy.call("shApiState")
      local years
      for _, i in ipairs(copy.call("shApiInvestigators") or {}) do if i.id == "sthrelias" then years = i.years end end
      check("a fresh control token adopts the imported state", years == 6 and s.loops >= 2,
        "years " .. tostring(years) .. ", loops " .. tostring(s.loops))
      copy.destruct()
      ctl.call("shApiRestore", { blob = snapshot })
      ctl.call("shApiSyncBoard")                        -- trackers back to the restored Years
      go()
    end, 30)
  end })
end)

-- does the control build carry this function? (a check that needs a newer
-- build is reported as skipped on an older one, not failed)
local function ctlHas(ctl, fname)
  return (ctl.getLuaScript() or ""):find(fname, 1, true) ~= nil
end

local function countOf(list, id)
  local n = 0
  for _, v in ipairs(list or {}) do if v == id then n = n + 1 end end
  return n
end

step("board: chaos bag difficulty presets", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  if not scedHere then
    local r = ctl.call("shApiDifficulty", { i = 2 })
    check("vanilla table: a difficulty preset asks for the bag to be built by hand", r == false)
    return go()
  end
  local bag = Global.call("findChaosBag")
  if not bag then check("SCED chaos bag found for the difficulty presets", false) ; return go() end
  -- the owner's bag is put back exactly as it was afterwards
  local before = {}
  for i, id in ipairs(Global.call("getChaosBagState") or {}) do before[i] = id end
  ctl.call("shApiCounter", { name = "dissonance", delta = (bandStarts(ctl)) })     -- Glitch: 1 [static]
  local ok1 = ctl.call("shApiDifficulty", { i = 1 })              -- Easy: 17 tokens
  waitFor(function()
    local st = Global.call("getChaosBagState") or {}
    return #st == 17 and staticInBag(bag) == 1
  end, 15, function(done1)
    local st = Global.call("getChaosBagState") or {}
    check("Easy fills SCED's chaos bag with the guide's 17 tokens", ok1 == true and done1 and #st == 17
      and countOf(st, "p1") == 2 and countOf(st, "blue") == 1, #st .. " token(s)")
    check("...and the band's [static] is put back in the bag", staticInBag(bag) == 1, "in bag: " .. staticInBag(bag))
    ctl.call("shApiDifficulty", { i = 4 })                          -- Expert: 19 tokens
    waitFor(function()
      local s2 = Global.call("getChaosBagState") or {}
      return #s2 == 19 and staticInBag(bag) == 1
    end, 15, function(done2)
      local s2 = Global.call("getChaosBagState") or {}
      check("Expert replaces the token set (19 tokens, one -8, no +1)", done2 and #s2 == 19
        and countOf(s2, "m8") == 1 and countOf(s2, "p1") == 0, #s2 .. " token(s)")
      Global.call("setChaosBagState", before)
      ctl.call("shApiRestore", { blob = snapshot })
      waitFor(function() return staticInBag(bag) == 0 and #(Global.call("getChaosBagState") or {}) == #before end,
        15, function(back)
          check("the table's own chaos bag is put back afterwards", back, "in bag: " .. staticInBag(bag))
          go()
        end)
    end)
  end)
end)

step("board: claiming a Victory banks it once", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  local m0 = ctl.call("shApiState").memory
  local first = ctl.call("shApiClaimVictory", { id = "sthr-bellringer" })
  local m1 = ctl.call("shApiState").memory
  local vn = ctl.call("shApiState").investigators
  check("claiming a Named enemy's Victory banks 2 per investigator", first == true and m1 == m0 + 2 * vn, m0 .. " -> " .. m1)
  local second = ctl.call("shApiClaimVictory", { id = "sthr-bellringer" })
  local m2 = ctl.call("shApiState").memory
  check("a second claim of the same Victory banks nothing", second == false and m2 == m1, m1 .. " -> " .. m2)
  check("an unknown enemy has no Victory to claim", ctl.call("shApiClaimVictory", { id = "sthr-nobody" }) == false)
  ctl.call("shApiRestore", { blob = snapshot })
  go()
end)

step("board: an interlude purchase", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  ctl.call("shApiCounter", { name = "memory", delta = 5 })
  local cost
  for _, r in ipairs(ctl.call("shApiInterlude", {}) or {}) do
    if r.id == "sthr-longwayround" then cost = r.cost end
  end
  check("the interlude panel lists a Recollection with its price", cost == 2, tostring(cost))
  check("the control shows the Interlude panel", hasButton(ctl, "Begin Next Loop"), labelsOf(ctl))
  local m0 = ctl.call("shApiState").memory
  local r1 = ctl.call("shApiBuy", { recollection = "sthr-longwayround" })
  check("buying a Recollection spends its Memory", r1 ~= nil and r1.ok == true and r1.memory == m0 - 2,
    r1 and (m0 .. " -> " .. r1.memory) or "no result")
  local r2 = ctl.call("shApiBuy", { level = 5 })
  check("an unaffordable level-up is refused", r2 ~= nil and r2.ok == false and r2.memory == m0 - 2)
  local r3 = ctl.call("shApiBuy", { level = 3 })
  check("a level-3 upgrade spends 3", r3 ~= nil and r3.ok == true and r3.memory == m0 - 5)
  ctl.call("shApiInterlude", { open = false })
  ctl.call("shApiRestore", { blob = snapshot })
  go()
end)

step("board: bank on-card Memory", function(go)
  local ctl = findControl()
  if not ctl or not INV.elias then check("investigators available for banking", false) ; return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  ctl.call("shApiOnCardMemory", { id = "sthrelias", delta = 2 })
  ctl.call("shApiOnCardMemory", { id = "sthrbirdie", delta = 1 })
  local departedCheck = ctlHas(ctl, "function Interlude.isDeparted")
  if departedCheck then ctl.call("shApiOnCardMemory", { id = "sthr-not-in-play", delta = 4 }) end
  local m0 = ctl.call("shApiState").memory
  local n = ctl.call("shApiBankOnCard")
  local m1 = ctl.call("shApiState").memory
  check("Bank on-card Memory moves the investigators' Memory to the bank (3)", n == 3 and m1 == m0 + 3,
    tostring(n) .. " banked, " .. m0 .. " -> " .. m1)
  check("the investigator card's Memory goes back to 0", hasButton(INV.elias, "Memory 0"), labelsOf(INV.elias))
  if departedCheck then
    check("Memory on a departed investigator's cards is not banked", n == 3)
  else
    info("control build predates departed investigators: that check is skipped")
  end
  ctl.call("shApiRestore", { blob = snapshot })
  go()
end)

step("board: pending Years", function(go)
  local ctl = findControl()
  if not ctl or not INV.elias then check("investigators available for pending Years", false) ; return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  ctl.call("shApiBeginNextLoop")                           -- a fresh loop: nobody has aged in it
  local p = ctl.call("shApiPendingYears", { id = "sthrelias", delta = 2 })
  check("a card's Years are held as pending (2)", p == 2, tostring(p))
  check("the investigator card shows its pending Years", hasButton(INV.elias, "Years pending 2"), labelsOf(INV.elias))
  ctl.call("shApiReset")                                    -- a calm loop: no danger
  local r = ctl.call("shApiAge", { id = "sthrelias", physical = "combat", mental = "willpower" })
  if ctlHas(ctl, "extraYears = cond.extraYears") then
    check("Age adds the pending Years (1 + 2)", r ~= nil and r.gained == 3, r and ("gained " .. r.gained) or "no result")
  else
    info("control build predates pending Years reaching Age: that check is skipped")
  end
  check("pending Years are cleared once added", ctl.call("shApiPendingYears", { id = "sthrelias", delta = 0 }) == 0)
  ctl.call("shApiRestore", { blob = snapshot })
  ctl.call("shApiSyncBoard")
  go()
end)

step("board: Hour VI once per loop", function(go)
  local ctl = findControl()
  if not ctl then return go() end
  ctl.call("shApiRestore", { blob = snapshot })
  local s0 = ctl.call("shApiState")
  local extra0 = s0.static.extra
  local s1 = ctl.call("shApiCounter", { name = "hour", delta = 6 - s0.hour })
  check("reaching Hour VI adds 1 Static token until the end of the loop", s1.hour == 6 and s1.static.extra == extra0 + 1,
    "hour " .. s1.hour .. ", extra " .. s1.static.extra)
  ctl.call("shApiCounter", { name = "hour", delta = -1 })
  local s2 = ctl.call("shApiCounter", { name = "hour", delta = 1 })
  check("reaching Hour VI again this loop adds nothing (once per loop)", s2.hour == 6 and s2.static.extra == extra0 + 1,
    "extra " .. s2.static.extra)
  if ctlHas(ctl, "function shApiUndoHourSix") then
    check("the control offers Undo Hour VI", hasButton(ctl, "Undo Hour VI"), labelsOf(ctl))
    local what = ctl.call("shApiUndoHourSix")
    local s3 = ctl.call("shApiState")
    check("Undo Hour VI takes its Static token back", what == "static" and s3.static.extra == extra0
      and s3.hourSix == false, tostring(what) .. ", extra " .. s3.static.extra)
    ctl.call("shApiCounter", { name = "hour", delta = -1 })
    local s4 = ctl.call("shApiCounter", { name = "hour", delta = 1 })
    check("after the undo, Hour VI resolves again when reached", s4.static.extra == extra0 + 1)
  else
    info("control build predates Undo Hour VI: that check is skipped")
  end
  ctl.call("shApiRestore", { blob = snapshot })
  Wait.frames(go, 10)
end)

step("deal a card", function(go)
  local bag, most = nil, 0
  for _, o in pairs(spawned) do
    local n = alive(o) and (o.type == "Bag" or o.type == "Deck") and #(o.getObjects() or {}) or 0
    if n > most then bag, most = o, n end
  end
  if not bag then check("a card container was spawned", false) ; return go() end
  local pos = bag.getPosition()
  local took
  bag.takeObject({ index = 0, smooth = false,
    position = { pos.x, pos.y + 3, pos.z + 6 },
    callback_function = function(o) took = o end })
  waitFor(function() return took ~= nil end, 10, function(ok)
    if ok then took.addTag(TAG) end
    check("a card can be taken out and lands on the table", ok and took ~= nil)
    if ok then
      local md = decode(took.getGMNotes())
      check("the dealt card carries its metadata", md ~= nil and md.id ~= nil,
        md and md.id or took.getName())
    end
    go()
  end)
end)

------------------------------------------------------ table presence steps --
-- The campaign box (dist/the_still_hour_table.json): SCED memory bag holding
-- the investigator minicards, the campaign log and the campaign guide.

local tp = { box = nil, ml = nil, placed = {}, log = nil, n = 0 }

local function findSpawned(pred)
  for _, o in pairs(spawned) do
    if alive(o) and pred(o) then return o end
  end
  return nil
end

local function gm(o)
  return decode(o.getGMNotes and o.getGMNotes() or "") or {}
end

local function hasButton(o, label)
  for _, b in ipairs(o.getButtons() or {}) do
    if b.label == label then return true end
  end
  return false
end

local function near(a, b)
  return a and b and math.abs(a.x - b.x) < 1 and math.abs(a.z - b.z) < 1
end

local function logValues(o)
  local ok, v = pcall(function() return o.call("getLogValues") end)
  if ok and type(v) == "table" then return v end
  return nil
end

step("campaign box: Place", function(go)
  tp.box = findSpawned(function(o) return gm(o).type == "CampaignBox" end)
  check("campaign box spawned (GMNotes type CampaignBox)", tp.box ~= nil)
  if not tp.box then return go() end
  check("campaign box carries SCED's memory-bag script",
    (tp.box.getLuaScript() or ""):find("function buttonClick_place", 1, true) ~= nil)
  local st = decode(tp.box.script_state) or {}
  tp.ml = st.ml or {}
  for _ in pairs(tp.ml) do tp.n = tp.n + 1 end
  check("campaign box remembers where its contents go", tp.n >= 3, tp.n .. " object(s)")
  -- SCED's memory bag MOVES an object already on the table under a remembered
  -- GUID instead of taking its own copy out: never let it move (and this run
  -- then tag and remove) the owner's own campaign pieces
  local taken = 0
  for g in pairs(tp.ml) do if getObjectFromGUID(g) ~= nil then taken = taken + 1 end end
  if taken > 0 then
    tp.box, tp.skipped = nil, true
    info("the table already holds " .. taken .. " object(s) under the campaign box's GUIDs (a campaign laid out?): "
      .. "its Place, minicard, guide, log and Recall checks are skipped so those pieces are left alone")
    return go()
  end
  waitFor(function() return hasButton(tp.box, "Place") and hasButton(tp.box, "Recall") end, 30, function(ok)
    check("campaign box shows Place and Recall", ok)
    local okc, err = pcall(function() tp.box.call("buttonClick_place") end)
    check("Place runs", okc, err)
    waitFor(function()
      for g in pairs(tp.ml) do if getObjectFromGUID(g) == nil then return false end end
      return true
    end, 20, function(all)
      local at = 0
      for g, e in pairs(tp.ml) do
        local o = getObjectFromGUID(g)
        if o then
          o.addTag(TAG)
          tp.placed[#tp.placed + 1] = o
          if near(o.getPosition(), e.pos) then at = at + 1 end
        end
      end
      check("Place lays out every remembered object", all, #tp.placed .. "/" .. tp.n)
      check("each lands on its remembered spot", at == tp.n, at .. "/" .. tp.n)
      Wait.frames(go, 30)
    end)
  end)
end)

step("investigator minicards", function(go)
  local deck
  for _, o in ipairs(tp.placed) do
    if o.hasTag("Minicard") then deck = o end
  end
  if tp.skipped then return go() end
  check("minicard deck placed", deck ~= nil)
  if not deck then return go() end
  local d = deck.getData()
  local cards, good, bad = d.ContainedObjects or { d }, 0, {}
  for _, c in ipairs(cards) do
    local md = decode(c.GMNotes) or {}
    local ok = c.Name == "CardCustom" and md.type == "Minicard"
      and type(md.id) == "string" and md.id:sub(-2) == "-m"
      and math.abs(((c.Transform or {}).scaleX or 0) - 0.6) < 0.01
    local tagged = false
    for _, t in ipairs(c.Tags or {}) do if t == "Minicard" then tagged = true end end
    for _, cd in pairs(c.CustomDeck or {}) do
      if (cd.FaceURL or ""):find("^file:") then ok = false end
    end
    if ok and tagged then good = good + 1 else bad[#bad + 1] = c.Nickname or "?" end
  end
  check("every minicard follows SCED's minicard schema", #bad == 0 and good >= 5,
    good .. " ok" .. (#bad > 0 and ("; bad: " .. table.concat(bad, ", ")) or ""))
  go()
end)

step("campaign guide", function(go)
  local guide
  for _, o in ipairs(tp.placed) do if o.hasTag("CampaignGuide") then guide = o end end
  if tp.skipped then return go() end
  check("campaign guide placed (Tag CampaignGuide)", guide ~= nil)
  if not guide then return go() end
  local d = guide.getData()
  local url = (d.CustomPDF or {}).PDFUrl or ""
  check("guide is a Custom_PDF with GMNotes type CampaignGuide",
    d.Name == "Custom_PDF" and gm(guide).type == "CampaignGuide", d.Name)
  check("guide PDF is hosted, not a local file", url:find("^https://") ~= nil and url:find("%.pdf") ~= nil, url)
  local okb, page = pcall(function() return guide.Book.getPage() end)
  if okb then check("guide opens as a book", type(page) == "number", tostring(page)) end
  go()
end)

step("campaign log", function(go)
  for _, o in ipairs(tp.placed) do if o.hasTag("CampaignLog") then tp.log = o end end
  local log = tp.log
  if tp.skipped then return go() end
  check("campaign log placed (Tag CampaignLog)", log ~= nil)
  if not log then return go() end
  check("log GMNotes type CampaignLog", gm(log).type == "CampaignLog")
  waitFor(function() return #(log.getButtons() or {}) >= 20 and #(log.getInputs() or {}) >= 5 end, 30, function(ok)
    check("log draws its checkboxes, counters and write-in fields", ok,
      #(log.getButtons() or {}) .. " buttons, " .. #(log.getInputs() or {}) .. " inputs")
    -- page 1 field order: 1 started, 2 Easy, 3 Standard, 4 Hard, 5 Expert, 6 loops
    local okc = pcall(function()
      log.call("sthrLog_3")
      log.call("sthrLog_6")
      log.call("sthrLog_6")
    end)
    local v = logValues(log)
    check("clicking a checkbox and a counter records them", okc and v and v.values.diff_standard == true
      and tonumber(v.values.loops) == 2, v and ("loops=" .. tostring(v.values.loops)) or "no values")
    local okt = pcall(function() log.call("setLogValue", { key = "inv1_name", value = "Relay Test" }) end)
    v = logValues(log)
    check("write-in text is recorded", okt and v and v.values.inv1_name == "Relay Test")
    local okr, tr = pcall(function() return log.call("returnTrauma") end)
    check("SCED can read trauma from the log", okr and type(tr) == "table" and #tr == 8)
    local saved = decode(log.script_state) or {}
    check("log saves its fields (onSave)", type(saved.values) == "table" and tonumber(saved.values.loops) == 2)
    local fresh = log.reload()
    waitFor(function() return fresh and #(fresh.getButtons() or {}) >= 20 end, 30, function(ok2)
      local v2 = fresh and logValues(fresh)
      check("log survives save+reload with its fields", ok2 and v2 and tonumber(v2.values.loops) == 2
        and v2.values.inv1_name == "Relay Test")
      fresh.addTag(TAG)
      tp.log = fresh
      local ok3, p2 = pcall(function() return fresh.setState(2) end)
      check("log turns to page 2", ok3 and p2 ~= nil, (not ok3) and p2 or nil)
      if not (ok3 and p2) then return go() end
      waitFor(function() return #(p2.getButtons() or {}) >= 10 end, 30, function(ok4)
        p2.addTag(TAG)
        local v3 = logValues(p2)
        check("page 2 draws the Knowledge Track", ok4 and v3 and v3.page == 2, gm(p2).id)
        pcall(function() p2.call("setLogValue", { key = "k:you-are-unstuck", value = true }) end)
        v3 = logValues(p2)
        check("page 2 records a fact", v3 and v3.values["k:you-are-unstuck"] == true)
        local ctl = findSpawned(function(o)
          return (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) ~= nil
        end)
        if ctl then
          -- give the campaign a known fact so the sync has something real to copy
          local snap = ctl.call("shApiSnapshot")
          pcall(function() ctl.call("shApiUnlockFact", { id = "the-hour-was-wrong" }) end)
          local oks, r = pcall(function() return p2.call("syncFromCampaignState") end)
          check("log syncs from the Control token",
            oks and type(r) == "table" and r.ok == true and (tonumber(r.updated) or 0) > 0,
            (oks and type(r) == "table") and ("updated " .. tostring(r.updated)) or tostring(r))
          local v5 = logValues(p2)
          check("synced fact is ticked on the log", v5 and v5.values["k:the-hour-was-wrong"] == true)
          pcall(function() ctl.call("shApiRestore", { blob = snap }) end)
        end
        local ok5, p1 = pcall(function() return p2.setState(1) end)
        waitFor(function() return ok5 and p1 and #(p1.getButtons() or {}) >= 20 end, 30, function(ok6)
          local v4 = ok6 and logValues(p1)
          check("page 1 kept its fields across the page turn", v4 and tonumber(v4.values.loops) == 2)
          if p1 then p1.addTag(TAG) ; tp.log = p1 end
          local p = hostPlayer()
          if p and p1 then
            p.lookAt({ position = p1.getPosition(), pitch = 80, yaw = 270, distance = 22 })
            Wait.time(function()
              send({ relay = "screenshot", name = "campaign log" })
              Wait.time(go, RELAY.pause or 2)
            end, RELAY.pause or 2)
          else
            go()
          end
        end)
      end)
    end)
  end)
end)

step("campaign box: Recall", function(go)
  if not tp.box then return go() end
  local before = #(tp.box.getObjects() or {})
  local ok, err = pcall(function() tp.box.call("buttonClick_recall") end)
  check("Recall runs", ok, err)
  waitFor(function()
    for g in pairs(tp.ml) do if getObjectFromGUID(g) ~= nil then return false end end
    return true
  end, 20, function(done)
    local after = #(tp.box.getObjects() or {})
    check("Recall puts everything back in the box", done and after == before + tp.n,
      before .. " -> " .. after)
    go()
  end)
end)

step("screenshots", function(go)
  local p = hostPlayer()
  if not p then info("no seated player: screenshots skipped") ; return go() end
  local views = {}
  for name, o in pairs(spawned) do
    if alive(o) then views[#views + 1] = { name = name, pos = o.getPosition() } end
  end
  table.sort(views, function(a, b) return a.name < b.name end)
  local i = 0
  local pause = RELAY.pause or 2
  local function shoot()
    i = i + 1
    local v = views[i]
    if not v then return go() end
    p.lookAt({ position = v.pos, pitch = 65, yaw = 180, distance = 18 })
    Wait.time(function()
      send({ relay = "screenshot", name = v.name })
      Wait.time(shoot, pause)
    end, pause)
  end
  shoot()
end)

------------------------------------------------------------------ cleanup --

-- the relay's own scenario boxes: the cleanup also removes what they laid out
local relayBoxTags = {}

-- leave the owner's table as it was: the owner plays on this same table, so a
-- run must not leave its test objects behind (they used to wait for the next
-- run's cleanup). Objects that were on the table before the run never go.
local function cleanUp(what)
  local n = 0
  local function drop(o)
    if alive(o) and not isOwners(o) then destroyObject(o) ; n = n + 1 end
  end
  for _, o in pairs(spawned) do drop(o) end
  for _, o in ipairs(getObjectsWithTag(TAG)) do drop(o) end
  for tag in pairs(relayBoxTags) do
    for _, o in ipairs(getObjectsWithTag(tag)) do drop(o) end
  end
  -- [static] tokens a relay Control spawned that never reached the chaos bag
  -- (its spawn callback dies with the Control); ones inside a bag are not
  -- table objects and stay put
  for _, o in ipairs(getObjectsWithTag("StillHourStatic")) do drop(o) end
  info("removed " .. n .. " object(s) " .. what)
end

-- the saved object below shares GUIDs with the component builds: clear them
-- away first so it spawns and lays out exactly as on the owner's table
-- objects on the table that were not there before the run, and objects that
-- were there and are gone. A report, not a check: SCED replaces some of its
-- own objects (its chaos bag when a difficulty is set), so a changed GUID is
-- not always a leftover or a loss.
local function reportNewObjects(when)
  local extra = {}
  for _, o in ipairs(getObjects()) do
    if alive(o) and not isOwners(o) then
      extra[#extra + 1] = (o.type == "Card" or o.type == "Deck") and (o.type .. " " .. o.getGUID())
        or (tostring(o.getName()) .. " (" .. tostring(o.type) .. ")")
    end
  end
  info(#extra == 0 and ("the table holds only what was on it before the run (" .. when .. ")")
    or (#extra .. " object(s) on the table that were not there before the run (" .. when .. "): "
      .. table.concat(extra, ", ", 1, math.min(#extra, 12))))
  local gone = {}
  for g, name in pairs(OWNER) do
    if getObjectFromGUID(g) == nil then gone[#gone + 1] = name .. " (" .. g .. ")" end
  end
  table.sort(gone)
  info(#gone == 0 and ("every object that was on the table before the run is still there (" .. when .. ")")
    or (#gone .. " object(s) that were on the table before the run are gone (" .. when .. "): "
      .. table.concat(gone, ", ", 1, math.min(#gone, 12))))
end

step("clear the component builds away", function(go)
  cleanUp("of the component builds")
  for k in pairs(spawned) do spawned[k] = nil end
  Wait.frames(function()
    reportNewObjects("component builds cleared")
    go()
  end, 30)
end)

-------------------------------------------------------- the saved object --
-- dist/saved_object_the_still_hour.json is the exact file the owner loads
-- (docs/LOADING.md: Objects > Saved Objects > The Still Hour, then Place). It
-- is tested on its own: what the box holds and where its card images come
-- from, its Place, the Control token it lays out, one scenario box's Place /
-- Clear Board / Place again, and moving a campaign in progress onto a fresh
-- Control through the campaign log (the update path in docs/LOADING.md).
-- Check names and details stay neutral (no scenario or card names): results
-- are summarised in chat.

local SB = { placed = {}, boxes = {} }

local function pieceKind(md, tags, script, isBag)
  if md.type == "ScenarioBox" then return "scenario box" end
  if md.type == "CampaignLog" or tags.CampaignLog then return "campaign log" end
  if md.type == "CampaignGuide" or tags.CampaignGuide then return "campaign guide" end
  if tags.Minicard then return "minicard deck" end
  if tags.StillHourStatic then return "[static] token" end
  if (script or ""):find("function runStillHourTests", 1, true) then return "Control token" end
  if isBag then return "player-card bag" end
  return "other"
end

local function tagSet(list)
  local t = {}
  for _, v in ipairs(list or {}) do t[v] = true end
  return t
end

local function kindOfData(e)
  return pieceKind(decode(e.GMNotes) or {}, tagSet(e.Tags), e.LuaScript, e.Name == "Bag")
end

local function kindOfObject(o)
  return pieceKind(gm(o), tagSet(o.getTags()), o.getLuaScript(), o.type == "Bag")
end

-- what the package holds (docs/LOADING.md, "Everything you need is one file")
local SAVED_HOLDS = {
  { "scenario box", 8, "8 scenario boxes" },
  { "campaign log", 1, "the campaign log" },
  { "campaign guide", 1, "the campaign guide" },
  { "minicard deck", 1, "the investigator minicards" },
  { "player-card bag", 1, "the player-card bag" },
  { "Control token", 1, "the Control token" },
  { "[static] token", 1, "the [static] token" },
}

-- the fields that make up "where the campaign is" (copied out at once: tables
-- a Control returns belong to its script and die with it)
local STATE_KEYS = { "memory", "dissonance", "hour", "stage", "investigators", "loops", "prologue", "finale", "partTwo" }
local function stateOf(ctl)
  local ok, s = pcall(function() return ctl.call("shApiState") end)
  if not ok or type(s) ~= "table" then return nil end
  local out = {}
  for _, k in ipairs(STATE_KEYS) do out[k] = s[k] end
  return out
end
local function describeState(s)
  if not s then return "no state" end
  return string.format("memory %s, dissonance %s, hour %s, loops %s, prologue %s", tostring(s.memory),
    tostring(s.dissonance), tostring(s.hour), tostring(s.loops), tostring(s.prologue))
end
local function mirrorSeq(ctl)
  local ok, m = pcall(function() return ctl.call("shApiLogMirror") end)
  if ok and type(m) == "table" then return tonumber(m.seq), tonumber(m.bytes) end
  return nil, nil
end

step("saved object: spawn the box the owner loads", function(go)
  if not SAVED then
    info("the job has no saved_object payload: the file the owner loads is not tested")
    return go()
  end
  local ok, err = pcall(spawnObjectJSON, { json = SAVED.json, callback_function = function(o)
    o.addTag(TAG)
    SB.box = o
  end })
  if not ok then check("spawnObjectJSON accepts the saved object", false, err) ; return go() end
  waitFor(function() return SB.box ~= nil end, 30, function(done)
    check("the saved object spawns", done)
    if not done then return go() end
    local box = SB.box
    check("it is SCED's campaign box (GMNotes type CampaignBox)", gm(box).type == "CampaignBox")
    check("it carries SCED's memory-bag script",
      (box.getLuaScript() or ""):find("function buttonClick_place", 1, true) ~= nil)
    waitFor(function() return alive(box) and hasButton(box, "Place") and hasButton(box, "Recall") end, 30, function(okb)
      check("the saved object's box shows Place and Recall", okb, labelsOf(box))
      go()
    end)
  end)
end)

step("saved object: what the box holds", function(go)
  local box = SB.box
  if not alive(box) then return go() end
  SB.data = box.getData()
  local contents = SB.data.ContainedObjects or {}
  local counts = {}
  for _, e in ipairs(contents) do
    local k = kindOfData(e)
    counts[k] = (counts[k] or 0) + 1
    if k == "Control token" then SB.ctlGuid = e.GUID end
    if k == "scenario box" then SB.nBoxes = (SB.nBoxes or 0) + 1 end
  end
  local total = 0
  for _, want in ipairs(SAVED_HOLDS) do
    total = total + want[2]
    check("the box holds " .. want[3], (counts[want[1]] or 0) == want[2], tostring(counts[want[1]] or 0))
  end
  check("the box holds nothing else (" .. total .. " pieces)", #contents == total and (counts.other or 0) == 0,
    #contents .. " piece(s), " .. (counts.other or 0) .. " unrecognised")
  check("TTS lists the same pieces inside the box", #(box.getObjects() or {}) == #contents,
    #(box.getObjects() or {}) .. " vs " .. #contents)
  local good, nb = 0, 0
  for _, e in ipairs(contents) do
    if kindOfData(e) == "scenario box" then
      nb = nb + 1
      local ml = (decode(e.LuaScriptState) or {}).ml
      if (e.LuaScript or ""):find("StillHourLoop", 1, true) and type(ml) == "table" and next(ml) ~= nil
         and #(e.ContainedObjects or {}) > 0 then
        good = good + 1
      end
    end
  end
  check("every scenario box is replayable, remembers its layout and holds its cards", nb > 0 and good == nb,
    good .. "/" .. nb)
  local acc = scanCards(SB.data)
  check("the box's cards are inside it", acc.cards > 0, acc.cards .. " card(s)")
  check("every card in the box has consistent SCED metadata", #acc.bad == 0,
    #acc.bad == 0 and nil or table.concat(acc.bad, "; ", 1, math.min(#acc.bad, 8)))
  check("every card face and back is a hosted raw.githubusercontent URL pinned to a commit",
    acc.urls > 0 and acc.hosted == acc.urls,
    acc.hosted .. "/" .. acc.urls .. (#acc.unhosted > 0 and ("; e.g. " .. table.concat(acc.unhosted, ", ")) or ""))
  local pdf
  for _, e in ipairs(contents) do
    if e.Name == "Custom_PDF" then pdf = (e.CustomPDF or {}).PDFUrl end
  end
  check("the guide PDF is hosted on raw.githubusercontent",
    type(pdf) == "string" and pdf:find("^https://raw%.githubusercontent%.com/") ~= nil and pdf:find("%.pdf") ~= nil)
  go()
end)

step("saved object: Place on the campaign box", function(go)
  local box = SB.box
  if not alive(box) then return go() end
  local ml = (decode(box.script_state) or {}).ml or {}
  local n, taken = 0, 0
  for g in pairs(ml) do
    n = n + 1
    if getObjectFromGUID(g) ~= nil then taken = taken + 1 end
  end
  check("the box remembers a spot for every piece", n > 0 and n == #((SB.data or {}).ContainedObjects or {}),
    n .. " spot(s)")
  -- SCED's memory bag MOVES an object already on the table under a remembered
  -- GUID: with the owner's own campaign laid out, Place would move their pieces
  if taken > 0 then
    SB.blocked = true
    info("the table already holds " .. taken .. " object(s) under the saved object's GUIDs (a campaign laid out?): "
      .. "its Place, scenario-box and update checks are skipped so those pieces are never moved. "
      .. "Run the relay on a fresh SCED table to test them.")
    return go()
  end
  local okc, err = pcall(function() box.call("buttonClick_place") end)
  check("Place runs on the saved object's box", okc, err)
  waitFor(function()
    for g in pairs(ml) do if getObjectFromGUID(g) == nil then return false end end
    return true
  end, 20, function(all)
    local at = 0
    for g, e in pairs(ml) do
      local o = getObjectFromGUID(g)
      if o and not isOwners(o) then
        o.addTag(TAG)
        SB.placed[#SB.placed + 1] = o
        if near(o.getPosition(), e.pos) then at = at + 1 end
        local k = kindOfObject(o)
        if k == "scenario box" then SB.boxes[#SB.boxes + 1] = o
        elseif k == "Control token" then SB.ctl = o
        elseif k == "campaign log" then SB.log = o end
      end
    end
    check("Place lays out every piece", all and #SB.placed == n, #SB.placed .. "/" .. n)
    check("each piece lands on its remembered spot", at == n, at .. "/" .. n)
    check("the campaign box is empty afterwards", #(box.getObjects() or {}) == 0)
    check("every scenario box is on the table", #SB.boxes > 0 and #SB.boxes == (SB.nBoxes or -1),
      #SB.boxes .. "/" .. tostring(SB.nBoxes))
    check("the campaign log is on the table", SB.log ~= nil)
    waitFor(function() return alive(SB.ctl) and #(SB.ctl.getButtons() or {}) >= 7 end, 20, function(ready)
      check("the Control token is on the table with its buttons", ready, SB.ctl and labelsOf(SB.ctl) or "no Control")
      Wait.frames(go, 70)          -- its onLoad board sync runs 60 frames in
    end)
  end)
end)

step("saved object: the Control token's tests", function(go)
  local ctl = SB.ctl
  if SB.blocked or not alive(ctl) then return go() end
  local s = stateOf(ctl)
  check("the box's Control opens a new campaign in the Prologue", s ~= nil and s.prologue == true and s.loops == 0,
    describeState(s))
  local ok, res = pcall(function() return ctl.call("runStillHourTests") end)
  local passed, failed = ok and type(res) == "table" and res.passed, ok and type(res) == "table" and res.failed
  check("the box's Control runs its in-engine tests", ok and type(res) == "table", (not ok) and res or nil)
  if ok and type(res) == "table" then
    check("the box's Control's in-engine tests all pass", (failed or 1) == 0,
      tostring(passed) .. " passed, " .. tostring(failed) .. " failed")
  end
  Wait.frames(go, 10)
end)

-- what the Control's Clear Board takes: anything tagged StillHourLoop, or a
-- campaign scenario card (src/tts/control.lua isLoopCard)
local SCENARIO_TYPES = { Location = true, Act = true, Agenda = true, Enemy = true, Treachery = true,
  Story = true, ScenarioReference = true, Scenario = true }
local function isLoopEntry(tags, gmNotes)
  for _, t in ipairs(tags or {}) do if t == "StillHourLoop" then return true end end
  local md = decode(gmNotes) or {}
  return tostring(md.id or ""):sub(1, 5) == "sthr-" and SCENARIO_TYPES[md.type] == true and not md.weakness
end

-- campaign scenario cards on the table that `tag` (one box's) did not lay out
local function foreignLoopCards(tag)
  local n = 0
  for _, o in ipairs(getObjects()) do
    if alive(o) and o.type == "Card" then
      if not o.hasTag(tag) and isLoopEntry(o.getTags(), o.getGMNotes()) then n = n + 1 end
    elseif alive(o) and o.type == "Deck" then
      for _, e in ipairs(o.getObjects() or {}) do
        if not tagSet(e.tags)[tag] and isLoopEntry(e.tags, e.gm_notes) then n = n + 1 end
      end
    end
  end
  return n
end

-- cards (and other objects) carrying `tag` on the table, counting decks' cards
local function cardsTagged(tag)
  local n, list = 0, {}
  for _, o in ipairs(getObjectsWithTag(tag)) do
    if alive(o) then
      list[#list + 1] = o
      n = n + (o.type == "Deck" and #(o.getObjects() or {}) or 1)
    end
  end
  return n, list
end

-- what a box's Place lays out, counting the cards in its decks
local function cardsIn(data)
  local n = 0
  for _, e in ipairs(data.ContainedObjects or {}) do
    n = n + ((e.Name == "Deck") and #(e.ContainedObjects or {}) or 1)
  end
  return n
end

local function footprint(o)
  local b = o.getBounds()
  return { x1 = b.center.x - b.size.x / 2, x2 = b.center.x + b.size.x / 2,
           z1 = b.center.z - b.size.z / 2, z2 = b.center.z + b.size.z / 2,
           cx = b.center.x, cz = b.center.z, sx = b.size.x, sz = b.size.z }
end

-- every pair of laid-out objects whose footprints overlap
local function overlapping(list)
  local out, pad = {}, 0.15
  for i = 1, #list do
    for j = i + 1, #list do
      local ok, hit = pcall(function()
        local a, b = footprint(list[i]), footprint(list[j])
        return a.x1 + pad < b.x2 and a.x2 - pad > b.x1 and a.z1 + pad < b.z2 and a.z2 - pad > b.z1
      end)
      if ok and hit then out[#out + 1] = list[i].type .. " " .. list[i].getGUID() .. " / " .. list[j].getGUID() end
    end
  end
  return out
end

-- the table's own pieces (SCED's tokens, counters, bags: objects that were
-- there before the run) that a laid-out object covers. Boards, zones and
-- hidden objects are not in the way; cards are the owner's, not SCED's.
local BOARDS = { ["9f334f"] = true, ["721ba2"] = true, ["4ee1f2"] = true, ["5ce0a1"] = true }
local NOT_PIECES = { Scripting = true, Hand = true, Layout = true, Fog = true, Randomize = true, Zone = true,
  Card = true, Deck = true }
local function onTablePieces(list)
  local out = {}
  local pieces = {}
  for _, s in ipairs(getObjects()) do
    local ok, keep = pcall(function()
      local g = s.getGUID()
      return OWNER[g] ~= nil and not BOARDS[g] and not NOT_PIECES[s.type] and s.interactable ~= false
        and not s.hasTag("NotInteractable")
    end)
    if ok and keep then pieces[#pieces + 1] = s end
  end
  for _, o in ipairs(list) do
    for _, s in ipairs(pieces) do
      local ok, covers = pcall(function()
        local a, b = footprint(o), footprint(s)
        if b.sx >= 30 or b.sz >= 30 then return false end
        -- bounds are not exact: count it only when one covers the other's centre
        return (b.cx > a.x1 and b.cx < a.x2 and b.cz > a.z1 and b.cz < a.z2)
          or (a.cx > b.x1 and a.cx < b.x2 and a.cz > b.z1 and a.cz < b.z2)
      end)
      if ok and covers then
        out[#out + 1] = o.type .. " " .. o.getGUID() .. " on " .. tostring(s.getName()) .. " (" .. s.getGUID() .. ")"
      end
    end
  end
  return out
end

-- A loop is set up again every night: a scenario box must Place a full,
-- fresh copy each time, and the Control's Clear Board must take every card it
-- laid out (and any card drawn from it) back off the table.
step("saved object: a scenario box's Place, Clear Board, Place again", function(go)
  if SB.blocked or not SAVED then return go() end
  local ctl, book = SB.ctl, nil
  for _, o in ipairs(SB.boxes) do if alive(o) and gm(o).id == "prologue" then book = o end end
  book = book or SB.boxes[1]
  check("a scenario box from the saved object and its Control are on the table", alive(book) and alive(ctl))
  if not alive(book) or not alive(ctl) then return go() end
  -- src/tts/loop_box.lua boxTag() is "StillHourBox_<GMNotes id>"; the first published build's boxes
  -- tag what they lay out with the box's GUID ("StillHourBox:<guid>"): test whichever the box has
  local tag = "StillHourBox_" .. tostring(gm(book).id or book.getGUID())
  local script = tostring(book.getLuaScript() or "")
  if script ~= "" and not script:find("StillHourBox_", 1, true) then tag = "StillHourBox:" .. book.getGUID() end
  relayBoxTags[tag] = true
  local inside = #(book.getObjects() or {})
  local expected = cardsIn(book.getData())
  -- Clear Board takes every campaign scenario card on the table: with the
  -- owner's own laid out, clear with this box's Recall (only what it placed)
  local foreign = foreignLoopCards(tag)
  if foreign > 0 then
    info(foreign .. " campaign scenario card(s) already on the table: this check clears with the box's Recall, "
      .. "not the Control's Clear Board")
  end
  local function clear()
    if foreign > 0 then return pcall(function() return book.call("buttonClick_recall") end) end
    return pcall(function() return ctl.call("shApiClearBoard") end)
  end
  local okp, placed = pcall(function() return book.call("buttonClick_place") end)
  check("the scenario box's Place lays out a copy of every object in it", okp and placed == inside,
    tostring(placed) .. "/" .. inside)
  Wait.time(function()
    local n1, list = cardsTagged(tag)
    check("every card it laid out is on the table (none fell into a bag)", n1 == expected, n1 .. "/" .. expected)
    local untagged = 0
    for _, o in ipairs(list) do if not o.hasTag("StillHourLoop") then untagged = untagged + 1 end end
    check("the laid-out cards carry the loop tag", n1 > 0 and untagged == 0, untagged .. " without it")
    local ov = overlapping(list)
    check("no two laid-out cards overlap", #ov == 0, #ov > 0 and table.concat(ov, "; ", 1, math.min(#ov, 6)) or nil)
    local on = onTablePieces(list)
    check("nothing laid out sits on the table's own pieces (tokens, counters, bags)", #on == 0,
      #on > 0 and table.concat(on, "; ", 1, math.min(#on, 6)) or nil)
    -- play: draw a card off a laid-out deck onto the table
    for _, o in ipairs(list) do
      if alive(o) and o.type == "Deck" then
        local p = o.getPosition()
        pcall(function() o.takeObject({ position = { p.x, p.y + 2, p.z + 3 }, smooth = false }) end)
        break
      end
    end
    Wait.time(function()
      local okc, r = clear()
      check(foreign > 0 and "the box's Recall runs" or "Clear Board runs", okc, (not okc) and r or nil)
      Wait.time(function()
        local left = cardsTagged(tag)
        check("every card the box laid out leaves the table (drawn ones too)", left == 0, left .. " left")
        check("the scenario box never empties", #(book.getObjects() or {}) == inside)
        local ok2, placed2 = pcall(function() return book.call("buttonClick_place") end)
        Wait.time(function()
          local n2 = cardsTagged(tag)
          check("the next loop's Place lays out the same cards again", ok2 and placed2 == inside and n2 == n1,
            n2 .. " vs " .. n1)
          clear()
          Wait.time(go, 2)
        end, 3)
      end, 2)
    end, 2)
  end, 3)
end)

-- docs/LOADING.md "Moving a campaign in progress to a newer build": the
-- Control copies its state into the campaign log's memo (TTS saves it with the
-- log); the owner deletes the old Control and takes the new build's Control
-- out of a freshly spawned box (no Place: that would lay out a second log);
-- the fresh Control adopts the copy when it loads.
step("saved object: a campaign in progress moves to a fresh Control (update path)", function(go)
  if SB.blocked or not SAVED then return go() end
  local old, log = SB.ctl, SB.log
  if not alive(old) or not alive(log) or not SB.data or not SB.ctlGuid then
    check("the saved object's Control and campaign log are on the table for the update path", false)
    return go()
  end
  local logs = getObjectsWithTag("CampaignLog")
  if #logs ~= 1 then
    info(#logs .. " campaign logs on the table (the Control keeps its copy only in a single log): "
      .. "update path not exercised")
    return go()
  end
  -- 1. campaign progress, made the way the Control's buttons make it
  old.call("shApiEndPrologue")
  local sp = stateOf(old)
  old.call("shApiCounter", { name = "memory", delta = 3 })
  old.call("shApiCounter", { name = "hour", delta = 2 })
  local s1 = stateOf(old)
  check("campaign progress is recorded on the Control (Prologue over, Memory +3, Hour +2)",
    sp ~= nil and s1 ~= nil and s1.prologue == false and s1.memory == sp.memory + 3 and s1.hour == sp.hour + 2,
    describeState(s1))
  local seq1, bytes1 = mirrorSeq(old)
  check("the Control copies the campaign state into the campaign log", (seq1 or 0) > 0 and (bytes1 or 0) > 0,
    "seq " .. tostring(seq1))
  check("the campaign log's saved data carries the copy (what a TTS save writes)",
    (log.getData().Memo or ""):find("stillHour", 1, true) ~= nil)
  -- 2. the game is saved and loaded: the log comes back from its saved data
  local fresh = log.reload()
  Wait.frames(function()
    if alive(fresh) then fresh.addTag(TAG) ; SB.log = fresh end
    local memo = alive(fresh) and fresh.memo or nil
    check("the copy survives a save+reload of the campaign log",
      type(memo) == "string" and memo:find("stillHour", 1, true) ~= nil)
    -- 3. delete the old Control; spawn the box again; take its Control out
    local pos = old.getPosition()
    destroyObject(old)
    SB.ctl = nil
    local data = SB.data
    data.GUID = nil
    data.Locked = true                     -- hangs where it spawns: nothing else is disturbed
    data.Transform = data.Transform or {}
    data.Transform.posY = (data.Transform.posY or 2) + 2
    data.Transform.posZ = (data.Transform.posZ or 0) - 7
    Wait.frames(function()
      spawnObjectData({ data = data, callback_function = function(copy)
        copy.addTag(TAG)
        local newCtl
        local okt, errt = pcall(function()
          newCtl = copy.takeObject({ guid = SB.ctlGuid, position = { pos.x, pos.y + 1, pos.z }, smooth = false })
        end)
        check("a Control token comes out of a fresh copy of the saved object", okt and newCtl ~= nil,
          (not okt) and errt or nil)
        if not newCtl then return go() end
        newCtl.addTag(TAG)
        waitFor(function() return alive(newCtl) and #(newCtl.getButtons() or {}) >= 7 end, 20, function(ready)
          check("the fresh Control loads with its buttons", ready)
          if not ready then return go() end
          SB.ctl = newCtl
          local s2 = stateOf(newCtl)
          local same = s2 ~= nil
          for _, k in ipairs(STATE_KEYS) do if same and s2[k] ~= s1[k] then same = false end end
          check("the fresh Control adopts the campaign state from the campaign log", same,
            describeState(s2) .. " (was " .. describeState(s1) .. ")")
          -- 4. play goes on: the fresh Control keeps its copy in the same log
          newCtl.call("shApiCounter", { name = "memory", delta = 1 })
          local seq2 = mirrorSeq(newCtl)
          check("the fresh Control keeps saving into the same campaign log", (seq2 or 0) > (seq1 or 0),
            "seq " .. tostring(seq1) .. " -> " .. tostring(seq2))
          go()
        end)
      end })
    end, 10)
  end, 30)
end)

step("clean up this run", function(go)
  cleanUp("this run created")
  Wait.frames(function()
    reportNewObjects("after the run")
    go()
  end, 30)
end)

nextStep()
return "runner started: " .. #steps .. " steps"
