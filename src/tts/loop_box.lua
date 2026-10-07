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
--     the box, as the official boxes' objects do. SCED's Token Spawn Tracker
--     remembers cards by GUID, so before anything is taken Place makes it forget
--     the GUIDs it is about to lay out again: a location spawns its clues in
--     every loop, not only in the first.
--   * every object in the box (and every card inside its decks) carries the
--     tags "StillHourLoop" and "StillHourBox_<box id>" from the build, so a
--     drawn card is still recognised; Place also tags what it takes out.
--   * Recall removes what this box placed (and any card that came out of it, and
--     the tokens resting on them) from the table; the Control token's Clear
--     Board does the same for every box at once (shClearBoard). Either one first
--     stops a Place that is still running (cancelPlace), so no half layout
--     arrives afterwards and the next Place is not refused.
--   * a second Place is refused while this box's objects are on the table, and
--     while objects of another box (or of an older build's box: an old Place
--     tagged them StillHourBox:<guid>) still lie where this box lays something
--     out: they would be dropped on and merged into what it lays there.
-- The button layout matches SCED's MemoryBag so the book looks and works like
-- an official scenario box.

LOOP_TAG = "StillHourLoop"

-- Frames between two takeObject calls. SCED does them all in one frame; a few
-- frames apart changes nothing about the mechanism, but the Lua log then shows
-- the last step reached if Tabletop Simulator ever stops.
local STEP_FRAMES = 6

-- SCED's GUID reference handler: the way to its Token Spawn Tracker
-- (src/StillHour/SCED.ttslua makes the same lookup).
local SCED_HANDLER_GUID = "123456"

-- What the working copy's name ends with while a Place takes objects out of it.
local WORKING_SUFFIX = " (placing)"

-- An object of another box closer than this to a spot this box lays something
-- on would be merged with it. Boxes that share a loop's board never use the
-- same spots (tests/test_table_presence.py), and the Appointed, which the
-- Control token stands beside a location, is farther off.
local SPOT_REACH = 0.75

local memoryList = {}
local placing = false      -- a Place of this box is running (not saved: a load ends it)
local run = 0              -- which Place is current; the callbacks of a stopped one see another number
local workingCopy = nil    -- the copy a running Place takes the objects out of

local function boxId()
  local ok, gm = pcall(JSON.decode, self.getGMNotes() or "")
  if ok and type(gm) == "table" and gm.id then return tostring(gm.id) end
  return tostring(self.getGUID())
end

local function boxTag()
  return "StillHourBox_" .. boxId()
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

--- Run fn; an error is written to the log (what failed) and never raised.
local function try(what, fn)
  local ok, err = pcall(fn)
  if not ok then trace(what .. " failed: " .. tostring(err)) end
  return ok
end

