-- The players' policy (designer tooling): a greedy but competent party.
-- Each action scores its options (objective progress, clue efficiency,
-- threats, the Appointed, time and Dissonance) and takes the best one. It
-- knows the rules and the chaos bag's contents (like a player who counts
-- tokens) but not the order of any deck.

return function(R, T)
  local A = {}
  R.AI = A
  local P = R.P
  local FX = R.FX

  ------------------------------------------------------------ objectives --

  --- The act the party is working on now (cfg.objectives order), or nil.
  function A.objective()
    local G = R.G
    for _, id in ipairs(G.cfg.objectives or {}) do
      for _, district in ipairs(G.actOrder) do
        local act = G.acts[district]
        if act and act.id == id and not act.completed then return act end
      end
    end
    return nil
  end
  function A.nextObjective(after)
    local G = R.G
    local seen = false
    for _, id in ipairs(G.cfg.objectives or {}) do
      for _, district in ipairs(G.actOrder) do
        local act = G.acts[district]
        if act and act.id == id and not act.completed then
          if seen then return act end
          if act == after then seen = true end
        end
      end
    end
    return nil
  end

  --- Clues the party still has to collect for this act (0 when enough).
  function A.need(act, inv)
    if not act then return 0 end
    local spec = FX.ACTS[act.id] or {}
    if spec.sequence or spec.contest then return 0 end
    if spec.standFirm then return math.max(0, R.walksBesideCost() - R.partyClues()) end
    local need = math.max(0, FX.actNeed(act.id) - R.partyClues())
    -- clues only count where they are contributed: an investigator on the way
    -- also counts only the clues of those who will be there about as soon
    -- (not engaged, no farther from the act's location than they are)
    if inv and spec.contrib and need == 0 then
      local loc = A.actLocation(act, inv)
      if loc then
        local mine = A.travelCost(R.locOf(inv), loc)
        local near = 0
        for _, x in ipairs(R.aliveInvs()) do
          local engaged = false
          for _, en in ipairs(R.G.enemies) do if en.engaged == x and not en.exhausted then engaged = true end end
          if x == inv or (not engaged and A.travelCost(R.locOf(x), loc) <= mine + 1) then near = near + x.clues end
        end
        need = math.max(0, FX.actNeed(act.id) - near)
      end
    end
    return need
  end
  function A.cluesReserved()
    local act = A.objective()
    if not act then return 0 end
    return FX.actNeed(act.id)
  end
  --- A secondary objective is paid for only when the clues also cover what
  -- the objective the party is working on still needs.
  function A.wantsAdvance(act)
    local obj = A.objective()
    if not obj or obj == act then return true end
    if FX.actNeed(act.id) == 0 then return true end          -- nothing to pay (a story asset delivered)
    local spec = FX.ACTS[obj.id] or {}
    if spec.sequence or spec.contest then return true end
    local objNeed = spec.standFirm and R.walksBesideCost() or FX.actNeed(obj.id)
    return R.partyClues() - FX.actNeed(act.id) >= objNeed
  end

  --- Where the act is met (location), or nil.
  function A.actLocation(act, inv)
    local G = R.G
    local spec = FX.ACTS[act.id] or {}
    if spec.sequence then
      local step = (inv and inv.walk or 0) + 1
      return R.locById(spec.sequence[math.min(step, 3)])
    end
    if spec.carry then
      -- take the story asset, pick a dropped one up, or deliver it
      if act.holder then return R.locById(spec.at) end
      if act.dropped then return R.G.locs[act.dropped] end
      return R.locById(spec.carry.take)
    end
    if spec.needLamp and not G.lampLit then return R.locById("sthr-loc-lanternroom") end
    if spec.at then return R.locById(spec.at) end
    return nil
  end

  ------------------------------------------------------------ helpers --

  local function pathLen(from, to)
    if not from or not to then return 99 end
    if from == to then return 0 end
    local _, d, crossings = R.route(from, to)
    if not d then return 99 end
    return d, crossings
  end

  --- Cost (in actions) of getting from a to b this round, crossings counted
  -- as an extra action unless already paid this round.
  local function travelCost(a, b)
    if a == b then return 0 end
    local nxt, d, crossings, path = R.route(a, b)
    if not d then return 99 end
    local extra = 0
    for i = 2, #(path or {}) do
      if R.isCrossing(path[i - 1], path[i]) and not R.G.crossedThisRound[R.crossKey(path[i - 1], path[i])] then extra = extra + 1.5 end
    end
    return d + extra
  end
  A.travelCost = travelCost

  function A.invP(inv, skill, diff, kind)
    local base = R.skillBase(inv, skill) + P.staticBonus(inv, skill, { kind = kind }) - diff
    -- cards and resources on hand add about one point
    local extra = (#inv.hand >= 3 and 1 or 0)
    return R.prob(inv, base + extra), R.prob(inv, base)
  end

  function A.valueOf(L)
    local obj = A.objective()
    if not obj then return 0 end
    local target = A.actLocation(obj)
    if target == L then return 20 end
    return 0
  end

  function A.bestEnemyHere(inv, pred)
    local best
    for _, en in ipairs(R.G.enemies) do
      if en.loc == inv.loc and not en.dead and (not pred or pred(en)) then
        if not best or (en.def.health or 1) - en.damage < (best.def.health or 1) - best.damage then best = en end
      end
    end
    return best
  end

  function A.mostHurtHere(inv, damageOnly)
    local best, bv
    for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
      local v = x.damage + (damageOnly and 0 or x.horror)
      if v > 0 and (bv == nil or v > bv) then best, bv = x, v end
    end
    return best
  end

  --- The location a hunter moves toward: its prey among the nearest investigators.
  function A.huntTarget(en)
    local G = R.G
    local here = G.locs[en.loc]
    if not here then return nil end
    local dist = R.paths(here, { enemy = true })
    local best, bd, cands = nil, nil, {}
    for _, inv in ipairs(R.aliveInvs()) do
      local d = dist[inv.loc]
      if d then
        if bd == nil or d < bd then bd, cands = d, { inv } elseif d == bd then cands[#cands + 1] = inv end
      end
    end
    local only = R.onlyPrey(en)
    if only then return G.locs[only.loc] end
    -- "Prey – Most ..." chooses among all investigators (the Appointed-like text), else the nearest
    local text = tostring(en.def.text or "")
    if text:find("Prey", 1, true) then
      local all = {}
      for _, inv in ipairs(R.aliveInvs()) do if dist[inv.loc] then all[#all + 1] = inv end end
      local prey = R.prey(en, all)
      return prey and G.locs[prey.loc]
    end
    local prey = R.prey(en, cands)
    return prey and G.locs[prey.loc]
  end

  --- Pick a connecting location for a forced or chosen move.
  function A.chooseMove(inv, from, forced, opts)
    opts = opts or {}
    local G = R.G
    if not from then return nil end
    local target = A.targetFor(inv)
    local best, bs
    for _, L in pairs(from.adj) do
      if R.canEnter(from, L) then
        local s = target and travelCost(L, target) or 0
        if opts.noEnemies then for _, en in ipairs(G.enemies) do if en.loc == L.guid then s = s + 5 end end end
        if bs == nil or s < bs then best, bs = L, s end
      end
    end
    return best
  end

  ------------------------------------------------------------ targets --

  --- How much staying at L is likely to hurt this investigator (rough units of damage/horror).
  function A.danger(L, inv)
    local G = R.G
    if not L then return 0 end
    local d = 0
    if L.id == "sthr-loc-wheel" then d = d + 3 end
    local AL = R.appointedLoc()
    if AL == L and R.stage() >= 2 and not G.appointed.exhausted then d = d + 4 end
    -- sleeping Echoes all wake when Dissonance leaves Calm: a careful party
    -- counts them once the band is close to turning (Hour VIII raises it by 2)
    local wakeSoon = R.band() == "Calm" and (R.dissonance() >= R.consts().glitch - 3 or R.hour() >= 7)
    for _, en in ipairs(G.enemies) do
      if en.loc == L.guid and not en.engaged and not en.exhausted and not R.isAloof(en) then
        if not R.sleepwalking(en) then
          d = d + (en.def.damage or 0) + (en.def.horror or 0)
        elseif wakeSoon then
          d = d + (en.def.damage or 0) + (en.def.horror or 0)
        end
      end
    end
    if inv and ((inv.sanity - inv.horror) <= 3 or (inv.health - inv.damage) <= 3) then d = d * 2 end
    return d
  end
  function A.frail(inv) return (inv.sanity - inv.horror) <= 2 or (inv.health - inv.damage) <= 2 end

  --- Clues the party still needs for `nxt` once `act` has been paid for.
  function A.needAfter(act, nxt)
    local left = math.max(0, R.partyClues() - (act and FX.actNeed(act.id) or 0))
    return math.max(0, FX.actNeed(nxt.id) - left)
  end

  --- Clue sources worth walking to: {L, score} (lower is better).
  local function clueSpots(inv, act)
    local G = R.G
    local here = R.locOf(inv)
    local target = act and A.actLocation(act, inv)
    local out = {}
    for _, L in ipairs(G.locList) do
      if not L.closed and G.impassable ~= L.guid then
        local c = L.revealed and R.clues(L) or (L.def.clues or 0) * ((L.def.clues_per_investigator and G.n) or 1)
        if c > 0 then
          local cost = travelCost(here, L)
          if cost < 99 then
            local p = A.invP(inv, "int", R.shroud(L), "investigate")
            local s = cost + (1 - p) * 2.5 + (target and 0.35 * travelCost(L, target) or 0)
            -- others already there take those clues
            local others = 0
            for _, x in ipairs(R.aliveInvs()) do if x ~= inv and x.loc == L.guid then others = others + 1 end end
            if others >= c then s = s + 3 end
            if L.id == "sthr-loc-almanacsteps" or L.id == "sthr-loc-belfry" and not R.knows("the-thirteenth-toll") then s = s + 0.8 end
            if L.id == "sthr-loc-well" and not R.knows("the-sheriff-is-already-dead") then s = s + 0.4 end
            s = s + 0.7 * A.danger(L, inv)
            out[#out + 1] = { L = L, s = s }
          end
        end
      end
    end
    table.sort(out, function(a, b) return a.s < b.s end)
    return out
  end

  --- The location this investigator is heading for, and why.
  function A.targetFor(inv)
    local G = R.G
    local here = R.locOf(inv)
    if G.finale then
      -- the party holds the Sealed Study and lets the Appointed come to it;
      -- it steps out only for a Hold Back one move away inside the district
      local study = R.locById("sthr-loc-sealedstudy")
      local AL = R.appointedLoc()
      local engagedNow = false
      for _, en in ipairs(G.enemies) do if en.engaged == inv and not en.exhausted then engagedNow = true end end
      if AL and R.stage() >= 1 and not G.appointed.exhausted and here and AL ~= here and not A.frail(inv) and not engagedNow then
        local _, d, crossings = R.route(here, AL)
        local skill = (R.skillBase(inv, "wil") >= R.skillBase(inv, "com")) and "wil" or "com"
        local p = R.prob(inv, R.skillBase(inv, skill) + P.staticBonus(inv, skill, {}) - R.holdBackDiff() + 1)
        if d and d <= 1 and (crossings or 0) == 0 and p >= 0.4 then return AL, "hold back" end
      end
      return study, "finale"
    end
    if G.cfg.finaleGoal and not G.finale then
      return R.locById("sthr-loc-sealedstudy"), "to the finale"
    end
    local act = A.objective()
    if not act then return A.maintenanceTarget(inv) end
    local spec = FX.ACTS[act.id] or {}
    local loc = A.actLocation(act, inv)
    if spec.sequence then return loc, "walk" end
    if spec.standFirm then return loc, "stand firm" end
    if spec.carry and (act.holder or act.dropped) then
      -- the controller delivers; the others pick a dropped asset up (nearest),
      -- or work ahead on the next objective, or go along
      if act.holder == inv then return loc, "go" end
      if act.dropped then
        local nearest, nd
        for _, x in ipairs(R.aliveInvs()) do
          local d = travelCost(R.locOf(x), loc)
          if nd == nil or d < nd then nearest, nd = x, d end
        end
        if nearest == inv then return loc, "go" end
      end
      local nxt = A.nextObjective(act)
      if nxt then
        if A.needAfter(act, nxt) > 0 then
          local s = clueSpots(inv, nxt)
          if s[1] then return s[1].L, "clues (next)" end
        end
        return A.actLocation(nxt, inv), "next"
      end
      return loc, "go"
    end
    if A.need(act, inv) > 0 then
      local spots = clueSpots(inv, act)
      if spots[1] then return spots[1].L, "clues" end
      local nxt = A.nextObjective(act)
      return loc, "go"
    end
    if spec.twoPlace then
      -- one investigator to each place: the nearest to the first goes there,
      -- the nearest other one to the second (solo: the first, then the second)
      local first, second = R.locById(spec.twoPlace[1]), R.locById(spec.twoPlace[2])
      if G.n == 1 then
        if inv.wellRound == G.round then return second, "go" end
        return first, "go"
      end
      local nearA, da
      for _, x in ipairs(R.aliveInvs()) do
        local d = travelCost(R.locOf(x), first)
        if da == nil or d < da then nearA, da = x, d end
      end
      if nearA == inv then return first, "go" end
      local nearB, db
      for _, x in ipairs(R.aliveInvs()) do
        if x ~= nearA then
          local d = travelCost(R.locOf(x), second)
          if db == nil or d < db then nearB, db = x, d end
        end
      end
      if nearB == inv then return second, "go" end
      local nxt = A.nextObjective(act)
      if nxt and A.needAfter(act, nxt) > 0 then
        local s = clueSpots(inv, nxt)
        if s[1] then return s[1].L, "clues (next)" end
      end
      return second, "go"
    end
    -- enough clues: those who carry them (or one investigator) go
    if spec.contrib then
      if inv.clues > 0 or spec.action then return loc, "go" end
      -- a clueless investigator helps elsewhere
      local nxt = A.nextObjective(act)
      if nxt and A.needAfter(act, nxt) > 0 then
        local s = clueSpots(inv, nxt)
        if s[1] then return s[1].L, "clues (next)" end
      end
      return loc, "go"
    end
    -- "an investigator at X": the nearest one goes, the others work ahead
    local nearest, nd
    for _, x in ipairs(R.aliveInvs()) do
      local d = travelCost(R.locOf(x), loc)
      if nd == nil or d < nd then nearest, nd = x, d end
    end
    if nearest == inv then return loc, "go" end
    local nxt = A.nextObjective(act)
    if nxt then
      if A.needAfter(act, nxt) > 0 then
        local s = clueSpots(inv, nxt)
        if s[1] then return s[1].L, "clues (next)" end
      end
      return A.actLocation(nxt, inv), "next"
    end
    return loc, "go"
  end

  --- No objective left: Victory locations, calm Dissonance, healing, safety.
  function A.maintenanceTarget(inv)
    local G = R.G
    local here = R.locOf(inv)
    local best, bs
    for _, L in ipairs(G.locList) do
      if not L.closed and (L.def.victory or 0) > 0 and G.impassable ~= L.guid then
        local c = L.revealed and R.clues(L) or 1
        if c > 0 or not L.revealed then
          local s = travelCost(here, L)
          if bs == nil or s < bs then best, bs = L, s end
        end
      end
    end
    if best and bs < 6 then return best, "victory" end
    local vestry = R.locById("sthr-loc-vestry")
    if vestry and R.dissonance() >= R.consts().glitch - 1 and R.partyClues() > 0 then return vestry, "vestry" end
    -- nothing left to do: wait out the night at the safest place a step away
    -- (inside the district, so no crossing), not in a crowd of enemies
    local safest, sd = here, A.danger(here, inv)
    for _, L in pairs((here and here.adj) or {}) do
      if not L.closed and G.impassable ~= L.guid and R.canEnter(here, L) and not R.isCrossing(here, L) then
        local dl = A.danger(L, inv)
        if dl < sd then safest, sd = L, dl end
      end
    end
    if safest ~= here then return safest, "safety" end
    return here, "hold"
  end

  ------------------------------------------------------------ test prep --

  function A.prepareTest(inv, skill, diff, base, opts)
    local G = R.G
    local target = opts.target or (opts.important and 0.72 or 0.6)
    if opts.kind == "treachery" or opts.kind == "location" then target = 0.7 end
    local committed, boost = {}, 0
    inv.lastCommitted = {}
    local function p() local t = base + boost for _, c in ipairs(committed) do t = t + c.icons end return R.prob(inv, t - diff) end
    local cur = p()
    if cur >= target then return committed, boost end
    -- own skill cards first
    local mine = P.commitables(inv, skill, opts)
    for _, c in ipairs(mine) do
      if cur >= target then break end
      if c.card.type == "Skill" or (opts.important and cur < 0.5) then
        P.discardFromHand(inv, c.card)
        table.remove(inv.discard)
        committed[#committed + 1] = { card = c.card, icons = c.icons, owner = inv }
        if c.card.name == "Deduction" and opts.kind == "investigate" then inv.lastCommitted.deduction = true end
        if c.card.name == "Vicious Blow" and opts.kind == "fight" then inv.lastCommitted.vicious = true end
        if c.card.name == "Foreknowledge" and (inv.memory or 0) > 0 then
          R.addMemory(inv, -1, "Foreknowledge")
          T.api("shApiTally", { id = inv.id, kind = "spent", delta = 1 })
        end
        cur = p()
      end
    end
    -- resource boosts
    local boosts = P.boosts(inv, skill, opts)
    for _, b in ipairs(boosts) do
      if cur >= target then break end
      if b.cost == "resource" then
        local n = 0
        while cur < target and inv.resources > 1 and n < 3 do
          b.pay() ; boost = boost + b.gain ; n = n + 1
          cur = p()
        end
      elseif b.cost == "secret" then
        b.pay() ; boost = boost + b.gain ; cur = p()
      end
    end
    -- other investigators at the location commit one card each
    if not opts.peril and not inv.round.nobodyBelieves and cur < target then
      for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
        if x ~= inv and cur < target and not x.round.nobodyBelieves then
          local theirs = P.commitables(x, skill, { helper = true })
          local c = theirs[1]
          if c and c.card.type == "Skill" then
            P.discardFromHand(x, c.card)
            table.remove(x.discard)
            committed[#committed + 1] = { card = c.card, icons = c.icons, owner = x }
            cur = p()
          end
        end
      end
    end
    -- Seraphine pays Dissonance only for a test that matters and would likely
    -- fail, well below the next band, and never enough to lean on the loop
    -- (3 payments in a loop cost a Year)
    if cur < 0.5 and opts.important then
      for _, b in ipairs(boosts) do
        if b.cost == "dissonance" and cur < target and R.dissonance() + 1 < R.consts().glitch - 1
           and (inv.raisedCost or 0) < 2 then
          b.pay() ; boost = boost + b.gain ; cur = p()
        end
      end
    end
    return committed, boost
  end

  ------------------------------------------------------------ turn --

  function A.turnOrder()
    local list = {}
    for _, inv in ipairs(R.G.inv) do list[#list + 1] = inv end
    -- engaged investigators first (deal with threats before they move)
    table.sort(list, function(a, b)
      local ea, eb = 0, 0
      for _, en in ipairs(R.G.enemies) do
        if en.engaged == a then ea = ea + 1 end
        if en.engaged == b then eb = eb + 1 end
      end
      if ea ~= eb then return ea > eb end
      return a.idx < b.idx
    end)
    return list
  end

  function A.startTurn(inv)
    local G = R.G
    local L = R.locOf(inv)
    -- Cass names a symbol (2 resources) when she can spare them
    if inv.id == "sthrcass" and not inv.round.cassNamed and inv.resources >= 4 then
      inv.round.cassNamed = true
      inv.resources = inv.resources - 2
      inv.namedToken = (R.band() ~= "Calm") and "Skull" or "Skull"
    end
    if L then FX.townHallFree(inv, L) end
    -- the finale: begin at the Sealed Study once the party is there
    if G.cfg.finaleGoal and not G.cfg.finaleAtNine and not G.finale and L and L.id == "sthr-loc-sealedstudy" then
      local all = true
      for _, x in ipairs(R.aliveInvs()) do if x.loc ~= L.guid then all = false end end
      if all or R.hour() >= 6 then R.beginFinale(inv) end
    end
  end

  local function engagedWith(inv)
    local l = {}
    for _, en in ipairs(R.G.enemies) do
      if en.engaged == inv and not R.sleepwalking(en) then l[#l + 1] = en end
    end
    return l
  end

  local function bestWeapon(inv)
    local best, bv
    for _, a in ipairs(inv.assets) do
      local w = P.WEAPON[a.name]
      if w and (not w[3] or a.uses > 0) then
        local skill = w[4] or "com"
        local v = R.skillBase(inv, skill) + w[1] + 0.8 * w[2]
        if bv == nil or v > bv then best, bv = a, v end
      end
    end
    return best
  end

  --- Is this card worth an action (and its cost) now? Returns a score.
  local WANT = {
    ["Machete"] = { "sthrelias", 8 }, [".45 Automatic"] = { "sthrelias", 7 }, ["Baseball Bat"] = { "sthrbirdie", 7 },
    ["Shrivelling"] = { "sthrseraphine", 7 }, ["Switchblade"] = { "sthrcass", 3 }, ["Knife"] = { nil, 2 },
    ["Magnifying Glass"] = { nil, 7 }, ["Flashlight"] = { nil, 5 }, ["Dr. Milan Christopher"] = { nil, 6 },
    ["Holy Rosary"] = { nil, 5 }, ["Leather Coat"] = { nil, 6 }, ["Guard Dog"] = { nil, 5 }, ["Beat Cop"] = { nil, 5 },
    ["Stray Cat"] = { nil, 3 }, ["Physical Training"] = { nil, 4 }, ["Hard Knocks"] = { nil, 4 }, ["Dig Deep"] = { nil, 4 },
    ["Hyperawareness"] = { nil, 4 }, ["Arcane Studies"] = { nil, 4 }, ["Rabbit's Foot"] = { nil, 4 },
    ["Pickpocketing"] = { nil, 2 }, ["Leo De Luca"] = { nil, 6 }, ["First Aid"] = { nil, 2 }, ["Medical Texts"] = { nil, 1 },
    ["Old Book of Lore"] = { nil, 1 }, ["The Lexicon of the Hour"] = { nil, 5 }, ["Marked Deck"] = { nil, 1 },
    ["The Bell of Ambergrove"] = { nil, 4 }, ["Lucky Compass"] = { nil, 2 }, ["The Ambergrove Lamp"] = { nil, 3 },
    -- XP cards
    ["Shotgun (4)"] = { "sthrelias", 9 }, ["Lightning Gun (5)"] = { "sthrelias", 10 }, ["Elder Sign Amulet (3)"] = { nil, 6 },
    ["Bulletproof Vest (3)"] = { nil, 6 }, ["Higher Education (3)"] = { nil, 5 }, ["Encyclopedia (2)"] = { nil, 5 },
    ["Switchblade (2)"] = { "sthrcass", 5 }, [".41 Derringer (2)"] = { "sthrcass", 7 }, ["Hired Muscle (1)"] = { nil, 5 },
    ["Chicago Typewriter (4)"] = { "sthrcass", 9 }, ["Streetwise (3)"] = { nil, 5 }, ["Shrivelling (3)"] = { "sthrseraphine", 8 },
    ["Shrivelling (5)"] = { "sthrseraphine", 9 }, ["Peter Sylvestre (2)"] = { nil, 6 }, ["Scrapper (3)"] = { nil, 4 },
  }
  local function assetScore(inv, c)
    local w = WANT[c.name]
    if not w then return 0 end
    if w[1] and w[1] ~= inv.id then return w[2] * 0.3 end
    for _, a in ipairs(inv.assets) do if a.name == c.name and (c.name ~= "Knife") then return 0 end end
    local s = w[2]
    if R.G.round <= 2 then s = s + 1 end
    return s
  end

  --- Choose the next action: {kind, actions, provokes, run}.
  function A.choose(inv)
    local G = R.G
    local L = R.locOf(inv)
    if not L then return nil end
    local act = A.objective()
    local spec = act and FX.ACTS[act.id] or {}
    local opts = {}
    local function add(score, kind, run, extra)
      local o = { score = score, kind = kind, run = run, actions = 1 }
      for k, v in pairs(extra or {}) do o[k] = v end
      opts[#opts + 1] = o
    end

    -- 1. engaged enemies: fight or evade any of them (the most dangerous or the
    -- easiest to remove scores best), not only the first to engage
    local eng = engagedWith(inv)
    local worst, worstThreat = nil, -1
    for _, en in ipairs(eng) do
      local threat = (en.def.damage or 0) + (en.def.horror or 0)
      if threat > worstThreat then worst, worstThreat = en, threat end
      local weapon = bestWeapon(inv)
      local skill = weapon and (P.WEAPON[weapon.name][4] or "com") or "com"
      local pf = R.prob(inv, R.skillBase(inv, skill) + P.staticBonus(inv, skill, { kind = "fight", weapon = weapon }) - R.enemyFight(en) + 1)
      local pe = R.prob(inv, R.skillBase(inv, "agi") + P.staticBonus(inv, "agi", { kind = "evade" }) - R.enemyEvade(en) + 1)
      local left = (en.def.health or 1) - en.damage
      local per = 1 + ((weapon and P.WEAPON[weapon.name][2]) or 0)
      local hits = math.ceil(left / per)
      local wantEvade = (en.id == "sthr-onewhorides" and not en.exhausted)
        or (G.walksBesideCurrent and L.id == "sthr-loc-turning" and R.hasTrait(en.def, "Echo"))
      -- an enemy that hits harder is worth more to be rid of (+1 a point of damage or horror)
      local fightScore = (30 + threat) * pf / hits
      local evadeScore = R.cannotEvade(en) and 0 or (26 + threat) * pe
      if (inv.health - inv.damage) <= (en.def.damage or 0) + 1 then fightScore = fightScore * 0.7 end
      if inv.id == "sthrelias" or inv.id == "sthrseraphine" and weapon then fightScore = fightScore * 1.3 end
      if wantEvade then evadeScore = evadeScore + 50 end
      -- the finale: the Uninvited's defeat is contest progress
      if G.finale and en.id == "sthr-uninvited" then fightScore = fightScore * 1.6 end
      add(fightScore, "fight", function() R.ACT.fight(inv, en, weapon) end, { provokes = false })
      add(evadeScore, "evade", function() R.ACT.evade(inv, en) end, { provokes = false })
    end
    if worst then
      local en = worst
      -- event answers
      for _, c in ipairs(inv.hand) do
        if c.name == "Cunning Distraction" and inv.resources >= 5 and #eng >= 2 then
          add(40, "play", function() R.ACT.play(inv, c) end, { provokes = false })
        end
      end
      local cat = P.findAsset(inv, "Stray Cat")
      if cat and not R.hasTrait(en.def, "Elite") then
        add(45, "ability", function()
          for i, a in ipairs(inv.assets) do if a == cat then table.remove(inv.assets, i) inv.discard[#inv.discard + 1] = a.rec break end end
          en.exhausted = true ; en.engaged = nil ; R.placeEnemy(en)
        end, { provokes = false, actions = 0 })
      end
    end

    -- Town Ledger: [action] exhaust: an awake Echo here is Sleepwalking until the end of the round
    if inv.story and inv.story.id == "sthr-item-ledger" and not inv.storyExhausted then
      for _, en in ipairs(G.enemies) do
        if en.loc == L.guid and not en.dead and R.hasTrait(en.def, "Echo") and not R.sleepwalking(en)
           and (en.engaged == inv or not en.exhausted) then
          add(en.engaged == inv and 42 or 22, "ability", function()
            inv.storyExhausted = true
            en.ledgerRound = G.round
            if en.engaged then en.engaged = nil ; R.placeEnemy(en) end
            R.log("Town Ledger: %s sleeps until the end of the round", en.name)
          end)
          break
        end
      end
    end

    -- 2. the Appointed here: Hold Back
    local AL = R.appointedLoc()
    -- (camping at the Sealed Study for Hour IX, finale_h9, the party lets the Appointed come)
    if AL == L and R.stage() >= 1 and not G.appointed.exhausted and not (G.cfg.finaleAtNine and G.cfg.finaleGoal and not G.finale) then
      local skill = (R.skillBase(inv, "wil") >= R.skillBase(inv, "com")) and "wil" or "com"
      local p = R.prob(inv, R.skillBase(inv, skill) + P.staticBonus(inv, skill, {}) - R.holdBackDiff() + 1)
      local s = 34 * p + (G.finale and 20 or 0) + (R.hour() >= 6 and 6 or 0)
      -- in the finale, once the deep entries are spent, Hold Back is the way
      -- forward: worth trying at long odds (cards are committed to it)
      local finaleNeed = G.finale and not (G.deepToSpend and #G.deepToSpend > 0)
      if finaleNeed then s = s + 25 end
      -- engaged by the Arrived Appointed, Hold Back is the one action it does not punish
      local caught = G.appointed.engaged == inv and R.stage() >= 3
      if caught then s = s + 20 end
      if p >= 0.3 or ((finaleNeed or caught) and p >= 0.12) then add(s, "holdback", function() R.ACT.holdBack(inv) end, { provokes = "notAppointed" }) end
    end

    -- 3. objective actions here
    if act then
      local target = A.actLocation(act, inv)
      if spec.action and target == L then
        local here = spec.contrib == false and R.aliveInvs() or R.investigatorsAt(L)
        local have = 0
        for _, x in ipairs(here) do
          have = have + x.clues
          if spec.fare then have = have + math.floor(x.resources / ((R.WHATIF or {}).fareRate or FX.FARE_RATE or 2)) + (x.memory or 0) end
        end
        local need = FX.actNeed(act.id)
        if have >= need then
          add(60, "objective", function() R.objectiveAction(inv, act) end)
        end
      end
      if spec.carry and not act.holder and target == L then
        if act.dropped then
          add(60, "objective", function() R.takeStory(inv, act) end)
        else
          local payers = spec.carry.any and R.aliveInvs() or R.investigatorsAt(L)
          local have = 0
          for _, x in ipairs(payers) do have = have + x.clues end
          if have >= FX.actNeed(act.id) then
            add(60, "objective", function() R.takeStory(inv, act) end)
          end
        end
      end
      local sfNeed = spec.standFirm and R.walksBesideCost() or 0
      local sfHave = 0
      for _, x in ipairs(R.investigatorsAt(L)) do sfHave = sfHave + x.clues end
      if spec.standFirm and target == L and sfHave >= sfNeed then
        for _, en in ipairs(G.enemies) do
          if en.loc == L.guid and R.hasTrait(en.def, "Echo") and not en.exhausted and not R.sleepwalking(en) then
            add(55, "objective", function() R.standFirm(inv, en) end)
            break
          end
        end
      end
      if spec.needLamp and not G.lampLit and L.id == "sthr-loc-lanternroom" then
        for _, ab in ipairs(FX.locationAbilities(inv, L)) do
          if ab.kind == "lamp" then add(58, "ability", ab.fn) end
        end
      end
    end
    if G.finale and G.deepToSpend and #G.deepToSpend > 0 then
      -- no hurry: spent while nothing is engaged with you
      local cost = (R.WHATIF or {}).deepActions or 1                      -- what-if: [action][action]
      if (inv.actionsLeft or 3) >= cost then
        add(#eng > 0 and 12 or 48, "objective", function() R.spendDeep(inv) end, { actions = cost })
      end
    end

    -- 4. clues here
    local need = A.need(act, inv)
    local clues = L.revealed and R.clues(L) or 0
    if clues > 0 then
      local p = A.invP(inv, "int", R.shroud(L), "investigate")
      local score
      if act and need > 0 then score = 18 + 14 * p
      elseif spec.sequence and A.actLocation(act, inv) == L then score = 40 + 10 * p
      elseif (L.def.victory or 0) > 0 then score = 10 + 6 * p
      elseif act then
        local nxt = A.nextObjective(act)
        score = (nxt and A.needAfter(act, nxt) > 0) and (8 + 8 * p) or (3 + 4 * p)
      else score = 4 + 4 * p end
      if p < 0.25 then score = score * 0.6 end
      if G.finale then score = 1 end            -- clues win nothing in the finale
      local targetHere = act and A.actLocation(act, inv) == L
      if not targetHere then score = score - 2 * A.danger(L, inv) end
      add(score, "investigate", function() R.ACT.investigate(inv, { important = need > 0 }) end)
    end

    -- 5. move toward the target
    local target, why = A.targetFor(inv)
    if target and target ~= L then
      local step
      if L.id == "sthr-loc-windingstair" and target.id == "sthr-loc-lanternroom" then
        add(20, "climb", function() FX.climb(inv) end)
      else
        step = R.route(L, target)
        if step and R.canEnter(L, step) then
          local s = 16
          if why == "go" then s = 24 end
          if why == "hold back" then s = 26 end
          if why == "finale" or why == "to the finale" then s = 30 end
          if why == "victory" then s = 9 end
          if why == "hold" then s = 0 end
          if why == "safety" then s = 14 end
          local AL2 = R.appointedLoc()
          if AL2 == step and R.stage() >= 2 and not G.appointed.exhausted and why ~= "hold back" then
            local frail = (inv.sanity - inv.horror) <= 3 or (inv.health - inv.damage) <= 3
            s = s - (frail and 22 or 8)
          end
          if R.isCrossing(L, step) then
            if not G.crossedThisRound[R.crossKey(L, step)] and not FX.freeCrossingAvailable(L, step) then
              -- the first crossing this round costs an Hour: never into Hour IX.
              -- Heading for the current objective it costs the same now as
              -- later (go early, together); other trips are weighed harder
              local forObjective = why == "go" or why == "walk" or why == "stand firm" or why == "clues"
              if R.hour() >= 8 then s = -100 elseif forObjective then s = s - 1 else s = s - 5 end
            else
              s = s + 4       -- already paid this round: cross with the others
            end
          end
          -- leaving a dangerous place
          local dHere, dThere = A.danger(L, inv), A.danger(step, inv)
          if dHere > dThere and not (act and A.actLocation(act, inv) == L and (spec.action or spec.contrib)) then
            s = s + 2 * (dHere - dThere)
          end
          local compass = P.findAsset(inv, "Lucky Compass")
          if compass and not compass.exhausted and #eng > 0 then
            add(s + 3, "move", function() R.ACT.assetAbility(inv, compass) ; R.moveInv(inv, step) end, { provokes = false })
          end
          add(s, "move", function() R.moveInv(inv, step) end, { provokes = true })
        elseif L.id == "sthr-loc-windingstair" then
          -- the path runs up the stair
          local _, _, _, path = R.route(L, target)
          if path and path[2] and path[2].id == "sthr-loc-lanternroom" then add(20, "climb", function() FX.climb(inv) end) end
        end
      end
    end

    -- 6. location abilities
    for _, ab in ipairs(FX.locationAbilities(inv, L)) do
      local s = 0
      if ab.kind == "dissonance" and R.dissonance() >= R.consts().glitch - 1 then s = 14 end
      if ab.kind == "heal" and (inv.damage + inv.horror) >= 3 then s = A.frail(inv) and 30 or 12 end
      if ab.kind == "memory" then s = 7 end
      if ab.kind == "rewind" then
        local d = R.dissonance()
        if R.hour() >= 5 and d + 2 < R.consts().glitch and act then s = 13 end
      end
      if ab.kind == "static" then s = 5 end
      if ab.kind == "year" then s = 6 end
      if ab.kind == "memory-year" then s = 0 end   -- a Year for 2 Memory: the party declines
      if s > 0 then add(s, "ability", ab.fn, { actions = ab.actions }) end
    end

    -- 7. cards
    for _, c in ipairs(inv.hand) do
      if c.type == "Asset" and (c.cost or 0) <= inv.resources then
        local s = assetScore(inv, c)
        if s > 0 then add(s, "play", function() R.ACT.play(inv, c) end) end
      elseif c.type == "Event" and (c.cost or 0) <= inv.resources then
        local n = c.name
        if n == "Emergency Cache" and inv.resources <= 3 then add(7, "play", function() R.ACT.play(inv, c) end) end
        if n == "Working a Hunch" and clues > 0 and need > 0 then add(40, "play", function() R.ACT.play(inv, c) end, { actions = 0, provokes = false }) end
        if n == "Drawn to the Flame" and clues >= 2 and need > 1 and (inv.health - inv.damage) > 3 and (inv.sanity - inv.horror) > 3 then
          add(19, "play", function() R.ACT.play(inv, c) end)
        end
        if n == "Sneak Attack" and A.bestEnemyHere(inv, function(en) return en.exhausted end) then add(15, "play", function() R.ACT.play(inv, c) end) end
        if n == "Elusive" and #eng > 0 and inv.resources >= 2 then add(28, "play", function() R.ACT.play(inv, c) end, { actions = 0, provokes = false }) end
        if n == "Blinding Light" and #eng > 0 then add(24, "play", function() R.ACT.play(inv, c) end, { provokes = false }) end
        if n == "Mind over Matter" and not inv.mindOverMatter and #eng > 0 and inv.stats.int > inv.stats.agi then
          add(20, "play", function() R.ACT.play(inv, c) end, { actions = 0, provokes = false })
        end
        if n == "I Remember the Ending" and not inv.loopUsed.rememberEnding and R.dissonance() <= 2 and R.hour() >= 3 then
          add(17, "play", function() R.ACT.play(inv, c) end)
        end
      end
    end
    for _, a in ipairs(inv.assets) do
      if a.name == "First Aid" and a.uses > 0 then
        local t = A.mostHurtHere(inv)
        if t and A.frail(t) then add(32, "ability", function() R.ACT.assetAbility(inv, a) end)
        elseif t and (t.damage + t.horror) >= 3 then add(8, "ability", function() R.ACT.assetAbility(inv, a) end) end
      end
      if a.name == "Old Book of Lore" and not a.exhausted and #inv.hand <= 3 then add(3, "ability", function() R.ACT.assetAbility(inv, a) end) end
      if a.name == "The Bell of Ambergrove" and not a.exhausted and a.uses > 0 and act and R.hour() >= 5
         and not inv.loopUsed.bell and not G.finale
         and R.dissonance() + 2 < R.consts().glitch - 1 and (inv.raisedCost or 0) < 2 then
        add(12, "ability", function() R.ACT.assetAbility(inv, a) end)
      end
    end
    -- persistent weaknesses: [action][action] discard
    for n, card in pairs(inv.threat) do
      if n == "Haunted" or n == "Internal Injury" or n == "Chronophobia" or n == "Psychosis" or n == "Hypochondria" then
        if inv.actionsLeft >= 2 then
          add(n == "Haunted" and 9 or 11, "ability", function() inv.threat[n] = nil ; inv.discard[#inv.discard + 1] = card end, { actions = 2 })
        end
      end
    end
    for _, en in ipairs(G.enemies) do
      if en.weakness and en.name == "Mob Enforcer" and en.engaged == inv and inv.resources >= 4 then
        add(35, "parley", function() inv.resources = inv.resources - 4 ; R.defeatEnemy(en, nil) end, { provokes = false })
      end
    end
    -- fighting unengaged enemies here (Victory, or in the way)
    for _, en in ipairs(G.enemies) do
      if en.loc == L.guid and not en.engaged and not R.sleepwalking(en) and not en.dead then
        local weapon = bestWeapon(inv)
        local skill = weapon and (P.WEAPON[weapon.name][4] or "com") or "com"
        local pf = R.prob(inv, R.skillBase(inv, skill) + P.staticBonus(inv, skill, { kind = "fight", weapon = weapon }) - R.enemyFight(en))
        local s = 0
        if (en.def.victory or 0) > 0 and pf >= 0.55 and (G.finale == false or en.id == "sthr-uninvited") then s = 9 * pf end
        if en.id == "sthr-uninvited" then s = 25 * pf end
        if en.id == "sthr-drownedverger" and L.id == "sthr-loc-vestry" and need > 0 then s = 10 * pf end
        if s > 0 then add(s, "fight", function() R.ACT.fight(inv, en, weapon) end) end
      end
    end

    -- 8. basics
    add(#inv.hand <= 2 and 5 or 2, "draw", function() P.draw(inv, 1) end)
    add(inv.resources <= 2 and 4 or 1.5, "resource", function() inv.resources = inv.resources + 1 end)

    -- actions that provoke attacks of opportunity cost what those attacks deal
    local aoo, dmg, hor = 0, 0, 0
    for _, en in ipairs(eng) do
      if not en.exhausted then
        aoo = aoo + 6 * ((en.def.damage or 0) + (en.def.horror or 0))
        dmg, hor = dmg + (en.def.damage or 0), hor + (en.def.horror or 0)
      end
    end
    local Aeng = G.appointed.engaged == inv and not G.appointed.exhausted and R.stage() >= 3
    local adef = R.card("sthr-appointed")
    for _, o in ipairs(opts) do
      if o.provokes ~= false and (o.actions or 1) > 0 then
        local d, h = dmg, hor
        if Aeng and o.provokes ~= "notAppointed" then d, h = d + (adef.damage or 2), h + (adef.horror or 2) end
        o.score = o.score - aoo
        if Aeng and o.provokes ~= "notAppointed" then o.score = o.score - 20 end
        -- never take an action whose attacks of opportunity would defeat you
        if (d > 0 or h > 0) and (inv.damage + d >= inv.health or inv.horror + h >= inv.sanity) then o.score = o.score - 200 end
      end
    end
    table.sort(opts, function(a, b) return a.score > b.score end)
    local best = opts[1]
    -- every action left would cost more than it gains (a lethal attack of
    -- opportunity): end the turn instead
    if best and best.score < -40 then return nil end
    if best and best.actions == 0 then
      -- free plays happen without spending an action
      best.actions = 0
    end
    return best
  end

  return A
end
