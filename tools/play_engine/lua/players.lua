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
                 ["Holy Rosary"] = { 0, 2 },
                 -- XP cards (decks.py UPGRADES)
                 ["Elder Sign Amulet (3)"] = { 0, 4 }, ["Bulletproof Vest (3)"] = { 4, 0 }, ["Hired Muscle (1)"] = { 3, 1 },
                 ["Peter Sylvestre (2)"] = { 1, 3 } }
  -- uses when played
  local USES = { [".45 Automatic"] = 4, ["Flashlight"] = 3, ["First Aid"] = 3, ["Shrivelling"] = 4,
                 ["The Bell of Ambergrove"] = 3, ["The Lexicon of the Hour"] = 0, ["Stolen Minute"] = 2,
                 ["Shotgun (4)"] = 2, ["Lightning Gun (5)"] = 3, [".41 Derringer (2)"] = 3, ["Chicago Typewriter (4)"] = 4,
                 ["Shrivelling (3)"] = 4, ["Shrivelling (5)"] = 4 }
  -- constant +skill while in play: name -> {skill, amount, when}
  local CONST = {
    ["Holy Rosary"] = { "wil", 1 }, ["Beat Cop"] = { "com", 1 }, ["Dr. Milan Christopher"] = { "int", 1 },
    ["Magnifying Glass"] = { "int", 1, "investigate" },
    ["Hired Muscle (1)"] = { "com", 1 }, ["Peter Sylvestre (2)"] = { "agi", 1 },
  }
  -- resource-for-skill talents: name -> skills they boost (1 resource: +1)
  local TALENT = { ["Physical Training"] = { wil = true, com = true }, ["Hard Knocks"] = { com = true, agi = true },
                   ["Dig Deep"] = { wil = true, agi = true }, ["Hyperawareness"] = { int = true, agi = true },
                   ["Arcane Studies"] = { wil = true, int = true },
                   ["Higher Education (3)"] = { wil = true, int = true }, ["Scrapper (3)"] = { com = true, agi = true },
                   ["Streetwise (3)"] = { int = true, agi = true } }
  -- weapons: name -> {skill bonus, extra damage, uses?, skill used}
  local WEAPON = { ["Machete"] = { 1, 1 }, [".45 Automatic"] = { 1, 1, true }, ["Knife"] = { 1, 0 },
                   ["Switchblade"] = { 0, 0 }, ["Baseball Bat"] = { 2, 1 }, ["Shrivelling"] = { 0, 1, true, "wil" },
                   ["Shotgun (4)"] = { 3, 2, true }, ["Lightning Gun (5)"] = { 5, 2, true }, [".41 Derringer (2)"] = { 2, 1, true },
                   ["Chicago Typewriter (4)"] = { 2, 2, true }, ["Switchblade (2)"] = { 2, 1 },
                   ["Shrivelling (3)"] = { 2, 1, true, "wil" }, ["Shrivelling (5)"] = { 3, 2, true, "wil" } }
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
    ["Finale aftermath"] = "contest and eligible ending are measured; ending choices and epilogues are not simulated, and no ordinary interlude is applied after a finale",
    ["Story assets"] = "sequential-objective policy carries at most one story asset per investigator",
    ["Old Book of Lore"] = "draws 1 card (the search of the top 3 is not modelled)",
    ["Stubborn Detective"] = "Hunter enemy (fight 3, evade 2, health 2, 1 damage); its text-box blanking is not modelled",
    ["Silver Twilight Acolyte"] = "Hunter enemy; its doom is represented on the current Hour",
    ["Leo De Luca"] = "1 additional action each turn",
    ["Opportunist"] = "own tests only; returns on success by 3 (level 0) or 1 (level 2)",
    ["Medical Texts"] = "heals 1 damage on a successful [int] (2) test, else 1 damage",
    ["It Means 'Wait'"] = "policy cancels threatening own treacheries, Hour VI/VIII text or an attack on her; other legal Hours are not selected",
    ["Chicago Typewriter (4)"] = "+2 [com], +2 damage (extra actions spent for more not modelled)",
    ["Survival Instinct"] = "disengages other enemies on an evade success; the optional move is not selected",
    ["Survival Instinct (2)"] = "automatically evades other legal enemies on an evade success; the optional move is not selected",
    ["Magnifying Glass (1)"] = "fast play and +1 intellect; the optional return to hand is not selected",
  }

  local BASIC_ENEMY = {
    ["Mob Enforcer"] = { fight = 4, evade = 3, health = 4, damage = 1, horror = 0, text = "Hunter." },
    ["Silver Twilight Acolyte"] = { fight = 2, evade = 3, health = 3, damage = 0, horror = 1, text = "Hunter." },
    ["Stubborn Detective"] = { fight = 3, evade = 2, health = 2, damage = 1, horror = 0, text = "Hunter." },
  }

  -- A reproducible, role-based mulligan policy. These are choices, not extra
  -- cards or free setup: rejected cards stay aside until replacements are drawn.
  function P.keepOpening(inv, card, kept)
    local n=card.name
    if kept[n] then return false end
    local useful = n == "Emergency Cache" or n == "Leather Coat" or n == "Holy Rosary"
      or n == "Flashlight" or n == "Magnifying Glass" or n == "The Ambergrove Lamp"
      or n == "The Lexicon of the Hour" or n == "Cassandra's Notebook" or n == "Stolen Minute"
      or n == "Leo De Luca" or n == "Marked Deck" or n == "Rabbit's Foot" or n == "Lucky Compass"
    if WEAPON[n] and (inv.id == "sthrelias" or inv.id == "sthrseraphine" or inv.id == "sthrbirdie") then
      if kept.weapon then return false end
      kept.weapon=true ; useful=true
    end
    if card.slot == "Ally" and n ~= "Stray Cat" then
      if kept.ally then return false end
      kept.ally=true ; useful=true
    end
    if useful then kept[n]=true end
    return useful
  end

  ------------------------------------------------------------ setup --

  --- A fresh investigator for a game: stats (aged, from the Control),
  -- deck, opening hand, 5 resources.
  function P.newInvestigator(idx, id, color, cardObj, mini, controlStats, deckData, weakness)
    local c = R.card(id)
    local inv = {
      idx = idx, id = id, name = c.name or id, color = color, card = cardObj, mini = mini,
      stats = { wil = c.wil, int = c.int, com = c.com, agi = c.agi },
      health = c.health, sanity = c.sanity, damage = 0, horror = 0, resources = 5, clues = 0, clueTokens = {},
      hand = {}, deck = {}, discard = {}, assets = {}, threat = {}, memory = 0, cardMemory = 0, round = {}, loopUsed = {},
      failedTypes = {}, testedTypes = {}, pendingYears = 0, compassMemory = 0, actionsTaken = 0, lastTurn = {},
    }
    if controlStats then
      inv.stats = { wil = controlStats.wil, int = controlStats.int, com = controlStats.com, agi = controlStats.agi }
      inv.health, inv.sanity = controlStats.health, controlStats.sanity
      -- The Control reads the printed card on the table (its GMNotes) and adds
      -- aging. If the campaign's card data has changed the printed maximum
      -- health or sanity since that card was packaged, play the current card.
      local md = cardObj and cardObj.getGMNotes and T.decode(cardObj.getGMNotes()) or nil
      if type(md) == "table" then
        if tonumber(md.health) and c.health then inv.health = inv.health + (c.health - md.health) end
        if tonumber(md.sanity) and c.sanity then inv.sanity = inv.sanity + (c.sanity - md.sanity) end
      end
      if (R.WHATIF or {}).soloBonus and R.G.n == 1 then
        inv.health, inv.sanity = inv.health + R.WHATIF.soloBonus, inv.sanity + R.WHATIF.soloBonus
      end
      if (R.WHATIF or {}).duoBonus and R.G.n == 2 then
        inv.health, inv.sanity = inv.health + R.WHATIF.duoBonus, inv.sanity + R.WHATIF.duoBonus
      end
    end
    for _, card in ipairs(deckData.cards) do
      if card.permanent or card.name == "Anchor Point" then
        inv.assets[#inv.assets + 1] = { name = card.name, rec = card, exhausted = false, uses = 0 }
        if card.name == "Anchor Point" then inv.sanity = inv.sanity + 1 end
      else inv.deck[#inv.deck + 1] = card end
    end
    for _, s in ipairs(deckData.signatures) do inv.deck[#inv.deck + 1] = s end
    if weakness then
      if weakness.permanent then inv.threat[weakness.name]=weakness
      else inv.deck[#inv.deck + 1] = weakness end
    end
    R.shuffle(inv.deck)
    -- opening hand: weaknesses drawn are set aside and replaced, then shuffled back
    local aside = {}
    while #inv.hand < 5 and #inv.deck > 0 do
      local card = table.remove(inv.deck)
      if card.weakness then aside[#aside + 1] = card else inv.hand[#inv.hand + 1] = card end
    end
    local keep, kept = {}, {}
    for _, card in ipairs(inv.hand) do
      if P.keepOpening(inv,card,kept) then keep[#keep+1]=card else aside[#aside+1]=card end
    end
    inv.hand=keep
    while #inv.hand < 5 and #inv.deck > 0 do
      local card=table.remove(inv.deck)
      if card.weakness then aside[#aside+1]=card else inv.hand[#inv.hand+1]=card end
    end
    for _, w in ipairs(aside) do inv.deck[#inv.deck + 1] = w end
    R.shuffle(inv.deck)
    if weakness and weakness.name == "Indebted" then inv.resources = inv.resources - 2 end
    return inv
  end

  ------------------------------------------------------------ cards --

  function P.draw(inv, n, why)
    local drawn = {}
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
        drawn[#drawn + 1] = card
      end
    end
    return drawn
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
    inv.resources = inv.resources - P.playCost(inv, card)
    if inv.round.recollectionDiscount then inv.round.recollectionDiscount[card] = nil end
    local a = { rec = card, name = card.name, uses = USES[card.name] or (card.uses and card.uses[1] and card.uses[1].count) or 0,
                exhausted = false, dmg = 0, hor = 0 }
    local s = SOAK[card.name]
    if s then a.hp, a.sp = s[1], s[2] end
    if card.name == "Beat Cop" and (card.level or 0) >= 2 then a.hp = 3 end
    -- Two hand and two arcane slots; one ally, accessory and body. A two-slot
    -- asset replaces as many assets as necessary, not just the oldest one.
    if card.slot then
      local function slot(s)
        if not s then return nil,0 end
        return s:gsub(" x2$",""), s:find(" x2$",1) and 2 or 1
      end
      local want, required = slot(card.slot)
      local cap = (want == "Hand" or want == "Arcane") and 2 or 1
      local used = 0
      for _, x in ipairs(inv.assets) do
        local s2,n2 = slot(x.rec.slot)
        if s2 == want then used = used + n2 end
      end
      while used + required > cap do
        local removed = false
        for i, x in ipairs(inv.assets) do
          local s2,n2 = slot(x.rec.slot)
          if s2 == want then
            table.remove(inv.assets, i)
            inv.discard[#inv.discard + 1] = x.rec
            used,removed = used-n2,true
            break
          end
        end
        if not removed then break end
      end
    end
    inv.assets[#inv.assets + 1] = a
    R.syncMemory(inv)
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
      if R.investigatorMemory(inv) > 0 then
        -- 1 horror per Memory on Elias (maximum 2), then remove 1 Memory from him
        R.hurt(inv, 0, math.min(2, R.investigatorMemory(inv)), "The Eighth Grave")
        R.addMemory(inv, -1, "The Eighth Grave")
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
      local n2 = math.min((R.WHATIF or {}).untransMax or 5, 2 + math.floor(banked / 4))
      R.hurt(inv, 0, n2, "Untranslatable")
    elseif card.id == "sthr-debtofhours" then
      local band = R.band()
      R.hurt(inv, 0, 2, "The Debt of Hours")
      if band == "Noticed" then
        if R.stage() < 3 then T.ctl("Appointed") ; R.touch() end
      elseif band == "Calm" then
        R.raise(1, "The Debt of Hours")
      end
    elseif card.id == "sthr-nobodybelieves" then
      inv.round.nobodyBelieves = true
      -- 1 horror, 1 more if no other investigator is at her location
      local alone = #R.investigatorsAt(R.locOf(inv)) <= 1
      R.hurt(inv, 0, alone and 2 or 1, "Nobody Believes Her")
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
    if R.G.phase == "investigation" and inv.round.encyclopedia and inv.round.encyclopedia.skill == skill then b = b + 2 end
    for _, a in ipairs(inv.assets) do
      local c = CONST[a.name]
      if c and c[1] == skill and (c[3] == nil or c[3] == opts.kind) then b = b + c[2] end
      if a.name == "Peter Sylvestre (2)" and skill == "wil" then b = b + 1 end
      if a.name == "The Ambergrove Lamp" then end
    end
    -- a story asset's constant modifier (Bound Almanac: -1 [agi])
    local st = inv.story and R.FX.STORY[inv.story.id]
    if st and st[skill] then b = b + st[skill] end
    if opts.kind == "evade" then
      for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
        if (x == inv or not inv.round.nobodyBelieves) and P.findAsset(x, "The Ambergrove Lamp") then b = b + 1 break end
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
      local price, gain = a.name == "Streetwise (3)" and 2 or 1, a.name == "Streetwise (3)" and 3 or 1
      if a.name == "Higher Education (3)" then gain = 2 end
      if t and t[skill] and inv.resources >= price and (a.name ~= "Higher Education (3)" or #inv.hand >= 5) then
        out[#out + 1] = { gain = gain, price = price, cost = "resource", repeatable = true, asset = a,
          pay = function() inv.resources = inv.resources - price end }
      end
      if a.name == "The Lexicon of the Hour" and skill == "int" and not a.exhausted and a.uses > 0 then
        out[#out + 1] = { gain = 2, cost = "secret", pay = function()
          a.exhausted = true ; a.uses = a.uses - 1
          local repeated = P.afterOwnAbility(inv, { canRepeat=function() return a.uses > 0 end,
            resolve=function() a.uses=a.uses-1 end })
          return repeated and 2 or 0
        end }
      end
    end
    -- Seraphine: take 1 horror: +2 (limit twice per round)
    if inv.id == "sthrseraphine" and (inv.round.sera or 0) < 2 and R.G.phase == "investigation" and R.G.turnOf == inv then
      out[#out + 1] = { gain = 2, cost = "horror", pay = function() return P.seraphine(inv) end }
    end
    return out
  end

  function P.seraphine(inv, choice, asset, repeating)
    inv.round.sera = (inv.round.sera or 0) + 1
    R.hurt(inv, 0, 1, "Seraphine's ability (cost)", { direct = true })
    if choice == "action" then inv.actionsLeft = inv.actionsLeft + 1
    elseif choice == "ready" and asset then asset.exhausted = false end
    if not repeating then
      local repeated = P.afterOwnAbility(inv,{canRepeat=function() return inv.round.sera < 2 end,
        resolve=function() P.seraphine(inv,choice,asset,true) end})
      return not choice and repeated and 2 or 0
    end
  end

  --- Cards in hand that could commit to this skill: {card, icons}.
  function P.commitables(inv, skill, opts)
    local out = {}
    for _, c in ipairs(inv.hand) do
      if c.type == "Skill" or (c.icons and ((c.icons[skill] or 0) + (c.icons.wild or 0)) > 0) then
        local n = (c.icons and ((c.icons[skill] or 0) + (c.icons.wild or 0))) or 0
        if c.name == "I've Done This Before" and inv.failedTypes[skill] then n = 3 end
        if c.name == "Muscle Memory" then
          n = inv.testedTypes[skill] and 2 or 1
          if (skill == "com" or skill == "agi") and ((inv.years or 0) >= 5 or inv.bracket == "Weathered" or inv.bracket == "Elder" or inv.bracket == "Ancient") then n = n + 1 end
        end
        if c.name == "Foreknowledge" then n = ((inv.memory or 0) > 0) and 3 or 2 end
        if c.name == "I've Done This Before" and opts.helper then n = 0 end
        if c.name == "Opportunist" and opts.helper then n = 0 end
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

  -- One commit path for the test taker and helpers. Costs and "when committed"
  -- draws happen here, before the reveal, and a shared maximum applies to all.
  function P.commit(inv, entry, skill, opts, committed)
    local card = entry.card
    if card.name == "Foreknowledge" or card.name == "Guts" or card.name == "Perception"
       or card.name == "Overpower" or card.name == "Manual Dexterity" or card.name == "Unexpected Courage" then
      for _, c in ipairs(committed) do if c.card.name == card.name then return nil end end
    end
    P.discardFromHand(inv, card)
    table.remove(inv.discard)
    local c = { card = card, icons = entry.icons, owner = inv }
    if card.name == "Foreknowledge" then
      c.icons = 2
      if R.syncMemory(inv) >= 1 then
        R.addMemory(inv, -1, "Foreknowledge", "any")
        T.api("shApiTally", { id = inv.id, kind = "spent", delta = 1 })
        c.icons, c.memoryPaid = 3, true
      end
    elseif card.name == "Muscle Memory" and inv.testedTypes[skill] then c.drawOnSuccess = true end
    committed[#committed + 1] = c
    inv.lastCommitted = inv.lastCommitted or {}
    return c
  end

  -- These skills change the test taker's result, including when a helper
  -- committed them. Keep every copy and its printing rather than a boolean.
  function P.resultBonus(inv, name, margin)
    local n = 0
    for _, c in ipairs(inv.lastCommitted and inv.lastCommitted[name] or {}) do
      n = n + (((c.level or 0) >= 2 and margin >= 2) and 2 or 1)
    end
    return n
  end

  --- The investigator's elder sign: its modifier (effects are applied after).
  function P.elderSign(inv)
    local G = R.G
    if inv.id == "sthrelias" then return R.investigatorMemory(inv) >= 3 and 3 or 1 end
    if inv.id == "sthrayako" then return R.investigatorMemory(inv) >= 2 and 3 or 2 end
    if inv.id == "sthrcass" then return 1 end
    if inv.id == "sthrseraphine" then return math.min(3, R.investigatorMemory(inv)) end
    if inv.id == "sthrbirdie" then return inv.round.failed and 3 or 1 end
    return 1
  end
  function P.elderSignAfter(inv, modifier)
    if inv.id == "sthrelias" and R.investigatorMemory(inv) >= 3 then
      local healed = inv.damage > 0
      R.heal(inv, 1, healed and R.knows("the-keepers-ninth-death") and 1 or 0)
    elseif inv.id == "sthrayako" then
      local cards = P.draw(inv, 1) or {}
      for _, c in ipairs(cards) do
        if tostring(c.traits or ""):find("Recollection", 1, true) then
          inv.round.recollectionDiscount = inv.round.recollectionDiscount or {}
          inv.round.recollectionDiscount[c] = 2
        end
      end
    elseif inv.id == "sthrcass" then
      inv.resources = inv.resources + math.min(3, R.investigatorMemory(inv))
    elseif inv.id == "sthrseraphine" then
      -- +X, where X is the Memory on her (maximum +3): nothing is spent
    end
  end

  --- After a skill test: committed cards' effects, then the investigator's reactions.
  function P.afterTest(inv, ok, margin, skill, opts, committed)
    local G = R.G
    for _, c in ipairs(committed) do
      local n = c.card.name
      if ok and (n == "Guts" or n == "Perception" or n == "Overpower" or n == "Manual Dexterity") then P.draw(c.owner, 1) end
      if ok and n == "Fearless" then R.heal(c.owner, 0, (c.card.level or 0) >= 2 and margin >= 2 and 2 or 1) end
      if ok and n == "Foreknowledge" and c.memoryPaid then P.draw(c.owner, 1) end
      if ok and n == "Muscle Memory" and c.drawOnSuccess then P.draw(c.owner, 1) end
      if ok and n == "Survival Instinct" and opts.kind == "evade" then
        for _, en in ipairs(G.enemies) do
          if en.engaged == inv and en ~= opts.enemy then
            if (c.card.level or 0) < 2 then en.engaged = nil ; R.placeEnemy(en)
            elseif not R.cannotEvade(en) then
              en.exhausted,en.engaged = true,nil ; R.placeEnemy(en)
              G.metrics.evades = G.metrics.evades + 1 ; R.FX.onEvade(inv,en)
            end
          end
        end
      end
      if n == "Opportunist" and ok and margin >= ((c.card.level or 0) >= 2 and 1 or 3) then
        c.owner.hand[#c.owner.hand + 1] = c.card
      else
        c.owner.discard[#c.owner.discard + 1] = c.card
      end
      if c.card.traits and tostring(c.card.traits):find("Recollection", 1, true) then c.owner.lastTurn.recollection = true end
    end
    if ok then
      -- Ayako: after you succeed at an [int] test: 1 Memory (once per round, 3 per loop)
      if inv.id == "sthrayako" and skill == "int" then P.memoryReaction(inv, "Ayako: [int] success") end
      local lex = P.findAsset(inv, "The Lexicon of the Hour")
      if lex and skill == "int" and margin >= 2 and lex.uses < 4 then lex.uses = lex.uses + 1 end
    else
      inv.round.failed = true
      inv.failedTypes[skill] = true
      -- Birdie: after you fail by 2 or more: 1 Memory (once per round, 3 per loop)
      if inv.id == "sthrbirdie" and margin <= -2 then P.memoryReaction(inv, "Birdie: failed by 2 or more") end
      local foot = P.findAsset(inv, "Rabbit's Foot")
      if foot and not foot.exhausted then foot.exhausted = true ; P.draw(inv, 1) end
      R.FX.afterFail(inv)
    end
    inv.testedTypes[skill] = true
  end

  --- "When you would fail": Lucky!, then Birdie's once-per-loop save. Returns the new margin or nil.
  function P.wouldFail(inv, margin, tokenName, opts)
    if tokenName == "Auto-fail" then
      if inv.id == "sthrbirdie" and not inv.loopUsed.birdieSave and R.investigatorMemory(inv) >= 3 and opts.important then
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
          if (c.level or 0) >= 2 then P.draw(inv, 1) end
          return margin + 2
        end
      end
    end
    if inv.id == "sthrbirdie" and not inv.loopUsed.birdieSave and R.investigatorMemory(inv) >= 3 and opts.important then
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
        inv.resources = inv.resources - 1 + ((tonumber(tokenName) ~= nil) and 1 or 2)
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
        inv.damage = math.min(inv.damage, inv.health - 1)
        inv.horror = math.min(inv.horror, inv.sanity - 1)
        for _, en in ipairs(R.G.enemies) do if en.engaged == inv then en.engaged = nil ; R.placeEnemy(en) end end
        if R.G.appointed.engaged == inv then R.G.appointed.engaged = nil end
        local here = R.locOf(inv)
        local to = R.AI.chooseMove(inv, here, true)
        if to then R.moveInv(inv, to, { noAoO = true }) end
        local compass = P.findAsset(inv, "Lucky Compass")
        if compass then R.addMemory(inv, 1, "I Get Out (Lucky Compass)", compass) end
        if R.G.phase == "investigation" and R.G.turnOf == inv then inv.actionsLeft = 0 end
        R.log("Birdie: I Get Out")
        return true
      end
    end
    return false
  end

  ------------------------------------------------------------ cancels --

  --- It Means 'Wait' (Ayako, cost 1): cancel a non-weakness treachery she
  -- draws (then 1 horror), or, with 3+ banked Memory, an Hour's "When reached"
  -- text or an attack by The Appointed on her (then raise Dissonance by 1).
  -- what: "losthour" / "crossing" (her own draw), "hour", "appointed-attack".
  local function playIMW(inv, why, horror)
    for _, c in ipairs(inv.hand) do
      if c.name == "It Means 'Wait'" and inv.resources >= 1 then
        P.discardFromHand(inv, c)
        inv.resources = inv.resources - 1
        R.G.metrics.itmeanswait = R.G.metrics.itmeanswait + 1
        R.log("It Means 'Wait' cancels %s", why)
        if horror then R.hurt(inv, 0, 1, "It Means 'Wait'") else R.raise(1, "It Means 'Wait'") end
        return true
      end
    end
    return false
  end
  function P.itMeansWait(target, what)
    local ayako
    for _, inv in ipairs(R.aliveInvs()) do if inv.id == "sthrayako" then ayako = inv end end
    if not ayako then return false end
    if what == "treachery" or what == "losthour" or what == "crossing" then
      if target ~= ayako or ayako.horror >= ayako.sanity - 1 then return false end
      return playIMW(ayako, what, true)
    end
    if (R.state().memory or 0) < 3 or R.dissonance() + 1 >= R.consts().glitch then return false end
    if what == "appointed-attack" then
      if target ~= ayako then return false end
      return playIMW(ayako, what, false)
    end
    if what == "hour" then return playIMW(ayako, "an Hour's text", false) end
    return false
  end
  function P.itMeansWaitHour(h)
    if h ~= 8 and h ~= 6 then return false end
    return P.itMeansWait(nil, "hour")
  end

  --- The Lexicon (any non-weakness treachery drawn at its owner's location, 2
  -- secrets, limit once per loop), It Means 'Wait' and Ward of Protection.
  function P.cancelTreachery(inv, id, def)
    local G = R.G
    local bad = { ["sthr-losthour"] = 3, ["sthr-crossing"] = 3, ["sthr-thirteen"] = 3, ["sthr-wheelsturn"] = 2,
                  ["sthr-yearinanight"] = 2, ["sthr-samespeech"] = 1, ["sthr-appointedwhisper"] = 2,
                  ["sthr-deadair"] = 1, ["sthr-loopnotices"] = 2, ["sthr-slippage"] = 0 }
    local worth = bad[id] or 0
    if worth <= 0 then return false end
    for _, x in ipairs(R.investigatorsAt(R.locOf(inv))) do
      local lex = P.findAsset(x, "The Lexicon of the Hour")
      if lex and not lex.exhausted and lex.uses >= 2 and worth >= 2 and not x.loopUsed.lexicon then
        lex.exhausted = true ; lex.uses = lex.uses - 2
        x.loopUsed.lexicon = true
        R.log("The Lexicon cancels %s", def.name or id)
        return true
      end
    end
    if worth >= 2 and not def.weakness and not (id == "sthr-yearinanight" and G.prologue) then
      if P.itMeansWait(inv, "treachery") then return true end
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
    for _, inv in ipairs(R.aliveInvs()) do
      local a = P.findAsset(inv, "Cassandra's Notebook")
      if a then
        local function reward()
          P.draw(inv, 2, "Cassandra's Notebook")
          inv.resources = inv.resources + 2
          R.addMemory(inv, 1, "Cassandra's Notebook", a)
        end
        reward()
        P.afterOwnAbility(inv,{canRepeat=function() return true end,resolve=reward})
      end
    end
  end

  function P.onHourReachedPlayers(h)
    for _, inv in ipairs(R.aliveInvs()) do
      -- Stolen Minute: after the Hourglass advances, 1 charge (maximum 2), limit
      -- once per loop (taken when it can add a charge)
      local a = P.findAsset(inv, "Stolen Minute")
      if a and a.uses < 2 and not inv.loopUsed.stolenMinute then
        inv.loopUsed.stolenMinute = true
        a.uses = a.uses + 1
      end
    end
  end

  --- An investigator's own Memory reaction (each of the five has one):
  -- "Place 1 Memory on <investigator>. (Limit three times per loop.)"
  -- (twice per loop for Ayako, Cass and Seraphine, whose triggers come up most often).
  -- Returns true if the Memory was placed.
  P.MEMORY_REACTION_PER_LOOP = 3
  P.MEMORY_REACTION_LOOP_CAP = { sthrcass = 2, sthrayako = 2, sthrseraphine = 2 }
  function P.memoryReaction(inv, why)
    local cap = P.MEMORY_REACTION_LOOP_CAP[inv.id] or P.MEMORY_REACTION_PER_LOOP
    if (inv.loopUsed.memoryReaction or 0) >= cap then return false end
    inv.loopUsed.memoryReaction = (inv.loopUsed.memoryReaction or 0) + 1
    R.addMemory(inv, 1, why)
    return true
  end

  --- Rehearsed Escape can choose this enemy: non-Elite, or Elite for 1
  -- Dissonance (limit once per loop).
  function P.rehearsedLegal(inv, en)
    if en.dead or R.cannotEvade(en) then return false end
    if not R.hasTrait(en.def, "Elite") then return true end
    return not inv.loopUsed.rehearsedElite and R.dissonance() + 1 < R.consts().reset
  end

  function P.playCost(inv, card)
    return math.max(0, (card.cost or 0) - ((inv.round.recollectionDiscount or {})[card] or 0))
  end

  function P.retryTest(inv, opts)
    if not opts.important then return false end
    for _, c in ipairs(inv.hand) do
      if c.name == "This Time, For Sure" or c.name == "This Time For Sure" then
        local knowsDistrict = false
        local district = R.locOf(inv).district
        for fact in pairs(R.G.knowledge) do
          if R.G.knowledge[fact] and R.SCEN.FACT_DISTRICT and R.SCEN.FACT_DISTRICT[fact] == district then knowsDistrict = true end
        end
        if P.playCost(inv, c) <= inv.resources and (knowsDistrict or R.dissonance() + 1 < R.consts().reset) then
          P.discardFromHand(inv, c)
          inv.resources = inv.resources - P.playCost(inv, c)
          if not knowsDistrict then R.raise(1, "This Time, For Sure (cost)", inv) end
          inv.lastTurn.recollection = true
          return true
        end
      end
    end
    return false
  end

  -- Doorway repeats an ability after it resolves. The descriptor supplies
  -- current legality, remaining costs and limits; action/exhaust costs alone
  -- are waived. It cannot repeat itself or bypass a reached limit.
  function P.afterOwnAbility(inv, ability)
    if R.G.ended or inv.defeated or R.G.turnOf ~= inv or ability.repeating or not ability.canRepeat() then return end
    for _, c in ipairs(inv.hand) do
      if c.name == "The Same Doorway Twice" then
        if P.playCost(inv, c) <= inv.resources and R.dissonance() + 1 < R.consts().glitch then
          P.discardFromHand(inv, c)
          inv.resources = inv.resources - P.playCost(inv, c)
          R.raise(1, "Déjà Vu at the Doorway (cost)", inv)
          inv.lastTurn.recollection = true
          ability.repeating = true
          ability.resolve(true)
          return true
        end
      end
    end
  end

  function P.markedDeck(inv, a, mode)
    if inv.sealedToken then return false end
    local entries = T.chaosBag().getObjects()
    if #entries == 0 then return false end
    local entry = R.pick(entries)
    if mode == "number" then
      if inv.loopUsed.marked or R.syncMemory(inv) < 1 then return false end
      local best
      for _, e in ipairs(entries) do
        local n = tonumber(e.name or e.nickname)
        if n and (not best or n > best) then entry, best = e, n end
      end
      if not best then return false end
      R.raise(1, "Marked Deck (cost)", inv)
      R.addMemory(inv, -1, "Marked Deck", "any")
      T.api("shApiTally", { id = inv.id, kind = "spent", delta = 1 })
      inv.loopUsed.marked = true
    end
    local pos = inv.card.getPosition()
    local token = T.chaosBag().takeObject({ guid = entry.guid, position = {pos.x, pos.y + 1, pos.z}, smooth = false })
    E.run(0.1)
    if not token then return false end
    if token.getName() == "Static" then T.api("shApiResolveStatic", { guid = token.getGUID(), cancel = true }) end
    inv.sealedToken, a.exhausted = token, true
    R.touch()
    return true
  end

  --- End of an investigator's turn: Internal Injury / Chronophobia.
  function P.endTurn(inv)
    for _, a in ipairs(inv.assets) do
      if a.name == "Peter Sylvestre (2)" then a.hor = math.max(0,(a.hor or 0)-1) end
    end
    if inv.threat["Internal Injury"] then R.hurt(inv, 1, 0, "Internal Injury", { direct = true }) end
    if inv.threat["Chronophobia"] then R.hurt(inv, 0, 1, "Chronophobia", { direct = true }) end
  end

  return P
end
