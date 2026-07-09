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
  state.loopsCompleted = state.loopsCompleted + 1

  -- Scar floor: completed loops, capped by scarCap.
  local c = CampaignState.constants()
  state.dissonance = math.min(state.loopsCompleted, c.scarCap)

  state.hourglass = Constants.HOUR_FIRST
  state.oncePerLoopFlags = {}
  state.testTypesLastLoop = state.testTypesThisLoop
  state.testTypesThisLoop = {}
  state.appointedStage = 0
  return state
end

--- Begin a new loop's play: enforce the Memory soft cap. Call at §2 setup after
-- the interlude has banked Memory and bought Recollections.
function CampaignState.startLoop()
  CampaignState.capMemory()
  return state
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

--- Prey = the investigator with the most on-card Memory. Pass a map
-- { investigatorId = memoryCount }. Ties resolve to the first max seen.
function Appointed.prey(memoryByInvestigator)
  local best, bestId
  for id, m in pairs(memoryByInvestigator or {}) do
    if best == nil or m > best then
      best = m
      bestId = id
    end
  end
  return bestId
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
  ["flooded-crypt"]   = { name = "The Flooded Crypt",  district = "Church", sealedUntil = { "the-thirteenth-toll" } },
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
                          sealedUntil = { "what-the-almanac-hid", "the-vote-that-never-ends" } },
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
function Interlude.age(investigatorId, cond, lockedChoice)
  return Aging.applyInterlude(investigatorId, cond, lockedChoice)
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
  return CampaignState.startLoop()
end

return Interlude

end

-- ===== control entry script =====
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
local Appointed     = require("StillHour/Appointed")
local Knowledge     = require("StillHour/Knowledge")
local Locations     = require("StillHour/Locations")
local Interlude     = require("StillHour/Interlude")

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

  -- row 1: play controls; row 2: interlude/knowledge demo (z offset)
  local defs = {
    { "runStillHourTests", "Run Tests",    -1.1, 1.4 },
    { "shStatus",          "Status",       -0.55, 1.4 },
    { "shAdvanceHour",     "Advance Hour",  0.0, 1.4 },
    { "shRaiseDissonance", "+1 Dissonance", 0.55, 1.4 },
    { "shReset",           "Reset Loop",    1.1, 1.4 },
    { "shInterludeDemo",   "Interlude Demo", -0.55, 2.3 },
    { "shKnowledgeStatus", "Knowledge",     0.55, 2.3 },
  }
  for _, d in ipairs(defs) do
    self.createButton({
      click_function = d[1], function_owner = self, label = d[2],
      position = { d[3], 0.3, d[4] }, rotation = { 0, 0, 0 },
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
    "STILL HOUR | loop %d | Memory %d/%d | Dissonance %d/%d (%s) | Hour %s | Appointed: %s | contest %d",
    CampaignState.getLoopsCompleted(), CampaignState.getBankedMemory(), c.memoryCap,
    CampaignState.getDissonance(), c.resetThreshold, CampaignState.band(),
    Hourglass.HOUR_NAMES[CampaignState.getHour()] or "?", Appointed.stageName(), c.contestTarget))
end

function shAdvanceHour()
  Hourglass.advance(1, { log = function(h, name, msg)
    print(string.format("  Hour %d — %s: %s", h, name, msg))
  end, dissonance = Dissonance, bag = demoBag, onReset = function() shReset() end })
  shStatus()
end

function shRaiseDissonance()
  local before = Appointed.stage()
  local info = Dissonance.raise(1, demoBag)
  print("Dissonance -> " .. info.value .. " (" .. info.band .. ")" ..
    (info.appointedStage > before and ("  ** the Appointed advances to " .. Appointed.stageName() .. " **") or ""))
  if info.reachedReset then print("  Dissonance hit the reset threshold — the loop ends.") ; shReset() end
end

function shReset()
  CampaignState.reset()
  Dissonance.syncBag(demoBag)
  print("The night folds. Loop reset — Memory/Knowledge/Years kept; Dissonance dropped to the scar.")
  shStatus()
end

