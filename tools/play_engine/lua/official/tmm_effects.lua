-- The effects table for The Dunwich Legacy's second scenario, The Miskatonic
-- Museum (designer tooling): every card SCED's box "2: The Miskatonic Museum"
-- holds, keyed by card id, encoded from the card text in ArkhamDB's data
-- (pack/dwl/tmm_encounter.json, core for Chilling Cold and Locked Doors).
-- Loaded after dwl_effects.lua, which already encodes the encounter sets the
-- Museum shares with 1a/1b (Bad Luck, Sorcery, The Beyond, Locked Doors);
-- this file adds the Museum's own cards to the same tables (FX.ENC, FX.ACTS,
-- FX.COVERAGE ...) and gives the FX hooks a Museum branch. In 1a/1b every
-- hook falls through to dwl_effects.lua's version unchanged. Numbers (shroud,
-- fight, health, clues, doom) come from the card data, never from here.
--
--   * Hunting Horror: Hunter, Retaliate; the token it reveals at the start of
--     the enemy phase; the void (where it goes instead of the discard pile)
--     and every effect that brings it back; Shadow-spawned (attached the first
--     time it enters play, +1 resource each time after: +1 fight, health and
--     evade per resource, Massive at 3);
--   * the Exhibit deck (the Restricted Hall shuffled into its bottom three),
--     the two Security Offices and Administration Offices (one of each, at
--     random), the locked Museum Halls and both ways in;
--   * Harold Walsted / Adam Lynch (a [tablet] token when one leaves play) and
--     the resolutions' choice (FX.resolve from act 3b).

