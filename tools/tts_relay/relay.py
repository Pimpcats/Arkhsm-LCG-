#!/usr/bin/env python3
"""THE STILL HOUR — TTS relay: automated in-game testing on the owner's PC.

Runs next to an open Tabletop Simulator. Every time a new build is pushed to the
watched branch it:

  1. pulls that commit into its own private clone (never the owner's checkout)
  2. sends the job's TTS objects + tools/tts_relay/ingame_runner.lua into the
     running game through TTS's External Editor API (localhost 39999)
  3. listens on localhost 39998 for print/error/result messages from TTS and
     screenshots the TTS window when the runner asks
  4. commits the log, results and screenshots to the results branch and pushes

So the build author (working remotely, without access to this PC) reads real
in-game results from GitHub and iterates. Only Lua from the watched commit is
ever sent to TTS, and TTS Lua cannot touch files on this machine. The relay
never executes anything from the repository on this computer itself.

Usage (Windows: double-click "Start TTS Relay.bat" in the repo folder):
    python tools/tts_relay/relay.py              watch the branch, test each push
    python tools/tts_relay/relay.py --once       test the current commit, then exit
    python tools/tts_relay/relay.py --help       all options

Stdlib only. Screenshots additionally need Pillow (already installed by the
CardForge launcher); without it the run continues without screenshots.
"""
import argparse
import datetime as dt
import json
import os
import platform
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time

DEFAULT_REMOTE = "https://github.com/Pimpcats/Arkhsm-LCG-.git"
DEFAULT_BRANCH = "claude/campaign-art-tts-testing-w2yabf"
RESULTS_BRANCH = "tts-results"
JOB_FILE = "tools/tts_relay/job.json"
TAG = "StillHourRelay"
KEEP_RUNS = 30

HERE = os.path.dirname(os.path.abspath(__file__))


def say(msg):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    line = "[{}] {}".format(stamp, msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:          # legacy Windows console code page
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)


# ----------------------------------------------------------------------- git --

class GitError(RuntimeError):
    pass


def git(*args, cwd=None, check=True):
    p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise GitError("git {} failed: {}".format(" ".join(args), (p.stderr or p.stdout).strip()))
    return p


def remote_sha(remote, branch):
    out = git("ls-remote", remote, "refs/heads/" + branch).stdout.split()
    return out[0] if out else None


def sync_repo(path, remote, branch):
    """Private clone at `path`, hard-reset to the tip of `branch`."""
    if not os.path.isdir(os.path.join(path, ".git")):
        say("cloning {} ({}) ...".format(remote, branch))
        git("clone", "--branch", branch, "--single-branch", "--depth", "20", remote, path)
    else:
        git("fetch", "--depth", "20", "origin", branch, cwd=path)
        git("reset", "--hard", "FETCH_HEAD", cwd=path)
    return git("rev-parse", "HEAD", cwd=path).stdout.strip()


