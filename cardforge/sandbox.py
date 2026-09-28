"""Run a selftest against a throwaway copy of the repository.

The CardForge selftests drive the real app: they rewrite campaign files,
rebuild dist/, install stub backends into vendor/ and wipe out/, se/ and
art/faces. Pointed at the working checkout that would dirty tracked files and
could cost the owner real work, so each selftest calls `enter()` first: it
copies the repository (minus git metadata and machine-local output) into a
temporary folder, re-runs the same script from the copy, and deletes the copy
afterwards, whether the run passes, fails, crashes or is interrupted.

Every path in CardForge and the pipeline is derived from the running file's
location, so the copy is fully self-contained and the checkout is never
touched. Set CARDFORGE_SANDBOX_KEEP=1 to keep the copy for debugging.
"""
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile

ENV = "CARDFORGE_SANDBOX"

# Machine-local or generated trees a selftest must start without (a fresh
# clone has none of them). A test that needs one creates it inside the copy.
SKIP_TOP = {".git", ".claude", "out", "state", "art", "se", "vendor"}
SKIP_ANY = ("__pycache__", ".pytest_cache", "*.pretest-backup", "*.pretest-copy",
            "*.pyc")
SKIP_FILES = {os.path.join("pipeline", "art_urls.json"), "rig.local.json"}


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def active():
    """True inside the temporary copy."""
    return bool(os.environ.get(ENV))


def _ignore(root):
    def ignore(directory, names):
        rel = os.path.relpath(directory, root)
        out = set()
        for n in names:
            path = n if rel == "." else os.path.join(rel, n)
            if rel == "." and n in SKIP_TOP:
                out.add(n)
            elif any(fnmatch.fnmatch(n, p) for p in SKIP_ANY):
                out.add(n)
            elif path in SKIP_FILES:
                out.add(n)
        return out
    return ignore


def enter(script):
    """Re-run `script` inside a temporary copy of the repository and exit
    with its status. Returns immediately (doing nothing) inside the copy."""
    if active():
        return
    root = repo_root()
    tmp = tempfile.mkdtemp(prefix="cardforge-selftest-")
    dest = os.path.join(tmp, "repo")
    rc = 1
    try:
        shutil.copytree(root, dest, ignore=_ignore(root), symlinks=True)
        rel = os.path.relpath(os.path.abspath(script), root)
        env = dict(os.environ, **{ENV: dest})
        env.pop("PYTHONPATH", None)          # never import the checkout's modules
        print("selftest sandbox: {} (the checkout is not touched)".format(dest),
              flush=True)
        rc = subprocess.call([sys.executable, os.path.join(dest, rel)] + sys.argv[1:],
                             cwd=dest, env=env)
    except KeyboardInterrupt:
        rc = 130
    finally:
        if os.environ.get("CARDFORGE_SANDBOX_KEEP"):
            print("selftest sandbox kept: " + dest)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(rc)
