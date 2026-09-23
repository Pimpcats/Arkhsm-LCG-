"""ChatGPT art pack: every illustrated card as a numbered, paste-ready brief.

The owner generates art in ChatGPT on their own subscription (no API credits),
so the prompt CardForge would have sent is rewritten for a chat. Every card's "prompt" is complete on its own (house style + brief), so
the owner can run one fresh chat per card, many at once. Numbers are stable (manifest order within a fixed type order), so an
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
    never mixes in a face that isn't there."""
    who = job.get("character") if job["art_type"] in CHARACTER_TYPES else None
    head = ("Generate exactly ONE image now: an illustration for a custom Arkham "
            "Horror: The Card Game campaign, \"The Still Hour\" (1920s New England "
            "coastal town, cosmic horror, uncanny rather than gory). Don't ask "
            "questions and don't offer variations. Never add text, letters, numbers, "
            "captions, borders or frames to the image.")
    if who and job["art_type"] != "investigator_portrait":
        head += (" I have attached the approved portrait of {}: match that face, "
                 "age, hair and costume exactly.".format(NAMES.get(who, who)))
    return head + "\n\n" + style_block(camp) + "\n\nCARD BRIEF\n" + brief_text


def brief(n, job, prof, chars):
    # the number alone maps back to the card; ids stay out of what the owner
    # reads (they name enemies and story beats — AGENTS.md, no spoilers)
    lines = ["#{:03d} · {}".format(n, aspect(prof)),
             "Scene: " + job["scene"].rstrip(".") + "."]
    if job.get("character") and prof.get("allow_character"):
        who = NAMES.get(job["character"], job["character"])
        line = "Character: {} — {}.".format(who, chars[job["character"]]["description"])
        if job["art_type"] != "investigator_portrait":
            # the portrait IS the reference; every later card matches it
            line += " Match the attached portrait exactly."
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
    pack = {"campaign": CAMPAIGN,
            "batches": [[c["n"] for c in b] for b in batches], "cards": cards}
    with open(os.path.join(ROOT, "pipeline", "chatgpt_art_pack.json"), "w",
              encoding="utf-8") as f:
        json.dump(pack, f, indent=1, ensure_ascii=False)
        f.write("\n")
    write_md(pack)
    print("{} cards in {} batches".format(len(cards), len(batches)))
    return pack


def write_md(pack):
    by_n = {c["n"]: c for c in pack["cards"]}
    out = ["# The Still Hour — ChatGPT art pack", "",
           "Generated by `pipeline/chatgpt_art_pack.py`; don't edit by hand.", "",
           "**Every prompt is complete on its own:** open a new ChatGPT chat per "
           "card, paste its prompt, and run as many chats at once as you like. "
           "Prompts marked \"attach portrait\" need that investigator's approved "
           "portrait attached. Name each image by its number (e.g. `007.png`).", ""]
    for i, batch in enumerate(pack["batches"], 1):
        title = "investigator portraits (approve these first)" if i == 1 else \
            "#{:03d}–#{:03d}".format(batch[0], batch[-1])
        out += ["## Batch {} — {}".format(i, title), ""]
        for n in batch:
            c = by_n[n]
            tag = " — attach portrait" if c["character"] and c["art_type"] in CHARACTER_TYPES \
                and c["art_type"] != "investigator_portrait" else ""
            out += ["### #{:03d}{}".format(n, tag), "", "```", c["prompt"], "```", ""]
    with open(os.path.join(ROOT, "docs", "CHATGPT_ART_PACK.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    build()
