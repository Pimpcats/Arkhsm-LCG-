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

------------------------------------------------------ table presence steps --
-- The campaign box (dist/the_still_hour_table.json): SCED memory bag holding
-- the investigator minicards, the campaign log and the campaign guide.

local tp = { box = nil, ml = nil, placed = {}, log = nil, n = 0 }

local function findSpawned(pred)
  for _, o in pairs(spawned) do
    if pred(o) then return o end
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
  check("campaign log placed (Tag CampaignLog)", log ~= nil)
  if not log then return go() end
  check("log GMNotes type CampaignLog", gm(log).type == "CampaignLog")
  waitFor(function() return #(log.getButtons() or {}) >= 20 and #(log.getInputs() or {}) >= 5 end, 30, function(ok)
    check("log draws its checkboxes, counters and write-in fields", ok,
      #(log.getButtons() or {}) .. " buttons, " .. #(log.getInputs() or {}) .. " inputs")
    -- page 1 field order: 1 started, 2 Standard, 3 Hard, 4 investigators, 5 loops
    local okc = pcall(function()
      log.call("sthrLog_2")
      log.call("sthrLog_5")
      log.call("sthrLog_5")
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
          local oks, r = pcall(function() return p2.call("syncFromCampaignState") end)
          check("log syncs from the campaign-state token", oks and type(r) == "table" and r.ok == true,
            (oks and type(r) == "table") and ("updated " .. tostring(r.updated)) or tostring(r))
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
