-- The scenario boxes' Place (SCED's own MemoryBag script) and the Control token's Clear Board, and
-- what the Control remembers about what they lay out, on the emulated table (tests only;
-- designer-facing, it names cards by id).
--
-- SCED's Place takes a box's objects out onto their spots and leaves the box empty. Clear Board takes
-- the scenario cards off the table and puts a full box back from the Spare Scenario Boxes bag, with the
-- same GUIDs, so anything keyed by GUID (SCED's Token Spawn Tracker, the Control's CLOSED labels) must
-- not outlive the objects:
--
--   N-1  loop 2 spawns a location's clues again (Clear Board makes the tracker forget the box's GUIDs)
--   N-2  the CLOSED label is read off the card, so a new card gets it and Sync Board repairs it
--   R-1  SCED's Recall puts a box's objects back; Clear Board refills a used box; Place lays it out again
--   N-5  Clear Board takes the tokens resting on the cards it removes, and nothing else
--   N-9  the delayed sweep after a Clear Board never takes the clues of a location laid on the same spot
--   N-8  a clue beside a removed card, or one SCED spawns just after it left, is taken too
--   N-6  a save and load keeps the spares: a box used before the save is refilled after it
--   N-7  a box out of context is laid out all the same and the chat says so, once
--   A-1  shared spots: a district's act deck yields the Act slot, the finale's act takes it
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
      return m.type == "ScenarioBox" and m.id == id
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
  -- how many objects a box holds against how many its Place lays out
  local function fullness(id)
    local box = scenarioBox(id)
    if not box then return -1, -1 end
    local ml = (decode(box.script_state) or {}).ml or {}
    local n = 0
    for _ in pairs(ml) do n = n + 1 end
    return #box.getObjects(), n
  end
  local function isFull(id)
    local have, want = fullness(id)
    return want > 0 and have == want
  end
  local function clearBoard()
    click(control(), "Clear Board"); E.run(0.5)
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
    local function busy() return control().call("shApiBoxBusy") == true end
    E.runUntil(function() return not busy() end, 15)      -- an earlier box's board sync is over first
    mark = chatMark()
    click(box, "Place")
    E.run(0.5)                                  -- SCED's Place is one frame; the Control settles shared spots
    if withSync then E.runUntil(function() return not busy() end, 15) else E.run(0.3) end
    return box, mark
  end
  local function saw(mark, needle) return chatHas(mark, needle) end
  local function tail(mark) return chatSince(mark):sub(-400) end

  -- a box's remembered spots (its LuaScriptState), straight from the payload
  local function spotsOf(id)
    for _, sb in ipairs(payload.ObjectStates[1].ContainedObjects) do
      if (decode(sb.GMNotes) or {}).id == id then
        local out = {}
        -- an entry with a fallback (a district's act deck) never refuses a Place: it moves to the fallback
        for _, e in pairs(decode(sb.LuaScriptState).ml) do if not e.alt then out[#out + 1] = e.pos end end
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
    check("the box is empty after its Place, as every SCED box is", not isFull("district_lighthouse")
      and select(1, fullness("district_lighthouse")) == 0)
    clearBoard()
    check("Clear Board takes it away again", boxCount("district_lighthouse") == 0)
    check("...and puts a full box back", isFull("district_lighthouse"), table.concat({ fullness("district_lighthouse") }, "/"))
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
    check("...and both boxes are full again", isFull("district_square") and isFull("district_almanac"))
    -- before anything is laid out again the tracker has forgotten every GUID the boxes hold
    check("Clear Board made the tracker forget the cards", not trackerKnows(rec.roGuid) and not trackerKnows(rec.wellGuid))
    place("district_square", true)
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
    check("SCED's Recall puts the closed location back into its box", looseCard("sthr-loc-sealedstudy") == nil)
    check("...and the Control forgets what it remembered about it", board().sealedMarked[rec.studyGuid] == nil)
    clearBoard()
  end)

  ----------------------------------------------------------- N-7, continued --

  step("N-7: with the Square laid out the Lighthouse needs the Road; a district beside the Square is in context", function()
    local lighthouse, mark = place("district_lighthouse", true)
    check("the Lighthouse without the Road is out of context",
      saw(mark, lighthouse.getName() .. " is laid out, but nothing on the table connects it to the Square yet."), tail(mark))
    clearBoard()
    place("district_square", false)
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
    clearBoard()
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.knowledge["the-way-the-night-breaks"] = true
    control().call("shApiRestore", { blob = J.encode(blob) }); E.run(1)
    local _, mark2 = place("finale", true)
    check("with its entry recorded nothing is said", boxCount("finale") > 0 and not saw(mark2, "is laid out, but"), tail(mark2))
    clearBoard()
  end)

  ----------------------------------------------------------- R-1 --

  step("R-1: SCED's Recall puts a box back together; Clear Board refills a used box; Place lays out the same again", function()
    clearBoard()
    check("(the box is full)", isFull("district_fairground"), table.concat({ fullness("district_fairground") }, "/"))
    place("district_fairground", false)
    local full = boxCount("district_fairground")
    check("its Place lays everything out and empties it", full > 0 and select(1, fullness("district_fairground")) == 0)
    scenarioBox("district_fairground").call("buttonClick_recall"); E.run(0.5)
    check("SCED's Recall puts every laid-out object back", boxCount("district_fairground") == 0
      and isFull("district_fairground"), boxCount("district_fairground") .. " left")
    place("district_fairground", false)
    check("a Place after the Recall lays out the same box", boxCount("district_fairground") == full,
      boxCount("district_fairground") .. " vs " .. full)
    -- play: a card drawn off a laid-out deck, then the night ends
    for _, o in ipairs(objects()) do
      if o.type == "Deck" and o.hasTag("StillHourBox_district_fairground") then
        local q = o.getPosition()
        o.takeObject({ position = { q.x, q.y + 2, q.z + 3 }, smooth = false })
        break
      end
    end
    E.run(0.5)
    local mark = chatMark()
    clearBoard()
    check("Clear Board takes every card the box laid out, the drawn one too", boxCount("district_fairground") == 0,
      boxCount("district_fairground"))
    check("...puts a full box back in its place", isFull("district_fairground"), table.concat({ fullness("district_fairground") }, "/"))
    check("...and says it filled the box again", saw(mark, "scenario box(es) filled again"), tail(mark))
    place("district_fairground", false)
    check("the next Place lays out the same box again", boxCount("district_fairground") == full,
      boxCount("district_fairground") .. " vs " .. full)
    clearBoard()
    mark = chatMark()
    clearBoard()
    check("a Clear Board with every box full fills none", not saw(mark, "filled again"), tail(mark))
  end)

  ----------------------------------------------------------- N-5 --

  step("N-5: Clear Board takes the tokens resting on the cards it removes, and only those", function()
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
    clearBoard()
    check("the tokens that rested on the removed card went with it", tokensIn(b) == 0, tokensIn(b))
    check("the token that was not on one of its cards stays", far ~= nil and not far.isDestroyed())
    local lost = 0
    for _, o in ipairs(mine) do if o.isDestroyed() then lost = lost + 1 end end
    check("SCED's own table objects are untouched", lost == 0, lost)
    far.destruct(); E.run(0.3)
  end)

  ----------------------------------------------------------- N-8 --

  step("N-8: a clue beside a removed card, or spawned just after it, goes too", function()
    local road = place("district_road", false)
    local card = looseCard("sthr-loc-milestones")
    local b = E.aabb(card)
    local cx, cz = (b.min.x + b.max.x) / 2, (b.min.z + b.max.z) / 2
    -- SCED marks every clue and doom token it spawns with the memo "clueDoom"
    local function clue(px, pz)
      return E.spawnData({ Name = "Custom_Tile", Nickname = "", Memo = "clueDoom",
        Transform = { posX = px, posY = 1.7, posZ = pz, scaleX = 0.25, scaleY = 1, scaleZ = 0.25 } }, {}, "table")
    end
    local beside = clue(b.max.x + 0.9, cz)          -- rolled off the card's edge
    -- nowhere near: Clear Board takes every box's cards, so a spot clear of all of them
    local function clearOfCards(px, pz)
      for _, o in ipairs(objects()) do
        if (o.type == "Card" or o.type == "Deck") and o.hasTag("StillHourLoop") then
          local q = o.getPosition()
          if math.abs(q.x - px) < 4 and math.abs(q.z - pz) < 4 then return false end
        end
      end
      return true
    end
    local fx, fz = b.max.x + 12, b.max.z + 12
    for _, d in ipairs({ { 12, 12 }, { -12, 12 }, { 12, -12 }, { -12, -12 }, { 20, 0 }, { -20, 0 }, { 0, 20 }, { 0, -20 } }) do
      if clearOfCards(cx + d[1], cz + d[2]) then fx, fz = cx + d[1], cz + d[2] ; break end
    end
    local far = clue(fx, fz)
    E.run(0.3)
    clearBoard()
    check("a clue standing just outside the removed card went with it", beside.isDestroyed())
    check("a clue far from every removed card stays", not far.isDestroyed())
    local late = clue(cx, cz)                       -- SCED's staggered spawn of a revealed location's clues
    E.run(2)
    check("a clue spawned a moment after the card left is taken too", late.isDestroyed())
    far.destruct(); E.run(0.3)
  end)

  ----------------------------------------------------------- N-9 --

  step("N-9: the delayed sweep after a Clear Board leaves the clues of a location laid on the same spot", function()
    place("district_road", false)
    click(control(), "Clear Board"); E.run(0.2)
    place("district_road", false)               -- the next Place, inside the sweep's 12 seconds
    local card = looseCard("sthr-loc-milestones")
    local b = E.aabb(card)
    local cx, cz = (b.min.x + b.max.x) / 2, (b.min.z + b.max.z) / 2
    local mine = E.spawnData({ Name = "Custom_Tile", Nickname = "", Memo = "clueDoom",
      Transform = { posX = cx, posY = 1.7, posZ = cz, scaleX = 0.25, scaleY = 1, scaleZ = 0.25 } }, {}, "table")
    E.run(14)
    check("a clue on a location a later Place laid survives the earlier Clear Board's sweeps", not mine.isDestroyed())
    mine.destruct(); E.run(0.2)
    clearBoard()
  end)

  ----------------------------------------------------------- A-1 --

  step("A-1: an act deck takes the mythos mat's Act slot when it is free, its own column when another box holds it", function()
    local function actDeck(prefix)
      return find(function(o)
        local n = tostring(o.getName())
        return o.type == "Deck" and n:find(prefix, 1, true) ~= nil and n:find("Act Deck", 1, true) ~= nil
      end)
    end
    local function at(o, x, z)
      if not o then return false end
      local p = o.getPosition()
      return math.abs(p.x - x) < 0.4 and math.abs(p.z - z) < 0.4
    end
    click(control(), "Clear Board"); E.run(0.5)
    place("district_lighthouse", false)
    local lone = actDeck("The Lighthouse")
    check("a district placed alone lays its act deck in the labelled Act slot", at(lone, -2.94, -5.05),
      lone and tostring(lone.getPosition().x) .. "," .. tostring(lone.getPosition().z))
    click(control(), "Clear Board"); E.run(0.5)
    place("district_square", false)
    place("district_lighthouse", false)
    local sq, lh = actDeck("The Square"), actDeck("The Lighthouse")
    check("with the Square placed first, the Square's act deck holds the Act slot", at(sq, -2.94, -5.05))
    check("...and the Lighthouse's act deck goes to its own column of the row", at(lh, -13.8, 9.18),
      lh and tostring(lh.getPosition().x) .. "," .. tostring(lh.getPosition().z))
    -- The Last Hour's act takes the slot from the Square's act deck, which moves to its own column
    place("finale", false)
    local contest = looseCard("sthr-act-lasthour")
    check("the finale's act takes the Act slot", contest ~= nil and at(contest, -2.94, -5.05),
      contest and tostring(contest.getPosition().x) .. "," .. tostring(contest.getPosition().z))
    check("the Square's act deck moved to its own column of the row", at(actDeck("The Square"), -13.8, -3.06),
      actDeck("The Square") and tostring(actDeck("The Square").getPosition().z))
    click(control(), "Clear Board"); E.run(0.5)
    check("Clear Board takes both act decks", actDeck("The Square") == nil and actDeck("The Lighthouse") == nil)
  end)

  step("A-2: Place sets a district's act deck up from the log: act 3a once the deep entry is in, none once the late record is", function()
    local function knowing(facts)
      local blob = decode(control().call("shApiSnapshot"))
      blob.campaign.partTwo = true
      blob.campaign.prologue = false
      for _, f in ipairs(facts) do blob.campaign.knowledge[f] = true end
      control().call("shApiRestore", { blob = J.encode(blob) }); E.run(6)   -- its board sync finishes first
    end
    local function onTable(id) return looseCard(id) ~= nil or find(function(o)
      if o.type ~= "Deck" then return false end
      for _, e in ipairs(o.getObjects()) do if (decode(e.gm_notes) or {}).id == id then return true end end
      return false
    end) ~= nil end
    click(control(), "Clear Board"); E.run(0.5)
    local before = control().call("shApiSnapshot")
    knowing({ "the-lamp-was-never-lit", "the-keepers-ninth-death" })
    local _, mark = place("district_lighthouse", true)
    check("deep entry recorded: act 3a is the Lighthouse's current act", onTable("sthr-act-keeplight")
      and not onTable("sthr-act-lamp") and not onTable("sthr-act-ninthdeath"),
      (function()
        local out = {}
        for _, o in ipairs(objects()) do
          local ids = {}
          if o.type == "Deck" then for _, e in ipairs(o.getObjects()) do ids[#ids + 1] = (decode(e.gm_notes) or {}).id end
          elseif o.type == "Card" then ids[1] = gm(o).id end
          local hit = false
          for _, i in ipairs(ids) do if tostring(i):find("act%-") then hit = true end end
          if hit then
            local q = o.getPosition()
            out[#out + 1] = string.format("%s %s [%s] at %.1f,%.1f,%.1f tags %s", o.type, o.getName(), table.concat(ids, ","),
              q.x, q.y, q.z, table.concat(o.getTags and o.getTags() or {}, ";"))
          end
        end
        return table.concat(out, " | ")
      end)())
    check("...and the chat says so", saw(mark, "act 3a is current"), chatSince(mark):sub(1, 1200))
    click(control(), "Clear Board"); E.run(0.5)
    knowing({ "the-light-is-kept" })
    local _, mark2 = place("district_lighthouse", true)
    check("late record recorded: the act deck is removed", not onTable("sthr-act-keeplight"), tail(mark2))
    check("...its objectives are complete", saw(mark2, "its objectives are complete"), tail(mark2))
    click(control(), "Clear Board"); E.run(0.5)
    control().call("shApiRestore", { blob = before }); E.run(1)
  end)

  step("A-3: Clear Board while the Appointed is out takes it too, and the Square lays out again", function()
    click(control(), "Clear Board"); E.run(0.5)
    local before = control().call("shApiSnapshot")
    local blob = decode(before)
    blob.campaign.prologue = false
    blob.campaign.appointedStage = 1                     -- Sensed: it manifests at the next board sync
    control().call("shApiRestore", { blob = J.encode(blob) }); E.run(6)
    local _, mark = place("district_square", true)
    check("the Appointed manifests with the Square", looseCard("sthr-appointed") ~= nil, tail(mark))
    local mark2 = chatMark()
    click(control(), "Clear Board"); E.run(2)
    check("Clear Board takes the Appointed's card (it is not put back as undefeatable)",
      looseCard("sthr-appointed") == nil and not saw(mark2, "cannot be defeated"), chatSince(mark2):sub(1, 400))
    local _, mark3 = place("district_square", true)
    check("...and the Square lays out again", (looseCard("sthr-loc-hubsquare") ~= nil or looseCard("sthr-loc-square") ~= nil),
      tail(mark3))
    check("...with the Appointed manifesting again", looseCard("sthr-appointed") ~= nil, tail(mark3))
    click(control(), "Clear Board"); E.run(2)
    control().call("shApiRestore", { blob = before }); E.run(6)
  end)

  ----------------------------------------------------------- N-6 --

  step("N-6: a save and load keeps the spares: a box used before the save is refilled after it", function()
    clearBoard()
    place("district_road", false)
    check("(the Road's box is used)", not isFull("district_road"))
    local saved = E.save()
    E.clearWorld(); E.loadSave(saved, "saved"); E.run(3)
    local spares = find(function(o) return gm(o).type == "ScenarioBoxMasters" end)
    check("the Spare Scenario Boxes bag is still on the table after the load", spares ~= nil)
    check("...holding a spare of every box", spares ~= nil and #spares.getObjects() == 8, spares and #spares.getObjects())
    clearBoard()
    check("Clear Board refills the Road's box after the load", isFull("district_road"), table.concat({ fullness("district_road") }, "/"))
    place("district_road", false)
    check("it lays the box out after the load", boxCount("district_road") > 0)
    clearBoard()
  end)

  ----------------------------------------------------------- N-7, the Prologue --

  step("N-7: the Prologue's box after the Prologue is laid out all the same, and the chat says so once", function()
    local prologue, mark = place("prologue", true)
    check("the Prologue's box is laid out", boxCount("prologue") > 0)
    check("the chat says the Prologue is over, naming the box as printed on it, once",
      saw(mark, prologue.getName() .. " is laid out, but the Prologue is already over.")
        and chatCount(mark, "the Prologue is already over") == 1, tail(mark))
    clearBoard()
    check("Clear Board takes it away and fills its box again", boxCount("prologue") == 0 and isFull("prologue"))
    place("district_square", false)
    check("the Square lays out after it", boxCount("district_square") > 0)
    clearBoard()
  end)
end
