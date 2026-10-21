-- Randomized whole-campaign playthroughs on SCED's real table (tests only; designer-facing).
--
-- One seed = one campaign: a random party (1-4 of the five investigators, seated from SCED's own
-- player cards, so a random basic weakness each), a random difficulty, then a long run of random
-- actions in a random order: any button on the Control token (left or right click, in whatever panel
-- it shows), any box on the campaign log (and turning its pages), the buttons on the investigator
-- cards, Place / Recall on a random scenario box, cards played from hand onto the table, and the
-- loop's own flow (Set Up, Reset Loop, Begin Next Loop, Begin Finale) when it comes up at random.
--
-- After every action the table is checked; any failure names the seed and the last actions:
--   * no Lua error, from the campaign's scripts or SCED's
--   * the Control's state is in range (Hour I-IX, Dissonance 0..reset, Memory >= 0, Approach 0-3,
--     loops >= 0, 1-4 investigators, a known panel) and the panel is drawn
--   * every card an investigator owns is still somewhere (hand, deck, table): none lost, none doubled
--   * no two objects on the table share a GUID
--   * nothing has fallen through or off the table
--
--   lua5.4 tests/sced_real/run.lua --suite fuzz --table ... --src ... --seed 7 --actions 120
-- tests/test_sced_fuzz.py runs a handful of seeds; tools/fuzz_campaign.py runs hundreds in parallel.

