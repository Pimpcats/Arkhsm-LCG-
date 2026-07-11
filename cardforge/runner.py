"""The batch runner — queue, variants, retries, ledger, report, contact, index.

Serial by design (one GPU); crash-safe via the ledger; fire-and-forget overnight
per CARDFORGE_BRIEF §9. Outputs land in out/<campaign>/<id>/<seed>.png; the
morning QA loop is: eyeball contact sheets -> bump a bad card's seed in the
manifest -> re-run (only that card regenerates).
"""
import json
import os
import shutil
import time

from .compose import compose, is_text_only, PLACEHOLDER_CHECKPOINT
from .ledger import Ledger
from .resolver import CharacterResolver
from .backends.a1111 import A1111Backend
from .backends.comfy import ComfyBackend

RETRIES = 2
BACKOFF_SECONDS = 5
MIN_FREE_BYTES = 500 * 1024 * 1024   # disk guard: abort cleanly, don't corrupt


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def campaign_dir(name):
    return os.path.join(repo_root(), "campaigns", name)


def load_campaign(name):
    path = os.path.join(campaign_dir(name), "campaign.json")
    camp = json.load(open(path, encoding="utf-8"))
    camp["name"] = name
    return camp


def load_profiles():
    return json.load(open(os.path.join(repo_root(), "cardforge", "profiles",
                                       "art_profiles.json"), encoding="utf-8"))


