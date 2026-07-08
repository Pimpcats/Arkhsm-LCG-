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
--   Latecomer arrival  = 4 x investigators   (Noticed band; boss enters)
--   Memory soft cap    = 6 x investigators
--   contest target     = 3 x investigators   (finale)
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
  local latecomer = 4 * n
  if n == 1 then
    -- Documented solo override (guide §10): looser than 4/6.
    reset = 9
    latecomer = 6
  end
  return {
    investigators = n,
    resetThreshold = reset,
    latecomerThreshold = latecomer,
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
    latecomerInPlay = false,
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
-- so the caller (Dissonance module) can drive chaos-bag / Latecomer hooks.
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

--- True once Dissonance has reached the Latecomer arrival threshold.
function CampaignState.latecomerShouldArrive()
  return state.dissonance >= CampaignState.constants().latecomerThreshold
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

------------------------------------------------------------------ latecomer --

function CampaignState.isLatecomerInPlay()
  return state.latecomerInPlay == true
end

function CampaignState.setLatecomerInPlay(v)
  state.latecomerInPlay = (v == true)
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
  state.latecomerInPlay = false
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

--- Raise Dissonance and reconcile the bag / report boss + reset transitions.
-- @return table {value, band, latecomerArriving, reachedReset}
function Dissonance.raise(n, bag)
  local value, before, after, reachedReset = CampaignState.raiseDissonance(n or 1)
  reconcileBand(bag, before, after)
  return {
    value = value,
    band = after,
    latecomerArriving = CampaignState.latecomerShouldArrive()
      and not CampaignState.isLatecomerInPlay(),
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
-- impassable location, spawning the Latecomer, etc.) are delegated to callbacks
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
--   ctx.moveLatecomerCloser -- function()
--   ctx.spawnLatecomer  -- function(exhausted)
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
    if CampaignState.band() ~= Constants.BAND_CALM then
      if ctx and ctx.awakenSleepwalkingEchoes then
        ctx.awakenSleepwalkingEchoes()
      end
      return "Sleepwalking Echoes awaken."
    end
    return "The streets empty (Echoes stay asleep in the Calm band)."
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
    if not CampaignState.isLatecomerInPlay() then
      if ctx and ctx.moveLatecomerCloser then ctx.moveLatecomerCloser() end
      return "The guest approaches (Latecomer moves 1 Hour closer)."
    end
    return "The guest approaches."
  end,

  [8] = function(ctx)
    raiseDissonance(ctx, 2)
    if ctx and ctx.enemiesGetFightBonus then ctx.enemiesGetFightBonus(1) end
    return "Raise Dissonance by 2. All enemies get +1 Fight until reset."
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

--- Did the loop end in the danger band (Dissonance >= Latecomer threshold)?
-- Measure BEFORE reset (reset drops Dissonance to the scar).
function Aging.loopEndedInDanger(dissonanceAtEnd, investigatorCount)
  local Constants = require("StillHour/Constants")
  return dissonanceAtEnd >= Constants.forCount(investigatorCount).latecomerThreshold
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

return Aging

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
