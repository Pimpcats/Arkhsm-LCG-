-- The Dunwich benchmark (designer tooling): plays The Dunwich Legacy's
-- first three scenarios -- 1a Extracurricular Activity, 1b The House Always
-- Wins, 2 The Miskatonic Museum (tmm_effects.lua, tmm_play.lua) --
-- on the emulated SCED table The Still Hour's play engine uses, with the
-- same rules layer, AI and level-0 cards, as a baseline for The Still Hour.
--
-- Runs as a suite of the headless harness (tests/sced_real/run.lua
-- --suite-file tools/play_engine/lua/official/dwl_engine.lua --config <json>);
-- started by tools/play_engine/official/dwl.py (run.py --official dwl). The
-- table is booted once; SCED's own Dunwich campaign box (downloaded, not in
-- the repository) is loaded and Placed; each game respawns the scenario box
-- from that data and Places it with its own script, so locations, decks and
-- set-aside cards are the real SCED objects. One "@@GAME <json>" line per game.

return function(H)
  local E, J = H.E, H.E.J
  local here = (H.args["suite-file"] or ""):match("^(.*)[/\\]") or (H.ROOT .. "/tools/play_engine/lua/official")
  local base = here .. "/.."
  local T = dofile(base .. "/tablekit.lua")
  T.init(H)
  local R = {}
  dofile(base .. "/rules.lua")(R, T)
  dofile(here .. "/dwl_effects.lua")(R, T)
  dofile(here .. "/tmm_effects.lua")(R, T)      -- 2: The Miskatonic Museum
  dofile(base .. "/players.lua")(R, T)
  dofile(base .. "/flow.lua")(R, T)
  dofile(base .. "/ai.lua")(R, T)
  dofile(here .. "/dwl_rules.lua")(R, T)
  dofile(here .. "/dwl_players.lua")(R, T)
  dofile(here .. "/dwl_ai.lua")(R, T)
  dofile(here .. "/tmm_play.lua")(R, T)
  local FX, P = R.FX, R.P

  local cfg = J.decode(H.readFile(H.args.config))
  local cards = J.decode(H.readFile(cfg.cards))
  R.CARDS = cards.cards
  local decks = J.decode(H.readFile(cfg.decks))
  local guide = cfg.guide          -- {scenario: {resolutions = {id: steps}, steps = {id: step}}}
  R.WHATIF = cfg

  local function emit(tag, t) io.write("@@", tag, " ", J.encode(t), "\n") io.flush() end
  local function copy(t) return T.decode(J.encode(t)) end

  ------------------------------------------------------------ coverage --

  do
    local missing = {}
    for _, id in ipairs(cards.scenario_ids) do if not FX.COVERAGE[id] then missing[#missing + 1] = id end end
    local approx = {}
    for id, how in pairs(FX.COVERAGE) do if how ~= "full" then approx[#approx + 1] = { id = id, how = how } end end
    for name, how in pairs(P.DWL_APPROX) do if how ~= "full" then approx[#approx + 1] = { id = name, how = how } end end
    table.sort(approx, function(a, b) return a.id < b.id end)
    local playerMissing, seen = {}, {}
    for _, d in pairs(decks.decks) do
      for _, c in ipairs(d.cards) do
        if not P.CODED[c.name] and not seen[c.name] then seen[c.name] = true ; playerMissing[#playerMissing + 1] = c.name end
      end
    end
    table.sort(playerMissing)
    emit("COVERAGE", { missing = missing, approx = approx, scenario_cards = #cards.scenario_ids, player_missing = playerMissing })
  end

  ------------------------------------------------------------ the table --

  local campaign = J.decode(H.readFile(cfg.box))
  local boxData = {}
  for _, c in ipairs(campaign.ContainedObjects) do boxData[c.Nickname] = c end
  local campaignBag = E.spawnData(campaign, { position = { 52, 1.5, -55 } }, "campaign")
  E.run(2)
  T.click(campaignBag, "Place")        -- SCED's own MemoryBag: the scenario boxes, the log and the guide
  E.run(4)
  local BOXNAME = { ["1a"] = "1a: Extracurricular Activity", ["1b"] = "1b: The House Always Wins",
                    ["2"] = "2: The Miskatonic Museum" }
  local boxPos = {}
  for key, name in pairs(BOXNAME) do
    local b = T.find(function(o) return o.type == "Bag" and o.getName() == name end)
    if b then boxPos[key] = b.getPosition() ; b.destruct() end
  end
  E.run(0.5)

  local party = cfg.party
  local n = #party
  local counter = T.owned("Mythos", "InvestigatorCounter")
  if counter then counter.call("updateVal", n) end

  -- seat the investigators: their cards from SCED's All Player Cards bag onto the playmats
  local seats = {}
  local allCards = T.find(function(o) return o.type == "Bag" and o.getName() == "All Player Cards" end)
  for i, id in ipairs(party) do
    local color = T.MATS[i]
    local mat = T.mat(color)
    local pos = mat.positionToWorld({ -1.17, 0.1, -0.01 })
    local card
    if allCards then
      for _, e in ipairs(allCards.getObjects()) do
        if (T.decode(e.gm_notes) or {}).id == id then
          card = allCards.takeObject({ guid = e.guid, position = { pos.x, pos.y + 1, pos.z }, smooth = false })
          break
        end
      end
    end
    E.run(0.3)
    if card then E.drop(card, { pos.x, pos.y + 0.5, pos.z }, color) end
    seats[i] = { id = id, color = color, card = card }
  end
  E.run(2)
  local baseline = {}
  for _, o in ipairs(T.objects()) do baseline[o.getGUID()] = true end
  H.info("dwl engine: table ready, party " .. table.concat(party, ", "))

  ------------------------------------------------------------ setup --

  local function freshMetrics()
    return {
      damage = 0, horror = 0, defeats = 0, defeated = {}, clues = 0, clues_spent = 0, clues_by_round = {}, spawns = {},
      bad_spawns = {}, drawn = {}, encounters = 0, reshuffles = 0, draw_failures = 0, enemies_defeated = 0,
      defeated_by_id = {}, victory = {}, acts_completed = {}, curve = {}, tests = 0, tests_passed = 0, tokens = {},
      actions = {}, moves = 0, crossings = 0, crossing_hours = 0, attacks = 0, aoo = 0, cards_played = 0,
      weaknesses_drawn = 0, cancelled_treacheries = 0, evades = 0, enemy_moves = 0, doom_sources = {},
      damage_by = {}, horror_by = {}, defeated_by = {}, defeated_who = {}, dissonance_sources = {}, hour_sources = {},
      memory_on_cards = {}, contest_sources = {}, knowledge = {}, rewinds = 0, holdbacks = 0, holdback_attempts = 0,
      appointed_attacks = 0, appointed_hunts = 0, appointed_engagements = 0, stage_max = 0, card_years = 0,
      cancelled_hours = {}, cancelled_advances = 0, itmeanswait = 0, approach_by_card = 0, diss_max = 0,
    }
  end

  local function cleanTable()
    local chaos = T.chaosBag()
    for _, o in ipairs(T.objects()) do
      if not baseline[o.getGUID()] and o ~= chaos and T.alive(o) then
        local t = o.type
        if t == "Card" or t == "Deck" or t == "Bag" or o.memo == "clueDoom" or t == "Tile" or t == "Generic" then
          if not (t == "Bag" and tostring(o.getName()):find("Chaos", 1, true)) then o.destruct() end
        end
      end
    end
    T.returnTokens()
    -- SCED remembers which cards have spawned their tokens (by GUID): the respawned box reuses the GUIDs,
    -- so the tracker is reset as SCED's own Clean Up helper does
    local tracker = T.owned("Mythos", "TokenSpawnTracker")
    if tracker then tracker.call("resetAll") else T.note("no token spawn tracker") end
    E.run(0.5)
  end

  local function setChaosBag(extra)
    local tile = T.find(function(o) return o.type == "Tile" and o.getName() == "The Dunwich Legacy" and T.hasLabel(o, "Standard") end)
    if tile then T.click(tile, "Standard")
    elseif cfg.standardBag then
      -- a box without a difficulty tile (The Miskatonic Museum): the campaign's Standard bag, from SCED's 1a tile
      local list = {}
      for _, t in ipairs(cfg.standardBag) do list[#list + 1] = t end
      E.Global.call("setChaosBagState", list)
    else T.note("no difficulty tile") end
    E.run(1)
    if extra and #extra > 0 then
      local list = E.Global.call("getChaosBagState") or {}
      for _, t in ipairs(extra) do list[#list + 1] = t end
      E.Global.call("setChaosBagState", list)
      E.run(1)
    end
  end

  local function newGame(key, seed, camp)
    local sc = FX.SC[key]
    E.seed(seed)
    math.randomseed(seed)
    local G = {
      cfg = { objectives = sc.acts }, name = key, scen = key, seed = seed, n = n, round = 0, phase = "setup", clock = 0,
      inv = {}, locs = {}, locList = {}, enemies = {}, acts = {}, actOrder = { "Main" }, pendingCurrent = {},
      hoursAside = {}, tempStatic = {}, risingWater = {}, inkRuns = {}, crossedThisRound = {}, group = {},
      roundGroup = {}, enteredThisTurn = {}, studyVisited = {}, appointed = {}, knowledge = {}, logFlags = {},
      metrics = freshMetrics(), trace = cfg.trace and {} or nil, live = cfg.live, prologue = false, partTwo = false,
      loopsCompleted = 0, contest = 0, finale = false, doom = 0, attached = {}, asideDecks = {},
      camp = camp, agenda = { list = sc.agendas, i = 1 },
    }
    G.goal1a = (key == "1a" and not camp.otherDone) and "R1" or "R2"
    R.G = G
    T.errors = {}
    local errMark = #E.errors
    cleanTable()

    -- the scenario box from SCED's campaign data, Placed with its own script
    local box = E.spawnData(boxData[BOXNAME[key]], { position = boxPos[key] or { 12, 1.6, 28 } }, "campaign")
    E.run(1)
    T.click(box, "Place")
    E.run(3)
    setChaosBag(camp.tokens)
    if counter then counter.call("updateVal", n) end
    -- set-aside cards: out of the bag into the aside zone (out of play)
    local aside = T.find(function(o) return o.type == "Bag" and o.getName() == "Set-aside" end)
    local k = 0
    if aside then
      for _, e in ipairs(aside.getObjects()) do
        local obj = aside.takeObject({ guid = e.guid, position = FX.asidePos(k), smooth = false })
        k = k + 1
        E.run(0.05)
        if obj and obj.type == "Deck" then
          local ids = {}
          for _, x in ipairs(obj.getObjects()) do ids[#ids + 1] = (T.decode(x.gm_notes) or {}).id end
          G.asideDecks[obj.getName()] = ids
        end
      end
    end
    E.run(0.5)
    if FX.SETUP and FX.SETUP[key] then FX.SETUP[key](G) end      -- random locations, extra decks (the Museum)
    R.scanLocations()
    G.agendaPos = T.mythosSpot("agenda")
    local deck = T.encounterDeck()
    if deck and deck.type == "Deck" then deck.shuffle() end
    G.metrics.deck_size = T.deckCount(deck)
    G.acts.Main = { id = sc.acts[1], district = "Main", pos = T.mythosSpot("act") }
    -- The House Always Wins: Clover Club Pit Boss in the Clover Club Lounge
    if key == "1b" then
      local pb = T.cardWithId(FX.ID.pitboss)
      local lounge = R.locById(FX.ID.lounge)
      if pb and lounge then R.spawnEnemy(pb, lounge, nil, { want = "Clover Club Lounge" }) end
    end
    -- investigators at the starting location (revealed)
    local start = R.locById(sc.start)
    R.reveal(start)
    for i, s in ipairs(seats) do
      local id = s.id
      local w = camp.weakness and camp.weakness[id] or R.pick(decks.weaknesses)
      local dk = camp.decks and camp.decks[id] or decks.decks[id]
      local inv = P.newInvestigator(i, id, s.color, s.card, nil, nil, dk, w)
      inv.loc = start.guid
      -- trauma from earlier scenarios: each starts the scenario as that much damage / horror
      local tr = (camp.trauma or {})[id] or { physical = 0, mental = 0 }
      inv.damage, inv.horror = tr.physical, tr.mental
      G.inv[i] = inv
      G.metrics.weakness = G.metrics.weakness or {}
      G.metrics.weakness[id] = w and w.name
      G.wk = G.wk or {}
      G.wk[id] = w
    end
    E.run(0.5)
    return G, errMark
  end

  ------------------------------------------------------------ the end --

  --- The resolution's steps from the campaign guide data (arkham-cards-data).
  local function applyResolution(G, res, xpVictory)
    local gd = guide[G.scen]
    local out = { log = {}, tokens = {}, xp_bonus = 0, xp_victory = xpVictory, physical_all = 0, cards = {} }
    local steps = gd.resolutions[res == "NR" and "no_resolution" or res] or {}
    local function run(list)
      for _, sid in ipairs(list) do
        if sid == "resolution_1" then run(gd.resolutions.R1 or {}) end
        local st = gd.steps[sid]
        if st then
          for _, ef in ipairs(st.effects or {}) do
            if ef.type == "campaign_log" then out.log[#out.log + 1] = ef.id
            elseif ef.type == "add_chaos_token" then for _, t in ipairs(ef.tokens or {}) do out.tokens[#out.tokens + 1] = t end
            elseif ef.type == "trauma" and ef.investigator == "all" then out.physical_all = out.physical_all + (ef.physical or 0)
            elseif ef.type == "add_card" then out.cards[#out.cards + 1] = ef.card end
          end
          if st.input then
            if st.input.type == "counter" then
              for _, ef in ipairs(st.input.effects or {}) do
                if ef.type == "earn_xp" then out.xp_bonus = out.xp_bonus + (ef.bonus or 0) end
              end
            elseif st.input.type == "choose_one" and sid == "cheated" then
              -- "Did any player cheat?"
              if G.cheated then for _, ch in ipairs(st.input.choices or {}) do run(ch.steps or {}) end end
            end
          end
        end
      end
    end
    run(steps)
    return out
  end
  local TOKEN_ID = { tablet = "tablet", elder_thing = "elder", skull = "skull", cultist = "cultist" }

  local function finish(G)
    local m = G.metrics
    local e = G.ended or { reason = "unfinished", round = G.round }
    local res = G.resolution or ((e.reason == "defeat" or e.reason == "resigned") and "NR") or "unfinished"
    -- the victory display: defeated enemies with Victory X, revealed Victory locations with no clues
    local vic, xpv = {}, 0
    for _, id in ipairs(m.victory) do vic[#vic + 1] = id ; xpv = xpv + (R.card(id).victory or 0) end
    for _, L in ipairs(G.locList) do
      if (L.def.victory or 0) > 0 and L.revealed and R.clues(L) == 0 then vic[#vic + 1] = L.id ; xpv = xpv + L.def.victory end
    end
    local outcome = res ~= "unfinished" and applyResolution(G, res, xpv) or { log = {}, tokens = {}, xp_bonus = 0, physical_all = 0, cards = {} }
    -- tokens added during the game (Harold Walsted / Adam Lynch leaving play)
    if FX.checkStoryAllies then FX.checkStoryAllies() end
    for _, t in ipairs(G.tokensAdded or {}) do outcome.tokens[#outcome.tokens + 1] = t end
    local trauma, xp = {}, {}
    for _, inv in ipairs(G.inv) do
      local t = { physical = inv.trauma.physical + outcome.physical_all, mental = inv.trauma.mental }
      -- Smite the Wicked / Searching for Izzie: when the game ends, 1 mental trauma
      if inv.id == "02001" and G.smite and not G.smite.dead then t.mental = t.mental + 1 ; t.smite = true end
      if inv.id == "02003" and G.izzie and G.izzie.owner == inv then t.mental = t.mental + 1 ; t.izzie = true end
      trauma[inv.id] = t
      xp[inv.id] = xpv + outcome.xp_bonus
    end
    local dmgRound, horRound = {}, {}
    return {
      scenario = G.name, seed = G.seed, players = n, party = party, ended = e.reason, resolution = res, round = e.round,
      victory = vic, xp_victory = xpv, xp = xp, log = outcome.log, tokens_added = outcome.tokens, cards_earned = outcome.cards,
      trauma = trauma, cheated = G.cheated == true, agenda_reached = G.agenda.i, act_reached = G.acts.Main and G.acts.Main.id,
      doom_in_play = R.doomInPlay(), resigned = m.resigned, camp = { otherDone = G.camp.otherDone, order = G.camp.order,
      tokens = G.camp.tokens, first = G.camp.firstResult, armitage = G.camp.armitage, log = G.camp.log },
      shadow_resources = G.shadow and G.shadow.res or nil, goal1a = G.scen == "1a" and G.goal1a or nil,
      metrics = m, trace = G.trace, table_notes = T.errors, lua_errors = {},
    }
  end

  local function snap(label) if cfg.snapshots and H.snapDir then H.snapshot(label) end end

  local function play(key, seed, camp)
    local G, errMark = newGame(key, seed, camp)
    snap(key .. ": setup done")
    local ok, err = xpcall(function()
      G.round = 1
      while G.round <= (cfg.maxRounds or 30) do
        if G.round > 1 then R.mythos() end
        R.investigation()
        R.enemyPhase()
        R.upkeep()
        G.metrics.curve[#G.metrics.curve + 1] = { round = G.round, doom = R.doomInPlay(), agenda = G.agenda.i,
          act = G.acts.Main and G.acts.Main.id, clues = R.partyClues() }
        G.round = G.round + 1
      end
    end, function(e) if type(e) == "table" then return e end return debug.traceback(tostring(e), 2) end)
    local engineError
    if not ok and not (type(err) == "table" and err.loopEnded) then engineError = tostring(err) end
    snap(key .. ": the game ends (" .. tostring(G.resolution) .. ")")
    local out = finish(G)
    if engineError then out.engine_error = engineError end
    for i = errMark + 1, #E.errors do
      local e = E.errors[i]
      out.lua_errors[#out.lua_errors + 1] = string.format("%s: %s", tostring(e.where), tostring(e.msg))
    end
    return out, G
  end

  ------------------------------------------------------------ campaign order --

  --- Between two scenarios: the log, chaos tokens, trauma, earned allies and XP spent on upgrades. prev is the
  -- campaign state the scenario just played started from (nil for the first one): it accumulates.
  local function between(first, G1, order, prev, bonusXp)
    local camp = { otherDone = true, order = order, tokens = {}, trauma = {}, decks = {}, weakness = {},
                   firstResult = prev and prev.firstResult or first.resolution, xpLeft = {}, stepAt = {}, log = {} }
    for _, t in ipairs(prev and prev.tokens or {}) do camp.tokens[#camp.tokens + 1] = t end
    for _, t in ipairs(first.tokens_added or {}) do camp.tokens[#camp.tokens + 1] = TOKEN_ID[t] or t end
    for _, e in ipairs(prev and prev.log or {}) do camp.log[#camp.log + 1] = e end
    for _, e in ipairs(first.log or {}) do camp.log[#camp.log + 1] = e end
    for _, inv in ipairs(G1.inv) do
      local pt = prev and prev.trauma[inv.id] or { physical = 0, mental = 0 }
      camp.trauma[inv.id] = { physical = pt.physical + first.trauma[inv.id].physical, mental = pt.mental + first.trauma[inv.id].mental }
      camp.weakness[inv.id] = G1.wk[inv.id]
      local dk = copy(prev and prev.decks[inv.id] or decks.decks[inv.id])
      -- XP: the upgrade path of the same-class Still Hour deck, bought in order while the XP lasts
      local xpLeft = (prev and prev.xpLeft[inv.id] or 0) + (first.xp[inv.id] or 0) + (bonusXp or 0)
      local bought = {}
      local steps = (decks.upgrade_steps or {})[inv.id] or {}
      local at = prev and prev.stepAt[inv.id] or 1
      while steps[at] do
        local step = steps[at]
        if xpLeft < step.cost then break end
        local idx = {}
        for j, c in ipairs(dk.cards) do if c.name == step.from or c.full == step.from then idx[#idx + 1] = j end end
        if step.card.permanent or #idx >= step.copies then
          for j = 1, step.copies do
            if step.card.permanent then dk.cards[#dk.cards + 1] = copy(step.card) else dk.cards[idx[j]] = copy(step.card) end
          end
          xpLeft = xpLeft - step.cost
          bought[#bought + 1] = step.card.full or step.card.name
        end
        at = at + 1
      end
      camp.decks[inv.id], camp.xpLeft[inv.id], camp.stepAt[inv.id] = dk, xpLeft, at
      first.upgrades = first.upgrades or {}
      first.upgrades[inv.id] = bought
    end
    -- an earned ally joins one investigator's deck (does not count toward deck size)
    for _, cid in ipairs(first.cards_earned or {}) do
      local who = (cid == FX.ID.rice) and (party[2] or party[1]) or party[1]
      FX.addToDeck(camp.decks[who], cid)
      first.ally_to = first.ally_to or {}
      first.ally_to[cid] = who
    end
    return camp
  end
  function FX.addToDeck(dk, cid)
    local c = R.card(cid)
    dk.cards[#dk.cards + 1] = { name = c.name, id = cid, sced = cid, type = "Asset", cost = c.cost, slot = c.slot,
      traits = c.traits, icons = { wil = c.wilIcons or 0, int = c.intIcons or 0, com = c.comIcons or 0,
      agi = c.agiIcons or 0, wild = c.wildIcons or 0 } }
  end

  --- Armitage's Fate (the interlude after 1a and 1b), from the guide data: kidnapped if the log holds
  -- "unconscious for several hours" (each investigator earns 2 bonus XP), else rescued (he joins a deck).
  local function armitagesFate(firstLog, secondLog)
    local out = false
    for _, list in ipairs({ firstLog or {}, secondLog or {} }) do
      for _, e in ipairs(list) do if e == "unconscious_for_several_hours" then out = true end end
    end
    return out
  end

  local total = 0
  for _, job in ipairs(cfg.jobs) do
    for r = 1, job.runs do
      local seed = job.seed + r - 1
      local t0 = os.clock()
      if job.scenario == "1a" or job.scenario == "1b" or job.scenario == "2" then
        local out = play(job.scenario, seed, { otherDone = false, tokens = {} })
        out.cpu = os.clock() - t0
        total = total + 1
        emit("GAME", out)
      else
        -- a campaign-order pair: "ab" (1a then 1b) or "ba"
        local order = job.scenario == "pair_ba" and { "1b", "1a" } or { "1a", "1b" }
        local first, G1 = play(order[1], seed * 10 + 1, { otherDone = false, tokens = {}, order = job.scenario })
        local camp = between(first, G1, job.scenario)
        local second, G2 = play(order[2], seed * 10 + 2, camp)
        first.pair, first.slot, second.pair, second.slot = job.scenario, 1, job.scenario, 2
        first.pair_seed, second.pair_seed = seed, seed
        first.cpu = os.clock() - t0
        local camp2, kidnapped
        if job.scenario == "trio_ab" then
          kidnapped = armitagesFate(first.log, second.log)
          camp2 = between(second, G2, job.scenario, camp, kidnapped and 2 or 0)
          second.armitage = kidnapped and "kidnapped" or "rescued"
        end
        emit("GAME", first)
        emit("GAME", second)
        total = total + 2
        if job.scenario == "trio_ab" then
          -- Armitage's Fate, then The Miskatonic Museum with everything the pair left behind
          local t1 = os.clock()
          camp2.armitage = kidnapped and "kidnapped" or "rescued"
          camp2.log[#camp2.log + 1] = kidnapped and "henry_armitage_kidnapped" or "henry_armitage_rescued"
          if not kidnapped then
            -- he joins the deck of the first investigator who was not given Rice or Morgan
            local taken = {}
            for _, r in ipairs({ first, second }) do for _, who in pairs(r.ally_to or {}) do taken[who] = true end end
            local who = party[1]
            for i = #party, 1, -1 do if not taken[party[i]] then who = party[i] end end
            FX.addToDeck(camp2.decks[who], FX.ID.armitage)
            camp2.armitage_to = who
          end
          local third = play("2", seed * 10 + 3, camp2)
          third.pair, third.slot, third.pair_seed = job.scenario, 3, seed
          third.cpu = os.clock() - t1
          emit("GAME", third)
          total = total + 1
        end
      end
    end
  end
  H.check("the Dunwich engine played " .. total .. " game(s)", total > 0)
end
