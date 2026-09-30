#!/usr/bin/env python3
"""
simulate_tempo.py — THE STILL HOUR act-vs-clock race (tempo) simulator.

pipeline/simulate.py models the clock, Dissonance, Memory, aging and the
finale; it never asks whether a party can actually travel, gather clues and
complete objectives before the Hourglass reaches Hour IX. This does.

One loop is played round by round:
  * Mythos (from round 2): 1 doom on the current Hour (Hour I holds 3,
    Hours II-VIII 2: half an Hour a round), so the
    Hourglass advances 1 Hour; each investigator draws an encounter card, and
    a Lost Hour (or a placed district's Skip card) advances it further.
  * Investigation: the party has 3 actions per investigator, minus a tax for
    everything that is not objective work (enemies, treacheries, setup plays).
  * Travel along a connection between districts advances the Hourglass 1 Hour.
  * The loop ends at Hour IX. Objective progress (clues, tests) does not carry
    over a reset; recorded facts do.

The party follows a finale-first plan: it takes each available objective in
priority order, grouped by district, starting in the Square (always placed).
Act II opens after an interlude with 3+ surface facts or after Loop 3; the
finale unlocks with The Appointed's Name + The Vote That Never Ends + any one
other deep fact (guide, "The Way the Night Breaks").

Reports: objectives / districts per loop, and loops until the finale unlocks,
for 1-4 investigators and three action-tax levels. Target from the design:
~2-3 districts per loop and a campaign of ~6-8 loops.

Every model assumption is a named constant marked ASSUMPTION. This validates
pacing arithmetic, not play; table play refines the constants.

Run: python3 pipeline/simulate_tempo.py [--trials 4000] [--seed 1729]
"""
import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulate import success_probability  # noqa: E402  (the calibrated bag)

ACTIONS = 3
# ASSUMPTION: share of actions spent on non-objective work.
TAX_LEVELS = (0.25, 0.35, 0.45)
# ASSUMPTION: party skill values by size (best investigator first), and the
# average boost from committed cards / assets on an objective test.
PARTY = {
    1: {"int": [4], "agi": [4], "wil": [4], "com": [4]},
    2: {"int": [5, 3], "agi": [5, 3], "wil": [5, 3], "com": [4, 3]},
    3: {"int": [5, 3, 3], "agi": [5, 4, 3], "wil": [5, 3, 3], "com": [4, 3, 2]},
    4: {"int": [5, 3, 3, 2], "agi": [5, 4, 3, 3], "wil": [5, 3, 3, 3], "com": [4, 3, 3, 2]},
}
BOOST = 1
# ASSUMPTION: Dissonance gained per round at three investigators (deck +
# typical foreknowledge use). It comes from encounter draws and chaos-token
# pulls, so it scales with the number of investigators (dissonance_rate).
DISSONANCE_PER_ROUND = 1.1        # 12-round loops: Cultist raises only on a fail by 2+


def dissonance_rate(n):
    return DISSONANCE_PER_ROUND * n / 3


def scar_cap(n):
    """Guide, Difficulty and Player Count: 2 x investigators (4 solo)."""
    return 4 if n == 1 else 2 * n


def reset_value(n):
    """Guide, Difficulty and Player Count: 8 x investigators (16 solo)."""
    return 16 if n == 1 else 8 * n
# ASSUMPTION: extra party actions a Named enemy costs when it guards an objective.
NAMED_COST = {"square_deep": 8, "church_deep": 6}
SPINE_SIZE = 23          # 22-card spine + The Crossing (audit pass 5 trim)
LOST_HOURS = 3

