"""Download and prepare every asset a set of table snapshots needs (assistant tool).

    python3 tools/godot_table/fetch_assets.py --snapshots <dir> [--save <SCED save .json>]

Reads the snapshot JSON files that tests/sced_real/run.py --snapshots wrote,
collects every URL they reference (card sheets, tile/token images, meshes,
Unity asset bundles, PDFs, decals) plus the save's sky panorama and Global XML
UI images, and prepares them for tools/godot_table (Godot cannot read Unity
bundles or crop card sheets by itself):

  * raw downloads:  .cache/godot_assets/raw/<sha1(url)>
  * images:         .cache/godot_assets/png/<sha1>.png (RGBA, longest side <= 4096)
  * card faces/backs cropped from deck sheets (row-major CardID % 100 cell of a
    NumWidth x NumHeight grid): .cache/godot_assets/crops/<sha1>_<W>x<H>_<i>.png
  * OBJ meshes:     .cache/godot_assets/mesh/<sha1>.obj
  * asset bundles (UnityPy): .cache/godot_assets/bundle/<sha1>/parts.json with
    one OBJ + textures per mesh renderer and its transform in Godot space
  * PDFs: first page as PNG
  * manifest: .cache/godot_assets/manifest.json (url -> files, sizes, failures)

Downloads run 8 at a time with retries; failures are recorded, never fatal.
Nothing here is committed (.cache/ is gitignored); no SCED or Steam asset is
ever vendored into the repository.
"""
import argparse
import concurrent.futures as cf
import glob
import hashlib
import io
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, ".cache", "godot_assets")
MAX_SIDE = 4096
CROP_MAX_H = 1024
UA = "Mozilla/5.0 (X11; Linux x86_64) godot-table-asset-cache"


def norm_url(u):
    """The URL TTS actually loads (cache hints stripped, old Steam hosts mapped)."""
    if not isinstance(u, str):
        return ""
    u = u.strip()
    for pre in ("{verifycache}", "{Unique}", "{unique}"):
        if u.startswith(pre):
            u = u[len(pre):]
    for old in ("http://cloud-3.steamusercontent.com", "https://cloud-3.steamusercontent.com",
                "http://steamusercontent-a.akamaihd.net"):
        if u.startswith(old):
            u = "https://steamusercontent-a.akamaihd.net" + u[len(old):]
    return u


