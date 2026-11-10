-- The official investigators for the Dunwich benchmark (designer tooling):
-- Zoey Samaras, Rex Murphy, Jenny Barnes and Jim Culver (their abilities,
-- elder signs, signature cards and weaknesses, from ArkhamDB's text), and the
-- scenarios' story assets ("Jazz" Mulligan, Alchemical Concoction, Professor
-- Warren Rice, Dr. Francis Morgan, Peter Clover). Their level-0 decks are The
-- Still Hour's same-class starter cards (official/dwl_data.py), whose effects
-- players.lua already encodes. Wraps players.lua's hooks for this process only.

return function(R, T)
  local E = T.E
  local P = R.P
  local FX = R.FX
  local ID = FX.ID

  P.APPROX = P.APPROX or {}
  local APPROX = {
    ["Zoey Samaras"] = "full",
    ["Rex Murphy"] = "full; the [elder_sign] is always taken as +2 (never the auto-fail for 3 cards); his reaction has no limit (as ArkhamDB's text prints it)",
    ["Jenny Barnes"] = "full; the extra resource is added at the end of the upkeep phase",
    ["Jim Culver"] = "full; he never treats an [elder_sign] as a [skull] (his [skull] is 0 but his [elder_sign] is +1)",
    ["Zoey's Cross"] = "full", ["Smite the Wicked"] = "full",
    ["Search for the Truth"] = "played with 2+ clues and room in hand",
    ["Rex's Curse"] = "on a success the token is re-revealed once; the first token's effects and the committed cards' success effects are not undone",
    ["Jenny's Twin .45s"] = "X is all her resources but 1 (at most 5)",
    ["Searching for Izzie"] = "the AI goes for it when no objective is pressing",
    ["Jim's Trumpet"] = "full", ["Final Rhapsody"] = "full",
  }
  P.DWL_APPROX = APPROX

  -- the new player cards' constants go into the tables players.lua and ai.lua read (their local
  -- tables, reached through the functions that use them, so The Still Hour's files stay untouched)
  local function upvalue(fn, name)
    for i = 1, 200 do
      local k, v = debug.getupvalue(fn, i)
      if not k then break end
      if k == name then return v end
    end
    error("play engine: no upvalue " .. name)
  end
  P.SOAK = P.SOAK or upvalue(P.playAsset, "SOAK")
  P.CONST = P.CONST or upvalue(P.staticBonus, "CONST")
  R.AI.WANT = R.AI.WANT or upvalue(R.AI.cardValue, "WANT")
  P.SOAK["Dr. Francis Morgan"] = { 4, 1 }
  P.SOAK["Professor Warren Rice"] = { 2, 3 }
  P.SOAK["\"Jazz\" Mulligan"] = { 2, 2 }
  P.SOAK["Dr. Henry Armitage"] = { 2, 2 }
  P.SOAK["Peter Clover"] = { 3, 2 }
  P.CONST["Dr. Francis Morgan"] = { "com", 1 }
  P.CONST["Professor Warren Rice"] = { "int", 1 }
  P.WEAPON["Jenny's Twin .45s"] = { 2, 1, true }
  for _, k in ipairs({ "Zoey's Cross", "Smite the Wicked", "Search for the Truth", "Rex's Curse", "Jenny's Twin .45s",
                       "Searching for Izzie", "Jim's Trumpet", "Final Rhapsody", "Holy Rosary" }) do P.CODED[k] = true end
  local WANT = R.AI.WANT
  WANT["Zoey's Cross"] = { "02001", 6 }
  WANT["Jim's Trumpet"] = { "02004", 6 }
  WANT["Jenny's Twin .45s"] = { "02003", 7 }
  WANT["Professor Warren Rice"] = { nil, 7 }
  WANT["Dr. Francis Morgan"] = { nil, 7 }
  WANT["Dr. Henry Armitage"] = { nil, 5 }

  function P.findAssetId(inv, id)
    for _, a in ipairs(inv.assets) do if a.rec and (a.rec.id == id or a.rec.sced == id) then return a end end
    return nil
  end

  ------------------------------------------------------------ setup --

  local newBase = P.newInvestigator
  function P.newInvestigator(idx, id, color, cardObj, mini, controlStats, deckData, weakness)
    local inv = newBase(idx, id, color, cardObj, mini, controlStats, deckData, weakness)
    inv.trauma = { physical = 0, mental = 0 }
    return inv
  end

  --- A story asset put into play under an investigator's control (its slot respected).
  function P.putIntoPlay(inv, rec)
    if rec.slot then
      for i, a in ipairs(inv.assets) do
        if a.rec and a.rec.slot == rec.slot then
          table.remove(inv.assets, i)
          inv.discard[#inv.discard + 1] = a.rec
          R.log("%s discards %s for %s", inv.name, a.name, rec.name)
          break
        end
      end
    end
    local a = { rec = rec, name = rec.name, uses = 0, exhausted = false, dmg = 0, hor = 0, story = rec.story }
    local s = P.SOAK[rec.name]
    if s then a.hp, a.sp = s[1], s[2] end
    inv.assets[#inv.assets + 1] = a
    R.log("%s takes control of %s", inv.name, rec.name)
    return a
  end

  ------------------------------------------------------------ abilities --

  local elderBase = P.elderSign
  function P.elderSign(inv)
    if inv.id == "02001" then return 1 end
    if inv.id == "02002" then return 2 end
    if inv.id == "02003" then return inv.resources end
    if inv.id == "02004" then return 1 end
    return elderBase(inv)
  end

  local resultBase = P.resultBonus
  function P.resultBonus(inv, name, margin)
    local b = resultBase(inv, name, margin)
    -- Zoey: [elder_sign] on a successful attack deals +1 damage
    if name == "Vicious Blow" and inv.id == "02001" and inv.lastToken == "Elder Sign" then b = b + 1 end
    -- Rex: after you succeed at a skill test by 2 or more while investigating: discover 1 clue
    if name == "Deduction" and inv.id == "02002" and margin >= 2 then b = b + 1 end
    return b
  end

  local engagedBase = P.onEngaged
  function P.onEngaged(inv, en)
    engagedBase(inv, en)
    if inv.defeated then return end
    if inv.id == "02001" then
      inv.resources = inv.resources + 1                           -- Zoey: gain 1 resource
      local cross = P.findAsset(inv, "Zoey's Cross")
      if cross and not cross.exhausted and inv.resources >= 1 and not en.dead then
        cross.exhausted = true
        inv.resources = inv.resources - 1
        R.damageEnemy(en, 1, inv, "Zoey's Cross")
      end
    end
  end

  --- Jim's Trumpet: when a [skull] is revealed during a skill test, heal 1 horror at or next to Jim.
  function P.trumpet(tester)
    for _, jim in ipairs(R.aliveInvs()) do
      local tr = P.findAsset(jim, "Jim's Trumpet")
      if tr and not tr.exhausted then
        local here = R.locOf(jim)
        local best, bh
        for _, x in ipairs(R.aliveInvs()) do
          local L = R.locOf(x)
          if x.horror > 0 and L and here and (L == here or here.adj[L.guid]) and (bh == nil or x.horror > bh) then best, bh = x, x.horror end
        end
        if best then tr.exhausted = true ; R.heal(best, 0, 1) ; R.log("Jim's Trumpet heals 1 horror from %s", best.name) end
      end
    end
  end

  local costBase = P.playCost
  function P.playCost(inv, card)
    if card.name == "Jenny's Twin .45s" then return math.min(5, math.max(1, inv.resources - 1)) end
    return costBase(inv, card)
  end
  local playBase = P.playAsset
  function P.playAsset(inv, card)
    local x = (card.name == "Jenny's Twin .45s") and P.playCost(inv, card) or nil
    local a = playBase(inv, card)
    if x then a.uses = x end
    return a
  end

  --- Skill values: Whippoorwill (-1 to each skill at its location), Cursed Luck (-1 during tests).
  local skillBase = R.skillBase
  function R.skillBase(inv, skill, opts)
    local v = skillBase(inv, skill, opts)
    for _, en in ipairs(R.G.enemies) do if en.id == "02090" and not en.dead and en.loc == inv.loc then v = v - 1 end end
    if inv.threat and inv.threat["Cursed Luck"] then v = v - 1 end
    return v
  end

  local afterTestBase = P.afterTest
  function P.afterTest(inv, ok, margin, skill, opts, committed)
    afterTestBase(inv, ok, margin, skill, opts, committed)
    -- Cursed Luck: after you succeed at a skill test by 1 or more, discard it
    if ok and margin >= 1 and inv.threat["Cursed Luck"] then
      local c = inv.threat["Cursed Luck"] ; inv.threat["Cursed Luck"] = nil
      if c.obj and T.alive(c.obj) then T.discardEncounter(c.obj) end
    end
    -- Science Building: when you fail a [willpower] test there, take 1 damage
    local L = R.locOf(inv)
    if not ok and skill == "wil" and L and L.id == ID.science and not inv.defeated then R.hurt(inv, 1, 0, "Science Building") end
  end

  --- Rex's Curse: when you would succeed, the token is revealed again (once per test).
  local testBase = R.test
  local function countTest(opts, ok)
    -- skill tests by kind (the benchmark's encounter-test metric; benchmark.py counts The Still Hour's the same way)
    local m = R.G and R.G.metrics
    if not m then return end
    local tk = m.tests_by_kind or {}
    m.tests_by_kind = tk
    local k = (opts and opts.kind) or "other"
    tk[k] = tk[k] or { n = 0, failed = 0 }
    tk[k].n = tk[k].n + 1
    if not ok then tk[k].failed = tk[k].failed + 1 end
  end
  function R.test(inv, skill, diff, opts)
    local ok, margin, token = testBase(inv, skill, diff, opts)
    countTest(opts, ok)
    if ok and inv.threat and inv.threat["Rex's Curse"] and not R.G.ended and not inv.defeated and token ~= "Canceled" then
      local old = FX.tokenValue(token, inv) or 0
      local name = FX.rawDraw(inv.color)
      R.touch()
      local v = FX.tokenValue(name, inv)
      local m2 = v and (margin - old + v) or -1
      R.log("Rex's Curse: %s re-reveals %s -> %s (margin %d)", inv.name, tostring(token), tostring(name), m2)
      R.G.metrics.tokens[name] = (R.G.metrics.tokens[name] or 0) + 1
      T.returnTokens()
      if m2 < 0 then
        FX.tokenAfter(name, inv, false, opts, m2)
        local c = inv.threat["Rex's Curse"] ; inv.threat["Rex's Curse"] = nil
        if c then inv.deck[#inv.deck + 1] = c.card or c ; R.shuffle(inv.deck) end
        R.G.metrics.tests_passed = R.G.metrics.tests_passed - 1
        local tk = (R.G.metrics.tests_by_kind or {})[opts and opts.kind or "other"]
        if tk then tk.failed = tk.failed + 1 end      -- counted as a success above
        return false, m2, name
      end
      return true, m2, name
    end
    return ok, margin, token
  end

  --- The House Always Wins: a [skull] is treated as 0 for 2 resources; Beginner's Luck's "cheat".
  local cancelBase = P.cancelToken
  function P.cancelToken(inv, tokenName, marginWith, marginWithout, opts)
    if R.G.scen == "1b" and tokenName == "Skull" and inv.resources >= 2 and marginWith < 0 and marginWithout >= 0 then
      inv.resources = inv.resources - 2
      R.G.metrics.skull_paid = (R.G.metrics.skull_paid or 0) + 1
      R.log("%s spends 2 resources: the [skull] is a 0", inv.name)
      return true
    end
    return cancelBase(inv, tokenName, marginWith, marginWithout, opts)
  end
  local wouldFailBase = P.wouldFail
  function P.wouldFail(inv, margin, tokenName, opts)
    local s = wouldFailBase(inv, margin, tokenName, opts)
    if s and s >= 0 then return s end
    if FX.mayCheat and FX.mayCheat(inv, opts) then
      -- treat the token as the best other token in the bag (the investigator's elder sign or +1)
      local best
      for _, name in ipairs(R.bag()) do
        local v = FX.tokenValue(name, inv)
        if v and (best == nil or v > best) then best = v end
      end
      local old = FX.tokenValue(tokenName, inv)
      if best and old and margin - old + best >= 0 then
        R.G.cheated, R.G.cheatRound = true, R.G.round
        R.G.metrics.cheats = (R.G.metrics.cheats or 0) + 1
        R.log("%s \"cheats\" (Beginner's Luck)", inv.name)
        return margin - old + best
      end
    end
    return s
  end

  --- Ward of Protection against these scenarios' treacheries (what each is worth cancelling).
  local WORTH = { ["02084"] = 3, ["02085"] = 2, ["02101"] = 2, ["02100"] = 2, ["02083"] = 2, ["02102"] = 2, ["01174"] = 2,
                  ["01166"] = 3, ["02091"] = 1, ["01178"] = 2, ["02092"] = 2, ["02093"] = 1, ["02082"] = 1, ["02099"] = 2,
                  ["02081"] = 1, ["01163"] = 1, ["01164"] = 2, ["01165"] = 1 }
  P.WARD_WORTH = WORTH
  function P.cancelTreachery(inv, id, def)
    local worth = WORTH[id] or 0
    if worth < 2 or def.weakness then return false end
    if inv.resources >= 1 and inv.horror < inv.sanity - 2 then
      for _, c in ipairs(inv.hand) do
        if c.name == "Ward of Protection" then
          P.discardFromHand(inv, c)
          inv.resources = inv.resources - 1
          R.hurt(inv, 0, 1, "Ward of Protection")
          R.log("%s cancels %s with Ward of Protection", inv.name, def.name or id)
          return true
        end
      end
    end
    return false
  end

  --- Draws: the VIP Area skips the upkeep draw; Beyond the Veil checks an empty deck.
  local drawBase = P.draw
  function P.draw(inv, k, why)
    local L = R.locOf(inv)
    if R.G.phase == "upkeep" and L and L.id == ID.vip and not why then return {} end
    local out = drawBase(inv, k, why)
    FX.checkEmptyDeck(inv)
    return out
  end

  ------------------------------------------------------------ weaknesses --

  local weaknessBase = P.weakness
  function P.weakness(inv, card)
    local G = R.G
    local id = card.id or card.sced
    if id == "02007" then
      -- Smite the Wicked: discard from the top of the encounter deck until an enemy; attach it, spawn it farthest from you
      G.metrics.weaknesses_drawn = G.metrics.weaknesses_drawn + 1
      for _ = 1, 50 do
        local c = T.drawEncounter(inv.color)
        if not c then break end
        local d = R.card(T.gm(c).id)
        if d.type == "Enemy" then
          local here = R.locOf(inv)
          local dist = R.paths(here, { enemy = true })
          local best, bd = here, -1
          for g, dd in pairs(dist) do if dd > bd then best, bd = G.locs[g], dd end end
          local en = R.spawnEnemy(c, best, nil, { want = "farthest from Zoey" })
          en.smite = inv
          G.smite = en
          R.log("Smite the Wicked: %s at %s", en.name, best.name)
          break
        end
        T.discardEncounter(c)
      end
      inv.discard[#inv.discard + 1] = card
      return
    elseif id == "02009" then
      G.metrics.weaknesses_drawn = G.metrics.weaknesses_drawn + 1
      inv.threat["Rex's Curse"] = { name = "Rex's Curse", card = card }
      return
    elseif id == "02011" then
      -- Searching for Izzie: attach to the location farthest from you
      G.metrics.weaknesses_drawn = G.metrics.weaknesses_drawn + 1
      local here = R.locOf(inv)
      local dist = R.paths(here, { enemy = true })
      local best, bd = here, -1
      for g, dd in pairs(dist) do if dd > bd then best, bd = G.locs[g], dd end end
      G.izzie = { loc = best.guid, owner = inv, card = card }
      R.log("Searching for Izzie: attached to %s", best.name)
      return
    elseif id == "02013" then
      -- Final Rhapsody: reveal 5 chaos tokens; each [skull] and [auto_fail]: 1 damage and 1 horror
      G.metrics.weaknesses_drawn = G.metrics.weaknesses_drawn + 1
      local k = 0
      for _ = 1, 5 do
        local name = FX.rawDraw(inv.color)
        if name == "Skull" or name == "Auto-fail" then k = k + 1 end
      end
      T.returnTokens()
      R.touch()
      inv.discard[#inv.discard + 1] = card
      if k > 0 then R.hurt(inv, k, k, "Final Rhapsody") end
      return
    end
    return weaknessBase(inv, card)
  end

  ------------------------------------------------------------ turns --

  local endTurnBase = P.endTurn
  function P.endTurn(inv)
    endTurnBase(inv)
    if inv.defeated or R.G.ended then return end
    local L = R.locOf(inv)
    -- Humanities Building: discard the top X cards, X = horror on you; Administration Building: the top card
    if L and L.id == ID.humanities and inv.horror > 0 then FX.mill(inv, inv.horror, "Humanities Building") end
    if L and L.id == ID.admin then FX.mill(inv, 1, "Administration Building") end
    -- Frozen in Fear: test [willpower] (3) at the end of your turn; discard it on a success
    if inv.threat["Frozen in Fear"] and not inv.defeated then
      if R.test(inv, "wil", 3, { kind = "treachery" }) then
        local c = inv.threat["Frozen in Fear"] ; inv.threat["Frozen in Fear"] = nil
        if c.obj and T.alive(c.obj) then T.discardEncounter(c.obj) end
      end
    end
  end

  --- Moves: Arcane Barrier is an additional cost to move into or out of its location.
  local moveBase = R.moveInv
  function R.moveInv(inv, b, opts)
    opts = opts or {}
    local a = R.locOf(inv)
    if not opts.teleport and a and b and a ~= b and not FX.barrierCost(inv, a, b) then return false end
    if inv.defeated or R.G.ended then return false end
    return moveBase(inv, b, opts)
  end
end
