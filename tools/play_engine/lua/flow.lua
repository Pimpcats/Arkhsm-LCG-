-- The round structure (Rules Reference: mythos, investigation, enemy,
-- upkeep), skill tests with real chaos-token draws, and the player actions.

return function(R, T)
  local E = T.E
  local P = R.P
  local FX = R.FX

  ------------------------------------------------------------ chaos odds --

  --- The bag as it is on the table now (names), cached until something changes.
  function R.bag()
    local G = R.G
    if not G.bagCache or G.bagCache.t ~= G.clock then
      G.bagCache = { t = G.clock, v = T.bagNames() }
    end
    return G.bagCache.v
  end

  --- P(success) for this investigator at `margin` = skill total - difficulty.
  function R.prob(inv, margin)
    local bag = R.bag()
    if #bag == 0 then return 0 end
    local ok = 0
    for _, name in ipairs(bag) do
      local v = FX.tokenValue(name, inv)
      if v ~= nil and margin + v >= 0 then ok = ok + 1 end
    end
    return ok / #bag
  end

  ------------------------------------------------------------ skill tests --

  --- Perform a skill test. opts.kind: investigate | fight | evade | treachery |
  -- location | ability | holdback | act; opts.peril: no help from others;
  -- opts.important: worth resources and cards; opts.target: wanted P(success).
  -- Returns success, margin, token name.
  function R.test(inv, skill, diff, opts)
    opts = opts or {}
    local G = R.G
    -- RR ST.1 -> ST.2: a player window before cards are committed.
    R.playerWindow("skill test before commits")
    G.metrics.tests = G.metrics.tests + 1
    local base = R.skillBase(inv, skill) + P.staticBonus(inv, skill, opts) + (opts.bonus or 0)
    -- the AI commits cards and pays for boosts up to its target odds
    local committed, boost = R.AI.prepareTest(inv, skill, diff, base, opts)
    inv.lastCommitted = {}
    for _, c in ipairs(committed) do
      local name = c.card.name
      if name == "Deduction" or name == "Vicious Blow" then
        inv.lastCommitted[name] = inv.lastCommitted[name] or {}
        inv.lastCommitted[name][#inv.lastCommitted[name]+1] = c.card
      end
    end
    local total = base + boost
    for _, c in ipairs(committed) do total = total + c.icons end
    -- RR ST.2 -> ST.3: the second player window precedes token reveal.
    -- A test inside an encounter therefore can offer a paid objective even
    -- though Mythos has not yet reached its general post-draw player window.
    R.playerWindow("skill test after commits")
    local name, tokenName, ok, margin
    repeat
      local token, sealed, sealedReturned
      if inv.sealedToken then
        token, sealed = inv.sealedToken, true
        inv.sealedToken = nil
        name = token.getName()
      else name, token = T.drawToken(inv.color) end
      R.touch()
      -- A canceled or previewed Static must never apply irreversible band
      -- transitions. Resolve pending tokens only after all cancellation windows.
      if name == "Static" and inv.story and inv.story.id == "sthr-item-almanac" and not inv.storyExhausted then
        inv.storyExhausted = true
        T.api("shApiResolveStatic", { guid = token and token.getGUID(), cancel = true })
        if sealed then T.chaosBag().putObject(token) end
        name, token = T.drawToken(inv.color)
        sealed = false
        R.touch()
      end
      tokenName = name
      local mod = FX.tokenValue(name, inv)
      local cancelled = false
      if inv.namedToken and inv.namedToken == name then
        inv.namedToken, cancelled = nil, true
      end
      -- Cass: after you reveal a symbol token: 1 Memory (once per round, 3 per loop)
      if inv.id == "sthrcass" and name and tonumber(name) == nil then P.memoryReaction(inv, "Cass: revealed a symbol token") end
      if not cancelled and total >= diff and (mod == nil or total + mod < diff)
         and P.cancelToken(inv, name, mod and total + mod - diff or -1, total - diff, opts) then cancelled = true end
      tokenName = cancelled and "Canceled" or name
      if name == "Static" then
        if sealed then
          if not cancelled then
            -- R.raise can end the loop immediately: put the revealed seal
            -- back first so that early exit cannot strand a chaos token.
            T.chaosBag().putObject(token) ; E.run(0.1) ; sealedReturned = true
            R.raise(1, "[static] token")
          end
        else
          T.api("shApiResolveStatic", { guid = token and token.getGUID(), cancel = cancelled })
          R.touch()
          if not cancelled then
            local m = G.metrics
            m.dissonance_sources["[static] token"] = (m.dissonance_sources["[static] token"] or 0) + 1
            m.diss_max = math.max(m.diss_max, R.dissonance())
          end
        end
        if not cancelled and R.dissonance() >= R.consts().reset then
          T.returnTokens()
          if sealed and not sealedReturned then T.chaosBag().putObject(token) ; E.run(0.1) end
          R.touch()
          R.checkReset()
          if G.ended then return false, -math.max(diff,1), name end
        end
      end
      if cancelled then mod = 0 end
      margin = mod and total + mod - diff or -math.max(diff, 1)
      ok = margin >= 0 and mod ~= nil
      if not ok then
        local saved = P.wouldFail(inv, margin, name, opts)
        if saved and saved >= 0 then ok, margin = true, saved end
      end
      G.metrics.tokens[name] = (G.metrics.tokens[name] or 0) + 1
      R.log("%s tests %s (%d) vs %d: token %s -> %s (margin %d)", inv.name, skill, total, diff,
        tostring(name), ok and "success" or "FAIL", margin)
      T.returnTokens()
      if sealed and not sealedReturned then T.chaosBag().putObject(token) ; E.run(0.1) end
      R.touch()
      if not cancelled then
        if name == "Elder Sign" then P.elderSignAfter(inv, mod) end
        FX.tokenAfter(name, inv, ok, opts, margin)
      end
      -- Repeat only the reveal step: no new commits or boosts; previously
      -- resolved token effects remain. Committed cards resolve once at the end.
      if not ok and P.retryTest(inv, opts) then total = total + 2 else break end
    until G.ended or inv.defeated
    R.syncAppointedArrival()
    R.checkReset()
    P.afterTest(inv, ok, margin, skill, opts, committed)
    if ok then G.metrics.tests_passed = G.metrics.tests_passed + 1 end
    return ok, margin, tokenName
  end

  ------------------------------------------------------------ clues --

  function R.partyClues()
    local n = 0
    for _, inv in ipairs(R.aliveInvs()) do n = n + inv.clues end
    return n
  end
  function R.cluesNeededTotal() return R.AI and R.AI.cluesReserved and R.AI.cluesReserved() or 0 end

  function R.discover(inv, L, n)
    local G = R.G
    for _ = 1, n do
      if G.inkRuns[L.guid] == G.round then
        G.inkRuns[L.guid] = nil
        R.log("Ink Runs Backward cancels a clue at %s", L.name)
      else
        local toks = T.cluesOn(L.obj)
        if #toks == 0 then break end
        local tok = toks[1]
        T.moveClueToMat(tok, inv.color, #inv.clueTokens)
        inv.clueTokens[#inv.clueTokens + 1] = tok
        inv.clues = inv.clues + 1
        G.metrics.clues = G.metrics.clues + 1
        G.metrics.clues_by_round[G.round] = (G.metrics.clues_by_round[G.round] or 0) + 1
        inv.lastTurn.clueAt = L.guid
        R.log("%s discovers a clue at %s (%d held, %d left there)", inv.name, L.name, inv.clues, #toks - 1)
        -- Walk It Backward: the Turning, the Low Bridge, the Milestones, in that order
        local seq = { "sthr-loc-turning", "sthr-loc-lowbridge", "sthr-loc-milestones" }
        local step = (inv.walk or 0) + 1
        -- clues per step (Walk It Backward); what-if walkSteps {a, b, c} or walkPer n
        local steps = (R.WHATIF or {}).walkSteps
        local per = (steps and steps[step]) or (R.WHATIF or {}).walkPer or (G.n == 1 and { 2, 1, 1 } or { 3, 1, 1 })[step]   -- the card's one-investigator clause
        if seq[step] == L.id then inv.walkCount = (inv.walkCount or 0) + 1 end
        if seq[step] == L.id and inv.walkCount >= per then
          inv.walk = step
          inv.walkCount = 0
          R.log("%s: Walk It Backward step %d (%s)", inv.name, step, L.name)
          local act = G.acts.Road
          if step == 3 and act and act.id == "sthr-act-walkbackward" and not act.completed then
            R.advanceAct(act, inv)
            if G.ended then return end
          end
        end
        FX.afterDiscover(inv, L)
      end
    end
    R.checkObjectives()
  end

  --- Spend n clues from these investigators (most clues first).
  function R.spendClues(payers, n, quiet)
    local left = n
    table.sort(payers, function(a, b) return a.clues > b.clues end)
    while left > 0 do
      local best
      for _, inv in ipairs(payers) do if inv.clues > 0 and (not best or inv.clues > best.clues) then best = inv end end
      if not best then break end
      best.clues = best.clues - 1
      local tok = table.remove(best.clueTokens)
      if tok and T.alive(tok) then tok.destruct() end
      left = left - 1
    end
    R.G.metrics.clues_spent = R.G.metrics.clues_spent + (n - left)
    return n - left
  end

  ------------------------------------------------------------ objectives --

  --- Mandatory delivery objectives resolve at their condition. Ordinary
  -- group clue payments are free triggered abilities, offered only in a
  -- legal player window (RR pp.3, 23-26). A nested consequence must never
  -- inherit permission to pay from its enclosing player window.
  function R.checkObjectives(allowPaid)
    local G = R.G
    if G.ended then return end
    for _, district in ipairs(G.actOrder or {}) do
      local act = G.acts[district]
      if act and not act.completed and not G.finale then
        local payers = FX.canAdvance(act)
        if payers and (#payers == 0 or (allowPaid and R.AI.wantsAdvance(act))) then
          R.spendClues(payers, FX.actNeed(act.id))
          R.advanceAct(act, payers[1])
          if G.ended then return end
        end
      end
    end
  end

  function R.playerWindow(why)
    R.checkObjectives(true)
  end

  function R.contest(n, why)
    local G = R.G
    if not G.finale then return end
    for _ = 1, n do T.ctl("Contest") end
    G.contest = G.contest + n
    G.metrics.contest_sources[why] = (G.metrics.contest_sources[why] or 0) + n
    R.log("Contest %+d (%s): %d / %d", n, why, G.contest, R.consts().contest)
    if G.contest >= R.consts().contest then R.endLoop("contest") end
  end

  ------------------------------------------------------------ encounter --

  function R.drawEncounter(inv)
    local G = R.G
    if G.ended or inv.defeated then return end
    local card, reshuffled = T.drawEncounter(inv.color)
    if reshuffled then G.metrics.reshuffles = G.metrics.reshuffles + 1 end
    if not card then
      T.note("encounter draw found no card (round " .. G.round .. ")")
      G.metrics.draw_failures = G.metrics.draw_failures + 1
      return
    end
    local md = T.gm(card)
    local id = md.id or "?"
    local def = R.card(id)
    G.metrics.drawn[id] = (G.metrics.drawn[id] or 0) + 1
    G.metrics.encounters = G.metrics.encounters + 1
    R.log("%s draws %s", inv.name, card.getName())
    if def.type == "Enemy" or md.type == "Enemy" then
      if id == "sthr-onewhorides" then
        local L = R.locById("sthr-loc-wheel")
        if L then R.spawnEnemy(card, L, nil, { want = "The Wheel" }) else T.discardEncounter(card) end
        return
      end
      FX.spawnDrawn(inv, card)
      if R.textHas(def, "Surge") then R.drawEncounter(inv) end
      return
    end
    local handler = FX.ENC[id]
    if not handler then
      T.note("no effect encoded for " .. id)
      T.discardEncounter(card)
      return
    end
    local res = "discard"
    if P.cancelTreachery(inv, id, def) then
      G.metrics.cancelled_treacheries = G.metrics.cancelled_treacheries + 1
      res = R.textHas(def, "Surge") and "surge" or "discard"
    else
      local ok, err = pcall(handler, inv, card)
      if not ok then
        T.discardEncounter(card)
        error(err, 0)
      end
      res = err or "discard"
    end
    if T.alive(card) then T.discardEncounter(card) end
    if res == "surge" then R.drawEncounter(inv) end
  end

  ------------------------------------------------------------ attacks --

  function R.enemyAttack(en, inv, why)
    local G = R.G
    if inv.defeated or en.dead then return end
    if P.dodge(inv, en) then return end
    G.metrics.attacks = G.metrics.attacks + 1
    R.log("%s attacks %s (%s)", en.name, inv.name, why or "")
    local dealt = R.hurt(inv, en.def.damage or 0, en.def.horror or 0, en.name, { enemy = en })
    FX.afterAttack(en, inv)
    if en.id == "weakness:Silver Twilight Acolyte" or en.name == "Silver Twilight Acolyte" then R.placeDoom(1, "Silver Twilight Acolyte (doom)") end
  end

  --- Attacks of opportunity before a provoking action.
  function R.attacksOfOpportunity(inv, notAppointed)
    local G = R.G
    for _, en in ipairs(G.enemies) do
      if en.engaged == inv and not en.exhausted and not R.sleepwalking(en) then
        G.metrics.aoo = G.metrics.aoo + 1
        R.enemyAttack(en, inv, "attack of opportunity")
        if inv.defeated or G.ended then return end
      end
    end
    local A = G.appointed
    if A.engaged == inv and not A.exhausted and R.stage() >= 3 and not notAppointed then
      R.appointedAttack(inv, "attack of opportunity")
    end
  end

  function R.appointedAttack(inv, why)
    local G = R.G
    if inv.defeated then G.appointed.engaged = nil return end
    if P.itMeansWait(inv, "appointed-attack") then return end
    local def = R.card("sthr-appointed")
    G.metrics.appointed_attacks = G.metrics.appointed_attacks + 1
    R.log("The Appointed attacks %s (%s)", inv.name, why)
    local dealt = R.hurt(inv, def.damage or 2, def.horror or 2, "The Appointed", {enemy={id="sthr-appointed",def=def}})
    R.raise(1, "The Appointed (Arrived) attacks")
  end

  ------------------------------------------------------------ actions --

  local A_ = {}
  R.ACT = A_

  function A_.investigate(inv, opts)
    opts = opts or {}
    local L = R.locOf(inv)
    local shroud = R.shroud(L)
    local fl = P.findAsset(inv, "Flashlight")
    if fl and fl.uses > 0 and shroud > 0 and not opts.noFlash then
      fl.uses = fl.uses - 1
      shroud = math.max(0, shroud - 2)
    end
    local ok, margin = R.test(inv, "int", shroud, { kind = "investigate", important = opts.important, target = opts.target })
    if ok then
      local n = 1 + P.resultBonus(inv, "Deduction", margin)
      R.discover(inv, L, n)
      if P.findAsset(inv, "Dr. Milan Christopher") then inv.resources = inv.resources + 1 end
    end
    return ok
  end

  function A_.move(inv, to, opts)
    R.moveInv(inv, to, opts)
  end

  function A_.fight(inv, en, weapon)
    local G = R.G
    local skill = "com"
    local w = weapon and P.WEAPON[weapon.name]
    if w and w[4] then skill = w[4] end
    if weapon and w and w[3] then weapon.uses = weapon.uses - 1 end
    local ok, margin, token = R.test(inv, skill, R.enemyFight(en), { kind = "fight", weapon = weapon, enemy = en, important = true })
    if weapon and weapon.name:find("Shrivelling",1,true) and (token == "Skull" or token == "Cultist" or token == "Tablet"
        or token == "Elder Thing" or token == "Auto-fail") then
      R.hurt(inv, 0, weapon.name == "Shrivelling (5)" and 2 or 1, "Shrivelling")
    end
    if weapon and weapon.name == "Baseball Bat" and (token == "Skull" or token == "Auto-fail") then
      for i, a in ipairs(inv.assets) do if a == weapon then table.remove(inv.assets, i) inv.discard[#inv.discard + 1] = a.rec break end end
    end
    if ok then
      local dmg = 1 + ((w and w[2]) or 0)
      if weapon and weapon.name == "Shotgun (4)" then dmg = math.max(1, math.min(5, margin)) end
      if weapon and weapon.name == ".41 Derringer (2)" and margin < 1 then dmg = dmg - 1 end
      if weapon and weapon.name == "Switchblade (2)" and margin < 2 then dmg = dmg - 1 end
      if weapon and weapon.name == "Machete" then
        local engaged = 0
        for _, x in ipairs(G.enemies) do if x.engaged == inv then engaged = engaged + 1 end end
        if engaged > 1 then dmg = dmg - 1 end
      end
      if weapon and weapon.name == "Switchblade" and margin >= 2 then dmg = dmg + 1 end
      dmg = dmg + P.resultBonus(inv, "Vicious Blow", margin)
      R.damageEnemy(en, dmg, inv, weapon and weapon.name or "fight")
      if weapon and weapon.name == ".41 Derringer (2)" and margin >= 3
         and (weapon.actionRound ~= G.round or weapon.actionTurn ~= G.turnOf) then
        weapon.actionRound,weapon.actionTurn = G.round,G.turnOf
        inv.actionsLeft = (inv.actionsLeft or 0) + 1
      end
    elseif R.hasRetaliate(en) and not en.exhausted and not en.dead then
      R.enemyAttack(en, inv, "retaliate")
    end
    return ok
  end

  function R.cannotEvade(en)
    if en.id ~= "sthr-housewins" then return false end
    local cass = R.invById("sthrcass")
    if not cass then return false end
    for _, x in ipairs(R.G.inv) do if x ~= cass and (x.memory or 0) >= (cass.memory or 0) then return false end end
    return true
  end

  function A_.evade(inv, en, opts)
    opts = opts or {}
    if R.cannotEvade(en) then return false end
    local ok, _, token = R.test(inv, opts.skill or "agi", R.enemyEvade(en), { kind = "evade", enemy = en, important = true })
    if opts.blinding and (token == "Skull" or token == "Cultist" or token == "Tablet" or token == "Elder Thing" or token == "Auto-fail") then
      inv.actionsLeft = math.max(0,(inv.actionsLeft or 0)-1)
      if opts.blinding >= 2 then R.hurt(inv,0,1,"Blinding Light") end
    end
    if ok then
      en.exhausted = true
      if en.engaged then en.engaged = nil end
      R.placeEnemy(en)
      local pp = P.findAsset(inv, "Pickpocketing")
      if pp and not pp.exhausted then pp.exhausted = true ; P.draw(inv, 1) end
      if opts.blinding then R.damageEnemy(en, opts.blinding, inv, "Blinding Light") end
      R.G.metrics.evades = R.G.metrics.evades + 1
      FX.onEvade(inv, en)
    end
    return ok
  end

  function A_.engage(inv, en)
    en.engaged = inv
    R.placeEnemy(en)
  end

  --- Hold Back's test difficulty (4; what-if: another value during the finale).
  function R.holdBackDiff()
    return (R.G.finale and (R.WHATIF or {}).finaleHoldBackDiff) or 4
  end

  function A_.holdBack(inv, automatic)
    local G = R.G
    if G.appointed.exhausted or G.appointed.holdBackRound == G.round or R.appointedLoc() ~= R.locOf(inv) or R.stage() < 1 then return false end
    local skill = (R.skillBase(inv, "wil") + P.staticBonus(inv, "wil", {}) >= R.skillBase(inv, "com") + P.staticBonus(inv, "com", {})) and "wil" or "com"
    G.metrics.holdback_attempts = G.metrics.holdback_attempts + 1
    if G.finale and G.logFlags["You carry the walker's ring"] and not G.ringUsed then G.ringUsed,automatic=true,true end
    local ok = automatic or R.test(inv, skill, R.holdBackDiff(), { kind = "holdback", important = true })
    if ok then
      G.metrics.holdbacks = G.metrics.holdbacks + 1
      local card = R.appointedCard()
      local before = R.hour()
      -- the card's Hold Back button pushes it back and rewinds the Hour counter
      T.click(card, "Hold Back")
      E.run(0.3)
      R.touch()
      if R.hour() < before then R.rewind(0) ; R.returnHourCard(R.hour(), before) ; G.metrics.rewinds = G.metrics.rewinds + 1 end
      G.appointed.exhausted = true
      G.appointed.holdBackRound = G.round
      G.appointed.engaged = nil
      R.contest((R.WHATIF or {}).holdBackValue or 1, "Hold Back")
    end
    return ok
  end

  --- Play a card from hand (asset or event); returns true if played.
  function A_.play(inv, card)
    local G = R.G
    local n = card.name
    if card.type == "Asset" then
      local a = P.playAsset(inv, card)
      if n == "The Ambergrove Lamp" then R.log("the Lamp is in play") end
      return true
    end
    -- events
    P.discardFromHand(inv, card)
    inv.resources = inv.resources - P.playCost(inv, card)
    if tostring(card.traits or ""):find("Recollection",1,true) then inv.lastTurn.recollection = true end
    G.metrics.cards_played = G.metrics.cards_played + 1
    R.log("%s plays %s", inv.name, n)
    if n == "Emergency Cache" then inv.resources = inv.resources + 3
    elseif n == "Working a Hunch" then R.discover(inv, R.locOf(inv), 1)
    elseif n == "Drawn to the Flame" then
      R.drawEncounter(inv)
      if not inv.defeated and not G.ended then R.discover(inv, R.locOf(inv), 2) end
    elseif n == "Sneak Attack" then
      local t = R.AI.bestEnemyHere(inv, function(en) return en.exhausted end)
      if t then R.damageEnemy(t, 2, inv, "Sneak Attack") end
    elseif n == "Elusive" then
      for _, en in ipairs(G.enemies) do if en.engaged == inv then en.engaged = nil ; R.placeEnemy(en) end end
      local to = R.AI.chooseMove(inv, R.locOf(inv), true, { noEnemies = true })
      if to then R.moveInv(inv, to, { teleport = true }) end
    elseif n == "Cunning Distraction" then
      for _, en in ipairs(G.enemies) do
        if en.loc == inv.loc then en.exhausted = true ; en.engaged = nil ; R.placeEnemy(en) end
      end
    elseif n == "Mind over Matter" then
      inv.mindOverMatter = true
    elseif n == "Blinding Light" then
      local t = R.AI.bestEnemyHere(inv, function(en) return en.engaged == inv end)
      if t then A_.evade(inv, t, { skill = "wil", blinding = (card.level or 0) >= 2 and 2 or 1 }) end
    elseif n == "Rehearsed Escape" then
      -- the Elite choice (raise Dissonance by 1) is limited once per loop
      local t = R.AI.bestEnemyHere(inv, function(en) return en.engaged == inv and P.rehearsedLegal(inv, en) end)
      if t then
        if R.hasTrait(t.def, "Elite") then inv.loopUsed.rehearsedElite = true ; R.raise(1, "Rehearsed Escape (cost)", inv) end
        t.exhausted, t.engaged = true, nil
        R.placeEnemy(t)
        G.metrics.evades = G.metrics.evades + 1
        FX.onEvade(inv, t)
      end
    elseif n == "The Long Way Round" then
      -- its doom-free first crossing is limited once per loop
      local waived = inv.loopUsed.longWay == true
      for _ = 1, 2 do
        local here = R.locOf(inv)
        local target = R.AI.targetFor(inv)
        local step = target and R.route(here, target)
        if step and R.canEnter(here, step) then
          local free = not waived and R.isCrossing(here, step)
          if free then waived = true ; inv.loopUsed.longWay = true end
          R.moveInv(inv, step, { noHour = free })
        else break end
      end
    elseif n == "The Hour I Learned Your Name" then
      inv.loopUsed.hourName = true
      if R.appointedLoc() == R.locOf(inv) and not G.appointed.exhausted and G.appointed.holdBackRound ~= G.round then
        if A_.holdBack(inv, true) and R.knows("the-appointeds-name") then
          T.ctl("Appointed", true) ; R.touch()
        end
      else
        local t = R.AI.bestEnemyHere(inv, function(en) return not en.dead end)
        if t and R.test(inv, "wil", 3, { kind = "ability", important = true }) then
          t.engaged, t.exhausted = nil, true
          if not R.hasTrait(t.def, "Elite") then t.skipReady = true end
          R.placeEnemy(t)
        end
      end
    elseif n == "I Remember the Ending" then
      -- Test [wil] (X = Dissonance, minimum 2): look at the top 3; for 1
      -- Dissonance, put the worst of them on the bottom; the rest on top, the
      -- worst last.
      local ok = R.test(inv, "wil", math.max(2, R.dissonance()), { kind = "ability", important = true })
      if ok then
        local function threat(md)
          local def=R.card(md.id)
          return (def.type=="Enemy" and 3 or 0)+(R.hasTrait(def,"Time") and 2 or 0)
        end
        local worst = 0
        local deck = T.encounterDeck()
        if deck and deck.type == "Deck" then
          for i, e in ipairs(deck.getObjects()) do
            if i > 3 then break end
            worst = math.max(worst, threat(T.decode(e.gm_notes) or {}))
          end
        end
        if worst >= 3 and R.dissonance() + 1 < R.consts().glitch then
          R.raise(1, "I Remember the Ending", inv)
          T.reorderEncounterTop(3, function(md) return -threat(md) end)
          T.moveTopEncounterBottom()
          T.reorderEncounterTop(2, threat)
        else
          T.reorderEncounterTop(3, threat)
        end
      end
      inv.loopUsed.rememberEnding = true
    end
    return true
  end

  --- An [action] ability of an asset in play.
  function A_.assetAbility(inv, a, mode, target, repeating)
    local G = R.G
    if a.name == "Encyclopedia (2)" then
      a.exhausted = true
      target = target or inv
      if target == inv or not target.round.nobodyBelieves then target.round.encyclopedia = {skill=mode or "int"} end
    elseif a.name == "Beat Cop" then
      if not target or target.loc ~= inv.loc or target.dead or a.exhausted or a.dmg >= a.hp then return false end
      a.exhausted = true ; a.dmg = a.dmg + 1
      if a.dmg >= a.hp then
        for i, x in ipairs(inv.assets) do if x == a then table.remove(inv.assets,i) ; inv.discard[#inv.discard+1] = a.rec break end end
      end
      R.damageEnemy(target,1,inv,"Beat Cop")
    elseif a.name == "First Aid" then
      a.uses = a.uses - 1
      local t = R.AI.mostHurtHere(inv)
      if t then if t.damage >= t.horror then R.heal(t, 1, 0) else R.heal(t, 0, 1) end end
    elseif a.name == "Medical Texts" then
      local t = R.AI.mostHurtHere(inv, true)
      local ok = R.test(inv, "int", 2, { kind = "ability" })
      if t then if ok then R.heal(t, 1, 0) else R.hurt(t, 1, 0, "Medical Texts") end end
    elseif a.name == "Old Book of Lore" then
      a.exhausted = true
      P.draw(inv, 1)
    elseif a.name == "The Bell of Ambergrove" then
      a.exhausted = true
      a.uses = a.uses - 1
      if mode == "evade" and target then
        if A_.evade(inv, target, { skill = "wil" }) then
          for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
            if x == inv or not x.round.nobodyBelieves then R.heal(x, 0, 1) end
          end
        end
      else
        inv.loopUsed.bell = true
        R.raise(2, "The Bell of Ambergrove (cost)", inv)
        if mode == "advance" then R.advance(1, "The Bell of Ambergrove") else R.rewind(1, "The Bell of Ambergrove") end
      end
    elseif a.name == "Lucky Compass" then
      a.exhausted = true
      if mode == "jump" then
        R.addMemory(inv, -1, "Lucky Compass", a)
        T.api("shApiTally", { id = inv.id, kind = "spent", delta = 1 })
      else
        for _, en in ipairs(G.enemies) do
          if en.engaged == inv and not R.hasTrait(en.def, "Elite") then en.engaged = nil ; R.placeEnemy(en) end
        end
      end
      if target then R.moveInv(inv, target, { teleport = mode == "jump" }) end
    elseif a.name == "Cassandra's Notebook" then
      a.exhausted = true
      local ok, margin = R.test(inv, "int", R.shroud(R.locOf(inv)), { kind = "investigate", important = true, bonus = 1 })
      if ok then R.discover(inv, R.locOf(inv), 1 + P.resultBonus(inv,"Deduction",margin)) ; P.draw(inv, 1) end
    elseif a.name == "Stolen Minute" then
      a.exhausted, a.uses = true, a.uses - 1
      inv.actionsLeft = inv.actionsLeft + 1
    elseif a.name == "The Ambergrove Lamp" then
      a.exhausted = true
      local deck = T.encounterDeck()
      if deck and deck.type == "Deck" then
        local entries = deck.getObjects()
        local top = entries[1]
        if top then
          local md = T.decode(top.gm_notes) or {}
          local def = R.card(md.id)
          -- take 1 horror to place it on the bottom
          if (def.type == "Enemy" or (def.type == "Treachery" and R.hasTrait(def, "Time")))
             and inv.sanity - inv.horror > 2 then
            R.hurt(inv, 0, 1, "The Ambergrove Lamp")
            T.moveTopEncounterBottom()
          end
        end
      end
      if target then
        local free = not inv.loopUsed.lamp and R.isCrossing(R.locOf(inv), target) and R.dissonance() + 1 < R.consts().glitch
        if free then inv.loopUsed.lamp = true ; R.raise(1, "The Ambergrove Lamp (cost)", inv) end
        R.moveInv(inv, target, { noHour = free })
      end
    elseif a.name == "Marked Deck" then
      P.markedDeck(inv, a, mode)
    end
    if not repeating then
      local can = function()
        if a.name == "The Bell of Ambergrove" then
          return mode == "evade" and a.uses > 0 and target and not target.dead and target.engaged == inv and not R.cannotEvade(target)
        end
        if a.name == "Stolen Minute" then return a.uses > 0 end
        if a.name == "Cassandra's Notebook" then return R.clues(R.locOf(inv)) > 0 end
        if a.name == "First Aid" then return a.uses > 0 and R.AI.mostHurtHere(inv) ~= nil end
        if a.name == "Medical Texts" then return R.AI.mostHurtHere(inv,true) ~= nil end
        if a.name == "Old Book of Lore" then return true end
        if a.name == "The Ambergrove Lamp" then return true end
        if a.name == "Lucky Compass" then
          if mode == "jump" and (a.memory or 0) < 1 then return false end
          local here = R.locOf(inv)
          local goal = R.AI.targetFor(inv)
          local nextLocation = goal and R.route(here, goal)
          if not nextLocation or nextLocation == here or not R.canEnter(here,nextLocation) then return false end
          if mode == "jump" then
            if not nextLocation.revealed then return false end
            local known = false
            for fact,v in pairs(G.knowledge) do if v and R.SCEN.FACT_DISTRICT[fact] == nextLocation.district then known = true end end
            if not known then return false end
          end
          target = nextLocation
          return true
        end
        return false
      end
      P.afterOwnAbility(inv, { canRepeat = can, resolve = function() A_.assetAbility(inv, a, mode, target, true) end })
    end
  end

  ------------------------------------------------------------ phases --

  function R.mythos()
    local G = R.G
    G.phase = "mythos"
    if G.round >= 2 then
      R.placeDoom(1, "Mythos phase")
      R.checkDoom()
    end
    for _, inv in ipairs(R.aliveInvs()) do
      R.drawEncounter(inv)
    end
    FX.checkWakes()
    R.playerWindow("Mythos encounter draws complete")
  end

  function R.investigation()
    local G = R.G
    G.phase = "investigation"
    local order = R.AI.turnOrder()
    for _, inv in ipairs(order) do
      if not inv.defeated then
        G.turnOf = inv
        R.turn(inv)
        G.turnOf = nil
      end
    end
  end

  function R.turn(inv)
    local G = R.G
    inv.lastTurn = {}
    inv.bridgeFlag = false          -- The Bridge Remembers: "during your most recent turn or since it ended"
    G.enteredThisTurn = {}
    local actions = 3
    if P.findAsset(inv, "Leo De Luca") then actions = actions + 1 end
    inv.actionsLeft = actions
    R.AI.startTurn(inv)
    local guard = 0
    while inv.actionsLeft > 0 and not inv.defeated and not G.ended do
      guard = guard + 1
      if guard > 20 then break end
      R.playerWindow("before action")
      FX.checkWakes()
      local choice = R.AI.choose(inv)
      if not choice then break end
      local cost = choice.actions or 1
      inv.actionsLeft = inv.actionsLeft - cost
      G.metrics.actions[choice.kind] = (G.metrics.actions[choice.kind] or 0) + cost
      if choice.provokes ~= false then R.attacksOfOpportunity(inv, choice.provokes == "notAppointed") end
      if not inv.defeated and not G.ended then choice.run() end
      R.playerWindow("after action")
      -- free abilities that open up after the action (the Town Hall Steps' calm side)
      local here = R.locOf(inv)
      if here and not G.ended then FX.townHallFree(inv, here) end
    end
    R.playerWindow("turn ends")
    -- Dead Air ends at the end of that investigator's next turn
    if G.deadAir and G.deadAir.inv == inv then
      if G.deadAir.armed then
        T.ctl("[static]", true)
        G.deadAir = nil
        R.touch()
      else
        G.deadAir.armed = true
      end
    end
    P.endTurn(inv)
    inv.turnDone = true
  end

  -- a copy of a list to iterate while it changes (a move, attack or defeat can
  -- add or remove enemies). Not { a and table.unpack(t) or unpack(t) }: an
  -- and/or expression keeps only the first value, so that copy held one enemy
  -- and every other enemy skipped the enemy phase.
  local function copyList(t)
    local c = {}
    for i, v in ipairs(t) do c[i] = v end
    return c
  end

  function R.enemyPhase()
    local G = R.G
    G.phase = "enemy"
    FX.checkWakes()
    -- hunters move
    for _, en in ipairs(copyList(G.enemies)) do
      if not en.dead and not en.engaged and not en.exhausted and not R.sleepwalking(en) and R.isHunter(en) then
        local here = G.locs[en.loc]
        if here and #R.investigatorsAt(here) == 0 then
          local target = R.AI.huntTarget(en)
          if target then
            local step = R.route(here, target, { enemy = true })
            if step then
              en.loc = step.guid
              R.placeEnemy(en)
              G.metrics.enemy_moves = G.metrics.enemy_moves + 1
              FX.onEnemyMoved(en)
              if G.ended then return end
              R.engageAt(step)
            end
          end
        end
      end
    end
    -- the Appointed hunts (the Control moves it)
    local A = G.appointed
    if R.stage() >= 2 and not A.exhausted and not A.engaged then
      local card = R.appointedCard()
      if card and T.hasLabel(card, "Hunt") then
        T.click(card, "Hunt")
        E.run(0.2)
        G.metrics.appointed_hunts = G.metrics.appointed_hunts + 1
        R.appointedEngageCheck()
      end
    end
    R.playerWindow("hunters complete")
    -- RR 3.3: each investigator resolves their complete batch of attacks,
    -- with a player window between investigators rather than between enemies.
    for _, inv in ipairs(R.aliveInvs()) do
      for _, en in ipairs(copyList(G.enemies)) do
        if not en.dead and en.engaged == inv and not en.exhausted and not R.sleepwalking(en) then
          R.enemyAttack(en, inv, "enemy phase")
          en.exhausted = true
          if G.ended then return end
        end
      end
      if A.engaged == inv and not A.exhausted and R.stage() >= 3 then
        R.appointedAttack(inv, "enemy phase")
        A.exhausted = true
      end
      R.playerWindow("investigator attacks complete")
    end
  end

  function R.upkeep()
    local G = R.G
    G.phase = "upkeep"
    R.playerWindow("Upkeep begins")
    for _, en in ipairs(G.enemies) do
      if en.skipReady then en.skipReady = nil else en.exhausted = false end
    end
    G.appointed.exhausted = false
    for _, inv in ipairs(R.aliveInvs()) do
      if inv.sealedToken then T.chaosBag().putObject(inv.sealedToken) ; inv.sealedToken = nil ; E.run(0.1) ; R.touch() end
      inv.storyExhausted = nil
      inv.round.encyclopedia = nil -- its bonus lasts only this phase
      for _, a in ipairs(inv.assets) do
        a.exhausted = false
      end
      P.draw(inv, 1)
      inv.resources = inv.resources + 1
      while #inv.hand > 8 do inv.discard[#inv.discard + 1] = table.remove(inv.hand, 1) end
    end
    -- the round ends
    FX.endOfRound()
    if G.ended then return end
    local L = R.appointedLoc()
    if R.stage() == 1 and L then
      for _, inv in ipairs(R.investigatorsAt(L)) do
        if not P.itMeansWait(inv, "approach-horror") then R.hurt(inv, 0, 1, "The Appointed (Sensed)") end
      end
    end
    for _, t in ipairs(G.tempStatic) do for _ = 1, t.n do T.ctl("[static]", true) end end
    G.tempStatic = {}
    G.crowdTurns = false
    G.inkRuns = {}
    G.roundGroup = {}
    G.crossedThisRound = {}
    for _, inv in ipairs(G.inv) do
      inv.round = {}
      inv.mindOverMatter = false
      inv.namedToken = nil
      inv.turnDone = false
    end
    R.touch()
    FX.checkWakes()
    for _, L2 in ipairs(G.locList) do R.engageAt(L2) end
    R.playerWindow("round ends")
  end

  function R.scanLocationsLight()
    for _, L in ipairs(R.G.locList or {}) do
      if T.alive(L.obj) then L.closed = T.hasLabel(L.obj, "CLOSED") end
    end
  end

  --- The Control places the Appointed when it manifests; the engine
  -- notes where it is and whether it can act.
  function R.syncAppointedArrival()
    local G = R.G
    local stage = R.stage()
    if stage == 0 then G.appointed.engaged = nil end
    if stage >= 1 and not G.appointed.seenRound then
      G.appointed.seenRound = G.round
      G.metrics.appointed_manifest_round = G.round
      G.metrics.appointed_manifest_hour = R.hour()
      local L = R.appointedLoc()
      G.metrics.appointed_manifest_at = L and L.id or "not on a location"
      R.log("The Appointed manifests at %s (stage %d)", L and L.name or "?", stage)
    end
    if stage ~= (G.appointed.lastStage or 0) then
      R.log("The Appointed's Approach: stage %d", stage)
      G.appointed.lastStage = stage
    end
    G.metrics.stage_max = math.max(G.metrics.stage_max, stage)
  end
end
