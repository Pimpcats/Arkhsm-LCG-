#!/usr/bin/env python3
"""Scenario readiness — is each scenario box genuinely content-complete?

The compiler only refuses to build until every scenario carries the owner's
`_locked` flag (campaigns/<id>/scenario_assignments.json, set by "Lock in as
finished" in the Studio). That flag is a human judgement; this module is the
evidence behind it. It measures every scenario box against the requirements in
campaigns/<id>/scenario_manifest.json and the SCED conventions the compiler
emits, and reports:

  * reference integrity — every card id on the board exists; every manifest
    requirement (reference card, locations, acts, the Occultation clock,
    encounter sets with their quantities, set-aside sets, Named enemies,
    resolutions, starting location, act locations, granted facts) resolves
    to the card that satisfies it;
  * the map — each location's connections resolve to exactly one real
    location of the same map (by printed symbol + colour), every link is
    symmetric, no symbol repeats inside a box (or a box plus the loop hub it
    is placed onto), every SCED connection key is unique on its map (so SCED
    draws exactly the printed lines) and no two locations share a grid slot;
  * feasibility — every objective can be met at 1, 2, 3 and 4 investigators;
  * card data — the fields a card type needs to be played are present, and
    the compiled GMNotes carry SCED's own shape for them.

    python3 pipeline/scenario_content.py              # report
    python3 pipeline/scenario_content.py --lock       # lock scenarios that pass
    python3 pipeline/scenario_content.py --apply-feed # pour the content feed in

`--lock` only ever sets the flag on a scenario with zero errors; it never
unlocks anything and never locks an incomplete box.
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402

ASIDE_DEFAULT = "aside"


def _norm(s):
    s = str(s or "").lower().replace("’", "'").replace("—", "-")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def _sym(x):
    return str(x or "").strip().lower().replace(" ", "")


def _col(x):
    return str(x or "").strip().lower()


def load_full_cards(paths):
    """Like compile_campaign.load_cards, but keeps the print layer (rules
    text, flavour, enemy stats) that the compiler has no use for and the audit
    needs: a card with no printed rules is not a finished card."""
    import render_placeholders as rp
    cards = CC.load_cards(paths)
    ovp = os.path.join(paths["dir"], "card_overrides.json")
    ov = json.load(open(ovp, encoding="utf-8")) if os.path.exists(ovp) else {}
    ptp = os.path.join(HERE, "stillhour_print_text.json")
    print_text = json.load(open(ptp, encoding="utf-8")) if os.path.exists(ptp) else {}
    full = {}
    for cid, c in cards.items():
        _, pt = rp.apply_card_overrides(c, dict(print_text.get(cid, {})), ov.get(cid))
        merged = dict(c)
        merged.update(pt)          # the print layer is what the card shows
        full[cid] = merged
    return full


def load(campaign="still_hour"):
    paths = CC.campaign_paths(campaign)
    cards = load_full_cards(paths)
    assign = json.load(open(paths["assignments"], encoding="utf-8"))
    manifest = json.load(open(paths["manifest"], encoding="utf-8"))
    return cards, assign, manifest


class Report(object):
    def __init__(self):
        self.errors = collections.defaultdict(list)
        self.warnings = collections.defaultdict(list)

    def err(self, sid, msg):
        self.errors[sid].append(msg)

    def warn(self, sid, msg):
        self.warnings[sid].append(msg)

    def ok(self, sid):
        return not self.errors.get(sid)


def expand_sets(manifest, set_ids, placement=None):
    """Set ids (with '#spine' shorthand) -> Counter of card id -> copies."""
    camp = manifest["campaign"]
    sets = camp.get("encounter_sets", {})
    out = collections.Counter()
    missing = []
    for sid in set_ids:
        names = camp.get("shared_spine", []) if sid == "#spine" else [sid]
        for n in names:
            if n not in sets:
                missing.append(n)
                continue
            for c in sets[n]["cards"]:
                where = c.get("placement", ASIDE_DEFAULT if placement == "aside"
                              else "encounter")
                if placement and where != placement:
                    continue
                if not c.get("id"):
                    missing.append("{}:{}".format(n, c.get("name")))
                    continue
                out[c["id"]] += int(c.get("qty", 1))
    return out, missing


def _box(assign, sid):
    return assign.get(sid, {}) or {}


def _locs(assign, sid, cards):
    return [c for c in _box(assign, sid).get("locations", []) if c in cards]


def map_groups(manifest):
    groups = collections.defaultdict(list)
    for sc in manifest["scenarios"]:
        groups[sc.get("map", sc["id"])].append(sc["id"])
    return groups


# the [markup] the renderer draws as glyphs (docs/design/CAMPAIGN_FEED.md); any
# other bracketed word prints literally, e.g. "[agility]"
MARKUP = {"action", "fast", "reaction", "wil", "int", "com", "agi", "wild",
          "perinv", "unique", "skull", "cultist", "tablet", "elderthing",
          "elder", "autofail", "codex"}


def owner_of(members, cid):
    return next((s for s, c in members if c == cid), "_map")


def check_card_fields(rep, sid, cid, c):
    t = c.get("type")
    for field in ("text", "flavor"):
        for tok in re.findall(r"\[([^\]]+)\]", str(c.get(field) or "")):
            if tok.strip().lower() not in MARKUP:
                rep.err(sid, "{}: [{}] in its {} is not card markup".format(cid, tok, field))
    if t == "Location":
        for f in ("shroud", "clues", "icons", "color"):
            if c.get(f) in (None, ""):
                rep.err(sid, "{}: location has no {}".format(cid, f))
        if not c.get("connections"):
            rep.err(sid, "{}: location has no connections".format(cid))
    elif t == "Act":
        if not c.get("text"):
            rep.err(sid, "{}: act has no objective text".format(cid))
        if not c.get("index"):
            rep.err(sid, "{}: act has no index".format(cid))
    elif t == "Agenda":
        if not c.get("text"):
            rep.err(sid, "{}: agenda has no text".format(cid))
    elif t == "Scenario":
        if not c.get("tokens"):
            rep.err(sid, "{}: reference card has no chaos-token rows".format(cid))
    elif t in ("Story", "Treachery"):
        if not c.get("text"):
            rep.err(sid, "{}: {} has no text".format(cid, t.lower()))
    elif t == "Enemy":
        for f in ("fight", "damage", "horror"):
            if c.get(f) is None:
                rep.err(sid, "{}: enemy has no {}".format(cid, f))
        if not c.get("text"):
            rep.err(sid, "{}: enemy has no text".format(cid))


def check_gmnotes(rep, sid, cid, c):
    """The compiled object must carry SCED's own metadata shape."""
    try:
        obj = B.build_card(CC.normalize(c))
        m = json.loads(obj["GMNotes"])
    except Exception as e:  # noqa: BLE001 - report, don't crash the audit
        rep.err(sid, "{}: card does not build ({})".format(cid, e))
        return
    t = c.get("type")
    if m.get("id") != cid:
        rep.err(sid, "{}: GMNotes id mismatch".format(cid))
    if t == "Location":
        front = m.get("locationFront") or {}
        if not front.get("icons") or not front.get("connections"):
            rep.err(sid, "{}: GMNotes locationFront lacks icons/connections".format(cid))
        if not front.get("uses"):
            rep.err(sid, "{}: GMNotes locationFront lacks clue uses".format(cid))
        if "Location" not in obj["Tags"]:
            rep.err(sid, "{}: location is not tagged Location".format(cid))
    elif t == "Agenda":
        if m.get("type") != "Agenda":
            rep.err(sid, "{}: GMNotes type is not Agenda".format(cid))
        if c.get("doom") not in (None, "") and m.get("doomThreshold") != c.get("doom"):
            rep.err(sid, "{}: GMNotes doomThreshold missing".format(cid))
        if not obj["SidewaysCard"]:
            rep.err(sid, "{}: agenda is not sideways".format(cid))
    elif t == "Act":
        if m.get("type") != "Act" or not obj["SidewaysCard"]:
            rep.err(sid, "{}: act metadata/orientation is not SCED's".format(cid))
    elif t == "Scenario":
        if m.get("type") != "ScenarioReference" or not (m.get("tokens") or {}).get("front"):
            rep.err(sid, "{}: reference is not a SCED ScenarioReference".format(cid))
    elif t == "Enemy" and c.get("victory"):
        if m.get("victory") != c.get("victory"):
            rep.err(sid, "{}: GMNotes victory missing".format(cid))
    if "ScenarioCard" not in obj["Tags"]:
        rep.err(sid, "{}: scenario-side card not tagged ScenarioCard".format(cid))


