#!/usr/bin/env python3
"""
simulate.py — THE STILL HOUR offline balance simulator.

This is the "run simulations" capability the design docs lean on when they cite
numbers like "~25% at delta 0" or "~17 Memory/loop". It is a math / Monte-Carlo
model of the four balance-bearing systems — it validates the MATH, not the fun
(rules-interaction surprises and drama still need real table play in TTS).

Four reports, each with pass/fail assertions where the design docs give a target:
  1. Success curve      — chaos-bag success % by test delta and Dissonance band.
  2. Memory economy      — banked/loop and the per-investigator campaign total,
                           checked against the official Arkham XP benchmark (~40-50).
  3. Dissonance pacing   — rounds to the Appointed's arrival / reset for cautious vs greedy.
  4. Aging spread        — final bracket distribution by playstyle over a campaign.

Run:
  python3 pipeline/simulate.py                 # full report + assertions
  python3 pipeline/simulate.py --trials 40000
  python3 pipeline/simulate.py --loops 7 --investigators 3
  python3 pipeline/simulate.py --quiet         # assertions only (CI use)

Every model assumption is labelled ASSUMPTION and is a single named constant so
it is easy to re-tune when table play refines it.
"""
import argparse
import json
import os
import re
import random
import statistics

# --------------------------------------------------------------------------- #
# CHAOS BAG MODEL
# --------------------------------------------------------------------------- #
# A "Standard"-difficulty bag calibrated so that the calm-bag success curve
# reproduces the design doc's headline numbers exactly: 25% / 56% / 75% at
# delta 0 / +1 / +2 (cards_v0.2 §D). "AUTOFAIL" always fails regardless of delta
# (that is why overkill tests never hit 100%). Symbol tokens are given generic
# campaign modifiers; ELDER is treated as a flat +1 baseline.
#
# ASSUMPTION: this token list. The design docs never print the exact bag; this
# one is reverse-engineered to hit the documented curve, then reused for the
# band comparison. Swap it here if the campaign ships a different Standard bag.
AUTOFAIL = "autofail"
BASE_BAG = [
    1, 0, 0, -1, -1, -1, -2, -2, -3, -4,   # numeric tokens
    -1, -1,        # two Skulls
    -2,            # Cultist
    -3,            # Tablet
    1,             # Elder Sign (flat +1 assumption)
    AUTOFAIL,      # auto-fail
]
STATIC_MODIFIER = -3           # the [static] token (encounter v0.4 §0)
STATIC_BY_BAND = {"Calm": 0, "Glitch": 1, "Noticed": 2}


def bag_for_band(band):
    return list(BASE_BAG) + [STATIC_MODIFIER] * STATIC_BY_BAND[band]


def success_probability(delta, band):
    """Exact (enumerated) success probability for a single-token draw."""
    bag = bag_for_band(band)
    wins = 0
    for tok in bag:
        if tok == AUTOFAIL:
            continue
        if tok + delta >= 0:
            wins += 1
    return wins / len(bag)


# --------------------------------------------------------------------------- #
# MEMORY ECONOMY MODEL
# --------------------------------------------------------------------------- #
# The shared pool banks a per-loop income the docs peg at ~17 Memory/loop for a
# 3-player table (5-95th percentile 14-20; aging_3p_v0.3 §2.1). Memory carried
# into the next loop is soft-capped at 6*investigators. The campaign runs ~7
# loops (guide §10). Total Memory EARNED across the campaign, divided per
# investigator, is the XP-analog we benchmark against official Arkham
# (~40-50 XP/investigator/campaign; CO-001).
#
# ASSUMPTION: income ~ Normal(mean per player, sd) clipped, summed over players.
INCOME_MEAN_PER_PLAYER = 17 / 3      # ~5.67 Memory/loop/player -> ~17 at 3p
INCOME_SD_PER_PLAYER = 1.1           # tuned so the 3p total lands 14-20 (5-95th)
BENCHMARK_LOW, BENCHMARK_HIGH = 40, 50


