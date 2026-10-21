-- The Setup panel on SCED's real table (tests only; designer-facing, it names cards by id): seating
-- investigators from SCED's own player cards, Set Up Prologue and Set Up Loop.
--
--   S-1  Seat investigators: card, minicard, permanent quest card and a 34-card deck (3 required cards,
--        the 30-card starter deck from SCED's player cards, 1 random basic weakness) on each playmat,
--        every card tagged with its owner; the party size follows
--   S-2  Set Up Prologue: the Prologue's box laid out, 5 resources and 5 cards each, at the Square
--   S-3  Set Up Loop: the night's districts picked from the log; every card an investigator played,
--        discarded or held goes back into their deck; Clear Board and the boxes in order; at the Square
--   S-4  the Hours deck follows the Control's Hour (advance and rewind)
--   S-5  Begin Finale sets The Last Hour up: its box, the act decks aside, the forms and The Uninvited
--        spawned, the Hourglass set back from Hour IX, the log's damage on the forms
--
-- tests/test_sced_setup.py runs it on SCED's real table (it needs SCED's All Player Cards bag).

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local J = E.J

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
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function click(o, which, alt)
    local ok, err = E.click(o, which, "White", alt)
    if not ok then check("button '" .. tostring(which) .. "' can be clicked", false, err) end
    return ok
  end
  local function chatMark() return #E.log end
  local function chatSince(mark)
    local out = {}
    for i = mark + 1, #E.log do out[#out + 1] = tostring(E.log[i].msg) end
    return table.concat(out, " || ")
  end
  local function handler() return E.byGuid("123456") end
  local function sced(owner, kind) return handler().call("getObjectByOwnerAndType", { owner = owner, type = kind }) end
  local function mat(colour) return sced(colour, "Playermat") end
  local function zone(colour, lp) return mat(colour).positionToWorld(lp) end
  local function near(a, b, r) return math.abs(a.x - b.x) <= r and math.abs(a.z - b.z) <= r end
  local DECK, INVESTIGATOR = { -1.82, 0, 0 }, { -1.177, 0, 0.002 }

  local function stackAt(p)
    for _, o in ipairs(objects()) do
      if (o.type == "Deck" or o.type == "Card") and near(o.getPosition(), p, 0.4) then return o end
    end
    return nil
  end
  local function count(o) if not o then return 0 end return o.type == "Deck" and #o.getObjects() or 1 end
  -- a permanent random basic weakness starts in play beside the mat, so the deck holds one card fewer
  local function permanentWeaknesses(colour)
    local n = 0
    for _, o in ipairs(objects()) do
      if o.type == "Card" and o.hasTag("StillHourOwner_" .. colour) and gm(o).permanent and gm(o).weakness then n = n + 1 end
    end
    return n
  end
  local function hand(colour)
    local pc = mat(colour).getVar("playerColor")
    return E.G.Player[pc].getHandObjects()
  end
  local function card(id) return find(function(o) return o.type == "Card" and gm(o).id == id end) end
  local function scenarioBox(id) return find(function(o) local m = gm(o) return m.type == "ScenarioBox" and m.id == id end) end
  local function boxEmpty(id) local b = scenarioBox(id) return b ~= nil and #b.getObjects() == 0 end
  local function loopCards()
    local n = 0
    for _, o in ipairs(objects()) do if o.hasTag("StillHourLoop") and (o.type == "Card" or o.type == "Deck") then n = n + 1 end end
    return n
  end

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")

  step("setup: the campaign box laid out; SCED's player cards are indexed", function()
    E.run(2); click(campaignBox, "Place"); E.run(4)
    click(control(), "Standard"); E.run(1)
    local bag = sced("Mythos", "AllCardsBag")
    check("SCED's All Player Cards bag is on the table", bag ~= nil)
    E.runUntil(function() return bag.call("isIndexReady") == true end, 120)
    check("its index is ready", bag.call("isIndexReady") == true)
    check("a new campaign begins in the Prologue", st().prologue == true)
  end)

  ----------------------------------------------------------------- S-1 --

  step("S-1: Seat investigators puts two investigators, their cards and their decks on the White and Orange mats", function()
    click(control(), "Set Up Prologue"); E.run(0.3)
    local labels = {}
    for _, b in ipairs(control().getButtons()) do labels[#labels + 1] = tostring(b.label) end
    check("the Set Up button opens the Setup panel, which lists the investigators",
      table.concat(labels, "|"):find("Elias Warde", 1, true) ~= nil, table.concat(labels, " | "))
    local mark = chatMark()
    local r = control().call("shApiSeat", { ids = { "sthrelias", "sthrcass" } })
    E.run(4)
    check("two investigators are seated", r and r.seated == 2, chatSince(mark))
    for _, case in ipairs({ { "White", "sthrelias", "sthr-quest-elias" }, { "Orange", "sthrcass", "sthr-quest-cass" } }) do
      local colour, inv, quest = case[1], case[2], case[3]
      local c = stackAt(zone(colour, INVESTIGATOR))
      check(colour .. ": the investigator card is on the mat's investigator spot", c ~= nil and gm(c).id == inv,
        c and tostring(gm(c).id) or "nothing there")
      local d = stackAt(zone(colour, DECK))
      local pw = permanentWeaknesses(colour)
      check(colour .. ": a 34-card deck is on the Deck spot (3 required + 30 starter + 1 random basic weakness;"
        .. " a permanent one starts beside the mat)", count(d) == 34 - pw, count(d) .. " (" .. pw .. " set aside)")
      local untagged = 0
      for _, e in ipairs(d and d.type == "Deck" and d.getObjects() or {}) do
        local mine = false
        for _, t in ipairs(e.tags or {}) do if t == "StillHourOwner_" .. colour then mine = true end end
        if not mine then untagged = untagged + 1 end
      end
      check(colour .. ": every card in it carries its owner", d ~= nil and untagged == 0, untagged)
      check(colour .. ": the deck is face down", d ~= nil and math.abs((d.getRotation().z or 0) - 180) < 5)
      local q = card(quest)
      check(colour .. ": the personal quest card is beside the mat, not in the deck",
        q ~= nil and near(q.getPosition(), mat(colour).positionToWorld({ (colour == "White") and 2.35 or -2.35, 0, -0.52 }), 0.6))
      check(colour .. ": the minicard is out", card(inv .. "-m") ~= nil)
    end
    check("the party size follows (2 investigators)", st().investigators == 2, st().investigators)
  end)

  ----------------------------------------------------------------- S-2 --


  step("S-2: Set Up Prologue lays the Prologue out and deals each investigator in", function()
    local mark = chatMark()
    local r = control().call("shApiSetUp")
    check("Set Up Prologue starts", r ~= false, chatSince(mark))
    E.run(20)
    check("the Prologue's box is laid out", boxEmpty("prologue"))
    check("its locations are on the table", card("sthr-loc-square") ~= nil and card("sthr-loc-longpier") ~= nil)
    for _, colour in ipairs({ "White", "Orange" }) do
      check(colour .. ": 5 cards in hand", #hand(colour) == 5, #hand(colour))
      check(colour .. ": 29 cards left in the deck", count(stackAt(zone(colour, DECK))) == 29 - permanentWeaknesses(colour),
        count(stackAt(zone(colour, DECK))))
      check(colour .. ": 5 resources", mat(colour).call("getCounterValue", "ResourceCounter") == 5,
        mat(colour).call("getCounterValue", "ResourceCounter"))
    end
    local sq = card("sthr-loc-square")
    check("both investigators are at the Square", sq ~= nil and card("sthrelias-m") ~= nil
      and near(card("sthrelias-m").getPosition(), sq.getPosition(), 1.0)
      and near(card("sthrcass-m").getPosition(), sq.getPosition(), 1.0))
    check("the chat says to check the table", chatSince(mark):find("Check the table", 1, true) ~= nil, chatSince(mark):sub(-600))
  end)

  ----------------------------------------------------------------- S-3 --

  step("S-3: Set Up Loop picks the night's districts, gathers every card back and lays the loop out", function()
    -- play happens: White plays a card next to the mat, discards one, keeps three
    local h = hand("White")
    local mp = mat("White").getPosition()
    if h[1] then h[1].setPosition({ mp.x + 1, mp.y + 0.5, mp.z }) end
    if h[2] then
      local dz = mat("White").positionToWorld({ -1.82, 0, 0.61 })
      h[2].setPosition({ dz.x, dz.y + 0.5, dz.z })
    end
    E.run(1)
    -- the Prologue ends; Between Loops; the next loop begins
    click(control(), "Reset Loop"); E.run(0.3)
    if not st().loopEnded then click(control(), "Reset Loop"); E.run(0.3) end
    click(control(), "Interlude"); E.run(0.2)
    click(control(), "Begin Next Loop"); E.run(0.2)
    if st().loopEnded then click(control(), "Begin Next Loop"); E.run(0.3) end
    check("the next loop is under way", st().prologue == false and st().loopEnded == false)
    click(control(), "Set Up Loop"); E.run(0.3)
    local labels = {}
    for _, b in ipairs(control().getButtons()) do labels[#labels + 1] = tostring(b.label) end
    local all = table.concat(labels, " | ")
    check("the night's districts are picked: the two with an objective left, in the map's order",
      all:find("[x] The Drowned Church", 1, true) ~= nil and all:find("[x] The Almanac House", 1, true) ~= nil
        and all:find("[ ] The Fairground", 1, true) ~= nil, all)
    local mark = chatMark()
    control().call("shApiSetUp")
    E.run(30)
    check("the Prologue's cards are gone and its box is full again", card("sthr-loc-longpier") == nil and not boxEmpty("prologue"))
    check("the Square, the Church and the Almanac House are laid out", boxEmpty("district_square") and boxEmpty("district_church")
      and boxEmpty("district_almanac"))
    check("the boxes not picked stay full", not boxEmpty("district_fairground") and not boxEmpty("district_road"))
    for _, colour in ipairs({ "White", "Orange" }) do
      check(colour .. ": every card is back and dealt again: 5 in hand, 29 in the deck",
        #hand(colour) == 5 and count(stackAt(zone(colour, DECK))) == 29 - permanentWeaknesses(colour),
        #hand(colour) .. " / " .. count(stackAt(zone(colour, DECK))))
    end
    for _, colour in ipairs({ "White", "Orange" }) do
      local strays = {}
      for _, o in ipairs(objects()) do
        if o.type == "Card" then
          for _, t in ipairs(o.getTags()) do
            if t == "StillHourOwner_" .. colour and gm(o).type ~= "Investigator" and not gm(o).permanent then
              local inHand = false
              for _, c in ipairs(hand(colour)) do if c == o then inHand = true end end
              if not inHand then
                local p = o.getPosition()
                strays[#strays + 1] = string.format("%s%s at %.1f,%.1f,%.1f", o.getName(),
                  gm(o).weakness and " (weakness)" or "", p.x, p.y, p.z)
              end
            end
          end
        end
      end
      check("no card of " .. colour .. "'s is left on the table outside the deck and hand", #strays == 0,
        #strays .. " " .. table.concat(strays, "; "))
    end
    local sq = card("sthr-loc-hubsquare")
    check("both investigators are at the Square", sq ~= nil and near(card("sthrelias-m").getPosition(), sq.getPosition(), 1.0)
      and near(card("sthrcass-m").getPosition(), sq.getPosition(), 1.0))
    check("the chat says the loop is set up", chatSince(mark):find("Set up:", 1, true) ~= nil, chatSince(mark):sub(-700))
    info("loop cards on the table: " .. loopCards())
  end)

  ----------------------------------------------------------------- S-4 --

  local AGENDA = { x = -2.94, z = 0.36 }
  local function shownHour()
    local d = stackAt({ x = AGENDA.x, y = 1.6, z = AGENDA.z })
    if not d then return nil, 0 end
    if d.type == "Card" then return gm(d).id, 1 end
    local list = d.getObjects()
    return decode(list[#list].gm_notes).id, #list
  end
  local function hourButton()
    for _, b in ipairs(control().getButtons()) do
      if tostring(b.label):find("^Hour %d") then return tostring(b.label) end
    end
  end

  step("S-4: the Hours deck on the table follows the Control's Hour", function()
    local id, n = shownHour()
    check("Hour I shows on the agenda spot, the eight later Hours under it", id == "sthr-hour-1" and n == 9, tostring(id) .. " / " .. n)
    click(control(), hourButton()); E.run(1)
    id, n = shownHour()
    check("an advance shows Hour II, eight Hours in the deck", id == "sthr-hour-2" and n == 8, tostring(id) .. " / " .. n)
    check("Hour I is set aside, face down", find(function(o)
      if o.type == "Card" and gm(o).id == "sthr-hour-1" then return true end
      if o.type == "Deck" then
        for _, e in ipairs(o.getObjects()) do if decode(e.gm_notes).id == "sthr-hour-1" then return true end end
      end
      return false
    end) ~= nil)
    click(control(), hourButton(), true); E.run(1)
    id, n = shownHour()
    check("a rewind shows Hour I again, all nine Hours in the deck", id == "sthr-hour-1" and n == 9, tostring(id) .. " / " .. n)
  end)

  ----------------------------------------------------------------- S-5 --

  step("S-5: Begin Finale at Hour IX sets The Last Hour up from the log", function()
    local blob = decode(control().call("shApiSnapshot"))
    blob.campaign.partTwo = true
    blob.campaign.knowledge["the-way-the-night-breaks"] = true
    blob.campaign.knowledge["every-name-was-read"] = true
    blob.campaign.knowledge["the-light-is-kept"] = true
    blob.campaign.hourglass = 9
    control().call("shApiRestore", { blob = J.encode(blob) }); E.run(6)
    check("(the Hour is IX)", st().hour == 9, st().hour)
    local mark = chatMark()
    click(control(), "Begin Finale"); E.run(25)
    check("the finale has begun", st().finale == true)
    check("The Last Hour's box is laid out", boxEmpty("finale"))
    local function at(formId, locId)
      local f, l = card(formId), card(locId)
      return f ~= nil and l ~= nil and near(f.getPosition(), l.getPosition(), 1.2)
    end
    check("As It Was is at The First Occultation", at("sthr-form-past", "sthr-loc-firstoccultation"))
    check("As It Will Be is at The Morning After", at("sthr-form-future", "sthr-loc-morningafter"))
    check("As It Is is at The Square", at("sthr-form-present", "sthr-loc-hubsquare"))
    check("The Uninvited is on the table", card("sthr-uninvited") ~= nil)
    check("no district's act deck is left", find(function(o)
      return o.type == "Deck" and tostring(o.getName()):find("Act Deck", 1, true) ~= nil
    end) == nil)
    check("the Hourglass is set back to Hour V", st().hour == 5, st().hour)
    local id = shownHour()
    check("the Hours deck shows Hour V", id == "sthr-hour-5", tostring(id))
    check("the chat says the finale is set up", chatSince(mark):find("The Last Hour is set up", 1, true) ~= nil,
      chatSince(mark):sub(-800))
    check("...with the late records' damage", chatSince(mark):find("1 damage on As It Was, 1 on As It Will Be", 1, true) ~= nil,
      chatSince(mark):sub(-800))
  end)
end