return function(R, T)
  local E = T.E
  local FX = R.FX
  local ID = FX.ID
  local function cov(id, how) FX.COVERAGE[id] = how or "full" end
  local function note(fmt, ...) R.log(fmt, ...) end
  local function is2() return R.G.scen == "2" end
  local function n() return R.G.n end
  local function cluesRaw(L) return (FX.cluesRaw or R.clues)(L) end

  local M = {
    scen = "02118", access = "02119", deepen = "02120", shadows = "02121",
    inside = "02122", night = "02123", breaking = "02124", tome = "02125",
    entrance = "02126", halls = "02127", security6 = "02128", securityLook = "02129", adminRes = "02130",
    adminHand = "02131", athabaskan = "02132", medusa = "02133", nature = "02134", egyptian = "02135",
    dead = "02136", restricted = "02137", harold = "02138", adam = "02139", necronomicon = "02140",
    horror = "02141", spawned = "02142", stalked = "02143", passage = "02144", ephemeral = "02145",
    slithering = "02146", chill = "01167", fog = "01168",
  }
  for k, v in pairs(M) do ID["m_" .. k] = v end
  FX.M = M
  local EXHIBITS = { M.athabaskan, M.medusa, M.nature, M.egyptian, M.dead }

  FX.SC["2"] = { agendas = { M.access, M.deepen, M.shadows }, acts = { M.inside, M.night, M.tome },
                 start = M.entrance, reference = M.scen }

  ------------------------------------------------------------ setup --

  FX.SETUP = FX.SETUP or {}
  --- After SCED's box is Placed: one Security Office and one Administration Office at random (the other is
  -- removed from the game), and the Exhibit deck (kept beside the table; its order is the engine's).
  FX.SETUP["2"] = function(G)
    local k = 16
    local function aside(id)
      local c = T.takeCard(id, FX.asidePos(k), { 0, 270, 0 })
      k = k + 1
      if not c then T.note("museum setup: card " .. id .. " not found") end
      return c
    end
    local keep = {}
    for _, pair in ipairs({ { M.security6, M.securityLook }, { M.adminRes, M.adminHand } }) do
      local out = (R.rand() < 0.5) and 1 or 2
      aside(pair[out])
      keep[#keep + 1] = pair[3 - out]
    end
    G.metrics.offices = keep
    for _, id in ipairs(EXHIBITS) do aside(id) end
    aside(M.restricted)
    E.run(0.3)
    -- the Restricted Hall and 2 other random Exhibit Halls shuffled as the bottom 3, the other 3 on top
    local others = {}
    for _, id in ipairs(EXHIBITS) do others[#others + 1] = id end
    R.shuffle(others)
    local bottom = { M.restricted, others[1], others[2] }
    local top = { others[3], others[4], others[5] }
    R.shuffle(bottom)
    R.shuffle(top)
    G.exhibit = { top[1], top[2], top[3], bottom[1], bottom[2], bottom[3] }
    for i, id in ipairs(G.exhibit) do if id == M.restricted then G.metrics.restricted_at = i end end
    G.metrics.exhibits_drawn = 0
    G.allies = {}
    G.tokensAdded = {}
    -- clues the objectives ask for: act 1's, 1 [per_investigator] per Exhibit Hall down to the Restricted Hall,
    -- and the Restricted Hall's own
    local a1 = R.card(M.inside)
    G.metrics.clues_required = (a1.clues or 0) * (a1.clues_per_investigator and G.n or 1)
      + G.metrics.restricted_at * G.n + (R.card(M.restricted).clues or 0) * G.n
  end

  -- where an Exhibit Hall enters play: two rows beyond the Museum Halls
  local SLOT = { { -6.55, -7.66 }, { -6.55, 0 }, { -6.55, 7.66 }, { -13.1, -7.66 }, { -13.1, 0 }, { -13.1, 7.66 } }
  --- Museum Halls' [action]: the top card of the Exhibit deck enters play, unrevealed.
  function FX.drawExhibit()
    local G = R.G
    local id = table.remove(G.exhibit, 1)
    if not id then return nil end
    local halls = R.locById(M.halls)
    local p = halls and halls.obj.getPosition() or { x = -23.7, y = 1.6, z = 0 }
    G.metrics.exhibits_drawn = G.metrics.exhibits_drawn + 1
    local s = SLOT[G.metrics.exhibits_drawn] or SLOT[6]
    local c = FX.take(id, { p.x + s[1], 1.7, p.z + s[2] }, false)
    if not c then T.note("exhibit hall " .. id .. " not found") return nil end
    R.scanLocations()
    note("An Exhibit Hall enters play (%d left in the Exhibit deck)", #G.exhibit)
    return R.locById(id)
  end

  ------------------------------------------------------------ Hunting Horror, the void --

  cov(M.horror, "full; its start-of-enemy-phase token is revealed by the lead investigator; while Massive (3 resources "
    .. "on Shadow-spawned) it still follows the investigator it is engaged with when that investigator moves")
  cov(M.spawned)

  local function hh() return FX.enemyById(M.horror) end
  FX.huntingHorror = hh
  local function voidPos() return FX.asidePos(50) end

  --- "Search the encounter deck, discard pile, and the void for Hunting Horror and spawn it" at L.
  local function summon(L, inv, why)
    if not L or hh() or R.G.ended then return nil end
    local p = L.obj.getPosition()
    local c = T.takeCard(M.horror, { p.x, 2.2, p.z + 2.4 }, { 0, 270, 0 })
    if not c then T.note("Hunting Horror not found (" .. tostring(why) .. ")") return nil end
    E.run(0.1)
    R.G.metrics.hh_summoned = R.G.metrics.hh_summoned or {}
    R.G.metrics.hh_summoned[why] = (R.G.metrics.hh_summoned[why] or 0) + 1
    return R.spawnEnemy(c, L, inv, { want = why })
  end
  FX.summonHorror = summon

  --- Every agenda's Forced: when Hunting Horror enters play, attach the set-aside Shadow-spawned to it, or add
  -- 1 resource to Shadow-spawned if it is already attached.
  local onSpawnBase = FX.onSpawn
  function FX.onSpawn(en)
    onSpawnBase(en)
    if en.id ~= M.horror then return end
    local G = R.G
    if not G.shadow then
      G.shadow = { res = 0 }
      local c = T.cardWithId(M.spawned)
      if c then G.shadow.obj = c else T.note("Shadow-spawned not found") end
    else
      G.shadow.res = G.shadow.res + 1
    end
    if G.shadow.obj and T.alive(G.shadow.obj) and T.alive(en.obj) then
      local p = en.obj.getPosition()
      G.shadow.obj.setPosition({ p.x + 0.4, p.y + 0.3, p.z + 0.4 })
    end
    en.maxHealth = (tonumber(en.def.health) or 3) + G.shadow.res
    local m = G.metrics
    m.hh_entries = (m.hh_entries or 0) + 1
    m.hh_first_round = m.hh_first_round or G.round
    m.shadow_res = G.shadow.res
    note("Shadow-spawned: %d resource(s) (Hunting Horror %d fight, %d health, %d evade%s)", G.shadow.res,
      (en.def.fight or 0) + G.shadow.res, en.maxHealth, (en.def.evade or 0) + G.shadow.res,
      G.shadow.res >= 3 and ", Massive" or "")
  end
  --- Shadow-spawned's bonus (fight here; health above; evade and Massive in tmm_play.lua).
  function FX.shadowBonus(en)
    local G = R.G
    return (en.id == M.horror and G.shadow) and G.shadow.res or 0
  end
  local fightModBase = FX.fightMod
  function FX.fightMod(en) return fightModBase(en) + FX.shadowBonus(en) end

  --- "When Hunting Horror leaves play, place it in the void" (Shadow-spawned stays attached; its doom is gone).
  function FX.toVoid(en)
    local G = R.G
    if T.alive(en.obj) then
      en.obj.setPosition(voidPos())
      en.obj.setRotation({ 0, 270, 0 })
    end
    if G.shadow and G.shadow.obj and T.alive(G.shadow.obj) then
      local p = voidPos()
      G.shadow.obj.setPosition({ p[1] + 3, p[2], p[3] })
    end
    G.metrics.hh_void = (G.metrics.hh_void or 0) + 1
    note("Hunting Horror is placed in the void")
  end

  local function hhDoom(why)
    local G = R.G
    local en = hh()
    en.doom = (en.doom or 0) + 1
    G.metrics.doom_sources[why] = (G.metrics.doom_sources[why] or 0) + 1
    G.metrics.doom_placed = (G.metrics.doom_placed or 0) + 1
    note("1 doom on Hunting Horror (%s): %d / %d", why, R.doomInPlay(), R.threshold())
  end

  --- Forced - At the start of the enemy phase: reveal a random chaos token; on a symbol, ready Hunting Horror.
  local wakesBase = FX.checkWakes
  function FX.checkWakes()
    local G = R.G
    if not is2() then return wakesBase() end
    if G.phase ~= "enemy" or G.enemyPhaseBegun == G.round then return end
    G.enemyPhaseBegun = G.round
    local en = hh()
    local lead = R.aliveInvs()[1]
    if not en or not lead then return end
    local name = FX.revealRandom(lead)
    local m = G.metrics
    m.hh_tokens = (m.hh_tokens or 0) + 1
    if FX.SYMBOL[name] then
      if en.exhausted then
        m.hh_readied = (m.hh_readied or 0) + 1
        note("Hunting Horror readies (%s)", name)
      end
      en.exhausted = false
      if not en.engaged then R.engageAt(G.locs[en.loc]) end
    end
  end

  ------------------------------------------------------------ scenario reference card --

  cov(M.scen, "full (Standard side); the asset discarded on a failed [elder_thing] is the least valuable one "
    .. "(Harold Walsted / Adam Lynch last)")

  local tokenValueBase = FX.tokenValue
  function FX.tokenValue(name, inv)
    if not is2() then return tokenValueBase(name, inv) end
    if name == "Auto-fail" then return nil end
    if name == "Elder Sign" then return R.P.elderSign(inv) end
    local v = tonumber(name)
    if v then return v end
    if name == "Skull" then
      if inv and inv.id == "02004" then return 0 end            -- Jim Culver: [skull] modifier is 0
      local en = hh()
      return (en and inv and en.loc == inv.loc) and -3 or -1
    end
    if name == "Cultist" then return -1 end
    if name == "Tablet" then return -2 end
    if name == "Elder Thing" then return -3 end
    return 0
  end
  local tokenAfterBase = FX.tokenAfter
  function FX.tokenAfter(name, inv, success, test, margin)
    if not is2() then return tokenAfterBase(name, inv, success, test, margin) end
    local G = R.G
    inv.lastToken = name
    G.pendingET = nil
    local L = R.locOf(inv)
    if name == "Cultist" and not success and not inv.defeated and L then
      summon(L, nil, "[cultist] token")
    elseif name == "Tablet" and inv.clues > 0 and L then
      -- return 1 of your clues to your current location
      inv.clues = inv.clues - 1
      local tok = table.remove(inv.clueTokens)
      if tok and T.alive(tok) then tok.destruct() end
      T.spawnClueOn(L.obj, 1)
      G.metrics.clues_returned = (G.metrics.clues_returned or 0) + 1
      note("%s returns 1 clue to %s ([tablet])", inv.name, L.name)
    elseif name == "Elder Thing" and not success and not inv.defeated then
      FX.discardAsset(inv, "[elder_thing] token")
    end
    if name == "Skull" then R.P.trumpet(inv) end
  end

  ------------------------------------------------------------ assets leaving play --

  --- "Discard an asset you control": the least valuable one; the scenario's ally only when there is no other.
  function FX.discardAsset(inv, why)
    local pick, pv
    for i, a in ipairs(inv.assets) do
      local v = (a.story and 100 or 0) + R.AI.cardValue(inv, a.rec or {}) + ((a.uses or 0) > 0 and 1 or 0)
      if pv == nil or v < pv then pick, pv = i, v end
    end
    if not pick then return false end
    local a = table.remove(inv.assets, pick)
    if not a.story then inv.discard[#inv.discard + 1] = a.rec end
    R.G.metrics.assets_discarded = (R.G.metrics.assets_discarded or 0) + 1
    note("%s discards %s (%s)", inv.name, a.name, why or "?")
    FX.checkStoryAllies()
    return true
  end

  cov(M.harold, "full; given to the investigator with the highest [intellect] who has no ally in play; the AI plays no "
    .. "other ally over him; not counted as leaving play when his controller resigns")
  cov(M.adam, "full; given to an investigator with no ally in play; see Harold Walsted")
  cov(M.necronomicon, "earned in R2 (added to a deck for later scenarios); not played in this scenario")

  --- Harold Walsted / Adam Lynch, Forced - when he leaves play: remove him from the game and add 1 [tablet]
  -- token to the chaos bag for the remainder of the campaign.
  function FX.checkStoryAllies()
    local G = R.G
    if not is2() or not G.allies then return end
    for id, s in pairs(G.allies) do
      if not s.lost then
        local inPlay = false
        for _, a in ipairs(s.holder.assets) do if a == s.asset then inPlay = true end end
        local gone = s.holder.drivenOut or (s.holder.defeated and not s.holder.resigned)
        if gone or not inPlay then
          s.lost = true
          for i, a in ipairs(s.holder.assets) do if a == s.asset then table.remove(s.holder.assets, i) break end end
          G.metrics.allies_lost = G.metrics.allies_lost or {}
          G.metrics.allies_lost[id] = G.round
          G.tokensAdded[#G.tokensAdded + 1] = "tablet"
          note("%s leaves play: removed from the game, 1 [tablet] token added to the chaos bag", R.card(id).name or id)
          if not G.ended then
            local list = E.Global.call("getChaosBagState") or {}
            list[#list + 1] = "tablet"
            E.Global.call("setChaosBagState", list)
            E.run(0.5)
            R.touch()
          end
        end
      end
    end
  end

  local function hasAlly(inv)
    for _, a in ipairs(inv.assets) do if a.rec and a.rec.slot == "Ally" then return true end end
    return false
  end
  local function giveAlly(id, byInt)
    local G = R.G
    local best, bv
    for _, inv in ipairs(R.aliveInvs()) do
      local v = (hasAlly(inv) and 0 or 100) + (byInt and inv.stats.int or (inv.health - inv.damage))
      if bv == nil or v > bv then best, bv = inv, v end
    end
    if not best then return end
    local c = T.cardWithId(id)
    if c then c.setPosition(FX.asidePos(52 + (byInt and 1 or 0))) end
    local a = R.P.putIntoPlay(best, { name = R.card(id).name, id = id, slot = "Ally", story = true })
    G.allies[id] = { holder = best, asset = a }
    G.metrics.ally = id
    G.metrics.ally_holder = best.id
  end

  ------------------------------------------------------------ locations --

  cov(M.entrance, "full; resources are not gained there in the upkeep phase or by the investigator's own action "
    .. "(gains during another investigator's turn are not blocked); the AI resigns only when the last agenda is "
    .. "about to advance")
  cov(M.halls, "full; the door is broken ([combat] 5) only when that looks better than investigating the Entrance")
  cov(M.security6, "full; the card taken is the one the AI values most; used with 4 or fewer cards in hand")
  cov(M.securityLook, "its [action][action] (look at an Exhibit Hall / the top of the Exhibit deck) is never used: "
    .. "the AI explores each Exhibit Hall by entering it")
  cov(M.adminRes) ; cov(M.adminHand)
  cov(M.athabaskan) ; cov(M.medusa) ; cov(M.nature) ; cov(M.egyptian) ; cov(M.dead)
  cov(M.restricted)

  local canEnterBase = FX.canEnter
  function FX.canEnter(inv, L)
    if not is2() then return canEnterBase(inv, L) end
    -- "The entrance to the Museum Halls is locked. You cannot move into the Museum Halls."
    if L.id == M.halls and not L.revealed then return false end
    return true
  end

  local canInvestigateBase = FX.canInvestigate
  function FX.canInvestigate(inv, L)
    if not canInvestigateBase(inv, L) then return false end
    if not is2() then return true end
    if L.id == M.restricted then
      local en = hh()
      if en and en.loc == L.guid then return false end
    end
    if L.id == M.adminRes and inv.resources <= 4 then return false end
    if L.id == M.adminHand and #inv.hand <= 4 then return false end
    return true
  end

  local onEnterBase = FX.onEnter
  function FX.onEnter(inv, L)
    onEnterBase(inv, L)
    if not is2() then return end
    local G = R.G
    if L.id == M.restricted and cluesRaw(L) == 0 and not G.restrictedSeen then
      T.note("the Restricted Hall was revealed without clues")
    end
    if L.id == M.restricted then G.restrictedSeen = true end
    if L.id == M.athabaskan then
      -- Forced - After you enter this location: lose all of your remaining actions and immediately end your turn
      if G.turnOf == inv then inv.actionsLeft = 0 end
      G.metrics.athabaskan = (G.metrics.athabaskan or 0) + 1
    elseif L.id == M.nature then
      -- Forced - After you enter this location: discard 2 cards from your hand at random
      for _ = 1, 2 do
        if #inv.hand == 0 then break end
        local k = math.floor(R.rand() * #inv.hand) + 1
        inv.discard[#inv.discard + 1] = table.remove(inv.hand, k)
      end
    end
    -- Night at the Museum / Breaking and Entering: Objective - if an investigator enters the Restricted Hall, advance
    local act = G.acts.Main
    if L.id == M.restricted and act and (act.id == M.night or act.id == M.breaking) then R.advanceAct(act, inv) end
  end

  --- After a failed investigation (tmm_play.lua calls this from the skill test's end).
  function FX.investigateFailed(inv, L)
    if L.id == M.medusa then FX.discardAsset(inv, "Medusa Exhibit")
    elseif L.id == M.egyptian then inv.actionsLeft = math.max(0, (inv.actionsLeft or 0) - 1)
    elseif L.id == M.dead then R.hurt(inv, 0, 1, "Hall of the Dead") end
  end

  local afterDiscoverBase = FX.afterDiscover
  function FX.afterDiscover(inv, L)
    afterDiscoverBase(inv, L)
    if not is2() or not L then return end
    -- Obscuring Fog: after the attached location is successfully investigated, discard it
    for _, a in ipairs(FX.attachedAt(L.guid, M.fog)) do
      FX.detach(a)
      R.G.shroudMod[L.guid] = nil
    end
  end

  local endOfRoundBase = FX.endOfRound
  function FX.endOfRound()
    if not is2() then return endOfRoundBase() end
    -- Museum Entrance: investigators there cannot gain resources (the upkeep resource was just added)
    local cap = {}
    for _, inv in ipairs(R.aliveInvs()) do
      local L = R.locOf(inv)
      if L and L.id == M.entrance then cap[inv] = math.max(0, inv.resources - 1) end
    end
    endOfRoundBase()
    for inv, c in pairs(cap) do if inv.resources > c then inv.resources = c end end
  end

  ------------------------------------------------------------ agendas --

  cov(M.access, "full; \"shuffle the encounter discard pile into the encounter deck\" is done only when Hunting "
    .. "Horror was searched for (the sentence is read with that clause)")
  cov(M.deepen, "full; see Restricted Access")
  cov(M.shadows, "full; investigators defeated by Driven Out are counted apart from defeats by damage or horror")

  local function creature()
    if hh() then hhDoom("Hunting Horror (agenda)")
    else
      summon(R.locById(M.halls), nil, "Museum Halls (agenda)")
      FX.shuffleDiscardIn()
    end
  end
  FX.AGENDA_BACK[M.access] = creature
  FX.AGENDA_BACK[M.deepen] = creature
  FX.AGENDA_BACK[M.shadows] = function()
    -- Driven Out: each investigator who has not resigned is defeated and suffers 1 physical trauma
    local G = R.G
    for _, inv in ipairs(R.aliveInvs()) do
      inv.trauma.physical = inv.trauma.physical + 1
      inv.drivenOut = true
      G.metrics.driven_out = (G.metrics.driven_out or 0) + 1
      note("%s is driven out (defeated, 1 physical trauma)", inv.name)
    end
    FX.checkStoryAllies()
    G.resolution = "NR"
    R.endLoop("agenda", "Driven Out")
  end

  ------------------------------------------------------------ acts --

  cov(M.inside) ; cov(M.night) ; cov(M.breaking)
  cov(M.tome, "full; the investigators' choice at 3b (destroy it, R1 / keep it, R2) is a run policy "
    .. "(--necronomicon, default keep)")

  FX.ACTS[M.inside] = { clues = true }
  FX.ACTS[M.night] = {} ; FX.ACTS[M.breaking] = {} ; FX.ACTS[M.tome] = {}

  FX.ACT_BACK[M.inside] = function()
    local G = R.G
    local halls = R.locById(M.halls)
    if not G.brokeDoor then giveAlly(M.adam, false) end
    if halls then R.reveal(halls) end
    return G.brokeDoor and M.breaking or M.night
  end
  local function toRestricted()
    -- search the encounter deck, discard pile, the void and all play areas for Hunting Horror; place it in
    -- the Restricted Hall, ready
    local G = R.G
    local L = R.locById(M.restricted)
    if not L then T.note("act 2 advanced without the Restricted Hall in play") return end
    local en = hh()
    if en then
      en.loc, en.engaged, en.exhausted = L.guid, nil, false
      R.placeEnemy(en)
      note("Hunting Horror is placed in the Restricted Hall")
      R.engageAt(L)
    else
      summon(L, nil, "Restricted Hall (act 2)")
    end
  end
  FX.ACT_BACK[M.night] = function() toRestricted() return M.tome end
  FX.ACT_BACK[M.breaking] = function()
    giveAlly(M.harold, true)
    toRestricted()
    return M.tome
  end
  FX.ACT_BACK[M.tome] = function()
    FX.resolve(((R.WHATIF or {}).necronomicon == "destroy") and "R1" or "R2")
  end

  local checkObjectivesBase = FX.checkObjectives
  function FX.checkObjectives(allowPaid)
    checkObjectivesBase(allowPaid)
    local G = R.G
    if not is2() or G.ended then return end
    FX.checkStoryAllies()
    -- Searching for the Tome: Objective - if there are no clues remaining in the Restricted Hall, advance
    local act = G.acts.Main
    if act and act.id == M.tome and not act.completed then
      local L = R.locById(M.restricted)
      if L and L.revealed and cluesRaw(L) == 0 then R.advanceAct(act, nil) end
    end
  end

  ------------------------------------------------------------ treacheries --

  local ENC = {}
  cov(M.stalked)
  ENC[M.stalked] = function(inv)             -- Stalked in the Dark
    local en = hh()
    if not en then return "surge" end
    local L = R.locOf(inv)
    en.exhausted = false
    en.loc, en.engaged = L.guid, inv
    R.placeEnemy(en)
    note("Hunting Horror readies and engages %s", inv.name)
    for _, x in ipairs(R.investigatorsAt(L)) do
      R.enemyAttack(en, x, "Stalked in the Dark")
      if R.G.ended or en.dead then return end
    end
  end
  cov(M.passage, "full; on a failed test the AI takes the damage when it has Beyond the Veil (unless that would lose "
    .. "Harold Walsted / Adam Lynch from a deck of more than 15 cards) or a deck of 8 or fewer cards, else discards "
    .. "the top 5 cards")
  ENC[M.passage] = function(inv)             -- Passage into the Veil
    local en = hh()
    local diff = 3 + ((en and en.loc == inv.loc) and 2 or 0)
    if FX.test(inv, "wil", diff) or inv.defeated then return end
    local veiled = inv.threat and inv.threat["Beyond the Veil"] ~= nil
    local left = inv.health - inv.damage
    local s = R.G.allies and (R.G.allies[M.harold] or R.G.allies[M.adam])
    local ally = s and not s.lost and s.holder == inv
    local takeDamage
    if left <= 1 then takeDamage = false
    elseif veiled then takeDamage = #inv.deck <= 15 or not ally          -- an empty deck would be 10 damage
    else takeDamage = #inv.deck <= 8 and not ally and left > 2 end
    if takeDamage then
      R.hurt(inv, 1, 0, "Passage into the Veil", { direct = true })
      for i = #inv.assets, 1, -1 do
        local a = inv.assets[i]
        if a.rec and a.rec.slot == "Ally" then
          a.dmg = (a.dmg or 0) + 1
          if a.dmg >= (a.hp or 1) then
            table.remove(inv.assets, i)
            if not a.story then inv.discard[#inv.discard + 1] = a.rec end
            note("%s's %s is defeated (Passage into the Veil)", inv.name, a.name)
          end
        end
      end
      FX.checkStoryAllies()
    else
      FX.mill(inv, 5, "Passage into the Veil")
    end
  end
  cov(M.ephemeral, "full; the lost actions come off the investigator's next turn")
  ENC[M.ephemeral] = function(inv)           -- Ephemeral Exhibits
    local ok, margin = FX.test(inv, "int", 3)
    if not ok and not inv.defeated then inv.loseAction = (inv.loseAction or 0) + math.max(1, -margin) end
  end
  cov(M.slithering)
  ENC[M.slithering] = function(inv)          -- Slithering Behind You
    if hh() then hhDoom("Slithering Behind You") return end
    summon(R.locOf(inv), inv, "Slithering Behind You")
    local deck = T.encounterDeck()
    if deck and deck.type == "Deck" then deck.shuffle() end
  end
  -- Chilling Cold (core set)
  cov(M.chill)
  ENC[M.chill] = function(inv)               -- Crypt Chill
    if FX.test(inv, "wil", 4) or inv.defeated then return end
    if not FX.discardAsset(inv, "Crypt Chill") then R.hurt(inv, 2, 0, "Crypt Chill") end
  end
  cov(M.fog)
  ENC[M.fog] = function(inv, card)           -- Obscuring Fog
    local L = R.locOf(inv)
    if #FX.attachedAt(L.guid, M.fog) > 0 then return "discard" end
    R.G.shroudMod = R.G.shroudMod or {}
    R.G.shroudMod[L.guid] = 2
    return FX.attach(card, L.guid)
  end
  for id, h in pairs(ENC) do FX.wrapEnc(id, h) end

  return FX
end
