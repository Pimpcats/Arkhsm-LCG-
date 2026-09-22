-- THE STILL HOUR — interactive campaign log (SCED CampaignLog token).
--
-- The token is a Custom_Token with one State per log page (GMNotes type
-- CampaignLog, Tags [CampaignLog]; docs/art_reference/sced_objects/
-- campaign_log_token.json). pipeline/campaign_log.py prepends, per page:
--
--   PAGE, PAGE_COUNT       this state's page number / how many pages
--   FIELDS                 { k = key, t = "cb"|"ct"|"tx"|"dv", u, v, w, h, ... }
--                          u/v = field centre, w/h = size, all as fractions of
--                          the page image (the same layout that drew the page)
--   INVESTIGATORS          { {id, name}, ... }   (CampaignState years keys)
--   FACT_LAYER             factId -> "prologue"|"surface"|"deep"|"assembled"
--
-- Field kinds, like SCED's CampaignLogLibrary: "cb" checkbox (click toggles a
-- handwritten cross; "g" = exclusive group), "ct" counter (left-click +1,
-- right-click -1), "tx" write-in text, "dv" derived read-out (Dissonance scar,
-- facts held, bracket from Years).
--
-- Placement: buttons/inputs sit at local (x, z) = ((u - 0.5) * 2hx,
-- (v - 0.5) * 2hz), where hx/hz are the token's local half-extents read from
-- its real bounds once the image has loaded — the orientation SCED's own logs
-- use (left = -x, top = -z in button space). Sizes use TTS's ~500 button units
-- per local unit.
--
-- State: every field value lives in `values` (key -> value), written to
-- script_state on each change and returned by onSave(), so it survives
-- save/load, SCED's campaign export (which stores the log's getData()), and
-- switching pages (each State keeps its own script state).
--
-- Integration: "Sync from campaign" (context menu, or call
-- syncFromCampaignState) reads THE STILL HOUR's campaign-state token (the
-- control object whose saved state carries loopsCompleted / knowledge / years)
-- and fills this page from it: loops, banked Memory, Act, Years and drift,
-- the Knowledge Track, the Named, threads. It only ever reads that token.

local UNITS_PER_LOCAL = 500
local UI_SCALE = 0.1
local Y = 0.11
local MARKS = { "✗", "✘" }
local INK = { 0.12, 0.09, 0.07, 1 }
local DIM = { 0.3, 0.25, 0.2, 1 }

values = values or {}
local extent = nil
local buttonIndex, inputIndex = {}, {}
local byKey = {}
for _, f in ipairs(FIELDS) do byKey[f.k] = f end

------------------------------------------------------------------ state --

local function defaults()
  local v = {}
  if byKey["investigators"] then v["investigators"] = 3 end
  return v
end

local function encodeState()
  return JSON.encode({ page = PAGE, values = values })
end

function updateSave()
  self.script_state = encodeState()
end

function onSave()
  return encodeState()
end

local function num(key)
  return tonumber(values[key]) or 0
end

---------------------------------------------------------------- geometry --

local function computeExtent()
  local ok, b = pcall(function() return self.getBoundsNormalized() end)
  local s = self.getScale()
  local hx, hz = 0, 0
  if ok and b and b.size and s and s.x and s.x ~= 0 then
    hx = b.size.x / 2 / s.x
    hz = b.size.z / 2 / s.z
  end
  if hx <= 0 or hz <= 0 then
    hx, hz = 1, 1650 / 1275    -- image aspect fallback
  end
  extent = { hx = hx, hz = hz }
end

local function toLocal(f)
  return (f.u - 0.5) * 2 * extent.hx, (f.v - 0.5) * 2 * extent.hz
end

local function units(localSize)
  return localSize * UNITS_PER_LOCAL / UI_SCALE
end

----------------------------------------------------------------- derived --

local function countFacts(layer)
  local n = 0
  for id, l in pairs(FACT_LAYER) do
    if l == layer and values["k:" .. id] then n = n + 1 end
  end
  return n