# Districts: node-set size and Skip cards in it (count, chance it triggers).
DISTRICT = {
    "square": {"set": 3, "skips": []},
    "almanac": {"set": 4, "skips": []},
    "fairground": {"set": 3, "skips": [(1, 1.0)]},     # The Wheel's Turn
    "church": {"set": 4, "skips": [(1, 0.8)]},         # Thirteen (if at the Church)
    "road": {"set": 3, "skips": [(1, 0.4)]},           # The Bridge Remembers
    "lighthouse": {"set": 2, "skips": []},
}
# Each district's own monster (the recurring Echoes are inside the action tax).
# kill: party actions to defeat it; cost: actions it takes when handled the
# efficient way (evade / endure). ASSUMPTION: values from its fight/health/evade
# against the modelled party (about one damage-2 hit per 1.5 actions).
DISTRICT_ENEMY = {
    "square": {"id": "band", "kill": 2, "cost": 1, "calm_idle": True},        # Echo: sleeps in Calm
    "church": {"id": "verger", "kill": 3, "cost": 1, "vp": 1},                # Aloof; engages at the Vestry
    "road": {"id": "milecounter", "kill": 3, "cost": 3, "vp": 1},             # Hunter; left alone it skips Hours, so it is always killed
    "fairground": {"id": "barker", "kill": 2, "cost": 2},                     # Hunter; killed either way
    "almanac": {"id": "compositor", "kill": 4, "cost": 0, "vp": 1,            # Retaliate; left alone, failed Press tests raise Dissonance
                "press_diss": True},
}
# Victory locations: (district, shroud, clues per investigator, opens when)
VP_LOCATIONS = {
    "keepers": ("lighthouse", 2, 2, None),
    "records": ("square", 3, 3, None),
    "ticketbooth": ("fairground", 2, 2, None),
    "crypt": ("church", 4, 3, "church_surface"),     # Part II: opens with its act 2a
    "study": ("almanac", 4, 3, "almanac_surface"),   # Part II: opens with its act 2a
}
# Named enemies: (district, Victory, extra kill cost for the greedy party when
# its objective does not already require dealing with it)
NAMED_VP = {"square_deep": ("sheriff", 3), "church_deep": ("bellringer", 2)}
RIDER = ("fairground", 2, 8)
# Map: the Square is the hub; the Lighthouse hangs off the Sunken Road.
EDGES = {("square", "almanac"), ("square", "fairground"), ("square", "church"),
         ("square", "road"), ("road", "lighthouse")}


def crossings(a, b):
    """District boundaries crossed travelling a -> b (shortest path)."""
    if a == b:
        return []
    if (a, b) in EDGES or (b, a) in EDGES:
        return [(a, b)]
    def to_square(x):
        return {"lighthouse": ["road", "square"]}.get(x, ["square"]) if x != "square" else []
    up = [a] + to_square(a)
    down = [b] + to_square(b)
    # meet at the first common node
    for i, x in enumerate(up):
        if x in down:
            j = down.index(x)
            nodes = up[:i + 1] + list(reversed(down[:j]))
            return list(zip(nodes, nodes[1:]))
    return []


