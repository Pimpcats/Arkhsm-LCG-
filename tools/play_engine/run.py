"""Play The Still Hour's scenarios on the emulated SCED table, many times.

    python3 tools/play_engine/run.py --scenario district_church --runs 30 --players 3
    python3 tools/play_engine/run.py --scenario all --runs 30 --players 3 --jobs 4
    python3 tools/play_engine/run.py --suite            # the full balance suite (see SUITE)
    python3 tools/play_engine/run.py --campaign --runs 20 --players 3
    python3 tools/play_engine/run.py --report           # rebuild the report from saved games

Designer tooling (spoilers). Every game runs on the real SCED table from the
owner's save with the campaign's Saved Object loaded (tests/sced_real), the
rules layer acting through the Control token, the boxes, SCED's playmats and
chaos bag (tools/play_engine/lua/). Results go to .cache/play_engine/:
games/<scenario>_<players>p.jsonl (one JSON per game), report.md and
metrics.json (tools/play_engine/report.py).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
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
             "district_lighthouse_p2", "district_fairground_p2", "district_almanac_p2", "loop_multi", "finale", "finale_h9",
             "finale_late"]
NIGHT_DISTRICTS = ("church", "road", "lighthouse", "fairground", "almanac")
NIGHT_VARIANTS = {1: "", 2: "_n2", 3: "_n3", 4: "_p2", 5: "_p2_n5", 6: "_p2_n6", 7: "_p2_n7", 8: "_p2_n8"}
SCENARIOS += ["district_" + d + suffix for suffix in NIGHT_VARIANTS.values() for d in NIGHT_DISTRICTS
              if "district_" + d + suffix not in SCENARIOS]
DISTRICT_LOOPS = [s for s in SCENARIOS if s.startswith("district_")]
WHAT_IF = {}          # {"cardOverrides": {id: {field: value}}, "actOverrides": {id: {...}}, "tag": name}
PARTIES = {1: ["sthrcass"], 2: ["sthrelias", "sthrayako"], 3: ["sthrelias", "sthrayako", "sthrcass"],
           4: ["sthrelias", "sthrayako", "sthrcass", "sthrseraphine"]}


def suite(runs3=30, runs_other=15):
    """(scenario, players, runs) for the full balance run: every scenario at
    3 investigators, the district loops at 1 and 4, the finale at 1, 2 and 4."""
    jobs = [(s, 3, runs3) for s in SCENARIOS]
    for p in (1, 2, 4):
        jobs += [(s, p, runs_other) for s in DISTRICT_LOOPS]
    jobs += [("prologue", p, runs_other) for p in (1, 2, 4)]
    jobs += [("finale", p, runs_other) for p in (1, 2, 4)]
    return jobs


def prepare(save):
    os.makedirs(OUT, exist_ok=True)
    cpath = cards_mod.write(os.path.join(OUT, "cards.json"))
    d = decks_mod.build(save, cpath)
    if d["problems"]:
        raise SystemExit("deck problems: " + "; ".join(d["problems"]))
    dpath = os.path.join(OUT, "decks.json")
    json.dump(d, open(dpath, "w", encoding="utf-8"), indent=1)
    payload()
    return cpath, dpath


def payload():
    """dist/'s Saved Object with the Control's and the campaign log's scripts
    rebuilt from src/ (tests/sced_real/run.py candidate_payload), so the engine
    plays the current rules code without a publish run."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("sced_harness_run", os.path.join(ROOT, "tests", "sced_real", "run.py"))
    harness_run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness_run)
    d = os.path.join(OUT, "payload")
    os.makedirs(d, exist_ok=True)
    return harness_run.candidate_payload(d)


def table_for(save):
    import sced_table
    table, _ = sced_table.build_table_from_save(save)
    src, _c = sced_table.find_sced(allow_fetch=False)
    return table, (os.path.join(src, "src") if src else ROOT)