end

local function derive(f)
  local d = f.d or ""
  if d == "scar" then
    return tostring(math.min(num("loops"), 6))
  elseif d == "surface" then
    return tostring(countFacts("surface"))
  elseif d == "deep" then
    return tostring(countFacts("deep"))
  end
  local i, lo, hi = d:match("^bracket:(%d+):(%d+):(%d+)$")
  if i then
    local named = (values["inv" .. i .. "_name"] or "") ~= ""
    local years = num("inv" .. i .. "_years")
    if (named or years > 0) and years >= tonumber(lo) and years <= tonumber(hi) then
      return MARKS[1]
    end
    return ""
  end
  return ""
end

local function markFor(idx)
  return MARKS[(idx % 2) + 1]
end

local function labelFor(f, idx)
  if f.t == "cb" then return values[f.k] and markFor(idx) or "" end
  if f.t == "ct" then return tostring(num(f.k)) end
  if f.t == "dv" then return derive(f) end
  return ""
end

local function refreshButton(key)
  local f, idx = byKey[key], buttonIndex[key]
  if f and idx then
    self.editButton({ index = idx, label = labelFor(f, idx) })
  end
end

local function refreshDerived()
  for _, f in ipairs(FIELDS) do
    if f.t == "dv" then refreshButton(f.k) end
  end
end

------------------------------------------------------------------ clicks --

function click_none() end

local function setValue(key, value)
  local f = byKey[key]
  if not f then return false end
  if f.t == "cb" then
    value = value and true or false
    if value and f.g then
      for _, o in ipairs(FIELDS) do
        if o.g == f.g and o.k ~= key and values[o.k] then
          values[o.k] = false
          refreshButton(o.k)
        end
      end
    end
  elseif f.t == "ct" then
    value = math.max(f.min or 0, math.min(f.max or 99, math.floor(tonumber(value) or 0)))
  elseif f.t == "tx" then
    value = tostring(value or "")
  else
    return false
  end
  values[key] = value
  if f.t == "tx" then
    if inputIndex[key] then self.editInput({ index = inputIndex[key], value = value }) end
  else
    refreshButton(key)
  end
  return true
end

local function clickCheckbox(key)
  setValue(key, not values[key])
  refreshDerived()
  updateSave()
end

local function clickCounter(key, alt)
  setValue(key, num(key) + (alt and -1 or 1))
  refreshDerived()
  updateSave()
end

local function typed(key, value, selected)
  if selected == false then
    values[key] = value or ""
    refreshDerived()
    updateSave()
  end
end

-------------------------------------------------------------------- build --

function buildUi()
  computeExtent()
  self.clearButtons()
  self.clearInputs()
  buttonIndex, inputIndex = {}, {}
  local nb, ni = 0, 0
  for i, f in ipairs(FIELDS) do
    local x, z = toLocal(f)
    local w = f.w * 2 * extent.hx
    local h = f.h * 2 * extent.hz
    local fname = "sthrLog_" .. i
    if f.t == "tx" then
      local rows = f.rows or 1
      local hu = units(h)
      local fs = math.max(20, math.floor((hu - 23) / rows * 0.82))
      self.setVar(fname, function(_, _, value, selected) typed(f.k, value, selected) end)
      self.createInput({
        input_function = fname, function_owner = self,
        label = "", alignment = 2,
        position = { x, Y, z }, rotation = { 0, 0, 0 },
        scale = { UI_SCALE, UI_SCALE, UI_SCALE },
        width = units(w), height = fs * rows + 23, font_size = fs,
        color = { 1, 1, 1, 0 }, font_color = INK,
        value = values[f.k] or "", tooltip = "",
      })
      inputIndex[f.k] = ni
      ni = ni + 1
    else
      local click = "click_none"
      if f.t == "cb" then
        self.setVar(fname, function() clickCheckbox(f.k) end)
        click = fname
      elseif f.t == "ct" then
        self.setVar(fname, function(_, _, alt) clickCounter(f.k, alt) end)
        click = fname
      end
      local size = units(math.min(w, h))
      self.createButton({
        click_function = click, function_owner = self,
        label = labelFor(f, nb),
        position = { x, Y, z }, rotation = { 0, 0, 0 },
        scale = { UI_SCALE, UI_SCALE, UI_SCALE },
        width = f.t == "dv" and 0 or size * 1.1, height = f.t == "dv" and 0 or size * 1.1,
        font_size = math.floor(size * (f.t == "cb" and 1.05 or 0.62)),
        color = { 1, 1, 1, 0 }, font_color = f.t == "dv" and DIM or INK,
        tooltip = f.t == "ct" and "Left-click +1, right-click -1" or "",
      })
      buttonIndex[f.k] = nb
      nb = nb + 1
    end
  end
  return { buttons = nb, inputs = ni }
