#!/usr/bin/env python3
"""fuzz_campaign.py — many randomized whole-campaign playthroughs on SCED's real table, in parallel.

Each seed runs tests/sced_real/fuzz.lua (a random party, difficulty and order of clicks; the table is
checked after every action) on the headless SCED table. Prints one line per failing seed and a summary;
a failing seed re-runs exactly with --seeds N --first N.

Run: python3 tools/fuzz_campaign.py [--seeds 100] [--first 1] [--actions 300] [--lua lua5.4] [--jobs 3]
     (SCED_DIR=<a SCED checkout> to run on another SCED version)
"""
import argparse
import concurrent.futures
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))
import run as harness  # noqa: E402
import sced_table  # noqa: E402


def one(args):
    seed, lua, actions = args
    t = time.time()
    r = harness.run(lua, "fuzz", extra={"seed": seed, "actions": actions}, timeout=1800)
    if r.get("skipped"):
        return {"seed": seed, "lua": lua, "skipped": r["skipped"]}
    bad = [c for c in r.get("checks", []) if not c["ok"]]
    ended = [ln[7:] for ln in r.get("stdout", "").splitlines() if ln.startswith("[INFO] seed") and "ended" in ln]
    party = [ln[7:] for ln in r.get("stdout", "").splitlines() if ln.startswith("[INFO] seed") and "investigator" in ln]
    return {"seed": seed, "lua": lua, "ok": not bad and r.get("rc") == 0, "failures": bad, "rc": r.get("rc"),
            "ended": ended[0] if ended else None, "party": party[0] if party else None,
            "stderr": (r.get("stderr") or "")[-800:], "secs": round(time.time() - t, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--actions", type=int, default=300)
    ap.add_argument("--lua", default="lua5.4")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", help="write every result as JSON here")
    a = ap.parse_args(argv)
    src, commit = sced_table.find_sced()
    if not src:
        raise SystemExit("SCED not available: %s" % commit)
    sced_table.build_table(src, commit)      # assemble once before the workers start
    jobs = [(s, a.lua, a.actions) for s in range(a.first, a.first + a.seeds)]
    results = []
    with concurrent.futures.ProcessPoolExecutor(a.jobs) as ex:
        for res in ex.map(one, jobs):
            results.append(res)
            if res.get("skipped"):
                print("seed %d skipped: %s" % (res["seed"], res["skipped"]))
            elif not res["ok"]:
                print("FAIL seed %d (%s): %s" % (res["seed"], res["lua"], "; ".join(
                    "%s -- %s" % (f["name"], (f.get("detail") or "")[:600]) for f in res["failures"])
                    or "exit %s %s" % (res["rc"], res["stderr"])), flush=True)
    ok = sum(1 for r in results if r.get("ok"))
    print("SCED %s, %s: %d of %d seeds passed (%d actions each)" % (commit[:12], a.lua, ok, len(results), a.actions))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
