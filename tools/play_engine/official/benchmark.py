"""The Still Hour side of the Dunwich benchmark (designer tooling; spoilers in the raw games).

    python3 tools/play_engine/official/benchmark.py --players 2,3,4 --runs 10 --jobs 3   # Still Hour games
    python3 tools/play_engine/official/benchmark.py --campaign --players 2,3,4 --runs 10 # carried campaigns
    python3 tools/play_engine/official/benchmark.py --report                             # both reports

Plays The Still Hour's scenarios exactly as tools/play_engine/run.py does (the
same engine, config, parties, seeds scheme and inputs), through
sh_metrics_suite.lua, which only adds a count of skill tests by kind (the
"encounter-card tests failed" metric). Games go to
.cache/play_engine/official/still_hour/ (The Still Hour's own
.cache/play_engine/games/ is left alone). The night's scenario for Night k
is each district's variant for that night (run.py NIGHT_VARIANTS), at the
same number of runs per district.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ENGINE))
sys.path.insert(0, HERE)
sys.path.insert(0, ENGINE)
OUT = os.path.join(ROOT, ".cache", "play_engine", "official", "still_hour")


def _run():
    import importlib.util
    spec = importlib.util.spec_from_file_location("play_engine_run", os.path.join(ENGINE, "run.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def batch(run, save, scenario, players, runs, seed, campaign=False, timeout=7200):
    cpath, dpath = os.path.join(run.OUT, "cards.json"), os.path.join(run.OUT, "decks.json")
    table, src = run.table_for(save)
    cfg = {"cards": cpath, "decks": dpath, "party": run.PARTIES[players], "difficulty": "Standard", "trace": False,
           "jobs": [{"scenario": scenario, "runs": runs, "seed": seed}], "snapshots": False, "campaign": campaign}
    cfg["inputDigest"] = run.provenance(save, table, cpath, dpath)["digest"]
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    key = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    cfgpath = os.path.join(OUT, "configs", "%s_%dp_%d_%s.json" % (scenario, players, seed, key))
    json.dump(cfg, open(cfgpath, "w", encoding="utf-8"))
    cmd = ["lua5.2", os.path.join(ROOT, "tests", "sced_real", "run.lua"), "--suite", "playthrough",
           "--suite-file", os.path.join(HERE, "sh_metrics_suite.lua"), "--config", cfgpath, "--table", table, "--src", src]
    pl = os.path.join(run.OUT, "payload", "candidate_saved_object.json")
    if os.path.isfile(pl):
        cmd += ["--payload", pl]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=ROOT)
    games = [json.loads(line[7:]) for line in p.stdout.splitlines() if line.startswith("@@GAME ")]
    return games, p.returncode, p.stderr[-1500:]


def jobs_for(run, players, runs, finale_runs):
    jobs = []
    for p in players:
        jobs.append(("prologue", p, max(runs * 3, 30)))
        for k, suf in run.NIGHT_VARIANTS.items():
            for d in run.NIGHT_DISTRICTS:
                jobs.append(("district_" + d + suf, p, runs))
        jobs.append(("finale", p, finale_runs))
    return jobs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--players", default="2,3,4")
    ap.add_argument("--runs", type=int, default=10, help="runs per district per night (the Prologue gets 3x)")
    ap.add_argument("--finale-runs", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--campaign", action="store_true", help="carried campaigns (run.py --campaign) instead")
    ap.add_argument("--report", action="store_true", help="only write the two reports")
    a = ap.parse_args(argv)
    if a.report:
        import dwl_docs
        print(dwl_docs.write_all())
        return 0
    run = _run()
    save = run.DEFAULT_SAVE if os.path.isfile(run.DEFAULT_SAVE) else run.save_from_checkout()
    if not os.path.isfile(os.path.join(run.OUT, "decks.json")):
        run.prepare(save)
    players = [int(x) for x in a.players.split(",")]
    if a.campaign:
        jobs = [("campaign", p, a.runs) for p in players]
    else:
        jobs = jobs_for(run, players, a.runs, a.finale_runs)
    tasks = []
    for scenario, p, runs in jobs:
        per = 1 if scenario == "campaign" else 10
        k = 0
        while k < runs:
            m = min(per, runs - k)
            tasks.append((scenario, p, m, a.seed + 7919 * p + k))
            k += m
    results, t0 = {}, time.time()

    def one(t):
        return t, batch(run, save, t[0], t[1], t[2], t[3], campaign=t[0] == "campaign")

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for t, (games, rc, err) in ex.map(one, tasks):
            results.setdefault((t[0], t[1]), []).extend(games)
            bad = rc != 0 or any(g.get("engine_error") or g.get("lua_errors") for g in games)
            print("%-26s %dp seeds %d..%d: %d game(s)%s [%.0fs]" % (t[0], t[1], t[3], t[3] + t[2] - 1, len(games),
                  " ** " + err[-400:] if bad else "", time.time() - t0), flush=True)
    d = os.path.join(OUT, "games")
    os.makedirs(d, exist_ok=True)
    for (scenario, p), games in results.items():
        with open(os.path.join(d, "%s_%dp.jsonl" % (scenario, p)), "w", encoding="utf-8") as f:
            for g in sorted(games, key=lambda g: (g.get("campaign_seed") or g["seed"], g.get("slot") or 0)):
                g.pop("trace", None)
                g.pop("campaign_state", None)
                f.write(json.dumps(g) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
