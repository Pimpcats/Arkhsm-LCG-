-- THE STILL HOUR — control object entry script.
-- Appended by pipeline/bundle_mod.py AFTER the inlined module table, so the
-- local require() defined in the bundle preamble is in scope here. This is the
-- code that actually runs on the control token in Tabletop Simulator.

local Constants     = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")
local Dissonance    = require("StillHour/Dissonance")
local LoopFlags     = require("StillHour/LoopFlags")
local Hourglass     = require("StillHour/Hourglass")
local Aging         = require("StillHour/Aging")

-- A no-op chaos-bag adapter so the demo buttons never error before the real
-- SCED chaos-bag wiring is in place (Dissonance also tolerates bag == nil).
local demoBag = { count = 0 }
demoBag.setBaselineStatic = function(n) demoBag.count = n end

-------------------------------------------------------------------- lifecycle --

function onSave()
  return CampaignState.serialize()          -- TTS global JSON.encode
end

function onLoad(saved)
  CampaignState.deserialize(saved)          -- empty/nil -> fresh state
  Dissonance.syncBag(demoBag)

  local defs = {
    { "runStillHourTests", "Run Tests",    -1.1 },
    { "shStatus",          "Status",       -0.55 },
    { "shAdvanceHour",     "Advance Hour",  0.0 },
    { "shRaiseDissonance", "+1 Dissonance", 0.55 },
    { "shReset",           "Reset Loop",    1.1 },
  }
  for _, d in ipairs(defs) do
    self.createButton({
      click_function = d[1], function_owner = self, label = d[2],
      position = { d[3], 0.3, 1.4 }, rotation = { 0, 0, 0 },
      width = 620, height = 360, font_size = 110,
      color = { 0.15, 0.13, 0.2 }, font_color = { 0.95, 0.9, 0.7 },
    })
  end
  print("THE STILL HOUR control ready. Investigators = " ..
    CampaignState.constants().investigators .. ". Click 'Run Tests' to verify the build.")
end

------------------------------------------------------------------ play/console --

function shStatus()
  local c = CampaignState.constants()
  print(string.format(
    "STILL HOUR | loop %d | Memory %d/%d | Dissonance %d/%d (%s) | Hour %s | contest target %d",
    CampaignState.getLoopsCompleted(), CampaignState.getBankedMemory(), c.memoryCap,
    CampaignState.getDissonance(), c.resetThreshold, CampaignState.band(),
    Hourglass.HOUR_NAMES[CampaignState.getHour()] or "?", c.contestTarget))
end

function shAdvanceHour()
  Hourglass.advance(1, { log = function(h, name, msg)
    print(string.format("  Hour %d — %s: %s", h, name, msg))
  end, dissonance = Dissonance, bag = demoBag, onReset = function() shReset() end })
  shStatus()
end

function shRaiseDissonance()
  local info = Dissonance.raise(1, demoBag)
  print("Dissonance -> " .. info.value .. " (" .. info.band .. ")" ..
    (info.latecomerArriving and "  ** the Latecomer stirs **" or ""))
  if info.reachedReset then print("  Dissonance hit the reset threshold — the loop ends.") ; shReset() end
end

function shReset()
  CampaignState.reset()
  Dissonance.syncBag(demoBag)
  print("The night folds. Loop reset — Memory/Knowledge/Years kept; Dissonance dropped to the scar.")
  shStatus()
end

--------------------------------------------------------------------- harness --

local function check(name, cond, P, F)
  if cond then print("[PASS] " .. name); return P + 1, F
  else print("[FAIL] " .. name); return P, F + 1 end
end

function runStillHourTests()
  local P, F = 0, 0
  print("──────── THE STILL HOUR — in-engine tests ────────")

  local c3 = Constants.forCount(3)
  P, F = check("reset 18 / latecomer 12 at 3p", c3.resetThreshold == 18 and c3.latecomerThreshold == 12, P, F)
  P, F = check("contest target 12 at 3p (CO-001 4*n)", c3.contestTarget == 12, P, F)

  local bag = { count = 0 }
  bag.setBaselineStatic = function(m) bag.count = m end
  CampaignState.init(3); Dissonance.syncBag(bag)
  P, F = check("Calm -> 0 [static]", bag.count == 0, P, F)
  Dissonance.raise(6, bag)
  P, F = check("Glitch -> 1 [static]; Dissonance 6", bag.count == 1 and CampaignState.getDissonance() == 6, P, F)
  local info = Dissonance.raise(6, bag)
  P, F = check("Noticed -> 2 [static]; Latecomer arriving", bag.count == 2 and info.latecomerArriving, P, F)
  local before = CampaignState.getDissonance(); Dissonance.onStaticRevealed(bag)
  P, F = check("[static] reveal raises Dissonance", CampaignState.getDissonance() == before + 1, P, F)

  CampaignState.init(3)
  P, F = check("once-per-loop free at node A", LoopFlags.use("igetout:White") == true, P, F)
  P, F = check("blocked on reuse", LoopFlags.use("igetout:White") == false, P, F)

  CampaignState.bankMemory(14); CampaignState.unlockFact("the-thirteenth-toll")
  CampaignState.addYears("sthr-elias", 3); CampaignState.raiseDissonance(11); CampaignState.setHour(7)
  LoopFlags.recordTest("combat"); CampaignState.reset()
  P, F = check("Memory persists across reset", CampaignState.getBankedMemory() == 14, P, F)
  P, F = check("Knowledge persists across reset", CampaignState.knows("the-thirteenth-toll"), P, F)
  P, F = check("Years persist across reset", CampaignState.getYears("sthr-elias") == 3, P, F)
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

  print(string.format("──────── RESULT: %d passed, %d failed ────────", P, F))
  broadcastToAll(string.format("Still Hour tests: %d passed, %d failed", P, F),
    F == 0 and { 0.2, 1, 0.2 } or { 1, 0.3, 0.3 })
  -- Restore a clean, freshly-loaded state for play after testing.
  CampaignState.init(CampaignState.constants().investigators)
  Dissonance.syncBag(demoBag)
end
