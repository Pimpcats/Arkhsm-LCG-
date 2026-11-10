-- The effects table for The Dunwich Legacy's opening pair (designer tooling):
-- every card SCED's scenario boxes "1a: Extracurricular Activity" and "1b: The
-- House Always Wins" hold, keyed by card id, encoded from the card text in
-- ArkhamDB's data (tools/play_engine/official/dwl_data.py). Numbers (shroud,
-- fight, health, clue thresholds, doom) come from that data or the table,
-- never from here. COVERAGE says per card whether its text is encoded in full
-- or approximated (and how). Plays the role lua/effects.lua plays for The
-- Still Hour, behind the same interface (R.FX), plus the hooks the official
-- mode adds (extraOptions, canInvestigate, investigateExtra, fightPenalty,
-- canEnter, onReveal, aloof, agendaThreshold, advanceAgenda, allGone).

return function(R, T)
  local E = T.E
  local FX = {}
  R.FX = FX

  local COVERAGE = {}
  FX.COVERAGE = COVERAGE
  local function cov(id, how) COVERAGE[id] = how or "full" end
  local ENC = {}
  FX.ENC = ENC
  local ACTS = {}
  FX.ACTS = ACTS
  FX.STORY = {}
  FX.FARE_RATE = 3

  local ID = {
    -- 1a Extracurricular Activity
    scen1a = "02041", quiet = "02042", deadnight = "02043", beast = "02044", afterhours = "02045", rice_act = "02046",
    campus = "02047", quad = "02048", humanities = "02049", orne = "02050", union = "02051", dorms = "02052",
    admin = "02053", faculty = "02054", facultyLate = "02055", science = "02056", labs = "02057", experiment = "02058",
    concoction = "02059", jazz = "02060", rice = "02061", armitage = "02040",
    -- 1b The House Always Wins
    scen1b = "02062", clover = "02063", muscle = "02064", chaos = "02065", luck = "02066", skin = "02067", allin = "02068",
    fold = "02069", bella = "02070", lounge = "02071", bar = "02072", cardroom = "02073", darkened = "02074",
    gallery = "02075", vip = "02076", alley = "02077", pitboss = "02078", peter = "02079", morgan = "02080",
  }
  FX.ID = ID

  -- scenario structure: agenda deck, act deck, starting location
  local SC = {
    ["1a"] = { agendas = { ID.quiet, ID.deadnight, ID.beast }, acts = { ID.afterhours, ID.rice_act, ID.campus },
               start = ID.quad, reference = ID.scen1a },
    ["1b"] = { agendas = { ID.clover, ID.muscle, ID.chaos }, acts = { ID.luck, ID.skin, ID.allin },
               start = ID.bella, reference = ID.scen1b },
  }
  FX.SC = SC

  local function G() return R.G end
  local function n() return R.G.n end
  local function cur() return R.G.scen end
  local function horror(inv, k, why) R.hurt(inv, 0, k, why) end
  local function hasThreat(inv, name) return inv.threat and inv.threat[name] ~= nil end
  local function note(fmt, ...) R.log(fmt, ...) end

  ------------------------------------------------------------ helpers on the table --

  -- set-aside cards wait in an aside zone beside the table (x > 60), out of play
  local ASIDE_X = 70
  FX.ASIDE_X = ASIDE_X
  local function asidePos(k) return { ASIDE_X + 3 * (k % 8), 2, -24 + 4 * math.floor(k / 8) } end
  FX.asidePos = asidePos

  --- A card by id from the aside zone (or any deck on the table), into play at pos.
  local function take(id, pos, faceDown)
    local c = T.takeCard(id, pos, { 0, 270, faceDown and 180 or 0 })
    if c then
      c.setPosition(pos)
      c.setRotation({ 0, 270, faceDown and 180 or 0 })
      E.run(0.1)
    end
    return c
  end
  FX.take = take

  local function locIn(id) return R.locById(id) end
  local LAYOUT = {
    -- where a set-aside location enters play: beside the location it connects to
    [ID.dorms] = { ID.union, -6.55, 0 }, [ID.faculty] = { ID.admin, -6.55, 0 }, [ID.facultyLate] = { ID.admin, -6.55, 0 },
    [ID.labs] = { ID.science, 6.55, 0 }, [ID.darkened] = { ID.cardroom, -6.55, 0 },
    [ID.gallery] = { ID.darkened, -6.55, -7.66 }, [ID.vip] = { ID.darkened, -6.55, 0 }, [ID.alley] = { ID.darkened, -6.55, 7.66 },
  }
  --- Put a set-aside location into play (unrevealed).
  local function putLocation(id)
    if locIn(id) then return locIn(id) end
    local spec = LAYOUT[id]
    local near = spec and locIn(spec[1])
    local p = near and near.obj.getPosition() or { x = -30, y = 1.6, z = 0 }
    local c = take(id, { p.x + (spec and spec[2] or 0), 1.7, p.z + (spec and spec[3] or 0) }, false)
    if not c then T.note("set-aside location " .. id .. " not found") return nil end
    R.scanLocations()
    note("%s enters play", R.card(id).name)
    return locIn(id)
  end
  FX.putLocation = putLocation
  FX.LAYOUT = LAYOUT

  --- Remove a location from the game (its investigators and enemies were moved first).
  function FX.removeLocation(L)
    local G = R.G
    for _, tok in ipairs(T.cluesOn(L.obj)) do tok.destruct() end
    L.obj.setPosition(asidePos(30 + (G.removedCount or 0)))
    G.removedCount = (G.removedCount or 0) + 1
    G.locs[L.guid] = nil
    R.scanLocations()
  end

  local function enemiesWith(pred)
    local l = {}
    for _, en in ipairs(R.G.enemies) do if not en.dead and pred(en) then l[#l + 1] = en end end
    return l
  end
  local function enemyById(id) for _, en in ipairs(R.G.enemies) do if en.id == id and not en.dead then return en end end end
  FX.enemyById = enemyById

  --- Discard an enemy (not defeated): to the encounter discard pile.
  local function discardEnemy(en, why)
    local G = R.G
    en.dead = true
    for i, x in ipairs(G.enemies) do if x == en then table.remove(G.enemies, i) break end end
    note("%s is discarded (%s)", en.name, why or "?")
    if T.alive(en.obj) then T.discardEncounter(en.obj) end
  end

  --- Gain clues from the token pool (onto the investigator's playmat).
  local cluePool
  local function gainClues(inv, k, why)
    cluePool = cluePool and T.alive(cluePool) and cluePool or E.byGuid("fae2f6")
    for _ = 1, k do
      local t = cluePool and cluePool.takeObject({ position = { 0, 3, 0 }, smooth = false })
      if t then
        t.memo = "clueDoom"
        T.moveClueToMat(t, inv.color, #inv.clueTokens)
        inv.clueTokens[#inv.clueTokens + 1] = t
      end
      inv.clues = inv.clues + 1
    end
    E.run(0.1)
    R.G.metrics.clues = R.G.metrics.clues + k
    R.G.metrics.clues_by_round[R.G.round] = (R.G.metrics.clues_by_round[R.G.round] or 0) + k
    R.G.metrics.clues_gained_other = (R.G.metrics.clues_gained_other or 0) + k
    note("%s gains %d clue(s) (%s)", inv.name, k, why or "?")
    FX.afterGainClues(inv, R.locOf(inv))
  end
  FX.gainClues = gainClues

  --- Discard the top k cards of an investigator's deck (returns them); Beyond the Veil checks.
  function FX.mill(inv, k, why)
    local out = {}
    for _ = 1, k do
      if #inv.deck == 0 then break end
      local c = table.remove(inv.deck)
      inv.discard[#inv.discard + 1] = c
      out[#out + 1] = c
    end
    R.G.metrics.milled = (R.G.metrics.milled or 0) + #out
    if #out > 0 then note("%s discards %d card(s) from the deck (%s): %d left", inv.name, #out, why or "?", #inv.deck) end
    FX.checkEmptyDeck(inv)
    return out
  end
  --- Beyond the Veil: "Forced - If your deck has no cards in it: Take 10 damage and discard Beyond the Veil."
  function FX.checkEmptyDeck(inv)
    if inv.defeated or #inv.deck > 0 or not hasThreat(inv, "Beyond the Veil") then return end
    local c = inv.threat["Beyond the Veil"]
    inv.threat["Beyond the Veil"] = nil
    if c and c.obj and T.alive(c.obj) then T.discardEncounter(c.obj) end
    R.G.metrics.beyond_the_veil = (R.G.metrics.beyond_the_veil or 0) + 1
    note("Beyond the Veil: %s's deck is empty", inv.name)
    R.hurt(inv, 10, 0, "Beyond the Veil")
  end

  --- Draw (move) the top encounter card through the playmat, for "discard the top X" effects.
  local function topEncounter(inv)
    local card = T.drawEncounter(inv.color)
    if not card then return nil end
    return card, T.gm(card).id
  end

  --- Reveal a chaos token outside a skill test (not a test: no commits, no token effects).
  local rawDraw = T.drawToken
  FX.rawDraw = rawDraw
  local function revealRandom(inv)
    local name = rawDraw(inv.color)
    T.returnTokens()
    R.touch()
    R.G.metrics.tokens[name] = (R.G.metrics.tokens[name] or 0) + 1
    return name
  end
  FX.revealRandom = revealRandom
  local SYMBOL = { Skull = true, Cultist = true, Tablet = true, ["Elder Thing"] = true, ["Auto-fail"] = true }
  FX.SYMBOL = SYMBOL

  --- Attached encounter cards: { id, obj, at = location guid | "agenda" | "act" | inv }
  local function attach(card, at)
    local G = R.G
    G.attached[#G.attached + 1] = { id = T.gm(card).id, obj = card, at = at }
    local p
    if type(at) == "string" and G.locs[at] then p = G.locs[at].obj.getPosition() ; card.setPosition({ p.x + 0.9, p.y + 0.3, p.z - 1.2 })
    elseif at == "agenda" then p = T.mythosSpot("agenda") ; card.setPosition({ p.x, p.y + 0.3, p.z - 1.3 })
    elseif at == "act" then p = T.mythosSpot("act") ; card.setPosition({ p.x, p.y + 0.3, p.z - 1.3 }) end
    return "keep"
  end
  local function attachedAt(at, id)
    local l = {}
    for _, a in ipairs(R.G.attached) do if a.at == at and (not id or a.id == id) then l[#l + 1] = a end end
    return l
  end
  FX.attachedAt = attachedAt
  local function detach(a)
    local G = R.G
    for i, x in ipairs(G.attached) do if x == a then table.remove(G.attached, i) break end end
    if T.alive(a.obj) then T.discardEncounter(a.obj) end
  end
  FX.detach = detach

  --- Shuffle a card or deck into the encounter deck (it becomes the deck when the deck is empty).
  local function shuffleIn(obj)
    if not obj then return end
    if T.encounterDeck() then T.shuffleIntoEncounter(obj) return end
    local p = T.mythosSpot("encounter")
    obj.setPosition({ p.x, p.y + 0.3, p.z })
    obj.setRotation({ 0, 270, 180 })
    E.run(0.2)
    local d = T.encounterDeck()
    if d and d.type == "Deck" then d.shuffle() end
  end
  FX.shuffleIn = shuffleIn
  FX.attach, FX.discardEnemy = attach, discardEnemy
  --- Shuffle the encounter discard pile into the encounter deck.
  local function shuffleDiscardIn()
    local d = T.encounterDiscard()
    if d then shuffleIn(d) end
  end
  FX.shuffleDiscardIn = shuffleDiscardIn

  ------------------------------------------------------------ scenario reference cards --

  cov(ID.scen1a, "full (Standard side); the [elder_thing] modifier is the discarded cards' printed cost (the AI estimates it before the reveal)")
  cov(ID.scen1b, "full (Standard side); a [skull] is treated as 0 for 2 resources only when that turns a failure into a success")

  local function deckCostEstimate(inv)
    local s, k = 0, 0
    for _, c in ipairs(inv.deck) do s = s + (tonumber(c.cost) or 0) ; k = k + 1 end
    return k > 0 and 2 * s / k or 0
  end
  function FX.tokenValue(name, inv)
    local G = R.G
    if name == "Auto-fail" then return nil end
    if name == "Elder Sign" then return R.P.elderSign(inv) end
    local v = tonumber(name)
    if v then return v end
    local s = cur()
    if name == "Skull" then
      if inv and inv.id == "02004" then return 0 end            -- Jim Culver: [skull] modifier is 0
      return s == "1a" and -1 or -2
    end
    if s == "1a" then
      if name == "Cultist" then return (#(inv and inv.discard or {}) >= 10) and -3 or -1 end
      if name == "Elder Thing" then
        local p = G.pendingET
        if p and p.inv == inv and p.name == name then
          if not p.value then
            local milled = FX.mill(inv, 2, "[elder_thing] token")
            local x = 0
            for _, c in ipairs(milled) do x = x + (tonumber(c.cost) or 0) end
            p.value = -x
          end
          return p.value
        end
        return -math.floor(deckCostEstimate(inv) + 0.5)
      end
      return 0                                                   -- not on this scenario's card
    else
      if name == "Cultist" then return -3 end
      if name == "Tablet" then return -2 end
      return 0
    end
  end
  function FX.tokenAfter(name, inv, success, test, margin)
    local G = R.G
    inv.lastToken = name
    G.pendingET = nil
    local s = cur()
    if s == "1a" and name == "Skull" and not success then FX.mill(inv, 3, "[skull] token") end
    if s == "1b" and name == "Cultist" and success then inv.resources = inv.resources + 3 end
    if s == "1b" and name == "Tablet" and not success then inv.resources = math.max(0, inv.resources - 3) end
    if name == "Skull" then R.P.trumpet(inv) end
  end
  -- the actual [elder_thing] value is taken when it is revealed during a test
  T.drawToken = function(color)
    local name, tok = rawDraw(color)
    for _, x in ipairs(R.G.inv) do
      if x.color == color then R.G.pendingET = { inv = x, name = name } end
    end
    return name, tok
  end

  ------------------------------------------------------------ locations --

  cov(ID.quad, "full; the AI never resigns in Extracurricular Activity (the no-resolution path is reached by defeat only)")
  cov(ID.humanities) ; cov(ID.orne) ; cov(ID.union) ; cov(ID.dorms) ; cov(ID.admin) ; cov(ID.science) ; cov(ID.labs)
  cov(ID.faculty) ; cov(ID.facultyLate)
  cov(ID.bella, "full; the AI resigns when its act 3 objective is done or the last agenda is about to advance")
  cov(ID.lounge) ; cov(ID.bar) ; cov(ID.cardroom, "full; the AI never \"cheats\" with Beginner's Luck unless the run asks it to")
  cov(ID.darkened) ; cov(ID.gallery) ; cov(ID.vip) ; cov(ID.alley, "full; see La Bella Luna")

  --- Locked doors: "You cannot move into X" on the unrevealed side; "Jazz" Mulligan's controller ignores it.
  local LOCKED = { [ID.dorms] = true, [ID.faculty] = true, [ID.facultyLate] = true, [ID.labs] = true }
  function FX.controlsJazz(inv) return inv and R.P.findAssetId(inv, ID.jazz) ~= nil end
  function FX.canEnter(inv, L)
    if LOCKED[L.id] and not L.revealed and not FX.controlsJazz(inv) then return false end
    return true
  end

  function FX.onEnter(inv, L)
    local G = R.G
    G.enteredThisTurn[L.id] = true
  end

  function FX.onReveal(L)
    local G = R.G
    if L.id == ID.union then putLocation(ID.dorms) end
    if L.id == ID.science then putLocation(ID.labs) end
    if L.id == ID.admin then putLocation(G.camp.otherDone and ID.facultyLate or ID.faculty) end
    if L.id == ID.darkened then
      for _, id in ipairs({ ID.gallery, ID.vip, ID.alley }) do putLocation(id) end
    end
    if L.id == ID.faculty then
      -- search the encounter deck and discard pile for a [[Humanoid]] enemy and spawn it here
      local c = T.searchEncounter(function(md) local d = R.card(md.id) return d.type == "Enemy" and R.hasTrait(d, "Humanoid") end)
      local deck = T.encounterDeck()
      if deck and deck.type == "Deck" then deck.shuffle() end
      if c then R.spawnEnemy(c, L, R.investigatorsAt(L)[1], { want = "Faculty Offices" }) end
    end
  end

  --- Locked Door: the attached location cannot be investigated.
  function FX.canInvestigate(inv, L)
    return #attachedAt(L.guid, "01174") == 0
  end
  --- Orne Library: you must spend 1 additional action to investigate it.
  function FX.investigateExtra(inv, L) return (L.id == ID.orne) and 1 or 0 end

  function FX.locationAbilities() return {} end
  function FX.townHallFree() end
  function FX.fastRoute() return nil end
  function FX.useFastRoute() end
  function FX.freeCrossingAvailable() return false end
  function FX.freeCrossing() return false end
  function FX.climb() end
  function FX.cannotBeDamaged() return false end
  function FX.storyHolder() return nil end
  function FX.registerCancels() return false end
  function FX.afterFail() end
  function FX.onEvade() end
  function FX.onSpawn(en) end

  --- After an investigator gains clues at a location (discovers or takes from the pool).
  function FX.afterGainClues(inv, L)
    local G = R.G
    if G.ended or not L then return end
    -- Clover Club Pit Boss: readies, engages that investigator, and makes an immediate attack
    for _, en in ipairs(enemiesWith(function(e) return e.id == ID.pitboss and e.loc == L.guid end)) do
      en.exhausted = false
      en.engaged = inv
      R.placeEnemy(en)
      note("Clover Club Pit Boss engages %s", inv.name)
      R.enemyAttack(en, inv, "Pit Boss (Forced)")
      if G.ended or inv.defeated then return end
    end
  end
  function FX.afterDiscover(inv, L)
    FX.afterGainClues(inv, L)
    -- Professor Warren Rice: after you discover the last remaining clue at your location, exhaust: draw 1 card
    local rice = R.P.findAssetId(inv, ID.rice)
    if rice and not rice.exhausted and L and R.clues(L) == 0 then rice.exhausted = true ; R.P.draw(inv, 1) end
  end

  ------------------------------------------------------------ agendas --

  cov(ID.quiet) ; cov(ID.deadnight, "full; the hand size of 5 is checked at the end of the upkeep phase")
  cov(ID.beast)
  cov(ID.clover) ; cov(ID.muscle) ; cov(ID.chaos)

  function FX.aloof(en)
    -- The Clover Club: each [[Criminal]] enemy gains Aloof
    return R.agendaId() == ID.clover and R.hasTrait(en.def, "Criminal")
  end
  function FX.fightPenalty(inv, en)
    -- hitting a Criminal while the Clover Club is the agenda advances it at once: a careful party weighs the
    -- doom it would lose, unless that enemy is about to defeat the investigator
    if not FX.aloof(en) then return 0 end
    if (inv.health - inv.damage) <= 2 * (en.def.damage or 0) + 1 then return 0 end
    return math.min(25, 6 * math.max(0, R.threshold() - R.doomInPlay()))
  end
  function FX.allDirect()
    for _, a in ipairs(R.G.attached) do if a.id == "02085" then return true end end
    return false
  end

  local function experiment() return enemyById(ID.experiment) end
  local function spawnSetAside(id, L, why)
    local c = take(id, { L.obj.getPosition().x, 2, L.obj.getPosition().z + 2.4 }, false)
    if not c then T.note("set-aside enemy " .. id .. " not found") return nil end
    return R.spawnEnemy(c, L, nil, { want = why })
  end
  local function moveExperiment()
    local en, dorms = experiment(), locIn(ID.dorms)
    if en and dorms then R.enemyStepToward(en, dorms) end
  end

  local AGENDA_BACK = {}
  FX.AGENDA_BACK = AGENDA_BACK
  AGENDA_BACK[ID.quiet] = function()
    for _, inv in ipairs(R.aliveInvs()) do
      local k = (#inv.discard >= 10) and 2 or (#inv.discard >= 5 and 1 or 0)
      if k > 0 then horror(inv, k, "Quiet Halls") end
    end
  end
  AGENDA_BACK[ID.deadnight] = function()
    putLocation(ID.dorms)
    if experiment() then moveExperiment()
    else
      local sci = locIn(ID.science)
      if sci then spawnSetAside(ID.experiment, sci, "Science Building") end
    end
  end
  AGENDA_BACK[ID.beast] = function()
    for _, inv in ipairs(R.aliveInvs()) do horror(inv, 3, "The Beast Unleashed") end
    FX.resolve("R4")
  end
  AGENDA_BACK[ID.clover] = function() shuffleDiscardIn() end
  AGENDA_BACK[ID.muscle] = function()
    local G = R.G
    local lounge, bella = locIn(ID.lounge), locIn(ID.bella)
    -- spawn a random enemy from the set-aside Hideous Abominations in the Clover Club Lounge
    local ab = G.asideDecks["Hideous Abominations"] or {}
    if #ab > 0 and lounge then
      local k = math.floor(R.rand() * #ab) + 1
      local id = table.remove(ab, k)
      spawnSetAside(id, lounge, "Clover Club Lounge")
    end
    -- shuffle the rest of that set, Striking Fear and the discard pile into the encounter deck
    for _, set in ipairs({ "Hideous Abominations", "Striking Fear" }) do
      for _, id in ipairs(G.asideDecks[set] or {}) do
        shuffleIn(T.takeCard(id, asidePos(40)))
      end
      G.asideDecks[set] = {}
    end
    shuffleDiscardIn()
    -- move all investigators and unengaged enemies from La Bella Luna to the Lounge; remove La Bella Luna
    if bella and lounge then
      for _, inv in ipairs(R.investigatorsAt(bella)) do R.moveInv(inv, lounge, { teleport = true, noAoO = true }) end
      for _, en in ipairs(G.enemies) do if en.loc == bella.guid and not en.engaged then en.loc = lounge.guid ; R.placeEnemy(en) end end
      FX.removeLocation(bella)
    end
  end
  AGENDA_BACK[ID.chaos] = function() FX.resolve("R4") end   -- R4's steps (the guide data) give the trauma

  --- The agenda advances: its back resolves, the next agenda becomes current.
  function FX.advanceAgenda(why)
    local G = R.G
    if G.ended then return end
    local A = G.agenda
    local id = A.list[A.i]
    G.metrics.agendas = G.metrics.agendas or {}
    G.metrics.agendas[#G.metrics.agendas + 1] = { id = id, round = G.round, why = why }
    note("AGENDA ADVANCES: %s (%s)", R.card(id).name or id, why or "?")
    R.removeAllDoom()
    for _, a in ipairs(attachedAt("agenda")) do detach(a) end
    -- Sordid and Silent etc. are not in these sets
    A.i = A.i + 1
    AGENDA_BACK[id]()
    if G.ended then return end
    -- "If the players have completed <the other scenario>, advance directly to agenda 2b"
    if A.i == 2 and G.camp.otherDone and (cur() == "1a" or cur() == "1b") then
      local skip = A.list[2]
      G.metrics.agendas[#G.metrics.agendas + 1] = { id = skip, round = G.round, why = "advance directly to 2b" }
      note("AGENDA ADVANCES directly to 2b: %s", R.card(skip).name or skip)
      A.i = 3
      AGENDA_BACK[skip]()
    end
  end

  --- The doom threshold is reached.
  function FX.agendaThreshold()
    local G = R.G
    if R.agendaId() == ID.beast then
      -- Forced: instead remove all doom in play and move The Experiment 1 location toward the Dormitories
      R.removeAllDoom()
      G.metrics.beast_moves = (G.metrics.beast_moves or 0) + 1
      note("The Beast Unleashed: doom removed, The Experiment moves")
      moveExperiment()
      return
    end
    FX.advanceAgenda("doom")
  end

  function FX.onEnemyMoved(en)
    -- The Beast Unleashed: Objective - If The Experiment enters the Dormitories, advance
    if en.id == ID.experiment and R.agendaId() == ID.beast then
      local L = R.G.locs[en.loc]
      if L and L.id == ID.dorms then FX.advanceAgenda("The Experiment enters the Dormitories") end
    end
  end

  ------------------------------------------------------------ acts --

  cov(ID.afterhours) ; cov(ID.rice_act, "full; the AI spends a clue on its [action] while \"Jazz\" Mulligan has not been found")
  cov(ID.campus)
  cov(ID.luck, "full; \"cheating\" is a policy switch (cfg.cheat), off by default") ; cov(ID.skin)
  cov(ID.allin) ; cov(ID.fold)

  -- clue objectives: clues (per investigator unless fixed) spent as a group (at = only investigators there)
  ACTS[ID.afterhours] = { clues = true }
  ACTS[ID.luck] = { clues = true, mandatory = true }
  ACTS[ID.skin] = { clues = true, at = ID.vip }
  ACTS[ID.rice_act] = {} ; ACTS[ID.campus] = {} ; ACTS[ID.allin] = {} ; ACTS[ID.fold] = {}

  function FX.actNeed(actId)
    local c = R.card(actId)
    if not ACTS[actId] or not ACTS[actId].clues then return 0 end
    return (c.clues or 0) * ((c.clues_per_investigator and n()) or 1)
  end

  local ACT_BACK = {}
  FX.ACT_BACK = ACT_BACK
  ACT_BACK[ID.afterhours] = function()
    shuffleDiscardIn()
    shuffleIn(T.takeCard(ID.jazz, asidePos(41)))
    return ID.rice_act
  end
  ACT_BACK[ID.rice_act] = function()
    local G = R.G
    local labs = putLocation(ID.labs)
    if R.agendaIndex() <= 2 and labs and not experiment() and not G.experimentGone then spawnSetAside(ID.experiment, labs, "Alchemy Labs") end
    if G.camp.otherDone then G.concoctionUnderLabs = true end
    return ID.campus
  end
  ACT_BACK[ID.campus] = function() FX.resolve("R3") end
  ACT_BACK[ID.luck] = function()
    local G = R.G
    local hall = putLocation(ID.darkened)
    if R.agendaIndex() == 1 and hall then
      -- discard from the top of the encounter deck until a [[Criminal]] enemy is discarded; spawn it in the Darkened Hall
      for _ = 1, 40 do
        local card, id = topEncounter(R.aliveInvs()[1])
        if not card then break end
        local d = R.card(id)
        if d.type == "Enemy" and R.hasTrait(d, "Criminal") then R.spawnEnemy(card, hall, nil, { want = "Darkened Hall" }) break end
        T.discardEncounter(card)
      end
    end
    return ID.skin
  end
  ACT_BACK[ID.skin] = function()
    local G = R.G
    if not G.camp.otherDone then
      local vip = locIn(ID.vip)
      local c = vip and take(ID.morgan, { vip.obj.getPosition().x, 1.8, vip.obj.getPosition().z - 1.4 }, false)
      G.npc = { id = ID.morgan, loc = vip and vip.guid, obj = c, clues = 0, damage = 0 }
      return ID.allin
    end
    local bar = locIn(ID.bar)
    local c = bar and take(ID.peter, { bar.obj.getPosition().x, 1.8, bar.obj.getPosition().z - 1.4 }, false)
    G.npc = { id = ID.peter, loc = bar and bar.guid, obj = c, clues = 0, damage = 0 }
    -- search the encounter deck (or out of play) for an [[Abomination]] enemy, spawn it in the Bar
    local card = T.searchEncounter(function(md) local d = R.card(md.id) return d.type == "Enemy" and R.hasTrait(d, "Abomination") end)
    if not card then
      local ab = G.asideDecks["Hideous Abominations"] or {}
      if #ab > 0 then
        local id = table.remove(ab, math.floor(R.rand() * #ab) + 1)
        card = take(id, asidePos(42))
      end
    end
    local deck = T.encounterDeck()
    if deck and deck.type == "Deck" then deck.shuffle() end
    if card and bar then R.spawnEnemy(card, bar, nil, { want = "Clover Club Bar" }) end
    return ID.fold
  end

  --- Advance the current act.
  function R.advanceAct(act, by)
    local G = R.G
    if G.ended or act.completed then return end
    act.completed = true
    G.metrics.acts_completed[#G.metrics.acts_completed + 1] = { id = act.id, round = G.round, by = by and by.id }
    note("ACT ADVANCES: %s (round %d)", R.card(act.id).name or act.id, G.round)
    for _, a in ipairs(attachedAt("act")) do detach(a) end
    local nextId = ACT_BACK[act.id]()
    if G.ended then return end
    if nextId then
      local nact = { id = nextId, district = "Main", pos = act.pos }
      G.acts.Main = nact
    end
    R.scanLocations()
  end

  --- Mandatory and paid objectives (acts and the locations' own), in player windows.
  function FX.checkObjectives(allowPaid)
    local G = R.G
    if G.ended then return end
    local act = G.acts.Main
    local spec = act and ACTS[act.id]
    if act and spec and spec.clues and not act.completed then
      local need = FX.actNeed(act.id)
      local payers = R.aliveInvs()
      if spec.at then
        local L = locIn(spec.at)
        payers = (L and L.revealed) and R.investigatorsAt(L) or {}
      end
      local have = 0
      for _, x in ipairs(payers) do have = have + x.clues end
      if need > 0 and have >= need and (spec.mandatory or allowPaid) then
        R.spendClues(payers, need)
        R.advanceAct(act, payers[1])
        if G.ended then return end
      end
    end
    if allowPaid then FX.locationObjectives() end
  end

  --- Extracurricular Activity's location objectives: investigators there spend clues as a group.
  function FX.locationObjectives()
    local G = R.G
    if cur() ~= "1a" then return end
    for _, spec in ipairs({ { ID.faculty, "R1" }, { ID.dorms, "R2" } }) do
      local L = locIn(spec[1])
      if L and L.revealed and (G.goal1a == nil or G.goal1a == spec[2] or G.anyGoal) then
        local need = (R.card(spec[1]).id == ID.faculty and 2 or 3) * n()
        local here = R.investigatorsAt(L)
        local have = 0
        for _, x in ipairs(here) do have = have + x.clues end
        if #here > 0 and have >= need then
          R.spendClues(here, need)
          G.metrics.objective_at = R.card(spec[1]).name
          FX.resolve(spec[2])
          return
        end
      end
    end
  end

  ------------------------------------------------------------ the end --

  function FX.resolve(res)
    local G = R.G
    if G.ended then return end
    G.resolution = res
    R.endLoop("resolution", res)
  end
  --- Every investigator resigned or was defeated.
  function FX.allGone()
    local G = R.G
    if G.ended then return end
    local act = G.acts.Main
    local resigned = {}
    for _, x in ipairs(G.inv) do if x.resigned then resigned[#resigned + 1] = x end end
    if cur() == "1b" and act and (act.id == ID.allin or act.id == ID.fold) and #resigned > 0 then
      -- "If each undefeated investigator has resigned, advance"
      act.completed = true
      G.metrics.acts_completed[#G.metrics.acts_completed + 1] = { id = act.id, round = G.round }
      local holder = G.npc and G.npc.holder
      local res = "R1"
      if holder and holder.resigned then res = (act.id == ID.allin) and "R2" or "R3" end
      FX.resolve(res)
      return
    end
    G.resolution = "NR"
    R.endLoop(#resigned > 0 and "resigned" or "defeat")
  end

  ------------------------------------------------------------ enemies --

  cov(ID.experiment, "full; Massive is the engine's (it attacks each investigator at its location)")
  cov(ID.pitboss)
  cov("02086") ; cov("02087", "full; its attack on a drawn [[Hex]]/[[Pact]] card happens before that card resolves")
  cov("02090", "full; the AI attacks it only when it is at the investigator's location (it is aloof)")
  cov("01177", "full; the random discard happens after the attack is dealt (if the hand was empty it deals +1/+1)")
  cov("02097", "full; the resource it denies is the upkeep phase's (other gains are not blocked)")
  cov("02098") ; cov("01159") ; cov("02103") ; cov("02104")

  function FX.fightMod(en) return 0 end

  --- An enemy drawn from the encounter deck: its spawn instruction, else engaged with the drawer.
  function FX.spawnDrawn(inv, card)
    local G = R.G
    local md = T.gm(card)
    local def = R.card(md.id)
    local text = tostring(def.text or "")
    local L = R.locOf(inv)
    if text:find("Spawn %- Location with the most clues") then
      local best, bc
      for _, x in ipairs(G.locList) do
        local c = x.revealed and R.clues(x) or 0
        -- ties: the lead investigator picks the one farthest from the investigators
        if bc == nil or c > bc then best, bc = x, c end
      end
      L = best or L
    elseif text:find("Spawn %- Farthest location from you") then
      local dist = R.paths(L, { enemy = true })
      local best, bd = L, -1
      for g, d in pairs(dist) do if d > bd then best, bd = G.locs[g], d end end
      L = best
    end
    R.spawnEnemy(card, L, inv, { want = text:match("Spawn %- ([^%.]+)") or "drawer" })
  end

  function FX.afterAttack(en, inv)
    if inv.defeated then return end
    if en.id == "01177" then
      -- Yithian Observer: discard 1 card at random from your hand; if you cannot, +1 damage and +1 horror
      if #inv.hand > 0 then
        local k = math.floor(R.rand() * #inv.hand) + 1
        inv.discard[#inv.discard + 1] = table.remove(inv.hand, k)
      else
        R.hurt(inv, 1, 1, en.name)
      end
    elseif en.id == "02098" then inv.resources = math.max(0, inv.resources - 1)   -- Mobster
    elseif en.id == "02104" then FX.mill(inv, 2, "Servant of the Lurker") end
  end

  function FX.onEnemyDefeated(en, inv)
    local G = R.G
    if en.id == ID.experiment then
      G.experimentGone = true
      -- Objective - If The Experiment is defeated, advance to act 3b
      FX.resolve("R3")
    end
  end

  --- "When the enemy phase begins" effects (flow's enemy phase calls checkWakes first).
  function FX.checkWakes()
    local G = R.G
    if G.phase ~= "enemy" or G.enemyPhaseBegun == G.round then return end
    G.enemyPhaseBegun = G.round
    local ex = experiment()
    if ex then ex.exhausted = false end                       -- The Experiment readies
    if G.npc and G.npc.id == ID.peter and not G.npc.holder and not G.npc.gone then
      -- Peter Clover: if no investigator controls him, deal 1 damage to him
      G.npc.damage = G.npc.damage + 1
      if G.npc.damage >= (R.card(ID.peter).health or 3) then
        G.npc.gone = true
        note("Peter Clover is defeated")
        if T.alive(G.npc.obj) then G.npc.obj.setPosition(asidePos(43)) end
      end
    end
    if R.agendaId() == ID.chaos then
      -- discard each [[Criminal]] enemy in the same location as an [[Abomination]] enemy
      for _, en in ipairs(enemiesWith(function(e) return R.hasTrait(e.def, "Criminal") end)) do
        for _, ab in ipairs(G.enemies) do
          if not ab.dead and ab.loc == en.loc and R.hasTrait(ab.def, "Abomination") then discardEnemy(en, "Chaos in the Clover Club") break end
        end
      end
    end
  end

  function FX.endOfRound()
    local G = R.G
    for _, inv in ipairs(R.aliveInvs()) do
      local L = R.locOf(inv)
      -- Jenny Barnes: 1 additional resource during each upkeep phase
      local gain = (inv.id == "02003") and 1 or 0
      -- VIP Area: no cards or resources during the upkeep phase (the draw was skipped in P.draw)
      if L and L.id == ID.vip then gain = -1 end
      -- O'Bannion's Thug: while engaged with you, you cannot gain resources
      for _, en in ipairs(G.enemies) do if en.id == "02097" and en.engaged == inv and gain >= 0 then gain = -1 break end end
      inv.resources = math.max(0, inv.resources + gain)
      -- Dead of Night: maximum hand size reduced by 3
      local maxHand = (R.agendaId() == ID.deadnight) and 5 or 8
      while #inv.hand > maxHand do inv.discard[#inv.discard + 1] = table.remove(inv.hand, 1) end
      -- Dissonant Voices: discarded at the end of the round
      if hasThreat(inv, "Dissonant Voices") then
        local c = inv.threat["Dissonant Voices"] ; inv.threat["Dissonant Voices"] = nil
        if c.obj and T.alive(c.obj) then T.discardEncounter(c.obj) end
      end
    end
  end

  ------------------------------------------------------------ treacheries --

  local function threat(inv, name, card)
    inv.threat[name] = { name = name, obj = card, id = T.gm(card).id }
    local mat = T.mat(inv.color)
    local p = mat.positionToWorld({ 0.4, 0.3, -0.63 })
    card.setPosition({ p.x, p.y + 0.2, p.z })
    return "keep"
  end
  local function test(inv, skill, diff, opts)
    opts = opts or {}
    opts.kind = opts.kind or "treachery"
    return R.test(inv, skill, diff, opts)
  end

  FX.threat, FX.test = threat, test
  -- the Sorcery set
  cov("02083")
  ENC["02083"] = function(inv)            -- Visions of Futures Past
    local ok, margin = test(inv, "wil", 5)
    if not ok and not inv.defeated then FX.mill(inv, math.max(1, -margin), "Visions of Futures Past") end
  end
  cov("02084")
  ENC["02084"] = function(inv, card)      -- Beyond the Veil
    if hasThreat(inv, "Beyond the Veil") then return "surge" end
    threat(inv, "Beyond the Veil", card)
    FX.checkEmptyDeck(inv)
    return "surge"
  end
  -- Bishop's Thralls
  cov("02085", "full; attached to the act unless the act already has one (the AI's choice)")
  ENC["02085"] = function(inv, card)      -- Light of Aforgomon (Peril)
    if #attachedAt("act", "02085") == 0 then return attach(card, "act") end
    if #attachedAt("agenda", "02085") == 0 then return attach(card, "agenda") end
    return "discard"
  end
  -- The Beyond
  cov("02100", "full; the asset shuffled back is the least valuable one")
  ENC["02100"] = function(inv)            -- Pushed into the Beyond
    local pick, pv
    for i, a in ipairs(inv.assets) do
      local v = R.AI.cardValue(inv, a.rec or {}) + ((a.uses or 0) > 0 and 1 or 0)
      if not a.story and (pv == nil or v < pv) then pick, pv = i, v end
    end
    local name
    if pick then
      local a = table.remove(inv.assets, pick)
      name = a.name
      inv.deck[#inv.deck + 1] = a.rec
      R.shuffle(inv.deck)
    end
    local milled = FX.mill(inv, 3, "Pushed into the Beyond")
    for _, c in ipairs(milled) do if name and c.name == name then horror(inv, 2, "Pushed into the Beyond") break end end
  end
  cov("02101", "full; the chosen card types are those that cost the party the fewest cards")
  ENC["02101"] = function(inv)            -- Terror from Beyond (Peril)
    local G = R.G
    local key = G.round .. ":" .. G.phase
    G.terrorPhase = G.terrorPhase or {}
    local k = G.terrorPhase[key] and 2 or 1
    G.terrorPhase[key] = true
    local counts = { Asset = 0, Event = 0, Skill = 0 }
    for _, x in ipairs(R.aliveInvs()) do for _, c in ipairs(x.hand) do if counts[c.type] then counts[c.type] = counts[c.type] + 1 end end end
    local order = { "Asset", "Event", "Skill" }
    table.sort(order, function(a, b) return counts[a] < counts[b] end)
    local chosen = {}
    for i = 1, k do chosen[order[i]] = true end
    for _, x in ipairs(R.aliveInvs()) do
      for i = #x.hand, 1, -1 do
        if chosen[x.hand[i].type] then x.discard[#x.discard + 1] = table.remove(x.hand, i) end
      end
    end
  end
  cov("02102", "full; on a failed test the AI discards the top 5 cards and moves (deck of 10 or more, no Beyond the Veil) or cancels the move")
  ENC["02102"] = function(inv, card)      -- Arcane Barrier
    local L = R.locOf(inv)
    if #attachedAt(L.guid, "02102") > 0 then return "discard" end
    return attach(card, L.guid)
  end
  -- Whippoorwills
  cov("02091")
  ENC["02091"] = function(inv)            -- Eager for Death
    if not test(inv, "wil", 2 + inv.damage) and not inv.defeated then horror(inv, 2, "Eager for Death") end
  end
  -- Agents of Yog-Sothoth, Ancient Evils, Locked Doors (core set)
  cov("01178", "full; the AI takes 2 horror unless that leaves it at 2 sanity or less, or the agenda is far from its threshold")
  ENC["01178"] = function(inv)            -- Offer of Power (Peril)
    local roomLeft = inv.sanity - inv.horror
    local doomLeft = R.threshold() - R.doomInPlay()
    if roomLeft <= 2 or (doomLeft > 3 and R.agendaIndex() < 3) then
      R.P.draw(inv, 2)
      R.placeDoom(2, "Offer of Power", { canAdvance = true })
    else
      horror(inv, 2, "Offer of Power")
    end
  end
  cov("01166")
  ENC["01166"] = function(inv) R.placeDoom(1, "Ancient Evils", { canAdvance = true }) end
  cov("01174", "full; attached to the revealed location with the most clues (ties: the first found)")
  ENC["01174"] = function(inv, card)      -- Locked Door
    local best, bc
    for _, L in ipairs(R.G.locList) do
      if #attachedAt(L.guid, "01174") == 0 then
        local c = L.revealed and R.clues(L) or 0
        if bc == nil or c > bc then best, bc = L, c end
      end
    end
    if not best then return "discard" end
    return attach(card, best.guid)
  end
  -- The House Always Wins
  cov("02081")
  ENC["02081"] = function(inv)            -- Something in the Drinks
    for _, x in ipairs(R.aliveInvs()) do if x.hadDrink then x.loseAction = (x.loseAction or 0) + 1 end end
    return "surge"
  end
  cov("02082")
  ENC["02082"] = function(inv)            -- Arousing Suspicions
    local placed = false
    for _, en in ipairs(R.G.enemies) do
      if not en.dead and en.loc == inv.loc and R.hasTrait(en.def, "Criminal") then en.doom = (en.doom or 0) + 1 ; placed = true end
    end
    if placed then R.G.metrics.doom_sources["Arousing Suspicions"] = (R.G.metrics.doom_sources["Arousing Suspicions"] or 0) + 1
    else inv.resources = math.max(0, inv.resources - 2) end
  end
  -- Bad Luck
  cov("02092")
  ENC["02092"] = function(inv, card)      -- Cursed Luck
    if hasThreat(inv, "Cursed Luck") then return "discard" end
    return threat(inv, "Cursed Luck", card)
  end
  cov("02093")
  ENC["02093"] = function(inv)            -- Twist of Fate
    local name = revealRandom(inv)
    local v = tonumber(name)
    if name == "Elder Sign" or (v and v > 0) then return end
    if v then R.hurt(inv, 1, 0, "Twist of Fate") else horror(inv, 2, "Twist of Fate") end
  end
  -- Naomi's Crew
  cov("02099")
  ENC["02099"] = function(inv)            -- Hunted Down
    local G = R.G
    local list = enemiesWith(function(e) return R.hasTrait(e.def, "Criminal") and not e.engaged end)
    if #list == 0 then return "surge" end
    local here = R.locOf(inv)
    for _, en in ipairs(list) do
      if en.loc ~= inv.loc then R.enemyStepToward(en, here) end
      if en.engaged == inv and not en.dead then R.enemyAttack(en, inv, "Hunted Down") end
      if G.ended or inv.defeated then return end
    end
  end
  -- Striking Fear (core set)
  cov("01163")
  ENC["01163"] = function(inv)            -- Rotting Remains
    local ok, margin = test(inv, "wil", 3)
    if not ok and not inv.defeated then horror(inv, math.max(1, -margin), "Rotting Remains") end
  end
  cov("01164")
  ENC["01164"] = function(inv, card)      -- Frozen in Fear
    if hasThreat(inv, "Frozen in Fear") then return "discard" end
    return threat(inv, "Frozen in Fear", card)
  end
  cov("01165")
  ENC["01165"] = function(inv, card)      -- Dissonant Voices
    if hasThreat(inv, "Dissonant Voices") then return "discard" end
    return threat(inv, "Dissonant Voices", card)
  end
  -- "Jazz" Mulligan: Revelation - put him into play at your location
  cov(ID.jazz)
  ENC[ID.jazz] = function(inv, card)
    local G = R.G
    local L = R.locOf(inv)
    G.jazz = { obj = card, loc = L.guid }
    local p = L.obj.getPosition()
    card.setPosition({ p.x + 0.9, p.y + 0.3, p.z + 1.2 })
    G.metrics.jazz_found = G.round
    note("\"Jazz\" Mulligan is at %s", L.name)
    return "keep"
  end
  -- set-aside story cards
  cov(ID.concoction) ; cov(ID.rice, "full; added to a deck only in campaign-order runs") ; cov(ID.morgan)
  cov(ID.peter) ; cov(ID.armitage, "not played in either scenario (Armitage's Fate decides who may add him)")

  -- Wizard of Yog-Sothoth: when the engaged investigator draws a [[Hex]] or [[Pact]] card, it attacks
  local function wrapEnc(id, h)
    ENC[id] = function(inv, card)
      local d = R.card(id)
      if R.hasTrait(d, "Hex") or R.hasTrait(d, "Pact") then
        for _, en in ipairs(enemiesWith(function(e) return e.id == "02087" and e.engaged == inv end)) do
          R.enemyAttack(en, inv, "Wizard of Yog-Sothoth (Forced)")
          if inv.defeated or R.G.ended then return "discard" end
        end
      end
      R.G.metrics.treacheries = R.G.metrics.treacheries or {}
      R.G.metrics.treacheries[id] = (R.G.metrics.treacheries[id] or 0) + 1
      return h(inv, card)
    end
  end
  FX.wrapEnc = wrapEnc
  do
    local list = {}
    for id, h in pairs(ENC) do list[#list + 1] = { id, h } end
    for _, x in ipairs(list) do wrapEnc(x[1], x[2]) end
  end

  --- Arcane Barrier on a move into or out of its location (an additional cost).
  function FX.barrierCost(inv, a, b)
    for _, L in ipairs({ a, b }) do
      for _, bar in ipairs(L and attachedAt(L.guid, "02102") or {}) do
        local ok = test(inv, "wil", 4, { kind = "treachery" })
        if inv.defeated or R.G.ended then return false end
        if ok then detach(bar)
        elseif #inv.deck >= 10 and not hasThreat(inv, "Beyond the Veil") then FX.mill(inv, 5, "Arcane Barrier")
        else R.G.metrics.barrier_cancels = (R.G.metrics.barrier_cancels or 0) + 1 ; return false end
      end
    end
    return true
  end

  function FX.dropStory(inv, L)
    local G = R.G
    if G.npc and G.npc.holder == inv then G.npc.holder = nil ; G.npc.gone = true end
  end

  return FX
end