def load_prompt_overrides(name):
    """Owner-authored per-card prompt overrides (Studio's card editor):
    campaigns/<name>/prompt_overrides.json  {card_id: {positive, negative}}.
    A non-empty field replaces the composed prompt verbatim."""
    path = os.path.join(campaign_dir(name), "prompt_overrides.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return {}


def save_prompt_override(name, card_id, positive, negative):
    path = os.path.join(campaign_dir(name), "prompt_overrides.json")
    ov = load_prompt_overrides(name)
    entry = {}
    if (positive or "").strip():
        entry["positive"] = positive.strip()
    if (negative or "").strip():
        entry["negative"] = negative.strip()
    if entry:
        ov[card_id] = entry
    else:
        ov.pop(card_id, None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ov, f, indent=2, ensure_ascii=False)
    return entry or None


def load_manifest(name, starter=False):
    fname = "manifest_starter.json" if starter else "manifest.json"
    path = os.path.join(campaign_dir(name), fname)
    if not os.path.exists(path) and starter:
        path = os.path.join(repo_root(), "pipeline", "art_manifest_starter.json")
    return [j for j in json.load(open(path, encoding="utf-8")) if not j.get("_comment")]


def make_backend(camp, dry_run=False):
    kind = camp.get("backend", "a1111")
    out_dir = os.path.join(repo_root(), camp.get("output_dir", "out/" + camp["name"]))
    payload_dir = os.path.join(out_dir, "payloads")
    if kind == "comfy":
        return ComfyBackend(camp.get("base_url") or ComfyBackend.DEFAULT_URL,
                            workflows_dir=os.path.join(repo_root(), "cardforge", "workflows"),
                            dry_run=dry_run, payload_dir=payload_dir)
    return A1111Backend(camp.get("base_url") or A1111Backend.DEFAULT_URL,
                        dry_run=dry_run, payload_dir=payload_dir)


def out_dir_for(camp):
    return os.path.join(repo_root(), camp.get("output_dir", "out/" + camp["name"]))


# --------------------------------------------------------------------- run --

def run_generate(campaign_name, only=None, art_type=None, variants_override=None,
                 dry_run=False, starter=False):
    camp = load_campaign(campaign_name)
    profiles = load_profiles()
    resolver = CharacterResolver(os.path.join(campaign_dir(campaign_name), "characters.json"))
    manifest = load_manifest(campaign_name, starter=starter)
    prompt_overrides = load_prompt_overrides(campaign_name)
    backend = make_backend(camp, dry_run=dry_run)
    out_dir = out_dir_for(camp)
    ledger = Ledger(os.path.join(repo_root(), "state", campaign_name + ".ledger.json"))

    report = {"campaign": campaign_name, "backend": backend.name, "dry_run": dry_run,
              "generated": [], "skipped_ledger": [], "skipped_text_only": [],
              "failed": [], "warnings": []}

    if not dry_run and camp.get("checkpoint", PLACEHOLDER_CHECKPOINT) == PLACEHOLDER_CHECKPOINT:
        report["warnings"].append("campaign checkpoint is still SET_ME — fill campaign.json")

    for job in manifest:
        if only and job["id"] not in only:
            continue
        if art_type and job.get("art_type") != art_type:
            continue
        if is_text_only(job):
            report["skipped_text_only"].append(job["id"])
            print("SKIP text-only  " + job["id"])
            continue

        character = None
        if job.get("character"):
            character = resolver.resolve(job["character"])
            if character.get("refs") and not character.get("lora") and backend.name == "a1111":
                report["warnings"].append(
                    job["id"] + ": character has refs but no LoRA; A1111 v1 renders "
                    "without consistency (use the Comfy/IPAdapter path or train the LoRA)")

        positive, negative, params = compose(job, camp, profiles, character)
        ov = prompt_overrides.get(job["id"])
        if ov:
            positive = ov.get("positive") or positive
            negative = ov.get("negative") or negative
            print("PROMPT OVERRIDE  " + job["id"])
        n_variants = variants_override or params["variants"]
        for k in range(n_variants):
            seed = job.get("seed", 1) + 1000 * k
            if ledger.is_done(job["id"], seed, dry_run):
                report["skipped_ledger"].append(Ledger.key(job["id"], seed))
                continue
            if shutil.disk_usage(out_dir if os.path.exists(out_dir) else repo_root()).free < MIN_FREE_BYTES:
                report["failed"].append({"id": job["id"], "seed": seed, "error": "disk guard"})
                print("ABORT: below disk-space guard; stopping cleanly (resume later)")
                _write_report(out_dir, report)
                return report
            p = dict(params, seed=seed)
            key = "{}_{}".format(job["id"], seed)
            err = None
            for attempt in range(RETRIES + 1):
                try:
                    images = backend.generate(positive, negative, p, key)
                    dest_dir = os.path.join(out_dir, job["id"])
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = os.path.join(dest_dir, "{}.png".format(seed))
                    with open(dest, "wb") as f:
                        f.write(images[0])
                    ledger.mark(job["id"], seed, dry_run)
                    report["generated"].append({"id": job["id"], "seed": seed,
                                                "path": os.path.relpath(dest, repo_root()),
                                                "art_type": job["art_type"]})
                    print("OK  {:28} seed={}".format(job["id"], seed))
                    err = None
                    break
                except Exception as e:  # noqa: BLE001 - retry then report
                    err = str(e)
                    if attempt < RETRIES:
                        time.sleep(BACKOFF_SECONDS * (attempt + 1))
            if err:
                report["failed"].append({"id": job["id"], "seed": seed, "error": err})
                print("FAIL {:27} seed={}  {}".format(job["id"], seed, err))

    _write_report(out_dir, report)
    print("\ngenerated {} | ledger-skip {} | text-only {} | failed {}".format(
        len(report["generated"]), len(report["skipped_ledger"]),
        len(report["skipped_text_only"]), len(report["failed"])))
    return report


def _write_report(out_dir, report):
    # atomic: the Studio's status endpoint polls this file while we run
    os.makedirs(out_dir, exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=out_dir)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    os.replace(tmp, os.path.join(out_dir, "report.json"))


# ------------------------------------------------------------------- seeds --

def run_seeds(campaign_name, variants=4, dry_run=False):
    """Step 0: canonical portrait candidates per character, for owner curation."""
    camp = load_campaign(campaign_name)
    profiles = load_profiles()
    resolver = CharacterResolver(os.path.join(campaign_dir(campaign_name), "characters.json"))
    backend = make_backend(camp, dry_run=dry_run)
    out_base = os.path.join(out_dir_for(camp), "seeds")
    made = 0
    for name in resolver.names():
        char = resolver.resolve(name)
        desc = char.get("description")
        if not desc:
            print("SKIP {} (no description in characters.json)".format(name))
            continue
        job = {"id": "seed-" + name, "art_type": "investigator_portrait",
               "scene": "canonical reference portrait, " + desc, "seed": 7000}
        # seeds render the RAW look — no LoRA token (the LoRA doesn't exist yet)
        positive, negative, params = compose(job, camp, profiles, None)
        for k in range(variants):
            p = dict(params, seed=7000 + 97 * k)
            images = backend.generate(positive, negative, p, "seed_{}_{}".format(name, p["seed"]))
            dest_dir = os.path.join(out_base, name)
            os.makedirs(dest_dir, exist_ok=True)
            with open(os.path.join(dest_dir, "{}.png".format(p["seed"])), "wb") as f:
                f.write(images[0])
            made += 1
        print("seeded {} x{}".format(name, variants))
    print("{} seed candidate(s) -> {}".format(made, os.path.relpath(out_base, repo_root())))


# ---------------------------------------------------------- contact + index --

def run_contact(campaign_name, thumb=256, cols=6):
    from PIL import Image
    camp = load_campaign(campaign_name)
    out_dir = out_dir_for(camp)
    report_path = os.path.join(out_dir, "report.json")
    if not os.path.exists(report_path):
        raise SystemExit("no report.json — run generate first")
    report = json.load(open(report_path, encoding="utf-8"))
    by_type = {}
    for g in report["generated"]:
        by_type.setdefault(g["art_type"], []).append(g)
    for art_type, items in sorted(by_type.items()):
        rows = (len(items) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb, rows * thumb), (16, 16, 22))
        for i, g in enumerate(items):
            img = Image.open(os.path.join(repo_root(), g["path"]))
            img.thumbnail((thumb, thumb))
            sheet.paste(img, ((i % cols) * thumb, (i // cols) * thumb))
        dest = os.path.join(out_dir, "contact_{}.png".format(art_type))
        sheet.save(dest)
        print("contact sheet: {} ({} face(s))".format(os.path.relpath(dest, repo_root()), len(items)))


def run_index(campaign_name):
    """id -> chosen illustration path. Default = lowest seed; a 'chosen.txt' file
    in a card's output dir (containing a filename) overrides — that's curation."""
    camp = load_campaign(campaign_name)
    out_dir = out_dir_for(camp)
    index = {}
    for card_id in sorted(os.listdir(out_dir)):
        card_dir = os.path.join(out_dir, card_id)
        if not os.path.isdir(card_dir) or card_id in ("payloads", "seeds"):
            continue
        pngs = sorted(p for p in os.listdir(card_dir) if p.endswith(".png"))
        if not pngs:
            continue
        chosen_marker = os.path.join(card_dir, "chosen.txt")
        chosen = open(chosen_marker, encoding="utf-8").read().strip() if os.path.exists(chosen_marker) else pngs[0]
        index[card_id] = os.path.relpath(os.path.join(card_dir, chosen), repo_root())
    dest = os.path.join(out_dir, "index.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print("index.json: {} card(s) -> {}".format(len(index), os.path.relpath(dest, repo_root())))
    return index