def provenance(save, table, cpath, dpath):
    """Fingerprints of the code and actual data used by a process, not just HEAD."""
    paths = list(Path(HERE).glob("*.py")) + list(Path(HERE, "lua").glob("*.lua"))
    paths += list(Path(ROOT, "src", "StillHour").glob("*.ttslua"))
    paths += [Path(ROOT, "src", "tts", "control.lua"), Path(ROOT, "tests", "sced_real", "tts_emu.lua")]
    paths += [Path(cpath), Path(dpath), Path(table), Path(save), Path(OUT, "payload", "candidate_saved_object.json")]
    hashes = {os.path.relpath(p, ROOT): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths)) if p.is_file()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"digest": digest, "sha256": hashes}


def run_batch(save, scenario, players, runs, seed, trace=False, snapshots=None, lua="lua5.2", party=None,
              timeout=3600, jobs=None, max_rounds=None, campaign=False, what_if=None):
    """One Lua process: boots the table once, plays `runs` games (or the given
    jobs [{scenario, runs, seed}]). Returns {games, coverage, failed_checks, stderr, rc}."""
    cpath, dpath = os.path.join(OUT, "cards.json"), os.path.join(OUT, "decks.json")
    table, src = table_for(save)
    inputs = provenance(save, table, cpath, dpath)
    cfg = {"cards": cpath, "decks": dpath, "party": party or PARTIES[players], "difficulty": "Standard",
           "trace": trace, "jobs": jobs or [{"scenario": scenario, "runs": runs, "seed": seed}],
           "snapshots": bool(snapshots)}
    cfg["campaign"] = campaign
    cfg["inputDigest"] = inputs["digest"]
    if max_rounds:
        cfg["maxRounds"] = max_rounds
    proposal = WHAT_IF if what_if is None else what_if
    if proposal:
        cfg.update(proposal)
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    cfgkey = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    cfgpath = os.path.join(OUT, "configs", "%s_%dp_%d_%s.json" % (scenario, players, seed, cfgkey))
    json.dump(cfg, open(cfgpath, "w", encoding="utf-8"))
    cmd = [lua, os.path.join(ROOT, "tests", "sced_real", "run.lua"), "--suite", "playthrough",
           "--suite-file", os.path.join(HERE, "lua", "engine.lua"), "--config", cfgpath,
           "--table", table, "--src", src]
    pl = os.path.join(OUT, "payload", "candidate_saved_object.json")
    if os.path.isfile(pl):
        cmd += ["--payload", pl]
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
    for g in games:
        g["input_digest"] = inputs["digest"]
    changed = provenance(save, table, cpath, dpath)["digest"] != inputs["digest"]
    return {"games": games, "coverage": coverage, "provenance": inputs, "inputs_changed": changed,
            "failed_checks": harness, "stderr": p.stderr[-3000:],
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


def invalid_game(game):
    """Table/API failures invalidate measurements even if Lua kept running."""
    return bool(game.get("engine_error") or game.get("lua_errors") or game.get("table_notes")
                or game.get("metrics", {}).get("draw_failures"))


def run_jobs(save, jobs, workers, seed0=1000, per_process=10, trace=False, party=None, campaign=False):
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
        return t, run_batch(save, t[0], t[1], t[2], t[3], trace=trace, party=party, campaign=campaign)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for t, r in ex.map(one, tasks):
            key = (t[0], t[1])
            results.setdefault(key, []).extend(r["games"])
            coverage = coverage or r["coverage"]
            actual = len(set(g.get("campaign_seed") for g in r["games"])) if campaign else len(r["games"])
            bad = (actual != t[2] or r["rc"] or r["failed_checks"] or r["inputs_changed"]
                   or any(invalid_game(g) for g in r["games"]))
            print("%-24s %dp seeds %d..%d: %d game(s)%s  [%.0fs]" % (t[0], t[1], t[3], t[3] + t[2] - 1, len(r["games"]),
                  "  ** " + (r["stderr"] or r["stdout_tail"])[-600:] if bad else "", time.time() - t0), flush=True)
            if bad:
                raise RuntimeError("invalid run: %s (%s); expected %d trials, got %d; rc=%s, checks=%s, inputs_changed=%s" %
                                   (t[0], t[1], t[2], actual, r["rc"], r["failed_checks"], r["inputs_changed"]))
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
    ap.add_argument("--runs-other", type=int, default=15, help="--suite: runs at 1, 2 and 4 investigators")
    ap.add_argument("--players", type=int, default=3, choices=(1, 2, 3, 4))
    ap.add_argument("--party", help="comma-separated investigator ids, replacing the default party")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--suite", action="store_true", help="the full balance suite (30 at 3p, 10 at 1p/4p for district loops)")
    ap.add_argument("--campaign", action="store_true", help="carry actual Years, discoveries, bank, paid decks and weaknesses through up to ten played slots")
    ap.add_argument("--trace", action="store_true", help="print one game's play-by-play (first game)")
    ap.add_argument("--report", action="store_true", help="only rebuild the report from saved games")
    ap.add_argument("--render", metavar="DIR", help="play one game with table snapshots into DIR/snapshots and "
                    "render them with tools/godot_table/render.py into DIR")
    ap.add_argument("--cameras", default="playtop,mythostop,top", help="cameras for --render")
    ap.add_argument("--what-if", help="JSON {tag, cardOverrides, actOverrides}: test a proposed change without touching "
                    "the campaign (games go to .cache/play_engine/whatif/<tag>/)")
    a = ap.parse_args(argv)
    if a.campaign and (a.suite or a.render):
        ap.error("--campaign cannot be combined with --suite or --render")
    party = a.party.split(",") if a.party else None
    if party:
        if len(party) not in (1, 2, 3, 4) or len(set(party)) != len(party) or any(i not in decks_mod.LISTS for i in party):
            ap.error("--party needs 1–4 distinct campaign investigator ids")
        if a.suite:
            ap.error("--party is for one party; use separate invocations to compare parties")
        a.players = len(party)
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
    if a.campaign:
        results = run_jobs(a.save, [("campaign", a.players, a.runs)], a.jobs, a.seed, party=party, campaign=True)
        games = results.get(("campaign", a.players), [])
        errors = [g for g in games if invalid_game(g)]
        print(json.dumps({"campaigns": len(set(g["campaign_seed"] for g in games)), "played_slots": len(games),
                          "engine_errors": len(errors), "results": os.path.join(OUT, "games", "campaign_%dp.jsonl" % a.players)}))
        return int(bool(errors) or not games)
    if a.render:
        snaps = os.path.join(a.render, "snapshots")
        if os.path.isdir(snaps):
            import shutil
            shutil.rmtree(snaps)
        r = run_batch(a.save, a.scenario, a.players, 1, a.seed, trace=True, snapshots=snaps, party=party)
        if (not r["games"] or r["rc"] or r["failed_checks"] or r["inputs_changed"]
                or any(invalid_game(g) for g in r["games"])):
            raise RuntimeError("invalid game; refusing to render it as verification evidence")
        for g in r["games"]:
            open(os.path.join(a.render, "trace.txt"), "w", encoding="utf-8").write("\n".join(g.get("trace") or []))
            print("game: ended %s, resolution %s, round %s, Hour %s" % (g["ended"], g["resolution"], g["round"], g["hour"]))
        cmd = [sys.executable, os.path.join(ROOT, "tools", "godot_table", "render.py"), "--save", a.save,
               "--snapshots", snaps, "--out", a.render, "--cameras", a.cameras]
        return subprocess.call(cmd, cwd=ROOT)
    if a.trace:
        r = run_batch(a.save, a.scenario, a.players, 1, a.seed, trace=True, party=party)
        for g in r["games"]:
            print("\n".join(g.get("trace") or []))
            g.pop("trace", None)
            print(json.dumps({k: v for k, v in g.items() if k != "metrics"}, indent=1))
        if not r["games"]:
            print(r["stderr"], r["stdout_tail"])
        return int(not r["games"] or bool(r["rc"] or r["failed_checks"] or r["inputs_changed"])
                   or any(invalid_game(g) for g in r["games"]))
    if a.suite:
        jobs = suite(a.runs, a.runs_other)
    else:
        names = SCENARIOS if a.scenario == "all" else [a.scenario]
        jobs = [(s, a.players, a.runs) for s in names]
    results = run_jobs(a.save, jobs, a.jobs, a.seed, party=party)
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