PLAYER_COUNTS = (1, 2, 3, 4)


def objective_feasibility(cards, assign, manifest, n):
    """[(scenario, problem)] for any objective that cannot be met with n
    investigators. Each act's manifest entry says what it consumes (needs):
    its printed clue threshold from named locations, a fixed number of clues,
    at least k clues at each named location, a non-clue test, or the finale
    contest. Clue values and thresholds scale when printed per investigator."""
    out = []
    groups = map_groups(manifest)
    for sc in manifest["scenarios"]:
        sid = sc["id"]
        pool = [x for g in groups[sc.get("map", sid)] for x in _locs(assign, g, cards)]

        def clues_at(name):
            hit = [cid for cid in pool if _norm(cards[cid]["name"]) == _norm(name)]
            if len(hit) != 1:
                return None
            c = cards[hit[0]]
            return int(c.get("clues") or 0) * (n if c.get("clues_per_investigator") else 1)

        for a in (sc.get("stacks", {}).get("act_deck") or {}).get("cards", []):
            need = a.get("needs")
            card = cards.get(a["id"], {})
            if not need:
                out.append((sid, "act {} does not say what it needs".format(a["id"])))
                continue
            where = need.get("from", [])
            got = [clues_at(w) for w in where]
            if None in got:
                out.append((sid, "act {}: a clue source does not resolve".format(a["id"])))
                continue
            label = "act {} at {} investigator(s)".format(a["id"], n)
            if need.get("clues") == "card":
                want = int(card.get("clues") or 0) * (n if card.get("clues_per_investigator") else 1)
                if not want:
                    out.append((sid, "act {} prints no clue threshold".format(a["id"])))
                elif sum(got) < want:
                    out.append((sid, "{}: needs {} clues, only {} exist".format(label, want, sum(got))))
            elif "fixed" in need:
                if sum(got) < need["fixed"]:
                    out.append((sid, "{}: needs {} clues, only {} exist".format(
                        label, need["fixed"], sum(got))))
            elif "each" in need:
                if min(got) < need["each"]:
                    out.append((sid, "{}: a location has fewer than {} clue(s)".format(label, need["each"])))
            elif "contest" in need:
                con = need["contest"]
                if not any("repeatable" in s for s in con.get("sources", [])):
                    out.append((sid, "{}: the contest has no repeatable source".format(label)))
            elif "test" not in need:
                out.append((sid, "act {}: unknown need {}".format(a["id"], need)))
    return out


