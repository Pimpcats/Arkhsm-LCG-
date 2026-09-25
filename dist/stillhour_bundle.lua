-- ============================================================================
-- THE STILL HOUR — generated bundle. DO NOT EDIT BY HAND.
-- Source: src/StillHour/*.ttslua + src/tts/control.lua ; assembled by
-- pipeline/bundle_mod.py. Edit the source and rebuild.
-- ============================================================================
local __modules = {}
local __loaded = {}
local function require(name)
  local cached = __loaded[name]
  if cached ~= nil then return cached end
  local factory = __modules[name]
  if factory == nil then
    error("StillHour bundle: module not found: " .. tostring(name))
  end
  local result = factory()
  if result == nil then result = true end
  __loaded[name] = result
  return result
end

__modules["StillHour/Constants"] = function()
--- THE STILL HOUR — campaign constants (derived from investigator count).
-- Every threshold in the campaign is a function of the number of investigators,
-- per aging_3p_v0.3 §2 and campaign_guide_v0.5 §10. Nothing here is hardcoded to
-- three players; three players is simply the tuned baseline (n = 3 -> 12 / 18).
--
-- Rules encoded:
--   reset threshold R  = 6 x investigators   (Dissonance hits R -> loop resets)
--   Appointed Arrived  = 4 x investigators   (Noticed band; the Appointed arrives)
--   Memory soft cap    = 6 x investigators
--   contest target     = 4 x investigators   (finale; 8/12/16 at 2/3/4p — CO-001)
--   scar cap           = floor(R / 3)         (start-of-loop Dissonance ceiling)
--   bands              = thirds of R: Calm / Glitch / Noticed
--
-- Solo (n = 1) is intentionally looser than the pure 4x/6x rule
-- (6 / 9 instead of 4 / 6) to keep true-solo playable — guide §10.
local Constants = {}

Constants.BAND_CALM = "Calm"
Constants.BAND_GLITCH = "Glitch"
Constants.BAND_NOTICED = "Noticed"

-- Baseline static-token count added to the chaos bag per band (encounter v0.4 §0).
Constants.STATIC_BY_BAND = {
  [Constants.BAND_CALM] = 0,
  [Constants.BAND_GLITCH] = 1,
  [Constants.BAND_NOTICED] = 2,
}

Constants.HOUR_FIRST = 1
Constants.HOUR_LAST = 9

--- Compute the full constant set for a given investigator count.
-- @param n integer number of investigators (>= 1)
-- @return table of thresholds
function Constants.forCount(n)
  n = math.max(1, math.floor(n or 3))
  local reset = 6 * n
  local appointed = 4 * n
  if n == 1 then
    -- Documented solo override (guide §10): looser than 4/6.
    reset = 9
    appointed = 6
  end
  return {
    investigators = n,
    resetThreshold = reset,
    appointedThreshold = appointed,
    memoryCap = 6 * n,
    -- Finale contest target = 4 x investigators (8 / 12 / 16 at 2 / 3 / 4p).
    -- Resolved by CO-001: the guide's "12 at three players" was intended and
    -- "3 x investigators" was an arithmetic slip (3 x 3 = 9). Nine made the
    -- finale too easy and undercut the "cost is age" payoff.
    contestTarget = 4 * n,
    scarCap = math.floor(reset / 3),
    bandGlitchStart = math.floor(reset / 3),
    bandNoticedStart = math.floor(2 * reset / 3),
  }
end

--- Classify a Dissonance value into its band.
-- @param dissonance integer
-- @param n integer investigator count
-- @return string one of BAND_CALM / BAND_GLITCH / BAND_NOTICED
function Constants.bandFor(dissonance, n)
  local c = Constants.forCount(n)
  if dissonance >= c.bandNoticedStart then
    return Constants.BAND_NOTICED
  elseif dissonance >= c.bandGlitchStart then
    return Constants.BAND_GLITCH
  end
  return Constants.BAND_CALM
end

return Constants

end

__modules["StillHour/CampaignState"] = function()
--- THE STILL HOUR — Campaign State Manager (SCED_BUILD_BRIEF P2).
--
-- THE single owned store for all novel-system state. Per the build brief's
-- state-persistence design note (§5): everything in P4/P6/P7 reads and writes
-- through this one manager. A card asks the manager ("is my once-per-loop flag
-- set?"); it never stores loop state itself.
--
-- Persistence model:
--   * This module holds an in-memory `state` table.
--   * The host object's onSave() calls CampaignState.serialize() and stores the
--     result in LuaScriptState; onLoad() calls CampaignState.deserialize(saved).
--   * SCED's campaign save/import-export carries LuaScriptState across scene
--     changes, so state survives BOTH node travel and a reset (board wipe).
--   * See docs/INTEGRATION.md for the exact host-object wiring.
--
-- What persists across a RESET (loop end): banked Memory (soft-capped), the
-- Knowledge Track, Years/brackets, loop counter. What clears: once-per-loop
-- flags, the Hourglass (back to Hour I), Dissonance (down to the scar floor).
-- Node travel WITHIN a loop preserves everything (the board, not tracked here,
-- persists too — guide §1).

local Constants = require("StillHour/Constants")

local CampaignState = {}

local STATE_VERSION = 1

-- Canonical test-type keys (match the four skill icons).
CampaignState.TEST_TYPES = { "willpower", "intellect", "combat", "agility" }

local function freshState(n)
  return {
    version = STATE_VERSION,
    investigators = math.max(1, math.floor(n or 3)),
    loopsCompleted = 0,
    bankedMemory = 0,
    dissonance = 0,
    hourglass = Constants.HOUR_FIRST,
    knowledge = {},          -- factId -> true
    oncePerLoopFlags = {},   -- flagId -> true (cleared on reset)
    testTypesThisLoop = {},  -- testType -> true (this loop)
    testTypesLastLoop = {},  -- snapshot of the previous loop (Muscle Memory reads this)
    years = {},              -- investigatorId -> integer
    brackets = {},           -- investigatorId -> {bracket, physical, mental}
    appointedStage = 0,      -- The Appointed's Approach: 0 Unseen..3 Arrived (CO-002)
    victoryLog = {},         -- enemyId -> true (Victory claimed; once per campaign)
    onCardMemory = {},       -- investigatorId -> Memory on that investigator's cards (this loop)
    loopTallies = {},        -- investigatorId -> {raises, spent}: Aging's "leaned on the loop" inputs
    lastLoopEndDissonance = nil, -- Dissonance when the last loop ended (Aging "ended in danger")
    prologue = false,        -- playing the Prologue (The First Hour): not a loop
    contest = 0,             -- finale contest progress (Contest the Crossing)
    partTwo = false,         -- Part II (The Shape of the Hour) has begun
  }
end

-- Internal live state. Always initialised so callers never hit nil.
local state = freshState(3)

------------------------------------------------------------------- lifecycle --

--- (Re)initialise a fresh campaign for `n` investigators. Wipes all state.
function CampaignState.init(n)
  state = freshState(n)
  return state
end

--- Set the active investigator count (drives every threshold). Does not wipe state.
function CampaignState.setInvestigatorCount(n)
  state.investigators = math.max(1, math.floor(n or 3))
  CampaignState.capMemory()
end

--- The derived constants (thresholds/bands) for the current investigator count.
function CampaignState.constants()
  return Constants.forCount(state.investigators)
end

--- Serialise the whole state to a JSON string (for LuaScriptState). Uses TTS's
-- global JSON when present; falls back to a passed encoder for offline tests.
function CampaignState.serialize(encoder)
  local enc = encoder or (JSON and JSON.encode) or error("no JSON encoder available")
  return enc(state)
end

--- Restore state from a JSON string produced by serialize(). Empty/nil -> fresh.
function CampaignState.deserialize(saved, decoder)
  if saved == nil or saved == "" then
    return state
  end
  local dec = decoder or (JSON and JSON.decode) or error("no JSON decoder available")
  local ok, restored = pcall(dec, saved)
  if ok and type(restored) == "table" and restored.version then
    state = restored
    -- Defensive: ensure sub-tables exist after a partial/legacy save.
    state.knowledge = state.knowledge or {}
    state.oncePerLoopFlags = state.oncePerLoopFlags or {}
    state.testTypesThisLoop = state.testTypesThisLoop or {}
    state.testTypesLastLoop = state.testTypesLastLoop or {}
    state.years = state.years or {}
    state.brackets = state.brackets or {}
    state.appointedStage = state.appointedStage or 0
    state.victoryLog = state.victoryLog or {}
    state.onCardMemory = state.onCardMemory or {}
    state.loopTallies = state.loopTallies or {}
  end
  return state
end

--- Raw state accessor (read-only intent; do not mutate directly from cards).
function CampaignState.raw()
  return state
end

--------------------------------------------------------------------- memory --

function CampaignState.getBankedMemory()
  return state.bankedMemory
end

--- Enforce the start-of-loop soft cap (6 x investigators). Excess is lost.
function CampaignState.capMemory()
  local cap = CampaignState.constants().memoryCap
  if state.bankedMemory > cap then
    state.bankedMemory = cap
  end
  return state.bankedMemory
end

--- Bank Memory (e.g. moving on-card Memory to the campaign pool at the interlude).
-- Not auto-capped here; the cap is applied at loop start via capMemory().
function CampaignState.bankMemory(amount)
  state.bankedMemory = math.max(0, state.bankedMemory + (amount or 0))
  return state.bankedMemory
end

--- Attempt to debit `cost` banked Memory. Returns false (no change) on overdraw.
-- Memory is a general experience currency (CO-001): it buys both regular card
-- level-ups (cost = card level) and Recollections (cost = memoryCost). This is
-- the core debit; see the semantic wrappers below.
function CampaignState.spendMemory(cost)
  cost = cost or 0
  if cost < 0 or state.bankedMemory < cost then
    return false
  end
  state.bankedMemory = state.bankedMemory - cost
  return true
end

--- Buy a normal higher-level card upgrade: cost = the target card's level (1-5),
-- exactly like official XP. Returns success bool.
function CampaignState.purchaseUpgrade(cardLevel)
  return CampaignState.spendMemory(cardLevel or 0)
end

--- Buy a Recollection into a deck: cost = its listed memoryCost. Returns success bool.
function CampaignState.purchaseRecollection(memoryCost)
  return CampaignState.spendMemory(memoryCost or 0)
end

----------------------------------------------------------- on-card Memory --

-- Memory on an investigator's cards (cards v0.2 §A: "tokens on investigator/
-- asset cards"). It persists between nodes of a loop, drives the Appointed's
-- Prey ("the investigator with the most Memory on their cards"), and is moved to
-- banked Memory at the interlude (guide §4 step 2).

function CampaignState.getOnCardMemory(investigatorId)
  return state.onCardMemory[investigatorId] or 0
end

function CampaignState.setOnCardMemory(investigatorId, n)
  state.onCardMemory[investigatorId] = math.max(0, math.floor(n or 0))
  return state.onCardMemory[investigatorId]
end

function CampaignState.addOnCardMemory(investigatorId, n)
  return CampaignState.setOnCardMemory(investigatorId, CampaignState.getOnCardMemory(investigatorId) + (n or 1))
end

--- Copy of the investigatorId -> on-card Memory map.
function CampaignState.onCardMemoryMap()
  local out = {}
  for id, n in pairs(state.onCardMemory) do out[id] = n end
  return out
end

--- Interlude: move all on-card Memory to banked Memory. Returns the amount moved.
function CampaignState.bankOnCardMemory()
  local total = 0
  for _, n in pairs(state.onCardMemory) do total = total + n end
  state.onCardMemory = {}
  CampaignState.bankMemory(total)
  return total
end

------------------------------------------------------- leaned-on-the-loop --

-- Per investigator, this loop (aging v0.3 §1.1): how many times THEY raised
-- Dissonance, and how much Memory they spent on loop-power effects
-- (Recollections, foreknowledge abilities). Kept through the reset so the
-- interlude can age with them; cleared when the next loop begins.
CampaignState.TALLY_KINDS = { raises = true, spent = true }

function CampaignState.getTallies(investigatorId)
  local t = state.loopTallies[investigatorId] or {}
  return { raises = t.raises or 0, spent = t.spent or 0 }
end

--- Add `delta` (may be negative; floors at 0) to one tally. Returns the new value.
function CampaignState.addTally(investigatorId, kind, delta)
  if not CampaignState.TALLY_KINDS[kind] or type(investigatorId) ~= "string" then return nil end
  local t = state.loopTallies[investigatorId] or { raises = 0, spent = 0 }
  t[kind] = math.max(0, (t[kind] or 0) + math.floor(delta or 1))
  state.loopTallies[investigatorId] = t
  return t[kind]
end

function CampaignState.clearTallies()
  state.loopTallies = {}
end

----------------------------------------------------------------- dissonance --

function CampaignState.getDissonance()
  return state.dissonance
end

function CampaignState.band()
  return Constants.bandFor(state.dissonance, state.investigators)
end

--- Clamp a raw Dissonance value into [0, resetThreshold] and store it.
local function setDissonanceClamped(v)
  local c = CampaignState.constants()
  state.dissonance = math.max(0, math.min(c.resetThreshold, v))
  return state.dissonance
end

--- Raise Dissonance. Returns new value, the band before, and the band after,
-- so the caller (Dissonance module) can drive chaos-bag / Appointed hooks.
function CampaignState.raiseDissonance(n)
  local before = CampaignState.band()
  local reachedReset = false
  setDissonanceClamped(state.dissonance + (n or 1))
  local c = CampaignState.constants()
  if state.dissonance >= c.resetThreshold then
    reachedReset = true
  end
  return state.dissonance, before, CampaignState.band(), reachedReset
end

--- Reduce Dissonance (specific cards only). Returns new value + bands.
function CampaignState.reduceDissonance(n)
  local before = CampaignState.band()
  setDissonanceClamped(state.dissonance - (n or 1))
  return state.dissonance, before, CampaignState.band()
end

--- True once Dissonance has reached the Appointed's Arrived threshold (Noticed
-- band start = 4 x investigators). The Approach is driven by band-entry EVENTS
-- (see Dissonance.raise); this is the corresponding level check.
function CampaignState.dissonanceAtAppointedThreshold()
  return state.dissonance >= CampaignState.constants().appointedThreshold
end

------------------------------------------------------------------ hourglass --

function CampaignState.getHour()
  return state.hourglass
end

--- Directly set the Hourglass (clamped I..IX). Advance/rewind logic that
-- resolves intervening Hours lives in Hourglass.ttslua.
function CampaignState.setHour(h)
  state.hourglass = math.max(Constants.HOUR_FIRST, math.min(Constants.HOUR_LAST, math.floor(h)))
  return state.hourglass
end

------------------------------------------------------------------ knowledge --

function CampaignState.knows(factId)
  return state.knowledge[factId] == true
end

function CampaignState.unlockFact(factId)
  local was = state.knowledge[factId] == true
  state.knowledge[factId] = true
  return not was  -- true if newly unlocked
end

function CampaignState.knownFacts()
  local list = {}
  for factId in pairs(state.knowledge) do
    list[#list + 1] = factId
  end
  table.sort(list)
  return list
end

----------------------------------------------------------- once-per-loop flags --

function CampaignState.isFlagSet(flagId)
  return state.oncePerLoopFlags[flagId] == true
end

--- Set a once-per-loop flag. Returns true if it was newly set (i.e. the ability
-- is allowed to fire now), false if it had already been used this loop.
function CampaignState.setFlag(flagId)
  if state.oncePerLoopFlags[flagId] then
    return false
  end
  state.oncePerLoopFlags[flagId] = true
  return true
end

----------------------------------------------------------- per-loop test types --

--- Record that a test of `testType` was performed this loop (for Muscle Memory).
function CampaignState.recordTestType(testType)
  if testType then
    state.testTypesThisLoop[testType] = true
  end
end

--- Did the party perform this test type during the PREVIOUS loop?
function CampaignState.performedLastLoop(testType)
  return state.testTypesLastLoop[testType] == true
end

------------------------------------------------------------------ years/age --

function CampaignState.getYears(investigatorId)
  return state.years[investigatorId] or 0
end

function CampaignState.addYears(investigatorId, n)
  state.years[investigatorId] = (state.years[investigatorId] or 0) + (n or 0)
  return state.years[investigatorId]
end

function CampaignState.getBracket(investigatorId)
  return state.brackets[investigatorId]
end

function CampaignState.setBracket(investigatorId, bracketData)
  state.brackets[investigatorId] = bracketData
end

-------------------------------------------------------- the appointed (P5) --

-- The Appointed occupies an Approach stage 0..3 (Unseen/Sensed/Emerging/Arrived,
-- CO-002 §1). It only ever ratchets UP via driver events (clock, Dissonance
-- bands, cards); Hold Back pushes it back one stage. It is on the board while
-- stage >= 1. Persisted in state.appointedStage; reset() sets it to 0.

function CampaignState.getAppointedStage()
  return state.appointedStage
end

--- Ratchet the Approach UP to at least driverStage (clamped 0..3). Never lowers
-- the stage — a driver can only raise it, so calling with a lower value is a
-- no-op. Returns the resulting stage.
function CampaignState.advanceAppointed(driverStage)
  -- the Prologue has no Appointed (guide: The First Hour): nothing drives it
  if state.prologue then return state.appointedStage end
  local target = math.max(0, math.min(3, math.floor(driverStage or 0)))
  if target > state.appointedStage then
    state.appointedStage = target
  end
  return state.appointedStage
end

--- Push the Approach back one stage (Hold Back success), clamped >= 0.
function CampaignState.pushBackAppointed()
  state.appointedStage = math.max(0, state.appointedStage - 1)
  return state.appointedStage
end

--- Is the Appointed manifested on the board (stage >= 1)?
function CampaignState.isAppointedInPlay()
  return state.appointedStage >= 1
end

------------------------------------------------------------ victory (Memory) --

-- Victory X in a loop campaign: defeated enemies return next loop, so Victory
-- banks ONCE per named enemy per campaign — the night repeats, but you only
-- learn a face once. The claim log lives on the campaign log (persists across
-- resets; reset() must NOT clear it).

--- Has this enemy's Victory already been claimed this campaign?
function CampaignState.isVictoryClaimed(enemyId)
  return state.victoryLog[enemyId] == true
end

--- Claim an enemy's Victory: banks `memoryValue` the first time only.
-- Returns true if newly claimed (Memory banked), false if already claimed.
function CampaignState.claimVictory(enemyId, memoryValue)
  if state.victoryLog[enemyId] then
    return false
  end
  state.victoryLog[enemyId] = true
  CampaignState.bankMemory(memoryValue or 0)
  return true
end

------------------------------------------------------------------ loop flow --

--- End the current loop (a RESET). Advances the loop counter, drops Dissonance
-- to the new scar floor, resets the Hourglass, clears once-per-loop flags, and
-- snapshots this loop's test types for next loop's Muscle Memory reads.
--
-- Banking on-card Memory and applying Years happen in the interlude (call
-- bankMemory()/Aging.applyInterlude() around this) — a reset alone does not
-- bank Memory, per guide §4.
function CampaignState.reset()
  if state.prologue then
    -- the Prologue's first reset: the night folds, but it is not a loop (no
    -- loop counted, no scar, no Years), and play continues at Loop 1
    state.prologue = false
    state.dissonance = 0
    state.hourglass = Constants.HOUR_FIRST
    state.oncePerLoopFlags = {}
    state.testTypesLastLoop = state.testTypesThisLoop
    state.testTypesThisLoop = {}
    state.appointedStage = 0
    state.lastLoopEndDissonance = nil
    return state
  end
  state.loopsCompleted = state.loopsCompleted + 1
  -- Aging reads this at the interlude ("ended in danger"), after the drop below.
  state.lastLoopEndDissonance = state.dissonance

  -- Scar floor: completed loops, capped by scarCap.
  local c = CampaignState.constants()
  state.dissonance = math.min(state.loopsCompleted, c.scarCap)

  state.hourglass = Constants.HOUR_FIRST
  state.oncePerLoopFlags = {}
  state.testTypesLastLoop = state.testTypesThisLoop
  state.testTypesThisLoop = {}
  state.appointedStage = 0
  state.contest = 0
  return state
end

--- Finale contest progress (guide: Contest the Crossing), 0..99. It lasts
-- only for the finale being played; a reset clears it.
function CampaignState.getContest()
  return state.contest or 0
end

function CampaignState.setContest(n)
  state.contest = math.max(0, math.min(99, math.floor(tonumber(n) or 0)))
  return state.contest
end

--- Begin a new loop's play: enforce the Memory soft cap. Call at §2 setup after
-- the interlude has banked Memory and bought Recollections.
function CampaignState.startLoop()
  CampaignState.capMemory()
  return state
end

--- Dissonance at the end of the last loop (nil before the first reset).
function CampaignState.getLastLoopEndDissonance()
  return state.lastLoopEndDissonance
end

--- Part II (guide: Between Loops step 5) begins at the interlude that holds
-- 3+ surface Knowledge entries, or once Loop 3 is complete. It never ends.
function CampaignState.inPartTwo()
  return state.partTwo == true
end

function CampaignState.setPartTwo(on)
  state.partTwo = on and true or false
  return state.partTwo
end

--- The Prologue (The First Hour) is played before Loop 1 and is not a loop.
function CampaignState.inPrologue()
  return state.prologue == true
end

function CampaignState.setPrologue(on)
  state.prologue = on and true or false
  return state.prologue
end

function CampaignState.getLoopsCompleted()
  return state.loopsCompleted
end

return CampaignState

end

__modules["StillHour/Dissonance"] = function()
--- THE STILL HOUR — Dissonance bands + the [static] chaos token (P3).
--
-- Owns the *chaos-bag consequences* of Dissonance. The value itself lives in
-- CampaignState; this module reconciles the bag's baseline [static] count to the
-- current band and implements the token's on-reveal behaviour.
--
-- The [static] token (encounter v0.4 §0):
--   * modifier -3
--   * when revealed: raise Dissonance by 1  ("the glitch feeds itself")
--
-- Baseline [static] count in the bag by band (auto-managed here):
--   Calm 0 · Glitch 1 · Noticed 2
-- Cards may add *temporary* extra [static] on top; those are the card's own
-- responsibility and are not tracked as baseline.
--
-- Chaos-bag edits go through an injected `bag` adapter (a thin wrapper over
-- SCED's existing chaos-bag / bless-curse manager) — never by mutating the bag
-- object directly (SCED_BUILD_BRIEF §6). The adapter must implement:
--     bag.setBaselineStatic(n)   -- ensure exactly n baseline [static] tokens
-- and optionally:
--     bag.addStatic(n) / bag.removeStatic(n)

local Constants = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")

local Dissonance = {}

Dissonance.STATIC_MODIFIER = -3
Dissonance.STATIC_TOKEN_TYPE = "static"

--- Baseline [static] count for a band.
local function baselineStaticForBand(band)
  return Constants.STATIC_BY_BAND[band] or 0
end

--- Reconcile the bag's baseline [static] tokens to the current band.
-- Safe to call any time (idempotent). Returns the baseline count now expected.
function Dissonance.syncBag(bag)
  local target = baselineStaticForBand(CampaignState.band())
  if bag and bag.setBaselineStatic then
    bag.setBaselineStatic(target)
  end
  return target
end

--- Handle a band transition by adjusting the bag from `before` to `after`.
local function reconcileBand(bag, before, after)
  if before == after then
    return
  end
  local target = baselineStaticForBand(after)
  if not bag then
    return
  end
  if bag.setBaselineStatic then
    bag.setBaselineStatic(target)
  elseif bag.addStatic and bag.removeStatic then
    local delta = target - baselineStaticForBand(before)
    if delta > 0 then
      bag.addStatic(delta)
    elseif delta < 0 then
      bag.removeStatic(-delta)
    end
  end
end

--- On entering a new Dissonance band, drive the Appointed's Approach (CO-002 §1):
-- entering Glitch -> at least Sensed (1); entering Noticed -> Arrived (3).
-- Event-based (only on band change); advanceAppointed only ratchets up.
local function driveAppointedOnBand(before, after)
  if before == after then
    return
  end
  if after == Constants.BAND_NOTICED then
    CampaignState.advanceAppointed(3)
  elseif after == Constants.BAND_GLITCH then
    CampaignState.advanceAppointed(1)
  end
end

--- Raise Dissonance, reconcile the bag, drive the Appointed on a band change.
-- @return table {value, band, appointedStage, reachedReset}
function Dissonance.raise(n, bag)
  local value, before, after, reachedReset = CampaignState.raiseDissonance(n or 1)
  reconcileBand(bag, before, after)
  driveAppointedOnBand(before, after)
  return {
    value = value,
    band = after,
    appointedStage = CampaignState.getAppointedStage(),
    reachedReset = reachedReset,
  }
end

--- Reduce Dissonance and reconcile the bag.
function Dissonance.reduce(n, bag)
  local value, before, after = CampaignState.reduceDissonance(n or 1)
  reconcileBand(bag, before, after)
  return { value = value, band = after }
end

--- The [static] token's symbol effect: after it is revealed, raise Dissonance by 1.
-- Returns the same info table as raise(), so callers can react to a boss/reset
-- transition triggered by the reveal itself.
function Dissonance.onStaticRevealed(bag)
  return Dissonance.raise(1, bag)
end

return Dissonance

end

__modules["StillHour/LoopFlags"] = function()
--- THE STILL HOUR — loop bookkeeping (P4).
--
-- Semantic wrapper over CampaignState's once-per-loop flags and per-loop
-- test-type record. These are the two flags the base game has no concept of:
--   * "Limit once per loop" persists across NODE TRAVEL and clears only on reset
--     (cards v0.2 §A) — CampaignState clears them in reset().
--   * Muscle Memory reads whether a test type was performed the PREVIOUS loop.
--
-- Cards call through here; they never store loop state themselves.

local CampaignState = require("StillHour/CampaignState")

local LoopFlags = {}

--- Try to use a once-per-loop ability keyed by `flagId`. Returns true if it is
-- allowed to fire now (and marks it used), false if already used this loop.
-- Use a stable, card-scoped id, e.g. "sthr-igetout:"..playerColor.
function LoopFlags.use(flagId)
  return CampaignState.setFlag(flagId)
end

--- Peek without consuming.
function LoopFlags.isUsed(flagId)
  return CampaignState.isFlagSet(flagId)
end

--- Record that this test type was performed this loop (call on any skill test).
function LoopFlags.recordTest(testType)
  CampaignState.recordTestType(testType)
end

--- Muscle Memory: true if the party performed this test type during the previous
-- loop, meaning the card provides [wild][wild] and draws 1 instead of [wild].
function LoopFlags.muscleMemoryUpgraded(testType)
  return CampaignState.performedLastLoop(testType)
end

return LoopFlags

end

__modules["StillHour/Hourglass"] = function()
--- THE STILL HOUR — the Hourglass / Occultation clock (P6, data model).
--
-- The Occultation is a FIXED, ordered stack of nine Hour cards (encounter v0.4
-- §1). The Hourglass advances by time and by Skip effects; each newly reached
-- Hour resolves its "when reached" effect IN ORDER — so a big Skip that jumps
-- several Hours must resolve every intervening Hour, not just the destination.
--
-- Knowledge facts edit specific Hours. Two edits change the clock's STRUCTURE
-- and are handled here:
--   * "The Hour Was Wrong"     -> Hour IV is removed entirely (skipped).
--   * "The Way the Night Breaks" -> reaching Hour IX may open the finale instead
--     of forcing a reset.
-- The remaining edits change what an Hour DOES; those are applied inside the
-- per-Hour handlers via the knows() checks.
--
-- Board-specific consequences (who is at a Church, moving investigators off an
-- impassable location, advancing the Appointed, etc.) are delegated to callbacks
-- in `ctx` so this module stays board-agnostic and testable. Any callback may be
-- omitted; it is then a no-op.
--
-- ctx fields (all optional):
--   ctx.dissonance      -- the Dissonance module (for raise/reduce + bag sync)
--   ctx.bag             -- chaos-bag adapter passed through to Dissonance
--   ctx.anyoneAtChurch  -- function() -> bool
--   ctx.log             -- function(hourNumber, hourName, message)
--   ctx.onHourReached   -- function(hourNumber, descriptor)
--   ctx.onReset         -- function()
--   ctx.onFinaleAttemptable -- function()
--   ctx.onAppointedAdvance  -- function(stage) board hook after the clock ratchets
--                              the Appointed's Approach (Hours V/VII/VIII)
--   ctx.addStatic       -- function(n) temporary bag static (Hour VI)
--   ctx.removeStatic    -- function(n) (Hour VI when almanac fact known)
--   ctx.enemiesGetFightBonus -- function(n) (Hour VIII)

local Constants = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")

local Hourglass = {}

Hourglass.HOUR_NAMES = {
  [1] = "First Dark",
  [2] = "Low Water",
  [3] = "The Thirteenth Toll",
  [4] = "The Road Gives Way",
  [5] = "The Streets Empty",
  [6] = "The Wrong Sky",
  [7] = "The Guest Approaches",
  [8] = "Almost",
  [9] = "The Appointed Hour",
}

local function raiseDissonance(ctx, n)
  if ctx and ctx.dissonance then
    return ctx.dissonance.raise(n, ctx.bag)
  end
  return CampaignState.raiseDissonance(n)
end

-- Ratchet the Appointed's Approach up as the clock reaches its trigger Hours
-- (CO-002 §1): Hour V -> Sensed(1), VII -> Emerging(2), VIII -> Arrived(3).
local function advanceAppointed(ctx, stage)
  local s = CampaignState.advanceAppointed(stage)
  if ctx and ctx.onAppointedAdvance then
    ctx.onAppointedAdvance(s)
  end
  return s
end

--- Is this Hour structurally removed from the clock by a Knowledge fact?
function Hourglass.isHourRemoved(hour)
  if hour == 4 and CampaignState.knows("the-hour-was-wrong") then
    return true
  end
  return false
end

-- Per-Hour "when reached" handlers. Return a short descriptor string for logging.
local HOUR_HANDLERS = {
  [1] = function(_) return "The night begins." end,

  [2] = function(ctx)
    if ctx and ctx.eachInvestigatorDrawsEncounter then
      ctx.eachInvestigatorDrawsEncounter()
    end
    return "Each investigator draws 1 encounter card."
  end,

  [3] = function(ctx)
    -- Raise Dissonance by 1; by 2 instead if anyone is at a Church location,
    -- UNLESS "The Thirteenth Toll" is known (then skip the extra +1).
    local atChurch = ctx and ctx.anyoneAtChurch and ctx.anyoneAtChurch()
    local amount = 1
    if atChurch and not CampaignState.knows("the-thirteenth-toll") then
      amount = 2
    end
    raiseDissonance(ctx, amount)
    return string.format("Raise Dissonance by %d.", amount)
  end,

  [4] = function(ctx)
    -- Handled structurally by isHourRemoved(); if we get here the fact is unknown.
    if ctx and ctx.roadGivesWay then
      ctx.roadGivesWay()
    end
    return "The location with the fewest clues becomes impassable."
  end,

  [5] = function(ctx)
    advanceAppointed(ctx, 1)  -- Hour V -> at least Sensed
    if CampaignState.band() ~= Constants.BAND_CALM then
      if ctx and ctx.awakenSleepwalkingEchoes then
        ctx.awakenSleepwalkingEchoes()
      end
      return "The streets empty. Sleepwalking Echoes awaken; the Appointed is Sensed."
    end
    return "The streets empty. The Appointed is Sensed (Echoes still asleep in Calm)."
  end,

  [6] = function(ctx)
    if CampaignState.knows("what-the-almanac-hid") then
      if ctx and ctx.removeStatic then ctx.removeStatic(1) end
      return "Each investigator removes 1 [static]."
    end
    if ctx and ctx.addStatic then ctx.addStatic(1) end
    return "Add 1 [static] token until the next reset."
  end,

  [7] = function(ctx)
    advanceAppointed(ctx, 2)  -- Hour VII -> at least Emerging
    return "The guest approaches. The Appointed is Emerging"
      .. (CampaignState.knows("the-appointeds-name") and " (arriving exhausted)." or ".")
  end,

  [8] = function(ctx)
    raiseDissonance(ctx, 2)
    advanceAppointed(ctx, 3)  -- Hour VIII -> Arrived
    if ctx and ctx.enemiesGetFightBonus then ctx.enemiesGetFightBonus(1) end
    return "Almost. Raise Dissonance by 2; all enemies +1 Fight; the Appointed has Arrived."
  end,

  [9] = function(ctx)
    if CampaignState.knows("the-way-the-night-breaks") then
      if ctx and ctx.onFinaleAttemptable then ctx.onFinaleAttemptable() end
      return "The Appointed Hour — you may attempt the finale."
    end
    if ctx and ctx.onReset then ctx.onReset() end
    return "The Appointed Hour — the night ends. Trigger a reset."
  end,
}

--- Resolve a single Hour's "when reached" effect (unless removed).
local function resolveHour(hour, ctx)
  if Hourglass.isHourRemoved(hour) then
    return
  end
  local handler = HOUR_HANDLERS[hour]
  local descriptor = handler and handler(ctx) or ""
  if ctx and ctx.log then
    ctx.log(hour, Hourglass.HOUR_NAMES[hour], descriptor)
  end
  if ctx and ctx.onHourReached then
    ctx.onHourReached(hour, descriptor)
  end
end

--- Advance the Hourglass by `n` Hours, resolving every newly reached Hour in
-- order (removed Hours are stepped over without resolving). Stops at Hour IX.
-- @return the new Hour
function Hourglass.advance(n, ctx)
  n = n or 1
  local current = CampaignState.getHour()
  for _ = 1, n do
    if current >= Constants.HOUR_LAST then
      break
    end
    -- Step to the next non-removed Hour.
    repeat
      current = current + 1
    until current >= Constants.HOUR_LAST or not Hourglass.isHourRemoved(current)
    CampaignState.setHour(current)
    resolveHour(current, ctx)
    if current >= Constants.HOUR_LAST then
      break
    end
  end
  return CampaignState.getHour()
end

--- Rewind the Hourglass by `n` Hours (e.g. Hold Back, the Bell). Rewinding does
-- NOT re-resolve Hour effects (you are un-marking the Hour, not living it again).
-- @return the new Hour
function Hourglass.rewind(n, ctx)
  n = n or 1
  local current = CampaignState.getHour()
  for _ = 1, n do
    if current <= Constants.HOUR_FIRST then
      break
    end
    repeat
      current = current - 1
    until current <= Constants.HOUR_FIRST or not Hourglass.isHourRemoved(current)
  end
  if ctx and ctx.log then
    ctx.log(current, Hourglass.HOUR_NAMES[current], "Hourglass rewound.")
  end
  return CampaignState.setHour(current)
end

return Hourglass

end

__modules["StillHour/Aging"] = function()
--- THE STILL HOUR — the Aging system (P7, data model).
--
-- The price of living the same night is years (aging_3p_v0.3 §1). Years accrue
-- per investigator at each interlude; brackets apply a "body for mind" stat
-- drift. This module owns the bracket math; it reads/writes Years and the locked
-- drift choice through CampaignState. Applying the stat changes to a physical
-- investigator sheet is the host's job (delegated via the returned drift).
--
-- Years gained this loop, per investigator:
--   +1 base (the night always takes something)
--   +1 if defeated during the loop
--   +1 if the loop ended at the danger threshold or higher (Dissonance >= 4x inv)
--   +1 if they leaned on the loop (raised Dissonance 3+ times OR spent 4+ Memory)
--
-- Brackets (checked at each interlude; higher bracket REPLACES lower — no stacking):
--   Prime     0-4   no change
--   Weathered 5-9   -1 one physical skill (com/agi), +1 one mental skill (wil/int)
--   Elder     10-14 Weathered drift, +1 more to the mental skill, -1 max health,
--                   begin each loop with 1 Memory on your investigator card
--   Ancient   15+   Elder drift, -1 max sanity, unlocks "Take Its Place";
--                   at 18 Years the investigator ages out (removed)
--
-- The physical/mental skills are chosen once on entering Weathered and LOCKED
-- (reused at Elder/Ancient). Skill values floor at 1; max health/sanity never
-- reach 0 from these deltas.

local CampaignState = require("StillHour/CampaignState")

local Aging = {}

Aging.PRIME = "Prime"
Aging.WEATHERED = "Weathered"
Aging.ELDER = "Elder"
Aging.ANCIENT = "Ancient"
Aging.AGE_OUT_YEARS = 18

Aging.PHYSICAL_SKILLS = { combat = true, agility = true }
Aging.MENTAL_SKILLS = { willpower = true, intellect = true }

--- Bracket name for a Years total.
function Aging.bracketForYears(years)
  years = years or 0
  if years >= 15 then return Aging.ANCIENT end
  if years >= 10 then return Aging.ELDER end
  if years >= 5 then return Aging.WEATHERED end
  return Aging.PRIME
end

--- Years gained this loop from the four conditions.
-- @param cond table {defeated, endedInDanger, leanedOnLoop} (booleans)
function Aging.computeYearsGained(cond)
  cond = cond or {}
  local y = 1
  if cond.defeated then y = y + 1 end
  if cond.endedInDanger then y = y + 1 end
  if cond.leanedOnLoop then y = y + 1 end
  return y
end

--- Did the loop end in the danger band (Dissonance >= the Appointed threshold)?
-- Measure BEFORE reset (reset drops Dissonance to the scar).
function Aging.loopEndedInDanger(dissonanceAtEnd, investigatorCount)
  local Constants = require("StillHour/Constants")
  return dissonanceAtEnd >= Constants.forCount(investigatorCount).appointedThreshold
end

--- "Leaned on the loop" test: raised Dissonance 3+ times OR spent 4+ Memory
-- on loop-power effects this loop. Caller supplies the tallies.
function Aging.leanedOnLoop(dissonanceRaises, memorySpentOnPower)
  return (dissonanceRaises or 0) >= 3 or (memorySpentOnPower or 0) >= 4
end

--- Apply an interlude's aging to one investigator.
-- @param investigatorId string
-- @param cond table {defeated, endedInDanger, leanedOnLoop}
-- @param lockedChoice table|nil {physical="combat"|"agility", mental="willpower"|"intellect"}
--        required the first time the investigator enters Weathered; ignored after.
-- @return table {years, bracket, bracketChanged, agedOut, drift}
function Aging.applyInterlude(investigatorId, cond, lockedChoice)
  local before = Aging.bracketForYears(CampaignState.getYears(investigatorId))
  local gained = Aging.computeYearsGained(cond)
  local years = CampaignState.addYears(investigatorId, gained)
  local bracket = Aging.bracketForYears(years)

  -- Lock the physical/mental drift choice the first time we reach Weathered+.
  local record = CampaignState.getBracket(investigatorId) or {}
  if bracket ~= Aging.PRIME and not record.physical and lockedChoice then
    record.physical = lockedChoice.physical
    record.mental = lockedChoice.mental
  end
  record.bracket = bracket
  CampaignState.setBracket(investigatorId, record)

  return {
    years = years,
    yearsGained = gained,
    bracket = bracket,
    bracketChanged = (bracket ~= before),
    agedOut = years >= Aging.AGE_OUT_YEARS,
    needsLockedChoice = (bracket ~= Aging.PRIME and not record.physical),
    drift = Aging.driftFor(investigatorId),
  }
end

--- Record the Weathered drift choice later than applyInterlude (e.g. from the
-- interlude panel). Only the first choice sticks — it is LOCKED thereafter.
-- Returns true if the choice was recorded now.
function Aging.lockChoice(investigatorId, physical, mental)
  if not Aging.PHYSICAL_SKILLS[physical] or not Aging.MENTAL_SKILLS[mental] then
    return false
  end
  local record = CampaignState.getBracket(investigatorId) or {}
  if record.physical then
    return false
  end
  record.physical, record.mental = physical, mental
  record.bracket = record.bracket or Aging.bracketForYears(CampaignState.getYears(investigatorId))
  CampaignState.setBracket(investigatorId, record)
  return true
end

--- Does this investigator still need a locked drift choice (Weathered+ without one)?
function Aging.needsChoice(investigatorId)
  local bracket = Aging.bracketForYears(CampaignState.getYears(investigatorId))
  local record = CampaignState.getBracket(investigatorId) or {}
  return bracket ~= Aging.PRIME and not record.physical
end

--- The cumulative stat drift for an investigator's current bracket.
-- Deltas are relative to the printed base stat line; the host applies them with
-- a floor of 1 on skills. Returns nil for Prime (no change).
-- @return table|nil {physicalSkill, mentalSkill, skillDeltas={physical,mental},
--                    maxHealthDelta, maxSanityDelta, startLoopMemory, unlocksTakeItsPlace}
function Aging.driftFor(investigatorId)
  local years = CampaignState.getYears(investigatorId)
  local bracket = Aging.bracketForYears(years)
  if bracket == Aging.PRIME then
    return nil
  end
  local record = CampaignState.getBracket(investigatorId) or {}
  local drift = {
    physicalSkill = record.physical,   -- "combat" | "agility" (may be nil until chosen)
    mentalSkill = record.mental,       -- "willpower" | "intellect"
    skillDeltas = { physical = -1, mental = 1 },
    maxHealthDelta = 0,
    maxSanityDelta = 0,
    startLoopMemory = 0,
    unlocksTakeItsPlace = false,
  }
  if bracket == Aging.ELDER or bracket == Aging.ANCIENT then
    drift.skillDeltas.mental = 2       -- +1 more to the mental skill
    drift.maxHealthDelta = -1
    drift.startLoopMemory = 1
  end
  if bracket == Aging.ANCIENT then
    drift.maxSanityDelta = -1
    drift.unlocksTakeItsPlace = true
  end
  return drift
end

-- Map a skill name to the stat-line key used by `base`.
local SKILL_KEY = { willpower = "wil", intellect = "int", combat = "com", agility = "agi" }

--- Apply an investigator's current bracket drift to a printed stat line and
-- return the effective line. Skills floor at 1; max health/sanity floor at 1
-- (the brackets never bring a maximum to 0). `base` is a table with keys
-- wil/int/com/agi/health/sanity. Non-destructive (returns a new table).
function Aging.applyDriftToStats(base, investigatorId)
  local out = {
    wil = base.wil, int = base.int, com = base.com, agi = base.agi,
    health = base.health, sanity = base.sanity,
  }
  local drift = Aging.driftFor(investigatorId)
  if not drift then
    return out
  end
  if drift.physicalSkill then
    local k = SKILL_KEY[drift.physicalSkill]
    out[k] = math.max(1, out[k] + drift.skillDeltas.physical)
  end
  if drift.mentalSkill then
    local k = SKILL_KEY[drift.mentalSkill]
    out[k] = math.max(1, out[k] + drift.skillDeltas.mental)
  end
  out.health = math.max(1, out.health + drift.maxHealthDelta)
  out.sanity = math.max(1, out.sanity + drift.maxSanityDelta)
  return out
end

return Aging

end

__modules["StillHour/Appointed"] = function()
--- THE STILL HOUR — THE APPOINTED (P5 / CO-002).
--
-- The boss is not a monster that spawns; it is an arrival the night owes. It
-- occupies an Approach stage (Unseen -> Sensed -> Emerging -> Arrived) tracked in
-- CampaignState.appointedStage, and manifests on the board once Sensed. It cannot
-- be attacked, evaded, or defeated — only HELD BACK (pushed back one stage) to
-- buy time on the clock.
--
-- This module owns the enemy's *behaviour*: manifest/remove by stage, the
-- stage-gated Forced effects, Prey selection, and the Hold Back action. Board
-- specifics (placing the figure, dealing damage to a seat) are delegated to a
-- `ctx` of callbacks so the module stays board-agnostic and testable; any
-- callback may be omitted (then it is a no-op).
--
-- Approach advancement lives OUTSIDE this module, on purpose: the clock
-- (Hourglass.ttslua, Hours V/VII/VIII) and Dissonance bands (Dissonance.ttslua,
-- entering Glitch/Noticed) call CampaignState.advanceAppointed(). Cards (The
-- Crossing, The Debt of Hours) do the same. This module reads the resulting
-- stage; it never advances itself.

local Constants = require("StillHour/Constants")
local CampaignState = require("StillHour/CampaignState")
local Hourglass = require("StillHour/Hourglass")

local Appointed = {}

Appointed.STAGE_NAMES = { [0] = "Unseen", [1] = "Sensed", [2] = "Emerging", [3] = "Arrived" }
Appointed.HOLD_BACK_DIFFICULTY = 4          -- test [wil] or [com] (4)
Appointed.ARRIVED_DAMAGE = 2
Appointed.ARRIVED_HORROR = 2

------------------------------------------------------------------ stage read --

function Appointed.stage()
  return CampaignState.getAppointedStage()
end

function Appointed.stageName()
  return Appointed.STAGE_NAMES[CampaignState.getAppointedStage()]
end

--- On the board while Sensed or later (stage >= 1).
function Appointed.isManifest()
  return CampaignState.getAppointedStage() >= 1
end

--- Gains Hunter while Emerging or later (stage >= 2).
function Appointed.isHunter()
  return CampaignState.getAppointedStage() >= 2
end

--------------------------------------------------------------------- targeting --

--- Every investigator tied for the most on-card Memory (sorted ids). Pass a
-- map { investigatorId = memoryCount }. The design gives no tie-break, so the
-- Arkham rule applies: among tied prey the Hunter goes for the nearest, and the
-- lead investigator decides a remaining tie (the board layer does both).
function Appointed.preyCandidates(memoryByInvestigator)
  local best
  for _, m in pairs(memoryByInvestigator or {}) do
    if best == nil or m > best then best = m end
  end
  local out = {}
  for id, m in pairs(memoryByInvestigator or {}) do
    if m == best then out[#out + 1] = id end
  end
  table.sort(out, function(a, b) return tostring(a) < tostring(b) end)
  return out, best
end

--- Prey = the investigator with the most on-card Memory (first tied id, sorted).
function Appointed.prey(memoryByInvestigator)
  return (Appointed.preyCandidates(memoryByInvestigator))[1]
end

------------------------------------------------------------- board manifest --

--- Reconcile the board figure to the current stage: place it at the farthest
-- location when it should be manifest and isn't; remove it when stage drops to 0.
-- ctx.isOnBoard() -> bool, ctx.placeAtFarthest(), ctx.removeFromBoard().
function Appointed.syncBoard(ctx)
  local onBoard = ctx and ctx.isOnBoard and ctx.isOnBoard()
  if Appointed.isManifest() then
    if not onBoard and ctx and ctx.placeAtFarthest then
      ctx.placeAtFarthest()
    end
  else
    if onBoard and ctx and ctx.removeFromBoard then
      ctx.removeFromBoard()
    end
  end
end

--------------------------------------------------------- stage-gated effects --

--- End of round, while Sensed (stage 1 only): each investigator at its location
-- takes 1 horror. Returns horror dealt (0 if not Sensed).
function Appointed.onRoundEnd(ctx)
  if CampaignState.getAppointedStage() == 1 then
    if ctx and ctx.horrorToInvestigatorsAtLocation then
      ctx.horrorToInvestigatorsAtLocation(1)
    end
    return 1
  end
  return 0
end

--- On engaging an investigator, while Emerging (stage 2): that investigator
-- takes 1 horror. Returns horror dealt (0 if not Emerging).
function Appointed.onEngage(ctx)
  if CampaignState.getAppointedStage() == 2 then
    if ctx and ctx.horrorToEngaged then
      ctx.horrorToEngaged(1)
    end
    return 1
  end
  return 0
end

--- The Appointed attacks. ONLY while Arrived (stage 3) does it deal damage: 2
-- damage + 2 horror, then raise Dissonance by 1. A Sensed/Emerging figure does
-- not attack, so this returns zeros below stage 3.
-- @return table {damage, horror, dissonanceRaised}
function Appointed.onAttack(deps)
  if CampaignState.getAppointedStage() < 3 then
    return { damage = 0, horror = 0, dissonanceRaised = false }
  end
  if deps and deps.dissonance then
    deps.dissonance.raise(1, deps.bag)
  else
    CampaignState.raiseDissonance(1)
  end
  return { damage = Appointed.ARRIVED_DAMAGE, horror = Appointed.ARRIVED_HORROR, dissonanceRaised = true }
end

----------------------------------------------------------------- counterplay --

--- Hold Back — call this on a SUCCESSFUL [wil]/[com] (4) test. Pushes the
-- Approach back one stage AND rewinds the Hourglass by 1 Hour, then reconciles
-- the board. Returns the new stage.
function Appointed.holdBack(ctx)
  local newStage = CampaignState.pushBackAppointed()
  Hourglass.rewind(1, ctx)
  Appointed.syncBoard(ctx)
  return newStage
end

--- It cannot be defeated. Any effect that would defeat or remove it is replaced
-- (it does not leave play). Always returns false ("was not defeated").
function Appointed.attemptDefeat()
  return false
end

--- Board hook for the defeat-replacement: the physical card was put into a
-- container, discarded or destroyed. While it is manifest (stage >= 1) it
-- "does not leave play": ctx.returnToPlay() puts it back. At Unseen (0) it is
-- legitimately off the board, so nothing happens. Returns true if restored.
function Appointed.onRemovalAttempt(ctx)
  if Appointed.attemptDefeat() == false and Appointed.isManifest() then
    if ctx and ctx.returnToPlay then ctx.returnToPlay() end
    return true
  end
  return false
end

--------------------------------------------------------------- hunter move --

--- While Emerging or Arrived it has Hunter and moves toward its prey (one
-- location per hunter move). ctx.moveTowardPrey() does the board work.
-- Returns true if it moved (i.e. it is a Hunter and the callback ran).
function Appointed.hunt(ctx)
  if not Appointed.isHunter() then
    return false
  end
  if ctx and ctx.moveTowardPrey then
    return ctx.moveTowardPrey() ~= false
  end
  return true
end

--------------------------------------------------------------- card effects --

--- A card advances the Approach one stage, to a minimum of Sensed (CO-002 §2,
-- the Crossing wording). Ratchets through CampaignState.advanceAppointed, then
-- reconciles the board. Returns the new stage.
function Appointed.advanceByCard(ctx)
  local s = CampaignState.getAppointedStage()
  local newStage = CampaignState.advanceAppointed(math.max(1, s + 1))
  Appointed.syncBoard(ctx)
  return newStage
end

--- It cannot be attacked or evaded either — expose these for callers/UX so the
-- three "cannot" clauses live in one place.
Appointed.canBeAttacked = false
Appointed.canBeEvaded = false
Appointed.canBeDefeated = false

return Appointed

end

__modules["StillHour/Knowledge"] = function()
--- THE STILL HOUR — the Knowledge Track (P6 support).
--
-- The registry of facts about Ambergrove. Facts are unlocked by completing
-- district objectives (CampaignState.unlockFact), never purchased. Flagged facts
-- permanently edit the night — Hours (Hourglass), locations (Locations), and the
-- finale gates handled here. This module is the single source of truth for the
-- fact ids the rest of the code references, plus the Act/finale gates that read
-- how many are known (campaign_guide_v0.5 §7-§8).

local CampaignState = require("StillHour/CampaignState")

local Knowledge = {}

-- id -> { name, district, layer = "prologue"|"surface"|"deep"|"assembled" }
Knowledge.FACTS = {
  ["you-are-unstuck"]          = { name = "You Are Unstuck",           district = "Prologue",    layer = "prologue" },
  ["the-lamp-was-never-lit"]   = { name = "The Lamp Was Never Lit",    district = "Lighthouse",  layer = "surface" },
  ["the-keepers-ninth-death"]  = { name = "The Keeper's Ninth Death",  district = "Lighthouse",  layer = "deep" },
  ["the-thirteenth-toll"]      = { name = "The Thirteenth Toll",       district = "Church",      layer = "surface" },
  ["the-hour-was-wrong"]       = { name = "The Hour Was Wrong",        district = "Church",      layer = "deep" },
  ["the-road-remembers"]       = { name = "The Road Remembers",        district = "Sunken Road", layer = "surface" },
  ["who-walks-beside-you"]     = { name = "Who Walks Beside You",      district = "Sunken Road", layer = "deep" },
  ["the-sheriff-is-already-dead"] = { name = "The Sheriff Is Already Dead", district = "Square", layer = "surface" },
  ["the-vote-that-never-ends"] = { name = "The Vote That Never Ends",  district = "Square",      layer = "deep" },
  ["the-wheel-still-turns"]    = { name = "The Wheel Still Turns",     district = "Fairground",  layer = "surface" },
  ["the-ticket-takers-bargain"] = { name = "The Ticket-Taker's Bargain", district = "Fairground", layer = "deep" },
  ["what-the-almanac-hid"]     = { name = "What the Almanac Hid",      district = "Almanac",     layer = "surface" },
  ["the-appointeds-name"]      = { name = "The Appointed's Name",      district = "Almanac",     layer = "deep" },
  ["the-way-the-night-breaks"] = { name = "The Way the Night Breaks",  district = "(assembled)", layer = "assembled" },
}

function Knowledge.knows(factId)
  return CampaignState.knows(factId)
end

--- Unlock a fact by id. Returns true if newly unlocked. Errors on unknown id so
-- typos surface immediately rather than silently no-op'ing.
function Knowledge.unlock(factId)
  assert(Knowledge.FACTS[factId], "unknown Knowledge fact: " .. tostring(factId))
  return CampaignState.unlockFact(factId)
end

local function countKnownByLayer(layer)
  local n = 0
  for id, f in pairs(Knowledge.FACTS) do
    if f.layer == layer and CampaignState.knows(id) then
      n = n + 1
    end
  end
  return n
end

function Knowledge.surfaceKnownCount()
  return countKnownByLayer("surface")
end

function Knowledge.deepKnownCount()
  return countKnownByLayer("deep")
end

--- Act II opens at the interlude once 3+ surface facts are known (guide §8).
function Knowledge.actIIOpen()
  return Knowledge.surfaceKnownCount() >= 3
end

--- "The Way the Night Breaks" assembles when you know The Appointed's Name, The
-- Vote That Never Ends, and any ONE OTHER deep fact (guide §6.6).
function Knowledge.canAssembleFinale()
  if not (CampaignState.knows("the-appointeds-name") and CampaignState.knows("the-vote-that-never-ends")) then
    return false
  end
  for id, f in pairs(Knowledge.FACTS) do
    if f.layer == "deep" and id ~= "the-appointeds-name" and id ~= "the-vote-that-never-ends"
        and CampaignState.knows(id) then
      return true
    end
  end
  return false
end

--- Unlock the assembled finale fact if its inputs are present. Returns true if it
-- was newly assembled this call.
function Knowledge.assembleFinale()
  if Knowledge.canAssembleFinale() and not CampaignState.knows("the-way-the-night-breaks") then
    return CampaignState.unlockFact("the-way-the-night-breaks")
  end
  return false
end

--- The finale may be attempted once the assembled fact is known.
function Knowledge.finaleAttemptable()
  return CampaignState.knows("the-way-the-night-breaks")
end

return Knowledge

end

__modules["StillHour/Locations"] = function()
--- THE STILL HOUR — location fact-toggles (P6).
--
-- Ambergrove locations have a FRONT (this loop) and, for some, a BACK that a
-- Knowledge fact flips to permanently — a calmer/more navigable version (design
-- §3 "Unremembered"; guide §6). A few locations are SEALED until a fact opens
-- them (the Flooded Crypt, the Sealed Study).
--
-- This module owns which face is active and whether a location is open, read off
-- the Knowledge flags in campaign state. The board layer asks the module which
-- face to show / whether the location is revealed; it never decides itself.
--
-- Fields per location:
--   flipFact    -- fact id that flips FRONT -> BACK (nil = no back)
--   sealedUntil -- list of fact ids ALL required to unseal (nil = always open)

local CampaignState = require("StillHour/CampaignState")

local Locations = {}

Locations.LOCATIONS = {
  -- The Lighthouse
  ["lantern-room"]    = { name = "The Lantern Room",   district = "Lighthouse",  flipFact = "the-lamp-was-never-lit" },
  ["winding-stair"]   = { name = "The Winding Stair",  district = "Lighthouse" },
  ["keepers-quarters"] = { name = "The Keeper's Quarters", district = "Lighthouse" },
  -- The Drowned Church
  ["nave"]            = { name = "The Nave",           district = "Church" },
  ["belfry"]          = { name = "The Belfry",         district = "Church" },
  ["flooded-crypt"]   = { name = "The Flooded Crypt",  district = "Church", sealedUntil = { "the-thirteenth-toll" }, partTwo = true },
  ["vestry"]          = { name = "The Vestry",         district = "Church" },
  -- The Sunken Road
  ["milestones"]      = { name = "The Milestones",     district = "Sunken Road" },
  ["low-bridge"]      = { name = "The Low Bridge",     district = "Sunken Road" },
  ["the-turning"]     = { name = "The Turning",        district = "Sunken Road" },
  -- The Square
  ["town-hall-steps"] = { name = "The Town Hall Steps", district = "Square", flipFact = "the-sheriff-is-already-dead" },
  ["records-office"]  = { name = "The Records Office", district = "Square" },
  ["the-well"]        = { name = "The Well",           district = "Square" },
  -- The Fairground
  ["the-wheel"]       = { name = "The Wheel",          district = "Fairground" },
  ["hall-of-mirrors"] = { name = "The Hall of Mirrors", district = "Fairground" },
  ["ticket-booth"]    = { name = "The Ticket Booth",   district = "Fairground" },
  -- The Almanac House
  ["reading-room"]    = { name = "The Reading Room",   district = "Almanac" },
  ["the-press"]       = { name = "The Press",          district = "Almanac" },
  ["sealed-study"]    = { name = "The Sealed Study",   district = "Almanac",
                          sealedUntil = { "what-the-almanac-hid", "the-vote-that-never-ends" }, partTwo = true },
}

local function loc(id)
  return assert(Locations.LOCATIONS[id], "unknown location: " .. tostring(id))
end

--- Which face is active: "back" once the flip fact is known, else "front".
function Locations.activeFace(id)
  local l = loc(id)
  if l.flipFact and CampaignState.knows(l.flipFact) then
    return "back"
  end
  return "front"
end

--- Sealed until every fact in sealedUntil is known.
function Locations.isSealed(id)
  local l = loc(id)
  if not l.sealedUntil then
    return false
  end
  -- closed until its act 2a can be the current act: Part II only
  if l.partTwo and not CampaignState.inPartTwo() then
    return true
  end
  for _, factId in ipairs(l.sealedUntil) do
    if not CampaignState.knows(factId) then
      return true
    end
  end
  return false
end

function Locations.isOpen(id)
  return not Locations.isSealed(id)
end

--- Convenience descriptor for the board layer / UI.
function Locations.describe(id)
  local l = loc(id)
  return {
    id = id,
    name = l.name,
    district = l.district,
    face = Locations.activeFace(id),
    sealed = Locations.isSealed(id),
  }
end

--- All location ids in a district (for revealing a district on entry).
function Locations.inDistrict(district)
  local ids = {}
  for id, l in pairs(Locations.LOCATIONS) do
    if l.district == district then
      ids[#ids + 1] = id
    end
  end
  table.sort(ids)
  return ids
end

------------------------------------------------------------ card metadata --

-- Physical location cards are keyed by their SCED GMNotes id, e.g.
-- "sthr-loc-lanternroom". Resolve one to a location id here by a normalised
-- match (prefix, case, hyphens and a leading "the" ignored) so the board never
-- keeps its own list of cards. Returns nil for cards this module doesn't know.
Locations.CARD_ID_PREFIX = "sthr-loc-"

local function normalise(s)
  s = string.lower(tostring(s or ""))
  s = s:gsub("[^%a%d]", "")
  s = s:gsub("^the", "")
  return s
end

local byNormalised
function Locations.idForCard(cardId)
  if type(cardId) ~= "string" then return nil end
  if Locations.LOCATIONS[cardId] then return cardId end
  local stem = cardId
  if stem:sub(1, #Locations.CARD_ID_PREFIX) == Locations.CARD_ID_PREFIX then
    stem = stem:sub(#Locations.CARD_ID_PREFIX + 1)
  elseif stem:sub(1, 5) == "sthr-" then
    return nil  -- another Still Hour card type, not a location
  end
  if not byNormalised then
    byNormalised = {}
    for id in pairs(Locations.LOCATIONS) do byNormalised[normalise(id)] = id end
  end
  return byNormalised[normalise(stem)]
end

--- Does this location have a fact-flipped back at all?
function Locations.hasBack(id)
  return loc(id).flipFact ~= nil
end

------------------------------------------------------------- map geometry --

-- Pure graph helpers for board effects that need "farthest" / "toward" (the
-- Appointed's manifest and Hunter move, CO-002 §1). `graph` maps a node key to
-- a list of neighbour keys; the board builds it from SCED location metadata.

--- Breadth-first distances from every node in `sources` (a list of keys).
function Locations.distances(graph, sources)
  local dist, queue, head = {}, {}, 1
  for _, s in ipairs(sources or {}) do
    if graph[s] and dist[s] == nil then
      dist[s] = 0
      queue[#queue + 1] = s
    end
  end
  while queue[head] do
    local node = queue[head]
    head = head + 1
    for _, nb in ipairs(graph[node] or {}) do
      if graph[nb] and dist[nb] == nil then
        dist[nb] = dist[node] + 1
        queue[#queue + 1] = nb
      end
    end
  end
  return dist
end

--- The node farthest (by connections) from all `sources`. Nodes unreachable
-- from the sources are ignored while any reachable one exists. Ties go to
-- `tiebreak(a, b)` (true when a should win) or else to the smaller key.
-- With no sources, every node counts as distance 0 (tiebreak decides).
function Locations.farthest(graph, sources, tiebreak)
  local dist = Locations.distances(graph, sources)
  local anyReachable = next(dist) ~= nil
  local best, bestD
  local keys = {}
  for k in pairs(graph) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
  for _, k in ipairs(keys) do
    local d = dist[k]
    if d == nil and not anyReachable then d = 0 end
    if d ~= nil then
      if best == nil or d > bestD or (d == bestD and tiebreak and tiebreak(k, best)) then
        best, bestD = k, d
      end
    end
  end
  return best, bestD
end

--- One step from `from` along a shortest path toward `to`; returns `from`
-- itself when already there and nil when `to` is unreachable.
function Locations.stepToward(graph, from, to)
  if from == to then return from end
  local dist = Locations.distances(graph, { to })
  if dist[from] == nil then return nil end
  local nbs = {}
  for _, nb in ipairs(graph[from] or {}) do nbs[#nbs + 1] = nb end
  table.sort(nbs, function(a, b) return tostring(a) < tostring(b) end)
  for _, nb in ipairs(nbs) do
    if dist[nb] ~= nil and dist[nb] == dist[from] - 1 then return nb end
  end
  return nil
end

return Locations

end

__modules["StillHour/Interlude"] = function()
--- THE STILL HOUR — the interlude procedure (P7).
--
-- Runs after every reset (guide §4): age each investigator, bank on-card Memory,
-- spend Memory (level-ups + Recollections), then begin the next loop (which
-- enforces the soft cap). This module is the orchestration/logic layer; the TTS
-- interlude panel (buttons in control.lua) calls into it. Board specifics —
-- moving actual Memory tokens, swapping a physical stat line — are the caller's;
-- this module owns the numbers and the rules.
--
-- Memory is a general experience currency (CO-001): buy Recollections at their
-- memoryCost, and level up normal cards at 1 Memory per card level. Both debit
-- the one shared banked pool via CampaignState.

local CampaignState = require("StillHour/CampaignState")
local Aging = require("StillHour/Aging")

local Interlude = {}

-- Recollection Memory prices (mirrors the memoryCost in the card spec / GMNotes).
-- In-engine the panel can instead read memoryCost off each card's GMNotes; this
-- table keeps the logic layer self-contained and testable.
Interlude.RECOLLECTION_COST = {
  ["sthr-foreknowledge"]      = 3,
  ["sthr-dejavu"]             = 4,
  ["sthr-musclememory"]       = 3,
  ["sthr-rehearsedescape"]    = 3,
  ["sthr-longwayround"]       = 2,
  ["sthr-borrowedtime"]       = 4,
  ["sthr-thistimeforsure"]    = 4,
  ["sthr-anchorpoint"]        = 3,
  ["sthr-cassandrasnotebook"] = 4,
  ["sthr-hourlearnedname"]    = 5,
}

--------------------------------------------------------------------- aging --

--- Age one investigator this interlude. `cond` = {defeated, endedInDanger,
-- leanedOnLoop}; `lockedChoice` = {physical, mental} (needed the first time they
-- enter Weathered). Returns the Aging result (years, bracket, drift, agedOut...).
-- When cond.leanedOnLoop is not given it is derived from the investigator's
-- loop tallies (Interlude.leanedOnLoop).
function Interlude.age(investigatorId, cond, lockedChoice)
  cond = cond or {}
  local c = { defeated = cond.defeated, endedInDanger = cond.endedInDanger, leanedOnLoop = cond.leanedOnLoop }
  if c.leanedOnLoop == nil then c.leanedOnLoop = Interlude.leanedOnLoop(investigatorId) end
  return Aging.applyInterlude(investigatorId, c, lockedChoice)
end

--- Age a whole party. `entries` = list of {id, cond, lockedChoice}. Returns a
-- map id -> result.
function Interlude.ageAll(entries)
  local results = {}
  for _, e in ipairs(entries or {}) do
    results[e.id] = Interlude.age(e.id, e.cond, e.lockedChoice)
  end
  return results
end

--------------------------------------------------------------------- memory --

--- Bank on-card Memory into the campaign pool (not yet capped; the cap applies
-- at loop start).
function Interlude.bank(amount)
  return CampaignState.bankMemory(amount)
end

--- Guide §4 step 2: move every investigator's on-card Memory to the bank.
-- Returns the amount moved.
function Interlude.bankOnCard()
  return CampaignState.bankOnCardMemory()
end

--- "Leaned on the loop" for Aging, derived from the investigator's own tallies
-- (raised Dissonance 3+ times OR spent 4+ Memory on loop powers). No override.
function Interlude.leanedOnLoop(investigatorId)
  local t = CampaignState.getTallies(investigatorId)
  return Aging.leanedOnLoop(t.raises, t.spent)
end

--- "Ended in danger" for Aging, from the Dissonance recorded when the loop ended.
function Interlude.loopEndedInDanger()
  local d = CampaignState.getLastLoopEndDissonance()
  if d == nil then return false end
  return Aging.loopEndedInDanger(d, CampaignState.constants().investigators)
end

function Interlude.recollectionCost(cardId)
  return Interlude.RECOLLECTION_COST[cardId]
end

function Interlude.canAfford(cost)
  return cost ~= nil and CampaignState.getBankedMemory() >= cost
end

--- Buy a Recollection into a deck. Returns true on success, false if unknown id
-- or the pool can't cover its memoryCost.
function Interlude.buyRecollection(cardId)
  local cost = Interlude.RECOLLECTION_COST[cardId]
  if cost == nil then
    return false
  end
  return CampaignState.purchaseRecollection(cost)
end

--- Level up a normal card: cost = the target card level (1-5). Returns success.
function Interlude.buyUpgrade(cardLevel)
  if type(cardLevel) ~= "number" or cardLevel < 1 or cardLevel > 5 then
    return false
  end
  return CampaignState.purchaseUpgrade(cardLevel)
end

--------------------------------------------------------------- loop handoff --

--- Begin the next loop's play: enforce the Memory soft cap (6 x investigators).
-- Call at the end of the interlude, before loop setup.
function Interlude.beginNextLoop()
  local s = CampaignState.startLoop()
  CampaignState.clearTallies()     -- the new loop starts its own tallies
  -- Elder/Ancient: "begin each loop with 1 Memory on your investigator card".
  for id in pairs(s.years or {}) do
    local drift = Aging.driftFor(id)
    if drift and drift.startLoopMemory > 0 and CampaignState.getOnCardMemory(id) < drift.startLoopMemory then
      CampaignState.setOnCardMemory(id, drift.startLoopMemory)
    end
  end
  return s
end

return Interlude

end

__modules["StillHour/SCED"] = function()
--- THE STILL HOUR — thin, fail-safe adapter over SCED's public API.
--
-- Every call here mirrors a real SCED API wrapper, verified against the
-- argonui/SCED source (src/chaosbag/ChaosBagApi.ttslua, src/core/
-- GUIDReferenceApi.ttslua, src/playarea/PlayAreaApi.ttslua, src/tokens/
-- TokenSpawnTrackerApi.ttslua, src/tokens/TokenManagerApi.ttslua). We call the
-- same Global functions / reference-handler lookups those wrappers make, rather
-- than requiring SCED's modules (they are not in this bundle).
--
-- Nothing here ever raises: each entry point is pcall-guarded and returns nil /
-- false when SCED (or TTS itself) is absent, so the campaign runs on a vanilla
-- table and inside the offline test harnesses.

local SCED = {}

-- SCED's GUIDReferenceHandler lives at this fixed GUID
-- (GUIDReferenceApi.ttslua: getObjectFromGUID("123456").call(...)).
SCED.REFERENCE_HANDLER_GUID = "123456"

local function try(fn, ...)
  local ok, v = pcall(fn, ...)
  if ok then return v end
  return nil
end

--- Global.call(name, param), or nil if Global/the function is unavailable.
function SCED.globalCall(name, param)
  return try(function()
    if Global == nil then return nil end
    return Global.call(name, param)
  end)
end

local function handler()
  return try(function()
    if type(getObjectFromGUID) ~= "function" then return nil end
    return getObjectFromGUID(SCED.REFERENCE_HANDLER_GUID)
  end)
end

--- True when this table is running SCED: its Global publishes MOD_VERSION
-- (core/Constants.ttslua, required by Global) and the GUID reference handler
-- object exists.
function SCED.isPresent()
  local version = try(function()
    if Global == nil then return nil end
    return Global.getVar("MOD_VERSION")
  end)
  return type(version) == "string" and handler() ~= nil
end

function SCED.version()
  return try(function() return Global.getVar("MOD_VERSION") end)
end

--- GUIDReferenceApi.getObjectByOwnerAndType(owner, type).
function SCED.getObjectByOwnerAndType(owner, objType)
  local h = handler()
  if not h then return nil end
  return try(function()
    return h.call("getObjectByOwnerAndType", { owner = owner, type = objType })
  end)
end

------------------------------------------------------------------ chaos bag --

--- ChaosBagApi.findChaosBag() -> Global.findChaosBag().
function SCED.findChaosBag()
  if not SCED.isPresent() then return nil end
  return SCED.globalCall("findChaosBag")
end

--- ChaosBagApi.canTouchChaosTokens(): false while someone searches the bag
-- (SCED blocks bag edits then to dodge a TTS token-vanishing bug).
function SCED.canTouchChaosTokens()
  if not SCED.isPresent() then return true end
  local v = SCED.globalCall("canTouchChaosTokens")
  return v ~= false
end

--- ChaosBagApi.getTokensInPlay() -> Global.getChaosTokensinPlay() (drawn,
-- not sealed). Returns a list of objects (possibly empty).
function SCED.getTokensInPlay()
  if not SCED.isPresent() then return {} end
  local t = SCED.globalCall("getChaosTokensinPlay")
  if type(t) ~= "table" then return {} end
  return t
end

--- ChaosBagApi.getChaosBagState() -> list of SCED token ids in the bag.
-- (Tokens SCED does not know — like [static] — are skipped by SCED itself.)
function SCED.getChaosBagState()
  if not SCED.isPresent() then return nil end
  return SCED.globalCall("getChaosBagState")
end

------------------------------------------------------------------- play area --

--- PlayAreaApi.isInPlayArea(object). nil when SCED is absent.
function SCED.isInPlayArea(obj)
  local pa = SCED.getObjectByOwnerAndType("Mythos", "PlayArea")
  if not pa then return nil end
  return try(function() return pa.call("isInPlayArea", obj) end)
end

--- PlayAreaApi.getInvestigatorCount() (the Mythos investigator counter's val).
function SCED.getInvestigatorCount()
  local counter = SCED.getObjectByOwnerAndType("Mythos", "InvestigatorCounter")
  if not counter then return nil end
  local v = try(function() return counter.getVar("val") end)
  if type(v) == "number" and v >= 1 then return v end
  return nil
end

--------------------------------------------------------------- token spawns --

local function spawnTracker()
  return SCED.getObjectByOwnerAndType("Mythos", "TokenSpawnTracker")
end

--- TokenSpawnTrackerApi.hasSpawnedTokens(objOrGuid).
function SCED.hasSpawnedTokens(objOrGuid)
  local t = spawnTracker()
  if not t then return nil end
  return try(function() return t.call("hasSpawnedTokens", objOrGuid) end)
end

--- TokenSpawnTrackerApi.markTokensSpawned(objOrGuid): SCED then skips the
-- card's automatic clue/uses spawn (Global TokenManager.spawnForCard returns
-- early when hasSpawnedTokens is true).
function SCED.markTokensSpawned(objOrGuid)
  local t = spawnTracker()
  if not t then return false end
  return try(function() t.call("markTokensSpawned", objOrGuid) ; return true end) or false
end

--- TokenSpawnTrackerApi.resetTokensSpawned(objOrGuid).
function SCED.resetTokensSpawned(objOrGuid)
  local t = spawnTracker()
  if not t then return false end
  return try(function() t.call("resetTokensSpawned", objOrGuid) ; return true end) or false
end

--- TokenManagerApi.spawnForCard(card): Global.callTable routing into
-- TokenManager.spawnForCard (spawns the side's `uses`, e.g. location clues).
function SCED.spawnForCard(card)
  if not SCED.isPresent() then return false end
  SCED.globalCall("callTable", { { "TokenManager", "spawnForCard" }, { card = card } })
  return true
end

------------------------------------------------------------------ playmats --

-- SCED's four mat colours (core/GUIDReferenceHandler.ttslua owners).
SCED.MAT_COLORS = { "White", "Orange", "Green", "Red" }

--- The playermat object for a mat colour (GUIDReferenceApi owner/type lookup).
function SCED.playermat(matColor)
  return SCED.getObjectByOwnerAndType(matColor, "Playermat")
end

--- PlayermatApi.getActiveInvestigatorData(matColor) -> {id, class, miniId, ...}.
-- Playermat.ttslua fills it when an investigator card lands on the mat.
function SCED.activeInvestigatorData(matColor)
  local mat = SCED.playermat(matColor)
  if not mat then return nil end
  local d = try(function() return mat.call("getActiveInvestigatorData") end)
  if type(d) == "table" then return d end
  return nil
end

--- Set a mat's skill tracker the way Playermat.maybeUpdateActiveInvestigator
-- does: ownedObjects.InvestigatorSkillTracker.call("updateStats", {wil, int, com, agi}).
function SCED.setSkillTracker(matColor, wil, int, com, agi)
  local tracker = SCED.getObjectByOwnerAndType(matColor, "InvestigatorSkillTracker")
  if not tracker then return false end
  return try(function() tracker.call("updateStats", { wil, int, com, agi }) ; return true end) or false
end

return SCED

end

__modules["StillHour/ChaosBag"] = function()
--- THE STILL HOUR — the real chaos-bag adapter for Dissonance (P3 board wiring).
--
-- Implements the adapter contract Dissonance.ttslua expects:
--     bag.setBaselineStatic(n)            -- exactly n baseline [static] tokens
--     bag.addStatic(n) / bag.removeStatic(n)  -- temporary extras (Hour VI)
-- and drives PHYSICAL [static] tokens in the table's chaos bag.
--
-- Where the bag comes from (first match wins):
--   1. SCED: ChaosBagApi.findChaosBag() (Global.findChaosBag, via SCED.ttslua).
--   2. Any table: a top-level container named/described "Chaos Bag" (the same
--      test SCED's own findChaosBag uses on the Mythos area).
--   3. Neither: a virtual bag — the count is tracked, nothing is touched. This
--      is the vanilla-table / offline fallback and never errors.
--
-- SCED's own spawnChaosToken/removeChaosToken only accept ids from its
-- ID_URL_MAP (core/Constants.ttslua), so a custom token cannot go through them.
-- Instead this adapter follows exactly what those Global functions do: it
-- respects canTouchChaosTokens(), spawns a Custom_Tile token (same data shape as
-- Global.spawnChaosToken) and puts it in the bag, and removes one by
-- takeObject({guid}) + destruct (as Global.removeChaosToken does).
-- Our tokens carry the tag below so they are recognised in and out of the bag.
--
-- Counting: tokens in the bag + our tokens that were drawn out of it and still
-- exist (revealed, sitting on a playmat) + spawns/removals still in flight.
-- SCED's getChaosBagState()/campaign export skips unknown token names, so the
-- [static] count is never exported; syncBag() rebuilds it from Dissonance.

local SCED = require("StillHour/SCED")

local ChaosBag = {}

ChaosBag.TOKEN_TAG = "StillHourStatic"
ChaosBag.TOKEN_NAME = "Static"
ChaosBag.TOKEN_DESCRIPTION = "[static] chaos token (-3). When revealed, raise Dissonance by 1."
-- Replaced with the hosted image URL by pipeline/bundle_mod.py.
ChaosBag.TOKEN_IMAGE_URL = "https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/41b29cef7b0c6a6999c49669e35641272f59c7a3/dist/cards/sthr-static-token.jpg?v=a556271511"
ChaosBag.BAG_NAME = "Chaos Bag"

--- Object data for one [static] token. Mirrors SCED Global.spawnChaosToken's
-- tokenData (Custom_Tile, circular CustomTile Type 2, thickness 0.1, scale 0.81).
function ChaosBag.tokenData(pos)
  pos = pos or { x = 0, y = 2, z = 0 }
  return {
    Name = "Custom_Tile",
    Nickname = ChaosBag.TOKEN_NAME,
    Description = ChaosBag.TOKEN_DESCRIPTION,
    Tags = { ChaosBag.TOKEN_TAG },
    ColorDiffuse = { r = 1, g = 1, b = 1 },
    Hands = false,
    HideWhenFaceDown = false,
    CustomImage = {
      ImageURL = ChaosBag.TOKEN_IMAGE_URL,
      ImageSecondaryURL = "",
      ImageScalar = 1,
      WidthScale = 0,
      CustomTile = { Type = 2, Thickness = 0.1, Stretch = true, Stackable = false },
    },
    Transform = {
      posX = pos.x, posY = pos.y, posZ = pos.z,
      rotX = 0, rotY = 0, rotZ = 0,
      scaleX = 0.81, scaleY = 1, scaleZ = 0.81,
    },
  }
end

local function safe(fn, ...)
  local ok, v = pcall(fn, ...)
  if ok then return v end
  return nil
end

--- Is `obj` one of our [static] tokens?
function ChaosBag.isStaticToken(obj)
  if obj == nil then return false end
  return safe(function()
    if obj.hasTag and obj.hasTag(ChaosBag.TOKEN_TAG) then return true end
    return false
  end) or false
end

--- Is `container` a chaos bag? Same name/description test as SCED findChaosBag.
function ChaosBag.isChaosBag(container)
  if container == nil then return false end
  return safe(function()
    return container.getName() == ChaosBag.BAG_NAME
      or (container.getDescription and container.getDescription() == ChaosBag.BAG_NAME)
  end) or false
end

local function entryIsStatic(entry)
  for _, t in ipairs(entry.tags or {}) do
    if t == ChaosBag.TOKEN_TAG then return true end
  end
  return false
end

--- Build an adapter. opts.log(msg) receives notices (optional).
function ChaosBag.new(opts)
  opts = opts or {}
  local log = opts.log or function() end

  local a = {
    baseline = 0,      -- band-driven baseline (Dissonance.syncBag)
    extra = 0,         -- temporary extras (Hour VI) until the next reset
    count = 0,         -- the target count (virtual bag's contents)
    pendingAdd = 0,
    pendingRemove = 0,
    removing = {},     -- guid -> true while we take a token out to destroy it
    out = {},          -- guid -> true: our tokens drawn out of the bag
    retryScheduled = false,
    lastMode = "virtual",
  }

  --- The chaos bag object, or nil (virtual mode).
  function a.findBag()
    if SCED.isPresent() then
      local bag = SCED.findChaosBag()
      if bag then a.lastMode = "sced" ; return bag end
    end
    local found = safe(function()
      if type(getObjects) ~= "function" then return nil end
      for _, o in ipairs(getObjects()) do
        if o.type == "Bag" and ChaosBag.isChaosBag(o) then return o end
      end
      return nil
    end)
    a.lastMode = found and "table" or "virtual"
    return found
  end

  function a.target()
    return math.max(0, a.baseline + a.extra)
  end

  --- Tokens drawn out of the bag that still exist on the table.
  local function outCount()
    local n = 0
    for guid in pairs(a.out) do
      local o = safe(function() return getObjectFromGUID(guid) end)
      if o ~= nil then n = n + 1 else a.out[guid] = nil end
    end
    return n
  end

  local function inBag(bag)
    local list = {}
    for _, e in ipairs(safe(function() return bag.getObjects() end) or {}) do
      if entryIsStatic(e) and not a.removing[e.guid] then list[#list + 1] = e.guid end
    end
    return list
  end

  --- Physical count (nil when there is no bag).
  function a.physicalCount()
    local bag = a.findBag()
    if not bag then return nil end
    return #inBag(bag) + outCount() + a.pendingAdd
  end

  local function spawnOne(bag)
    local p = safe(function() return bag.getPosition() end) or { x = 0, y = 1, z = 0 }
    a.pendingAdd = a.pendingAdd + 1
    local ok = pcall(spawnObjectData, {
      data = ChaosBag.tokenData({ x = p.x, y = (p.y or 1) + 2, z = p.z }),
      callback_function = function(o)
        a.pendingAdd = math.max(0, a.pendingAdd - 1)
        pcall(function() bag.putObject(o) end)
      end,
    })
    if not ok then a.pendingAdd = math.max(0, a.pendingAdd - 1) end
  end

  local function removeOne(bag, guid)
    a.removing[guid] = true
    a.pendingRemove = a.pendingRemove + 1
    local ok = pcall(function()
      bag.takeObject({
        guid = guid, smooth = false,
        callback_function = function(o)
          a.pendingRemove = math.max(0, a.pendingRemove - 1)
          a.removing[guid] = nil
          pcall(function() o.destruct() end)
        end,
      })
    end)
    if not ok then
      a.removing[guid] = nil
      a.pendingRemove = math.max(0, a.pendingRemove - 1)
    end
  end

  local function scheduleRetry()
    if a.retryScheduled then return end
    a.retryScheduled = true
    pcall(function()
      Wait.time(function() a.retryScheduled = false ; a.reconcile() end, 2)
    end)
  end

  --- Bring the physical bag to target(). Safe to call any time.
  function a.reconcile()
    a.count = a.target()
    local bag = a.findBag()
    if not bag then return a.count end
    if not SCED.canTouchChaosTokens() then
      scheduleRetry()
      return a.count
    end
    local present = inBag(bag)
    local have = #present + outCount() + a.pendingAdd
    local delta = a.count - have
    if delta > 0 then
      for _ = 1, delta do spawnOne(bag) end
      log(string.format("[static] +%d into the chaos bag (now %d)", delta, a.count))
    elseif delta < 0 then
      local n = math.min(-delta, #present)
      for i = 1, n do removeOne(bag, present[i]) end
      if n > 0 then log(string.format("[static] -%d from the chaos bag (now %d)", n, a.count)) end
      if n < -delta then scheduleRetry() end  -- the rest are drawn; retry once returned
    end
    return a.count
  end

  -- Dissonance adapter contract --------------------------------------------
  function a.setBaselineStatic(n)
    a.baseline = math.max(0, math.floor(n or 0))
    return a.reconcile()
  end

  function a.addStatic(n)
    a.extra = a.extra + math.max(0, math.floor(n or 1))
    return a.reconcile()
  end

  function a.removeStatic(n)
    a.extra = math.max(0, a.extra - math.max(0, math.floor(n or 1)))
    return a.reconcile()
  end

  --- Temporary [static] lasts "until the next reset" (Hour VI).
  function a.clearTemporary()
    a.extra = 0
    return a.reconcile()
  end

  -- Event plumbing (forwarded by the host object's universal event handlers) ---

  --- onObjectLeaveContainer: returns true if this is a REVEAL (one of our
  -- tokens drawn out of the chaos bag by anyone but this adapter).
  function a.onLeave(container, obj)
    if not ChaosBag.isStaticToken(obj) or not ChaosBag.isChaosBag(container) then
      return false
    end
    local guid = safe(function() return obj.getGUID() end) or obj.guid
    if guid and a.removing[guid] then return false end
    if guid then a.out[guid] = true end
    return true
  end

  --- onObjectEnterContainer: a drawn token went back into the bag.
  function a.onEnter(container, obj)
    if ChaosBag.isStaticToken(obj) and ChaosBag.isChaosBag(container) then
      local guid = safe(function() return obj.getGUID() end) or obj.guid
      if guid then a.out[guid] = nil end
    end
  end

  --- Cheap summary for labels (no bag lookup); pass true to also count the
  -- physical tokens (looks the bag up).
  function a.describe(withPhysical)
    local phys = withPhysical and a.physicalCount() or nil
    return { mode = a.lastMode, target = a.target(), baseline = a.baseline,
             extra = a.extra, physical = phys }
  end

  function a.save()
    local out = {}
    for g in pairs(a.out) do out[#out + 1] = g end
    return { baseline = a.baseline, extra = a.extra, out = out }
  end

  function a.load(t)
    if type(t) ~= "table" then return end
    a.baseline = tonumber(t.baseline) or 0
    a.extra = tonumber(t.extra) or 0
    a.out = {}
    for _, g in ipairs(t.out or {}) do a.out[g] = true end
    a.count = a.target()
  end

  return a
end

return ChaosBag

end

__modules["StillHour/Board"] = function()
--- THE STILL HOUR — board plumbing (BUILD_STATUS "path to the table" item 2).
--
-- Connects the logic modules to physical objects on the table. No rules live
-- here: which face a location shows / whether it is sealed comes from
-- Locations; when the Appointed is on the board, whether it hunts, and that it
-- cannot leave play come from Appointed. This file only finds objects, reads
-- their SCED metadata, and moves / flips / labels them.
--
-- Everything is keyed on card metadata (the SCED GMNotes JSON `id`, `type`,
-- `locationFront` / `locationBack` {icons, connections}; see
-- docs/art_reference/sced_objects/location_*.json), never on a content list.
-- Investigators are located by their minicards (SCED Tags ["Minicard"]).
--
-- TTS API used (Berserk-Games/Tabletop-Simulator-API docs): getObjects,
-- getObjectFromGUID, Object.getGMNotes/getPosition/getRotation/setPosition/
-- setRotation/is_face_down/hasTag/getObjects/takeObject/createButton/
-- getButtons/removeButton/clearButtons/getData, spawnObjectData, Wait.frames.
-- SCED API (via SCED.ttslua): PlayAreaApi.isInPlayArea,
-- TokenSpawnTrackerApi.mark/resetTokensSpawned, TokenManagerApi.spawnForCard.
--
-- All entry points are pcall-guarded by the host (control.lua); on a vanilla
-- table they simply find fewer objects.

local Aging = require("StillHour/Aging")
local Appointed = require("StillHour/Appointed")
local CampaignState = require("StillHour/CampaignState")
local Locations = require("StillHour/Locations")
local SCED = require("StillHour/SCED")

local Board = {}

Board.APPOINTED_ID = "sthr-appointed"
Board.MINICARD_TAG = "Minicard"
Board.SEALED_LABEL = "CLOSED"
Board.OCCUPY_RADIUS = 2.0       -- a minicard within this of a location's centre is "at" it
Board.APPOINTED_OFFSET = { x = 0, y = 0.6, z = -0.9 }

local host                       -- the object owning the button callbacks
local say = function() end
local st = {
  flipped = {},        -- guid -> true: location we flipped to its back
  sealedMarked = {},   -- guid -> true: SCED clue auto-spawn suppressed by us
  sealedLabel = {},    -- guid -> true: we put a SEALED label on it
  appointed = { guid = nil, placed = false, lastPos = nil, lastRot = nil },
}
local restoreScheduled = false
local restoreData = nil

------------------------------------------------------------------ utilities --

local function safe(fn, ...)
  local ok, v = pcall(fn, ...)
  if ok then return v end
  return nil
end

local function decode(s)
  if type(s) ~= "string" or s == "" or JSON == nil then return nil end
  local ok, v = pcall(JSON.decode, s)
  if ok and type(v) == "table" then return v end
  return nil
end

local function vec(p)
  if p == nil then return nil end
  return { x = p.x or p[1] or 0, y = p.y or p[2] or 0, z = p.z or p[3] or 0 }
end

local function dist2d(a, b)
  local dx, dz = a.x - b.x, a.z - b.z
  return math.sqrt(dx * dx + dz * dz)
end

local function topLevel()
  return safe(function()
    if type(getObjects) ~= "function" then return {} end
    return getObjects()
  end) or {}
end

local function guidOf(o)
  return safe(function() return o.getGUID() end) or safe(function() return o.guid end)
end

local function metaOf(o)
  return decode(safe(function() return o.getGMNotes() end))
end

local function isCard(o)
  return safe(function() return o.type == "Card" end) == true
end

local function split(s)
  local out = {}
  for part in string.gmatch(tostring(s or ""), "[^|]+") do out[#out + 1] = part end
  return out
end

------------------------------------------------------------------- lifecycle --

function Board.init(hostObject, opts)
  host = hostObject
  opts = opts or {}
  say = opts.log or say
end

function Board.save()
  return st
end

function Board.load(t)
  if type(t) ~= "table" then return end
  st.flipped = t.flipped or {}
  st.sealedMarked = t.sealedMarked or {}
  st.sealedLabel = t.sealedLabel or {}
  st.appointed = t.appointed or { placed = false }
end

------------------------------------------------------------------- scanning --

--- Location cards on the table: {obj, md, guid, locId, side, pos}.
-- locId is nil for locations this campaign does not define (still map nodes).
function Board.locationCards()
  local out = {}
  for _, o in ipairs(topLevel()) do
    if isCard(o) then
      local md = metaOf(o)
      if md and md.type == "Location" then
        local down = safe(function() return o.is_face_down end) == true
        local side = (down and md.locationBack or md.locationFront)
          or md.locationFront or md.locationBack or {}
        out[#out + 1] = { obj = o, md = md, guid = guidOf(o), locId = Locations.idForCard(md.id),
                          side = side, pos = vec(safe(function() return o.getPosition() end)) }
      end
    end
  end
  return out
end

--- Graph keyed by guid, from each visible side's icons/connections (the same
-- data SCED's PlayArea uses to draw connection lines). Undirected.
function Board.graph(locs)
  local graph, byIcon = {}, {}
  for _, l in ipairs(locs) do
    graph[l.guid] = {}
    for _, icon in ipairs(split(l.side.icons)) do
      byIcon[icon] = byIcon[icon] or {}
      table.insert(byIcon[icon], l.guid)
    end
  end
  local seen = {}
  local function link(a, b)
    if a == b then return end
    local k = a < b and (a .. ">" .. b) or (b .. ">" .. a)
    if seen[k] then return end
    seen[k] = true
    table.insert(graph[a], b)
    table.insert(graph[b], a)
  end
  for _, l in ipairs(locs) do
    for _, icon in ipairs(split(l.side.connections)) do
      for _, other in ipairs(byIcon[icon] or {}) do link(l.guid, other) end
    end
  end
  return graph
end

--- The location a position is at (nearest centre within radius), or nil.
local function locationAt(locs, pos, radius)
  if not pos then return nil end
  local best, bestD
  for _, l in ipairs(locs) do
    if l.pos then
      local d = dist2d(pos, l.pos)
      if d <= (radius or Board.OCCUPY_RADIUS) and (bestD == nil or d < bestD) then
        best, bestD = l, d
      end
    end
  end
  return best
end

--- Investigator minicards: {obj, pos}.
function Board.minicards()
  local out = {}
  for _, o in ipairs(topLevel()) do
    if safe(function() return o.hasTag(Board.MINICARD_TAG) end) then
      out[#out + 1] = { obj = o, pos = vec(safe(function() return o.getPosition() end)) }
    end
  end
  return out
end

--- Location guids that hold at least one investigator.
function Board.occupied(locs)
  local out, seen = {}, {}
  for _, m in ipairs(Board.minicards()) do
    local l = locationAt(locs, m.pos)
    if l and not seen[l.guid] then seen[l.guid] = true ; out[#out + 1] = l.guid end
  end
  return out
end

------------------------------------------------------------- investigators --

-- An investigator is known by its card metadata id (e.g. "sthrelias"). Its
-- minicard carries the SCED minicard id "<id>-m" (docs/art_reference/
-- sced_objects/minicard.json). Under SCED the mat colour comes from
-- PlayermatApi.getActiveInvestigatorData(matColor).id. We match minicards by
-- stripping "-m" rather than trusting SCED's miniId: Global.getMiniId keeps
-- only the first five characters of a short hyphenated id, which for
-- "sthr-..." ids gives "sthr--m" for everyone.

local function minicardInvestigatorId(md)
  if not md or type(md.id) ~= "string" then return nil end
  local base = md.id:match("^(.*)%-m$")
  return base
end

--- Investigators in play: list of {id, name, matColor, card, md, minicard}.
function Board.investigators()
  local cards, minis = {}, {}
  for _, o in ipairs(topLevel()) do
    if isCard(o) then
      local md = metaOf(o)
      if md and md.type == "Investigator" and type(md.id) == "string" and not cards[md.id] then
        cards[md.id] = { obj = o, md = md }
      end
      local hasMini = safe(function() return o.hasTag(Board.MINICARD_TAG) end)
      local mid = hasMini and minicardInvestigatorId(md)
      if mid and not minis[mid] then minis[mid] = o end
    end
  end
  local out, seen = {}, {}
  local function add(id, matColor)
    if seen[id] then return end
    seen[id] = true
    local c = cards[id]
    out[#out + 1] = {
      id = id, matColor = matColor,
      name = c and (safe(function() return c.obj.getName() end) or id) or id,
      card = c and c.obj, md = c and c.md, minicard = minis[id],
    }
  end
  if SCED.isPresent() then
    for _, colour in ipairs(SCED.MAT_COLORS) do
      local d = SCED.activeInvestigatorData(colour)
      if d and type(d.id) == "string" and d.id ~= "" and d.id ~= "00000" then add(d.id, colour) end
    end
  end
  local rest = {}
  for id in pairs(cards) do if not seen[id] then rest[#rest + 1] = id end end
  table.sort(rest)
  for _, id in ipairs(rest) do add(id, nil) end
  return out
end

--- Where the Appointed hunts: the location (guid) of its prey, and a short
-- reason. Prey = most on-card Memory (Appointed.preyCandidates); among tied
-- prey it goes for the nearest; a tie that remains is the lead investigator's
-- call (Arkham rules), so the first by id is used and the table is told.
function Board.preyLocation(locs, graph, here)
  local memory, locOf, nameOf = {}, {}, {}
  for _, inv in ipairs(Board.investigators()) do
    local p = inv.minicard and vec(safe(function() return inv.minicard.getPosition() end))
    local l = p and locationAt(locs, p)
    if l then
      memory[inv.id] = CampaignState.getOnCardMemory(inv.id)
      locOf[inv.id], nameOf[inv.id] = l.guid, inv.name
    end
  end
  local dist = here and Locations.distances(graph, { here.guid }) or {}
  local function nearest(guids)
    local best, bestD, ties = nil, nil, 0
    for _, g in ipairs(guids) do
      local d = dist[g] or math.huge
      if bestD == nil or d < bestD then best, bestD, ties = g, d, 1
      elseif d == bestD and g ~= best then ties = ties + 1 end
    end
    return best, ties
  end
  if next(memory) == nil then
    -- no minicard can be tied to an investigator: nearest investigator
    local occ = Board.occupied(locs)
    if #occ == 0 then return nil end
    return (nearest(occ)), "nearest investigator"
  end
  local cands, most = Appointed.preyCandidates(memory)
  local guids, byGuid = {}, {}
  for _, id in ipairs(cands) do
    guids[#guids + 1] = locOf[id]
    byGuid[locOf[id]] = byGuid[locOf[id]] or id
  end
  local g, ties = nearest(guids)
  local id = byGuid[g]
  local why
  if #cands == 1 then
    why = string.format("prey: %s, most Memory (%d)", nameOf[id], most)
  elseif ties <= 1 then
    why = string.format("prey: %s, nearest of those tied at %d Memory", nameOf[id], most)
  else
    why = string.format("prey: %s; tied at %d Memory and distance, lead investigator may choose", nameOf[id], most)
  end
  return g, why
end

local function removeByPrefix(o, prefixes)
  local buttons = safe(function() return o.getButtons() end) or {}
  for i = #buttons, 1, -1 do
    local label = buttons[i].label or ""
    for _, p in ipairs(prefixes) do
      if label:sub(1, #p) == p then
        safe(function() o.removeButton(buttons[i].index or (i - 1)) end)
        break
      end
    end
  end
end

Board.INV_PREFIXES = { "Memory ", "Years ", "Dissonance raised ", "Loop-power Memory " }

--- The printed stat line from investigator metadata (SCED GMNotes keys).
function Board.baseStats(md)
  if not md then return nil end
  return { wil = md.willpowerIcons or 1, int = md.intellectIcons or 1, com = md.combatIcons or 1,
           agi = md.agilityIcons or 1, health = md.health or 1, sanity = md.sanity or 1 }
end

--- Apply Aging to one investigator in play: the SCED skill tracker on their mat
-- gets the drifted skills; the card shows Years / bracket / drifted maxima.
-- Returns the effective stat line (or nil without metadata).
function Board.applyAging(inv, toTracker)
  local base = Board.baseStats(inv.md)
  if not base then return nil end
  local eff = Aging.applyDriftToStats(base, inv.id)
  if toTracker and inv.matColor then
    SCED.setSkillTracker(inv.matColor, eff.wil, eff.int, eff.com, eff.agi)
  end
  return eff
end

--- Memory / Years buttons on every investigator card (idempotent). With
-- applyStats, also push the aged skills to the SCED skill trackers — only done
-- on purpose (Age, Begin Next Loop, Sync Board) so a player's own tracker
-- adjustments are not overwritten on every click.
function Board.refreshInvestigators(applyStats)
  local out = {}
  for _, inv in ipairs(Board.investigators()) do
    local eff = Board.applyAging(inv, applyStats)
    local card = inv.card
    if card and host then
      removeByPrefix(card, Board.INV_PREFIXES)
      local years = CampaignState.getYears(inv.id)
      local yearsLabel = string.format("Years %d · %s", years, Aging.bracketForYears(years))
      if eff and inv.md and (eff.health ~= inv.md.health or eff.sanity ~= inv.md.sanity) then
        yearsLabel = yearsLabel .. string.format(" · max %d/%d", eff.health, eff.sanity)
      end
      safe(function()
        card.createButton({
          click_function = "shCardMemory", function_owner = host,
          label = "Memory " .. CampaignState.getOnCardMemory(inv.id),
          tooltip = "Memory on this investigator's cards. Left-click +1 · Right-click -1",
          position = { -0.75, 0.3, 1.25 }, rotation = { 0, 0, 0 },
          width = 620, height = 200, font_size = 120,
          color = { 0.12, 0.08, 0.16 }, font_color = { 0.95, 0.85, 0.6 },
        })
        card.createButton({
          click_function = "shNoop", function_owner = host, label = yearsLabel,
          tooltip = "Years lived in the loop (Aging). Skills on the playmat tracker include the drift.",
          position = { 0.65, 0.3, 1.25 }, rotation = { 0, 0, 0 },
          width = 0, height = 0, font_size = 90, font_color = { 0.95, 0.85, 0.6 },
        })
        -- "leaned on the loop" tallies (aging v0.3 §1.1), this investigator's own
        local t = CampaignState.getTallies(inv.id)
        card.createButton({
          click_function = "shCardRaised", function_owner = host,
          label = "Dissonance raised " .. t.raises,
          tooltip = "Times THIS investigator raised Dissonance this loop (3+ = leaned on the loop). "
            .. "Left-click +1 · Right-click -1",
          position = { -0.75, 0.3, 1.65 }, rotation = { 0, 0, 0 },
          width = 760, height = 180, font_size = 90,
          color = { 0.12, 0.08, 0.16 }, font_color = { 0.95, 0.85, 0.6 },
        })
        card.createButton({
          click_function = "shCardSpent", function_owner = host,
          label = "Loop-power Memory " .. t.spent,
          tooltip = "Memory THIS investigator spent on loop powers (Recollections, foreknowledge) "
            .. "this loop (4+ = leaned on the loop). Left-click +1 · Right-click -1",
          position = { 0.75, 0.3, 1.65 }, rotation = { 0, 0, 0 },
          width = 760, height = 180, font_size = 90,
          color = { 0.12, 0.08, 0.16 }, font_color = { 0.95, 0.85, 0.6 },
        })
      end)
    end
    local t = CampaignState.getTallies(inv.id)
    out[#out + 1] = { id = inv.id, name = inv.name, matColor = inv.matColor, stats = eff,
                      hasCard = card ~= nil, hasMinicard = inv.minicard ~= nil,
                      raises = t.raises, spent = t.spent }
  end
  return out
end

--- Investigator id for an investigator card object (for its button clicks).
function Board.investigatorIdOf(o)
  local md = metaOf(o)
  if md and md.type == "Investigator" then return md.id end
  return nil
end

------------------------------------------------------------------ locations --

local function removeLabel(o, label)
  local buttons = safe(function() return o.getButtons() end) or {}
  for i = #buttons, 1, -1 do
    local b = buttons[i]
    if b.label == label then
      safe(function() o.removeButton(b.index or (i - 1)) end)
    end
  end
end

local function addLabel(o, label, z)
  if not host then return end
  removeLabel(o, label)
  safe(function()
    o.createButton({
      click_function = "shNoop", function_owner = host, label = label,
      position = { 0, 0.3, z or 0 }, rotation = { 0, 0, 0 },
      width = 0, height = 0, font_size = 260,
      font_color = { 0.95, 0.25, 0.2 },
    })
  end)
end

local function setFaceDown(o, down)
  local r = vec(safe(function() return o.getRotation() end)) or { x = 0, y = 180, z = 0 }
  safe(function() o.setRotation({ r.x, r.y, down and 180 or 0 }) end)
end

--- Flip every known location to Locations.activeFace and gate clues on isOpen.
-- Returns a report {flipped, unflipped, sealed, opened, seen}.
function Board.syncLocations()
  local rep = { flipped = 0, unflipped = 0, sealed = 0, opened = 0, seen = 0 }
  for _, l in ipairs(Board.locationCards()) do
    if l.locId then
      rep.seen = rep.seen + 1
      local o, g = l.obj, l.guid
      -- face: only locations with a fact-flipped back are ever turned by us
      if Locations.hasBack(l.locId) then
        local want = Locations.activeFace(l.locId)
        local down = safe(function() return o.is_face_down end) == true
        if want == "back" and not down then
          setFaceDown(o, true) ; st.flipped[g] = true ; rep.flipped = rep.flipped + 1
        elseif want == "front" and down and st.flipped[g] then
          setFaceDown(o, false) ; st.flipped[g] = nil ; rep.unflipped = rep.unflipped + 1
        end
      end
      -- clues: a sealed location never auto-spawns its clues
      if Locations.isSealed(l.locId) then
        rep.sealed = rep.sealed + 1
        if SCED.markTokensSpawned(g) then st.sealedMarked[g] = true end
        if not st.sealedLabel[g] then addLabel(o, Board.SEALED_LABEL) ; st.sealedLabel[g] = true end
      else
        if st.sealedLabel[g] then removeLabel(o, Board.SEALED_LABEL) ; st.sealedLabel[g] = nil end
        if st.sealedMarked[g] then
          st.sealedMarked[g] = nil
          SCED.resetTokensSpawned(g)
          if SCED.isInPlayArea(o) then SCED.spawnForCard(o) end
          rep.opened = rep.opened + 1
        end
      end
    end
  end
  return rep
end

--------------------------------------------------------------- the Appointed --

local function isAppointedMeta(md)
  return md ~= nil and md.id == Board.APPOINTED_ID
end

function Board.isAppointedObject(o)
  return isCard(o) and isAppointedMeta(metaOf(o))
end

--- The Appointed card if it lies loose on the table.
function Board.findAppointed()
  for _, o in ipairs(topLevel()) do
    if Board.isAppointedObject(o) then return o end
  end
  return nil
end

--- A container holding the Appointed: container, entry.
local function findAppointedInContainer(guid)
  for _, o in ipairs(topLevel()) do
    local t = safe(function() return o.type end)
    if t == "Bag" or t == "Deck" then
      for _, e in ipairs(safe(function() return o.getObjects() end) or {}) do
        if (guid and e.guid == guid) or isAppointedMeta(decode(e.gm_notes)) then
          return o, e
        end
      end
    end
  end
  return nil
end

local function setAsidePos()
  local p = host and vec(safe(function() return host.getPosition() end)) or { x = 0, y = 1, z = 0 }
  return { x = p.x, y = p.y + 1.5, z = p.z + 4.5 }
end

local function placePosFor(l)
  local p = l.pos or { x = 0, y = 1, z = 0 }
  local off = Board.APPOINTED_OFFSET
  return { x = p.x + off.x, y = p.y + off.y, z = p.z + off.z }
end

local function rotFor(l)
  local r = l and vec(safe(function() return l.obj.getRotation() end)) or { x = 0, y = 180, z = 0 }
  return { 0, r.y, 0 }
end

--- Move (or take out of its container) the Appointed to pos/rot, then call
-- done(obj). Returns true if a card was found.
local function bringAppointed(pos, rot, done)
  local card = Board.findAppointed()
  if card then
    safe(function() card.setPosition({ pos.x, pos.y, pos.z }) end)
    if rot then safe(function() card.setRotation(rot) end) end
    st.appointed.guid = guidOf(card)
    if done then done(card) end
    return true
  end
  local c, e = findAppointedInContainer(st.appointed.guid)
  if c then
    local ok = pcall(function()
      c.takeObject({
        guid = e.guid, smooth = false,
        position = { pos.x, pos.y, pos.z }, rotation = rot,
        callback_function = function(o)
          st.appointed.guid = guidOf(o)
          if done then done(o) end
        end,
      })
    end)
    return ok
  end
  return false
end

local STAGE_BUTTONS = {
  { fn = "shAppointedInfo", label = function() return "The Appointed: " .. Appointed.stageName() end,
    z = 1.75, w = 1100, fs = 120, tip = "Approach stage (CO-002)" },
  { fn = "shHoldBack", label = function() return "Hold Back (success)" end, z = 2.2, w = 1100, fs = 120,
    tip = "Click after a SUCCESSFUL [willpower] or [combat] (4) test: back one stage, rewind one Hour." },
}

--- Put the Hold Back / Hunt buttons on the Appointed card (idempotent).
function Board.refreshAppointedButtons(card)
  card = card or Board.findAppointed()
  if not card or not host then return false end
  safe(function() card.clearButtons() end)   -- only our buttons live on this card
  if not Appointed.isManifest() then return true end
  local defs = {}
  for _, b in ipairs(STAGE_BUTTONS) do defs[#defs + 1] = b end
  if Appointed.isHunter() then
    defs[#defs + 1] = { fn = "shHunt", label = function() return "Hunt (move toward prey)" end,
                        z = 2.65, w = 1100, fs = 120, tip = "Hunter: move one location toward its prey." }
  end
  for _, b in ipairs(defs) do
    safe(function()
      card.createButton({
        click_function = b.fn, function_owner = host, label = b.label(), tooltip = b.tip,
        position = { 0, 0.3, b.z }, rotation = { 0, 0, 0 },
        width = b.w, height = 200, font_size = b.fs,
        color = { 0.12, 0.08, 0.16 }, font_color = { 0.95, 0.85, 0.6 },
      })
    end)
  end
  return true
end

--- The board ctx the Appointed / Hourglass modules call back into.
function Board.appointedCtx(extra)
  local ctx = {}
  for k, v in pairs(extra or {}) do ctx[k] = v end

  function ctx.isOnBoard()
    local card = Board.findAppointed()
    if not card then return false end
    if st.appointed.placed then return true end
    return SCED.isInPlayArea(card) == true
  end

  function ctx.placeAtFarthest()
    local locs = Board.locationCards()
    if #locs == 0 then
      -- nothing to place it on: tell the table once per stage, not per click
      if st.appointed.noticeStage ~= Appointed.stage() then
        st.appointed.noticeStage = Appointed.stage()
        say("The Appointed manifests (" .. Appointed.stageName() .. "): place it at the location farthest from the investigators.")
      end
      return false
    end
    local graph = Board.graph(locs)
    local occ = Board.occupied(locs)
    local byGuid = {}
    for _, l in ipairs(locs) do byGuid[l.guid] = l end
    local minis = Board.minicards()
    -- tie-break: farther (straight-line) from the nearest investigator wins
    local function spread(g)
      local p, best = byGuid[g].pos, nil
      for _, m in ipairs(minis) do
        if m.pos then
          local d = dist2d(p, m.pos)
          if best == nil or d < best then best = d end
        end
      end
      return best or 0
    end
    local target = Locations.farthest(graph, occ, function(a, b) return spread(a) > spread(b) end)
    local l = byGuid[target]
    if not l then return false end
    local ok = bringAppointed(placePosFor(l), rotFor(l), function(card)
      Board.refreshAppointedButtons(card)
    end)
    if ok then
      -- recorded now (not in the take-out callback) so a second sync in the
      -- same frame sees it as placed
      st.appointed.placed = true
      st.appointed.lastPos = placePosFor(l)
      st.appointed.lastRot = rotFor(l)
      say("The Appointed manifests at " .. (safe(function() return l.obj.getName() end) or "a location")
        .. " (" .. Appointed.stageName() .. ").")
    else
      say("The Appointed manifests: its card was not found on the table. Place it at "
        .. (safe(function() return l.obj.getName() end) or "the farthest location") .. ".")
    end
    return ok
  end

  function ctx.removeFromBoard()
    local p = setAsidePos()
    local ok = bringAppointed(p, nil, function(card)
      safe(function() card.clearButtons() end)
    end)
    st.appointed.placed = false
    st.appointed.lastPos = nil
    st.appointed.noticeStage = nil
    say("The Appointed recedes into shadow (Unseen).")
    return ok
  end

  function ctx.moveTowardPrey()
    local card = Board.findAppointed()
    if not card then return false end
    local locs = Board.locationCards()
    local graph = Board.graph(locs)
    local byGuid = {}
    for _, l in ipairs(locs) do byGuid[l.guid] = l end
    local here = locationAt(locs, vec(safe(function() return card.getPosition() end)), 3.0)
    -- Rules Reference, Hunter: an enemy at a location with an investigator
    -- does not move
    if here then
      for _, g in ipairs(Board.occupied(locs)) do
        if g == here.guid then
          say("The Appointed is with an investigator: it does not move.")
          return false
        end
      end
    end
    local target, why = Board.preyLocation(locs, graph, here)
    if not target then say("The Appointed hunts, but no investigator minicard is on a location.") ; return false end
    local nextKey = here and Locations.stepToward(graph, here.guid, target) or target
    if nextKey == nil then say("The Appointed cannot reach its prey from here.") ; return false end
    if here and nextKey == here.guid then say("The Appointed is already with its prey.") ; return false end
    local l = byGuid[nextKey]
    local pos, rot = placePosFor(l), rotFor(l)
    safe(function() card.setPosition({ pos.x, pos.y, pos.z }) end)
    safe(function() card.setRotation(rot) end)
    st.appointed.placed = true
    st.appointed.lastPos, st.appointed.lastRot = pos, rot
    say("The Appointed moves to " .. (safe(function() return l.obj.getName() end) or "the next location")
      .. " (" .. why .. ").")
    return true
  end

  function ctx.returnToPlay()
    Board.scheduleRestore()
  end

  return ctx
end

--- Reconcile the Appointed's physical card with its Approach stage.
function Board.syncAppointed(extra)
  local ctx = Board.appointedCtx(extra)
  Appointed.syncBoard(ctx)
  Board.refreshAppointedButtons()
  return ctx
end

------------------------------------------------- undefeatable: restore card --

local function restoreNow()
  restoreScheduled = false
  if not Appointed.isManifest() then return end
  local pos = st.appointed.lastPos or setAsidePos()
  local rot = st.appointed.lastRot
  if bringAppointed(pos, rot, function(card) Board.refreshAppointedButtons(card) end) then
    say("The Appointed cannot be defeated. It does not leave play.")
  elseif restoreData then
    local data = restoreData
    safe(function()
      spawnObjectData({ data = data, position = { pos.x, pos.y, pos.z },
        callback_function = function(o)
          st.appointed.guid = guidOf(o)
          Board.refreshAppointedButtons(o)
        end })
    end)
    say("The Appointed cannot be defeated. It does not leave play.")
  end
  restoreData = nil
end

function Board.scheduleRestore()
  if restoreScheduled then return end
  restoreScheduled = true
  local ok = pcall(function() Wait.frames(restoreNow, 5) end)
  if not ok then restoreNow() end
end

--- Universal-event forwards from the host script.
function Board.onEnterContainer(container, obj)
  if Board.isAppointedObject(obj) then
    Appointed.onRemovalAttempt(Board.appointedCtx())
  end
end

function Board.onDestroy(obj)
  if Board.isAppointedObject(obj) and Appointed.isManifest() then
    restoreData = safe(function() return obj.getData() end)
    Appointed.onRemovalAttempt(Board.appointedCtx())
  end
end

function Board.onLeaveContainer(container, obj)
  if Board.isAppointedObject(obj) then
    pcall(function() Wait.frames(function() Board.refreshAppointedButtons() end, 3) end)
  end
end

function Board.onDrop(obj)
  if Board.isAppointedObject(obj) then
    st.appointed.lastPos = vec(safe(function() return obj.getPosition() end))
    local r = vec(safe(function() return obj.getRotation() end))
    st.appointed.lastRot = r and { 0, r.y, 0 } or nil
  end
end

--- Everything at once (load, after a reset / fact unlock).
function Board.syncAll(extra)
  local rep = Board.syncLocations()
  Board.syncAppointed(extra)
  rep.investigators = Board.refreshInvestigators(extra and extra.applyStats)
  return rep
end

------------------------------------------------ SCED campaign export carry --

-- SCED's Campaign Importer/Exporter has no hook for third-party data, but its
-- export stores the one object tagged "CampaignLog" whole (getData()) inside
-- the save coin and respawns it on import (core/CampaignImporterExporter.ttslua
-- exportToToken / importFromToken). TTS saves an object's `memo` string with it
-- (Object.memo, "persist user-data"), so the control token mirrors its state
-- into the campaign log's memo; SCED then carries it through export/import.

Board.CAMPAIGN_LOG_TAG = "CampaignLog"
Board.MEMO_KEY = "stillHour"

function Board.campaignLog()
  local list = safe(function() return getObjectsWithTag(Board.CAMPAIGN_LOG_TAG) end) or {}
  if #list == 1 then return list[1] end
  return nil
end

--- Write `blob` (a JSON string) with sequence `seq` into the log's memo.
function Board.mirrorToLog(blob, seq)
  local log = Board.campaignLog()
  if not log or JSON == nil then return false end
  return safe(function()
    log.memo = JSON.encode({ [Board.MEMO_KEY] = blob, seq = seq })
    return true
  end) or false
end

--- The mirrored {blob, seq} in a campaign log object's memo, or nil.
function Board.readLogMirror(log)
  log = log or Board.campaignLog()
  if not log then return nil end
  local memo = safe(function() return log.memo end)
  local t = decode(memo)
  if t and type(t[Board.MEMO_KEY]) == "string" then
    return { blob = t[Board.MEMO_KEY], seq = tonumber(t.seq) or 0 }
  end
  return nil
end

return Board

end

-- ===== control entry script =====
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
  local prologue = CampaignState.inPrologue()
  CampaignState.reset()
  -- Between Loops step 5: Part II begins with 3+ surface entries or after Loop 3
  if not prologue and not CampaignState.inPartTwo()
      and (Knowledge.surfaceKnownCount() >= 3 or CampaignState.getLoopsCompleted() >= 3) then
    CampaignState.setPartTwo(true)
    announce("Part II begins: read The Shape of the Hour (Between Loops).")
  end
  bag.clearTemporary()
  Dissonance.syncBag(bag)
  if prologue then
    note("The night folds for the first time. The Prologue is over (it is not a loop): Loop 1 is next.")
  else
    note("The night folds. Loop reset: Memory/Knowledge/Years kept; Dissonance dropped to the scar.")
  end
end

-- Card types a scenario box lays out (never a player card or a weakness).
local SCENARIO_TYPES = { Location = true, Act = true, Agenda = true, Enemy = true,
  Treachery = true, Story = true, ScenarioReference = true, Scenario = true }
local LOOP_TAG = "StillHourLoop"

local function isLoopCard(tags, gm)
  for _, t in ipairs(tags or {}) do if t == LOOP_TAG then return true end end
  local ok, md = pcall(JSON.decode, gm or "")
  if not ok or type(md) ~= "table" then return false end
  local id = tostring(md.id or "")
  return id:sub(1, 5) == "sthr-" and SCENARIO_TYPES[md.type] == true and not md.weakness
end

--- Tokens resting on a card (clues, doom, damage): small, unlocked, not cards.
local function tokensOn(card)
  local found = {}
  if type(Physics) ~= "table" or type(Physics.cast) ~= "function" then return found end
  local b = card.getBounds()
  local hits = Physics.cast({ origin = { b.center.x, b.center.y + 2, b.center.z },
    direction = { 0, -1, 0 }, type = 3, size = { b.size.x, 1, b.size.z }, max_distance = 3 }) or {}
  for _, h in ipairs(hits) do
    local o = h.hit_object
    if o and o ~= card and not o.getLock() and (o.type == "Tile" or o.type == "Generic"
        or o.type == "Chip") then
      found[#found + 1] = o
    end
  end
  return found
end

--- Loop Setup step 1: take every card the scenario boxes laid out (and the
-- tokens on them) off the table, so the boxes can be Placed fresh. Player
-- cards, minicards, mats and the campaign's own objects are never touched.
local function clearLoopBoard()
  local removed, tokens = 0, 0
  if type(getObjects) ~= "function" then return { cards = 0, tokens = 0 } end
  for pass = 1, 2 do
    for _, o in ipairs(getObjects()) do
      if not o.isDestroyed() and (o.type == "Card" or o.type == "Deck") then
        if o.type == "Card" then
          if isLoopCard(o.getTags and o.getTags() or {}, o.getGMNotes()) then
            for _, t in ipairs(tokensOn(o)) do t.destruct() ; tokens = tokens + 1 end
            o.destruct()
            removed = removed + 1
          end
        else
          local mine, others = {}, 0
          for _, e in ipairs(o.getObjects() or {}) do
            if isLoopCard(e.tags, e.gm_notes) then mine[#mine + 1] = e.guid else others = others + 1 end
          end
          if #mine > 0 and others == 0 then
            for _, t in ipairs(tokensOn(o)) do t.destruct() ; tokens = tokens + 1 end
            o.destruct()
            removed = removed + #mine
          elseif #mine > 0 then
            local pos = o.getPosition()
            for _, g in ipairs(mine) do
              if o.isDestroyed() then break end
              local ok, c = pcall(o.takeObject, { guid = g, position = { pos.x, pos.y + 3, pos.z }, smooth = false })
              if ok and c then c.destruct() ; removed = removed + 1 end
            end
          end
        end
      end
    end
  end
  return { cards = removed, tokens = tokens }
end

-- The campaign guide's chaos bags (Campaign Setup), as SCED's token ids
-- (core/Constants.ttslua ID_URL_MAP: blue = Elder Sign, red = Auto-fail,
-- elder = Elder Thing). [static] tokens are added on top by Dissonance.
local DIFFICULTY = {
  { key = "easy", label = "Easy",
    bag = { "p1", "p1", "0", "0", "0", "m1", "m1", "m1", "m2", "m2",
            "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
  { key = "standard", label = "Standard",
    bag = { "p1", "0", "0", "m1", "m1", "m1", "m2", "m2", "m3", "m4",
            "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
  { key = "hard", label = "Hard",
    bag = { "0", "0", "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m5",
            "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
  { key = "expert", label = "Expert",
    bag = { "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m4", "m5", "m6", "m8",
            "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
}

--- Fill SCED's chaos bag for a difficulty, then put the band's [static] back.
local function setDifficulty(i)
  local d = DIFFICULTY[i]
  if not d then return false end
  if not SCED.isPresent() then
    announce("Chaos bag presets need the SCED mod: build the " .. d.label
      .. " bag by hand from the Campaign Guide (Campaign Setup).")
    return false
  end
  SCED.globalCall("setChaosBagState", d.bag)
  -- SCED respawns the bag; once it has landed, re-add the band's [static] tokens
  Wait.time(function()
    guarded("chaos bag", Dissonance.syncBag, bag)
    refreshControl()
  end, 1.5)
  announce("Chaos bag set to " .. d.label .. " (" .. #d.bag .. " tokens), plus the Dissonance band's [static].")
  return true
end

local function unlockFact(id)
  local ok, newly = pcall(Knowledge.unlock, id)
  if not ok then
    note("unknown fact id: " .. tostring(id))
    return nil
  end
  -- the assembled entry: record it the moment its inputs are all known
  if newly and Knowledge.assembleFinale() then
    announce("Record The Way the Night Breaks in your Campaign Log: the finale may now be begun.")
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
  header(CampaignState.inPrologue() and "THE STILL HOUR · Prologue"
    or string.format("THE STILL HOUR · loop %d", CampaignState.getLoopsCompleted() + 1), -2.3)
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
  if CampaignState.knows("the-way-the-night-breaks") then
    button("shClickContest", string.format("Contest %d / %d", CampaignState.getContest(), c.contestTarget),
      0.0, 2.6, 620, "The Last Hour: contest progress. " .. PLUS_MINUS)
  end
  button("shClearBoard", "Clear Board", -ROW3_X, 2.6, 620,
    "Loop Setup: remove every card the scenario boxes laid out, and the tokens on them.")
  for i, d in ipairs(DIFFICULTY) do
    button("shDifficulty" .. i, d.label, -1.8 + (i - 1) * 1.2, 3.2, 520,
      "Campaign Setup: fill SCED's chaos bag for " .. d.label .. " (the guide's list).", 90)
  end
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
  -- a brand-new campaign begins with the Prologue, which is not a loop
  if saved == nil or saved == "" then CampaignState.setPrologue(true) end
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
    prologue = CampaignState.inPrologue(),
  }
end

--- End the Prologue if it is still running (tests and the relay start at Loop 1).
function shApiEndPrologue()
  if CampaignState.inPrologue() then guarded("reset", resetLoop) ; afterChange() end
  return shApiState()
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

function shClearBoard()
  local r = guarded("clear board", clearLoopBoard) or { cards = 0, tokens = 0 }
  announce(string.format("The board is cleared: %d scenario card(s) and %d token(s) removed. "
    .. "Press Place on The Square's box to set up the next loop.", r.cards, r.tokens))
  return r
end

function shApiClearBoard() return guarded("clear board", clearLoopBoard) end
function shApiSetPartTwo(p)
  CampaignState.setPartTwo(p == nil or p.on ~= false)
  local rep = guarded("locations", Board.syncLocations)
  afterChange()
  return rep
end
-- Victory X of the Named (the encounter cards' ids; the log's v:<id> boxes)
local VICTORY = { ["sthr-bellringer"] = 2, ["sthr-wearssheriff"] = 3, ["sthr-onewhorides"] = 2 }

--- Bank a Named enemy's Victory once per campaign (the log's tick calls this).
function shApiClaimVictory(p)
  local id = p and p.id
  if not VICTORY[id] then return false end
  local newly = CampaignState.claimVictory(id, VICTORY[id])
  if newly then
    announce(string.format("Victory: %d banked Memory (%d banked).", VICTORY[id], CampaignState.getBankedMemory()))
  end
  afterChange()
  return newly
end

function shClickContest(_, _, alt)
  CampaignState.setContest(CampaignState.getContest() + (alt and -1 or 1))
  local c = CampaignState.constants()
  if CampaignState.getContest() >= c.contestTarget then
    announce("The contest is reached: advance Contest the Crossing.")
  end
  afterChange()
end

function shDifficulty1() setDifficulty(1) end
function shDifficulty2() setDifficulty(2) end
function shDifficulty3() setDifficulty(3) end
function shDifficulty4() setDifficulty(4) end
function shApiDifficulty(p) return setDifficulty(p and p.i) end

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
  P, F = check("Sealed Study stays closed in Part I", Locations.isSealed("sealed-study"), P, F)
  CampaignState.setPartTwo(true)
  P, F = check("Sealed Study opens with both facts in Part II", Locations.isOpen("sealed-study"), P, F)
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
