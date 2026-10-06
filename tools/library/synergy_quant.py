#!/usr/bin/env python3
"""synergy_quant.py - back-of-envelope numbers for the investigators' own abilities (designer tooling).

The scan (synergy_scan.py) finds which cards touch an ability. This script answers "how big is the
ability itself" with explicit, adjustable assumptions, so a reviewer can compare it with an official
investigator that has a similar engine. Exact enumeration over the Standard chaos bag for token
questions; seeded Monte Carlo (seed 1) for the deck, resolve and horror questions. Nothing here is a
playtest and nothing replaces the engine simulation in tools/play_engine.

    python3 tools/library/synergy_quant.py            # print every table
    python3 tools/library/synergy_quant.py cass       # one investigator
    python3 tools/library/synergy_quant.py interactions   # per-round value of the strongest pairings
    python3 tools/library/synergy_quant.py --tests 4  # change the tests-per-round assumption

Assumptions (override with flags): 3 skill tests per investigator per round; Standard chaos bag
from the player guide (+1, 0, 0, -1, -1, -1, -2, -2, -3, -4, skull x2, cultist, tablet, elder thing,
auto-fail, elder sign); symbol modifiers skull -2, cultist -2, tablet -3, elder thing -4 (the
scenario reference card sets the real values); a loop of 11 rounds.
"""
import argparse
import itertools
import math
import random

BAG = ["+1", "0", "0", "-1", "-1", "-1", "-2", "-2", "-3", "-4",
       "skull", "skull", "cultist", "tablet", "elder_thing", "autofail", "elder"]
SYMBOL_MOD = {"skull": -2, "cultist": -2, "tablet": -3, "elder_thing": -4}
SYMBOLS_NARROW = {"skull", "cultist", "tablet", "elder_thing"}           # the four scenario symbols
SYMBOLS_WIDE = SYMBOLS_NARROW | {"autofail"}                              # plus auto-fail
SYMBOLS_WIDEST = SYMBOLS_WIDE | {"elder"}                                 # plus the elder sign


def modifier(tok, elder=1):
    if tok == "autofail":
        return None
    if tok == "elder":
        return elder
    if tok in SYMBOL_MOD:
        return SYMBOL_MOD[tok]
    return int(tok)


def p_success(skill, difficulty, elder=1, bag=BAG):
    """P(test succeeds) with one token, exact."""
    ok = 0
    for t in bag:
        m = modifier(t, elder)
        if m is not None and skill + m >= difficulty:
            ok += 1
    return ok / len(bag)


def p_any(q, tests):
    return 1 - (1 - q) ** tests


# ---------------------------------------------------------------- Cass
def cass(tests=3):
    out = {}
    for name, sym in (("skull/cultist/tablet/elder thing", SYMBOLS_NARROW), ("+ auto-fail", SYMBOLS_WIDE),
                      ("+ elder sign (every token with a symbol)", SYMBOLS_WIDEST)):
        q = sum(1 for t in BAG if t in sym) / len(BAG)
        react = p_any(q, tests)
        out[name] = {"q_per_test": round(q, 3), "reaction_per_round": round(react, 3)}
    elder = tests * (1 / len(BAG)) * 2
    base = out["+ elder sign (every token with a symbol)"]["reaction_per_round"]
    out["elder_sign_resources_per_round"] = round(elder, 3)
    out["total_resources_per_round_range"] = (round(out["skull/cultist/tablet/elder thing"]["reaction_per_round"] + elder, 2),
                                              round(base + elder, 2))
    # her named cancel: chance the named symbol appears this round, and what it is worth
    cancel = {}
    for tok, n in (("skull", 2), ("tablet", 1), ("elder_thing", 1)):
        pr = p_any(n / len(BAG), tests)
        cancel[tok] = {"p_named_symbol_revealed_in_round": round(pr, 3),
                       "net_resource_cost_if_not_revealed": 2, "gain_if_revealed": "+1 resource reaction (once a round), no modifier"}
    out["named_cancel"] = cancel
    # the value of one cancelled skull on a skill-4 vs difficulty-4 test
    base_p = p_success(4, 4)
    skull_gone = sum(1 for t in BAG if t != "skull" and (modifier(t) is not None and 4 + modifier(t) >= 4)) / (len(BAG) - 1)
    out["success_gain_when_skull_removed_skill4_vs4"] = round(skull_gone - base_p, 3)
    return out


# ---------------------------------------------------------------- Birdie
def birdie(tests=3, p_fail_values=(0.3, 0.45, 0.6)):
    out = {}
    for pf in p_fail_values:
        pmf = [math.comb(tests, k) * pf ** k * (1 - pf) ** (tests - k) for k in range(tests + 1)]
        gain = sum(p * min(2, k) for k, p in enumerate(pmf))
        out["p_fail=%.2f" % pf] = {"resolve_per_round": round(gain, 2), "returns_per_round_if_all_spent": round(gain / 2, 2),
                                    "p_failed_this_round": round(1 - pmf[0], 2)}
    # elder sign: +3 once she has failed this round vs +1; chance a given reveal is the elder sign
    out["elder_sign_per_test"] = round(1 / len(BAG), 3)
    return out


