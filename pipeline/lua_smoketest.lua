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
-- finale contest target = 5 at every investigator count (tuning 2026-09; was 4 x investigators, CO-001)
check("contest target = 5 at n=3", c3.contestTarget == 5)
check("contest target = 5 at n=1", Constants.forCount(1).contestTarget == 5)
check("contest target = 5 at n=4", Constants.forCount(4).contestTarget == 5)
check("scar cap = 6", c3.scarCap == 6)
check("band of 5 is Calm", Constants.bandFor(5, 3) == "Calm")
check("band of 6 is Glitch", Constants.bandFor(6, 3) == "Glitch")
check("band of 12 is Noticed", Constants.bandFor(12, 3) == "Noticed")
check("solo override 8/12", Constants.forCount(1).resetThreshold == 12 and Constants.forCount(1).appointedThreshold == 8)

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

print("== P4/P2: Muscle Memory reads this loop's test types (card: 'during this loop') ==")
check("no combat test yet this loop -> not upgraded", LoopFlags.muscleMemoryUpgraded("combat") == false)
LoopFlags.recordTest("combat")
check("a combat test earlier this loop -> upgraded", LoopFlags.muscleMemoryUpgraded("combat") == true)
check("another skill type is not upgraded", LoopFlags.muscleMemoryUpgraded("agility") == false)

print("== P2: reset persists Memory/Knowledge/Years, drops Dissonance to scar, clears flags ==")
CampaignState.bankMemory(14)
CampaignState.unlockFact("the-thirteenth-toll")
CampaignState.addYears("sthrelias", 3)
CampaignState.raiseDissonance(11)
CampaignState.setHour(7)
CampaignState.reset() -- loop 1 completed
check("Memory persists across reset", CampaignState.getBankedMemory() == 14)
check("Knowledge persists across reset", CampaignState.knows("the-thirteenth-toll") == true)
check("Years persist across reset", CampaignState.getYears("sthrelias") == 3)
check("Dissonance dropped to scar (1)", CampaignState.getDissonance() == 1)
check("Hourglass reset to Hour I", CampaignState.getHour() == 1)
check("once-per-loop flags cleared", CampaignState.isFlagSet("igetout:White") == false)
check("Muscle Memory: last loop's combat test does not count this loop", LoopFlags.muscleMemoryUpgraded("combat") == false)

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
check("restored Years", CampaignState.getYears("sthrelias") == 3)

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
CampaignState.addYears("sthrayako", 4) -- start this interlude at Prime edge (4)
-- Interlude pushes 4 -> 7 (Weathered); the locked drift choice is applied now.
local r = Aging.applyInterlude("sthrayako", { defeated = true, leanedOnLoop = true },
  { physical = "combat", mental = "intellect" })
check("crossed into Weathered", r.bracket == "Weathered" and r.bracketChanged == true)
check("locked mental skill = intellect", r.drift.mentalSkill == "intellect")
check("locked physical skill = combat", r.drift.physicalSkill == "combat")
check("Weathered mental delta +1", r.drift.skillDeltas.mental == 1)
CampaignState.addYears("sthrayako", 4) -- push 7 -> 11 (Elder)
local drift = Aging.driftFor("sthrayako")
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
check("Flooded Crypt stays closed in Part I, Toll or not", Locations.isSealed("flooded-crypt") == true)
CampaignState.setPartTwo(true)
check("Flooded Crypt opens once the Toll is known in Part II", Locations.isOpen("flooded-crypt") == true)
check("Sealed Study needs BOTH facts", Locations.isSealed("sealed-study") == true)
CampaignState.unlockFact("what-the-almanac-hid")
check("Sealed Study still sealed with only one fact", Locations.isSealed("sealed-study") == true)
CampaignState.unlockFact("the-vote-that-never-ends")
check("Sealed Study stays closed on facts alone (act 2a never became current)", Locations.isSealed("sealed-study") == true)
check("act 2a becomes current in Part II with both entries", Locations.markAlmanacActTwoCurrent() == true)
check("Sealed Study opens when The Appointed's Name becomes the current act", Locations.isOpen("sealed-study") == true)
CampaignState.reset()
check("a reset closes it again until act 2a is current again", Locations.isSealed("sealed-study") == true)
CampaignState.unlockFact("the-appointeds-name")
check("once The Appointed's Name is recorded it enters play open", Locations.isOpen("sealed-study") == true)
check("act 2a is not current again once its deep entry is recorded", Locations.markAlmanacActTwoCurrent() == false)
CampaignState.forgetFact("the-appointeds-name")
CampaignState.setPartTwo(false)
check("act 2a needs Part II", Locations.markAlmanacActTwoCurrent() == false)
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
local prime = Aging.applyDriftToStats(base, "sthrayako")
check("Prime: no stat drift", prime.int == 5 and prime.com == 1 and prime.health == 5)
CampaignState.addYears("sthrayako", 4)
Aging.applyInterlude("sthrayako", { defeated = true, leanedOnLoop = true }, { physical = "combat", mental = "intellect" }) -- ->7 Weathered
local weathered = Aging.applyDriftToStats(base, "sthrayako")
check("Weathered: mental +1 (int 5->6)", weathered.int == 6)
check("Weathered: physical -1 floored (com 1 stays 1)", weathered.com == 1)
CampaignState.addYears("sthrayako", 8) -- ->15 Ancient
local ancient = Aging.applyDriftToStats(base, "sthrayako")
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

