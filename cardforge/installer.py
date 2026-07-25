"""Self-contained setup — the app installs its own dependencies into vendor/.

Everything lands inside the repo folder and every path is resolved from
runner.repo_root() at call time, so the whole folder can move machines or
drives and keep working:

    vendor/models/           the art checkpoint (MoodyKrea2Mix)
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
import json
import os
import platform
import subprocess

from . import runner, se_bridge

# The art checkpoint the Setup tab installs. Searched BY NAME on Civitai so the
# model can be changed here (or per campaign via campaign.json "art_model")
# without needing a hardcoded id. CIVITAI_MODEL_ID is an optional exact-id
# override for when search is ambiguous.
CIVITAI_MODEL_ID = 2731187           # Moody Krea 2 Mix (Krea 2 checkpoint merge)
CIVITAI_MODEL_QUERY = "moody krea 2 mix"
CIVITAI_VERSION_HINT = ""            # empty = take the LATEST version published
CIVITAI_MODEL_LABEL = "Moody Krea 2 Mix"
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


def _ls(path):
    """Directory listing that answers [] instead of raising — an install job
    can be rewriting vendor/ while the UI polls status."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def vendor_status():
    """What's installed under vendor/ right now (paths relative to the repo)."""
    models = [f for f in _ls(vendor_dir("models"))
              if f.endswith((".safetensors", ".ckpt"))]
    se_exe = _find_se_binary()
    return {
        "models": models,
        "models_dir": "vendor/models",
        "a1111_installed": a1111_installed(),
        "a1111_partial": (bool(_ls(a1111_dir()))
                          and not a1111_installed()),
        "a1111_dir": "vendor/a1111",
        "se_installed": bool(se_exe),
        "se_path": os.path.relpath(se_exe, runner.repo_root()) if se_exe else None,
        "se_downloads": _ls(vendor_dir("strange-eons")),
        "has_token": bool(load_token()),
        "plugin": _plugin_status(),
        "fonts": _font_status(),
    }


def _font_status():
    """Which title fonts are actually present — so the Setup row can show a
    verified green state instead of a button that appears to do nothing."""
    d = os.path.join(runner.repo_root(), "assets", "fonts")
    have = sorted(f for f in os.listdir(d)
                  if f.lower().endswith((".ttf", ".otf"))) \
        if os.path.isdir(d) else []
    return {"arkhamic": [f for f in have if f.lower().startswith("arkhamic")],
            "teutonic": [f for f in have if f.lower().startswith("teutonic")],
            "count": len(have)}


def _plugin_status():
    """The Arkham SE plugin is VENDORED and already extracted — this reports
    what the renderer is actually drawing from, so the Setup row can show a
    verified state instead of looking like an install step."""
    root = runner.repo_root()
    seext = os.path.join(root, "assets", "plugins", "ArkhamHorrorLCG.seext")
    fdir = os.path.join(root, "assets", "frames", "se")

    def _count(sub):
        d = os.path.join(fdir, sub)
        return len([f for f in os.listdir(d) if f.endswith(".png")]) \
            if os.path.isdir(d) else 0

    regions = 0
    rp = os.path.join(fdir, "regions.json")
    if os.path.exists(rp):
        try:
            regions = sum(len(v) for v in json.load(
                open(rp, encoding="utf-8")).values())
        except (ValueError, OSError):
            regions = 0
    return {"have_seext": os.path.exists(seext),
            "templates": _count("templates"), "overlays": _count("overlays"),
            "icons": _count("icons"), "regions": regions}


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
    """Download the campaign art checkpoint into vendor/models/, then point the
    campaign at it. The model is found by NAME on Civitai (overridable per
    campaign with "art_model"/"art_model_version"), so swapping models needs no
    code change. Returns the checkpoint filename."""
    os.makedirs(vendor_dir("models"), exist_ok=True)
    if token:
        save_token(token)
    token = load_token()

    # per-campaign override, else the module default
    query, hint = CIVITAI_MODEL_QUERY, CIVITAI_VERSION_HINT
    try:
        _cp = os.path.join(runner.campaign_dir(campaign), "campaign.json")
        _c = json.load(open(_cp, encoding="utf-8"))
        query = _c.get("art_model") or query
        hint = _c.get("art_model_version") or hint
    except (OSError, ValueError):
        pass

    if dry_run:
        fname = "{}_STUB.safetensors".format(query)
        with open(os.path.join(vendor_dir("models"), fname), "wb") as f:
            f.write(b"stub-checkpoint")
        log("dry-run: wrote stub checkpoint " + fname)
    else:
        import requests
        headers = {"Authorization": "Bearer " + token} if token else {}
        if CIVITAI_MODEL_ID:
            log("querying Civitai for model {}…".format(CIVITAI_MODEL_ID))
            meta = requests.get(
                "https://civitai.com/api/v1/models/{}".format(CIVITAI_MODEL_ID),
                timeout=30, headers=headers).json()
        else:
            log("searching Civitai for \"{}\"…".format(query))
            try:
                res = requests.get("https://civitai.com/api/v1/models",
                                   params={"query": query, "types": "Checkpoint",
                                           "limit": 10},
                                   timeout=30, headers=headers).json()
            except Exception as e:  # noqa: BLE001 - offline/proxy/TLS
                raise RuntimeError(
                    "could not reach Civitai ({}). Check your connection, or "
                    "download the model yourself and drop the .safetensors "
                    "into vendor/models/.".format(e))
            if isinstance(res, dict) and res.get("error"):
                raise RuntimeError("Civitai said: {}".format(res["error"]))
            items = (res or {}).get("items") or []
            if not items:
                raise RuntimeError(
                    "Civitai has no checkpoint matching \"{}\". Check the name "
                    "in Setup, or drop the .safetensors into vendor/models/ "
                    "yourself.".format(query))
            # prefer an exact-ish name match over search ranking
            ql = query.lower().replace(" ", "")
            meta = next((m for m in items
                         if ql in (m.get("name", "").lower().replace(" ", ""))),
                        items[0])
            log("found: {} (id {})".format(meta.get("name"), meta.get("id")))
        versions = meta.get("modelVersions") or []
        # no hint -> newest published version (Civitai lists newest first), so
        # the installer keeps working as the model is updated
        version = next((v for v in versions
                        if hint and hint in (v.get("name") or "")),
                       versions[0] if versions else None)
        if version:
            log("version: {}{}".format(version.get("name"),
                                       "" if hint else " (latest)"))
        if not version:
            raise RuntimeError("Civitai returned no versions for the model")
        vfile = next((f for f in version.get("files", [])
                      if f.get("name", "").endswith(".safetensors")),
                     (version.get("files") or [{}])[0])
        fname = vfile.get("name") or (query + ".safetensors")
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


