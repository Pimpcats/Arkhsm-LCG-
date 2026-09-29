-- Scenario configurations (designer tooling): which boxes are placed, the
-- representative campaign state each is played from, and what the party
-- goes for. Part II and finale states are representative, not tuned: see
-- docs/design/PLAYTEST_SIM.md.

return function(R, T)
  local S = {}
  R.SCEN = S

  local SURFACE = { church = "the-thirteenth-toll", road = "the-road-remembers", lighthouse = "the-lamp-was-never-lit",
                    square = "the-sheriff-is-already-dead", fairground = "the-wheel-still-turns", almanac = "what-the-almanac-hid" }

  local function partOne(boxes, objectives, extra)
    -- banked Memory after the interlude's spending (the Prologue paid 7 at 3p; Recollections bought)
    local c = { boxes = boxes, part = 1, loops = 0, knowledge = { "you-are-unstuck" }, objectives = objectives,
                banked = 2, years = 0 }
    for k, v in pairs(extra or {}) do c[k] = v end
    return c
  end
  local function partTwo(boxes, knowledge, objectives, extra)
    local k = { "you-are-unstuck" }
    for _, f in ipairs(knowledge) do k[#k + 1] = f end
    local c = { boxes = boxes, part = 2, loops = 3, knowledge = k, objectives = objectives, banked = 5, years = 6 }
    for x, v in pairs(extra or {}) do c[x] = v end
    return c
  end

  S.prologue = { boxes = { "prologue" }, prologue = true, loops = 0, knowledge = {}, objectives = { "sthr-act-firsthour" },
                 banked = 0, years = 0 }

  -- Part I: the Square plus one district (the Lighthouse needs the Sunken Road)
  S.district_square = partOne({ "district_square" }, { "sthr-act-sheriffdead" })
  S.district_church = partOne({ "district_square", "district_church" }, { "sthr-act-whythirteen", "sthr-act-sheriffdead" })
  S.district_road = partOne({ "district_square", "district_road" }, { "sthr-act-walkbackward", "sthr-act-sheriffdead" })
  S.district_lighthouse = partOne({ "district_square", "district_road", "district_lighthouse" },
    { "sthr-act-lamp", "sthr-act-walkbackward", "sthr-act-sheriffdead" })
  S.district_fairground = partOne({ "district_square", "district_fairground" }, { "sthr-act-wheelturns", "sthr-act-sheriffdead" })
  S.district_almanac = partOne({ "district_square", "district_almanac" }, { "sthr-act-almanachid", "sthr-act-sheriffdead" })

  -- Part II (loop 4, scar 3, Weathered): the district's surface entry and two others recorded
  S.district_square_p2 = partTwo({ "district_square" }, { SURFACE.square, SURFACE.church, SURFACE.road }, { "sthr-act-vote" })
  S.district_church_p2 = partTwo({ "district_square", "district_church" }, { SURFACE.church, SURFACE.square, SURFACE.road },
    { "sthr-act-hourwaswrong", "sthr-act-vote" })
  S.district_road_p2 = partTwo({ "district_square", "district_road" }, { SURFACE.road, SURFACE.square, SURFACE.church },
    { "sthr-act-walksbeside", "sthr-act-vote" })
  S.district_lighthouse_p2 = partTwo({ "district_square", "district_road", "district_lighthouse" },
    { SURFACE.lighthouse, SURFACE.road, SURFACE.square }, { "sthr-act-ninthdeath", "sthr-act-walksbeside", "sthr-act-vote" })
  S.district_fairground_p2 = partTwo({ "district_square", "district_fairground" }, { SURFACE.fairground, SURFACE.square, SURFACE.church },
    { "sthr-act-bargain", "sthr-act-vote" })
  -- the Almanac House's deep act also needs The Vote That Never Ends
  S.district_almanac_p2 = partTwo({ "district_square", "district_almanac" },
    { SURFACE.almanac, SURFACE.square, SURFACE.church, "the-vote-that-never-ends" }, { "sthr-act-appointedname" })

  -- a typical Part I loop: the Square and two districts (loop 2, scar 1)
  S.loop_multi = partOne({ "district_square", "district_church", "district_almanac" },
    { "sthr-act-whythirteen", "sthr-act-almanachid", "sthr-act-sheriffdead" }, { loops = 1, years = 1, banked = 3 })

  -- the finale from a representative campaign state (loop 7, scar 6, Elder)
  S.finale = { boxes = { "district_square", "district_almanac" }, part = 2, loops = 6, finaleGoal = true, banked = 14, years = 11,
               knowledge = { "you-are-unstuck", SURFACE.church, SURFACE.road, SURFACE.lighthouse, SURFACE.square,
                             SURFACE.fairground, SURFACE.almanac, "the-vote-that-never-ends", "the-appointeds-name",
                             "the-hour-was-wrong", "the-keepers-ninth-death", "the-way-the-night-breaks" },
               logFlags = { ["The name is kept unspoken"] = true, ["The drowned heard the true hour"] = true,
                            ["The vote still stands"] = true, ["The ninth line was left blank"] = true,
                            ["The town was warned"] = true },
               objectives = {} }

  -- the same state, the finale begun when Hour IX is reached (the guide's other way in)
  S.finale_h9 = {}
  for k, v in pairs(S.finale) do S.finale_h9[k] = v end
  S.finale_h9.finaleAtNine = true

  S.ORDER = { "prologue", "district_square", "district_church", "district_road", "district_lighthouse",
              "district_fairground", "district_almanac", "district_square_p2", "district_church_p2", "district_road_p2",
              "district_lighthouse_p2", "district_fairground_p2", "district_almanac_p2", "loop_multi", "finale", "finale_h9" }

  S.BOX_DISTRICT = { district_square = "Square", district_church = "Church", district_road = "Road",
                     district_lighthouse = "Lighthouse", district_fairground = "Fairground", district_almanac = "Almanac",
                     prologue = "Prologue" }
  S.SURFACE = SURFACE
  S.DEEP = { Square = "the-vote-that-never-ends", Church = "the-hour-was-wrong", Road = "who-walks-beside-you",
             Lighthouse = "the-keepers-ninth-death", Fairground = "the-ticket-takers-bargain", Almanac = "the-appointeds-name" }
  S.SURF = { Square = SURFACE.square, Church = SURFACE.church, Road = SURFACE.road, Lighthouse = SURFACE.lighthouse,
             Fairground = SURFACE.fairground, Almanac = SURFACE.almanac }

  -- aging choices when Weathered (the drifting physical skill, the rising mental one)
  S.DRIFT = { sthrelias = { "agility", "willpower" }, sthrayako = { "combat", "intellect" }, sthrcass = { "combat", "intellect" },
              sthrseraphine = { "agility", "willpower" }, sthrbirdie = { "combat", "intellect" } }

  return S
end
