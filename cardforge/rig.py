"""Backend rig — where A1111/ComfyUI live on THIS machine and how to start
them, so the Studio can launch the image backend itself and wait for its API.

Config is rig.json at the repo root (machine-local; edit there or in the
Studio's Illustrate tab). The launched process gets its own console window on
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
    "a1111": {"cwd": "", "command": "webui.bat --api", "startup_timeout": 420},
    "comfy": {"cwd": "", "command": "python main.py", "startup_timeout": 300},
}


def rig_path():
    return os.path.join(runner.repo_root(), "rig.json")


def load_rig():
    cfg = {k: dict(v) for k, v in RIG_DEFAULTS.items()}
    if os.path.exists(rig_path()):
        data = json.load(open(rig_path(), encoding="utf-8"))
        for k in cfg:
            cfg[k].update(data.get(k, {}))
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
                       "tab (or rig.json)".format(kind))
    if cwd and not os.path.isdir(cwd):
        return False, ("backend folder not found: {} — fix it in the "
                       "Illustrate tab (or rig.json)".format(cwd))
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
        "needs longer on first boot, raise startup_timeout in rig.json"
        .format(backend.name, timeout))
