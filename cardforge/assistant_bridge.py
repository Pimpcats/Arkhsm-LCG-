"""Repository handoff for campaign authors and chat-generated artwork.

No server, credentials, or remote execution. Run from the CardForge checkout.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("Invalid campaign/card identifier: " + value)
    return value


def inside(root, path):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path must stay inside the repository: " + str(path))
    return path


def context(campaign, root=ROOT):
    folder = inside(root, root / "campaigns" / identifier(campaign))
    if not (folder / "campaign.json").exists():
        raise ValueError("Unknown campaign: " + campaign)
    config = read(folder / "campaign.json", {})
    prefix = "stillhour" if campaign == "still_hour" else campaign
    cards = {}
    for suffix in ("cards", "encounter", "scenario", "imported", "handmade"):
        for card in read(root / "pipeline" / (prefix + "_" + suffix + "_spec.json"), []):
            cards[card["id"]] = card
    overrides = read(folder / "card_overrides.json", {})
    for cid in cards:
        cards[cid] = {**cards[cid], **overrides.get(cid, {})}
    profiles = read(root / "cardforge/profiles/art_profiles.json", {})
    characters = read(folder / "characters.json", {})
    prompts = read(folder / "prompt_overrides.json", {})
    registry = read(folder / "assistant/art.json", {})
    jobs = []
    for job in read(folder / "manifest.json", []):
        if job.get("_comment") or job.get("no_art") or not job.get("scene"):
            continue
        cid = identifier(job["id"])
        profile = profiles.get(job.get("art_type"), {})
        character = characters.get(job.get("character"), {})
        positive = prompts.get(cid, {}).get("positive") or ", ".join(filter(None, [
            job["scene"], character.get("description"), profile.get("type_positive"),
            config.get("style_positive")]))
        negative = prompts.get(cid, {}).get("negative") or ", ".join(filter(None, [
            config.get("style_negative"), profile.get("type_negative")]))
        art = registry.get(cid, {})
        available = bool(art.get("path") and inside(root, root / art["path"]).is_file())
        jobs.append({"id": cid, "prompt": positive, "avoid": negative,
                     "character": character, "card": cards.get(cid, {}),
                     "width": profile.get("width"), "height": profile.get("height"),
                     "art": art, "status": "registered" if available else "pending"})
    illustrated = {j["id"] for j in jobs}
    return {"schema_version": 1, "campaign": campaign,
            "style": {k: config.get(k, "") for k in ("style_positive", "style_negative")},
            "cards": list(cards.values()), "art_jobs": jobs,
            "cards_without_art_jobs": sorted(set(cards) - illustrated),
            "scenario_manifest": read(folder / "scenario_manifest.json", {}),
            "assignments": read(folder / "scenario_assignments.json", {}),
            "production": read(folder / "assistant/production.json", {}),
            "note": "Registered art is not proof of visual approval or playability. Cards without jobs may be text-only or need an art brief."}


def register_art(campaign, card, source, root=ROOT):
    from PIL import Image
    card = identifier(card)
    ctx = context(campaign, root)
    if card not in {j["id"] for j in ctx["art_jobs"]}:
        raise ValueError("Card has no illustration job: " + card)
    # Decode before writing anything; normalize all inputs to real PNG.
    with Image.open(source) as image:
        image.load()
        normalized = image.convert("RGB")
    folder = root / "campaigns" / campaign / "assistant"
    import io
    buffer = io.BytesIO()
    normalized.save(buffer, format="PNG")
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    dest = inside(root, folder / "art" / (card + "-" + digest[:16] + ".png"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    registry = read(folder / "art.json", {})
    registry[card] = {"path": dest.relative_to(root).as_posix(), "sha256": digest,
                      "width": normalized.width, "height": normalized.height}
    write(folder / "art.json", registry)
    return registry[card]


def sync_art(campaign, root=ROOT):
    import shutil
    folder = inside(root, root / "campaigns" / identifier(campaign))
    context(campaign, root)  # validate campaign before writing
    config = read(folder / "campaign.json", {})
    output = inside(root, root / config.get("output_dir", "out/" + campaign))
    registry = read(folder / "assistant/art.json", {})
    pending = []
    for cid, entry in registry.items():
        identifier(cid)
        source = inside(root, root / entry["path"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Artwork checksum mismatch: " + cid)
        target = inside(root, output / cid / source.name)
        pending.append((cid, source, target))
    index = read(output / "index.json", {})
    for cid, source, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        (target.parent / "chosen.txt").write_text(target.name, encoding="utf-8")
        index[cid] = target.relative_to(root).as_posix()
    write(output / "index.json", index)
    return {"synced": [item[0] for item in pending]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default="still_hour")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Write the current campaign and art queue as JSON")
    export.add_argument("--output", type=Path, required=True)
    art = commands.add_parser("register-art", help="Save generated art in the campaign for Git sync")
    art.add_argument("--card", required=True)
    art.add_argument("--image", type=Path, required=True)
    commands.add_parser("sync-art", help="Select repository artwork in CardForge's existing art index")
    args = parser.parse_args()
    if args.command == "export":
        result = context(args.campaign)
        write(args.output, result)
        print(json.dumps({"cards": len(result["cards"]), "art_jobs": len(result["art_jobs"]),
                          "pending": sum(j["status"] == "pending" for j in result["art_jobs"])}))
    elif args.command == "register-art":
        print(json.dumps(register_art(args.campaign, args.card, args.image)))
    else:
        print(json.dumps(sync_art(args.campaign)))


if __name__ == "__main__":
    main()
