-- THE STILL HOUR — relay probe: seating, one piece at a time (tests only).
--
-- Real TTS froze while Seat investigators spawned the first investigator card (relay run
-- 20261102-174855_4817f64: the last breadcrumb was "seat: spawn the investigator card"). This probe
-- does each piece of seating on its own, a second or more apart, and reports a breadcrumb after each,
-- so the relay's log ends at the exact piece that freezes TTS:
--
--   the saved object spawned and Placed -> Elias's card data copied out of his pouch -> that copy
--   spawned off the mats -> a copy spawned on the White mat's investigator spot (SCED's playmat
--   registers it and reloads its texture) -> his minicard -> his starter deck from SCED's player
--   cards -> the Control's own Seat investigators for both investigators -> everything cleaned up.
--
-- Same protocol as ingame_runner.lua (RELAY header from relay.py, results via sendExternalMessage).
-- Only objects this probe spawned (tagged, or new since it started) are removed.

local TAG = "StillHourRelay"
local P, F = 0, 0
local function send(t) t.run = RELAY.run ; sendExternalMessage(t) end
local function check(name, ok, detail)
  if ok then P = P + 1 else F = F + 1 end
  print((ok and "[PASS] " or "[FAIL] ") .. name .. (detail and ("  -- " .. tostring(detail)) or ""))
  send({ relay = "result", name = name, ok = ok and true or false, detail = detail ~= nil and tostring(detail) or nil })
end
local function crumb(msg)
  print("[probe] " .. msg)
  send({ relay = "info", message = "probe: " .. msg })
end
local function alive(o)
  if o == nil then return false end
  local ok, dead = pcall(function() return o.isDestroyed() end)
  return ok and dead == false
end
local function decode(s)
  if type(s) ~= "string" or s == "" then return nil end
  local ok, v = pcall(JSON.decode, s)
  return ok and v or nil
end
local function gm(o) return decode(o.getGMNotes()) or {} end
local function copy(t) return JSON.decode(JSON.encode(t)) end

local SAVED
for _, pl in ipairs(RELAY.payloads) do if pl.role == "saved_object" then SAVED = pl end end

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
  crumb("step " .. idx .. ": " .. s.name)
  local called = false
  local function go()
    if called then return end
    called = true
    -- a second between pieces: each breadcrumb reaches the relay before the next piece runs
    Wait.time(nextStep, 1.5)
  end
  local ok, err = pcall(s.fn, go)
  if not ok then check("probe step '" .. s.name .. "' ran without a Lua error", false, err) ; go() end
end
local function waitFor(cond, timeout, done)
  local fin = false
  Wait.condition(function() if not fin then fin = true ; done(true) end end,
    function() local ok, v = pcall(cond) ; return ok and v end, timeout,
    function() if not fin then fin = true ; done(false) end end)
end

local function sced(owner, kind)
  local h = getObjectFromGUID("123456")
  return h and h.call("getObjectByOwnerAndType", { owner = owner, type = kind }) or nil
end
local function zone(mat, p) return mat.positionToWorld({ p[1], p[2], p[3] }) end
local function above(p) return { p.x, p.y + 1.5, p.z } end