def simulate_economy(trials, loops, investigators, rng):
    per_investigator_totals = []
    per_loop_samples = []
    for _ in range(trials):
        earned_total = 0.0
        carry = 0.0
        for _loop in range(loops):
            income = 0.0
            for _p in range(investigators):
                income += max(0.0, rng.gauss(INCOME_MEAN_PER_PLAYER, INCOME_SD_PER_PLAYER))
            per_loop_samples.append(income)
            earned_total += income
            # Interlude order is bank -> spend -> (next loop start) cap, so the
            # cap binds only what you CARRY, not what you earn: a spend-all party
            # (CO-001 gives level-ups as a deep sink) carries 0 and wastes 0. The
            # cap is an anti-hoarding governor, not an income ceiling.
            carry = 0.0
        per_investigator_totals.append(earned_total / investigators)
    return {
        "per_investigator_mean": statistics.mean(per_investigator_totals),
        "per_investigator_p05": percentile(per_investigator_totals, 5),
        "per_investigator_p95": percentile(per_investigator_totals, 95),
        "per_loop_mean": statistics.mean(per_loop_samples),
        "per_loop_p05": percentile(per_loop_samples, 5),
        "per_loop_p95": percentile(per_loop_samples, 95),
    }


# --------------------------------------------------------------------------- #
# DISSONANCE PACING MODEL
# --------------------------------------------------------------------------- #
# Dissonance climbs ~0.8/round from the mythos deck alone (encounter v0.4 §8);
# foreknowledge use is the primary driver. Cautious play adds little; greedy play
# leans on Recollections/loop-powers and self-inflicts Dissonance.
#
# ASSUMPTION: per-round Dissonance gain per style (mean, sd). Targets from the
# docs: cautious ~13 rounds to the Appointed; greedy ~5.5 to the Appointed, ~8 to
# reset (aging_3p_v0.3 §2.2).
DECK_DISSONANCE_PER_ROUND = 0.8
STYLE_EXTRA = {           # extra Dissonance/round from foreknowledge use
    "cautious": (0.15, 0.2),
    "greedy": (1.5, 0.5),
}


def simulate_pacing(trials, investigators, rng, style, threshold):
    rounds_list = []
    for _ in range(trials):
        d = 0.0
        r = 0
        mean_extra, sd_extra = STYLE_EXTRA[style]
        while d < threshold and r < 100:
            r += 1
            gain = DECK_DISSONANCE_PER_ROUND + max(0.0, rng.gauss(mean_extra, sd_extra))
            d += gain
        rounds_list.append(r)
    return statistics.mean(rounds_list)


# --------------------------------------------------------------------------- #
# AGING SPREAD MODEL
# --------------------------------------------------------------------------- #
# Years/loop: clean +1, typical +2, reckless +4 (aging_3p_v0.3 §1.1). Over a
# ~7-loop campaign this should land clean players ~Weathered, typical ~Elder,
# reckless Ancient / aged-out (guide §10).
YEARS_PER_LOOP = {"clean": (1, 0.0), "typical": (2, 0.5), "reckless": (4, 0.7)}


def bracket_for_years(y):
    if y >= 18:
        return "Aged out"
    if y >= 15:
        return "Ancient"
    if y >= 10:
        return "Elder"
    if y >= 5:
        return "Weathered"
    return "Prime"


def simulate_aging(trials, loops, rng, style):
    finals = {}
    for _ in range(trials):
        mean_y, sd_y = YEARS_PER_LOOP[style]
        years = 0
        for _loop in range(loops):
            years += max(1, round(rng.gauss(mean_y, sd_y)))
        b = bracket_for_years(years)
        finals[b] = finals.get(b, 0) + 1
    return {k: v / trials for k, v in finals.items()}


