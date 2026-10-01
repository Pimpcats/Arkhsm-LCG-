#!/usr/bin/env python3
"""Search the LCG reference library (build it first: tools/library/build_library.py).

    python3 tools/library/search.py surge                  # every line with "surge"
    python3 tools/library/search.py "Concealed" --in rules # only the rules files
    python3 tools/library/search.py "Forced – When" --in cards/player --max 40
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(ROOT, "library")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words", nargs="+")
    ap.add_argument("--in", dest="sub", default="", help="limit to a subfolder (rules, cards, campaigns, ...)")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    if not os.path.isdir(LIB):
        raise SystemExit("library/ is not built: python3 tools/library/build_library.py")
    pat = re.compile(re.escape(" ".join(a.words)), re.I)
    hits = 0
    for d, _, fs in os.walk(os.path.join(LIB, a.sub)):
        for f in sorted(fs):
            p = os.path.join(d, f)
            heading = ""
            for line in open(p, encoding="utf-8"):
                if line.startswith("#"):
                    heading = line.strip("# \n")
                if pat.search(line):
                    print("%s | %s | %s" % (os.path.relpath(p, LIB), heading, line.strip()[:300]))
                    hits += 1
                    if hits >= a.max:
                        return
    print("(%d hit(s))" % hits)


if __name__ == "__main__":
    main()
