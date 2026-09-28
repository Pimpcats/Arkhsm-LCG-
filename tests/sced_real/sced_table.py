"""Locate SCED (Arkham Horror LCG Super Complete Edition) and assemble its
table the way SCED's build does (tests only).

SCED's repository (argonui/SCED) keeps the mod as a tree: config.json lists
the top-level objects (ObjectStates_order), objects/<Name>.<guid>.json holds
each object, and bulky fields live in side files:

  * ContainedObjects_path + ContainedObjects_order: a folder of child objects
  * States_path: {stateId: "<Name>.<guid>"} files next to the children
  * GMNotes_path / LuaScript_path / LuaScriptState_path: text files

SCED's build tool (TTSModManager) inlines those side files and bundles each
`require("x/y")` script with src/x/y.ttslua. This module does the first part
and leaves `require` to the emulator (tests/sced_real/tts_emu.lua resolves it
against src/ at run time, which is what the bundle's prelude does in TTS).

The result is written once per SCED commit as a Lua table literal (fast to
load in Lua) under .cache/sced_real/<commit>/table.lua.

SCED has no license file upstream, so this repository never contains SCED
code. Sources, first match wins:
  1. $SCED_DIR (a checkout of argonui/SCED)
  2. /home/user/argonui/sced (the session's shallow clone)
  3. .cache/sced/<PINNED> fetched with git (the pinned commit, or the default
     branch if the host refuses a fetch by hash; the commit used is recorded)
"""
import hashlib
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
PINNED = "0e12534a3dcaceba504f02678e999b727900f6dd"
REPO_URL = "https://github.com/argonui/SCED"
CACHE = os.path.join(ROOT, ".cache")
LOCAL_CLONE = "/home/user/argonui/sced"
ASSEMBLER_VERSION = "3"


def _git(*args, cwd=None, timeout=300):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def _is_sced(path):
    return bool(path) and os.path.isfile(os.path.join(path, "config.json")) \
        and os.path.isdir(os.path.join(path, "objects")) \
        and os.path.isdir(os.path.join(path, "src"))


def _commit_of(path):
    marker = os.path.join(path, ".sced_commit")
    if os.path.isfile(marker):
        return open(marker, encoding="utf-8").read().strip()
    try:
        r = _git("rev-parse", "HEAD", cwd=path, timeout=20)
        if r.returncode == 0 and os.path.isdir(os.path.join(path, ".git")):
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _fetch(dest_root):
    """Fetch SCED into .cache/sced/<commit>. Returns the folder or None."""
    dest = os.path.join(dest_root, PINNED)
    if _is_sced(dest):
        return dest
    tmp = dest + ".tmp"
    try:
        subprocess.run(["rm", "-rf", tmp], check=False)
        os.makedirs(tmp, exist_ok=True)
        if _git("init", "-q", cwd=tmp).returncode != 0:
            return None
        _git("remote", "add", "origin", REPO_URL, cwd=tmp)
        ok = _git("fetch", "-q", "--depth", "1", "origin", PINNED, cwd=tmp).returncode == 0
        if not ok:   # host refuses fetch-by-hash: take the default branch
            ok = _git("fetch", "-q", "--depth", "1", "origin", "HEAD", cwd=tmp).returncode == 0
        if not ok or _git("checkout", "-q", "FETCH_HEAD", cwd=tmp).returncode != 0:
            return None
        commit = _git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
        with open(os.path.join(tmp, ".sced_commit"), "w", encoding="utf-8") as f:
            f.write(commit + "\n")
        final = os.path.join(dest_root, commit)
        if not os.path.isdir(final):
            os.rename(tmp, final)
        if commit != PINNED:
            # record the substitution so a later run finds it under PINNED too
            with open(os.path.join(dest_root, PINNED + ".txt"), "w", encoding="utf-8") as f:
                f.write(commit + "\n")
        return final
    except (OSError, subprocess.SubprocessError):
        return None


def find_sced(allow_fetch=True):
    """(path, commit) of a usable SCED checkout, or (None, reason)."""
    candidates = [os.environ.get("SCED_DIR"), LOCAL_CLONE]
    for c in candidates:
        if _is_sced(c):
            return c, _commit_of(c)
    cache_root = os.path.join(CACHE, "sced")
    alias = os.path.join(cache_root, PINNED + ".txt")
    if os.path.isfile(alias):
        c = os.path.join(cache_root, open(alias, encoding="utf-8").read().strip())
        if _is_sced(c):
            return c, _commit_of(c)
    if _is_sced(os.path.join(cache_root, PINNED)):
        c = os.path.join(cache_root, PINNED)
        return c, _commit_of(c)
    if allow_fetch and os.environ.get("SCED_NO_FETCH") != "1":
        os.makedirs(cache_root, exist_ok=True)
        c = _fetch(cache_root)
        if c:
            return c, _commit_of(c)
    return None, "SCED not available (no checkout found and the fetch failed)"


