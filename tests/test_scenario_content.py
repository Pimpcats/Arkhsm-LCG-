"""Scenario content integrity for The Still Hour.

Every scenario box must resolve every reference it makes (cards, locations,
the clock, encounter sets and their quantities, set-aside sets, Named enemies,
resolutions, granted facts), every location connection must be symmetric and
point at a real location, and a scenario may only carry the owner's lock flag
when all of that holds. The audit itself lives in pipeline/scenario_content.py;
these tests also re-derive the map independently and prove the audit catches
the faults it claims to.
"""
import collections
import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import scenario_content as SC  # noqa: E402
import compile_campaign as CC  # noqa: E402

CARDS, ASSIGN, MANIFEST = SC.load("still_hour")
SCENARIOS = [s["id"] for s in MANIFEST["scenarios"]]

# deliberate deviations are recorded as "accepted" in the manifest (see
# docs/design/CONTENT_DECISIONS.md), so the audit raises no notes at all


def audit_with(cards=None, assign=None, manifest=None):
    """Run the audit on modified copies of the campaign data."""
    orig = SC.load

    def fake(campaign="still_hour"):
        return (cards if cards is not None else copy.deepcopy(CARDS),
                assign if assign is not None else copy.deepcopy(ASSIGN),
                manifest if manifest is not None else copy.deepcopy(MANIFEST))
    SC.load = fake
    try:
        return SC.audit("still_hour")[0]
    finally:
        SC.load = orig


def all_errors(rep):
    return [e for v in rep.errors.values() for e in v]


class ScenarioContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = SC.audit("still_hour")[0]

    def test_eight_scenarios(self):
        self.assertEqual(SCENARIOS, ["prologue", "district_lighthouse", "district_church",
                                     "district_road", "district_square",
                                     "district_fairground", "district_almanac", "finale"])

    def test_every_scenario_is_content_complete(self):
        for sid in SCENARIOS:
            with self.subTest(scenario=sid):
                self.assertEqual(self.rep.errors.get(sid, []), [])
        self.assertEqual(self.rep.errors.get("_campaign", []), [])

    def test_no_unaccepted_deviations(self):
        self.assertEqual(dict(self.rep.warnings), {})

    def test_locks_reflect_complete_content(self):
        for sid in SCENARIOS:
            with self.subTest(scenario=sid):
                if ASSIGN[sid].get("_locked"):
                    self.assertTrue(self.rep.ok(sid), "locked but incomplete")
        self.assertTrue(all(ASSIGN[s].get("_locked") for s in SCENARIOS))

    def test_every_board_id_is_a_card(self):
        for sid, box in ASSIGN.items():
            for st, ids in box.items():
                if st.startswith("_"):
                    continue
                for cid in ids:
                    self.assertIn(cid, CARDS, "{}:{}".format(sid, st))

    def test_connections_symmetric_and_real(self):
        """Independent of the audit: resolve each printed connection (symbol +
        colour) to a location of the same map and demand the reverse link."""
        groups = collections.defaultdict(list)
        for sc in MANIFEST["scenarios"]:
            groups[sc.get("map", sc["id"])] += ASSIGN[sc["id"]].get("locations", [])
        self.assertEqual(set(groups), {"prologue", "loop"})
        for group, locs in groups.items():
            key = {}
            for cid in locs:
                c = CARDS[cid]
                k = (c["icons"].lower(), c["color"].lower())
                self.assertNotIn(k, key, "{} duplicates {}".format(cid, key.get(k)))
                key[k] = cid
            graph = {}
            for cid in locs:
                outs = set()
                for con in CARDS[cid]["connections"]:
                    k = (con["symbol"].lower(), con["color"].lower())
                    self.assertIn(k, key, "{} -> {} is not a location".format(cid, k))
                    outs.add(key[k])
                graph[cid] = outs
            for a, outs in graph.items():
                for b in outs:
                    self.assertIn(a, graph[b], "{} -> {} one-way".format(a, b))
            # the loop map is one connected night: everything reachable from the hub
            start = "sthr-loc-hubsquare" if group == "loop" else "sthr-loc-square"
            seen, todo = {start}, [start]
            while todo:
                for n in graph[todo.pop()]:
                    if n not in seen:
                        seen.add(n)
                        todo.append(n)
            self.assertEqual(seen, set(locs), "{} map is not connected".format(group))

    def test_guide_map_shape(self):
        """Guide §3: the Square hub touches Fairground, Church, Almanac, Road;
        the Road alone leads on to the Lighthouse."""
        district = {}
        for sc in MANIFEST["scenarios"]:
            for cid in ASSIGN[sc["id"]].get("locations", []):
                district[cid] = sc["id"]
        edges = set()
        for cid, sid in district.items():
            if sid == "prologue":
                continue
            for con in CARDS[cid]["connections"]:
                for other, osid in district.items():
                    c = CARDS[other]
                    if osid != "prologue" and c["icons"].lower() == con["symbol"].lower() \
                            and c["color"].lower() == con["color"].lower() and osid != sid:
                        edges.add(frozenset((sid, osid)))
        self.assertEqual(edges, {frozenset(p) for p in [
            ("district_square", "district_fairground"), ("district_square", "district_church"),
            ("district_square", "district_almanac"), ("district_square", "district_road"),
            ("district_road", "district_lighthouse")]})

    def test_encounter_quantities(self):
        spine = collections.Counter(ASSIGN["prologue"]["encounter"])
        self.assertEqual(sum(spine.values()), 24)
        self.assertEqual(spine["sthr-losthour"], 3)
        hub = collections.Counter(ASSIGN["district_square"]["encounter"])
        self.assertEqual(hub - spine, collections.Counter(
            {"sthr-crossing": 1, "sthr-samespeech": 1, "sthr-crowdturns": 1}))
        self.assertNotIn("sthr-crossing", ASSIGN["prologue"]["encounter"])
        aside = collections.Counter(ASSIGN["district_square"]["setup_aside"])
        self.assertEqual(aside["sthr-appointedwhisper"], 2)
        self.assertEqual(aside["sthr-appointed"], 1)

    def test_compiles_with_sced_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "box.json")
            r = CC.compile_campaign(out, require_locked=True)
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["scenarios"], 8)
            top = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
        # real SCED scenario boxes carry no tag; their GMNotes type identifies them
        boxes = [o for o in top["ContainedObjects"]
                 if json.loads(o.get("GMNotes") or "{}").get("type") == "ScenarioBox"]
        self.assertEqual(len(boxes), 8)
        seen = collections.Counter()

        def walk(o, box):
            if o.get("Name") == "Card":
                m = json.loads(o["GMNotes"])
                seen[m["type"]] += 1
                if m["type"] == "Location":
                    self.assertTrue(m["locationFront"]["connections"])
                if m["type"] == "Agenda" and m["id"] != "sthr-hour-9":
                    self.assertEqual(m["doomThreshold"], 1)
                if m["type"] == "ScenarioReference":
                    self.assertIn("Skull", m["tokens"]["front"])
            for c in o.get("ContainedObjects") or []:
                walk(c, box)
        for b in boxes:
            state = json.loads(b["LuaScriptState"])
            self.assertEqual(set(state), {"ml"})
            self.assertEqual(len(state["ml"]), len(b["ContainedObjects"]))
            for o in b["ContainedObjects"]:
                walk(o, b)
        self.assertEqual(seen["Location"], 23)
        self.assertEqual(seen["Act"], 14)
        self.assertEqual(seen["Agenda"], 18)
        self.assertEqual(seen["ScenarioReference"], 8)

    # ---- the audit catches what it claims to --------------------------------
    def test_catches_one_way_connection(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-loc-belfry"]["connections"] = [{"symbol": "t", "color": "#2c4a7c"}]
        errs = all_errors(audit_with(cards=cards))
        self.assertTrue(any("not symmetric" in e for e in errs), errs)

    def test_catches_dangling_connection(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-loc-well"]["connections"] = [{"symbol": "t", "color": "#000000"}]
        errs = all_errors(audit_with(cards=cards))
        self.assertTrue(any("resolves to []" in e for e in errs), errs)

    def test_catches_missing_location_and_bad_start(self):
        assign = copy.deepcopy(ASSIGN)
        assign["district_square"]["locations"].remove("sthr-loc-hubsquare")
        rep = audit_with(assign=assign)
        self.assertFalse(rep.ok("district_square"))
        self.assertTrue(any("starting location" in e for e in rep.errors["district_road"]))

    def test_catches_wrong_encounter_count(self):
        assign = copy.deepcopy(ASSIGN)
        assign["district_square"]["encounter"].remove("sthr-losthour")
        rep = audit_with(assign=assign)
        self.assertTrue(any("encounter deck mismatch" in e for e in rep.errors["district_square"]))
        self.assertTrue(any("shared spine" in e for e in rep.errors["district_church"]))

    def test_catches_unknown_card_and_deck_clash(self):
        assign = copy.deepcopy(ASSIGN)
        assign["finale"]["setup_aside"].append("sthr-no-such-card")
        cards = copy.deepcopy(CARDS)
        cards["sthr-res-2"]["deck"] = cards["sthr-res-1"]["deck"]
        rep = audit_with(cards=cards, assign=assign)
        self.assertTrue(any("unknown card" in e for e in rep.errors["finale"]))
        self.assertTrue(rep.errors["_campaign"])

    def test_catches_unrecorded_fact_and_empty_act(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-act-vote"]["text"] = ""
        cards["sthr-act-vote"]["back_text"] = ""     # the fact's record side
        rep = audit_with(cards=cards)
        errs = rep.errors["district_square"]
        self.assertTrue(any("granted fact" in e for e in errs), errs)
        self.assertTrue(any("no objective text" in e for e in errs), errs)

    def test_catches_symbol_clash_in_a_box(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-loc-vestry"]["icons"] = "triangle"
        rep = audit_with(cards=cards)
        self.assertTrue(any("repeats" in e for e in rep.errors["district_church"]))

    def test_catches_bad_markup(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-act-lamp"]["text"] += " [combat]"
        rep = audit_with(cards=cards)
        self.assertTrue(any("not card markup" in e for e in rep.errors["district_lighthouse"]))



class ContentGapTests(unittest.TestCase):
    """Every element complete: feasibility at every table size, SCED lines,
    the fact-flipped location, the resolution set, no dead cards, art briefs."""

    def test_every_objective_is_achievable_at_1_to_4_investigators(self):
        for n in (1, 2, 3, 4):
            with self.subTest(investigators=n):
                self.assertEqual(SC.objective_feasibility(CARDS, ASSIGN, MANIFEST, n), [])
        acts = [a for s in MANIFEST["scenarios"]
                for a in (s.get("stacks", {}).get("act_deck") or {}).get("cards", [])]
        self.assertEqual(len(acts), 14)
        self.assertTrue(all(a.get("needs") for a in acts))

    def test_feasibility_catches_a_solo_dead_end(self):
        cards = copy.deepcopy(CARDS)
        cards["sthr-act-almanachid"].update(clues=6, clues_per_investigator=False)
        probs = SC.objective_feasibility(cards, ASSIGN, MANIFEST, 1)
        self.assertTrue(any("almanachid" in m for _, m in probs), probs)
        self.assertEqual(SC.objective_feasibility(cards, ASSIGN, MANIFEST, 3), [])

    def test_contest_target_matches_the_engine(self):
        lua = open(os.path.join(ROOT, "src", "StillHour", "Constants.ttslua"),
                   encoding="utf-8").read()
        self.assertIn("contestTarget = 4 * n", lua)
        need = next(a for s in MANIFEST["scenarios"] if s["id"] == "finale"
                    for a in s["stacks"]["act_deck"]["cards"])["needs"]["contest"]
        self.assertEqual(need["per_investigator"], 4)
        act = CARDS["sthr-act-lasthour"]
        text = act["text"] + "\n" + act["back_text"]    # b side: the resolutions
        for part in ("4 ×", "Hold Back", "Sealed Study", "Hour V", "R1b"):
            self.assertIn(part, text)

    def test_sced_draws_only_the_printed_lines(self):
        """Replay SCED's own matcher (PlayArea.ttslua: icons/connections split
        on letters, a connection links every card with that icon) over every
        loop location placed at once: no extra line between districts, none
        missing, all bidirectional."""
        import re
        import build_cards as B
        locs = [c for sc in MANIFEST["scenarios"] if sc.get("map") == "loop"
                for c in ASSIGN[sc["id"]].get("locations", [])]
        meta = {cid: json.loads(B.build_card(CC.normalize(CARDS[cid]))["GMNotes"])["locationFront"]
                for cid in locs}
        by_icon = collections.defaultdict(list)
        for cid, m in meta.items():
            for k in re.findall(r"%a+".replace("%a", "[A-Za-z]"), m["icons"]):
                by_icon[k].append(cid)
        self.assertTrue(all(len(v) == 1 for v in by_icon.values()), dict(by_icon))
        drawn = set()
        for cid, m in meta.items():
            for k in re.findall(r"[A-Za-z]+", m["connections"]):
                self.assertIn(k, by_icon, "{} -> {}".format(cid, k))
                for other in by_icon[k]:
                    drawn.add((cid, other))
        printed = set()
        key = {(CARDS[c]["icons"].lower(), CARDS[c]["color"].lower()): c for c in locs}
        for cid in locs:
            for con in CARDS[cid]["connections"]:
                printed.add((cid, key[(con["symbol"].lower(), con["color"].lower())]))
        self.assertEqual(drawn, printed)
        self.assertTrue(all((b, a) in drawn for a, b in drawn))

    def test_lantern_room_has_its_calm_side(self):
        c = CARDS["sthr-loc-lanternroom"]
        self.assertEqual(c["back_shroud"], 3)
        self.assertIn("The Lamp Was Never Lit", c["back_text"])
        lua = open(os.path.join(ROOT, "src", "StillHour", "Locations.ttslua"),
                   encoding="utf-8").read()
        self.assertIn('"lantern-room"', lua)
        self.assertIn('flipFact = "the-lamp-was-never-lit"', lua)
        # Town Hall Steps is the only other flip; its side is printed on the front
        self.assertIn("The Sheriff Is Already Dead", CARDS["sthr-loc-townhallsteps"]["text"])

    def test_resolutions_complete_and_in_order(self):
        order = [r["card"] for r in MANIFEST["campaign"]["resolutions"]]
        self.assertEqual([r["id"] for r in MANIFEST["campaign"]["resolutions"]],
                         ["R1", "R1b", "R2", "R3", "R4", "R5", "R6"])
        aside = [c for c in ASSIGN["finale"]["setup_aside"] if c in order]
        self.assertEqual(aside, order)
        self.assertIn("Who Walks Beside You", CARDS["sthr-res-1"]["text"])
        self.assertIn("instead", CARDS["sthr-res-1"]["text"])
        self.assertIn("The Ticket-Taker's Bargain", CARDS["sthr-res-bargain"]["text"])
        for cid in order:
            # every row opens with the condition it is checked against
            self.assertTrue(CARDS[cid]["text"].startswith("Contest "), cid)

    def test_hold_is_defined_where_it_is_used(self):
        text = CARDS["sthr-act-walksbeside"]["text"]
        self.assertIn("[action] Hold", text)
        self.assertIn("[wil] or [com]", text)

    def test_no_dead_cards_in_the_pool(self):
        """Every Still Hour card is played: in a scenario stack, in the player
        or encounter bag, or the campaign log token the compiler builds."""
        bagged = set()
        for name in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json"):
            bagged |= {c["id"] for c in json.load(open(os.path.join(ROOT, "pipeline", name),
                                                        encoding="utf-8"))}
        boxed = {cid for box in ASSIGN.values() for st, ids in box.items()
                 if not st.startswith("_") for cid in ids}
        dead = sorted(set(CARDS) - bagged - boxed - {"sthr-campaign-log"})
        self.assertEqual(dead, [])

    def test_every_card_is_briefed_or_text_only(self):
        jobs = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "manifest.json"),
                              encoding="utf-8"))
        self.assertEqual(jobs, json.load(open(os.path.join(ROOT, "pipeline", "art_manifest.json"),
                                              encoding="utf-8")))
        by = {j["id"]: j for j in jobs}
        for cid, c in CARDS.items():
            with self.subTest(card=cid):
                self.assertIn(cid, by)
                j = by[cid]
                if j.get("no_art"):
                    self.assertTrue(j.get("reason"))
                else:
                    self.assertGreater(len(j.get("scene", "")), 20)
                    self.assertTrue(j.get("art_type"))
                if c["type"] == "Investigator":
                    self.assertTrue(by[cid + "-back"]["no_art"])
        extra = {i for i in by if i not in CARDS and not i.endswith("-back")}
        self.assertEqual(extra, set())
        chars = json.load(open(os.path.join(ROOT, "campaigns", "still_hour", "characters.json"),
                               encoding="utf-8"))
        for j in jobs:
            if j.get("character"):
                self.assertIn(j["character"], chars)

    def test_flipped_locations_have_their_side_as_a_hosted_back(self):
        """Every location Locations.ttslua can flip (flipFact / hasBack) is
        built with its own rendered, hosted back face, so the board's flip
        shows the authored side instead of the generic encounter back."""
        import re
        lua = open(os.path.join(ROOT, "src", "StillHour", "Locations.ttslua"),
                   encoding="utf-8").read()
        flips = re.findall(r'name\s*=\s*"([^"]+)"[^}]*flipFact\s*=', lua)
        self.assertEqual(sorted(flips), ["The Lantern Room", "The Town Hall Steps"])
        loop = {CARDS[c]["name"]: c for sc in MANIFEST["scenarios"] if sc.get("map") == "loop"
                for c in ASSIGN[sc["id"]].get("locations", [])}
        box = json.load(open(os.path.join(ROOT, "dist", "the_still_hour_campaign.json"),
                             encoding="utf-8"))
        objs = {}

        def walk(o):
            if o.get("Name") == "Card":
                objs.setdefault(json.loads(o["GMNotes"])["id"], o)
            for c in o.get("ContainedObjects") or []:
                walk(c)
        for o in box["ObjectStates"]:
            walk(o)
        for name in flips:
            cid = loop[name]
            with self.subTest(location=cid):
                self.assertTrue(CARDS[cid].get("back_text"))
                deck = next(iter(objs[cid]["CustomDeck"].values()))
                self.assertTrue(deck["UniqueBack"])
                self.assertIn("/dist/cards/{}-back.jpg".format(cid), deck["BackURL"])
                self.assertTrue(os.path.exists(os.path.join(ROOT, "dist", "cards", cid + "-back.jpg")))
                self.assertNotEqual(deck["BackURL"], deck["FaceURL"])


if __name__ == "__main__":
    unittest.main()
