-- Offline smoke test for the StillHour Lua modules.
-- Stubs TTS's require() (path-based module loader) and a Lua-literal JSON so the
-- state manager's serialize/deserialize contract can be exercised without TTS.
-- Run: lua5.4 pipeline/lua_smoketest.lua   (from repo root)

-- ---- minimal module loader for "StillHour/X" -> src/StillHour/X.ttslua ----
local cache = {}
local realRequire = require
function require(name)
  if cache[name] then return cache[name] end
  local path = "src/" .. name:gsub("%.", "/") .. ".ttslua"
  local chunk = assert(loadfile(path))
  local mod = chunk()
  cache[name] = mod
  return mod
end

-- ---- Lua-literal encoder/decoder standing in for TTS's JSON ----
local function encode(v, seen)
  local t = type(v)
  if t == "number" or t == "boolean" then return tostring(v) end
  if t == "string" then return string.format("%q", v) end
  if t == "table" then
    local parts = {}
    for k, val in pairs(v) do
      local key
      if type(k) == "number" then key = "[" .. k .. "]" else key = "[" .. string.format("%q", k) .. "]" end
      parts[#parts + 1] = key .. "=" .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. t)
end
JSON = {
  encode = function(v) return encode(v) end,
  decode = function(s) return assert(load("return " .. s))() end,
}

-- ---- test scaffolding ----
local passed, failed = 0, 0
local function check(name, cond)
  if cond then passed = passed + 1; print("  PASS  " .. name)
  else failed = failed + 1; print("  FAIL  " .. name) end
end

local Constants = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")
local Dissonance = require("StillHour/Dissonance")
local LoopFlags = require("StillHour/LoopFlags")
local Hourglass = require("StillHour/Hourglass")
local Aging = require("StillHour/Aging")
local Appointed = require("StillHour/Appointed")
local Knowledge = require("StillHour/Knowledge")
local Locations = require("StillHour/Locations")
local Interlude = require("StillHour/Interlude")

-- A fake chaos-bag adapter that records the baseline static count.
local function fakeBag()
  return { baseline = 0, setBaselineStatic = function(self, n) end,
           _set = 0 }
end
local bag = { count = 0 }
bag.setBaselineStatic = function(n) bag.count = n end

print("== Constants (3-player baseline) ==")
local c3 = Constants.forCount(3)
check("reset threshold = 18", c3.resetThreshold == 18)
check("appointed threshold = 12", c3.appointedThreshold == 12)
check("memory cap = 18", c3.memoryCap == 18)
-- CO-001: finale contest target = 4 x investigators (8 / 12 / 16 at 2 / 3 / 4p).
check("contest target = 12 at n=3", c3.contestTarget == 12)
check("contest target = 8 at n=2", Constants.forCount(2).contestTarget == 8)
check("contest target = 16 at n=4", Constants.forCount(4).contestTarget == 16)
check("scar cap = 6", c3.scarCap == 6)
check("band of 5 is Calm", Constants.bandFor(5, 3) == "Calm")
check("band of 6 is Glitch", Constants.bandFor(6, 3) == "Glitch")
check("band of 12 is Noticed", Constants.bandFor(12, 3) == "Noticed")
check("solo override 6/9", Constants.forCount(1).resetThreshold == 9 and Constants.forCount(1).appointedThreshold == 6)

print("== P3: Dissonance bands drive the [static] baseline ==")
CampaignState.init(3)
Dissonance.syncBag(bag)
check("Calm -> 0 static", bag.count == 0)
Dissonance.raise(6, bag) -- cross into Glitch (6)
check("Dissonance now 6", CampaignState.getDissonance() == 6)
check("Glitch -> 1 static", bag.count == 1)
local info = Dissonance.raise(6, bag) -- 12 -> Noticed
check("Noticed -> 2 static", bag.count == 2)
check("entering Noticed drives Appointed to Arrived (3)", info.appointedStage == 3)
Dissonance.reduce(7, bag) -- back to 5 -> Calm
check("reduce back to Calm -> 0 static", bag.count == 0 and CampaignState.getDissonance() == 5)
check("reducing Dissonance does NOT lower the Appointed (ratchet up only)", CampaignState.getAppointedStage() == 3)

print("== P3: revealing [static] raises Dissonance ==")
local before = CampaignState.getDissonance()
Dissonance.onStaticRevealed(bag)
check("static reveal +1 Dissonance", CampaignState.getDissonance() == before + 1)

print("== P4: once-per-loop flag persists across node travel, clears on reset ==")
CampaignState.init(3)
check("flag free at node A", LoopFlags.use("igetout:White") == true)
check("flag used again at node A -> blocked", LoopFlags.use("igetout:White") == false)
-- "travel to node B" = no reset; flag must still be blocked
check("flag still blocked at node B (same loop)", LoopFlags.isUsed("igetout:White") == true)

print("== P4/P2: Muscle Memory reads previous-loop test types ==")
LoopFlags.recordTest("combat")
check("combat not yet 'last loop'", LoopFlags.muscleMemoryUpgraded("combat") == false)

print("== P2: reset persists Memory/Knowledge/Years, drops Dissonance to scar, clears flags ==")
CampaignState.bankMemory(14)
CampaignState.unlockFact("the-thirteenth-toll")
CampaignState.addYears("sthr-elias", 3)
CampaignState.raiseDissonance(11)
CampaignState.setHour(7)
CampaignState.reset() -- loop 1 completed
check("Memory persists across reset", CampaignState.getBankedMemory() == 14)
check("Knowledge persists across reset", CampaignState.knows("the-thirteenth-toll") == true)
check("Years persist across reset", CampaignState.getYears("sthr-elias") == 3)
check("Dissonance dropped to scar (1)", CampaignState.getDissonance() == 1)
check("Hourglass reset to Hour I", CampaignState.getHour() == 1)
check("once-per-loop flags cleared", CampaignState.isFlagSet("igetout:White") == false)
check("Muscle Memory now sees last-loop combat", LoopFlags.muscleMemoryUpgraded("combat") == true)

print("== P2: soft cap applied at loop start ==")
CampaignState.bankMemory(30) -- 14 + 30 = 44, uncapped until startLoop
CampaignState.startLoop()
check("banked Memory capped to 18 at loop start", CampaignState.getBankedMemory() == 18)

print("== P2: serialize / deserialize round-trip ==")
local blob = CampaignState.serialize()
CampaignState.init(3) -- wipe
check("wiped Memory is 0", CampaignState.getBankedMemory() == 0)
CampaignState.deserialize(blob)
check("restored Memory = 18", CampaignState.getBankedMemory() == 18)
check("restored Knowledge", CampaignState.knows("the-thirteenth-toll") == true)
check("restored Years", CampaignState.getYears("sthr-elias") == 3)

print("== CO-001: Memory is experience — level-ups (=level) and Recollections (memoryCost) ==")
CampaignState.init(3)
CampaignState.bankMemory(10)
check("upgrade to level 3 debits exactly 3", CampaignState.purchaseUpgrade(3) == true and CampaignState.getBankedMemory() == 7)
check("Recollection debits its memoryCost (5)", CampaignState.purchaseRecollection(5) == true and CampaignState.getBankedMemory() == 2)
check("cannot overdraw the pool (need 4, have 2)", CampaignState.purchaseUpgrade(4) == false and CampaignState.getBankedMemory() == 2)
check("both wrappers share one pool", CampaignState.spendMemory(2) == true and CampaignState.getBankedMemory() == 0)

print("== P6: a big Skip resolves intervening Hours; 'The Hour Was Wrong' removes Hour IV ==")
CampaignState.init(3)
local reached = {}
local ctx = { onHourReached = function(h) reached[#reached + 1] = h end }
Hourglass.advance(3, ctx) -- I -> IV, resolving II, III, IV
check("advancing resolved Hours II,III,IV", reached[1] == 2 and reached[2] == 3 and reached[3] == 4)
CampaignState.init(3)
CampaignState.unlockFact("the-hour-was-wrong")
reached = {}
Hourglass.advance(4, ctx) -- should step over IV
local sawIV = false
for _, h in ipairs(reached) do if h == 4 then sawIV = true end end
check("Hour IV skipped when 'The Hour Was Wrong' known", sawIV == false)
-- With IV removed the clock is I,II,III,V,VI,...; 4 steps from I lands on VI
-- (II,III,V,VI) — a removed Hour is stepped over, it does not consume a step.
check("landed on Hour VI (IV stepped over)", CampaignState.getHour() == 6)

print("== P7: Aging brackets + drift ==")
check("years 4 -> Prime", Aging.bracketForYears(4) == "Prime")
check("years 5 -> Weathered", Aging.bracketForYears(5) == "Weathered")
check("years 10 -> Elder", Aging.bracketForYears(10) == "Elder")
check("years 15 -> Ancient", Aging.bracketForYears(15) == "Ancient")
check("clean+defeated+leaned = +3 years", Aging.computeYearsGained({ defeated = true, leanedOnLoop = true }) == 3)
CampaignState.init(3)
CampaignState.addYears("sthr-ayako", 4) -- start this interlude at Prime edge (4)
-- Interlude pushes 4 -> 7 (Weathered); the locked drift choice is applied now.
local r = Aging.applyInterlude("sthr-ayako", { defeated = true, leanedOnLoop = true },
  { physical = "combat", mental = "intellect" })
check("crossed into Weathered", r.bracket == "Weathered" and r.bracketChanged == true)
check("locked mental skill = intellect", r.drift.mentalSkill == "intellect")
check("locked physical skill = combat", r.drift.physicalSkill == "combat")
check("Weathered mental delta +1", r.drift.skillDeltas.mental == 1)
CampaignState.addYears("sthr-ayako", 4) -- push 7 -> 11 (Elder)
local drift = Aging.driftFor("sthr-ayako")
check("Elder mental delta +2", drift.skillDeltas.mental == 2)
check("Elder max health -1", drift.maxHealthDelta == -1)
check("Elder starts loop with 1 Memory", drift.startLoopMemory == 1)
check("Elder keeps locked mental skill = intellect", drift.mentalSkill == "intellect")

print("== P5: The Appointed — staged, clock-driven Approach (CO-002) ==")
CampaignState.init(3)
check("starts Unseen (0)", Appointed.stage() == 0)
-- Clock drivers ratchet the Approach up.
Hourglass.advance(4, {}) -- reach Hour V
check("Hour V -> Sensed (>=1)", Appointed.stage() == 1)
Hourglass.advance(2, {}) -- reach Hour VII
check("Hour VII -> Emerging (>=2)", Appointed.stage() == 2)
Hourglass.advance(1, {}) -- reach Hour VIII
check("Hour VIII -> Arrived (3)", Appointed.stage() == 3)
-- Ratchets up only: a lower driver never lowers it.
CampaignState.advanceAppointed(1)
check("advanceAppointed only ratchets up", Appointed.stage() == 3)
check("clamps at 3", CampaignState.advanceAppointed(9) == 3)
-- Arrived attack: 2/2 + raise Dissonance; Hold Back drops one stage + rewinds one Hour.
local dBefore = CampaignState.getDissonance()
local atk = Appointed.onAttack({})
check("Arrived attacks 2/2", atk.damage == 2 and atk.horror == 2)
check("Arrived attack raises Dissonance", CampaignState.getDissonance() == dBefore + 1)
local hourBefore = CampaignState.getHour()
local newStage = Appointed.holdBack({})
check("Hold Back drops exactly one stage", newStage == 2)
check("Hold Back rewinds exactly one Hour", CampaignState.getHour() == hourBefore - 1)
-- Sensed figure deals no attack damage; undefeatable; reset -> 0.
CampaignState.init(3); CampaignState.advanceAppointed(1)
check("Sensed figure deals no attack damage", Appointed.onAttack({}).damage == 0)
check("cannot be defeated (defeat-replacement)", Appointed.attemptDefeat() == false)
check("clamps at 0 via pushBack", (function() CampaignState.pushBackAppointed(); return CampaignState.pushBackAppointed() end)() == 0)
CampaignState.advanceAppointed(2)
CampaignState.reset()
check("reset() zeroes the Approach", Appointed.stage() == 0)
-- Dissonance-band driver: entering Glitch -> Sensed, Noticed -> Arrived.
CampaignState.init(3)
Dissonance.raise(6, {}) -- into Glitch
check("entering Glitch -> Sensed (1)", Appointed.stage() == 1)
Dissonance.raise(6, {}) -- into Noticed
check("entering Noticed -> Arrived (3)", Appointed.stage() == 3)
-- Persists across serialize/deserialize and node travel (no reset).
CampaignState.advanceAppointed(3)
local blob2 = CampaignState.serialize()
CampaignState.init(3)
CampaignState.deserialize(blob2)
check("Approach stage survives serialize/deserialize", Appointed.stage() == 3)

print("== Victory (Memory): once per campaign per named enemy ==")
CampaignState.init(3)
check("first defeat claims Victory and banks its Memory",
  CampaignState.claimVictory("sthr-bellringer", 2) == true and CampaignState.getBankedMemory() == 2)
check("second defeat of the same name banks nothing",
  CampaignState.claimVictory("sthr-bellringer", 2) == false and CampaignState.getBankedMemory() == 2)
CampaignState.reset() -- the night repeats; the Named return...
check("Victory claim survives a reset (log, not board state)",
  CampaignState.isVictoryClaimed("sthr-bellringer") == true)
check("...and still cannot be re-claimed next loop",
  CampaignState.claimVictory("sthr-bellringer", 2) == false and CampaignState.getBankedMemory() == 2)
check("a different Named enemy claims independently",
  CampaignState.claimVictory("sthr-wearssheriff", 3) == true and CampaignState.getBankedMemory() == 5)
local vblob = CampaignState.serialize()
CampaignState.init(3)
CampaignState.deserialize(vblob)
check("Victory log survives serialize/deserialize",
  CampaignState.isVictoryClaimed("sthr-bellringer") and CampaignState.isVictoryClaimed("sthr-wearssheriff"))

print("== P6: location fact-toggles + Knowledge gates ==")
CampaignState.init(3)
check("Lantern Room starts on its front", Locations.activeFace("lantern-room") == "front")
CampaignState.unlockFact("the-lamp-was-never-lit")
check("Lantern Room flips to back when lamp fact known", Locations.activeFace("lantern-room") == "back")
check("Flooded Crypt sealed until the Toll", Locations.isSealed("flooded-crypt") == true)
CampaignState.unlockFact("the-thirteenth-toll")
check("Flooded Crypt opens once the Toll is known", Locations.isOpen("flooded-crypt") == true)
check("Sealed Study needs BOTH facts", Locations.isSealed("sealed-study") == true)
CampaignState.unlockFact("what-the-almanac-hid")
check("Sealed Study still sealed with only one fact", Locations.isSealed("sealed-study") == true)
CampaignState.unlockFact("the-vote-that-never-ends")
check("Sealed Study opens with both facts", Locations.isOpen("sealed-study") == true)
check("a plain location has no back", Locations.activeFace("winding-stair") == "front")
-- Knowledge gates
CampaignState.init(3)
check("Act II closed at 0 surface facts", Knowledge.actIIOpen() == false)
CampaignState.unlockFact("the-lamp-was-never-lit")
CampaignState.unlockFact("the-thirteenth-toll")
CampaignState.unlockFact("the-road-remembers")
check("Act II opens at 3 surface facts", Knowledge.actIIOpen() == true)
check("surface count = 3", Knowledge.surfaceKnownCount() == 3)
-- Finale assembly: name + vote + one other deep
CampaignState.unlockFact("the-appointeds-name")
CampaignState.unlockFact("the-vote-that-never-ends")
check("cannot assemble finale without a third deep fact", Knowledge.canAssembleFinale() == false)
CampaignState.unlockFact("the-hour-was-wrong")
check("can assemble finale with name+vote+one other deep", Knowledge.canAssembleFinale() == true)
check("assembleFinale unlocks the-way-the-night-breaks", Knowledge.assembleFinale() == true)
check("finale now attemptable", Knowledge.finaleAttemptable() == true)
check("assembleFinale is idempotent", Knowledge.assembleFinale() == false)

print("== P7: aging stat drift + interlude spend ==")
local base = { wil = 5, int = 5, com = 1, agi = 3, health = 5, sanity = 8 } -- Ayako-ish
CampaignState.init(3)
local prime = Aging.applyDriftToStats(base, "sthr-ayako")
check("Prime: no stat drift", prime.int == 5 and prime.com == 1 and prime.health == 5)
CampaignState.addYears("sthr-ayako", 4)
Aging.applyInterlude("sthr-ayako", { defeated = true, leanedOnLoop = true }, { physical = "combat", mental = "intellect" }) -- ->7 Weathered
local weathered = Aging.applyDriftToStats(base, "sthr-ayako")
check("Weathered: mental +1 (int 5->6)", weathered.int == 6)
check("Weathered: physical -1 floored (com 1 stays 1)", weathered.com == 1)
CampaignState.addYears("sthr-ayako", 8) -- ->15 Ancient
local ancient = Aging.applyDriftToStats(base, "sthr-ayako")
check("Ancient: mental +2 (int 5->7)", ancient.int == 7)
check("Ancient: -1 max health and -1 max sanity", ancient.health == 4 and ancient.sanity == 7)
-- Interlude spend (Memory as experience)
CampaignState.init(3)
CampaignState.bankMemory(10)
check("buy Recollection debits its memoryCost (longwayround=2)",
  Interlude.buyRecollection("sthr-longwayround") == true and CampaignState.getBankedMemory() == 8)
check("buy level-3 upgrade debits 3", Interlude.buyUpgrade(3) == true and CampaignState.getBankedMemory() == 5)
check("unknown Recollection id is rejected", Interlude.buyRecollection("nope") == false)
check("illegal upgrade level rejected", Interlude.buyUpgrade(6) == false)
check("cannot overdraw (need 5-cost Recollection, have 5 -> ok; then 1 -> fail)",
  Interlude.buyRecollection("sthr-hourlearnedname") == true and CampaignState.getBankedMemory() == 0
  and Interlude.buyUpgrade(1) == false)
-- beginNextLoop enforces the soft cap
CampaignState.bankMemory(30)
Interlude.beginNextLoop()
check("beginNextLoop caps Memory at 18", CampaignState.getBankedMemory() == 18)

print("")
print(string.format("RESULT: %d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