local function isWorkingCopy()
  local name = tostring(self.getName() or "")
  return name:sub(-#WORKING_SUFFIX) == WORKING_SUFFIX
end

function updateSave()
  self.script_state = JSON.encode({ ml = memoryList })
end

--- True while a Place of this box is laying it out. The working copies it makes
-- ask their box this (a copy is a box too, and says false).
function isPlacing()
  return placing
end

--- Another box on the table, made from the same book, that is laying out now.
local function madeFromAPlacingBox()
  local mine = boxId()
  for _, o in ipairs(getObjects()) do
    if o ~= self and not o.isDestroyed() and tostring(o.getGMNotes()):find("ScenarioBox", 1, true) then
      local ok, gm = pcall(JSON.decode, o.getGMNotes())
      if ok and type(gm) == "table" and tostring(gm.id) == mine then
        local okCall, busy = pcall(function() return o.call("isPlacing") end)
        if okCall and busy == true then return true end
      end
    end
  end
  return false
end

--- A working copy still on the table when a game is loaded was left there by a
-- save taken while a Place was running. It holds the same objects, so it would
-- be a second box to lay the same things out from: throw it away, unless the
-- box it was copied from is, right now, still laying out (the copy of a Place
-- that is under way loads too, and is needed).
local function discardIfStray()
  Wait.frames(function()
    pcall(function()
      if self.isDestroyed() or madeFromAPlacingBox() then return end
      trace("a working copy was left on the table by a save taken during a Place: destroyed")
      self.destruct()
    end)
  end, 30)
end

function onLoad(savedData)
  if isWorkingCopy() then return discardIfStray() end
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

--- SCED's Token Spawn Tracker (src/tokens/TokenSpawnTracker.ttslua) remembers by
-- GUID which cards already had their clues spawned, and forgets one only when
-- it enters a hand or a discard pile (or from its own menu). These objects keep
-- their GUIDs from loop to loop, so without this a location laid out again would
-- be taken for one that already spawned. resetTokensSpawned takes a GUID string.
-- Silent when SCED is not on the table. Returns how many GUIDs it made forget.
local function forgetSpawns(guids)
  local ok, n = pcall(function()
    local handler = getObjectFromGUID(SCED_HANDLER_GUID)
    if handler == nil then return 0 end
    local tracker = handler.call("getObjectByOwnerAndType", { owner = "Mythos", type = "TokenSpawnTracker" })
    if tracker == nil then return 0 end
    local count = 0
    for _, guid in ipairs(guids) do
      if pcall(function() tracker.call("resetTokensSpawned", guid) end) then count = count + 1 end
    end
    return count
  end)
  return ok and n or 0
end

--- Does this object belong to a scenario box other than this one? What a box
-- lays out carries the loop tag and the box's own tag; the previous build's
-- boxes tagged it StillHourBox:<guid> instead, a tag this build cannot know.
local function ofAnotherBox(o, mine)
  local ok, tags = pcall(function() return o.getTags() end)
  local belongs = false
  for _, t in ipairs(ok and tags or {}) do
    if t == mine then return false end
    if t == LOOP_TAG or t:sub(1, 13) == "StillHourBox_" or t:sub(1, 13) == "StillHourBox:" then belongs = true end
  end
  return belongs
end

--- Objects of other boxes lying where this box would lay something out (the
-- Prologue's cards on the mythos mat when the next box is Placed, an older
-- build's leftovers). Boxes that share a loop's board never share a spot, so
-- for them this is 0.
--- The id of the box an object of the loop belongs to (its StillHourBox_<id> tag), or nil.
local function boxIdOf(o)
  local ok, tags = pcall(function() return o.getTags() end)
  for _, t in ipairs(ok and tags or {}) do
    if t:sub(1, 13) == "StillHourBox_" then return t:sub(14) end
  end
  return nil
end

local function foreignOnMySpots(tag, guids)
  local n = 0
  for _, o in ipairs(getObjects()) do
    if o ~= self and alive(o) and ofAnotherBox(o, tag) then
      local p = o.getPosition()
      local owner = boxIdOf(o)
      for _, guid in ipairs(guids) do
        local e = memoryList[guid]
        local s = e.pos
        -- an object with a fallback spot (a district's act deck) never clashes: it uses the fallback
        -- when another box's deck holds its first choice (spotFor); one that makes the other box's
        -- object yield (the finale's act) does not clash with the boxes it names (yieldTo)
        local yields = e.yield ~= nil and owner ~= nil and e.yield[owner] ~= nil
        if not e.alt and not yields and math.abs(p.x - s.x) < SPOT_REACH and math.abs(p.z - s.z) < SPOT_REACH then
          n = n + 1 ; break
        end
      end
    end
  end
  return n
end

--- An object that takes its spot from another box's (the finale's act takes the Act slot from the
-- Square's or a district's act deck): the other box's object moves to the place that box gave it.
local function yieldTo(tag, entry)
  if not entry.yield then return end
  local s = entry.pos
  for _, o in ipairs(getObjects()) do
    if o ~= self and alive(o) and ofAnotherBox(o, tag) then
      local p = o.getPosition()
      local to = entry.yield[boxIdOf(o) or ""]
      if to and math.abs(p.x - s.x) < SPOT_REACH and math.abs(p.z - s.z) < SPOT_REACH then
        trace("moving an object of " .. tostring(boxIdOf(o)) .. " off the spot")
        pcall(function()
          o.setPosition({ to.pos.x, to.pos.y + 0.5, to.pos.z })
          o.setRotation({ to.rot.x, to.rot.y, o.getRotation().z })
        end)
      end
    end
  end
end

--- Where an object of this box goes: its first spot, or its fallback (`alt`) when another box's
-- object already lies on the first. A district's act deck takes the mythos mat's labelled Act slot
-- when it is free and its own column of the district row when it is not.
local function spotFor(tag, entry)
  local alt = entry.alt
  if not alt then return entry end
  local s = entry.pos
  for _, o in ipairs(getObjects()) do
    if o ~= self and alive(o) and ofAnotherBox(o, tag) then
      local p = o.getPosition()
      if math.abs(p.x - s.x) < SPOT_REACH and math.abs(p.z - s.z) < SPOT_REACH then
        return { pos = alt.pos, rot = alt.rot, lock = entry.lock, alt = nil }
      end
    end
  end
  return entry
end

--- Clue and doom tokens that stand near where a card was, whether or not they rest on it. SCED's
-- token spawner gives every clue and doom token the memo "clueDoom". A token can roll off a card's
-- edge, and SCED spawns a revealed location's clues over a second or two, so a Recall or Clear Board
-- that came a moment after a Place could leave clues standing on an empty map slot.
-- `places`: { { x, z, hx, hz }, ... } (card centres and half sizes, in world units).
local function memoOf(o)
  local ok, m = pcall(function() return o.memo end)
  return ok and m or nil
end

local function clueTokensNear(places, margin)
  local found = {}
  if #places == 0 then return found end
  for _, o in ipairs(getObjects()) do
    if not o.isDestroyed() and memoOf(o) == "clueDoom" and not o.getLock() then
      local p = o.getPosition()
      for _, pl in ipairs(places) do
        if math.abs(p.x - pl.x) <= pl.hx + margin and math.abs(p.z - pl.z) <= pl.hz + margin then
          found[#found + 1] = o
          break
        end
      end
    end
  end
  return found
end

local function placeOf(o)
  local b = o.getBounds()
  return { x = b.center.x, z = b.center.z, hx = b.size.x / 2, hz = b.size.z / 2 }
end

--- Take the clue and doom tokens near `places` now and again shortly after (tokens SCED is still
-- spawning). Returns how many went at once.
local function sweepClues(places, once)
  local n = 0
  for _, t in ipairs(clueTokensNear(places, 1.2)) do
    if not t.isDestroyed() then t.destruct() ; n = n + 1 end
  end
  if #places > 0 and not once then
    for _, delay in ipairs({ 1.5, 5, 12 }) do
      Wait.time(function()
        for _, t in ipairs(clueTokensNear(places, 1.2)) do
          if not t.isDestroyed() then t.destruct() end
        end
      end, delay)
    end
  end
  return n
end

--- Stop a Place that is still running: nothing more comes out of the box, and
-- the working copy goes. Recall and the Control token's Clear Board call this
-- first. Returns true when a Place was running.
function cancelPlace()
  if not placing then return false end
  run = run + 1
  placing = false
  if alive(workingCopy) then workingCopy.destruct() end
  workingCopy = nil
  trace("Place stopped")
  return true
end

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
  -- (the GUID only, never a card's title: a first-time player reads the chat, and the
  -- Lua log gets pasted into messages. An entry's `name` is the object's title, as
  -- SCED's own scripts rely on, so it is not read here at all)
  local inside = {}
  for _, e in ipairs(self.getObjects()) do
    inside[e.guid] = { index = e.index, tags = e.tags }
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

  -- cards of a box laid out earlier (another one, or an older build's) still
  -- where this one lays something out would be merged with it
  local clash = foreignOnMySpots(tag, guids)
  if clash > 0 then
    trace("not placed: " .. clash .. " object(s) of another box lie where this box lays out")
    say(self.getName() .. ": cards from a box laid out earlier are still on the table where this one lays out."
      .. " Click Clear Board on the Control token first.")
    return 0
  end

  trace("SCED's spawn tracker forgets " .. forgetSpawns(guids) .. " of " .. #guids .. " GUID(s)")

  -- clue tokens left standing where this box lays its locations out (from a box that went before, or
  -- a build that did not take them with their cards) would be taken for the new locations' own
  local spots = {}
  for _, guid in ipairs(guids) do
    local isLocation = false
    for _, t in ipairs(inside[guid].tags or {}) do if t == "Location" then isLocation = true end end
    local pos = memoryList[guid].pos
    if isLocation and pos then spots[#spots + 1] = { x = pos.x, z = pos.z, hx = 1.55, hz = 1.1 } end
  end
  local leftovers = sweepClues(spots, true)
  if leftovers > 0 then trace("took " .. leftovers .. " clue/doom token(s) left standing on the location spots") end

  placing = true
  run = run + 1
  local myRun = run
  local placed = 0
  local took = {}      -- the GUIDs of what came out, for the Control's board sync

  local function done(copy, why)
    if myRun ~= run then                       -- stopped meanwhile: only the copy is left to throw away
      if alive(copy) then copy.destruct() end
      return
    end
    placing = false
    workingCopy = nil
    if alive(copy) then copy.destruct() end
    trace(why .. "; placed " .. placed)
    say(self.getName() .. ": " .. placed .. " object(s) placed.")
    if placed == 0 then return end
    -- once the cards have landed, let the control token apply the log's
    -- Knowledge to them (location sides, sealed locations, the Appointed),
    -- one announced step at a time; it is told which box this was and which
    -- GUIDs came out (what it remembered of them belongs to older objects)
    Wait.time(function()
      local ok, objs = pcall(getObjectsWithTag, "StillHour")
      for _, o in ipairs(ok and objs or {}) do
        if tostring(o.getName()):find("Control", 1, true) then
          trace("starting the board sync")
          pcall(function()
            local info = { box = boxId(), name = self.getName(), guids = took }
            if not o.call("shApiSyncBoardStaged", info) then o.call("shApiSyncBoard") end
          end)
        end
      end
    end, 2)
  end

  -- SCED's own step: take the object out of the bag at its remembered spot.
  -- By GUID, as SCED does; if the working copy does not know that GUID (a
  -- copy is free to renumber what it holds) by the object's position in the
  -- bag instead, which is why the positions are taken from the highest down.
  local function takeOne(copy, i)
    local guid = guids[i]
    yieldTo(tag, memoryList[guid])
    local entry = spotFor(tag, memoryList[guid])
    local what = "object " .. guid
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
      -- what is out is counted and tagged first, so Recall and Clear Board find it
      placed = placed + 1
      try("tagging " .. what, function()
        for _, t in ipairs({ LOOP_TAG, tag }) do
          if not item.hasTag(t) then item.addTag(t) end
        end
      end)
      try("locking " .. what, function() item.setLock(entry.lock and true or false) end)
      try("reading the GUID of " .. what, function()
        took[#took + 1] = tostring(item.getGUID())
        trace(string.format("took %d/%d %s as %s", i, #guids, what, took[#took]))
      end)
    else
      trace("take failed for " .. what .. ": " .. tostring(ok and "nothing returned" or item))
    end
  end

  -- guarded as a whole: an error in one step is traced and the chain goes on with
  -- the next object, so it always reaches done() and the box is never left "placing"
  local function take(copy, i)
    if myRun ~= run then return end            -- stopped: nothing more comes out
    if not alive(copy) then return done(nil, "the working copy disappeared") end
    if not guids[i] then return done(copy, "all objects taken") end
    try(string.format("step %d/%d", i, #guids), function() takeOne(copy, i) end)
    Wait.frames(function() take(copy, i + 1) end, STEP_FRAMES)
  end

  -- the native copy SCED's Place will run on, parked above the box and frozen
  local okClone, copy = pcall(function()
    local pos = self.getPosition()
    return self.clone({ position = { pos.x, pos.y + 6, pos.z } })
  end)
  if not okClone or not alive(copy) then
    placing = false
    trace("could not copy the box: " .. tostring(copy))
    say(self.getName() .. ": could not prepare the objects (see the log).")
    return 0
  end
  workingCopy = copy
  local started = try("starting the Place", function()
    copy.setLock(true)
    copy.setName(self.getName() .. WORKING_SUFFIX)
    trace("working copy made; waiting for it to be ready")
    Wait.condition(function() take(copy, 1) end,
      function() return alive(copy) and not copy.spawning and not copy.loading_custom end,
      10,
      function() done(copy, "the working copy was not ready after 10 s") end)
  end)
  if not started then
    done(copy, "the Place could not start")
    return 0
  end
  return #guids
end

function buttonClick_recall()
  local stopped = cancelPlace()
  local n, tokens = clearTagged(boxTag())
  local what = n .. " object(s)" .. (tokens > 0 and (" and " .. tokens .. " token(s)") or "")
  say(self.getName() .. ": " .. (stopped and "the Place in progress was stopped; " or "") .. what
    .. " removed from the table.")
  return n
end

--- Tokens resting on a card (clues, doom, damage): small, unlocked, not cards,
-- centred on the card and above it. SCED's own table pieces that merely touch
-- the card's edge or lie under it (the lead-investigator marker, the tour
-- starter) are never taken, nor anything SCED marks CleanUpHelper_ignore.
-- The same rule as the Control token's Clear Board (control.lua tokensOn).
local function tokensOn(card)
  local found = {}
  if type(Physics) ~= "table" or type(Physics.cast) ~= "function" then return found end
  local b = card.getBounds()
  local hx, hz = b.size.x / 2, b.size.z / 2
  local hits = Physics.cast({ origin = { b.center.x, b.center.y + 2, b.center.z },
    direction = { 0, -1, 0 }, type = 3, size = { b.size.x, 1, b.size.z }, max_distance = 3 }) or {}
  for _, h in ipairs(hits) do
    local o = h.hit_object
    if o and o ~= card and not o.getLock() and (o.type == "Tile" or o.type == "Generic"
        or o.type == "Chip") and not o.hasTag("CleanUpHelper_ignore") then
      local p = o.getPosition()
      if math.abs(p.x - b.center.x) <= hx and math.abs(p.z - b.center.z) <= hz and p.y >= b.center.y then
        found[#found + 1] = o
      end
    end
  end
  return found
end

--- Destroy every loose object and deck carrying `tag` (decks: when every card
-- in them carries it; otherwise only those cards are taken out and removed),
-- and the tokens resting on each card or deck removed. Returns the number of
-- objects and of tokens removed.
function clearTagged(tag)
  local count, tokens = 0, 0
  local places = {}
  local function dropTokens(card)
    for _, t in ipairs(tokensOn(card)) do
      if not t.isDestroyed() then t.destruct() ; tokens = tokens + 1 end
    end
    local ok, pl = pcall(placeOf, card)
    if ok then places[#places + 1] = pl end
  end
  for _, obj in ipairs(getObjects()) do
    if obj ~= self and not obj.isDestroyed() then
      if obj.hasTag(tag) and obj.type ~= "Deck" then
        if obj.type == "Card" then dropTokens(obj) end
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
          dropTokens(obj)
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
  tokens = tokens + sweepClues(places)
  return count, tokens
end