# ------------------------------------------------------------------ assembly --

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Assembler:
    def __init__(self, sced):
        self.sced = sced
        self.objects = os.path.join(sced, "objects")

    def _side(self, base_dir, rel):
        for cand in (os.path.join(self.objects, rel), os.path.join(base_dir, rel)):
            if os.path.isfile(cand):
                return cand
        raise FileNotFoundError(rel)

    def load(self, json_path):
        base_dir = os.path.dirname(json_path)
        own = os.path.splitext(os.path.basename(json_path))[0]
        with open(json_path, encoding="utf-8") as f:
            d = json.load(f)
        for key in ("GMNotes", "LuaScript", "LuaScriptState", "XmlUI", "Description"):
            p = d.pop(key + "_path", None)
            if p:
                d[key] = _read(self._side(base_dir, p))
        cpath = d.pop("ContainedObjects_path", None)
        order = d.pop("ContainedObjects_order", None)
        if cpath:
            folder = os.path.join(base_dir, cpath)
            if order is None:
                order = sorted(n[:-5] for n in os.listdir(folder) if n.endswith(".json"))
            d["ContainedObjects"] = [self.load(os.path.join(folder, n + ".json")) for n in order]
        spath = d.pop("States_path", None)
        if spath:
            states = {}
            for sid, name in spath.items():
                for folder in (os.path.join(base_dir, own), base_dir, os.path.join(base_dir, cpath or own)):
                    f = os.path.join(folder, name + ".json")
                    if os.path.isfile(f):
                        states[sid] = self.load(f)
                        break
                else:
                    raise FileNotFoundError(name)
            d["States"] = states
        return d

    def table(self):
        cfg = json.load(open(os.path.join(self.sced, "config.json"), encoding="utf-8"))
        objs = [self.load(os.path.join(self.objects, n + ".json")) for n in cfg["ObjectStates_order"]]
        state = ""
        p = cfg.get("LuaScriptState_path")
        if p:
            for cand in (os.path.join(self.objects, p), os.path.join(self.sced, p)):
                if os.path.isfile(cand):
                    state = _read(cand)
        snaps = []
        sp = os.path.join(self.sced, "modsettings", "SnapPoints.json")
        if os.path.isfile(sp):
            snaps = json.load(open(sp, encoding="utf-8"))
        return {"SaveName": cfg.get("SaveName", ""), "LuaScript": cfg.get("LuaScript", ""),
                "LuaScriptState": state, "ObjectStates": objs, "SnapPoints": snaps}


def _lua_str(s):
    out = ['"']
    for ch in s.encode("utf-8"):
        if ch == 0x22:
            out.append('\\"')
        elif ch == 0x5C:
            out.append("\\\\")
        elif ch == 0x0A:
            out.append("\\n")
        elif ch == 0x0D:
            out.append("\\r")
        elif ch < 0x20 or ch == 0x7F:
            out.append("\\%03d" % ch)
        else:
            out.append(chr(ch) if ch < 0x80 else "\\%03d" % ch)
    out.append('"')
    return "".join(out)


def to_lua(v, out):
    """Append a Lua literal for JSON value v to the list out."""
    if v is None:
        out.append("nil")
    elif v is True:
        out.append("true")
    elif v is False:
        out.append("false")
    elif isinstance(v, (int, float)):
        out.append(repr(v) if isinstance(v, float) else str(v))
    elif isinstance(v, str):
        out.append(_lua_str(v))
    elif isinstance(v, list):
        out.append("{")
        for x in v:
            to_lua(x, out)
            out.append(",")
        out.append("}")
    elif isinstance(v, dict):
        out.append("{")
        for k, x in v.items():
            if x is None:
                continue
            out.append("[")
            out.append(_lua_str(str(k)))
            out.append("]=")
            to_lua(x, out)
            out.append(",")
        out.append("}")
    else:
        raise TypeError(type(v))


def build_table(sced, commit):
    """Assemble once per (commit, assembler version); returns the .lua path."""
    key = hashlib.sha1((commit + ASSEMBLER_VERSION + sced).encode()).hexdigest()[:10]
    out_dir = os.path.join(CACHE, "sced_real", commit[:12] + "-" + key)
    out = os.path.join(out_dir, "table.lua")
    if os.path.isfile(out):
        return out
    os.makedirs(out_dir, exist_ok=True)
    t = Assembler(sced).table()
    t["commit"] = commit
    parts = ["return "]
    to_lua(t, parts)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="latin-1") as f:
        f.write("".join(parts))
    os.replace(tmp, out)
    return out


if __name__ == "__main__":
    path, commit = find_sced()
    if not path:
        raise SystemExit(commit)
    print(path, commit, build_table(path, commit))
