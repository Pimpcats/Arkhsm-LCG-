"""Summarize whole-campaign simulations (tools/play_engine/run.py --campaign).

    python3 tools/play_engine/campaign_summary.py [games/campaign_3p.jsonl ...]
    python3 tools/play_engine/campaign_summary.py --dir /path/to/.cache/play_engine/games

Designer tooling (spoilers). Two measurements, the ones the balance targets use:

  * Difficulty: per played slot (Prologue, Nights 1-8, Finale) how often the
    night's goal was met (every goal act advanced; the Prologue's own act; the
    finale reaches its contest), against the design curve 80/80/70/70/60/60/50/
    50/40/40 (mean 60%).
  * Experience: Memory banked per investigator over the campaign (the bank's
    gain each slot: on-card Memory banked at the interlude plus direct income),
    against 35-45 XP, the range of official campaigns.

Also: when each personal quest card is met (slot number), how often each
investigator was defeated, and where the Memory came from.
"""
import argparse
import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report  # noqa: E402

CURVE = [80, 80, 70, 70, 60, 60, 50, 50, 40, 40]
SLOT_NAMES = ["Prologue", "Night 1", "Night 2", "Night 3", "Night 4", "Night 5", "Night 6", "Night 7", "Night 8", "Finale"]
XP_RANGE = (35, 45)


def slot_won(g):
    """The slot's goal was met."""
    if g.get("scenario") == "prologue":
        return report.act_done(g, "sthr-act-firsthour") is not None and bool(report.act_done(g, "sthr-act-firsthour"))
    if g.get("ended") == "contest":
        return True
    goals = g.get("goals")
    if isinstance(goals, list) and goals:
        return all(bool(report.act_done(g, a)) for a in goals)
    return False


def load(paths):
    games = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            games += [json.loads(line) for line in f if line.strip()]
    return games


def summarize(games):
    by = collections.defaultdict(list)
    for g in games:
        by[g["campaign_seed"]].append(g)
    campaigns = len(by)
    out = {"campaigns": campaigns, "slots": {}, "xp": {}, "quest": {}, "defeats": collections.Counter(),
           "memory_sources": collections.Counter(), "players": None, "usage": {}}
    slot_games = collections.defaultdict(list)
    xp = []
    for seed, slots in by.items():
        slots.sort(key=lambda g: g["slot"])
        for g in slots:
            slot_games[g["slot"]].append(g)
            out["players"] = g["players"]
        gain = 0
        for g in slots:
            if g["slot"] < 10:
                gain += (g.get("memory_bank_end") or 0) - (g.get("memory_bank_start") or 0)
        n = slots[0]["players"]
        xp.append(gain / n)
    for slot in range(1, 11):
        gs = slot_games.get(slot, [])
        if not gs:
            continue
        wins = sum(1 for g in gs if slot_won(g))
        out["slots"][slot] = {"name": SLOT_NAMES[slot - 1], "played": len(gs), "reached": len(gs) / campaigns,
                              "wins": wins, "rate": wins / len(gs), "target": CURVE[slot - 1] / 100}
        for g in gs:
            m = g.get("metrics") or {}
            for who in (m.get("defeated_who") or {}):
                out["defeats"][who] += 1
            for why, n in (m.get("memory_on_cards") or {}).items():
                out["memory_sources"][why] += n
            # each investigator's personal quest at the end of the slot: the carried campaign state
            quests = ((g.get("campaign_state") or {}).get("campaign") or {}).get("quest") or m.get("quest") or {}
            for who, q in quests.items():
                if q.get("unlocked"):
                    seen = out["quest"].setdefault(who, {})
                    seen.setdefault(g["campaign_seed"], slot)    # the first slot that ended with it met
    # how often the new abilities fire, per played slot (the Prologue included)
    all_games = [g for gs in slot_games.values() for g in gs]
    for key, label in (("prevented", "damage prevented by Elias"), ("translations", "translation tokens placed"),
                       ("recurred", "events returned by Birdie"), ("reshuffles", "deck reshuffles (empty deck)")):
        vals = [(g.get("metrics") or {}).get(key) or 0 for g in all_games]
        if any(vals):
            out["usage"][label] = statistics.mean(vals)
    # a campaign that ended early counts its unplayed slots as lost
    per_slot = []
    for slot in range(1, 11):
        wins = sum(1 for g in slot_games.get(slot, []) if slot_won(g))
        per_slot.append(wins / campaigns)
    out["mean_rate_all_slots"] = statistics.mean(per_slot)
    # the headline: Prologue to Night 8. The Finale slot only records reaching the contest, so it is
    # shown but kept out of the mean (as in FINISHING_BALANCE.md's earlier whole-campaign table)
    out["mean_rate_nine"] = statistics.mean(per_slot[:9])
    out["target_mean_nine"] = statistics.mean(CURVE[:9]) / 100
    out["xp"] = {"mean": statistics.mean(xp), "min": min(xp), "max": max(xp),
                 "stdev": statistics.pstdev(xp) if len(xp) > 1 else 0.0, "per_campaign": xp}
    return out


def render(s, title=""):
    lines = ["", "== %s: %d campaigns, %s investigators ==" % (title or "campaigns", s["campaigns"], s["players"]),
             "slot        reached  goal met  (of those played)   target"]
    for slot, r in s["slots"].items():
        met = r["wins"] / s["campaigns"]
        lines.append("%-10s  %5.0f%%   %5.0f%%        %5.0f%%            %3.0f%%" %
                     (r["name"], 100 * r["reached"], 100 * met, 100 * r["rate"], 100 * r["target"]))
    lines.append("mean goal-met rate, Prologue to Night 8 (target curve mean %.1f%%, design target about 60%%): %.1f%%" %
                 (100 * s["target_mean_nine"], 100 * s["mean_rate_nine"]))
    x = s["xp"]
    lines.append("Memory banked per investigator over the campaign: mean %.1f, range %.1f-%.1f (official 35-45)" %
                 (x["mean"], x["min"], x["max"]))
    if s["quest"]:
        lines.append("quest card met by the end of slot (mean / earliest / latest; 1 = Prologue):")
        for who, bycamp in sorted(s["quest"].items()):
            slots = list(bycamp.values())
            lines.append("  %-14s %.1f / %d / %d   (%d of %d campaigns)" %
                         (who, statistics.mean(slots), min(slots), max(slots), len(slots), s["campaigns"]))
    if s["usage"]:
        lines.append("per played slot: " + "; ".join("%s %.1f" % (k, v) for k, v in s["usage"].items()))
    if s["defeats"]:
        lines.append("slots with a defeat, by investigator: " + ", ".join("%s %d" % kv for kv in sorted(s["defeats"].items())))
    top = s["memory_sources"].most_common(8)
    if top:
        total = sum(s["memory_sources"].values())
        lines.append("Memory placed on cards, by source (share): " + "; ".join("%s %.0f%%" % (k, 100 * v / total) for k, v in top))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), ".cache", "play_engine", "games"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    files = a.files or sorted(glob.glob(os.path.join(a.dir, "campaign_*p.jsonl")))
    if not files:
        print("no campaign results found")
        return 1
    for f in files:
        s = summarize(load([f]))
        if a.json:
            s["defeats"], s["memory_sources"] = dict(s["defeats"]), dict(s["memory_sources"])
            print(json.dumps(s))
        else:
            print(render(s, os.path.basename(f)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