def key(u):
    return hashlib.sha1(norm_url(u).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ collect --

def collect(snapshot_files, save=None):
    need = {"image": set(), "crop": set(), "mesh": set(), "bundle": set(), "pdf": set()}

    def img(u):
        u = norm_url(u)
        if u:
            need["image"].add(u)

    def card(ci):
        if not ci or not ci.get("CustomDeck"):
            return
        cd = ci["CustomDeck"]
        w, h = int(cd.get("NumWidth") or 1), int(cd.get("NumHeight") or 1)
        idx = int(ci.get("CardID") or 0) % 100
        if cd.get("FaceURL"):
            need["crop"].add((norm_url(cd["FaceURL"]), w, h, idx))
        if cd.get("BackURL"):
            if cd.get("UniqueBack"):
                need["crop"].add((norm_url(cd["BackURL"]), w, h, idx))
            else:
                img(cd["BackURL"])

    for f in snapshot_files:
        d = json.load(open(f, encoding="utf-8"))
        for o in d.get("objects", []):
            card(o.get("card"))
            dk = o.get("deck") or {}
            card(dk.get("top"))
            card(dk.get("bottom"))
            im = o.get("image") or {}
            img(im.get("ImageURL"))
            img(im.get("ImageSecondaryURL"))
            m = o.get("mesh") or {}
            if m.get("MeshURL"):
                need["mesh"].add(norm_url(m["MeshURL"]))
            img(m.get("DiffuseURL"))
            img(m.get("NormalURL"))
            b = o.get("bundle") or {}
            if b.get("AssetbundleURL"):
                need["bundle"].add(norm_url(b["AssetbundleURL"]))
            p = o.get("pdf") or {}
            if p.get("PDFUrl"):
                need["pdf"].add(norm_url(p["PDFUrl"]))
            for dc in o.get("decals") or []:
                img(((dc or {}).get("CustomDecal") or {}).get("ImageURL"))
        for dc in (d.get("global") or {}).get("decals") or []:
            img(((dc or {}).get("CustomDecal") or {}).get("ImageURL"))
    if save:
        s = json.load(open(save, encoding="utf-8"))
        img(s.get("SkyURL"))
        img(s.get("TableURL"))
        for a in s.get("CustomUIAssets") or []:
            if int(a.get("Type") or 0) == 0:     # 1 = a font asset bundle (not drawn)
                img(a.get("URL"))
    need["image"].discard("")
    return need


# ----------------------------------------------------------------- download --

def _raw_path(u):
    return os.path.join(CACHE, "raw", key(u))


def download(u, tries=3):
    """(path, None) or (None, reason); cached by URL."""
    path = _raw_path(u)
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import requests
    err = None
    for i in range(tries):
        try:
            r = requests.get(u, timeout=(20, 120), headers={"User-Agent": UA})
            if r.status_code == 200 and r.content:
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    f.write(r.content)
                os.replace(tmp, path)
                return path, None
            err = "HTTP %s" % r.status_code
            if r.status_code in (404, 403, 410):
                break
        except Exception as e:  # network errors: retry
            err = type(e).__name__ + ": " + str(e)[:200]
        time.sleep(1.5 * (i + 1))
    return None, err


# ------------------------------------------------------------------ convert --

def _open_image(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path)
    im.load()
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if ("A" in im.getbands() or "transparency" in im.info or im.mode == "P") else "RGB")
    return im


def _save_png(im, out, max_side):
    from PIL import Image
    w, h = im.size
    s = max(w, h)
    if s > max_side:
        f = max_side / s
        im = im.resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS)
    tmp = out + ".tmp.png"
    im.save(tmp, compress_level=1)
    os.replace(tmp, out)
    return im.size


def prep_image(u):
    out = os.path.join(CACHE, "png", key(u) + ".png")
    meta = out + ".json"
    if os.path.isfile(out) and os.path.isfile(meta):
        return json.load(open(meta))
    raw, err = download(u)
    if not raw:
        return {"error": err}
    try:
        im = _open_image(raw)
    except Exception as e:
        return {"error": "not an image: " + str(e)[:120]}
    w, h = im.size
    alpha = False
    if im.mode == "RGBA":
        lo, _hi = im.getchannel("A").getextrema()
        alpha = lo < 250
        if not alpha:
            im = im.convert("RGB")
    size = _save_png(im, out, MAX_SIDE)
    rec = {"file": out, "orig_size": [w, h], "size": list(size), "alpha": alpha}
    json.dump(rec, open(meta, "w"))
    return rec


def prep_sheet(u, crops):
    """crops: list of (W, H, idx) for this sheet URL -> {(W,H,idx): rec}"""
    out = {}
    todo = []
    for (w, h, i) in crops:
        p = os.path.join(CACHE, "crops", "%s_%dx%d_%d.png" % (key(u), w, h, i))
        if os.path.isfile(p) and os.path.isfile(p + ".json"):
            out[(w, h, i)] = json.load(open(p + ".json"))
        else:
            todo.append((w, h, i, p))
    if not todo:
        return out
    raw, err = download(u)
    if not raw:
        for (w, h, i, p) in todo:
            out[(w, h, i)] = {"error": err}
        return out
    try:
        im = _open_image(raw)
    except Exception as e:
        for (w, h, i, p) in todo:
            out[(w, h, i)] = {"error": "not an image: " + str(e)[:120]}
        return out
    from PIL import Image
    W, H = im.size
    for (w, h, i, p) in todo:
        cw, ch = W / w, H / h
        col, row = i % w, i // w
        if row >= h:
            row = h - 1
        box = (round(col * cw), round(row * ch), round((col + 1) * cw), round((row + 1) * ch))
        c = im.crop(box)
        if c.size[1] > CROP_MAX_H:
            f = CROP_MAX_H / c.size[1]
            c = c.resize((max(1, round(c.size[0] * f)), CROP_MAX_H), Image.LANCZOS)
        if c.mode == "RGBA" and c.getchannel("A").getextrema()[0] >= 250:
            c = c.convert("RGB")
        tmp = p + ".tmp.png"
        c.save(tmp, compress_level=1)
        os.replace(tmp, p)
        rec = {"file": p, "size": list(c.size), "sheet_size": [W, H]}
        json.dump(rec, open(p + ".json", "w"))
        out[(w, h, i)] = rec
    return out


