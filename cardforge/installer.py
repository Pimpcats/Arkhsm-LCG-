"""Self-contained setup — the app installs its own dependencies into vendor/.

Everything lands inside the repo folder and every path is resolved from
runner.repo_root() at call time, so the whole folder can move machines or
drives and keep working:

    vendor/models/           the art checkpoint (Painter's Checkpoint v1.1)
    vendor/strange-eons/     the Strange Eons download (+ app/ once installed)

Checkpoint: pulled via Civitai's public API (model 240154), preferring the
v1.1 version. Civitai requires a personal API token for most downloads —
paste it in the Setup tab (stored in state/, never committed). After the
download the campaign's "checkpoint" is set to the file and the A1111 rig
launch gains --ckpt-dir vendor/models so the backend sees it wherever the
folder lives (toggle "use_vendor_models" off in rig.json to use your own
model library instead).

Strange Eons: fetched from the official GitHub releases (CGJennings/
strange-eons), picking the asset for this OS. On Windows the installer is
run silently into vendor/strange-eons/app when it accepts install4j's
-q -dir flags; otherwise it's left in vendor/ with instructions. The SE
launch command in se/se_config.json is pointed at the result. The Arkham
plugin (jaqenZann's external build) and the AH font pack cannot be
auto-fetched — they are distributed via the Barnaby Files guide and the
Mythos Busters Discord; the Setup tab links both.

Dry-run mode fabricates tiny stub artifacts with no network, so the whole
flow is testable anywhere (and is what the selftest drives).
"""
import json
import os
import platform
import subprocess

from . import runner, se_bridge

CIVITAI_MODEL_ID = 240154            # Painter's Checkpoint (SDXL)
CIVITAI_VERSION_HINT = "1.1"
SE_RELEASES_API = "https://api.github.com/repos/CGJennings/strange-eons/releases/latest"
CHUNK = 1 << 20                      # 1 MiB


def vendor_dir(*parts):
    return os.path.join(runner.repo_root(), "vendor", *parts)


def token_path():
    return os.path.join(runner.repo_root(), "state", "civitai_token.txt")


def load_token():
    if os.path.exists(token_path()):
        return open(token_path(), encoding="utf-8").read().strip()
    return ""


def save_token(token):
    os.makedirs(os.path.dirname(token_path()), exist_ok=True)
    with open(token_path(), "w", encoding="utf-8") as f:
        f.write(token.strip())


def vendor_status():
    """What's installed under vendor/ right now (paths relative to the repo)."""
    models = []
    mdir = vendor_dir("models")
    if os.path.isdir(mdir):
        models = sorted(f for f in os.listdir(mdir)
                        if f.endswith((".safetensors", ".ckpt")))
    se_exe = _find_se_binary()
    return {
        "models": models,
        "models_dir": "vendor/models",
        "se_installed": bool(se_exe),
        "se_path": os.path.relpath(se_exe, runner.repo_root()) if se_exe else None,
        "se_downloads": sorted(os.listdir(vendor_dir("strange-eons")))
        if os.path.isdir(vendor_dir("strange-eons")) else [],
        "has_token": bool(load_token()),
    }


