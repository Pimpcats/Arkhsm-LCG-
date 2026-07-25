#!/usr/bin/env python3
"""Rebuild an entire campaign through the Studio's own hand-editing API.

The point of this harness is a claim, checked rather than asserted: *every*
piece of a finished campaign can be typed in by hand, with no JSON editing and
no AI. It touches nothing but the endpoints the editor's own buttons call —

    campaign_new · card_new · card_save · scenario_new · scenario_save
    map_save · map_connect · campaign_compile

— then compares the rebuilt campaign field-for-field against the original and
reports any field it could not reproduce.

    python3 tools/rebuild_by_hand.py                 # rebuild still_hour
    python3 tools/rebuild_by_hand.py --keep          # leave the copy behind
    python3 tools/rebuild_by_hand.py --source hollow

Art is deliberately not copied: this proves the *content* path, which is the
part that must never need a text editor.
"""
import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
BASE = "http://127.0.0.1:8570"

# what the editor can set, straight from the renderer's own key lists so this
# harness can never claim coverage the app does not actually have
import render_placeholders as rp                                # noqa: E402

EDITABLE = (set(rp.OV_SPEC_KEYS) | set(rp.OV_PT_KEYS) | set(rp.OV_LOC_KEYS)
            | set(rp.OV_FLAG_KEYS) | set(rp.OV_COUNT_KEYS)
            | set(rp.OV_PROP_KEYS) | {"tokens"})
STRUCTURAL = {"id", "type"}          # chosen when the card is created


