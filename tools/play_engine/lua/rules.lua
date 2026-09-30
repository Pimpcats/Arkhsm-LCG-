-- The play engine's rules layer (designer tooling).
--
-- Arkham Horror LCG's round structure (Rules Reference) and the campaign's
-- own rules (the player guide's Campaign Rules), acting on the table through
-- tablekit.lua. What lives here is what a player keeps in their head: whose
-- turn it is, hands and decks, damage, which enemy is engaged with whom.
-- Everything a card or box puts on the table (locations, clues, encounter
-- cards, the Hours, the chaos bag, the Control's counters) is read from and
-- changed on the table.

return function(R, T)
  local E = T.E
  local J = T.J

  ------------------------------------------------------------ helpers --

  function R.log(fmt, ...)
    if R.G and R.G.trace then
      local s = select("#", ...) > 0 and string.format(fmt, ...) or fmt
      R.G.trace[#R.G.trace + 1] = string.format("[r%d %s] %s", R.G.round or 0, R.G.phase or "-", s)
      if R.G.live then io.stderr:write(R.G.trace[#R.G.trace], "\n") end
    end
  end

  function R.rand() return E.rand() end
  function R.pick(list) if #list == 0 then return nil end return list[math.floor(R.rand() * #list) + 1] end
  function R.shuffle(list)
    for i = #list, 2, -1 do
      local j = math.floor(R.rand() * i) + 1
      list[i], list[j] = list[j], list[i]
    end
    return list
  end
  function R.count(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end
  function R.clamp(v, a, b) return math.max(a, math.min(b, v)) end

  function R.card(id) return R.CARDS[id] or {} end
  function R.hasTrait(def, trait) return tostring(def.traits or ""):find(trait, 1, true) ~= nil end
  function R.textHas(def, s) return tostring(def.text or ""):find(s, 1, true) ~= nil end

  ------------------------------------------------------------ campaign --

  function R.state()
    local G = R.G
    if not G.stCache or G.stCache.t ~= G.clock then
      G.stCache = { t = G.clock, v = T.st() }
    end
    return G.stCache.v
  end
  function R.touch() R.G.clock = (R.G.clock or 0) + 1 end
  function R.band() return R.state().band end
  function R.dissonance() return R.state().dissonance end
  function R.hour() return R.state().hour end
  function R.stage() return R.state().stage end
  function R.knows(fact) return R.G.knowledge[fact] == true end

  -- Contest the Crossing: progress 7, 6 with one investigator (Constants.contestTarget)
  R.CONTEST_TARGET = 7
  function R.consts()
    local n = R.G.n
    local reset = 8 * n                         -- Constants.forCount
    if n == 1 then reset = 16 end               -- solo: the two-investigator bands
    local noticed = math.floor(2 * reset / 3)
    return { reset = reset, glitch = math.floor(reset / 3), noticed = noticed, scar = (n == 1) and 4 or 2 * n,
             contest = (R.WHATIF or {}).contestFlat
               or ((R.G.cfg.contestPerInv or R.CONTEST_PER_INV) and (R.G.cfg.contestPerInv or R.CONTEST_PER_INV) * n)
               or (n == 1 and R.CONTEST_TARGET - 1 or R.CONTEST_TARGET) }
  end

  --- Raise (or lower) Dissonance through the Control's button.
  -- cost = the investigator paid it as a cost (leaning on the loop).
  function R.raise(n, why, costInv)
    if n == 0 then return end
    local before = R.dissonance()
    T.dissonance(n)
    R.touch()
    local after = R.dissonance()
    R.log("Dissonance %+d (%s): %d -> %d", n, why or "?", before, after)
    local m = R.G.metrics
    if n > 0 then
      m.dissonance_sources[why or "?"] = (m.dissonance_sources[why or "?"] or 0) + (after - before)
    end
    if costInv then
      T.api("shApiTally", { id = costInv.id, kind = "raises", delta = 1 })
      costInv.raisedCost = (costInv.raisedCost or 0) + 1
    end
    m.diss_max = math.max(m.diss_max, after)
    R.syncAppointedArrival()
    R.checkReset()
  end
  function R.lower(n, why) R.raise(-n, why) end

  function R.checkReset()
    local G = R.G
    if G.ended then return end
    if R.dissonance() >= R.consts().reset then
      R.endLoop("reset")
    end
  end

  function R.addMemory(inv, n, why)
    if n == 0 then return end
    T.api("shApiOnCardMemory", { id = inv.id, delta = n })
    inv.memory = math.max(0, (inv.memory or 0) + n)
    local m = R.G.metrics
    if n > 0 then
      m.memory_on_cards[why or "?"] = (m.memory_on_cards[why or "?"] or 0) + n
    end
    R.log("%s Memory %+d (%s) -> %d", inv.name, n, why or "?", inv.memory)
  end

  function R.pendingYear(inv, n, why)
    for _ = 1, n do T.click(inv.card, "Years pending") end
    inv.pendingYears = (inv.pendingYears or 0) + n
    R.log("%s gains %d Year(s) pending (%s)", inv.name, n, why)
    R.G.metrics.card_years = R.G.metrics.card_years + n
  end

  ------------------------------------------------------------ the Hourglass --

  --- Advance the Hourglass by n Hours (a Skip, or doom): the Control's Hour
  -- button once per Hour, the Hours deck moved to match, then the parts of
  -- each Hour's "When reached" text the Control leaves to the players.
  --- Doom on the current Hour (engine-tracked; the table's doom tokens).
  -- The Mythos phase places 1 and checks the threshold (the Hour card's doom
  -- value); card effects that "place 1 doom on the current Hour" wait for
  -- that check, as in the Rules Reference.
  function R.threshold()
    local c = R.card("sthr-hour-" .. R.hour()) or {}
    return tonumber(c.doom) or 1
  end
  function R.placeDoom(n, why)
    local G = R.G
    if G.ended or n <= 0 then return end
    G.doom = (G.doom or 0) + n
    local m = G.metrics
    m.doom_sources[why or "?"] = (m.doom_sources[why or "?"] or 0) + n
    R.log("%d doom on Hour %d (%s): %d / %d", n, R.hour(), why or "?", G.doom, R.threshold())
  end
  --- Mythos step: check the doom threshold.
  function R.checkDoom()
    local G = R.G
    if (G.doom or 0) >= R.threshold() then
      R.advance(1, "doom")
    end
  end

  function R.advance(n, why)
    local G = R.G
    local turned = false
    for _ = 1, n do
      if G.ended then return end
      G.doom = 0            -- an advance removes all doom in play (cancelled or not)
      -- cancel effects: I Remember the Ending, the name kept unspoken, It Means 'Wait'
      if R.cancelAdvance(why) then
        R.log("Hourglass advance (%s) cancelled", why)
      else
        local before = R.hour()
        if before >= 9 then return end
        local fx = R.hourPrevent and R.hourPrevent(before + 1)
        R.G.metrics.last_diss = R.dissonance()
        local s0 = fx and T.st()
        R.moveHourCard(before)                 -- the current Hour is turned over and set aside
        T.ctl("Hour")
        E.run(0.2)
        R.touch()
        local now = R.hour()
        if fx then
          -- its "When reached" was cancelled: undo what the Control applied
          -- (guide: Cancelled effects)
          local s1 = T.st()
          if s1.dissonance > s0.dissonance then T.dissonance(s0.dissonance - s1.dissonance) end
          for _ = 1, s1.stage - s0.stage do T.ctl("Appointed", true) end
          if s1.hourSix and not s0.hourSix then T.ctl("Undo Hour VI") end
          E.run(0.2)
          R.touch()
        end
        R.G.metrics.hour_sources[why or "?"] = (R.G.metrics.hour_sources[why or "?"] or 0) + 1
        turned = true
        -- the Hour turns: each investigator heals 1 horror (guide: The Hourglass)
        local heal = (R.WHATIF or {}).hourHeal or 1
        for _, x in ipairs(R.aliveInvs()) do
          if heal > 0 and x.horror > 0 then
            R.heal(x, 0, math.min(heal, x.horror))
            R.G.metrics.hour_heal = (R.G.metrics.hour_heal or 0) + 1
          end
        end
        R.log("Hourglass advances (%s): Hour %d -> %d", why or "?", before, now)
        do
          -- what the Control applied (Hour III's and VIII's Dissonance)
          local m = R.G.metrics
          local d = R.dissonance()
          if d > (m.last_diss or 0) and (now == 3 or now == 8) then
            m.dissonance_sources["Hour " .. now] = (m.dissonance_sources["Hour " .. now] or 0) + (d - (m.last_diss or 0))
          end
          m.diss_max = math.max(m.diss_max, d)
        end
        G.lastAdvanceRound = G.round
        -- a removed Hour (IV) is stepped over by the Control: move its card too
        if now > before + 1 then R.moveHourCard(before + 1, true) end
        R.onHourReached(now, fx)
        R.checkReset()
        R.G.metrics.last_diss = R.dissonance()
        if now >= 9 then return end
      end
    end
    if turned and not G.ended and R.FX.afterAdvance then R.FX.afterAdvance() end
  end

  function R.rewind(n, why, alreadyCounted)
    R.G.doom = 0
    for _ = 1, n do
      local before = R.hour()
      if before <= 1 then return end
      if not alreadyCounted then T.ctl("Hour", true) end
      E.run(0.1)
      R.touch()
      local now = R.hour()
      R.returnHourCard(now, before)
      R.G.metrics.rewinds = R.G.metrics.rewinds + 1
      R.log("Hourglass rewinds (%s): Hour %d -> %d", why or "?", before, now)
      if R.G.impassable then R.G.impassable = nil end   -- Hour IV lasts until the Hourglass next moves
    end
  end

  -- the Hours deck on the table follows the Control: the current Hour is
  -- turned over and set aside where SCED's own "advance" puts it
  local function hourName(h) return "Hour " .. ({ "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX" })[h] .. " —" end
  function R.moveHourCard(h, removed)
    local G = R.G
    local agenda = G.agendaPos
    if not agenda then return end
    local want = hourName(h)
    local pile = T.find(function(o) return (o.type == "Deck" or o.type == "Card") and T.dist(o.getPosition(), agenda) < 0.8 end)
    if not pile then return end
    local card
    if pile.type == "Card" then
      card = pile
    else
      for _, e in ipairs(pile.getObjects()) do
        if tostring(e.name or e.nickname):sub(1, #want) == want then
          card = pile.takeObject({ guid = e.guid, smooth = false })
          break
        end
      end
    end
    if not card then return end
    E.run(0.05)
    local aside = T.mythosSpot("agendaAside")
    aside.y = aside.y + 0.2 * (#G.hoursAside + 1)
    card.setPosition(aside)
    card.setRotation({ 0, 180, 180 })
    G.hoursAside[#G.hoursAside + 1] = { hour = h, obj = card, removed = removed }
  end
  function R.returnHourCard(now, before)
    local G = R.G
    -- put back every Hour set aside after `now` (a removed Hour is stepped over)
    while #G.hoursAside > 0 and G.hoursAside[#G.hoursAside].hour >= now do
      local e = table.remove(G.hoursAside)
      if T.alive(e.obj) then
        local pile = T.find(function(o) return o ~= e.obj and (o.type == "Deck" or o.type == "Card") and T.dist(o.getPosition(), G.agendaPos) < 0.8 end)
        e.obj.setRotation({ 0, 180, 0 })
        if pile then pile.putObject(e.obj) else e.obj.setPosition({ G.agendaPos.x, G.agendaPos.y + 0.3, G.agendaPos.z }) end
      end
    end
    E.run(0.05)
  end

  ------------------------------------------------------------ locations --

  -- district of each campaign location (the guide's map)
  R.DISTRICT = {
    ["sthr-loc-square"] = "Prologue", ["sthr-loc-longpier"] = "Prologue", ["sthr-loc-almanacsteps"] = "Prologue",
    ["sthr-loc-hubsquare"] = "Square", ["sthr-loc-townhallsteps"] = "Square", ["sthr-loc-recordsoffice"] = "Square",
    ["sthr-loc-well"] = "Square",
    ["sthr-loc-nave"] = "Church", ["sthr-loc-belfry"] = "Church", ["sthr-loc-floodedcrypt"] = "Church", ["sthr-loc-vestry"] = "Church",
    ["sthr-loc-milestones"] = "Road", ["sthr-loc-lowbridge"] = "Road", ["sthr-loc-turning"] = "Road",
    ["sthr-loc-lanternroom"] = "Lighthouse", ["sthr-loc-windingstair"] = "Lighthouse", ["sthr-loc-keepersquarters"] = "Lighthouse",
    ["sthr-loc-wheel"] = "Fairground", ["sthr-loc-hallofmirrors"] = "Fairground", ["sthr-loc-ticketbooth"] = "Fairground",
    ["sthr-loc-readingroom"] = "Almanac", ["sthr-loc-press"] = "Almanac", ["sthr-loc-sealedstudy"] = "Almanac",
  }
  -- locations whose back is a revealed calm side (a Knowledge entry flips them)
  R.CALM_BACK = { ["sthr-loc-townhallsteps"] = "the-sheriff-is-already-dead", ["sthr-loc-lanternroom"] = "the-lamp-was-never-lit" }

  function R.scanLocations()
    local G = R.G
    local list = {}
    for _, o in ipairs(T.findAll(function(x) return x.type == "Card" and T.gm(x).type == "Location" end)) do
      local md = T.gm(o)
      local def = R.card(md.id)
      local down = o.is_face_down
      local calm = down and R.CALM_BACK[md.id] and R.knows(R.CALM_BACK[md.id])
      local side = (down and md.locationBack or md.locationFront) or {}
      local L = G.locs[o.getGUID()] or { guid = o.getGUID() }
      L.obj, L.id, L.name, L.def = o, md.id, o.getName(), def
      L.district = R.DISTRICT[md.id] or "?"
      L.revealed = (not down) or calm and true or false
      L.calm = calm and true or false
      L.side = side
      L.closed = T.hasLabel(o, "CLOSED")
      L.pos = o.getPosition()
      G.locs[L.guid] = L
      list[#list + 1] = L
    end
    table.sort(list, function(a, b) return a.guid < b.guid end)
    G.locList = list
    R.buildGraph()
    return list
  end

  local function split(s)
    local out = {}
    for part in string.gmatch(tostring(s or ""), "[^|]+") do out[#out + 1] = part end
    return out
  end

  --- Connections from each location's visible side (the data SCED's play
  -- area draws its connection lines from). Closed locations connect to nothing.
  function R.buildGraph()
    local G = R.G
    local byIcon = {}
    for _, L in ipairs(G.locList) do
      L.adj = {}
      if not L.closed then
        for _, ic in ipairs(split(L.side.icons)) do
          byIcon[ic] = byIcon[ic] or {}
          table.insert(byIcon[ic], L)
        end
      end
    end
    for _, L in ipairs(G.locList) do
      if not L.closed then
        for _, c in ipairs(split(L.side.connections)) do
          for _, other in ipairs(byIcon[c] or {}) do
            if other ~= L then L.adj[other.guid] = other ; other.adj[L.guid] = L end
          end
        end
      end
    end
  end

  function R.locById(id)
    for _, L in ipairs(R.G.locList) do if L.id == id then return L end end
    return nil
  end
  function R.clues(L) return #T.cluesOn(L.obj) end

  function R.shroud(L)
    local G = R.G
    local s = L.calm and (L.def.back_shroud or L.def.shroud) or L.def.shroud or 0
    if G.risingWater and G.risingWater[L.guid] then s = s + G.risingWater[L.guid] end
    if L.id == "sthr-loc-recordsoffice" then
      for _, en in ipairs(G.enemies) do if en.id == "sthr-wearssheriff" then s = s + 1 end end
    end
    return s
  end

  function R.isCrossing(a, b)
    if a.district == b.district or a.district == "Prologue" or b.district == "Prologue" then return false end
    -- the Lighthouse stands at the end of the Sunken Road: the Turning - the
    -- Winding Stair joins two districts but is not a district connection
    -- (guide: Districts and travel), unless a what-if puts the old rule back
    if R.crossKey(a, b) == "Lighthouse|Road" and not (R.WHATIF or {}).lighthouseCrossingCosts then return false end
    return true
  end
  function R.crossKey(a, b)
    local x, y = a.district, b.district
    if x > y then x, y = y, x end
    return x .. "|" .. y
  end

  --- Can an investigator move from a to b along a connection?
  function R.canEnter(a, b, inv)
    local G = R.G
    if b.closed then return false end
    if G.impassable == b.guid then return false end
    if not a.adj[b.guid] then return false end
    -- the Winding Stair: only its own ability leads up to the Lantern Room
    if a.id == "sthr-loc-windingstair" and b.id == "sthr-loc-lanternroom" then return false end
    return true
  end

  function R.investigatorsAt(L)
    local l = {}
    for _, inv in ipairs(R.G.inv) do if not inv.defeated and inv.loc == L.guid then l[#l + 1] = inv end end
    return l
  end
  function R.locOf(inv) return R.G.locs[inv.loc] end

  --- Shortest paths in actions from L (BFS; enemies ignore the stair rule
  -- only when told). Returns dist, prev, crossings.
  function R.paths(from, opts)
    opts = opts or {}
    local dist, prev = { [from.guid] = 0 }, {}
    local q, h = { from }, 1
    while q[h] do
      local a = q[h] ; h = h + 1
      for g, b in pairs(a.adj) do
        local ok = opts.enemy and (not b.closed) or R.canEnter(a, b)
        if opts.enemy and R.G.impassable == b.guid then ok = false end
        if ok and dist[g] == nil then
          dist[g] = dist[a.guid] + 1
          prev[g] = a
          q[#q + 1] = b
        end
      end
      -- the stair's own climb counts as one action
      if not opts.enemy and a.id == "sthr-loc-windingstair" then
        local lr = R.locById("sthr-loc-lanternroom")
        if lr and not lr.closed and dist[lr.guid] == nil then
          dist[lr.guid] = dist[a.guid] + 1 ; prev[lr.guid] = a ; q[#q + 1] = lr
        end
      end
    end
    return dist, prev
  end

  --- The next step from a toward b, and the number of district crossings on the way.
  function R.route(a, b, opts)
    local dist, prev = R.paths(a, opts)
    if dist[b.guid] == nil then return nil end
    local path = { b }
    local cur = b
    while prev[cur.guid] do cur = prev[cur.guid] ; table.insert(path, 1, cur) end
    local crossings = 0
    for i = 2, #path do if R.isCrossing(path[i - 1], path[i]) then crossings = crossings + 1 end end
    return path[2], dist[b.guid], crossings, path
  end

  ------------------------------------------------------------ investigators --

  function R.skillBase(inv, skill)
    local v = inv.stats[skill] or 1
    -- persistent weaknesses and effects
    if inv.threat and inv.threat["Haunted"] then v = v - 1 end
    if inv.mindOverMatter and (skill == "com" or skill == "agi") then v = math.max(v, inv.stats.int) end
    return v
  end

  function R.aliveInvs()
    local l = {}
    for _, inv in ipairs(R.G.inv) do if not inv.defeated then l[#l + 1] = inv end end
    return l
  end

  --- Deal damage/horror to an investigator: allies and armor soak first
  -- (the AI assigns), then defeat.
  function R.hurt(inv, dmg, hor, source, opts)
    opts = opts or {}
    if inv.defeated or (dmg <= 0 and hor <= 0) then return end
    local G = R.G
    -- Elias: take damage for another investigator at his location
    if dmg > 0 and not opts.direct and inv.id ~= "sthrelias" then
      local elias = R.invById("sthrelias")
      if elias and not elias.defeated and elias.loc == inv.loc and not elias.round.redirect
         and (elias.health - elias.damage) > dmg + 1 then
        elias.round.redirect = true
        R.log("Elias takes %d damage for %s", dmg, inv.name)
        R.hurt(elias, dmg, 0, source .. " (redirected)", { direct = true })
        R.addMemory(elias, 1, "Elias: took damage for another")
        dmg = 0
        if hor <= 0 then return end
      end
    end
    if not opts.direct then
      for _, a in ipairs(inv.assets) do
        if dmg > 0 and (a.hp or 0) > (a.dmg or 0) then
          local take = math.min(dmg, a.hp - a.dmg)
          a.dmg = a.dmg + take ; dmg = dmg - take
          if a.name == "Guard Dog" and opts.enemy and take > 0 then R.damageEnemy(opts.enemy, 1, inv, "Guard Dog") end
        end
        if hor > 0 and (a.sp or 0) > (a.hor or 0) then
          local take = math.min(hor, a.sp - a.hor)
          a.hor = a.hor + take ; hor = hor - take
        end
      end
      -- discard defeated assets
      for i = #inv.assets, 1, -1 do
        local a = inv.assets[i]
        if (a.hp and a.dmg >= a.hp) or (a.sp and a.sp > 0 and a.hor >= a.sp) then
          table.remove(inv.assets, i)
          inv.discard[#inv.discard + 1] = a.rec
          R.log("%s's %s is defeated", inv.name, a.name)
        end
      end
    end
    inv.damage = inv.damage + dmg
    inv.horror = inv.horror + hor
    G.metrics.damage = G.metrics.damage + dmg
    G.metrics.horror = G.metrics.horror + hor
    local src = tostring(source or "?"):gsub(" %(.*%)$", "")
    if dmg > 0 then G.metrics.damage_by[src] = (G.metrics.damage_by[src] or 0) + dmg end
    if hor > 0 then G.metrics.horror_by[src] = (G.metrics.horror_by[src] or 0) + hor end
    R.log("%s takes %d damage, %d horror (%s): %d/%d, %d/%d", inv.name, dmg, hor, source or "?",
      inv.damage, inv.health, inv.horror, inv.sanity)
    -- Psychosis / Hypochondria
    if hor > 0 and inv.threat["Psychosis"] and not opts.fromWeakness then R.hurt(inv, 1, 0, "Psychosis", { direct = true, fromWeakness = true }) end
    if dmg > 0 and inv.threat["Hypochondria"] and not opts.fromWeakness then R.hurt(inv, 0, 1, "Hypochondria", { direct = true, fromWeakness = true }) end
    if inv.damage >= inv.health or inv.horror >= inv.sanity then R.defeat(inv, source, opts) end
  end

  function R.heal(inv, dmg, hor)
    inv.damage = math.max(0, inv.damage - (dmg or 0))
    inv.horror = math.max(0, inv.horror - (hor or 0))
  end

  function R.invById(id)
    for _, inv in ipairs(R.G.inv) do if inv.id == id then return inv end end
    return nil
  end

  function R.defeat(inv, source, opts)
    local G = R.G
    if inv.defeated then return end
    -- "I Get Out" (Birdie): not defeated
    if R.P.tryIGetOut(inv) then return end
    inv.defeated = true
    G.metrics.defeats = G.metrics.defeats + 1
    G.metrics.defeated[inv.id] = true
    local src = tostring(source or "?"):gsub(" %(.*%)$", "")
    G.metrics.defeated_by[src] = (G.metrics.defeated_by[src] or 0) + 1
    G.metrics.defeated_who[inv.id] = (G.metrics.defeated_who[inv.id] or 0) + 1
    R.log("%s is DEFEATED (%s)", inv.name, source or "?")
    -- clues go on the location; engaged enemies stay, unengaged
    local L = R.locOf(inv)
    if inv.clues > 0 and L then
      for _, tok in ipairs(inv.clueTokens) do if T.alive(tok) then tok.destruct() end end
      inv.clueTokens = {}
      T.spawnClueOn(L.obj, inv.clues)
      inv.clues = 0
    end
    for _, en in ipairs(G.enemies) do
      if en.engaged == inv then en.engaged = nil ; R.placeEnemy(en) end
    end
    if G.appointed.engaged == inv then G.appointed.engaged = nil end
    if opts and opts.enemy and opts.enemy.id == "sthr-housewins" then
      for _ = 1, 3 do T.ctl("Memory", true) end
    end
    -- the minicard leaves the map
    if T.alive(inv.mini) then inv.mini.setPosition({ -60, 2, -20 + 4 * inv.idx }) end
    local any = false
    for _, x in ipairs(G.inv) do if not x.defeated then any = true end end
    if not any then R.endLoop("defeat") end
  end

  ------------------------------------------------------------ moving --

  --- Move an investigator to location b (along a connection unless told).
  -- opts.noHour: this move does not advance the Hourglass;
  -- opts.noAoO: does not provoke attacks of opportunity.
  function R.moveInv(inv, b, opts)
    opts = opts or {}
    local G = R.G
    local a = R.locOf(inv)
    if not b or b == a then return false end
    inv.loc = b.guid
    local slot = #R.investigatorsAt(b)
    if T.alive(inv.mini) then T.moveMini(inv.mini, b.obj, slot) end
    G.metrics.moves = G.metrics.moves + 1
    R.log("%s moves %s -> %s", inv.name, a and a.name or "?", b.name)
    -- engaged enemies move with the investigator
    for _, en in ipairs(G.enemies) do if en.engaged == inv then en.loc = b.guid ; R.placeEnemy(en) end end
    if G.appointed.engaged == inv then G.appointed.loc = b.guid ; R.placeAppointed(b) end
    -- entering an unrevealed location reveals it (SCED spawns its clues)
    if not b.revealed and not b.closed then R.reveal(b) end
    if a and (a.id == "sthr-loc-lowbridge" or b.id == "sthr-loc-lowbridge") then inv.bridgeFlag = true end
    R.FX.onEnter(inv, b)
    R.engageAt(b)
    if G.ended then return true end
    -- district travel costs time (guide: Districts and travel): after the
    -- first move each round along a district connection, the Hourglass
    -- advances; a move not along a connection, or one that says it does not
    -- advance it, costs nothing and does not count as that first move
    if a and not opts.teleport and R.isCrossing(a, b) then
      local key = R.crossKey(a, b)
      G.metrics.crossings = G.metrics.crossings + 1
      if not opts.noHour and not G.crossedThisRound[key] and not R.FX.freeCrossing(a, b, inv) then
        G.crossedThisRound[key] = true
        G.metrics.crossing_hours = G.metrics.crossing_hours + 1
        R.placeDoom(1, "district crossing")
      end
    end
    return true
  end

  function R.reveal(L)
    if L.revealed then return end
    E.playerFlip(L.obj)
    E.run(0.5)
    L.revealed = true
    R.log("%s is revealed (%d clue(s))", L.name, R.clues(L))
  end

  ------------------------------------------------------------ enemies --

  function R.enemyDef(id) return R.card(id) end

  --- Is this enemy Sleepwalking right now? (Echo keyword, guide: Echoes and Sleepwalking)
  function R.sleepwalking(en)
    local G = R.G
    if not R.hasTrait(en.def, "Echo") then return false end
    if en.wakeLoop then return false end                          -- The Eighth Grave
    if G.crowdTurns then return false end                           -- The Crowd Turns
    if en.id == "sthr-lamplighterecho" and R.P.lampInPlay() then return false end
    local L = G.locs[en.loc]
    if G.walksBesideCurrent and L and L.id == "sthr-loc-turning" then return false end
    local band = R.band()
    if G.lampLit and L and (L.district == "Lighthouse" or L.district == "Road") and band ~= "Noticed" then return true end
    return band == "Calm"
  end

  function R.enemyFight(en)
    local f = en.def.fight or 0
    if R.G.hourEightFight then f = f + 1 end
    if R.knows("who-walks-beside-you") and R.hasTrait(en.def, "Echo") then f = f - 1 end
    return math.max(0, f)
  end
  function R.enemyEvade(en) return en.def.evade or 0 end
  function R.isHunter(en)
    if R.textHas(en.def, "Hunter.") then return true end
    if en.id == "sthr-waitingcongregation" and R.band() ~= "Calm" then return true end
    return false
  end
  function R.isAloof(en) return R.textHas(en.def, "Aloof.") end
  function R.hasRetaliate(en)
    if R.textHas(en.def, "Retaliate.") then return true end
    if en.id == "sthr-lamplighterecho" and R.P.lampInPlay() then return true end
    return false
  end

  --- Put an enemy card where the engine says it is: engaged ones in the
  -- threat area of that investigator's playmat, others below their location.
  function R.placeEnemy(en)
    if not T.alive(en.obj) then return end
    local G = R.G
    if en.engaged then
      local mat = T.mat(en.engaged.color)
      local k = 0
      for _, x in ipairs(G.enemies) do if x.engaged == en.engaged then if x == en then break end k = k + 1 end end
      local p = mat.positionToWorld({ -0.6 + 0.55 * k, 0.3, -0.63 })
      en.obj.setPosition({ p.x, p.y + 0.2, p.z })
      en.obj.setRotation({ 0, mat.getRotation().y, en.exhausted and 0 or 0 })
    else
      local L = G.locs[en.loc]
      if not L then return end
      local k = 0
      for _, x in ipairs(G.enemies) do if x.loc == en.loc and not x.engaged then if x == en then break end k = k + 1 end end
      local p = L.obj.getPosition()
      en.obj.setPosition({ p.x - 1.0 + 1.0 * k, p.y + 0.2, p.z + 2.45 })
      en.obj.setRotation({ 0, 270, 0 })
    end
  end

  --- Spawn an enemy card (already out of the deck) at location L, engaged
  -- with inv when given and it can engage.
  function R.spawnEnemy(card, L, inv, meta)
    local G = R.G
    local md = T.gm(card)
    local def = R.enemyDef(md.id)
    local en = { obj = card, id = md.id, name = card.getName(), def = def, loc = L and L.guid, damage = 0,
                 exhausted = false, engaged = nil, uid = (G.nextEnemy or 0) + 1, res = 0 }
    G.nextEnemy = en.uid
    G.enemies[#G.enemies + 1] = en
    card.setRotation({ 0, 270, 0 })
    local m = G.metrics
    m.spawns[#m.spawns + 1] = { id = en.id, at = L and L.id or "?", want = meta and meta.want or "engaged", ok = meta and meta.ok ~= false,
                                note = meta and meta.note or nil, round = G.round }
    if meta and meta.ok == false then
      m.bad_spawns[#m.bad_spawns + 1] = { id = en.id, want = meta.want, used = L and L.id or "?", note = meta.note }
    end
    R.log("%s spawns at %s%s", en.name, L and L.name or "?", inv and (" (drawn by " .. inv.name .. ")") or "")
    if inv and inv.loc == en.loc and not R.sleepwalking(en) and not R.isAloof(en) then
      en.engaged = inv
    end
    R.placeEnemy(en)
    if not en.engaged then R.engageAt(G.locs[en.loc]) end
    R.FX.onSpawn(en)
    return en
  end

  --- Ready, awake, non-aloof enemies at L engage an investigator there (prey).
  function R.engageAt(L)
    if not L then return end
    local here = R.investigatorsAt(L)
    if #here == 0 then return end
    for _, en in ipairs(R.G.enemies) do
      if en.loc == L.guid and not en.engaged and not en.exhausted and not R.sleepwalking(en) and not R.isAloof(en) then
        en.engaged = R.prey(en, here)
        R.log("%s engages %s", en.name, en.engaged.name)
        R.placeEnemy(en)
      end
    end
    R.appointedEngageCheck()
  end

  --- Prey among candidates (card text; else the lead investigator decides: the sturdiest).
  function R.prey(en, cands)
    local text = tostring(en.def.text or "")
    local best, bv
    for _, inv in ipairs(cands) do
      local v
      if text:find("Prey – Most Memory", 1, true) then v = inv.memory or 0
      elseif text:find("Prey – Most clues", 1, true) then v = inv.clues
      elseif text:find("Prey – Most resources", 1, true) then v = inv.resources
      else v = (inv.health - inv.damage) + (inv.sanity - inv.horror) + (inv.id == "sthrelias" and 5 or 0) end
      if bv == nil or v > bv then best, bv = inv, v end
    end
    return best
  end

  function R.damageEnemy(en, n, inv, why)
    local G = R.G
    if n <= 0 or en.dead then return end
    if en.id == "sthr-onewhorides" and not en.exhausted then
      R.log("%s is ready: it cannot be dealt damage", en.name)
      return
    end
    if R.sleepwalking(en) then return end
    en.damage = en.damage + n
    local hp = en.def.health or 1
    R.log("%s deals %d damage to %s (%s): %d/%d", inv and inv.name or "?", n, en.name, why or "?", en.damage, hp)
    if en.damage >= hp then R.defeatEnemy(en, inv) end
  end

  function R.defeatEnemy(en, inv)
    local G = R.G
    en.dead = true
    for i, x in ipairs(G.enemies) do if x == en then table.remove(G.enemies, i) break end end
    G.metrics.enemies_defeated = G.metrics.enemies_defeated + 1
    G.metrics.defeated_by_id[en.id] = (G.metrics.defeated_by_id[en.id] or 0) + 1
    R.log("%s is defeated", en.name)
    R.FX.onEnemyDefeated(en, inv)
    if (en.def.victory or 0) > 0 then
      -- Victory X: record it on the log (the Control banks it the first time)
      T.tickLog("v:" .. en.id, true)
      G.metrics.victory[#G.metrics.victory + 1] = en.id
      -- to the victory display
      en.obj.setPosition({ 6, 2, -18 + #G.metrics.victory })
    else
      if en.weakness then
        en.obj.destruct()
      else
        T.discardEncounter(en.obj)
      end
    end
    if inv then R.P.afterDefeatEnemy(inv, en) end
  end

  ------------------------------------------------------------ the Appointed --

  function R.appointedCard() return T.cardWithId("sthr-appointed") end

  --- Where the Appointed stands (the location nearest its card), or nil.
  function R.appointedLoc()
    local c = R.appointedCard()
    if not c or R.stage() < 1 then return nil end
    local p, best, bd = c.getPosition(), nil, nil
    for _, L in ipairs(R.G.locList) do
      local d = T.dist(p, L.pos)
      if d < 3.2 and (bd == nil or d < bd) then best, bd = L, d end
    end
    return best
  end

  function R.placeAppointed(L)
    local c = R.appointedCard()
    if c and L then
      local p = L.obj.getPosition()
      c.setPosition({ p.x, p.y + 0.6, p.z - 0.9 })
    end
  end

  --- After the Board moved the Appointed or an investigator moved: it
  -- engages its prey at its location (not while Sensed: aloof).
  function R.appointedEngageCheck()
    local G = R.G
    local A = G.appointed
    local stage = R.stage()
    if stage < 2 or A.engaged or A.exhausted then return end
    local L = R.appointedLoc()
    if not L then return end
    local here = R.investigatorsAt(L)
    if #here == 0 then return end
    local best, bm
    for _, inv in ipairs(here) do if bm == nil or (inv.memory or 0) > bm then best, bm = inv, inv.memory or 0 end end
    A.engaged = best
    A.loc = L.guid
    R.log("The Appointed engages %s", best.name)
    G.metrics.appointed_engagements = G.metrics.appointed_engagements + 1
    if stage == 2 then
      if not R.P.itMeansWait(best, "approach-horror") then R.hurt(best, 0, 1, "The Appointed (Emerging) engages") end
    end
  end

  ------------------------------------------------------------ loop end --

  function R.endLoop(reason, detail)
    local G = R.G
    if G.ended then return end
    G.ended = { reason = reason, detail = detail, round = G.round, hour = R.hour(), dissonance = R.dissonance() }
    R.log("THE LOOP ENDS: %s", reason)
    error({ loopEnded = true }, 0)
  end
end