def prep_mesh(u):
    out = os.path.join(CACHE, "mesh", key(u) + ".obj")
    if os.path.isfile(out):
        return {"file": out}
    raw, err = download(u)
    if not raw:
        return {"error": err}
    data = open(raw, "rb").read()
    head = data[:2000].decode("latin-1", "replace")
    if not any(line.startswith(("v ", "vt ", "f ", "o ", "g ", "#", "mtllib")) for line in head.splitlines()):
        return {"error": "not an OBJ"}
    with open(out, "wb") as f:
        f.write(data)
    return {"file": out}


def prep_pdf(u):
    out = os.path.join(CACHE, "png", key(u) + "_pdf0.png")
    if os.path.isfile(out) and os.path.isfile(out + ".json"):
        return json.load(open(out + ".json"))
    raw, err = download(u)
    if not raw:
        return {"error": err}
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
        doc = fitz.open(raw)
        page = doc[0]
        r = page.rect
        zoom = 1400 / max(r.width, r.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(out)
        rec = {"file": out, "size": [pix.width, pix.height], "pages": doc.page_count,
               "page_size": [r.width, r.height]}
    except Exception as e:
        return {"error": "pdf: " + str(e)[:150]}
    json.dump(rec, open(out + ".json", "w"))
    return rec


# ------------------------------------------------------------ asset bundles --

def _quat_mat(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def _trs(t):
    """4x4 (row-major) of a Unity Transform's local TRS."""
    p, q, s = t.m_LocalPosition, t.m_LocalRotation, t.m_LocalScale
    r = _quat_mat((q.x, q.y, q.z, q.w))
    m = [[r[i][0] * s.x, r[i][1] * s.y, r[i][2] * s.z, (p.x, p.y, p.z)[i]] for i in range(3)]
    m.append([0, 0, 0, 1])
    return m


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _to_godot(m):
    """Unity (left-handed) matrix -> the same transform in Godot space
    (x mirrored): M m M with M = diag(-1, 1, 1, 1). OBJ exports are already
    mirrored, so this maps OBJ-space vertices straight into Godot."""
    s = [-1, 1, 1, 1]
    g = [[m[i][j] * s[i] * s[j] for j in range(4)] for i in range(4)]
    # Godot Transform3D: basis columns x, y, z then origin
    return [g[0][0], g[1][0], g[2][0], g[0][1], g[1][1], g[2][1], g[0][2], g[1][2], g[2][2],
            g[0][3], g[1][3], g[2][3]]


def prep_bundle(u):
    d = os.path.join(CACHE, "bundle", key(u))
    parts_file = os.path.join(d, "parts.json")
    if os.path.isfile(parts_file):
        return json.load(open(parts_file))
    raw, err = download(u)
    if not raw:
        return {"error": err}
    try:
        import UnityPy
    except ImportError:
        return {"error": "UnityPy not installed (pip install UnityPy)"}
    os.makedirs(d, exist_ok=True)
    try:
        env = UnityPy.load(raw)
        objs = {o.path_id: o for o in env.objects}
        transforms = {}
        for o in env.objects:
            if o.type.name == "Transform":
                transforms[o.path_id] = o.read()

        def world(t):
            m = _trs(t)
            f = t.m_Father
            depth = 0
            while f and f.path_id and f.path_id in transforms and depth < 64:
                pt = transforms[f.path_id]
                if not (pt.m_Father and pt.m_Father.path_id):
                    break           # the prefab root: TTS puts it at the object's transform
                m = _mul(_trs(pt), m)
                f = pt.m_Father
                depth += 1
            return m

        tex_cache = {}

        def tex(pptr, tag):
            if not pptr or not pptr.path_id or pptr.path_id not in objs:
                return None
            if pptr.path_id in tex_cache:
                return tex_cache[pptr.path_id]
            t = objs[pptr.path_id].read()
            out = os.path.join(d, "tex_%s_%d.png" % (tag, len(tex_cache)))
            try:
                im = t.image
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA")
                # Unity textures are stored bottom-up; .image is already top-down
                _save_png(im, out, 2048)
                tex_cache[pptr.path_id] = out
            except Exception:
                tex_cache[pptr.path_id] = None
            return tex_cache[pptr.path_id]

        parts = []
        for o in env.objects:
            if o.type.name not in ("MeshRenderer", "SkinnedMeshRenderer"):
                continue
            rend = o.read()
            go = rend.m_GameObject.read()
            mesh = None
            if o.type.name == "SkinnedMeshRenderer":
                mesh = rend.m_Mesh.read() if rend.m_Mesh and rend.m_Mesh.path_id else None
            else:
                for c in go.m_Component:
                    comp = c.component if hasattr(c, "component") else c[1] if isinstance(c, tuple) else c
                    try:
                        if comp.type.name == "MeshFilter":
                            mf = comp.read()
                            if mf.m_Mesh and mf.m_Mesh.path_id:
                                mesh = mf.m_Mesh.read()
                    except Exception:
                        continue
            if mesh is None:
                continue
            tr = None
            for c in go.m_Component:
                comp = c.component if hasattr(c, "component") else c
                try:
                    if comp.type.name == "Transform":
                        tr = comp.read()
                except Exception:
                    continue
            obj_text = mesh.export()
            if not obj_text:
                continue
            n = len(parts)
            obj_file = os.path.join(d, "part_%d.obj" % n)
            open(obj_file, "w").write(obj_text)
            mats = []
            for mp in rend.m_Materials:
                if not mp or not mp.path_id or mp.path_id not in objs:
                    mats.append({})
                    continue
                mat = mp.read()
                rec = {"name": mat.m_Name}
                props = mat.m_SavedProperties
                for k, v in props.m_TexEnvs:
                    kn = k if isinstance(k, str) else getattr(k, "name", str(k))
                    if kn in ("_MainTex", "_BaseMap", "_BaseColorMap") and "albedo" not in rec:
                        f = tex(v.m_Texture, "albedo")
                        if f:
                            rec["albedo"] = f
                            rec["uv_scale"] = [v.m_Scale.x, v.m_Scale.y]
                            rec["uv_offset"] = [v.m_Offset.x, v.m_Offset.y]
                    elif kn in ("_BumpMap", "_NormalMap"):
                        f = tex(v.m_Texture, "normal")
                        if f:
                            rec["normal"] = f
                    elif kn in ("_EmissionMap",):
                        f = tex(v.m_Texture, "emission")
                        if f:
                            rec["emission"] = f
                for k, v in props.m_Colors:
                    kn = k if isinstance(k, str) else getattr(k, "name", str(k))
                    if kn in ("_Color", "_BaseColor"):
                        rec["color"] = [v.r, v.g, v.b, v.a]
                    elif kn == "_EmissionColor":
                        rec["emission_color"] = [v.r, v.g, v.b, v.a]
                for k, v in props.m_Floats:
                    kn = k if isinstance(k, str) else getattr(k, "name", str(k))
                    if kn in ("_Glossiness", "_Smoothness", "_Metallic", "_Mode", "_Cutoff"):
                        rec[kn.strip("_").lower()] = v
                mats.append(rec)
            parts.append({"obj": obj_file, "name": go.m_Name, "materials": mats,
                          "transform": _to_godot(world(tr)) if tr else None,
                          "active": bool(getattr(go, "m_IsActive", True)), "enabled": bool(getattr(rend, "m_Enabled", True))})
        rec = {"parts": parts}
        if not parts:
            rec["error"] = "no mesh renderers in the bundle (effects/sounds only)"
    except Exception as e:
        rec = {"error": "UnityPy: %s: %s" % (type(e).__name__, str(e)[:200])}
    json.dump(rec, open(parts_file, "w"))
    return rec


# -------------------------------------------------------------------- main --

def _run(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def fetch(snapshot_files, save=None, workers=8, log=print):
    for sub in ("raw", "png", "crops", "mesh", "bundle"):
        os.makedirs(os.path.join(CACHE, sub), exist_ok=True)
    need = collect(snapshot_files, save)
    sheets = {}
    for (u, w, h, i) in need["crop"]:
        sheets.setdefault(u, []).append((w, h, i))
    urls = set(need["image"]) | set(sheets) | need["mesh"] | need["bundle"] | need["pdf"]
    log("assets: %d urls (%d images, %d card sheets / %d cards, %d meshes, %d bundles, %d pdfs)" % (
        len(urls), len(need["image"]), len(sheets), len(need["crop"]), len(need["mesh"]), len(need["bundle"]),
        len(need["pdf"])))
    t0 = time.time()
    # downloads first (network bound, 8 at a time), then conversion (CPU bound)
    fails = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for u, (p, err) in zip(urls, ex.map(download, urls)):
            if err:
                fails[u] = err
    log("downloaded in %.1fs, %d failed" % (time.time() - t0, len(fails)))
    man = {"images": {}, "crops": {}, "meshes": {}, "bundles": {}, "pdfs": {}, "failed": dict(fails)}
    with cf.ProcessPoolExecutor(max(2, min(8, os.cpu_count() or 2))) as ex:
        fut = {}
        for u in need["image"]:
            fut[ex.submit(_run, prep_image, u)] = ("images", u)
        for u, crops in sheets.items():
            fut[ex.submit(_run, prep_sheet, u, crops)] = ("crops", u)
        for u in need["mesh"]:
            fut[ex.submit(_run, prep_mesh, u)] = ("meshes", u)
        for u in need["bundle"]:
            fut[ex.submit(_run, prep_bundle, u)] = ("bundles", u)
        for u in need["pdf"]:
            fut[ex.submit(_run, prep_pdf, u)] = ("pdfs", u)
        for f in cf.as_completed(fut):
            kind, u = fut[f]
            rec = f.result()
            if kind == "crops":
                if isinstance(rec, dict) and "error" in rec and len(rec) == 1:
                    man["failed"][u] = rec["error"]
                    continue
                for (w, h, i), r in rec.items():
                    k = "%s#%d#%d#%d" % (u, w, h, i)
                    if "error" in r:
                        man["failed"][k] = r["error"]
                    else:
                        man["crops"][k] = r
            else:
                man[kind][u] = rec
                if rec.get("error"):
                    man["failed"][u] = rec["error"]
    man["stats"] = {"urls": len(urls), "failed": len([k for k in man["failed"] if "#" not in k]),
                    "crops": len(man["crops"]), "seconds": round(time.time() - t0, 1)}
    path = os.path.join(CACHE, "manifest.json")
    json.dump(man, open(path, "w"), indent=1, sort_keys=True)
    log("prepared in %.1fs: %d images, %d card crops, %d meshes, %d bundles, %d pdfs; failures: %d" % (
        time.time() - t0, len(man["images"]), len(man["crops"]), len(man["meshes"]), len(man["bundles"]),
        len(man["pdfs"]), len(man["failed"])))
    return path, man


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", required=True, help="folder with snapshot .json files (searched recursively)")
    ap.add_argument("--save", help="the SCED save (sky panorama, Global UI images)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    files = sorted(glob.glob(os.path.join(a.snapshots, "**", "*.json"), recursive=True))
    path, man = fetch(files, a.save, a.workers)
    print(path)
    for u, e in sorted(man["failed"].items())[:40]:
        print("  failed:", u[:120], "--", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