def _download(url, dest, headers=None, log=print):
    import requests
    with requests.get(url, stream=True, timeout=60, headers=headers or {}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        next_pct = 10
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(CHUNK):
                f.write(chunk)
                done += len(chunk)
                if total and done * 100 // total >= next_pct:
                    log("  {}% of {:.1f} GB".format(
                        done * 100 // total, total / 1e9))
                    next_pct += 10
        os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------- checkpoint --

def install_checkpoint(campaign="still_hour", token=None, dry_run=False, log=print):
    """Download Painter's Checkpoint v1.1 into vendor/models/, then point the
    campaign at it. Returns the checkpoint filename."""
    os.makedirs(vendor_dir("models"), exist_ok=True)
    if token:
        save_token(token)
    token = load_token()

    if dry_run:
        fname = "paintersCheckpoint_v11_STUB.safetensors"
        with open(os.path.join(vendor_dir("models"), fname), "wb") as f:
            f.write(b"stub-checkpoint")
        log("dry-run: wrote stub checkpoint " + fname)
    else:
        import requests
        log("querying Civitai for model {}…".format(CIVITAI_MODEL_ID))
        meta = requests.get(
            "https://civitai.com/api/v1/models/{}".format(CIVITAI_MODEL_ID),
            timeout=30).json()
        versions = meta.get("modelVersions") or []
        version = next((v for v in versions
                        if CIVITAI_VERSION_HINT in (v.get("name") or "")),
                       versions[0] if versions else None)
        if not version:
            raise RuntimeError("Civitai returned no versions for the model")
        vfile = next((f for f in version.get("files", [])
                      if f.get("name", "").endswith(".safetensors")),
                     (version.get("files") or [{}])[0])
        fname = vfile.get("name") or "painters_checkpoint.safetensors"
        url = version.get("downloadUrl") or \
            "https://civitai.com/api/download/models/{}".format(version["id"])
        if token:
            url += ("&" if "?" in url else "?") + "token=" + token
        dest = os.path.join(vendor_dir("models"), fname)
        log("downloading {} ({}, ~{:.1f} GB)…".format(
            version.get("name"), fname,
            (vfile.get("sizeKB") or 0) / 1e6))
        try:
            _download(url, dest, log=log)
        except Exception as e:  # noqa: BLE001 - auth is the common failure
            raise RuntimeError(
                "download failed ({}). Civitai usually needs a personal API "
                "key — create one at civitai.com/user/account, paste it in "
                "the Setup tab, and retry.".format(e))
        log("saved vendor/models/" + fname)

    # point the campaign at it
    camp_path = os.path.join(runner.campaign_dir(campaign), "campaign.json")
    camp = json.load(open(camp_path, encoding="utf-8"))
    camp["checkpoint"] = fname
    with open(camp_path, "w", encoding="utf-8") as f:
        json.dump(camp, f, indent=2)
    log("campaign checkpoint -> " + fname)
    log("A1111 will see it via --ckpt-dir vendor/models (added at launch; "
        "set \"use_vendor_models\": false in rig.json to opt out)")
    return fname


def ckpt_dir_args():
    """Extra A1111 launch args so the backend sees vendor/models/ wherever
    this folder lives. Empty when unused/empty/opted out."""
    from . import rig
    entry = rig.load_rig().get("a1111", {})
    if entry.get("use_vendor_models") is False:
        return ""
    mdir = vendor_dir("models")
    has_model = os.path.isdir(mdir) and any(
        f.endswith((".safetensors", ".ckpt")) for f in os.listdir(mdir))
    return ' --ckpt-dir "{}"'.format(mdir) if has_model else ""


# -------------------------------------------------------------- strange eons --

def _find_se_binary():
    app = vendor_dir("strange-eons", "app")
    if not os.path.isdir(app):
        return None
    for name in ("StrangeEons.exe", "strangeeons.exe", "StrangeEons",
                 "strangeeons", "bin/eons"):
        p = os.path.join(app, *name.split("/"))
        if os.path.exists(p):
            return p
    return None


def install_strange_eons(dry_run=False, log=print):
    """Download the latest Strange Eons release for this OS into
    vendor/strange-eons/ and (Windows) try a silent install into app/;
    then point the SE launch command at the result."""
    dest_dir = vendor_dir("strange-eons")
    app_dir = os.path.join(dest_dir, "app")
    os.makedirs(dest_dir, exist_ok=True)

    if dry_run:
        os.makedirs(app_dir, exist_ok=True)
        exe = os.path.join(app_dir, "StrangeEons.exe")
        with open(exe, "wb") as f:
            f.write(b"stub-se")
        log("dry-run: wrote stub Strange Eons install")
    else:
        import requests
        log("querying GitHub for the latest Strange Eons release…")
        rel = requests.get(SE_RELEASES_API, timeout=30).json()
        assets = rel.get("assets", [])
        system = platform.system()
        want = {"Windows": (".exe",), "Darwin": (".dmg",),
                "Linux": (".tar.gz", ".tgz", ".deb")}.get(system, (".tar.gz",))
        asset = next((a for a in assets
                      if a["name"].lower().endswith(want)), None)
        if not asset:
            raise RuntimeError(
                "no {} asset in release {} — install manually from "
                "strangeeons.cgjennings.ca into vendor/strange-eons/app"
                .format(want, rel.get("tag_name")))
        pkg = os.path.join(dest_dir, asset["name"])
        log("downloading {} ({:.0f} MB)…".format(
            asset["name"], asset.get("size", 0) / 1e6))
        _download(asset["browser_download_url"], pkg, log=log)
        log("saved vendor/strange-eons/" + asset["name"])
        if system == "Windows":
            log("attempting silent install into vendor/strange-eons/app…")
            try:
                subprocess.run([pkg, "-q", "-dir", app_dir],
                               check=True, timeout=600)
            except Exception as e:  # noqa: BLE001 - installer flags vary
                log("silent install didn't take ({}) — run the installer in "
                    "vendor/strange-eons/ yourself and choose\n  {}\nas the "
                    "install folder.".format(e, app_dir))
        elif pkg.endswith((".tar.gz", ".tgz")):
            import tarfile
            with tarfile.open(pkg) as t:
                t.extractall(app_dir)
            log("extracted into vendor/strange-eons/app")
        else:
            log("open vendor/strange-eons/{} and install into {}".format(
                asset["name"], app_dir))

    exe = _find_se_binary()
    if exe:
        cfg = se_bridge.load_config()
        cfg["launch_command"] = '"{}" --run {{script}}'.format(exe)
        se_bridge.save_config(cfg)
        log("SE launch command -> " + cfg["launch_command"])
    else:
        log("SE binary not found yet under vendor/strange-eons/app — the "
            "Frame tab's launch command updates automatically once it is.")
    log("REMINDER: the Arkham plugin must be jaqenZann's EXTERNAL build "
        "(Barnaby Files guide), NOT the in-app catalog one; AH font pack "
        "from the Mythos Busters Discord.")
    return {"installed": bool(exe), "path": exe}
