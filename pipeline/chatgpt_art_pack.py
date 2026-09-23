"""ChatGPT art pack: every illustrated card as a numbered, paste-ready brief.

The owner generates art in ChatGPT on their own subscription (no API credits),
so the prompt CardForge would have sent is rewritten for a chat: one SETUP
message carrying the house style and character bible, then one short brief per
card. Numbers are stable (manifest order within a fixed type order), so an
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


def setup_message(camp, chars):
    bible = "\n".join("- {}: {}".format(NAMES.get(k, k), v["description"])
                      for k, v in chars.items())
    return (
        "You are illustrating a custom Arkham Horror: The Card Game campaign, "
        "\"The Still Hour\" (1920s New England coastal town, cosmic horror, "
        "uncanny rather than gory). I will send card briefs one at a time. Each "
        "starts with a number like #007. For each brief, generate exactly ONE "
        "image in the stated shape. Don't ask questions, don't offer variations, "
        "and never add text, letters, numbers, captions, borders or frames to the image.\n\n"
        "HOUSE STYLE (every image): " + camp["style_positive"] + ".\n\n"
        + "".join("{}: {}\n\n".format(k, v)
                  for k, v in camp.get("style_guidance", {}).items()) +
        "CROP: keep the main subject away from the outer edges; the card frame "
        "crops the image.\n\n"
        "LIGHTING AND PALETTE: vary them from card to card to suit each scene. Flat, "
        "muted and desaturated overall; lamplight is the only fragile warm note. "
        "Don't reuse the same lighting setup every time.\n\n"
        "AVOID: " + camp["style_negative"] + ".\n\n"
        "THE INVESTIGATORS (keep their looks identical whenever they appear; if I "
        "attach a portrait, match that face exactly):\n" + bible + "\n\n"
        "Reply to this message with only \"Ready.\"")


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
            line += " Match the attached approved portrait of {} exactly.".format(who)
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
        cards.append({"n": n, "id": job["id"], "art_type": job["art_type"],
                      "aspect": aspect(prof), "character": job.get("character"),
                      "brief": brief(n, job, prof, chars)})
    # batch 1 is the investigator portraits alone: approved before anything else
    inv = [c for c in cards if c["art_type"] == "investigator_portrait"]
    rest = [c for c in cards if c["art_type"] != "investigator_portrait"]
    batches = [inv] + [rest[i:i + BATCH] for i in range(0, len(rest), BATCH)]
    pack = {"campaign": CAMPAIGN, "setup": setup_message(camp, chars),
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
           "**How to run a batch:** open a NEW ChatGPT chat, paste SETUP, wait for "
           "\"Ready.\", then paste each brief of the batch one at a time. For cards "
           "with a Character line, attach that investigator's approved portrait "
           "with the brief. Send the images back in brief order.", "",
           "## SETUP (paste first in every new chat)", "", "```", pack["setup"], "```", ""]
    for i, batch in enumerate(pack["batches"], 1):
        title = "investigator portraits (approve these first)" if i == 1 else \
            "#{:03d}–#{:03d}".format(batch[0], batch[-1])
        out += ["## Batch {} — {}".format(i, title), ""]
        for n in batch:
            out += ["```", by_n[n]["brief"], "```", ""]
    with open(os.path.join(ROOT, "docs", "CHATGPT_ART_PACK.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    build()