# --------------------------------------------------------------------------- #
# XP (MEMORY) DISTRIBUTION — how often a loop yields max vs minimal Memory
# --------------------------------------------------------------------------- #
# "A scenario" in this campaign is a loop (it spans 2-3 nodes). Memory is the
# XP-analog. "Max" = income at/above the carry cap (6 x investigators = 18 at
# 3p). NOTE the rules order (bank -> spend -> cap at next loop start): income
# above the cap is NOT wasted — it must be SPENT that interlude or lost. The
# cap is a forced-spend line, and it only destroys Memory a party hoards past
# it. Minimal = the low-income tail. Same income model as simulate_economy.
def simulate_xp_distribution(trials, investigators, rng):
    cap = 6 * investigators
    per_loop = []
    for _ in range(trials):
        income = 0.0
        for _p in range(investigators):
            income += max(0.0, rng.gauss(INCOME_MEAN_PER_PLAYER, INCOME_SD_PER_PLAYER))
        per_loop.append(income)
    at_or_above_cap = sum(1 for x in per_loop if x >= cap) / trials
    low = percentile(per_loop, 5)
    at_or_below_low = sum(1 for x in per_loop if x <= low) / trials
    # integer buckets for a compact histogram
    buckets = {}
    for x in per_loop:
        b = int(round(x))
        buckets[b] = buckets.get(b, 0) + 1
    hist = sorted((b, c / trials) for b, c in buckets.items())
    return {
        "cap": cap, "mean": statistics.mean(per_loop),
        "p05": low, "p50": percentile(per_loop, 50), "p95": percentile(per_loop, 95),
        "pct_max": at_or_above_cap, "pct_min": at_or_below_low, "hist": hist,
    }


# --------------------------------------------------------------------------- #
# BALANCE STRESS TEST — push each playstyle to failure and measure the rates
# --------------------------------------------------------------------------- #
# One loop, round by round: the Hourglass advances ~1.5 Hours/round (baseline +
# deck Skips, encounter v0.4 §8); Dissonance climbs deck(0.8) + playstyle. The
# loop ends at Hour IX (a natural reset) or Dissonance = reset threshold (a HARD
# reset — the loop closed its hand on you). The Appointed's stage is derived from
# the clock (V/VII/VIII) and bands (Glitch/Noticed), matching Appointed.ttslua.
# ASSUMPTION: per-round Hour advance and the playstyle Dissonance gains.
HOUR_PER_ROUND_MEAN = 1.5
HOUR_PER_ROUND_SD = 0.3
STRESS_STYLES = {           # extra Dissonance/round from foreknowledge use
    "cautious": (0.15, 0.20),
    "typical":  (0.70, 0.40),
    "greedy":   (1.50, 0.50),
}


def simulate_stress_loop(rng, investigators, style, scar=0):
    reset_t = 6 * investigators if investigators != 1 else 9
    glitch = reset_t // 3
    noticed = 2 * reset_t // 3
    mean_extra, sd_extra = STRESS_STYLES[style]
    # scar floor = start-of-loop Dissonance (= completed loops, capped) — this is
    # how greedy play compounds across a campaign.
    hour, diss, rounds = 1.0, float(scar), 0
    arrived = False
    arrived_round = None
    while True:
        rounds += 1
        hour += max(0.5, rng.gauss(HOUR_PER_ROUND_MEAN, HOUR_PER_ROUND_SD))
        diss += DECK_DISSONANCE_PER_ROUND + max(0.0, rng.gauss(mean_extra, sd_extra))
        stage = 0
        if hour >= 5: stage = max(stage, 1)
        if hour >= 7: stage = max(stage, 2)
        if hour >= 8: stage = 3
        if diss >= noticed: stage = 3
        elif diss >= glitch: stage = max(stage, 1)
        if stage >= 3 and not arrived:
            arrived, arrived_round = True, rounds
        if diss >= reset_t:
            return {"hard_reset": True, "arrived": arrived, "rounds": rounds, "arrived_round": arrived_round}
        if hour >= 9 or rounds >= 60:
            return {"hard_reset": False, "arrived": arrived, "rounds": rounds, "arrived_round": arrived_round}