# Objectives: (id, district, layer, steps). Clue steps name the locations the
# act allows, as (shroud, clues per investigator, location); from the location
# cards. ("at", loc) marks the moment the party must stand at an objective
# location (its "after you enter" effects apply there).
OBJ = {
    "square_surface": ("square", "surface", [("clues_pi", 5, [(1, 2, "square"), (2, 2, "townhall"), (2, 2, "well"),
                                                            (3, 3, "records")]), ("at", "well"), ("act", 1)]),
    "square_deep": ("square", "deep", [("named", "square_deep"), ("clues_pi", 5, [(4, 3, "records"), (2, 2, "townhall"),
                                                                            (2, 2, "well"), (1, 2, "square")])]),
    "almanac_surface": ("almanac", "surface", [("clues_pi", 5, [(2, 2, "readingroom"), (3, 3, "press")]),
                                               ("at", "press"), ("act", 1)]),
    "almanac_deep": ("almanac", "deep", [("move", 1), ("clues_pi", 5, [(4, 3, "study"), (2, 2, "readingroom"), (3, 3, "press")])]),
    "fairground_surface": ("fairground", "surface", [("clues_pi", 3, [(3, 2, "wheel"), (2, 3, "hallofmirrors")]),
                                                     ("at", "wheel"), ("test", "agi", 3, "wheel")]),
    "fairground_deep": ("fairground", "deep", [("clues_pi", 5, [(2, 2, "ticketbooth"), (3, 2, "wheel"), (2, 3, "hallofmirrors")]),
                                               ("at", "ticketbooth"), ("act", 1)]),
    "church_surface": ("church", "surface", [("clues_pi", 5, [(2, 3, "nave"), (3, 2, "belfry"), (2, 2, "vestry")]),
                                             ("at", "vestry"), ("act", 1)]),
    "church_deep": ("church", "deep", [("named", "church_deep"), ("clues_pi", 5, [(4, 3, "crypt"), (2, 3, "nave"),
                                                                            (3, 2, "belfry"), (2, 2, "vestry")])]),
    "road_surface": ("road", "surface", [("move", 1), ("clues", 3, [(2, 3, "turning")]), ("move", 1),
                                         ("clues", 3, [(3, 2, "lowbridge")]), ("move", 1),
                                         ("clues", 3, [(1, 2, "milestones")])]),
    "road_deep": ("road", "deep", [("glitch",), ("move", 1), ("test", "agi", 3, "turning")]),
    "lighthouse_surface": ("lighthouse", "surface", [("clues_pi", 3, [(2, 1, "stair"), (2, 2, "keepers"),
                                                                   (4, 2, "lantern")]), ("test", "wil", 3, "lantern")]),
    "lighthouse_deep": ("lighthouse", "deep", [("act", 1), ("move", 1), ("clues_pi", 3, [(2, 2, "keepers"), (2, 1, "stair"),
                                                                                       (3, 2, "lantern")])]),
}
# Location card effects the pacing can feel, per profile. Keys:
#   extra_action  - investigating here costs this many more actions
#   fail_diss     - Dissonance raised when an investigation here fails
#   fail_harm     - damage/horror when an investigation here fails
#   enter_diss / enter_harm - per investigator who enters (see VISITORS)
#   hour_harm     - horror to the investigator here each time the Hourglass advances
# Effects with no tempo weight (the Ticket Booth's lost resource, the Keeper's
# Quarters' optional heal, the Hall of Mirrors, which no objective needs you to
# investigate) are left out. An extra-action cost on the Records Office was
# tried and rejected: solo, it cut the finale unlock rate (2% -> 20% never by
# loop 15) because the Square's deep objective spends its clues there.
LOCATION_PROFILES = {
    "none": {},
    # friction only (the previous proposal, kept for comparison)
    "friction": {
        "well": {"enter_harm": 1},
        "press": {"fail_diss": 1},
        "wheel": {"hour_harm": 1},
        "belfry": {"enter_diss": 1},
        "lowbridge": {"fail_harm": 1},
    },
    # "What the town remembers" (the printed location cards): one lever per
    # district, hazards that a Knowledge entry quiets. Not modelled (no tempo
    # weight): the Ticket Booth's fare, the Press removing a temporary Static
    # token, the Keeper's Quarters' rest, the Prologue's Long Pier.
    "spin": {
        "well": {"enter_harm": 1, "unless": "square_surface"},
        "belfry": {"enter_diss": 1, "unless": "church_surface"},
        "wheel": {"hour_harm": 1},
        "levers": {
            # district: (lever, config)
            "road": ("rewind", {"diss_cost": 2, "actions": 1, "per_loop": 1}),
            "church": ("lower_diss", {"actions": 2, "per_round": 1}),
            "fairground": ("mirror", {"actions": 1, "memory": 2, "years": 1, "per_loop": 1}),
            "square": ("strike_year", {"actions": 3, "per_loop": 1}),
        },
    },
}


def visitors(n):
    """ASSUMPTION: how many investigators enter a given side location."""
    return 1 if n <= 2 else 2


# ASSUMPTION: finale-first priority (the party is heading for the finale).
PRIORITY = ["square_surface", "almanac_surface", "fairground_surface",
            "square_deep", "almanac_deep", "fairground_deep",
            "church_surface", "road_surface", "church_deep", "road_deep",
            "lighthouse_surface", "lighthouse_deep"]


def band_for(diss, n):
    reset = reset_value(n)
    if diss >= reset * 2 / 3:
        return "Noticed"
    if diss >= reset / 3:
        return "Glitch"
    return "Calm"


def prereq_met(obj, known):
    """Can this objective be attempted, given the facts known right now?"""
    d, layer, _ = OBJ[obj]
    if layer == "surface":
        return True
    if (d + "_surface") not in known:
        return False
    return obj != "almanac_deep" or "square_deep" in known


def available(obj, facts, act2):
    """Worth planning this loop: a surface objective, or (Act II) a deep one
    whose prerequisites are known or planned earlier in the same loop."""
    d, layer, _ = OBJ[obj]
    if obj in facts:
        return False
    if layer == "surface":
        return True
    return act2


