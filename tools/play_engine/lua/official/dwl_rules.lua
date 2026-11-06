-- Official-scenario rules for the play engine (designer tooling): what the
-- Rules Reference says where The Still Hour's rules layer (rules.lua,
-- flow.lua) plays the campaign's own systems. Loaded after rules.lua,
-- players.lua, flow.lua and ai.lua by lua/official/dwl_engine.lua; it only
-- replaces functions on R for this process (The Still Hour's engine never
-- loads it).
--
--   * no Hours, Dissonance, Approach or Memory: an agenda deck with doom
--     thresholds (doom on the agenda and on cards in play counts), an act
--     deck, standard Mythos doom;
--   * SCED's location sides: the face-up side of a location card is its
--     unrevealed side ("locationFront"), flipping it reveals it ("locationBack",
--     where SCED spawns its clues);
--   * Prey as printed (nearest first, Prey breaks ties), resignation, trauma.

return function(R, T)
  local E = T.E
  local G_ = function() return R.G end

  ------------------------------------------------------------ campaign state stubs --

  local STATE = { dissonance = 0, hour = 1, stage = 0, band = "Calm", memory = 0, investigators = 0 }
  function R.state() return STATE end
  function R.consts() return { reset = 999, glitch = 999, noticed = 999, scar = 0, contest = 999 } end
  function R.raise(n, why) R.log("(no Dissonance in an official scenario: %s ignored)", tostring(why)) end
  function R.checkReset() end
  function R.addMemory() return 0 end
  function R.syncMemory(inv) return 0 end
  function R.investigatorMemory() return 0 end
  function R.pendingYear() end
  function R.rewind() end
  function R.appointedCard() return nil end
  function R.appointedLoc() return nil end
  function R.appointedEngageCheck() end
  function R.syncAppointedArrival() end
  function R.placeAppointed() end
  function R.isCrossing() return false end
  function R.crossKey(a, b) return "-" end
  function R.knows() return false end
  function R.contest() end
  T.tickLog = function() return true end      -- The Still Hour's campaign log is not on this table
  T.setLog = function() end
  -- objectives are the official scenario's (flow.lua's Still Hour version is replaced)
  R.checkObjectives = R.FX.checkObjectives

  ------------------------------------------------------------ agenda and doom --

  --- Doom in play: on the agenda and on cards (enemies) in play.
  function R.doomInPlay()
    local G = R.G
    local n = G.doom or 0
    for _, en in ipairs(G.enemies) do n = n + (en.doom or 0) end
    return n
  end
  function R.agendaId() return R.G.agenda and R.G.agenda.list[R.G.agenda.i] end
  function R.agendaIndex() return R.G.agenda and R.G.agenda.i or 0 end
  function R.threshold()
    local id = R.agendaId()
    return id and (R.card(id).doom or 99) or 99
  end
  --- opts.canAdvance: "this effect can cause the current agenda to advance".
  function R.placeDoom(n, why, opts)
    local G = R.G
    if G.ended or n <= 0 then return end
    G.doom = (G.doom or 0) + n
    G.metrics.doom_sources[why or "?"] = (G.metrics.doom_sources[why or "?"] or 0) + n
    G.metrics.doom_placed = (G.metrics.doom_placed or 0) + n
    R.log("%d doom on the agenda (%s): %d / %d", n, why or "?", R.doomInPlay(), R.threshold())
    if opts and opts.canAdvance then R.checkDoom() end
  end
  function R.checkDoom()
    local G = R.G
    if G.ended then return end
    if R.doomInPlay() >= R.threshold() then R.FX.agendaThreshold() end
  end
  -- doom advancing the "Hourglass" in The Still Hour is the agenda here
  function R.advance(n, why) if (n or 0) > 0 then R.FX.advanceAgenda(why or "advance") end end
  --- RR: when the agenda advances, all doom in play is removed.
  function R.removeAllDoom()
    local G = R.G
    G.doom = 0
    for _, en in ipairs(G.enemies) do en.doom = 0 end
  end

  ------------------------------------------------------------ locations --

  --- SCED: the face-up side of a location card is its unrevealed side; a
  -- flipped (face-down) card shows the revealed side, whose clues SCED spawned.
  function R.scanLocations()
    local G = R.G
    local list = {}
    for _, o in ipairs(T.findAll(function(x) return x.type == "Card" and T.gm(x).type == "Location" end)) do
      local md = T.gm(o)
      -- cards in the aside zone beside the table (set aside or removed from the game) are out of play
      if o.getPosition().x < 60 then
        local def = R.card(md.id)
        local down = o.is_face_down
        local L = G.locs[o.getGUID()] or { guid = o.getGUID() }
        L.obj, L.id, L.def = o, md.id, def
        L.name = def.name or o.getName()
        L.district = "Main"
        L.revealed = down and true or false
        L.side = (down and md.locationBack or md.locationFront) or {}
        L.closed = false
        L.pos = o.getPosition()
        G.locs[L.guid] = L
        list[#list + 1] = L
      end
    end
    table.sort(list, function(a, b) return a.guid < b.guid end)
    G.locList = list
    R.buildGraph()
    return list
  end

  function R.shroud(L)
    return (L.def.shroud or 0) + ((R.G.shroudMod or {})[L.guid] or 0)
  end

  --- Can an investigator move from a to b? (locked doors are the scenario's: FX.canEnter)
  function R.canEnter(a, b, inv)
    if not b or b.closed or not a or not a.adj[b.guid] then return false end
    inv = inv or R.G.routeInv        -- ai.lua asks without saying who moves: the investigator being planned for
    if R.FX.canEnter and not R.FX.canEnter(inv, b) then return false end
    return true
  end

  local revealBase = R.reveal
  function R.reveal(L)
    if L.revealed then return end
    revealBase(L)
    L.side = T.gm(L.obj).locationBack or L.side
    R.buildGraph()
    if R.FX.onReveal then R.FX.onReveal(L) end
  end

  ------------------------------------------------------------ enemies --

  function R.enemyHealth(en)
    if en.maxHealth then return en.maxHealth end
    local h = en.def.health
    if type(h) == "string" then
      local n = tonumber(h:match("^(%d+)")) or 1
      if h:find("perinv", 1, true) then n = n * R.G.n end
      h = n
    end
    h = (h or 1) + (en.def.health_plus_per_investigator or 0) * R.G.n
    en.maxHealth = h
    return h
  end
  function R.sleepwalking() return false end
  function R.enemyFight(en) return math.max(0, (en.def.fight or 0) + (R.FX.fightMod and R.FX.fightMod(en) or 0)) end
  function R.enemyEvade(en) return math.max(0, en.def.evade or 0) end
  function R.onlyPrey() return nil end
  function R.isHunter(en) return R.textHas(en.def, "Hunter.") end
  function R.isAloof(en)
    return R.textHas(en.def, "Aloof.") or (R.FX.aloof and R.FX.aloof(en)) or false
  end
  function R.cannotEvade() return false end

  --- Prey as printed (RR: Prey decides among the investigators the enemy could engage).
  local function preyValue(text, inv)
    local t = text:lower()
    local function rem(k) return k == "health" and (inv.health - inv.damage) or (inv.sanity - inv.horror) end
    if t:find("prey %- least cards in hand") or t:find("prey %- fewest cards in hand") then return -#inv.hand end
    if t:find("prey %- lowest remaining health") then return -rem("health") end
    if t:find("prey %- lowest remaining sanity") then return -rem("sanity") end
    for _, sk in ipairs({ { "willpower", "wil" }, { "intellect", "int" }, { "combat", "com" }, { "agility", "agi" } }) do
      if t:find("prey %- highest %[" .. sk[1] .. "%]") then return inv.stats[sk[2]] end
      if t:find("prey %- lowest %[" .. sk[1] .. "%]") then return -inv.stats[sk[2]] end
    end
    return nil
  end
  R.preyValue = preyValue
  function R.prey(en, cands)
    local text = tostring(en.def.text or "")
    local best, bv
    for _, inv in ipairs(cands) do
      local v = preyValue(text, inv)
      -- no Prey: the lead investigator decides (the sturdiest takes it)
      if v == nil then v = (inv.health - inv.damage) + (inv.sanity - inv.horror) end
      if bv == nil or v > bv then best, bv = inv, v end
    end
    return best
  end

  --- Move an enemy one location toward a location (enemy paths ignore locked doors).
  function R.enemyStepToward(en, goal)
    local G = R.G
    local here = G.locs[en.loc]
    if not here or not goal or here == goal then return false end
    local step = R.route(here, goal, { enemy = true })
    if not step then return false end
    en.loc = step.guid
    if en.engaged and en.engaged.loc ~= step.guid then en.engaged = nil end
    R.placeEnemy(en)
    G.metrics.enemy_moves = G.metrics.enemy_moves + 1
    R.log("%s moves to %s", en.name, step.name)
    R.FX.onEnemyMoved(en)
    if not G.ended then R.engageAt(step) end
    return true
  end

  ------------------------------------------------------------ damage, defeat, trauma --

  local hurtBase = R.hurt
  function R.hurt(inv, dmg, hor, source, opts)
    opts = opts or {}
    if R.FX.allDirect and R.FX.allDirect() then opts.direct = true end   -- Light of Aforgomon
    -- the scenario's key allies ("Jazz" Mulligan, Dr. Morgan, Peter Clover) are assigned damage or
    -- horror only when the investigator could not take it: the party protects them
    local hidden = {}
    if not opts.direct then
      local lethal = (dmg > 0 and inv.damage + dmg >= inv.health) or (hor > 0 and inv.horror + hor >= inv.sanity)
      if not lethal then
        for i = #inv.assets, 1, -1 do
          if inv.assets[i].story then hidden[#hidden + 1] = table.remove(inv.assets, i) end
        end
      end
    end
    local dealt = hurtBase(inv, dmg, hor, source, opts)
    for _, a in ipairs(hidden) do inv.assets[#inv.assets + 1] = a end
    return dealt
  end

  local defeatBase = R.defeat
  function R.defeat(inv, source, opts)
    if inv.defeated then return end
    -- RR: an investigator defeated by damage suffers 1 physical trauma, by horror 1 mental
    if inv.damage >= inv.health then inv.trauma.physical = inv.trauma.physical + 1
    elseif inv.horror >= inv.sanity then inv.trauma.mental = inv.trauma.mental + 1 end
    inv.defeatedCause = (inv.damage >= inv.health) and "physical" or "mental"
    R.G.metrics.defeat_rounds = R.G.metrics.defeat_rounds or {}
    table.insert(R.G.metrics.defeat_rounds, { id = inv.id, round = R.G.round, by = tostring(source or "?"), cause = inv.defeatedCause })
    -- the engine's defeat ends the game when nobody is left; a resigned investigator is not defeated
    local G = R.G
    local others = false
    for _, x in ipairs(G.inv) do if x ~= inv and not x.defeated then others = true end end
    if not others and G.anyResigned then
      -- everyone else resigned: the act's "each undefeated investigator has resigned" may resolve
      inv.defeated = true
      G.metrics.defeats = G.metrics.defeats + 1
      G.metrics.defeated[inv.id] = true
      local src = tostring(source or "?"):gsub(" %(.*%)$", "")
      G.metrics.defeated_by[src] = (G.metrics.defeated_by[src] or 0) + 1
      G.metrics.defeated_who[inv.id] = (G.metrics.defeated_who[inv.id] or 0) + 1
      R.log("%s is DEFEATED (%s)", inv.name, source or "?")
      R.FX.allGone()
      return
    end
    defeatBase(inv, source, opts)
  end

  --- Resign: the investigator leaves the scenario (not defeated).
  function R.resign(inv)
    local G = R.G
    if inv.defeated then return end
    inv.defeated, inv.resigned = true, true
    G.anyResigned = true
    G.metrics.resigned = G.metrics.resigned or {}
    G.metrics.resigned[inv.id] = G.round
    R.log("%s RESIGNS at %s", inv.name, (R.locOf(inv) or {}).name or "?")
    for _, en in ipairs(G.enemies) do if en.engaged == inv then en.engaged = nil ; R.placeEnemy(en) end end
    if T.alive(inv.mini) then inv.mini.setPosition({ -60, 2, -20 + 4 * inv.idx }) end
    local any = false
    for _, x in ipairs(G.inv) do if not x.defeated then any = true end end
    if not any then R.FX.allGone() end
  end
end