def ensure_results_repo(path, remote):
    if not os.path.isdir(os.path.join(path, ".git")):
        p = git("clone", "--branch", RESULTS_BRANCH, "--single-branch", remote, path, check=False)
        if p.returncode != 0:           # first run ever: start the orphan branch
            if os.path.isdir(path):
                shutil.rmtree(path)
            os.makedirs(path)
            git("init", cwd=path)
            git("checkout", "--orphan", RESULTS_BRANCH, cwd=path)
            git("remote", "add", "origin", remote, cwd=path)
    # commits here are the relay's, not the owner's
    git("config", "user.name", "Still Hour TTS Relay", cwd=path)
    git("config", "user.email", "tts-relay@users.noreply.github.com", cwd=path)
    readme = os.path.join(path, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write("# TTS relay results\n\nWritten by tools/tts_relay/relay.py. "
                    "`latest.json` is the newest run; `runs/<id>/` holds each run's "
                    "log, results and screenshots.\n")


def publish_results(path, remote, run_dir_name, summary):
    """Commit + push one run. Returns True when it reached GitHub."""
    runs = os.path.join(path, "runs")
    for old in sorted(os.listdir(runs))[:-KEEP_RUNS]:
        shutil.rmtree(os.path.join(runs, old), ignore_errors=True)
    git("add", "-A", cwd=path)
    msg = "TTS run {}: {} passed, {} failed ({})".format(
        run_dir_name, summary.get("passed", 0), summary.get("failed", 0), summary["verdict"])
    if git("diff", "--cached", "--quiet", cwd=path, check=False).returncode == 0:
        return True
    git("commit", "-q", "-m", msg, cwd=path)
    for attempt in range(4):
        has_remote = git("ls-remote", "--exit-code", "origin", "refs/heads/" + RESULTS_BRANCH,
                         cwd=path, check=False).returncode == 0
        if has_remote:
            git("pull", "-q", "--rebase", "origin", RESULTS_BRANCH, cwd=path, check=False)
        p = git("push", "-q", "origin", "HEAD:refs/heads/" + RESULTS_BRANCH, cwd=path, check=False)
        if p.returncode == 0:
            return True
        say("push failed ({}), retrying: {}".format(attempt + 1, p.stderr.strip()[:200]))
        time.sleep(2 ** (attempt + 1))
    return False


# ----------------------------------------------------------------------- TTS --

class EditorListener(threading.Thread):
    """Stands in for an external script editor: TTS connects to 127.0.0.1:port
    and writes one JSON message per connection."""

    def __init__(self, port):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.bind(("127.0.0.1", port))
        except OSError as e:
            raise SystemExit(
                "Port {} is already in use ({}). Another TTS script editor (Atom or the "
                "VS Code Tabletop Simulator extension) is probably running; close it and "
                "start the relay again.".format(port, e))
        self.sock.listen(16)

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn):
        """Parse messages as bytes arrive: works whether TTS sends one message
        per connection (what it does today) or keeps the connection open."""
        dec = json.JSONDecoder()
        raw = b""
        with conn:
            conn.settimeout(600)
            while True:
                try:
                    b = conn.recv(65536)
                except OSError:
                    b = b""
                raw += b
                # never split a multi-byte character: hold back an incomplete tail
                cut = len(raw)
                for back in range(0, 4):
                    try:
                        text = raw[:len(raw) - back].decode("utf-8")
                        cut = len(raw) - back
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text, cut = raw.decode("utf-8", "replace"), len(raw)
                tail = raw[cut:]
                i = 0
                while True:
                    while i < len(text) and text[i].isspace():
                        i += 1
                    if i >= len(text):
                        break
                    try:
                        obj, i = dec.raw_decode(text, i)
                    except ValueError:
                        break
                    self.q.put(obj)
                raw = text[i:].encode("utf-8") + tail
                if not b:
                    if raw.strip():
                        self.q.put({"messageID": -1, "raw": raw[:500].decode("utf-8", "replace")})
                    return

    def drain(self):
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return


def tts_send(port, message, timeout=10):
    data = json.dumps(message).encode("utf-8")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(data)


