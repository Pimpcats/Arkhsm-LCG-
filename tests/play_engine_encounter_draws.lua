-- Independent encounter-draw identity regressions.
-- Production tablekit and real emulator Card/Deck/timer/button behavior.
-- The small scripted button reproduces SCED MythosArea's moved last Card,
-- DeckLib target merge and delayed reshuffle; it never replaces draw polling.
-- No generated campaign payload, existing reviewer fixture or file writes.
local passed, failed = 0, 0
local function expect(name, condition)
  if condition then passed = passed + 1; print("PASS " .. name)
  else failed = failed + 1; print("FAIL " .. name) end
end
local function case(name, fn)
  local ok, err = pcall(fn)
  if not ok then failed = failed + 1; print("ERROR " .. name .. ": " .. tostring(err)) end
end
local function fixture()
  local E = dofile("tests/sced_real/tts_emu.lua")
  E.srcDirs = {}; E.quiet = true; E.loadSave({ ObjectStates = {} }, "independent-draw")
  E.seed(20261002)
  local T = dofile("tools/play_engine/lua/tablekit.lua"); T.init({ E = E })
  local mat = E.spawnData({ Name = "Custom_Tile", GUID = "8b081b",
    Transform = { posX = 0, posY = 1, posZ = 0, scaleX = 1, scaleY = 1, scaleZ = 1 },
    LuaScript = [[
      function onLoad()
        self.createButton({ label = "Draw", click_function = "drawEncounterCard",
          function_owner = self, position = {0,0.1,0}, width = 100, height = 100, font_size = 20 })
      end
      function drawEncounterCard(_, _, _)
        Wait.time(function() fixtureAction() end, fixtureDelay or 0)
      end
    ]] }, {}, "independent-draw")
  E.spawnData({ Name = "Custom_Tile", GUID = "9f334f",
    Transform = { posX = 30, posY = 1, posZ = 0, scaleX = 5, scaleY = 1, scaleZ = 2 } },
    {}, "independent-draw")
  E.run(0.2)
  T.mat = function() return mat end
  local C = { E = E, T = T, mat = mat, clicks = 0,
    target = mat.positionToWorld({ 1.365, 0.5, -0.625 }) }
  function C.card(guid, id)
    return { Name = "CardCustom", GUID = guid, Nickname = id, CardID = 101,
      GMNotes = E.J.encode({ id = id, type = "Treachery" }),
      Memo = id .. "-memo", Tags = { "identity-fixture" },
      CustomDeck = { ["1"] = { FaceURL = "https://example.test/" .. id .. ".jpg",
        BackURL = "https://example.test/back.jpg", NumWidth = 1, NumHeight = 1 } } }
  end
  function C.spawnCard(guid, id, position)
    return E.spawnData(C.card(guid, id), { position = position }, "independent-draw")
  end
  function C.spawnDeck(guid, cards, position)
    local ids = {}; for _, card in ipairs(cards) do ids[#ids + 1] = card.CardID end
    return E.spawnData({ Name = "DeckCustom", GUID = guid, DeckIDs = ids, ContainedObjects = cards },
      { position = position }, "independent-draw")
  end
  function C.atTarget()
    return T.find(function(o)
      return (o.type == "Card" or o.type == "Deck") and T.dist(o.getPosition(), C.target) < 1.2
    end)
  end
  function C.place(card)
    local pile = C.atTarget()
    if pile then return pile.putObject(card) end
    card.setPosition(C.target); return card
  end
  function C.action(fn, delay)
    mat.setVar("fixtureDelay", delay or 0)
    mat.setVar("fixtureAction", function() C.clicks = C.clicks + 1; fn() end)
  end
  function C.sameCard(card, guid, id)
    if not card or not T.alive(card) or card.type ~= "Card" or card.getGUID() ~= guid then return false end
    local d = card.getData()
    return T.gm(card).id == id and d.Memo == id .. "-memo"
      and d.CustomDeck["1"].FaceURL == "https://example.test/" .. id .. ".jpg"
      and d.CustomDeck["1"].BackURL == "https://example.test/back.jpg"
  end
  function C.drawSource()
    local source = T.encounterDeck()
    if not source then return end
    local card = source.type == "Deck" and source.takeObject({ smooth = false }) or source
    C.place(card)
  end
  return C
end

case("existing last Card moves to draw destination", function()
  local C = fixture(); local E, T = C.E, C.T
  local last = C.spawnCard("a10001", "encounter-last", T.mythosSpot("encounter")); E.run(0.2)
  C.action(function() C.place(last) end)
  local card, reshuffled = T.drawEncounter("White")
  expect("last Card is recognized even though object existed before click", card == last)
  expect("last Card GUID, metadata, memo and images survive", C.sameCard(card, "a10001", "encounter-last"))
  expect("last Card is not falsely reported as reshuffled", reshuffled == false and T.deckCount(T.encounterDeck()) == 0)
  expect("one button draw has no emulator or tablekit error", C.clicks == 1 and #E.errors == 0 and #T.errors == 0)
end)
case("arrival merges with preexisting weakness Card", function()
  local C = fixture(); local E, T = C.E, C.T
  C.spawnCard("a20001", "existing-weakness", C.target)
  local source = C.spawnCard("a10001", "encounter-new", T.mythosSpot("encounter")); E.run(0.2)
  C.action(function() C.place(source) end)
  local card = T.drawEncounter("White")
  expect("draw extracts newly arrived child after Card-to-Deck merge", C.sameCard(card, "a10001", "encounter-new"))
  expect("existing weakness remains with its original identity", C.sameCard(E.byGuid("a20001"), "a20001", "existing-weakness"))
  expect("weakness is not returned as encounter card", card and card.getGUID() ~= "a20001")
  expect("Card-to-Deck extraction has no emulator or tablekit error", #E.errors == 0 and #T.errors == 0)
end)
case("arrival merges with preexisting weakness Deck", function()
  local C = fixture(); local E, T = C.E, C.T
  local prior = C.spawnDeck("a30001", {
    C.card("a20001", "existing-one"), C.card("a20002", "existing-two") }, C.target)
  local source = C.spawnCard("a10001", "encounter-new", T.mythosSpot("encounter")); E.run(0.2)
  C.action(function() C.place(source) end)
  local card = T.drawEncounter("White")
  expect("draw extracts new child from an existing Deck", C.sameCard(card, "a10001", "encounter-new"))
  expect("preexisting Deck container identity survives extraction", T.alive(prior) and prior.getGUID() == "a30001" and T.deckCount(prior) == 2)
  local old = {}; for _, child in ipairs(prior.getData().ContainedObjects) do old[child.GUID] = child end
  expect("both preexisting child GUIDs remain", old.a20001 ~= nil and old.a20002 ~= nil and old.a10001 == nil)
  expect("preexisting child metadata and artwork remain",
    old.a20001 and old.a20001.GMNotes == E.J.encode({ id = "existing-one", type = "Treachery" })
      and old.a20002 and old.a20002.CustomDeck["1"].FaceURL == "https://example.test/existing-two.jpg")
  expect("Deck child extraction has no emulator or tablekit error", #E.errors == 0 and #T.errors == 0)
end)
case("two-card source becomes existing final Card", function()
  local C = fixture(); local E, T = C.E, C.T
  C.spawnDeck("a40001", { C.card("a10001", "first"), C.card("a10002", "second") }, T.mythosSpot("encounter")); E.run(0.2)
  C.action(C.drawSource)
  local first, shuffle1 = T.drawEncounter("White")
  expect("first draw from Deck preserves its identity", C.sameCard(first, "a10001", "first"))
  T.discardEncounter(first)
  expect("source remainder is a lone existing Card", T.encounterDeck() and T.encounterDeck().type == "Card")
  local second, shuffle2 = T.drawEncounter("White")
  expect("existing source remainder draws correctly", C.sameCard(second, "a10002", "second"))
  T.discardEncounter(second)
  expect("source exhausted without duplicate draw or false reshuffle", T.deckCount(T.encounterDeck()) == 0 and shuffle1 == false and shuffle2 == false and C.clicks == 2)
  expect("both actual returned cards reach the discard pile", T.deckCount(T.encounterDiscard()) == 2)
  expect("Deck-to-final-Card transition has no emulator error", #E.errors == 0 and #T.errors == 0)
end)
case("delayed reshuffle draw remains within polling window", function()
  local C = fixture(); local E, T = C.E, C.T
  local discard = C.spawnDeck("a40001", {
    C.card("a10001", "reshuffled-first"), C.card("a10002", "reshuffled-second"), C.card("a10003", "reshuffled-third") },
    T.mythosSpot("discard")); E.run(0.2)
  C.action(function() discard.setPosition(T.mythosSpot("encounter")); C.drawSource() end, 0.55)
  local started = E.now
  local card, reshuffled = T.drawEncounter("White")
  expect("delayed SCED-style draw is found by production polling", C.sameCard(card, "a10001", "reshuffled-first"))
  expect("empty initial source reports reshuffle", reshuffled == true)
  expect("polling waits for delayed arrival without timing out", E.now - started >= 0.55 and E.now - started < 3)
  expect("remaining encounter identities stay in source", T.deckCount(T.encounterDeck()) == 2 and T.deckCount(T.encounterDiscard()) == 0)
  expect("delayed draw has no emulator or tablekit error", #E.errors == 0 and #T.errors == 0)
end)
case("no draw cannot return old destination Card", function()
  local C = fixture(); local E, T = C.E, C.T
  local old = C.spawnCard("a20001", "old-weakness", C.target)
  C.spawnCard("a10001", "undrawn", T.mythosSpot("encounter")); E.run(0.2)
  C.action(function() end)
  local started = E.now
  local card, reshuffled = T.drawEncounter("White")
  expect("no arriving card returns nil instead of an old weakness", card == nil and reshuffled == false)
  expect("no-draw polling times out rather than immediately accepting old card", E.now - started >= 3)
  expect("existing weakness remains intact after no draw", C.sameCard(old, "a20001", "old-weakness"))
  expect("undrawn source remains intact", C.sameCard(T.encounterDeck(), "a10001", "undrawn"))
end)
case("no draw cannot return old destination Deck children", function()
  local C = fixture(); local E, T = C.E, C.T
  local prior = C.spawnDeck("a30001", { C.card("a20001", "old-one"), C.card("a20002", "old-two") }, C.target)
  E.run(0.2); C.action(function() end)
  local card = T.drawEncounter("White")
  expect("no newly added child returns nil", card == nil)
  expect("both old Deck children remain undrawn", T.alive(prior) and T.deckCount(prior) == 2)
  expect("no-draw cases have no emulator or tablekit error", #E.errors == 0 and #T.errors == 0)
end)
print(string.format("INDEPENDENT ENCOUNTER DRAWS: %d passed, %d failed", passed, failed))
if failed > 0 then os.exit(1) end
