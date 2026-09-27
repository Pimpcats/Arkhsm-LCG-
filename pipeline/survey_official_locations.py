#!/usr/bin/env python3
"""
survey_official_locations.py — how official Arkham Horror LCG locations use
their revealed-side text, from the public ArkhamDB card data.

Downloads the encounter files of the core set and the first seven cycles
(Dunwich through Innsmouth) from github.com/Kamalisk/arkhamdb-json-data and
reports: how many locations have no text, what kind of text the rest carry
(Forced, action, restriction, ...), how long it is, and which scenarios have
blank locations. docs/design/LOCATION_DESIGN.md quotes its output.

Run: python3 pipeline/survey_official_locations.py [--cache DIR]
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics
import urllib.request

BASE = "https://raw.githubusercontent.com/Kamalisk/arkhamdb-json-data/master/pack"
PACKS = {
    "core": ["core"],
    "dwl": ["dwl", "tmm", "wda", "litas", "tece", "bota", "uau"],
    "ptc": ["ptc", "eotp", "tuo", "apot", "tpm", "bsr", "dca"],
    "tfa": ["tfa", "tof", "tbb", "hote", "tcoa", "tdoy", "sha"],
    "tcu": ["tcu", "tsn", "wos", "fgg", "uad", "icc", "bbt"],
    "tde": ["tde", "sfk", "tsh", "dsm", "pnr", "wgd", "woc"],
    "tic": ["tic", "itd", "def", "hhg", "lif", "lod", "itm"],
}


def fetch(cache):
    os.makedirs(cache, exist_ok=True)
    for cyc, packs in PACKS.items():
        for p in packs:
            dest = os.path.join(cache, p + "_encounter.json")
            if not os.path.exists(dest):
                with urllib.request.urlopen("{}/{}/{}_encounter.json".format(BASE, cyc, p), timeout=60) as r:
                    open(dest, "wb").write(r.read())


def kinds(text):
    if not text:
        return {"blank"}
    k = set()
    if "Forced" in text:
        k.add("Forced")
    if "[action]" in text:
        k.add("action ability")
    if re.search(r"\[fast\]|\[free\]", text):
        k.add("fast ability")
    if re.search(r"cannot|must|can only|impassable", text, re.I):
        k.add("restriction")
    if re.search(r"horror|damage", text, re.I):
        k.add("deals harm")
    return k or {"other"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "arkhamdb"))
    a = ap.parse_args()
    fetch(a.cache)
    locs = [c for f in glob.glob(os.path.join(a.cache, "*_encounter.json"))
            for c in json.load(open(f, encoding="utf-8")) if c.get("type_code") == "location"]
    clean = lambda t: re.sub(r"Victory \d+\.", "", re.sub(r"<[^>]+>", "", t or "")).strip()
    tally = collections.Counter(k for c in locs for k in kinds(clean(c.get("text"))))
    print("official locations:", len(locs))
    for k, v in tally.most_common():
        print("  {:15} {:4}  {:.0%}".format(k, v, v / len(locs)))
    words = [len(clean(c.get("text")).split()) for c in locs if clean(c.get("text"))]
    print("words of text: median", statistics.median(words))
    print("with Victory: {:.0%}".format(sum(1 for c in locs if c.get("victory")) / len(locs)))
    print("blank:", sorted("{} ({})".format(c["name"], c.get("encounter_code"))
                           for c in locs if not clean(c.get("text"))))


if __name__ == "__main__":
    main()