-- P7 demo: run an interlude for a 3-investigator party with sample conditions,
-- print the aging outcome per investigator, then cap and hand off to the loop.
function shInterludeDemo()
  print("── Interlude ──")
  local entries = {
    { id = "sthr-elias",   cond = { defeated = true }, lockedChoice = { physical = "combat", mental = "willpower" } },
    { id = "sthr-ayako",   cond = { leanedOnLoop = true }, lockedChoice = { physical = "combat", mental = "intellect" } },
    { id = "sthr-birdie",  cond = {} },
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
    .. "Buy Recollections with shBuy(\"sthr-longwayround\") etc.")
end

function shBuy(cardId)
  if Interlude.buyRecollection(cardId) then
    print("Bought " .. cardId .. " for " .. Interlude.recollectionCost(cardId)
      .. " Memory. Banked now " .. CampaignState.getBankedMemory() .. ".")
  else
    print("Cannot buy " .. tostring(cardId) .. " (unknown id or not enough Memory).")
  end
end

-- P6 demo: report Act/finale gates and any location whose face has flipped.
function shKnowledgeStatus()
  print(string.format("Knowledge: %d surface, %d deep. Act II %s. Finale %s.",
    Knowledge.surfaceKnownCount(), Knowledge.deepKnownCount(),
    Knowledge.actIIOpen() and "OPEN" or "closed",
    Knowledge.finaleAttemptable() and "ATTEMPTABLE" or (Knowledge.canAssembleFinale() and "assemblable" or "locked")))
  for _, id in ipairs({ "lantern-room", "town-hall-steps", "flooded-crypt", "sealed-study" }) do
    local d = Locations.describe(id)
    print(string.format("  %-16s face=%s%s", d.name, d.face, d.sealed and " (SEALED)" or ""))
  end
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
  CampaignState.init(3); CampaignState.advanceAppointed(1)
  P, F = check("Sensed figure deals no attack damage", Appointed.onAttack({}).damage == 0, P, F)

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

  -- P6: location fact-toggles + Knowledge gates.
  CampaignState.init(3)
  P, F = check("Lantern Room front until lamp fact", Locations.activeFace("lantern-room") == "front", P, F)
  CampaignState.unlockFact("the-lamp-was-never-lit")
  P, F = check("Lantern Room flips to back with the fact", Locations.activeFace("lantern-room") == "back", P, F)
  P, F = check("Sealed Study sealed until both facts", Locations.isSealed("sealed-study"), P, F)
  CampaignState.unlockFact("what-the-almanac-hid"); CampaignState.unlockFact("the-vote-that-never-ends")
  P, F = check("Sealed Study opens with both facts", Locations.isOpen("sealed-study"), P, F)
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
  CampaignState.init(3); CampaignState.addYears("sthr-ayako", 14)
  -- interlude pushes 14 -> 15 (Ancient) and locks the drift choice
  Aging.applyInterlude("sthr-ayako", {}, { physical = "combat", mental = "intellect" })
  local st = Aging.applyDriftToStats(base, "sthr-ayako")
  P, F = check("Ancient drift: int 5->7, health/sanity -1, com floored at 1",
    st.int == 7 and st.health == 4 and st.sanity == 7 and st.com == 1, P, F)
  CampaignState.init(3); CampaignState.bankMemory(6)
  P, F = check("Interlude buys Recollection at memoryCost (longwayround=2)",
    Interlude.buyRecollection("sthr-longwayround") and CampaignState.getBankedMemory() == 4, P, F)
  P, F = check("Interlude buys level-3 upgrade (=3)",
    Interlude.buyUpgrade(3) and CampaignState.getBankedMemory() == 1, P, F)
  P, F = check("Interlude rejects unaffordable purchase", Interlude.buyRecollection("sthr-hourlearnedname") == false, P, F)

  print(string.format("──────── RESULT: %d passed, %d failed ────────", P, F))
  broadcastToAll(string.format("Still Hour tests: %d passed, %d failed", P, F),
    F == 0 and { 0.2, 1, 0.2 } or { 1, 0.3, 0.3 })
  -- Restore a clean, freshly-loaded state for play after testing.
  CampaignState.init(CampaignState.constants().investigators)
  Dissonance.syncBag(demoBag)
end
