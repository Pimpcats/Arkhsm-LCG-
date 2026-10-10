#!/usr/bin/env python3
"""The Still Hour's story map: every thread, where it starts and where it leads.

SPOILERS: the report names Knowledge entries, choices and endings. Designer use only.

It reads the campaign as a player meets it (the player guide and every card's
effective text, both faces) plus the campaign log's registry, and checks that
the story is one connected web rather than a set of dead ends:

  K  each Knowledge entry is written by exactly one act and read somewhere else
     (another scenario's text, the finale, or a card/rule that changes because of it)
  C  each choice is offered once, and each of its two options changes the finale
     and echoes in at least one other place
  M  the loop marks (Torn / Taken / Closed at the Hour), the Prologue records and
     Seraphine's thread are each written and read
  P  every printed pointer resolves: (→Rn) on a card names a resolution of that
     scenario; "see **X**" / "turn to **X**" names a guide section or rule
  A  every act's front has an objective and its back says what happens next;
     every district has its full set of resolutions, and each act-named
     resolution names one of that district's acts
  H  the agenda (Hours I–IX) is complete and Hour IX sends each context somewhere
  E  the finale has several endings; which ones are open depends on the choices
     and Knowledge you carry (enumerated over every combination), and each
     ending is reachable

Run: python3 tools/story_map.py            (report; exit 1 on any failure)
     python3 tools/story_map.py --json     (machine-readable)
"""
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GUIDE = os.path.join(ROOT, "docs", "design", "THE_STILL_HOUR_player_guide.md")
ASSIGN = os.path.join(ROOT, "campaigns", "still_hour", "scenario_assignments.json")
CODE = [os.path.join(ROOT, "src", "tts", "control.lua"),
        os.path.join(ROOT, "src", "StillHour", "Knowledge.ttslua"),
        os.path.join(ROOT, "src", "StillHour", "Hourglass.ttslua"),
        os.path.join(ROOT, "src", "StillHour", "Appointed.ttslua")]

DISTRICT_SECTIONS = {"district_lighthouse": "The Lighthouse", "district_church": "The Drowned Church",
                     "district_road": "The Sunken Road", "district_square": "The Square",
                     "district_fairground": "The Fairground", "district_almanac": "The Almanac House"}


