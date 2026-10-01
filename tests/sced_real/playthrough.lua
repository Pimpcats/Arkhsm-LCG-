-- Scripted campaign playthrough on the emulated SCED table (tests only).
--
-- Loads dist/saved_object_the_still_hour.json the way the owner does
-- (docs/LOADING.md), then plays Campaign Setup, the Prologue, a loop, the
-- interlude, Part II and the finale start ONLY through what the owner
-- touches: the Control token's buttons, the scenario boxes' Place/Recall, the
-- campaign log's checkboxes and context menu, and moving cards/decks by hand.
-- After each step it looks at the table: SCED's real chaos bag, its play
-- area and mythos mat positions, card counts, overlaps, and whether anything
-- landed where it should not.

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local unpack = table.unpack or unpack
  local J = E.J
  local sced = H.mode == "sced"

  ------------------------------------------------------------ helpers --

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function gm(o) return decode(o.getGMNotes()) or {} end
  local function alive(o) return o ~= nil and not o.isDestroyed() end
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
  local function byName(n) return find(function(o) return o.getName() == n end) end
  local function labels(o)
    local l = {}
    for _, b in ipairs(o and o.getButtons() or {}) do l[#l + 1] = b.label end
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
    if not ok then check("button '" .. tostring(which) .. "' on " .. tostring(o) .. " can be clicked", false, err) end
    return ok
  end
  local function dist(a, b)
    local dx, dz = a.x - b.x, a.z - b.z
    return math.sqrt(dx * dx + dz * dz)
  end
  local function countOf(list, v)
    local n = 0
    for _, x in ipairs(list or {}) do if x == v then n = n + 1 end end
    return n
  end
  local function sortedCopy(l)
    local c = {}
    for i, v in ipairs(l or {}) do c[i] = v end
    table.sort(c)
    return c
  end
  local function sameList(a, b)
    a, b = sortedCopy(a), sortedCopy(b)
    if #a ~= #b then return false end
    for i = 1, #a do if a[i] ~= b[i] then return false end end
    return true
  end

  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end

  -- SCED's chaos bag through its own Global API (ChaosBagApi)
  local function chaosBag() return E.Global.call("findChaosBag") end
  local function bagState() return E.Global.call("getChaosBagState") or {} end
  local function staticInBag()
    local bag = chaosBag()
    local n = 0
    for _, e in ipairs(bag and bag.getObjects() or {}) do
      for _, t in ipairs(e.tags or {}) do if t == "StillHourStatic" then n = n + 1 end end
    end
    return n
  end

  -- SCED's mythos mat spots (src/mythos/MythosArea.ttslua local coordinates)
  local MYTHOS = { agenda = { 0.056, 0.1, 0.251 }, act = { -0.777, 0.1, 0.251 },
                   encounter = { 0.88, 0.1, 0.391 }, reference = { -1.6, 0.1, 0.37 } }
  local function mythosSpot(key)
    local mat = E.byGuid("9f334f")
    if mat and not mat.isDestroyed() then return mat.positionToWorld(MYTHOS[key]) end
    -- fake table: SCED's mythos mat transform (objects/MythosArea.9f334f.json)
    local l = MYTHOS[key]
    local x, y, z = E.rotate({ x = l[1] * 6.5, y = l[2], z = l[3] * 6.5 }, { x = 0, y = 270, z = 0 })
    return { x = -1.31 + x, y = 1.483 + y, z = z }
  end

  local function playArea()
    local h = E.byGuid("123456")
    if not h then return nil end
    return h.call("getObjectByOwnerAndType", { owner = "Mythos", type = "PlayArea" })
  end
  local function inPlayArea(o)
    local pa = playArea()
    if not pa then return nil end
    return pa.call("isInPlayArea", o)
  end

  -- objects a box laid out (its per-box tag), counting cards inside decks
  local function boxTag(box) return "StillHourBox:" .. box.getGUID() end
  local function placedBy(box)
    return findAll(function(o) return o.hasTag(boxTag(box)) end)
  end
  local function loopObjects()
    return findAll(function(o) return o.hasTag("StillHourLoop") end)
  end
  local function loopCardCount()
    local n = 0
    for _, o in ipairs(loopObjects()) do n = n + (o.type == "Deck" and #o.getObjects() or 1) end
    return n
  end

  local function scenarioBox(id)
    return find(function(o) local m = gm(o) return m.type == "ScenarioBox" and m.id == id end)
  end
  local function deckNamed(suffix, box)
    return find(function(o)
      return o.type == "Deck" and tostring(o.getName()):sub(-#suffix) == suffix and (not box or o.hasTag(boxTag(box)))
    end)
  end
  local function cardWithId(id)
    return find(function(o) return o.type == "Card" and gm(o).id == id end)
  end

  -- every pair of placed cards/decks whose footprints overlap
  local function overlaps(list)
    local out = {}
    for i = 1, #list do
      for j = i + 1, #list do
        local a, b = E.aabb(list[i]), E.aabb(list[j])
        local pad = 0.15
        if a.min.x + pad < b.max.x and a.max.x - pad > b.min.x and a.min.z + pad < b.max.z and a.max.z - pad > b.min.z then
          out[#out + 1] = list[i].getName() .. " / " .. list[j].getName()
        end
      end
    end
    return out
  end

  -- SCED's own objects that a placed object sits on (boards excluded)
  local BOARDS = { ["9f334f"] = true, ["721ba2"] = true, ["4ee1f2"] = true, ["5ce0a1"] = true }
  local function landedOnScedObject(list)
    local out = {}
    for _, o in ipairs(list) do
      local a = E.aabb(o)
      for _, s in ipairs(objects()) do
        local g = s.getGUID()
        -- hidden, non-interactable boards (the mythos mat's warning overlay
        -- under it) are not in the way
        if H.scedGuids[g] and not BOARDS[g] and not E.isZone(s) and s.type ~= "Scripting"
           and not s.hasTag("NotInteractable") then
          local b = E.aabb(s)
          local sp, op = s.getPosition(), o.getPosition()
          -- sizes are estimates: count it only when one covers the other's centre
          local covers = (sp.x > a.min.x and sp.x < a.max.x and sp.z > a.min.z and sp.z < a.max.z)
            or (op.x > b.min.x and op.x < b.max.x and op.z > b.min.z and op.z < b.max.z)
          if b.size.x < 30 and b.size.z < 30 and covers then
            out[#out + 1] = o.getName() .. " on " .. s.getName() .. " (" .. g .. ")"
          end
        end
      end
    end
    return out
  end

  -- tokens SCED spawned onto a card (clues), found by footprint
  local function tokenObjectsOn(card)
    local l = {}
    if not card or not alive(card) then return l end
    local b = E.aabb(card)
    for _, o in ipairs(objects()) do
      if E.stateOfObj(o).origin == "sced" and not H.scedGuids[o.getGUID()]
         and (o.type == "Tile" or o.type == "Generic" or o.type == "Chip") then
        local p = o.getPosition()
        if p.x >= b.min.x and p.x <= b.max.x and p.z >= b.min.z and p.z <= b.max.z then l[#l + 1] = o end
      end
    end
    return l
  end
  local function tokensOn(card) return #tokenObjectsOn(card) end

  local fellMark = 0
  local function newFalls()
    local l = {}
    for i = fellMark + 1, #(E.fellInto or {}) do
      local f = E.fellInto[i]
      l[#l + 1] = string.format("%s fell into %s", f.obj, f.bag)
    end
    fellMark = #(E.fellInto or {})
    return l
  end

  -- snapshot of SCED's own table objects (GUID -> name/pos/count)
  local function scedSnapshot()
    local snap = {}
    local bag = chaosBag()
    for _, o in ipairs(objects()) do
      local g = o.getGUID()
      if H.scedGuids[g] and o ~= bag then
        local p = o.getPosition()
        snap[g] = string.format("%s|%.2f|%.2f|%d", o.getName(), p.x, p.z, o.getQuantity())
      end
    end
    return snap
  end
  local function snapshotDiff(a, b)
    local diffs = {}
    for g, v in pairs(a) do
      if b[g] == nil then
        local by = (E.destroyedBy or {})[g]
        diffs[#diffs + 1] = "gone: " .. v .. (by and (" (destroyed by " .. by:match("^[^\n]*") .. ")") or "")
        if by then io.write("  [destroyed] " .. v .. " by " .. by:sub(1, 1500) .. "\n") end
      elseif b[g] ~= v then diffs[#diffs + 1] = v .. " -> " .. b[g] end
    end
    for g, v in pairs(b) do if a[g] == nil then diffs[#diffs + 1] = "new: " .. v end end
    table.sort(diffs)
    return diffs
  end

  -- the campaign log (its current page) and its fields
  local function campaignLog()
    return find(function(o) return o.hasTag("CampaignLog") and gm(o).type == "CampaignLog" end)
  end
  local function logPage(n)
    local log = campaignLog()
    if not log then return nil end
    local v = log.call("getLogValues")
    if v and v.page ~= n then
      E.menu(log, "Next page")
      E.run(1)
      return logPage(n)
    end
    return log
  end
  local function tickLog(key)
    local log = logPage(2)
    if not log then return false end
    local fields = log.getVar("FIELDS") or {}
    for i, f in ipairs(fields) do
      if f.k == key then return click(log, "sthrLog_" .. i) end
    end
    check("the campaign log has a box for " .. key, false)
    return false
  end
  local function logValue(key)
    local log = campaignLog()
    local v = log and log.call("getLogValues")
    return v and v.values[key]
  end

  ------------------------------------------------------- loading the box --

  local payloadPath = H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")
  info("payload: " .. payloadPath)
  local payload = decode(H.readFile(payloadPath))
  local campaignBox
  local startScedSnapshot

  step("load the Saved Object (Objects > Saved Objects > The Still Hour)", function()
    startScedSnapshot = scedSnapshot()
    local d = payload.ObjectStates[1]
    campaignBox = E.spawnData(d, {}, "campaign")
    E.run(2)
    check("the campaign box spawns with its saved GUID", campaignBox.getGUID() == d.GUID, campaignBox.getGUID())
    check("the campaign box shows Place and Recall", hasLabel(campaignBox, "Place") and hasLabel(campaignBox, "Recall"),
      labels(campaignBox))
  end)

  local placedCampaign = {}
  step("press Place on the campaign box", function()
    local ml = (decode(campaignBox.script_state) or {}).ml or {}
    local n = 0
    for _ in pairs(ml) do n = n + 1 end
    click(campaignBox, "Place")
    E.run(4)
    local at, missing = 0, {}
    for g, e in pairs(ml) do
      local o = E.G.getObjectFromGUID(g)
      if o then
        placedCampaign[#placedCampaign + 1] = o
        if dist(o.getPosition(), e.pos) < 1 then at = at + 1 end
      else
        missing[#missing + 1] = g
      end
    end
    check("Place lays out every remembered object (" .. n .. ")", #missing == 0, #missing .. " missing")
    check("each lands on its remembered spot", at == n, at .. "/" .. n)
    check("the Control token is on the table with its buttons", control() ~= nil and #(control().getButtons() or {}) >= 7,
      control() and labels(control()) or "no control")
    check("the campaign log is on the table", campaignLog() ~= nil)
    check("nothing the box laid out fell into a bag", #newFalls() == 0)
    local on = landedOnScedObject(placedCampaign)
    check("nothing the box laid out sits on SCED's own table objects", #on == 0, table.concat(on, "; "))
    E.run(2)
    local s = st()
    check("a new campaign opens in the Prologue, Hour I, Dissonance 0", s.prologue == true and s.hour == 1 and s.dissonance == 0,
      J.encode(s))
    check("the Control sees SCED", s.sced == true, tostring(s.sced))
  end)

  ------------------------------------------------------------ setup --

  local DIFF = {
    { label = "Easy", bag = { "p1", "p1", "0", "0", "0", "m1", "m1", "m1", "m2", "m2", "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
    { label = "Standard", bag = { "p1", "0", "0", "m1", "m1", "m1", "m2", "m2", "m3", "m4", "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
    { label = "Hard", bag = { "0", "0", "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m5", "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
    { label = "Expert", bag = { "0", "m1", "m1", "m2", "m2", "m3", "m3", "m4", "m4", "m5", "m6", "m8", "skull", "skull", "cultist", "tablet", "elder", "red", "blue" } },
  }

  step("Campaign Setup: the difficulty buttons fill SCED's chaos bag", function()
    for _, d in ipairs({ DIFF[1], DIFF[3], DIFF[4], DIFF[2] }) do
      click(control(), d.label)
      E.run(3)
      local got = bagState()
      check(d.label .. ": SCED's bag holds exactly the guide's " .. #d.bag .. " tokens", sameList(got, d.bag),
        table.concat(sortedCopy(got), ","))
      check(d.label .. ": no [static] in the bag at Calm", staticInBag() == 0, "static " .. staticInBag())
    end
    check("the chaos bag is still where SCED keeps it (on the mythos mat)", chaosBag() ~= nil)
  end)

  step("Campaign Setup: investigators = 2", function()
    local before = st().investigators
    for _ = 1, math.abs(before - 2) do click(control(), "Investigators", before > 2) end
    check("the Investigators button sets the party size", st().investigators == 2, tostring(st().investigators))
  end)

  -- seat two investigators the way the owner does: card from the player-card
  -- bag onto a playmat, minicard onto the map later
  local seated = {}
  step("Campaign Setup: seat two investigators on SCED playmats", function()
    local pbag = find(function(o) return o.type == "Bag" and o.hasTag("StillHour")
      and tostring(o.getName()):find("Player Cards", 1, true) ~= nil end)
    check("the player-card bag is on the table", pbag ~= nil)
    if not pbag then return end
    local mats = { "White", "Orange" }
    local want = { "sthrelias", "sthrbirdie" }
    local handler = E.byGuid("123456")
    for i, id in ipairs(want) do
      local guid
      for _, e in ipairs(pbag.getObjects()) do
        local m = decode(e.gm_notes) or {}
        if m.id == id then guid = e.guid end
      end
      local mat = handler and handler.call("getObjectByOwnerAndType", { owner = mats[i], type = "Playermat" })
      -- SCED's investigator slot on the mat (PlayermatApi localInvestigatorPosition)
      local pos = mat and mat.positionToWorld({ -1.17, 0.1, -0.01 }) or { x = -20 + 4 * i, y = 2, z = -25 }
      local card = guid and pbag.takeObject({ guid = guid, position = { pos.x, (pos.y or 1.5) + 1, pos.z }, smooth = false })
      E.run(1)
      if card then
        E.drop(card, { pos.x, (pos.y or 1.5) + 0.5, pos.z }, mats[i])
        seated[#seated + 1] = { id = id, card = card, mat = mats[i] }
      end
    end
    E.run(3)
    check("two investigator cards are on the playmats", #seated == 2)
    local inv = control().call("shApiInvestigators") or {}
    local found = 0
    for _, x in ipairs(inv) do if x.id == "sthrelias" or x.id == "sthrbirdie" then found = found + 1 end end
    check("the Control finds both investigators", found == 2, J.encode(inv))
  end)

  ------------------------------------------------------------ prologue --

  local function placeBox(id, expectCount)
    local box = scenarioBox(id)
    check("scenario box " .. id .. " is on the table", box ~= nil)
    if not box then return nil end
    local inside = #box.getObjects()
    local ok, n = E.click(box, "Place")
    E.run(4)
    check(id .. ": Place lays out a copy of every object in its box (" .. inside .. ")", ok and n == inside,
      tostring(n) .. "/" .. inside)
    check(id .. ": the box never empties", #box.getObjects() == inside)
    return box
  end

  local function expectAt(label, o, spot, tol)
    check(label, o ~= nil and dist(o.getPosition(), spot) < (tol or 0.6),
      o and string.format("%.2f from the spot", dist(o.getPosition(), spot)) or "not found")
  end

  local function locationsOf(box)
    local l = {}
    for _, o in ipairs(placedBy(box)) do if o.type == "Card" and gm(o).type == "Location" then l[#l + 1] = o end end
    return l
  end

  local prologueBox
  step("Prologue: Place The First Hour", function()
    fellMark = #(E.fellInto or {})
    -- SCED rearranges its own pieces when investigators are seated; from here
    -- on only the campaign acts on the table
    startScedSnapshot = scedSnapshot()
    prologueBox = placeBox("prologue")
    if not prologueBox then return end
    local placed = placedBy(prologueBox)
    local agenda = deckNamed("Agenda Deck", prologueBox)
    local enc = deckNamed("Encounter Deck", prologueBox)
    local act = cardWithId("sthr-act-firsthour")
    local ref = find(function(o) return o.hasTag(boxTag(prologueBox)) and gm(o).type == "ScenarioReference" end)
    expectAt("the Hours sit on SCED's agenda spot", agenda, mythosSpot("agenda"))
    expectAt("the act sits on SCED's act spot", act, mythosSpot("act"))
    expectAt("the encounter deck sits on SCED's encounter deck spot", enc, mythosSpot("encounter"))
    expectAt("the scenario reference card sits in SCED's scenario card area", ref, mythosSpot("reference"), 1.0)
    check("the encounter deck holds 21 cards", enc ~= nil and #enc.getObjects() == 21, enc and #enc.getObjects())
    check("the encounter deck is face down", enc ~= nil and enc.is_face_down)
    if enc then
      enc.shuffle()                         -- Setup: "Shuffle it"
      check("the encounter deck still holds 21 after shuffling", #enc.getObjects() == 21)
    end
    local locs = locationsOf(prologueBox)
    check("three Prologue locations are laid out", #locs == 3, #locs)
    local outside = {}
    for _, l in ipairs(locs) do if inPlayArea(l) == false then outside[#outside + 1] = l.getName() end end
    check("every location is inside SCED's play area", #outside == 0, table.concat(outside, ", "))
    local ov = overlaps(placed)
    check("no two laid-out cards overlap", #ov == 0, table.concat(ov, "; "))
    local falls = newFalls()
    check("nothing laid out fell into a bag", #falls == 0, table.concat(falls, "; "))
    local on = landedOnScedObject(placed)
    check("nothing laid out sits on SCED's own table objects", #on == 0, table.concat(on, "; "))
    local square = cardWithId("sthr-loc-square")
    check("The Square is revealed, the other two are not", square ~= nil and not square.is_face_down
      and cardWithId("sthr-loc-longpier").is_face_down and cardWithId("sthr-loc-almanacsteps").is_face_down)
    E.run(2)
    check("SCED spawns clues on the revealed location (its play area)", tokensOn(square) > 0,
      tokensOn(square) .. " token(s)")
    check("SCED spawns nothing on the unrevealed ones", tokensOn(cardWithId("sthr-loc-longpier")) == 0
      and tokensOn(cardWithId("sthr-loc-almanacsteps")) == 0)
    -- the owner reveals a location: SCED spawns its clues
    local pier = cardWithId("sthr-loc-longpier")
    if pier then E.playerFlip(pier) end
    E.run(2)
    check("revealing a location (flipping it) spawns its clues", tokensOn(pier) > 0, tokensOn(pier) .. " token(s)")
    -- the minicards go to The Square (each investigator begins there)
    local minis = find(function(o) return o.type == "Deck" and o.hasTag("Minicard") end)
    if minis and square then
      local sp = square.getPosition()
      for i, s in ipairs(seated) do
        local g
        for _, e in ipairs(minis.getObjects()) do if (decode(e.gm_notes) or {}).id == s.id .. "-m" then g = e.guid end end
        local alive_ = alive(minis) and minis or find(function(o) return o.hasTag("Minicard") and gm(o).id == s.id .. "-m" end)
        local m
        if g and alive_ and alive_.type == "Deck" then
          m = alive_.takeObject({ guid = g, position = { sp.x - 0.8 + i * 0.6, sp.y + 1, sp.z }, smooth = false })
        end
        if m then E.drop(m, { sp.x - 0.8 + i * 0.6, sp.y + 0.3, sp.z }) end
        minis = find(function(o) return o.type == "Deck" and o.hasTag("Minicard") end) or minis
      end
      E.run(2)
    end
  end)

  step("Prologue: the Hourglass and Dissonance buttons", function()
    local s0 = st()
    click(control(), "Hour")
    E.run(1)
    check("Hour advances by one", st().hour == s0.hour + 1, st().hour)
    click(control(), "Hour", true)
    E.run(1)
    check("Hour rewinds by one", st().hour == s0.hour, st().hour)
    for _ = 1, 3 do click(control(), "Dissonance") end
    E.run(3)
    check("Dissonance raises", st().dissonance == 3, st().dissonance)
  end)

  step("Prologue ends: Reset Loop, Interlude, Begin Next Loop", function()
    local memBefore = st().memory
    tickLog("k:you-are-unstuck")
    E.run(1)
    check("ticking You Are Unstuck on the log records it on the Control", control().call("shApiState") ~= nil
      and logValue("k:you-are-unstuck") == true)
    -- Resolution: each investigator gains 2 banked Memory (owner clicks +4)
    for _ = 1, 4 do click(control(), "Memory") end
    check("Memory button banks +4", st().memory == memBefore + 4, memBefore .. " -> " .. st().memory)
    click(control(), "Reset Loop")
    E.run(2)
    local s = st()
    check("Reset Loop ends the Prologue without counting a loop", s.prologue == false and s.loops == 0 and s.loopEnded == true,
      J.encode(s))
    click(control(), "Reset Loop")
    check("a second Reset Loop is refused", st().loops == 0)
    click(control(), "Interlude")
    check("the Interlude panel opens", hasLabel(control(), "Begin Next Loop"), labels(control()))
    click(control(), "Begin Next Loop")
    E.run(2)
    s = st()
    check("Begin Next Loop starts Loop 1 (Hour I, Dissonance at the scar 0)", s.mode == "play" and s.hour == 1
      and s.dissonance == 0 and s.loopEnded == false, J.encode(s))
    check("the [static] tokens follow Dissonance back to Calm", staticInBag() == 0, staticInBag())
  end)

  ------------------------------------------------------------ loop 1 --

  local square, districts = nil, {}
  local ownObjectsBefore
  step("Loop 1: Clear Board", function()
    local snap = scedSnapshot()
    local campaignGuids = {}
    for _, o in ipairs(placedCampaign) do if alive(o) then campaignGuids[o.getGUID()] = true end end
    -- the tokens SCED spawned onto the laid-out cards (clues on locations)
    local onCards = {}
    for _, c in ipairs(loopObjects()) do
      for _, t in ipairs(tokenObjectsOn(c)) do onCards[#onCards + 1] = t end
    end
    info(#onCards .. " token(s) on the laid-out cards before Clear Board")
    click(control(), "Clear Board")
    E.run(3)
    check("Clear Board removes every card the Prologue box laid out", loopCardCount() == 0, loopCardCount() .. " left")
    local names = {}
    for _, t in ipairs(onCards) do if alive(t) then names[#names + 1] = t.getName() .. "(" .. t.type .. ")" end end
    check("no token placed on those cards is left behind", #onCards > 0 and #names == 0,
      #onCards .. " on cards; left: " .. table.concat(names, ", "))
    local diff = snapshotDiff(snap, scedSnapshot())
    check("SCED's own table objects are untouched", #diff == 0, table.concat(diff, "; "))
    local kept = 0
    for g in pairs(campaignGuids) do if E.G.getObjectFromGUID(g) then kept = kept + 1 end end
    local n = 0
    for _ in pairs(campaignGuids) do n = n + 1 end
    check("the campaign's own objects stay (boxes, Control, log, guide, bags)", kept == n, kept .. "/" .. n)
  end)

  local function encounterDeck()
    return find(function(o)
      return o.type == "Deck" and o.hasTag("StillHourLoop") and dist(o.getPosition(), mythosSpot("encounter")) < 0.8
    end)
  end

  step("Loop 1: Place The Square (Town Hall)", function()
    fellMark = #(E.fellInto or {})
    square = placeBox("district_square")
    if not square then return end
    local enc = encounterDeck()
    check("the shared encounter deck holds 25 cards", enc ~= nil and #enc.getObjects() == 25, enc and #enc.getObjects())
    expectAt("the Hours sit on SCED's agenda spot", deckNamed("Agenda Deck", square), mythosSpot("agenda"))
    local act = deckNamed("Act Deck", square)
    check("the Square's act deck is in the district row (not on SCED's act spot)",
      act ~= nil and dist(act.getPosition(), mythosSpot("act")) > 3, act and string.format("%.1f", dist(act.getPosition(), mythosSpot("act"))))
    local locs = locationsOf(square)
    check("the Square's four locations are laid out", #locs == 4, #locs)
    local falls = newFalls()
    check("nothing laid out fell into a bag", #falls == 0, table.concat(falls, "; "))
  end)

  step("Loop 1: Place two districts (the Lighthouse, the Drowned Church)", function()
    for _, id in ipairs({ "district_lighthouse", "district_church" }) do
      local b = placeBox(id)
      if b then districts[#districts + 1] = b end
    end
    E.run(2)
    -- Loop Setup 5: shuffle each district's encounter set into the encounter deck
    local enc = encounterDeck()
    local added = 0
    for _, b in ipairs(districts) do
      local set = deckNamed("Encounter Deck", b)
      if set and enc then
        added = added + #set.getObjects()
        E.playerPut(enc, set)
      end
    end
    E.run(1)
    enc = encounterDeck()
    if enc then enc.shuffle() end
    check("the encounter deck holds 25 + the district sets (" .. (25 + added) .. ")", enc ~= nil and #enc.getObjects() == 25 + added,
      enc and #enc.getObjects())
    local all = {}
    for _, b in ipairs({ square, unpack(districts) }) do
      for _, o in ipairs(placedBy(b)) do if o.type == "Card" or o.type == "Deck" then all[#all + 1] = o end end
    end
    local ov = overlaps(all)
    check("no two cards from the three boxes overlap", #ov == 0, table.concat(ov, "; "))
    local locs = {}
    for _, b in ipairs({ square, unpack(districts) }) do for _, l in ipairs(locationsOf(b)) do locs[#locs + 1] = l end end
    local outside = {}
    for _, l in ipairs(locs) do if inPlayArea(l) == false then outside[#outside + 1] = l.getName() end end
    check("every location is inside SCED's play area", #outside == 0, table.concat(outside, ", "))
    -- connections: each location's visible side connects to at least one other
    local icons, lonely = {}, {}
    local function side(l)
      local m = gm(l)
      return (l.is_face_down and m.locationBack or m.locationFront) or {}
    end
    for _, l in ipairs(locs) do
      for ic in tostring(side(l).icons or ""):gmatch("[^|]+") do icons[ic] = (icons[ic] or 0) + 1 end
    end
    for _, l in ipairs(locs) do
      local linked = false
      for c in tostring(side(l).connections or ""):gmatch("[^|]+") do if icons[c] then linked = true end end
      if not linked then lonely[#lonely + 1] = l.getName() end
    end
    check("every placed location connects to another placed location", #lonely == 0, table.concat(lonely, ", "))
    if sced then
      local tracked = (playArea() and playArea().call("getTrackedLocations")) or {}
      local missing = {}
      for _, l in ipairs(locs) do if tracked[l.getGUID()] == nil then missing[#missing + 1] = l.getName() end end
      check("SCED's play area tracks every placed location (connection lines)", #missing == 0, table.concat(missing, ", "))
    end
    local falls = newFalls()
    check("nothing laid out fell into a bag", #falls == 0, table.concat(falls, "; "))
    local on = landedOnScedObject(all)
    check("nothing laid out sits on SCED's own table objects", #on == 0, table.concat(on, "; "))
  end)

  step("Loop 1: Hour advance and rewind", function()
    local h0 = st().hour
    click(control(), "Hour")
    click(control(), "Hour")
    E.run(1)
    check("two Hour advances", st().hour == h0 + 2, st().hour)
    click(control(), "Hour", true)
    E.run(1)
    check("one rewind", st().hour == h0 + 1, st().hour)
  end)

  local function appointed()
    return find(function(o) return o.type == "Card" and gm(o).id == "sthr-appointed" end)
  end
  local function nearestLocation(o)
    local best, bd
    for _, l in ipairs(findAll(function(x) return x.type == "Card" and gm(x).type == "Location" end)) do
      local d = dist(l.getPosition(), o.getPosition())
      if not bd or d < bd then best, bd = l, d end
    end
    return best, bd
  end

  step("Loop 1: the Appointed manifests, hunts and is held back", function()
    local s0 = st()
    click(control(), "Appointed")
    E.run(2)
    local s = st()
    check("a card advance makes the Appointed Sensed", s0.stage == 0 and s.stage == 1, s0.stage .. " -> " .. s.stage)
    local a = appointed()
    local loc, d
    if a then loc, d = nearestLocation(a) end
    check("it manifests on a location", a ~= nil and d ~= nil and d < 2, a and d and string.format("%.1f from %s", d, loc.getName()) or "not on the table")
    check("its card has a Hold Back button", hasLabel(a, "Hold Back"), labels(a))
    click(control(), "Appointed")
    E.run(2)
    a = appointed()
    check("Emerging adds Hunt", hasLabel(a, "Hunt"), labels(a))
    local before = a and a.getPosition()
    if a then click(a, "Hunt") end
    E.run(2)
    a = appointed()
    check("Hunt runs from the card (it moves or holds with an investigator)", a ~= nil)
    local h = st().hour
    if a then click(a, "Hold Back") end
    E.run(2)
    s = st()
    check("Hold Back drops one stage and rewinds one Hour", s.stage == 1 and s.hour == math.max(1, h - 1),
      "stage " .. s.stage .. ", hour " .. h .. " -> " .. s.hour)
  end)

  step("Loop 1: Dissonance bands move [static] in SCED's chaos bag", function()
    -- bands scale with the party (Constants.forCount): reset 8n (16 solo),
    -- Glitch from a third of it, Noticed from two-thirds
    local n = st().investigators
    local reset = (n == 1) and 16 or 8 * n
    local glitchAt, noticedAt = math.floor(reset / 3), math.floor(2 * reset / 3)
    local d0 = st().dissonance
    for _ = 1, math.max(0, glitchAt - d0) do click(control(), "Dissonance") end
    E.run(3)
    check("Glitch band: 1 [static] in SCED's chaos bag", staticInBag() == 1 and st().band == "Glitch",
      staticInBag() .. " at " .. st().dissonance .. " " .. st().band)
    check("SCED's own bag state still reads (unknown [static] skipped)", #bagState() == 17, #bagState())
    for _ = 1, noticedAt - st().dissonance do click(control(), "Dissonance") end
    E.run(3)
    check("Noticed band: 2 [static] in SCED's chaos bag", staticInBag() == 2 and st().band == "Noticed",
      staticInBag() .. " at " .. st().dissonance .. " " .. st().band)
    -- a reveal through SCED's own draw (its chaos-token draw for the White
    -- mat, asking for the [static] by name): Dissonance rises by 1
    local before = st().dissonance
    local okDraw, tok = pcall(E.Global.call, "drawChaosToken",
      { mat = "White", drawAdditional = true, tokenType = "Static" })
    E.run(2)
    check("SCED's chaos-token draw takes the [static] out", okDraw and tok ~= nil and tostring(tok.getName()) == "Static",
      okDraw and tostring(tok) or tok)
    check("drawing a [static] raises Dissonance by 1", st().dissonance == before + 1, before .. " -> " .. st().dissonance)
    local okRet, errRet = pcall(E.Global.call, "returnChaosTokens")
    E.run(2)
    check("SCED returns the drawn [static] to the bag", okRet and staticInBag() == 2, okRet and staticInBag() or errRet)
    for _ = 1, st().dissonance - d0 do click(control(), "Dissonance", true) end
    E.run(3)
    check("back below Glitch: the [static] tokens leave the bag", staticInBag() == 0, staticInBag() .. " at " .. st().dissonance)
  end)

  step("Loop 1: a Victory on the log banks once", function()
    local m0 = st().memory
    tickLog("v:sthr-bellringer")
    E.run(1)
    local m1 = st().memory
    check("ticking a Named enemy's Victory banks it (+2)", m1 == m0 + 2, m0 .. " -> " .. m1)
    tickLog("v:sthr-bellringer")      -- untick
    tickLog("v:sthr-bellringer")      -- tick again
    E.run(1)
    check("ticking it again banks nothing more", st().memory == m1, m1 .. " -> " .. st().memory)
  end)

  step("Loop 1: a Knowledge tick on the log reaches the Control and pays once", function()
    local m0 = st().memory
    tickLog("k:the-lamp-was-never-lit")
    E.run(1)
    local m1 = st().memory
    check("a surface entry pays nothing (Knowledge pays Memory for deep entries only)", m1 == m0, m0 .. " -> " .. m1)
    check("the log shows it ticked", logValue("k:the-lamp-was-never-lit") == true)
    tickLog("k:the-lamp-was-never-lit")      -- a mis-tick cleared: refund
    E.run(1)
    check("clearing the box refunds it", st().memory == m0, st().memory)
    tickLog("k:the-lamp-was-never-lit")
    E.run(1)
    check("ticking it again pays it once, not twice", st().memory == m1, st().memory)
    local lamp = cardWithId("sthr-loc-lanternroom")
    check("the location that entry changes is turned (Sync Board applied it)", lamp ~= nil and lamp.is_face_down == true,
      lamp and tostring(lamp.is_face_down))
  end)

  step("Loop 1 ends: Reset Loop, an interlude purchase, Begin Next Loop", function()
    click(control(), "Reset Loop")
    E.run(1)
    check("the loop is counted", st().loops == 1 and st().loopEnded == true, J.encode(st()))
    click(control(), "Interlude")
    E.run(1)
    local b
    for _, x in ipairs(control().getButtons() or {}) do
      if tostring(x.label):find("^The Long Way Round") then b = x end
    end
    check("the interlude panel lists a Recollection with its price", b ~= nil and tostring(b.label):find("%(2%)") ~= nil,
      labels(control()))
    local m0 = st().memory
    if b then click(control(), b.click_function) end
    check("buying it spends 2 Memory", st().memory == m0 - 2, m0 .. " -> " .. st().memory)
    click(control(), "Begin Next Loop")
    E.run(2)
    check("Loop 2 begins at the scar (Dissonance 1)", st().dissonance == 1 and st().mode == "play", J.encode(st()))
  end)

  step("Loop 2: Clear Board, then Place again", function()
    local snap = scedSnapshot()
    click(control(), "Clear Board")
    E.run(3)
    check("Clear Board takes every loop card off the table (drawn ones too)", loopCardCount() == 0, loopCardCount() .. " left")
    local diff = snapshotDiff(snap, scedSnapshot())
    check("SCED's own table objects are untouched", #diff == 0, table.concat(diff, "; "))
    square = placeBox("district_square")
    local enc = encounterDeck()
    check("a fresh encounter deck of 25 again", enc ~= nil and #enc.getObjects() == 25, enc and #enc.getObjects())
    placeBox("district_road")
    local falls = newFalls()
    check("nothing laid out fell into a bag", #falls == 0, table.concat(falls, "; "))
  end)

  ------------------------------------------------------------ part II --

  step("Part II: three surface entries before Begin Next Loop", function()
    tickLog("k:the-thirteenth-toll")
    tickLog("k:the-road-remembers")
    click(control(), "Reset Loop")
    E.run(1)
    click(control(), "Interlude")
    click(control(), "Begin Next Loop")
    E.run(2)
    check("Part II has begun", st().partTwo == true, J.encode(st()))
    click(control(), "Clear Board")
    E.run(2)
    placeBox("district_square")
    placeBox("district_almanac")
    check("the boxes still lay out in Part II", loopCardCount() > 26)
    E.run(3)
    local study = cardWithId("sthr-loc-sealedstudy")
    check("a location that is still closed carries its CLOSED label", hasLabel(study, "CLOSED"), labels(study))
    if study then E.playerFlip(study) end
    E.run(2)
    check("revealing a closed location spawns no clues (held back in SCED's spawn tracker)",
      study ~= nil and tokensOn(study) == 0, tokensOn(study) .. " token(s)")
  end)

  ------------------------------------------------------------ finale --

  step("Finale: record the entries, Begin Finale, the contest counter", function()
    for _, k in ipairs({ "k:the-vote-that-never-ends", "k:what-the-almanac-hid", "k:the-appointeds-name", "k:the-hour-was-wrong" }) do
      tickLog(k)
    end
    E.run(2)
    local study = cardWithId("sthr-loc-sealedstudy")
    check("once opened, the location loses its CLOSED label", study ~= nil and not hasLabel(study, "CLOSED"), labels(study))
    check("once opened, SCED spawns its clues", tokensOn(study) > 0, tokensOn(study) .. " token(s)")
    check("the finale entry is assembled on the Control", hasLabel(control(), "Begin Finale"), labels(control()))
    click(control(), "Begin Finale")
    E.run(1)
    check("Begin Finale starts the finale", st().finale == true, J.encode(st()))
    check("the Contest counter shows", hasLabel(control(), "Contest 0"), labels(control()))
    click(control(), "Contest")
    click(control(), "Contest")
    check("the contest counter counts", hasLabel(control(), "Contest 2"), labels(control()))
    fellMark = #(E.fellInto or {})
    local bagBefore = chaosBag() and #chaosBag().getObjects()
    local fin = placeBox("finale")
    E.run(3)
    local falls = newFalls()
    check("nothing the finale box laid out fell into a bag", #falls == 0, table.concat(falls, "; "))
    check("SCED's chaos bag holds the same number of objects", chaosBag() ~= nil and #chaosBag().getObjects() == bagBefore,
      tostring(bagBefore) .. " -> " .. tostring(chaosBag() and #chaosBag().getObjects()))
    if fin then
      local on = landedOnScedObject(placedBy(fin))
      check("nothing the finale box laid out sits on SCED's own table objects", #on == 0, table.concat(on, "; "))
      local act = cardWithId("sthr-act-lasthour")
      expectAt("the finale's act sits on SCED's act spot", act, mythosSpot("act"))
    end
  end)

  ------------------------------------------------------------ save/load --

  step("save and load the table (onSave -> onLoad)", function()
    local s0 = st()
    local log0 = campaignLog() and campaignLog().call("getLogValues")
    local boxes0 = {}
    for _, o in ipairs(findAll(function(o) return gm(o).type == "ScenarioBox" end)) do
      boxes0[o.getGUID()] = o.script_state
    end
    local loops0 = loopCardCount()
    local saved = E.save()
    local errMark = #E.errors
    E.clearWorld()
    E.loadSave(saved, "saved")
    E.run(5)
    local errs = H.errorsSince(errMark)
    check("the saved table loads again without Lua errors", #errs == 0, H.describeErrors(errs))
    local ctl = control()
    check("the Control is back", ctl ~= nil)
    if not ctl then return end
    local s1 = ctl.call("shApiState")
    local same = true
    for _, k in ipairs({ "memory", "dissonance", "hour", "stage", "investigators", "loops", "prologue", "finale", "partTwo" }) do
      if s0[k] ~= s1[k] then same = false end
    end
    check("the Control's campaign state survives save+load", same, J.encode(s0) .. " vs " .. J.encode(s1))
    local log1 = campaignLog() and campaignLog().call("getLogValues")
    local function same(a, b)
      if type(a) ~= type(b) then return false end
      if type(a) ~= "table" then return a == b end
      for k, v in pairs(a) do if not same(v, b[k]) then return false end end
      for k in pairs(b) do if a[k] == nil then return false end end
      return true
    end
    check("the campaign log's fields survive save+load", log0 ~= nil and log1 ~= nil and log0.page == log1.page
      and same(log0.values, log1.values), log1 and ("page " .. tostring(log1.page)) or "no log")
    local okBoxes = true
    for g, s in pairs(boxes0) do
      local b = E.G.getObjectFromGUID(g)
      if not b or b.script_state ~= s then okBoxes = false end
    end
    check("every scenario box keeps its layout memory", okBoxes)
    check("the laid-out cards are still on the table", loopCardCount() == loops0, loopCardCount() .. " vs " .. loops0)
    check("the chaos bag still holds the band's [static]", staticInBag() == (s1.static and s1.static.target or 0),
      staticInBag() .. " vs " .. tostring(s1.static and s1.static.target))
    click(ctl, "Clear Board")
    E.run(2)
    check("Clear Board still works after loading", loopCardCount() == 0, loopCardCount())
  end)

  step("the table outside the campaign is as SCED left it", function()
    local diff = snapshotDiff(startScedSnapshot, scedSnapshot())
    check("SCED's own objects are where they were before the first box was Placed", #diff == 0, table.concat(diff, "; "))
  end)
end
