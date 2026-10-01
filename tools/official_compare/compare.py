#!/usr/bin/env python3
"""Compare a campaign's structure with the official campaigns.

Seven areas, the owner's checklist: agenda pacing (doom), act pacing
(clues), locations (count, connections, clues against the act), enemies
(share, stats, elites), encounter cards (skill tests, lingering effects),
chaos-bag changes over a campaign, and XP.

Official data is downloaded on first use into .cache/official/ (never
committed):
  - SCED's own TTS campaign files (github.com/Chr1Z93/SCED-downloads
    releases): the scenario boxes as the table builds them, with each
    card's GMNotes (agenda doom, act clue thresholds, location icons and
    connections, enemy traits).
  - arkhamdb-json-data (github.com/Kamalisk/arkhamdb-json-data): card
    stats and text (location clues and shroud, enemy stats, victory,
    treachery text) for Night of the Zealot to The Innsmouth Conspiracy.
  - arkham-cards-data (github.com/zzorba/arkham-cards-data): campaign
    guides as data (chaos-bag adds/removes, XP awards).

The Still Hour's side comes from the campaign data and dist/'s Saved
Object (location connections). Usage:

    python3 tools/official_compare/compare.py
"""
import glob
import json
import os
import re
import statistics as st
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, ".cache", "official")
SCED_DL = "https://github.com/Chr1Z93/SCED-downloads/releases/latest/download/%s.json"
CAMPAIGNS = ["night_of_the_zealot", "the_dunwich_legacy", "the_path_to_carcosa", "the_forgotten_age",
             "the_circle_undone", "the_dream_eaters", "the_innsmouth_conspiracy"]
GUIDES = ["notz", "dwl", "ptc", "tfa", "tcu", "tdea", "tdeb", "tic", "eoe", "tskc", "fhv", "tdc"]


def fetch():
    os.makedirs(os.path.join(CACHE, "tts"), exist_ok=True)
    for repo, name in (("https://github.com/Kamalisk/arkhamdb-json-data", "adb"),
                       ("https://github.com/zzorba/arkham-cards-data", "acd")):
        if not os.path.isdir(os.path.join(CACHE, name)):
            subprocess.run(["git", "clone", "-q", "--depth", "1", repo, os.path.join(CACHE, name)], check=True)
    for c in CAMPAIGNS:
        path = os.path.join(CACHE, "tts", c + ".json")
        if not os.path.exists(path):
            urllib.request.urlretrieve(SCED_DL % c, path)


