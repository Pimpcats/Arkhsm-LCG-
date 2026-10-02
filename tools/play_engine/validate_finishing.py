"""Reproducible finishing evidence; designer tooling, contains spoilers.

SCED_SAVE=/path/to/save.json python tools/play_engine/validate_finishing.py --output DIR
Use --screen for smaller baseline cells and paired clue-cost proposals.
The output includes every trial, input fingerprints, seeds and Wilson intervals.
Rates describe this policy on the emulator, never human win probabilities.
"""
import argparse
import concurrent.futures
import gzip
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path

import report
import run


def interval(wins, total):
    z = 1.959963984540054
    p = wins / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [center - radius, center + radius]


def tasks(screen):
    cells = []

    def add(label, scenario, n, seed, party=None, proposal=None, campaign=False):
        cells.append(dict(label=label, scenario=scenario, runs=n, seed=seed,
                          party=party or run.PARTIES[3], what_if=proposal or {}, campaign=campaign))

    add("opening", "prologue", 40 if screen else 100, 710000)
    for night, suffix in run.NIGHT_VARIANTS.items():
        for district_index, district in enumerate(run.NIGHT_DISTRICTS):
            add("night%d_%s" % (night, district), "district_" + district + suffix,
                10 if screen else 20, 720000 + 1000 * night + 100 * district_index)
    add("finale", "finale", 40 if screen else 100, 740000)
    if screen:
        for clues in (2, 3, 4):
            add("opening_clues%d" % clues, "prologue", 40, 710000,
                proposal={"cardOverrides": {"sthr-act-firsthour": {"clues": clues}}})
        for night in (4, 8):
            add("night%d_church_clues3" % night, "district_church" + run.NIGHT_VARIANTS[night], 20,
                720000 + 1000 * night,
                proposal={"cardOverrides": {"sthr-act-hourwaswrong": {"clues": 3}}})
    else:
        profiles = [["sthrcass"], ["sthrbirdie"], ["sthrelias", "sthrayako"], ["sthrelias", "sthrbirdie"],
                    ["sthrayako", "sthrcass", "sthrseraphine"], ["sthrelias", "sthrayako", "sthrbirdie"],
                    ["sthrelias", "sthrayako", "sthrcass", "sthrseraphine"],
                    ["sthrelias", "sthrcass", "sthrseraphine", "sthrbirdie"]]
        for i, party in enumerate(profiles):
            for scenario in ("prologue", "district_church_p2", "finale"):
                add("sensitivity%d_%s" % (i, scenario), scenario, 5, 750000 + i * 1000, party=party)
        for i in range(4):
            add("carried%d" % i, "campaign", 5, 760000 + 1000 * i, campaign=True)
    return cells


def execute(task):
    return task, run.run_batch(os.environ["SCED_SAVE"], task["scenario"], len(task["party"]), task["runs"],
                               task["seed"], party=task["party"], what_if=task["what_if"], campaign=task["campaign"])


def summarize(task, result):
    games = result["games"]
    summary = {k: task[k] for k in ("label", "scenario", "party", "runs", "seed", "what_if", "campaign")}
    summary.update(played_slots=len(games), input_digest=result["provenance"]["digest"])
    if not task["campaign"]:
        stats = report.summarize(task["scenario"], len(task["party"]), games)
        rate = stats.get("completion", stats.get("contest_reached"))
        wins = round(rate * len(games))
        summary.update(stats=stats, wins=wins, success=rate, wilson95=interval(wins, len(games)))
    else:
        summary["campaign_seeds"] = sorted(set(g["campaign_seed"] for g in games))
        summary["income_per_investigator"] = statistics.mean([
            sum(g["memory_bank_end"] - g["memory_bank_start"] for g in games if g["campaign_seed"] == seed)
            / len(task["party"]) for seed in summary["campaign_seeds"]])
        summary["spent"] = sum(g.get("spent", 0) for g in games)
        summary["carry_lost"] = sum(g.get("carry_lost", 0) for g in games)
        summary["finale_attempts"] = sum(bool(g["metrics"].get("finale_began")) for g in games)
        summary["finale_wins"] = sum(g["ended"] == "contest" for g in games)
        for seed in summary["campaign_seeds"]:
            chain = sorted((g for g in games if g["campaign_seed"] == seed), key=lambda g: g["slot"])
            initial = chain[0]["metrics"].get("weakness")
            assert all(g["metrics"].get("weakness") == initial for g in chain), "basic weakness changed"
            assert all(a["memory_after_spending"] == b["memory_bank_start"] for a, b in zip(chain, chain[1:])), "bank not carried"
            assert all(0 <= g["memory_after_spending"] <= 10 * len(task["party"])
                       for g in chain if "memory_after_spending" in g), "carry cap"
            assert all(g.get("spent", 0) >= 0 and g.get("carry_lost", 0) >= 0 for g in chain), "negative spending"
            assert all(sum(p["cost"] for p in g.get("purchases", [])) == g.get("spent", 0)
                       for g in chain), "purchase total differs from payment"
            assert all(g["memory_bank_end"] - g["spent"] - g["carry_lost"] == g["memory_after_spending"]
                       for g in chain if "memory_after_spending" in g), "interlude bank conservation"
            assert all(set(a["campaign_state"]["campaign"]["knowledge"])
                       <= set(b["campaign_state"]["campaign"]["knowledge"])
                       for a, b in zip(chain, chain[1:])), "knowledge lost"
        summary["progression_invariants"] = "weakness, bank, carry cap, purchase payments, interlude conservation, monotone Knowledge"
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--screen", action="store_true")
    args = ap.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    run.prepare(os.environ["SCED_SAVE"])
    todo = tasks(args.screen)
    (output / "tasks.json").write_text(json.dumps(todo, indent=2) + "\n")
    started = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(execute, t): t for t in todo}
        for future in concurrent.futures.as_completed(pending):
            task, result = future.result()
            actual = len(set(g.get("campaign_seed") for g in result["games"])) if task["campaign"] else len(result["games"])
            failures = [g for g in result["games"] if run.invalid_game(g)]
            if actual != task["runs"] or result["rc"] or result["failed_checks"] or result["inputs_changed"] or failures:
                (output / (task["label"] + ".failure.json")).write_text(json.dumps(result, indent=1))
                raise RuntimeError("invalid evidence: " + task["label"])
            summary = summarize(task, result)
            with gzip.open(output / (task["label"] + ".json.gz"), "wt", encoding="utf-8") as f:
                json.dump(result, f, separators=(",", ":"))
            results.append(summary)
            print(task["label"], "slots", len(result["games"]), "success", summary.get("success"),
                  "elapsed", round(time.monotonic() - started), flush=True)
            (output / "summary.json").write_text(json.dumps(sorted(results, key=lambda r: r["label"]), indent=2) + "\n")
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}
    (output / "SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("VALID", len(results), "cells", sum(r["played_slots"] for r in results), "played slots", flush=True)


if __name__ == "__main__":
    main()