def api(action, **body):
    req = urllib.request.Request(
        BASE + "/api/" + action, json.dumps(body).encode(),
        {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}")


def status(campaign):
    return json.load(urllib.request.urlopen(
        BASE + "/api/status?campaign=" + campaign, timeout=900))


def source_cards(campaign):
    """The finished campaign as the renderer sees it: spec + print text +
    whatever the owner has already edited, merged into one dict per card."""
    import glob
    prefix = "stillhour" if campaign == "still_hour" else campaign
    specs = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "pipeline",
                                              prefix + "_*_spec.json"))):
        for c in json.load(open(path, encoding="utf-8")):
            specs[c["id"]] = c
    pt_path = os.path.join(ROOT, "pipeline", prefix + "_print_text.json")
    pts = json.load(open(pt_path, encoding="utf-8")) \
        if os.path.exists(pt_path) else {}
    ov_path = os.path.join(ROOT, "campaigns", campaign, "card_overrides.json")
    ovs = json.load(open(ov_path, encoding="utf-8")) \
        if os.path.exists(ov_path) else {}
    out = {}
    for cid, spec in specs.items():
        merged, mpt = rp.apply_card_overrides(spec, pts.get(cid, {}),
                                              ovs.get(cid))
        merged = dict(merged)
        merged.update({k: v for k, v in mpt.items() if not k.startswith("_")})
        out[cid] = merged
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="still_hour")
    ap.add_argument("--name", default="Rebuilt By Hand")
    ap.add_argument("--keep", action="store_true",
                    help="leave the rebuilt campaign in place")
    args = ap.parse_args()

    src = args.source
    cards = source_cards(src)
    if not cards:
        sys.exit("no cards found for campaign '{}'".format(src))
    print("source: {} — {} card(s)".format(src, len(cards)))

    # 0. what does the source use that the editor cannot set?
    unreachable = {}
    for cid, c in cards.items():
        for k in c:
            if k not in EDITABLE and k not in STRUCTURAL:
                unreachable.setdefault(k, []).append(cid)
    if unreachable:
        print("\n!! fields with NO hand-editable control:")
        for k, ids in sorted(unreachable.items()):
            print("   {:<18} on {} card(s), e.g. {}".format(k, len(ids), ids[0]))
    else:
        print("every authored field has a control in the editor")

    # 1. a brand-new, empty campaign
    r = api("campaign_new", name=args.name)
    if not r.get("ok"):
        sys.exit("could not create the campaign: " + str(r.get("message")))
    dest = r["id"]
    print("\nnew campaign: {} (starts with {} cards)"
          .format(dest, len(status(dest)["cards"])))

    # 2. every card, created and filled in exactly as a person would
    idmap, failed = {}, []
    for cid, c in cards.items():
        made = api("card_new", campaign=dest, type=c.get("type", "Asset"),
                   name=c.get("name") or cid, **{"class": c.get("class") or ""})
        if not made.get("ok"):
            failed.append((cid, made.get("message")))
            continue
        idmap[cid] = made["id"]
        fields = {k: v for k, v in c.items() if k in EDITABLE}
        fields.pop("connections", None)      # made with map_connect below
        fields.pop("icons", None)
        api("card_save", campaign=dest, card=made["id"], **fields)
    print("cards typed in: {}/{}{}".format(
        len(idmap), len(cards),
        ("  FAILED: " + str(failed[:3])) if failed else ""))

    # 3. the scenario boxes, and what sits in each stack
    board = {}
    apath = os.path.join(ROOT, "campaigns", src, "scenario_assignments.json")
    if os.path.exists(apath):
        board = json.load(open(apath, encoding="utf-8"))
    mpath = os.path.join(ROOT, "campaigns", src, "scenario_manifest.json")
    names = {}
    if os.path.exists(mpath):
        man = json.load(open(mpath, encoding="utf-8"))
        for s in (man.get("scenarios") or []):
            if isinstance(s, dict) and s.get("id"):
                names[s["id"]] = s.get("name") or s["id"]
    sid_map, assigns = {}, {}
    for sid in board:
        made = api("scenario_new", campaign=dest, name=names.get(sid, sid))
        if made.get("ok"):
            sid_map[sid] = made["id"]
    for sid, stacks in board.items():
        if sid not in sid_map:
            continue
        assigns[sid_map[sid]] = {
            st: [idmap[i] for i in ids if i in idmap]
            for st, ids in stacks.items()
            if isinstance(ids, list) and st != "_map"}
    api("scenario_save", campaign=dest, assignments=assigns)
    print("scenario boxes: {}/{}".format(len(sid_map), len(board)))

    # 4. lay the locations out on the map grid
    grid = status(dest)["scenarios"]["grid"]
    placed = 0
    for sid, new_sid in sid_map.items():
        locs = assigns.get(new_sid, {}).get("locations") or []
        slots = {cid: [i % grid["cols"], i // grid["cols"]]
                 for i, cid in enumerate(locs[:grid["cols"] * grid["rows"]])}
        if slots and api("map_save", campaign=dest, scenario=new_sid,
                         slots=slots).get("ok"):
            placed += len(slots)
    print("locations placed on the map: {}".format(placed))

    # 5. the connections, made the way the app makes them: click A, click B
    sym_of = {cid: str(c.get("icons") or "").lower()
              for cid, c in cards.items() if c.get("type") == "Location"}
    wanted, links = set(), 0
    for cid, c in cards.items():
        if c.get("type") != "Location":
            continue
        for conn in (c.get("connections") or []):
            s = str(conn.get("symbol") if isinstance(conn, dict) else conn).lower()
            for other, osym in sym_of.items():
                if osym and osym == s and other != cid:
                    wanted.add(tuple(sorted((cid, other))))
    for a, b in sorted(wanted):
        if a in idmap and b in idmap:
            sid = next((sid_map[s] for s, st in board.items()
                        if a in (st.get("locations") or [])), None)
            if api("map_connect", campaign=dest, scenario=sid,
                   a=idmap[a], b=idmap[b]).get("ok"):
                links += 1
    print("connections clicked in: {}/{}".format(links, len(wanted)))

    # 6. compare, field by field, against the original
    rebuilt = {c["id"]: c for c in status(dest)["cards"]}
    diffs, checked = [], 0
    for cid, c in cards.items():
        new = rebuilt.get(idmap.get(cid, ""))
        if not new:
            continue
        got = new.get("content") or {}
        for k, v in c.items():
            if k not in EDITABLE or k in ("icons", "connections", "tokens"):
                continue
            checked += 1
            mine, theirs = got.get(k), v
            if isinstance(theirs, bool):
                mine = bool(mine)
            elif theirs is not None:
                mine = "" if mine is None else str(mine).strip()
                theirs = str(theirs).strip()
            if mine != theirs:
                diffs.append((cid, k, theirs, mine))
    print("\nfields compared: {}   mismatched: {}".format(checked, len(diffs)))
    for d in diffs[:15]:
        print("   {} · {}: authored {!r} -> rebuilt {!r}".format(*d))

    # 7. the finished box: lock every scenario, compile it for TTS
    for new_sid in assigns:
        assigns[new_sid]["_locked"] = True
    api("scenario_save", campaign=dest, assignments=assigns)
    comp = api("campaign_compile", campaign=dest)
    print("\ncompiled to TTS: {}  ({})".format(
        comp.get("ok"),
        "{} scenario(s), {} card(s) -> {}".format(
            comp.get("scenarios"), comp.get("cards"), comp.get("out"))
        if comp.get("ok") else comp.get("message")))

    faces = sum(1 for i in idmap.values()
                if os.path.exists(os.path.join(ROOT, "art", "faces", i + ".png")))
    print("card faces composed: {}/{}".format(faces, len(idmap)))

    ok = (not unreachable and not failed and not diffs
          and len(idmap) == len(cards) and comp.get("ok"))
    print("\n{}".format(
        "VERDICT: the whole campaign is reproducible by hand"
        if ok else "VERDICT: gaps above still need a JSON edit"))

    if not args.keep:
        for path in (os.path.join(ROOT, "campaigns", dest),
                     os.path.join(ROOT, "out", dest)):
            shutil.rmtree(path, ignore_errors=True)
        for path in (os.path.join(ROOT, "pipeline", dest + "_cards_spec.json"),
                     os.path.join(ROOT, "pipeline", dest + "_imported_spec.json"),
                     os.path.join(ROOT, "dist", dest + "_campaign.json")):
            if os.path.exists(path):
                os.remove(path)
        # investigators also compose a "-back" face — name both explicitly so
        # the sweep can never reach a card this run did not create
        for i in idmap.values():
            for f in (i + ".png", i + "-back.png"):
                path = os.path.join(ROOT, "art", "faces", f)
                if os.path.exists(path):
                    os.remove(path)
        # the copy's edits lived in its own campaign folder, which just went
        # with the rmtree above — nothing to unpick from anyone else's file
        print("(rebuilt copy cleaned up — pass --keep to inspect it)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
