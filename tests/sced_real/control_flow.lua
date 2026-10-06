-- The Control token's flow on the emulated SCED table (tests only; designer-facing,
-- so it names the campaign's entries freely). tests/test_sced_control_flow.py
-- runs it on a Saved Object built from src/ (run.candidate_payload).
--
-- The stub-TTS suite (tests/control_flow.lua) drives the Control alone; what needs
-- the real table's objects is played here: SCED's investigator counter and chaos
-- bag, the campaign log with its pages (TTS States) and its memo, the campaign
-- box's Place, and a scenario box laid out mid-loop.
--
--   * G8   SCED's investigator counter follows the Control's
--   * G20  the Control token is locked once Place has laid it out
--   * F-03 a page turn, then the Control token replaced (LOADING.md "Updating")
--   * F-04 the first chaos-bag change after a load
--   * F-05 the Almanac House Placed mid-loop with both entries recorded
--   * F-09 a Victory box un-ticked on the log
--   * F-11 two campaign logs; the spare one deleted

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local J = E.J
  local sced = H.mode == "sced"

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
  local function findAll(pred)
    local l = {}
    for _, o in ipairs(objects()) do if pred(o) then l[#l + 1] = o end end
    return l
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
  local function click(o, which, alt)
    local ok, err = E.click(o, which, "White", alt)
    if not ok then H.info("CLICK FAILED: " .. tostring(which) .. " " .. tostring(err)) end
    return ok
  end
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function logs() return findAll(function(o) return o.hasTag("CampaignLog") end) end
  local function logObj() return find(function(o) return o.hasTag("CampaignLog") end) end
  local function chatMark() return #E.log end
  local function chat(from)
    local out = {}
    for i = (from or 0) + 1, #E.log do out[#out + 1] = tostring(E.log[i].msg) end
    return table.concat(out, " || ")
  end
  local function scenarioBox(id) return find(function(o) local m = gm(o) return m.type == "ScenarioBox" and m.id == id end) end
  local function looseCard(id) return find(function(o) return o.type == "Card" and gm(o).id == id end) end
  local function tokensOn(card)
    local b = E.aabb(card)
    local n = 0
    for _, o in ipairs(objects()) do
      if (o.type == "Tile" or o.type == "Generic" or o.type == "Chip") and not H.scedGuids[o.getGUID()] then
        local p = o.getPosition()
        if p.x >= b.min.x and p.x <= b.max.x and p.z >= b.min.z and p.z <= b.max.z then n = n + 1 end
      end
    end
    return n
  end
  local function logPage(n)
    for _ = 1, 4 do
      local log = logObj()
      local v = log and log.call("getLogValues")
      if v and v.page == n then return log end
      E.menu(log, "Next page")
      E.run(1)
    end
    return nil
  end
  --- tick (or clear) a box on a log page, as the owner does
  local function tickLog(key, page)
    local log = logPage(page or 2)
    for i, f in ipairs(log.getVar("FIELDS") or {}) do
      if f.k == key then return click(log, "sthrLog_" .. i) end
    end
    check("the log has a box " .. key, false)
  end
  local function logValue(key, page)
    local log = logPage(page or 2)
    return log.call("getLogValues").values[key]
  end
  local function beginNextLoop()
    click(control(), "Begin Next Loop") ; E.run(0.2)
    if st().mode ~= "play" or st().loopEnded then click(control(), "Begin Next Loop") ; E.run(0.2) end
  end
  --- Reset Loop asks once when the night is not over by the Control's count; the second click ends it
  local function resetLoop()
    click(control(), "Reset Loop") ; E.run(0.2)
    if not st().loopEnded then click(control(), "Reset Loop") ; E.run(0.2) end
  end

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local box = payload.ObjectStates[1]

  --- The published file is built before the pipeline's Place keeps a saved-locked object locked
  -- (table_presence.ml_entry lock=Locked): write what the next publish will, so this suite plays it.
  local function emulateNextPublish(d)
    local state = decode(d.LuaScriptState)
    for _, c in ipairs(d.ContainedObjects or {}) do
      local e = state and state.ml and state.ml[c.GUID]
      if e then e.lock = c.Locked == true end
    end
    d.LuaScriptState = J.encode(state)
    return d
  end

  local bare = E.save()
  local function freshTable()
    E.clearWorld()
    E.loadSave(bare, "sced")
    E.run(2)
  end
  --- a new table with the campaign Placed
  local function newCampaign()
    freshTable()
    local d = emulateNextPublish(decode(J.encode(box)))
    local campaignBox = E.spawnData(d, {}, "campaign")
    E.run(2)
    click(campaignBox, "Place") ; E.run(4)
    return campaignBox
  end
  --- Loop 1 under way: Standard bag, the Prologue ended
  local function inLoopOne()
    local campaignBox = newCampaign()
    click(control(), "Standard") ; E.run(3)
    resetLoop() ; click(control(), "Interlude") ; beginNextLoop() ; E.run(1)
    return campaignBox
  end
  --- take the object with a tag (and, when given, a name fragment) out of a box
  local function takeTagged(container, tag, fragment, pos)
    local guid
    for _, e in ipairs(container.getObjects()) do
      for _, t in ipairs(e.tags or {}) do
        if t == tag and (fragment == nil or tostring(e.name):find(fragment, 1, true)) then guid = e.guid end
      end
    end
    if not guid then return nil end
    local o = container.takeObject({ guid = guid, position = pos or { 12, 3, 12 }, smooth = false })
    E.run(4)
    return o
  end
  --- LOADING.md "Updating": delete the old Control, spawn the new box (no Place), drag its Control out,
  -- delete the spare box. Returns the new Control's state and what the table was told.
  local function replaceControl()
    local m = chatMark()
    control().destruct() ; E.run(1)
    local box2 = E.spawnData(decode(J.encode(box)), {}, "campaign2")
    E.run(2)
    takeTagged(box2, "StillHour", "Control")
    local said = chat(m)
    local s = control() and st() or {}
    box2.destruct() ; E.run(1)
    return s, said
  end

  ------------------------------------------------------------ G8, G20 --

  step("G8, G20: SCED's investigator counter follows the Control's; the Control is locked after Place", function()
    newCampaign()
    check("the Control token is on the table", control() ~= nil)
    check("Place leaves the Control token locked (its own Locked flag)", control() ~= nil and control().getLock() == true)
    local log = logObj()
    check("...and the campaign log free, as in the official boxes", log ~= nil and log.getLock() == false)
    E.run(2)
    local counter = E.byGuid("f182ee")
    check("SCED's investigator counter is on the table", counter ~= nil)
    if not counter then return end
    check("it takes the Control's party size (" .. st().investigators .. ")", counter.getVar("val") == st().investigators,
      tostring(counter.getVar("val")))
    click(control(), "Investigators", true) ; E.run(0.5)
    check("Investigators -1 sets it", counter.getVar("val") == 2 and st().investigators == 2, tostring(counter.getVar("val")))
    click(control(), "Investigators", true) ; click(control(), "Investigators", true) ; E.run(0.5)
    check("it stops at 1 with the Control", counter.getVar("val") == 1 and st().investigators == 1, tostring(counter.getVar("val")))
    for _ = 1, 4 do click(control(), "Investigators") end
    E.run(0.5)
    check("+4 stops at 4 with the Control", counter.getVar("val") == 4 and st().investigators == 4, tostring(counter.getVar("val")))
    click(control(), "Investigators", true) ; E.run(0.5)
    check("4 -1 is 3 on both", counter.getVar("val") == 3 and st().investigators == 3)
    -- a campaign saved with 2 investigators, on a table whose counter says 4, loads with the Control's number
    click(control(), "Investigators", true) ; E.run(0.5)
    counter.call("updateVal", 4)
    local saved = E.save()
    E.clearWorld() ; E.loadSave(saved, "saved") ; E.run(6)
    local c2 = E.byGuid("f182ee")
    check("a loaded campaign sets SCED's counter to its own party size (2)", c2 ~= nil and control() ~= nil
      and st().investigators == 2 and c2.getVar("val") == 2, c2 and tostring(c2.getVar("val")))
  end)

  --------------------------------------------------------------- F-03 --

  step("F-03: the log turned to another page, then the Control replaced", function()
    inLoopOne()
    for _ = 1, 4 do click(control(), "Memory") end
    local before = st()
    local memoA = logObj().memo
    check("loop 1 is under way with 4 Memory", before.loops == 0 and before.prologue == false and before.memory == 4, J.encode(before))
    -- 1. the page the mirror was written to
    local s, said = replaceControl()
    check("replaced with the log on page 1: the state is back", s.memory == before.memory and s.prologue == false and s.hour == before.hour,
      J.encode(s) .. " | " .. said:sub(1, 160))
    -- 2. turn to page 3 first: the page now on show is given the Control's copy
    E.menu(logObj(), "Next page") ; E.run(1) ; E.menu(logObj(), "Next page") ; E.run(1)
    local shown = decode(logObj().memo)
    check("the page turned to carries the Control's current copy at once", shown ~= nil and type(shown.stillHour) == "string"
      and shown.seq == control().call("shApiLogMirror").seq and decode(shown.stillHour).campaign.bankedMemory == 4,
      logObj().memo and logObj().memo:sub(1, 80) or "no memo")
    s, said = replaceControl()
    check("replaced with the log on page 3: the state is back", s.memory == before.memory and s.prologue == false and s.hour == before.hour,
      J.encode(s) .. " | " .. said:sub(1, 160))
    -- 3. the same without that copy: the new Control looks at every page
    logObj().memo = ""
    s, said = replaceControl()
    check("a blank page on show: the copy on another page is found", s.memory == before.memory and s.prologue == false,
      J.encode(s) .. " | " .. said:sub(1, 160))
    -- 4. an older copy on the page on show, the newest on another page
    click(control(), "Memory") ; click(control(), "Memory") ; E.run(1)        -- the copy on page 3 is now newest
    local newest = st()
    logPage(1)
    logObj().memo = memoA                                                      -- page 1 holds the loop's first copy
    s, said = replaceControl()
    check("a stale copy on the page on show is not adopted (Memory " .. newest.memory .. ", not " .. before.memory .. ")",
      s.memory == newest.memory, J.encode(s) .. " | " .. said:sub(1, 160))
    -- 5. a click after the page turn keeps the newest copy on the page on show
    E.menu(logObj(), "Next page") ; E.run(1)
    click(control(), "Memory") ; E.run(1)
    check("the copy follows the Control's changes on the page on show", decode(logObj().memo).seq == control().call("shApiLogMirror").seq)
  end)

  --------------------------------------------------------------- F-04 --

  step("F-04: the first change to the chaos bag after a load is applied", function()
    newCampaign()
    click(control(), "Standard") ; E.run(3)
    -- loops completed = 2: Part II begins at the end of loop 3
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.prologue = false
    blob.campaign.loopsCompleted = 2
    control().call("shApiRestore", { blob = J.encode(blob) })
    E.run(2)
    local saved = E.save()
    E.clearWorld() ; E.loadSave(saved, "saved") ; E.run(6)
    check("the Control is back with loops = 2", control() ~= nil and st().loops == 2, control() and J.encode(st()))
    local m = chatMark()
    resetLoop()
    E.run(5)
    check("Part II began", st().partTwo == true)
    check("the table is told to add a Tablet to the chaos bag", chat(m):find("Campaign chaos-bag change", 1, true) ~= nil, chat(m):sub(1, 200))
    if sced then
      local bag = E.Global.call("getChaosBagState") or {}
      local tablets = 0
      for _, x in ipairs(bag) do if x == "tablet" then tablets = tablets + 1 end end
      check("SCED's chaos bag holds the Part II Tablet (18 tokens, 2 tablets)", #bag == 18 and tablets == 2, #bag .. " tokens, " .. tablets .. " tablets")
    end
  end)

  --------------------------------------------------------------- F-05 --

  step("F-05: the Almanac House Placed after the Vote was recorded, in Part II", function()
    inLoopOne()
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.loopsCompleted = 4 ; blob.campaign.partTwo = true
    blob.campaign.knowledge = { ["what-the-almanac-hid"] = true, ["the-sheriff-is-already-dead"] = true }
    control().call("shApiRestore", { blob = J.encode(blob) }) ; E.run(2)
    click(control(), "Clear Board") ; E.run(1)
    click(scenarioBox("district_square"), "Place") ; E.run(6)
    check("Part II, the Vote not recorded", st().partTwo == true and not (decode(control().call("shApiSnapshot")).campaign.knowledge["the-vote-that-never-ends"]))
    tickLog("k:the-vote-that-never-ends") ; E.run(2)
    click(scenarioBox("district_almanac"), "Place") ; E.run(6) ; E.run(3)
    local study = looseCard("sthr-loc-sealedstudy")
    check("the Sealed Study is on the table", study ~= nil)
    local lab = study and labels(study) or ""
    check("act 2a is current at Place: the Control does not label it CLOSED", study ~= nil and not lab:find("CLOSED", 1, true), "label: '" .. lab .. "'")
    if study then
      E.playerFlip(study) ; E.run(3)
      check("flipping the Sealed Study spawns its clues", tokensOn(study) > 0, tokensOn(study) .. " token(s)")
    end
    -- the same Place with the Vote unknown leaves it closed
    click(control(), "Clear Board") ; E.run(1)
    local b2 = decode(control().call("shApiSnapshot"))
    b2.campaign.knowledge["the-vote-that-never-ends"] = nil
    b2.campaign.oncePerLoopFlags = {}
    control().call("shApiRestore", { blob = J.encode(b2) }) ; E.run(1)
    click(scenarioBox("district_square"), "Place") ; E.run(6)
    click(scenarioBox("district_almanac"), "Place") ; E.run(6) ; E.run(3)
    local study2 = looseCard("sthr-loc-sealedstudy")
    check("without the Vote the Almanac House's Study is CLOSED", study2 ~= nil and labels(study2):find("CLOSED", 1, true) ~= nil,
      study2 and labels(study2) or "no card")
  end)

  --------------------------------------------------------------- F-09 --

  step("F-09: a Victory box un-ticked on the log refunds what it paid", function()
    inLoopOne()
    local m0 = st().memory
    local n = st().investigators
    tickLog("v:sthr-bellringer") ; E.run(1)
    check("ticking the Victory pays 2 per investigator and ticks its banked box", st().memory == m0 + 2 * n and logValue("vb:sthr-bellringer") == true,
      st().memory .. " vs " .. (m0 + 2 * n))
    local m = chatMark()
    tickLog("v:sthr-bellringer") ; E.run(1)
    check("clearing the box takes it back", st().memory == m0 and logValue("v:sthr-bellringer") ~= true and logValue("vb:sthr-bellringer") ~= true,
      st().memory .. " vs " .. m0)
    check("...and says so", chat(m):find("Victory removed: -" .. 2 * n .. " banked Memory", 1, true) ~= nil, chat(m):sub(1, 200))
    tickLog("v:sthr-bellringer") ; E.run(1)
    check("ticking it again pays once", st().memory == m0 + 2 * n, st().memory)
  end)

  --------------------------------------------------------------- F-11 --

  step("F-11: two campaign logs; the spare one deleted", function()
    inLoopOne()
    for _ = 1, 5 do click(control(), "Memory") end
    local before = st()
    local oldLog = logObj()
    local seqBefore = decode(oldLog.memo).seq
    -- the Control is replaced, and a second log has come out of a second box beforehand
    control().destruct() ; E.run(1)
    local box3 = E.spawnData(decode(J.encode(box)), {}, "campaign3")
    E.run(2)
    local spare = takeTagged(box3, "CampaignLog", nil, { 14, 3, 14 })
    box3.destruct() ; E.run(1)
    check("two campaign logs are on the table", #logs() == 2 and spare ~= nil, #logs())
    local m = chatMark()
    local box2 = E.spawnData(decode(J.encode(box)), {}, "campaign2")
    E.run(2)
    takeTagged(box2, "StillHour", "Control")
    box2.destruct() ; E.run(1)
    check("a Control exists", control() ~= nil)
    local s1 = control() and st() or {}
    check("with two logs it starts a new campaign, and says why (one sentence)",
      s1.prologue == true and s1.memory == 0 and chat(m):find("More than one Campaign Log is on the table", 1, true) ~= nil,
      J.encode(s1) .. " | " .. chat(m):sub(1, 240))
    check("the old log keeps its copy while there are two", decode(oldLog.memo).seq == seqBefore)
    m = chatMark()
    spare.destruct() ; E.run(2)
    check("the spare log is gone", #logs() == 1, #logs())
    local s2 = st()
    check("the Control adopts the campaign the other log holds", s2.memory == before.memory and s2.prologue == false and s2.hour == before.hour,
      J.encode(s2) .. " | " .. chat(m):sub(1, 200))
    check("...and says it was restored", chat(m):find("restored from the campaign log", 1, true) ~= nil, chat(m):sub(1, 200))
    click(control(), "Memory") ; E.run(1)
    check("it keeps that log's copy up to date from then on", decode(logObj().memo).seq > seqBefore)
  end)

  step("F-03: a Control that starts blank beside a log with entries says so", function()
    newCampaign()
    control().destruct() ; E.run(1)
    tickLog("k:the-lamp-was-never-lit") ; E.run(1)       -- ticked while no Control is on the table: nothing reaches it
    local box2 = E.spawnData(decode(J.encode(box)), {}, "campaign4")
    E.run(2)
    local m = chatMark()
    takeTagged(box2, "StillHour", "Control")
    local said = chat(m)
    check("the new Control begins a new campaign (the log's copy is the first state, no newer than its own)", control() ~= nil
      and st().prologue == true, control() and J.encode(st()))
    check("it says the Campaign Log has entries but it found no saved campaign",
      said:find("The Campaign Log has entries, but no saved campaign was found for this Control token", 1, true) ~= nil, said:sub(1, 300))
  end)
end