# -------------------------------------------------------------------- fonts --

ARKHAMIC_RELEASES_API = "https://api.github.com/repos/javnik36/arkhamic/releases"


def install_fonts(dry_run=False, log=print):
    """Fetch Arkhamic — the community's OFL-licensed extension of Teutonic
    (the FFG title face) from github.com/javnik36/arkhamic — into
    assets/fonts/. The renderer prefers it over plain Teutonic once present."""
    dest = os.path.join(runner.repo_root(), "assets", "fonts")
    os.makedirs(dest, exist_ok=True)
    if dry_run:
        with open(os.path.join(dest, "Arkhamic.ttf"), "wb") as f:
            f.write(b"stub-font")
        log("dry-run: wrote stub Arkhamic.ttf")
        return {"installed": ["Arkhamic.ttf"]}
    have = [f for f in os.listdir(dest)
            if f.lower().startswith("arkhamic") and f.lower().endswith((".ttf", ".otf"))]
    if have:
        log("Arkhamic already installed: " + ", ".join(sorted(have)))
        return {"installed": sorted(have), "already": True}
    import requests
    log("querying GitHub for Arkhamic releases…")
    try:
        rels = requests.get(ARKHAMIC_RELEASES_API + "?per_page=5", timeout=30).json()
    except Exception as e:  # noqa: BLE001 - offline/DNS/TLS
        raise RuntimeError(
            "could not reach GitHub to fetch Arkhamic ({}). The app already "
            "ships Teutonic, so cards still render; retry when you are "
            "online.".format(e))
    if isinstance(rels, dict):
        msg = rels.get("message", "unexpected response")
        if "rate limit" in msg.lower():
            msg = ("GitHub rate-limited this machine (resets within the hour) "
                   "— try again later")
        raise RuntimeError("GitHub said: " + msg)
    if not isinstance(rels, list):
        raise RuntimeError("unexpected GitHub response while fetching Arkhamic")
    got = []
    for rel in rels:
        for a in rel.get("assets", []):
            name = a["name"]
            if name.lower().endswith((".ttf", ".otf")):
                _download(a["browser_download_url"],
                          os.path.join(dest, name), log=log)
                got.append(name)
            elif name.lower().endswith(".zip"):
                import io as _io
                import zipfile
                r = requests.get(a["browser_download_url"], timeout=120)
                r.raise_for_status()
                with zipfile.ZipFile(_io.BytesIO(r.content)) as z:
                    for zn in z.namelist():
                        if zn.lower().endswith((".ttf", ".otf")):
                            base = os.path.basename(zn)
                            with open(os.path.join(dest, base), "wb") as f:
                                f.write(z.read(zn))
                            got.append(base)
        if got:
            break
    if not got:
        raise RuntimeError(
            "no font assets in the Arkhamic releases — download the .ttf "
            "from github.com/javnik36/arkhamic manually into assets/fonts/")
    log("installed: " + ", ".join(got) + " (title text now uses Arkhamic)")
    return {"installed": got}


