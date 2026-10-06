-- THE STILL HOUR — scenario box: a replayable SCED-style memory bag.
--
-- SCED's MemoryBag (src/tts/memory_bag.lua) takes its contents OUT on Place and
-- only gets back what still has its original GUID on Recall. A Still Hour box is
-- laid out again every loop, after its decks were drawn, shuffled and
-- discarded, so that cannot work. This box therefore never empties:
--   * Place makes a native copy of the whole box (what copy and paste does in
--     Tabletop Simulator: self.clone), then does exactly what SCED's own Place
--     does to that copy: takeObject{guid, position, rotation, smooth = false}
--     for every remembered object (LuaScriptState.ml, the same
--     {guid: {pos, rot, lock}} layout SCED uses), then setLock, and throws the
--     empty copy away. Nothing is rebuilt from data in Lua: no spawnObjectData,
--     no JSON round trip, no new GUIDs. The objects keep the GUIDs they have in
--     the box, as the official boxes' objects do.
--   * every object in the box (and every card inside its decks) carries the
--     tags "StillHourLoop" and "StillHourBox_<box id>" from the build, so a
--     drawn card is still recognised; Place also tags what it takes out.
--   * Recall removes what this box placed (and any card that came out of it)
--     from the table; the Control token's Clear Board removes every box's
--     objects at once (shClearBoard).
-- The button layout matches SCED's MemoryBag so the book looks and works like
-- an official scenario box.

LOOP_TAG = "StillHourLoop"

-- Frames between two takeObject calls. SCED does them all in one frame; a few
-- frames apart changes nothing about the mechanism, but the Lua log then shows
-- the last step reached if Tabletop Simulator ever stops.
local STEP_FRAMES = 6

local memoryList = {}

local function boxId()
  local ok, gm = pcall(JSON.decode, self.getGMNotes() or "")
  if ok and type(gm) == "table" and gm.id then return tostring(gm.id) end
  return tostring(self.getGUID())
end

local function boxTag()
  return "StillHourBox_" .. boxId()
end

function updateSave()
  self.script_state = JSON.encode({ ml = memoryList })
end

function onLoad(savedData)
  if savedData and savedData ~= "" then
    local ok, loaded = pcall(JSON.decode, savedData)
    if ok and type(loaded) == "table" then memoryList = loaded.ml or {} end
  end
  memoryList = memoryList or {}
  Wait.condition(function()
    Wait.frames(function() createButtons() end, 5)
  end, function() return not self.loading_custom end)
end

function createButtons()
  self.clearButtons()
  if not next(memoryList) then return end
  local scale  = self.getScale()
  local bounds = self.getBoundsNormalized()
  local bx = math.max(bounds.size.x / 5, 1.5) / scale.x
  local by = -(bounds.size.y / 2 + bounds.offset.y) / scale.y + 0.5
  local bz = (bounds.size.z / 2 + 1.15 - 0.15) / scale.z
  local bscale = { 1 / scale.x, 1, 1 / scale.z }
  self.createButton({ label = "Place", click_function = "buttonClick_place", function_owner = self,
    position = { bx, by, bz }, rotation = { 0, 0, 0 }, height = 850, width = 2000,
    font_size = 350, scale = bscale, color = { 0, 0, 0 }, font_color = { 1, 1, 1 },
    tooltip = "Lay this box out for the loop (a fresh copy every time)" })
  self.createButton({ label = "Recall", click_function = "buttonClick_recall", function_owner = self,
    position = { -bx, by, bz }, rotation = { 0, 0, 0 }, height = 850, width = 2000,
    font_size = 350, scale = bscale, color = { 0, 0, 0 }, font_color = { 1, 1, 1 },
    tooltip = "Remove this box's cards from the table" })
end

--- Written to the Lua log (Player.log) before the step it names runs, so a
-- crash in Tabletop Simulator leaves the failing step behind.
local function trace(msg)
  log("StillHour box '" .. tostring(self.getName()) .. "': " .. msg)
end

local function say(msg)
  broadcastToAll(msg, { 0.95, 0.85, 0.6 })
end

local function alive(o)
  return o ~= nil and not o.isDestroyed()
end

local placing = false

