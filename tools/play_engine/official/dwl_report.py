"""Reports for the Dunwich benchmark (designer tooling).

    python3 tools/play_engine/official/dwl_report.py        # docs/design/DUNWICH_SIM_REPORT.md and
                                                            # docs/design/BENCHMARK_DUNWICH_VS_STILL_HOUR.md

Reads the Dunwich games (.cache/play_engine/official/games/*.jsonl, from
dwl.py) and The Still Hour's (.cache/play_engine/games/*.jsonl, from run.py),
and measures both with the same metrics. The Still Hour side is reported
under neutral labels only (Prologue, Night 1-8, Finale): numbers, no card
names, roles or rules text.
"""
import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ENGINE))
OUT = os.path.join(ROOT, ".cache", "play_engine", "official")
SH_OUT = os.path.join(ROOT, ".cache", "play_engine")
sys.path.insert(0, HERE)
sys.path.insert(0, ENGINE)

NAMES = {"1a": "1a Extracurricular Activity", "1b": "1b The House Always Wins"}
WIN = {"1a": ("R1", "R2", "R3"), "1b": ("R1", "R2", "R3")}
INV = {"02001": "Zoey Samaras", "02002": "Rex Murphy", "02003": "Jenny Barnes", "02004": "Jim Culver"}
PARTY = {2: "Zoey, Rex", 3: "Zoey, Rex, Jenny", 4: "Zoey, Rex, Jenny, Jim"}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def f1(x, nd=1):
    return "–" if x is None else (("%." + str(nd) + "f") % x)


def pct(k, n):
    return "–" if not n else "%d%%" % round(100.0 * k / n)


def ci(k, n):
    """95% Wilson interval, as text."""
    if not n:
        return "–"
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return "%d–%d%%" % (round(100 * max(0, c - h)), round(100 * min(1, c + h)))


def load(d):
    games = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                g = json.loads(line)
                games[os.path.basename(path)[:-6]].append(g)
    return games


def cards():
    p = os.path.join(OUT, "dwl_cards.json")
    return json.load(open(p, encoding="utf-8"))["cards"] if os.path.isfile(p) else {}


def cname(cs, k):
    return (cs.get(k) or {}).get("name") or k


def won(g):
    return g["resolution"] in WIN.get(g["scenario"], ())


def loss_kind(g):
    if won(g):
        return None
    if g["resolution"] == "R4":
        return "agenda ran out (R4)"
    if g["resolution"] == "NR":
        return "every investigator defeated" if not g.get("resigned") else "resigned / defeated before act 3"
    return "unfinished (round cap)"


def tests_failed(m, kinds=("treachery",)):
    tk = m.get("tests_by_kind") or {}
    n = sum((tk.get(k) or {}).get("n", 0) for k in kinds)
    fl = sum((tk.get(k) or {}).get("failed", 0) for k in kinds)
    return n, fl


def common(games, players):
    """The shared benchmark metrics for a list of games (either campaign)."""
    n = len(games)
    ms = [g.get("metrics") or {} for g in games]
    rounds = [g.get("round") or 0 for g in games]
    out = {"runs": n}
    out["rounds"] = mean(rounds)
    out["defeats"] = mean([m.get("defeats", 0) for m in ms])
    out["dmg_inv_round"] = mean([m.get("damage", 0) / players / max(1, r) for m, r in zip(ms, rounds)])
    out["hor_inv_round"] = mean([m.get("horror", 0) / players / max(1, r) for m, r in zip(ms, rounds)])
    out["clues_inv_round"] = mean([m.get("clues", 0) / players / max(1, r) for m, r in zip(ms, rounds)])
    out["spawned"] = mean([len(m.get("spawns") or []) for m in ms])
    out["enemies_defeated"] = mean([m.get("enemies_defeated", 0) for m in ms])
    tf = [tests_failed(m) for m in ms]
    out["enc_tests"] = mean([t[0] for t in tf])
    out["enc_failed"] = mean([t[1] for t in tf])
    out["enc_fail_rate"] = (sum(t[1] for t in tf) / sum(t[0] for t in tf)) if sum(t[0] for t in tf) else None
    out["encounters"] = mean([m.get("encounters", 0) for m in ms])
    return out


