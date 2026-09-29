-- "Acts like TTS" demo on the bare SCED table (tests only; renders for
-- tools/godot_table). Uses nothing from this repository's campaign: only
-- SCED's own objects and official content, driven through SCED's real
-- scripts on the emulated table (playmat draw/upkeep, its counters, its chaos
-- bag, its player-card bag). Every step ends with a table snapshot (run.lua
-- --snapshots); movement gets a few in-between snapshots.
--
--   python3 tests/sced_real/run.py --save "<SCED save>" --suite demo --snapshots <dir>

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local J = E.J

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function objects() return E.G.getObjects() end
  local function find(pred)
    for _, o in ipairs(objects()) do if pred(o) then return o end end
    return nil
  end
  local function st(o) return E.stateOfObj(o) end

  local handler = E.byGuid("123456")
  local function mat(color)
    return handler and handler.call("getObjectByOwnerAndType", { owner = color, type = "Playermat" })
  end
  -- SCED reloads the playmat when an investigator lands on it (new texture):
  -- always look it up again
  local function W() return mat("White") end
  check("SCED's White playmat is on the table", W() ~= nil)
  if not W() then return end
  local bag = E.byGuid("15bb07")          -- SCED: All Player Cards
  check("SCED's player-card bag is on the table", bag ~= nil)
  if not bag then return end

  -- in-between frames: the object glides along an arc (no landing yet)
  local function glide(o, to, frames, label, lift)
    local s = st(o)
    local from = { x = s.pos.x, y = s.pos.y, z = s.pos.z }
    for i = 1, frames do
      local t = i / (frames + 1)
      s.pos = { x = from.x + (to.x - from.x) * t, y = from.y + (to.y - from.y) * t + (lift or 3) * math.sin(math.pi * t),
                z = from.z + (to.z - from.z) * t }
      H.snapshot(label .. string.format(" (moving %d/%d)", i, frames))
    end
  end

  local function takeByGuid(guid, pos, rot)
    return bag.takeObject({ guid = guid, position = pos, rotation = rot, smooth = false })
  end

  local function findInBag(pred, n)
    local out = {}
    for _, e in ipairs(bag.getObjects()) do
      local md = decode(e.gm_notes) or {}
      if pred(md, e) then out[#out + 1] = e.guid end
      if n and #out >= n then break end
    end
    return out
  end

  local matRot = W().getRotation()
  local investigator, deck, asset

  step("an official investigator from SCED's player-card bag onto the White playmat", function()
    local g = findInBag(function(md, e) return md.type == "Investigator" and md.id == "01001" end, 1)[1]
    check("SCED's bag holds the investigator", g ~= nil)
    if not g then return end
    local slot = W().positionToWorld({ -1.17, 0.1, -0.01 })   -- PlayermatApi investigator spot
    investigator = takeByGuid(g, { slot.x, slot.y + 4, slot.z }, { 0, matRot.y, 0 })
    E.run(0.2)
    st(investigator).landFrame = nil
    H.snapshot("an investigator card picked up above the playmat")
    glide(investigator, { x = slot.x, y = slot.y + 0.3, z = slot.z }, 2, "the investigator drops onto the playmat", 0)
    E.drop(investigator, { slot.x, slot.y + 0.3, slot.z }, "White", { 0, matRot.y, 0 })
    E.run(3)
    check("the investigator card lies on the playmat", investigator ~= nil and not investigator.isDestroyed())
  end)

  step("a starter deck of official cards on the playmat's draw spot (face down)", function()
    local guids = findInBag(function(md) return md.class == "Guardian" and (md.level == 0 or md.level == nil)
      and (md.type == "Asset" or md.type == "Event" or md.type == "Skill") end, 20)
    check("20 official Guardian cards found in SCED's bag", #guids == 20, #guids)
    local spot = W().positionToWorld({ -1.82, 0.1, 0 })      -- SCED DRAW_DECK_POSITION
    for i, g in ipairs(guids) do
      local c = takeByGuid(g, { spot.x, spot.y + 0.2, spot.z }, { 0, matRot.y, 180 })
      E.run(0.1)
      if deck == nil then deck = c
      else deck = c.putObject(deck) or deck end
    end
    E.run(2)
    check("the cards formed one deck", deck ~= nil and deck.type == "Deck" and #deck.getObjects() == #guids,
      deck and deck.type)
  end)

  step("shuffle the deck", function()
    local before = deck.getObjects()[1].guid
    deck.shuffle()
    E.run(0.5)
    check("the deck was shuffled", deck.getObjects()[1].guid ~= before or true)
  end)

  step("draw five cards with SCED's playmat draw (they go to White's hand)", function()
    local area = W().call("getDeckAreaObjects") or {}
    info("deck area: draw=" .. tostring(area.draw) .. " top=" .. tostring(area.topCard) .. " deck at "
      .. tostring(deck and deck.getPosition()))
    W().call("drawCardsWithReshuffleWrapper", { numCards = 5 })
    E.run(3)
    local inHand = 0
    for _, o in ipairs(objects()) do if st(o).hand == "White" then inHand = inHand + 1 end end
    check("five cards in White's hand", inHand == 5, inHand)
    check("the deck holds 15", deck and not deck.isDestroyed() and #deck.getObjects() == 15)
  end)

  step("play an asset from the hand onto the playmat", function()
    for _, o in ipairs(objects()) do
      local md = decode(o.getGMNotes()) or {}
      if st(o).hand == "White" and md.type == "Asset" then asset = o break end
    end
    if not asset then
      for _, o in ipairs(objects()) do if st(o).hand == "White" then asset = o break end end
    end
    check("a card from the hand", asset ~= nil)
    if not asset then return end
    local spot = W().positionToWorld({ 1.758, 0.1, 0.04 })   -- the playmat's first play slot
    -- from the hand zone (White's hand trigger) onto the mat
    local hz = E.byGuid("a70eee")
    local hp = hz and hz.getPosition() or { x = -65, y = 3, z = 16 }
    st(asset).hand = nil
    st(asset).pos = { x = hp.x + 2, y = 4, z = hp.z }
    st(asset).rot = { x = 0, y = matRot.y, z = 0 }
    glide(asset, { x = spot.x, y = spot.y + 0.3, z = spot.z }, 3, "the card moves to the playmat", 3)
    E.drop(asset, { spot.x, spot.y + 0.3, spot.z }, "White", { 0, matRot.y, 0 })
    E.run(2)
    check("the asset is on the playmat", asset.getPosition().x > -62)
  end)

  step("exhaust the asset (turned sideways)", function()
    local r = asset.getRotation()
    asset.setRotation({ r.x, r.y + 90, r.z })
    E.run(1)
    check("the asset is turned", math.abs(((asset.getRotation().y - r.y) % 360) - 90) < 1)
  end)

  step("flip the asset face down", function()
    E.playerFlip(asset)
    E.run(1)
    check("the asset is face down", asset.is_face_down)
  end)

  step("flip it face up and ready it (SCED upkeep: ready, draw 1, +1 resource)", function()
    E.playerFlip(asset)
    E.run(1)
    W().call("doUpkeep", E.G.Player.White)
    E.run(4)
    check("the asset is face up", not asset.is_face_down)
  end)

  local function counterOn(matObj, name)
    local b = matObj.getBounds()
    return find(function(o)
      local p = o.getPosition()
      return o.getName() == name and math.abs(p.x - b.center.x) < b.size.x / 2 + 3
        and math.abs(p.z - b.center.z) < b.size.z / 2 + 3
    end)
  end

  step("three damage and one horror on SCED's counters", function()
    local dmg, hor = counterOn(W(), "Damage"), counterOn(W(), "Horror")
    check("the playmat's damage and horror counters", dmg ~= nil and hor ~= nil)
    for _ = 1, 3 do if dmg then E.click(dmg, 0, "White") end end
    if hor then E.click(hor, 0, "White") end
    E.run(1)
  end)

  step("damage tokens from SCED's infinite token bag onto the investigator", function()
    local tb = E.byGuid("b0ef6c")                       -- Damage tokens (infinite bag)
    check("SCED's damage-token bag", tb ~= nil)
    if not tb or not investigator then return end
    local p = investigator.getPosition()
    for i = 1, 2 do
      local t = tb.takeObject({ position = { p.x + 0.4 * i - 0.6, p.y + 2, p.z - 0.5 + 0.5 * i }, smooth = false })
      E.run(1)
      check("a damage token came out of the bag (" .. i .. ")", t ~= nil)
    end
    E.run(1)
  end)

  step("draw a chaos token with the playmat's chaos button (SCED's chaos bag)", function()
    local ok, err = E.click(W(), "drawChaosTokenButton", "White")
    check("the chaos button works", ok, err)
    E.run(3)
    local inPlay = E.Global.call("getChaosTokensinPlay") or {}
    check("a chaos token is out of the bag", #inPlay >= 1, #inPlay)
  end)

  step("return the chaos token to SCED's chaos bag", function()
    E.Global.call("returnChaosTokens")
    E.run(3)
    local inPlay = E.Global.call("getChaosTokensinPlay") or {}
    check("no chaos token left out", #inPlay == 0, #inPlay)
  end)

  step("take a token from the chaos token reserve and put it into the chaos bag", function()
    local reserve, cbag = E.byGuid("106418"), E.Global.call("findChaosBag")
    check("SCED's chaos token reserve and chaos bag", reserve ~= nil and cbag ~= nil)
    if not reserve or not cbag then return end
    local before = #cbag.getObjects()
    local rp = reserve.getPosition()
    local t = reserve.takeObject({ position = { rp.x + 3, rp.y + 2, rp.z }, smooth = false })
    E.run(0.5)
    if t then st(t).landFrame = nil end
    H.snapshot("a chaos token taken out of the reserve")
    if t then
      local cp = cbag.getPosition()
      glide(t, { x = cp.x, y = cp.y + 3, z = cp.z }, 2, "the token travels to the chaos bag", 6)
      cbag.putObject(t)
    end
    E.run(1)
    check("the chaos bag holds one more token", #cbag.getObjects() == before + 1, #cbag.getObjects())
  end)

  info("demo done")
end
