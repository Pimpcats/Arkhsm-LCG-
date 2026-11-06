"""The Dunwich Legacy benchmark: play the official opening pair on the emulated SCED table.

    python3 tools/play_engine/run.py --official dwl --runs 60 --players 2
    python3 tools/play_engine/official/dwl.py --scenario 1a --players 2 --trace      # one game, play by play
    python3 tools/play_engine/official/dwl.py --suite --jobs 3                       # 1a, 1b and both campaign orders at 2/3/4

Designer tooling. The same table, rules layer, AI and level-0 cards as The
Still Hour's play engine (tools/play_engine), driving SCED's own Dunwich
campaign box (downloaded data, .cache/official/dwl_sced.json; never committed).
Scenarios: 1a (Extracurricular Activity), 1b (The House Always Wins), pair_ab
(1a then 1b in campaign order: the second sees the first's outcome) and
pair_ba. Parties: official investigators (dwl_data.PARTIES) playing The Still
Hour's same-class starter cards. Games go to .cache/play_engine/official/games/.
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
sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))

import dwl_data  # noqa: E402

OUT = os.path.join(ROOT, ".cache", "play_engine", "official")
SCENARIOS = ["1a", "1b", "pair_ab", "pair_ba"]


def _engine_run():
    import importlib.util
    spec = importlib.util.spec_from_file_location("play_engine_run", os.path.join(ENGINE, "run.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def guide_config():
    out = {}
    for key, name in (("1a", "extracurricular_activity"), ("1b", "the_house_always_wins")):
        g = dwl_data.guide(name)
        out[key] = {"resolutions": {r["id"]: r.get("steps", []) for r in g["resolutions"]},
                    "steps": {s["id"]: s for s in g["steps"] if "id" in s}}
    return out


def prepare(save):
    if not os.path.isfile(dwl_data.SCED_BOX):
        raise SystemExit("no SCED Dunwich box at %s (downloaded data; see the module docstring)" % dwl_data.SCED_BOX)
    run = _engine_run()
    # The Still Hour's cards and starter decks (decks.json) are the template decks. They are built once
    # and never rewritten here: a Still Hour run reading them at the same time would see its inputs change.
    if not os.path.isfile(os.path.join(run.OUT, "decks.json")):
        run.prepare(save)
    os.makedirs(OUT, exist_ok=True)
    cpath = dwl_data.write_cards(os.path.join(OUT, "dwl_cards.json"))
    dpath = os.path.join(OUT, "dwl_decks.json")
    d = dwl_data.write_decks(os.path.join(run.OUT, "decks.json"), save, dpath)
    if d["problems"]:
        raise SystemExit("deck problems: " + "; ".join(d["problems"]))
    return cpath, dpath


def run_batch(save, scenario, players, runs, seed, trace=False, extra=None, timeout=7200, lua="lua5.2"):
    run = _engine_run()
    table, src = run.table_for(save)
    cfg = {"cards": os.path.join(OUT, "dwl_cards.json"), "decks": os.path.join(OUT, "dwl_decks.json"),
           "box": dwl_data.SCED_BOX, "party": dwl_data.PARTIES[players], "guide": guide_config(),
           "trace": trace, "jobs": [{"scenario": scenario, "runs": runs, "seed": seed}]}
    cfg.update(extra or {})
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    key = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    cpath = os.path.join(OUT, "configs", "%s_%dp_%d_%s.json" % (scenario, players, seed, key))
    json.dump(cfg, open(cpath, "w", encoding="utf-8"))
    cmd = [lua, os.path.join(ROOT, "tests", "sced_real", "run.lua"), "--suite", "dwl",
           "--suite-file", os.path.join(ENGINE, "lua", "official", "dwl_engine.lua"), "--config", cpath,
           "--table", table, "--src", src]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=ROOT)
    games, coverage, failed = [], None, []
    for line in p.stdout.splitlines():
        if line.startswith("@@GAME "):
            games.append(json.loads(line[7:]))
        elif line.startswith("@@COVERAGE "):
            coverage = json.loads(line[11:])
        elif line.startswith("@@CHECK "):
            rec = json.loads(line[8:])
            if "name" in rec and not rec["ok"]:
                failed.append(rec)
    return {"games": games, "coverage": coverage, "failed_checks": failed, "rc": p.returncode,
            "stderr": p.stderr[-3000:], "stdout_tail": p.stdout[-3000:]}


def invalid(g):
    return bool(g.get("engine_error") or g.get("lua_errors") or g.get("table_notes")
                or g.get("metrics", {}).get("draw_failures"))


def run_jobs(save, jobs, workers, seed0=5000, per_process=10, tag=None, extra=None, strict=True):
    tasks = []
    for scenario, players, runs in jobs:
        k = 0
        while k < runs:
            m = min(per_process, runs - k)
            tasks.append((scenario, players, m, seed0 + 7919 * players + 104729 * SCENARIOS.index(scenario) + k))
            k += m
    results, coverage, t0 = {}, None, time.time()

    def one(t):
        return t, run_batch(save, t[0], t[1], t[2], t[3], extra=extra)

    bad_runs = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t, r in ex.map(one, tasks):
            results.setdefault((t[0], t[1]), []).extend(r["games"])
            coverage = coverage or r["coverage"]
            want = t[2] * (2 if t[0].startswith("pair") else 1)
            bad = len(r["games"]) != want or r["rc"] or r["failed_checks"] or any(invalid(g) for g in r["games"])
            print("%-8s %dp seeds %d..%d: %d game(s)%s  [%.0fs]" % (t[0], t[1], t[3], t[3] + t[2] - 1, len(r["games"]),
                  "  ** " + (r["stderr"] or r["stdout_tail"])[-800:] if bad else "", time.time() - t0), flush=True)
            if bad:
                bad_runs.append((t, [g.get("engine_error") or g.get("lua_errors") or g.get("table_notes")
                                     for g in r["games"] if invalid(g)][:3]))
    d = os.path.join(OUT, "games" if not tag else "games_" + tag)
    os.makedirs(d, exist_ok=True)
    for (scenario, players), games in results.items():
        games.sort(key=lambda g: (g.get("pair_seed") or g["seed"], g.get("slot") or 0))
        with open(os.path.join(d, "%s_%dp.jsonl" % (scenario, players)), "w", encoding="utf-8") as f:
            for g in games:
                g = dict(g)
                g.pop("trace", None)
                f.write(json.dumps(g) + "\n")
    if coverage:
        json.dump(coverage, open(os.path.join(OUT, "coverage.json"), "w", encoding="utf-8"), indent=1)
    if bad_runs and strict:
        raise RuntimeError("invalid runs: %s" % bad_runs[:3])
    return results, bad_runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    run = _engine_run()
    ap.add_argument("--save", default=os.environ.get("SCED_SAVE", run.DEFAULT_SAVE))
    ap.add_argument("--scenario", default="1a", help="1a, 1b, pair_ab, pair_ba or all")
    ap.add_argument("--players", type=int, default=2, choices=(2, 3, 4))
    ap.add_argument("--runs", type=int, default=60)
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--suite", action="store_true", help="every scenario at 2, 3 and 4 investigators")
    ap.add_argument("--trace", action="store_true", help="one game, play by play")
    ap.add_argument("--cheat", choices=("never", "cardroom", "important"), default="never",
                    help="The House Always Wins: whether the party 'cheats' with Beginner's Luck")
    ap.add_argument("--tag", help="write games to games_<tag>/ (variants)")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.save):
        a.save = run.save_from_checkout()
        if not a.save:
            print("SKIPPED: no SCED save and no SCED checkout")
            return 0
    prepare(a.save)
    extra = {"cheat": a.cheat} if a.cheat != "never" else None
    if a.trace:
        r = run_batch(a.save, a.scenario, a.players, 1, a.seed, trace=True, extra=extra)
        for g in r["games"]:
            print("\n".join(g.get("trace") or []))
            g.pop("trace", None)
            print(json.dumps({k: v for k, v in g.items() if k != "metrics"}, indent=1))
        if not r["games"]:
            print(r["stderr"], r["stdout_tail"])
        return int(not r["games"] or any(invalid(g) for g in r["games"]))
    names = SCENARIOS if a.scenario == "all" else [a.scenario]
    if a.suite:
        jobs = [(s, p, a.runs) for p in (2, 3, 4) for s in SCENARIOS]
    else:
        jobs = [(s, a.players, a.runs) for s in names]
    run_jobs(a.save, jobs, a.jobs, a.seed, tag=a.tag, extra=extra)
    import dwl_report
    print(dwl_report.summary_text(OUT, a.tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