end

local function isLoaded()
  return not self.loading_custom
end

function onLoad(saved)
  local data = nil
  if saved and saved ~= "" then
    local ok, d = pcall(JSON.decode, saved)
    if ok and type(d) == "table" then data = d end
  end
  if data and type(data.values) == "table" then
    values = data.values
  else
    values = defaults()
  end
  self.addContextMenuItem("Sync from campaign", function() syncFromCampaignState() end)
  if PAGE == 1 then
    self.addContextMenuItem("Fill investigators", function() fillInvestigators() end)
  end
  if PAGE_COUNT > 1 then
    self.addContextMenuItem("Next page", function()
      self.setState(PAGE % PAGE_COUNT + 1)
    end)
  end
  Wait.condition(function() Wait.frames(buildUi, 2) end, isLoaded, 30,
    function() buildUi() end)
end

---------------------------------------------------------------------- api --

function getLogValues()
  return { page = PAGE, pageCount = PAGE_COUNT, values = values }
end

-- params: { key = <field key>, value = <bool|number|string> }
function setLogValue(params)
  if type(params) ~= "table" then return false end
  local ok = setValue(params.key, params.value)
  if ok then
    refreshDerived()
    updateSave()
  end
  return ok
end

-- SCED's clean-up / campaign export read trauma from the log; this campaign
-- has none (age is its cost), so report zeros: 4 physical, then 4 mental.
function returnTrauma()
  return { 0, 0, 0, 0, 0, 0, 0, 0 }
end

----------------------------------------------------------- campaign sync --

local function findCampaignState()
  for _, o in ipairs(getObjects()) do
    if o ~= self then
      local ok, raw = pcall(function() return o.script_state end)
      if ok and type(raw) == "string" and raw:find('"loopsCompleted"', 1, true)
          and raw:find('"knowledge"', 1, true) then
        local ok2, st = pcall(JSON.decode, raw)
        if ok2 and type(st) == "table" and st.version then return st, o end
      end
    end
  end
  return nil
end

local function fold(s)
  s = string.lower(tostring(s or ""))
  s = s:gsub("ō", "o"):gsub("[^%a ]", "")
  return s
end

local function slotFor(id, name)
  local want = fold(name)
  local last = want:match("(%a+)$") or want
  for i = 1, 4 do
    local have = fold(values["inv" .. i .. "_name"])
    if have ~= "" and (have == want or have:find(last, 1, true)) then return i end
  end
  for i = 1, 4 do
    if (values["inv" .. i .. "_name"] or "") == "" then return i, true end
  end
  return nil
end

local DRIFT = { combat = "dcom", agility = "dagi", willpower = "dwil", intellect = "dint" }
local CRACKED = {
  lighthouse = { "the-lamp-was-never-lit", "the-keepers-ninth-death" },
  church     = { "the-thirteenth-toll", "the-hour-was-wrong" },
  road       = { "the-road-remembers", "who-walks-beside-you" },
  square     = { "the-sheriff-is-already-dead", "the-vote-that-never-ends" },
  fairground = { "the-wheel-still-turns", "the-ticket-takers-bargain" },
  almanac    = { "what-the-almanac-hid", "the-appointeds-name" },
}

