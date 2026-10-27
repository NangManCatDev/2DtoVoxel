"""2DtoVoxel local web UI. Start it in the workspace folder (the one with models/ and
reference/): `voxtool ui`, `py -m voxtool ui`, `py -m ui` or 2DtoVoxel.bat.

Stdlib-only HTTP server bound to 127.0.0.1. Every POST must carry the per-launch
token embedded in the page, and the Host header must be local, so other web
pages can't drive the server (it can start Claude runs that write files).
"""
from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import re
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import numpy as np

from ..__main__ import find_magicavoxel, open_in_magicavoxel, screenshot_magicavoxel
from ..vox_io import merge_models, read_vox
from .i18n import UserError, pick_lang
from .jobs import ROOT, JobManager, find_claude, generate_prompt, refine_prompt, voxtool_command

STATIC = Path(__file__).resolve().parent / "static"
for _d in ("models", "reference", "output"):
    (ROOT / _d).mkdir(exist_ok=True)

TOKEN = secrets.token_urlsafe(24)
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
SERVE_DIRS = ("output", "reference")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
        ".bmp": "image/bmp", ".svg": "image/svg+xml", ".vox": "application/octet-stream",
        ".py": "text/plain; charset=utf-8", ".glb": "model/gltf-binary", ".obj": "text/plain; charset=utf-8",
        ".mtl": "text/plain; charset=utf-8", ".ply": "application/octet-stream"}
EXPORT_DIRS = ("sprites", "export", "variants")


def file_url(p: Path) -> str:
    rel = p.resolve().relative_to(ROOT).as_posix()
    return "/files/" + quote(rel) + f"?t={int(p.stat().st_mtime)}"


JOBS = JobManager(file_url)


# ---------------------------------------------------------------- model info

def parse_script(path: Path) -> dict:
    """Reads NAME / REFERENCE / VIEW and the docstring without executing the script."""
    info = {"name": path.stem, "reference": None, "view": None, "doc": ""}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return info
    info["doc"] = ast.get_docstring(tree) or ""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            if key in ("NAME", "REFERENCE", "VIEW"):
                try:
                    info[key.lower()] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return info


def model_paths(slug: str) -> dict:
    script = ROOT / "models" / f"{slug}.py"
    info = parse_script(script)
    out = ROOT / "output" / info["name"]
    n = info["name"]
    return {"script": script, "info": info, "dir": out, "vox": out / f"{n}.vox",
            "iso": out / f"{n}_iso.png", "sheet": out / f"{n}_sheet.png", "compare": out / f"{n}_compare.png",
            "angles": out / f"{n}_angles.png", "score": out / f"{n}_score.png", "fit": out / f"{n}_fit.png",
            "scores": out / f"{n}_scores.jsonl"}


def list_models() -> list[dict]:
    items = []
    for script in (ROOT / "models").glob("*.py"):
        if script.name.startswith("_"):
            continue
        mp = model_paths(script.stem)
        mtimes = [p.stat().st_mtime for p in (script, mp["vox"]) if p.exists()]
        running = JOBS.running_for(script.stem)
        items.append({"slug": script.stem, "name": mp["info"]["name"],
                      "title": mp["info"]["doc"].splitlines()[0] if mp["info"]["doc"] else "",
                      "thumb": file_url(mp["iso"]) if mp["iso"].exists() else None,
                      "has_vox": mp["vox"].exists(), "mtime": max(mtimes) if mtimes else 0,
                      "running": running.id if running else None})
    # jobs that are creating a model whose script doesn't exist yet
    known = {m["slug"] for m in items}
    for j in JOBS.jobs.values():
        if j.status == "running" and j.name not in known:
            items.append({"slug": j.name, "name": j.name, "title": "", "pending": True, "thumb": None,
                          "has_vox": False, "mtime": j.started, "running": j.id})
            known.add(j.name)
    return sorted(items, key=lambda m: m["mtime"], reverse=True)


_stats_cache: dict[str, tuple[float, dict]] = {}


