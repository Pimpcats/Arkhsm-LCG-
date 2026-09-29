"""Play The Still Hour's scenarios on the emulated SCED table, many times.

    python3 tools/play_engine/run.py --scenario district_church --runs 30 --players 3
    python3 tools/play_engine/run.py --scenario all --runs 30 --players 3 --jobs 4
    python3 tools/play_engine/run.py --suite            # the full balance suite (see SUITE)
    python3 tools/play_engine/run.py --report           # rebuild the report from saved games

Designer tooling (spoilers). Every game runs on the real SCED table from the
owner's save with the campaign's Saved Object loaded (tests/sced_real), the
rules layer acting through the Control token, the boxes, SCED's playmats and
chaos bag (tools/play_engine/lua/). Results go to .cache/play_engine/:
games/<scenario>_<players>p.jsonl (one JSON per game), report.md and
metrics.json (tools/play_engine/report.py).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import cards as cards_mod  # noqa: E402
import decks as decks_mod  # noqa: E402

DEFAULT_SAVE = "/home/user/sce480/Arkham SCE 4.8.0.json"
OUT = os.path.join(ROOT, ".cache", "play_engine")
SCENARIOS = ["prologue", "district_square", "district_church", "district_road", "district_lighthouse",
             "district_fairground", "district_almanac", "district_square_p2", "district_church_p2", "district_road_p2",
             "district_lighthouse_p2", "district_fairground_p2", "district_almanac_p2", "loop_multi", "finale", "finale_h9"]
DISTRICT_LOOPS = [s for s in SCENARIOS if s.startswith("district_")]
WHAT_IF = {}          # {"cardOverrides": {id: {field: value}}, "actOverrides": {id: {...}}, "tag": name}
PARTIES = {1: ["sthrcass"], 2: ["sthrelias", "sthrayako"], 3: ["sthrelias", "sthrayako", "sthrcass"],
           4: ["sthrelias", "sthrayako", "sthrcass", "sthrseraphine"]}


def suite(runs3=30, runs_other=10):
    """(scenario, players, runs) for the full balance run."""
    jobs = [(s, 3, runs3) for s in SCENARIOS]
    for p in (1, 4):
        jobs += [(s, p, runs_other) for s in DISTRICT_LOOPS]
    return jobs


def prepare(save):
    os.makedirs(OUT, exist_ok=True)
    cpath = cards_mod.write(os.path.join(OUT, "cards.json"))
    d = decks_mod.build(save, cpath)
    if d["problems"]:
        raise SystemExit("deck problems: " + "; ".join(d["problems"]))
    dpath = os.path.join(OUT, "decks.json")
    json.dump(d, open(dpath, "w", encoding="utf-8"), indent=1)
    return cpath, dpath


def table_for(save):
    import sced_table
    table, _ = sced_table.build_table_from_save(save)
    src, _c = sced_table.find_sced(allow_fetch=False)
    return table, (os.path.join(src, "src") if src else ROOT)


def run_batch(save, scenario, players, runs, seed, trace=False, snapshots=None, lua="lua5.2", party=None,
              timeout=3600, jobs=None, max_rounds=None):
    """One Lua process: boots the table once, plays `runs` games (or the given
    jobs [{scenario, runs, seed}]). Returns {games, coverage, failed_checks, stderr, rc}."""
    cpath, dpath = os.path.join(OUT, "cards.json"), os.path.join(OUT, "decks.json")
    table, src = table_for(save)
    cfg = {"cards": cpath, "decks": dpath, "party": party or PARTIES[players], "difficulty": "Standard",
           "trace": trace, "jobs": jobs or [{"scenario": scenario, "runs": runs, "seed": seed}],
           "snapshots": bool(snapshots)}
    if max_rounds:
        cfg["maxRounds"] = max_rounds
    if WHAT_IF:
        cfg.update(WHAT_IF)
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    cfgpath = os.path.join(OUT, "configs", "%s_%dp_%d.json" % (scenario, players, seed))
    json.dump(cfg, open(cfgpath, "w", encoding="utf-8"))
    cmd = [lua, os.path.join(ROOT, "tests", "sced_real", "run.lua"), "--suite", "playthrough",
           "--suite-file", os.path.join(HERE, "lua", "engine.lua"), "--config", cfgpath,
           "--table", table, "--src", src]
    if snapshots:
        os.makedirs(snapshots, exist_ok=True)
        cmd += ["--snapshots", os.path.abspath(snapshots)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       cwd=ROOT)
    games, coverage, harness = [], None, []
    for line in p.stdout.splitlines():
        if line.startswith("@@GAME "):
            games.append(json.loads(line[7:]))
        elif line.startswith("@@COVERAGE "):
            coverage = json.loads(line[11:])
        elif line.startswith("@@CHECK "):
            rec = json.loads(line[8:])
            if "name" in rec and not rec["ok"]:
                harness.append(rec)
    return {"games": games, "coverage": coverage, "failed_checks": harness, "stderr": p.stderr[-3000:],
            "rc": p.returncode, "stdout_tail": p.stdout[-3000:] if not games else ""}


def save_games(scenario, players, games):
    d = os.path.join(OUT, "whatif", WHAT_IF["tag"]) if WHAT_IF.get("tag") else os.path.join(OUT, "games")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "%s_%dp.jsonl" % (scenario, players))
    with open(path, "w", encoding="utf-8") as f:
        for g in games:
            g = dict(g)
            g.pop("trace", None)
            f.write(json.dumps(g) + "\n")
    return path


def run_jobs(save, jobs, workers, seed0=1000, per_process=10, trace=False):
    """Split each (scenario, players, runs) into processes of `per_process` games."""
    tasks = []
    for scenario, players, runs in jobs:
        k = 0
        while k < runs:
            n = min(per_process, runs - k)
            tasks.append((scenario, players, n, seed0 + 7919 * players + k))
            k += n
    results = {}
    coverage = None
    t0 = time.time()

    def one(t):
        return t, run_batch(save, t[0], t[1], t[2], t[3], trace=trace)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t, r in ex.map(one, tasks):
            key = (t[0], t[1])
            results.setdefault(key, []).extend(r["games"])
            coverage = coverage or r["coverage"]
            bad = len(r["games"]) < t[2]
            print("%-24s %dp seeds %d..%d: %d game(s)%s  [%.0fs]" % (t[0], t[1], t[3], t[3] + t[2] - 1, len(r["games"]),
                  "  ** " + (r["stderr"] or r["stdout_tail"])[-600:] if bad else "", time.time() - t0), flush=True)
    for (scenario, players), games in results.items():
        games.sort(key=lambda g: g["seed"])
        save_games(scenario, players, games)
    if coverage:
        json.dump(coverage, open(os.path.join(OUT, "coverage.json"), "w", encoding="utf-8"), indent=1)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", default=os.environ.get("SCED_SAVE", DEFAULT_SAVE))
    ap.add_argument("--scenario", default="district_church", help="a scenario id, or 'all' (%s)" % ", ".join(SCENARIOS))
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--players", type=int, default=3, choices=(1, 2, 3, 4))
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--suite", action="store_true", help="the full balance suite (30 at 3p, 10 at 1p/4p for district loops)")
    ap.add_argument("--trace", action="store_true", help="print one game's play-by-play (first game)")
    ap.add_argument("--report", action="store_true", help="only rebuild the report from saved games")
    ap.add_argument("--render", metavar="DIR", help="play one game with table snapshots into DIR/snapshots and "
                    "render them with tools/godot_table/render.py into DIR")
    ap.add_argument("--cameras", default="playtop,mythostop,top", help="cameras for --render")
    ap.add_argument("--what-if", help="JSON {tag, cardOverrides, actOverrides}: test a proposed change without touching "
                    "the campaign (games go to .cache/play_engine/whatif/<tag>/)")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.save):
        print("SKIPPED: no SCED save at", a.save)
        return 0
    if a.report:
        import report
        print(report.build(OUT))
        return 0
    prepare(a.save)
    if a.what_if:
        WHAT_IF.update(json.load(open(a.what_if, encoding="utf-8")))
    if a.render:
        snaps = os.path.join(a.render, "snapshots")
        if os.path.isdir(snaps):
            import shutil
            shutil.rmtree(snaps)
        r = run_batch(a.save, a.scenario, a.players, 1, a.seed, trace=True, snapshots=snaps)
        for g in r["games"]:
            open(os.path.join(a.render, "trace.txt"), "w", encoding="utf-8").write("\n".join(g.get("trace") or []))
            print("game: ended %s, resolution %s, round %s, Hour %s" % (g["ended"], g["resolution"], g["round"], g["hour"]))
        cmd = [sys.executable, os.path.join(ROOT, "tools", "godot_table", "render.py"), "--save", a.save,
               "--snapshots", snaps, "--out", a.render, "--cameras", a.cameras]
        return subprocess.call(cmd, cwd=ROOT)
    if a.trace:
        r = run_batch(a.save, a.scenario, a.players, 1, a.seed, trace=True)
        for g in r["games"]:
            print("\n".join(g.get("trace") or []))
            g.pop("trace", None)
            print(json.dumps({k: v for k, v in g.items() if k != "metrics"}, indent=1))
        if not r["games"]:
            print(r["stderr"], r["stdout_tail"])
        return 0
    if a.suite:
        jobs = suite(a.runs, max(10, a.runs // 3))
    else:
        names = SCENARIOS if a.scenario == "all" else [a.scenario]
        jobs = [(s, a.players, a.runs) for s in names]
    results = run_jobs(a.save, jobs, a.jobs, a.seed)
    import report
    if WHAT_IF.get("tag"):
        for (scenario, players), games in sorted(results.items()):
            s = report.summarize(scenario, players, games)
            print(json.dumps({k: s.get(k) for k in ("scenario", "players", "runs", "completion", "completed_round",
                                                    "hours_to_spare", "rounds", "defeat_games", "diss_max_mean",
                                                    "objectives_mean", "contest_reached", "resolution")}))
        return 0
    print(report.build(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