# ---------------------------------------------------------------- Elias
def elias(rounds=11, loops=4000, seed=1, deck=29, upkeep=1, extra_draw=1):
    """Deck use under three prevention policies. Damage events per round: attacks hit his location with
    probability 0.7; damage 1 (50%), 2 (35%), 3 (15%). Limit once per round, up to 3 cards."""
    rnd = random.Random(seed)
    res = {}
    for policy in ("always", "only-if-2+", "never"):
        spent_tot = prev_tot = out_tot = reshuffle_tot = 0
        for _ in range(loops):
            d = deck
            for r in range(rounds):
                # upkeep and one extra draw per round
                for _ in range(upkeep + extra_draw):
                    if d == 0:
                        reshuffle_tot += 1
                        d = 8
                    d -= 1
                if rnd.random() < 0.7:
                    dmg = rnd.choices([1, 2, 3], [0.5, 0.35, 0.15])[0]
                    use = 0
                    if policy == "always":
                        use = min(dmg, 3, d)
                    elif policy == "only-if-2+" and dmg >= 2:
                        use = min(dmg, 3, d)
                    d -= use
                    spent_tot += use
                    prev_tot += use
            if d == 0:
                out_tot += 1
        res[policy] = {"cards_spent_on_prevention_per_loop": round(spent_tot / loops, 1),
                       "damage_prevented_per_loop": round(prev_tot / loops, 1),
                       "p_deck_empty_at_loop_end": round(out_tot / loops, 2),
                       "reshuffles_(1_horror_each)_per_loop": round(reshuffle_tot / loops, 2)}
    return res


# ---------------------------------------------------------------- Seraphine
def seraphine(rounds=11, loops=6000, seed=1, sanity=8):
    """Horror over a loop for different use rates of her ability. Other horror: 0.35 chance a round of
    1 horror (65%) or 2 (35%); an Hour passes every 2nd round and heals 1 horror (the campaign's rule,
    not part of the investigator). 'heal' is extra horror healed per round by the deck (0, 0.5, 1)."""
    rnd = random.Random(seed)
    res = {}
    for use in (0.0, 0.4, 0.7, 1.0):
        for heal in (0.0, 0.5, 1.0):
            dead = total = 0
            for _ in range(loops):
                h = 0
                for r in range(rounds):
                    if rnd.random() < 0.35:
                        h += rnd.choices([1, 2], [0.65, 0.35])[0]
                    if rnd.random() < use:
                        h += 1
                    if r % 2 == 1:
                        h = max(0, h - 1)
                    h = max(0, h - (1 if rnd.random() < heal else 0))
                    if h >= sanity:
                        dead += 1
                        break
                total += h
            res["use=%.1f/round heal=%.1f/round" % (use, heal)] = round(dead / loops, 3)
    return res


# ---------------------------------------------------------------- Ayako
def ayako(difficulties=(3, 4, 5)):
    """Chance one attack/evasion test succeeds with a single token (no commits), her intellect against
    a Guardian's combat with and without a +1 weapon, and against her own printed combat/agility."""
    rows = {}
    for d in difficulties:
        rows["difficulty %d" % d] = {
            "Ayako [int 5] (tagged)": round(p_success(5, d, elder=2), 3),
            "Ayako printed [com 1]": round(p_success(1, d, elder=2), 3),
            "Ayako printed [agi 3]": round(p_success(3, d, elder=2), 3),
            "Guardian com 4": round(p_success(4, d), 3),
            "Guardian com 4 +1 weapon": round(p_success(5, d), 3),
            "Rogue agi 5": round(p_success(5, d), 3),
        }
    return rows


def tag_rate(tests=3, p_success_test=0.6):
    return round(p_any(p_success_test, tests), 3)



# ---------------------------------------------------------------- official comparators
def comparators(tests=3, p_fail=0.45, p_margin2=0.35):
    """Per-round output of official investigators with a similar engine, same assumptions."""
    return {
        "Stella Clark (after a fail: +1 action, once a round)": {"actions_per_round": round(p_any(p_fail, tests), 2), "cost": "none"},
        "Andre Patel (after success by 2+ on your turn: +1 action, once a round)": {"actions_per_round": round(p_any(p_margin2, tests), 2), "cost": "none"},
        "Skids O'Toole (spend 2 resources: +1 action each turn)": {"actions_per_round": 1.0, "cost": "2 resources"},
        "Jenny Barnes (+1 resource each upkeep, elder sign +1 per resource)": {"resources_per_round": 1.0, "cost": "none"},
        "Nathaniel Cho (elder sign on a successful attack returns an event)": {"events_returned_per_round": round(tests / len(BAG) * 0.5, 2), "cost": "needs the elder sign"},
        "Isabelle Barnes (1 direct horror: commit a skill from the discard pile, once a round)": {"skills_per_round": 1.0, "cost": "1 direct horror"},
        "Jacqueline Fine (reveal 2 more tokens and cancel 2, once a round)": {"tokens_cancelled_per_round": 2.0, "cost": "none"},
    }