def norm(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[*_]", "", s)
    return re.sub(r"\s+", " ", s).lower()


def load():
    from pipeline import scenario_content
    cards = scenario_content.load("still_hour")[0]
    cards = cards if isinstance(cards, list) else list(cards.values())
    cards = {c["id"]: c for c in cards if c.get("id")}
    guide = open(GUIDE, encoding="utf-8").read()
    assign = json.load(open(ASSIGN, encoding="utf-8"))
    from pipeline import campaign_log
    code = {os.path.relpath(p, ROOT): open(p, encoding="utf-8").read() for p in CODE if os.path.exists(p)}
    return cards, guide, assign, campaign_log, code


def sections(guide):
    """[(heading, level, text)] for every ##/### heading, text up to the next heading of any level."""
    out, cur, lvl, buf = [], "(top)", 1, []
    for line in guide.splitlines():
        m = re.match(r"^(#{2,3}) (.+)$", line)
        if m:
            out.append((cur, lvl, "\n".join(buf)))
            cur, lvl, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(line)
    out.append((cur, lvl, "\n".join(buf)))
    return out


def card_text(c, faces=("text", "back_text", "flavor", "back_flavor", "unrevealed_text", "unrevealed_flavor")):
    return "\n".join(str(c.get(k) or "") for k in faces)


def card_scenario(cid, assign):
    for scn, a in assign.items():
        for k, v in a.items():
            if isinstance(v, list) and cid in v:
                return scn
    return None


def resolutions(text):
    """{'R1': condition, ..., 'NR': condition} from ```resolution fences in a guide section."""
    out = {}
    for m in re.finditer(r"^```resolution (Resolution (\d+b?)|No Resolution)[^(\n]*\(([^\n]*)\)\s*$", text, re.M):
        out["R" + m.group(2) if m.group(2) else "NR"] = m.group(3)
    return out


class Map:
    def __init__(self):
        self.cards, self.guide, self.assign, self.log, self.code = load()
        self.secs = sections(self.guide)
        self.fails, self.notes, self.rows = [], [], {}
        self.places = []                                   # (where, normalized text)
        for h, _l, t in self.secs:
            self.places.append(("guide: " + h, norm(t)))
        for cid, c in self.cards.items():
            self.places.append(("card: " + cid, norm(card_text(c))))
        for p, t in self.code.items():
            self.places.append(("code: " + p, norm(t)))

    def fail(self, check, msg):
        self.fails.append("%s  %s" % (check, msg))

    def where(self, phrase, exclude=()):
        p = norm(phrase)
        return [w for w, t in self.places if p in t and w not in exclude]

    def section(self, name):
        for h, _l, t in self.secs:
            if h == name:
                return t
        return ""

    # -------------------------------------------------------------- K ----
    def check_knowledge(self):
        facts = re.findall(r'\["([a-z-]+)"\]\s*=\s*\{ name = "([^"]+)",\s*district = "([^"]+)",\s*layer = "(\w+)"',
                           self.code.get(os.path.join("src", "StillHour", "Knowledge.ttslua"), ""))
        if len(facts) < 14:
            self.fail("K", "Knowledge registry not found (%d entries)" % len(facts))
        for fid, name, district, layer in facts:
            writers = [cid for cid, c in self.cards.items()
                       if norm("Record in your Campaign Log: " + name) in norm(c.get("back_text") or c.get("text"))]
            if layer in ("surface", "deep") and len(writers) != 1:
                self.fail("K", "%s: written by %d act(s) %s (want exactly 1)" % (name, len(writers), writers))
            own = {"card: " + w for w in writers}
            scn = "district_" + district.lower().replace("sunken ", "").replace(" ", "")
            sec = DISTRICT_SECTIONS.get(scn, "")
            home = {"guide: " + sec} | {"card: " + x for k, v in self.assign.get(scn, {}).items()
                                        if isinstance(v, list) for x in v}
            readers = [r for r in self.where(name, exclude=own) if not r.startswith("code: src/StillHour/Knowledge")]
            # one story: an entry must matter beyond the district that wrote it
            beyond = [r for r in readers if r not in home]
            self.rows["K " + name] = {"layer": layer, "written_by": writers, "home": sorted(set(readers) & home),
                                      "beyond": beyond}
            if layer in ("surface", "deep") and not beyond:
                self.fail("K", "%s: nothing outside its own district reads it" % name)

    # -------------------------------------------------------------- C ----
    def check_choices(self):
        finale = norm(self.section("FINALE — THE LAST HOUR")) + "\n".join(
            t for w, t in self.places if w.startswith("card: sthr-res") or w == "card: sthr-act-lasthour")
        for key, district, a, b in self.log.CHOICES:
            for opt in (a, b):
                name = opt.replace(" (name below)", "")
                offered = [w for w in self.where(name) if w.startswith("guide: ")]
                in_finale = norm(name) in finale
                own = "guide: " + district if district != "Prologue" else "guide: What You Saw"
                echoes = [w for w in self.where(name) if w not in (own, "guide: FINALE — THE LAST HOUR")
                          and not w.startswith("card: sthr-res") and not w.startswith("code: ")]
                self.rows["C %s / %s" % (key, name)] = {"offered_in": own, "finale": in_finale, "echoes": echoes}
                if own not in offered:
                    self.fail("C", "%s: not offered in %s" % (name, own))
                if not in_finale:
                    self.fail("C", "%s: no effect in the finale" % name)
                if not echoes:
                    self.fail("C", "%s: no echo outside its district and the finale" % name)

    # -------------------------------------------------------------- M ----
    def check_marks(self):
        marks = {"Torn": "mark this loop **Torn**", "Taken": "mark this loop **Taken**",
                 "Closed at the Hour": "mark this loop **Closed at the Hour**"}
        g = self.guide
        for m, w in marks.items():
            written = norm(w) in norm(g)
            readers = [x for x in self.where(m) if x != "guide: The Loop"]
            self.rows["M " + m] = {"written": written, "read_in": readers}
            if not written:
                self.fail("M", "%s: no loop ending marks it" % m)
            if not readers:
                self.fail("M", "%s: written but never read" % m)
        for rec in ("You Are Unstuck", "The First Death", "Seraphine's thread", "kept as anchor"):
            n = len(self.where(rec))
            self.rows["M " + rec] = {"places": n}
            if n < 2:
                self.fail("M", "%s: appears in %d place(s): written but not read" % (rec, n))

    # -------------------------------------------------------------- P ----
    def check_pointers(self):
        res = {}
        for h, _l, t in self.secs:
            r = resolutions(t)
            if r:
                res[h] = r
        loop = res.get("THE LOOP", {})
        prologue = res.get("PROLOGUE — THE FIRST HOUR", {}) or res.get("Prologue — The First Hour", {})
        finale = res.get("FINALE — THE LAST HOUR", {})
        for cid, c in self.cards.items():
            t = card_text(c, ("text", "back_text"))
            scn = card_scenario(cid, self.assign)
            for m in re.finditer(r"→\s*(?:(Loop|Finale) Resolution |R)(\d+b?)", t):
                kind, n = m.group(1), "R" + m.group(2)
                if kind == "Loop":
                    table = loop
                elif kind == "Finale" or scn == "finale" or cid.startswith("sthr-act-lasthour"):
                    table = finale
                elif scn == "prologue" or "Prologue" in t[max(0, m.start() - 40):m.start()]:
                    table = prologue
                else:
                    table = loop if cid.startswith("sthr-hour") else res.get(DISTRICT_SECTIONS.get(scn, ""), {})
                if n not in table:
                    self.fail("P", "%s points to %s, which is not a resolution there" % (cid, m.group(0)))
        heads = {norm(h) for h, _l, _t in self.secs}
        terms = {norm(m) for m in re.findall(r"^\*\*([^*]+?)\.?\*\*", self.guide, re.M)}
        terms |= {norm(m) for m in re.findall(r"\*\*([^*]+)\*\*", self.guide)}
        texts = [("guide", self.guide)] + [(cid, card_text(c, ("text", "back_text"))) for cid, c in self.cards.items()]
        for who, t in texts:
            for m in re.finditer(r"(?:see|turn to|read) \*\*([^*]+)\*\*", t):
                x = norm(m.group(1))
                if x not in heads and x not in terms:
                    self.fail("P", "%s: '%s' names no guide section" % (who, m.group(0)))
            for m in re.finditer(r"(?:turn to|in) (?:the )?([A-Z][\w' —-]+?) in the Campaign Guide", t):
                x = norm(m.group(1))
                if not any(x in h or h in x for h in heads) and "resolution" not in x:
                    self.fail("P", "%s: '%s' names no guide section" % (who, m.group(0)))

    # -------------------------------------------------------------- A ----
    def check_acts(self):
        for scn, a in self.assign.items():
            acts = a.get("act_deck") or []
            for cid in acts:
                c = self.cards.get(cid)
                if not c:
                    self.fail("A", "%s: act %s has no card" % (scn, cid))
                    continue
                front, back = norm(c.get("text")), norm(c.get("back_text"))
                if "objective" not in front and scn != "finale":
                    self.fail("A", "%s: no objective on the front" % cid)
                if not back:
                    self.fail("A", "%s: blank back (what happens next?)" % cid)
                elif not re.search(r"record|→|resolution|advance|objectives are complete|choose", back):
                    self.fail("A", "%s: back does not say what happens next" % cid)
            sec = DISTRICT_SECTIONS.get(scn)
            if sec:
                r = resolutions(self.section(sec))
                missing = {"R1", "R2", "R3", "NR"} - set(r)
                if missing:
                    self.fail("A", "%s: missing resolutions %s" % (sec, sorted(missing)))
                names = {norm(self.cards[x]["name"]) for x in acts if x in self.cards}
                for k, cond in r.items():
                    m = re.search(r"you completed (.+?) this loop", cond)
                    if m and m.group(1) != "no act here" and norm(m.group(1)) not in names:
                        self.fail("A", "%s %s: names act '%s', not one of %s" % (sec, k, m.group(1), sorted(names)))
                self.rows["A " + sec] = {"acts": [self.cards[x]["name"] for x in acts if x in self.cards],
                                         "resolutions": sorted(r)}

    # -------------------------------------------------------------- H ----
    def check_hours(self):
        hours = [self.cards.get("sthr-hour-%d" % i) for i in range(1, 10)]
        for i, h in enumerate(hours, 1):
            if not h:
                self.fail("H", "Hour %d missing" % i)
            elif not (h.get("back_flavor") or h.get("back_text")):
                self.fail("H", "Hour %d has no back" % i)
        h9 = norm(hours[8].get("text") if hours[8] else "")
        for ctx in ("prologue", "finale", "loop"):
            if ctx not in h9:
                self.fail("H", "Hour IX does not say what happens in the %s" % ctx)

    # -------------------------------------------------------------- E ----
    def check_endings(self):
        r = resolutions(self.section("FINALE — THE LAST HOUR"))
        need = {"R1", "R1b", "R2", "R3", "R4", "R5", "R6"}
        if need - set(r):
            self.fail("E", "finale resolutions missing: %s" % sorted(need - set(r)))
        choice_opts = [(k, a, b) for k, _d, a, b in self.log.CHOICES]
        deep = [n for n in ("The Keeper's Ninth Death", "The Ticket-Taker's Bargain")]
        conds = {k: norm(v) for k, v in r.items()}
        # every record an ending names must exist in the registry
        known = {norm(x) for _k, _d, a, b in self.log.CHOICES for x in (a, b)} | {norm(x) for x in deep}
        for k, c in conds.items():
            for m in re.finditer(r"records (.+?)(?: and | or |,|$)", c):
                rec = m.group(1).strip()
                if not any(rec in kn or kn in rec for kn in known):
                    self.notes.append("E %s names a record not in the choice/Knowledge registry: %s" % (k, rec))
        # enumerate: which contest-reached endings are open for each combination of
        # choice options, deep entries held, an Ancient/signer present and Memory
        def open_endings(pick, ninth_death, bargain, ancient, memory_ok):
            ch = {k: (a if pick[i] == 0 else b) for i, (k, a, b) in enumerate(choice_opts)}
            o = {"R4"}
            signer = ch["ninth"].startswith("signed")
            if ancient or signer:
                o.add("R1")
            if bargain and ch["ticket"] == "You hold the ticket" and memory_ok:
                o.add("R1b")
            if ch["vote"] == "The vote still stands":
                o.add("R2")
            if ninth_death:
                o.add("R3")
            return frozenset(o)
        seen, reach = set(), set()
        for pick in itertools.product((0, 1), repeat=len(choice_opts)):
            for nd, bg, an, mem in itertools.product((False, True), repeat=4):
                o = open_endings(pick, nd, bg, an, mem)
                seen.add(o)
                reach |= o
        reach |= {"R5", "R6"}                              # contest not reached, by banked Memory
        self.rows["E endings"] = {"defined": sorted(r), "reachable": sorted(reach),
                                  "distinct_open_sets": len(seen)}
        if need - reach:
            self.fail("E", "unreachable endings: %s" % sorted(need - reach))
        if len(seen) < 4:
            self.fail("E", "the open endings barely depend on the story (%d distinct sets)" % len(seen))
        # the conditions the model uses must match the guide's headings
        for k, words in (("R1", "ninth line"), ("R1b", "you hold the ticket"), ("R2", "the vote still stands"),
                         ("R3", "the keeper's ninth death"), ("R4", "contest reached")):
            if words not in conds.get(k, ""):
                self.fail("E", "%s's heading no longer says '%s': update the ending model" % (k, words))

    def run(self):
        for f in (self.check_knowledge, self.check_choices, self.check_marks, self.check_pointers,
                  self.check_acts, self.check_hours, self.check_endings):
            f()
        return self


def main():
    m = Map().run()
    if "--json" in sys.argv:
        print(json.dumps({"fails": m.fails, "notes": m.notes, "rows": m.rows}, indent=1, default=list))
    else:
        for k, v in m.rows.items():
            print("%-60s %s" % (k, json.dumps(v, default=list)[:300]))
        print()
        for n in m.notes:
            print("NOTE", n)
        for f in m.fails:
            print("FAIL", f)
        print("\n%d failure(s)" % len(m.fails))
    return 1 if m.fails else 0


if __name__ == "__main__":
    sys.exit(main())
