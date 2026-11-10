-- The Miskatonic Museum on the play engine (designer tooling): the rules
-- hooks and the party's policy tmm_effects.lua's cards need beyond the FX
-- table. Loaded last by dwl_engine.lua (after dwl_rules.lua, dwl_players.lua
-- and dwl_ai.lua); every function it replaces falls through to the version
-- it found when the scenario is not the Museum, so 1a/1b play as before.
--
--   * rules: Shadow-spawned's evade and Massive, the void instead of the
--     discard pile, Harold Walsted's [intellect], the Athabaskan Exhibit's
--     [agility], what a failed investigation costs in an Exhibit Hall;
--   * the AI: gather clues, pay for Exhibit Halls at the Museum Halls, walk
--     into each new one (the Restricted Hall advances the act), fight Hunting
--     Horror off the Restricted Hall, empty it; resign at the Entrance when
--     the last agenda is about to advance.

return function(R, T)
  local A, P, FX = R.AI, R.P, R.FX
  local M = FX.M
  local function is2() return R.G.scen == "2" end
  local function cluesRaw(L) return (FX.cluesRaw or R.clues)(L) end
  local function hh() return FX.huntingHorror() end

  P.SOAK["Harold Walsted"] = { 1, 1 }
  P.SOAK["Adam Lynch"] = { 1, 1 }
  P.DWL_APPROX["Dr. Henry Armitage"] = "in the Museum after 1a/1b (trio runs) he is an ally that soaks 2 damage and 2 horror; "
    .. "his [reaction] (discard a drawn card for resources) is not used"
  -- Ward of Protection: what each Museum treachery is worth cancelling
  for id, w in pairs({ [M.stalked] = 2, [M.passage] = 1, [M.ephemeral] = 1, [M.slithering] = 3, [M.chill] = 2, [M.fog] = 1 }) do
    P.WARD_WORTH[id] = w
  end

  ------------------------------------------------------------ rules --

  local evadeBase = R.enemyEvade
  function R.enemyEvade(en) return evadeBase(en) + FX.shadowBonus(en) end
  local massiveBase = R.isMassive
  function R.isMassive(en)
    if FX.shadowBonus(en) >= 3 then return true end
    return massiveBase(en)
  end

  --- Hunting Horror leaves play: to the void, not the discard pile.
  local defeatEnemyBase = R.defeatEnemy
  function R.defeatEnemy(en, inv)
    if en.id ~= M.horror then return defeatEnemyBase(en, inv) end
    local G = R.G
    en.dead = true
    for i, x in ipairs(G.enemies) do if x == en then table.remove(G.enemies, i) break end end
    G.metrics.enemies_defeated = G.metrics.enemies_defeated + 1
    G.metrics.defeated_by_id[en.id] = (G.metrics.defeated_by_id[en.id] or 0) + 1
    R.log("%s is defeated", en.name)
    FX.toVoid(en)
    if inv then P.afterDefeatEnemy(inv, en) end
  end

  local skillBase = R.skillBase
  function R.skillBase(inv, skill, opts)
    local v = skillBase(inv, skill, opts)
    if skill == "agi" and R.G.scen == "2" then
      local L = R.G.locs[inv.loc]
      if L and L.revealed and L.id == M.athabaskan then v = v + 2 end
    end
    return v
  end
  local staticBase = P.staticBonus
  function P.staticBonus(inv, skill, opts)
    local b = staticBase(inv, skill, opts)
    -- Harold Walsted: +2 [intellect] while investigating [[Miskatonic]] locations (every Museum location)
    if skill == "int" and opts and opts.kind == "investigate" and R.G.scen == "2" and P.findAssetId(inv, M.harold) then b = b + 2 end
    return b
  end

  local afterTestBase = P.afterTest
  function P.afterTest(inv, ok, margin, skill, opts, committed)
    afterTestBase(inv, ok, margin, skill, opts, committed)
    if ok or not is2() or inv.defeated or R.G.ended or not (opts and opts.kind == "investigate") then return end
    local L = R.locOf(inv)
    if L then FX.investigateFailed(inv, L) end
  end

  ------------------------------------------------------------ objectives --

  local function restricted() return R.locById(M.restricted) end
  local function actTwo(act) return act and (act.id == M.night or act.id == M.breaking) end
  local function unrevealedExhibit()
    for _, L in ipairs(R.G.locList) do
      if not L.revealed and R.hasTrait(L.def, "Exhibit") then return L end
    end
  end

  local goalNeedBase = A.goalNeed
  function A.goalNeed()
    if not is2() then return goalNeedBase() end
    local G = R.G
    local act = G.acts.Main
    if not act then return 0 end
    if act.id == M.inside then return FX.actNeed(act.id) end
    -- Museum Halls: 1 [per_investigator] clues for the next Exhibit Hall, until the Restricted Hall is in play
    if actTwo(act) and #G.exhibit > 0 then return G.n end
    return 0
  end
  local needBase = A.need
  function A.need(act, inv)
    if not is2() then return needBase(act, inv) end
    if act and act.id == M.tome then
      local L = restricted()
      return (L and L.revealed) and cluesRaw(L) or 0
    end
    return math.max(0, A.goalNeed() - R.partyClues())
  end
  local goalLocationBase = A.goalLocation
  function A.goalLocation()
    if not is2() then return goalLocationBase() end
    local act = R.G.acts.Main
    if act and act.id == M.tome then return restricted() end
    return nil
  end

  local function upvalue(fn, name)
    for i = 1, 250 do
      local k, v = debug.getupvalue(fn, i)
      if not k then break end
      if k == name then return v end
    end
    return nil
  end
  local chooseDwl = A.choose
  local chooseStill = upvalue(chooseDwl, "chooseBase")
  local bestWeapon = chooseStill and upvalue(chooseStill, "bestWeapon")
  local function fightOdds(inv, en)
    local weapon = bestWeapon and bestWeapon(inv)
    local w = weapon and P.WEAPON[weapon.name]
    local skill = (w and w[4]) or "com"
    local pf = R.prob(inv, R.skillBase(inv, skill, { enemy = en }) + P.staticBonus(inv, skill, { kind = "fight", weapon = weapon })
      - R.enemyFight(en) + 1)
    local per = 1 + ((w and w[2]) or 0)
    return pf, weapon, math.ceil(math.max(1, R.enemyHealth(en) - en.damage) / per)
  end

  --- What-if "hunt" (not the benchmark's AI): whoever is likely to hit Hunting Horror fights it wherever it is,
  -- and a better fighter walks over to take it off a worse one. The benchmark keeps The Still Hour's own
  -- fight/evade scoring, except on the Restricted Hall in act 3, where the Horror must go.
  local function hunts() return (R.WHATIF or {}).aiVariant == "hunt" end

  local function travel(a, b) return A.travelCost(a, b) end
  local function nearestTo(L)
    local best, bd
    local keep = R.G.routeInv
    for _, x in ipairs(R.aliveInvs()) do
      R.G.routeInv = x
      local d = travel(R.locOf(x), L)
      if bd == nil or d < bd then best, bd = x, d end
    end
    R.G.routeInv = keep
    return best
  end

  --- Time to leave: the last agenda is about to advance (Driven Out defeats whoever has not resigned).
  function A.shouldResignMuseum(inv)
    local G = R.G
    if R.agendaIndex() ~= 3 then return false end
    local here = R.locOf(inv)
    local door = R.locById(M.entrance)
    if not here or not door then return false end
    local left = R.threshold() - R.doomInPlay()
    local d = travel(here, door)
    if left > 1 + math.floor(d / 3) then return false end
    -- one or two clues from the end, standing in an open Restricted Hall: stay and take them
    local act = G.acts.Main
    if act and act.id == M.tome and here.id == M.restricted and FX.canInvestigate(inv, here) and cluesRaw(here) <= 2 then
      return false
    end
    return true
  end

  --- Locked Door: the better of [combat] and [agility] against 4.
  function A.doorOdds(inv)
    local sk = (R.skillBase(inv, "com") >= R.skillBase(inv, "agi")) and "com" or "agi"
    local _, p = A.invP(inv, sk, 4, "ability")      -- the odds on the skill value alone, no cards committed
    return sk, p
  end

  local targetBase = A.targetFor
  function A.targetFor(inv)
    local G = R.G
    if not is2() then return targetBase(inv) end
    G.routeInv = inv
    local here = R.locOf(inv)
    local act = G.acts.Main
    if not act or not here then return A.maintenanceTarget(inv) end
    if A.shouldResignMuseum(inv) then return R.locById(M.entrance), "go" end
    -- Hunting Horror on an investigator who fights worse, a step or two away: go and take it
    local en = hh()
    if en and en.engaged and en.engaged ~= inv and hunts() and G.locs[en.loc] and en.loc ~= inv.loc then
      local pf = fightOdds(inv, en)
      if pf >= 0.6 and pf > fightOdds(en.engaged, en) + 0.1 and travel(here, G.locs[en.loc]) <= 2 then
        return G.locs[en.loc], "go"
      end
    end
    if act.id == M.tome then
      local L = restricted()
      if L then return L, "go" end
    end
    if actTwo(act) then
      -- a new Exhibit Hall: the nearest investigator walks in (the Restricted Hall advances the act)
      local ex = unrevealedExhibit()
      if ex and nearestTo(ex) == inv then return ex, "go" end
      -- enough clues for the next Exhibit Hall: whoever holds them brings them to the Museum Halls
      if not ex and #G.exhibit > 0 and R.partyClues() >= G.n and inv.clues > 0 then
        local halls = R.locById(M.halls)
        if halls then return halls, "go" end
      end
    end
    -- (an Exhibit Hall is not known until it is entered: unrevealed ones are not clue targets)
    for _, sp in ipairs(A.clueSpots(inv)) do
      if sp.L.revealed or not R.hasTrait(sp.L.def, "Exhibit") then return sp.L, "clues" end
    end
    -- nothing this investigator may investigate: an Administration Office waiting for resources / cards
    for _, L in ipairs(G.locList) do
      if (L.id == M.adminRes or L.id == M.adminHand) and L.revealed and cluesRaw(L) > 0 and travel(here, L) < 99 then
        return L, "go"
      end
    end
    -- clues behind a Locked Door: whoever has a real chance at it goes there
    for _, L in ipairs(G.locList) do
      if L.revealed and cluesRaw(L) > 0 and #FX.attachedAt(L.guid, "01174") > 0 and travel(here, L) < 99 then
        local _, pl = A.doorOdds(inv)
        if pl >= 0.25 then return L, "go" end
      end
    end
    if inv.clues > 0 and R.locById(M.halls) and R.locById(M.halls).revealed then return R.locById(M.halls), "go" end
    return here, "hold"
  end

  ------------------------------------------------------------ the scenario's actions --

  local extraBase = FX.extraOptions
  function FX.extraOptions(inv, L, act, eng)
    local out = extraBase(inv, L, act, eng) or {}
    if not is2() then return out end
    local G = R.G
    local function add(score, kind, run, extra) out[#out + 1] = { score = score, kind = kind, run = run, extra = extra } end
    -- Locked Door ([combat] or [agility] 4 to discard it): dwl_ai.lua's option tries at any odds; here it is
    -- left to an investigator with a real chance (the others look for clues elsewhere)
    local door = FX.attachedAt(L.guid, "01174")[1]
    if door then
      for i = #out, 1, -1 do
        if out[i].kind == "ability" and not out[i].extra then table.remove(out, i) end
      end
      local sk, pl = A.doorOdds(inv)
      if cluesRaw(L) > 0 and pl >= 0.25 then
        add(14 + 12 * pl, "ability", function()
          if R.test(inv, sk, 4, { kind = "treachery" }) then FX.detach(door) end
        end)
      end
    end
    local actId = act and act.id
    local halls = R.locById(M.halls)
    -- Museum Entrance: [action] Test [combat] (5) to break down the door; on a success advance to act 1b
    if L.id == M.entrance and actId == M.inside and halls and not halls.revealed then
      local pb = R.prob(inv, R.skillBase(inv, "com") + P.staticBonus(inv, "com", { kind = "ability" }) - 5 + 1)
      add(10 + 20 * pb, "ability", function()
        G.metrics.door_attempts = (G.metrics.door_attempts or 0) + 1
        if R.test(inv, "com", 5, { kind = "ability", important = true }) and not G.ended then
          G.brokeDoor = true
          G.metrics.broke_door = G.round
          R.advanceAct(G.acts.Main, inv)
        end
      end)
    end
    -- Museum Entrance: [action] Resign
    if L.id == M.entrance and A.shouldResignMuseum(inv) then
      add(90, "resign", function() R.resign(inv) end, { provokes = true })
    end
    -- Museum Halls: [action] investigators here spend 1 [per_investigator] clues, as a group: the next Exhibit Hall
    if L.id == M.halls and L.revealed and actTwo(act) and #G.exhibit > 0 and not unrevealedExhibit() then
      local here = R.investigatorsAt(L)
      local have = 0
      for _, x in ipairs(here) do have = have + x.clues end
      if have >= G.n then
        add(60, "objective", function()
          R.spendClues(here, G.n)
          FX.drawExhibit()
        end)
      end
    end
    -- Security Office: [action][action] ([action] with Adam Lynch): search the top 6 cards of your deck for a card
    if L.id == M.security6 and L.revealed and not inv.lastTurn.security and #inv.hand <= 4 and #inv.deck >= 6 then
      local cost = P.findAssetId(inv, M.adam) and 1 or 2
      if (inv.actionsLeft or 0) >= cost then
        add(8, "ability", function()
          inv.lastTurn.security = true
          G.metrics.security_searches = (G.metrics.security_searches or 0) + 1
          P.searchTop(inv, 6)
        end, { actions = cost })
      end
    end
    -- Administration Office: build up to what investigating it asks for (5 resources / 5 cards in hand)
    if L.revealed and cluesRaw(L) > 0 and A.need(act, inv) > 0 then
      if L.id == M.adminRes and inv.resources <= 4 then
        add(19, "resource", function() inv.resources = inv.resources + 1 end)
      elseif L.id == M.adminHand and #inv.hand <= 4 then
        add(19, "draw", function() P.draw(inv, 1) end)
      end
    end
    local en = hh()
    if en and en.loc == L.guid then
      local pf, weapon, hits = fightOdds(inv, en)
      local blocking = actId == M.tome and L.id == M.restricted
      if not en.engaged then
        -- Hunting Horror here, not engaged with anyone (evaded, exhausted: no Retaliate): on the Restricted
        -- Hall it must go before the hall can be investigated
        if (blocking and pf >= 0.25) or (hunts() and pf >= 0.5) then
          add(8 + 32 * pf / hits, "fight", function() R.ACT.fight(inv, en, weapon) end, { provokes = false })
        end
      elseif hunts() and en.engaged ~= inv and pf >= 0.6 and #eng == 0 then
        -- engaged with someone who fights worse: take it off them ([action] engage), then fight it
        local pfo = fightOdds(en.engaged, en)
        if pf > pfo + 0.1 then
          add(26 + 10 * pf, "engage", function()
            G.metrics.hh_taken_over = (G.metrics.hh_taken_over or 0) + 1
            R.ACT.engage(inv, en)
          end)
        end
      end
    end
    return out
  end

  ------------------------------------------------------------ the turn --

  function A.choose(inv)
    local G = R.G
    if not is2() then return chooseDwl(inv) end
    local L = R.locOf(inv)
    -- Harold Walsted / Adam Lynch hold the ally slot: no other ally is played over them
    local saved
    local s = G.allies and (G.allies[M.harold] or G.allies[M.adam])
    if s and not s.lost and s.holder == inv then
      saved = inv.hand
      local h = {}
      for _, c in ipairs(saved) do if c.slot ~= "Ally" then h[#h + 1] = c end end
      inv.hand = h
    end
    local ok, choice = pcall(chooseDwl, inv)
    if saved then
      for _, c in ipairs(inv.hand) do
        local seen = false
        for _, s2 in ipairs(saved) do if s2 == c then seen = true end end
        if not seen then saved[#saved + 1] = c end
      end
      inv.hand = saved
    end
    if not ok then error(choice, 0) end
    if not choice or not L then return choice end
    local act = G.acts.Main
    -- Hunting Horror on the Restricted Hall keeps the hall from being investigated: there, whoever is likely
    -- to hit it fights it rather than evade it (the what-if "hunt" does so everywhere)
    local en = hh()
    if choice.kind == "evade" and en and en.engaged == inv
       and (hunts() or (act and act.id == M.tome and L.id == M.restricted)) then
      local pf, weapon = fightOdds(inv, en)
      if pf >= 0.5 then
        G.metrics.hh_fight_not_evade = (G.metrics.hh_fight_not_evade or 0) + 1
        choice = { score = choice.score, kind = "fight", actions = choice.actions or 1, provokes = false,
                   run = function() R.ACT.fight(inv, en, weapon) end }
      end
    end
    -- the last agenda is about to advance: nothing but the way out (an engaged enemy is still dealt with first)
    if A.shouldResignMuseum(inv) and L.id ~= M.entrance and choice.kind ~= "move" then
      local engaged = false
      for _, x in ipairs(G.enemies) do if not x.dead and x.engaged == inv and not x.exhausted then engaged = true end end
      local step = R.route(L, R.locById(M.entrance))
      if step and R.canEnter(L, step, inv) and not (engaged and (choice.kind == "evade" or choice.kind == "fight")) then
        choice = { score = 90, kind = "move", actions = 1, run = function() R.ACT.move(inv, step) end }
      end
    end
    -- Museum Entrance: investigators there cannot gain resources
    if L.id == M.entrance then
      if choice.kind == "resource" then
        choice = { score = choice.score, kind = "draw", actions = choice.actions or 1, provokes = choice.provokes,
                   run = function() P.draw(inv, 1) end }
      else
        local run = choice.run
        choice.run = function()
          local before = inv.resources
          run()
          local here = R.locOf(inv)
          if here and here.id == M.entrance and inv.resources > before then inv.resources = before end
        end
      end
    end
    return choice
  end
end