def audit(campaign="still_hour"):
    cards, assign, manifest = load(campaign)
    rep = Report()
    scen = {sc["id"]: sc for sc in manifest["scenarios"]}
    camp = manifest["campaign"]
    by_name = collections.defaultdict(list)
    for cid, c in cards.items():
        by_name[_norm(c.get("name"))].append(cid)

    # ---- every id on the board is a real card ------------------------------
    for sid, box in assign.items():
        if sid not in scen:
            rep.err(sid, "board has a scenario the manifest does not list")
        for st, ids in box.items():
            if st.startswith("_"):
                continue
            for cid in ids:
                if cid not in cards:
                    rep.err(sid, "{} stack references unknown card {}".format(st, cid))
        for cid in (box.get("_map") or {}):
            if cid not in box.get("locations", []):
                rep.err(sid, "map places {} which is not in its locations".format(cid))

    # ---- deck ids: one CustomDeck per card, or faces overwrite each other ---
    decks = collections.defaultdict(set)
    for cid, c in cards.items():
        decks[CC.normalize(c)["deck"]].add(cid)
    for d, ids in decks.items():
        if len(ids) > 1:
            rep.err("_campaign", "deck id {} shared by {}".format(d, sorted(ids)))

    for sid, sc in scen.items():
        box = _box(assign, sid)
        stacks = sc.get("stacks", {})
        shared = sc.get("shared_from")
        if shared and shared not in scen:
            rep.err(sid, "shared_from names unknown scenario {}".format(shared))
        own_locs = _locs(assign, sid, cards)
        reach = list(own_locs) + (_locs(assign, shared, cards) if shared else [])

        def loc_named(name, pool, _sid=sid):
            hits = [cid for cid in pool if _norm(cards[cid]["name"]) == _norm(name)]
            return hits[0] if len(hits) == 1 else None

        # reference
        ref = sc.get("reference") or {}
        refs = [c for c in box.get("reference", []) if c in cards]
        if not refs:
            rep.err(sid, "no scenario reference card")
        for cid in refs:
            if cards[cid].get("type") != "Scenario":
                rep.err(sid, "{} in reference stack is not a Scenario card".format(cid))
        if ref.get("id") and ref["id"] not in refs:
            rep.err(sid, "reference {} is not in the box".format(ref["id"]))

        # locations
        lst = stacks.get("locations")
        if lst:
            want = [c.get("id") for c in lst.get("cards", [])]
            for entry in lst.get("cards", []):
                cid = entry.get("id")
                if not cid or cid not in own_locs:
                    rep.err(sid, "location '{}' is not on the board".format(entry.get("name")))
                    continue
                c = cards[cid]
                if c.get("type") != "Location":
                    rep.err(sid, "{} is not a Location".format(cid))
                if _norm(c.get("name")) != _norm(entry.get("name")):
                    rep.err(sid, "{} is named '{}', manifest says '{}'".format(
                        cid, c.get("name"), entry.get("name")))
                accepted = entry.get("accepted") or {}
                for f in ("shroud", "clues"):
                    if f in entry and str(c.get(f)) != str(entry[f]):
                        if f in accepted and str(accepted[f]) == str(c.get(f)):
                            continue        # a deliberate, documented deviation
                        rep.warn(sid, "{}: {} {} differs from the guide's {}".format(
                            cid, f, c.get(f), entry[f]))
                back = entry.get("back")
                if back:
                    # a fact-flipped location prints its other side as the back
                    if not c.get("back_text"):
                        rep.err(sid, "{}: flips on a fact but has no back text".format(cid))
                    elif _norm(back.get("flip_fact")) not in _norm(c.get("back_text")):
                        rep.err(sid, "{}: back does not name its fact".format(cid))
                    if str(c.get("back_shroud")) != str(back.get("shroud")):
                        rep.err(sid, "{}: back shroud {} != {}".format(
                            cid, c.get("back_shroud"), back.get("shroud")))
            extra = [c for c in own_locs if c not in want]
            if extra:
                rep.err(sid, "locations not in the manifest: {}".format(extra))
            placed = box.get("_map") or {}
            for cid in own_locs:
                if cid not in placed:
                    rep.err(sid, "{} has no map slot".format(cid))
        elif own_locs:
            rep.err(sid, "locations on the board but none required")

        # starting location
        start = (sc.get("setup") or {}).get("starting_location")
        if start and not loc_named(start, reach):
            rep.err(sid, "starting location '{}' does not resolve".format(start))

        # agenda (the Occultation clock)
        ag = stacks.get("agenda_deck")
        if ag:
            clock = next((k for k in camp.get("clocks", []) if k["id"] == ag.get("ref")), None)
            if not clock:
                rep.err(sid, "agenda ref {} is not a campaign clock".format(ag.get("ref")))
            else:
                want = [s.get("id") for s in clock["stages"]]
                if box.get("agenda_deck", []) != want:
                    rep.err(sid, "agenda deck is not the {} stages in order".format(clock["id"]))
                for s in clock["stages"]:
                    c = cards.get(s.get("id"))
                    if c and c.get("doom") in (None, "") and not s.get("final"):
                        rep.err(sid, "{}: agenda has no doom threshold".format(s["id"]))
        elif box.get("agenda_deck"):
            rep.err(sid, "agenda deck on the board but none required")
        elif shared and not stacks.get("agenda_deck") and sc.get("map") == "loop":
            if not _box(assign, shared).get("agenda_deck"):
                rep.err(sid, "no clock here or in {}".format(shared))

        # acts
        acts = stacks.get("act_deck")
        if acts:
            want = [a.get("id") for a in acts.get("cards", [])]
            if box.get("act_deck", []) != want:
                rep.err(sid, "act deck {} != manifest {}".format(box.get("act_deck"), want))
            # an act is played where the scenario's own map (plus the hub it is
            # placed onto) puts it; the finale has no locations of its own and
            # is played on the whole loop map
            group = [x for g in map_groups(manifest)[sc.get("map", sid)]
                     for x in _locs(assign, g, cards)]
            pool = reach if lst else group
            for a in acts.get("cards", []):
                c = cards.get(a.get("id"))
                if not c or c.get("type") != "Act":
                    rep.err(sid, "act {} is missing or not an Act".format(a.get("id")))
                    continue
                if _norm(c.get("name")) != _norm(a.get("name")):
                    rep.err(sid, "act {} is named '{}', manifest says '{}'".format(
                        a["id"], c.get("name"), a.get("name")))
                where = a.get("at") or a.get("clues_at")
                if where:
                    if not loc_named(where, pool):
                        rep.err(sid, "act {} is played at '{}', which does not resolve".format(
                            a["id"], where))
                    elif _norm(re.sub(r"^The ", "", where)) not in _norm(c.get("text")):
                        rep.warn(sid, "act {} text does not name '{}'".format(a["id"], where))
                for req in a.get("requires", []):
                    if _norm(req) not in _norm(c.get("text")):
                        rep.err(sid, "act {} does not state its requirement '{}'".format(a["id"], req))
        elif box.get("act_deck"):
            rep.err(sid, "act deck on the board but none required")

        # encounter deck
        enc = stacks.get("encounter") or {}
        own_sets = [s for s in enc.get("sets", []) if not (shared and s == "#spine")]
        want, missing = expand_sets(manifest, own_sets)
        aside_want, amiss = expand_sets(manifest, [] if shared else enc.get("aside", []),
                                        placement="aside")
        into_deck, dmiss = expand_sets(manifest, [] if shared else enc.get("aside", []),
                                       placement="encounter")
        for m in missing + amiss + dmiss:
            rep.err(sid, "encounter set member {} has no card id".format(m))
        want = want + into_deck
        have = collections.Counter(box.get("encounter", []))
        if have != want:
            rep.err(sid, "encounter deck mismatch: missing {} extra {}".format(
                dict(want - have), dict(have - want)))
        if shared:
            sbox = _box(assign, shared)
            sneed, _ = expand_sets(manifest, [s for s in enc.get("sets", []) if s == "#spine"])
            if sneed - collections.Counter(sbox.get("encounter", [])):
                rep.err(sid, "the shared spine is not in {}".format(shared))
            for s in enc.get("aside", []):
                sa, _ = expand_sets(manifest, [s], placement="aside")
                if sa - collections.Counter(sbox.get("setup_aside", [])):
                    rep.err(sid, "set-aside set {} is not in {}".format(s, shared))
        for cid in have:
            if cid in cards and cards[cid].get("type") not in ("Enemy", "Treachery"):
                rep.err(sid, "{} in the encounter deck is a {}".format(cid, cards[cid].get("type")))

        # set aside: required sets + story cards the manifest lists
        aside_have = collections.Counter(box.get("setup_aside", []))
        aside_need = collections.Counter(aside_want)
        for entry in (stacks.get("setup_aside") or {}).get("cards", []):
            aside_need[entry["id"]] += 1
        res = stacks.get("resolutions")
        if res:
            for r in camp.get("resolutions", []):
                if not r.get("card"):
                    rep.err(sid, "resolution {} has no card".format(r.get("id")))
                    continue
                aside_need[r["card"]] += 1
                c = cards.get(r["card"])
                if not c or c.get("type") != "Story":
                    rep.err(sid, "resolution {} card missing or not a Story".format(r["id"]))
                elif _norm(c.get("name")) != _norm(r.get("name")):
                    rep.err(sid, "resolution {} card is named '{}'".format(r["id"], c.get("name")))
        if aside_have != aside_need:
            rep.err(sid, "set-aside mismatch: missing {} extra {}".format(
                dict(aside_need - aside_have), dict(aside_have - aside_need)))

        # Named enemies
        named_need = [e["ref"] for e in (stacks.get("enemies_named") or {}).get("cards", [])]
        if sorted(box.get("named", [])) != sorted(named_need):
            rep.err(sid, "named stack {} != manifest {}".format(box.get("named", []), named_need))
        for cid in named_need:
            c = cards.get(cid, {})
            if not c.get("elite") or not c.get("victory"):
                rep.err(sid, "{}: Named enemy lacks Elite/Victory".format(cid))

        # granted facts are recorded by a card in this box (an act records
        # its fact on its b side, as the official acts do)
        texts = " ".join(_norm(cards[c].get(f)) for st in ("act_deck", "setup_aside")
                         for c in box.get(st, []) if c in cards
                         for f in ("text", "back_text"))
        for g in sc.get("grants", []):
            if 'record ' + _norm(g) not in texts and _norm(g) not in texts:
                rep.err(sid, "granted fact '{}' is not recorded by any card".format(g))

        # every card placed in the box is playable and builds as SCED expects
        for st, ids in box.items():
            if st.startswith("_"):
                continue
            for cid in sorted(set(ids)):
                if cid in cards:
                    check_card_fields(rep, sid, cid, cards[cid])
                    check_gmnotes(rep, sid, cid, cards[cid])

    # ---- the maps: connections, symmetry, symbols, slots ---------------------
    for group, sids in map_groups(manifest).items():
        members = [(sid, cid) for sid in sids for cid in _locs(assign, sid, cards)]
        ident = collections.defaultdict(list)
        for sid, cid in members:
            c = cards[cid]
            ident[(_sym(c.get("icons")), _col(c.get("color")))].append(cid)
        for key, ids in ident.items():
            if len(ids) > 1:
                rep.err(sids[0], "map '{}': {} share symbol+colour {}".format(group, ids, key))
        links = {}
        for sid, cid in members:
            out = set()
            for con in cards[cid].get("connections") or []:
                sym = con.get("symbol") if isinstance(con, dict) else con
                col = con.get("color") if isinstance(con, dict) else None
                hits = [x for (s, k), xs in ident.items() for x in xs
                        if s == _sym(sym) and (col is None or k == _col(col))]
                if len(hits) != 1:
                    rep.err(sid, "{}: connection {} {} resolves to {}".format(cid, sym, col, hits))
                    continue
                if hits[0] == cid:
                    rep.err(sid, "{} connects to itself".format(cid))
                out.add(hits[0])
            links[cid] = out
            if not out:
                rep.err(sid, "{} connects to nothing".format(cid))
        owner = {cid: sid for sid, cid in members}
        for a, outs in links.items():
            for b in outs:
                if a not in links.get(b, set()):
                    rep.err(owner[a], "{} -> {} is not symmetric".format(a, b))
        # symbols must be unique within a box and the hub it is placed onto
        for sid in sids:
            sc = scen[sid]
            pool = _locs(assign, sid, cards) + (
                _locs(assign, sc["shared_from"], cards) if sc.get("shared_from") else [])
            seen = collections.defaultdict(list)
            for cid in pool:
                seen[_sym(cards[cid].get("icons"))].append(cid)
            for s, ids in seen.items():
                if len(ids) > 1:
                    rep.err(sid, "symbol {} repeats on {}".format(s, ids))
        # what SCED itself matches on: the GMNotes icon keys. A printed symbol
        # may repeat across districts in another colour, but the key never may,
        # or SCED would draw lines between districts placed in the same loop.
        keys = collections.defaultdict(list)
        meta = {}
        for sid, cid in members:
            m = json.loads(B.build_card(CC.normalize(cards[cid]))["GMNotes"])
            front = m.get("locationFront") or {}
            meta[cid] = front
            for k in re.findall(r"[A-Za-z]+", front.get("icons", "")):
                keys[k].append(cid)
        for k, ids in keys.items():
            if len(ids) > 1:
                rep.err(owner_of(members, ids[0]), "SCED icon key {} shared by {}".format(k, ids))
        for cid, front in meta.items():
            for k in re.findall(r"[A-Za-z]+", front.get("connections", "")):
                hits = keys.get(k, [])
                if len(hits) != 1:
                    rep.err(owner_of(members, cid), "{}: SCED connection {} matches {}".format(
                        cid, k, hits))
                elif not any(kk in re.findall(r"[A-Za-z]+", meta[hits[0]].get("connections", ""))
                             for kk in re.findall(r"[A-Za-z]+", front.get("icons", ""))):
                    rep.err(owner_of(members, cid), "{}: SCED line to {} is one-way".format(
                        cid, hits[0]))
        slots = collections.defaultdict(list)
        for sid, cid in members:
            slot = (_box(assign, sid).get("_map") or {}).get(cid)
            if slot:
                slots[tuple(slot)].append(cid)
                if not (0 <= slot[0] < CC.LOCATION_GRID["cols"] and
                        0 <= slot[1] < CC.LOCATION_GRID["rows"]):
                    rep.err(sid, "{} is off the playmat grid at {}".format(cid, slot))
        for slot, ids in slots.items():
            if len(ids) > 1:
                rep.err(owner[ids[0]], "map '{}': {} share slot {}".format(group, ids, slot))
    # ---- every objective can be met at every supported table size -----------
    for n in PLAYER_COUNTS:
        for sid, msg in objective_feasibility(cards, assign, manifest, n):
            rep.err(sid, msg)
    return rep, assign, manifest


