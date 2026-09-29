-- The player side (designer tooling): the five investigators of The Still
-- Hour (their abilities, elder signs, signature cards and weaknesses, from
-- the campaign's card data) and the level-0 SCED player cards the starting
-- decks use (tools/play_engine/decks.py picks them from the save's own
-- player-card bag; their effects are encoded here by name).

return function(R, T)
  local E = T.E
  local P = {}
  R.P = P

  -- soak (health, sanity) of allies and armor
  local SOAK = { ["Guard Dog"] = { 3, 1 }, ["Beat Cop"] = { 2, 2 }, ["Dr. Milan Christopher"] = { 1, 2 },
                 ["Stray Cat"] = { 1, 1 }, ["Leo De Luca"] = { 2, 2 }, ["Leather Coat"] = { 2, 0 },
                 ["Holy Rosary"] = { 0, 2 } }
  -- uses when played
  local USES = { [".45 Automatic"] = 4, ["Flashlight"] = 3, ["First Aid"] = 3, ["Shrivelling"] = 4,
                 ["The Bell of Ambergrove"] = 3, ["The Lexicon of the Hour"] = 0 }
  -- constant +skill while in play: name -> {skill, amount, when}
  local CONST = {
    ["Holy Rosary"] = { "wil", 1 }, ["Beat Cop"] = { "com", 1 }, ["Dr. Milan Christopher"] = { "int", 1 },
    ["Magnifying Glass"] = { "int", 1, "investigate" },
  }
  -- resource-for-skill talents: name -> skills they boost (1 resource: +1)
  local TALENT = { ["Physical Training"] = { wil = true, com = true }, ["Hard Knocks"] = { com = true, agi = true },
                   ["Dig Deep"] = { wil = true, agi = true }, ["Hyperawareness"] = { int = true, agi = true },
                   ["Arcane Studies"] = { wil = true, int = true } }
  -- weapons: name -> {skill bonus, extra damage, uses?, skill used}
  local WEAPON = { ["Machete"] = { 1, 1 }, [".45 Automatic"] = { 1, 1, true }, ["Knife"] = { 1, 0 },
                   ["Switchblade"] = { 0, 0 }, ["Baseball Bat"] = { 2, 1 }, ["Shrivelling"] = { 2, 1, true, "wil" } }
  P.WEAPON = WEAPON
  P.CODED = {}
  for _, t in ipairs({ SOAK, USES, CONST, TALENT, WEAPON }) do for k in pairs(t) do P.CODED[k] = true end end
  for _, n in ipairs({ "Vicious Blow", "Deduction", "Guts", "Perception", "Overpower", "Manual Dexterity",
                       "Unexpected Courage", "Fearless", "Opportunist", "Survival Instinct", "Emergency Cache",
                       "Working a Hunch", "Evidence!", "Dodge", "Elusive", "Sneak Attack", "Mind over Matter",
                       "Ward of Protection", "Blinding Light", "Drawn to the Flame", "Lucky!", "Cunning Distraction",
                       "Rabbit's Foot", "Pickpocketing", "Old Book of Lore", "Medical Texts", "First Aid",
                       "Paranoia", "Amnesia", "Haunted", "Psychosis", "Hypochondria", "Mob Enforcer",
                       "Silver Twilight Acolyte", "Stubborn Detective", "Indebted", "Internal Injury", "Chronophobia" }) do
    P.CODED[n] = true
  end
  -- approximations (reported)
  P.APPROX = {
    ["Old Book of Lore"] = "draws 1 card (the search of the top 3 is not modelled)",
    ["Stubborn Detective"] = "Hunter enemy (fight 3, evade 2, health 2, 1 damage); its text-box blanking is not modelled",
    ["Silver Twilight Acolyte"] = "Hunter enemy; after it attacks, 1 doom on the current Hour, which advances it (threshold 1)",
    ["Leo De Luca"] = "1 additional action each turn",
    ["Opportunist"] = "returns to hand when the test succeeds by 3 or more",
    ["Medical Texts"] = "heals 1 damage on a successful [int] (2) test, else 1 damage",
    ["Marked Deck"] = "played as an asset; neither ability is used by the AI",
    ["Lucky Compass"] = "used as a move that provokes no attacks of opportunity when engaged; its Knowledge-district jump is not used",
    ["Nobody Believes Her"] = "blocks commits from others and deals 1 horror if alone; other investigators' abilities still reach her (Elias's redirect)",
    ["Recollections"] = "not in the starting decks (bought between loops); only Foreknowledge, Muscle Memory and I've Done This Before are encoded",
    ["The walker's ring / The walkers keep their ring"] = "not in any representative campaign state, so not encoded",
    ["The Ambergrove Lamp"] = "+1 [agi] to evade at its location; its [action] (peek and move) is not used by the AI",
  }

  local BASIC_ENEMY = {
    ["Mob Enforcer"] = { fight = 4, evade = 3, health = 4, damage = 1, horror = 0, text = "Hunter." },
    ["Silver Twilight Acolyte"] = { fight = 2, evade = 3, health = 3, damage = 0, horror = 1, text = "Hunter." },
    ["Stubborn Detective"] = { fight = 3, evade = 2, health = 2, damage = 1, horror = 0, text = "Hunter." },
  }

  ------------------------------------------------------------ setup --

  --- A fresh investigator for a game: stats (aged, from the Control),
  -- deck, opening hand, 5 resources.
  function P.newInvestigator(idx, id, color, cardObj, mini, controlStats, deckData, weakness)
    local c = R.card(id)
    local inv = {
      idx = idx, id = id, name = c.name or id, color = color, card = cardObj, mini = mini,
      stats = { wil = c.wil, int = c.int, com = c.com, agi = c.agi },
      health = c.health, sanity = c.sanity, damage = 0, horror = 0, resources = 5, clues = 0, clueTokens = {},
      hand = {}, deck = {}, discard = {}, assets = {}, threat = {}, memory = 0, round = {}, loopUsed = {},
      failedTypes = {}, testedTypes = {}, pendingYears = 0, compassMemory = 0, actionsTaken = 0,
    }
    if controlStats then
      inv.stats = { wil = controlStats.wil, int = controlStats.int, com = controlStats.com, agi = controlStats.agi }
      inv.health, inv.sanity = controlStats.health, controlStats.sanity
      if (R.WHATIF or {}).soloBonus and R.G.n == 1 then
        inv.health, inv.sanity = inv.health + R.WHATIF.soloBonus, inv.sanity + R.WHATIF.soloBonus
      end
    end
    for _, card in ipairs(deckData.cards) do inv.deck[#inv.deck + 1] = card end
    for _, s in ipairs(deckData.signatures) do inv.deck[#inv.deck + 1] = s end
    if weakness then inv.deck[#inv.deck + 1] = weakness end
    R.shuffle(inv.deck)
    -- opening hand: weaknesses drawn are set aside and replaced, then shuffled back
    local aside = {}
    while #inv.hand < 5 and #inv.deck > 0 do
      local card = table.remove(inv.deck)
      if card.weakness then aside[#aside + 1] = card else inv.hand[#inv.hand + 1] = card end
    end
    for _, w in ipairs(aside) do inv.deck[#inv.deck + 1] = w end
    R.shuffle(inv.deck)
    if weakness and weakness.name == "Indebted" then inv.resources = inv.resources - 2 end
    return inv
  end

  ------------------------------------------------------------ cards --

  function P.draw(inv, n, why)
    for _ = 1, n or 1 do
      if inv.defeated then return end
      if #inv.deck == 0 then
        -- Rules Reference: shuffle the discard pile back, take 1 horror
        for _, c in ipairs(inv.discard) do inv.deck[#inv.deck + 1] = c end
        inv.discard = {}
        R.shuffle(inv.deck)
        R.hurt(inv, 0, 1, "empty deck")
        if #inv.deck == 0 then return end
      end
      local card = table.remove(inv.deck)
      if card.weakness then
        P.weakness(inv, card)
      else
        inv.hand[#inv.hand + 1] = card
      end
    end
  end

  function P.discardFromHand(inv, card)
    for i, c in ipairs(inv.hand) do
      if c == card then table.remove(inv.hand, i) break end
    end
    inv.discard[#inv.discard + 1] = card
  end

  function P.findAsset(inv, name)
    for _, a in ipairs(inv.assets) do if a.name == name then return a end end
    return nil
  end
  function P.lampInPlay()
    for _, inv in ipairs(R.G.inv) do if not inv.defeated and P.findAsset(inv, "The Ambergrove Lamp") then return true end end
    return false
  end

  function P.handHasIcon(inv, icons)
    for _, c in ipairs(inv.hand) do
      for _, k in ipairs(icons) do if (c.icons or {})[k] and c.icons[k] > 0 then return true end end
    end
    return false
  end

  --- Put an asset from hand into play (pays its cost).
  function P.playAsset(inv, card)
    P.discardFromHand(inv, card)
    table.remove(inv.discard)          -- it goes into play, not the discard
    inv.resources = inv.resources - (card.cost or 0)
    local a = { rec = card, name = card.name, uses = USES[card.name] or (card.uses and card.uses[1] and card.uses[1].count) or 0,
                exhausted = false, dmg = 0, hor = 0 }
    local s = SOAK[card.name]
    if s then a.hp, a.sp = s[1], s[2] end
    -- one ally slot, two hand slots (Baseball Bat takes both), one arcane, one accessory, one body
    if card.slot then
      local want, cap = card.slot, 1
      if card.slot == "Hand" then cap = 2 end
      local used = 0
      for _, x in ipairs(inv.assets) do
        local s2 = x.rec.slot
        if s2 == want or (want == "Hand" and s2 == "Hand x2") then used = used + ((s2 == "Hand x2") and 2 or 1) end
      end
      if want == "Hand x2" then want, cap = "Hand", 2 ; used = used + 1 end
      if used >= cap then
        -- replace the oldest in that slot
        for i, x in ipairs(inv.assets) do
          if x.rec.slot == card.slot or (card.slot:find("Hand") and tostring(x.rec.slot):find("Hand")) then
            table.remove(inv.assets, i)
            inv.discard[#inv.discard + 1] = x.rec
            break
          end
        end
      end
    end
    inv.assets[#inv.assets + 1] = a
    R.G.metrics.cards_played = R.G.metrics.cards_played + 1
    R.log("%s plays %s", inv.name, card.name)
    return a
  end

  ------------------------------------------------------------ weaknesses --

  function P.weakness(inv, card)
    local G = R.G
    local n = card.name
    G.metrics.weaknesses_drawn = G.metrics.weaknesses_drawn + 1
    R.log("%s draws weakness %s", inv.name, n)
    inv.discard[#inv.discard + 1] = card
    if card.id == "sthr-eighthgrave" then
      if (inv.memory or 0) > 0 then
        R.hurt(inv, 0, math.min(4, inv.memory), "The Eighth Grave")
      else
        local c = T.searchEncounter(function(md) return R.hasTrait(R.card(md.id), "Echo") and R.card(md.id).type == "Enemy" end)
        if c then
          local en = R.spawnEnemy(c, R.locOf(inv), nil, { want = "engaged with Elias" })
          en.wakeLoop = true
          en.engaged = inv
          R.placeEnemy(en)
        else
          R.hurt(inv, 0, 2, "The Eighth Grave")
        end
        local enc = T.encounterDeck()
        if enc and enc.type == "Deck" then enc.shuffle() end
      end
    elseif card.id == "sthr-untranslatable" then
      local banked = R.state().memory or 0
      local n2 = math.min(5, math.ceil(banked / 2))
      if n2 > 0 then R.hurt(inv, 0, n2, "Untranslatable") end
    elseif card.id == "sthr-debtofhours" then
      local band = R.band()
      if band == "Noticed" then
        if R.stage() >= 3 then R.hurt(inv, 0, 2, "The Debt of Hours") else T.ctl("Appointed") ; R.touch() end
      elseif band == "Glitch" then
        R.hurt(inv, 0, 2, "The Debt of Hours")
      else
        R.raise(1, "The Debt of Hours")
      end
    elseif card.id == "sthr-nobodybelieves" then
      inv.round.nobodyBelieves = true
      local alone = #R.investigatorsAt(R.locOf(inv)) <= 1
      if alone then R.hurt(inv, 0, 1, "Nobody Believes Her") end
    elseif card.id == "sthr-housewins" then
      table.remove(inv.discard)
      local def = R.card("sthr-housewins")
      local en = P.spawnWeaknessEnemy(inv, card, def, "most clues")
    elseif n == "Paranoia" then
      inv.resources = 0
    elseif n == "Amnesia" then
      while #inv.hand > 1 do inv.discard[#inv.discard + 1] = table.remove(inv.hand) end
    elseif n == "Haunted" or n == "Psychosis" or n == "Hypochondria" or n == "Internal Injury" or n == "Chronophobia" then
      table.remove(inv.discard)
      inv.threat[n] = card
    elseif BASIC_ENEMY[n] then
      table.remove(inv.discard)
      P.spawnWeaknessEnemy(inv, card, BASIC_ENEMY[n], nil)
    end
  end

  --- A weakness enemy (not an encounter card): a stand-in card object on the
  -- table, spawned engaged with its owner (or where its text says).
  function P.spawnWeaknessEnemy(inv, card, def, spawnRule)
    local G = R.G
    local L = R.locOf(inv)
    if spawnRule == "most clues" then
      local best, bc
      for _, x in ipairs(G.locList) do if not x.closed then local c = R.clues(x) if bc == nil or c > bc then best, bc = x, c end end end
      L = best or L
    end
    local p = L.obj.getPosition()
    local obj = T.E.spawnData({ Name = "Card", Nickname = card.name, GMNotes = T.J.encode({ id = card.id or card.sced, type = "Enemy" }),
                                Transform = { posX = p.x, posY = p.y + 1, posZ = p.z + 2.4, rotX = 0, rotY = 270, rotZ = 0,
                                              scaleX = 1, scaleY = 1, scaleZ = 1 } }, {}, "campaign")
    T.E.run(0.1)
    local en = { obj = obj, id = card.id or ("weakness:" .. card.name), name = card.name, def = def, loc = L.guid, damage = 0,
                 exhausted = false, engaged = (spawnRule == nil) and inv or nil, uid = (G.nextEnemy or 0) + 1, weakness = true, owner = inv }
    G.nextEnemy = en.uid
    G.enemies[#G.enemies + 1] = en
    R.placeEnemy(en)
    R.engageAt(L)
    return en
  end

  ------------------------------------------------------------ skills --

  --- Constant bonuses from assets in play for this test.
  function P.staticBonus(inv, skill, opts)
    local b = 0
    for _, a in ipairs(inv.assets) do
      local c = CONST[a.name]
      if c and c[1] == skill and (c[3] == nil or c[3] == opts.kind) then b = b + c[2] end
      if a.name == "The Ambergrove Lamp" then end
    end
    if opts.kind == "evade" then
      for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
        if P.findAsset(x, "The Ambergrove Lamp") then b = b + 1 break end
      end
    end
    if opts.weapon then
      local w = WEAPON[opts.weapon.name]
      if w then b = b + w[1] end
    end
    return b
  end

  --- Optional boosts available for a test, cheapest first: {gain, pay = fn, kind}.
  function P.boosts(inv, skill, opts)
    local out = {}
    for _, a in ipairs(inv.assets) do
      local t = TALENT[a.name]
      if t and t[skill] and inv.resources > 0 then
        out[#out + 1] = { gain = 1, cost = "resource", repeatable = true, asset = a, pay = function() inv.resources = inv.resources - 1 end }
      end
      if a.name == "The Lexicon of the Hour" and skill == "int" and not a.exhausted and a.uses > 0 then
        out[#out + 1] = { gain = 2, cost = "secret", pay = function() a.exhausted = true ; a.uses = a.uses - 1 end }
      end
    end
    -- Seraphine: raise Dissonance by 1: +2 (limit twice per round)
    if inv.id == "sthrseraphine" and (inv.round.sera or 0) < 2 and R.G.phase == "investigation" and R.G.turnOf == inv then
      out[#out + 1] = { gain = 2, cost = "dissonance", pay = function() P.seraphine(inv) end }
    end
    return out
  end

  function P.seraphine(inv)
    inv.round.sera = (inv.round.sera or 0) + 1
    R.raise(1, "Seraphine's ability (cost)", inv)
    inv.lastTurn.paidDiss = true
    if inv.round.sera == 2 then R.addMemory(inv, 1, "Seraphine: second use in a round") end
  end

  --- Cards in hand that could commit to this skill: {card, icons}.
  function P.commitables(inv, skill, opts)
    local out = {}
    for _, c in ipairs(inv.hand) do
      if c.type == "Skill" or (c.icons and ((c.icons[skill] or 0) + (c.icons.wild or 0)) > 0) then
        local n = (c.icons and ((c.icons[skill] or 0) + (c.icons.wild or 0))) or 0
        if c.name == "I've Done This Before" and inv.failedTypes[skill] then n = 3 end
        if c.name == "Muscle Memory" and inv.testedTypes[skill] then n = 2 end
        if c.name == "Foreknowledge" and (inv.memory or 0) > 0 then n = 3 end
        if c.name == "I've Done This Before" and opts.helper then n = 0 end
        if n > 0 then
          -- skill cards are the ones meant to be committed; others only when needed
          local value = (c.type == "Skill") and 1 or 3
          if c.type == "Asset" and (c.cost or 0) <= inv.resources then value = 4 end
          out[#out + 1] = { card = c, icons = n, value = value }
        end
      end
    end
    table.sort(out, function(a, b) if a.value ~= b.value then return a.value < b.value end return a.icons > b.icons end)
    return out
  end

  --- The investigator's elder sign: its modifier (effects are applied after).
  function P.elderSign(inv)
    local G = R.G
    if inv.id == "sthrelias" then return (inv.memory or 0) >= 3 and 3 or 1 end
    if inv.id == "sthrayako" then return 2 end
    if inv.id == "sthrcass" then return 1 end
    if inv.id == "sthrseraphine" then return math.min(5, R.dissonance()) end
    if inv.id == "sthrbirdie" then return inv.round.failed and 3 or 1 end
    return 1
  end
  function P.elderSignAfter(inv)
    if inv.id == "sthrelias" and (inv.memory or 0) >= 3 then
      R.heal(inv, 1, R.knows("the-keepers-ninth-death") and 1 or 0)
    elseif inv.id == "sthrayako" then
      P.draw(inv, 1)
    elseif inv.id == "sthrcass" then
      inv.resources = inv.resources + math.min(3, inv.memory or 0)
    elseif inv.id == "sthrseraphine" then
      local x = math.min(5, R.dissonance())
      if x > 0 then R.lower(x, "Seraphine's elder sign") end
    end
  end

  --- After a skill test: committed cards' effects, then the investigator's reactions.
  function P.afterTest(inv, ok, margin, skill, opts, committed)
    local G = R.G
    for _, c in ipairs(committed) do
      local n = c.card.name
      if ok and (n == "Guts" or n == "Perception" or n == "Overpower" or n == "Manual Dexterity") then P.draw(c.owner, 1) end
      if ok and n == "Fearless" then R.heal(c.owner, 0, 1) end
      if n == "Muscle Memory" and c.owner.testedTypes[skill] then P.draw(c.owner, 1) end
      if n == "Opportunist" and ok and margin >= 3 then
        c.owner.hand[#c.owner.hand + 1] = c.card
      else
        c.owner.discard[#c.owner.discard + 1] = c.card
      end
      if c.card.traits and tostring(c.card.traits):find("Recollection", 1, true) then c.owner.lastTurn.recollection = true end
    end
    if ok then
      -- Ayako: after you succeed at an [int] test: 1 Memory (limit once per round)
      if inv.id == "sthrayako" and skill == "int" and not inv.round.ayako then
        inv.round.ayako = true
        R.addMemory(inv, 1, "Ayako: [int] success")
      end
      local lex = P.findAsset(inv, "The Lexicon of the Hour")
      if lex and skill == "int" and margin >= 2 and lex.uses < 5 then lex.uses = lex.uses + 1 end
    else
      inv.round.failed = true
      inv.failedTypes[skill] = true
      if inv.id == "sthrbirdie" and margin <= -2 and not inv.round.birdie then
        inv.round.birdie = true
        R.addMemory(inv, 1, "Birdie: failed by 2 or more")
      end
      local foot = P.findAsset(inv, "Rabbit's Foot")
      if foot and not foot.exhausted then foot.exhausted = true ; P.draw(inv, 1) end
      R.FX.afterFail(inv)
    end
    inv.testedTypes[skill] = true
  end

  --- "When you would fail": Lucky!, then Birdie's once-per-loop save. Returns the new margin or nil.
  function P.wouldFail(inv, margin, tokenName, opts)
    if tokenName == "Auto-fail" then
      if inv.id == "sthrbirdie" and not inv.loopUsed.birdieSave and (inv.memory or 0) >= 3 and opts.important then
        inv.loopUsed.birdieSave = true
        R.addMemory(inv, -3, "Birdie: succeed instead")
        T.api("shApiTally", { id = inv.id, kind = "spent", delta = 3 })
        return 0
      end
      return nil
    end
    if margin >= -2 and inv.resources >= 1 then
      for _, c in ipairs(inv.hand) do
        if c.name == "Lucky!" then
          P.discardFromHand(inv, c)
          inv.resources = inv.resources - 1
          R.log("%s plays Lucky!", inv.name)
          return margin + 2
        end
      end
    end
    if inv.id == "sthrbirdie" and not inv.loopUsed.birdieSave and (inv.memory or 0) >= 3 and opts.important then
      inv.loopUsed.birdieSave = true
      R.addMemory(inv, -3, "Birdie: succeed instead")
      T.api("shApiTally", { id = inv.id, kind = "spent", delta = 3 })
      return 0
    end
    return nil
  end

  --- Seen This Hand Before (Cass): cancel a revealed token that makes the test fail.
  function P.cancelToken(inv, tokenName, marginWith, marginWithout, opts)
    if marginWith >= 0 then return false end
    if marginWithout < 0 then return false end
    if not opts.important then return false end
    for _, c in ipairs(inv.hand) do
      if c.name == "Seen This Hand Before" and inv.resources >= 1 then
        P.discardFromHand(inv, c)
        inv.resources = inv.resources - 1 + ((tonumber(tokenName) ~= nil) and 2 or 3)
        R.log("%s cancels %s with Seen This Hand Before", inv.name, tokenName)
        return true
      end
    end
    return false
  end

  ------------------------------------------------------------ defeat --

  function P.tryIGetOut(inv)
    if inv.id ~= "sthrbirdie" or inv.loopUsed.igetout then return false end
    for _, c in ipairs(inv.hand) do
      if c.name == "\"I Get Out\"" or c.name == "I Get Out" then
        inv.loopUsed.igetout = true
        P.discardFromHand(inv, c)
        inv.damage = inv.health - 1
        inv.horror = inv.sanity - 1
        for _, en in ipairs(R.G.enemies) do if en.engaged == inv then en.engaged = nil ; R.placeEnemy(en) end end
        if R.G.appointed.engaged == inv then R.G.appointed.engaged = nil end
        local here = R.locOf(inv)
        local to = R.AI.chooseMove(inv, here, true)
        if to then R.moveInv(inv, to, { noAoO = true }) end
        local compass = P.findAsset(inv, "Lucky Compass")
        if compass then compass.memory = (compass.memory or 0) + 1 ; R.addMemory(inv, 1, "I Get Out (Lucky Compass)") end
        R.log("Birdie: I Get Out")
        return true
      end
    end
    return false
  end

  ------------------------------------------------------------ cancels --

  --- It Means 'Wait' against an effect ("losthour", "slippage", "crossing",
  -- "whisper", "appointed-attack", "approach-horror"); returns true if cancelled.
  function P.itMeansWait(target, what)
    local G = R.G
    if (R.state().memory or 0) < 3 then return false end
    local want = { losthour = true, crossing = true, ["appointed-attack"] = true }
    if not want[what] then return false end
    for _, inv in ipairs(R.aliveInvs()) do
      if inv.id == "sthrayako" then
        for _, c in ipairs(inv.hand) do
          if c.name == "It Means 'Wait'" then
            if what == "appointed-attack" and target ~= inv then return false end
            P.discardFromHand(inv, c)
            G.metrics.itmeanswait = G.metrics.itmeanswait + 1
            R.log("It Means 'Wait' cancels %s", what)
            return true
          end
        end
      end
    end
    return false
  end
  function P.itMeansWaitHour(h)
    if h ~= 8 and h ~= 6 then return false end
    return P.itMeansWait(nil, "losthour")
  end

  --- Lexicon (Static treachery) and Ward of Protection (any treachery).
  function P.cancelTreachery(inv, id, def)
    local G = R.G
    local bad = { ["sthr-losthour"] = 3, ["sthr-crossing"] = 3, ["sthr-thirteen"] = 3, ["sthr-wheelsturn"] = 2,
                  ["sthr-yearinanight"] = 2, ["sthr-samespeech"] = 1, ["sthr-appointedwhisper"] = 2,
                  ["sthr-deadair"] = 1, ["sthr-loopnotices"] = 2, ["sthr-slippage"] = 0 }
    local worth = bad[id] or 0
    if worth <= 0 then return false end
    if R.hasTrait(def, "Static") then
      for _, x in ipairs(R.aliveInvs()) do
        local lex = P.findAsset(x, "The Lexicon of the Hour")
        if lex and not lex.exhausted and lex.uses > 0 then
          lex.exhausted = true ; lex.uses = lex.uses - 1
          R.log("The Lexicon cancels %s", def.name or id)
          return true
        end
      end
    end
    if id == "sthr-losthour" or id == "sthr-crossing" or id == "sthr-appointedwhisper" then
      if P.itMeansWait(inv, id == "sthr-losthour" and "losthour" or "crossing") then return true end
    end
    if worth >= 2 and inv.resources >= 1 and inv.horror < inv.sanity - 2 then
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

  --- Dodge: cancel an enemy attack against an investigator at your location.
  function P.dodge(target, en)
    for _, x in ipairs(R.investigatorsAt(R.locOf(target))) do
      if x.resources >= 1 then
        for _, c in ipairs(x.hand) do
          if c.name == "Dodge" and ((en.def.damage or 0) + (en.def.horror or 0) >= 2) then
            P.discardFromHand(x, c)
            x.resources = x.resources - 1
            R.log("%s cancels %s's attack with Dodge", x.name, en.name)
            return true
          end
        end
      end
    end
    return false
  end

  ------------------------------------------------------------ hooks --

  function P.afterDefeatEnemy(inv, en)
    -- Evidence!: discover 1 clue at your location
    for _, c in ipairs(inv.hand) do
      if c.name == "Evidence!" and inv.resources >= 1 and R.clues(R.locOf(inv)) > 0 then
        P.discardFromHand(inv, c)
        inv.resources = inv.resources - 1
        R.discover(inv, R.locOf(inv), 1)
        break
      end
    end
  end

  function P.onKnowledge(fact)
    -- Cassandra's Notebook is not in the starting decks
  end

  function P.onHourReachedPlayers(h) end

  --- End of an investigator's turn: Internal Injury / Chronophobia.
  function P.endTurn(inv)
    if inv.threat["Internal Injury"] then R.hurt(inv, 1, 0, "Internal Injury", { direct = true }) end
    if inv.threat["Chronophobia"] then R.hurt(inv, 0, 1, "Chronophobia", { direct = true }) end
  end

  return P
end