-- Fill this page from a campaign-state table (or find the state token).
-- Checkboxes are only ever ticked, never cleared, so hand-written marks stay.
function syncFromCampaignState(st)
  if type(st) ~= "table" then st = findCampaignState() end
  if type(st) ~= "table" then
    broadcastToAll("Campaign log: no Still Hour campaign-state token found on the table.",
      { 1, 0.6, 0.4 })
    return { ok = false, page = PAGE, updated = 0 }
  end
  local n = 0
  local function put(key, value)
    if byKey[key] and values[key] ~= value then
      if setValue(key, value) then n = n + 1 end
    end
  end
  local function tick(key) if not values[key] then put(key, true) end end
  local knowledge = st.knowledge or {}
  local surface = 0
  for id, l in pairs(FACT_LAYER) do
    if l == "surface" and knowledge[id] then surface = surface + 1 end
  end
  if PAGE == 1 then
    put("loops", tonumber(st.loopsCompleted) or 0)
    put("banked", tonumber(st.bankedMemory) or 0)
    if st.investigators then put("investigators", tonumber(st.investigators)) end
    if knowledge["the-way-the-night-breaks"] then tick("act3")
    elseif surface >= 3 or (tonumber(st.loopsCompleted) or 0) >= 3 then tick("act2")
    else tick("act1") end
    for _, inv in ipairs(INVESTIGATORS) do
      local years = (st.years or {})[inv.id]
      if years ~= nil then
        local i, fresh = slotFor(inv.id, inv.name)
        if i then
          if fresh then put("inv" .. i .. "_name", inv.name) end
          put("inv" .. i .. "_years", tonumber(years) or 0)
          local br = (st.brackets or {})[inv.id]
          if type(br) == "table" then
            if DRIFT[br.physical] then tick("inv" .. i .. "_" .. DRIFT[br.physical]) end
            if DRIFT[br.mental] then tick("inv" .. i .. "_" .. DRIFT[br.mental]) end
          end
        end
      end
    end
  elseif PAGE == 2 then
    for id, known in pairs(knowledge) do
      if known then tick("k:" .. id) end
    end
    for id, claimed in pairs(st.victoryLog or {}) do
      if claimed then tick("v:" .. id) ; tick("vb:" .. id) end
    end
    local vote, name = knowledge["the-vote-that-never-ends"], knowledge["the-appointeds-name"]
    if vote and name then tick("sera_known") elseif vote or name then tick("sera_suspected") end
    if knowledge["the-ticket-takers-bargain"] then tick("bargain_heard") end
    for key, pair in pairs(CRACKED) do
      if knowledge[pair[1]] and knowledge[pair[2]] then tick("cracked_" .. key) end
    end
  end
  refreshDerived()
  updateSave()
  return { ok = true, page = PAGE, updated = n }
end

-- Page 1: investigator names/classes from the investigator cards on the table
-- (left to right) and the seated players' names, like SCED's "Fill" items.
function fillInvestigators()
  local found = {}
  for _, o in ipairs(getObjectsWithTag("Investigator")) do
    local ok, md = pcall(JSON.decode, o.getGMNotes() or "")
    if ok and type(md) == "table" and md.type == "Investigator" then
      found[#found + 1] = { obj = o, md = md, x = o.getPosition().x }
    end
  end
  table.sort(found, function(a, b) return a.x < b.x end)
  local n = 0
  for i = 1, math.min(4, #found) do
    setValue("inv" .. i .. "_name", found[i].obj.getName())
    if found[i].md.class then setValue("inv" .. i .. "_class", found[i].md.class) end
    n = n + 1
  end
  local players = Player.getPlayers and Player.getPlayers() or {}
  for i = 1, math.min(4, #players) do
    if (values["inv" .. i .. "_player"] or "") == "" then
      setValue("inv" .. i .. "_player", players[i].steam_name or players[i].color)
    end
  end
  if n > 0 then setValue("investigators", n) end
  refreshDerived()
  updateSave()
  return n
end
