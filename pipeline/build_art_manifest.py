#!/usr/bin/env python3
"""
build_art_manifest.py — emits the SCENE-MODE art manifest CardForge consumes
(CARDFORGE_BRIEF §5): one job per card face, {id, art_type, character?, scene,
seed}. CardForge owns prompt composition (house style + art-type profile +
character LoRA + scene), so entries carry SUBJECT text only.

The job list is DERIVED from every Still Hour card spec (player, encounter,
scenario, imported), so it cannot drift from the real cards: a card added to a
spec without a scene here, and not listed as TEXT_ONLY, fails the build loudly.
Also writes campaigns/still_hour/manifest.json (what CardForge and the
assistant bridge read).

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
    "sthrelias": "elias", "sthr-donebefore": "elias",
    "sthrayako": "ayako", "sthr-itmeanswait": "ayako",
    "sthrcass": "cass", "sthr-seenthishand": "cass",
    "sthrseraphine": "sera", "sthr-rememberending": "sera",
    "sthrbirdie": "birdie", "sthr-igetout": "birdie",
}

# ---- the scenes (subject only — style/type framing is CardForge's job) ----
SCENES = {
    # investigators
    "sthrelias": "standing before a dark unlit lighthouse at night, salt wind pulling at his coat",
    "sthrayako": "in a lamplit reading room past midnight, surrounded by open books, one page glowing faintly wrong",
    "sthrcass": "alone at a card table, dealing the same hand again, smoke hanging motionless in the air",
    "sthrseraphine": "mid-seance, reaching toward a darkness that reaches back, candle flames bending sideways",
    "sthrbirdie": "on an empty night road at the edge of town, glancing back over her shoulder, distant lit windows",
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

# ---- the scenario side: the town, the clock, the objectives and the endings ----
# Ambergrove is a small inland 1920s town under a starless, snagged sky on the
# night of an occultation that repeats. Scenes stay subject-only; the art-type
# profile adds the framing (locations are empty places, agendas wide dread,
# acts the place mid-event, stories quiet beats).
SCENES.update({
    # the Occultation — Hours I-IX, one night getting later
    "sthr-hour-1": "the town square at eleven o'clock, lamps lit, townsfolk looking up at a sky where the stars are sliding behind something without an edge",
    "sthr-hour-2": "a lake shore where the water is drawing back unnaturally fast under a dark sky, moored boats settling crooked on the mud",
    "sthr-hour-3": "a half-drowned church tower against the night, the bell swinging, thirteen faint rings of sound rippling the air",
    "sthr-hour-4": "a sunken road collapsing into black water, milestones tilting, a lantern on the far side going out",
    "sthr-hour-5": "empty streets at midnight, every door open, a single chair still rocking on a porch",
    "sthr-hour-6": "the sky over the rooftops cracked like glaze, wrong constellations showing through the seams",
    "sthr-hour-7": "a long street seen from its far end, lamps going dark one by one toward the viewer, something tall at the vanishing point",
    "sthr-hour-8": "the whole town seen from above at the last minute before the hour, clocks on every building pointing the same wrong time",
    "sthr-hour-9": "a black occulted sun-like disc filling the sky over Ambergrove, the town below perfectly still, a seam of pale light down the middle of the night",
    # the shared spine
    "sthr-losthour": "a pocket watch lying in the street, its hands missing, a scattering of numerals on the cobbles like dropped coins",
    "sthr-slippage": "a street reflected in a puddle that is a few seconds behind the street above it",
    "sthr-waitingcongregation": "townsfolk in their Sunday best standing in a line in the fog, all facing the same direction, eyes closed, patient",
    "sthr-drownedchoir": "a choir in waterlogged robes singing with no sound, lake weed in their hair, lit from below by cold water-light",
    "sthr-familiarface": "a stranger in a doorway whose face is almost someone you know, the features blurred as though remembered badly",
    "sthr-lamplighterecho": "a lamplighter frozen mid-reach with his pole to a streetlamp, his outline repeated faintly behind him",
    "sthr-wrongturn": "a crossroads where the signposts point to the same town four times",
    "sthr-rewind": "footprints in wet sand leading backward into a figure that is walking forward",
    "sthr-deadair": "a radio set on a kitchen table with its dial glowing and the air around it visibly still, dust hanging motionless",
    "sthr-loopnotices": "a hundred lit windows across a dark street, a silhouette standing in every one, all turned toward the viewer",
    "sthr-yearinanight": "a hand on a table aging from young to old across a single candle's burn",
    "sthr-forgotten": "a photograph whose faces are fading out while the room in it stays sharp",
    "sthr-oldbones": "a walking cane and a pair of worn boots at the foot of a long steep stair",
    # locations — the Prologue row
    "sthr-loc-square": "Ambergrove's town square at night, bunting and paper lanterns for the occultation, a bandstand, the sky wrong overhead",
    "sthr-loc-hubsquare": "the town square seen from its centre, four streets leading off into fog toward a church, a fairground, a road and a tall house of books",
    "sthr-loc-longpier": "a long wooden pier running out over black still water into mist, lanterns at intervals, the far end lost",
    "sthr-loc-almanacsteps": "broad stone steps up to a narrow printing house door, a painted sign reading nothing legible, handbills scattered on the steps",
    # the Lighthouse
    "sthr-loc-lanternroom": "the glass lantern room at the top of a lighthouse, the great lens dark and cold, salt on the panes, night beyond",
    "sthr-loc-windingstair": "a spiral iron stair climbing the inside of a lighthouse tower, rust and damp, the steps vanishing upward into shadow",
    "sthr-loc-keepersquarters": "a lighthouse keeper's cramped room, a narrow cot, oilcloth coat on a hook, a logbook open on the desk",
    # the Drowned Church
    "sthr-loc-nave": "a church nave half flooded, pews standing in black water, candles still burning on the altar above the waterline",
    "sthr-loc-belfry": "a belfry with a great bell hanging motionless, its rope dripping, the town far below through the louvres",
    "sthr-loc-floodedcrypt": "a vaulted crypt under dark water, tomb lids just visible, a faint shape of paper drifting near the ceiling",
    "sthr-loc-vestry": "a small vestry with robes on pegs and a heavy parish register open on a lectern by candlelight",
    # the Sunken Road
    "sthr-loc-milestones": "a sunken lane between high banks, old milestones along the verge counting down to a town that is behind you",
    "sthr-loc-lowbridge": "a low stone bridge barely above a slow river, water lapping over the cobbles, fog on both banks",
    "sthr-loc-turning": "a bend in a sunken road where the lane doubles back on itself, a lighthouse beam that never sweeps visible over the trees",
    # the Square (Town Hall)
    "sthr-loc-townhallsteps": "the wide steps of a small town hall draped in occultation bunting, a speaker's podium at the top, papers blowing",
    "sthr-loc-recordsoffice": "a records office of tall wooden drawers and ledgers, a single green-shaded lamp over a desk",
    "sthr-loc-well": "an old stone well in a small yard behind the town hall, a bucket rope pulled taut into the dark",
    # the Fairground
    "sthr-loc-wheel": "a Ferris wheel lit with bulbs against the black sky, one carriage swinging at the very top",
    "sthr-loc-hallofmirrors": "a hall of warped mirrors under strings of bulbs, reflections not quite matching one another",
    "sthr-loc-ticketbooth": "a painted ticket booth at the fairground gate, a roll of tickets unspooling across the counter, the window dark",
    # the Almanac House
    "sthr-loc-readingroom": "a reading room of floor-to-ceiling shelves, ladders and green lamps, one book lying open on the floor",
    "sthr-loc-press": "a hand-cranked printing press with a half-set page of type, ink gleaming, almanac sheets hung to dry",
    "sthr-loc-sealedstudy": "a locked study door at the end of a book-lined corridor, light and a faint murmur coming from under it",
    # node sets
    "sthr-darkthatwaits": "darkness pooled at the top of a lighthouse stair, thick as water, the lens above it unlit",
    "sthr-somethingonstair": "a hunched figure sitting on a spiral stair in the dark, knees drawn up, head turned away",
    "sthr-thirteen": "a church clock face with thirteen hour marks, the hands pointing to the extra one",
    "sthr-risingwater": "black water climbing a flight of stone stairs one step at a time",
    "sthr-bridgeremembers": "wet footprints crossing a low stone bridge that begin and end in the middle",
    "sthr-samespeech": "a crowd in a square listening to a speech, their faces lit identically, their mouths moving with the speaker's",
    "sthr-crowdturns": "a crowd of townsfolk all turning their heads at once toward the viewer",
    "sthr-wheelsturn": "the gears and axle of a Ferris wheel turning in the dark, the hub bolt shaped like a clock hand",
    "sthr-reflectionlies": "a funhouse mirror whose reflection is smiling while the room is empty",
    "sthr-pagethatwasnt": "a single loose page lying on a library floor, printed in fresh ink that the rest of the book never had",
    "sthr-inkrunsbackward": "ink lifting off a written page back up into the nib of a hovering pen",
    "sthr-studydoor": "a brass keyhole in a dark wooden door, a thread of pale light leaking out and bending the wrong way",
    # objectives (acts)
    "sthr-act-firsthour": "the almanac house steps at eleven, handbills announcing the occultation at midnight, the sky already darkening at the edges",
    "sthr-act-lamp": "the great lighthouse lens catching its first flame, light beginning to pour out over the dark water",
    "sthr-act-ninthdeath": "an open lighthouse logbook by lamplight, the same hand filling page after page, the ink of the latest entry still wet",
    "sthr-act-whythirteen": "a parish register open under a candle, a column of tally marks for the bell, one mark too many",
    "sthr-act-hourwaswrong": "a waterlogged almanac page held up out of dark crypt water, the printed time smeared",
    "sthr-act-walkbackward": "a sunken road seen looking back toward town, footsteps in the mud pointing the other way",
    "sthr-act-walksbeside": "a hooded walker on a fog-bound road, the hood beginning to lift in the lamplight",
    "sthr-act-sheriffdead": "a sheriff's star and hat lying on the stone lip of a well at night",
    "sthr-act-vote": "a town ledger open to a page of signatures and a tally, a pen resting across it",
    "sthr-act-wheelturns": "the view from the top of a Ferris wheel over the whole lamplit town at once",
    "sthr-act-bargain": "a fairground ticket held out through a booth window by a gloved hand, the face behind it in shadow",
    "sthr-act-almanachid": "a printing press mid-stroke, a fresh almanac sheet coming off it with a different time printed",
    "sthr-act-appointedname": "a study desk with a single word written again and again on every paper, the word itself illegible",
    "sthr-act-lasthour": "the town square at the edge of midnight, a freestanding doorway at its centre, figures holding it shut against the dark",
    # the ending beats and interludes (stories)
    "sthr-story-firstreset": "dawn that is not dawn over the town square, lanterns relit, the night folding back into eleven o'clock",
    "sthr-story-firstdark": "a figure waking on a bench in the square at dusk, salt on the lips, the same lanterns being lit again",
    "sthr-story-actii": "the edge of the square at night, a tall shape at the end of a street that was not there a moment ago",
    "sthr-story-beforefinale": "an almanac house window lit late at night, the rest of the town dark and still",
    "sthr-appointed-approach": "a long empty street of four lamp posts receding into darkness, each farther lamp dimmer, the last one out",
    "sthr-res-1": "a lone lit window in a lighthouse at dawn, the town below waking, one figure keeping watch",
    "sthr-res-bargain": "a fairground gate at first light, a punched ticket on the ground, a tall shadow walking out into the morning",
    "sthr-res-2": "a heavy door closing on a darkness, the town square in first morning light, the lanterns burnt out",
    "sthr-res-3": "figures walking out of the town along the sunken road at dawn, the fog behind them not quite lifting",
    "sthr-res-4": "a door sealed with iron bands and wax in the middle of the square, one chair empty beside it",
    "sthr-res-5": "eleven o'clock in the square again, but the sky has fewer stars missing than before",
    "sthr-res-6": "hooded figures walking the sunken road in fog, all in the same direction, never arriving",
})

# faces with no illustration of their own: the chaos-token reference renders on
# the scenario-reference template (no art window) and the log is a form
TEXT_ONLY = {"sthr-scn-stillhour": "scenario reference: chaos-token template, no art window",
             "sthr-campaign-log": "campaign log: a fillable form"}

CARD_SPECS = ("stillhour_cards_spec.json", "stillhour_encounter_spec.json",
              "stillhour_scenario_spec.json", "stillhour_imported_spec.json")


# deterministic seeds: stable per card id, spaced so variants don't collide
def seed_for(card_id):
    return 100 + (sum(ord(c) for c in card_id) * 7) % 8000


def load_spec(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))


def main():
    cards, seen = [], set()
    for name in CARD_SPECS:
        for c in load_spec(name):
            if c["id"] not in seen:
                seen.add(c["id"])
                cards.append(c)
    manifest = []
    missing = []
    for c in cards:
        cid = c["id"]
        if cid in TEXT_ONLY or c["type"] in NO_ART:
            manifest.append({"id": cid, "art_type": ART_TYPE.get(c["type"], "story"),
                             "no_art": True, "frame": "text_only",
                             "reason": TEXT_ONLY.get(cid, "form")})
            continue
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
    # the campaign folder CardForge and the assistant bridge read
    camp = os.path.join(os.path.dirname(HERE), "campaigns", "still_hour")
    json.dump(manifest, open(os.path.join(camp, "manifest.json"), "w", encoding="utf-8"), indent=2)

    # first-milestone subset (ART_PIPELINE_BRIEF Part D): the Elias slice + the boss
    starter_ids = {"sthrelias", "sthrelias-back", "sthr-lamp", "sthr-donebefore",
                   "sthr-eighthgrave", "sthr-appointed"}
    starter = [j for j in manifest if j["id"] in starter_ids]
    json.dump(starter, open(os.path.join(HERE, "art_manifest_starter.json"), "w", encoding="utf-8"), indent=2)
    json.dump(starter, open(os.path.join(camp, "manifest_starter.json"), "w", encoding="utf-8"), indent=2)

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
