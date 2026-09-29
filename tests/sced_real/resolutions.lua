-- Every story resolution of THE STILL HOUR, played on the emulated table
-- (tests only; designer-facing, so it names outcomes freely).
--
-- For each resolution in docs/design/THE_STILL_HOUR_player_guide.md (the
-- Prologue's, the loop's, each district's, the finale's R1/R1b/R2-R6 and the
-- epilogue) this suite:
--   1. forces the state that triggers it, through what the owner touches (the
--      Control token's buttons, the investigator cards' buttons, the campaign
--      log's boxes/counters/inputs and context menu) or, where the guide has
--      no button (a Hold Back on an Appointed that is not on the table), the
--      Control's API;
--   2. asks ORACLE (the guide's conditions, reading ONLY the campaign log and
--      the Control) which resolution applies, and checks it is exactly the
--      intended one, so every condition is shown reachable and the
--      top-to-bottom orders give one answer;
--   3. records it exactly as the resolution text instructs a player, then
--      runs Between Loops (Reset Loop, Interlude, Age, Bank, Begin Next Loop)
--      where the guide sends the table there, and checks the Control's state,
--      the log's fields and the next loop's setup.
-- Between scenarios the harness restores the Control from a snapshot
-- (shApiSnapshot / shApiRestore) and the log from a copy of its values: that
-- is bookkeeping, not play.

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local J = E.J

  ------------------------------------------------------------ helpers --

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function gm(o) return decode(o.getGMNotes()) or {} end
  local function objects() return E.G.getObjects() end
  local function find(pred)
    for _, o in ipairs(objects()) do if pred(o) then return o end end
    return nil
  end
  local function labels(o)
    local l = {}
    for _, b in ipairs(o and o.getButtons() or {}) do l[#l + 1] = tostring(b.label) end
    return table.concat(l, " | ")
  end
  local function hasLabel(o, prefix)
    for _, b in ipairs(o and o.getButtons() or {}) do
      if tostring(b.label):sub(1, #prefix) == prefix then return true end
    end
    return false
  end
  local function buttonLabel(o, fn)
    for _, b in ipairs(o and o.getButtons() or {}) do
      if b.click_function == fn then return tostring(b.label) end
    end
    return nil
  end
  local function click(o, which, alt)
    local ok, err = E.click(o, which, "White", alt)
    if not ok then check("button '" .. tostring(which) .. "' can be clicked", false, err) end
    return ok
  end
  local function times(n, fn) for _ = 1, n do fn() end end

  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function ctl(fn, alt) local ok = click(control(), fn, alt) ; E.run(0.2) ; return ok end

  -- the table's chat since a mark
  local function chatMark() return #E.log end
  local function chatHas(mark, needle)
    for i = mark + 1, #E.log do
      if tostring(E.log[i].msg):find(needle, 1, true) then return true end
    end
    return false
  end

  ------------------------------------------------------------ the log --

  local function campaignLog()
    return find(function(o) return o.hasTag("CampaignLog") and gm(o).type == "CampaignLog" end)
  end
  local function logGoto(n)
    for _ = 1, 4 do
      local log = campaignLog()
      if not log then return nil end
      if log.call("getLogValues").page == n then return log end
      E.menu(log, "Next page")
      E.run(0.5)
    end
    return nil
  end
  local PAGE_OF, FIELDS_OF = {}, {}
  local function scanLog()
    for p = 1, 3 do
      local log = logGoto(p)
      FIELDS_OF[p] = log and log.getVar("FIELDS") or {}
      for _, f in ipairs(FIELDS_OF[p]) do PAGE_OF[f.k] = p end
    end
  end
  local function field(key)
    local p = PAGE_OF[key]
    if not p then check("the campaign log has a field " .. key, false) ; return nil end
    local log = logGoto(p)
    for i, f in ipairs(FIELDS_OF[p]) do if f.k == key then return log, i, f end end
    return nil
  end
  local function logVal(key)
    local log = field(key)
    return log and log.call("getLogValues").values[key]
  end
  local function logClick(key, alt)
    local log, i = field(key)
    if log then click(log, "sthrLog_" .. i, alt) ; E.run(0.2) end
  end
  --- a checkbox to on/off, clicking only when it differs (as a player would)
  local function logTick(key, on)
    if on == nil then on = true end
    if (logVal(key) == true) ~= on then logClick(key) end
  end
  local function logCount(key, n)
    for _ = 1, 99 do
      local v = tonumber(logVal(key)) or 0
      if v == n then return end
      logClick(key, v > n)
    end
  end
  local function logType(key, text)
    local log, i = field(key)
    if not log then return end
    local idx = 0
    for j = 1, i - 1 do if FIELDS_OF[PAGE_OF[key]][j].t == "tx" then idx = idx + 1 end end
    E.type(log, idx, text)
    E.run(0.2)
  end
  local function logShows(key, text)
    local log = field(key)
    return log ~= nil and hasLabel(log, text)
  end
  local function logSync(page)
    local log = logGoto(page)
    E.menu(log, "Sync from campaign")
    E.run(0.5)
  end
  -- bookkeeping between scenarios: every page's values, and putting them back
  local function logSnapshot()
    local snap = {}
    for p = 1, 3 do snap[p] = J.encode(logGoto(p).call("getLogValues").values) end
    return snap
  end
  local function logRestore(snap)
    for p = 1, 3 do
      local log = logGoto(p)
      local want = decode(snap[p]) or {}
      for _, f in ipairs(FIELDS_OF[p]) do
        if f.t == "cb" or f.t == "ct" or f.t == "tx" then
          local v = want[f.k]
          if v == nil then
            if f.t == "cb" then v = false
            elseif f.t == "ct" then v = (f.k == "investigators") and 3 or 0
            else v = "" end
          end
          if log.call("getLogValues").values[f.k] ~= v then log.call("setLogValue", { key = f.k, value = v }) end
        end
      end
    end
  end

  ----------------------------------------------------- investigators --

  local PARTY = { "sthrelias", "sthrseraphine", "sthrbirdie" }
  local NAME = { sthrelias = "Elias Warde", sthrseraphine = "Seraphine Vale", sthrbirdie = "\"Birdie\" Okonkwo" }
  local cards, slot = {}, {}      -- id -> investigator card; id -> Interlude panel row
  local function refreshSlots()
    slot = {}
    for i, inv in ipairs(control().call("shApiInvestigators") or {}) do slot[inv.id] = i end
  end
  local function years(id)
    for _, inv in ipairs(control().call("shApiInvestigators") or {}) do if inv.id == id then return inv.years end end
    return nil
  end
  local function onCard(id)
    for _, inv in ipairs(control().call("shApiInvestigators") or {}) do if inv.id == id then return inv.memory end end
    return nil
  end
  local function pending(id)
    local l = buttonLabel(cards[id], "shCardYears") or ""
    return tonumber(l:match("(%d+)$"))
  end
  local function addPending(id, n)
    times(math.abs(n), function() click(cards[id], "shCardYears", n < 0) end)
    E.run(0.2)
  end

  --------------------------------------------------------- the oracle --
  -- The guide's conditions. It reads the campaign log (logVal) and the
  -- Control (its state, and each investigator's Years and Years pending)
  -- and nothing else, so a condition that needs an input the log or the
  -- Control does not hold fails here.

  local ORACLE = {}
  local SURFACE = { lighthouse = "the-lamp-was-never-lit", church = "the-thirteenth-toll",
    road = "the-road-remembers", square = "the-sheriff-is-already-dead", fairground = "the-wheel-still-turns",
    almanac = "what-the-almanac-hid" }
  local DEEP = { lighthouse = "the-keepers-ninth-death", church = "the-hour-was-wrong",
    road = "who-walks-beside-you", square = "the-vote-that-never-ends", fairground = "the-ticket-takers-bargain",
    almanac = "the-appointeds-name" }
  local CHOICE_ROW = { lighthouse = "ninth", church = "page", road = "ring", square = "vote",
    fairground = "ticket", almanac = "name" }

  local function bracket(y)
    if y >= 15 then return "Ancient" elseif y >= 10 then return "Elder" elseif y >= 5 then return "Weathered" end
    return "Prime"
  end
  local function knows(id) return logVal("k:" .. id) == true end

  -- Prologue: its three endings (the Prologue ends at the first to happen)
  function ORACLE.prologue(ev)
    local out = {}
    if ev.actAdvanced then out[#out + 1] = "R1" end
    if ev.hour >= 9 or ev.dissonance >= ev.reset then out[#out + 1] = "R2" end
    if ev.allDefeated then out[#out + 1] = "NR" end
    return out
  end
  -- The Loop: "check the endings top to bottom and read the first that happened"
  function ORACLE.loop(ev)
    local out = {}
    if ev.dissonance >= ev.reset then out[#out + 1] = "R2" end
    if ev.allDefeated then out[#out + 1] = "NR" end
    if ev.hour >= 9 then out[#out + 1] = "R1" end
    return out[1], out
  end
  -- a district: top to bottom, first that applies
  function ORACLE.district(d, done)
    if done.deep then return "R1" end
    if done.surface then return "R2" end
    if knows(SURFACE[d]) or knows(DEEP[d]) then return "R3" end
    return "NR"
  end
  --- the finale. f = {contest = bool, present = {id = true}}; Years for a
  -- condition are recorded + pending (guide: The Last Hour)
  function ORACLE.finale(f)
    local s = st()
    local n = s.investigators
    if not f.contest then return { s.memory >= 4 * n and "R5" or "R6" } end
    local opts = {}
    local r1 = false
    for id in pairs(f.present) do
      if bracket(years(id) + (pending(id) or 0)) == "Ancient" then r1 = true end
    end
    local signer = logVal("ninth_signer") or ""
    if logVal("ninth_a") == true then
      for id in pairs(f.present) do
        if signer ~= "" and NAME[id]:lower():find(signer:lower(), 1, true) then r1 = true end
      end
    end
    if r1 then opts[#opts + 1] = "R1" end
    local need = (logVal("prologue_b") == true) and 3 or 4
    if knows("the-ticket-takers-bargain") and logVal("ticket_a") == true and s.memory >= need * n then
      opts[#opts + 1] = "R1b"
    end
    if knows("the-vote-that-never-ends") and knows("the-appointeds-name") and logVal("vote_b") == true then
      opts[#opts + 1] = "R2"
    end
    if knows("the-keepers-ninth-death") then opts[#opts + 1] = "R3" end
    opts[#opts + 1] = "R4"
    return opts
  end
  --- the epilogue: one line per present investigator not kept as anchor and
  -- not aged out, by the bracket of recorded + pending Years (the finale's
  -- Years are clicked as Years pending); Seraphine's thread from the log
  function ORACLE.epilogue(res, f)
    if res == "R5" or res == "R6" then return nil end
    local lines = {}
    for id in pairs(f.present) do
      if id ~= f.anchor and id ~= f.agedOut then lines[id] = bracket(years(id) + (pending(id) or 0)) end
    end
    local thread = (logVal("sera_known") and "known") or (logVal("sera_suspected") and "suspected")
      or (logVal("sera_unheard") and "unheard") or nil
    return lines, lines.sthrseraphine and thread or nil
  end
  local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not same(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
  end
  local function list(t) return J.encode(t) end
  local function has(l, x)
    for _, v in ipairs(l or {}) do if v == x then return true end end
    return false
  end
  --- the log's investigator row (page 1) whose name contains `part`
  local function invRow(part)
    for k = 1, 4 do if tostring(logVal("inv" .. k .. "_name")):find(part, 1, true) then return k end end
    return nil
  end

  ------------------------------------------------------------ setup --

  local payloadPath = H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")
  info("payload: " .. payloadPath)
  local snaps = {}   -- name -> { control = blob, log = values }
  local function save(name)
    snaps[name] = { control = control().call("shApiSnapshot"), log = logSnapshot() }
  end
  local function restore(name)
    local s = snaps[name]
    control().call("shApiRestore", { blob = s.control })
    control().call("shApiInterlude", { open = false })
    logRestore(s.log)
    E.run(0.5)
  end
  local function endLoop()            -- Between Loops: Reset Loop, then Interlude
    ctl("shReset") ; ctl("shOpenInterlude")
  end
  local function age(id, defeated)
    local i = slot[id]
    if defeated then
      local l = buttonLabel(control(), "shAgeDef" .. i) or ""
      if l:find("no", 1, true) then ctl("shAgeDef" .. i) end
    end
    ctl("shAge" .. i)
  end

  step("setup: the campaign box, three investigators, a new campaign", function()
    local payload = decode(H.readFile(payloadPath))
    local box = E.spawnData(payload.ObjectStates[1], {}, "campaign")
    E.run(2)
    click(box, "Place")
    E.run(4)
    check("the Control token and the campaign log are on the table", control() ~= nil and campaignLog() ~= nil)
    E.run(2)
    local n = st().investigators
    times(math.abs(n - 3), function() ctl("shClickInvestigators", n > 3) end)
    check("Investigators = 3", st().investigators == 3, st().investigators)
    local pbag = find(function(o) return o.type == "Bag" and o.hasTag("StillHour")
      and tostring(o.getName()):find("Player Cards", 1, true) ~= nil end)
    for i, id in ipairs(PARTY) do
      local guid
      for _, e in ipairs(pbag and pbag.getObjects() or {}) do
        if (decode(e.gm_notes) or {}).id == id then guid = e.guid end
      end
      local pos = { 40 + 4 * i, 2.5, -30 }
      local c = guid and pbag.takeObject({ guid = guid, position = pos, smooth = false })
      E.run(1)
      if c then E.drop(c, { pos[1], 1.6, pos[3] }) ; cards[id] = c end
    end
    E.run(2)
    ctl("shSyncBoard")
    refreshSlots()
    check("the Control finds the three investigators", slot.sthrelias and slot.sthrseraphine and slot.sthrbirdie,
      list(slot))
    check("each investigator card carries Years pending", pending("sthrelias") == 0, labels(cards.sthrelias))
    scanLog()
    check("the campaign log has its three pages of fields", #FIELDS_OF[1] > 0 and #FIELDS_OF[2] > 0 and #FIELDS_OF[3] > 0)
    local s = st()
    check("a new campaign: Prologue, Hour I, Dissonance 0, Memory 0",
      s.prologue and s.hour == 1 and s.dissonance == 0 and s.memory == 0, list(s))
    save("fresh")
  end)

  -- every input the oracle, the guide's later checks and the epilogue read
  -- has a place on the log
  step("the log holds every record a later check reads", function()
    local missing = {}
    local want = { "k:you-are-unstuck", "k:the-way-the-night-breaks", "torn", "taken", "closed",
      "pro_r1", "pro_r2", "pro_nr", "ninth_signer", "sera_unheard", "sera_suspected", "sera_known",
      "contest_yes", "contest_no", "finale_memory", "spent_deep", "anchor", "aged3", "finale_loop",
      "r1", "r1b", "r2", "r3", "r4", "r5", "r6" }
    for d, id in pairs(SURFACE) do
      want[#want + 1] = "k:" .. id ; want[#want + 1] = "k:" .. DEEP[d]
      want[#want + 1] = CHOICE_ROW[d] .. "_a" ; want[#want + 1] = CHOICE_ROW[d] .. "_b"
    end
    want[#want + 1] = "prologue_a" ; want[#want + 1] = "prologue_b"
    for i = 1, 4 do
      for _, k in ipairs({ "inv%d_years", "inv%d_agedout", "dead%d_name", "dead%d_aged", "dead%d_kept" }) do
        want[#want + 1] = k:format(i)
      end
    end
    for _, k in ipairs(want) do if not PAGE_OF[k] then missing[#missing + 1] = k end end
    check("every record has a field on the log (" .. #want .. ")", #missing == 0, table.concat(missing, ", "))
  end)

  ------------------------------------------------------------ prologue --

  local function prologueEnd(res, memoryEach, extra, choice)
    local m0 = st().memory
    times(memoryEach * 3 + extra, function() ctl("shClickMemory") end)
    check(res .. ": the banked Memory button banks " .. (memoryEach * 3 + extra), st().memory == m0 + memoryEach * 3 + extra,
      m0 .. " -> " .. st().memory)
    logTick("k:you-are-unstuck")
    check(res .. ": You Are Unstuck recorded; the Prologue's entry pays nothing",
      st().memory == m0 + memoryEach * 3 + extra and logShows("kr:you-are-unstuck", "You Are Unstuck"))
    logTick(({ R1 = "pro_r1", R2 = "pro_r2", NR = "pro_nr" })[res])
    logTick(choice)
    check(res .. ": What You Saw is recorded (its text shows only on the ticked row)",
      logShows(choice .. "r", choice == "prologue_a" and "The town was warned" or "You kept the night to yourselves")
      and not logShows(choice == "prologue_a" and "prologue_br" or "prologue_ar",
        choice == "prologue_a" and "You kept the night to yourselves" or "The town was warned"))
    endLoop()
    local s = st()
    check(res .. ": Reset Loop ends the Prologue; it is not a loop (loops 0, Dissonance 0, Hour I, no Appointed)",
      not s.prologue and s.loops == 0 and s.dissonance == 0 and s.hour == 1 and s.stage == 0 and s.loopEnded, list(s))
    check(res .. ": no Years after the Prologue: the Age buttons read No Age",
      buttonLabel(control(), "shAge1") == "No Age", labels(control()))
    local y0 = years("sthrelias")
    age("sthrelias", true)
    check(res .. ": Age does nothing after the Prologue (even defeated)", years("sthrelias") == y0, years("sthrelias"))
    ctl("shBankOnCard")
    ctl("shBeginNextLoop")
    s = st()
    check(res .. ": Begin Next Loop starts Loop 1 at Hour I, Dissonance 0 (scar 0), Part I",
      s.mode == "play" and s.hour == 1 and s.dissonance == 0 and not s.partTwo and not s.loopEnded and s.loops == 0,
      list(s))
    check(res .. ": the Control's header reads loop 1", hasLabel(control(), "THE STILL HOUR · loop 1"), labels(control()))
    logSync(1) ; logSync(2)
    check(res .. ": the log syncs Part I, 0 loops, the banked Memory",
      logVal("act1") == true and logVal("loops") == 0 and logVal("banked") == s.memory, list({ logVal("act1"), logVal("loops"), logVal("banked") }))
    check(res .. ": Seraphine's thread starts unheard on the log", logVal("sera_unheard") == true)
  end

  step("Prologue R1 (You Saw It Coming): the act advanced", function()
    restore("fresh")
    check("oracle: R1 when The First Hour advances", same(ORACLE.prologue({ actAdvanced = true, hour = 3, dissonance = 2,
      reset = 18 }), { "R1" }))
    prologueEnd("R1", 2, 1, "prologue_a")
    check("R1: 2 per investigator + 1 = 7 banked", st().memory == 7, st().memory)
    save("loop1")                       -- Loop 1, the town was warned, 7 Memory
  end)

  step("Prologue R2 (It Caught You Unready): Hour IX", function()
    restore("fresh")
    local mark = chatMark()
    times(8, function() ctl("shClickHour") end)
    local s = st()
    check("Hour IX reached in the Prologue; Hours III and VIII raised Dissonance (1 + 2)", s.hour == 9 and s.dissonance == 3,
      list(s))
    check("no Appointed in the Prologue: Hours V, VII, VIII leave it Unseen", s.stage == 0, s.stage)
    check("the Control tells the table the night ends", chatHas(mark, "the night ends"))
    check("oracle: R2", same(ORACLE.prologue({ hour = s.hour, dissonance = s.dissonance, reset = 18 }), { "R2" }))
    prologueEnd("R2", 2, 0, "prologue_b")
    check("R2: 2 per investigator = 6 banked", st().memory == 6, st().memory)
  end)

  step("Prologue R2 (It Caught You Unready): Dissonance reached the reset value", function()
    restore("fresh")
    local mark = chatMark()
    times(18, function() ctl("shClickDissonance") end)
    local s = st()
    check("Dissonance 18 = the reset value at 3 investigators", s.dissonance == 18 and s.band == "Noticed", list(s))
    check("no Appointed in the Prologue even in the Noticed band", s.stage == 0, s.stage)
    check("the Control announces the reset", chatHas(mark, "reset threshold"))
    check("oracle: R2", same(ORACLE.prologue({ hour = s.hour, dissonance = s.dissonance, reset = 18 }), { "R2" }))
    prologueEnd("R2", 2, 0, "prologue_a")
    check("the Prologue's reset is not 'ended in danger'", st().danger == false, list(st()))
  end)

  step("Prologue No Resolution (The First Death): every investigator defeated", function()
    restore("fresh")
    check("oracle: NR", same(ORACLE.prologue({ allDefeated = true, hour = 4, dissonance = 1, reset = 18 }), { "NR" }))
    prologueEnd("NR", 2, 0, "prologue_a")
    check("NR: 6 banked and no Years for anyone (the first death is free)", st().memory == 6
      and years("sthrelias") == 0 and years("sthrbirdie") == 0 and years("sthrseraphine") == 0)
  end)

  --------------------------------------------------------------- loops --

  local function loopStart(label)
    local s = st()
    check(label .. ": the next loop begins at Hour I, Dissonance = scar " .. math.min(s.loops, 6) ..
      ", the Appointed Unseen", s.hour == 1 and s.dissonance == math.min(s.loops, 6) and s.stage == 0
      and s.mode == "play" and not s.loopEnded, list(s))
  end

  step("Loop R1 (The Appointed Hour): the Hourglass reached Hour IX", function()
    restore("loop1")
    local mark = chatMark()
    logTick("k:the-lamp-was-never-lit")        -- a new entry this loop (Light the Lamp)
    check("a new surface entry pays 1 per investigator", st().memory == 10, st().memory)
    times(8, function() ctl("shClickHour") end)
    local s = st()
    check("Hour IX: Hour V/VII/VIII brought the Appointed to Arrived; Dissonance 0 + 1 + 2", s.hour == 9
      and s.stage == 3 and s.dissonance == 3, list(s))
    check("the Control says the loop ends", chatHas(mark, "the night ends"))
    local first, all = ORACLE.loop({ dissonance = s.dissonance, reset = 18, hour = s.hour })
    check("oracle: R1 alone", first == "R1" and #all == 1, list(all))
    logClick("closed")
    check("Closed at the Hour counted on the log", logVal("closed") == 1, logVal("closed"))
    -- "Before anything else, claim Victory for each Victory X location in
    -- play, revealed and with no clues on it"
    local m = st().memory
    logTick("v:sthr-loc-keepersquarters")
    check("a Victory 1 location claimed at the loop's end banks 1, marked banked",
      st().memory == m + 1 and logVal("vb:sthr-loc-keepersquarters") == true, m .. " -> " .. st().memory)
    logTick("v:sthr-loc-keepersquarters", false) ; logTick("v:sthr-loc-keepersquarters", true)
    check("...once per campaign", st().memory == m + 1, st().memory)
    check("a Lighthouse district resolution: R2 (Light the Lamp completed)",
      ORACLE.district("lighthouse", { surface = true }) == "R2")
    check("an unvisited district: No Resolution", ORACLE.district("church", {}) == "NR")
    endLoop()
    s = st()
    check("Reset Loop counts Loop 1; not in danger (3 < 12)", s.loops == 1 and s.danger == false, list(s))
    check("the Interlude shows 'Loop ended in danger: no'", hasLabel(control(), "Loop ended in danger: no"), labels(control()))
    for _, id in ipairs(PARTY) do age(id) end
    check("each investigator gains 1 Year", years("sthrelias") == 1 and years("sthrseraphine") == 1 and years("sthrbirdie") == 1)
    check("Age is once per interlude", buttonLabel(control(), "shAge1") == "Aged +1", labels(control()))
    ctl("shAge1")
    check("a second Age click adds nothing", years("sthrbirdie") == 1 and years("sthrelias") == 1)
    ctl("shBeginNextLoop")
    loopStart("R1")
    check("the lamp's location stays turned: a later check on the district reads R3 if nothing is done",
      ORACLE.district("lighthouse", {}) == "R3")
  end)

  step("Loop R2 (The Seam Tears): Dissonance reached the reset value, twice", function()
    restore("loop1")
    for pass = 1, 2 do
      local mark = chatMark()
      local d0 = st().dissonance
      times(18 - d0, function() ctl("shClickDissonance") end)
      local s = st()
      check("pass " .. pass .. ": Dissonance 18, Noticed, the Appointed Arrived, 2 band [static]", s.dissonance == 18
        and s.band == "Noticed" and s.stage == 3 and s.static.baseline == 2, list(s))
      check("pass " .. pass .. ": the Control announces the reset", chatHas(mark, "reset threshold"))
      local first, all = ORACLE.loop({ dissonance = 18, reset = 18, hour = s.hour, allDefeated = pass == 2 })
      check("pass " .. pass .. ": oracle reads R2 first" .. (pass == 2 and " (even with every investigator defeated too)" or ""),
        first == "R2", list(all))
      logClick("torn")
      endLoop()
      s = st()
      check("pass " .. pass .. ": Reset Loop: the loop ended in danger", s.danger == true, list(s))
      check("pass " .. pass .. ": the Interlude shows 'Loop ended in danger: yes (+1)'",
        hasLabel(control(), "Loop ended in danger: yes (+1)"), labels(control()))
      local y0 = years("sthrelias")
      for _, id in ipairs(PARTY) do age(id, pass == 2) end
      check("pass " .. pass .. ": +1 Year always, +1 for the Noticed band" .. (pass == 2 and ", +1 defeated" or ""),
        years("sthrelias") == y0 + (pass == 2 and 3 or 2), y0 .. " -> " .. years("sthrelias"))
      ctl("shBeginNextLoop")
      loopStart("R2 pass " .. pass)
      check("pass " .. pass .. ": the band's [static] follow the scar back down", st().static.baseline == 0, list(st().static))
    end
    check("the log counts two Torn loops: the second-or-later story applies", logVal("torn") == 2, logVal("torn"))
  end)

  step("Loop No Resolution (The Night Keeps You): every investigator defeated", function()
    restore("loop1")
    times(3, function() click(cards.sthrelias, "shCardRaised") end)   -- Elias leaned on the loop
    E.run(0.2)
    local s = st()
    local first, all = ORACLE.loop({ dissonance = s.dissonance, reset = 18, hour = s.hour, allDefeated = true })
    check("oracle: NR", first == "NR" and #all == 1, list(all))
    logClick("taken")
    endLoop()
    check("the Interlude derives 'Leaned: yes' for Elias from his card's tally",
      hasLabel(control(), "Leaned: yes"), labels(control()))
    for _, id in ipairs(PARTY) do age(id, true) end
    check("defeated: 1 + 1 Years; Elias leaned: + 1 more", years("sthrbirdie") == 2 and years("sthrseraphine") == 2
      and years("sthrelias") == 3, list({ years("sthrbirdie"), years("sthrseraphine"), years("sthrelias") }))
    ctl("shBeginNextLoop")
    loopStart("NR")
    check("Begin Next Loop clears the tallies", hasLabel(cards.sthrelias, "Dissonance raised 0"), labels(cards.sthrelias))
    check("the log counts one Taken loop", logVal("taken") == 1)
  end)

  step("Part II begins after Loop 3 (Between Loops step 5)", function()
    restore("loop1")
    for loop = 1, 3 do
      local mark = chatMark()
      times(8, function() ctl("shClickHour") end)
      endLoop()
      check("after Loop " .. loop .. ": Part II " .. (loop == 3 and "begins" or "not yet"),
        st().partTwo == (loop == 3) and (loop < 3 or chatHas(mark, "Part II begins")), list(st()))
      ctl("shBeginNextLoop")
    end
    check("Loop 4 starts at scar 3", st().dissonance == 3, st().dissonance)
    logSync(1)
    check("the log syncs Part II and 3 loops", logVal("act2") == true and logVal("loops") == 3)
  end)

  step("Part II begins with a third surface entry; one ticked mid-loop waits for Between Loops", function()
    restore("loop1")
    logTick("k:the-lamp-was-never-lit")
    logTick("k:the-thirteenth-toll")
    logTick("k:the-road-remembers")
    check("three surface entries: 3 x 3 banked Memory", st().memory == 16, st().memory)
    check("still Part I during the loop", st().partTwo == false)
    local mark = chatMark()
    endLoop()
    check("Reset Loop starts Part II (step 5)", st().partTwo == true and chatHas(mark, "Part II begins"))
    ctl("shBeginNextLoop")
    check("Begin Next Loop caps banked Memory at 18", st().memory <= 18, st().memory)
    save("part2")                       -- Loop 2, Part II, 3 surface entries, no Years yet
  end)

  ----------------------------------------------------------- districts --

  local function deepResolution(d, choice, extra)
    local m0 = st().memory
    logTick("k:" .. DEEP[d])
    check(d .. " R1: the deep entry pays 3 per investigator", st().memory == m0 + 9, m0 .. " -> " .. st().memory)
    check(d .. " R1: oracle reads R1", ORACLE.district(d, { deep = true, surface = true }) == "R1")
    logTick(CHOICE_ROW[d] .. choice)
    local other = CHOICE_ROW[d] .. (choice == "_a" and "_b" or "_a")
    check(d .. " R1: the choice is recorded, the other box stays clear", logVal(CHOICE_ROW[d] .. choice) == true
      and logVal(other) ~= true)
    if extra then extra() end
  end

  step("district resolutions: surface R2, deep R1 with each choice, R3 and No Resolution", function()
    restore("part2")
    -- R3 / No Resolution: nothing recorded
    local m0 = st().memory
    check("Lighthouse visited, nothing done, its surface entry known: R3", ORACLE.district("lighthouse", {}) == "R3")
    check("Fairground visited, nothing done, nothing known: No Resolution", ORACLE.district("fairground", {}) == "NR")
    check("reading R3 / No Resolution records nothing", st().memory == m0)
    -- the surfaces this campaign has not recorded yet (R2)
    for _, d in ipairs({ "square", "fairground", "almanac" }) do
      local m = st().memory
      logTick("k:" .. SURFACE[d])
      check(d .. " R2: the surface entry pays 1 per investigator", st().memory == m + 3, m .. " -> " .. st().memory)
      check(d .. " R2: oracle reads R2", ORACLE.district(d, { surface = true }) == "R2")
    end
    -- a mis-tick un-ticked: refunded, and re-ticking pays nothing twice
    local m = st().memory
    logTick("k:the-wheel-still-turns", false)
    logTick("k:the-wheel-still-turns", true)
    check("un-ticking and re-ticking an entry pays it once", st().memory == m, m .. " -> " .. st().memory)
    -- deep resolutions with their choices
    deepResolution("lighthouse", "_a", function()
      logType("ninth_signer", "Birdie")
      addPending("sthrbirdie", 1)
      check("Lighthouse R1 (sign): the signer's name is on the log; +1 Year pending on the signer's card",
        logVal("ninth_signer") == "Birdie" and pending("sthrbirdie") == 1 and pending("sthrelias") == 0)
    end)
    deepResolution("church", "_a")
    deepResolution("road", "_b")
    -- the Square's deep entry comes before the Almanac's (its act 2a needs The Vote)
    deepResolution("square", "_b")
    logSync(2)
    check("Sync leaves Seraphine's thread to the players (still 'unheard')", logVal("sera_unheard") == true
      and logVal("sera_suspected") ~= true)
    logTick("sera_suspected")   -- the Vote's act, with Seraphine at the Records Office
    check("The Vote That Never Ends: Seraphine's thread 'suspected' on the log", logVal("sera_suspected") == true
      and logVal("sera_unheard") ~= true)
    check("no finale yet: The Way the Night Breaks needs The Appointed's Name",
      not hasLabel(control(), "Begin Finale"))
    local mark = chatMark()
    deepResolution("almanac", "_a", function()
      for _, id in ipairs(PARTY) do addPending(id, 1) end
      check("Almanac R1 (speak the name): +1 Year pending on every investigator card",
        pending("sthrelias") == 1 and pending("sthrseraphine") == 1 and pending("sthrbirdie") == 2)
    end)
    check("the Control tells the table to record The Way the Night Breaks", chatHas(mark, "Record The Way the Night Breaks"))
    check("Begin Finale appears", hasLabel(control(), "Begin Finale"), labels(control()))
    local m1 = st().memory
    logTick("k:the-way-the-night-breaks")
    check("ticking the assembled entry pays nothing", st().memory == m1)
    logSync(1) ; logSync(2)
    logTick("sera_known")       -- the Name's act, with Seraphine at the Sealed Study
    check("the log syncs 'The Last Hour available'; Seraphine's thread 'known' replaces 'suspected'",
      logVal("act3") == true and logVal("sera_known") == true and logVal("sera_suspected") ~= true)
    deepResolution("fairground", "_b")
    -- Between Loops: pending Years reach Age, then clear
    endLoop()
    for _, id in ipairs(PARTY) do age(id) end
    check("Age adds the pending Years: Birdie 1 + 2, Elias and Seraphine 1 + 1",
      years("sthrbirdie") == 3 and years("sthrelias") == 2 and years("sthrseraphine") == 2,
      list({ years("sthrbirdie"), years("sthrelias"), years("sthrseraphine") }))
    check("Years pending go back to 0", pending("sthrbirdie") == 0 and pending("sthrelias") == 0)
    ctl("shBeginNextLoop")
    loopStart("districts")
    check("Begin Finale is available in the next loop", hasLabel(control(), "Begin Finale"))
    -- Loop Setup step 3 and the Hours the Control automates
    local s0 = st()
    ctl("shClickHour") ; ctl("shClickHour")
    check("The Thirteenth Toll: Hour III raises only the base 1", st().hour == 3 and st().dissonance == s0.dissonance + 1,
      list(st()))
    ctl("shClickHour")
    check("The Hour Was Wrong: the Hourglass steps from Hour III to Hour V; the Appointed Sensed",
      st().hour == 5 and st().stage >= 1, list(st()))
    ctl("shClickHour", true)
    check("...and rewinds from Hour V to Hour III", st().hour == 3, st().hour)
    times(6 - st().dissonance, function() ctl("shClickDissonance") end)
    check("Glitch band: 1 band Static token", st().static.baseline == 1 and st().static.target == 1, list(st().static))
    times(2, function() ctl("shClickHour") end)
    check("What the Almanac Hid: Hour VI leaves the bag 1 Static token short of its band (0)",
      st().hour == 6 and st().static.almanac == true and st().static.target == 0, list(st().static))
    local markVII = chatMark()
    ctl("shClickHour")
    check("The Appointed's Name: Hour VII tells the table to exhaust the Appointed", chatHas(markVII, "Exhaust the Appointed"))
    save("districts")
  end)

  step("district locations on the next loop's boxes (Part II)", function()
    restore("part2")
    ctl("shClearBoard")
    for _, id in ipairs({ "district_square", "district_church", "district_lighthouse", "district_almanac" }) do
      local box = find(function(o) local m = gm(o) return m.type == "ScenarioBox" and m.id == id end)
      if box then click(box, "Place") ; E.run(3) end
    end
    E.run(2)
    local function card(id) return find(function(o) return o.type == "Card" and gm(o).id == id end) end
    check("The Lamp Was Never Lit: the Lantern Room enters play calm side up (turned)",
      card("sthr-loc-lanternroom") ~= nil and card("sthr-loc-lanternroom").is_face_down == true)
    check("Part II with The Thirteenth Toll: the Flooded Crypt is open (act 2a current at Place)",
      card("sthr-loc-floodedcrypt") ~= nil and not hasLabel(card("sthr-loc-floodedcrypt"), "CLOSED"),
      labels(card("sthr-loc-floodedcrypt")))
    check("The Sealed Study is CLOSED (act 2a needs What the Almanac Hid and The Vote)",
      hasLabel(card("sthr-loc-sealedstudy"), "CLOSED"))
    local steps = card("sthr-loc-townhallsteps")
    local down0 = steps and steps.is_face_down
    logTick("k:the-sheriff-is-already-dead")
    E.run(1)
    check("The Sheriff Is Already Dead: the Town Hall Steps turn to their calm side",
      steps ~= nil and down0 == false and steps.is_face_down == true)
    logTick("k:the-vote-that-never-ends")
    logTick("k:what-the-almanac-hid")
    E.run(1)
    check("What the Almanac Hid in Part II with The Vote: act 2a current, the Sealed Study opens",
      not hasLabel(card("sthr-loc-sealedstudy"), "CLOSED"), labels(card("sthr-loc-sealedstudy")))
    ctl("shClearBoard")
  end)

  ------------------------------------------------------------ finale --

  step("the finale's campaign: Years by bracket, the entries, Begin Finale is a loop action", function()
    restore("part2")
    for _, k in ipairs({ "what-the-almanac-hid", "the-vote-that-never-ends", "the-appointeds-name",
                         "the-hour-was-wrong", "the-keepers-ninth-death" }) do
      logTick("k:" .. k)
    end
    logTick("vote_a") ; logTick("name_b") ; logTick("page_a") ; logTick("ninth_b")
    -- the acts' backs: The Vote marks the thread "suspected", The Name "known"
    logTick("sera_suspected") ; logTick("sera_known")
    check("Seraphine's thread boxes are one group: 'known' replaces 'suspected'",
      logVal("sera_known") == true and logVal("sera_suspected") ~= true)
    check("The Way the Night Breaks is assembled", hasLabel(control(), "Begin Finale"))
    logTick("k:the-way-the-night-breaks")
    -- Years for the brackets: Elias Ancient, Birdie Elder, Seraphine Prime
    addPending("sthrelias", 14) ; addPending("sthrbirdie", 11) ; addPending("sthrseraphine", 3)
    endLoop()
    check("Between Loops (after Reset Loop) there is no Begin Finale", not hasLabel(control(), "Begin Finale"),
      labels(control()))
    ctl("shCloseInterlude")
    check("...on the play panel either", not hasLabel(control(), "Begin Finale"), labels(control()))
    control().call("shApiSetFinale", { on = true })
    check("...and the Control refuses to begin one Between Loops", st().finale == false, list(st()))
    ctl("shOpenInterlude")
    -- the first time Weathered+ is reached: choose the locked changes first
    local i = slot.sthrbirdie
    ctl("shAgePhys" .. i) ; ctl("shAgeMent" .. i)
    for _, id in ipairs(PARTY) do age(id) end
    check("Elias 15 (Ancient), Birdie 12 (Elder), Seraphine 4 (Prime)", years("sthrelias") == 15
      and years("sthrbirdie") == 12 and years("sthrseraphine") == 4,
      list({ years("sthrelias"), years("sthrbirdie"), years("sthrseraphine") }))
    ctl("shBeginNextLoop")
    check("Elder and Ancient begin the loop with 1 Memory on their cards; Prime with none",
      onCard("sthrelias") == 1 and onCard("sthrbirdie") == 1 and onCard("sthrseraphine") == 0)
    logSync(1)
    local bi = invRow("Birdie")
    check("the log syncs Birdie's Years and her locked changes (-1 agility, +1 willpower)",
      bi ~= nil and logVal("inv" .. bi .. "_years") == 12 and logVal("inv" .. bi .. "_dagi") == true
      and logVal("inv" .. bi .. "_dwil") == true)
    check("Begin Finale is back in the new loop", hasLabel(control(), "Begin Finale"))
    save("finaleBase")
  end)

  step("a mis-ticked input of the assembled entry, unticked, takes The Way the Night Breaks with it", function()
    restore("finaleBase")
    local mark = chatMark()
    logTick("k:the-appointeds-name", false)
    check("unticking The Appointed's Name removes the finale", not hasLabel(control(), "Begin Finale")
      and chatHas(mark, "untick it on the Campaign Log too"), labels(control()))
    logTick("k:the-way-the-night-breaks", false)
    mark = chatMark()
    logTick("k:the-appointeds-name", true)
    check("ticking it again assembles it again", hasLabel(control(), "Begin Finale")
      and chatHas(mark, "Record The Way the Night Breaks"), labels(control()))
    logTick("k:the-way-the-night-breaks", true)
  end)

  --- The finale's Setup and the contest, as the guide has the table do them.
  local function beginFinale(opts)
    opts = opts or {}
    local mark = chatMark()
    if opts.atHourNine then
      times(8, function() ctl("shClickHour") end)
      check("Hour IX with The Way the Night Breaks: the Control offers the finale", chatHas(mark, "unless you begin the finale"))
      times(4, function() ctl("shClickHour", true) end)
      check("Setup 2: four right-clicks put Hour V back as the current Hour", st().hour == 5, st().hour)
    end
    for _ = 1, 3 do if st().stage < 3 then ctl("shClickAppointed") end end
    ctl("shBeginFinale")
    local s = st()
    check("Setup 2-3: the Appointed Arrived, Begin Finale shows Contest 0 / 5", s.finale and s.stage == 3
      and hasLabel(control(), "Contest 0 / 5"), list(s))
    if logVal("name_a") then
      ctl("shClickContest")
      check("You have spoken the name: 1 contest progress", hasLabel(control(), "Contest 1 / 5"), labels(control()))
    end
    if logVal("page_b") then
      local h = st().hour
      ctl("shClickHour", true)
      check("The drowned heard the true hour: the Hourglass rewinds 1 (stepping over Hour IV)",
        st().hour == (h == 5 and 3 or h - 1), h .. " -> " .. st().hour)
    end
  end
  local function reachContest()
    local mark = chatMark()
    for _ = 1, 20 do
      if hasLabel(control(), "Contest 5 / 5") then break end
      ctl("shClickContest")
    end
    check("the contest is reached at 5 (every player count)", chatHas(mark, "The contest is reached"))
    logTick("contest_yes") ; logType("finale_loop", tostring(st().loops + 1))
    logCount("finale_memory", st().memory)
  end
  local function setMemory(n)
    local m = st().memory
    times(math.abs(n - m), function() ctl("shClickMemory", n < m) end)
    check("banked Memory set to " .. n, st().memory == n, st().memory)
  end
  local ALL = { sthrelias = true, sthrseraphine = true, sthrbirdie = true }
  local function finaleRecord(res, howEnded)
    logTick(res:lower())
    logType("anchor", howEnded)
    check(res .. ": the Finale Record shows it", logVal(res:lower()) == true and logVal("anchor") == howEnded)
  end
  local function epilogueIs(res, f, want, wantThread)
    local lines, thread = ORACLE.epilogue(res, f)
    check(res .. ": epilogue lines " .. list(want), same(lines, want), list(lines))
    check(res .. ": Seraphine's thread line " .. tostring(wantThread), thread == wantThread, tostring(thread))
  end

  step("finale setup at Hour IX; name spoken, drowned heard; Hour IX ends the finale", function()
    restore("finaleBase")
    logTick("name_a") ; logTick("page_b")
    local d0 = st().dissonance
    beginFinale({ atHourNine = true })
    check("contest is reset to 1 by the spoken name, not carried", hasLabel(control(), "Contest 1 / 5"))
    local s0 = st()
    local mark = chatMark()
    local static0 = st().static.extra
    for _ = 1, 9 do if st().hour < 9 then ctl("shClickHour") end end
    local s = st()
    check("Hours VII and VIII resolve again: Hour VIII raises Dissonance by 2 again", s.dissonance >= s0.dissonance + 2,
      s0.dissonance .. " -> " .. s.dissonance)
    check("Hour VI does not stack", st().static.extra == static0, list(st().static))
    check("Hour IX in the finale: the finale ends and the contest is not reached",
      chatHas(mark, "the finale ends and the contest is not reached"))
    info("Dissonance over the setup: " .. d0 .. " -> " .. s.dissonance)
  end)

  step("finale R1 (Take Its Place): an Ancient investigator is kept as anchor", function()
    restore("finaleBase")
    beginFinale()
    reachContest()
    local opts = ORACLE.finale({ contest = true, present = ALL })
    check("oracle: R1 (Elias is Ancient), R3 (The Keeper's Ninth Death), R4", same(opts, { "R1", "R3", "R4" }), list(opts))
    finaleRecord("R1", "Elias Warde kept as anchor")
    logType("dead1_name", "Elias Warde") ; logTick("dead1_kept") ; logType("dead1_loop", "3")
    check("R1: Elias is on Those Who Left the Loop as kept as anchor", logVal("dead1_kept") == true
      and logVal("dead1_aged") ~= true)
    epilogueIs("R1", { present = ALL, anchor = "sthrelias" }, { sthrbirdie = "Elder", sthrseraphine = "Prime" }, "known")
  end)

  step("finale R1 with Who Walks Beside You: the anchor walks out (+3, or +1 with the walkers' ring)", function()
    for _, ring in ipairs({ "_a", "_b" }) do
      restore("finaleBase")
      logTick("k:who-walks-beside-you") ; logTick("ring" .. ring)
      beginFinale()
      reachContest()
      check("ring" .. ring .. ": oracle offers R1", ORACLE.finale({ contest = true, present = ALL })[1] == "R1")
      local add = ring == "_a" and 3 or 1
      addPending("sthrelias", add)
      finaleRecord("R1", "Elias walked out free")
      check("ring" .. ring .. ": +" .. add .. " Years pending on Elias's card", pending("sthrelias") == add)
      epilogueIs("R1", { present = ALL }, { sthrelias = "Ancient", sthrbirdie = "Elder", sthrseraphine = "Prime" }, "known")
      check("ring" .. ring .. ": " .. (15 + add) .. " Years is not aged out (finale Years never age out)",
        years("sthrelias") + pending("sthrelias") == 15 + add)
    end
  end)

  step("finale R1 through the ninth line: the signer, when present, even if no one is Ancient", function()
    restore("finaleBase")
    logTick("ninth_a") ; logType("ninth_signer", "Seraphine")
    beginFinale()
    reachContest()
    local noElias = { sthrseraphine = true, sthrbirdie = true }
    check("Elias defeated, Seraphine signed: R1 offered", ORACLE.finale({ contest = true, present = noElias })[1] == "R1")
    check("Elias and Seraphine defeated: no R1 (Birdie is only Elder)",
      ORACLE.finale({ contest = true, present = { sthrbirdie = true } })[1] ~= "R1")
    finaleRecord("R1", "Seraphine kept as anchor")
    epilogueIs("R1", { present = noElias, anchor = "sthrseraphine" }, { sthrbirdie = "Elder" }, nil)
  end)

  step("finale R1b (Let It In, On Your Terms): the ticket, and 4 (or 3) Memory per investigator", function()
    for _, v in ipairs({ { kept = false }, { kept = true } }) do
      restore("finaleBase")
      -- the Prologue's choice came from a different Prologue ending
      logTick(v.kept and "prologue_b" or "prologue_a")
      logTick("k:the-ticket-takers-bargain") ; logTick("ticket_a")
      beginFinale()
      reachContest()
      local need = v.kept and 9 or 12
      setMemory(need - 1)
      local o1 = ORACLE.finale({ contest = true, present = ALL })
      setMemory(need)
      local o2 = ORACLE.finale({ contest = true, present = ALL })
      local label = v.kept and "kept the night to yourselves" or "the town was warned"
      check(label .. ": R1b needs " .. need .. " banked (not " .. (need - 1) .. ")",
        not same(o1, o2) and o2[2] == "R1b", list(o1) .. " / " .. list(o2))
      -- the fare: banked Memory drops to 0, 2 Years each present investigator
      times(need + 1, function() ctl("shClickMemory", true) end)
      check(label .. ": right-clicking Memory takes it to 0 and never below", st().memory == 0, st().memory)
      for _, id in ipairs(PARTY) do addPending(id, 2) end
      finaleRecord("R1b", "the guest let in")
      logType("aged3", "2 each")
      epilogueIs("R1b", { present = ALL }, { sthrelias = "Ancient", sthrbirdie = "Elder", sthrseraphine = "Weathered" },
        "known")
    end
  end)

  step("finale R2 (Close the Door): the vote still stands; 3 Years, or 2 if the town was warned", function()
    for _, warned in ipairs({ true, false }) do
      restore("finaleBase")
      logTick(warned and "prologue_a" or "prologue_b")
      beginFinale()
      reachContest()
      check("the vote torn out: no R2", not has(ORACLE.finale({ contest = true, present = ALL }), "R2"))
      logTick("vote_b")
      check("the vote still stands: R2 offered", has(ORACLE.finale({ contest = true, present = ALL }), "R2"))
      local add = warned and 2 or 3
      for _, id in ipairs(PARTY) do addPending(id, add) end
      finaleRecord("R2", "the door closed")
      epilogueIs("R2", { present = ALL }, { sthrelias = "Ancient", sthrbirdie = add == 3 and "Ancient" or "Elder",
        sthrseraphine = "Weathered" }, "known")
    end
  end)

  step("finale R3 (Break Through): The Keeper's Ninth Death; the ninth line blank or signed", function()
    restore("finaleBase")
    beginFinale()
    reachContest()
    check("R3 offered with The Keeper's Ninth Death", ORACLE.finale({ contest = true, present = ALL })[2] == "R3")
    check("the log tells which last point to read (the ninth line was left blank)", logVal("ninth_b") == true)
    finaleRecord("R3", "broke through")
    epilogueIs("R3", { present = ALL }, { sthrelias = "Ancient", sthrbirdie = "Elder", sthrseraphine = "Prime" }, "known")
  end)

  step("finale R4 (Seal by Force): one ages out, or walks away 3 Years older if the vote was torn out", function()
    for _, torn in ipairs({ true, false }) do
      restore("finaleBase")
      if not torn then logTick("vote_b") end
      beginFinale()
      reachContest()
      check("R4 is always offered", has(ORACLE.finale({ contest = true, present = ALL }), "R4"))
      finaleRecord("R4", "Birdie held the door")
      local f = { present = ALL }
      if torn then
        addPending("sthrbirdie", 3)
        check("the vote torn out: Birdie +3 Years pending, not aged out", pending("sthrbirdie") == 3)
      else
        logType("dead1_name", "Birdie") ; logTick("dead1_aged") ; logTick("inv" .. (invRow("Birdie") or 3) .. "_agedout")
        f.agedOut = "sthrbirdie"
        check("the vote stands: Birdie ages out on the log", logVal("dead1_aged") == true and logVal("dead1_kept") ~= true)
      end
      epilogueIs("R4", f, torn and { sthrelias = "Ancient", sthrbirdie = "Ancient", sthrseraphine = "Prime" }
        or { sthrelias = "Ancient", sthrseraphine = "Prime" }, "known")
    end
  end)

  step("finale R5 (Next Time): contest not reached, 12+ banked; the loop ends; the finale again", function()
    restore("finaleBase")
    beginFinale()
    times(5, function() ctl("shClickContest") end)
    setMemory(12)
    local mark = chatMark()
    for _ = 1, 9 do if st().hour < 9 then ctl("shClickHour") end end
    check("Hour IX ends the finale", chatHas(mark, "the contest is not reached"))
    check("oracle: R5 with 12 banked", same(ORACLE.finale({ contest = false }), { "R5" }))
    logTick("contest_no") ; finaleRecord("R5", "next time") ; logClick("closed")
    check("R5: marked Closed at the Hour", logVal("closed") == 1)
    check("the epilogue is not read", ORACLE.epilogue("R5", { present = ALL }) == nil)
    local loops0 = st().loops
    endLoop()
    local s = st()
    check("Reset Loop ends the loop and the finale: contest cleared", s.loops == loops0 + 1 and not s.finale
      and s.loopEnded and not hasLabel(control(), "Contest"), list(s))
    local y0 = years("sthrelias")
    for _, id in ipairs(PARTY) do age(id) end
    check("R5 is a loop end: reset Years are gained", years("sthrelias") > y0, y0 .. " -> " .. years("sthrelias"))
    ctl("shBeginNextLoop")
    check("the next loop offers Begin Finale again", hasLabel(control(), "Begin Finale"), labels(control()))
    ctl("shBeginFinale")
    check("a second finale starts from Contest 0", st().finale and hasLabel(control(), "Contest 0 / 5"), labels(control()))
  end)

  step("finale R5/R6 by Dissonance and by defeat; R6 (The Loop Wins) below 12 banked", function()
    restore("finaleBase")
    beginFinale()
    local mark = chatMark()
    times(18 - st().dissonance, function() ctl("shClickDissonance") end)
    check("Dissonance at the reset value in the finale: the Control says the contest is not reached",
      chatHas(mark, "the finale ends and the contest is not reached"))
    setMemory(11)
    check("oracle: R6 with 11 banked (4 per investigator is 12)", same(ORACLE.finale({ contest = false }), { "R6" }))
    finaleRecord("R6", "the loop won")
    check("the epilogue is not read", ORACLE.epilogue("R6", { present = ALL }) == nil)
    -- on-card Memory does not count
    control().call("shApiOnCardMemory", { id = "sthrbirdie", delta = 5 })
    check("Memory on cards does not count toward R5/R1b (still R6)", same(ORACLE.finale({ contest = false }), { "R6" }))
  end)

  step("walker's ring: a Hold Back without a test pushes back and rewinds (contest +1 by hand)", function()
    restore("finaleBase")
    logTick("ring_a")
    beginFinale()
    local h = st().hour
    control().call("shApiHoldBack")
    ctl("shClickContest")
    check("Hold Back: Arrived -> Emerging, the Hourglass rewinds 1", st().stage == 2 and st().hour == math.max(1, h - 1),
      list(st()))
    check("contest +1 for the Hold Back success", hasLabel(control(), "Contest 1 / 5"), labels(control()))
  end)

  ------------------------------------------------------ epilogue inputs --

  step("epilogue inputs: brackets, aging out at 18, the log's aged-out box", function()
    restore("finaleBase")
    addPending("sthrelias", 2)            -- 15 + 1 + 2 = 18
    endLoop()
    local mark = chatMark()
    for _, id in ipairs(PARTY) do age(id) end
    check("Elias reaches 18 Years and ages out", years("sthrelias") == 18 and chatHas(mark, "aged out of the campaign"))
    check("brackets: 18 Ancient, 13 Elder, 5 Weathered",
      bracket(years("sthrelias")) == "Ancient" and bracket(years("sthrbirdie")) == "Elder"
      and bracket(years("sthrseraphine")) == "Weathered")
    local m0 = st().memory
    ctl("shBankOnCard")
    info("Bank on-card Memory after Elias aged out: " .. m0 .. " -> " .. st().memory
      .. " (the Control drops an aged-out investigator's on-card Memory; see the report)")
    ctl("shBeginNextLoop")
    check("an aged-out investigator begins no loop with Memory", onCard("sthrelias") == 0 and onCard("sthrbirdie") == 1)
    logSync(1)
    local ei = invRow("Elias")
    check("Sync from campaign ticks Elias's Aged out box", ei ~= nil and logVal("inv" .. ei .. "_agedout") == true)
    check("...and not the others'", logVal("inv" .. (ei == 1 and 2 or 1) .. "_agedout") ~= true)
  end)

  step("Seraphine's thread in every finale state", function()
    restore("finaleBase")
    logSync(2)
    check("the thread is marked by hand, so every state is reachable at the finale",
      logVal("sera_known") == true or logVal("sera_suspected") == true or logVal("sera_unheard") == true)
  end)
end
