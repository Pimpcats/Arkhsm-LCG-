-- The party's policy in The Dunwich Legacy's opening pair (designer tooling).
-- The action scoring is The Still Hour's (ai.lua: fights, evasion, cards,
-- commits, attacks of opportunity); this module tells it what the objective is
-- in an official scenario (where to go, what the act needs) and adds the
-- scenarios' own actions (parleys, location abilities, resigning) through the
-- hooks ai.lua offers official modes (FX.extraOptions).

return function(R, T)
  local A = R.AI
  local P = R.P
  local FX = R.FX
  local ID = FX.ID

  local function G() return R.G end
  local function cur() return R.G.scen end

  ------------------------------------------------------------ routes for one investigator --

  -- locked doors depend on who moves ("Jazz" Mulligan's controller ignores them): the AI
  -- plans the route of the investigator whose turn it is
  local pathsBase = R.paths
  function R.paths(from, opts)
    opts = opts or {}
    if opts.enemy then return pathsBase(from, opts) end
    local inv = R.G.routeInv
    local dist, prev = { [from.guid] = 0 }, {}
    local q, h = { from }, 1
    while q[h] do
      local a = q[h] ; h = h + 1
      for g, b in pairs(a.adj) do
        if dist[g] == nil and R.canEnter(a, b, inv) then
          dist[g] = dist[a.guid] + 1
          prev[g] = a
          q[#q + 1] = b
        end
      end
    end
    return dist, prev
  end

  ------------------------------------------------------------ objectives --

  function A.objective() return R.G.acts.Main end
  function A.nextObjective() return nil end
  function A.cluesReserved() return A.goalNeed() end
  function A.wantsAdvance() return true end

  --- Clues the party must hold for its current goal (the act's, or a location objective's).
  function A.goalNeed()
    local G = R.G
    local act = G.acts.Main
    if not act then return 0 end
    local need = FX.actNeed(act.id)
    if need > 0 then return need end
    if cur() == "1a" and (act.id == ID.rice_act or act.id == ID.campus) then
      -- the location objective that ends the scenario: 2 [per_investigator] at the Faculty Offices, 3 at the Dormitories
      return (G.goal1a == "R1" and 2 or 3) * G.n
    end
    return 0
  end
  function A.goalLocation()
    local G = R.G
    local act = G.acts.Main
    if not act then return nil end
    if act.id == ID.skin then return R.locById(ID.vip) end
    if cur() == "1a" and (act.id == ID.rice_act or act.id == ID.campus) then
      return R.locById(G.goal1a == "R1" and ID.faculty or ID.dorms)
    end
    return nil
  end
  function A.need(act, inv)
    return math.max(0, A.goalNeed() - R.partyClues())
  end
  function A.actLocation(act, inv) return A.goalLocation() end

  --- Nearest enemies hunt; Prey breaks ties among the nearest (RR).
  function A.huntTarget(en)
    local G = R.G
    local here = G.locs[en.loc]
    if not here then return nil end
    local dist = R.paths(here, { enemy = true })
    local bd, cands = nil, {}
    for _, inv in ipairs(R.aliveInvs()) do
      local d = dist[inv.loc]
      if d then
        if bd == nil or d < bd then bd, cands = d, { inv } elseif d == bd then cands[#cands + 1] = inv end
      end
    end
    local prey = R.prey(en, cands)
    return prey and G.locs[prey.loc]
  end

  ------------------------------------------------------------ targets --

  local function travel(a, b) return A.travelCost(a, b) end

  local function clueSpots(inv)
    local G = R.G
    local here = R.locOf(inv)
    local out = {}
    for _, L in ipairs(G.locList) do
      local c = L.revealed and R.clues(L) or (L.def.clues or 0) * ((L.def.clues_per_investigator and G.n) or 1)
      if c > 0 and (not FX.canInvestigate or FX.canInvestigate(inv, L) or not L.revealed) then
        local cost = travel(here, L)
        if cost < 99 then
          local p = A.invP(inv, "int", R.shroud(L), "investigate")
          local s = cost + (1 - p) * 2.5 + 0.7 * A.danger(L, inv) + (FX.investigateExtra(inv, L) or 0)
          local others = 0
          for _, x in ipairs(R.aliveInvs()) do if x ~= inv and x.loc == L.guid then others = others + 1 end end
          if others >= c then s = s + 3 end
          out[#out + 1] = { L = L, s = s }
        end
      end
    end
    table.sort(out, function(a, b) return a.s < b.s end)
    return out
  end
  A.clueSpots = clueSpots

  local function nearestTo(L)
    local best, bd
    for _, x in ipairs(R.aliveInvs()) do
      R.G.routeInv = x
      local d = travel(R.locOf(x), L)
      if bd == nil or d < bd then best, bd = x, d end
    end
    return best
  end

  --- 1b: where an investigator can get clues during act 1 without locations to investigate.
  local function cloverClueAction(inv)
    local G = R.G
    if R.G.acts.Main.id ~= ID.luck then return nil end
    local opts = {}
    local bar, lounge, room = R.locById(ID.bar), R.locById(ID.lounge), R.locById(ID.cardroom)
    if bar and not inv.hadDrink and inv.resources >= 2 then opts[#opts + 1] = bar end
    local ally = false
    for _, c in ipairs(inv.hand) do if c.slot == "Ally" then ally = true end end
    if lounge and ally and not inv.usedLounge then opts[#opts + 1] = lounge end
    if room and inv.resources >= 2 then opts[#opts + 1] = room end
    local here = R.locOf(inv)
    local best, bs
    for _, L in ipairs(opts) do
      local s = travel(here, L) + (L == room and 1.5 or 0)
      for _, en in ipairs(G.enemies) do if en.id == ID.pitboss and en.loc == L.guid then s = s + 2 end end
      if bs == nil or s < bs then best, bs = L, s end
    end
    return best
  end

  local function resignSpot(inv)
    local here = R.locOf(inv)
    local best, bd
    for _, id in ipairs({ ID.bella, ID.alley }) do
      local L = R.locById(id)
      if L then
        local d = travel(here, L)
        if bd == nil or d < bd then best, bd = L, d end
      end
    end
    return best, bd
  end
  --- 1b: time to leave (act 3 done, or the last agenda about to advance).
  function A.shouldResign(inv)
    local G = R.G
    if cur() ~= "1b" then return false end
    local act = G.acts.Main
    local npc = G.npc
    local actThree = act and (act.id == ID.allin or act.id == ID.fold)
    if actThree and npc and (npc.holder or npc.gone) then return true end
    if R.agendaIndex() == 3 then
      local left = R.threshold() - R.doomInPlay()
      local _, d = resignSpot(inv)
      if left <= 1 + math.floor((d or 0) / 3) then return true end
    end
    if actThree and A.frail(inv) and not (npc and npc.holder == inv) then return true end
    return false
  end

  function A.targetFor(inv)
    local G = R.G
    G.routeInv = inv
    local here = R.locOf(inv)
    local act = G.acts.Main
    if not act then return A.maintenanceTarget(inv) end
    -- 1b: resign
    if A.shouldResign(inv) then
      local L = resignSpot(inv)
      if L then return L, "go" end
    end
    -- 1b act 3: free Dr. Morgan / Peter Clover
    if cur() == "1b" and G.npc and not G.npc.holder and not G.npc.gone and G.npc.loc then
      local L = G.locs[G.npc.loc]
      if L then return L, "go" end
    end
    -- 1a act 2: "Jazz" Mulligan is waiting somewhere: the nearest investigator goes to him
    if cur() == "1a" and act.id == ID.rice_act and G.jazz and not G.jazz.holder then
      local L = G.locs[G.jazz.loc]
      if L and nearestTo(L) == inv then return L, "go" end
    end
    -- 1a: the Alchemical Concoction under the Alchemy Labs (an [action] investigate takes it)
    local need = A.need(act, inv)
    local goal = A.goalLocation()
    -- "Jazz" Mulligan's controller opens the locked door of the objective
    if goal and not goal.revealed and FX.controlsJazz(inv) then return goal, "go" end
    if need > 0 then
      local spots = clueSpots(inv)
      local alt = cur() == "1b" and cloverClueAction(inv)
      if alt and (not spots[1] or spots[1].s > travel(here, alt) + 2.5) then return alt, "clues" end
      if spots[1] then return spots[1].L, "clues" end
      if alt then return alt, "clues" end
      -- nothing to investigate: explore (an unrevealed location may put more into play)
      local best, bd
      for _, L in ipairs(G.locList) do
        if not L.revealed then
          local d = travel(here, L)
          if d < 99 and (bd == nil or d < bd) then best, bd = L, d end
        end
      end
      if best then return best, "clues" end
    end
    if goal then
      if goal.revealed or FX.controlsJazz(inv) then return goal, "go" end
      -- the Back Hall Doorways look alike until revealed: explore the nearest unrevealed one
      if goal.id == ID.vip then
        local best, bd
        for _, L in ipairs(G.locList) do
          if not L.revealed and (L.id == ID.vip or L.id == ID.gallery or L.id == ID.alley) then
            local d = travel(here, L)
            if bd == nil or d < bd then best, bd = L, d end
          end
        end
        if best then return best, "go" end
      end
      -- the door is still locked: wait at the nearest place next to it
      for _, L in pairs(goal.adj) do return L, "go" end
    end
    -- nothing pressing: Searching for Izzie, Victory locations
    if G.izzie and G.izzie.owner == inv and G.locs[G.izzie.loc] then return G.locs[G.izzie.loc], "go" end
    local spots = clueSpots(inv)
    if spots[1] then return spots[1].L, "clues (next)" end
    return A.maintenanceTarget(inv)
  end

  ------------------------------------------------------------ the scenarios' actions --

  local function p(inv, skill, diff, kind) return (A.invP(inv, skill, diff, kind)) end

  function FX.mayCheat(inv, opts)
    local G = R.G
    if (R.WHATIF or {}).cheat ~= "important" then return false end
    if cur() ~= "1b" or not G.acts.Main or G.acts.Main.id ~= ID.luck or G.cheatRound == G.round then return false end
    return opts and (opts.important or opts.kind == "treachery")
  end

  function FX.extraOptions(inv, L, act, eng)
    local G = R.G
    local out = {}
    local function add(score, kind, run, extra) out[#out + 1] = { score = score, kind = kind, run = run, extra = extra } end
    local need = A.need(act, inv)
    -- Extracurricular Activity ------------------------------------------------
    if cur() == "1a" then
      -- parley "Jazz" Mulligan here: Test [intellect] (3); take control of him
      if G.jazz and not G.jazz.holder and G.jazz.loc == L.guid then
        local pj = p(inv, "int", 3, "parley")
        add(12 + 55 * pj, "parley", function()
          if R.test(inv, "int", 3, { kind = "parley", important = true }) then
            G.jazz.holder = inv
            P.putIntoPlay(inv, { name = "\"Jazz\" Mulligan", id = ID.jazz, slot = "Ally", story = true })
            if T.alive(G.jazz.obj) then G.jazz.obj.setPosition(FX.asidePos(44)) end
            G.metrics.jazz_controlled = G.round
            local a = G.acts.Main
            if a and a.id == ID.rice_act then R.advanceAct(a, inv) end
          end
        end)
      end
      -- Rice's Whereabouts: [action] Spend 1 clue: discard the top 5 cards of the encounter deck
      if act and act.id == ID.rice_act and not G.jazz and inv.clues >= 1 then
        add(26, "ability", function()
          R.spendClues({ inv }, 1)
          G.metrics.rice_searches = (G.metrics.rice_searches or 0) + 1
          for _ = 1, (G.n == 1 and 10 or 5) do
            local card = T.drawEncounter(inv.color)
            if not card then break end
            local id = T.gm(card).id
            if id == ID.jazz then FX.ENC[ID.jazz](inv, card) else T.discardEncounter(card) end
          end
          R.log("%s searches the encounter deck for \"Jazz\" (%s)", inv.name, G.jazz and "found" or "not found")
        end)
      end
      -- Student Union: [action][action]: heal 1 damage and 1 horror
      if L.id == ID.union and L.revealed and inv.damage + inv.horror >= 2 and (inv.actionsLeft or 0) >= 2 then
        add(A.frail(inv) and 30 or 9, "ability", function() R.heal(inv, 1, 1) end, { actions = 2 })
      end
      -- Alchemy Labs: investigate; on a success take the Alchemical Concoction instead of clues
      if L.id == ID.labs and L.revealed and G.concoctionUnderLabs and not G.concoctionTaken then
        local pi = p(inv, "int", R.shroud(L), "investigate")
        add(18 + 10 * pi, "investigate", function()
          if R.test(inv, "int", R.shroud(L), { kind = "investigate", important = true }) then
            G.concoctionTaken = true
            P.putIntoPlay(inv, { name = "Alchemical Concoction", id = ID.concoction, story = true })
          end
        end)
      end
      -- Alchemical Concoction: Fight using [intellect]; +6 damage against The Experiment; removed on a success
      local conc = P.findAssetId(inv, ID.concoction)
      local ex = FX.enemyById(ID.experiment)
      if conc and ex and ex.loc == L.guid then
        local pf = p(inv, "int", R.enemyFight(ex), "fight")
        add(35 + 30 * pf, "fight", function()
          local ok = R.test(inv, "int", R.enemyFight(ex), { kind = "fight", enemy = ex, important = true })
          if ok then
            for i, a in ipairs(inv.assets) do if a == conc then table.remove(inv.assets, i) break end end
            R.damageEnemy(ex, 7, inv, "Alchemical Concoction")
          end
        end, { provokes = false })
      end
      -- Whippoorwill (aloof): attack it where it is
      for _, en in ipairs(G.enemies) do
        if en.id == "02090" and en.loc == L.guid and not en.dead and not en.engaged then
          local pf = p(inv, "com", R.enemyFight(en), "fight")
          -- it takes 1 from every skill here: worth clearing before the tests that matter
          if pf >= 0.3 then add(18 + 22 * pf, "fight", function() R.ACT.fight(inv, en, nil) end) end
          break
        end
      end
    end
    -- The House Always Wins ---------------------------------------------------
    if cur() == "1b" then
      local actId = act and act.id
      local pitHere = false
      for _, en in ipairs(G.enemies) do if en.id == ID.pitboss and en.loc == L.guid and not en.dead then pitHere = true end end
      -- the Pit Boss engages and attacks whoever gains clues at its location: only a sturdy investigator risks it
      local pitCost = pitHere and ((inv.health - inv.damage >= 6) and 10 or 30) or 0
      if actId == ID.luck and need > 0 then
        if L.id == ID.bar and not inv.hadDrink and inv.resources >= 2 then
          add(30 - pitCost, "ability", function()
            inv.resources = inv.resources - 2
            inv.hadDrink = true
            FX.gainClues(inv, 2, "Clover Club Bar")
            if not inv.defeated then P.draw(inv, 2, "Clover Club Bar") end
          end)
        end
        if L.id == ID.lounge and not inv.usedLounge then
          for _, c in ipairs(inv.hand) do
            if c.slot == "Ally" then
              add(28 - pitCost, "ability", function()
                P.discardFromHand(inv, c)
                inv.usedLounge = true
                FX.gainClues(inv, 2, "Clover Club Lounge")
              end)
              break
            end
          end
        end
        if L.id == ID.cardroom and inv.resources >= 2 then
          add(17 - pitCost, "ability", function()
            inv.resources = inv.resources - 2
            local name = FX.revealRandom(inv)
            -- Beginner's Luck: the "cheat" would make it an [elder_sign] (policy switch)
            if (R.WHATIF or {}).cheat == "cardroom" and G.cheatRound ~= G.round and name ~= "Elder Sign" then
              G.cheated, G.cheatRound = true, G.round
              G.metrics.cheats = (G.metrics.cheats or 0) + 1
              name = "Elder Sign"
            end
            local v = tonumber(name)
            G.metrics.cardroom = G.metrics.cardroom or { tries = 0, wins = 0 }
            G.metrics.cardroom.tries = G.metrics.cardroom.tries + 1
            if name == "Elder Sign" then
              inv.resources = inv.resources + 2
              FX.gainClues(inv, 2, "Clover Club Cardroom")
              G.metrics.cardroom.wins = G.metrics.cardroom.wins + 1
            elseif v and v % 2 == 0 then
              FX.gainClues(inv, 2, "Clover Club Cardroom")
              G.metrics.cardroom.wins = G.metrics.cardroom.wins + 1
            end
          end)
        end
      end
      -- parley Dr. Morgan / Peter Clover: Test [willpower] (3): 1 clue on him; 1 [per_investigator]: take control
      local npc = G.npc
      if npc and not npc.holder and not npc.gone and npc.loc == L.guid then
        local pw = p(inv, "wil", 3, "parley")
        add(12 + 50 * pw, "parley", function()
          if R.test(inv, "wil", 3, { kind = "parley", important = true }) then
            npc.clues = npc.clues + 1
            if npc.clues >= G.n then
              npc.holder = inv
              local rec = (npc.id == ID.morgan) and { name = "Dr. Francis Morgan", id = ID.morgan, slot = "Ally", story = true }
                or { name = "Peter Clover", id = ID.peter, story = true }
              P.putIntoPlay(inv, rec)
              if T.alive(npc.obj) then npc.obj.setPosition(FX.asidePos(45)) end
              G.metrics.npc_controlled = G.round
            end
          end
        end)
      end
      -- Peter Clover: [fast] exhaust: automatically evade a [[Criminal]] enemy at your location
      local peter = P.findAssetId(inv, ID.peter)
      if peter and not peter.exhausted then
        for _, en in ipairs(eng or {}) do
          if R.hasTrait(en.def, "Criminal") then
            add(45, "evade", function()
              peter.exhausted = true
              en.exhausted, en.engaged = true, nil
              R.placeEnemy(en)
              G.metrics.evades = G.metrics.evades + 1
            end, { actions = 0, provokes = false })
            break
          end
        end
      end
      -- resign (La Bella Luna, the Back Alley)
      if (L.id == ID.bella or (L.id == ID.alley and L.revealed)) and A.shouldResign(inv) then
        add(90, "resign", function() R.resign(inv) end, { provokes = true })
      end
    end
    -- both -------------------------------------------------------------------
    -- Locked Door: Test [combat] (4) or [agility] (4) to discard it
    for _, a in ipairs(FX.attachedAt(L.guid, "01174")) do
      if (FX.cluesRaw or R.clues)(L) > 0 and need > 0 then
        local sk = (R.skillBase(inv, "com") >= R.skillBase(inv, "agi")) and "com" or "agi"
        local pl = p(inv, sk, 4, "ability")
        add(14 + 12 * pl, "ability", function()
          if R.test(inv, sk, 4, { kind = "treachery" }) then FX.detach(a) end
        end)
      end
      break
    end
    -- Searching for Izzie: [action][action] investigate; on a success discard it
    if G.izzie and G.izzie.owner == inv and G.izzie.loc == L.guid and (inv.actionsLeft or 0) >= 2 then
      local pi = p(inv, "int", R.shroud(L), "investigate")
      add(need > 0 and 6 or 16, "ability", function()
        if R.test(inv, "int", R.shroud(L), { kind = "investigate" }) then
          inv.discard[#inv.discard + 1] = G.izzie.card
          G.izzie = nil
        end
      end, { actions = 2 })
    end
    -- Search for the Truth: draw X cards, X = clues on Rex (max 5)
    for _, c in ipairs(inv.hand) do
      if c.name == "Search for the Truth" and P.playCost(inv, c) <= inv.resources and inv.clues >= 2 and #inv.hand <= 5 then
        add(6 + 2 * math.min(5, inv.clues), "play", function()
          P.discardFromHand(inv, c)
          inv.resources = inv.resources - P.playCost(inv, c)
          G.metrics.cards_played = G.metrics.cards_played + 1
          P.draw(inv, math.min(5, inv.clues))
        end)
        break
      end
    end
    return out
  end

  --- Beyond the Veil makes an empty deck deadly: drawing (and milling locations) is weighed by the cards left.
  local function veiled(inv) return inv and inv.threat and inv.threat["Beyond the Veil"] ~= nil end
  function FX.drawPenalty(inv)
    if not veiled(inv) then return 0 end
    return (#inv.deck <= 8) and 50 or 3
  end
  local dangerBase = A.danger
  function A.danger(L, inv)
    local d = dangerBase(L, inv)
    if L and inv and veiled(inv) then
      if L.id == ID.admin then d = d + 2 end
      if L.id == ID.humanities and inv.horror > 0 then d = d + 1 + inv.horror end
    end
    return d
  end

  ------------------------------------------------------------ the turn --

  local chooseBase = A.choose
  local cluesRaw = R.clues
  FX.cluesRaw = cluesRaw

  --- What attacks of opportunity would cost an option that provokes them (ai.lua's own weighing).
  local function aooCost(inv)
    local aoo, d, h = 0, 0, 0
    for _, en in ipairs(R.G.enemies) do
      if not en.dead and not en.exhausted and (en.engaged == inv or R.massiveWith(en, inv)) then
        aoo = aoo + 6 * ((en.def.damage or 0) + (en.def.horror or 0))
        d, h = d + (en.def.damage or 0), h + (en.def.horror or 0)
      end
    end
    return aoo, d, h
  end

  --- The Still Hour's action scoring (ai.lua A.choose) with this scenario's knowledge around it:
  -- the scenario's own actions compete with its best option, Locked Door / Orne Library change what
  -- investigating costs, a Criminal is not hit while the Clover Club is the agenda unless it must be,
  -- and an investigator with Beyond the Veil does not draw from a thin deck.
  function A.choose(inv)
    local G = R.G
    G.routeInv = inv
    local L = R.locOf(inv)
    -- Dissonant Voices: you cannot play assets or events
    local saved
    if inv.threat["Dissonant Voices"] then
      saved = inv.hand
      local h = {}
      for _, c in ipairs(saved) do if c.type ~= "Asset" and c.type ~= "Event" then h[#h + 1] = c end end
      inv.hand = h
    end
    -- Locked Door: the location cannot be investigated; Orne Library: 2 actions to investigate
    R.clues = function(X)
      if X == L then
        if FX.canInvestigate and not FX.canInvestigate(inv, X) then return 0 end
        if (FX.investigateExtra(inv, X) or 0) > 0 and (inv.actionsLeft or 0) < 2 then return 0 end
      end
      return cluesRaw(X)
    end
    local ok, choice = pcall(chooseBase, inv)
    R.clues = cluesRaw
    if saved then
      for _, c in ipairs(inv.hand) do
        local seen = false
        for _, s2 in ipairs(saved) do if s2 == c then seen = true end end
        if not seen then saved[#saved + 1] = c end
      end
      inv.hand = saved
    end
    if not ok then error(choice, 0) end
    if not L then return choice end
    if choice and choice.kind == "investigate" and (FX.investigateExtra(inv, L) or 0) > 0 then
      choice.actions = (choice.actions or 1) + FX.investigateExtra(inv, L)
    end
    -- the scenario's own actions
    local act = A.objective()
    local eng = {}
    for _, en in ipairs(G.enemies) do if not en.dead and (en.engaged == inv or R.massiveWith(en, inv)) then eng[#eng + 1] = en end end
    local aoo, d, h = aooCost(inv)
    for _, o in ipairs(FX.extraOptions(inv, L, act, eng) or {}) do
      local x = o.extra or {}
      local opt = { score = o.score, kind = o.kind, run = o.run, actions = x.actions or 1, provokes = x.provokes }
      if opt.provokes ~= false and opt.actions > 0 then
        opt.score = opt.score - aoo
        if (d > 0 or h > 0) and (inv.damage + d >= inv.health or inv.horror + h >= inv.sanity) then opt.score = opt.score - 200 end
      end
      if opt.actions <= (inv.actionsLeft or 3) and (not choice or opt.score > (choice.score or -1e9)) and opt.score > -40 then
        choice = opt
      end
    end
    -- a Criminal under the Clover Club: evade it rather than hit it, unless it must be hit
    if choice and choice.kind == "fight" and #eng > 0 then
      local worst, pen
      for _, en in ipairs(eng) do
        local p = FX.fightPenalty(inv, en)
        if p > 0 and (pen == nil or p > pen) then worst, pen = en, p end
      end
      if worst then
        local pe = R.prob(inv, R.skillBase(inv, "agi", { enemy = worst }) + P.staticBonus(inv, "agi", { kind = "evade" })
          - R.enemyEvade(worst) + 1)
        local evadeScore = (26 + (worst.def.damage or 0) + (worst.def.horror or 0)) * pe
        if (choice.score or 0) - pen < evadeScore then
          choice = { score = evadeScore, kind = "evade", actions = 1, provokes = false,
                     run = function() R.ACT.evade(inv, worst) end }
        end
      end
    end
    -- Beyond the Veil: no extra draws from a thin deck
    if choice and choice.kind == "draw" and (FX.drawPenalty(inv) or 0) > 3 then
      choice = { score = 1, kind = "resource", actions = 1, run = function() inv.resources = inv.resources + 1 end }
    end
    -- Frozen in Fear: the first move, fight or evade each round costs 1 additional action
    if choice and inv.threat["Frozen in Fear"] and not inv.round.frozen
       and (choice.kind == "move" or choice.kind == "fight" or choice.kind == "evade") and (choice.actions or 1) > 0 then
      if (inv.actionsLeft or 0) < (choice.actions or 1) + 1 then return nil end
      inv.round.frozen = true
      choice.actions = (choice.actions or 1) + 1
    end
    return choice
  end

  local startBase = A.startTurn
  function A.startTurn(inv)
    startBase(inv)
    -- Something in the Drinks: lose 1 action
    if (inv.loseAction or 0) > 0 then
      inv.actionsLeft = math.max(0, inv.actionsLeft - inv.loseAction)
      inv.loseAction = 0
    end
  end
end