def play_loop(rng, n, tax, facts, act2, scar, explore=False, fx=None, greedy=False, claimed=None, only=None):
    fx = fx or {}
    claimed = claimed if claimed is not None else set()
    vp_gain = []
    enemies_in = []            # district enemies shuffled into the deck
    compositor_live = False
    pending_cost = 0
    clearing = {}              # VP location -> clues still on it (greedy)
    rider_hp = None
    party = PARTY[n]
    reset_at = reset_value(n)
    stats = {"reset": False, "harm": 0, "diss_fx": 0, "memory": 0, "years": 0,
             "rewinds": 0, "lowered": 0}
    levers = fx.get("levers", {})
    used = {}
    year_in_night = 0
    entered = set()

    def enter(loc, who):
        if loc in entered:
            return
        entered.add(loc)
        e = fx.get(loc, {})
        if e.get("unless") in facts:
            return 0
        stats["harm"] += e.get("enter_harm", 0) * who
        stats["diss_fx"] += e.get("enter_diss", 0) * who
        return e.get("enter_diss", 0) * who
    hours_total = 8 - (1 if "church_deep" in facts else 0)   # advances to Hour IX
    hour = 0
    diss = float(scar)
    prio = list(PRIORITY)
    if explore:
        # a first-time party: no idea which facts the finale needs, so it
        # picks districts in a random order (the Square is always first)
        ds = [d for d in DISTRICT if d != "square"]
        rng.shuffle(ds)
        rank = {d: i for i, d in enumerate(["square"] + ds)}
        prio.sort(key=lambda o: (rank[OBJ[o][0]], OBJ[o][1] != "surface"))
    plan = [o for o in prio if available(o, facts, act2)]
    if only is not None:
        plan = [o for o in plan if o in only]
    # group by district in first-appearance order, Square first
    order = ["square"] + [OBJ[o][0] for o in plan if OBJ[o][0] != "square"]
    districts = list(dict.fromkeys(order))
    tasks = [("district", "square")]
    here = "square"
    # the Turning - the Winding Stair never costs an Hour (not a district
    # connection); The Road Remembers frees the Square - the Milestones once
    free_road = "road_surface" in facts
    placed = {"square"}
    for d in districts:
        objs = [o for o in plan if OBJ[o][0] == d]
        # deep objectives open only once the surface is recorded; surface first
        objs.sort(key=lambda o: OBJ[o][1] != "surface")
        if not objs:
            continue
        for a, b in crossings(here, d):
            free = "lighthouse" in (a, b) or (free_road and {a, b} == {"square", "road"})
            tasks.append(("travel", b, 0 if free else 1))
            tasks.append(("district", b))
            if free and "lighthouse" not in (a, b):
                free_road = False
        here = d
        for o in objs:
            tasks.append(("begin", o))
            tasks.extend(OBJ[o][2])
            tasks.append(("done", o))
    done = []
    deck = SPINE_SIZE + DISTRICT["square"]["set"] + (2 if act2 else 0)
    skip_cards = []
    if "square" in DISTRICT_ENEMY:
        enemies_in.append("square")
    cur, progress, supply = None, 0, None
    cur_district = "square"
    comp_round = -1
    rounds = 0
    ti = 0
    while True:
        rounds += 1
        if rounds > 1:
            draws = n + (n if 1 <= hour < 1.5 else 0)    # Hour II: extra draw
            adv = 1 / 3 if hour < 1 else 0.5              # 1 doom: Hour I holds 3, the others 2
            for _ in range(draws):
                if rng.random() < 2 / deck and rng.random() < 0.45:
                    year_in_night += 1
                r = rng.random() * deck
                if r < LOST_HOURS:
                    adv += 1                                  # Lost Hour: a 1-Hour Skip
                else:
                    r -= LOST_HOURS
                    drawn_skip = False
                    for cnt, p in skip_cards:
                        if r < cnt:
                            if rng.random() < p:
                                adv += 0.5                            # Thirteen / Bridge / Wheel's Turn: 1 doom
                            drawn_skip = True
                            break
                        r -= cnt
                    if not drawn_skip:
                        for d_ in list(enemies_in):
                            if r < 1:
                                en = DISTRICT_ENEMY[d_]
                                enemies_in.remove(d_)            # one copy: it stays in play
                                band_now = band_for(diss, n)
                                vp = en.get("vp")
                                if vp and greedy and en["id"] not in claimed:
                                    pending_cost += en["kill"]
                                    claimed.add(en["id"]); vp_gain.append((en["id"], vp))
                                elif en["id"] == "milecounter":
                                    pending_cost += en["kill"]
                                    if en["id"] not in claimed:
                                        claimed.add(en["id"]); vp_gain.append((en["id"], vp))
                                elif en.get("press_diss"):
                                    compositor_live = True
                                elif en.get("calm_idle") and band_now == "Calm":
                                    pass
                                else:
                                    pending_cost += en["cost"]
                                break
                            r -= 1
            hour += adv
            diss += dissonance_rate(n)
            if ti < len(tasks) and tasks[ti][0] == "test" and len(tasks[ti]) > 3 \
                    and fx.get(tasks[ti][3], {}).get("unless") not in facts:
                stats["harm"] += fx.get(tasks[ti][3], {}).get("hour_harm", 0) * adv
            if diss >= reset_at:
                stats["reset"] = True
                break
            if hour >= hours_total:
                break
        band = band_for(diss, n)
        budget = sum(1 for _ in range(n * ACTIONS) if rng.random() >= tax)
        paid = min(budget, pending_cost)
        budget -= paid
        pending_cost -= paid
        actor = 0
        glitch_at = reset_at // 3
        noticed_at = 2 * reset_at // 3
        def district_clear():
            """ASSUMPTION: optional levers (Memory, striking a Year) are used only
            once this district's objectives for the loop are done, before moving on."""
            for t2 in tasks[ti:]:
                if t2[0] in ("travel", "district"):
                    return True
                if t2[0] in ("clues", "clues_pi", "test", "move", "act", "named", "at", "glitch"):
                    return False
            return True

        if greedy and budget > 0 and district_clear():
            # greed: clear this district's Victory location before moving on
            for name, (dd, sh, cpi, needs) in VP_LOCATIONS.items():
                if dd != cur_district or name in claimed:
                    continue
                if needs and not (act2 and needs in facts):
                    continue
                left = clearing.setdefault(name, cpi * n)
                while budget > 0 and left > 0:
                    budget -= 1
                    if rng.random() < success_probability(party["int"][actor % n] + BOOST - sh, band_for(diss, n)):
                        left -= 1
                    actor += 1
                clearing[name] = left
            if act2 and cur_district == RIDER[0] and "rider" not in claimed:
                rider_hp = RIDER[2] if rider_hp is None else rider_hp
                spend = min(budget, rider_hp)
                budget -= spend
                rider_hp -= spend
                if rider_hp <= 0:
                    claimed.add("rider"); vp_gain.append(("rider", RIDER[1]))

        lv = levers.get(cur_district)
        if lv and budget > 0 and (lv[0] in ("rewind", "lower_diss") or district_clear()):
            kind, cfg = lv
            if kind == "rewind" and used.get(kind, 0) < cfg["per_loop"] and hour > 0 \
                    and diss + cfg["diss_cost"] < noticed_at:
                used[kind] = used.get(kind, 0) + 1
                hour -= 1
                diss += cfg["diss_cost"]
                stats["diss_fx"] += cfg["diss_cost"]
                stats["rewinds"] += 1
                budget -= cfg["actions"]
            elif kind == "lower_diss" and diss >= noticed_at - 1 and budget >= cfg["actions"]:
                # ASSUMPTION: used to stay out of the Noticed band, not every round
                diss -= 1
                stats["diss_fx"] -= 1
                stats["lowered"] += 1
                budget -= cfg["actions"]
            elif kind == "mirror" and used.get(kind, 0) < cfg["per_loop"]:
                used[kind] = 1
                stats["memory"] += cfg["memory"]
                stats["years"] += cfg["years"]
                budget -= cfg["actions"]
            elif kind == "strike_year" and used.get(kind, 0) < cfg["per_loop"] \
                    and (year_in_night > 0 or stats["years"] > 0) and budget >= cfg["actions"]:
                used[kind] = 1
                if year_in_night > 0:
                    year_in_night -= 1
                else:
                    stats["years"] -= 1
                stats["struck"] = stats.get("struck", 0) + 1
                budget -= cfg["actions"]
        while budget > 0 and ti < len(tasks):
            t = tasks[ti]
            k = t[0]
            if k == "travel":
                budget -= min(budget, n)          # everyone moves
                hour += 0.5 * t[2]                        # a paid crossing: 1 doom
                d = t[1]
                if d not in placed:
                    placed.add(d)
                    deck += DISTRICT[d]["set"]
                    skip_cards += DISTRICT[d]["skips"]
                    if d in DISTRICT_ENEMY:
                        enemies_in.append(d)
                ti += 1
                if hour >= hours_total:
                    break
            elif k == "begin":
                if prereq_met(t[1], facts | set(done)):
                    ti += 1
                else:                               # skip to after its "done"
                    ti = tasks.index(("done", t[1]), ti) + 1
            elif k == "district":
                cur_district = t[1]
                ti += 1
            elif k == "at":
                diss += enter(t[1], 1) or 0
                ti += 1
            elif k == "done":
                done.append(t[1])
                stats.setdefault("done_hour", {})[t[1]] = hour
                if t[1] in NAMED_VP and NAMED_VP[t[1]][0] not in claimed:
                    claimed.add(NAMED_VP[t[1]][0]); vp_gain.append(NAMED_VP[t[1]])
                ti += 1
            elif k == "move":
                need = n * t[1]
                spend = min(budget, need - progress)
                budget -= spend
                progress += spend
                if progress >= need:
                    progress = 0
                    ti += 1
            elif k == "act":
                budget -= 1
                progress += 1
                if progress >= t[1]:
                    progress = 0
                    ti += 1
            elif k == "named":
                cost = NAMED_COST[t[1]]
                spend = min(budget, cost - progress)
                budget -= spend
                progress += spend
                if progress >= cost:
                    progress = 0
                    ti += 1
            elif k == "glitch":
                if band == "Calm":
                    budget = 0                      # wait for the loop to glitch
                else:
                    ti += 1
            elif k == "test":
                budget -= 1
                skill = party[t[1]][0] + BOOST
                if rng.random() < success_probability(skill - t[2], band):
                    ti += 1
            elif k in ("clues", "clues_pi"):
                need = t[1] * (n if k == "clues_pi" else 1)
                if supply is None or cur != ti:
                    # easiest first; an extra action counts like higher shroud
                    order = sorted(t[2], key=lambda x: x[0] + 1.5 * fx.get(x[2], {}).get("extra_action", 0))
                    cur, supply = ti, [[s_, c * n, name] for s_, c, name in order]
                    progress = 0
                loc = next((s_ for s_ in supply if s_[1] > 0), None)
                if loc is None:
                    ti += 1                         # feasibility is audited elsewhere
                    continue
                e = fx.get(loc[2], {})
                diss += enter(loc[2], visitors(n)) or 0
                budget -= 1 + e.get("extra_action", 0)
                skill = party["int"][actor % n] + BOOST
                actor += 1
                if rng.random() < success_probability(skill - loc[0], band):
                    loc[1] -= 1
                    progress += 1
                else:
                    diss += e.get("fail_diss", 0)
                    stats["diss_fx"] += e.get("fail_diss", 0)
                    stats["harm"] += e.get("fail_harm", 0)
                    if compositor_live and loc[2] == "press" and comp_round != rounds:
                        comp_round = rounds
                        diss += 1
                        stats["diss_fx"] += 1
                if progress >= need:
                    progress, supply = 0, None
                    ti += 1
        if diss >= reset_at:
            stats["reset"] = True
            break
        if ti >= len(tasks):
            break
        if hour >= hours_total:
            break
    stats["year_in_night"] = year_in_night
    for name, left in clearing.items():
        if left <= 0 and name not in claimed:
            claimed.add(name); vp_gain.append((name, 1))
    stats["vp"] = sum(v for _, v in vp_gain)
    return done, rounds, len(placed), stats