print("== Board wiring: location cards resolve by metadata id ==")
check("sthr-loc-lanternroom -> lantern-room", Locations.idForCard("sthr-loc-lanternroom") == "lantern-room")
check("sthr-loc-townhallsteps -> town-hall-steps", Locations.idForCard("sthr-loc-townhallsteps") == "town-hall-steps")
check("leading 'the' is ignored (sthr-loc-well -> the-well)", Locations.idForCard("sthr-loc-well") == "the-well")
check("sealed study resolves", Locations.idForCard("sthr-loc-sealedstudy") == "sealed-study")
check("a module id passes straight through", Locations.idForCard("flooded-crypt") == "flooded-crypt")
check("a non-location Still Hour card is not a location", Locations.idForCard("sthrelias") == nil)
check("an unknown / foreign location is nil", Locations.idForCard("01129") == nil and Locations.idForCard(nil) == nil)
check("hasBack only where a fact flips it", Locations.hasBack("lantern-room") and not Locations.hasBack("nave"))

print("== Board wiring: farthest / toward on a location graph ==")
--   A - B - C - D      E (unconnected)
local g = { A = { "B" }, B = { "A", "C" }, C = { "B", "D" }, D = { "C" }, E = {} }
local dist = Locations.distances(g, { "A" })
check("BFS distances A->D = 3, E unreachable", dist.D == 3 and dist.B == 1 and dist.E == nil)
check("farthest from A is D (unreachable E ignored)", Locations.farthest(g, { "A" }) == "D")
check("farthest from B and C: A or D, tiebreak decides",
  Locations.farthest(g, { "B", "C" }, function(a, b) return a == "D" end) == "D")
check("no investigators: tiebreak picks among all", Locations.farthest(g, {}, function(a) return a == "E" end) == "E")
check("step from A toward D is B", Locations.stepToward(g, "A", "D") == "B")
check("step when already there is a no-op", Locations.stepToward(g, "C", "C") == "C")
check("step toward an unreachable location is nil", Locations.stepToward(g, "A", "E") == nil)

print("== Board wiring: Appointed hooks (hunt / undefeatable / card advance) ==")
CampaignState.init(3)
local moved = 0
local hctx = { moveTowardPrey = function() moved = moved + 1 end }
check("Unseen does not hunt", Appointed.hunt(hctx) == false and moved == 0)
CampaignState.advanceAppointed(1)
check("Sensed does not hunt", Appointed.hunt(hctx) == false and moved == 0)
CampaignState.advanceAppointed(2)
check("Emerging hunts (Hunter)", Appointed.hunt(hctx) == true and moved == 1)
local back = 0
check("removing it while manifest puts it back",
  Appointed.onRemovalAttempt({ returnToPlay = function() back = back + 1 end }) == true and back == 1)
CampaignState.init(3)
check("at Unseen it may leave the board", Appointed.onRemovalAttempt({ returnToPlay = function() back = back + 1 end }) == false and back == 1)
local placed = 0
local actx = { isOnBoard = function() return placed > 0 end, placeAtFarthest = function() placed = placed + 1 end }
check("a card advance from Unseen goes to Sensed and manifests", Appointed.advanceByCard(actx) == 1 and placed == 1)
check("a second card advance -> Emerging", Appointed.advanceByCard(actx) == 2 and placed == 1)
CampaignState.advanceAppointed(3)
check("card advance never exceeds Arrived", Appointed.advanceByCard(actx) == 3)
local removed = 0
actx.removeFromBoard = function() removed = removed + 1 ; placed = 0 end
CampaignState.init(3); CampaignState.advanceAppointed(1); CampaignState.setHour(5)
Appointed.holdBack(actx)
check("Hold Back to Unseen removes the figure from the board", removed == 1 and Appointed.stage() == 0)

print("== Prey: on-card Memory per investigator ==")
CampaignState.init(3)
CampaignState.addOnCardMemory("sthrelias", 2)
CampaignState.addOnCardMemory("sthrayako", 3)
CampaignState.addOnCardMemory("sthrcass", 3)
check("on-card Memory is per investigator", CampaignState.getOnCardMemory("sthrayako") == 3
  and CampaignState.getOnCardMemory("sthrbirdie") == 0)
check("on-card Memory never goes below 0", CampaignState.addOnCardMemory("sthrelias", -9) == 0)
local cands, most = Appointed.preyCandidates(CampaignState.onCardMemoryMap())
check("prey candidates = everyone tied for most", #cands == 2 and cands[1] == "sthrayako"
  and cands[2] == "sthrcass" and most == 3)
CampaignState.addOnCardMemory("sthrcass", 1)
check("a single most-Memory investigator is the prey", Appointed.prey(CampaignState.onCardMemoryMap()) == "sthrcass")
local blob2 = CampaignState.serialize()
CampaignState.init(3) ; CampaignState.deserialize(blob2)
check("on-card Memory survives save/load (node travel)", CampaignState.getOnCardMemory("sthrcass") == 4)
CampaignState.raiseDissonance(13) ; CampaignState.reset()
check("a reset keeps on-card Memory until the interlude banks it", CampaignState.getOnCardMemory("sthrcass") == 4)
check("the loop-end Dissonance is recorded for Aging", CampaignState.getLastLoopEndDissonance() == 13)
check("...and reads as ended in danger (>= 12 at 3p)", Interlude.loopEndedInDanger() == true)
local banked0 = CampaignState.getBankedMemory()
check("interlude banks all on-card Memory", Interlude.bankOnCard() == 7
  and CampaignState.getBankedMemory() == banked0 + 7 and CampaignState.getOnCardMemory("sthrcass") == 0)