def summary(rep, manifest, assign):
    lines = []
    for sc in manifest["scenarios"]:
        sid = sc["id"]
        state = "LOCKED" if (assign.get(sid) or {}).get("_locked") else "unlocked"
        lines.append("{:22} {:8} {} error(s), {} note(s)".format(
            sid, state, len(rep.errors.get(sid, [])), len(rep.warnings.get(sid, []))))
        for e in rep.errors.get(sid, []):
            lines.append("    ERROR " + e)
        for w in rep.warnings.get(sid, []):
            lines.append("    note  " + w)
    for k in sorted(set(rep.errors) | set(rep.warnings)):
        if k.startswith("_"):
            for e in rep.errors.get(k, []):
                lines.append("{} ERROR {}".format(k, e))
            for w in rep.warnings.get(k, []):
                lines.append("{} note  {}".format(k, w))
    return "\n".join(lines)


def apply_feed(campaign="still_hour"):
    """Pour campaigns/<id>/scenario_content_feed.json in through the Studio's
    own import (the manual-first contract: the feed only fills the fields the
    card editor edits)."""
    sys.path.insert(0, ROOT)
    from cardforge import studio
    feed = json.load(open(os.path.join(ROOT, "campaigns", campaign,
                                       "scenario_content_feed.json"), encoding="utf-8"))
    return studio.act_campaign_import({"campaign": campaign, "data": feed})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="still_hour")
    ap.add_argument("--lock", action="store_true",
                    help="set _locked on every scenario with zero errors")
    ap.add_argument("--apply-feed", action="store_true")
    a = ap.parse_args()
    if a.apply_feed:
        r = apply_feed(a.campaign)
        print("feed: {} created, {} updated, {} skipped".format(
            len(r.get("created", [])), len(r.get("updated", [])), len(r.get("skipped", []))))
    rep, assign, manifest = audit(a.campaign)
    if a.lock:
        path = CC.campaign_paths(a.campaign)["assignments"]
        changed = []
        for sc in manifest["scenarios"]:
            box = assign.get(sc["id"])
            if box is not None and rep.ok(sc["id"]) and not rep.errors.get("_campaign") \
                    and not box.get("_locked"):
                box["_locked"] = True
                changed.append(sc["id"])
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(assign, f, indent=2, ensure_ascii=False)
                f.write("\n")
        print("locked: " + (", ".join(changed) or "nothing new"))
    print(summary(rep, manifest, assign))
    bad = [sc["id"] for sc in manifest["scenarios"] if not rep.ok(sc["id"])]
    return 1 if bad or rep.errors.get("_campaign") else 0


if __name__ == "__main__":
    sys.exit(main())