def campaign(rng, n, tax, max_loops=15, explore=False, fx=None, log=None, greedy=False):
    facts, act2 = set(), False
    per_loop, districts = [], []
    claimed = set()
    for loop in range(1, max_loops + 1):
        done, rounds, placed, st = play_loop(rng, n, tax, facts, act2, min(loop - 1, scar_cap(n)), explore, fx,
                                             greedy=greedy, claimed=claimed)
        if log is not None:
            log.append(dict(st, rounds=rounds, done=sorted(done)))
        facts.update(done)
        per_loop.append(len(done))
        districts.append(placed)
        surface = sum(1 for f in facts if OBJ[f][1] == "surface")
        if not act2 and (surface >= 3 or loop >= 3):
            act2 = True
        deep = [f for f in facts if OBJ[f][1] == "deep"]
        if "square_deep" in facts and "almanac_deep" in facts and len(deep) >= 3:
            return loop, per_loop, districts
    return None, per_loop, districts


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


PROFILES_TO_COMPARE = ("none", "friction", "spin")


def district_race(trials, seed, n=3):
    """One loop, one district: how often its objective beats the Hourglass."""
    fx = LOCATION_PROFILES["spin"]
    print()
    print("District race at {} investigators (one loop, heading straight there from the Square):".format(n))
    print("objective                 | scar 0: done  Hours left | scar 4: done  Hours left")
    rows = [(o, OBJ[o][0], OBJ[o][1]) for o in PRIORITY]
    for obj, d, layer in rows:
        facts = set()
        if layer == "deep":
            facts = {d + "_surface"} | ({"square_deep"} if obj == "almanac_deep" else set())
        out = []
        for scar in (0, 4):
            rng = random.Random(seed)
            ok, left = 0, []
            for _ in range(trials):
                done, rounds, placed, st = play_loop(rng, n, 0.35, set(facts), layer == "deep", scar,
                                                     fx=fx, only={obj})
                if obj in done:
                    ok += 1
                    left.append(8 - st["done_hour"][obj])
            out.append((ok / trials, statistics.mean(left) if left else 0))
        print("{:25} |   {:>5.0%}   {:>4.1f}            |   {:>5.0%}   {:>4.1f}".format(
            obj, out[0][0], out[0][1], out[1][0], out[1][1]))


