-- The scenario boxes' Place and Recall, and what the Control token remembers about what they lay
-- out, on the emulated table (tests only; designer-facing, it names cards by id).
--
-- A box lays its objects out again every loop with the GUIDs they had before, so anything keyed by
-- GUID (SCED's Token Spawn Tracker, the Control's CLOSED labels) must not outlive the objects, and a
-- Place or a Clear Board that comes while another Place is running must not leave a half layout:
--
--   N-1  loop 2 spawns a location's clues again (the tracker forgets the GUIDs a Place lays out)
--   N-2  the CLOSED label is read off the card, so a new card gets it and Sync Board repairs it
--   N-4  Recall and Clear Board stop a Place that is still running; the next Place is not refused
--   N-5  Recall takes the tokens resting on the cards it removes, and nothing else
--   N-6  a save taken during a Place leaves no second, Place-able box behind
--   N-7  a box out of context is laid out all the same and the chat says so, once
--   G12  a Place is refused while another box's cards (or an older build's) lie where it lays out
--
-- tests/test_sced_place.py runs it on the SCED stand-in and, when SCED is available, on its real
-- table, with the Control and box scripts rebuilt from src/ (run.candidate_payload).

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
  local function click(o, which, alt)
    local ok, err = E.click(o, which, "White", alt)
    if not ok then check("button '" .. tostring(which) .. "' can be clicked", false, err) end
    return ok
  end
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function scenarioBox(id)
    return find(function(o)
      local m = gm(o)
      return m.type == "ScenarioBox" and m.id == id and not tostring(o.getName()):find("(placing)", 1, true)
    end)
  end
  local function looseCard(id) return find(function(o) return o.type == "Card" and gm(o).id == id end) end
  local function beginNextLoop()
    click(control(), "Begin Next Loop"); E.run(0.2)
    if st().mode ~= "play" then click(control(), "Begin Next Loop") end
  end
  -- Reset Loop (the first click only asks when the loop is not over by the Control's count)
  local function resetLoop()
    click(control(), "Reset Loop"); E.run(0.3)
    if not st().loopEnded then click(control(), "Reset Loop"); E.run(0.3) end
  end
  -- Reset Loop, Interlude, Begin Next Loop, Clear Board: the next loop's setup step 1
  local function nextLoop()
    resetLoop()
    click(control(), "Interlude"); beginNextLoop(); E.run(0.5)
    click(control(), "Clear Board"); E.run(0.5)
  end

  local function chatMark() return #E.log end
  local function chatSince(mark)
    local out = {}
    for i = mark + 1, #E.log do out[#out + 1] = tostring(E.log[i].msg) end
    return table.concat(out, " || ")
  end
  local function chatHas(mark, needle) return chatSince(mark):find(needle, 1, true) ~= nil end
  local function chatCount(mark, needle) return select(2, chatSince(mark):gsub(needle:gsub("%p", "%%%0"), "")) end

  -- objects (decks counted by their cards) that carry a tag
  local function counted(tag)
    local n = 0
    for _, o in ipairs(objects()) do
      if o.hasTag(tag) then n = n + (o.type == "Deck" and #o.getObjects() or 1) end
    end
    return n
  end
  local function boxCount(id) return counted("StillHourBox_" .. id) end
  local function loopCount() return counted("StillHourLoop") end
  local function strays()
    local n = 0
    for _, o in ipairs(objects()) do
      if tostring(o.getName()):find("(placing)", 1, true) then n = n + 1 end
    end
    return n
  end

  -- tokens (not SCED's own pieces) resting within a rectangle
  local function tokensIn(b)
    local n = 0
    for _, o in ipairs(objects()) do
      if (o.type == "Tile" or o.type == "Generic" or o.type == "Chip") and not H.scedGuids[o.getGUID()] then
        local p = o.getPosition()
        if p.x >= b.min.x and p.x <= b.max.x and p.z >= b.min.z and p.z <= b.max.z then n = n + 1 end
      end
    end
    return n
  end
  local function tokensOn(card) return tokensIn(E.aabb(card)) end

  -- what the Control remembers by GUID (Board.save: flipped / sealedMarked / appointed)
  local function board() return decode(control().call("shApiSnapshot")).board end

  local function tracker()
    local handler = E.byGuid("123456")
    return handler and handler.call("getObjectByOwnerAndType", { owner = "Mythos", type = "TokenSpawnTracker" })
  end
  local function trackerKnows(guid) return tracker().call("hasSpawnedTokens", guid) == true end
  -- the card is revealed: what SCED does when the investigators flip a location (the real SCED
  -- reacts to the flip itself; the stand-in only to this call, which the real one then ignores)
  local function reveal(card)
    E.playerFlip(card)
    E.runUntil(function() return tokensOn(card) > 0 end, 3)
    E.G.Global.call("callTable", { { "TokenManager", "spawnForCard" }, { card = card } }); E.run(0.3)
  end

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")

  -- Place a box and wait until it has finished laying out (and, when asked, until the Control token
  -- has synced the board to it). Returns the box and the chat mark from before the press.
  local function place(id, withSync)
    local box = scenarioBox(id)
    local mark = chatMark()
    click(box, "Place")
    E.runUntil(function() return not box.call("isPlacing") end, 12)
    if withSync then E.runUntil(function() return chatHas(mark, "Board synced.") end, 12) else E.run(0.3) end
    return box, mark
  end
  local function saw(mark, needle) return chatHas(mark, needle) end
  local function tail(mark) return chatSince(mark):sub(-400) end

  -- a box's remembered spots (its LuaScriptState), straight from the payload
  local function spotsOf(id)
    for _, sb in ipairs(payload.ObjectStates[1].ContainedObjects) do
      if (decode(sb.GMNotes) or {}).id == id then
        local out = {}
        for _, e in pairs(decode(sb.LuaScriptState).ml) do out[#out + 1] = e.pos end
        return out
      end
    end
  end

  ------------------------------------------------- setup: Part II loop 1 --

  step("setup: the campaign past its Prologue, in Part II, with the Study's first entry recorded", function()
    E.run(2); click(campaignBox, "Place"); E.run(4)
    click(control(), "Standard"); E.run(1)
    nextLoop()
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.loopsCompleted = 4; blob.campaign.partTwo = true
    blob.campaign.knowledge = { ["what-the-almanac-hid"] = true, ["the-thirteenth-toll"] = true }
    control().call("shApiRestore", { blob = J.encode(blob) }); E.run(1)
    check("the Prologue is over and the loop is under way", st().prologue == false and st().loopEnded == false)
  end)

  ----------------------------------------------------------- N-7 --

  step("N-7: a district with no Square on the table is out of context (a small box, an empty board)", function()
    local lighthouse, mark = place("district_lighthouse", true)
    check("it is laid out all the same", boxCount("district_lighthouse") > 0)
    check("the chat says nothing connects it to the Square yet, naming the box as printed on it",
      saw(mark, lighthouse.getName() .. " is laid out, but nothing on the table connects it to the Square yet."), tail(mark))
    check("...once", chatCount(mark, "is laid out, but") == 1, chatCount(mark, "is laid out, but"))
    click(lighthouse, "Recall"); E.run(0.3)
    check("Recall takes it away again", boxCount("district_lighthouse") == 0)
  end)

  ----------------------------------------------------------- N-1, N-2 --

  local rec = {}
  step("loop 1: the Square and the Almanac district; a revealed location spawns its clues; the closed one is labelled", function()
    local _, mark = place("district_square", true)
    place("district_almanac", true)
    local ro, well = looseCard("sthr-loc-recordsoffice"), looseCard("sthr-loc-well")
    check("the Records Office and the Well are laid out", ro ~= nil and well ~= nil)
    rec.roGuid, rec.wellGuid = ro.getGUID(), well.getGUID()
    reveal(ro); reveal(well)
    rec.roTokens, rec.wellTokens = tokensOn(ro), tokensOn(well)
    info(string.format("loop 1: tokens on the Records Office %d, the Well %d", rec.roTokens, rec.wellTokens))
    check("loop 1: the revealed locations spawned their tokens", rec.roTokens > 0 and rec.wellTokens > 0)
    check("SCED's Token Spawn Tracker remembers both cards", trackerKnows(rec.roGuid) and trackerKnows(rec.wellGuid))
    local study = looseCard("sthr-loc-sealedstudy")
    rec.studyGuid = study and study.getGUID()
    check("loop 1: the closed location carries the CLOSED label", study ~= nil and labels(study):find("CLOSED", 1, true) ~= nil, labels(study))
    check("the Control remembers it kept the closed location's clues back", board().sealedMarked[rec.studyGuid] == true)
    check("the box's chat and log name no card (the kind and the GUID only)", (function()
      local names, boxes = {}, {}
      for _, o in ipairs(objects()) do
        if o.type == "Card" and gm(o).type == "Location" then names[#names + 1] = o.getName() end
        if gm(o).type == "ScenarioBox" then boxes[#boxes + 1] = o.getName() end
      end
      for i = mark + 1, #E.log do
        local m = tostring(E.log[i].msg)
        if m:find("StillHour box", 1, true) or m:find("Placing ", 1, true) then
          for _, b in ipairs(boxes) do m = m:gsub(b:gsub("%p", "%%%0"), "") end   -- a box is named as printed on it
          for _, n in ipairs(names) do
            if n ~= "" and m:find(n, 1, true) then return false end
          end
        end
      end
      return #names > 0
    end)())
  end)

  step("loop 2: the same GUIDs again; the tracker forgets them before anything comes out; the clues and the label return", function()
    nextLoop()
    check("Clear Board left no loop object", loopCount() == 0, loopCount())
    check("...and the Control forgot what it remembered about the removed cards", board().sealedMarked[rec.studyGuid] == nil)
    local box = scenarioBox("district_square")
    click(box, "Place")
    -- before anything is taken out of the box the tracker has forgotten every GUID it is about to lay out
    check("pressing Place made the tracker forget the cards at once", not trackerKnows(rec.roGuid) and not trackerKnows(rec.wellGuid))
    check("...before the first object came out", loopCount() == 0, loopCount())
    E.runUntil(function() return not box.call("isPlacing") end, 12)
    place("district_almanac", true)
    local ro, well = looseCard("sthr-loc-recordsoffice"), looseCard("sthr-loc-well")
    check("the new cards carry the old GUIDs (a box keeps its objects' GUIDs)", ro ~= nil and well ~= nil
      and ro.getGUID() == rec.roGuid and well.getGUID() == rec.wellGuid)
    reveal(ro); reveal(well)
    local a, b = tokensOn(ro), tokensOn(well)
    info(string.format("loop 2: tokens on the Records Office %d, the Well %d", a, b))
    check("loop 2: revealing a location spawns its tokens again", a == rec.roTokens and b == rec.wellTokens, a .. "/" .. b)
    local study = looseCard("sthr-loc-sealedstudy")
    check("loop 2: the same GUID is laid out again", study ~= nil and study.getGUID() == rec.studyGuid)
    check("loop 2: the new card carries the CLOSED label", study ~= nil and labels(study):find("CLOSED", 1, true) ~= nil, labels(study))
  end)

  step("Sync Board repairs a lost CLOSED label and takes a stale one off an open location", function()
    local study = looseCard("sthr-loc-sealedstudy")
    study.clearButtons()
    check("(the label is gone, as after a save: buttons are not saved)", labels(study) == "")
    click(control(), "Sync Board"); E.run(2)
    check("Sync Board puts the CLOSED label back", labels(study):find("CLOSED", 1, true) ~= nil, labels(study))
    click(control(), "Sync Board"); E.run(2)
    check("...once", select(2, labels(study):gsub("CLOSED", "")) == 1, labels(study))
    local open = looseCard("sthr-loc-readingroom")
    open.createButton({ click_function = "shNoop", function_owner = control(), label = "CLOSED", position = { 0, 0.3, 0 },
      rotation = { 0, 0, 0 }, width = 0, height = 0, font_size = 260 })
    click(control(), "Sync Board"); E.run(2)
    check("an open location never keeps a CLOSED label", labels(open):find("CLOSED", 1, true) == nil, labels(open))
    check("(the Control remembers the closed location again)", board().sealedMarked[rec.studyGuid] == true)
    scenarioBox("district_almanac").call("buttonClick_recall"); E.run(0.5)
    check("Recall drops it too: the Control hears of every object destroyed", board().sealedMarked[rec.studyGuid] == nil)
  end)

  ----------------------------------------------------------- N-7, continued --

  step("N-7: with the Square laid out the Lighthouse needs the Road; a district beside the Square is in context", function()
    local lighthouse, mark = place("district_lighthouse", true)
    check("the Lighthouse without the Road is out of context",
      saw(mark, lighthouse.getName() .. " is laid out, but nothing on the table connects it to the Square yet."), tail(mark))
    click(lighthouse, "Recall"); E.run(0.3)
    place("district_road", false)
    lighthouse, mark = place("district_lighthouse", true)
    check("with the Road laid out the Lighthouse is in context", boxCount("district_lighthouse") > 0 and not saw(mark, "is laid out, but"), tail(mark))
    local _, mark2 = place("district_church", true)
    check("a district beside the Square is in context", boxCount("district_church") > 0 and not saw(mark2, "is laid out, but"), tail(mark2))
  end)

  step("N-7: the finale's box before it can begin; with its entry recorded the same Place says nothing", function()
    local finale, mark = place("finale", true)
    check("it is laid out all the same", boxCount("finale") > 0)
    check("the chat says it is not its time yet, naming the box as printed on it",
      saw(mark, finale.getName() .. " is laid out, but it is not its time yet."), tail(mark))
    click(finale, "Recall"); E.run(0.3)
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.knowledge["the-way-the-night-breaks"] = true
    control().call("shApiRestore", { blob = J.encode(blob) }); E.run(1)
    local _, mark2 = place("finale", true)
    check("with its entry recorded nothing is said", boxCount("finale") > 0 and not saw(mark2, "is laid out, but"), tail(mark2))
    check("...and no box of this loop was refused for another box's cards", not saw(mark, "cards from a box laid out earlier"))
    scenarioBox("finale").call("buttonClick_recall"); E.run(0.3)
  end)

  ----------------------------------------------------------- N-4 --

  step("N-4: Recall stops a Place that is still running", function()
    local box = scenarioBox("district_fairground")
    click(box, "Place"); E.run(0.2)
    check("a Place is running (some of the box is out, not all)", boxCount("district_fairground") > 0 and box.call("isPlacing") == true)
    local out = boxCount("district_fairground")
    local mark = chatMark()
    click(box, "Recall"); E.run(0.1)
    check("Recall says the Place was stopped", saw(mark, "the Place in progress was stopped"), tail(mark))
    E.run(3)
    check("nothing more arrived and nothing is left", boxCount("district_fairground") == 0 and strays() == 0,
      boxCount("district_fairground") .. " / " .. strays() .. " (" .. out .. " were out)")
    mark = chatMark()
    click(box, "Place"); E.runUntil(function() return not box.call("isPlacing") end, 8)
    check("the next Place is not refused", not saw(mark, "already laid out") and boxCount("district_fairground") > 0)
    local full = boxCount("district_fairground")
    mark = chatMark()
    click(box, "Recall"); E.run(0.3)
    check("a Recall with no Place running does not say it stopped one", not saw(mark, "stopped"))
    check("...and removes the whole box", boxCount("district_fairground") == 0)
    click(box, "Place"); E.runUntil(function() return not box.call("isPlacing") end, 8)
    check("a Place after that lays out the same box again", boxCount("district_fairground") == full, boxCount("district_fairground") .. " vs " .. full)
    click(box, "Recall"); E.run(0.3)
  end)

  step("N-4: Clear Board stops a Place that is still running", function()
    local box = scenarioBox("district_fairground")
    local others = loopCount()
    click(box, "Place"); E.run(0.2)
    check("a Place is running", loopCount() > others)
    local mark = chatMark()
    click(control(), "Clear Board"); E.run(0.1)
    check("Clear Board says the Place was stopped", saw(mark, "A Place that was still running was stopped."), tail(mark))
    E.run(3)
    check("nothing more arrived and nothing is left", loopCount() == 0 and strays() == 0, loopCount() .. " / " .. strays())
    mark = chatMark()
    click(box, "Place"); E.runUntil(function() return not box.call("isPlacing") end, 8)
    check("the next Place is not refused", not saw(mark, "already laid out") and boxCount("district_fairground") > 0)
    mark = chatMark()
    click(control(), "Clear Board"); E.run(0.3)
    check("a Clear Board with no Place running does not say it stopped one", not saw(mark, "stopped"))
  end)

  ----------------------------------------------------------- N-5 --

  step("N-5: Recall takes the tokens resting on the cards it removes, and only those", function()
    local road = place("district_road", false)
    local card = looseCard("sthr-loc-milestones")
    local b = E.aabb(card)
    reveal(card)
    check("the revealed card has tokens on it", tokensOn(card) > 0, tokensOn(card))
    local mine = {}
    for _, o in ipairs(objects()) do if H.scedGuids[o.getGUID()] then mine[#mine + 1] = o end end
    -- a token that is somebody else's: not on any card of this box
    local far = E.spawnData({ Name = "Custom_Token", Nickname = "Marker", Tags = { "MyMarker" },
      Transform = { posX = b.max.x + 6, posY = 1.6, posZ = b.max.z + 6, scaleX = 0.3, scaleY = 0.3, scaleZ = 0.3 } }, {}, "table")
    E.run(0.5)
    road.call("buttonClick_recall"); E.run(0.5)
    check("the tokens that rested on the removed card went with it", tokensIn(b) == 0, tokensIn(b))
    check("the token that was not on one of its cards stays", far ~= nil and not far.isDestroyed())
    local lost = 0
    for _, o in ipairs(mine) do if o.isDestroyed() then lost = lost + 1 end end
    check("SCED's own table objects are untouched", lost == 0, lost)
    far.destruct(); E.run(0.3)
  end)

  ----------------------------------------------------------- N-6 --

  step("N-6: a save taken during a Place leaves no second box behind", function()
    local box = scenarioBox("district_road")
    click(box, "Place"); E.run(0.3)
    check("a working copy is on the table", strays() == 1, strays())
    local saved = E.save()
    E.clearWorld(); E.loadSave(saved, "saved"); E.run(3)
    check("after the load no working copy is left", strays() == 0, strays())
    local boxes = 0
    for _, o in ipairs(objects()) do
      local m = gm(o)
      if m.type == "ScenarioBox" and m.id == "district_road" then boxes = boxes + 1 end
    end
    check("the box itself is still there, once", boxes == 1, boxes)
    box = scenarioBox("district_road")
    box.call("buttonClick_recall"); E.run(0.5)
    click(box, "Place"); E.runUntil(function() return not box.call("isPlacing") end, 8)
    check("it lays the box out after the load", boxCount("district_road") > 0 and strays() == 0)
    click(control(), "Clear Board"); E.run(0.5)
  end)

  ----------------------------------------------------------- G12 --

  step("G12: the Prologue's cards on the mythos mat refuse the Square's Place until Clear Board", function()
    local prologue, mark = place("prologue", true)
    local prologueCount = boxCount("prologue")
    check("the Prologue's box is laid out", prologueCount > 0)
    check("the chat says the Prologue is over, naming the box as printed on it, once",
      saw(mark, prologue.getName() .. " is laid out, but the Prologue is already over.") and chatCount(mark, "the Prologue is already over") == 1, tail(mark))
    local square = scenarioBox("district_square")
    mark = chatMark()
    local n = square.call("buttonClick_place"); E.run(0.5)
    check("the Square's Place is refused", n == 0 and boxCount("district_square") == 0, tostring(n) .. " / " .. boxCount("district_square"))
    check("it says to click Clear Board first, naming the box as printed on it",
      saw(mark, square.getName() .. ": cards from a box laid out earlier are still on the table where this one lays out."
        .. " Click Clear Board on the Control token first."), tail(mark))
    check("the Prologue's cards were not touched", boxCount("prologue") == prologueCount)
    click(control(), "Clear Board"); E.run(0.5)
    click(square, "Place"); E.run(0.3)
    check("after Clear Board the Square's Place starts", square.call("isPlacing") == true and boxCount("district_square") > 0)
    square.call("buttonClick_recall"); E.run(0.3)
  end)

  step("G12: a leftover that carries only the loop tag, or the old build's box tag, refuses a Place on its spot", function()
    local church = scenarioBox("district_church")
    local spot = spotsOf("district_church")[1]
    for _, tags in ipairs({ { "StillHourLoop" }, { "StillHourLoop", "StillHourBox:3c5e1a" }, { "StillHourBox:3c5e1a" } }) do
      local old = E.spawnData({ Name = "Custom_Tile", Nickname = "leftover", Tags = tags,
        Transform = { posX = spot.x + 0.1, posY = 1.6, posZ = spot.z - 0.1 } }, {}, "table")
      E.run(0.3)
      local mark = chatMark()
      local n = church.call("buttonClick_place"); E.run(0.3)
      check("an object tagged " .. table.concat(tags, " + ") .. " on one of its spots refuses the Place",
        n == 0 and boxCount("district_church") == 0 and saw(mark, "Click Clear Board on the Control token first."), tail(mark))
      old.destruct(); E.run(0.3)
    end
    local mark = chatMark()
    church.call("buttonClick_place")
    E.runUntil(function() return not church.call("isPlacing") end, 8)
    check("with the leftover gone the same Place lays the box out", boxCount("district_church") > 0 and not saw(mark, "Clear Board"))
    church.call("buttonClick_recall"); E.run(0.3)
  end)
end