def dwl_summary(games, cs):
    s = {"runs": len(games)}
    if not games:
        return s
    players = games[0]["players"]
    s.update(common(games, players))
    n = len(games)
    s["players"] = players
    s["wins"] = sum(1 for g in games if won(g))
    s["res"] = collections.Counter(g["resolution"] for g in games)
    s["loss"] = collections.Counter(loss_kind(g) for g in games if not won(g))
    s["xp"] = mean([mean(list((g.get("xp") or {}).values())) for g in games])
    s["log"] = collections.Counter(e for g in games for e in (g.get("log") or []))
    s["cheated"] = sum(1 for g in games if g.get("cheated"))
    tr = collections.Counter()
    for g in games:
        for inv, t in (g.get("trauma") or {}).items():
            tr["physical"] += t.get("physical", 0)
            tr["mental"] += t.get("mental", 0)
    s["trauma_phys"] = tr["physical"] / n
    s["trauma_ment"] = tr["mental"] / n
    s["defeat_games"] = sum(1 for g in games if (g.get("metrics") or {}).get("defeats", 0) > 0) / n
    db, dmg, hor, drawn = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    who = collections.Counter()
    for g in games:
        m = g.get("metrics") or {}
        for k, v in (m.get("defeated_by") or {}).items():
            db[k] += v
        for k, v in (m.get("damage_by") or {}).items():
            dmg[k] += v
        for k, v in (m.get("horror_by") or {}).items():
            hor[k] += v
        for k, v in (m.get("drawn") or {}).items():
            drawn[cname(cs, k)] += v
        for k, v in (m.get("defeated_who") or {}).items():
            who[INV.get(k, k)] += v
    s["defeated_by"], s["damage_by"], s["horror_by"], s["drawn"], s["defeated_who"] = db, dmg, hor, drawn, who
    # objective pace
    s["round_won"] = mean([g["round"] for g in games if won(g)])
    acts = collections.defaultdict(list)
    for g in games:
        for a in (g.get("metrics") or {}).get("acts_completed") or []:
            acts[a["id"]].append(a["round"])
    s["acts"] = {k: (len(v) / n, mean(v)) for k, v in acts.items()}
    ag = collections.defaultdict(list)
    for g in games:
        for a in (g.get("metrics") or {}).get("agendas") or []:
            if a.get("why") != "advance directly to 2b":
                ag[a["id"]].append(a["round"])
    s["agendas"] = {k: (len(v) / n, mean(v)) for k, v in ag.items()}
    s["rounds_per_agenda"] = mean([g["round"] / max(1, len([a for a in (g.get("metrics") or {}).get("agendas") or []
                                                           if a.get("why") != "advance directly to 2b"]) or 1)
                                   for g in games if (g.get("metrics") or {}).get("agendas")])
    s["doom_placed"] = mean([(g.get("metrics") or {}).get("doom_placed", 0) for g in games])
    s["clues_required"] = None
    return s


def guide_need(scen, players):
    """Clues the scenario's objectives require (acts plus the location objective the AI goes for), from the card data."""
    cs = cards()
    if scen == "1a":
        a = cs.get("02045", {}).get("clues", 3) * players
        return a + 2 * players          # After Hours, then the Faculty Offices' 2 [per_investigator]
    a = cs.get("02066", {}).get("clues", 4) * players + cs.get("02067", {}).get("clues", 2) * players
    return a


# ---------------------------------------------------------------- The Still Hour side

def sh_label(name):
    import run as sh_run
    if name == "prologue":
        return "Prologue", 0
    if name.startswith("finale"):
        return "Finale", 9
    for k, suf in sh_run.NIGHT_VARIANTS.items():
        for d in sh_run.NIGHT_DISTRICTS:
            if name == "district_" + d + suf:
                return "Night %d" % k, k
    return None, None


SH_GAMES = os.path.join(OUT, "still_hour", "games")


def sh_load(d=SH_GAMES):
    games = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                g = json.loads(line)
                games[(g["scenario"], g["players"])].append(g)
    return games


