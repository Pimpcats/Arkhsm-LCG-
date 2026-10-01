"""Which campaign the build is for, and every name the build derives from it.

Each campaign has campaigns/<id>/build.json (see campaigns/_template/build.json
and docs/NEW_CAMPAIGN.md). Choose the campaign with the CAMPAIGN environment
variable or a --campaign <id> argument; without either, the build is for
The Still Hour (the reference campaign), so existing commands are unchanged.

    from campaign_config import CFG
    CFG.name            # "The Still Hour"
    CFG.path("guide_md")  # absolute path of a repo-relative entry
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT = "still_hour"


def campaign_id(argv=None):
    """--campaign <id> / --campaign=<id> on the command line, else $CAMPAIGN,
    else the reference campaign."""
    argv = sys.argv if argv is None else argv
    for i, a in enumerate(argv):
        if a == "--campaign" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--campaign="):
            return a.split("=", 1)[1]
    return os.environ.get("CAMPAIGN") or DEFAULT


class Config(dict):
    """build.json with derived defaults; keys read as attributes."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def path(self, key):
        """Absolute path for a repo-relative entry (or list of entries)."""
        v = self[key]
        if isinstance(v, list):
            return [os.path.join(ROOT, x) for x in v]
        return os.path.join(ROOT, v) if v else v

    def dist(self, name):
        return os.path.join(ROOT, "dist", name)


def load(cid=None):
    cid = cid or campaign_id()
    path = os.path.join(ROOT, "campaigns", cid, "build.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    c = Config(id=cid)
    c.update(data)
    name = c.setdefault("name", cid.replace("_", " ").title())
    slug = c.setdefault("slug", name.lower().replace(" ", "_").replace("'", ""))
    prefix = c.setdefault("prefix", cid[:4])
    up = prefix.upper()
    c.setdefault("upper_name", name.upper())
    c.setdefault("box_name", name)                    # the compiled campaign box's nickname
    c.setdefault("tag", "".join(w.capitalize() for w in cid.split("_")))
    c.setdefault("lua_dir", c["tag"])
    c.setdefault("box_id", "CB-" + up)
    c.setdefault("log_id", up + "-LOG")
    c.setdefault("guide_id", up + "-CG")
    c.setdefault("box_texture_id", prefix + "-box")
    c.setdefault("control_guid", prefix + "-control")
    c.setdefault("download_box_guid", prefix + "-download-box")
    c.setdefault("log_pages", [prefix + "-log-page%d" % i for i in (1, 2, 3)])
    c.setdefault("specs", ["campaigns/%s/specs/cards_spec.json" % cid,
                           "campaigns/%s/specs/encounter_spec.json" % cid])
    c.setdefault("cards_spec", c["specs"][0])
    c.setdefault("encounter_spec", c["specs"][1] if len(c["specs"]) > 1 else None)
    c.setdefault("print_text", "campaigns/%s/specs/print_text.json" % cid)
    c.setdefault("guide_md", "campaigns/%s/guide.md" % cid)
    c.setdefault("starter", [])
    c.setdefault("starter_out", slug + "_starter.json")
    c.setdefault("bundle_out", slug + "_bundle.lua")
    c.setdefault("lua_modules", [])
    c.setdefault("control_lua", "src/tts/control.lua")
    c.setdefault("tests_entry", "runCampaignTests")
    c.setdefault("static_token", None)                # optional campaign-specific chaos token
    c.setdefault("encounter_bag_name", c["upper_name"] + " — Encounter Cards")
    c.setdefault("skip_bags", [])                     # bags package_download leaves out of the box
    c.setdefault("illustrations", "assets/illustrations/" + cid)
    c.setdefault("out_dir", "out/" + cid)
    c.setdefault("genre", "custom campaign")
    c.setdefault("art_setting", "1920s New England, cosmic horror, uncanny rather than gory")
    c.setdefault("art_scenes", "campaigns/%s/art_scenes.json" % cid)   # {scenes, characters, text_only}
    c.setdefault("art_pack_json", "campaigns/%s/art/chatgpt_art_pack.json" % cid)
    c.setdefault("art_pack_md", "campaigns/%s/art/ART_PACK.md" % cid)
    c.setdefault("art_manifest_copies", [])
    c.setdefault("art_starter", [])
    c.setdefault("art_starter_copies", [])
    return c


CFG = load()


# The shared table scripts (src/tts/loop_box.lua, download_box.lua,
# campaign_log.lua) were written for The Still Hour; the build swaps its names
# for the campaign's (an identity for The Still Hour itself).
def lua_text(path, cfg=None):
    cfg = cfg or CFG
    s = open(path, encoding="utf-8").read()
    for old, new in (("THE STILL HOUR", cfg.upper_name), ("The Still Hour", cfg.name),
                     ("the_still_hour", cfg.slug), ("StillHour", cfg.tag),
                     ("sthrLog_", cfg.prefix + "Log_"), ("Still Hour", cfg.box_name)):
        if old != new:
            s = s.replace(old, new)
    return s


def log_module(cfg=None):
    """The campaign log layout: campaigns/<id>/log_layout.py when build.json
    names one ("log_layout"), else pipeline/campaign_log.py's own (The Still Hour)."""
    import importlib.util
    cfg = cfg or CFG
    rel = cfg.get("log_layout")
    if not rel:
        return None
    spec = importlib.util.spec_from_file_location("campaign_log_layout", os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
