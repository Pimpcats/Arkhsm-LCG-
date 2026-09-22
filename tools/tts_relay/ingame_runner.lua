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
      elseif ids[md.id] then
        bad[#bad + 1] = md.id .. ": duplicate id"
      else
        ids[md.id] = true
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
  check("every card has unique SCED metadata", #bad == 0,
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
