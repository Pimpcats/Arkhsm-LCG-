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

print("")
print(string.format("RESULT: %d passed, %d failed", passed, failed))
os.exit(failed == 0 and 0 or 1)