def tts_reachable(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            return True
    except OSError:
        return False


# --------------------------------------------------------------- screenshots --

def screenshot(dest):
    """Capture only the TTS window (brought to the front). Returns a note on
    failure instead of raising: screenshots are evidence, not a gate."""
    if platform.system() != "Windows":
        return "screenshots are only taken on Windows"
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Pillow not installed: python -m pip install Pillow"
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    hwnd = user32.FindWindowW(None, "Tabletop Simulator")
    if not hwnd:
        return "Tabletop Simulator window not found"
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    box = (rect.left, rect.top, rect.right, rect.bottom)
    if box[2] - box[0] < 100 or box[3] - box[1] < 100:
        return "Tabletop Simulator window is too small to capture"
    img = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    if img.width > 1600:
        img = img.resize((1600, round(img.height * 1600 / img.width)))
    img.save(dest, "JPEG", quality=80)
    return None


# ----------------------------------------------------------------------- job --

def lua_long_string(s):
    level = 0
    while ("]" + "=" * level + "]") in s:
        level += 1
    eq = "=" * level
    # a newline right after the opening bracket is dropped by Lua, so the JSON
    # (which never starts with a newline) goes in verbatim
    return "[" + eq + "[\n" + s + "]" + eq + "]"


def lua_quote(s):
    """Lua 5.2 (TTS's MoonSharp) string literal. Non-ASCII passes through as
    UTF-8: 5.2 has no \\u escapes, so json.dumps() output would not parse."""
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return '"' + out + '"'


def load_payloads(repo, job):
    """Each job payload is a dist/ file: a TTS save (ObjectStates) or one
    object. Every top-level object is tagged so the runner can clean it up."""
    out = []
    for p in job["payloads"]:
        data = json.load(open(os.path.join(repo, p["file"]), encoding="utf-8"))
        objs = data["ObjectStates"] if "ObjectStates" in data else [data]
        for i, o in enumerate(objs):
            o = dict(o)
            tags = list(o.get("Tags") or [])
            if TAG not in tags:
                tags.append(TAG)
            o["Tags"] = tags
            name = "{}#{} {}".format(os.path.basename(p["file"]), i, o.get("Nickname") or o.get("Name"))
            out.append({"name": name, "json": json.dumps(o, ensure_ascii=False)})
    return out


def build_chunk(repo, job, run_id):
    payloads = load_payloads(repo, job)
    runner = open(os.path.join(repo, job["runner"]), encoding="utf-8").read()
    parts = ["local RELAY = {{ run = {}, pause = {}, payloads = {{".format(
        lua_quote(run_id), float(job.get("screenshot_pause_s", 2)))]
    for p in payloads:
        parts.append("  {{ name = {}, json = {} }},".format(lua_quote(p["name"]), lua_long_string(p["json"])))
    parts.append("} }")
    return "\n".join(parts) + "\n" + runner, len(payloads)


def run_job(repo, sha, branch, args, listener, run_dir):
    job = json.load(open(os.path.join(repo, JOB_FILE), encoding="utf-8"))
    run_id = os.path.basename(run_dir)
    os.makedirs(run_dir, exist_ok=True)
    shots = os.path.join(run_dir, "screenshots")
    log_lines, checks, errors, notes, screenshots = [], [], [], [], []
    summary = {"run": run_id, "commit": sha, "branch": branch,
               "started": dt.datetime.utcnow().isoformat() + "Z",
               "host": platform.platform(), "passed": 0, "failed": 0}

    def log(kind, text):
        log_lines.append("{} {:5} {}".format(dt.datetime.utcnow().strftime("%H:%M:%S.%f")[:-3], kind, text))

    chunk, n = build_chunk(repo, job, run_id)
    log("relay", "sending runner + {} object(s), {} KB".format(n, len(chunk) // 1024))
    listener.drain()
    tts_send(args.tts_port, {"messageID": 3, "guid": "-1", "script": chunk})

    timeout = float(job.get("timeout_s", 240))
    deadline = time.time() + timeout
    last_activity = time.time()
    done = None
    while time.time() < deadline:
        try:
            m = listener.q.get(timeout=1)
        except queue.Empty:
            # a Lua error with no further output means the runner died
            if errors and not checks and time.time() - last_activity > 15:
                break
            continue
        last_activity = time.time()
        mid = m.get("messageID")
        if mid == 2:
            log("print", m.get("message", ""))
        elif mid == 3:
            err = (m.get("errorMessagePrefix") or "") + str(m.get("error"))
            errors.append({"guid": m.get("guid"), "error": err})
            log("ERROR", err)
        elif mid == 4:
            c = m.get("customMessage") or {}
            if c.get("run") != run_id:
                log("other", json.dumps(c)[:300])
                continue
            kind = c.get("relay")
            if kind == "result":
                checks.append({"name": c.get("name"), "ok": bool(c.get("ok")),
                               "detail": c.get("detail")})
            elif kind == "info":
                notes.append(c.get("message"))
            elif kind == "screenshot":
                os.makedirs(shots, exist_ok=True)
                fname = "{:02d}_{}.jpg".format(len(screenshots) + 1,
                                               "".join(ch if ch.isalnum() else "_" for ch in
                                                       str(c.get("name")))[:60])
                problem = None if args.no_screenshots else screenshot(os.path.join(shots, fname))
                if args.no_screenshots:
                    problem = "disabled with --no-screenshots"
                if problem:
                    log("relay", "screenshot skipped: " + problem)
                else:
                    screenshots.append("screenshots/" + fname)
            elif kind == "done":
                done = c
                deadline = min(deadline, time.time() + 2)   # stragglers from other connections
        elif mid == 5:
            log("return", json.dumps(m.get("returnValue"))[:300])
        elif mid == 1:
            notes.append("TTS loaded a game while the run was in progress")
            log("relay", "TTS reloaded the game during the run")
        elif mid == -1:
            log("relay", "unparseable message: " + m.get("raw", ""))

    passed = sum(1 for c in checks if c["ok"])
    failed = sum(1 for c in checks if not c["ok"])
    if done is None:
        verdict = "incomplete"
    elif failed or errors:
        verdict = "fail"
    else:
        verdict = "pass"
    summary.update({"finished": dt.datetime.utcnow().isoformat() + "Z", "verdict": verdict,
                    "passed": passed, "failed": failed, "lua_errors": errors,
                    "checks": checks, "notes": notes, "screenshots": screenshots,
                    "timed_out": done is None})
    with open(os.path.join(run_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(os.path.join(run_dir, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    return summary


# ---------------------------------------------------------------------- main --

def default_workdir():
    return os.path.join(os.path.expanduser("~"), "StillHourRelay")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Test each pushed Still Hour build inside a running TTS.")
    ap.add_argument("--branch", default=DEFAULT_BRANCH, help="branch to watch (default: %(default)s)")
    ap.add_argument("--remote", default=DEFAULT_REMOTE, help="repository URL")
    ap.add_argument("--workdir", default=default_workdir(), help="relay's own folder (default: %(default)s)")
    ap.add_argument("--interval", type=int, default=60, help="seconds between checks for a new push")
    ap.add_argument("--once", action="store_true", help="test the current commit once and exit")
    ap.add_argument("--no-push", action="store_true", help="keep results local, do not push")
    ap.add_argument("--no-screenshots", action="store_true", help="never capture the screen")
    ap.add_argument("--tts-port", type=int, default=39999, help=argparse.SUPPRESS)
    ap.add_argument("--editor-port", type=int, default=39998, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if not shutil.which("git"):
        raise SystemExit("Git was not found. Install it from https://git-scm.com and run this again.")
    os.makedirs(args.workdir, exist_ok=True)
    repo = os.path.join(args.workdir, "repo")
    results = os.path.join(args.workdir, "results")
    state_path = os.path.join(args.workdir, "state.json")
    try:
        state = json.load(open(state_path, encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    listener = EditorListener(args.editor_port)
    listener.start()
    say("TTS relay started. Watching '{}'. Leave Tabletop Simulator open with a game loaded.".format(args.branch))
    say("Results go to the '{}' branch. Ctrl+C to stop.".format(RESULTS_BRANCH))

    waiting_note = None
    while True:
        try:
            sha = remote_sha(args.remote, args.branch)
            if sha is None:
                raise GitError("branch '{}' not found on {}".format(args.branch, args.remote))
            if args.once or sha != state.get("last_tested"):
                if not tts_reachable(args.tts_port):
                    if waiting_note != "tts":
                        say("new build {} is waiting: Tabletop Simulator is not reachable. "
                            "Open TTS and load a game (SCED).".format(sha[:7]))
                        waiting_note = "tts"
                    if args.once:
                        return 2
                else:
                    waiting_note = None
                    say("testing {} in TTS ...".format(sha[:7]))
                    tested = sync_repo(repo, args.remote, args.branch)
                    ensure_results_repo(results, args.remote)
                    run_name = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "_" + tested[:7]
                    run_dir = os.path.join(results, "runs", run_name)
                    try:
                        summary = run_job(repo, tested, args.branch, args, listener, run_dir)
                    except (GitError, OSError):
                        raise
                    except Exception as e:      # bad job file, bad payload JSON, ...
                        os.makedirs(run_dir, exist_ok=True)
                        summary = {"run": run_name, "commit": tested, "branch": args.branch,
                                   "verdict": "relay_error", "error": repr(e), "passed": 0,
                                   "failed": 0, "lua_errors": [], "checks": []}
                        with open(os.path.join(run_dir, "results.json"), "w", encoding="utf-8") as f:
                            json.dump(summary, f, indent=2)
                    with open(os.path.join(results, "latest.json"), "w", encoding="utf-8") as f:
                        json.dump(summary, f, indent=2, ensure_ascii=False)
                    if summary.get("error"):
                        say("relay error: " + summary["error"])
                    say("result: {} ({} passed, {} failed, {} Lua error(s))".format(
                        summary["verdict"].upper(), summary["passed"], summary["failed"],
                        len(summary["lua_errors"])))
                    for c in summary["checks"]:
                        if not c["ok"]:
                            say("  FAIL " + c["name"] + (" -- " + c["detail"] if c.get("detail") else ""))
                    if not args.no_push:
                        pushed = publish_results(results, args.remote, run_name, summary)
                        say("results pushed to GitHub" if pushed else
                            "could not push results; they are saved in " + run_dir)
                    state["last_tested"] = tested
                    with open(state_path, "w", encoding="utf-8") as f:
                        json.dump(state, f)
                    if args.once:
                        return 0 if summary["verdict"] == "pass" else 1
        except (GitError, OSError) as e:
            say("problem: {} (retrying)".format(e))
            if args.once:
                return 3
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("relay stopped.")
