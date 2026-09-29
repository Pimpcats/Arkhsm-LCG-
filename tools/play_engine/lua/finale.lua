-- Objective [action]s and the finale (The Last Hour): its setup from the
-- guide, contest progress, and the finale resolutions.

return function(R, T)
  local E = T.E
  local FX = R.FX

  ------------------------------------------------------------ objective actions --

  --- Light the Lamp, The Wheel Still Turns, The Ticket-Taker's Bargain.
  function R.objectiveAction(inv, act)
    local G = R.G
    local spec = FX.ACTS[act.id]
    local L = R.locById(spec.at)
    local need = FX.actNeed(act.id)
    local here = spec.contrib == false and R.aliveInvs() or R.investigatorsAt(L)
    R.spendClues(here, need)
    if spec.test then
      local skill, best = spec.test[1], -99
      for _, s in ipairs(spec.test) do
        local v = R.skillBase(inv, s) + R.P.staticBonus(inv, s, {})
        if v > best then skill, best = s, v end
      end
      local ok = R.test(inv, skill, spec.diff, { kind = "act", important = true, target = 0.8 })
      if ok then
        R.advanceAct(act, inv)
      elseif spec.failClues then
        -- place 1 [perinv] clues from the token pool on the location
        T.spawnClueOn(L.obj, need)
        G.metrics.objective_fails = (G.metrics.objective_fails or 0) + 1
      end
    else
      R.advanceAct(act, inv)
    end
  end

  --- Who Walks Beside You: Stand Firm against a ready Echo at the Turning.
  function R.standFirm(inv, en)
    local x = R.enemyFight(en)
    local skill = (R.skillBase(inv, "wil") >= R.skillBase(inv, "com")) and "wil" or "com"
    local ok = R.test(inv, skill, x, { kind = "act", important = true })
    if ok then
      en.exhausted = true
      en.engaged = nil
      R.placeEnemy(en)
      local act = R.G.acts.Road
      if act and act.id == "sthr-act-walksbeside" then R.advanceAct(act, inv) end
    end
  end

  function FX.onEvade(inv, en)
    local G = R.G
    local L = G.locs[en.loc]
    if G.walksBesideCurrent and L and L.id == "sthr-loc-turning" and R.hasTrait(en.def, "Echo") then
      local act = G.acts.Road
      if act and act.id == "sthr-act-walksbeside" and not act.completed then
        G.walksBesideCurrent = false
        R.advanceAct(act, inv)
      end
    end
  end

  ------------------------------------------------------------ the finale --

  local DEEP = { "the-keepers-ninth-death", "the-hour-was-wrong", "who-walks-beside-you", "the-vote-that-never-ends",
                 "the-ticket-takers-bargain", "the-appointeds-name" }

  --- [free] at the Sealed Study: begin the finale (guide: The Last Hour, Setup).
  function R.beginFinale(inv, atNine)
    local G = R.G
    if G.finale then return end
    G.finale = true
    G.metrics.finale_began = { round = G.round, hour = R.hour(), dissonance = R.dissonance(), atNine = atNine and true or false }
    R.log("THE FINALE BEGINS (Hour %d, Dissonance %d)", R.hour(), R.dissonance())
    -- 1. Place The Last Hour; district act decks are set aside
    for d, act in pairs(G.acts) do
      local c = T.cardWithId(act.id)
      if c then c.setPosition({ -60, 2, -12 }) end
    end
    G.actsBeforeFinale = G.acts
    G.acts, G.actOrder = {}, {}
    local box = T.placeBox("finale")
    E.run(1)
    local unv = T.takeCard("sthr-uninvited")
    -- 2. the Approach advances to Arrived (it manifests if set aside)
    local guard = 0
    while R.stage() < 3 and guard < 4 do
      guard = guard + 1
      T.ctl("Appointed")
      E.run(0.3)
      R.touch()
    end
    R.syncAppointedArrival()
    -- begun at Hour IX: Hours IX to VI go back on the deck, Hour V is current,
    -- no Hour resolves (right-click Hour four times)
    if atNine then R.rewind(4, "the finale begins at Hour IX") end
    -- the Uninvited at the revealed location farthest from all investigators, not closed
    if unv then
      local far, fd
      for _, L in ipairs(G.locList) do
        if L.revealed and not L.closed then
          local d = 99
          for _, x in ipairs(R.aliveInvs()) do
            local dist = R.paths(R.locOf(x), { enemy = true })[L.guid] or 99
            if dist < d then d = dist end
          end
          if fd == nil or d > fd then far, fd = L, d end
        end
      end
      if R.FINALE_SPAWN_AT then far = R.locById(R.FINALE_SPAWN_AT) or far end     -- what-if only
      R.spawnEnemy(unv, far, nil, { want = "the revealed location farthest from all investigators" })
    end
    if R.FINALE_SPAWN_AT then
      local L = R.locById(R.FINALE_SPAWN_AT)
      if L then R.placeAppointed(L) end
    end
    -- 3. Begin Finale on the Control: the Contest counter
    T.ctl("Begin Finale")
    E.run(0.3)
    R.touch()
    if G.logFlags["You have spoken the name"] then R.contest(2, "You have spoken the name") end
    if G.logFlags["The drowned heard the true hour"] then R.rewind(1, "The drowned heard the true hour") end
    G.nameUnspoken = G.logFlags["The name is kept unspoken"]
    G.deepToSpend = {}
    for _, f in ipairs(DEEP) do if R.knows(f) then G.deepToSpend[#G.deepToSpend + 1] = f end end
    -- the first time each investigator is at the Sealed Study (those already there gain it now)
    local study = R.locById("sthr-loc-sealedstudy")
    for _, x in ipairs(R.aliveInvs()) do
      if study and x.loc == study.guid and not G.studyVisited[x.id] then
        G.studyVisited[x.id] = true
        R.contest(1, "first time at the Sealed Study")
      end
    end
  end

  --- [action] on Contest the Crossing: spend a deep Knowledge entry.
  function R.spendDeep(inv)
    local G = R.G
    local f = table.remove(G.deepToSpend, 1)
    if f then
      G.metrics.deep_spent = (G.metrics.deep_spent or 0) + 1
      R.contest(1, "deep entry spent: " .. f)
    end
  end

  --- The finale resolution the party reads (it chooses among those it meets).
  function R.finaleResolution()
    local G = R.G
    local n = G.n
    local reached = G.contest >= R.consts().contest
    local banked = T.st().memory or 0
    if not reached then
      return banked >= 4 * n and "R5" or "R6"
    end
    local present = {}
    for _, inv in ipairs(G.inv) do if not inv.defeated then present[#present + 1] = inv end end
    local lf = G.logFlags
    if R.knows("the-keepers-ninth-death") then return "R3" end
    if R.knows("the-ticket-takers-bargain") and lf["You hold the ticket"]
       and banked >= (lf["You kept the night to yourselves"] and 3 or 4) * n then return "R1b" end
    if R.knows("the-vote-that-never-ends") and R.knows("the-appointeds-name") and lf["The vote still stands"] then return "R2" end
    for _, inv in ipairs(present) do if inv.bracket == "Ancient" then return "R1" end end
    return "R4"
  end
end
