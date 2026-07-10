#!/usr/bin/env python3
"""CardForge CLI — reusable overnight card-art batch tool.

    python3 -m cardforge.cardforge generate --campaign still_hour
    python3 -m cardforge.cardforge generate --campaign still_hour --only sthr-elias
    python3 -m cardforge.cardforge generate --campaign still_hour --starter --dry-run
    python3 -m cardforge.cardforge seeds    --campaign still_hour --variants 4
    python3 -m cardforge.cardforge contact  --campaign still_hour
    python3 -m cardforge.cardforge index    --campaign still_hour
    python3 -m cardforge.cardforge sync     --campaign still_hour
    python3 -m cardforge.cardforge profiles list
    python3 -m cardforge.cardforge backends check --campaign still_hour
    python3 -m cardforge.cardforge characters list --campaign still_hour

A campaign is a folder: campaigns/<name>/{campaign.json, manifest.json,
characters.json}. Nothing in the engine is Still-Hour-specific — any Arkham mod
plugs in by dropping a folder.
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardforge import runner  # noqa: E402
from cardforge.compose import PLACEHOLDER_CHECKPOINT  # noqa: E402


def cmd_generate(a):
    runner.run_generate(a.campaign, only=set(a.only) if a.only else None,
                        art_type=a.art_type, variants_override=a.variants,
                        dry_run=a.dry_run, starter=a.starter)


def cmd_seeds(a):
    runner.run_seeds(a.campaign, variants=a.variants or 4, dry_run=a.dry_run)


def cmd_contact(a):
    runner.run_contact(a.campaign)


def cmd_index(a):
    runner.run_index(a.campaign)


def cmd_sync(a):
    """Refresh the campaign manifest from the pipeline generator's output."""
    src = os.path.join(runner.repo_root(), "pipeline", "art_manifest.json")
    dst = os.path.join(runner.campaign_dir(a.campaign), "manifest.json")
    shutil.copyfile(src, dst)
    src_s = os.path.join(runner.repo_root(), "pipeline", "art_manifest_starter.json")
    if os.path.exists(src_s):
        shutil.copyfile(src_s, os.path.join(runner.campaign_dir(a.campaign),
                                            "manifest_starter.json"))
    print("synced manifest(s) from pipeline/ into campaigns/{}/".format(a.campaign))


def cmd_profiles(a):
    profiles = runner.load_profiles()
    for name, p in sorted(profiles.items()):
        if name.startswith("_"):
            continue
        print("{:24} {}x{}  steps {}  cfg {}  variants {}  character={}".format(
            name, p["width"], p["height"], p["steps"], p["cfg"],
            p.get("variants", 1), "yes" if p.get("allow_character") else "no"))


def cmd_backends(a):
    camp = runner.load_campaign(a.campaign)
    backend = runner.make_backend(camp, dry_run=False)
    ok, msg = backend.check()
    print("[{}] {}: {}".format("OK" if ok else "FAIL", backend.name, msg))
    unset = []
    if camp.get("checkpoint", PLACEHOLDER_CHECKPOINT) == PLACEHOLDER_CHECKPOINT:
        unset.append("campaign.json checkpoint")
    for name, p in runner.load_profiles().items():
        if not name.startswith("_") and p.get("checkpoint") == PLACEHOLDER_CHECKPOINT:
            unset.append("profile '{}'".format(name))
    if unset:
        print("SET_ME checkpoints (campaign checkpoint fills these at compose time):")
        for u in unset:
            print("  - " + u)


def cmd_characters(a):
    from cardforge.resolver import CharacterResolver
    r = CharacterResolver(os.path.join(runner.campaign_dir(a.campaign), "characters.json"))
    for name in r.names():
        c = r.resolve(name)
        print("{:8} lora={}  weight={}  refs={}  trigger='{}'".format(
            name, c.get("lora") or "-", c.get("weight", 0.8),
            len(c.get("refs", [])), c.get("trigger", "")[:50]))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cardforge", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_campaign(p):
        p.add_argument("--campaign", required=True)

    g = sub.add_parser("generate", help="run the batch (respects the resume ledger)")
    add_campaign(g)
    g.add_argument("--only", nargs="*", help="restrict to these card ids")
    g.add_argument("--art-type", help="restrict to one art type")
    g.add_argument("--variants", type=int, help="override per-profile variant count")
    g.add_argument("--dry-run", action="store_true",
                   help="write exact HTTP payloads + stub PNGs; no backend calls")
    g.add_argument("--starter", action="store_true", help="use the starter manifest subset")
    g.add_argument("--resume", action="store_true",
                   help="(alias) resuming is the default — the ledger always skips done work")
    g.set_defaults(fn=cmd_generate)

    s = sub.add_parser("seeds", help="generate canonical portrait candidates (Step 0)")
    add_campaign(s)
    s.add_argument("--variants", type=int, default=4)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_seeds)

    for name, fn, hlp in (("contact", cmd_contact, "contact sheet per art type"),
                          ("index", cmd_index, "emit index.json (framing stage input)"),
                          ("sync", cmd_sync, "refresh manifest from pipeline/")):
        p = sub.add_parser(name, help=hlp)
        add_campaign(p)
        p.set_defaults(fn=fn)

    p = sub.add_parser("profiles", help="list art-type profiles")
    p.add_argument("action", choices=["list"])
    p.set_defaults(fn=cmd_profiles)

    b = sub.add_parser("backends", help="check backend reachability + config")
    b.add_argument("action", choices=["check"])
    add_campaign(b)
    b.set_defaults(fn=cmd_backends)

    c = sub.add_parser("characters", help="list a campaign's characters")
    c.add_argument("action", choices=["list"])
    add_campaign(c)
    c.set_defaults(fn=cmd_characters)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
