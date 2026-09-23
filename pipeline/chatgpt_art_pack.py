"""ChatGPT art pack: every illustrated card as a numbered, paste-ready brief.

The owner generates art in ChatGPT on their own subscription (no API credits),
so the prompt CardForge would have sent is rewritten for a chat. "requests"
are the owner's batch format: up to 4 separate images per message with the
house style pasted once, one fresh chat each, many at once. Every card also
keeps a standalone single-image "prompt". Numbers are stable (manifest order within a fixed type order), so an
image that comes back as "#007" maps to exactly one card id.

    python3 pipeline/chatgpt_art_pack.py
      -> pipeline/chatgpt_art_pack.json   (number -> card id, used by import_art.py)
      -> docs/CHATGPT_ART_PACK.md     (what the owner pastes)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = "still_hour"

# investigators first (their portraits get approved before anything else, then
# serve as the face reference), then the character cards, then everything else
TYPE_ORDER = ("investigator_portrait", "event", "skill", "asset", "enemy",
              "treachery", "location", "agenda", "act", "story", "scenario")
BATCH = 10
PER_REQUEST = 4       # images per ChatGPT message (owner's batch-request format)

# scenes that invite painted writing or numerals get an explicit guard
LETTERING_WORDS = ("script", "ink", "writ", "page", "letter", "numeral", "sign",
                   "handbill", "marking", "journal", "notebook", "logbook",
                   "map", "clock", "watch", "photograph", "name")

# words that pull image models toward the glossy generated look; stripped from
# the per-type framing because the house style already says how to paint
AI_WORDS = ("cinematic", "atmospheric")
GENERIC_TAIL = "detail concentrated on the focal point"

# art types whose profile puts the investigator in the picture
CHARACTER_TYPES = ("investigator_portrait", "event", "skill", "minicard")

NAMES = {"elias": "Elias Warde", "ayako": "Dr. Ayako Sōma", "cass": "Cass Lindqvist",
         "sera": "Seraphine Vale", "birdie": "Birdie Okonkwo"}


def load(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))


def aspect(prof):
    r = prof["width"] / float(prof["height"])
    if r >= 1.2:
        return "landscape 3:2"
    if r <= 0.83:
        return "portrait 2:3"
    return "square 1:1"


def framing(prof):
    text = prof["type_positive"].split(GENERIC_TAIL)[0]
    parts = [p.strip() for p in text.split(",")
             if p.strip() and not any(w in p for w in AI_WORDS)]
    return ", ".join(parts)


def style_block(camp):
    """The house style every image carries, word for word from campaign.json."""
    return ("HOUSE STYLE: " + camp["style_positive"] + ".\n\n"
            + "".join("{}: {}\n\n".format(k, v)
                      for k, v in camp.get("style_guidance", {}).items()) +
            "CROP: keep the main subject away from the outer edges; the card frame "
            "crops the image.\n\n"
            "LIGHTING AND PALETTE: suit this scene. Flat, muted and desaturated "
            "overall; lamplight is the only fragile warm note.\n\n"
            "AVOID: " + camp["style_negative"] + ".")


def standalone_prompt(camp, chars, job, brief_text):
    """One complete prompt per card, for a fresh chat each: the owner runs many
    chats in parallel, so nothing may depend on an earlier message. Only the
    investigator on this card is described (none on the others), so a chat
    never mixes in a face that isn't there. No reference images: the owner
    found ChatGPT stalls on them."""
    head = ("Generate exactly ONE image now: an illustration for a custom Arkham "
            "Horror: The Card Game campaign, \"The Still Hour\" (1920s New England "
            "coastal town, cosmic horror, uncanny rather than gory). Don't ask "
            "questions and don't offer variations. Never add text, letters, numbers, "
            "captions, borders or frames to the image.")
    return head + "\n\n" + style_block(camp) + "\n\nCARD BRIEF\n" + brief_text


def scene_text(job):
    text = job["scene"].rstrip(".")
    if any(w in text.lower() for w in LETTERING_WORDS):
        text += " (any writing or numbers only as unreadable marks, never legible)"
    return text + "."


def request_prompt(camp, chars, cards, jobs_by_id, profiles):
    """The owner's batch format: up to PER_REQUEST separate images in one
    message, house style pasted once, one block per image. No reference line —
    ChatGPT stalls on references."""
    k = len(cards)
    out = ["BATCH REQUEST: {k} SEPARATE IMAGES\n\n"
           "Generate exactly ONE independent image for EACH numbered prompt below: "
           "{k} separate images total.\n\n"
           "These are different scenes, not {k} variations of one scene. Do not "
           "combine them into a collage, grid, or contact sheet. Do not ask for "
           "approval between images. Apply the shared house style to every image. "
           "No text, letters, numbers, captions, borders, or frames inside any "
           "image.\n\nSHARED HOUSE STYLE:\n".format(k=k)
           + style_block(camp).replace("HOUSE STYLE: ", "", 1)]
    ratio = {"landscape 3:2": "3:2 (landscape)", "portrait 2:3": "2:3 (portrait)",
             "square 1:1": "1:1 (square)"}
    for i, c in enumerate(cards, 1):
        job, prof = jobs_by_id[c["id"]], profiles[c["art_type"]]
        who = "none"
        if job.get("character") and prof.get("allow_character"):
            who = "{} — {}".format(NAMES.get(job["character"], job["character"]),
                                   chars[job["character"]]["description"])
        out.append("IMAGE {} (save as {:03d})\nAspect ratio: {}\nScene: {}\n"
                   "Framing: {}.\nCharacter: {}".format(
                       i, c["n"], ratio[c["aspect"]], scene_text(job),
                       framing(prof), who))
    return "\n\n".join(out)


def brief(n, job, prof, chars):
    # the number alone maps back to the card; ids stay out of what the owner
    # reads (they name enemies and story beats — AGENTS.md, no spoilers)
    lines = ["#{:03d} · {}".format(n, aspect(prof)),
             "Scene: " + scene_text(job)]
    if job.get("character") and prof.get("allow_character"):
        who = NAMES.get(job["character"], job["character"])
        line = "Character: {} — {}.".format(who, chars[job["character"]]["description"])
        # written description only: ChatGPT stalls on attached reference images
        # (owner, 2026-09-23), so the character bible carries the likeness
        line += " Paint them exactly as described."
        lines.append(line)
    lines.append("Framing: " + framing(prof) + ".")
    lines.append("Broad economical paint, detail only at the focal point, calm simple "
                 "areas elsewhere; no all-over texture, no repeated shapes, no text.")
    return "\n".join(lines)


def build():
    camp = load("campaigns/{}/campaign.json".format(CAMPAIGN))
    chars = load("campaigns/{}/characters.json".format(CAMPAIGN))
    profiles = load("cardforge/profiles/art_profiles.json")
    manifest = load("campaigns/{}/manifest.json".format(CAMPAIGN)) \
        if os.path.exists(os.path.join(ROOT, "campaigns", CAMPAIGN, "manifest.json")) \
        else load("pipeline/art_manifest.json")
    jobs = [j for j in manifest if j.get("scene") and not j.get("no_art")]
    unknown = sorted({j["art_type"] for j in jobs} - set(TYPE_ORDER))
    if unknown:
        raise SystemExit("art types missing from TYPE_ORDER: " + ", ".join(unknown))
    jobs.sort(key=lambda j: (TYPE_ORDER.index(j["art_type"]),
                             0 if j.get("character") else 1))
    cards = []
    for n, job in enumerate(jobs, 1):
        prof = profiles[job["art_type"]]
        text = brief(n, job, prof, chars)
        cards.append({"n": n, "id": job["id"], "art_type": job["art_type"],
                      "aspect": aspect(prof), "character": job.get("character"),
                      "brief": text,
                      "prompt": standalone_prompt(camp, chars, job, text)})
    # batch 1 is the investigator portraits alone: approved before anything else
    inv = [c for c in cards if c["art_type"] == "investigator_portrait"]
    rest = [c for c in cards if c["art_type"] != "investigator_portrait"]
    batches = [inv] + [rest[i:i + BATCH] for i in range(0, len(rest), BATCH)]
    jobs_by_id = {j["id"]: j for j in jobs}
    requests = []
    for bi, b in enumerate(batches, 1):
        for i in range(0, len(b), PER_REQUEST):
            group = b[i:i + PER_REQUEST]
            requests.append({"batch": bi, "cards": [c["n"] for c in group],
                             "prompt": request_prompt(camp, chars, group,
                                                      jobs_by_id, profiles)})
    pack = {"campaign": CAMPAIGN,
            "batches": [[c["n"] for c in b] for b in batches],
            "requests": requests, "cards": cards}
    with open(os.path.join(ROOT, "pipeline", "chatgpt_art_pack.json"), "w",
              encoding="utf-8") as f:
        json.dump(pack, f, indent=1, ensure_ascii=False)
        f.write("\n")
    write_md(pack)
    print("{} cards in {} batches".format(len(cards), len(batches)))
    return pack


def write_md(pack):
    out = ["# The Still Hour — ChatGPT art pack", "",
           "Generated by `pipeline/chatgpt_art_pack.py`; don't edit by hand.", "",
           "**One request per new ChatGPT chat**, up to {} images each, house style "
           "included. Run as many chats at once as you like; no attachments. Save "
           "each image under the number in its `save as` line (e.g. `016.png`)."
           .format(PER_REQUEST), ""]
    for bi in range(1, len(pack["batches"]) + 1):
        out += ["## Batch {}".format(bi), ""]
        for r in (r for r in pack["requests"] if r["batch"] == bi):
            out += ["### #{:03d}–#{:03d}".format(r["cards"][0], r["cards"][-1]), "",
                    "```", r["prompt"], "```", ""]
    with open(os.path.join(ROOT, "docs", "CHATGPT_ART_PACK.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    build()