def vox_stats(vox: Path) -> dict | None:
    if not vox.exists():
        return None
    mt = vox.stat().st_mtime
    hit = _stats_cache.get(str(vox))
    if hit and hit[0] == mt:
        return hit[1]
    scene = read_vox(str(vox))
    v = merge_models(scene)
    st = {"size": list(v.shape), "voxels": int((v > 0).sum()), "colors": int(len(np.unique(v[v > 0]))),
          "models": len(scene.models), "bytes": vox.stat().st_size}
    _stats_cache[str(vox)] = (mt, st)
    return st


def model_detail(slug: str) -> dict | None:
    mp = model_paths(slug)
    running = JOBS.running_for(slug)
    if not mp["script"].exists():
        if running:
            return {"slug": slug, "name": slug, "pending": True, "running": running.id}
        return None
    info = mp["info"]
    ref = info["reference"]
    ref_path = ROOT / ref if ref else None
    imgs = {k: file_url(mp[k]) for k in ("compare", "score", "sheet", "iso", "angles", "fit") if mp[k].exists()}
    # copies of MagicaVoxel-edited files that a build would otherwise have overwritten
    backups = sorted(mp["dir"].glob(f"{info['name']}_edited_*.vox"), reverse=True)
    history = []
    if mp["scores"].exists():
        for line in mp["scores"].read_text(encoding="utf-8").splitlines()[-60:]:
            try:
                r = json.loads(line)
                history.append({"t": r["t"], "iou": r["iou"], "delta_e": r["delta_e"]})
            except (ValueError, KeyError):
                pass
    exports = {}
    for sub in EXPORT_DIRS:
        d = mp["dir"] / sub
        if d.is_dir():
            files = sorted((f for f in d.iterdir() if f.is_file()), key=lambda f: f.name)
            exports[sub] = [{"name": f.name, "url": file_url(f)} for f in files]
    return {"slug": slug, "name": info["name"], "doc": info["doc"], "view": info["view"],
            "reference": ref, "reference_url": file_url(ref_path) if ref_path and ref_path.exists() else None,
            "script": mp["script"].read_text(encoding="utf-8"),
            "script_path": str(mp["script"]), "images": imgs,
            "vox_url": file_url(mp["vox"]) if mp["vox"].exists() else None,
            "backups": [{"name": b.name, "url": file_url(b)} for b in backups],
            "score_history": history, "exports": exports, "last_session": JOBS.last_session(slug),
            "stats": vox_stats(mp["vox"]), "running": running.id if running else None,
            "jobs": [j for j in JOBS.list() if j["name"] == slug][:10]}


def voxel_payload(slug: str) -> dict | None:
    """Surface voxels (x, y, z, color) as base64 for the 3D viewer."""
    mp = model_paths(slug)
    if not mp["vox"].exists():
        return None
    scene = read_vox(str(mp["vox"]))
    v = merge_models(scene)
    filled = v > 0
    pad = np.pad(filled, 1)
    interior = (pad[2:, 1:-1, 1:-1] & pad[:-2, 1:-1, 1:-1] & pad[1:-1, 2:, 1:-1] &
                pad[1:-1, :-2, 1:-1] & pad[1:-1, 1:-1, 2:] & pad[1:-1, 1:-1, :-2])
    xs, ys, zs = np.nonzero(filled & ~interior)
    quad = np.stack([xs, ys, zs, v[xs, ys, zs]], axis=1).astype(np.uint8)
    pal = ["#%02x%02x%02x" % tuple(int(c) for c in row[:3]) for row in scene.palette]
    emissive = [i for i, p in scene.materials.items() if p.get("_type") == "_emit"]
    return {"size": list(v.shape), "palette": pal, "emissive": emissive,
            "voxels": base64.b64encode(quad.tobytes()).decode("ascii"), "count": len(quad)}


def list_references() -> list[dict]:
    refs = [p for p in (ROOT / "reference").glob("*") if p.suffix.lower() in IMAGE_EXT]
    refs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"path": p.relative_to(ROOT).as_posix(), "name": p.name, "url": file_url(p)} for p in refs]


