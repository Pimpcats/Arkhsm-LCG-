"""Strange Eons bridge — the Frame stage as automation, not a rewrite.

Strange Eons 3 (strangeeons.cgjennings.ca; source github.com/CGJennings/
strange-eons) is a Java desktop app with a first-class scripting engine. The
right integration is therefore orchestration: this module

  1. builds a FRAME BUNDLE — an SE automation script with our card jobs
     embedded as a literal (no file-IO inside SE), plus a README;
  2. provides the launch command (configurable — SE installs differ);
  3. collects exported faces and reports coverage vs. the job list.

Two seams are the OWNER'S to verify once against their installed SE + Arkham
plugin (exactly as ART_PIPELINE_BRIEF A1.4 anticipated): the plugin's class-map
keys (what component each frame type creates) and its per-component setting
keys (where title/traits/stats live). Both live in se/se_config.json and are
editable from the Studio's Frame tab; the generated script marks them clearly.
"""
import json
import os

from . import runner

SE_DIR_NAME = "se"

DEFAULT_CONFIG = {
    # command template; {script} is replaced with the generated script path.
    # SE also installs a native launcher — adjust to taste (e.g. "strangeeons").
    "launch_command": "java -jar /path/to/strange-eons.jar --run {script}",
    "export_dpi": 300,
    "faces_dir": "art/faces",
    # frame type -> Arkham plugin class-map key (owner: Toolbox > New Component,
    # or inspect the plugin's classmap; see the generated script header).
    "classmap": {
        "investigator_portrait": "TODO:arkham-investigator-classmap-key",
        "asset": "TODO:arkham-asset-classmap-key",
        "event": "TODO:arkham-event-classmap-key",
        "skill": "TODO:arkham-skill-classmap-key",
        "treachery": "TODO:arkham-treachery-classmap-key",
        "enemy": "TODO:arkham-enemy-classmap-key",
        "location": "TODO:arkham-location-classmap-key",
        "agenda": "TODO:arkham-agenda-classmap-key",
    },
    # component setting keys (owner: open one card of each type in SE and
    # inspect its keys; these defaults follow common plugin conventions).
    "keys": {
        "title": "name", "subtitle": "subtitle", "traits": "traits",
        "text": "rules", "cost": "cost", "willpower": "willpower",
        "intellect": "intellect", "combat": "combat", "agility": "agility",
        "health": "health", "sanity": "sanity",
    },
}


def se_dir():
    return os.path.join(runner.repo_root(), SE_DIR_NAME)


def config_path():
    return os.path.join(se_dir(), "se_config.json")


