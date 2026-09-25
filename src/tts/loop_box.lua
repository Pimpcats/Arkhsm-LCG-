-- THE STILL HOUR — scenario box: a replayable SCED-style memory bag.
--
-- SCED's MemoryBag (src/tts/memory_bag.lua) takes its contents OUT on Place and
-- only gets back what still has its original GUID on Recall. A Still Hour box is
-- laid out again every loop, after its decks were drawn, shuffled and
-- discarded, so that cannot work. This box never empties instead:
--   * Place spawns a fresh copy of every contained object at its remembered
--     spot (LuaScriptState.ml, the same {guid: {pos, rot, lock}} layout SCED
--     uses), with new GUIDs, tagged "StillHourLoop" (every card inside a
--     deck carries the tag too, so drawn cards keep it).
--   * Recall removes the copies this box placed (and any card that came out
--     of them) from the table; the control token's Reset Loop removes every
--     box's copies at once (shClearLoopBoard).
-- The button layout matches SCED's MemoryBag so the book looks and works like
-- an official scenario box.

LOOP_TAG = "StillHourLoop"

local memoryList = {}

local function boxTag()
  return "StillHourBox:" .. tostring(self.getGUID())
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

local HEX = "0123456789abcdef"
local function newGuid()
  local t = {}
  for i = 1, 6 do
    local n = math.random(1, 16)
    t[i] = HEX:sub(n, n)
  end
  return table.concat(t)
end

--- Fresh GUIDs and the loop tags on an object and everything inside it.
local function prepare(data, tags)
  data.GUID = newGuid()
  local have = {}
  data.Tags = data.Tags or {}
  for _, t in ipairs(data.Tags) do have[t] = true end
  for _, t in ipairs(tags) do
    if not have[t] then table.insert(data.Tags, t) end
  end
  for _, inner in ipairs(data.ContainedObjects or {}) do prepare(inner, tags) end
  for _, state in pairs(data.States or {}) do prepare(state, tags) end
  return data
end

function buttonClick_place()
  local placed = 0
  local tags = { LOOP_TAG, boxTag() }
  for _, od in ipairs(self.getData().ContainedObjects or {}) do
    local entry = memoryList[od.GUID]
    if entry then
      local data = prepare(JSON.decode(JSON.encode(od)), tags)
      data.Locked = entry.lock and true or false
      local obj = spawnObjectData({ data = data, position = entry.pos, rotation = entry.rot })
      if obj then placed = placed + 1 end
    end
  end
  if placed > 0 then
    broadcastToAll(self.getName() .. ": " .. placed .. " object(s) placed.", { 0.95, 0.85, 0.6 })
    -- once the cards have landed, let the control token apply the log's
    -- Knowledge to them (location sides, sealed locations, the Appointed)
    Wait.time(function()
      local ok, list = pcall(getObjectsWithTag, "StillHour")
      for _, o in ipairs(ok and list or {}) do
        if tostring(o.getName()):find("Control", 1, true) then
          pcall(function() o.call("shApiSyncBoard") end)
        end
      end
    end, 2)
  else
    broadcastToAll(self.getName() .. ": nothing to place.", { 0.95, 0.85, 0.6 })
  end
  return placed
end

function buttonClick_recall()
  local n = clearTagged(boxTag())
  broadcastToAll(self.getName() .. ": " .. n .. " object(s) removed from the table.", { 0.95, 0.85, 0.6 })
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
