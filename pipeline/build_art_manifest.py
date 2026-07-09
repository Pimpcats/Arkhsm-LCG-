#!/usr/bin/env python3
"""
build_art_manifest.py — emits the machine-readable art job list the overnight
batch runner consumes (one entry per card face). Mirrors build_cards.py.
Run: python3 build_art_manifest.py  ->  art_manifest_starter.json
Each entry = {id, card_type, frame, aspect, gen_size, prompt, negative, reference, seed}.
The pipeline: manifest -> Krea batch (illustration) -> Strange Eons (frame) -> sheet -> CDN -> URL rewrite.
"""
import json

# ---- HOUSE STYLE (prepended to every illustration prompt) ----
STYLE = ("cosmic horror illustration, painterly, muted desaturated palette, "
         "1920s New England coastal town, eerie stillness, starless folding sky, "
         "cinematic soft lighting, oil-paint texture, subtle grain, "
         "Arkham Horror card art style, atmospheric, unsettling")
NEG = ("text, watermark, signature, frame, border, ui, logo, deformed hands, "
       "extra fingers, modern clothing, bright saturated colors, cartoon, 3d render, "
       "cheerful, sunny, lens flare, cluttered")

# ---- CHARACTER BIBLE (keeps each investigator consistent across their cards) ----
# For production: generate one canonical portrait each, then train a per-investigator
# LoRA OR pass the portrait as a weighted reference image on every one of their cards.
CHARS = {
 "elias": "Elias Warde, weathered lighthouse keeper in his late fifties, grey-streaked "
          "beard, deep-set tired resolute eyes, heavy dark oilcloth coat, holding a lantern",
 "ayako": "Dr. Ayako Soma, Japanese woman in her thirties, sharp intelligent gaze, wire "
          "spectacles, ink-stained fingers, dark travelling coat, notebook in hand",
 "cass":  "Cass Lindqvist, sharp-featured woman in her late twenties, short slicked hair, "
          "worn pinstripe waistcoat, a deck of cards, wary confident half-smile",
 "sera":  "Seraphine Vale, pale spiritualist woman in her forties, dark hair loose, haunted "
          "distant eyes, layered dark shawls, faint occult jewelry",
 "birdie":"Birdie Okonkwo, young Black woman in her early twenties, patched practical coat, "
          "alert scrappy expression, a small brass compass on a cord",
}

# frame -> (aspect, generation size) for the ILLUSTRATION area (Strange Eons crops into the frame)
FRAME = {
 "investigator_front":("landscape",(1024,768)), "investigator_back":("landscape",(1024,768)),
 "asset":("portrait",(768,1024)), "event":("portrait",(768,1024)), "skill":("portrait",(768,1024)),
 "treachery":("portrait",(768,1024)), "enemy":("portrait",(768,1024)),
 "location_front":("portrait",(768,1024)), "location_back":("portrait",(768,1024)),
 "agenda":("landscape",(1024,768)), "act":("landscape",(1024,768)),
 "minicard":("portrait",(512,768)), "story":("landscape",(1024,768)),
}

def entry(id, frame, scene, char=None, seed=1, no_art=False):
    aspect, size = FRAME[frame]
    if no_art:
        prompt = None; neg = None; ref = None
    else:
        who = CHARS[char]+", " if char else ""
        prompt = f"{who}{scene}. {STYLE}"
        neg = NEG
        ref = (f"ref:{char}_canonical.png (weight 0.7)  OR  lora:{char}") if char else "moodboard:still_hour_style"
    return {"id":id,"card_type":frame.split("_")[0].capitalize(),"frame":frame,
            "aspect":aspect,"gen_size":list(size),"prompt":prompt,"negative":neg,
            "reference":ref,"seed":seed}

# ---- STARTER MANIFEST: Elias slice + one of each encounter frame type ----
MANIFEST = [
 entry("sthr-elias","investigator_front",
       "half-length portrait, standing before a dark unlit lighthouse at night, salt wind", char="elias", seed=101),
 entry("sthr-elias-back","investigator_back","", no_art=True),          # deckbuilding back = text only
 entry("sthr-lamp","asset",
       "an old brass storm-lantern glowing faint amber in fog, close-up still life", seed=111),
 entry("sthr-donebefore","skill",
       "a man's hands gripping a rail, knuckles white, ghostly repeated afterimages of the same gesture", seed=112),
 entry("sthr-eighthgrave","treachery",
       "eight identical fresh graves in a row under a folding starless sky, one open and empty", seed=113),
 entry("loc-lantern-room","location_front",
       "the top room of a lighthouse, cold dark lamp mechanism, cracked glass, sea beyond", seed=201),
 entry("echo-congregation","enemy",
       "a silent crowd of townsfolk frozen mid-gesture, faces turned slightly wrong, grey light", seed=301),
 entry("treach-lost-hour","treachery",
       "a pocket watch with the hands blurring forward, clock face dissolving into fog", seed=401),
 entry("hour-iii-toll","agenda",
       "a drowned church belfry, a great bronze bell mid-swing, water rising in the nave", seed=501),
 entry("enemy-appointed","enemy",
       "a tall wrong silhouette at the far end of an empty street, too many angles, not quite arriving, "
       "featureless, dread, negative space", seed=666),
]

json.dump(MANIFEST, open("art_manifest_starter.json","w"), indent=2)

# validate
d = json.load(open("art_manifest_starter.json"))
art = [e for e in d if e["prompt"]]
print(f"{len(d)} card faces ({len(art)} need illustration, {len(d)-len(art)} text-only)")
for e in d:
    tag = "TEXT-ONLY" if not e["prompt"] else f"{e['aspect']:9} {e['gen_size']}"
    print(f"  {e['id']:22} {e['frame']:19} {tag}")
print("\nWrote art_manifest_starter.json")