def simulate_stress(trials, investigators, rng, style, scar=0):
    hard, arrived, rounds_sum, arr_rounds = 0, 0, 0, []
    for _ in range(trials):
        r = simulate_stress_loop(rng, investigators, style, scar)
        hard += 1 if r["hard_reset"] else 0
        arrived += 1 if r["arrived"] else 0
        rounds_sum += r["rounds"]
        if r["arrived_round"] is not None:
            arr_rounds.append(r["arrived_round"])
    return {
        "hard_reset_rate": hard / trials,
        "appointed_arrival_rate": arrived / trials,
        "avg_rounds": rounds_sum / trials,
        "avg_arrival_round": (statistics.mean(arr_rounds) if arr_rounds else None),
    }


# --------------------------------------------------------------------------- #
# FINALE CONTEST — stage-aware model of "contest the crossing"
# --------------------------------------------------------------------------- #
# Target = 4 x investigators (12 at 3p). Deep facts spent add 1 contest each at
# the start. Each round every investigator may attempt one Hold Back (wil/com 4);
# a success adds 1 contest, pushes the Appointed back ONE APPROACH STAGE, and
# rewinds the Hourglass 1 Hour. The self-limiters the naive model missed:
#   * Hold Back needs the Appointed MANIFEST (stage >= 1) — pushed to Unseen, it
#     can't be farmed until the clock re-raises it.
#   * Hour "when reached" effects re-fire on re-crossing after a rewind
#     (Hourglass.advance resolves every newly stepped Hour): re-crossing VIII
#     re-Arrives it AND raises Dissonance +2; III adds +1.
#   * Dissonance does not reset in the finale and still climbs from the deck; at
#     the reset threshold (18) the finale is LOST (the loop closes its hand).
# ASSUMPTIONS: Hold Back success p; deck Dissonance 0.8/round; finale declared at
# start_hour with Dissonance = start_diss; one attempt per investigator per round.
def simulate_finale_staged(rng, investigators, deep_facts, holdback_p, trials,
                           start_hour=5.0, start_diss=12.0):
    target = 4 * investigators
    reset_t = 6 * investigators if investigators != 1 else 9
    reached = 0
    for _ in range(trials):
        contest = deep_facts
        hour = start_hour
        diss = start_diss
        stage = 3                      # enters the finale Arrived
        rounds = 0
        won = False
        while rounds < 40:
            rounds += 1
            # mythos: clock advances, resolving each crossed Hour's effect
            new_hour = hour + max(0.5, rng.gauss(HOUR_PER_ROUND_MEAN, HOUR_PER_ROUND_SD))
            for h in range(int(hour) + 1, int(new_hour) + 1):
                if h == 3:
                    diss += 1
                elif h == 5:
                    stage = max(stage, 1)
                elif h == 7:
                    stage = max(stage, 2)
                elif h == 8:
                    diss += 2
                    stage = 3
            hour = new_hour
            diss += DECK_DISSONANCE_PER_ROUND
            if hour >= 9 or diss >= reset_t:
                break                  # night ends or the loop closes: not reached
            # investigators: one Hold Back attempt each while it is manifest
            for _i in range(investigators):
                if stage >= 1 and contest < target and rng.random() < holdback_p:
                    contest += 1
                    stage -= 1
                    hour = max(1.0, hour - 1)   # rewind (no re-resolve on rewind)
            if contest >= target:
                won = True
                break
        if won:
            reached += 1
    return reached / trials