def compare_greed(trials, seed):
    """Efficient vs greedy Victory play, printed locations, first-time play."""
    print()
    print("Victory greed: 'efficient' ignores optional Victory; 'greedy' kills optional Victory")
    print("monsters, clears Victory locations before moving on and hunts the Named rider.")
    print("players | policy    | unlock median (10-90%) | never | obj/loop | Victory Memory by unlock | loops of extra aging")
    fx = LOCATION_PROFILES["spin"]
    for n in (1, 2, 3, 4):
        base = None
        for greedy in (False, True):
            rng = random.Random(seed)
            unlocks, objs, never, log = [], [], 0, []
            vps = []
            for _ in range(trials):
                sub = []
                u, per, _ = campaign(rng, n, 0.35, explore=True, fx=fx, log=sub, greedy=greedy)
                vps.append(sum(x["vp"] for x in sub))
                if u is None:
                    never += 1
                else:
                    unlocks.append(u)
                objs.extend(per)
            med = statistics.mean(unlocks) if unlocks else float("nan")
            if base is None:
                base = med
            rs = "{}-{}".format(pct(unlocks, 10), pct(unlocks, 90)) if unlocks else "-"
            print("   {}    | {:9} | {:>4.1f} ({:>5})           | {:>5.1%} | {:>8.2f} | {:>6.1f}                   | {:+.1f}".format(
                n, "greedy" if greedy else "efficient", med, rs, never / trials, statistics.mean(objs),
                statistics.mean(vps), med - base))


