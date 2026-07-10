"""Prompt composition — the one place a final prompt is assembled.

Order (validated by cardforge_stub.py, which this lifts):
    subject -> art-type framing -> house style
    positive = "<lora:..:w> {trigger}, {scene}, {profile.type_positive}, {campaign.style_positive}"
    negative = "{campaign.style_negative}, {profile.type_negative}"

Overrides (any profile field): profile < campaign.overrides[art_type] < job.overrides.
A campaign-level `checkpoint` replaces any profile checkpoint still set to the
"SET_ME.safetensors" placeholder.
"""

PLACEHOLDER_CHECKPOINT = "SET_ME.safetensors"


def is_text_only(job):
    """Text-only faces (investigator backs etc.) are framed, never illustrated."""
    return bool(job.get("no_art")) or not job.get("scene")


def effective_profile(job, campaign, profiles):
    prof = dict(profiles[job["art_type"]])
    prof.update(campaign.get("overrides", {}).get(job["art_type"], {}))
    prof.update(job.get("overrides", {}))
    if prof.get("checkpoint", PLACEHOLDER_CHECKPOINT) == PLACEHOLDER_CHECKPOINT \
            and campaign.get("checkpoint"):
        prof["checkpoint"] = campaign["checkpoint"]
    return prof


def compose(job, campaign, profiles, character=None):
    """Return (positive, negative, params) for one manifest job.

    `character` is the resolver output ({lora, weight, trigger, refs}) or None;
    it is only applied when the art-type profile allows characters.
    """
    prof = effective_profile(job, campaign, profiles)
    char = character if prof.get("allow_character") else None

    lora_tok = ""
    if char:
        if char.get("lora"):
            lora_tok = "<lora:{}:{}> {}, ".format(
                char["lora"], char.get("weight", 0.8), char.get("trigger", ""))
        elif char.get("trigger"):
            # no LoRA yet: trigger words still anchor the look; refs are the
            # backend's problem (Comfy IPAdapter) or skipped (A1111 v1).
            lora_tok = "{}, ".format(char["trigger"])

    positive = "{}{}, {}, {}".format(
        lora_tok, job["scene"], prof["type_positive"], campaign["style_positive"])
    negative = "{}, {}".format(campaign["style_negative"], prof["type_negative"])
    params = {
        "width": prof["width"], "height": prof["height"], "steps": prof["steps"],
        "cfg": prof["cfg"], "sampler": prof["sampler"], "seed": job.get("seed", 1),
        "checkpoint": prof.get("checkpoint", PLACEHOLDER_CHECKPOINT),
        "variants": prof.get("variants", 1),
        "comfy_workflow": prof.get("comfy_workflow"),
        "refs": (char or {}).get("refs", []),
        "hires": prof.get("hires"),
    }
    return positive, negative, params
