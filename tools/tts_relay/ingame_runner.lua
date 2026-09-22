-- THE STILL HOUR — automated in-game test runner.
--
-- Sent into a running Tabletop Simulator game by tools/tts_relay/relay.py via
-- the External Editor API ("Execute Lua Code", messageID 3, guid -1). The relay
-- prepends one table before this file:
--
--   local RELAY = { run = "<run id>", payloads = { {name=, json=}, ... },
--                   pause = <seconds between screenshots> }
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

------------------------------------------------------------------ the steps --

step("environment", function(go)
  local all = getObjects()
  info("table has " .. #all .. " object(s) before the run")
  -- SCED marks its playmats with this tag; its absence means a vanilla table
  local mats = getObjectsWithTag("Playermat")
  info(#mats > 0 and ("SCED detected (" .. #mats .. " playmat(s))")
    or "SCED not detected: running on a non-SCED table")
  go()
end)

step("cleanup previous run", function(go)
  local old = getObjectsWithTag(TAG)
  for _, o in ipairs(old) do destroyObject(o) end
  info("removed " .. #old .. " object(s) left by an earlier relay run")
  Wait.frames(go, 10)
end)

step("spawn payloads", function(go)
  local pending = #RELAY.payloads
  if pending == 0 then check("job has at least one payload", false) ; return go() end
  for _, pl in ipairs(RELAY.payloads) do
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
    check("every payload finished spawning", ok and n == #RELAY.payloads,
      n .. "/" .. #RELAY.payloads .. " spawned")
    Wait.frames(go, 30)       -- let onLoad scripts run
  end)
end)

step("card metadata", function(go)
  local ids, cards, bad, local_urls = {}, 0, {}, 0
  local function scan(data)
    if data.Name == "Card" or data.Name == "CardCustom" then
      cards = cards + 1
      local md = decode(data.GMNotes)
      if not md or type(md.id) ~= "string" then
        bad[#bad + 1] = (data.Nickname or "?") .. ": GMNotes not SCED JSON"
      elseif ids[md.id] and not deepEqual(ids[md.id], md) then
        -- copies of one card legitimately share an id; they must agree
        bad[#bad + 1] = md.id .. ": copies disagree on metadata"
      else
        ids[md.id] = md
      end
      for _, d in pairs(data.CustomDeck or {}) do
        for _, u in ipairs({ d.FaceURL or "", d.BackURL or "" }) do
          if u:find("^file:") then local_urls = local_urls + 1 end
        end
      end
    end
    for _, c in ipairs(data.ContainedObjects or {}) do scan(c) end
  end
  for _, o in pairs(spawned) do scan(o.getData()) end
  check("spawned content contains cards", cards > 0, cards .. " card(s)")
  check("every card has consistent SCED metadata", #bad == 0,
    #bad == 0 and nil or table.concat(bad, "; ", 1, math.min(#bad, 8)))
  check("no card image points at a local file:/// path", local_urls == 0,
    local_urls .. " local URL(s)")
  go()
end)

step("control token", function(go)
  local ctl, ctlName
  for name, o in pairs(spawned) do
    if (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) then
      ctl, ctlName = o, name
    end
  end
  check("control token is present and scripted", ctl ~= nil)
  if not ctl then return go() end
  local buttons = ctl.getButtons() or {}
  check("control token created its buttons", #buttons >= 7, #buttons .. " button(s)")
  local ok, res = pcall(function() return ctl.call("runStillHourTests") end)
  check("in-engine rules tests ran", ok and type(res) == "table", (not ok) and res or nil)
  if ok and type(res) == "table" then
    check("in-engine rules tests all pass", (res.failed or 1) == 0,
      tostring(res.passed) .. " passed, " .. tostring(res.failed) .. " failed")
  end
  -- save/load round trip: reload() re-runs onLoad(script_state)
  local state = ctl.script_state
  check("control token saves its state", type(state) == "string" and #state > 0)
  local fresh = ctl.reload()
  Wait.frames(function()
    local nb = fresh and #(fresh.getButtons() or {}) or 0
    check("control token survives save+reload", fresh ~= nil and nb >= 7, nb .. " button(s) after reload")
    check("state preserved across reload",
      fresh ~= nil and deepEqual(decode(fresh.script_state), decode(state)))
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
    if (o.getLuaScript() or ""):find("function runStillHourTests", 1, true) then return o end
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
  local saved = ctl.script_state
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

local function staticInBag(bag)
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
    local s = ctl.call("shApiCounter", { name = "dissonance", delta = 6 })
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
  local toGlitch = math.max(0, 6 - d0)
  ctl.call("shApiCounter", { name = "dissonance", delta = toGlitch })
  waitFor(function() return staticInBag(bag) == 1 end, 15, function(ok1)
    check("entering Glitch puts 1 [static] in the chaos bag", ok1, start .. " -> " .. staticInBag(bag))
    ctl.call("shApiCounter", { name = "dissonance", delta = 6 })
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
      waitFor(function() return ctl.call("shApiState").dissonance == before + 1 end, 10, function(ok3)
        check("drawing a [static] from the bag raises Dissonance by 1", ok3,
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
    Transform = { posX = base.x - 2, posY = 2, posZ = base.z + 9, rotX = 0, rotY = 180, rotZ = 0,
                  scaleX = 0.6, scaleY = 1, scaleZ = 0.6 } }), function(o) MINI = o ; one() end)
  waitFor(function() return pending <= 0 end, 20, function(ok)
    check("test locations + minicard spawned", ok)
    if not ok then return go() end
    local rep = ctl.call("shApiSyncBoard")
    check("board finds both campaign locations by metadata id", (rep.seen or 0) >= 2, "seen " .. tostring(rep.seen))
    check("a location with an unknown fact stays on its front", LOC_A.obj.is_face_down == false)
    check("a sealed location is labelled SEALED", hasButton(LOC_B.obj, "SEALED"), labelsOf(LOC_B.obj))
    if scedHere then
      local tracker = scedObject("Mythos", "TokenSpawnTracker")
      check("SCED clue spawn is held back while sealed (TokenSpawnTrackerApi)",
        tracker ~= nil and tracker.call("hasSpawnedTokens", LOC_B.obj.getGUID()) == true)
    end
    ctl.call("shApiUnlockFact", { id = "the-lamp-was-never-lit" })
    Wait.frames(function()
      check("unlocking the flip fact turns the location to its back", LOC_A.obj.is_face_down == true)
      ctl.call("shApiUnlockFact", { id = "what-the-almanac-hid" })
      local r = ctl.call("shApiUnlockFact", { id = "the-vote-that-never-ends" })
      check("the SEALED label comes off once every fact is known", not hasButton(LOC_B.obj, "SEALED"),
        labelsOf(LOC_B.obj))
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
    if o.type == "Card" then
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
        for _, o in pairs(spawned) do if o.type == "Bag" then bin = o end end
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
  -- the earlier step's minicard would count as a nearer investigator; move it off the map
  if MINI then MINI.destruct() ; MINI = nil end
  local base = ctl.getPosition()
  local pending = 5
  local function one() pending = pending - 1 end
  spawnJSON(investigatorJSON("sthr-elias", "Relay Investigator E", { 3, 2, 4, 3, 9, 5 }, base.x - 3, base.z - 7),
    function(o) INV.elias = o ; one() end)
  spawnJSON(investigatorJSON("sthr-birdie", "Relay Investigator B", { 2, 3, 3, 5, 6, 7 }, base.x + 3, base.z - 7),
    function(o) INV.birdie = o ; one() end)
  spawnJSON(minicardJSON("sthr-elias-m", LOC_A.obj.getPosition()), one)
  spawnJSON(minicardJSON("sthr-birdie-m", LOC_B.obj.getPosition()), one)
  -- a third location joined to both, so "toward the prey" has two directions
  spawnJSON(locationJSON("sthr-loc-nave", "Relay Location C", "Moon", "Diamond|Circle", base.x, base.z + 14),
    function(o) LOC_C = o ; one() end)
  waitFor(function() return pending <= 0 end, 20, function(ok)
    check("investigator cards, minicards and a third location spawned", ok)
    if not ok then return go() end
    local list = ctl.call("shApiInvestigators")
    local seen = {}
    for _, i in ipairs(list or {}) do if i.hasCard then seen[i.id] = i end end
    check("both investigators are found by card metadata", seen["sthr-elias"] ~= nil and seen["sthr-birdie"] ~= nil)
    check("each investigator card has a Memory button", hasButton(INV.elias, "Memory ")
      and hasButton(INV.birdie, "Memory "), labelsOf(INV.elias))
    check("each investigator card shows Years", hasButton(INV.birdie, "Years 0"), labelsOf(INV.birdie))
    ctl.call("shApiOnCardMemory", { id = "sthr-birdie", delta = 3 })
    ctl.call("shApiOnCardMemory", { id = "sthr-elias", delta = 1 })
    check("the card's Memory button follows the count", hasButton(INV.birdie, "Memory 3"), labelsOf(INV.birdie))
    ctl.call("shApiCounter", { name = "appointed" })
    ctl.call("shApiCounter", { name = "appointed" })      -- Emerging: a Hunter
    Wait.frames(function()
      check("it manifests at the location away from both investigators", appointedAt(LOC_C))
      ctl.call("shApiHunt")
      check("it hunts the investigator with the most Memory (not merely the nearest)", appointedAt(LOC_B.obj))
      ctl.call("shApiOnCardMemory", { id = "sthr-elias", delta = 4 })
      ctl.call("shApiHunt")
      check("when another investigator has more Memory, the prey changes", appointedAt(LOC_A.obj))
      go()
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
  ctl.call("shApiCounter", { name = "dissonance", delta = 12 })
  ctl.call("shApiReset")                                   -- the loop ends in danger
  local r1 = ctl.call("shApiAge", { id = "sthr-elias", defeated = true, leaned = true,
    physical = "combat", mental = "willpower" })
  check("Age adds Years for defeat, danger and leaning (4)", r1 ~= nil and r1.years == 4,
    r1 and ("years " .. r1.years) or "no result")
  check("a second Age in the same interlude is refused", ctl.call("shApiAge", { id = "sthr-elias" }) == nil)
  ctl.call("shApiBeginNextLoop")
  ctl.call("shApiReset")
  local r2 = ctl.call("shApiAge", { id = "sthr-elias", defeated = true, physical = "combat", mental = "willpower" })
  check("the next interlude reaches Weathered", r2 ~= nil and r2.bracket == "Weathered",
    r2 and (r2.years .. " " .. r2.bracket) or "no result")
  check("the investigator card shows Years and bracket", hasButton(INV.elias, "Years 6 · Weathered"),
    labelsOf(INV.elias))
  local seatedMat
  for _, i in ipairs(ctl.call("shApiInvestigators") or {}) do
    if i.id == "sthr-elias" and i.matColor then seatedMat = i.matColor end
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
    for _, i in ipairs(list) do if i.id == "sthr-elias" then years = i.years end end
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
      for _, i in ipairs(copy.call("shApiInvestigators") or {}) do if i.id == "sthr-elias" then years = i.years end end
      check("a fresh control token adopts the imported state", years == 6 and s.loops >= 2,
        "years " .. tostring(years) .. ", loops " .. tostring(s.loops))
      copy.destruct()
      ctl.call("shApiRestore", { blob = snapshot })
      ctl.call("shApiSyncBoard")                        -- trackers back to the restored Years
      go()
    end, 30)
  end })
end)

step("deal a card", function(go)
  local bag, most = nil, 0
  for _, o in pairs(spawned) do
    local n = (o.type == "Bag" or o.type == "Deck") and #(o.getObjects() or {}) or 0
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

step("screenshots", function(go)
  local p = hostPlayer()
  if not p then info("no seated player: screenshots skipped") ; return go() end
  local views = {}
  for name, o in pairs(spawned) do
    views[#views + 1] = { name = name, pos = o.getPosition() }
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

nextStep()
return "runner started: " .. #steps .. " steps"
