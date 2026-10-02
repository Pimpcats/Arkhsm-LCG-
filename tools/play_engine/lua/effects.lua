-- The effects table (designer tooling): every scenario card of The Still
-- Hour, keyed by card id, encoded from its effective text (the owner's
-- overrides over the print layer; tools/play_engine/cards.py). Numbers
-- (shroud, fight, health, clue thresholds...) are read from the card data or
-- the table, never copied here. COVERAGE says, per card, whether its text is
-- encoded in full or approximated (and how); the report lists the latter.

return function(R, T)
  local E = T.E
  local FX = {}
  R.FX = FX

  local COVERAGE = {}
  FX.COVERAGE = COVERAGE
  local function cov(id, how) COVERAGE[id] = how or "full" end

  local ENC = {}      -- revelation handlers: fn(inv, card) -> "discard" | "keep" | "surge"
  FX.ENC = ENC

  local function horror(inv, n, why) R.hurt(inv, 0, n, why) end

  local function staticForRound(n, why)
    for _ = 1, n do T.ctl("[static]") end
    R.G.tempStatic[#R.G.tempStatic + 1] = { n = n, why = why, untilRound = R.G.round }
    R.touch()
  end

  ---------------------------------------------------------- the Hours --

  for h = 1, 9 do cov("sthr-hour-" .. h) end
  cov("sthr-hour-4", "full; the lead investigator picks the revealed location other than the Square with the fewest clues that no investigator is at when there is one")

  --- The Wheel: "Forced – After the Hourglass advances: Each investigator at the Wheel takes 1 horror."
  function FX.afterAdvance()
    local G = R.G
    R.P.onHourReachedPlayers(R.hour())  -- recharge once per complete advance
    local wheel = R.locById("sthr-loc-wheel")
    if wheel and not G.riderDefeated then
      for _, inv in ipairs(R.investigatorsAt(wheel)) do horror(inv, 1, "The Wheel") end
    end
    -- Why Thirteen?: "After the Hourglass advances, if the investigator who
    -- controls Parish Register is at The Belfry, advance."
    for _, act in pairs(G.acts) do
      local A = FX.ACTS[act.id] or {}
      if A.onAdvance and act.holder and not act.completed and not act.holder.defeated
         and R.locOf(act.holder) == R.locById(A.at) then
        R.advanceAct(act, act.holder)
        if G.ended then return end
      end
    end
  end
  --- The Flooded Crypt: "Forced – At the end of the round: Each investigator at the Flooded Crypt takes 1 damage."
  function FX.endOfRound()
    local crypt = R.locById("sthr-loc-floodedcrypt")
    if crypt and crypt.revealed and not crypt.closed then
      for _, inv in ipairs(R.investigatorsAt(crypt)) do
        R.hurt(inv, 1, 0, "The Flooded Crypt")
        if R.G.ended then return end
      end
    end
  end

  --- The parts of "When reached" the Control token leaves to the players.
  function FX.onHourReached(h, cancelled)
    local G = R.G
    G.metrics.hour_round[h] = G.metrics.hour_round[h] or G.round
    G.metrics.curve[#G.metrics.curve + 1] = { round = G.round, hour = h, diss = R.dissonance(), stage = R.stage() }
    -- (the Wheel's horror is at the end of the round: FX.endOfRound)
    if G.impassable then G.impassable = nil end
    if cancelled then return end
    if h == 2 then
      for _, inv in ipairs(R.aliveInvs()) do R.drawEncounter(inv) end
    elseif h == 3 and G.bellDefeated then
      -- The Bell-Ringer Beneath was defeated: Hour III's text does not resolve
      -- (undo the +1 the Control applied)
      R.lower(1, "Hour III does not resolve (the Bell-Ringer is defeated)")
    elseif h == 3 then
      -- the Belfry's unrevealed side: "Forced – When Hour III is reached: Reveal the Belfry."
      local belfry = R.locById("sthr-loc-belfry")
      if belfry and not belfry.revealed and not belfry.closed then R.reveal(belfry) end
      local atChurch = false
      for _, inv in ipairs(R.aliveInvs()) do if (R.locOf(inv) or {}).district == "Church" then atChurch = true end end
      if atChurch and not R.knows("the-thirteenth-toll") then R.raise(1, "Hour III (Church)") end
      for _, en in ipairs(G.enemies) do
        if en.id == "sthr-bellringer" then
          en.exhausted = false
          -- it attacks the nearest investigator at its location or a connecting location
          local here = G.locs[en.loc]
          local best, bd
          for _, inv in ipairs(R.aliveInvs()) do
            local d = here and (R.paths(here, { enemy = true })[inv.loc]) or 99
            if d and (bd == nil or d < bd) then best, bd = inv, d end
          end
          local reach = (R.WHATIF or {}).bellReach or 1                    -- what-if: another distance
          if best and reach and bd > reach then best = nil end
          if best and not (R.WHATIF or {}).bellNoAttack then R.enemyAttack(en, best, "Hour III") end
        end
      end
    elseif h == 4 and R.knows("the-hour-was-wrong") then
      R.log("Hour IV's text does not resolve (The Hour Was Wrong)")
    elseif h == 4 then
      -- the lead chooses a revealed location with the fewest clues, other than
      -- the Square: impassable. Among the fewest, a careful lead spares the
      -- places the party needs (any act's location, the next steps of each
      -- investigator's route) and the crossroads
      local need = {}
      for _, act in pairs(G.acts) do
        local spec = FX.ACTS[act.id] or {}
        if spec.at then need[spec.at] = true end
        if spec.carry then need[spec.carry.take] = true end
        for _, id in ipairs(spec.sequence or {}) do need[id] = true end
        if spec.needLamp then need["sthr-loc-lanternroom"] = true end
      end
      local onRoute = {}
      for _, inv in ipairs(R.aliveInvs()) do
        local target = R.AI.targetFor(inv)
        local here = R.locOf(inv)
        if target and here and target ~= here then
          local _, _, _, path = R.route(here, target)
          for _, X in ipairs(path or {}) do onRoute[X.guid] = true end
        end
      end
      local best, bc
      for _, L in ipairs(G.locList) do
        if L.revealed and not L.closed and L.id ~= "sthr-loc-hubsquare" and L.id ~= "sthr-loc-square" then
          local c = R.clues(L)
          local occupied = #R.investigatorsAt(L) > 0
          local degree = 0
          for _ in pairs(L.adj or {}) do degree = degree + 1 end
          local score = c * 10 + (occupied and 3 or 0) + (need[L.id] and 6 or 0) + (onRoute[L.guid] and 4 or 0)
                        + math.max(0, degree - 1)
          if bc == nil or score < bc then best, bc = L, score end
        end
      end
      if best then
        G.impassable = best.guid
        R.log("Hour IV: %s is impassable", best.name)
        for _, inv in ipairs(R.investigatorsAt(best)) do
          local to = R.AI.chooseMove(inv, best, true)
          if to then R.moveInv(inv, to, { noHour = true }) end
        end
      end
    elseif h == 7 then
      if R.knows("the-appointeds-name") then G.appointed.exhausted = true end
    elseif h == 8 then
      G.hourEightFight = true
    elseif h == 9 then
      if G.finale then R.endLoop("hour9") end
      -- "when Hour IX is reached while your log records The Way the Night
      -- Breaks, you may begin the finale instead of ending the loop"
      if G.cfg.finaleAtNine and R.knows("the-way-the-night-breaks") then
        R.beginFinale(R.aliveInvs()[1], true)
        return
      end
      if G.prologue then R.endLoop("hour9") end
      R.endLoop("hour9")
    end
  end
  R.onHourReached = function(h, fx)
    R.scanLocationsLight()
    FX.onHourReached(h, fx)
    R.syncAppointedArrival()
  end

  --- Effects that cancel an Hour's "When reached" text before it resolves
  -- (the Town Hall Steps' calm side, It Means 'Wait').
  function R.hourPrevent(h)
    local G = R.G
    if h == 9 then return false end
    if G.townHallNamed == h then
      G.townHallNamed = nil
      G.metrics.cancelled_hours[#G.metrics.cancelled_hours + 1] = h
      R.log("Hour %d's When reached is cancelled (Town Hall Steps)", h)
      return true
    end
    return R.P.itMeansWaitHour(h)
  end

  function R.cancelAdvance(why)
    local G = R.G
    -- the finale's setup Skip to Hour V is an instruction, not an advance to cancel
    if why == "the finale begins" then return false end
    if G.rememberEnding and G.round <= G.rememberEnding then
      G.rememberEnding = nil
      G.metrics.cancelled_advances = G.metrics.cancelled_advances + 1
      return true
    end
    if G.finale and G.nameUnspoken and not G.nameUnspokenUsed and R.hour() >= 7 then
      G.nameUnspokenUsed = true
      G.metrics.cancelled_advances = G.metrics.cancelled_advances + 1
      R.log("The name is spoken: the advance is cancelled")
      return true
    end
    return false
  end

  ---------------------------------------------------------- scenario reference --

  cov("sthr-scn-stillhour")
  --- Token modifier and after-effects (Easy / Standard side).
  function FX.tokenValue(name, inv)
    local G = R.G
    local band = R.band()
    if name == "Skull" then return (band ~= "Calm") and -2 or -1 end
    if name == "Cultist" then return -2 end
    if name == "Tablet" then return -2 end
    if name == "Elder Thing" then return -3 end
    if name == "Static" then return (G.deadAir and G.deadAir.active) and -4 or -3 end
    if name == "Auto-fail" then return nil end
    if name == "Elder Sign" then return R.P.elderSign(inv) end
    return tonumber(name) or 0
  end
  function FX.tokenAfter(name, inv, success, test, margin)
    local W = R.WHATIF or {}
    -- (Easy / Standard side; W.oldTokens: the side before the 12-round loops)
    if name == "Cultist" and not success and (W.oldTokens or (margin or -9) <= -2) then R.raise(1, "Cultist token") end
    if name == "Tablet" and R.stage() >= (W.oldTokens and 1 or 2) then horror(inv, 1, "Tablet token") end
    if name == "Elder Thing" and not success then R.placeDoom(1, "Elder Thing token") end
    -- Static: the Control raised Dissonance when it left the bag
  end

  ---------------------------------------------------------- locations --

  cov("sthr-loc-square") ; cov("sthr-loc-almanacsteps") ; cov("sthr-loc-hubsquare")
  cov("sthr-loc-townhallsteps", "full; the calm side's ability names the next Hour that has a harmful When reached")
  cov("sthr-loc-recordsoffice") ; cov("sthr-loc-well") ; cov("sthr-loc-nave") ; cov("sthr-loc-belfry")
  cov("sthr-loc-floodedcrypt") ; cov("sthr-loc-vestry") ; cov("sthr-loc-milestones") ; cov("sthr-loc-lowbridge")
  cov("sthr-loc-turning") ; cov("sthr-loc-lanternroom") ; cov("sthr-loc-windingstair") ; cov("sthr-loc-keepersquarters")
  cov("sthr-loc-wheel") ; cov("sthr-loc-hallofmirrors") ; cov("sthr-loc-ticketbooth") ; cov("sthr-loc-readingroom")
  cov("sthr-loc-press") ; cov("sthr-loc-sealedstudy") ; cov("sthr-loc-longpier")
  cov("sthr-loc-readingroom", "full; the [reaction] is always taken")
  cov("sthr-loc-hubsquare", "full; the party never resigns (a resigned investigator cannot win the loop's objectives)")

  function FX.onEnter(inv, L)
    local G = R.G
    G.enteredThisTurn[L.id] = true
    if L.id == "sthr-loc-almanacsteps" then R.raise(1, "The Almanac Steps") end
    if L.id == "sthr-loc-belfry" and not R.knows("the-thirteenth-toll") and not FX.registerCancels() then R.raise(1, "The Belfry") end
    if L.id == "sthr-loc-well" then inv.wellRound = G.round end
    if L.id == "sthr-loc-well" and not R.knows("the-sheriff-is-already-dead") then horror(inv, 1, "The Well") end
    if L.id == "sthr-loc-nave" and not R.test(inv, "wil", 2, { kind = "location" }) then horror(inv, 1, "The Nave") end
    if L.id == "sthr-loc-lowbridge" and not R.test(inv, "agi", 2, { kind = "location" }) then
      R.hurt(inv, 1, 0, "The Low Bridge")
    end
    if L.id == "sthr-loc-ticketbooth" and not G.logFlags["You hold the ticket"] then
      inv.resources = math.max(0, inv.resources - 1)
    end
    if G.finale and L.id == "sthr-loc-sealedstudy" and not G.studyVisited[inv.id] and (R.WHATIF or {}).studyVisits then
      G.studyVisited[inv.id] = true
      R.contest(1, "first time at the Sealed Study")
    end
  end

  --- Location abilities an investigator can use now: list of
  -- { name, actions, fn, why } (the AI picks among them).
  function FX.locationAbilities(inv, L)
    local G = R.G
    local out = {}
    if L.id == "sthr-loc-longpier" and not G.group.longPier then
      out[#out + 1] = { name = "Long Pier", actions = 1, kind = "memory", fn = function()
        G.group.longPier = true
        local ok = R.test(inv, "wil", 2, { kind = "ability" })
        if ok then R.addMemory(inv, 1, "The Long Pier") end
      end }
    end
    if L.id == "sthr-loc-vestry" and G.roundGroup.vestry ~= true and R.partyClues() > R.cluesNeededTotal() then
      out[#out + 1] = { name = "Vestry", actions = 1, kind = "dissonance", fn = function()
        G.roundGroup.vestry = true
        R.spendClues({ inv }, 1)
        R.lower(1, "The Vestry")
      end }
    end
    if L.id == "sthr-loc-turning" and not G.group.turning then
      out[#out + 1] = { name = "Turning", actions = 1, kind = "rewind", fn = function()
        G.group.turning = true
        R.raise(2, "The Turning (cost)", inv)
        R.rewind(1, "The Turning")
      end }
    end
    if L.id == "sthr-loc-keepersquarters" and not inv.round.keeper and (inv.damage > 0 or inv.horror > 0) then
      out[#out + 1] = { name = "Keeper's Quarters", actions = 2, kind = "heal", fn = function()
        inv.round.keeper = true
        R.heal(inv, 1, 1)
      end }
    end
    if L.id == "sthr-loc-hallofmirrors" and not G.group.mirrors then
      out[#out + 1] = { name = "Hall of Mirrors", actions = 1, kind = "memory-year", fn = function()
        G.group.mirrors = true
        R.pendingYear(inv, 1, "The Hall of Mirrors")
        R.addMemory(inv, 2, "The Hall of Mirrors")
      end }
    end
    if L.id == "sthr-loc-press" and G.roundGroup.press ~= true and #G.tempStatic > 0 and inv.clues > 0 then
      out[#out + 1] = { name = "Press", actions = 1, kind = "static", fn = function()
        G.roundGroup.press = true
        R.spendClues({ inv }, 1)
        local t = table.remove(G.tempStatic)
        T.ctl("[static]", true)
        if t.n > 1 then t.n = t.n - 1 ; G.tempStatic[#G.tempStatic + 1] = t end
        R.touch()
      end }
    end
    if L.id == "sthr-loc-recordsoffice" and not G.group.records and R.partyClues() >= 2 then
      for _, x in ipairs(R.investigatorsAt(L)) do
        if (x.pendingYears or 0) > 0 then
          out[#out + 1] = { name = "Records Office", actions = 1, kind = "year", fn = function()
            G.group.records = true
            R.spendClues(R.investigatorsAt(L), 2)
            T.click(x.card, "Years pending", true)
            x.pendingYears = x.pendingYears - 1
          end }
          break
        end
      end
    end
    if L.id == "sthr-loc-lanternroom" and L.calm and not G.lampLit then
      out[#out + 1] = { name = "Light the lamp", actions = 1, kind = "lamp", fn = function()
        G.lampLit = true
        R.log("The Lantern Room's lamp is lit")
      end }
    end
    return out
  end

  --- The Town Hall Steps' calm side ([free], group limit once per loop).
  function FX.townHallFree(inv, L)
    local G = R.G
    if L.id ~= "sthr-loc-townhallsteps" or not L.calm or G.group.townhall then return false end
    local h = R.hour()
    -- the next harmful Hour after this one: VIII (+2 Dissonance, Arrived), II, III, VI, IV
    for _, want in ipairs({ 8, 6, 3, 2, 4, 5, 7 }) do
      if want > h then
        G.group.townhall = true
        G.townHallNamed = want
        R.log("Town Hall Steps: Hour %d is named", want)
        return true
      end
    end
    return false
  end

  --- The Winding Stair's climb ([action] Test [agi] (2)).
  function FX.climb(inv)
    local ok = R.test(inv, "agi", 2, { kind = "ability" })
    local lr = R.locById("sthr-loc-lanternroom")
    if ok and lr then R.moveInv(inv, lr, {}) else R.hurt(inv, 1, 0, "The Winding Stair") end
    return ok
  end

  --- Would this crossing be free (a group-limit ability still unused)? (no side effects)
  function FX.freeCrossingAvailable(a, b)
    local G = R.G
    local key = R.crossKey(a, b)
    if key == "Road|Square" and R.knows("the-road-remembers") and not G.group.roadFree then return true end
    if key == "Almanac|Square" and G.logFlags["The true page reached the Press"] and not G.group.pressFree then return true end
    return false
  end

  function FX.freeCrossing(a, b, inv)
    local G = R.G
    local key = R.crossKey(a, b)
    if key == "Road|Square" and R.knows("the-road-remembers") and not G.group.roadFree then
      G.group.roadFree = true
      return true
    end
    if key == "Almanac|Square" and G.logFlags["The true page reached the Press"] and not G.group.pressFree then
      G.group.pressFree = true
      return true
    end
    return false
  end

  ---------------------------------------------------------- acts --

  -- act id -> objective description the engine and the AI share:
  --   at       = location id an investigator must be at (group spend) or that
  --              the contributing investigators must be at (contrib = true)
  --   perinv   = clues per investigator (read from the card's clue value)
  --   action   = the objective is an [action] (with a test)
  local ACTS = {}
  FX.ACTS = ACTS
  local function clueNeed(id) local c = R.card(id) return (c.clues or 0) * (c.clues_per_investigator and R.G.n or 1) end

  ACTS["sthr-act-firsthour"] = { at = "sthr-loc-almanacsteps", contrib = true, fact = nil, spend = true, minHour = 8 }
  -- carry = a take-and-deliver objective: an [action] at carry.take spends the
  -- act's clues (any investigator contributes when carry.any, else those at
  -- carry.take) to take control of a set-aside story asset; the act advances
  -- when its controller is at `at`. A defeated controller drops it.
  -- onAdvance = the carry is delivered only when the Hourglass advances (FX.afterAdvance)
  ACTS["sthr-act-whythirteen"] = { at = "sthr-loc-belfry", fact = "the-thirteenth-toll", spend = true, onAdvance = true,
                                   carry = { asset = "sthr-item-register", take = "sthr-loc-vestry", any = true } }
  -- twoPlace = one investigator at each location at once (solo: at the second, having been at the first this round)
  ACTS["sthr-act-sheriffdead"] = { at = "sthr-loc-townhallsteps", fact = "the-sheriff-is-already-dead", spend = true,
                                   twoPlace = { "sthr-loc-well", "sthr-loc-townhallsteps" } }
  ACTS["sthr-act-almanachid"] = { at = "sthr-loc-press", fact = "what-the-almanac-hid", spend = true,
                                  carry = { asset = "sthr-item-almanac", take = "sthr-loc-readingroom", any = true } }
  ACTS["sthr-act-hourwaswrong"] = { at = "sthr-loc-vestry", contrib = true, fact = "the-hour-was-wrong", spend = true,
                                    carry = { asset = "sthr-item-drownedpage", take = "sthr-loc-floodedcrypt" } }
  ACTS["sthr-act-vote"] = { at = "sthr-loc-townhallsteps", contrib = true, fact = "the-vote-that-never-ends", spend = true,
                            carry = { asset = "sthr-item-ledger", take = "sthr-loc-recordsoffice" } }
  ACTS["sthr-act-appointedname"] = { at = "sthr-loc-sealedstudy", contrib = true, fact = "the-appointeds-name", spend = true,
                                     minStage = 3 }
  ACTS["sthr-act-ninthdeath"] = { at = "sthr-loc-lanternroom", contrib = true, fact = "the-keepers-ninth-death", spend = true,
                                  needLamp = true, carry = { asset = "sthr-item-logbook", take = "sthr-loc-keepersquarters" } }
  ACTS["sthr-act-lamp"] = { at = "sthr-loc-lanternroom", contrib = true, fact = "the-lamp-was-never-lit", action = true,
                            test = { "wil", "com" }, diff = 3, failClues = true }
  ACTS["sthr-act-wheelturns"] = { at = "sthr-loc-wheel", contrib = true, fact = "the-wheel-still-turns", action = true,
                                  doomCost = 2 }
  -- fare = paid in clues, Memory from own cards and resources (FX.FARE_RATE for 1)
  FX.FARE_RATE = 3
  ACTS["sthr-act-bargain"] = { at = "sthr-loc-ticketbooth", contrib = true, fact = "the-ticket-takers-bargain", action = true,
                               fare = true }
  ACTS["sthr-act-walkbackward"] = { sequence = { "sthr-loc-turning", "sthr-loc-lowbridge", "sthr-loc-milestones" },
                                    fact = "the-road-remembers" }
  ACTS["sthr-act-walksbeside"] = { at = "sthr-loc-turning", standFirm = true, fact = "who-walks-beside-you" }
  ACTS["sthr-act-lasthour"] = { contest = true }
  for id in pairs(ACTS) do cov(id) end
  cov("sthr-act-lasthour", "full; the [action] spends one recorded deep entry per action, in the order they were recorded")

  --- The act's clue cost still to pay: a carry act's story asset already
  -- taken (held or dropped) owes nothing more.
  function FX.actNeed(actId)
    if ACTS[actId] and ACTS[actId].carry then
      for _, act in pairs(R.G.acts or {}) do
        if act.id == actId and (act.holder or act.dropped) then return 0 end
      end
    end
    return clueNeed(actId)
  end

  --- The story assets: who controls one gets its skill bonus (and penalty).
  --- (each one's ability is encoded where it triggers; a constant modifier sits here)
  FX.STORY = {
    ["sthr-item-logbook"] = { name = "Keeper's Logbook" },        -- R.hurt: 1 less damage (exhaust)
    ["sthr-item-register"] = { name = "Parish Register" },        -- the Verger hunts its holder; cancels a Belfry/Thirteen raise
    ["sthr-item-drownedpage"] = { name = "Drowned Page" },        -- Lost Hour: 1 doom instead of the advance
    ["sthr-item-ledger"] = { name = "Town Ledger" },              -- [action]: an Echo here sleeps this round
    ["sthr-item-almanac"] = { name = "Bound Almanac", agi = -1 }, -- R.test: redraws a Static token
  }
  --- The investigator who controls this story asset now, or nil.
  function FX.storyHolder(assetId)
    for _, inv in ipairs(R.aliveInvs()) do if inv.story and inv.story.id == assetId then return inv end end
    return nil
  end
  --- Exhaust a held story asset for its reaction: true if it was ready.
  function FX.useStory(assetId)
    local h = FX.storyHolder(assetId)
    if not h or h.storyExhausted then return nil end
    h.storyExhausted = true
    R.G.metrics.story_uses = R.G.metrics.story_uses or {}
    R.G.metrics.story_uses[assetId] = (R.G.metrics.story_uses[assetId] or 0) + 1
    return h
  end
  function FX.registerCancels()
    if FX.useStory("sthr-item-register") then R.log("Parish Register cancels a Dissonance raise") return true end
    return false
  end
  for id in pairs(FX.STORY) do cov(id, "full; a defeated controller drops it at their location, where any investigator may take it with an [action]") end
  cov("sthr-item-ledger", "full; the AI reads an Echo to sleep when it is engaged with one or one is ready at its location")
  cov("sthr-act-bargain", "full; the fare is paid in resources (3 for 1) first, then clues, then Memory")
  cov("sthr-act-sheriffdead", "full; the nearest investigator to each place goes there")

  --- A carry act's [action]: the investigator takes control of the story asset
  -- (paying the act's clues), or picks a dropped one up.
  function R.takeStory(inv, act)
    local G = R.G
    local A = act and ACTS[act.id]
    if not inv or inv.defeated or not A or not A.carry or act.completed or act.holder or inv.story then return false end
    local L
    if act.dropped then L = G.locs and G.locs[act.dropped] else L = R.locById(A.carry.take) end
    local here = R.locOf(inv)
    if not L or L.closed or not here or here.guid ~= L.guid then return false end
    if act.dropped then
      act.dropped = nil
    else
      local payers = A.carry.any and R.aliveInvs() or R.investigatorsAt(L)
      local need, have = clueNeed(act.id), 0
      for _, payer in ipairs(payers) do have = have + (payer.clues or 0) end
      if have < need then return false end
      if R.spendClues(payers, need) ~= need then error("story asset preflight/payment disagreement") end
      G.metrics.story_taken = G.metrics.story_taken or {}
      G.metrics.story_taken[#G.metrics.story_taken + 1] = { id = A.carry.asset, round = G.round, hour = R.hour() }
    end
    act.holder = inv
    inv.story = { id = A.carry.asset, act = act }
    R.log("%s takes control of %s", inv.name, FX.STORY[A.carry.asset].name)
    return true
  end

  --- A defeated controller's story asset stays at their location.
  function FX.dropStory(inv, L)
    if not inv.story then return end
    local act = inv.story.act
    act.holder = nil
    act.dropped = L and L.guid
    inv.story = nil
    R.log("%s drops %s", inv.name, FX.STORY[ACTS[act.id].carry.asset].name)
  end

  --- Can the act's objective be met right now by the party (no action)?
  -- Returns the investigators whose clues pay, or nil.
  function FX.canAdvance(act)
    local G = R.G
    local A = ACTS[act.id]
    if not A or A.action or A.sequence or A.standFirm or A.contest or A.onAdvance then return nil end
    if A.needLamp and not G.lampLit then return nil end
    if A.carry then
      -- "If the investigator who controls X is at Y, advance."
      local h = act.holder
      if h and not h.defeated and R.locOf(h) == R.locById(A.at) then return {} end
      return nil
    end
    if A.minHour and R.hour() < A.minHour then return nil end       -- "Hour VIII or later" (The First Hour)
    if A.minStage and R.stage() < A.minStage then return nil end    -- "while the Approach is Arrived"
    if A.twoPlace then
      -- one investigator at each location at once; solo: at the second, having been at the first this round
      local a, b = R.locById(A.twoPlace[1]), R.locById(A.twoPlace[2])
      if not a or not b then return nil end
      local atA, atB = R.investigatorsAt(a), R.investigatorsAt(b)
      local ok = (#atA > 0 and #atB > 0)
      if G.n == 1 and #atB > 0 and (atB[1].wellRound == G.round) then ok = true end
      if not ok then return nil end
      local have = 0
      for _, inv in ipairs(R.aliveInvs()) do have = have + inv.clues end
      if have >= clueNeed(act.id) then return R.aliveInvs() end
      return nil
    end
    local L = R.locById(A.at)
    if not L or L.closed then return nil end
    local here = R.investigatorsAt(L)
    if #here == 0 then return nil end
    local payers = A.contrib and here or R.aliveInvs()
    local have = 0
    for _, inv in ipairs(payers) do have = have + inv.clues end
    if have >= clueNeed(act.id) then return payers end
    return nil
  end

  --- Advance a district's act: its back is recorded, the next act (Part II)
  -- becomes current or the act deck leaves.
  function R.advanceAct(act, by)
    local G = R.G
    local A = ACTS[act.id] or {}
    act.completed = true
    if act.holder then act.holder.story = nil ; act.holder = nil end     -- the story asset leaves play
    G.metrics.acts_completed[#G.metrics.acts_completed + 1] = { id = act.id, round = G.round, hour = R.hour(),
                                                                 by = by and by.id }
    R.log("ACT ADVANCES: %s (Hour %d, round %d)", act.id, R.hour(), G.round)
    -- the card is turned over and set aside by its deck
    local c = T.cardWithId(act.id) or T.takeCard(act.id)
    if c then
      local p = act.pos or c.getPosition()
      c.setPosition({ p.x + 2.7, p.y + 0.2, p.z })
      c.setRotation({ 0, 180, 180 })
    end
    if act.id == "sthr-act-firsthour" then
      R.endLoop("act")
    end
    if act.id == "sthr-act-lamp" then G.lampLit = true end
    if A.fact then
      T.tickLog("k:" .. A.fact, true)
      R.touch()
      G.knowledge[A.fact] = true
      G.metrics.knowledge[#G.metrics.knowledge + 1] = A.fact
      R.P.onKnowledge(A.fact)
    end
    R.scanLocations()
    -- Part II: the district's act 2a becomes current if its requirements are met
    local nextId = act.next
    if nextId and G.partTwo and FX.actTwoRequirements(nextId) then
      local n = { id = nextId, district = act.district, pos = act.pos }
      G.acts[act.district] = n
      FX.actBecomesCurrent(n)
    else
      G.acts[act.district] = nil
      -- "Otherwise, remove this act deck from the game": act 2a leaves the table too
      if nextId then
        local rest = T.cardWithId(nextId)
        if rest then rest.setPosition({ -60, 2, -30 - 3 * #G.metrics.acts_completed }) end
      end
    end
  end

  function FX.actTwoRequirements(id)
    if id == "sthr-act-appointedname" then
      return R.knows("what-the-almanac-hid") and R.knows("the-vote-that-never-ends")
    end
    return true
  end

  --- "Forced – When this act becomes the current act".
  function FX.actBecomesCurrent(act)
    local G = R.G
    if act.id == "sthr-act-hourwaswrong" then
      R.scanLocations()
      local crypt = R.locById("sthr-loc-floodedcrypt")
      local c = T.takeCard("sthr-bellringer")
      if c and crypt then
        if not crypt.revealed and not crypt.closed then R.reveal(crypt) end
        R.spawnEnemy(c, crypt, nil, { want = "The Flooded Crypt" })
      elseif c then
        R.spawnEnemy(c, nil, nil, { want = "The Flooded Crypt", ok = false, note = "the Flooded Crypt is closed or not in play" })
      end
    elseif act.id == "sthr-act-vote" then
      local steps = R.locById("sthr-loc-townhallsteps")
      local c = T.takeCard("sthr-wearssheriff")
      if c and steps then R.spawnEnemy(c, steps, nil, { want = "The Town Hall Steps" }) end
    elseif act.id == "sthr-act-walksbeside" then
      G.walksBesideCurrent = true
      local turning = R.locById("sthr-loc-turning")
      local c = T.searchEncounter(function(md) return md.id == "sthr-waitingcongregation" end)
      if c and turning then
        R.spawnEnemy(c, turning, nil, { want = "The Turning" })
        local enc = T.encounterDeck()
        if enc and enc.type == "Deck" then enc.shuffle() end
      elseif turning then
        G.metrics.bad_spawns[#G.metrics.bad_spawns + 1] = { id = "sthr-waitingcongregation", want = "The Turning",
          used = "none", note = "no Waiting Congregation left in the encounter deck or discard pile" }
      end
    elseif act.id == "sthr-act-appointedname" then
      -- the Sealed Study opens (the Control: act 2a is current)
      R.scanLocations()
    end
  end

  ---------------------------------------------------------- encounter cards --

  local function surge() return "surge" end

  cov("sthr-losthour")
  ENC["sthr-losthour"] = function(inv)
    local G = R.G
    if G.logFlags["You refused the ticket"] and not G.group.refusedTicket then
      G.group.refusedTicket = true
      return "discard"
    end
    if FX.useStory("sthr-item-drownedpage") then
      R.log("Drowned Page: the Lost Hour costs 1 doom instead")
      R.placeDoom(1, "Lost Hour (Drowned Page)")
      return "discard"
    end
    local mode = (R.WHATIF or {}).lostHour                           -- what-if: "doom" / "old"
    if mode == "doom" then R.placeDoom(R.hour() >= 6 and 2 or 1, "Lost Hour")
    elseif mode == "doom2" then R.placeDoom(2, "Lost Hour")
    elseif mode == "old" then R.advance(R.hour() >= 6 and 2 or 1, "Lost Hour")
    else R.advance(1, "Lost Hour") end
    return "discard"
  end

  cov("sthr-slippage")
  ENC["sthr-slippage"] = function(inv)
    staticForRound(1, "Slippage")
    return "surge"
  end

  cov("sthr-wrongturn", "full; the lead investigator chooses the destination toward that investigator's goal")
  ENC["sthr-wrongturn"] = function(inv)
    if R.test(inv, "agi", 3, { kind = "treachery" }) then return "discard" end
    local to = R.AI.chooseMove(inv, R.locOf(inv), true)
    if to then R.moveInv(inv, to, { noHour = true }) end
    return "discard"
  end

  cov("sthr-rewind")
  ENC["sthr-rewind"] = function(inv)
    if R.test(inv, "int", 3, { kind = "treachery", peril = true }) then return "discard" end
    local last = inv.lastTurn and inv.lastTurn.clueAt
    if last and inv.clues > 0 then
      local L = R.G.locs[last]
      R.spendClues({ inv }, 1, true)
      if L then T.spawnClueOn(L.obj, 1) end
    else
      horror(inv, 2, "Stutter")
    end
    return "discard"
  end

  cov("sthr-deadair")
  ENC["sthr-deadair"] = function(inv)
    local G = R.G
    if R.test(inv, "wil", 3, { kind = "treachery" }) then return "discard" end
    T.ctl("[static]")
    R.touch()
    G.deadAir = { active = true, inv = inv, turnsLeft = (G.phase == "investigation" and inv.turnDone ~= true) and 1 or 1,
                  armed = G.phase ~= "investigation" or inv.turnDone }
    return "discard"
  end

  cov("sthr-loopnotices")
  ENC["sthr-loopnotices"] = function(inv)
    local lt = inv.lastTurn or {}
    if R.test(inv, "wil", 3, { kind = "treachery" }) then return "discard" end
    R.raise((lt.recollection or lt.paidDiss) and 2 or 1, "The Loop Notices You")
    return "discard"
  end

  cov("sthr-yearinanight")
  ENC["sthr-yearinanight"] = function(inv)
    local ok, margin = R.test(inv, "wil", 3, { kind = "treachery", peril = true })
    if not ok then
      horror(inv, (R.WHATIF or {}).oldYear and math.max(1, -margin) or 1, "A Year in a Night")
      if not R.G.prologue and ((R.WHATIF or {}).oldYear or (margin or -9) <= -2) then R.pendingYear(inv, 1, "A Year in a Night") end
    end
    return "discard"
  end

  cov("sthr-forgotten")
  ENC["sthr-forgotten"] = function(inv)
    if R.test(inv, "int", 3, { kind = "treachery" }) then return "discard" end
    local have = inv.memory or 0
    local want = (R.WHATIF or {}).oldForgotten and 2 or 1
    local take = math.min(want, have)
    if take > 0 then R.addMemory(inv, -take, "What You've Forgotten", "any") end
    if take < want then horror(inv, want - take, "What You've Forgotten") end
    return "discard"
  end

  cov("sthr-oldbones")
  ENC["sthr-oldbones"] = function(inv)
    if R.test(inv, "com", 3, { kind = "treachery", peril = true }) then return "discard" end
    local old = inv.bracket == "Elder" or inv.bracket == "Ancient"
    R.hurt(inv, old and 2 or 1, 0, "Old Bones")
    return "discard"
  end

  cov("sthr-crossing")
  ENC["sthr-crossing"] = function(inv)
    local s0 = R.stage()
    T.ctl("Appointed")
    E.run(0.3)
    R.touch()
    R.G.metrics.approach_by_card = R.G.metrics.approach_by_card + (R.stage() - s0)
    if (R.WHATIF or {}).oldCrossing then R.raise(1, "The Crossing") else R.placeDoom(1, "The Crossing") end
    return "discard"
  end

  cov("sthr-samespeech")
  ENC["sthr-samespeech"] = function(inv)
    if R.test(inv, "wil", 3, { kind = "treachery", peril = true }) then return "discard" end
    local loops = R.G.loopsCompleted or 0
    local extra = R.knows("the-vote-that-never-ends") and 0 or math.min((R.WHATIF or {}).speechMax or 3, math.floor(loops / 3))
    horror(inv, 1 + extra, "The Same Speech")
    return "discard"
  end

  cov("sthr-crowdturns")
  ENC["sthr-crowdturns"] = function(inv)
    local G = R.G
    local any = false
    for _, en in ipairs(G.enemies) do if R.hasTrait(en.def, "Echo") then any = true ; en.exhausted = false end end
    if not any then return "surge" end
    G.crowdTurns = true
    for _, L in ipairs(G.locList) do R.engageAt(L) end
    return "discard"
  end

  cov("sthr-appointedwhisper")
  ENC["sthr-appointedwhisper"] = function(inv)
    if R.stage() >= 2 then
      horror(inv, 2, "The Appointed's Whisper")
      R.raise(1, "The Appointed's Whisper")
    else
      horror(inv, 1, "The Appointed's Whisper")
    end
    return "discard"
  end

  cov("sthr-darkthatwaits")
  ENC["sthr-darkthatwaits"] = function(inv)
    if R.test(inv, "wil", 3, { kind = "treachery" }) then return "discard" end
    local L = R.locOf(inv)
    local there = L and L.id == "sthr-loc-lanternroom" and not R.G.lampLit
    horror(inv, there and 2 or 1, "The Dark That Waits")
    return "discard"
  end

  cov("sthr-thirteen")
  ENC["sthr-thirteen"] = function(inv)
    R.placeDoom(1, "Thirteen")
    if (R.locOf(inv) or {}).district == "Church" and not FX.registerCancels() then R.raise(1, "Thirteen (Church)") end
    return "discard"
  end

  cov("sthr-risingwater", "attached to the location until the Hourglass advances")
  ENC["sthr-risingwater"] = function(inv)
    local G = R.G
    local L = R.locOf(inv)
    if L then G.risingWater[L.guid] = (G.risingWater[L.guid] or 0) + 1 end
    return "discard"
  end

  cov("sthr-bridgeremembers")
  ENC["sthr-bridgeremembers"] = function(inv)
    local G = R.G
    if inv.bridgeFlag then
      R.placeDoom(1, "The Bridge Remembers")
      return "discard"
    end
    return "surge"
  end

  cov("sthr-wheelsturn")
  ENC["sthr-wheelsturn"] = function(inv)
    R.placeDoom(1, "The Wheel's Turn")
    for _, x in ipairs(R.aliveInvs()) do x.resources = x.resources + 1 end
    return "discard"
  end

  cov("sthr-reflectionlies")
  ENC["sthr-reflectionlies"] = function(inv)
    if R.test(inv, "wil", 3, { kind = "treachery" }) then return "discard" end
    local L = R.locOf(inv)
    if L and L.id == "sthr-loc-hallofmirrors" then
      horror(inv, 2, "Your Reflection Lies")
      staticForRound(1, "Your Reflection Lies")
    else
      horror(inv, 1, "Your Reflection Lies")
    end
    return "discard"
  end

  cov("sthr-pagethatwasnt")
  ENC["sthr-pagethatwasnt"] = function(inv)
    if R.test(inv, "int", 3, { kind = "treachery", peril = true }) then return "discard" end
    local banked = R.state().memory or 0
    local n = math.min((R.WHATIF or {}).pageMax or 3, math.ceil(banked / 6))
    if n > 0 then horror(inv, n, "The Page That Wasn't") end
    return "discard"
  end

  cov("sthr-inkrunsbackward")
  ENC["sthr-inkrunsbackward"] = function(inv)
    local L = R.locOf(inv)
    if L then R.G.inkRuns[L.guid] = R.G.round end
    return "discard"
  end

  cov("sthr-studydoor")
  ENC["sthr-studydoor"] = function(inv)
    local s = R.locById("sthr-loc-sealedstudy")
    if s and s.closed then
      staticForRound(1, "The Study Door")
      return "discard"
    end
    return "surge"
  end

  ---------------------------------------------------------- enemies --

  -- spawn instruction per enemy (card text "Spawn – ..."); nil = engaged with the drawer
  local SPAWN = {
    ["sthr-bandonsteps"] = "sthr-loc-townhallsteps", ["sthr-somethingonstair"] = "sthr-loc-windingstair",
    ["sthr-drownedverger"] = "sthr-loc-vestry", ["sthr-milecounter"] = "sthr-loc-milestones",
    ["sthr-barker"] = "sthr-loc-ticketbooth", ["sthr-compositor"] = "sthr-loc-press",
    ["sthr-bellringer"] = "sthr-loc-floodedcrypt", ["sthr-wearssheriff"] = "sthr-loc-townhallsteps",
    ["sthr-onewhorides"] = "sthr-loc-wheel",
  }
  FX.SPAWN = SPAWN
  for _, id in ipairs({ "sthr-waitingcongregation", "sthr-drownedchoir", "sthr-familiarface", "sthr-lamplighterecho",
                        "sthr-minutehand", "sthr-bandonsteps", "sthr-somethingonstair", "sthr-drownedverger",
                        "sthr-milecounter", "sthr-barker", "sthr-compositor", "sthr-bellringer", "sthr-wearssheriff",
                        "sthr-onewhorides", "sthr-uninvited" }) do cov(id) end
  cov("sthr-appointed", "full; its movement, manifesting and Hold Back run on the Control token (Board/Appointed modules); the engine adds engagement and attacks")
  cov("sthr-appointed-approach")

  local function locByName(id) return R.locById(id) end

  --- An enemy drawn from the encounter deck (or searched out) spawns.
  function FX.spawnDrawn(inv, card)
    local G = R.G
    local md = T.gm(card)
    local id = md.id
    local want = SPAWN[id]
    if want then
      local L = locByName(want)
      local name = R.card(want).name or want
      if not L then
        -- no such location in play: the enemy is discarded (Rules Reference, Spawn)
        G.metrics.bad_spawns[#G.metrics.bad_spawns + 1] = { id = id, want = name, used = "discarded",
                                                             note = "spawn location not in play" }
        R.log("%s: its spawn location (%s) is not in play: discarded", card.getName(), name)
        T.discardEncounter(card)
        return nil
      end
      if L.closed then
        G.metrics.bad_spawns[#G.metrics.bad_spawns + 1] = { id = id, want = name, used = "discarded",
                                                             note = "spawn location is closed" }
        T.discardEncounter(card)
        return nil
      end
      return R.spawnEnemy(card, L, nil, { want = name })
    end
    if id == "sthr-familiarface" then
      local best, bm
      for _, x in ipairs(R.aliveInvs()) do if bm == nil or (x.memory or 0) > bm then best, bm = x, x.memory or 0 end end
      local L = R.locOf(best or inv)
      return R.spawnEnemy(card, L, nil, { want = "the location of the investigator with the most Memory" })
    end
    if id == "sthr-housewins" then
      local best, bc
      for _, L in ipairs(G.locList) do
        if not L.closed then
          local c = R.clues(L)
          if bc == nil or c > bc then best, bc = L, c end
        end
      end
      return R.spawnEnemy(card, best, nil, { want = "the location with the most clues" })
    end
    -- no spawn instruction: engaged with the investigator who drew it
    local L = R.locOf(inv)
    return R.spawnEnemy(card, L, inv, { want = "engaged with the drawing investigator" })
  end

  function FX.onSpawn(en)
    -- the Drowned Choir wakes: 1 horror to each investigator there (once per loop)
  end

  function FX.onEnemyDefeated(en, inv)
    local G = R.G
    if en.id == "sthr-familiarface" and inv then R.addMemory(inv, 1, "Familiar Face") end
    if en.id == "sthr-uninvited" then R.contest(1, "the Uninvited defeated") end
    if en.id == "sthr-milecounter" then en.res = 0 end
    if en.id == "sthr-bellringer" then G.bellDefeated = true end      -- Hour III no longer resolves this loop
    if en.id == "sthr-onewhorides" then G.riderDefeated = true end    -- the Wheel's Forced no longer resolves
  end

  --- After an enemy moves (the Mile-Counter keeps count).
  function FX.onEnemyMoved(en)
    if en.id == "sthr-milecounter" then
      en.res = (en.res or 0) + 1
      if en.res >= 3 then
        en.res = 0
        R.placeDoom(1, "The Mile-Counter")
      end
    end
  end

  --- After an enemy attack (Barker, Arrived Appointed).
  function FX.afterAttack(en, inv)
    if en.id == "sthr-barker" then inv.resources = math.max(0, inv.resources - 2) end
  end

  --- The Drowned Choir: when it wakes, 1 horror to each investigator at its location (limit once per loop).
  function FX.checkWakes()
    local G = R.G
    for _, en in ipairs(G.enemies) do
      local asleep = R.sleepwalking(en)
      if en.wasAsleep and not asleep and en.id == "sthr-drownedchoir" and not en.wokeOnce then
        en.wokeOnce = true
        for _, x in ipairs(R.investigatorsAt(G.locs[en.loc] or {})) do horror(x, 1, "The Drowned Choir wakes") end
      end
      -- an Echo that wakes is exhausted: it engages no one until it readies
      -- (guide: Echoes and Sleepwalking; what-if wakeExhausted = false: the old rule)
      if en.wasAsleep and not asleep and (R.WHATIF or {}).wakeExhausted ~= false and not en.dead then
        en.exhausted = true
        en.engaged = nil
        G.metrics.woke_exhausted = (G.metrics.woke_exhausted or 0) + 1
      end
      en.wasAsleep = asleep
    end
  end

  --- The Compositor: after an investigator at its location fails a test (limit once per round).
  function FX.afterFail(inv)
    local G = R.G
    for _, en in ipairs(G.enemies) do
      if en.id == "sthr-compositor" and en.loc == inv.loc and en.roundUsed ~= G.round then
        en.roundUsed = G.round
        R.raise(1, "The Compositor")
      end
    end
  end

  --- The Drowned Verger: after you discover a clue at the Vestry, it engages you.
  function FX.afterDiscover(inv, L)
    if L.id == "sthr-loc-milestones" and not R.knows("the-road-remembers") then
      if not R.test(inv, "wil", 2, { kind = "location" }) then horror(inv, 1, "The Milestones") end
      return
    end
    -- the Reading Room's [reaction] (always taken): the last clue places 1 Memory
    if L.id == "sthr-loc-readingroom" and R.clues(L) == 0 and not R.G.group.readingRoom then
      R.G.group.readingRoom = true
      R.addMemory(inv, 1, "The Reading Room")
      return
    end
    if L.id ~= "sthr-loc-vestry" then return end
    for _, en in ipairs(R.G.enemies) do
      if en.id == "sthr-drownedverger" and en.loc == L.guid and not en.exhausted and not en.engaged then
        en.engaged = inv
        R.placeEnemy(en)
        R.log("The Drowned Verger engages %s", inv.name)
      end
    end
  end

  ---------------------------------------------------------- story cards --

  for _, id in ipairs({ "sthr-story-firstdark", "sthr-story-firstreset", "sthr-story-actii", "sthr-story-beforefinale",
                        "sthr-res-1", "sthr-res-2", "sthr-res-3", "sthr-res-4", "sthr-res-5", "sthr-res-6",
                        "sthr-res-bargain" }) do
    cov(id, "full (read at a loop's end; the engine picks the resolution by its condition)")
  end

  return FX
end
