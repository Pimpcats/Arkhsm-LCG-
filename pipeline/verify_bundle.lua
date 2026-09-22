-- Loads dist/stillhour_bundle.lua inside a stubbed Tabletop Simulator
-- environment and drives it exactly as TTS would: onLoad -> harness -> play
-- buttons -> interlude panel -> save/load. The stub is a *vanilla* table: no
-- SCED, no Global, no getObjects — so this also proves the board wiring
-- degrades without errors. Run: lua5.2 pipeline/verify_bundle.lua

-- ---- Lua-literal JSON standing in for TTS's global JSON ----
local function encode(v)
  local t = type(v)
  if t == "number" or t == "boolean" then return tostring(v) end
  if t == "string" then return string.format("%q", v) end
  if t == "nil" then return "nil" end
  if t == "table" then
    local parts = {}
    for k, val in pairs(v) do
      local key = (type(k) == "number") and ("[" .. k .. "]")
        or ("[" .. string.format("%q", k) .. "]")
      parts[#parts + 1] = key .. "=" .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. t)
end

local failures = 0
local encodeJSON  -- set below
local function expect(name, cond)
  print((cond and "  ok    " or "  FAIL  ") .. name)
  if not cond then failures = failures + 1 end
end

local buttons = {}
local errors = {}
local selfObj = {
  createButton = function(def) buttons[#buttons + 1] = def ; return true end,
  clearButtons = function() buttons = {} ; return true end,
  getPosition = function() return { x = 3, y = 1, z = 0 } end,
}
encodeJSON = encode
local env = setmetatable({
  JSON = { encode = encode, decode = function(s) return assert(load("return " .. s))() end },
  print = function(...)
    local s = table.concat({ ... }, "\t")
    if s:find("board wiring skipped", 1, true) then errors[#errors + 1] = s end
    print(s)
  end,
  broadcastToAll = function(msg) print("  (broadcast) " .. msg) end,
  self = selfObj,
}, { __index = _G })

local chunk = assert(loadfile("dist/stillhour_bundle.lua", "t", env))
chunk()

local function labels()
  local n = {}
  for _, b in ipairs(buttons) do n[#n + 1] = b.label end
  return n
end
local function hasLabel(prefix)
  for _, b in ipairs(buttons) do
    if b.label:sub(1, #prefix) == prefix then return b end
  end
  return nil
end

print("== driving the bundle as TTS would ==")
env.onLoad(nil)
print("  created " .. #buttons .. " buttons: " .. table.concat(labels(), ", "))
for _, p in ipairs({ "Memory ", "Dissonance ", "Hour ", "Appointed: ", "[static] ", "Investigators ",
                     "Run Tests", "Reset Loop", "Interlude", "Sync Board" }) do
  expect("control has a '" .. p .. "' button", hasLabel(p) ~= nil)
end
for _, b in ipairs(buttons) do
  expect("button '" .. b.label .. "' has a click function",
    b.click_function and type(env[b.click_function]) == "function")
end

print("\n== runStillHourTests() ==")
local res = env.runStillHourTests()
expect("in-bundle tests all pass (" .. res.passed .. ")", res.failed == 0 and res.passed > 0)

print("\n== touch counters (left / right click) ==")
env.shClickMemory(nil, "White", false) ; env.shClickMemory(nil, "White", false)
expect("Memory +2 by clicks", env.shApiState().memory == 2)
env.shClickMemory(nil, "White", true)
expect("Memory right-click -1", env.shApiState().memory == 1)
for _ = 1, 6 do env.shClickDissonance(nil, "White", false) end
local s = env.shApiState()
expect("Dissonance 6 -> Glitch, Appointed Sensed, 1 [static] (virtual bag)",
  s.dissonance == 6 and s.band == "Glitch" and s.stage == 1 and s.static.target == 1 and s.static.mode == "virtual")
env.shClickDissonance(nil, "White", true)
expect("Dissonance right-click reduces", env.shApiState().dissonance == 5)
env.shClickHour(nil, "White", false)
expect("Hour left-click advances", env.shApiState().hour == 2)
env.shClickHour(nil, "White", true)
expect("Hour right-click rewinds", env.shApiState().hour == 1)
expect("Dissonance button label tracks state", hasLabel("Dissonance 5 / 18") ~= nil)
env.shClickAppointed(nil, "White", false)
expect("Appointed card-advance ratchets up a stage", env.shApiState().stage == 2)
env.shHoldBack()
expect("Hold Back drops a stage (no card on a vanilla table: no error)", env.shApiState().stage == 1)
env.shHunt() ; env.shSyncBoard() ; env.shClickStatic()
env.shClickInvestigators(nil, "White", false)
expect("Investigators +1 -> 4 (Memory cap 24)", env.shApiState().investigators == 4)
env.shClickInvestigators(nil, "White", true)

print("\n== [static] reveal from a chaos bag (table event) ==")
local fakeBag = { getName = function() return "Chaos Bag" end, getDescription = function() return "" end }
local token = { hasTag = function(t) return t == "StillHourStatic" end, getGUID = function() return "abc123" end }
local d0 = env.shApiState().dissonance
env.onObjectLeaveContainer(fakeBag, token)
expect("revealing [static] raises Dissonance by 1", env.shApiState().dissonance == d0 + 1)
env.onObjectLeaveContainer({ getName = function() return "Deck" end }, token)
expect("leaving another container is not a reveal", env.shApiState().dissonance == d0 + 1)
env.onObjectEnterContainer(fakeBag, token)
env.onObjectDestroy({ type = "Card", getGMNotes = function() return "" end })
env.onObjectDrop("White", token)

print("\n== interlude buy panel ==")
env.shApiCounter({ name = "memory", delta = 9 })
env.shOpenInterlude()
print("  panel: " .. table.concat(labels(), ", "))
expect("panel lists Recollections with prices", hasLabel("sthr-longwayround (2)") ~= nil)
expect("panel has level-up buttons", hasLabel("Lvl 3 (3)") ~= nil and hasLabel("Lvl 5 (5)") ~= nil)
local m0 = env.shApiState().memory
local rb = hasLabel("sthr-longwayround (2)")
env[rb.click_function](nil, "White", false)
expect("clicking a Recollection spends its memoryCost", env.shApiState().memory == m0 - 2)
env.shBuyLvl3(nil, "White", false)
expect("clicking Lvl 3 spends 3", env.shApiState().memory == m0 - 5)
expect("unaffordable purchase is refused", env.shApiBuy({ level = 5 }).ok == (m0 - 5 >= 5))
env.shBeginNextLoop()
expect("Begin Next Loop returns to the play panel", env.shApiState().mode == "play" and hasLabel("Run Tests") ~= nil)

print("\n== play sequence (console helpers) ==")
env.shRaiseDissonance()
env.shAdvanceHour()
env.shStatus()
env.shKnowledgeStatus()
env.shUnlock("no-such-fact")

print("\n== onSave -> onLoad round trip ==")
local before = env.shApiState()
local blob = env.onSave()
assert(type(blob) == "string" and #blob > 0, "onSave produced no state")
env.shApiCounter({ name = "memory", delta = 5 })
env.onLoad(blob)
local after = env.shApiState()
expect("state restored from LuaScriptState (" .. #blob .. " bytes)",
  after.memory == before.memory and after.dissonance == before.dissonance and after.stage == before.stage
  and after.hour == before.hour)
-- a v1 save (bare CampaignState blob) still loads
env.onLoad(encode({ version = 1, investigators = 3, loopsCompleted = 2, bankedMemory = 7, dissonance = 2,
  hourglass = 1, knowledge = {}, oncePerLoopFlags = {}, testTypesThisLoop = {}, testTypesLastLoop = {},
  years = {}, brackets = {}, appointedStage = 0, victoryLog = {} }))
expect("legacy v1 save loads", env.shApiState().memory == 7 and env.shApiState().loops == 2)

print("\n== investigators on a vanilla table: on-card Memory, Aging, log mirror ==")
-- a tiny table: two investigator cards, one minicard, a campaign log
local function stubCard(nick, md, tags)
  local o = { type = "Card", buttons = {}, tags = {}, memo = "" }
  for _, t in ipairs(tags or {}) do o.tags[t] = true end
  o.getName = function() return nick end
  o.getGMNotes = function() return encodeJSON(md) end
  o.getGUID = function() return nick end
  o.getPosition = function() return { x = 0, y = 1, z = 0 } end
  o.hasTag = function(t) return o.tags[t] == true end
  o.createButton = function(def) o.buttons[#o.buttons + 1] = def ; return true end
  o.getButtons = function()
    local l = {}
    for i, b in ipairs(o.buttons) do l[i] = { label = b.label, index = i - 1 } end
    return l
  end
  o.removeButton = function(i) table.remove(o.buttons, i + 1) ; return true end
  return o
end
local elias = stubCard("Elias Warde", { id = "sthr-elias", type = "Investigator", willpowerIcons = 3,
  intellectIcons = 2, combatIcons = 4, agilityIcons = 3, health = 9, sanity = 5 })
local birdie = stubCard("Birdie", { id = "sthr-birdie", type = "Investigator", willpowerIcons = 2,
  intellectIcons = 3, combatIcons = 3, agilityIcons = 5, health = 6, sanity = 7 })
local mini = stubCard("Elias mini", { id = "sthr-elias-m", type = "Minicard" }, { "Minicard" })
local log = stubCard("Campaign Log", { id = "STHR-LOG", type = "CampaignLog" }, { "CampaignLog" })
log.type = "Generic"
local table_ = { elias, birdie, mini, log }
env.getObjects = function() return table_ end
env.getObjectsWithTag = function(t)
  local l = {}
  for _, o in ipairs(table_) do if o.hasTag(t) then l[#l + 1] = o end end
  return l
end
env.shSyncBoard()
local function cardLabel(o, prefix)
  for _, b in ipairs(o.buttons) do if b.label:sub(1, #prefix) == prefix then return b end end
end
expect("each investigator card gets a Memory button", cardLabel(elias, "Memory 0") and cardLabel(birdie, "Memory 0"))
expect("each investigator card shows its Years", cardLabel(elias, "Years 0 · Prime") ~= nil)
expect("control lists investigator Memory rows", hasLabel("Birdie · Memory 0") and hasLabel("Elias Warde · Memory 0"))
env.shCardMemory(elias, "White", false) ; env.shCardMemory(elias, "White", false)
expect("clicking the card's Memory button adds on-card Memory", cardLabel(elias, "Memory 2") ~= nil
  and hasLabel("Elias Warde · Memory 2") ~= nil)
local row = hasLabel("Birdie · Memory")
env[row.click_function](nil, "White", false)
env.shCardMemory(birdie, "White", true) ; env.shCardMemory(birdie, "White", true)
expect("right-click lowers it, never below 0", cardLabel(birdie, "Memory 0") ~= nil)
local inv = env.shApiInvestigators()
expect("runner API reports investigators with Memory", #inv == 2 and inv[1].memory + inv[2].memory == 2)
local mirror = env.shApiLogMirror()
expect("state is mirrored into the campaign log memo", mirror ~= nil and mirror.bytes > 0)

-- interlude: bank, age with a locked choice, visible Years
env.shApiCounter({ name = "dissonance", delta = 12 })
env.shApiReset()
env.shOpenInterlude()
expect("interlude shows Bank on-card Memory (2)", hasLabel("Bank on-card Memory (2)") ~= nil)
expect("loop ended in danger is shown", hasLabel("Loop ended in danger: yes") ~= nil)
local mem0 = env.shApiState().memory
env.shBankOnCard()
expect("banking moves on-card Memory to the bank", env.shApiState().memory == mem0 + 2)
env.shApiCounter({ name = "memory", delta = 0 })
local b = hasLabel("Birdie · Years 0")
expect("aging row per investigator", b ~= nil and hasLabel("Defeated: no") ~= nil)
-- Birdie is row 1 or 2 depending on sort; find its index
local bi = investigatorIndex and investigatorIndex("sthr-birdie")
local r = env.shApiAge({ id = "sthr-birdie", defeated = true, leaned = true, physical = "agility", mental = "willpower" })
expect("Age applies Years (1 + defeated + danger + leaned = 4)", r ~= nil and r.years == 4 and r.gained == 4)
expect("aging only once per interlude", env.shApiAge({ id = "sthr-birdie" }) == nil)
env.shApiAge({ id = "sthr-elias" })
local r2 = env.shApiAge({ id = "sthr-birdie" })
expect("Birdie's card shows her Years", cardLabel(birdie, "Years 4 · Prime") ~= nil)
env.shBeginNextLoop()
env.shApiAge({ id = "sthr-birdie", physical = "agility", mental = "willpower" })   -- 4 -> 5 Weathered
expect("the card shows the new bracket", cardLabel(birdie, "Years 6 · Weathered") ~= nil)
-- a fresh control token adopts the newer state from the campaign log (SCED export/import path)
local before2 = env.shApiState()
local env2 = setmetatable({ self = { createButton = function() return true end, clearButtons = function() return true end,
  getPosition = function() return { x = 3, y = 1, z = 0 } end } }, { __index = env })
local chunk2 = assert(loadfile("dist/stillhour_bundle.lua", "t", env2))
chunk2()
env2.onLoad("")
local after2 = env2.shApiState()
local yrs = 0
for _, i in ipairs(env2.shApiInvestigators()) do yrs = yrs + i.years end
expect("a fresh control token adopts the campaign-log copy (SCED export/import path)",
  after2.loops == before2.loops and after2.memory == before2.memory and yrs == 8)

expect("no board-wiring errors on a vanilla table", #errors == 0)
for _, e in ipairs(errors) do print("    " .. e) end
if failures > 0 then
  print("verify_bundle: " .. failures .. " FAILURE(S)")
  os.exit(1)
end
print("verify_bundle: OK")
