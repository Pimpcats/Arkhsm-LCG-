-- THE STILL HOUR — control object entry script.
-- Appended by pipeline/bundle_mod.py AFTER the inlined module table, so the
-- local require() defined in the bundle preamble is in scope here. This is the
-- code that actually runs on the control token in Tabletop Simulator.
--
-- It is the campaign's one state host (docs/INTEGRATION.md §2) and the board
-- wiring: touchable Memory / Dissonance / Hour counters, the [static] chaos-bag
-- adapter, the Appointed's card buttons, location flips/seals and the interlude
-- buy panel. Rules live in src/StillHour/*; this file only routes clicks and
-- table events into them. Every entry point is guarded so a vanilla (non-SCED)
-- table, or a missing object, never raises a script error.

local Constants     = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")
local Dissonance    = require("StillHour/Dissonance")
local LoopFlags     = require("StillHour/LoopFlags")
local Hourglass     = require("StillHour/Hourglass")
local Aging         = require("StillHour/Aging")
local Appointed     = require("StillHour/Appointed")
local Knowledge     = require("StillHour/Knowledge")
local Locations     = require("StillHour/Locations")
local Interlude     = require("StillHour/Interlude")
local SCED          = require("StillHour/SCED")
local ChaosBag      = require("StillHour/ChaosBag")
local Board         = require("StillHour/Board")

local SAVE_VERSION = 2

local function note(msg)
  pcall(print, "[Still Hour] " .. tostring(msg))
end

local function announce(msg, tint)
  local ok = pcall(broadcastToAll, tostring(msg), tint or { 0.95, 0.85, 0.6 })
  if not ok then note(msg) end
end

--- Run fn; report (never raise) a Lua error.
local function guarded(what, fn, ...)
  local ok, res = pcall(fn, ...)
  if not ok then
    note("board wiring skipped (" .. what .. "): " .. tostring(res))
    return nil
  end
  return res
end

-- The real chaos-bag adapter (SCED bag / table "Chaos Bag" / virtual).
local bag = ChaosBag.new({ log = note })

local mode = "play"             -- "play" | "interlude"
local recollectionList = nil    -- cached {id, name, cost} for the buy panel
local investigatorList = {}     -- cached Board.investigators() for the row buttons
local aging = {}                -- investigatorId -> interlude aging inputs {defeated, physical, mental, aged}
local saveSeq = 0               -- bumps on every change; newest copy wins (control vs campaign log)

-------------------------------------------------------------- board contexts --

local function hourLog(h, name, msg)
  note(string.format("Hour %d — %s: %s", h, name or "?", msg or ""))
end

local refreshControl  -- forward

local function syncBoard()
  guarded("Appointed", Board.syncAppointed, { log = hourLog })
end

--- The ctx the Hourglass/Appointed modules call back into.
local function playCtx()
  return Board.appointedCtx({
    dissonance = Dissonance,
    bag = bag,
    log = hourLog,
    addStatic = function(n) bag.addStatic(n) end,
    removeStatic = function(n) bag.removeStatic(n) end,
    onAppointedAdvance = function() end,        -- reconciled once, after the action
    onReset = function()
      announce("The Appointed Hour: the night ends. Resolve the reset, then click Reset Loop.")
    end,
    onFinaleAttemptable = function()
      announce("The Appointed Hour: you may attempt the finale.")
    end,
  })
end

local function afterChange()
  syncBoard()
  guarded("investigators", Board.refreshInvestigators, false)
  refreshControl()
end

-------------------------------------------------------------------- actions --
-- Shared by the buttons (click functions) and the runner API (Object.call).

local function changeMemory(delta)
  CampaignState.bankMemory(delta)
end

local function changeInvestigators(delta)
  local n = CampaignState.constants().investigators + delta
  CampaignState.setInvestigatorCount(math.max(1, math.min(4, n)))
  Dissonance.syncBag(bag)
end

local function changeDissonance(delta)
  local before = Appointed.stage()
  if delta > 0 then
    local info = Dissonance.raise(delta, bag)
    if info.appointedStage > before then
      announce("The Appointed draws nearer: " .. Appointed.stageName() .. ".")
    end
    if info.reachedReset then
      announce("Dissonance reached the reset threshold. Resolve the reset, then click Reset Loop.",
        { 1, 0.4, 0.4 })
    end
  else
    Dissonance.reduce(-delta, bag)
  end
end

local function changeHour(delta)
  if delta > 0 then
    Hourglass.advance(delta, playCtx())
  else
    Hourglass.rewind(-delta, playCtx())
  end
end

local function advanceAppointedByCard()
  Appointed.advanceByCard(playCtx())
  announce("The Appointed's Approach advances: " .. Appointed.stageName() .. ".")
end

local function holdBack()
  local s = Appointed.holdBack(playCtx())
  announce("Held back: the Appointed is " .. Appointed.stageName() .. "; the Hourglass rewinds to Hour "
    .. CampaignState.getHour() .. ".")
  return s
end

local function hunt()
  local moved = Appointed.hunt(playCtx())
  if not Appointed.isHunter() then note("The Appointed is not hunting yet (" .. Appointed.stageName() .. ").") end
  return moved
end

local function resetLoop()
  CampaignState.reset()
  bag.clearTemporary()
  Dissonance.syncBag(bag)
  note("The night folds. Loop reset: Memory/Knowledge/Years kept; Dissonance dropped to the scar.")
end

local function unlockFact(id)
  local ok, newly = pcall(Knowledge.unlock, id)
  if not ok then
    note("unknown fact id: " .. tostring(id))
    return nil
  end
  local rep = guarded("locations", Board.syncLocations) or {}
  return { newly = newly, report = rep }
end

--------------------------------------------------------------- interlude --

local function readRecollections()
  local list, seen = {}, {}
  local function consider(id, name, md)
    if type(id) ~= "string" or seen[id] then return end
    local cost = Interlude.recollectionCost(id) or (md and tonumber(md.memoryCost))
    if cost == nil then return end
    seen[id] = true
    list[#list + 1] = { id = id, name = name ~= "" and name or id, cost = cost }
  end
  -- metadata first: any card on the table (or in a bag/deck) carrying memoryCost
  guarded("recollection scan", function()
    if type(getObjects) ~= "function" then return end
    for _, o in ipairs(getObjects()) do
      local t = o.type
      if t == "Bag" or t == "Deck" then
        for _, e in ipairs(o.getObjects() or {}) do
          local ok, md = pcall(JSON.decode, e.gm_notes or "")
          if ok and type(md) == "table" and md.memoryCost ~= nil then consider(md.id, e.name or "", md) end
        end
      elseif t == "Card" then
        local ok, md = pcall(JSON.decode, o.getGMNotes() or "")
        if ok and type(md) == "table" and md.memoryCost ~= nil then consider(md.id, o.getName(), md) end
      end
    end
  end)
  -- then the rules table (so the panel works with no cards on the table)
  local ids = {}
  for id in pairs(Interlude.RECOLLECTION_COST) do ids[#ids + 1] = id end
  table.sort(ids)
  for _, id in ipairs(ids) do consider(id, id, nil) end
  table.sort(list, function(a, b) return a.name < b.name end)
  return list
end

local function buyRecollection(id)
  local ok = Interlude.buyRecollection(id)
  local cost = Interlude.recollectionCost(id)
  local name = id
  for _, r in ipairs(recollectionList or {}) do if r.id == id then name = r.name end end
  if ok then
    announce(string.format("Bought %s for %d Memory (%d banked).", name, cost, CampaignState.getBankedMemory()))
  else
    note("Cannot buy " .. tostring(id) .. " (unknown, or not enough Memory).")
  end
  return ok
end

local function buyLevel(level)
  local ok = Interlude.buyUpgrade(level)
  if ok then
    announce(string.format("Level-%d upgrade bought for %d Memory (%d banked).", level, level,
      CampaignState.getBankedMemory()))
  else
    note("Not enough Memory for a level-" .. tostring(level) .. " upgrade.")
  end
  return ok
end

local function beginNextLoop()
  Interlude.beginNextLoop()
  Dissonance.syncBag(bag)
  aging = {}
  mode = "play"
  guarded("aging", Board.refreshInvestigators, true)
  announce("A new night begins. Memory capped at " .. CampaignState.constants().memoryCap .. ".")
end

----------------------------------------------------- investigators / Aging --

local function changeOnCardMemory(id, delta)
  if type(id) ~= "string" then return nil end
  return CampaignState.addOnCardMemory(id, delta)
end

--- kind = "raises" | "spent"
local function changeTally(id, kind, delta)
  return CampaignState.addTally(id, kind, delta)
end

local function bankOnCard()
  local n = Interlude.bankOnCard()
  announce(string.format("Banked %d on-card Memory (%d banked).", n, CampaignState.getBankedMemory()))
  return n
end

local function agingFor(id)
  aging[id] = aging[id] or {}
  local a = aging[id]
  local rec = CampaignState.getBracket(id) or {}
  a.physical = rec.physical or a.physical or "combat"
  a.mental = rec.mental or a.mental or "intellect"
  return a
end

--- Age one investigator this interlude (once). "Defeated" comes from the panel
-- toggle; "ended in danger" from the Dissonance recorded when the loop ended;
-- "leaned on the loop" is derived from the investigator's own tallies
-- (Interlude.leanedOnLoop: raised Dissonance 3+ times or spent 4+ Memory on
-- loop powers) — the design has no override, so neither does the panel.
local function ageInvestigator(id)
  local a = agingFor(id)
  if a.aged then return nil end
  local r = Interlude.age(id, { defeated = a.defeated, endedInDanger = Interlude.loopEndedInDanger() },
    { physical = a.physical, mental = a.mental })
  a.aged = r.yearsGained
  guarded("aging", Board.refreshInvestigators, true)
  local name = id
  for _, inv in ipairs(investigatorList) do if inv.id == id then name = inv.name end end
  announce(string.format("%s ages %d year(s): %d (%s)%s", name, r.yearsGained, r.years, r.bracket,
    r.agedOut and " — aged out of the campaign" or ""))
  return r
end

------------------------------------------------------------ control buttons --

local BTN_COLOR = { 0.15, 0.13, 0.2 }
local BTN_FONT = { 0.95, 0.9, 0.7 }

-- Button height above the token: the block's top face is at local y 0.5, so
-- anything lower is hidden wherever it passes over the block.
local BTN_Y = 0.55
-- Layout grid (local units): a width-1000 button is ~2.0 wide and a width-620
-- one ~1.24, so pairs sit at +-PAIR_X and rows of three at -ROW3_X / 0 / ROW3_X.
local PAIR_X, ROW3_X = 1.05, 1.35

local function button(fn, label, x, z, w, tooltip, fs)
  pcall(function()
    self.createButton({
      click_function = fn, function_owner = self, label = label, tooltip = tooltip or "",
      position = { x, BTN_Y, z }, rotation = { 0, 0, 0 },
      width = w or 620, height = 300, font_size = fs or 100,
      color = BTN_COLOR, font_color = BTN_FONT,
    })
  end)
end

local function header(label, z)
  pcall(function()
    self.createButton({
      click_function = "shNoop", function_owner = self, label = label,
      position = { 0, BTN_Y, z }, rotation = { 0, 0, 0 },
      width = 0, height = 0, font_size = 120, font_color = BTN_FONT,
    })
  end)
end

local PLUS_MINUS = "Left-click +1 · Right-click -1"

local function drawPlay()
  local c = CampaignState.constants()
  header(string.format("THE STILL HOUR · loop %d", CampaignState.getLoopsCompleted() + 1), -2.3)
  button("shClickMemory", string.format("Memory %d / %d", CampaignState.getBankedMemory(), c.memoryCap),
    -PAIR_X, -1.7, 1000, "Banked Memory. " .. PLUS_MINUS)
  button("shClickInvestigators", "Investigators " .. c.investigators, PAIR_X, -1.7, 1000,
    "Sets every threshold. " .. PLUS_MINUS .. (SCED.getInvestigatorCount()
      and (" (SCED counter: " .. SCED.getInvestigatorCount() .. ")") or ""))
  button("shClickDissonance", string.format("Dissonance %d / %d · %s", CampaignState.getDissonance(),
    c.resetThreshold, CampaignState.band()), -PAIR_X, -1.1, 1000, "Left-click raise · Right-click reduce")
  local d = bag.describe()
  button("shClickStatic", string.format("[static] %d (%s)", d.target, d.mode), PAIR_X, -1.1, 1000,
    "Baseline + temporary [static] this bag should hold. Click to re-sync the chaos bag.")
  local h = CampaignState.getHour()
  button("shClickHour", string.format("Hour %d · %s", h, Hourglass.HOUR_NAMES[h] or "?"), -PAIR_X, -0.5, 1000,
    "Left-click advance (resolves the Hour) · Right-click rewind")
  button("shClickAppointed", "Appointed: " .. Appointed.stageName(), PAIR_X, -0.5, 1000,
    "Left-click: a card advances its Approach one stage (min Sensed). Hold Back is on its card.")
  investigatorList = guarded("investigators", Board.investigators) or {}
  for i, inv in ipairs(investigatorList) do
    if i > 4 then break end
    button("shInvMem" .. i, string.format("%s · Memory %d", inv.name, CampaignState.getOnCardMemory(inv.id)),
      (i % 2 == 1) and -PAIR_X or PAIR_X, 0.1 + math.floor((i - 1) / 2) * 0.55, 1000,
      "Memory on this investigator's cards (prey = most). " .. PLUS_MINUS, 80)
  end
  -- two rows of three, spaced so no button overlaps another
  button("runStillHourTests", "Run Tests", -ROW3_X, 1.4)
  button("shStatus", "Status", 0.0, 1.4)
  button("shSyncBoard", "Sync Board", ROW3_X, 1.4, 620, "Re-apply location faces/seals, the Appointed and the chaos bag.")
  button("shReset", "Reset Loop", -ROW3_X, 2.0)
  button("shOpenInterlude", "Interlude", 0.0, 2.0, 620, "Spend Memory: Recollections and level-ups.")
  button("shKnowledgeStatus", "Knowledge", ROW3_X, 2.0)
end

local function drawInterlude()
  local c = CampaignState.constants()
  header("INTERLUDE · spend Memory", -2.3)
  button("shClickMemory", string.format("Memory %d / %d", CampaignState.getBankedMemory(), c.memoryCap),
    0, -1.7, 1400, "Bank on-card Memory. " .. PLUS_MINUS)
  recollectionList = readRecollections()
  for i, r in ipairs(recollectionList) do
    if i > 16 then break end
    local col = (i - 1) % 2
    local row = math.floor((i - 1) / 2)
    button("shBuyRec" .. i, string.format("%s (%d)", r.name, r.cost),
      col == 0 and -PAIR_X or PAIR_X, -1.1 + row * 0.55, 1000, "Buy this Recollection for " .. r.cost .. " Memory.", 80)
  end
  local rows = math.ceil(math.min(#recollectionList, 16) / 2)
  local z = -1.1 + rows * 0.55 + 0.1
  for lvl = 1, 5 do
    button("shBuyLvl" .. lvl, "Lvl " .. lvl .. " (" .. lvl .. ")", -2.4 + (lvl - 1) * 1.2, z, 520,
      "Level a card up to level " .. lvl .. " for " .. lvl .. " Memory.", 90)
  end
  button("shBeginNextLoop", "Begin Next Loop", -0.8, z + 0.6, 1000, "Cap Memory and start the next night.")
  button("shCloseInterlude", "Back", 1.35, z + 0.6, 620)
  -- Aging + banking, in a column to the right of the token
  local onCard = 0
  for _, n in pairs(CampaignState.onCardMemoryMap()) do onCard = onCard + n end
  local X = 4.2
  header("AGING", -2.3)
  button("shBankOnCard", "Bank on-card Memory (" .. onCard .. ")", X, -1.7, 1400,
    "Guide interlude step 2: move all Memory on cards to banked Memory.", 90)
  local danger = Interlude.loopEndedInDanger()
  button("shNoop", "Loop ended in danger: " .. (danger and "yes (+1)" or "no"), X, -1.2, 1400,
    "From the Dissonance when the loop ended.", 80)
  investigatorList = guarded("investigators", Board.investigators) or {}
  for i, inv in ipairs(investigatorList) do
    if i > 4 then break end
    local a = agingFor(inv.id)
    local zi = -0.65 + (i - 1) * 0.95
    local yrs = CampaignState.getYears(inv.id)
    button("shNoop", string.format("%s · Years %d · %s", inv.name, yrs, Aging.bracketForYears(yrs)),
      X - 0.75, zi, 1000, "", 80)
    local t = CampaignState.getTallies(inv.id)
    button("shTalRaised" .. i, "Raised " .. t.raises, X + 0.85, zi, 380,
      "Times this investigator raised Dissonance this loop. " .. PLUS_MINUS, 70)
    button("shTalSpent" .. i, "Spent " .. t.spent, X + 1.75, zi, 380,
      "Memory this investigator spent on loop powers (Recollections, foreknowledge) this loop. " .. PLUS_MINUS, 70)
    local locked = (CampaignState.getBracket(inv.id) or {}).physical ~= nil
    button("shAgeDef" .. i, "Defeated: " .. (a.defeated and "yes" or "no"), X - 1.45, zi + 0.42, 330, "", 70)
    button("shNoop", "Leaned: " .. (Interlude.leanedOnLoop(inv.id) and "yes" or "no"), X - 0.7, zi + 0.42, 330,
      "Derived: raised Dissonance 3+ times or spent 4+ Memory on loop powers this loop.", 70)
    button("shAgePhys" .. i, "-" .. a.physical .. (locked and " (locked)" or ""), X + 0.05, zi + 0.42, 330,
      "Physical skill that drifts down (chosen once, locked).", 60)
    button("shAgeMent" .. i, "+" .. a.mental .. (locked and " (locked)" or ""), X + 0.8, zi + 0.42, 330,
      "Mental skill that drifts up (chosen once, locked).", 60)
    button("shAge" .. i, a.aged and ("Aged +" .. a.aged) or "Age", X + 1.6, zi + 0.42, 330,
      "Apply this interlude's Years.", 70)
  end
end

-- The campaign content that decides "newer": the sequence number only moves
-- when this changes (so a plain reload or a button redraw is not a change).
local lastBody = nil
local function body()
  local ok, s = pcall(JSON.encode, { c = CampaignState.raw(), b = bag.save(), a = aging, m = mode })
  return ok and s or nil
end

local function persist()
  local b = body()
  if b ~= lastBody then
    if lastBody ~= nil then saveSeq = saveSeq + 1 end
    lastBody = b
  end
  -- TTS only refreshes script_state when the game saves; reload() (and SCED
  -- tools that reload objects) rebuild from it, so keep it current ourselves
  pcall(function() self.script_state = onSave() end)
  guarded("campaign log", function() Board.mirrorToLog(onSave(), saveSeq) end)
end

refreshControl = function()
  pcall(function() self.clearButtons() end)
  if mode == "interlude" then drawInterlude() else drawPlay() end
  persist()
end

-- Click handlers: click_function(obj, player_color, alt_click) (TTS createButton).
function shNoop() end

function shClickMemory(_, _, alt) guarded("memory", changeMemory, alt and -1 or 1) ; refreshControl() end
function shClickInvestigators(_, _, alt) guarded("investigators", changeInvestigators, alt and -1 or 1) ; afterChange() end
function shClickDissonance(_, _, alt) guarded("dissonance", changeDissonance, alt and -1 or 1) ; afterChange() end
function shClickHour(_, _, alt) guarded("hour", changeHour, alt and -1 or 1) ; afterChange() end
function shClickStatic() guarded("chaos bag", Dissonance.syncBag, bag) ; refreshControl() end
function shClickAppointed(_, _, alt)
  if alt then note("The Appointed: " .. Appointed.stageName()) return end
  guarded("appointed", advanceAppointedByCard) ; afterChange()
end
function shAppointedInfo() note("The Appointed: " .. Appointed.stageName() .. " (stage " .. Appointed.stage() .. ")") end
function shHoldBack() guarded("hold back", holdBack) ; afterChange() end
function shHunt() guarded("hunt", hunt) ; afterChange() end
function shSyncBoard()
  local rep = guarded("sync", Board.syncAll, { log = hourLog, applyStats = true }) or {}
  guarded("chaos bag", Dissonance.syncBag, bag)
  refreshControl()
  note(string.format("Board synced: %d campaign location(s), %d flipped, %d sealed.",
    rep.seen or 0, rep.flipped or 0, rep.sealed or 0))
  return rep
end
local function invAt(i) return investigatorList[i] and investigatorList[i].id end
local function clickInvMem(i, alt) guarded("memory", changeOnCardMemory, invAt(i), alt and -1 or 1) ; afterChange() end
function shInvMem1(_, _, alt) clickInvMem(1, alt) end
function shInvMem2(_, _, alt) clickInvMem(2, alt) end
function shInvMem3(_, _, alt) clickInvMem(3, alt) end
function shInvMem4(_, _, alt) clickInvMem(4, alt) end
--- The Memory button on an investigator card itself.
function shCardMemory(obj, _, alt)
  guarded("memory", changeOnCardMemory, Board.investigatorIdOf(obj), alt and -1 or 1)
  afterChange()
end
function shBankOnCard() guarded("bank", bankOnCard) ; afterChange() end

local function toggleAging(i, field)
  local id = invAt(i)
  if not id then return end
  local a = agingFor(id)
  local locked = (CampaignState.getBracket(id) or {}).physical ~= nil
  if field == "physical" then
    if not locked then a.physical = (a.physical == "combat") and "agility" or "combat" end
  elseif field == "mental" then
    if not locked then a.mental = (a.mental == "intellect") and "willpower" or "intellect" end
  elseif not a.aged then
    a[field] = not a[field]
  end
  refreshControl()
end
local function ageAt(i) if invAt(i) then guarded("age", ageInvestigator, invAt(i)) end ; afterChange() end
function shAgeDef1() toggleAging(1, "defeated") end
function shAgeDef2() toggleAging(2, "defeated") end
function shAgeDef3() toggleAging(3, "defeated") end
function shAgeDef4() toggleAging(4, "defeated") end
local function clickTally(i, kind, alt) guarded("tally", changeTally, invAt(i), kind, alt and -1 or 1) ; afterChange() end
function shTalRaised1(_, _, alt) clickTally(1, "raises", alt) end
function shTalRaised2(_, _, alt) clickTally(2, "raises", alt) end
function shTalRaised3(_, _, alt) clickTally(3, "raises", alt) end
function shTalRaised4(_, _, alt) clickTally(4, "raises", alt) end
function shTalSpent1(_, _, alt) clickTally(1, "spent", alt) end
function shTalSpent2(_, _, alt) clickTally(2, "spent", alt) end
function shTalSpent3(_, _, alt) clickTally(3, "spent", alt) end
function shTalSpent4(_, _, alt) clickTally(4, "spent", alt) end
--- The tally buttons on an investigator card itself.
function shCardRaised(obj, _, alt)
  guarded("tally", changeTally, Board.investigatorIdOf(obj), "raises", alt and -1 or 1)
  afterChange()
end
function shCardSpent(obj, _, alt)
  guarded("tally", changeTally, Board.investigatorIdOf(obj), "spent", alt and -1 or 1)
  afterChange()
end
function shAgePhys1() toggleAging(1, "physical") end
function shAgePhys2() toggleAging(2, "physical") end
function shAgePhys3() toggleAging(3, "physical") end
function shAgePhys4() toggleAging(4, "physical") end
function shAgeMent1() toggleAging(1, "mental") end
function shAgeMent2() toggleAging(2, "mental") end
function shAgeMent3() toggleAging(3, "mental") end
function shAgeMent4() toggleAging(4, "mental") end
function shAge1() ageAt(1) end
function shAge2() ageAt(2) end
function shAge3() ageAt(3) end
function shAge4() ageAt(4) end

function shOpenInterlude() mode = "interlude" ; refreshControl() end
function shCloseInterlude() mode = "play" ; refreshControl() end
function shBeginNextLoop() guarded("next loop", beginNextLoop) ; afterChange() end

local function buyRecAt(i)
  local r = recollectionList and recollectionList[i]
  if r then guarded("buy", buyRecollection, r.id) end
  refreshControl()
end
function shBuyRec1() buyRecAt(1) end
function shBuyRec2() buyRecAt(2) end
function shBuyRec3() buyRecAt(3) end
function shBuyRec4() buyRecAt(4) end
function shBuyRec5() buyRecAt(5) end
function shBuyRec6() buyRecAt(6) end
function shBuyRec7() buyRecAt(7) end
function shBuyRec8() buyRecAt(8) end
function shBuyRec9() buyRecAt(9) end
function shBuyRec10() buyRecAt(10) end
function shBuyRec11() buyRecAt(11) end
function shBuyRec12() buyRecAt(12) end
function shBuyRec13() buyRecAt(13) end
function shBuyRec14() buyRecAt(14) end
function shBuyRec15() buyRecAt(15) end
function shBuyRec16() buyRecAt(16) end
function shBuyLvl1() guarded("buy", buyLevel, 1) ; refreshControl() end
function shBuyLvl2() guarded("buy", buyLevel, 2) ; refreshControl() end
function shBuyLvl3() guarded("buy", buyLevel, 3) ; refreshControl() end
function shBuyLvl4() guarded("buy", buyLevel, 4) ; refreshControl() end
function shBuyLvl5() guarded("buy", buyLevel, 5) ; refreshControl() end

-------------------------------------------------------------------- lifecycle --

function onSave()
  return JSON.encode({
    v = SAVE_VERSION,
    campaign = CampaignState.raw(),
    bag = bag.save(),
    board = Board.save(),
    mode = mode,
    aging = aging,
    seq = saveSeq,
  })
end

local function restore(saved)
  if saved == nil or saved == "" then return end
  local ok, blob = pcall(JSON.decode, saved)
  if ok and type(blob) == "table" and blob.campaign ~= nil then
    CampaignState.deserialize(JSON.encode(blob.campaign))
    bag.load(blob.bag)
    Board.load(blob.board)
    mode = blob.mode == "interlude" and "interlude" or "play"
    aging = type(blob.aging) == "table" and blob.aging or {}
    saveSeq = tonumber(blob.seq) or 0
    lastBody = body()
  else
    CampaignState.deserialize(saved)          -- v1: the bare CampaignState blob
  end
end

--- Adopt the copy SCED carried in the campaign log (its export/import) when it
-- is newer than ours. Returns true if adopted.
local function adoptLogMirror(log)
  local m = Board.readLogMirror(log)
  if not m or m.seq <= saveSeq then return false end
  restore(m.blob)
  saveSeq = m.seq
  Dissonance.syncBag(bag)
  announce("Still Hour campaign state restored from the campaign log.")
  return true
end

function onLoad(saved)
  guarded("load", restore, saved)
  Board.init(self, { log = note })
  guarded("campaign log", adoptLogMirror)
  bag.count = bag.target()
  refreshControl()
  -- let the table settle (SCED's own objects load too) before touching it
  local ok = pcall(function()
    Wait.frames(function()
      guarded("chaos bag", Dissonance.syncBag, bag)
      guarded("board", Board.syncAll, { log = hourLog })
      refreshControl()
    end, 60)
  end)
  if not ok then guarded("chaos bag", Dissonance.syncBag, bag) end
  print("THE STILL HOUR control ready. Investigators = " ..
    CampaignState.constants().investigators .. (SCED.isPresent() and " (SCED detected)" or "")
    .. ". Click 'Run Tests' to verify the build.")
end

---------------------------------------------------- table events (universal) --

function onObjectLeaveContainer(container, obj)
  guarded("reveal", function()
    if bag.onLeave(container, obj) then
      local info = Dissonance.onStaticRevealed(bag)
      announce(string.format("[static] revealed: Dissonance %d (%s).", info.value, info.band))
      if info.reachedReset then
        announce("Dissonance reached the reset threshold. Resolve the reset, then click Reset Loop.",
          { 1, 0.4, 0.4 })
      end
      afterChange()
    end
    Board.onLeaveContainer(container, obj)
  end)
end

function onObjectEnterContainer(container, obj)
  guarded("container", function()
    bag.onEnter(container, obj)
    Board.onEnterContainer(container, obj)
  end)
end

function onObjectDestroy(obj)
  if obj == self then return end
  guarded("destroy", Board.onDestroy, obj)
end

function onObjectDrop(_, obj)
  guarded("drop", Board.onDrop, obj)
end

function onObjectSpawn(obj)
  -- SCED respawns the chaos bag when its difficulty is set; re-add [static].
  if ChaosBag.isChaosBag(obj) then
    pcall(function() Wait.frames(function() guarded("chaos bag", bag.reconcile) ; refreshControl() end, 30) end)
  end
  -- SCED's campaign import respawns the campaign log (with our mirrored state)
  local isLog = pcall(function() return obj.hasTag(Board.CAMPAIGN_LOG_TAG) end) and obj.hasTag(Board.CAMPAIGN_LOG_TAG)
  if isLog then
    pcall(function()
      Wait.frames(function()
        if guarded("campaign log", adoptLogMirror, obj) then afterChange() end
      end, 10)
    end)
  end
end

------------------------------------------------------ runner / console API --
-- Object.call(name, param) passes one table; these return plain tables.

function shApiState()
  local c = CampaignState.constants()
  return {
    memory = CampaignState.getBankedMemory(), dissonance = CampaignState.getDissonance(),
    band = CampaignState.band(), hour = CampaignState.getHour(), stage = Appointed.stage(),
    investigators = c.investigators, loops = CampaignState.getLoopsCompleted(),
    static = bag.describe(), sced = SCED.isPresent(), mode = mode,
  }
end

function shApiCounter(p)
  p = p or {}
  local d = tonumber(p.delta) or 1
  local fns = { memory = changeMemory, investigators = changeInvestigators,
                dissonance = changeDissonance, hour = changeHour }
  if p.name == "appointed" then
    guarded("appointed", advanceAppointedByCard)
  elseif fns[p.name] then
    guarded(p.name, fns[p.name], d)
  end
  afterChange()
  return shApiState()
end

function shApiInvestigators()
  local out = {}
  for i, inv in ipairs(guarded("investigators", Board.refreshInvestigators, false) or {}) do
    out[i] = inv
    out[i].memory = CampaignState.getOnCardMemory(inv.id)
    out[i].years = CampaignState.getYears(inv.id)
  end
  return out
end
function shApiOnCardMemory(p)
  guarded("memory", changeOnCardMemory, p and p.id, tonumber(p and p.delta) or 1)
  afterChange()
  return CampaignState.getOnCardMemory(p and p.id)
end
function shApiBankOnCard() local n = guarded("bank", bankOnCard) ; afterChange() ; return n end
--- p = {id, kind = "raises"|"spent", delta}
function shApiTally(p)
  p = p or {}
  guarded("tally", changeTally, p.id, p.kind, tonumber(p.delta) or 1)
  afterChange()
  local t = CampaignState.getTallies(p.id)
  return { raises = t.raises, spent = t.spent, leaned = Interlude.leanedOnLoop(p.id) }
end
--- p = {id, defeated, physical, mental}; "leaned" is derived from the tallies
function shApiAge(p)
  p = p or {}
  local a = agingFor(p.id)
  a.defeated = p.defeated and true or nil
  if p.physical then a.physical = p.physical end
  if p.mental then a.mental = p.mental end
  local r = guarded("age", ageInvestigator, p.id)
  afterChange()
  return r and { years = r.years, bracket = r.bracket, gained = r.yearsGained } or nil
end
function shApiLogMirror() local m = Board.readLogMirror() ; return m and { seq = m.seq, bytes = #m.blob } or nil end

function shApiHoldBack() local s = guarded("hold back", holdBack) ; afterChange() ; return s end
function shApiHunt() local m = guarded("hunt", hunt) ; afterChange() ; return m end
function shApiReset() guarded("reset", resetLoop) ; afterChange() ; return shApiState() end
function shApiSyncBoard() return shSyncBoard() end
function shApiUnlockFact(p) local r = unlockFact(p and p.id) ; refreshControl() ; return r end
function shApiSnapshot() return onSave() end
--- Put back the campaign (and [static] extras) from a shApiSnapshot blob. The
-- board's own tracking (what it placed / flipped) stays live, so the objects
-- are reconciled to the restored state rather than forgotten.
function shApiRestore(p)
  CampaignState.init(CampaignState.constants().investigators)
  guarded("restore", function()
    local blob = JSON.decode(p.blob)
    CampaignState.deserialize(JSON.encode(blob.campaign))
    bag.load(blob.bag)
  end)
  guarded("chaos bag", Dissonance.syncBag, bag)
  afterChange()
  return shApiState()
end
function shApiInterlude(p)
  mode = (p and p.open == false) and "play" or "interlude"
  refreshControl()
  local out = {}
  for i, r in ipairs(recollectionList or {}) do out[i] = { id = r.id, name = r.name, cost = r.cost } end
  return out
end
function shApiBuy(p)
  p = p or {}
  local ok
  if p.recollection then ok = buyRecollection(p.recollection) end
  if p.level then ok = buyLevel(tonumber(p.level)) end
  refreshControl()
  return { ok = ok == true, memory = CampaignState.getBankedMemory() }
end
function shApiBeginNextLoop() guarded("next loop", beginNextLoop) ; afterChange() ; return shApiState() end

------------------------------------------------------------------ console --

function shStatus()
  local c = CampaignState.constants()
  print(string.format(
    "STILL HOUR | loop %d | Memory %d/%d | Dissonance %d/%d (%s) | Hour %s | Appointed: %s | contest %d | [static] %d (%s)%s",
    CampaignState.getLoopsCompleted(), CampaignState.getBankedMemory(), c.memoryCap,
    CampaignState.getDissonance(), c.resetThreshold, CampaignState.band(),
    Hourglass.HOUR_NAMES[CampaignState.getHour()] or "?", Appointed.stageName(), c.contestTarget,
    bag.target(), bag.describe().mode, SCED.isPresent() and (" | SCED " .. tostring(SCED.version())) or ""))
end

function shAdvanceHour()
  guarded("hour", changeHour, 1)
  afterChange()
  shStatus()
end

function shRaiseDissonance()
  local before = Appointed.stage()
  local info = Dissonance.raise(1, bag)
  print("Dissonance -> " .. info.value .. " (" .. info.band .. ")" ..
    (info.appointedStage > before and ("  ** the Appointed advances to " .. Appointed.stageName() .. " **") or ""))
  if info.reachedReset then print("  Dissonance hit the reset threshold — the loop ends.") ; shReset() end
  afterChange()
end

function shReset()
  guarded("reset", resetLoop)
  afterChange()
  shStatus()
end

--- Console: unlock a Knowledge fact by id when a card or the guide says so,
-- then re-apply location faces/seals. e.g. shUnlock("fact-id")
function shUnlock(id)
  local r = unlockFact(id)
  if r then note("Fact recorded. Locations re-synced.") end
  refreshControl()
end

-- P7 demo (console only — it mutates the campaign): age a sample party, bank
-- Memory, and hand off to the loop.
function shInterludeDemo()
  print("── Interlude ──")
  local entries = {
    { id = "sthrelias",   cond = { defeated = true }, lockedChoice = { physical = "combat", mental = "willpower" } },
    { id = "sthrayako",   cond = { leanedOnLoop = true }, lockedChoice = { physical = "combat", mental = "intellect" } },
    { id = "sthrbirdie",  cond = {} },
  }
  local results = Interlude.ageAll(entries)
  for _, e in ipairs(entries) do
    local r = results[e.id]
    print(string.format("  %-13s +%d yr -> %d (%s)%s", e.id, r.yearsGained, r.years, r.bracket,
      r.bracketChanged and "  << bracket change" or ""))
  end
  Interlude.bank(17)  -- sample on-card Memory banked this loop
  Interlude.beginNextLoop()
  print("  banked +17 Memory (capped to " .. CampaignState.getBankedMemory() .. "). "
    .. "Buy Recollections with the Interlude panel or shBuy(\"sthr-longwayround\").")
  refreshControl()
end

function shBuy(cardId)
  buyRecollection(cardId)
  refreshControl()
end

-- P6: report Act/finale gates and the campaign locations on the table.
function shKnowledgeStatus()
  print(string.format("Knowledge: %d surface, %d deep. Act II %s. Finale %s.",
    Knowledge.surfaceKnownCount(), Knowledge.deepKnownCount(),
    Knowledge.actIIOpen() and "OPEN" or "closed",
    Knowledge.finaleAttemptable() and "ATTEMPTABLE" or (Knowledge.canAssembleFinale() and "assemblable" or "locked")))
  local locs = guarded("scan", Board.locationCards) or {}
  local n = 0
  for _, l in ipairs(locs) do
    if l.locId then
      n = n + 1
      local d = Locations.describe(l.locId)
      print(string.format("  %-22s face=%s%s", d.name, d.face, d.sealed and " (SEALED)" or ""))
    end
  end
  if n == 0 then print("  (no campaign location cards on the table)") end
end

--------------------------------------------------------------------- harness --

local function check(name, cond, P, F)
  if cond then print("[PASS] " .. name); return P + 1, F
  else print("[FAIL] " .. name); return P, F + 1 end
end

function runStillHourTests()
  local P, F = 0, 0
  -- the harness drives the real modules; keep the live campaign and put it back
  local snapshot = CampaignState.serialize()
  print("──────── THE STILL HOUR — in-engine tests ────────")

  local c3 = Constants.forCount(3)
  P, F = check("reset 18 / appointed 12 at 3p", c3.resetThreshold == 18 and c3.appointedThreshold == 12, P, F)
  P, F = check("contest target 12 at 3p (CO-001 4*n)", c3.contestTarget == 12, P, F)

  local bag = { count = 0 }
  bag.setBaselineStatic = function(m) bag.count = m end
  CampaignState.init(3); Dissonance.syncBag(bag)
  P, F = check("Calm -> 0 [static]; Appointed Unseen", bag.count == 0 and Appointed.stage() == 0, P, F)
  Dissonance.raise(6, bag)
  P, F = check("Glitch -> 1 [static]; Appointed Sensed (1)", bag.count == 1 and Appointed.stage() == 1, P, F)
  local info = Dissonance.raise(6, bag)
  P, F = check("Noticed -> 2 [static]; Appointed Arrived (3)", bag.count == 2 and info.appointedStage == 3, P, F)
  local before = CampaignState.getDissonance(); Dissonance.onStaticRevealed(bag)
  P, F = check("[static] reveal raises Dissonance", CampaignState.getDissonance() == before + 1, P, F)

  -- the real adapter with no chaos bag reachable degrades to a virtual count
  local vbag = ChaosBag.new()
  vbag.findBag = function() return nil end
  vbag.setBaselineStatic(2); vbag.addStatic(1)
  P, F = check("virtual [static] bag tracks baseline + temporary", vbag.count == 3 and vbag.target() == 3, P, F)

  -- P5: staged Approach via the clock, Hold Back, undefeatable.
  CampaignState.init(3)
  Hourglass.advance(4, {})  -- reach Hour V -> Sensed
  P, F = check("Hour V -> Appointed Sensed (1)", Appointed.stage() == 1, P, F)
  Hourglass.advance(3, {})  -- reach Hour VIII -> Arrived
  P, F = check("Hour VIII -> Appointed Arrived (3)", Appointed.stage() == 3, P, F)
  local dBefore = CampaignState.getDissonance()
  local atk = Appointed.onAttack({})
  P, F = check("Arrived attacks 2/2 and raises Dissonance",
    atk.damage == 2 and atk.horror == 2 and CampaignState.getDissonance() == dBefore + 1, P, F)
  local hourBefore = CampaignState.getHour()
  local newStage = Appointed.holdBack({})
  P, F = check("Hold Back drops one stage and rewinds one Hour",
    newStage == 2 and CampaignState.getHour() == hourBefore - 1, P, F)
  P, F = check("Appointed cannot be defeated", Appointed.attemptDefeat() == false, P, F)
  local restored = false
  Appointed.onRemovalAttempt({ returnToPlay = function() restored = true end })
  P, F = check("removing a manifest Appointed puts it back", restored, P, F)
  CampaignState.init(3); CampaignState.advanceAppointed(1)
  P, F = check("Sensed figure deals no attack damage", Appointed.onAttack({}).damage == 0, P, F)
  P, F = check("a Sensed figure does not hunt", Appointed.hunt({ moveTowardPrey = function() return true end }) == false, P, F)

  CampaignState.init(3)
  P, F = check("once-per-loop free at node A", LoopFlags.use("igetout:White") == true, P, F)
  P, F = check("blocked on reuse", LoopFlags.use("igetout:White") == false, P, F)

  CampaignState.bankMemory(14); CampaignState.unlockFact("the-thirteenth-toll")
  CampaignState.addYears("sthrelias", 3); CampaignState.raiseDissonance(11); CampaignState.setHour(7)
  LoopFlags.recordTest("combat"); CampaignState.reset()
  P, F = check("Memory persists across reset", CampaignState.getBankedMemory() == 14, P, F)
  P, F = check("Knowledge persists across reset", CampaignState.knows("the-thirteenth-toll"), P, F)
  P, F = check("Years persist across reset", CampaignState.getYears("sthrelias") == 3, P, F)
  P, F = check("Dissonance dropped to scar (1)", CampaignState.getDissonance() == 1, P, F)
  P, F = check("Hourglass reset to Hour I", CampaignState.getHour() == 1, P, F)
  P, F = check("once-per-loop flags cleared", not CampaignState.isFlagSet("igetout:White"), P, F)
  P, F = check("Muscle Memory sees last-loop combat", LoopFlags.muscleMemoryUpgraded("combat"), P, F)

  CampaignState.bankMemory(30); CampaignState.startLoop()
  P, F = check("Memory soft-capped to 18 at loop start", CampaignState.getBankedMemory() == 18, P, F)
  local blob = CampaignState.serialize()
  CampaignState.init(3); CampaignState.deserialize(blob)
  P, F = check("serialize round-trip (real TTS JSON)", CampaignState.getBankedMemory() == 18
    and CampaignState.knows("the-thirteenth-toll"), P, F)

  CampaignState.init(3); CampaignState.bankMemory(10)
  P, F = check("level-3 upgrade debits 3", CampaignState.purchaseUpgrade(3) and CampaignState.getBankedMemory() == 7, P, F)
  P, F = check("Recollection debits memoryCost 5", CampaignState.purchaseRecollection(5) and CampaignState.getBankedMemory() == 2, P, F)
  P, F = check("cannot overdraw the pool", (CampaignState.purchaseUpgrade(4) == false) and CampaignState.getBankedMemory() == 2, P, F)

  CampaignState.init(3)
  local reached = {}
  local ctx = { onHourReached = function(h) reached[#reached + 1] = h end }
  Hourglass.advance(3, ctx)
  P, F = check("advance resolves Hours II,III,IV", reached[1] == 2 and reached[2] == 3 and reached[3] == 4, P, F)
  CampaignState.init(3); CampaignState.unlockFact("the-hour-was-wrong"); reached = {}
  Hourglass.advance(4, ctx)
  local sawIV = false
  for _, h in ipairs(reached) do if h == 4 then sawIV = true end end
  P, F = check("'The Hour Was Wrong' removes Hour IV", not sawIV, P, F)

  P, F = check("aging brackets 5/10/15 -> Weathered/Elder/Ancient",
    Aging.bracketForYears(5) == "Weathered" and Aging.bracketForYears(10) == "Elder"
    and Aging.bracketForYears(15) == "Ancient", P, F)

  -- P6: location fact-toggles + Knowledge gates.
  CampaignState.init(3)
  P, F = check("Lantern Room front until lamp fact", Locations.activeFace("lantern-room") == "front", P, F)
  CampaignState.unlockFact("the-lamp-was-never-lit")
  P, F = check("Lantern Room flips to back with the fact", Locations.activeFace("lantern-room") == "back", P, F)
  P, F = check("Sealed Study sealed until both facts", Locations.isSealed("sealed-study"), P, F)
  CampaignState.unlockFact("what-the-almanac-hid"); CampaignState.unlockFact("the-vote-that-never-ends")
  P, F = check("Sealed Study opens with both facts", Locations.isOpen("sealed-study"), P, F)
  P, F = check("location cards resolve by metadata id",
    Locations.idForCard("sthr-loc-lanternroom") == "lantern-room" and Locations.idForCard("sthr-loc-well") == "the-well"
    and Locations.idForCard("sthrelias") == nil, P, F)
  CampaignState.init(3)
  CampaignState.unlockFact("the-lamp-was-never-lit"); CampaignState.unlockFact("the-thirteenth-toll")
  CampaignState.unlockFact("the-road-remembers")
  P, F = check("Act II opens at 3 surface facts", Knowledge.actIIOpen(), P, F)
  CampaignState.unlockFact("the-appointeds-name"); CampaignState.unlockFact("the-vote-that-never-ends")
  CampaignState.unlockFact("the-hour-was-wrong")
  P, F = check("finale assembles with name+vote+one deep", Knowledge.assembleFinale() and Knowledge.finaleAttemptable(), P, F)

  -- Victory (Memory): once per campaign per Named enemy; survives resets.
  CampaignState.init(3)
  P, F = check("Victory claims once and banks its Memory",
    CampaignState.claimVictory("sthr-bellringer", 2) and CampaignState.getBankedMemory() == 2
    and CampaignState.claimVictory("sthr-bellringer", 2) == false, P, F)
  CampaignState.reset()
  P, F = check("Victory log survives a reset", CampaignState.isVictoryClaimed("sthr-bellringer"), P, F)

  -- P7: aging stat drift + interlude spend.
  local base = { wil = 5, int = 5, com = 1, agi = 3, health = 5, sanity = 8 }
  CampaignState.init(3); CampaignState.addYears("sthrayako", 14)
  -- interlude pushes 14 -> 15 (Ancient) and locks the drift choice
  Aging.applyInterlude("sthrayako", {}, { physical = "combat", mental = "intellect" })
  local st = Aging.applyDriftToStats(base, "sthrayako")
  P, F = check("Ancient drift: int 5->7, health/sanity -1, com floored at 1",
    st.int == 7 and st.health == 4 and st.sanity == 7 and st.com == 1, P, F)
  CampaignState.init(3); CampaignState.bankMemory(6)
  P, F = check("Interlude buys Recollection at memoryCost (longwayround=2)",
    Interlude.buyRecollection("sthr-longwayround") and CampaignState.getBankedMemory() == 4, P, F)
  P, F = check("Interlude buys level-3 upgrade (=3)",
    Interlude.buyUpgrade(3) and CampaignState.getBankedMemory() == 1, P, F)
  P, F = check("Interlude rejects unaffordable purchase", Interlude.buyRecollection("sthr-hourlearnedname") == false, P, F)

  -- Aging: leaning derived from the investigator's own tallies
  CampaignState.init(3)
  CampaignState.addTally("sthrcass", "raises", 3)
  P, F = check("3 Dissonance raises = leaned on the loop (+1 Year)",
    Interlude.leanedOnLoop("sthrcass") and Interlude.age("sthrcass", {}).yearsGained == 2, P, F)

  -- Prey + on-card Memory
  CampaignState.init(3)
  CampaignState.addOnCardMemory("sthrcass", 2); CampaignState.addOnCardMemory("sthrelias", 3)
  P, F = check("prey is the investigator with the most on-card Memory",
    Appointed.prey(CampaignState.onCardMemoryMap()) == "sthrelias", P, F)
  P, F = check("interlude banks on-card Memory", Interlude.bankOnCard() == 5 and CampaignState.getBankedMemory() == 5, P, F)

  print(string.format("──────── RESULT: %d passed, %d failed ────────", P, F))
  pcall(broadcastToAll, string.format("Still Hour tests: %d passed, %d failed", P, F),
    F == 0 and { 0.2, 1, 0.2 } or { 1, 0.3, 0.3 })
  -- Put the live campaign back exactly as it was before testing.
  CampaignState.init(CampaignState.constants().investigators)
  CampaignState.deserialize(snapshot)
  refreshControl()
  -- returned to Object.call() so automated runs (tools/tts_relay) read the tally
  return { passed = P, failed = F }
end