def load_config():
    if os.path.exists(config_path()):
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(json.load(open(config_path(), encoding="utf-8")))
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    os.makedirs(se_dir(), exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _load_card_specs():
    here = os.path.join(runner.repo_root(), "pipeline")
    cards = json.load(open(os.path.join(here, "stillhour_cards_spec.json"), encoding="utf-8"))
    enc = os.path.join(here, "stillhour_encounter_spec.json")
    if os.path.exists(enc):
        cards += json.load(open(enc, encoding="utf-8"))
    return {c["id"]: c for c in cards}


def _load_print_text():
    path = os.path.join(runner.repo_root(), "pipeline", "stillhour_print_text.json")
    if os.path.exists(path):
        return {k: v for k, v in json.load(open(path, encoding="utf-8")).items() if not k.startswith("_")}
    return {}


def build_jobs(campaign="still_hour"):
    """One frame job per manifest face: spec fields + the PRINT layer
    (stillhour_print_text.json: rules text, flavor, enemy combat stats,
    investigator back text — see docs/art_reference/CARD_ANATOMY.md) + the
    illustration path from CardForge's index.json when present. Rules text uses
    the repo's [wil]-style markup; convert to plugin tags or glyph letters at
    frame time."""
    specs = _load_card_specs()
    print_text = _load_print_text()
    manifest = runner.load_manifest(campaign)
    camp = runner.load_campaign(campaign)
    index_path = os.path.join(runner.out_dir_for(camp), "index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else {}
    jobs = []
    for m in manifest:
        is_back = m["id"].endswith("-back")
        base_id = m["id"][:-5] if is_back else m["id"]
        spec = specs.get(base_id, {})
        pt = print_text.get(base_id, {})
        job = {
            "id": m["id"],
            "frame": m.get("frame") or m.get("art_type"),
            "text_only": bool(m.get("no_art")),
            "illustration": index.get(base_id),
            "name": spec.get("name", ""),
            "subtitle": spec.get("subtitle", ""),
            "traits": spec.get("traits", ""),
            "class": spec.get("class", ""),
            "cost": spec.get("cost"),
            "stats": {k: spec.get(k) for k in ("wil", "int", "com", "agi",
                                               "health", "sanity") if k in spec},
            "victory": spec.get("victory"),
            "elite": bool(spec.get("elite")),
            "text": pt.get("back_text" if is_back else "text", ""),
            "flavor": pt.get("back_flavor" if is_back else "flavor", ""),
        }
        # enemy combat line lives only in the print layer
        for k in ("fight", "evade", "damage", "horror"):
            if k in pt:
                job[k] = pt[k]
        if "health" in pt:            # enemy health (investigator health is in stats)
            job["enemy_health"] = pt["health"]
        jobs.append(job)
    return jobs


SCRIPT_TEMPLATE = """/*
 * frame_cards.js — GENERATED by CardForge Studio; regenerate, don't hand-edit.
 * Run inside Strange Eons 3 (Toolbox > Script console, or via the launch
 * command). Creates one component per job, fills its settings, injects the
 * illustration, exports a PNG face per card.
 *
 * OWNER SEAMS (verify once against your SE + Arkham plugin install):
 *  - CLASSMAP: plugin class-map key per frame type (any 'TODO:' entry is
 *    skipped with a console note). Find keys via the plugin's class map or by
 *    saving a component of each type and inspecting it.
 *  - KEYS: the plugin's setting names for title/traits/stats.
 *  - The component-creation call below targets the documented scripting API;
 *    if your SE build names it differently, see the Scripting section of the
 *    SE docs (github.com/CGJennings/strange-eons) and adjust makeComponent().
 */
useLibrary('imageutils');
importClass(java.io.File);

const CLASSMAP = %(classmap)s;
const KEYS = %(keys)s;
const OUT_DIR = %(out_dir)s;
const DPI = %(dpi)s;
const JOBS = %(jobs)s;

function makeComponent(classKey) {
    // Documented route: instantiate from the game data class map.
    return gamedata.ClassMap.createInstance
        ? gamedata.ClassMap.createInstance(classKey)
        : eons.createComponent(classKey);   // fallback naming on some builds
}

function setIf(comp, key, value) {
    if (value === null || value === undefined || value === '') return;
    try { comp.settings.set(KEYS[key] !== undefined ? KEYS[key] : key, String(value)); }
    catch (ex) { println('  [warn] key ' + key + ': ' + ex); }
}

new File(OUT_DIR).mkdirs();
let done = 0, skipped = 0;
for (let i = 0; i < JOBS.length; i++) {
    const job = JOBS[i];
    const classKey = CLASSMAP[job.frame];
    if (!classKey || String(classKey).indexOf('TODO:') === 0) {
        println('SKIP ' + job.id + ' (no classmap for frame ' + job.frame + ')');
        skipped++;
        continue;
    }
    try {
        const comp = makeComponent(classKey);
        setIf(comp, 'title', job.name);
        setIf(comp, 'subtitle', job.subtitle);
        setIf(comp, 'traits', job.traits);
        setIf(comp, 'text', job.text);
        setIf(comp, 'cost', job.cost);
        for (let s in job.stats) setIf(comp, s, job.stats[s]);
        if (job.illustration && comp.portraits && comp.portraits.length > 0) {
            comp.portraits[0].setSource(job.illustration);
        }
        comp.createDefaultSheets();
        const sheet = comp.sheets[0];
        const image = sheet.paint(arkham.sheet.RenderTarget.EXPORT, DPI);
        ImageUtils.write(image, new File(OUT_DIR, job.id + '.png'), ImageUtils.FORMAT_PNG);
        println('OK   ' + job.id);
        done++;
    } catch (ex) {
        println('FAIL ' + job.id + ': ' + ex);
    }
}
println('frame_cards: ' + done + ' exported, ' + skipped + ' skipped, of ' + JOBS.length);
"""


def write_bundle(campaign="still_hour"):
    """Write se/frame_jobs.json + se/frame_cards.js (+ README). Returns paths."""
    cfg = load_config()
    jobs = build_jobs(campaign)
    os.makedirs(se_dir(), exist_ok=True)
    faces_abs = os.path.join(runner.repo_root(), cfg["faces_dir"])
    # illustration paths must be absolute for SE
    for j in jobs:
        if j["illustration"]:
            j["illustration"] = os.path.join(runner.repo_root(), j["illustration"])
    jobs_path = os.path.join(se_dir(), "frame_jobs.json")
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
    script = SCRIPT_TEMPLATE % {
        "classmap": json.dumps(cfg["classmap"], indent=4),
        "keys": json.dumps(cfg["keys"], indent=4),
        "out_dir": json.dumps(faces_abs),
        "dpi": json.dumps(cfg["export_dpi"]),
        "jobs": json.dumps(jobs, indent=2),
    }
    script_path = os.path.join(se_dir(), "frame_cards.js")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    readme_path = os.path.join(se_dir(), "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            "# Strange Eons frame bundle (generated)\n\n"
            "1. Install Strange Eons 3 (strangeeons.cgjennings.ca; source\n"
            "   github.com/CGJennings/strange-eons). IMPORTANT: do NOT use the\n"
            "   Arkham plugin from the in-app catalog — it is OUTDATED. Use the\n"
            "   maintained external build by jaqenZann, linked from the Barnaby\n"
            "   Files guide 'Strange Eons: How to Make an Investigator'\n"
            "   (barnabyfiles.wordpress.com). Install the AH font family from\n"
            "   the Mythos Busters Discord or cards render in a Times-like font.\n"
            "2. Fill the class-map + setting keys in se_config.json (or the\n"
            "   Studio's Frame tab) — once per plugin version.\n"
            "3. Run frame_cards.js in SE (script console, or:\n   "
            + cfg["launch_command"].replace("{script}", script_path) + "\n"
            "4. Faces land in " + cfg["faces_dir"] + "/; the Studio's Frame tab\n"
            "   shows coverage and the Apply tab pushes them into the mod.\n")
    return {"script": script_path, "jobs": jobs_path, "readme": readme_path,
            "job_count": len(jobs)}


def coverage(campaign="still_hour"):
    """Which jobs have an exported face in faces_dir?"""
    cfg = load_config()
    faces_dir = os.path.join(runner.repo_root(), cfg["faces_dir"])
    jobs = build_jobs(campaign)
    have = set()
    if os.path.isdir(faces_dir):
        have = {os.path.splitext(f)[0] for f in os.listdir(faces_dir) if f.endswith(".png")}
    framed = [j["id"] for j in jobs if j["id"] in have]
    missing = [j["id"] for j in jobs if j["id"] not in have]
    return {"framed": framed, "missing": missing,
            "total": len(jobs), "faces_dir": cfg["faces_dir"]}