# -------------------------------------------------------------------- a1111 --

A1111_RELEASES_API = ("https://api.github.com/repos/AUTOMATIC1111/"
                      "stable-diffusion-webui/releases")


def a1111_dir():
    return vendor_dir("a1111")


def a1111_installed():
    """True only when a usable A1111 actually sits in vendor/a1111 — a
    launcher AND the webui payload, not just an empty folder from a failed
    download (which is what made the button look like it did nothing)."""
    d = a1111_dir()
    if not os.path.isdir(d):
        return False
    launcher = any(os.path.exists(os.path.join(d, f))
                   for f in ("run.bat", "webui.sh", "webui.bat",
                             os.path.join("webui", "webui.bat"),
                             os.path.join("webui", "webui.sh")))
    payload = any(os.path.exists(os.path.join(d, f))
                  for f in ("webui.py", os.path.join("webui", "webui.py"),
                            os.path.join("webui", "launch.py")))
    return bool(launcher and payload)


def install_a1111(dry_run=False, log=print):
    """Self-contained Stable Diffusion: download AUTOMATIC1111's standalone
    Windows package (sd.webui.zip — bundled Python, no system installs) into
    vendor/a1111/, force --api on, and point the rig at it. First launch
    still downloads its own torch etc. into the same folder (one-time,
    several GB — its console shows progress)."""
    from . import rig
    dest_dir = a1111_dir()
    os.makedirs(dest_dir, exist_ok=True)

    if dry_run:
        os.makedirs(os.path.join(dest_dir, "webui"), exist_ok=True)
        for f in ("run.bat", os.path.join("webui", "webui.py")):
            with open(os.path.join(dest_dir, f), "w", encoding="utf-8") as fh:
                fh.write("rem stub\n")
        log("dry-run: wrote stub A1111 install")
    else:
        import requests, zipfile  # noqa: E401
        log("querying GitHub for the A1111 standalone package…")
        asset = None
        try:
            resp = requests.get(A1111_RELEASES_API + "?per_page=15", timeout=30)
            rels = resp.json()
        except Exception as e:  # noqa: BLE001 - offline/DNS/TLS all land here
            raise RuntimeError(
                "could not reach GitHub to find the A1111 package ({}). Check "
                "your internet connection, or install A1111 yourself and point "
                "the Illustrate tab's Backend row at it.".format(e))
        # GitHub answers with an OBJECT (not a list) on rate limit / error —
        # say so plainly instead of crashing on it
        if isinstance(rels, dict):
            msg = rels.get("message", "unexpected response")
            if "rate limit" in msg.lower():
                msg = ("GitHub rate-limited this machine (this resets within "
                       "the hour). Wait and click again, or install A1111 "
                       "yourself and point the Backend row at it.")
            raise RuntimeError("GitHub said: " + msg)
        if not isinstance(rels, list):
            raise RuntimeError("unexpected GitHub response while looking for "
                               "the A1111 package")
        for rel in rels:
            if not isinstance(rel, dict):
                continue
            for a in rel.get("assets") or []:
                name = (a or {}).get("name", "")
                if name.startswith("sd.webui") and name.endswith(".zip"):
                    asset = a
                    break
            if asset:
                break
        if not asset:
            raise RuntimeError(
                "no sd.webui*.zip asset found in recent releases — install "
                "A1111 manually into vendor/a1111/ (git clone "
                "AUTOMATIC1111/stable-diffusion-webui) or keep using your "
                "existing install via the rig")
        pkg = os.path.join(dest_dir, asset["name"])
        log("downloading {} ({:.0f} MB)…".format(asset["name"],
                                                 asset.get("size", 0) / 1e6))
        _download(asset["browser_download_url"], pkg, log=log)
        log("extracting…")
        with zipfile.ZipFile(pkg) as z:
            z.extractall(dest_dir)
        os.remove(pkg)

    # force the API on (and keep any future owner args alongside)
    user_bat = os.path.join(dest_dir, "webui", "webui-user.bat")
    os.makedirs(os.path.dirname(user_bat), exist_ok=True)
    with open(user_bat, "w", encoding="utf-8") as f:
        f.write("@echo off\n"
                "rem headless: API only, no A1111 browser UI - CardForge drives it\n"
                "set COMMANDLINE_ARGS=--api --nowebui --autolaunch-disable "
                "--skip-version-check\n"
                "call webui.bat\n")
    # point the rig at the vendored install
    cfg = rig.load_rig()
    cfg["a1111"]["cwd"] = dest_dir
    cfg["a1111"]["command"] = "run.bat"
    rig.save_rig(cfg)
    log("rig -> vendor/a1111 (run.bat, API on). First real launch installs "
        "its own dependencies — give it time and watch its console window.")
    return {"installed": True, "dir": dest_dir}


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