return function(H)
  local E, check, info = H.E, H.check, H.info
  local J = E.J
  local seed = tonumber(H.args.seed) or 1
  local ACTIONS = tonumber(H.args.actions) or 120

  -- the run's own generator (SCED reseeds math.random for its own draws): Park-Miller, exact in
  -- Lua 5.2's doubles and 5.4's integers alike
  local rs = (seed * 48271) % 2147483647
  if rs == 0 then rs = 1 end
  local function rnd(n)
    rs = (rs * 16807) % 2147483647
    return math.floor(rs / 2147483647 * n) + 1      -- the high bits: the low ones follow the seed
  end
  for _ = 1, 12 do rnd(2) end
  local function pick(list) if #list == 0 then return nil end return list[rnd(#list)] end

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function gm(o) return decode(o.getGMNotes()) or {} end
  local function alive(o) return o ~= nil and not o.isDestroyed() end
  local function objects() return E.G.getObjects() end
  local function find(pred)
    for _, o in ipairs(objects()) do if alive(o) and pred(o) then return o end end
    return nil
  end
  local function findAll(pred)
    local l = {}
    for _, o in ipairs(objects()) do if alive(o) and pred(o) then l[#l + 1] = o end end
    return l
  end
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function handler() return E.byGuid("123456") end
  local function sced(owner, kind) return handler().call("getObjectByOwnerAndType", { owner = owner, type = kind }) end
  local function mat(colour) return sced(colour, "Playermat") end
  local COLOURS = { "White", "Orange", "Green", "Red" }

  local trail = {}
  local function did(what)
    trail[#trail + 1] = what
    if #trail > 15 then table.remove(trail, 1) end
  end
  local failed = false
  local function fail(name, detail)
    if failed then return end
    failed = true
    check(string.format("seed %d: %s", seed, name), false,
      tostring(detail) .. " || last actions: " .. table.concat(trail, " > "))
  end

  local function labelsOf(o)
    local l = {}
    for _, b in ipairs(o.getButtons() or {}) do
      -- a button with no width is a heading; a click on it does nothing worth testing
      if (b.width or 0) > 0 and b.click_function ~= "shNoop" then l[#l + 1] = b end
    end
    return l
  end
  local function clickButton(o, b, alt, where)
    did(string.format("%s '%s'%s", where, tostring(b.label):gsub("\n", " "), alt and " (right)" or ""))
    E.click(o, b.index, "White", alt)
  end

  ------------------------------------------------------------- the party --

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")
  local mark = #E.errors
  E.run(2) ; E.click(campaignBox, "Place", "White", false) ; E.run(4)
  local bag = sced("Mythos", "AllCardsBag")
  E.runUntil(function() return bag.call("isIndexReady") == true end, 120)
  local difficulties = { "Easy", "Standard", "Hard", "Expert" }
  local diff = pick(difficulties)
  E.click(control(), diff, "White", false) ; E.run(2)
  E.click(control(), "Set Up Prologue", "White", false) ; E.run(0.5)
  local partySize = rnd(4)
  local picked, order = {}, {}
  while #order < partySize do
    local i = rnd(5)
    if not picked[i] then picked[i] = true ; order[#order + 1] = i end
  end
  for _, i in ipairs(order) do E.click(control(), "shSeatPick" .. i, "White", false) end
  E.click(control(), "Seat investigators", "White", false)
  E.run(5)
  info(string.format("seed %d: %s, %d investigator(s) (%s)", seed, diff, partySize,
    table.concat((function() local t = {} for _, i in ipairs(order) do t[#t + 1] = tostring(i) end return t end)(), ",")))
  local errs = H.errorsSince(mark)
  if #errs > 0 then fail("seating raised a Lua error", H.describeErrors(errs)) end

  -- every card each investigator owns, counted wherever it is (loose, in a deck, in a hand)
  local function owned()
    local n = {}
    for _, o in ipairs(objects()) do
      if alive(o) and o.type == "Card" then
        for _, t in ipairs(o.getTags()) do
          local c = t:match("^StillHourOwner_(%a+)$")
          if c then n[c] = (n[c] or 0) + 1 end
        end
      elseif alive(o) and o.type == "Deck" then
        for _, e in ipairs(o.getObjects()) do
          for _, t in ipairs(e.tags or {}) do
            local c = t:match("^StillHourOwner_(%a+)$")
            if c then n[c] = (n[c] or 0) + 1 end
          end
        end
      end
    end
    return n
  end
  local baseline = owned()
  local seated = 0
  for _ in pairs(baseline) do seated = seated + 1 end
  if seated ~= partySize then fail("seating", "seated " .. seated .. " of " .. partySize) end

  ------------------------------------------------------------- the checks --

  local MODES = { play = true, interlude = true, setup = true }
  local function checkTable(after)
    if failed then return end
    local e = H.errorsSince(mark)
    if #e > 0 then return fail("Lua error after " .. after, H.describeErrors(e)) end
    local ctl = control()
    if not ctl then return fail("the Control token is gone", after) end
    local s = st()
    local bad = {}
    if not (s.hour >= 1 and s.hour <= 9) then bad[#bad + 1] = "hour " .. tostring(s.hour) end
    if not (s.dissonance >= 0 and s.dissonance <= 32) then bad[#bad + 1] = "dissonance " .. tostring(s.dissonance) end
    if not (s.memory >= 0) then bad[#bad + 1] = "memory " .. tostring(s.memory) end
    if not (s.stage >= 0 and s.stage <= 3) then bad[#bad + 1] = "approach " .. tostring(s.stage) end
    if not (s.loops >= 0) then bad[#bad + 1] = "loops " .. tostring(s.loops) end
    if not (s.investigators >= 1 and s.investigators <= 4) then bad[#bad + 1] = "investigators " .. tostring(s.investigators) end
    if not MODES[s.mode] then bad[#bad + 1] = "panel " .. tostring(s.mode) end
    if #(ctl.getButtons() or {}) == 0 then bad[#bad + 1] = "the panel is empty" end
    if #bad > 0 then return fail("the Control's state is out of range after " .. after, table.concat(bad, ", ")) end
    local now = owned()
    for c, n in pairs(baseline) do
      if (now[c] or 0) ~= n then
        return fail("an investigator's cards went missing or doubled after " .. after,
          string.format("%s: %d cards, %d at seating", c, now[c] or 0, n))
      end
    end
    local seen = {}
    for _, o in ipairs(objects()) do
      if alive(o) then
        local g = o.getGUID()
        if seen[g] then return fail("two objects share a GUID after " .. after, g .. ": " .. tostring(o.getName())) end
        seen[g] = true
        local p = o.getPosition()
        -- SCED's own table furniture (its legs sit below the surface) is not the campaign's
        if not H.scedGuids[g] and p.y < -5 or math.abs(p.x) > 120 or math.abs(p.z) > 120 then
          return fail("an object fell off the table after " .. after,
            string.format("%s at %.1f,%.1f,%.1f", tostring(o.getName()), p.x, p.y, p.z))
        end
      end
    end
  end
  checkTable("seating")

  ------------------------------------------------------------- the actions --

  local function logToken()
    return find(function(o) return o.hasTag("CampaignLog") or tostring(o.getName()):find("Campaign Log", 1, true) end)
  end
  local function investigatorCards()
    return findAll(function(o) return o.type == "Card" and gm(o).type == "Investigator" and #(o.getButtons() or {}) > 0 end)
  end
  local function boxes()
    return findAll(function(o) return gm(o).type == "ScenarioBox" end)
  end

  local actions = {
    -- weight, name, fn
    { 30, "Control button", function()
      local ctl = control()
      local b = pick(labelsOf(ctl))
      if b then clickButton(ctl, b, rnd(4) == 1, "Control") end
    end },
    { 12, "log box", function()
      local log = logToken()
      if not log then return end
      if rnd(8) == 1 then did("log: Next page") ; E.menu(log, "Next page") ; return end
      local b = pick(labelsOf(log))
      if b then clickButton(log, b, rnd(5) == 1, "log") end
    end },
    { 10, "investigator card", function()
      local c = pick(investigatorCards())
      local b = c and pick(labelsOf(c))
      if b then clickButton(c, b, rnd(3) == 1, "card " .. tostring(c.getName())) end
    end },
    { 5, "Place or Recall a box", function()
      local b = pick(boxes())
      if not b then return end
      local which = (rnd(3) == 1) and "Recall" or "Place"
      did(which .. " " .. tostring(b.getName()))
      E.click(b, which, "White", false)
    end },
    { 6, "play a card from hand", function()
      local c = pick(COLOURS)
      local m = mat(c)
      local pc = m and m.getVar("playerColor")
      local h = pc and E.G.Player[pc] and E.G.Player[pc].getHandObjects() or {}
      local card = pick(h)
      if card then
        local p = m.positionToWorld({ rnd(3) * 0.4 - 0.4, 0, rnd(3) * 0.3 - 0.6 })
        did("play " .. tostring(card.getName()) .. " (" .. c .. ")")
        card.setPosition({ p.x, p.y + 0.5, p.z })
      end
    end },
    { 6, "the loop's flow", function()
      local ctl = control()
      local s = st()
      local want
      if s.loopEnded then want = pick({ "Interlude", "Begin Next Loop", "Set Up" })
      elseif s.finale then want = pick({ "Hour", "Forms defeated", "Reset Loop" })
      else want = pick({ "Reset Loop", "Set Up", "Begin Finale", "Hour", "Dissonance" }) end
      for _, b in ipairs(labelsOf(ctl)) do
        if tostring(b.label):sub(1, #want) == want then
          clickButton(ctl, b, false, "flow")
          -- a Reset Loop the Control asks to confirm is confirmed half the time
          if want == "Reset Loop" and rnd(2) == 1 then
            E.run(0.3)
            for _, b2 in ipairs(labelsOf(control())) do
              if tostring(b2.label):sub(1, 10) == "Reset Loop" then return clickButton(control(), b2, false, "flow") end
            end
          end
          return
        end
      end
    end },
    { 8, "play on to the next loop", function()
      -- what the players do at the end of a night, in order: Reset Loop (confirmed), the Interlude
      -- (Age everyone, Bank, maybe a purchase), Begin Next Loop (past its warning), Set Up Loop
      local function press(prefix, alt)
        local ctl = control()
        for _, b in ipairs(labelsOf(ctl)) do
          if tostring(b.label):sub(1, #prefix) == prefix then clickButton(ctl, b, alt, "next loop") ; return true end
        end
        return false
      end
      if not st().loopEnded then press("Reset Loop") ; E.run(0.5) ; press("Reset Loop") ; E.run(2) end
      press("Interlude") ; E.run(0.5)
      local ctl = control()
      for _, b in ipairs(labelsOf(ctl)) do
        if b.label == "Age" then clickButton(ctl, b, false, "next loop") ; E.run(0.3) end
      end
      press("Bank on-card Memory") ; E.run(0.3)
      if rnd(2) == 1 then
        local buys = {}
        for _, b in ipairs(labelsOf(control())) do
          if tostring(b.click_function):find("^shBuy") then buys[#buys + 1] = b end
        end
        local b = pick(buys)
        if b then clickButton(control(), b, false, "next loop") end
      end
      press("Begin Next Loop") ; E.run(0.5)
      if st().loopEnded then press("Begin Next Loop") ; E.run(0.5) end
      if press("Set Up Loop") then E.run(0.5) ; press("Set Up Loop") end
      E.run(40)
    end },
    { 3, "let time pass", function()
      did("wait 20s")
      E.run(20)
    end },
  }
  local total = 0
  for _, a in ipairs(actions) do total = total + a[1] end
  local function choose()
    local r = rnd(total)
    for _, a in ipairs(actions) do
      r = r - a[1]
      if r <= 0 then return a end
    end
    return actions[1]
  end

  for i = 1, ACTIONS do
    if failed then break end
    local a = choose()
    local ok, err = xpcall(a[3], function(e) return debug.traceback(tostring(e), 2) end)
    if not ok then fail("the harness could not do '" .. a[2] .. "'", err) break end
    E.run(0.2 + rnd(20) / 10)
    checkTable(string.format("action %d (%s)", i, a[2]))
  end
  -- whatever was started (a Set Up, a board sync) is allowed to finish, then the table is checked again
  E.run(60)
  checkTable("the table settled")
  local s = st()
  info(string.format("seed %d ended: loops %d, hour %d, dissonance %d, memory %d, prologue %s, finale %s, part II %s",
    seed, s.loops, s.hour, s.dissonance, s.memory, tostring(s.prologue), tostring(s.finale), tostring(s.partTwo)))
  if not failed then check(string.format("seed %d: %d random actions, no Lua error, the table stayed sound", seed, ACTIONS), true) end
end
