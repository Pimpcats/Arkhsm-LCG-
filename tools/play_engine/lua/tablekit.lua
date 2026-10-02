-- The play engine's hands on the emulated table (designer tooling).
--
-- Everything the engine does to the game goes through here, and only
-- through what the owner touches at a real table: the Control token's and
-- the scenario boxes' buttons, the campaign log's boxes, SCED's playmat
-- buttons (encounter draw, chaos token draw), SCED's chaos bag, clue and
-- resource token bags, and picking cards/tokens up and putting them down.
-- Positions, spawns and draws are the real objects on the table; the rules
-- layer (rules.lua) only keeps what a player keeps in their head.

local T = {}

local E, J, H
local unpack = table.unpack or unpack

function T.init(h)
  H = h
  E = h.E
  J = E.J
  T.E, T.J = E, J
  T.errors = {}          -- engine-side problems worth reporting (not Lua errors)
end

------------------------------------------------------------------ basics --

function T.decode(s)
  if type(s) ~= "string" or s == "" then return nil end
  local ok, v = pcall(J.decode, s)
  return ok and type(v) == "table" and v or nil
end
function T.gm(o) return T.decode(o.getGMNotes()) or {} end
function T.alive(o) return o ~= nil and not o.isDestroyed() end
function T.objects() return E.G.getObjects() end
function T.find(pred) for _, o in ipairs(T.objects()) do if pred(o) then return o end end end
function T.findAll(pred)
  local l = {}
  for _, o in ipairs(T.objects()) do if pred(o) then l[#l + 1] = o end end
  return l
end
function T.dist(a, b) local dx, dz = a.x - b.x, a.z - b.z return math.sqrt(dx * dx + dz * dz) end
function T.run(s) E.run(s or 0.2) end

function T.note(msg) T.errors[#T.errors + 1] = msg end

function T.click(o, which, alt, color)
  if not o then T.note("click " .. tostring(which) .. ": no object") return false end
  local ok, err = E.click(o, which, color or "White", alt)
  if not ok then T.note("click '" .. tostring(which) .. "' on " .. tostring(o.getName()) .. ": " .. tostring(err)) end
  return ok, err
end

function T.hasLabel(o, prefix)
  for _, b in ipairs(o and o.getButtons() or {}) do
    if tostring(b.label):sub(1, #prefix) == prefix then return true end
  end
  return false
end

------------------------------------------------------------- the pieces --

function T.handler() return E.byGuid("123456") end
function T.owned(owner, typ)
  local h = T.handler()
  return h and h.call("getObjectByOwnerAndType", { owner = owner, type = typ })
end
function T.mat(color) return T.owned(color, "Playermat") end

T.MATS = { "White", "Orange", "Green", "Red" }

local controlObj
function T.control()
  if controlObj and T.alive(controlObj) then return controlObj end
  controlObj = T.find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  return controlObj
end
function T.st() return T.control().call("shApiState") end
function T.ctl(label, alt) return T.click(T.control(), label, alt) end
function T.api(name, p) return T.control().call(name, p) end

function T.campaign()
  local blob = T.decode(T.api("shApiSnapshot"))
  return blob and blob.campaign or {}
end
function T.knows(fact) return (T.campaign().knowledge or {})[fact] == true end

function T.log()
  return T.find(function(o) return o.hasTag("CampaignLog") and T.gm(o).type == "CampaignLog" end)
end

function T.scenarioBox(id)
  return T.find(function(o) local m = T.gm(o) return m.type == "ScenarioBox" and m.id == id end)
end

-- SCED's mythos mat spots (src/mythos/MythosArea.ttslua)
local MYTHOS = { agenda = { 0.056, 0.1, 0.251 }, act = { -0.777, 0.1, 0.251 },
                 encounter = { 0.88, 0.1, 0.391 }, discard = { 1.597, 0.1, 0.391 },
                 reference = { -1.6, 0.1, 0.37 },
                 -- where SCED's own "advance" puts a flipped agenda/act card
                 agendaAside = { 0.056, 0.1, 0.251 - 0.6 }, actAside = { -0.777, 0.1, 0.251 - 0.6 } }
function T.mythosSpot(key)
  local mat = E.byGuid("9f334f")
  return mat.positionToWorld(MYTHOS[key])
end

function T.playArea() return T.owned("Mythos", "PlayArea") end
function T.inPlayArea(o)
  local pa = T.playArea()
  if not pa then return nil end
  return pa.call("isInPlayArea", o)
end

------------------------------------------------------------ chaos bag --

function T.chaosBag() return E.Global.call("findChaosBag") end

--- Reveal one chaos token through SCED's own draw for this mat; returns
-- the token's name ("+1", "-2", "Skull", "Elder Sign", "Auto-fail", "Static", ...)
function T.drawToken(color)
  local tok = E.Global.call("drawChaosToken", { mat = color, drawAdditional = true })
  if not tok then
    -- SCED returns another mat's tokens first (and draws nothing): draw again
    E.run(0.1)
    tok = E.Global.call("drawChaosToken", { mat = color, drawAdditional = true })
  end
  E.run(0.1)
  if not tok then T.note("chaos token draw returned nothing") return "0", nil end
  return tok.getName(), tok
end
function T.returnTokens()
  E.Global.call("returnChaosTokens")
  E.run(0.1)
end
function T.bagNames()
  local l = {}
  for _, e in ipairs(T.chaosBag().getObjects()) do l[#l + 1] = e.name or e.nickname end
  return l
end

------------------------------------------------------------- the Control --

function T.dissonance(delta)
  for _ = 1, math.abs(delta) do T.ctl("Dissonance", delta < 0) end
  E.run(0.1)
end

function T.setInvestigators(n)
  local cur = T.st().investigators
  for _ = 1, math.abs(cur - n) do T.ctl("Investigators", cur > n) end
  -- SCED's own investigator counter (clues per investigator)
  local counter = T.owned("Mythos", "InvestigatorCounter")
  if counter then counter.call("updateVal", n) end
  E.run(0.5)
end

function T.difficulty(label)
  T.ctl(label)
  E.run(3)
end

------------------------------------------------------------ the log --

local function logPage(n)
  local log = T.log()
  if not log then return nil end
  local v = log.call("getLogValues")
  if v and v.page ~= n then
    E.menu(log, "Next page")
    E.run(0.5)
    return logPage(n)
  end
  return log
end
T.logPage = logPage

--- Tick (or clear) a box on the log's second page, as the owner does:
-- a Knowledge box records the entry on the Control (and pays its Memory),
-- a Victory box banks the Victory.
function T.tickLog(key, want)
  local log = logPage(2)
  if not log then T.note("no campaign log") return false end
  local cur = (log.call("getLogValues").values or {})[key] == true
  if want == nil then want = true end
  if cur == want then return true end
  for i, f in ipairs(log.getVar("FIELDS") or {}) do
    if f.k == key then
      local ok = T.click(log, "sthrLog_" .. i)
      E.run(0.2)
      return ok
    end
  end
  T.note("the campaign log has no box " .. key)
  return false
end

--- Set a log field without side effects (scenario setup only).
function T.setLog(key, value)
  local log = logPage(2)
  if log then log.call("setLogValue", { key = key, value = value }) end
end
function T.logValues()
  local log = logPage(2)
  return log and (log.call("getLogValues").values or {}) or {}
end

------------------------------------------------------------ boxes --

function T.boxTag(box) return "StillHourBox:" .. box.getGUID() end
function T.placedBy(box) return T.findAll(function(o) return o.hasTag(T.boxTag(box)) end) end

function T.placeBox(id)
  local box = T.scenarioBox(id)
  if not box then T.note("no scenario box " .. id) return nil end
  T.click(box, "Place")
  E.run(3)
  return box
end

function T.deckNamed(suffix, box)
  return T.find(function(o)
    return (o.type == "Deck" or o.type == "Card") and tostring(o.getName()):sub(-#suffix) == suffix
      and (not box or o.hasTag(T.boxTag(box)))
  end)
end

------------------------------------------------------------ cards --

function T.cardWithId(id)
  return T.find(function(o) return o.type == "Card" and T.gm(o).id == id end)
end
function T.cardsWithId(id)
  return T.findAll(function(o) return o.type == "Card" and T.gm(o).id == id end)
end

--- Take the card with this metadata id out of a deck (by GUID), or find it loose.
function T.takeCard(id, pos, rot)
  local loose = T.cardWithId(id)
  if loose then
    if pos then loose.setPosition(pos) end
    if rot then loose.setRotation(rot) end
    return loose
  end
  for _, d in ipairs(T.findAll(function(o) return o.type == "Deck" end)) do
    for _, e in ipairs(d.getObjects()) do
      local md = T.decode(e.gm_notes)
      if md and md.id == id then
        local c = d.takeObject({ guid = e.guid, position = pos, rotation = rot, smooth = false })
        E.run(0.1)
        return c
      end
    end
  end
  return nil
end

--- Put a card on a pile at pos (merging into the card/deck lying there).
function T.putOnPile(card, pos, faceUp)
  local pile = T.find(function(o)
    return o ~= card and (o.type == "Card" or o.type == "Deck") and T.dist(o.getPosition(), pos) < 0.5
  end)
  local r = card.getRotation()
  card.setRotation({ 0, r.y, faceUp and 0 or 180 })
  if pile then
    pile.putObject(card)
  else
    card.setPosition({ pos.x, pos.y + 0.3, pos.z })
  end
  E.run(0.1)
end

------------------------------------------------------------ tokens --

-- clue tokens SCED put on a card (Tiles marked "clueDoom", clue side up)
function T.tokensOn(card, memo)
  local l = {}
  if not T.alive(card) then return l end
  local b = E.aabb(card)
  for _, o in ipairs(T.objects()) do
    if (o.type == "Tile" or o.type == "Generic" or o.type == "Chip") and (memo == nil or o.memo == memo) then
      local p = o.getPosition()
      if p.x >= b.min.x and p.x <= b.max.x and p.z >= b.min.z and p.z <= b.max.z and p.y >= b.center.y - 0.05 then
        l[#l + 1] = o
      end
    end
  end
  return l
end
function T.cluesOn(card)
  local l = {}
  for _, o in ipairs(T.tokensOn(card, "clueDoom")) do
    if not o.is_face_down then l[#l + 1] = o end
  end
  return l
end

--- A clue token taken from the SCED clue token bag (the token pool), placed on a card.
local cluePool
function T.spawnClueOn(card, n)
  cluePool = cluePool and T.alive(cluePool) and cluePool or E.byGuid("fae2f6")
  if not cluePool then T.note("no clue token bag") return 0 end
  local p = card.getPosition()
  for i = 1, n do
    local t = cluePool.takeObject({ position = { p.x - 0.6 + 0.4 * ((i - 1) % 4), p.y + 0.5, p.z - 0.4 + 0.4 * math.floor((i - 1) / 4) },
      smooth = false })
    if t then t.memo = "clueDoom" end
  end
  E.run(0.2)
  return n
end

--- A clue token moves from a location to the investigator's playmat.
function T.moveClueToMat(tok, color, k)
  local mat = T.mat(color)
  local p = mat.positionToWorld({ -1.17 + 0.25 * ((k or 0) % 4), 0.3, 0.45 + 0.2 * math.floor((k or 0) / 4) })
  tok.setPosition({ p.x, p.y + 0.2, p.z })
end

------------------------------------------------------------ encounter --

function T.encounterDeck()
  local pos = T.mythosSpot("encounter")
  return T.find(function(o) return (o.type == "Deck" or o.type == "Card") and T.dist(o.getPosition(), pos) < 0.8 end)
end
function T.encounterDiscard()
  local pos = T.mythosSpot("discard")
  return T.find(function(o) return (o.type == "Deck" or o.type == "Card") and T.dist(o.getPosition(), pos) < 0.8 end)
end
function T.deckCount(o)
  if not o then return 0 end
  if o.type == "Deck" then return #o.getObjects() end
  return 1
end

-- Preserve card identities, metadata and images while changing only encounter
-- order. This is designer tooling using the same object-data API as setup.
local function replaceEncounterOrder(deck, data)
  data.DeckIDs = {}
  for _, c in ipairs(data.ContainedObjects or {}) do data.DeckIDs[#data.DeckIDs+1] = c.CardID end
  deck.destruct()
  E.run(0.1)
  local obj = E.spawnData(data, {}, "campaign")
  E.run(0.1)
  return obj
end
function T.reorderEncounterTop(n, score)
  local deck=T.encounterDeck()
  if not deck or deck.type~="Deck" then return false end
  local data=deck.getData()
  local top={}
  for i=1,math.min(n,#data.ContainedObjects) do top[#top+1]={card=data.ContainedObjects[i],index=i} end
  table.sort(top,function(a,b)
    local sa,sb=score(T.decode(a.card.GMNotes) or {}),score(T.decode(b.card.GMNotes) or {})
    if sa==sb then return a.index<b.index end
    return sa<sb
  end)
  for i,c in ipairs(top) do data.ContainedObjects[i]=c.card end
  replaceEncounterOrder(deck,data)
  return true
end
function T.moveTopEncounterBottom()
  local deck=T.encounterDeck()
  if not deck or deck.type~="Deck" then return false end
  local data=deck.getData()
  local card=table.remove(data.ContainedObjects,1)
  if not card then return false end
  data.ContainedObjects[#data.ContainedObjects+1]=card
  replaceEncounterOrder(deck,data)
  return true
end

--- Draw an encounter card through the playmat's own button (SCED
-- MythosArea.drawEncounterCard, which reshuffles the discard pile when the
-- deck is empty). Returns the card object and whether a reshuffle happened.
function T.drawEncounter(color)
  local deckBefore = T.deckCount(T.encounterDeck())
  local reshuffled = deckBefore == 0
  local mat = T.mat(color)
  local pos = mat.positionToWorld({ 1.365, 0.5, -0.625 })
  -- SCED stacks left-click draws at one spot. A weakness already there can
  -- turn the arriving encounter into a Deck, and the final encounter card
  -- can be an existing object moved from the source rather than a new one.
  -- Remember identities already at the destination, including pile contents.
  local before = {}
  for _, o in ipairs(T.objects()) do
    if (o.type == "Card" or o.type == "Deck") and T.dist(o.getPosition(), pos) < 1.2 then
      before[o.getGUID()] = true
      if o.type == "Deck" then
        for _, entry in ipairs(o.getObjects()) do before[entry.guid] = true end
      end
    end
  end
  T.click(mat, "drawEncounterCard", false, color)
  local card
  local function findDrawn()
    for _, o in ipairs(T.objects()) do
      if T.dist(o.getPosition(), pos) < 1.2 then
        if o.type == "Card" and not before[o.getGUID()] then card = o return true end
        if o.type == "Deck" then
          for _, entry in ipairs(o.getObjects()) do
            if not before[entry.guid] then
              card = o.takeObject({ guid = entry.guid,
                position = { pos.x, pos.y + 2, pos.z }, smooth = false })
              if card then return true end
            end
          end
        end
      end
    end
    return false
  end
  E.runUntil(findDrawn, 3)
  E.run(0.1)
  return card, reshuffled
end

function T.discardEncounter(card)
  if not T.alive(card) then return end
  -- tokens left on it go back to the pool (SCED removes tokens from cards entering the discard area)
  T.putOnPile(card, T.mythosSpot("discard"), true)
end

--- Shuffle a (set-aside) deck or card into the encounter deck.
function T.shuffleIntoEncounter(obj)
  local enc = T.encounterDeck()
  if not enc then T.note("no encounter deck to shuffle into") return end
  local r = obj.getRotation()
  obj.setRotation({ 0, r.y, 180 })
  E.playerPut(enc, obj)
  E.run(0.2)
  enc = T.encounterDeck()
  if enc and enc.type == "Deck" then enc.shuffle() end
end

--- Search the encounter deck and discard pile for a card with this id
-- (e.g. "search the encounter deck ... for an Echo enemy").
function T.searchEncounter(pred)
  for _, pile in ipairs({ T.encounterDeck(), T.encounterDiscard() }) do
    if pile then
      if pile.type == "Card" then
        local md = T.gm(pile)
        if pred(md) then return pile end
      else
        for _, e in ipairs(pile.getObjects()) do
          local md = T.decode(e.gm_notes)
          if md and pred(md) then
            local p = pile.getPosition()
            local c = pile.takeObject({ guid = e.guid, position = { p.x, p.y + 2, p.z }, smooth = false })
            E.run(0.1)
            return c
          end
        end
      end
    end
  end
  return nil
end

------------------------------------------------------------ minicards --

function T.minicard(id)
  local want = id .. "-m"
  local loose = T.find(function(o) return o.type == "Card" and o.hasTag("Minicard") and T.gm(o).id == want end)
  if loose then return loose end
  local deck = T.find(function(o) return o.type == "Deck" and o.hasTag("Minicard") end)
  if not deck then return nil end
  for _, e in ipairs(deck.getObjects()) do
    if (T.decode(e.gm_notes) or {}).id == want then
      local p = deck.getPosition()
      local m = deck.takeObject({ guid = e.guid, position = { p.x, p.y + 2, p.z }, smooth = false })
      E.run(0.1)
      return m
    end
  end
  return nil
end

--- Minicard onto a location card (slot k spreads several investigators).
function T.moveMini(mini, loc, k)
  local p = loc.getPosition()
  E.drop(mini, { p.x - 0.9 + 0.6 * ((k or 1) - 1), p.y + 0.3, p.z + 0.55 })
end

return T