def compare(trials, seed):
    """Location profiles side by side (tax 0.35, first-time and finale-first)."""
    print()
    print("Location effects: 'none' = no location text, 'proposed' = the location cards")
    print("play      | players | profile  | unlock median (10-90%) | never | obj/loop | reset loops | harm/inv/loop | diss/loop | Memory/loop | Years/inv/loop (locations)")
    for explore in (True, False):
        for n in (1, 2, 3, 4):
            for prof in PROFILES_TO_COMPARE:
                rng = random.Random(seed)
                fx = LOCATION_PROFILES[prof]
                unlocks, objs, never, log = [], [], 0, []
                for _ in range(trials):
                    u, per, _ = campaign(rng, n, 0.35, explore=explore, fx=fx, log=log)
                    if u is None:
                        never += 1
                    else:
                        unlocks.append(u)
                    objs.extend(per)
                med = statistics.median(unlocks) if unlocks else float("nan")
                rs = "{}-{}".format(pct(unlocks, 10), pct(unlocks, 90)) if unlocks else "-"
                print("{:9} | {:>7} | {:8} | {:>4} ({:>5})           | {:>5.1%} | {:>8.2f} | {:>11.1%} | {:>13.2f} | {:>6.2f} | {:>6.2f} | {:>6.2f}".format(
                    "first" if explore else "planned", n, prof, med, rs, never / trials, statistics.mean(objs),
                    sum(1 for x in log if x["reset"]) / len(log),
                    statistics.mean(x["harm"] for x in log) / n,
                    statistics.mean(x["diss_fx"] for x in log),
                    statistics.mean(x["memory"] for x in log),
                    statistics.mean(x["years"] - x.get("struck", 0) * 0 for x in log) / n))


# --------------------------------------------------------------------------- #
# MEMORY (XP) INCOME — derived from the cards, not assumed
# --------------------------------------------------------------------------- #
# Memory comes from (1) each investigator's once-per-round Memory reaction,
# (2) Knowledge entries (guide, "Knowledge pays Memory": a surface entry gives
# each investigator 1 banked Memory, a deep entry 2, once per campaign),
# (3) Victory (once per campaign), (4) the Prologue (2 per investigator) and
# (5) the Elder/Ancient bracket (+1 Memory at the start of each loop).
# ASSUMPTION: chance per round that each investigator's Memory reaction
# triggers in typical play (card text in comments).
MEMORY_TRIGGER = {
    "Ayako": 0.80,      # after you succeed at an [int] test
    "Elias": 0.50,      # soak damage for an ally / attacked while alone (2 reactions)
    "Birdie": 0.45,     # after you fail a skill test by 2 or more
    "Cass": 0.35,       # 2 resources, then the named token must come up
    "Seraphine": 0.30,  # second use of her Dissonance ability in a round
}
PROLOGUE_MEMORY = 2       # per investigator (the average Prologue result)
# guide, "Knowledge pays Memory": per investigator, the first time an entry is recorded
KNOWLEDGE_PAYS = {"surface": int(os.environ.get("STHR_PAY_SURFACE", 0)), "deep": int(os.environ.get("STHR_PAY_DEEP", 2))}
ELDER_FROM_LOOP = 7       # ASSUMPTION: typical loop an investigator turns Elder