# --------------------------------------------------------------------------- #
def percentile(data, p):
    s = sorted(data)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser(description="THE STILL HOUR balance simulator.")
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--loops", type=int, default=7)
    ap.add_argument("--investigators", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1729)
    ap.add_argument("--quiet", action="store_true", help="assertions only")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    n = args.investigators

    failures = []

    def assert_(name, cond):
        status = "PASS" if cond else "FAIL"
        if not cond:
            failures.append(name)
        if not args.quiet:
            print(f"  [{status}] {name}")

    # ---- 1. success curve ----
    if not args.quiet:
        print("\n== 1. Chaos-bag success curve (exact) ==")
        print("  delta |  Calm  Glitch Noticed")
        for delta in range(0, 4):
            row = "  {:+5d} | {}".format(
                delta,
                " ".join("{:5.0f}%".format(100 * success_probability(delta, b))
                         for b in ("Calm", "Glitch", "Noticed")))
            print(row)
    assert_("calm curve 25/56/75 at delta 0/+1/+2 (within 1pt)",
            abs(success_probability(0, "Calm") - 0.25) < 0.01
            and abs(success_probability(1, "Calm") - 0.5625) < 0.01
            and abs(success_probability(2, "Calm") - 0.75) < 0.01)
    assert_("Noticed band squeezes marginal (delta+1) tests vs Calm",
            success_probability(1, "Noticed") < success_probability(1, "Calm"))
    assert_("overkill never reaches 100% (autofail floor)",
            success_probability(3, "Calm") < 1.0)

    # ---- 2. economy ----
    econ = simulate_economy(args.trials, args.loops, n, rng)
    if not args.quiet:
        print("\n== 2. Memory economy ({}p, {} loops, {} trials) ==".format(n, args.loops, args.trials))
        print("  banked/loop:        mean {:.1f}  (5-95th {:.1f}-{:.1f})".format(
            econ["per_loop_mean"], econ["per_loop_p05"], econ["per_loop_p95"]))
        print("  per investigator:   mean {:.1f}  (5-95th {:.1f}-{:.1f})   benchmark {}-{}".format(
            econ["per_investigator_mean"], econ["per_investigator_p05"],
            econ["per_investigator_p95"], BENCHMARK_LOW, BENCHMARK_HIGH))
    # The per-investigator total scales with campaign length (~6-8 loops, guide
    # §10). The official-XP benchmark (40-50) is reached across that window; show
    # the whole window so the length dependence is explicit rather than hidden in
    # a single --loops value. The 18/loop cap is the governor that stops the loop
    # structure from inflating the total past this.
    window = {L: L * econ["per_loop_mean"] / n for L in (6, 7, 8)}
    if not args.quiet:
        print("  campaign total by length (per investigator):")
        for L in (6, 7, 8):
            tag = " <- benchmark 40-50" if BENCHMARK_LOW <= window[L] <= BENCHMARK_HIGH else ""
            print("    {} loops: {:.1f}{}".format(L, window[L], tag))
    if n == 3:
        assert_("3p banked/loop ~17 (14-20 band)",
                14 <= econ["per_loop_mean"] <= 20)
        assert_("a 6-8 loop campaign reaches the official-XP benchmark (40-50/inv)",
                any(BENCHMARK_LOW <= v <= BENCHMARK_HIGH for v in window.values()))

    # ---- 3. pacing ----
    reset_threshold = 6 * n if n != 1 else 9
    appointed_threshold = 4 * n if n != 1 else 6
    cautious = simulate_pacing(args.trials, n, rng, "cautious", appointed_threshold)
    greedy_late = simulate_pacing(args.trials, n, rng, "greedy", appointed_threshold)
    greedy_reset = simulate_pacing(args.trials, n, rng, "greedy", reset_threshold)
    if not args.quiet:
        print("\n== 3. Dissonance pacing (rounds) ==")
        print("  cautious -> Appointed ({}): {:.1f}".format(appointed_threshold, cautious))
        print("  greedy   -> Appointed ({}): {:.1f}".format(appointed_threshold, greedy_late))
        print("  greedy   -> reset     ({}): {:.1f}".format(reset_threshold, greedy_reset))
    assert_("cautious reaches the Appointed later than greedy", cautious > greedy_late)
    assert_("greedy wakes the Appointed mid-node (4-8 rounds)", 4 <= greedy_late <= 8)

    # ---- 4. aging ----
    if not args.quiet:
        print("\n== 4. Aging spread over {} loops ==".format(args.loops))
        for style in ("clean", "typical", "reckless"):
            dist = simulate_aging(args.trials, args.loops, rng, style)
            summary = ", ".join("{} {:.0%}".format(k, v)
                                for k, v in sorted(dist.items(), key=lambda kv: -kv[1]))
            print("  {:8s}: {}".format(style, summary))
    clean = simulate_aging(args.trials, args.loops, rng, "clean")
    typical = simulate_aging(args.trials, args.loops, rng, "typical")
    assert_("clean players land ~Weathered by the finale",
            clean.get("Weathered", 0) > 0.5)
    assert_("typical players land ~Elder by the finale",
            typical.get("Elder", 0) > 0.4)
    if not args.quiet:
        # When does sustained play cross the age-out line (18 Years)?
        print("  age-out timing (loops of sustained play to reach 18 Years):")
        for style, (mean_y, _sd) in sorted(YEARS_PER_LOOP.items(), key=lambda kv: -kv[1][0]):
            print("    {:8s}: ~{:.1f} loops".format(style, 18 / mean_y))
        print("  NOTE: sustained reckless play ages out at ~loop 5 — at or before a")
        print("  typical finale (openable ~loop 4, tuned length 6-8). See BALANCE.md flag.")

    # ---- 5. XP (Memory) distribution: how often a loop yields max vs minimal ----
    xp = simulate_xp_distribution(args.trials, n, rng)
    if not args.quiet:
        print("\n== 5. Memory (XP) per loop — distribution ({}p, {} trials) ==".format(n, args.trials))
        print("  shared pool/loop: median {:.0f}, 5-95th {:.0f}-{:.0f}  (carry cap {})".format(
            xp["p50"], xp["p05"], xp["p95"], xp["cap"]))
        print("  MAX  XP  (income >= carry cap {}; must spend the excess that interlude or lose it): {:.1%} of loops".format(
            xp["cap"], xp["pct_max"]))
        print("  MIN  XP  (bottom 5% tail, <= {:.0f}):   {:.1%} of loops".format(xp["p05"], xp["pct_min"]))
        print("  per-investigator equivalent: median {:.1f}, max {:.0f}".format(xp["p50"] / n, xp["cap"] / n))
        print("  histogram (shared/loop):")
        for b, share in xp["hist"]:
            if share >= 0.005:
                bar = "#" * int(round(share * 100))
                mark = "  <- max/cap" if b >= xp["cap"] else ""
                print("    {:>2}: {:5.1%} {}{}".format(b, share, bar, mark))

    # ---- 6. balance stress test ----
    scar_cap = reset_threshold // 3
    if not args.quiet:
        print("\n== 6. Balance stress test ({}p, {} trials/style) ==".format(n, args.trials))
        print("  fresh loop (scar 0):")
        print("  playstyle | hard-reset | Appointed Arrives | avg rounds | avg arrival round")
        for style in ("cautious", "typical", "greedy"):
            s = simulate_stress(args.trials, n, rng, style)
            ar = "{:.1f}".format(s["avg_arrival_round"]) if s["avg_arrival_round"] else "  -"
            print("  {:9s} |   {:5.1%}   |      {:5.1%}       |    {:4.1f}    |     {}".format(
                style, s["hard_reset_rate"], s["appointed_arrival_rate"], s["avg_rounds"], ar))
        # The reset threat compounds across a campaign via the scar floor.
        print("\n  hard-reset % as the scar floor rises (late-campaign loops):")
        print("  scar floor |  cautious   typical    greedy")
        for scar in range(0, scar_cap + 1, 2):
            cells = "  ".join("{:6.1%}".format(simulate_stress(args.trials // 2, n, rng, st, scar)["hard_reset_rate"])
                              for st in ("cautious", "typical", "greedy"))
            print("      {}      |  {}".format(scar, cells))
        print("\n  Finale contest reach % — STAGE-AWARE model (target {} = 4x inv;".format(4 * n))
        print("  Approach stages, re-fired Hour crossings, Dissonance-18 loss all modelled).")
        print("  The declared-at Dissonance dominates — declaring early in a calm loop vs")
        print("  at the Noticed band is the strategic choice the numbers reward:")
        print("  declared at Dissonance \\ Hold-Back p |  0.40   0.50   0.60   (4 deep facts)")
        for d0 in (6, 9, 12):
            cells = " ".join("{:5.1%}".format(
                simulate_finale_staged(rng, n, 4, p, max(4000, args.trials // 4), start_diss=float(d0)))
                for p in (0.40, 0.50, 0.60))
            print("             {:2d}                        | {}".format(d0, cells))
        print("  deep facts axis (declared at Dissonance 9, p=0.50): " + "  ".join(
            "{}f={:.0%}".format(f, simulate_finale_staged(rng, n, f, 0.50,
                                                          max(4000, args.trials // 4), start_diss=9.0))
            for f in (3, 4, 5)))

    # stress-test sanity assertions — hard-resets are clock-gated (Hour IX ends the
    # night first), so the reset threat is a CAMPAIGN pressure via the scar, not a
    # single-loop one. Verify the scar makes greedy degrade.
    fresh_greedy = simulate_stress(args.trials, n, rng, "greedy", 0)
    scarred_greedy = simulate_stress(args.trials, n, rng, "greedy", scar_cap)
    assert_("fresh loop rarely hard-resets for any style (clock ends it first, < 10%)",
            fresh_greedy["hard_reset_rate"] < 0.10)
    assert_("the scar floor makes greedy hard-reset materially more late-campaign",
            scarred_greedy["hard_reset_rate"] > fresh_greedy["hard_reset_rate"] + 0.10)
    assert_("the Appointed arrives almost every loop (clock-driven, > 90%)",
            fresh_greedy["appointed_arrival_rate"] > 0.90)

    # ---- 7. code <-> data audit (cross-checks, not simulation) ----
    here = os.path.dirname(os.path.abspath(__file__))
    if not args.quiet:
        print("\n== 7. Code <-> data audit ==")
    # Recollection Memory prices: Interlude.RECOLLECTION_COST must match the
    # card spec's memoryCost per id (one source of truth, two copies).
    spec = {c["id"]: c["memoryCost"]
            for c in json.load(open(os.path.join(here, "stillhour_cards_spec.json")))
            if "memoryCost" in c}
    lua = open(os.path.join(here, "..", "src", "StillHour", "Interlude.ttslua")).read()
    lua_costs = dict(re.findall(r'\["(sthr-[a-z]+)"\]\s*=\s*(\d+)', lua))
    lua_costs = {k: int(v) for k, v in lua_costs.items()}
    mismatches = sorted(set(spec) ^ set(lua_costs)) + sorted(
        k for k in set(spec) & set(lua_costs) if spec[k] != lua_costs[k])
    if not args.quiet:
        print("  Recollection prices: {} in spec, {} in Interlude.ttslua, {} mismatch(es)".format(
            len(spec), len(lua_costs), len(mismatches)))
        for k in mismatches:
            print("    MISMATCH {}: spec={} lua={}".format(k, spec.get(k), lua_costs.get(k)))
    assert_("Interlude Recollection prices match the card spec", not mismatches)
    # Threshold formulas: bands must partition [0, reset) and Noticed must start
    # exactly at the Appointed threshold for 2-4 players (solo is a documented
    # override with its own numbers).
    ok_bands = True
    for m in (2, 3, 4):
        reset = 6 * m
        if not (reset // 3 < 2 * reset // 3 < reset and 2 * reset // 3 == 4 * m):
            ok_bands = False
    assert_("bands partition cleanly and Noticed start == Appointed threshold (2-4p)", ok_bands)

    # ---- verdict ----
    print("\nSIMULATION RESULT: {} assertion(s) failed{}".format(
        len(failures), "" if not failures else " -> " + "; ".join(failures)))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
