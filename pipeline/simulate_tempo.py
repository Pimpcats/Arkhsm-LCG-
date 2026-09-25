#!/usr/bin/env python3
"""
simulate_tempo.py — THE STILL HOUR act-vs-clock race (tempo) simulator.

pipeline/simulate.py models the clock, Dissonance, Memory, aging and the
finale; it never asks whether a party can actually travel, gather clues and
complete objectives before the Hourglass reaches Hour IX. This does.

One loop is played round by round:
  * Mythos (from round 2): the current Hour's doom threshold is 1, so the
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
# ASSUMPTION: Dissonance gained per round (deck + typical foreknowledge use).
DISSONANCE_PER_ROUND = 1.3
# ASSUMPTION: extra party actions a Named enemy costs when it guards an objective.
NAMED_COST = {"square_deep": 8, "church_deep": 6}
SPINE_SIZE = 25          # 24-card spine + The Crossing (CONTENT_DECISIONS D4/D5)
LOST_HOURS = 3

# Districts: node-set size and Skip cards in it (count, chance it triggers).
DISTRICT = {
    "square": {"set": 2, "skips": []},
    "almanac": {"set": 3, "skips": []},
    "fairground": {"set": 2, "skips": [(1, 1.0)]},     # The Wheel's Turn
    "church": {"set": 3, "skips": [(1, 0.8)]},         # Thirteen (if at the Church)
    "road": {"set": 2, "skips": [(1, 0.4)]},           # The Bridge Remembers
    "lighthouse": {"set": 2, "skips": []},
}
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
# act allows, as (shroud, clues per investigator); from the location cards.
OBJ = {
    "square_surface": ("square", "surface", [("clues", 5, [(1, 2), (2, 2), (2, 2), (3, 3)]), ("act", 1)]),
    "square_deep": ("square", "deep", [("named", "square_deep"), ("clues", 3, [(4, 3)])]),
    "almanac_surface": ("almanac", "surface", [("clues_pi", 2, [(2, 2), (3, 3)]), ("act", 1)]),
    "almanac_deep": ("almanac", "deep", [("move", 1), ("clues", 3, [(4, 3)])]),
    "fairground_surface": ("fairground", "surface", [("test", "agi", 3)]),
    "fairground_deep": ("fairground", "deep", [("move", 1), ("act", 1)]),
    "church_surface": ("church", "surface", [("clues", 6, [(2, 3), (3, 2), (2, 2)]), ("act", 1)]),
    "church_deep": ("church", "deep", [("named", "church_deep"), ("clues", 3, [(4, 3)])]),
    "road_surface": ("road", "surface", [("move", 1), ("clues", 1, [(2, 3)]), ("move", 1),
                                         ("clues", 1, [(3, 2)]), ("move", 1), ("clues", 1, [(1, 2)])]),
    "road_deep": ("road", "deep", [("glitch",), ("move", 1), ("test", "agi", 3)]),
    "lighthouse_surface": ("lighthouse", "surface", [("clues", 4, [(2, 1), (2, 2), (4, 2)]), ("test", "wil", 3)]),
    "lighthouse_deep": ("lighthouse", "deep", [("act", 1), ("move", 1), ("clues", 2, [(2, 2)])]),
}
# ASSUMPTION: finale-first priority (the party is heading for the finale).
PRIORITY = ["square_surface", "almanac_surface", "fairground_surface",
            "square_deep", "almanac_deep", "fairground_deep",
            "church_surface", "road_surface", "church_deep", "road_deep",
            "lighthouse_surface", "lighthouse_deep"]


def band_for(diss, n):
    reset = 9 if n == 1 else 6 * n
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


def play_loop(rng, n, tax, facts, act2, scar, explore=False):
    party = PARTY[n]
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
    # group by district in first-appearance order, Square first
    order = ["square"] + [OBJ[o][0] for o in plan if OBJ[o][0] != "square"]
    districts = list(dict.fromkeys(order))
    tasks = []
    here = "square"
    free_lighthouse = "road_surface" in facts
    placed = {"square"}
    for d in districts:
        objs = [o for o in plan if OBJ[o][0] == d]
        # deep objectives open only once the surface is recorded; surface first
        objs.sort(key=lambda o: OBJ[o][1] != "surface")
        if not objs:
            continue
        for a, b in crossings(here, d):
            free = free_lighthouse and "lighthouse" in (a, b)
            tasks.append(("travel", b, 0 if free else 1))
            if free:
                free_lighthouse = False
        here = d
        for o in objs:
            tasks.append(("begin", o))
            tasks.extend(OBJ[o][2])
            tasks.append(("done", o))
    done = []
    deck = SPINE_SIZE + DISTRICT["square"]["set"] + (2 if act2 else 0)
    skip_cards = []
    cur, progress, supply = None, 0, None
    rounds = 0
    ti = 0
    while True:
        rounds += 1
        if rounds > 1:
            draws = n + (n if hour == 1 else 0)          # Hour II: extra draw
            adv = 1
            for _ in range(draws):
                r = rng.random() * deck
                if r < LOST_HOURS:
                    adv += 2 if hour >= 5 else 1
                else:
                    r -= LOST_HOURS
                    for cnt, p in skip_cards:
                        if r < cnt:
                            if rng.random() < p:
                                adv += 1
                            break
                        r -= cnt
            hour += adv
            diss += DISSONANCE_PER_ROUND
            if hour >= hours_total:
                break
        band = band_for(diss, n)
        budget = sum(1 for _ in range(n * ACTIONS) if rng.random() >= tax)
        actor = 0
        while budget > 0 and ti < len(tasks):
            t = tasks[ti]
            k = t[0]
            if k == "travel":
                budget -= min(budget, n)          # everyone moves
                hour += t[2]
                d = t[1]
                if d not in placed:
                    placed.add(d)
                    deck += DISTRICT[d]["set"]
                    skip_cards += DISTRICT[d]["skips"]
                ti += 1
                if hour >= hours_total:
                    break
            elif k == "begin":
                if prereq_met(t[1], facts | set(done)):
                    ti += 1
                else:                               # skip to after its "done"
                    ti = tasks.index(("done", t[1]), ti) + 1
            elif k == "done":
                done.append(t[1])
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
                    cur, supply = ti, [[s, c * n] for s, c in sorted(t[2])]
                    progress = 0
                loc = next((s for s in supply if s[1] > 0), None)
                if loc is None:
                    ti += 1                         # feasibility is audited elsewhere
                    continue
                budget -= 1
                skill = party["int"][actor % n] + BOOST
                actor += 1
                if rng.random() < success_probability(skill - loc[0], band):
                    loc[1] -= 1
                    progress += 1
                if progress >= need:
                    progress, supply = 0, None
                    ti += 1
        if ti >= len(tasks):
            break
        if hour >= hours_total:
            break
    return done, rounds, len(placed)


def campaign(rng, n, tax, max_loops=15, explore=False):
    facts, act2 = set(), False
    per_loop, districts = [], []
    for loop in range(1, max_loops + 1):
        done, rounds, placed = play_loop(rng, n, tax, facts, act2, min(loop - 1, 6), explore)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1729)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    for explore in (False, True):
      print()
      print("Tempo: loops until the finale unlocks ({} play)".format(
          "exploring, first-time" if explore else "finale-first"))
      print("players | tax  | unlock loop median (10-90%) | never by 15 | objectives/loop | districts/loop")
      for n in (1, 2, 3, 4):
        for tax in TAX_LEVELS:
            unlocks, objs, dists, never = [], [], [], 0
            for _ in range(a.trials):
                u, per, ds = campaign(rng, n, tax, explore=explore)
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