def sh_summaries():
    import report as sh_report
    games = sh_load()
    groups = collections.defaultdict(list)
    for (name, players), gs in games.items():
        label, k = sh_label(name)
        if label:
            for g in gs:
                groups[(k, label, players)].append((name, g))
    out = {}
    cs = {}
    try:
        cs = json.load(open(os.path.join(SH_OUT, "cards.json"), encoding="utf-8"))["cards"]
    except (OSError, ValueError):
        pass
    for (k, label, players), pairs in sorted(groups.items()):
        gl = [g for _, g in pairs]
        byname = collections.defaultdict(list)
        for name, g in pairs:
            byname[name].append(g)
        wins, rounds_won, need = 0, [], []
        loss = collections.Counter()
        for name, gs in byname.items():
            sm = sh_report.summarize(name, players, gs)
            if "completion" in sm:
                wins += round(sm["completion"] * len(gs))
                if sm.get("completed_round"):
                    rounds_won += [sm["completed_round"]] * round(sm["completion"] * len(gs))
            elif "contest_reached" in sm:
                wins += round(sm["contest_reached"] * len(gs))
            for g in gs:
                goals = g.get("goals") or sh_report.NIGHT.get(name) or []
                done = all(sh_report.act_done(g, a) for a in goals) if goals else (g.get("ended") == "contest")
                if not done:
                    m = g.get("metrics") or {}
                    alive = sum(1 for v in (m.get("defeated") or {}).values() if v)
                    if g.get("ended") == "defeat":
                        loss["every investigator defeated"] += 1
                    elif g.get("ended") == "reset":
                        loss["campaign clock (reset) before the goal"] += 1
                    else:
                        loss["time ran out (Hour IX) before the goal"] += 1
                nd = 0
                for a in goals:
                    c = cs.get(a) or {}
                    nd += (c.get("clues") or 0) * (players if c.get("clues_per_investigator") else 1)
                need.append(nd)
        s = common(gl, players)
        s["players"] = players
        s["wins"] = wins
        s["loss"] = loss
        s["round_won"] = mean(rounds_won)
        s["defeat_games"] = sum(1 for g in gl if (g.get("metrics") or {}).get("defeats", 0) > 0) / len(gl)
        s["clues_required"] = mean(need)
        # pace: rounds per Hour turned (the Still Hour's agenda equivalent)
        s["rounds_per_agenda"] = mean([g["round"] / max(1, (g.get("hour") or 1) - 1) for g in gl if g.get("hour")])
        s["xp"] = mean([(g.get("memory_bank_end") or 0) - (g.get("memory_bank_start") or 0) for g in gl])
        s["scenarios"] = len(byname)
        out[(k, label, players)] = s
    return out


# ---------------------------------------------------------------- rendering

def table_row(cells):
    return "| " + " | ".join(cells) + " |"


def dwl_report(tag=None):
    d = os.path.join(OUT, "games" if not tag else "games_" + tag)
    games = load(d)
    cs = cards()
    cov = {}
    if os.path.isfile(os.path.join(OUT, "coverage.json")):
        cov = json.load(open(os.path.join(OUT, "coverage.json"), encoding="utf-8"))
    sums = {}
    for key, gs in games.items():
        scen, p = key.rsplit("_", 1)
        p = int(p[:-1])
        if scen in ("1a", "1b"):
            sums[(scen, "standalone", p)] = dwl_summary(gs, cs)
        else:
            for slot in (1, 2):
                sub = [g for g in gs if g.get("slot") == slot]
                if sub:
                    sums[(sub[0]["scenario"], "%s #%d" % (scen, slot), p)] = dwl_summary(sub, cs)
    return games, sums, cov


def summary_text(out=OUT, tag=None):
    _, sums, _ = dwl_report(tag)
    lines = []
    for (scen, mode, p), s in sorted(sums.items()):
        if s.get("runs"):
            lines.append("%s %-12s %dp: %d games, win %s, %s, rounds %s, defeats %s, xp %s" % (
                scen, mode, p, s["runs"], pct(s["wins"], s["runs"]),
                ", ".join("%s %s" % (k, pct(v, s["runs"])) for k, v in sorted(s["res"].items())),
                f1(s["rounds"]), f1(s["defeats"], 2), f1(s["xp"])))
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary_text())