def save_reference(filename: str, data_url: str) -> dict:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", Path(filename).name).strip("._") or "reference.png"
    if Path(name).suffix.lower() not in IMAGE_EXT:
        raise UserError("not_image")
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    dst = ROOT / "reference" / name
    stem, ext = dst.stem, dst.suffix
    i = 2
    while dst.exists() and dst.read_bytes() != raw:
        dst = dst.with_name(f"{stem}_{i}{ext}")
        i += 1
    dst.parent.mkdir(exist_ok=True)
    dst.write_bytes(raw)
    return {"path": dst.relative_to(ROOT).as_posix(), "name": dst.name, "url": file_url(dst)}


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "2DtoVoxel"

    def log_message(self, fmt, *args):
        if "/api/jobs/" in self.path and self.command == "GET":
            return  # polling noise
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # -------------------------------------------------------- helpers

    @property
    def lang(self) -> str:
        return pick_lang(self.headers.get("X-Lang") or self.headers.get("Accept-Language"))

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _err(self, msg: str, code: int = 400):
        self._json({"error": msg}, code)

    def _file(self, path: Path, download: bool = False):
        if not path.is_file():
            return self._err("not found", 404)
        extra = {}
        if download:
            extra["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(path.name)}"
        self._send(200, path.read_bytes(), MIME.get(path.suffix.lower(), "application/octet-stream"), extra)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # -------------------------------------------------------- GET

    def do_GET(self):
        if not self._host_ok():
            return self._err("bad host", 403)
        url = urlparse(self.path)
        path, q = unquote(url.path), parse_qs(url.query)
        try:
            if path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", TOKEN)
                return self._send(200, html.encode("utf-8"), MIME[".html"])
            if path.startswith("/static/"):
                target = (STATIC / path[len("/static/"):]).resolve()
                if STATIC not in target.parents:
                    return self._err("forbidden", 403)
                return self._file(target)
            if path.startswith("/files/"):
                target = (ROOT / path[len("/files/"):]).resolve()
                if not any((ROOT / d).resolve() in target.parents for d in SERVE_DIRS):
                    return self._err("forbidden", 403)
                return self._file(target, download="download" in q)
            if path == "/api/status":
                return self._json({"claude": find_claude(), "magicavoxel": find_magicavoxel(), "root": str(ROOT)})
            if path == "/api/models":
                return self._json(list_models())
            if path == "/api/references":
                return self._json(list_references())
            if path == "/api/jobs":
                return self._json(JOBS.list())
            m = re.fullmatch(r"/api/jobs/([\w-]+)", path)
            if m:
                job = JOBS.get(m.group(1))
                if not job:
                    return self._err("job not found", 404)
                return self._json(job.detail(int(q.get("since", ["0"])[0])))
            m = re.fullmatch(r"/api/models/([a-z0-9_]+)", path)
            if m:
                d = model_detail(m.group(1))
                return self._json(d) if d else self._err("model not found", 404)
            m = re.fullmatch(r"/api/models/([a-z0-9_]+)/voxels", path)
            if m:
                d = voxel_payload(m.group(1))
                return self._json(d) if d else self._err("no .vox yet", 404)
            return self._err("not found", 404)
        except Exception as e:  # noqa: BLE001
            return self._err(f"{type(e).__name__}: {e}", 500)

    # -------------------------------------------------------- POST

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN:
            return self._err("forbidden", 403)
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/references":
                return self._json(save_reference(body.get("filename", ""), body.get("data", "")))
            if path == "/api/jobs":
                return self._json(self._start_job(body))
            m = re.fullmatch(r"/api/jobs/([\w-]+)/cancel", path)
            if m:
                return self._json({"ok": JOBS.cancel(m.group(1))})
            m = re.fullmatch(r"/api/jobs/([\w-]+)/restore", path)
            if m:
                return self._json(JOBS.restore(m.group(1), int(body.get("n", -1))).summary())
            m = re.fullmatch(r"/api/models/([a-z0-9_]+)/(open|shot)", path)
            if m:
                mp = model_paths(m.group(1))
                if m.group(2) == "open":
                    if not mp["vox"].exists():
                        raise UserError("no_vox")
                    try:
                        open_in_magicavoxel(str(mp["vox"]))
                    except RuntimeError:
                        raise UserError("no_magicavoxel") from None
                    return self._json({"ok": True})
                out = ROOT / "output" / "_mv" / f"{mp['info']['name']}_{int(time.time())}.png"
                try:
                    screenshot_magicavoxel(str(out))
                except RuntimeError:
                    raise UserError("shot_failed") from None
                return self._json({"url": file_url(out)})
            return self._err("not found", 404)
        except UserError as e:
            return self._json({"error": e.render(self.lang), "code": e.key}, 400)
        except ValueError as e:
            return self._err(str(e))
        except Exception as e:  # noqa: BLE001
            return self._err(f"{type(e).__name__}: {e}", 500)

    def _start_job(self, body: dict) -> dict:
        kind = body.get("kind")
        name = (body.get("name") or "").strip()
        if not NAME_RE.match(name):
            raise UserError("bad_name")
        script = ROOT / "models" / f"{name}.py"
        model = body.get("model") or ""
        if model not in ("", "opus", "sonnet", "haiku", "fable"):
            raise UserError("bad_model")
        lang = self.lang
        budget = _num(body.get("budget"), float, 0.05, 1000)
        max_builds = _num(body.get("max_builds"), int, 1, 50)
        if kind == "build":
            if not script.exists():
                raise UserError("no_script", name=name)
            return JOBS.start_build(name).summary()
        if kind in ("generate", "convert"):
            ref = body.get("reference") or ""
            if not ref.startswith("reference/") or not (ROOT / ref).is_file():
                raise UserError("no_reference")
            if script.exists() and not body.get("overwrite"):
                raise UserError("exists", name=name)
        if kind == "generate":
            prompt = generate_prompt(name, ref, body.get("notes") or "", lang, max_builds)
            return JOBS.start_claude("generate", name, prompt, model, {"reference": ref, "lang": lang},
                                     budget=budget, max_builds=max_builds).summary()
        if kind == "convert":
            depth = _num(body.get("depth"), int, 1, 32) or 4
            args = ["extrude", ref, "--name", name, "--depth", str(depth)] + (["--inflate"] if body.get("inflate") else [])
            return JOBS.start_voxtool("convert", name, args, {"reference": ref, "depth": depth,
                                                              "inflate": bool(body.get("inflate"))}).summary()
        if kind == "refine":
            if not script.exists():
                raise UserError("no_script", name=name)
            notes = (body.get("notes") or "").strip()
            if not notes:
                raise UserError("no_request")
            ref = parse_script(script)["reference"]
            prompt = refine_prompt(name, ref, notes, lang, max_builds)
            resume = JOBS.last_session(name) if body.get("resume") else None
            return JOBS.start_claude("refine", name, prompt, model, {"request": notes, "lang": lang},
                                     budget=budget, max_builds=max_builds, resume=resume).summary()
        if kind == "export":
            if not script.exists():
                raise UserError("no_script", name=name)
            fmt = body.get("format")
            if fmt == "sprites":
                dirs = _num(body.get("dirs"), int, 1, 32) or 8
                args = ["sprites", f"models/{name}.py", "--dirs", str(dirs)]
            elif fmt in ("glb", "obj", "ply"):
                args = ["export", f"models/{name}.py", "--format", fmt]
            else:
                raise UserError("bad_format")
            return JOBS.start_voxtool("export", name, args, {"format": fmt}).summary()
        raise UserError("bad_kind")


def _num(value, cast, lo, hi):
    """Optional number from a form field, clamped; empty -> None."""
    if value in (None, ""):
        return None
    try:
        return min(max(cast(value), lo), hi)
    except (TypeError, ValueError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ui", description="2DtoVoxel web UI")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    class Server(ThreadingHTTPServer):
        # On Windows SO_REUSEADDR lets a second server bind a port that is already in
        # use, so a second launch would silently share 8765 with the first one.
        allow_reuse_address = os.name != "nt"

    srv = None
    for port in range(a.port, a.port + 20):
        try:
            srv = Server(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        sys.exit(f"No free port in {a.port}-{a.port + 19}.")
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"2DtoVoxel UI: {url}")
    print(f"  workspace   : {ROOT}")
    print(f"  Claude Code : {find_claude() or 'NOT FOUND - set CLAUDE_CLI'}")
    print(f"  voxtool cmd : {voxtool_command()}  (what Claude jobs are allowed to run)")
    print(f"  MagicaVoxel : {find_magicavoxel() or 'not found (optional) - set MAGICAVOXEL_EXE'}")
    print("  Stop with Ctrl+C or by closing this window.")
    if not a.no_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for j in JOBS.jobs.values():
            if j.status == "running":
                JOBS.cancel(j.id)
        srv.server_close()
