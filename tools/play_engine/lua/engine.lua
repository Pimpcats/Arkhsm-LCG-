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
  R.WHATIF = cfg
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

  -- the candidate Saved Object (dist/'s, with the Control's and the log's
  -- scripts rebuilt from src/) when run.py made one, else dist/'s
  local payload = J.decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
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
      itmeanswait = 0, evades = 0, enemy_moves = 0, contest_sources = {}, approach_by_card = 0, doom_sources = {},
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
    local scarCap = (n == 1) and 4 or 2 * n     -- Constants.forCount scarCap
    c.dissonance = math.min(sc.loops or 0, scarCap)
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
    -- personal quest cards: a representative night from the third on (loops >= 2)
    -- has every quest met; earlier nights are still on their tallies
    c.quest = {}
    if (sc.loops or 0) >= ((cfg.questUnlockLoop) or 2) then
      for _, id in ipairs(party) do c.quest[id] = { tally = 99, unlocked = true } end
    end
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

  local carried, campaignDecks, campaignWeaknesses, campaignFlags, upgradeAt, recollectionAt

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
    -- Place's loop setup (control.lua setUpPlacedBox) has already removed a finished act deck and, when act
    -- 2a is current, act 1a; what is left on the table says which act is current
    local deck = T.deckNamed("Act Deck", box)
    if not deck then
      -- act 2a alone is left (the setup took act 1a): a loose card that no longer carries the deck's name
      local DEEP_ACT = { Square = "sthr-act-vote", Church = "sthr-act-hourwaswrong", Road = "sthr-act-walksbeside",
                         Lighthouse = "sthr-act-ninthdeath", Fairground = "sthr-act-bargain", Almanac = "sthr-act-appointedname" }
      local id2 = DEEP_ACT[district]
      local c2 = id2 and T.find(function(o) return o.type == "Card" and T.gm(o).id == id2 and o.hasTag(T.boxTag(box)) end)
      if not c2 then return end
      deck = c2
    end
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
      -- act 1a leaves the game (Place's setup already took it when only act 2a is left); act 2a is current
      if #ids > 1 then T.takeCard(a1, { pos.x + 2.7, pos.y + 0.3, pos.z }, { 0, 180, 180 }) end
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
    local restored = carried and T.decode(J.encode(carried)) or campaignFor(sc)
    if carried then restored.campaign.onCardMemory = {} end -- re-created on actual card sources below
    T.api("shApiRestore", { blob = J.encode(restored) })
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
    -- what-if: fewer copies of an encounter card ({id = copies to remove})
    for id, k in pairs((R.WHATIF or {}).removeFromEncounter or {}) do
      for _ = 1, k do
        local d = T.encounterDeck()
        if d and d.type == "Deck" then
          for _, e in ipairs(d.getObjects()) do
            if (T.decode(e.gm_notes) or {}).id == id then
              local p = d.getPosition()
              local c = d.takeObject({ guid = e.guid, position = { p.x + 40, p.y + 2, p.z }, smooth = false })
              E.run(0.1)
              if c then c.destruct() end
              break
            end
          end
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
    local invQuest = {}
    for _, x in ipairs(T.api("shApiInvestigators") or {}) do
      invStats[x.id] = x.stats
      invQuest[x.id] = { tally = x.quest or 0, unlocked = x.questUnlocked == true }
    end
    for i, s in ipairs(seats) do
      local w = campaignWeaknesses and campaignWeaknesses[s.id] or R.pick(decks.weaknesses)
      local mini = T.minicard(s.id)
      -- later nights play the XP deck of that night (decks.py TIERS: n2, n3, n4, n6, fin)
      local deck = campaignDecks and campaignDecks[s.id] or (sc.xp and decks.tiers and decks.tiers[sc.xp] and decks.tiers[sc.xp][s.id]) or decks.decks[s.id]
      local inv = R.P.newInvestigator(i, s.id, s.color, s.card, mini, invStats[s.id], deck, w)
      inv.questTally, inv.questUnlocked = (invQuest[s.id] or {}).tally or 0, (invQuest[s.id] or {}).unlocked == true
      inv.years = (restored.campaign.years or {})[s.id] or sc.years or 0
      inv.bracket = inv.years >= 15 and "Ancient" or inv.years >= 10 and "Elder" or inv.years >= 5 and "Weathered" or "Prime"
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
      if R.P.findAsset(inv, "Anchor Point") then R.addMemory(inv, 1, "Anchor Point: begins the loop with 1 Memory") end
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
      T.tickLog("k:you-are-unstuck", true) -- every Prologue resolution records it
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
    -- Ordinary loops use the interlude. The finale's outcome is classified
    -- above; its ending/epilogue must be read from the guide. It must not
    -- silently receive an ordinary loop's reset, aging or Memory banking.
    local st0 = T.st()
    local onCard = 0
    for _, inv in ipairs(G.inv) do onCard = onCard + (inv.memory or 0) end
    local years = {}
    local banked = 0
    if not G.finale then
      T.ctl("Reset Loop")
      E.run(0.5)
      -- a night that ended by its objective (not by the Hourglass or Dissonance) is not over by the Control's
      -- count: the first click only asks, the second ends it
      if T.st().loopEnded == false then
        T.ctl("Reset Loop")
        E.run(0.5)
      end
      if not G.prologue then
        T.api("shApiInterlude", { open = true })
        for _, inv in ipairs(G.inv) do
          local r = T.api("shApiAge", { id = inv.id, defeated = m.defeated[inv.id] == true })
          years[inv.id] = r and r.gained or 0
        end
      end
      banked = T.api("shApiBankOnCard") or 0
      T.api("shApiInterlude", { open = false })
    end
    local st1 = T.st()
    local out = {
      scenario = G.name, seed = G.seed, players = n, party = party,
      ended = e.reason, resolution = res, districts = districts, round = e.round, hour = e.hour,
      finale_aftermath = G.finale and "not simulated; resolve the ending and epilogue in the guide" or nil,
      dissonance_end = e.dissonance, band_end = st0.band, stage_max = m.stage_max,
      acts = m.acts_completed, knowledge = m.knowledge, contest = G.contest,
      goals = G.cfg.goals or G.cfg.objectives,
      memory_on_cards = onCard, memory_banked_on_cards = banked, memory_bank_start = m.start.memory,
      memory_bank_end = st1.memory, years = years, card_years = m.card_years,
      campaign_state = cfg.campaign and T.decode(T.api("shApiSnapshot")) or nil,
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
  -- A campaign keeps the actual log, paid Knowledge/Victory, scar, Years,
  -- remaining bank, purchased deck and original basic weakness. Its route
  -- rotates districts; it never injects unearned finale requirements.
  local SURFACE_ACT={Square="sthr-act-sheriffdead",Church="sthr-act-whythirteen",Road="sthr-act-walkbackward",
    Lighthouse="sthr-act-lamp",Fairground="sthr-act-wheelturns",Almanac="sthr-act-almanachid"}
  local DEEP_ACT={Square="sthr-act-vote",Church="sthr-act-hourwaswrong",Road="sthr-act-walksbeside",
    Lighthouse="sthr-act-ninthdeath",Fairground="sthr-act-bargain",Almanac="sthr-act-appointedname"}
  local ROUTE={"Church","Fairground","Almanac","Road","Lighthouse"}
  local BOX={Church="district_church",Fairground="district_fairground",Almanac="district_almanac",Road="district_road",Lighthouse="district_lighthouse"}
  local function purchaseAfter(out)
    local spent, purchases = 0, {}
    T.api("shApiInterlude",{open=true})
    for _,id in ipairs(party) do
      local dk=campaignDecks[id]
      local ri=recollectionAt[id]
      local rid=(decks.recollection_picks[id] or {})[ri]
      local rc=rid and decks.recollections[rid]
      if rc and T.st().memory >= rc.memoryCost then
        local result=T.api("shApiBuy",{recollection=rid})
        if result and result.ok then
          if not rc.permanent then
            local replace
            for j,c in ipairs(dk.cards) do if c.name=="Unexpected Courage" or c.name=="Knife" or c.name=="Emergency Cache" then replace=j break end end
            table.remove(dk.cards,replace or 1)
          end
          dk.cards[#dk.cards+1]=T.decode(J.encode(rc))
          recollectionAt[id]=ri+1
          spent=spent+rc.memoryCost
          purchases[#purchases+1]={investigator=id,id=rid,cost=rc.memoryCost}
        end
      end
      local ui=upgradeAt[id]
      local up=(decks.upgrade_steps[id] or {})[ui]
      if up and T.st().memory >= up.cost then
        local replaced={}
        for j,c in ipairs(dk.cards) do if c.name==up.from or c.full==up.from then replaced[#replaced+1]=j end end
        if up.card.permanent or #replaced >= up.copies then
          for j=1,up.copies do
            local result=T.api("shApiBuy",{level=up.level})
            if not result or not result.ok then error("upgrade preflight/payment disagreement") end
            if up.card.permanent then dk.cards[#dk.cards+1]=T.decode(J.encode(up.card))
            else dk.cards[replaced[j]]=T.decode(J.encode(up.card)) end
          end
          upgradeAt[id]=ui+1
          spent=spent+up.cost
          purchases[#purchases+1]={investigator=id,id=up.card.full or up.card.name,cost=up.cost}
        end
      end
    end
    out.spent, out.purchases=spent,purchases
    local before=T.st().memory
    T.api("shApiBeginNextLoop")
    out.carry_lost=before-T.st().memory
    carried=T.decode(T.api("shApiSnapshot"))
    out.memory_after_spending=T.st().memory
  end
  local function campaignScenario(slot)
    local c=carried.campaign
    local sc={part=c.partTwo and 2 or 1,loops=c.loopsCompleted,knowledge={},logFlags=campaignFlags,
      objectives={},boxes={"district_square"}}
    for fact,v in pairs(c.knowledge) do if v then sc.knowledge[#sc.knowledge+1]=fact end end
    table.sort(sc.knowledge)
    local district=ROUTE[((slot-2)%#ROUTE)+1]
    local districts={district}
    -- what-if districtsPerNight = 2: the party places the next two districts
    -- (in route order) that still have an act to play this Part, so a night's
    -- goal is two district acts plus the Square's current act
    local function pending(d)
      return not c.knowledge[S.SURF[d]] or (c.partTwo and not c.knowledge[S.DEEP[d]])
    end
    local perNight=(cfg.districtsPerNight or 1)
    -- what-if goalsPerNight = N: every night's goal is N acts (the Square's
    -- while it still has one, the rest districts'), as an official scenario's
    -- act deck is about 3 acts however the party gets there
    if cfg.goalsPerNight then
      perNight=math.max(1,cfg.goalsPerNight-(pending("Square") and 1 or 0))
    end
    if perNight>1 then
      districts={}
      local start=((slot-2)*(cfg.goalsPerNight and 1 or perNight))%#ROUTE
      for i=0,#ROUTE-1 do
        local d=ROUTE[((start+i)%#ROUTE)+1]
        if pending(d) and #districts<perNight then districts[#districts+1]=d end
      end
      for i=0,#ROUTE-1 do
        local d=ROUTE[((start+i)%#ROUTE)+1]
        local dup=false
        for _,x in ipairs(districts) do if x==d then dup=true end end
        if #districts<perNight and not dup then districts[#districts+1]=d end
      end
    end
    if slot==10 and c.knowledge["the-way-the-night-breaks"] then
      districts={"Almanac"} ; sc.finaleGoal=true
    end
    local placed={}
    local function add(d)
      if not placed[d] then placed[d]=true ; sc.boxes[#sc.boxes+1]=BOX[d] end
    end
    for _,d in ipairs(districts) do
      if d=="Lighthouse" then add("Road") end
      add(d)
    end
    local goalsFor={"Square"}
    for _,d in ipairs(districts) do goalsFor[#goalsFor+1]=d end
    for _,d in ipairs(goalsFor) do
      if not c.knowledge[S.SURF[d]] then sc.objectives[#sc.objectives+1]=SURFACE_ACT[d]
      elseif c.partTwo and not c.knowledge[S.DEEP[d]] then sc.objectives[#sc.objectives+1]=DEEP_ACT[d] end
    end
    if slot==10 and not sc.finaleGoal then sc.finaleUnavailable=true end
    return sc
  end
  for _, job in ipairs(cfg.jobs) do
    for r = 1, job.runs do
      local seed = job.seed + r - 1
      local t0 = os.clock()
      if cfg.campaign then
        carried=nil
        campaignDecks, campaignWeaknesses, campaignFlags, upgradeAt, recollectionAt={},{},{},{},{}
        E.seed(seed)
        for _,id in ipairs(party) do
          campaignDecks[id]=T.decode(J.encode(decks.decks[id]))
          campaignWeaknesses[id]=R.pick(decks.weaknesses)
          upgradeAt[id],recollectionAt[id]=1,1
        end
        for slot=1,10 do
          local name=slot==1 and "prologue" or "campaign_slot_"..slot
          if slot>1 then S[name]=campaignScenario(slot) end
          local out=play(name,seed*100+slot)
          out.campaign_seed,out.slot=seed,slot
          out.cpu=os.clock()-t0
          for d,res in pairs(out.districts or {}) do
            if res=="R1" then
              if d=="Square" then campaignFlags["The vote still stands"]=true
              elseif d=="Church" then campaignFlags["The drowned heard the true hour"]=true
              elseif d=="Road" then campaignFlags["The walkers keep their ring"]=true
              elseif d=="Almanac" then campaignFlags["The name is kept unspoken"]=true end
            end
          end
          local agedOut=false
          for _,id in ipairs(party) do if (out.campaign_state.campaign.years[id] or 0)>=18 then agedOut=true end end
          if slot<10 and not out.engine_error and not agedOut then purchaseAfter(out) end
          total=total+1 ; emit("GAME",out)
          if out.engine_error or agedOut or out.ended=="contest" then break end
        end
        carried,campaignDecks,campaignWeaknesses,campaignFlags=nil,nil,nil,nil
      else
        local out = play(job.scenario, seed)
        out.cpu = os.clock() - t0
        total = total + 1
        emit("GAME", out)
      end
      if H.args.snapshots and cfg.snapshotGame then H.snapshot("end of " .. job.scenario) end
    end
  end
  H.check("the play engine played " .. total .. " game(s)", total > 0)
end