def adb_cards():
    out = {}
    for f in glob.glob(os.path.join(CACHE, "adb", "pack", "*", "*.json")) + glob.glob(os.path.join(CACHE, "adb", "*.json")):
        try:
            data = json.load(open(f, encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(data, list):
            for c in data:
                if isinstance(c, dict) and c.get("code"):
                    out[c["code"]] = c
    return out


def gm(o):
    g = o.get("GMNotes") or ""
    if not g.startswith("{"):
        return None
    try:
        return json.loads(g)
    except ValueError:
        return None


def cards_in(o, path=""):
    out = []
    g = gm(o)
    if g and g.get("type") in ("Agenda", "Act", "Location", "Enemy", "Treachery"):
        out.append((path.lower(), g))
    for c in o.get("ContainedObjects") or []:
        out += cards_in(c, path + "/" + (o.get("Nickname") or ""))
    return out


def boxes(o, out):
    g = gm(o)
    if g and g.get("type") == "ScenarioBox":
        out.append((o.get("Nickname"), cards_in(o)))
        return
    for c in o.get("ContainedObjects") or []:
        boxes(c, out)


def icons(s):
    return set(x for x in (s or "").split("|") if x)


def degree(locs):
    """Average connections per location: A connects to B when A's connection
    symbols include one of B's icons (either side)."""
    ic = {k: icons(g.get("locationBack", {}).get("icons")) | icons(g.get("locationFront", {}).get("icons"))
          for k, g in locs.items()}
    deg = []
    for k, g in locs.items():
        con = icons(g.get("locationBack", {}).get("connections")) | icons(g.get("locationFront", {}).get("connections"))
        deg.append(sum(1 for o in locs if o != k and ic[o] & con))
    return st.mean(deg) if deg else 0


TEST = re.compile(r"\btest\b", re.I)
LINGER = re.compile(r"\battach\b|put .* into (?:play|your threat area)|threat area", re.I)


def official_rows(adb):
    rows = []
    for camp in CAMPAIGNS:
        found = []
        boxes(json.load(open(os.path.join(CACHE, "tts", camp + ".json"), encoding="utf-8")), found)
        for name, cards in found:
            ag = [g for p, g in cards if g["type"] == "Agenda" and "set-aside" not in p]
            ac = [g for p, g in cards if g["type"] == "Act" and "set-aside" not in p]
            doom = [x for x in (adb.get(g["id"], {}).get("doom") or g.get("doomThreshold") for g in ag) if isinstance(x, int)]
            act_pi = [g.get("clueThresholdPerInvestigator") or (adb.get(g["id"], {}).get("clues") or 0)
                      for g in ac if not adb.get(g["id"], {}).get("clues_fixed")]
            act_pi = [x for x in act_pi if x]
            locs = {g["id"]: g for p, g in cards if g["type"] == "Location"}
            lclues = sum((adb.get(k, {}).get("clues") or 0) for k in locs if not adb.get(k, {}).get("clues_fixed"))
            enc = [(g, adb.get(g["id"], {})) for p, g in cards if "encounter deck" in p and g["type"] in ("Enemy", "Treachery")]
            en = [c for g, c in enc if g["type"] == "Enemy"]
            tr = [c.get("text") or "" for g, c in enc if g["type"] == "Treachery"]
            elites = [g for p, g in cards if g["type"] == "Enemy" and "Elite" in (g.get("traits") or "")]
            vic = sum((adb.get(k, {}).get("victory") or 0) for k in locs) + \
                sum((adb.get(g["id"], {}).get("victory") or 0) for p, g in cards if g["type"] == "Enemy")
            if len(enc) < 10:
                continue
            rows.append(dict(scenario=name, agendas=len(ag), doom=sum(doom), clue_acts=len(act_pi), act_pi=sum(act_pi),
                             locations=len(locs), degree=degree(locs), loc_clues_pi=lclues,
                             clue_per_loc=lclues / len(locs) if locs else 0,
                             deck=len(enc), enemy_share=len(en) / len(enc),
                             fight=st.mean([c["enemy_fight"] for c in en if isinstance(c.get("enemy_fight"), int)] or [0]),
                             health=st.mean([c["health"] for c in en if isinstance(c.get("health"), int)] or [0]),
                             elites=len(elites), victory=vic,
                             tr_test=sum(1 for t in tr if TEST.search(t)) / len(tr) if tr else 0,
                             tr_linger=sum(1 for t in tr if LINGER.search(t)) / len(tr) if tr else 0))
    return rows


def bag_changes():
    def walk(x, out):
        if isinstance(x, dict):
            if x.get("type") in ("add_chaos_token", "remove_chaos_token"):
                out.append(x)
            for v in x.values():
                walk(v, out)
        elif isinstance(x, list):
            for v in x:
                walk(v, out)
    add, rem = {}, {}
    for camp in GUIDES:
        out = []
        for f in glob.glob(os.path.join(CACHE, "acd", "campaigns", camp, "*.json")):
            walk(json.load(open(f, encoding="utf-8")), out)
        for e in out:
            toks = e.get("tokens") or []
            if e["type"] == "add_chaos_token" and len(toks) >= 8:
                continue                     # a difficulty's starting bag
            for t in toks:
                d = add if e["type"] == "add_chaos_token" else rem
                d[t] = d.get(t, 0) + 1
    return add, rem


def q(xs):
    xs = [x for x in xs if x is not None]
    a, _, b = st.quantiles(xs, n=4)
    return "%.1f (middle half %.1f-%.1f)" % (st.median(xs), a, b)


def main():
    fetch()
    adb = adb_cards()
    rows = official_rows(adb)
    print("OFFICIAL: %d scenarios, Night of the Zealot to The Innsmouth Conspiracy (Standard)" % len(rows))
    for k, label in (("agendas", "agendas"), ("doom", "total doom"), ("clue_acts", "acts asking for clues"),
                     ("act_pi", "act clues per investigator"), ("locations", "locations"),
                     ("degree", "connections per location"), ("loc_clues_pi", "location clues per investigator"),
                     ("clue_per_loc", "clues per investigator per location"), ("deck", "encounter deck"),
                     ("enemy_share", "enemy share of the deck"), ("fight", "enemy fight"), ("health", "enemy health"),
                     ("elites", "elites in the box"), ("victory", "victory points in the box"),
                     ("tr_test", "treacheries with a skill test"), ("tr_linger", "treacheries that stay in play")):
        print("  %-38s %s" % (label, q([r[k] for r in rows])))
    add, rem = bag_changes()
    print("  chaos-bag changes over a campaign (guide instructions, all campaigns):")
    print("    add   ", dict(sorted(add.items(), key=lambda kv: -kv[1])))
    print("    remove", dict(sorted(rem.items(), key=lambda kv: -kv[1])))
    print()
    print("THE STILL HOUR: see docs/design/OFFICIAL_COMPARISON.md for the matching figures and how they are measured.")


if __name__ == "__main__":
    sys.exit(main())
