"""Backend rig — where A1111/ComfyUI live on THIS machine and how to start
them, so the Studio can launch the image backend itself and wait for its API.

Config is layered: built-in defaults, then rig.json at the repo root (tracked,
neutral shared defaults, never machine paths), then rig.local.json (ignored by
git: this machine's folders and commands). The Studio's Illustrate tab and the
installers write rig.local.json only, so a pull never overwrites the owner's
settings and a commit never publishes them. rig.example.json shows the shape. The launched process gets its own console window on
Windows (its logs stay visible) / its own session elsewhere, and outlives the
Studio. `ensure_up` is the one entry point: reachable? done. Not reachable?
launch it, then poll the backend's own check() until the API answers or the
rig's startup_timeout passes — first A1111 boot can take minutes.
"""
import json
import os
import subprocess
import time

from . import runner

POLL_SECONDS = 5

RIG_DEFAULTS = {
    # headless by default: --nowebui serves only the API, so the backend runs
    # inside CardForge and never opens a second web UI of its own
    "a1111": {"cwd": "", "command": "webui.bat --api --nowebui", "startup_timeout": 420},
    "comfy": {"cwd": "", "command": "python main.py", "startup_timeout": 300},
}


def shared_rig_path():
    """Tracked, neutral defaults (no machine paths)."""
    return os.path.join(runner.repo_root(), "rig.json")


def rig_path():
    """This machine's settings (not tracked); every save goes here."""
    return os.path.join(runner.repo_root(), "rig.local.json")


def _read(path):
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_rig():
    """Defaults, then rig.json, then rig.local.json (each layer optional)."""
    cfg = {k: dict(v) for k, v in RIG_DEFAULTS.items()}
    for data in (_read(shared_rig_path()), _read(rig_path())):
        for k in cfg:
            if isinstance(data.get(k), dict):
                cfg[k].update(data[k])
        if data.get("_note"):
            cfg["_note"] = data["_note"]
    return cfg


def save_rig(cfg):
    out = {k: cfg[k] for k in cfg if k in RIG_DEFAULTS or k == "_note"}
    with open(rig_path(), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def launch(kind):
    """Start the backend detached, in its rig cwd. Returns (ok, message)."""
    entry = load_rig().get(kind, {})
    cwd, command = entry.get("cwd", ""), entry.get("command", "")
    if not command:
        return False, ("no launch command for '{}' — set it in the Illustrate "
                       "tab (or rig.local.json)".format(kind))
    if cwd and not os.path.isdir(cwd):
        return False, ("backend folder not found: {} — fix it in the "
                       "Illustrate tab (or rig.local.json)".format(cwd))
    if kind == "a1111":
        from . import installer
        command += installer.ckpt_dir_args()   # self-contained vendor/models
    kw = {"cwd": cwd or None, "shell": True}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kw["start_new_session"] = True
    subprocess.Popen(command, **kw)
    return True, "launched: {}  (in {})".format(command, cwd or os.getcwd())


def ensure_up(camp, dry_run=False, on_log=print, launch_if_down=True):
    """Make the campaign's backend reachable, launching it if the rig knows
    how. Raises RuntimeError when it can't — callers surface the message."""
    backend = runner.make_backend(camp, dry_run=dry_run)
    ok, msg = backend.check()
    if ok:
        on_log("[{}] {}".format(backend.name, msg))
        return True
    if not launch_if_down:
        raise RuntimeError("[{}] {}".format(backend.name, msg))
    on_log("[{}] not reachable — launching it".format(backend.name))
    ok, msg = launch(backend.name)
    on_log(msg)
    if not ok:
        raise RuntimeError(msg)
    entry = load_rig().get(backend.name, {})
    timeout = int(entry.get("startup_timeout", 300))
    t0 = time.time()
    polls = 0
    while time.time() - t0 < timeout:
        time.sleep(POLL_SECONDS)
        ok, msg = backend.check()
        if ok:
            on_log("[{}] up after {}s — {}".format(
                backend.name, int(time.time() - t0), msg))
            return True
        polls += 1
        if polls % 4 == 0:
            on_log("[{}] still starting… {}s (its console window has the "
                   "progress)".format(backend.name, int(time.time() - t0)))
    raise RuntimeError(
        "[{}] did not come up within {}s — check its console window; if it "
        "needs longer on first boot, raise startup_timeout in rig.local.json"
        .format(backend.name, timeout))