# ---------------------------------------------------------------- the best interactions, per round
def interactions(tests=3, p_fail=0.45):
    """Value per round of the strongest pairings the scan found, with the official investigator that comes
    closest. 'Per return' values are the printed card text; 'returns' use birdie()'s upper bound (every resolve
    spent, every round has `tests` tests). The simulation measured far fewer (see FINISHING_BALANCE.md)."""
    pmf = [math.comb(tests, k) * p_fail ** k * (1 - p_fail) ** (tests - k) for k in range(tests + 1)]
    returns = sum(p * min(2, k) for k, p in enumerate(pmf)) / 2.0
    out = {"assumptions": {"tests_per_round": tests, "p_fail": p_fail, "returns_per_round_upper_bound": round(returns, 2)}}
    out["birdie_free_fast_events_per_round"] = {
        "Cheat the System (gain 1 per different class you control: 3 to 5)": {"resources": [round(returns * 3, 2), round(returns * 5, 2)], "cost": "0"},
        "Swift Reflexes (taboo: limit twice per round)": {"actions": round(returns, 2), "cost": "2 resources each"},
        "Working a Hunch": {"clues": round(returns, 2), "cost": "2 resources each"},
        "True Awakening (Drifter only: 2 of: draw 2, 1 clue, heal 1 damage, heal 1 horror)": {"cards_plus_clue": [round(returns * 2, 2), round(returns, 2)], "cost": "0 resources, 1 action"},
        "official comparators (same assumptions)": {"Stella Clark extra actions": round(p_any(p_fail, tests), 2), "Jenny Barnes extra resources": 1.0,
                                                   "Skids O'Toole extra actions (pays 2 resources)": 1.0},
    }
    # "Look what I found!": needs a failed investigation by 2 or less; each play yields 2 clues
    out["birdie_look_what_i_found"] = {"clues_per_play": 2, "needs": "a failed investigation by 2 or less (3 at level 2)",
                                      "plays_per_round_max": 2, "note": "a second play in the same round needs the recursion (2 resolve) and a second failed investigation"}
    q_symbol = 7.0 / len(BAG)
    out["cass"] = {
        "income_per_round": {"upkeep": 1.0, "reaction": round(p_any(q_symbol, tests), 2), "elder_sign": round(tests / len(BAG) * 2, 2)},
        "Jenny Barnes income per round (upkeep 1 + extra 1)": 2.0,
        "marked_deck_peek": {"p_sealed_token_is_a_symbol": round(q_symbol, 2), "cost_to_cancel": "2 resources", "named_cancel_alone_hit_rate_per_round_skull": round(p_any(2.0 / len(BAG), tests), 2)},
    }
    out["seraphine_per_use"] = {"price": "1 direct horror", "gives": "+2 skill value, or 1 additional action, or ready a Spell",
                                "with Jim Culver level 4": "+1 card and +1 resource (reaction, exhausts)", "uses_per_round_cap": 1}
    out["elias_per_use"] = {"price": "1 deck card per damage prevented (up to 3, once per round)", "official_price_comparison":
                            "First Aid: 1 supply and an action per damage healed; Dodge/Delay the Inevitable: a card from hand"}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("which", nargs="?", choices=("all", "elias", "ayako", "cass", "birdie", "seraphine", "interactions"), default="all")
    ap.add_argument("--tests", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=11)
    a = ap.parse_args()
    import json
    out = {}
    if a.which in ("all", "elias"):
        out["elias"] = elias(rounds=a.rounds)
    if a.which in ("all", "ayako"):
        out["ayako"] = {"one_test_success_chance": ayako(), "first_success_per_round_tags_(p=0.6)": tag_rate(a.tests)}
    if a.which in ("all", "cass"):
        out["cass"] = cass(a.tests)
    if a.which in ("all", "birdie"):
        out["birdie"] = birdie(a.tests)
    if a.which in ("all", "seraphine"):
        out["seraphine_p_defeated_by_horror_in_a_loop"] = seraphine(rounds=a.rounds)
    if a.which in ("all", "interactions"):
        out["interactions_per_round"] = interactions(a.tests)
    if a.which == "all":
        out["official_comparators_per_round"] = comparators(a.tests)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