print("== Aging: locked choice + Elder start-of-loop Memory ==")
CampaignState.init(3) ; CampaignState.addYears("sthrbirdie", 5)
check("Weathered without a choice needs one", Aging.needsChoice("sthrbirdie") == true)
check("lockChoice rejects a non-physical skill", Aging.lockChoice("sthrbirdie", "intellect", "willpower") == false)
check("lockChoice records the first choice", Aging.lockChoice("sthrbirdie", "agility", "willpower") == true
  and not Aging.needsChoice("sthrbirdie"))
check("the choice is locked", Aging.lockChoice("sthrbirdie", "combat", "intellect") == false
  and CampaignState.getBracket("sthrbirdie").physical == "agility")
local bs = Aging.applyDriftToStats({ wil = 2, int = 3, com = 3, agi = 5, health = 6, sanity = 7 }, "sthrbirdie")
check("locked drift applies (agi 5->4, wil 2->3)", bs.agi == 4 and bs.wil == 3 and bs.com == 3)
CampaignState.addYears("sthrbirdie", 5)   -- Elder
Interlude.beginNextLoop()
check("Elder begins the loop with 1 Memory on their card", CampaignState.getOnCardMemory("sthrbirdie") == 1)
check("a Prime investigator does not", CampaignState.getOnCardMemory("sthrelias") == 0)

print("== Aging: 'leaned on the loop' derived from per-investigator tallies ==")
CampaignState.init(3)
check("no tallies -> not leaned", Interlude.leanedOnLoop("sthrelias") == false)
CampaignState.addTally("sthrelias", "raises", 2)
check("2 Dissonance raises -> not leaned", Interlude.leanedOnLoop("sthrelias") == false)
CampaignState.addTally("sthrelias", "raises", 1)
check("3 Dissonance raises -> leaned", Interlude.leanedOnLoop("sthrelias") == true)
CampaignState.addTally("sthrcass", "spent", 3)
check("3 loop-power Memory -> not leaned", Interlude.leanedOnLoop("sthrcass") == false)
CampaignState.addTally("sthrcass", "spent", 1)
check("4 loop-power Memory -> leaned", Interlude.leanedOnLoop("sthrcass") == true)
check("tallies are per investigator", Interlude.leanedOnLoop("sthrbirdie") == false)
check("a tally never goes below 0", CampaignState.addTally("sthrbirdie", "raises", -5) == 0)
check("unknown tally kind is rejected", CampaignState.addTally("sthrbirdie", "bogus", 1) == nil)
local tblob = CampaignState.serialize()
CampaignState.init(3) ; CampaignState.deserialize(tblob)
check("tallies survive save/load", CampaignState.getTallies("sthrcass").spent == 4)
CampaignState.reset()
check("tallies survive the reset so the interlude can age with them", Interlude.leanedOnLoop("sthrelias") == true)
local ra = Interlude.age("sthrelias", { defeated = false, endedInDanger = false })
check("Interlude.age derives leaned (+1): 1 base + 1 = 2 years", ra.yearsGained == 2)
local rb = Interlude.age("sthrbirdie", {})
check("...and no +1 when not leaned", rb.yearsGained == 1)
check("an explicit condition still wins (logic callers)", Interlude.age("sthrayako", { leanedOnLoop = true }).yearsGained == 2)
Interlude.beginNextLoop()
check("tallies clear when the next loop begins", CampaignState.getTallies("sthrelias").raises == 0
  and Interlude.leanedOnLoop("sthrcass") == false)

print("== Board wiring: SCED adapter is inert without SCED ==")
local SCED = require("StillHour/SCED")
check("SCED absent offline", SCED.isPresent() == false)
check("no chaos bag offline", SCED.findChaosBag() == nil)
check("tokens can be touched when SCED is absent", SCED.canTouchChaosTokens() == true)
check("SCED spawn tracker calls are no-ops", SCED.markTokensSpawned("abc") == false and SCED.isInPlayArea({}) == nil)

print("== Board wiring: real chaos-bag adapter ==")
local ChaosBag = require("StillHour/ChaosBag")
-- a virtual bag (no table) tracks the count only
local vb = ChaosBag.new()
vb.setBaselineStatic(1) ; vb.addStatic(2)
check("virtual: baseline 1 + temporary 2 = 3", vb.count == 3 and vb.describe().mode == "virtual")
vb.clearTemporary()
check("virtual: temporary cleared at reset", vb.count == 1)
-- Hour VI with What the Almanac Hid: 1 fewer than the band, not a negative extra
local ab = ChaosBag.new()
ab.setBaselineStatic(1) ; ab.setAlmanac(true)
check("almanac: band 1 -> bag holds 0", ab.count == 0)
ab.addStatic(1)
check("almanac: a card-added token still joins (0 + 1)", ab.count == 1)
ab.removeStatic(1) ; ab.removeStatic(1)
check("removing temporary tokens never goes below the band rule", ab.count == 0 and ab.describe().extra == 0)
ab.setAlmanac(true)
check("almanac is idempotent (no stacking)", ab.count == 0)
ab.setBaselineStatic(2)
check("almanac: band 2 -> bag holds 1", ab.count == 1)
ab.clearTemporary()
check("almanac cleared at reset", ab.count == 2)

