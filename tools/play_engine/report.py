"""Aggregate the play engine's games into .cache/play_engine/report.md and
metrics.json (designer tooling; spoilers).

    python3 tools/play_engine/report.py            # from .cache/play_engine/games/*.jsonl

Compares with the abstract tempo model (pipeline/simulate_tempo.py --race),
whose output is cached in .cache/play_engine/tempo_race.txt.
"""
import collections
import glob
import json
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, ".cache", "play_engine")

PRIMARY = {
    "prologue": "sthr-act-firsthour", "district_square": "sthr-act-sheriffdead",
    "district_church": "sthr-act-whythirteen", "district_road": "sthr-act-walkbackward",
    "district_lighthouse": "sthr-act-lamp", "district_fairground": "sthr-act-wheelturns",
    "district_almanac": "sthr-act-almanachid", "district_square_p2": "sthr-act-vote",
    "district_church_p2": "sthr-act-hourwaswrong", "district_road_p2": "sthr-act-walksbeside",
    "district_lighthouse_p2": "sthr-act-ninthdeath", "district_fairground_p2": "sthr-act-bargain",
    "district_almanac_p2": "sthr-act-appointedname",
}
for _k in list(PRIMARY):                  # later-night variants (scenarios.lua: _n3, _p2_n5/_n6/_n7)
    for _v in (("_n5", "_n6", "_n7", "_n8") if _k.endswith("_p2") else ("_n2", "_n3")):
        PRIMARY[_k + _v] = PRIMARY[_k]
# The night's goal, as an official scenario's act deck: the district's act and
# the Square's current act (both are on the board every loop). A night "wins"
# when every one advanced. (Official scenarios run about 3 acts, usually one
# of them asking for clues: docs/design/OFFICIAL_COMPARISON.md.)
NIGHT = {}
for _k, _a in PRIMARY.items():
    if _k == "prologue" or _k.startswith("district_square") or _k.startswith("district_almanac_p2"):
        NIGHT[_k] = [_a]
    elif "_p2" in _k:
        NIGHT[_k] = [_a, "sthr-act-vote"]
    else:
        NIGHT[_k] = [_a, "sthr-act-sheriffdead"]
MULTI = {"loop_multi": ["sthr-act-whythirteen", "sthr-act-almanachid", "sthr-act-sheriffdead"]}
TEMPO_KEY = {
    "district_square": ("square_surface", 0), "district_church": ("church_surface", 0),
    "district_road": ("road_surface", 0), "district_lighthouse": ("lighthouse_surface", 0),
    "district_fairground": ("fairground_surface", 0), "district_almanac": ("almanac_surface", 0),
    "district_square_p2": ("square_deep", 1), "district_church_p2": ("church_deep", 1),
    "district_road_p2": ("road_deep", 1), "district_lighthouse_p2": ("lighthouse_deep", 1),
    "district_fairground_p2": ("fairground_deep", 1), "district_almanac_p2": ("almanac_deep", 1),
}
ORDER = ["prologue", "district_square", "district_church", "district_road", "district_lighthouse",
         "district_fairground", "district_almanac", "district_square_p2", "district_church_p2", "district_road_p2",
         "district_lighthouse_p2", "district_fairground_p2", "district_almanac_p2", "loop_multi", "finale", "finale_h9"]
ORDER += [k for k in PRIMARY if k not in ORDER]


def L(x):
    return x if isinstance(x, list) else []


def D(x):
    return x if isinstance(x, dict) else {}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def fmt(x, nd=1):
    if x is None:
        return "–"
    if isinstance(x, float):
        return ("%." + str(nd) + "f") % x
    return str(x)


def pct(n, d):
    return "–" if not d else "%d%%" % round(100.0 * n / d)


