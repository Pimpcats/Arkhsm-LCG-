--- THE STILL HOUR — in-engine test harness (Tabletop Simulator / SCED).
--
-- Runs the SAME assertions as pipeline/lua_smoketest.lua, but against the REAL
-- StillHour modules as bundled into your SCED build — so you can confirm the Lua
-- behaves in-engine exactly as it does offline. It also does a live
-- loop -> reset -> interlude walkthrough, printing state at each step so you can
-- WATCH Memory/Knowledge/Years persist and Dissonance drop to the scar.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- HOW TO RUN (mod open, StillHour bundled into Global):
--
--   Option A — attach to an object:
--     1. Spawn any object (a token/tile). Right-click -> Scripting -> paste this
--        whole file as its Lua Script, then "Save & Play".
--     2. A red "Run Still Hour Tests" button appears on the object. Click it.
--     3. Open the console with the ` (backtick/tilde) key to read PASS/FAIL.
--
--   Option B — paste into Global:
--     Append this file to your Global.-1.lua (dev build), rebuild/save, then in
--     the in-game console run:  >execute runStillHourTests()
--
-- If the modules are not bundled yet (P0 not done), the harness prints a clear
-- message instead of erroring — it needs require("StillHour/...") to resolve,
-- which only works once src/StillHour is part of the build (see docs/INTEGRATION.md).
-- ─────────────────────────────────────────────────────────────────────────────

local PASS, FAIL = 0, 0

local function check(name, cond)
  if cond then
    PASS = PASS + 1
    print("[PASS] " .. name)
  else
    FAIL = FAIL + 1
    print("[FAIL] " .. name)
  end
end

-- Safe require: returns nil instead of hard-erroring if the module isn't bundled.
local function tryRequire(path)
  local ok, mod = pcall(require, path)
  if ok then return mod end
  return nil
end

function runStillHourTests()
  PASS, FAIL = 0, 0
  print("──────────── THE STILL HOUR — in-engine tests ────────────")

  local Constants = tryRequire("StillHour/Constants")
  local CampaignState = tryRequire("StillHour/CampaignState")
  local Dissonance = tryRequire("StillHour/Dissonance")
  local LoopFlags = tryRequire("StillHour/LoopFlags")
  local Hourglass = tryRequire("StillHour/Hourglass")
  local Aging = tryRequire("StillHour/Aging")
  local Appointed = tryRequire("StillHour/Appointed")

  if not (Constants and CampaignState and Dissonance and LoopFlags and Hourglass and Aging and Appointed) then
    print("[SKIP] StillHour modules are not bundled into this build yet.")
    print("       Add src/StillHour to the build (see docs/INTEGRATION.md), then re-run.")
    return
  end

  -- 1. Constants (CO-001: contest = 4 x investigators).
  local c3 = Constants.forCount(3)
  check("reset threshold 18 / appointed 12 at 3p",
    c3.resetThreshold == 18 and c3.appointedThreshold == 12)
  check("contest target 12 at 3p (CO-001 4*n)", c3.contestTarget == 12)
  check("memory cap 18, scar cap 6", c3.memoryCap == 18 and c3.scarCap == 6)

  -- 2. Dissonance bands drive the [static] baseline (fake bag adapter).
  local bag = { count = 0 }
  bag.setBaselineStatic = function(m) bag.count = m end
  CampaignState.init(3)
  Dissonance.syncBag(bag)
  check("Calm band -> 0 baseline [static]", bag.count == 0)
  Dissonance.raise(6, bag)
  check("Glitch band -> 1 [static]; Dissonance 6", bag.count == 1 and CampaignState.getDissonance() == 6)
  local info = Dissonance.raise(6, bag)
  check("Noticed band -> 2 [static]; Appointed Arrived (3)",
    bag.count == 2 and info.appointedStage == 3)
  local before = CampaignState.getDissonance()
  Dissonance.onStaticRevealed(bag)
  check("revealing [static] raises Dissonance by 1", CampaignState.getDissonance() == before + 1)

  -- P5. The Appointed: clock-driven staged Approach, Hold Back, undefeatable.
  CampaignState.init(3)
  Hourglass.advance(4, {})  -- Hour V
  check("Hour V -> Appointed Sensed (1)", Appointed.stage() == 1)
  Hourglass.advance(3, {})  -- Hour VIII
  check("Hour VIII -> Appointed Arrived (3)", Appointed.stage() == 3)
  local dPre = CampaignState.getDissonance()
  local atk = Appointed.onAttack({})
  check("Arrived attacks 2/2 and raises Dissonance",
    atk.damage == 2 and atk.horror == 2 and CampaignState.getDissonance() == dPre + 1)
  local hPre = CampaignState.getHour()
  check("Hold Back drops one stage and rewinds one Hour",
    Appointed.holdBack({}) == 2 and CampaignState.getHour() == hPre - 1)
  check("cannot be defeated", Appointed.attemptDefeat() == false)

  -- 3. Once-per-loop flags persist across node travel, clear on reset (P4).
  CampaignState.init(3)
  check("once-per-loop flag free at node A", LoopFlags.use("igetout:White") == true)
  check("blocked on second use (node A)", LoopFlags.use("igetout:White") == false)
  check("still blocked at node B (no reset)", LoopFlags.isUsed("igetout:White") == true)

  -- 4. A full loop: set state, reset, verify persistence + scar + clear (P2).
  print("···· live loop walkthrough ····")
  CampaignState.bankMemory(14)
  CampaignState.unlockFact("the-thirteenth-toll")
  CampaignState.addYears("sthr-elias", 3)
  CampaignState.raiseDissonance(11)
  CampaignState.setHour(7)
  LoopFlags.recordTest("combat")
  print(string.format("  before reset: Memory=%d Dissonance=%d Hour=%d Years(elias)=%d",
    CampaignState.getBankedMemory(), CampaignState.getDissonance(),
    CampaignState.getHour(), CampaignState.getYears("sthr-elias")))
  CampaignState.reset()
  print(string.format("  after  reset: Memory=%d Dissonance=%d Hour=%d Years(elias)=%d",
    CampaignState.getBankedMemory(), CampaignState.getDissonance(),
    CampaignState.getHour(), CampaignState.getYears("sthr-elias")))
  check("Memory persists across reset", CampaignState.getBankedMemory() == 14)
  check("Knowledge persists across reset", CampaignState.knows("the-thirteenth-toll"))
  check("Years persist across reset", CampaignState.getYears("sthr-elias") == 3)
  check("Dissonance dropped to scar (1)", CampaignState.getDissonance() == 1)
  check("Hourglass reset to Hour I", CampaignState.getHour() == 1)
  check("once-per-loop flags cleared", not CampaignState.isFlagSet("igetout:White"))
  check("Muscle Memory now sees last-loop combat", LoopFlags.muscleMemoryUpgraded("combat"))

  -- 5. Soft cap + serialize/deserialize with the REAL TTS JSON (P2).
  CampaignState.bankMemory(30)
  CampaignState.startLoop()
  check("banked Memory soft-capped to 18 at loop start", CampaignState.getBankedMemory() == 18)
  local blob = CampaignState.serialize()               -- uses TTS global JSON.encode
  CampaignState.init(3)
  CampaignState.deserialize(blob)                       -- uses TTS global JSON.decode
  check("serialize/deserialize round-trips Memory", CampaignState.getBankedMemory() == 18)
  check("serialize/deserialize round-trips Knowledge", CampaignState.knows("the-thirteenth-toll"))

  -- 6. CO-001: Memory is experience (level-ups + Recollections).
  CampaignState.init(3)
  CampaignState.bankMemory(10)
  check("level-3 upgrade debits exactly 3",
    CampaignState.purchaseUpgrade(3) and CampaignState.getBankedMemory() == 7)
  check("Recollection debits its memoryCost (5)",
    CampaignState.purchaseRecollection(5) and CampaignState.getBankedMemory() == 2)
  check("cannot overdraw the shared pool",
    (CampaignState.purchaseUpgrade(4) == false) and CampaignState.getBankedMemory() == 2)

  -- 7. Hourglass: big Skip resolves intervening Hours; 'The Hour Was Wrong'.
  CampaignState.init(3)
  local reached = {}
  local ctx = { onHourReached = function(h) reached[#reached + 1] = h end }
  Hourglass.advance(3, ctx)
  check("advance resolves Hours II,III,IV in order",
    reached[1] == 2 and reached[2] == 3 and reached[3] == 4)
  CampaignState.init(3)
  CampaignState.unlockFact("the-hour-was-wrong")
  reached = {}
  Hourglass.advance(4, ctx)
  local sawIV = false
  for _, h in ipairs(reached) do if h == 4 then sawIV = true end end
  check("'The Hour Was Wrong' removes Hour IV from the clock", not sawIV)

  -- 8. Aging brackets + drift (P7).
  check("years 5 -> Weathered, 10 -> Elder, 15 -> Ancient",
    Aging.bracketForYears(5) == "Weathered" and Aging.bracketForYears(10) == "Elder"
    and Aging.bracketForYears(15) == "Ancient")

  print(string.format("──────────── RESULT: %d passed, %d failed ────────────", PASS, FAIL))
  broadcastToAll(string.format("Still Hour tests: %d passed, %d failed", PASS, FAIL),
    FAIL == 0 and {0.2, 1, 0.2} or {1, 0.3, 0.3})
end

-- Button wiring when attached to an object (Option A).
function onLoad()
  self.createButton({
    click_function = "runStillHourTests",
    function_owner = self,
    label = "Run Still Hour Tests",
    position = { 0, 0.3, 0 },
    width = 1400, height = 400, font_size = 160,
    color = { 0.6, 0.1, 0.1 }, font_color = { 1, 1, 1 },
  })
  print("Still Hour test harness ready — click the object's button, or run "
    .. "'>execute runStillHourTests()' from the console.")
end
