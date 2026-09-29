-- The play engine (designer tooling): plays The Still Hour's scenarios on the
-- emulated SCED table, many times, and reports what happened.
--
-- Runs as a suite of the headless harness (tests/sced_real/run.lua
-- --suite-file tools/play_engine/lua/engine.lua --config <json>); started by
-- tools/play_engine/run.py. The table is booted once; each game restores the
-- campaign state on the Control token, clears the board and Places the boxes,
-- then plays rounds until the loop ends. One "@@GAME <json>" line per game.

return function(H)
  local E, J = H.E, H.E.J
  local here = (H.args["suite-file"] or ""):match("^(.*)[/\\]") or (H.ROOT .. "/tools/play_engine/lua")
  local T = dofile(here .. "/tablekit.lua")
  T.init(H)
  local R = {}
  dofile(here .. "/rules.lua")(R, T)
  dofile(here .. "/effects.lua")(R, T)
  dofile(here .. "/players.lua")(R, T)
  dofile(here .. "/flow.lua")(R, T)
  dofile(here .. "/ai.lua")(R, T)
  dofile(here .. "/finale.lua")(R, T)
  local S = dofile(here .. "/scenarios.lua")(R, T)

  local cfg = J.decode(H.readFile(H.args.config))
  local cards = J.decode(H.readFile(cfg.cards))
  R.CARDS = cards.cards
  local decks = J.decode(H.readFile(cfg.decks))
  R.CONTEST_PER_INV = cfg.contestPerInv
  R.FINALE_SPAWN_AT = cfg.finaleSpawnAt
  -- what-if runs: scenario fields replaced (e.g. the finale's log choices)
  for name, patch in pairs(cfg.scenarioPatch or {}) do
    if S[name] then for k, v in pairs(patch) do S[name][k] = v end end
  end
  -- what-if runs (run.py --what-if): card numbers and act terms changed for this run only
  for id, fields in pairs(cfg.cardOverrides or {}) do
    R.CARDS[id] = R.CARDS[id] or {}
    for k, v in pairs(fields) do R.CARDS[id][k] = v end
  end
  for id, fields in pairs(cfg.actOverrides or {}) do
    R.FX.ACTS[id] = R.FX.ACTS[id] or {}
    for k, v in pairs(fields) do R.FX.ACTS[id][k] = v end
  end

  local function emit(tag, t) io.write("@@", tag, " ", J.encode(t), "\n") io.flush() end

  ------------------------------------------------------------ coverage --

  do
    local missing = {}
    for _, id in ipairs(cards.scenario_ids) do
      if not R.FX.COVERAGE[id] then missing[#missing + 1] = id end
    end
    local approx = {}
    for id, how in pairs(R.FX.COVERAGE) do if how ~= "full" then approx[#approx + 1] = { id = id, how = how } end end
    for name, how in pairs(R.P.APPROX) do approx[#approx + 1] = { id = name, how = how } end
    table.sort(approx, function(a, b) return a.id < b.id end)
    emit("COVERAGE", { missing = missing, approx = approx, scenario_cards = #cards.scenario_ids })
  end

  ------------------------------------------------------------ the table --

  local payload = J.decode(H.readFile(H.ROOT .. "/dist/saved_object_the_still_hour.json"))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")
  E.run(2)
  T.click(campaignBox, "Place")
  E.run(4)
  T.difficulty(cfg.difficulty or "Standard")

  local party = cfg.party
  local n = #party
  T.setInvestigators(n)

  -- seat the investigators on SCED playmats (card from the campaign's player-card bag)
  local seats = {}
  local pbag = T.find(function(o) return o.type == "Bag" and o.hasTag("StillHour") and tostring(o.getName()):find("Player Cards", 1, true) ~= nil end)
  for i, id in ipairs(party) do
    local color = T.MATS[i]
    local guid
    for _, e in ipairs(pbag.getObjects()) do if (T.decode(e.gm_notes) or {}).id == id then guid = e.guid end end
    local mat = T.mat(color)
    local pos = mat.positionToWorld({ -1.17, 0.1, -0.01 })
    local card = pbag.takeObject({ guid = guid, position = { pos.x, pos.y + 1, pos.z }, smooth = false })
    E.run(0.5)
    E.drop(card, { pos.x, pos.y + 0.5, pos.z }, color)
    seats[i] = { id = id, color = color, card = card }
  end
  E.run(3)
  local baseline = T.decode(T.api("shApiSnapshot"))
  H.info("engine: table ready, party " .. table.concat(party, ", "))

  ------------------------------------------------------------ state --

  local function freshMetrics()
    return {
      dissonance_sources = {}, hour_sources = {}, memory_on_cards = {}, damage = 0, horror = 0, defeats = 0, defeated = {},
      diss_max = 0, clues = 0, clues_spent = 0, clues_by_round = {}, spawns = {}, bad_spawns = {}, drawn = {}, encounters = 0,
      reshuffles = 0, draw_failures = 0, enemies_defeated = 0, defeated_by_id = {}, victory = {}, acts_completed = {},
      knowledge = {}, curve = {}, hour_round = {}, tests = 0, tests_passed = 0, tokens = {}, actions = {}, moves = 0,
      crossings = 0, crossing_hours = 0, rewinds = 0, holdbacks = 0, holdback_attempts = 0, attacks = 0, aoo = 0,
      appointed_attacks = 0, appointed_hunts = 0, appointed_engagements = 0, stage_max = 0, cards_played = 0,
      weaknesses_drawn = 0, card_years = 0, cancelled_hours = {}, cancelled_advances = 0, cancelled_treacheries = 0,
      itmeanswait = 0, evades = 0, enemy_moves = 0, contest_sources = {}, approach_by_card = 0,
      damage_by = {}, horror_by = {}, defeated_by = {}, defeated_who = {},
    }
  end

  --- The Control token's campaign state for this scenario (Loop Setup: the
  -- Hour at I, Dissonance at the scar, the Appointed Unseen).
  local function campaignFor(sc)
    local blob = T.decode(J.encode(baseline))
    local c = blob.campaign
    local consts = R.consts and nil
    c.investigators = n
    c.prologue = sc.prologue == true
    c.loopsCompleted = sc.loops or 0
    local reset = (n == 1) and 9 or 6 * n
    c.dissonance = math.min(sc.loops or 0, math.floor(reset / 3))
    c.hourglass = 1
    c.knowledge = {}
    c.knowledgePaid = {}
    for _, f in ipairs(sc.knowledge or {}) do c.knowledge[f] = true ; c.knowledgePaid[f] = 0 end
    c.partTwo = sc.part == 2
    c.bankedMemory = sc.banked or 0
    c.years, c.brackets, c.onCardMemory, c.loopTallies, c.pendingYears = {}, {}, {}, {}, {}
    for _, id in ipairs(party) do
      c.years[id] = sc.years or 0
      if (sc.years or 0) >= 5 then
        local d = S.DRIFT[id]
        local br = (sc.years >= 15 and "Ancient") or (sc.years >= 10 and "Elder") or "Weathered"
        c.brackets[id] = { bracket = br, physical = d[1], mental = d[2] }
      end
    end
    c.appointedStage = 0
    c.oncePerLoopFlags = {}
    if sc.part == 2 and c.knowledge["what-the-almanac-hid"] and c.knowledge["the-vote-that-never-ends"]
       and not c.knowledge["the-appointeds-name"] then
      c.oncePerLoopFlags["almanac-act2a-current"] = true
    end
    c.victoryLog = {}
    c.loopEnded = false
    c.finale = false
    c.contest = 0
    c.testTypesThisLoop, c.testTypesLastLoop = {}, {}
    c.lastLoopEndDissonance, c.lastLoopEndedInDanger = nil, nil
    blob.bag = { baseline = 0, extra = 0, almanac = false, out = {} }
    blob.aging = {}
    return blob
  end

  ------------------------------------------------------------ setup --

  local AWAY = { x = -60, y = 2, z = 0 }

  local function cleanTable()
    -- engine-made objects from the last game: weakness enemies, clue tokens on mats
    for _, o in ipairs(T.findAll(function(o) return o.getVar and o.memo == "clueDoom" end)) do
      local p = o.getPosition()
      if p.x < -46 or p.z > 18 or p.z < -18 then o.destruct() end
    end
    for _, o in ipairs(T.findAll(function(o) return o.type == "Card" and tostring((T.gm(o)).id or ""):sub(1, 9) == "weakness:" end)) do
      o.destruct()
    end
    T.returnTokens()
    E.run(0.2)
  end

  local function setupAct(box, district, sc, G)
    local deck = T.deckNamed("Act Deck", box)
    if not deck then return end
    local ids = {}
    if deck.type == "Deck" then
      for _, e in ipairs(deck.getObjects()) do ids[#ids + 1] = (T.decode(e.gm_notes) or {}).id end
    else
      ids = { T.gm(deck).id }
    end
    -- the face-up deck shows its last entry: act 1a on top, 2a under it
    local a1, a2 = ids[#ids], ids[1]
    local pos = deck.getPosition()
    local deep, surf = S.DEEP[district], S.SURF[district]
    local function remove()
      G.removedDecks = (G.removedDecks or 0) + 1
      deck.setPosition({ AWAY.x, AWAY.y, AWAY.z - 6 - 4 * G.removedDecks })
    end
    if G.knowledge[deep] then remove() return end
    if G.knowledge[surf] then
      if sc.part ~= 2 then remove() return end
      if not R.FX.actTwoRequirements(a2) then remove() return end
      -- act 1a leaves the game; act 2a is current
      local c1 = T.takeCard(a1, { pos.x + 2.7, pos.y + 0.3, pos.z }, { 0, 180, 180 })
      G.acts[district] = { id = a2, district = district, pos = pos }
      G.actOrder[#G.actOrder + 1] = district
      G.pendingCurrent[#G.pendingCurrent + 1] = G.acts[district]
      return
    end
    G.acts[district] = { id = a1, district = district, pos = pos, next = a2 }
    G.actOrder[#G.actOrder + 1] = district
  end

  local function placementChecks(G, boxes)
    local m = G.metrics
    m.placement = { overlaps = {}, outside = {}, lonely = {}, missing_links = {} }
    local cardsOut = {}
    for _, b in ipairs(boxes) do
      for _, o in ipairs(T.placedBy(b)) do if o.type == "Card" or o.type == "Deck" then cardsOut[#cardsOut + 1] = o end end
    end
    for i = 1, #cardsOut do
      for j = i + 1, #cardsOut do
        local a, b = E.aabb(cardsOut[i]), E.aabb(cardsOut[j])
        local pad = 0.15
        if a.min.x + pad < b.max.x and a.max.x - pad > b.min.x and a.min.z + pad < b.max.z and a.max.z - pad > b.min.z then
          m.placement.overlaps[#m.placement.overlaps + 1] = cardsOut[i].getName() .. " / " .. cardsOut[j].getName()
        end
      end
    end
    for _, L in ipairs(G.locList) do
      if T.inPlayArea(L.obj) == false then m.placement.outside[#m.placement.outside + 1] = L.name end
      if not L.closed and R.count(L.adj) == 0 then m.placement.lonely[#m.placement.lonely + 1] = L.name end
    end
    -- the guide's district connections must resolve on the table
    local LINKS = { { "sthr-loc-hubsquare", "sthr-loc-nave" }, { "sthr-loc-hubsquare", "sthr-loc-milestones" },
                    { "sthr-loc-hubsquare", "sthr-loc-ticketbooth" }, { "sthr-loc-hubsquare", "sthr-loc-readingroom" },
                    { "sthr-loc-turning", "sthr-loc-windingstair" } }
    for _, l in ipairs(LINKS) do
      local a, b = R.locById(l[1]), R.locById(l[2])
      if a and b and not a.adj[b.guid] then
        m.placement.missing_links[#m.placement.missing_links + 1] = a.name .. " - " .. b.name
      end
    end
  end

  local function newGame(scName, seed)
    local sc = S[scName]
    E.seed(seed)
    math.randomseed(seed)
    local G = {
      cfg = sc, name = scName, seed = seed, n = n, round = 0, phase = "setup", clock = 0,
      inv = {}, locs = {}, locList = {}, enemies = {}, acts = {}, actOrder = {}, pendingCurrent = {},
      hoursAside = {}, tempStatic = {}, risingWater = {}, inkRuns = {}, crossedThisRound = {}, group = {},
      roundGroup = {}, enteredThisTurn = {}, studyVisited = {}, appointed = {}, knowledge = {}, logFlags = {},
      metrics = freshMetrics(), trace = cfg.trace and {} or nil, live = cfg.live, prologue = sc.prologue == true, partTwo = sc.part == 2,
      loopsCompleted = sc.loops or 0, contest = 0, finale = false,
    }
    R.G = G
    for _, f in ipairs(sc.knowledge or {}) do G.knowledge[f] = true end
    for k, v in pairs(sc.logFlags or {}) do G.logFlags[k] = v end
    T.errors = {}
    local errMark = #E.errors

    cleanTable()
    T.api("shApiRestore", { blob = J.encode(campaignFor(sc)) })
    E.run(0.5)
    -- the campaign log shows the same entries
    local vals = T.logValues()
    for k, v in pairs(vals) do
      if (k:sub(1, 2) == "k:" or k:sub(1, 2) == "v:" or k:sub(1, 3) == "vb:") and v == true then T.setLog(k, false) end
    end
    for _, f in ipairs(sc.knowledge or {}) do T.setLog("k:" .. f, true) end
    T.ctl("Clear Board")
    E.run(1)

    -- Loop Setup: Place the boxes
    local boxes = {}
    for _, id in ipairs(sc.boxes) do
      local b = T.placeBox(id)
      if b then boxes[#boxes + 1] = b end
    end
    E.run(3)
    R.touch()
    G.agendaPos = T.mythosSpot("agenda")
    R.scanLocations()
    placementChecks(G, boxes)

    -- the encounter deck: the district sets shuffled in (Loop Setup step 5)
    local main = T.encounterDeck()
    for i = 2, #boxes do
      local set = T.deckNamed("Encounter Deck", boxes[i])
      if set and main then E.playerPut(main, set) E.run(0.2) end
    end
    local sq = T.scenarioBox("district_square")
    local aside = sq and T.deckNamed("Set Aside", sq)
    if sc.part == 2 and aside then
      -- Part II: the Appointed's Whispers join the encounter deck
      local ids = {}
      if aside.type == "Deck" then
        for _, e in ipairs(aside.getObjects()) do
          if (T.decode(e.gm_notes) or {}).id == "sthr-appointedwhisper" then ids[#ids + 1] = e.guid end
        end
      end
      for _, g in ipairs(ids) do
        local src = T.deckNamed("Set Aside", sq)
        if src and src.type == "Deck" then
          local p = src.getPosition()
          local w = src.takeObject({ guid = g, position = { p.x, p.y + 2, p.z }, smooth = false })
          E.run(0.1)
          if w then T.shuffleIntoEncounter(w) end
        end
      end
      -- the Fairground's Named enemy is shuffled in with its set
      for _, b in ipairs(boxes) do
        if T.gm(b).id == "district_fairground" then
          local rides = T.find(function(o) return o.type == "Card" and o.hasTag(T.boxTag(b)) and T.gm(o).id == "sthr-onewhorides" end)
          if rides then T.shuffleIntoEncounter(rides) end
        end
      end
    end
    main = T.encounterDeck()
    if main and main.type == "Deck" then main.shuffle() end
    G.metrics.deck_size = T.deckCount(main)
    -- the Appointed's Approach beside the Hours (not in the Prologue)
    if not sc.prologue then
      local ap = T.takeCard("sthr-appointed-approach")
      if ap then
        -- the mythos mat's story card spot, clear of the decks
        local p = E.byGuid("9f334f").positionToWorld({ -2.2, 0.1, 0.37 })
        ap.setPosition({ p.x, p.y + 0.2, p.z })
        ap.setRotation({ 0, 270, 0 })
      end
    end
    -- the Hours: an Hour a Knowledge entry removed leaves the deck
    if G.knowledge["the-hour-was-wrong"] then
      local h4 = T.find(function(o) return o.type == "Deck" and T.dist(o.getPosition(), G.agendaPos) < 0.8 end)
      if h4 then
        for _, e in ipairs(h4.getObjects()) do
          if tostring(e.name or ""):sub(1, 7) == "Hour IV" then
            h4.takeObject({ guid = e.guid, position = { AWAY.x, AWAY.y, AWAY.z + 6 }, smooth = false })
          end
        end
      end
    end
    -- act decks
    for _, b in ipairs(boxes) do
      local id = T.gm(b).id
      if id == "prologue" then
        G.acts.Prologue = { id = "sthr-act-firsthour", district = "Prologue", pos = T.mythosSpot("act") }
        G.actOrder[#G.actOrder + 1] = "Prologue"
      elseif S.BOX_DISTRICT[id] then
        setupAct(b, S.BOX_DISTRICT[id], sc, G)
      end
    end
    R.scanLocations()

    -- investigators at the Square
    local start = R.locById("sthr-loc-hubsquare") or R.locById("sthr-loc-square")
    local invStats = {}
    for _, x in ipairs(T.api("shApiInvestigators") or {}) do invStats[x.id] = x.stats end
    for i, s in ipairs(seats) do
      local w = R.pick(decks.weaknesses)
      local mini = T.minicard(s.id)
      local inv = R.P.newInvestigator(i, s.id, s.color, s.card, mini, invStats[s.id], decks.decks[s.id], w)
      inv.bracket = (sc.years or 0) >= 15 and "Ancient" or (sc.years or 0) >= 10 and "Elder" or (sc.years or 0) >= 5 and "Weathered" or "Prime"
      inv.loc = start.guid
      if mini then T.moveMini(mini, start.obj, i) end
      G.inv[i] = inv
      G.metrics.weakness = G.metrics.weakness or {}
      G.metrics.weakness[s.id] = w and w.name
    end
    E.run(1)
    -- Elder and Ancient investigators begin each loop with 1 Memory
    for _, inv in ipairs(G.inv) do
      if inv.bracket == "Elder" or inv.bracket == "Ancient" then R.addMemory(inv, 1, "Elder: begins the loop with 1 Memory") end
    end
    G.metrics.start = { dissonance = R.dissonance(), hour = R.hour(), memory = R.state().memory }
    -- Part II acts that are current from the start resolve "When this act becomes the current act"
    for _, act in ipairs(G.pendingCurrent) do R.FX.actBecomesCurrent(act) end
    return G, errMark
  end

  ------------------------------------------------------------ the loop's end --

  local function districtResolution(G, district)
    local done1, done2 = false, false
    for _, a in ipairs(G.metrics.acts_completed) do
      local spec = R.FX.ACTS[a.id] or {}
      if spec.fact == S.DEEP[district] then done2 = true end
      if spec.fact == S.SURF[district] then done1 = true end
    end
    if done2 then return "R1" end
    if done1 then return "R2" end
    if G.knowledge[S.DEEP[district]] or G.knowledge[S.SURF[district]] then return "R3" end
    return "NR"
  end

  local function finish(G)
    local m = G.metrics
    local e = G.ended or { reason = "unfinished", round = G.round }
    -- Victory: each Victory X location in play, revealed, with no clues
    for _, L in ipairs(G.locList) do
      if (L.def.victory or 0) > 0 and L.revealed and not L.closed and T.alive(L.obj) and R.clues(L) == 0 then
        m.victory[#m.victory + 1] = L.id
        T.tickLog("v:" .. L.id, true)
      end
    end
    local res
    if G.prologue then
      if e.reason == "act" then res = "R1" elseif e.reason == "defeat" then res = "NR" else res = "R2" end
      local mem = 2 * n + (res == "R1" and 1 or 0)
      for _ = 1, mem do T.ctl("Memory") end
    elseif G.finale then
      res = R.finaleResolution()
    else
      if e.reason == "reset" then res = "R2" elseif e.reason == "defeat" then res = "NR" else res = "R1" end
    end
    local districts = {}
    for _, d in ipairs(G.actOrderAll or G.actOrder) do if d ~= "Prologue" then districts[d] = districtResolution(G, d) end end
    for _, id in ipairs(G.cfg.boxes) do
      local d = S.BOX_DISTRICT[id]
      if d and d ~= "Prologue" and not districts[d] then districts[d] = districtResolution(G, d) end
    end
    -- Reset Loop, then the Interlude: Age (who was defeated) and bank on-card Memory
    local st0 = T.st()
    local onCard = 0
    for _, inv in ipairs(G.inv) do onCard = onCard + (inv.memory or 0) end
    T.ctl("Reset Loop")
    E.run(0.5)
    local years = {}
    if not G.prologue then
      T.api("shApiInterlude", { open = true })
      for _, inv in ipairs(G.inv) do
        local r = T.api("shApiAge", { id = inv.id, defeated = m.defeated[inv.id] == true })
        years[inv.id] = r and r.gained or 0
      end
    end
    local banked = T.api("shApiBankOnCard") or 0
    T.api("shApiInterlude", { open = false })
    local st1 = T.st()
    local out = {
      scenario = G.name, seed = G.seed, players = n, party = party,
      ended = e.reason, resolution = res, districts = districts, round = e.round, hour = e.hour,
      dissonance_end = e.dissonance, band_end = st0.band, stage_max = m.stage_max,
      acts = m.acts_completed, knowledge = m.knowledge, contest = G.contest,
      memory_on_cards = onCard, memory_banked_on_cards = banked, memory_bank_start = m.start.memory,
      memory_bank_end = st1.memory, years = years, card_years = m.card_years,
      metrics = m, trace = G.trace, table_notes = T.errors,
      lua_errors = {},
    }
    return out
  end

  ------------------------------------------------------------ play --

  -- table snapshots for tools/godot_table (run.py --render)
  local function snap(label)
    if cfg.snapshots and H.snapDir then H.snapshot(label) end
  end

  local function play(scName, seed)
    local G, errMark = newGame(scName, seed)
    snap(scName .. ": Loop Setup done")
    local ok, err = xpcall(function()
      G.round = 1
      while G.round <= (cfg.maxRounds or 30) do
        if G.round > 1 then R.mythos() ; snap(scName .. ": round " .. G.round .. " after the Mythos phase") end
        R.investigation()
        snap(scName .. ": round " .. G.round .. " after the Investigation phase")
        R.enemyPhase()
        R.upkeep()
        G.metrics.curve[#G.metrics.curve + 1] = { round = G.round, hour = R.hour(), diss = R.dissonance(), stage = R.stage(),
                                                  clues = R.partyClues(), phase = "end" }
        G.round = G.round + 1
      end
    end, function(e) if type(e) == "table" then return e end return debug.traceback(tostring(e), 2) end)
    local engineError = nil
    if not ok and not (type(err) == "table" and err.loopEnded) then engineError = tostring(err) end
    snap(scName .. ": the loop ends (" .. tostring(G.ended and G.ended.reason) .. ")")
    local out = finish(G)
    if engineError then out.engine_error = engineError end
    for i = errMark + 1, #E.errors do
      local e = E.errors[i]
      out.lua_errors[#out.lua_errors + 1] = string.format("%s: %s", tostring(e.where), tostring(e.msg))
    end
    return out
  end

  local total = 0
  for _, job in ipairs(cfg.jobs) do
    for r = 1, job.runs do
      local seed = job.seed + r - 1
      local t0 = os.clock()
      local out = play(job.scenario, seed)
      out.cpu = os.clock() - t0
      total = total + 1
      emit("GAME", out)
      if H.args.snapshots and cfg.snapshotGame then H.snapshot("end of " .. job.scenario) end
    end
  end
  H.check("the play engine played " .. total .. " game(s)", total > 0)
end