def memory_report(trials, seed):
    import itertools
    fx = LOCATION_PROFILES["spin"]
    names = sorted(MEMORY_TRIGGER)
    print()
    print("Memory (XP) income, first-time exploring play, tax 0.35 (per investigator):")
    print("players | party                        | per loop: min  typ  max | campaign total (10-90%)")
    for n in (1, 2, 3, 4):
        parties = [tuple(p) for p in itertools.combinations(names, n)]
        scored = []
        for party in parties:
            rng = random.Random(seed)
            per_loop, totals = [], []
            for _ in range(max(1, trials // len(parties))):
                log = []
                unlock, _, _ = campaign(rng, n, 0.35, explore=True, fx=fx, log=log)
                total = PROLOGUE_MEMORY * n
                for loop_i, st in enumerate(log, 1):
                    gain = sum(1 for who in party for _ in range(st["rounds"])
                               if rng.random() < MEMORY_TRIGGER[who])
                    gain += sum((KNOWLEDGE_PAYS["surface"] if OBJ[o][1] == "surface" else KNOWLEDGE_PAYS["deep"]) * n
                                for o in st["done"])
                    gain += st.get("vp", 0)
                    if loop_i >= ELDER_FROM_LOOP:
                        gain += n
                    per_loop.append(gain / n)
                    total += gain
                totals.append(total / n)
            scored.append((statistics.mean(totals), party, per_loop, totals))
        scored.sort()
        rows = [scored[0], scored[len(scored) // 2], scored[-1]] if len(scored) > 2 else scored
        for mean_total, party, per_loop, totals in rows:
            print("   {}    | {:28} |          {:>4.1f} {:>4.1f} {:>4.1f} | {:>5.1f} ({}-{})".format(
                n, ", ".join(party), pct(per_loop, 5), statistics.mean(per_loop), pct(per_loop, 95),
                mean_total, round(pct(totals, 10)), round(pct(totals, 90))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1729)
    ap.add_argument("--locations", choices=sorted(LOCATION_PROFILES), default="spin",
                    help="location effects to apply in the main table")
    ap.add_argument("--compare", action="store_true",
                    help="print only the location-profile comparison")
    ap.add_argument("--race", action="store_true",
                    help="print only the per-district race (objective vs Hourglass)")
    ap.add_argument("--greed", action="store_true",
                    help="print only the efficient-vs-greedy Victory comparison")
    ap.add_argument("--memory", action="store_true",
                    help="print only the Memory (XP) income derived from the cards")
    a = ap.parse_args()
    if a.memory:
        memory_report(a.trials, a.seed)
        return
    if a.compare:
        compare(a.trials, a.seed)
        return
    if a.greed:
        compare_greed(a.trials, a.seed)
        return
    if a.race:
        for n in (2, 3, 4):
            district_race(a.trials, a.seed, n)
        return
    rng = random.Random(a.seed)
    fx = LOCATION_PROFILES[a.locations]
    for explore in (False, True):
      print()
      print("Tempo: loops until the finale unlocks ({} play)".format(
          "exploring, first-time" if explore else "finale-first"))
      print("players | tax  | unlock loop median (10-90%) | never by 15 | objectives/loop | districts/loop")
      for n in (1, 2, 3, 4):
        for tax in TAX_LEVELS:
            unlocks, objs, dists, never = [], [], [], 0
            for _ in range(a.trials):
                u, per, ds = campaign(rng, n, tax, explore=explore, fx=fx)
                if u is None:
                    never += 1
                else:
                    unlocks.append(u)
                objs.extend(per)
                dists.extend(ds)
            med = statistics.median(unlocks) if unlocks else float("nan")
            rng_s = "{}-{}".format(pct(unlocks, 10), pct(unlocks, 90)) if unlocks else "-"
            print("   {}    | {:.2f} | {:>4} ({:>5})               | {:>5.1%}      | {:.2f}            | {:.2f}".format(
                n, tax, med, rng_s, never / a.trials, statistics.mean(objs), statistics.mean(dists)))


if __name__ == "__main__":
    main()