def tempo_race():
    """{players: {objective: [(done%, hours), (done%, hours)]}} from the old tempo model."""
    path = os.path.join(OUT, "tempo_race.txt")
    if not os.path.isfile(path):
        try:
            txt = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "simulate_tempo.py"), "--race",
                                  "--trials", "1500"], capture_output=True, text=True, timeout=900, cwd=ROOT).stdout
        except (OSError, subprocess.SubprocessError):
            return {}
        open(path, "w", encoding="utf-8").write(txt)
    out, players = {}, None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"District race at (\d) investigators", line)
        if m:
            players = int(m.group(1))
            out[players] = {}
            continue
        m = re.match(r"(\w+)\s+\|\s+(\d+)%\s+([\d.]+)\s+\|\s+(\d+)%\s+([\d.]+)", line)
        if m and players:
            out[players][m.group(1)] = [(int(m.group(2)), float(m.group(3))), (int(m.group(4)), float(m.group(5)))]
    return out


def load_games():
    games = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(OUT, "games", "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                g = json.loads(line)
                games[(g["scenario"], g["players"])].append(g)
    return games


def band_of(d, n):
    reset = 9 if n == 1 else 6 * n
    if d >= reset:
        return "Reset"
    if d >= (2 * reset) // 3:
        return "Noticed"
    if d >= reset // 3:
        return "Glitch"
    return "Calm"


def act_done(g, act_id):
    for a in L(g.get("acts")):
        if a.get("id") == act_id:
            return a
    return None


def summarize(name, players, games):
    n = len(games)
    s = {"scenario": name, "players": players, "runs": n}
    prim = PRIMARY.get(name)
    ms = [D(g.get("metrics")) for g in games]
    if prim:
        # the district's own act alone (for reference)
        s["district_completion"] = sum(1 for g in games if act_done(g, prim)) / n if n else 0
        done = []
        for g in games:
            need = L(g.get("goals")) or NIGHT.get(name, [prim])
            ds = [act_done(g, a) for a in need]
            done.append(max(ds, key=lambda d: d["round"]) if all(ds) else None)
        ok = [d for d in done if d]
        s["completion"] = len(ok) / n if n else 0
        s["completed_hour"] = mean([d["hour"] for d in ok])
        s["completed_round"] = mean([d["round"] for d in ok])
        s["hours_to_spare"] = mean([9 - d["hour"] for d in ok])
        # rounds the loop still ran after the objective was met (the loop ends at Hour IX)
        s["rounds_to_spare"] = mean([g.get("round") - d["round"] for g, d in zip(games, done) if d])
    if name in MULTI:
        counts = collections.Counter(sum(1 for a in MULTI[name] if act_done(g, a)) for g in games)
        s["objectives_per_loop"] = {k: counts.get(k, 0) / n for k in range(len(MULTI[name]) + 1)}
        s["objectives_mean"] = mean([sum(1 for a in MULTI[name] if act_done(g, a)) for g in games])
        s["each"] = {a: sum(1 for g in games if act_done(g, a)) / n for a in MULTI[name]}
        s["two_or_more"] = sum(v for k, v in s["objectives_per_loop"].items() if k >= 2)
    if name.startswith("finale"):
        s["contest_reached"] = sum(1 for g in games if g.get("ended") == "contest") / n
        s["contest_mean"] = mean([g.get("contest", 0) for g in games])
        src = collections.Counter()
        for m in ms:
            for k, v in D(m.get("contest_sources")).items():
                src[re.sub(r": .*", "", k)] += v
        s["contest_sources"] = {k: v / n for k, v in src.items()}
        s["finale_began_hour"] = mean([D(m.get("finale_began")).get("hour") for m in ms])
        s["finale_began_diss"] = mean([D(m.get("finale_began")).get("dissonance") for m in ms])
    s["rounds"] = mean([g.get("round") for g in games])
    s["end_hour"] = mean([g.get("hour") for g in games])
    s["ended"] = dict(collections.Counter(g.get("ended") for g in games))
    s["resolution"] = dict(collections.Counter(g.get("resolution") for g in games))
    dres = collections.defaultdict(collections.Counter)
    for g in games:
        for d, r in D(g.get("districts")).items():
            dres[d][r] += 1
    s["district_resolutions"] = {d: dict(c) for d, c in dres.items()}
    s["reset_rate"] = sum(1 for g in games if g.get("ended") == "reset") / n
    s["diss_max_mean"] = mean([m.get("diss_max") for m in ms])
    s["diss_max_max"] = max([m.get("diss_max", 0) for m in ms] or [0])
    s["diss_end_mean"] = mean([g.get("dissonance_end") for g in games])
    s["band_end"] = dict(collections.Counter(g.get("band_end") for g in games))
    s["band_max"] = dict(collections.Counter(band_of(m.get("diss_max", 0), players) for m in ms))
    s["defeat_games"] = sum(1 for m in ms if m.get("defeats", 0) > 0) / n
    s["defeats_mean"] = mean([m.get("defeats", 0) for m in ms])
    s["damage_mean"] = mean([m.get("damage", 0) for m in ms])
    s["horror_mean"] = mean([m.get("horror", 0) for m in ms])
    s["clues_mean"] = mean([m.get("clues", 0) for m in ms])
    s["clues_per_round"] = mean([m.get("clues", 0) / max(1, g.get("round") or 1) for g, m in zip(games, ms)])
    s["stage_max"] = dict(collections.Counter(g.get("stage_max") for g in games))
    s["manifest_hour"] = mean([m.get("appointed_manifest_hour") for m in ms])
    s["holdbacks"] = mean([m.get("holdbacks", 0) for m in ms])
    s["appointed_attacks"] = mean([m.get("appointed_attacks", 0) for m in ms])
    s["reshuffles"] = mean([m.get("reshuffles", 0) for m in ms])
    s["deck_size"] = mean([m.get("deck_size") for m in ms])
    s["encounters"] = mean([m.get("encounters", 0) for m in ms])
    s["crossing_hours"] = mean([m.get("crossing_hours", 0) for m in ms])
    s["memory_on_cards"] = mean([g.get("memory_on_cards", 0) for g in games])
    s["memory_bank_gain"] = mean([(g.get("memory_bank_end") or 0) - (g.get("memory_bank_start") or 0) for g in games])
    yrs = [v for g in games for v in D(g.get("years")).values()]
    s["years_per_investigator"] = mean(yrs)
    s["card_years"] = mean([g.get("card_years", 0) for g in games])
    # curves: mean Hour / Dissonance at the end of each round
    hc, dc = collections.defaultdict(list), collections.defaultdict(list)
    for m in ms:
        for p in L(m.get("curve")):
            if p.get("phase") == "end":
                hc[p["round"]].append(p["hour"])
                dc[p["round"]].append(p["diss"])
    s["hour_curve"] = {r: mean(v) for r, v in sorted(hc.items()) if len(v) >= max(1, n // 4)}
    s["diss_curve"] = {r: mean(v) for r, v in sorted(dc.items()) if len(v) >= max(1, n // 4)}
    hs = collections.Counter()
    ds = collections.Counter()
    for m in ms:
        for k, v in D(m.get("hour_sources")).items():
            hs[k] += v
        for k, v in D(m.get("dissonance_sources")).items():
            ds[k] += v
    s["hour_sources"] = {k: v / n for k, v in hs.most_common()}
    dm = collections.Counter()
    for m in ms:
        for k, v in D(m.get("doom_sources")).items():
            dm[k] += v
    s["doom_sources"] = {k: v / n for k, v in dm.most_common()}
    s["dissonance_sources"] = {k: v / n for k, v in ds.most_common()}
    sp = collections.Counter()
    where = collections.defaultdict(collections.Counter)
    want = {}
    for m in ms:
        for x in L(m.get("spawns")):
            sp[x["id"]] += 1
            where[x["id"]][x.get("at")] += 1
            want[x["id"]] = x.get("want")
    s["spawns"] = {k: v / n for k, v in sp.most_common()}
    s["spawn_locations"] = {k: {"instruction": want.get(k), "used": dict(v)} for k, v in where.items()}
    bad = collections.Counter()
    for m in ms:
        for b in L(m.get("bad_spawns")):
            bad["%s: wants %s, used %s (%s)" % (b.get("id"), b.get("want"), b.get("used"), b.get("note"))] += 1
    s["bad_spawns"] = dict(bad)
    place = collections.Counter()
    for m in ms:
        for k, v in D(m.get("placement")).items():
            for x in L(v):
                place["%s: %s" % (k, x)] += 1
    s["placement_problems"] = dict(place)
    vic = collections.Counter()
    for m in ms:
        for v in L(m.get("victory")):
            vic[v] += 1
    s["victory"] = {k: v / n for k, v in vic.items()}
    for key in ("damage_by", "horror_by", "defeated_by", "defeated_who"):
        c = collections.Counter()
        for m in ms:
            for k, v in D(m.get(key)).items():
                c[k] += v
        s[key] = {k: v / n for k, v in c.most_common(8)}
    s["lua_errors"] = sum(len(L(g.get("lua_errors"))) for g in games)
    s["engine_errors"] = [g.get("engine_error")[:300] for g in games if g.get("engine_error")]
    notes = collections.Counter()
    for g in games:
        for t in L(g.get("table_notes")):
            notes[t] += 1
    s["table_notes"] = dict(notes)
    s["tests_pass_rate"] = mean([m.get("tests_passed", 0) / max(1, m.get("tests", 1)) for m in ms])
    return s


def whatifs():
    out = []
    for d in sorted(glob.glob(os.path.join(OUT, "whatif", "*"))):
        if not os.path.isdir(d):
            continue
        for path in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
            gs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
            if gs:
                out.append((os.path.basename(d), summarize(gs[0]["scenario"], gs[0]["players"], gs)))
    return out


def build(out_dir=OUT):
    games = load_games()
    if not games:
        return "no games in " + os.path.join(out_dir, "games")
    summaries = []
    for (name, players), gs in sorted(games.items(), key=lambda kv: (ORDER.index(kv[0][0]) if kv[0][0] in ORDER else 99, kv[0][1])):
        summaries.append(summarize(name, players, gs))
    coverage = {}
    cpath = os.path.join(out_dir, "coverage.json")
    if os.path.isfile(cpath):
        coverage = json.load(open(cpath, encoding="utf-8"))
    tempo = tempo_race()
    json.dump({"summaries": summaries, "coverage": coverage, "tempo_race": tempo},
              open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8"), indent=1)
    md = render(summaries, coverage, tempo)
    open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8").write(md)
    return os.path.join(out_dir, "report.md")


def render(summaries, coverage, tempo):
    lines = ["# The Still Hour — play engine report", "",
             "Designer-facing (spoilers). Every game was played on the emulated SCED table from the owner's save "
             "(tools/play_engine). Simulation, not a playtest.", ""]
    lines += ["## Per scenario", "",
              "| scenario | p | runs | objective done | Hour done | Hours to spare | rounds | defeat games | Dissonance max (mean/max) | reset | loop resolution |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        obj = pct(round(s.get("completion", 0) * s["runs"]), s["runs"]) if "completion" in s else (
            "%.2f obj/loop" % s["objectives_mean"] if "objectives_mean" in s else (
                "contest %s" % pct(round(s.get("contest_reached", 0) * s["runs"]), s["runs"]) if "contest_reached" in s else "–"))
        res = ", ".join("%s %s" % (k, pct(v, s["runs"])) for k, v in sorted(s["resolution"].items(), key=lambda kv: str(kv[0])))
        lines.append("| %s | %d | %d | %s | %s | %s | %s | %s | %s / %d | %s | %s |" % (
            s["scenario"], s["players"], s["runs"], obj, fmt(s.get("completed_hour")), fmt(s.get("hours_to_spare")),
            fmt(s["rounds"]), pct(round(s["defeat_games"] * s["runs"]), s["runs"]), fmt(s["diss_max_mean"]),
            s["diss_max_max"], pct(round(s["reset_rate"] * s["runs"]), s["runs"]), res))
    lines += ["", "## Compared with the tempo model (pipeline/simulate_tempo.py --race)", "",
              "The old model: one district, heading straight there (scar 0 for Part I rows, scar 4 for Part II rows). "
              "The engine: Part I at scar 0, Part II at scar 3, 3 investigators.", "",
              "| scenario | engine done | engine Hours left | tempo done | tempo Hours left |", "|---|---|---|---|---|"]
    for s in summaries:
        k = TEMPO_KEY.get(s["scenario"])
        t = tempo.get(s["players"], {}).get(k[0]) if k else None
        if k and "completion" in s:
            tv = t[k[1]] if t else None
            lines.append("| %s (%dp) | %s | %s | %s | %s |" % (s["scenario"], s["players"], pct(round(s["completion"] * s["runs"]), s["runs"]),
                         fmt(s.get("hours_to_spare")), "%d%%" % tv[0] if tv else "–", fmt(tv[1]) if tv else "–"))
    lines += ["", "## Details", ""]
    for s in summaries:
        lines += ["### %s — %d investigator(s), %d runs" % (s["scenario"], s["players"], s["runs"]), ""]
        if "objectives_per_loop" in s:
            lines.append("- objectives per loop: " + ", ".join("%d: %s" % (k, pct(round(v * s["runs"]), s["runs"]))
                                                          for k, v in s["objectives_per_loop"].items()))
            lines.append("- each objective: " + ", ".join("%s %s" % (k, pct(round(v * s["runs"]), s["runs"])) for k, v in s["each"].items()))
        if "contest_reached" in s:
            lines.append("- contest reached %s; mean progress %s; finale begun at Hour %s, Dissonance %s" % (
                pct(round(s["contest_reached"] * s["runs"]), s["runs"]), fmt(s["contest_mean"]), fmt(s["finale_began_hour"]),
                fmt(s["finale_began_diss"])))
            lines.append("- contest sources per game: " + ", ".join("%s %.1f" % (k, v) for k, v in s["contest_sources"].items()))
        lines.append("- loop ended by: %s; district resolutions: %s" % (
            s["ended"], "; ".join("%s %s" % (d, dict(c)) for d, c in s["district_resolutions"].items())))
        lines.append("- mean rounds %s, final Hour %s; clues %s (%s per round); tests passed %s" % (
            fmt(s["rounds"]), fmt(s["end_hour"]), fmt(s["clues_mean"]), fmt(s["clues_per_round"]), fmt(s["tests_pass_rate"], 2)))
        lines.append("- Hour by end of round: " + ", ".join("r%s %s" % (r, fmt(v)) for r, v in s["hour_curve"].items()))
        lines.append("- Dissonance by end of round: " + ", ".join("r%s %s" % (r, fmt(v)) for r, v in s["diss_curve"].items()))
        lines.append("- Hours from: " + ", ".join("%s %.2f" % (k, v) for k, v in s["hour_sources"].items()))
        lines.append("- Dissonance from: " + ", ".join("%s %.2f" % (k, v) for k, v in s["dissonance_sources"].items()))
        lines.append("- band at the end: %s; highest band reached: %s; Appointed max stage: %s (manifests ~Hour %s); "
                     "Hold Backs %s; its attacks %s" % (s["band_end"], s["band_max"], s["stage_max"], fmt(s["manifest_hour"]),
                                                         fmt(s["holdbacks"]), fmt(s["appointed_attacks"])))
        lines.append("- defeats: %s of games (mean %s); damage %s, horror %s per game" % (
            pct(round(s["defeat_games"] * s["runs"]), s["runs"]), fmt(s["defeats_mean"], 2), fmt(s["damage_mean"]), fmt(s["horror_mean"])))
        lines.append("- horror from: " + ", ".join("%s %.2f" % kv for kv in s["horror_by"].items()))
        lines.append("- damage from: " + ", ".join("%s %.2f" % kv for kv in s["damage_by"].items()))
        if s["defeated_by"]:
            lines.append("- defeats per game by the last blow: " + ", ".join("%s %.2f" % kv for kv in s["defeated_by"].items())
                         + "; who: " + ", ".join("%s %.2f" % (k.replace("sthr", ""), v) for k, v in s["defeated_who"].items()))
        lines.append("- encounter deck %s cards, %s draws, reshuffles %s; crossings cost %s Hours" % (
            fmt(s["deck_size"]), fmt(s["encounters"]), fmt(s["reshuffles"], 2), fmt(s["crossing_hours"])))
        lines.append("- enemies spawned per game: " + ", ".join("%s %.2f" % (k.replace("sthr-", ""), v) for k, v in s["spawns"].items()))
        lines.append("- spawn instruction -> location used: " + "; ".join(
            "%s (%s) -> %s" % (k.replace("sthr-", ""), v["instruction"], ", ".join("%s %d" % (a.replace("sthr-loc-", ""), c)
                                                                               for a, c in v["used"].items()))
            for k, v in s["spawn_locations"].items()))
        lines.append("- Memory: %s on cards, banked +%s per game; Years per investigator %s (card Years %s per game)" % (
            fmt(s["memory_on_cards"]), fmt(s["memory_bank_gain"]), fmt(s["years_per_investigator"], 2), fmt(s["card_years"], 2)))
        if s["victory"]:
            lines.append("- Victory claimed: " + ", ".join("%s %s" % (k.replace("sthr-", ""), pct(round(v * s["runs"]), s["runs"])) for k, v in s["victory"].items()))
        if s["bad_spawns"]:
            lines.append("- **spawn problems**: " + "; ".join("%s ×%d" % kv for kv in s["bad_spawns"].items()))
        if s["placement_problems"]:
            lines.append("- **placement problems**: " + "; ".join("%s ×%d" % kv for kv in s["placement_problems"].items()))
        if s["lua_errors"] or s["engine_errors"]:
            lines.append("- **errors**: %d Lua error(s); engine: %s" % (s["lua_errors"], s["engine_errors"][:3]))
        if s["table_notes"]:
            lines.append("- table notes: " + "; ".join("%s ×%d" % kv for kv in list(s["table_notes"].items())[:6]))
        lines.append("")
    whatif = whatifs()
    if whatif:
        lines += ["## What-if runs (proposed changes, tested without touching the campaign)", "",
                  "| what-if | scenario | runs | objective / contest | Hour done | rounds | defeat games | Dissonance max |",
                  "|---|---|---|---|---|---|---|---|"]
        for tag, s in whatif:
            obj = pct(round(s.get("completion", 0) * s["runs"]), s["runs"]) if "completion" in s else (
                "contest %s" % pct(round(s.get("contest_reached", 0) * s["runs"]), s["runs"]) if "contest_reached" in s else "–")
            lines.append("| %s | %s | %d | %s | %s | %s | %s | %s |" % (tag, s["scenario"], s["runs"], obj,
                         fmt(s.get("completed_hour")), fmt(s["rounds"]), pct(round(s["defeat_games"] * s["runs"]), s["runs"]),
                         fmt(s["diss_max_mean"])))
        lines.append("")
    if coverage:
        lines += ["## Encoding coverage", "",
                  "%d scenario cards; not encoded: %s" % (coverage.get("scenario_cards", 0), coverage.get("missing") or "none"), "",
                  "Approximated:", ""]
        for a in L(coverage.get("approx")):
            lines.append("- %s: %s" % (a["id"], a["how"]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(build())