--- Lay the box out. Returns how many objects will be placed (they land over
-- the next second or so), or 0 when nothing was started.
function buttonClick_place()
  if placing then
    say(self.getName() .. ": still placing, wait a moment.")
    return 0
  end
  local tag = boxTag()
  trace("Place pressed")

  -- what this box can place: the remembered objects that are really inside it,
  -- highest position first so that taking one never moves the position of a
  -- later one (the index fallback below relies on it)
  -- (kind and GUID only, never a card's title: a first-time player reads the chat, and
  -- the Lua log gets pasted into messages; the GUID says which object it was)
  local inside = {}
  for _, e in ipairs(self.getObjects()) do
    inside[e.guid] = { index = e.index, kind = e.name or "object" }
  end
  local guids = {}
  for guid in pairs(memoryList) do
    if inside[guid] ~= nil then guids[#guids + 1] = guid end
  end
  table.sort(guids, function(a, b)
    local ia, ib = inside[a].index or 0, inside[b].index or 0
    if ia ~= ib then return ia > ib end
    return a < b
  end)
  trace("read " .. #guids .. " object(s) to place")
  if #guids == 0 then
    say(self.getName() .. ": nothing to place.")
    return 0
  end

  -- a second press must not lay a second copy on top of the first
  local already = {}
  local okTag, tagged = pcall(getObjectsWithTag, tag)
  for _, o in ipairs(okTag and tagged or {}) do
    if o ~= self and alive(o) then already[#already + 1] = o end
  end
  if #already > 0 then
    trace("already placed: " .. #already .. " object(s) carry " .. tag)
    say(self.getName() .. " is already laid out. Press Recall first (or Clear Board on the Control token).")
    return 0
  end

  placing = true
  local placed = 0

  local function done(copy, why)
    placing = false
    if alive(copy) then copy.destruct() end
    trace(why .. "; placed " .. placed)
    say(self.getName() .. ": " .. placed .. " object(s) placed.")
    if placed == 0 then return end
    -- once the cards have landed, let the control token apply the log's
    -- Knowledge to them (location sides, sealed locations, the Appointed),
    -- one announced step at a time
    Wait.time(function()
      local ok, objs = pcall(getObjectsWithTag, "StillHour")
      for _, o in ipairs(ok and objs or {}) do
        if tostring(o.getName()):find("Control", 1, true) then
          trace("starting the board sync")
          pcall(function()
            if not o.call("shApiSyncBoardStaged") then o.call("shApiSyncBoard") end
          end)
        end
      end
    end, 2)
  end

  -- SCED's own step: take the object out of the bag at its remembered spot.
  -- By GUID, as SCED does; if the working copy does not know that GUID (a
  -- copy is free to renumber what it holds) by the object's position in the
  -- bag instead, which is why the positions are taken from the highest down.
  local function take(copy, i)
    if not alive(copy) then return done(nil, "the working copy disappeared") end
    local guid = guids[i]
    if not guid then return done(copy, "all objects taken") end
    local entry = memoryList[guid]
    local what = tostring(inside[guid].kind) .. " " .. guid
    trace(string.format("taking %d/%d %s", i, #guids, what))
    broadcastToAll(string.format("Placing %d/%d", i, #guids), { 0.7, 0.7, 0.7 })
    local ok, item = pcall(copy.takeObject, {
      guid = guid, position = entry.pos, rotation = entry.rot, smooth = false })
    if not (ok and item) and inside[guid].index ~= nil then
      trace("no object " .. guid .. " in the copy; taking position " .. tostring(inside[guid].index))
      ok, item = pcall(copy.takeObject, {
        index = inside[guid].index, position = entry.pos, rotation = entry.rot, smooth = false })
    end
    if ok and item then
      item.setLock(entry.lock and true or false)
      for _, t in ipairs({ LOOP_TAG, tag }) do
        if not item.hasTag(t) then item.addTag(t) end
      end
      placed = placed + 1
    else
      trace("take failed for " .. what .. ": " .. tostring(ok and "nothing returned" or item))
    end
    Wait.frames(function() take(copy, i + 1) end, STEP_FRAMES)
  end

  -- the native copy SCED's Place will run on, parked above the box and frozen
  local pos = self.getPosition()
  local okClone, copy = pcall(self.clone, { position = { pos.x, pos.y + 6, pos.z } })
  if not okClone or not alive(copy) then
    placing = false
    trace("could not copy the box: " .. tostring(copy))
    say(self.getName() .. ": could not prepare the objects (see the log).")
    return 0
  end
  copy.setLock(true)
  copy.setName(self.getName() .. " (placing)")
  trace("working copy made; waiting for it to be ready")
  Wait.condition(function() take(copy, 1) end,
    function() return alive(copy) and not copy.spawning and not copy.loading_custom end,
    10,
    function() done(copy, "the working copy was not ready after 10 s") end)
  return #guids
end

function buttonClick_recall()
  local n = clearTagged(boxTag())
  say(self.getName() .. ": " .. n .. " object(s) removed from the table.")
  return n
end

--- Destroy every loose object and deck carrying `tag` (decks: when every card
-- in them carries it; otherwise only those cards are taken out and removed).
function clearTagged(tag)
  local count = 0
  for _, obj in ipairs(getObjects()) do
    if obj ~= self and not obj.isDestroyed() then
      if obj.hasTag(tag) and obj.type ~= "Deck" then
        obj.destruct()
        count = count + 1
      elseif obj.type == "Deck" then
        local contents = obj.getObjects() or {}
        local mine, others = {}, 0
        for _, e in ipairs(contents) do
          local tagged = false
          for _, t in ipairs(e.tags or {}) do if t == tag then tagged = true end end
          if tagged then mine[#mine + 1] = e.guid else others = others + 1 end
        end
        if #mine > 0 and others == 0 then
          obj.destruct()
          count = count + #mine
        elseif #mine > 0 then
          local pos = obj.getPosition()
          for _, g in ipairs(mine) do
            local ok, card = pcall(obj.takeObject, { guid = g, position = { pos.x, pos.y + 3, pos.z }, smooth = false })
            if ok and card then card.destruct() ; count = count + 1 end
          end
        end
      end
    end
  end
  return count
end