-- a physical "Chaos Bag" on a table (vanilla: no SCED)
local live = {}
local guidN = 0
local function fakeToken(data)
  guidN = guidN + 1
  local t = { guid = "tok" .. guidN, data = data }
  t.getGUID = function() return t.guid end
  t.hasTag = function(tag) for _, x in ipairs(data.Tags or {}) do if x == tag then return true end end return false end
  t.destruct = function() live[t.guid] = nil end
  live[t.guid] = t
  return t
end
local contents = {}
local chaos = { type = "Bag" }
chaos.getName = function() return "Chaos Bag" end
chaos.getDescription = function() return "" end
chaos.getPosition = function() return { x = 1, y = 1, z = 1 } end
chaos.getObjects = function()
  local l = {}
  for i, t in ipairs(contents) do l[i] = { guid = t.guid, name = "Static", index = i - 1, tags = t.data.Tags } end
  return l
end
chaos.putObject = function(t) contents[#contents + 1] = t end
chaos.takeObject = function(p)
  for i, t in ipairs(contents) do
    if t.guid == p.guid then
      table.remove(contents, i)
      if p.callback_function then p.callback_function(t) end
      return t
    end
  end
end
getObjects = function() return { chaos } end
getObjectFromGUID = function(g) return live[g] end
spawnObjectData = function(p) local t = fakeToken(p.data) ; p.callback_function(t) ; return t end
local pb = ChaosBag.new()
pb.setBaselineStatic(2)
check("table bag: 2 [static] spawned into the Chaos Bag", #contents == 2 and pb.describe().mode == "table")
check("spawned token is the tagged Custom_Tile", contents[1].data.Name == "Custom_Tile"
  and contents[1].data.CustomImage.CustomTile.Type == 2 and contents[1].hasTag("StillHourStatic"))
pb.addStatic(1)
check("temporary [static] adds a third", #contents == 3)
pb.setBaselineStatic(0)
check("band drop removes baseline tokens, keeps the temporary one", #contents == 1 and pb.physicalCount() == 1)
-- a reveal: someone draws our token out of the bag
local drawn = table.remove(contents, 1)
check("drawing it from the Chaos Bag is a reveal", pb.onLeave(chaos, drawn) == true)
check("our own removal is not a reveal", (function()
  local t = fakeToken(ChaosBag.tokenData()) ; contents[#contents + 1] = t
  pb.reconcile()  -- 1 target, 1 out + 1 in bag -> removes the in-bag one
  return #contents == 0 and pb.physicalCount() == 1
end)())
pb.setBaselineStatic(1)
check("a drawn token still counts (only the shortfall is added)", #contents == 1 and pb.physicalCount() == 2)
pb.onEnter(chaos, drawn) ; contents[#contents + 1] = drawn
check("returned token is counted once, in the bag", pb.physicalCount() == 2 and #contents == 2)
check("other containers never count as the chaos bag",
  pb.onLeave({ getName = function() return "Deck" end }, drawn) == false)

-- SCED present: the bag comes from Global.findChaosBag; edits wait while searched
local touchable = false
local retries = 0
Global = {
  getVar = function(k) if k == "MOD_VERSION" then return "4.9.2" end end,
  call = function(name)
    if name == "findChaosBag" then return chaos end
    if name == "canTouchChaosTokens" then return touchable end
  end,
}
getObjectFromGUID = function(g) if g == "123456" then return { call = function() return nil end } end return live[g] end
Wait = { time = function(fn) retries = retries + 1 end, frames = function(fn) fn() end }
check("SCED detected via Global MOD_VERSION + reference handler", SCED.isPresent() == true)
local sb = ChaosBag.new()
local n0 = #contents
sb.setBaselineStatic(n0 + 1)
check("SCED: bag untouched while someone searches it; retry scheduled", #contents == n0 and retries == 1)
touchable = true
sb.reconcile()
check("SCED: bag reconciled once touchable", #contents == n0 + 1 and sb.describe().mode == "sced")
Global, getObjects, getObjectFromGUID, spawnObjectData, Wait = nil, nil, nil, nil, nil
check("adapter falls back cleanly when the table goes away", ChaosBag.new().setBaselineStatic(2) == 2)

-- The Prologue (The First Hour) is not a loop: no Appointed, and its reset
-- counts no loop and leaves no scar.
CampaignState.init(3)
CampaignState.setPrologue(true)
check("prologue: a fresh campaign can start in the Prologue", CampaignState.inPrologue())
CampaignState.advanceAppointed(3)
check("prologue: nothing drives the Appointed", CampaignState.getAppointedStage() == 0)
CampaignState.raiseDissonance(4)
CampaignState.reset()
check("prologue: its reset counts no loop", CampaignState.getLoopsCompleted() == 0)
check("prologue: its reset leaves no scar", CampaignState.getDissonance() == 0)
check("prologue: afterwards the campaign is in Loop 1", not CampaignState.inPrologue())
CampaignState.advanceAppointed(1)
check("prologue: the Appointed is driven again from Loop 1", CampaignState.getAppointedStage() == 1)
CampaignState.reset()
check("prologue: Loop 1's reset counts as the first loop", CampaignState.getLoopsCompleted() == 1)

print("")
print("== Hour VI does not stack ==")
do
  local cnt = 0
  local c = { addStatic = function(n) cnt = cnt + n end, removeStatic = function() end,
              setAlmanac = function() cnt = cnt + 100 end }
  CampaignState.reset()
  local guard = 0
  while CampaignState.getHour() < 6 and guard < 20 do Hourglass.advance(1, c) ; guard = guard + 1 end
  local after = cnt
  check("Hour VI resolved once on the way", after > 0)
  Hourglass.rewind(1, c) ; Hourglass.advance(1, c)
  check("reaching Hour VI again after a rewind adds nothing", cnt == after)
end

print("== Banked Memory never goes below 0 ==")
CampaignState.init(3)
CampaignState.bankMemory(2)
check("removing more banked Memory than there is clamps at 0", CampaignState.bankMemory(-3) == 0
  and CampaignState.getBankedMemory() == 0)
check("a spend larger than the bank is refused (no change)", CampaignState.spendMemory(1) == false
  and CampaignState.getBankedMemory() == 0)
CampaignState.deserialize(JSON.encode({ version = 1, investigators = 3, bankedMemory = -4 }))
check("a save holding negative banked Memory loads as 0", CampaignState.getBankedMemory() == 0)
check("Borrowed Time costs 3 Memory", Interlude.recollectionCost("sthr-borrowedtime") == 3)

print("== Reset Loop: the loop-ended flag (guards a second Reset Loop) ==")
CampaignState.init(3)
check("a loop under way is not ended", CampaignState.isLoopEnded() == false)
CampaignState.reset()
check("a reset marks the loop ended", CampaignState.isLoopEnded() == true)
local leblob = CampaignState.serialize()
CampaignState.init(3) ; CampaignState.deserialize(leblob)
check("the loop-ended flag survives save/load", CampaignState.isLoopEnded() == true)
Interlude.beginNextLoop()
check("Begin Next Loop clears it", CampaignState.isLoopEnded() == false)
CampaignState.init(3) ; CampaignState.setPrologue(true) ; CampaignState.reset()
check("the Prologue's reset marks it too (Between Loops follows)", CampaignState.isLoopEnded() == true)
CampaignState.deserialize(JSON.encode({ version = 1, investigators = 3, loopsCompleted = 1 }))
check("an older save without the flag loads as a loop under way", CampaignState.isLoopEnded() == false)

print("== Ended in danger: decided at the reset with that loop's count ==")
CampaignState.init(4)                  -- 4p: Noticed from 16
CampaignState.raiseDissonance(13)
CampaignState.reset()
check("13 at 4 investigators is not danger", CampaignState.getLastLoopEndedInDanger() == false)
CampaignState.setInvestigatorCount(3)  -- someone leaves before Age: 3p Noticed is 12
check("changing Investigators before Age keeps the answer (no danger)", Interlude.loopEndedInDanger() == false)
CampaignState.init(2)                  -- 2p: Noticed from 8
CampaignState.raiseDissonance(9)
CampaignState.reset()
CampaignState.setInvestigatorCount(4)
check("9 at 2 investigators stays danger after changing to 4", Interlude.loopEndedInDanger() == true)
check("Age reads it: 1 base + 1 danger",
  Interlude.age("sthrelias", { endedInDanger = Interlude.loopEndedInDanger() }).yearsGained == 2)
CampaignState.deserialize(JSON.encode({ version = 1, investigators = 3, lastLoopEndDissonance = 12 }))
check("an older save falls back to the loop-end Dissonance (12 at 3p: danger)", Interlude.loopEndedInDanger() == true)
CampaignState.deserialize(JSON.encode({ version = 1, investigators = 3, lastLoopEndDissonance = 11 }))
check("...and 11 at 3p is not", Interlude.loopEndedInDanger() == false)

print("== Departed investigators: no start-of-loop Memory, nothing banked ==")
CampaignState.init(3)
CampaignState.addYears("sthrelias", 18)   -- aged out
CampaignState.addYears("sthrbirdie", 12)  -- Elder, in play
CampaignState.addYears("sthrcass", 11)    -- Elder, no longer in play
Interlude.beginNextLoop({ sthrbirdie = true, sthrelias = true })
check("an aged-out investigator (18 Years) gets no Elder/Ancient Memory", CampaignState.getOnCardMemory("sthrelias") == 0)
check("an Elder no longer in play gets none", CampaignState.getOnCardMemory("sthrcass") == 0)
check("an Elder in play begins with 1", CampaignState.getOnCardMemory("sthrbirdie") == 1)
CampaignState.init(3)
CampaignState.addYears("sthrelias", 18)
CampaignState.addOnCardMemory("sthrelias", 4) ; CampaignState.addOnCardMemory("sthrbirdie", 2)
CampaignState.addOnCardMemory("sthrcass", 3)
local bankedN, droppedN = Interlude.bankOnCard({ sthrbirdie = true, sthrelias = true })
check("bank on-card Memory banks only the investigators still in the campaign", bankedN == 2
  and CampaignState.getBankedMemory() == 2)
check("...and drops a departed investigator's Memory", droppedN == 7 and CampaignState.getOnCardMemory("sthrelias") == 0)
CampaignState.init(3) ; CampaignState.addYears("sthrelias", 18) ; CampaignState.addOnCardMemory("sthrelias", 2)
CampaignState.addOnCardMemory("sthrbirdie", 1)
check("with no board list, the Years rule alone decides", Interlude.bankOnCard() == 1)

print("== Band starts and scar cap at 1-4 investigators ==")
local expectBands = { [1] = { 3, 6, 3, 9 }, [2] = { 4, 8, 4, 12 }, [3] = { 6, 12, 6, 18 }, [4] = { 8, 16, 8, 24 } }
for n = 1, 4 do
  local cn, e = Constants.forCount(n), expectBands[n]
  check(string.format("%dp: Glitch from %d, Noticed from %d, scar cap %d, reset %d", n, e[1], e[2], e[3], e[4]),
    cn.bandGlitchStart == e[1] and cn.bandNoticedStart == e[2] and cn.scarCap == e[3] and cn.resetThreshold == e[4]
    and Constants.bandFor(e[1] - 1, n) == "Calm" and Constants.bandFor(e[1], n) == "Glitch"
    and Constants.bandFor(e[2], n) == "Noticed" and cn.appointedThreshold == e[2])
  CampaignState.init(n)
  for _ = 1, e[3] + 2 do
    CampaignState.raiseDissonance(e[4]) ; CampaignState.reset() ; CampaignState.setLoopEnded(false)
  end
  check(string.format("%dp: the scar stops at %d", n, e[3]), CampaignState.getDissonance() == e[3])
end

print("== Hour VI undo (a cancelled Hour VI) ==")
do
  local ub = ChaosBag.new()
  ub.findBag = function() return nil end
  local uctx = { addStatic = function(n) ub.addStatic(n) end, removeStatic = function(n) ub.removeStatic(n) end,
                 setAlmanac = function(on) ub.setAlmanac(on ~= false) end }
  CampaignState.init(3) ; ub.setBaselineStatic(1)
  Hourglass.advance(5, uctx)
  check("Hour VI adds 1 temporary Static (band 1 -> 2)", ub.count == 2 and Hourglass.hourSixResolved())
  check("undo takes it back and clears the once-per-loop flag", Hourglass.undoHourSix(uctx) == "static"
    and ub.count == 1 and not Hourglass.hourSixResolved())
  Hourglass.rewind(1, uctx) ; Hourglass.advance(1, uctx)
  check("after the undo, reaching Hour VI again resolves it", ub.count == 2)
  Hourglass.undoHourSix(uctx)
  check("a second undo with nothing applied is refused", Hourglass.undoHourSix(uctx) == nil and ub.count == 1)
  CampaignState.init(3) ; ub.clearTemporary() ; ub.setBaselineStatic(2)
  CampaignState.unlockFact("what-the-almanac-hid")
  Hourglass.advance(5, uctx)
  check("with What the Almanac Hid, Hour VI makes it 1 fewer (2 -> 1)", ub.count == 1 and ub.almanac == true)
  local ablob = CampaignState.serialize()
  CampaignState.init(3) ; CampaignState.deserialize(ablob)
  check("what Hour VI applied survives save/load", CampaignState.isFlagSet("hour-vi-almanac") == true)
  check("undo restores the band's count (setAlmanac false)", Hourglass.undoHourSix(uctx) == "almanac"
    and ub.count == 2 and ub.almanac == false and not Hourglass.hourSixResolved())
  Hourglass.rewind(1, uctx) ; Hourglass.advance(1, uctx)
  CampaignState.reset()
  check("a reset clears Hour VI's flags", not Hourglass.hourSixResolved() and not CampaignState.isFlagSet("hour-vi-almanac"))
end

print("== Hour IX in the finale ==")
do
  CampaignState.init(3)
  CampaignState.unlockFact("the-way-the-night-breaks")
  local said = {}
  local fctx = { onReset = function() said.reset = true end, onFinaleAttemptable = function() said.may = true end,
                 onFinaleEnds = function() said.ends = true end }
  CampaignState.setHour(8) ; Hourglass.advance(1, fctx)
  check("outside the finale, Hour IX offers the finale", said.may == true and not said.ends)
  said = {}
  CampaignState.setFinale(true) ; CampaignState.setHour(8) ; Hourglass.advance(1, fctx)
  check("in the finale, Hour IX ends the finale (contest not reached)", said.ends == true and not said.may and not said.reset)
  CampaignState.reset()
  check("a reset ends the finale", CampaignState.inFinale() == false)
end

print("== Knowledge pays Memory (once per entry, refunded on removal) ==")
CampaignState.init(3)
local n0, p0 = Knowledge.unlock("the-thirteenth-toll")
check("a surface entry pays 1 per investigator (3 at 3p)", n0 == true and p0 == 3 and CampaignState.getBankedMemory() == 3)
local n1, p1 = Knowledge.unlock("the-thirteenth-toll")
check("recording it again pays nothing", n1 == false and p1 == 0 and CampaignState.getBankedMemory() == 3)
local _, pd = Knowledge.unlock("the-hour-was-wrong")
check("a deep entry pays 3 per investigator (9 at 3p)", pd == 9 and CampaignState.getBankedMemory() == 12)
local _, pp = Knowledge.unlock("you-are-unstuck")
check("the prologue entry pays nothing", pp == 0 and CampaignState.getBankedMemory() == 12)
local _, pa = Knowledge.unlock("the-way-the-night-breaks")
check("the assembled entry pays nothing", pa == 0 and CampaignState.getBankedMemory() == 12)
CampaignState.setInvestigatorCount(2)
local _, p2 = Knowledge.unlock("the-road-remembers")
check("the current investigator count is used (surface at 2p = 2)", p2 == 2 and CampaignState.getBankedMemory() == 14)
local kblob = CampaignState.serialize()
CampaignState.init(3) ; CampaignState.deserialize(kblob)
check("what each entry paid survives save/load", CampaignState.getKnowledgePaid("the-hour-was-wrong") == 9)
local rem, refund = Knowledge.forget("the-hour-was-wrong")
check("removing an entry refunds what it paid", rem == true and refund == 9 and CampaignState.getBankedMemory() == 5
  and not CampaignState.knows("the-hour-was-wrong"))
check("removing it twice refunds nothing more", select(2, Knowledge.forget("the-hour-was-wrong")) == 0)
CampaignState.setInvestigatorCount(3)
check("recording it again pays again (net once)", select(2, Knowledge.unlock("the-hour-was-wrong")) == 9
  and CampaignState.getBankedMemory() == 14)
CampaignState.init(3) ; CampaignState.bankMemory(16)
Knowledge.unlock("the-keepers-ninth-death")
check("banked Memory may sit above the cap until the next loop begins (25 > 18)", CampaignState.getBankedMemory() == 25)
Interlude.beginNextLoop()
check("...and is reduced to 6n when it does", CampaignState.getBankedMemory() == 18)
CampaignState.init(3) ; CampaignState.bankMemory(1)
Knowledge.unlock("the-lamp-was-never-lit") ; CampaignState.spendMemory(4)
check("a refund never takes banked Memory below 0", select(2, Knowledge.forget("the-lamp-was-never-lit")) == 0
  and CampaignState.getBankedMemory() == 0)
check("re-ticking an entry whose Memory was spent pays nothing again",
  select(2, Knowledge.unlock("the-lamp-was-never-lit")) == 0 and CampaignState.getBankedMemory() == 0)
CampaignState.init(3) ; CampaignState.bankMemory(1)
Knowledge.unlock("the-lamp-was-never-lit") ; CampaignState.spendMemory(3)
check("a partial refund takes back what the bank holds", select(2, Knowledge.forget("the-lamp-was-never-lit")) == 1
  and CampaignState.getBankedMemory() == 0)
check("...and a re-tick pays back only that part", select(2, Knowledge.unlock("the-lamp-was-never-lit")) == 1
  and CampaignState.getBankedMemory() == 1)
CampaignState.unlockFact("the-wheel-still-turns")
check("an entry recorded before this rule (no payment) refunds nothing",
  select(2, Knowledge.forget("the-wheel-still-turns")) == 0)

print("== Act II status includes the after-Loop-3 route ==")
CampaignState.init(3)
check("no route: closed", Knowledge.actIIOpen() == false)
for _ = 1, 3 do CampaignState.reset() end
check("after Loop 3 with no surface entries: open", Knowledge.actIIOpen() == true)
CampaignState.init(3) ; CampaignState.setPartTwo(true)
check("Part II begun: open", Knowledge.actIIOpen() == true)

-- ---- the Control token itself (src/tts/control.lua) on a stubbed table ----
local function loadControl()
  local btns = {}
  local env = setmetatable({}, { __index = _G })
  env.self = {
    createButton = function(def) btns[#btns + 1] = def ; return true end,
    clearButtons = function() for i = #btns, 1, -1 do btns[i] = nil end ; return true end,
    getPosition = function() return { x = 0, y = 1, z = 0 } end,
  }
  env.print = function() end
  env.lastBroadcast = ""
  env.broadcastToAll = function(msg) env.lastBroadcast = msg end
  assert(loadfile("src/tts/control.lua", "t", env))()
  env.label = function(prefix)
    for _, b in ipairs(btns) do if b.label:sub(1, #prefix) == prefix then return b end end
  end
  return env
end

print("== Control: double Reset Loop, Age after the Prologue, Hour VI undo, finale ==")
do
  local C = loadControl()
  CampaignState.init(3)
  C.onLoad(nil)
  check("a new campaign opens in the Prologue", C.shApiState().prologue == true)
  C.shApiReset()
  check("the Prologue's Reset Loop starts Between Loops", C.shApiState().loopEnded == true and C.shApiState().loops == 0)
  C.shApiReset()
  check("a second Reset Loop after the Prologue does nothing but say so", C.shApiState().loops == 0
    and C.lastBroadcast:find("already been reset", 1, true) ~= nil)
  C.shApiInterlude({})
  check("Age is refused after the Prologue", C.shApiAge({ id = "sthrelias" }) == nil
    and CampaignState.getYears("sthrelias") == 0 and C.lastBroadcast:find("do not gain Years", 1, true) ~= nil)
  C.shApiBeginNextLoop()
  check("Begin Next Loop: a loop is under way again", C.shApiState().loopEnded == false)
  C.shApiCounter({ name = "dissonance", delta = 12 })
  C.shApiReset()
  local st1 = C.shApiState()
  C.shApiReset()
  local st2 = C.shApiState()
  check("double Reset Loop: one loop counted, scar and danger kept", st1.loops == 1 and st2.loops == 1
    and st2.dissonance == 1 and st2.danger == true)
  C.shApiCounter({ name = "investigators", delta = 1 })
  check("changing Investigators between loops keeps 'ended in danger'", C.shApiState().danger == true
    and C.shApiState().investigators == 4)
  C.shApiCounter({ name = "investigators", delta = -1 })
  check("Age works after a real loop (1 + danger)", (C.shApiAge({ id = "sthrelias" }) or {}).gained == 2)
  C.shApiBeginNextLoop()
  for _ = 1, 5 do C.shClickHour(nil, "White", false) end
  local sv = C.shApiState()
  check("Hour VI adds its Static token and shows Undo Hour VI", sv.hour == 6 and sv.static.extra == 1
    and C.label("Undo Hour VI") ~= nil)
  C.shUndoHourSix()
  local su = C.shApiState()
  check("Undo Hour VI takes the token back and clears the flag", su.static.extra == 0 and su.hourSix == false
    and C.label("Undo Hour VI") == nil)
  C.shApiCounter({ name = "dissonance", delta = 13 })   -- 14 at 3p
  C.shApiCounter({ name = "investigators", delta = -1 }) -- 2p: reset value 12
  check("fewer Investigators mid-loop: reaching the new reset value is announced",
    C.lastBroadcast:find("Reset Loop", 1, true) ~= nil and C.shApiState().loopEnded == false
    and C.shApiState().static.baseline == 2)
  C.shApiCounter({ name = "investigators", delta = 1 })
  CampaignState.unlockFact("the-way-the-night-breaks")
  C.shSyncBoard()
  check("with The Way the Night Breaks the Control offers Begin Finale", C.label("Begin Finale") ~= nil)
  C.shBeginFinale()
  check("Begin Finale switches to the contest", C.shApiState().finale == true and C.label("Contest 0 /") ~= nil)
  C.shClickContest(nil, "White", true)
  check("right-click Contest at 0 takes Begin Finale back", C.shApiState().finale == false)
  C.shApiSetFinale({ on = true })
  CampaignState.setHour(8)
  C.shClickHour(nil, "White", false)
  check("Hour IX in the finale says the finale ends", C.lastBroadcast:find("finale ends", 1, true) ~= nil)
  CampaignState.init(3)
  local m0 = CampaignState.getBankedMemory()
  local r1 = C.shApiUnlockFact({ id = "the-lamp-was-never-lit" })
  local r2 = C.shApiUnlockFact({ id = "the-lamp-was-never-lit" })
  check("Control: recording an entry pays once (+3); ticking it again pays nothing",
    r1.paid == 3 and r2.paid == 0 and CampaignState.getBankedMemory() == m0 + 3)
  local r3 = C.shApiForgetFact({ id = "the-lamp-was-never-lit" })
  check("Control: removing it refunds (-3)", r3.refund == 3 and CampaignState.getBankedMemory() == m0)
  CampaignState.init(3) ; CampaignState.setPartTwo(true)
  C.shApiUnlockFact({ id = "what-the-almanac-hid" })
  C.shApiUnlockFact({ id = "the-vote-that-never-ends" })
  check("Control: the Vote recorded after act 1a is gone -> Sealed Study stays closed this loop",
    Locations.isSealed("sealed-study"))
  C.shApiReset() ; C.shApiBeginNextLoop()
  check("Control: next loop in Part II act 2a is current -> it opens", Locations.isOpen("sealed-study"))
  CampaignState.init(3) ; CampaignState.setPartTwo(true)
  C.shApiUnlockFact({ id = "the-vote-that-never-ends" })
  C.shApiUnlockFact({ id = "what-the-almanac-hid" })
  check("Control: act 1a advancing with the Vote recorded -> it opens at once", Locations.isOpen("sealed-study"))
  CampaignState.init(3) ; CampaignState.bankMemory(7) ; CampaignState.addYears("sthrbirdie", 4)
  local realAdvance = Hourglass.advance
  Hourglass.advance = function() error("boom") end
  local res = C.runStillHourTests()
  Hourglass.advance = realAdvance
  check("Run Tests: an error is reported as a failure", res.failed >= 1 and res.error ~= nil)
  check("Run Tests: the live campaign is restored after the error", CampaignState.getBankedMemory() == 7
    and CampaignState.getYears("sthrbirdie") == 4)
  local ok2 = C.runStillHourTests()
  check("Run Tests: every in-engine test passes (" .. ok2.passed .. ")", ok2.failed == 0 and ok2.passed > 0)
  check("Run Tests: state restored after a clean run", CampaignState.getBankedMemory() == 7)
end

print("== Campaign log: Part II is ticked from the Control's partTwo only ==")
do
  local L = setmetatable({}, { __index = _G })
  L.PAGE, L.PAGE_COUNT = 1, 2
  L.FIELDS = { { k = "act1", t = "cb" }, { k = "act2", t = "cb" }, { k = "act3", t = "cb" },
               { k = "loops", t = "ct" }, { k = "banked", t = "ct" }, { k = "investigators", t = "ct" } }
  L.INVESTIGATORS = {}
  L.FACT_LAYER = { ["the-lamp-was-never-lit"] = "surface", ["the-thirteenth-toll"] = "surface",
                   ["the-road-remembers"] = "surface" }
  L.self = { editButton = function() end, editInput = function() end }
  L.broadcastToAll = function() end
  assert(loadfile("src/tts/campaign_log.lua", "t", L))()
  local know3 = { ["the-lamp-was-never-lit"] = true, ["the-thirteenth-toll"] = true, ["the-road-remembers"] = true }
  L.syncFromCampaignState({ version = 1, loopsCompleted = 3, knowledge = know3, partTwo = false })
  local v = L.getLogValues().values
  check("3 surface entries and 3 loops, Part II not begun: Part II is not ticked", v.act1 == true and not v.act2)
  L.syncFromCampaignState({ version = 1, loopsCompleted = 3, knowledge = know3, partTwo = true })
  v = L.getLogValues().values
  check("the Control's Part II ticks Part II", v.act2 == true)
  L.values = {}
  L.syncFromCampaignState({ version = 1, loopsCompleted = 3, knowledge = {} })
  check("a state saved before partTwo was recorded falls back to the loop count", L.getLogValues().values.act2 == true)
end

print("== Pending Years reach Age ==")
CampaignState.init(3)
CampaignState.addPendingYears("sthrelias", 2)
check("Interlude.age adds a card's pending Years (1 + 2)",
  Interlude.age("sthrelias", { extraYears = CampaignState.getPendingYears("sthrelias") }).yearsGained == 3)
print(string.format("RESULT: %d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