local before = {}
local S = {}
local function findByName(prefix)
  for _, o in ipairs(getObjects()) do
    if alive(o) and tostring(o.getName()):sub(1, #prefix) == prefix and not before[o.getGUID()] then return o end
  end
  return nil
end
local function entryById(container, id)
  local d = container.getData()
  for _, e in ipairs(d.ContainedObjects or {}) do
    if (decode(e.GMNotes) or {}).id == id then return e end
  end
  return nil
end

step("the table", function(go)
  for _, o in ipairs(getObjects()) do before[o.getGUID()] = true end
  local n = 0
  for _ in pairs(before) do n = n + 1 end
  crumb(n .. " objects on the table; SCED " .. tostring(getObjectFromGUID("123456") ~= nil))
  S.white, S.orange = sced("White", "Playermat"), sced("Orange", "Playermat")
  check("SCED's White and Orange playmats are on the table", S.white ~= nil and S.orange ~= nil)
  if not SAVED then check("the job carries the saved object", false) ; idx = #steps end
  go()
end)

step("spawn the saved object", function(go)
  spawnObjectJSON({ json = SAVED.json, callback_function = function(o) o.addTag(TAG) ; S.box = o end })
  waitFor(function() return alive(S.box) and #(S.box.getButtons() or {}) > 0 end, 30, function(ok)
    check("the campaign box spawns with its buttons", ok)
    go()
  end)
end)

step("Place the campaign box", function(go)
  local ok, err = pcall(function() S.box.call("buttonClick_place") end)
  check("Place runs", ok, err)
  Wait.time(function()
    S.pouch = findByName("Elias Warde")
    S.ctl = findByName("THE STILL HOUR")
    S.minis = nil
    for _, o in ipairs(getObjects()) do
      if alive(o) and not before[o.getGUID()] and o.type == "Deck" then
        for _, e in ipairs(o.getObjects() or {}) do
          if (decode(e.gm_notes) or {}).id == "sthrelias-m" then S.minis = o end
        end
      end
    end
    check("Elias's pouch, the Control and the minicards are on the table", S.pouch ~= nil and S.ctl ~= nil and S.minis ~= nil,
      tostring(S.pouch ~= nil) .. " " .. tostring(S.ctl ~= nil) .. " " .. tostring(S.minis ~= nil))
    if not (S.pouch and S.ctl) then idx = #steps - 1 end
    go()
  end, 8)
end)

step("copy Elias's card data out of his pouch", function(go)
  local e = entryById(S.pouch, "sthrelias")
  crumb("got the entry: " .. tostring(e ~= nil))
  S.inv = e and copy(e)
  if S.inv then S.inv.GUID = nil end
  crumb("copied: " .. tostring(S.inv ~= nil) .. ", " .. #JSON.encode(S.inv or {}) .. " characters")
  check("Elias's card data copies out of his pouch", S.inv ~= nil)
  if not S.inv then idx = #steps - 1 end
  go()
end)

step("spawn that copy off the mats", function(go)
  local p = S.pouch.getPosition()
  crumb("spawning at " .. string.format("%.1f %.1f", p.x + 4, p.z))
  local o = spawnObjectData({ data = copy(S.inv), position = { p.x + 4, p.y + 2, p.z }, rotation = { 0, 180, 0 } })
  crumb("spawnObjectData returned " .. tostring(o ~= nil))
  if o then o.addTag(TAG) end
  Wait.time(function()
    check("the investigator card spawns off the mats", alive(o))
    crumb("still alive after 3 s: " .. tostring(alive(o)))
    if alive(o) then o.destruct() end
    go()
  end, 3)
end)

step("spawn a copy on the White mat's investigator spot", function(go)
  local d = copy(S.inv)
  d.Tags = d.Tags or {}
  d.Tags[#d.Tags + 1] = "StillHourOwner_White"
  local pos = above(zone(S.white, { -1.177, 0, 0.002 }))
  local r = S.white.getRotation()
  crumb("spawning on the mat")
  local o = spawnObjectData({ data = d, position = pos, rotation = { 0, r.y, 0 } })
  crumb("spawnObjectData returned " .. tostring(o ~= nil))
  S.card = o
  -- SCED's playmat sees it land (onCollisionEnter), registers the investigator and reloads its texture
  Wait.time(function() crumb("1 s after the spawn") end, 1)
  Wait.time(function() crumb("2 s after the spawn") end, 2)
  Wait.time(function()
    local mat = sced("White", "Playermat")
    local okd, md = pcall(function() return mat and mat.call("getActiveInvestigatorData") end)
    check("SCED's White mat registers Elias", okd and type(md) == "table" and md.id == "sthrelias",
      okd and type(md) == "table" and tostring(md.id) or tostring(md))
    go()
  end, 4)
end)

step("his minicard on the mat", function(go)
  local mini = S.minis and entryById(S.minis, "sthrelias-m")
  local mat = sced("White", "Playermat")
  if mini and mat then
    local m = copy(mini)
    m.GUID = nil
    crumb("spawning the minicard")
    S.mini = spawnObjectData({ data = m, position = above(zone(mat, { -0.911, 0, -0.625 })), rotation = { 0, mat.getRotation().y, 0 } })
    crumb("minicard spawnObjectData returned " .. tostring(S.mini ~= nil))
  end
  Wait.time(function() check("the minicard spawns", alive(S.mini)) ; go() end, 2)
end)

step("a starter deck from SCED's player cards", function(go)
  local bag = sced("Mythos", "AllCardsBag")
  local ready = bag and bag.call("isIndexReady")
  crumb("SCED's player cards indexed: " .. tostring(ready))
  local cards = {}
  for _, id in ipairs({ "01020", "01021", "01022", "01023", "01024", "01025", "01086", "01087" }) do
    local r = bag and bag.call("getCardById", { id = id })
    if type(r) == "table" and r.data then
      local c = copy(r.data)
      c.GUID = nil
      cards[#cards + 1] = c
    end
  end
  crumb(#cards .. " official cards copied")
  local mat = sced("White", "Playermat")
  if #cards > 1 and mat then
    local first = cards[1]
    local deck = { Name = "Deck", ContainedObjects = {}, DeckIDs = {}, CustomDeck = {},
      Transform = { scaleX = (first.Transform or {}).scaleX or 1, scaleY = 1, scaleZ = (first.Transform or {}).scaleZ or 1 } }
    for _, c in ipairs(cards) do
      for k, v in pairs(c.CustomDeck or {}) do deck.CustomDeck[k] = v end
      deck.ContainedObjects[#deck.ContainedObjects + 1] = c
      deck.DeckIDs[#deck.DeckIDs + 1] = c.CardID
    end
    crumb("spawning the deck")
    S.deck = spawnObjectData({ data = deck, position = above(zone(mat, { -1.82, 0, 0 })), rotation = { 0, mat.getRotation().y, 180 } })
    crumb("deck spawnObjectData returned " .. tostring(S.deck ~= nil))
  end
  Wait.time(function() check("the starter deck spawns", alive(S.deck)) ; go() end, 2)
end)

step("clear the probe's own cards", function(go)
  for _, o in ipairs({ S.card, S.mini, S.deck }) do if alive(o) then o.destruct() end end
  Wait.time(go, 2)
end)

step("the Control's own Seat investigators", function(go)
  pcall(function() S.ctl.call("shApiTrace", { on = true }) end)
  pcall(function() S.ctl.call("shApiNewCampaign") end)
  crumb("calling Seat investigators")
  local ok, r = pcall(function() return S.ctl.call("shApiSeat", { ids = { "sthrelias", "sthrcass" } }) end)
  crumb("Seat returned: " .. tostring(ok) .. " " .. tostring(type(r) == "table" and r.seated or r))
  Wait.time(function() crumb("Seat + 2 s") end, 2)
  Wait.time(function()
    local n = 0
    for _, i in ipairs(S.ctl.call("shApiInvestigators") or {}) do if i.matColor then n = n + 1 end end
    check("Seat investigators seats both", n == 2, n .. " seated")
    go()
  end, 8)
end)

step("clean up", function(go)
  pcall(function() S.ctl.call("shApiTrace", { on = false }) end)
  local gone = {}
  local function drop(o)
    if alive(o) and not gone[o] then gone[o] = true ; pcall(function() o.destruct() end) end
  end
  for _, o in ipairs(getObjects()) do if alive(o) and not before[o.getGUID()] then drop(o) end end
  for _, o in ipairs(getObjectsWithTag(TAG)) do drop(o) end
  Wait.time(go, 2)
end)

nextStep()
