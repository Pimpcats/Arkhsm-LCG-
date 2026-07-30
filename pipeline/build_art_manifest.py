#!/usr/bin/env python3
"""
build_art_manifest.py — emits the SCENE-MODE art manifest CardForge consumes
(CARDFORGE_BRIEF §5): one job per card face, {id, art_type, character?, scene,
seed}. CardForge owns prompt composition (house style + art-type profile +
character LoRA + scene), so entries carry SUBJECT text only.

The job list is DERIVED from the card specs (stillhour_cards_spec.json +
stillhour_encounter_spec.json), so it cannot drift from the real cards: a card
added to a spec without a scene here fails the build loudly.

Run: python3 pipeline/build_art_manifest.py   (from repo root or pipeline/)
Out: pipeline/art_manifest.json          (full set)
     pipeline/art_manifest_starter.json  (first-milestone subset, Elias slice + boss)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- card type -> CardForge art-type profile (art_profiles.json) ----
ART_TYPE = {
    "Investigator": "investigator_portrait",
    "Asset": "asset",
    "Event": "event",
    "Skill": "skill",
    "Treachery": "treachery",
    "Enemy": "enemy",
    # scenario side — every card type gets its own art template so a full
    # sweep covers the whole campaign, not just the player cards
    "Location": "location",
    "Agenda": "agenda",
    "Act": "act",
    "Scenario": "scenario",
    "Story": "story",
}
# card types that carry no illustration of their own (the log is a form)
NO_ART = {"CampaignLog"}

# ---- which cards render with a character LoRA/reference (art_profiles allow_character) ----
CHARACTER = {
    "sthr-elias": "elias", "sthr-donebefore": "elias",
    "sthr-ayako": "ayako", "sthr-itmeanswait": "ayako",
    "sthr-cass": "cass", "sthr-seenthishand": "cass",
    "sthr-seraphine": "sera", "sthr-rememberending": "sera",
    "sthr-birdie": "birdie", "sthr-igetout": "birdie",
}

# ---- the scenes (subject only — style/type framing is CardForge's job) ----
SCENES = {
    # investigators
    "sthr-elias": "standing before a dark unlit lighthouse at night, salt wind pulling at his coat",
    "sthr-ayako": "in a lamplit reading room past midnight, surrounded by open books, one page glowing faintly wrong",
    "sthr-cass": "alone at a card table, dealing the same hand again, smoke hanging motionless in the air",
    "sthr-seraphine": "mid-seance, reaching toward a darkness that reaches back, candle flames bending sideways",
    "sthr-birdie": "on an empty night road at the edge of town, glancing back over her shoulder, distant lit windows",
    # Elias signatures/weakness
    "sthr-lamp": "an old brass storm-lantern glowing faint amber in fog, close-up still life",
    "sthr-donebefore": "hands gripping a rail, knuckles white, ghostly repeated afterimages of the same gesture",
    "sthr-eighthgrave": "eight identical fresh graves in a row under a folding starless sky, one open and empty",
    # Ayako
    "sthr-lexicon": "a battered journal filled with spiraling unreadable script, annotations crowding the margins, candlelight",
    "sthr-itmeanswait": "a raised hand in a stillness gesture toward an unseen presence, dust motes frozen mid-air",
    "sthr-untranslatable": "a page of writhing script that hurts to look at, the letters casting shadows in the wrong direction",
    # Cass
    "sthr-markeddeck": "a worn deck of playing cards fanned on green felt, tiny scratches on the backs catching lamplight",
    "sthr-seenthishand": "catching a falling card mid-air without looking at it, barroom blur behind",
    "sthr-housewins": "a debt collector in a long coat at the end of a hallway, ledger in hand, face in shadow, patient",
    # Seraphine
    "sthr-bell": "a small bronze hand-bell on dark velvet, its surface etched with hour markings, faint blue afterglow",
    "sthr-rememberending": "her eyes reflecting a scene that has not happened yet, the room around her dissolving",
    "sthr-debtofhours": "a grandfather clock with its hands spinning backward, shadow spilling from the open case like water",
    # Birdie
    "sthr-compass": "a small brass compass in an open palm, needle pointing at nothing on the map beneath",
    "sthr-igetout": "slipping through a closing door of light, reaching hands just missing her coat",
    "sthr-nobodybelieves": "a crowd of townsfolk looking straight through the viewer, one empty space where a person should be",
    # Recollections
    "sthr-foreknowledge": "a chess move played before the opponent's hand has left the piece, afterimages of futures",
    "sthr-dejavu": "the same doorway twice in one image, mirrored, a single figure entering both",
    "sthr-musclememory": "hands performing a delicate task in total darkness, perfect and sure, faint motion trails",
    "sthr-rehearsedescape": "a night alley with an escape route chalk-marked in glowing lines only the viewer can see",
    "sthr-longwayround": "a street map with one path burned through it, footsteps skipping impossible distances",
    "sthr-borrowedtime": "an hourglass with sand flowing upward into the top bulb, cradled in careful hands",
    "sthr-thistimeforsure": "the same die frozen mid-tumble at five angles at once, one face beginning to glow",
    "sthr-anchorpoint": "a single fixed lit window on a street where everything else blurs with motion",
    "sthr-cassandrasnotebook": "a notebook whose ink writes itself, the pages ahead already filled, pen hovering unheld",
    "sthr-hourlearnedname": "a name spoken as visible frost in the air, a vast shadow flinching back from it",
    # the Appointed boss set (the Appointed's line is ART_SPEC's canonical key image)
    "sthr-appointed": "a tall wrong silhouette at the far end of an empty street, too many angles, not quite arriving, featureless, dread, negative space",
    "sthr-appointedwhisper": "an ear-shaped ripple in the air over a sleeping town, words visible as thin black threads",
    "sthr-crossing": "a freestanding doorway in the town square, its far side showing the same square one hour later",
    # the Named of Ambergrove (Victory elites)
    "sthr-bellringer": "a drowned figure in sodden vestments hauling a bell rope in a flooded belfry, water past its waist, the bell mid-swing",
    "sthr-wearssheriff": "a sheriff on courthouse steps frozen mid-speech, seams of pale light splitting his silhouette, the crowd not noticing",
    "sthr-onewhorides": "a lone rider on a carousel horse at night, motion-blurred at the edges, face perfectly still and smiling",
}

# deterministic seeds: stable per card id, spaced so variants don't collide
def seed_for(card_id):
    return 100 + (sum(ord(c) for c in card_id) * 7) % 8000


def load_spec(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))


def main():
    cards = load_spec("stillhour_cards_spec.json") + load_spec("stillhour_encounter_spec.json")
    manifest = []
    missing = []
    for c in cards:
        cid = c["id"]
        if cid not in SCENES:
            missing.append(cid)
            continue
        job = {
            "id": cid,
            "art_type": ART_TYPE.get(c["type"], "location"),
            "scene": SCENES[cid],
            "seed": seed_for(cid),
        }
        if cid in CHARACTER:
            job["character"] = CHARACTER[cid]
        manifest.append(job)
        # investigators also need a text-only deckbuilding back (Strange Eons renders it)
        if c["type"] == "Investigator":
            manifest.append({"id": cid + "-back", "art_type": "investigator_portrait",
                             "no_art": True, "frame": "investigator_back"})
    if missing:
        raise SystemExit("cards in the spec with NO SCENE (add them to SCENES): " + ", ".join(missing))

    out = os.path.join(HERE, "art_manifest.json")
    json.dump(manifest, open(out, "w", encoding="utf-8"), indent=2)

    # first-milestone subset (ART_PIPELINE_BRIEF Part D): the Elias slice + the boss
    starter_ids = {"sthr-elias", "sthr-elias-back", "sthr-lamp", "sthr-donebefore",
                   "sthr-eighthgrave", "sthr-appointed"}
    starter = [j for j in manifest if j["id"] in starter_ids]
    json.dump(starter, open(os.path.join(HERE, "art_manifest_starter.json"), "w", encoding="utf-8"), indent=2)

    art = [j for j in manifest if not j.get("no_art")]
    print(f"art_manifest.json: {len(manifest)} faces ({len(art)} illustrated, {len(manifest)-len(art)} text-only)")
    print(f"art_manifest_starter.json: {len(starter)} faces (first milestone)")
    by_type = {}
    for j in art:
        by_type[j["art_type"]] = by_type.get(j["art_type"], 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"  {t:22} {n}")


if __name__ == "__main__":
    main()
