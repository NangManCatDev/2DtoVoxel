"""CLI. Run from the project (workspace) folder; `py -m voxtool` on Windows, `python3 -m voxtool`
elsewhere, or `voxtool` after `pip install -e .`.

  build models/<name>.py [--open] [--no-score]    script -> output/<name>/ (.vox, previews, score)
  score models/<name>.py                          measured match with REFERENCE (IoU, colour ΔE)
  fit-camera models/<name>.py [--fovs 0,25,45]    camera (VIEW) whose silhouette best fits REFERENCE
  angles models/<name>.py 30,20 42,15[,30] ...    renders az,el[,fov] next to the reference
  render <file.vox> [--az --el --fov]             preview sheet for any .vox
  open <file.vox> / shot                          open in MagicaVoxel / capture its window (Windows)
  ref grid|crop|palette|sample|cutout <img> ...   reference study tools
  compare <a.png> <b.png> ...                     side-by-side image
  extrude <img> --name N [--depth 4 --inflate]    image/pixel art -> voxels (no Claude)
  carve --front f.png [--side s.png --top t.png] --name N    silhouettes -> voxels (no Claude)
  sprites <models/x.py | x.vox> [--dirs 8]        sprite sheet + manifest.json
  export <models/x.py | x.vox> --format obj|ply|glb
  recolor <models/x.py | x.vox> (--swap name=#hex ... | --hue 30,180) [--only names]
  ui [--port 8765] [--no-browser]                 web UI
  install-skill [--dest ~/.claude/skills]         make /voxelize available in every project
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

import numpy as np

from .reftools import crop, cutout, dominant_colors, grid_overlay, sample, side_by_side, swatches
from .render import render_iso, render_sheet
from .vox_io import VoxModel, VoxScene, merge_models, read_vox, write_vox

ROOT = os.getcwd()
OUT = os.path.join(ROOT, "output")
REF_CACHE = os.path.join(OUT, "_ref")


def _stem(p: str) -> str:
    return os.path.splitext(os.path.basename(p))[0]


# ---------------------------------------------------------------- MagicaVoxel

def find_magicavoxel() -> str | None:
    env = os.environ.get("MAGICAVOXEL_EXE")
    if env and os.path.exists(env):
        return env
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        pats = ["/Applications/MagicaVoxel*.app", os.path.join(home, "Applications", "MagicaVoxel*.app"),
                os.path.join(home, "Downloads", "MagicaVoxel*", "MagicaVoxel*.app")]
    else:
        pats = [os.path.join(home, d, "MagicaVoxel*", "MagicaVoxel.exe") for d in ("Desktop", "Downloads", "")]
        pats += [r"C:\Program Files\MagicaVoxel*\MagicaVoxel.exe", r"C:\MagicaVoxel*\MagicaVoxel.exe"]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def open_in_magicavoxel(vox_path: str):
    exe = find_magicavoxel()
    if not exe:
        raise RuntimeError("MagicaVoxel not found; set MAGICAVOXEL_EXE")
    path = os.path.abspath(vox_path)
    if exe.endswith(".app"):
        subprocess.Popen(["open", "-a", exe, path])
    else:
        # MagicaVoxel resolves relative paths against its own folder, so pass an absolute path
        subprocess.Popen([exe, path], cwd=os.path.dirname(exe))
    print(f"opened in MagicaVoxel: {path}")


def screenshot_magicavoxel(out: str):
    """Saves what MagicaVoxel currently shows (to verify a file really loaded). Windows only."""
    if os.name != "nt":
        raise RuntimeError("MagicaVoxel window capture is only supported on Windows")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if os.path.isfile(out):
        os.remove(out)  # so a failed capture can't pass for a fresh one
    ps1 = os.path.join(os.path.dirname(__file__), "mv_screenshot.ps1")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1,
                        "-out", os.path.abspath(out)], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"screenshot failed (is MagicaVoxel running?)\n{r.stdout}{r.stderr}")
    print(out)


# ---------------------------------------------------------------- loading scripts / files

def load_script(path: str):
    spec = importlib.util.spec_from_file_location(_stem(path), path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, ROOT)
    spec.loader.exec_module(mod)
    return mod


def script_view(mod, key: str = "VIEW") -> dict:
    view = {"azimuth": 30.0, "elevation": 30.0, "fov": 0.0}
    view.update(getattr(mod, key, None) or getattr(mod, "VIEW", {}) or {})
    return view


@dataclass
class Target:
    name: str
    v: np.ndarray
    palette: np.ndarray
    materials: dict
    view: dict
    names: dict          # palette name -> index ({} for plain .vox files)

    @property
    def emissive(self) -> set[int]:
        return {i for i, p in self.materials.items() if p.get("_type") == "_emit"}


def load_target(path: str) -> Target:
    """A model script (built now) or a .vox file."""
    if path.endswith(".py"):
        mod = load_script(path)
        m = mod.build()
        return Target(getattr(mod, "NAME", _stem(path)), m.v, m.pal.rgba, dict(m.pal.materials),
                      script_view(mod), dict(m.pal.names))
    scene = read_vox(path)
    return Target(_stem(path), merge_models(scene), scene.palette, dict(scene.materials),
                  {"azimuth": 30.0, "elevation": 30.0, "fov": 0.0}, {})


def _out_dir(name: str, *sub: str) -> str:
    d = os.path.join(OUT, name, *sub)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- build / score / camera

def _score(mod, name, m, out_dir, emissive, *, quiet=False):
    from .score import append_history, score_model, summary_line
    ref = getattr(mod, "REFERENCE", None)
    if not ref or not os.path.isfile(os.path.join(ROOT, ref)):
        return None
    met, img = score_model(m.v, m.pal.rgba, emissive, os.path.join(ROOT, ref), script_view(mod, "SCORE_VIEW"),
                           cutout_kw=getattr(mod, "CUTOUT", None), cache_dir=REF_CACHE)
    img.save(os.path.join(out_dir, f"{name}_score.png"))
    append_history(os.path.join(out_dir, f"{name}_scores.jsonl"), met)
    if not quiet:
        print(f"score: {summary_line(met)}")
        print(f"score    -> {os.path.join(out_dir, name + '_score.png')}")
    return met


def cmd_build(a):
    mod = load_script(a.script)
    name = getattr(mod, "NAME", _stem(a.script))
    view = script_view(mod)
    if a.az is not None:
        view["azimuth"] = a.az
    if a.el is not None:
        view["elevation"] = a.el

    t = time.time()
    m = mod.build()
    out_dir = _out_dir(name)
    vox = os.path.join(out_dir, f"{name}.vox")
    backup = m.save(vox)
    if backup:
        print(f"backup: the previous {name}.vox had MagicaVoxel edits -> {backup}")
    print(f"built {name} in {time.time() - t:.1f}s -> {vox}")
    print(m.stats())

    emissive = {i for i in m.pal.materials if m.pal.is_emissive(i)}
    pal = m.pal.rgba
    render_sheet(m.v, pal, title=name, emissive=emissive, **view).save(os.path.join(out_dir, f"{name}_sheet.png"))
    iso = render_iso(m.v, pal, scale=a.scale, emissive=emissive, **view)
    iso.save(os.path.join(out_dir, f"{name}_iso.png"))
    print(f"preview  -> {os.path.join(out_dir, name + '_sheet.png')}")
    print(f"iso      -> {os.path.join(out_dir, name + '_iso.png')}")

    ref = getattr(mod, "REFERENCE", None)
    if ref and os.path.isfile(os.path.join(ROOT, ref)):
        cmp_path = os.path.join(out_dir, f"{name}_compare.png")
        side_by_side([os.path.join(ROOT, ref), iso], labels=["reference", "voxel build"]).save(cmp_path)
        print(f"compare  -> {cmp_path}")
        if not a.no_score:
            _score(mod, name, m, out_dir, emissive)
    if a.open:
        open_in_magicavoxel(vox)


def cmd_score(a):
    mod = load_script(a.script)
    name = getattr(mod, "NAME", _stem(a.script))
    m = mod.build()
    emissive = {i for i in m.pal.materials if m.pal.is_emissive(i)}
    met = _score(mod, name, m, _out_dir(name), emissive)
    if met is None:
        raise RuntimeError("the script has no REFERENCE image to score against")
    print(json.dumps({k: met[k] for k in ("iou", "delta_e", "view", "regions")}, ensure_ascii=False))


def cmd_fit_camera(a):
    from .score import fit_camera, score_model, summary_line
    mod = load_script(a.script)
    name = getattr(mod, "NAME", _stem(a.script))
    ref = getattr(mod, "REFERENCE", None)
    if not ref or not os.path.isfile(os.path.join(ROOT, ref)):
        raise RuntimeError("the script has no REFERENCE image")
    m = mod.build()
    emissive = {i for i in m.pal.materials if m.pal.is_emissive(i)}
    fovs = [float(f) for f in a.fovs.split(",")]
    best = fit_camera(m.v, os.path.join(ROOT, ref), fovs=fovs, cutout_kw=getattr(mod, "CUTOUT", None),
                      cache_dir=REF_CACHE)
    for b in best:
        print(f"  az={b['azimuth']:g} el={b['elevation']:g} fov={b['fov']:g}  silhouette≈{b['iou']:.3f}")
    view = {k: best[0][k] for k in ("azimuth", "elevation", "fov")}
    met, img = score_model(m.v, m.pal.rgba, emissive, os.path.join(ROOT, ref), view,
                           cutout_kw=getattr(mod, "CUTOUT", None), cache_dir=REF_CACHE)
    out = os.path.join(_out_dir(name), f"{name}_fit.png")
    img.save(out)
    print(f"best: {summary_line(met)}")
    print(f'VIEW = {{"azimuth": {view["azimuth"]:g}, "elevation": {view["elevation"]:g}, "fov": {view["fov"]:g}}}')
    print(f"fit      -> {out}")


def cmd_angles(a):
    mod = load_script(a.script)
    name = getattr(mod, "NAME", _stem(a.script))
    m = mod.build()
    emissive = {i for i in m.pal.materials if m.pal.is_emissive(i)}
    ims, labels = [], []
    ref = getattr(mod, "REFERENCE", None)
    if ref and os.path.isfile(os.path.join(ROOT, ref)):
        ims.append(os.path.join(ROOT, ref))
        labels.append("reference")
    for v in a.views:
        parts = [float(k) for k in v.split(",")]
        az, el, fov = (parts + [0.0])[:3]
        ims.append(render_iso(m.v, m.pal.rgba, azimuth=az, elevation=el, fov=fov, scale=5, emissive=emissive))
        labels.append(f"az={az:g} el={el:g}" + (f" fov={fov:g}" if fov else ""))
    out = os.path.join(_out_dir(name), f"{name}_angles.png")
    side_by_side(ims, height=a.height, labels=labels).save(out)
    print(out)


def cmd_render(a):
    t = load_target(a.vox)
    out = a.out or os.path.join(OUT, "_render", f"{_stem(a.vox)}_sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    render_sheet(t.v, t.palette, title=os.path.basename(a.vox), azimuth=a.az, elevation=a.el, fov=a.fov,
                 emissive=t.emissive).save(out)
    print(f"grid {t.v.shape}, voxels {(t.v > 0).sum()} -> {out}")


def cmd_ref(a):
    d = os.path.join(OUT, "_ref")
    os.makedirs(d, exist_ok=True)
    s = _stem(a.img)
    if a.action == "grid":
        p = os.path.join(d, f"{s}_grid.png")
        grid_overlay(a.img, a.step or 50).save(p)
        print(p)
    elif a.action == "crop":
        x0, y0, x1, y1 = map(int, a.args[:4])
        p = os.path.join(d, f"{s}_crop_{x0}_{y0}_{x1}_{y1}.png")
        crop(a.img, x0, y0, x1, y1, zoom=a.zoom, step=a.step if a.step is not None else 10).save(p)
        print(p)
    elif a.action == "palette":
        cols = dominant_colors(a.img, k=a.k, box=tuple(a.box) if a.box else None)
        p = os.path.join(d, f"{s}_palette.png")
        swatches(cols).save(p)
        for h, share in cols:
            print(f"{h}  {share * 100:5.1f}%")
        print(p)
    elif a.action == "sample":
        # accepts "x,y x,y" as well as "x y x y"
        nums = " ".join(a.args).replace(",", " ").split()
        if not nums or len(nums) % 2:
            raise RuntimeError("ref sample needs x,y pairs, e.g.: ref sample img.png 120,80 300,95")
        pts = [(int(nums[i]), int(nums[i + 1])) for i in range(0, len(nums), 2)]
        for (x, y), h in zip(pts, sample(a.img, pts)):
            print(f"({x},{y}) {h}")
    elif a.action == "cutout":
        im = cutout(a.img, keep=a.keep)
        p = os.path.join(d, f"{s}_cutout_{a.keep}.png")
        im.save(p)
        cover = (np.asarray(im)[..., 3] > 0).mean() * 100
        print(f"object covers {cover:.1f}% of the image -> {p}")


# ---------------------------------------------------------------- conversions (no Claude)

def _write_base(name: str, m, reference: str, how: str, score_view: dict | None):
    from .convert import base_script
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    base = f"models/{name}.base.vox"
    m.save(os.path.join(ROOT, base))
    script = os.path.join(ROOT, "models", f"{name}.py")
    if os.path.exists(script):
        print(f"kept existing {script} (it loads {base})")
    else:
        with open(script, "w", encoding="utf-8") as f:
            f.write(base_script(name, base, reference.replace("\\", "/"), how, score_view=score_view))
        print(f"script   -> {script}")
    print(f"base     -> {base}  ({int((m.v > 0).sum())} voxels, grid {m.v.shape})")
    cmd_build(argparse.Namespace(script=script, az=None, el=None, scale=8, no_score=False, open=False))


def cmd_extrude(a):
    from .convert import extrude
    m = extrude(a.img, depth=a.depth, inflate=a.inflate, pixel=a.pixel, max_size=a.max_size,
                cutout_kw={"keep": a.keep})
    how = f"extrude --depth {a.depth}" + (" --inflate" if a.inflate else "")
    _write_base(a.name, m, os.path.relpath(a.img, ROOT), how, {"azimuth": 0, "elevation": 0, "fov": 0})


def cmd_carve(a):
    from .convert import carve
    m = carve(a.front, a.side, a.top, height=a.height, side_from=a.side_from, cutout_kw={"keep": a.keep})
    how = "carve" + "".join(f" --{k} {os.path.basename(v)}" for k, v in (("front", a.front), ("side", a.side),
                                                                       ("top", a.top)) if v)
    _write_base(a.name, m, os.path.relpath(a.front, ROOT), how, {"azimuth": 0, "elevation": 0, "fov": 0})


# ---------------------------------------------------------------- game-asset outputs

def cmd_sprites(a):
    from .export import sprite_sheet
    t = load_target(a.target)
    el = a.el if a.el is not None else t.view.get("elevation", 30)
    man = sprite_sheet(t.v, t.palette, t.emissive, _out_dir(t.name, "sprites"), t.name, dirs=a.dirs,
                       elevation=el, fov=a.fov, scale=a.scale, columns=a.columns)
    print(f"{len(man['frames'])} frames {man['frame_width']}x{man['frame_height']}, anchor {man['anchor']}")
    print(f"sprites  -> {os.path.join(OUT, t.name, 'sprites', man['sheet'])}")


def cmd_export(a):
    from .export import write_glb, write_obj, write_ply
    t = load_target(a.target)
    d = _out_dir(t.name, "export")
    path = os.path.join(d, f"{t.name}.{a.format}")
    if a.format == "obj":
        files = write_obj(path, t.v, t.palette, scale=a.scale)
    elif a.format == "ply":
        files = write_ply(path, t.v, t.palette, scale=a.scale)
    else:
        files = write_glb(path, t.v, t.palette, t.emissive, scale=a.scale, name=t.name)
    for f in files:
        print(f"export   -> {f}")


def cmd_recolor(a):
    from .export import recolor
    t = load_target(a.target)

    def idx(key: str) -> int:
        if key.isdigit():
            return int(key)
        if key not in t.names:
            raise RuntimeError(f"unknown colour {key!r}; names: {sorted(t.names)}")
        return t.names[key]

    only = {idx(k) for k in a.only.split(",")} if a.only else None
    variants = []
    if a.swap:
        swaps = {}
        for s in a.swap:
            k, _, hx = s.partition("=")
            swaps[idx(k)] = hx
        variants.append((a.label or "swap", recolor(t.palette, swaps=swaps)))
    for h in (float(x) for x in a.hue.split(",")) if a.hue else []:
        variants.append((f"hue{h:g}", recolor(t.palette, hue=h, only=only, skip=t.emissive)))
    if not variants:
        raise RuntimeError("give --swap name=#rrggbb ... and/or --hue 30,180")
    d = _out_dir(t.name, "variants")
    for label, pal in variants:
        base = os.path.join(d, f"{t.name}_{label}")
        write_vox(base + ".vox", VoxScene([VoxModel(t.v)], pal, t.materials))
        render_iso(t.v, pal, emissive=t.emissive, **t.view).save(base + "_iso.png")
        print(f"variant  -> {base}.vox")


# ---------------------------------------------------------------- misc

def cmd_install_skill(a):
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "skills", "voxelize")
    if not os.path.isdir(src):
        raise RuntimeError("skill source not found; run this from a source checkout of 2DtoVoxel")
    dest = os.path.join(os.path.expanduser(a.dest), "voxelize")
    shutil.copytree(src, dest, dirs_exist_ok=True)
    print(f"installed /voxelize -> {dest}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Korean file names in output paths
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["ui"]:
        from .ui.server import main as ui_main
        return ui_main(argv[1:])

    ap = argparse.ArgumentParser(prog="voxtool", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build a model script")
    b.add_argument("script")
    b.add_argument("--open", action="store_true")
    b.add_argument("--no-score", action="store_true")
    b.add_argument("--az", type=float)
    b.add_argument("--el", type=float)
    b.add_argument("--scale", type=int, default=8)
    b.set_defaults(fn=cmd_build)

    s = sub.add_parser("score", help="measure the match with REFERENCE")
    s.add_argument("script")
    s.set_defaults(fn=cmd_score)

    fc = sub.add_parser("fit-camera", help="find the VIEW that best matches REFERENCE")
    fc.add_argument("script")
    fc.add_argument("--fovs", default="0,25,45", help="fields of view to try; 0 = orthographic")
    fc.set_defaults(fn=cmd_fit_camera)

    an = sub.add_parser("angles", help="renders at several cameras next to the reference")
    an.add_argument("script")
    an.add_argument("views", nargs="+", help="az,el[,fov] e.g. 30,20 42,15,30")
    an.add_argument("--height", type=int, default=420)
    an.set_defaults(fn=cmd_angles)

    r = sub.add_parser("render", help="preview sheet for a .vox or script")
    r.add_argument("vox")
    r.add_argument("--az", type=float, default=30.0)
    r.add_argument("--el", type=float, default=30.0)
    r.add_argument("--fov", type=float, default=0.0)
    r.add_argument("--out")
    r.set_defaults(fn=cmd_render)

    o = sub.add_parser("open", help="open a .vox in MagicaVoxel")
    o.add_argument("vox")
    o.set_defaults(fn=lambda a: open_in_magicavoxel(a.vox))

    sh = sub.add_parser("shot", help="capture the MagicaVoxel window (Windows)")
    sh.add_argument("--out", default=os.path.join(OUT, "_mv", "magicavoxel.png"))
    sh.set_defaults(fn=lambda a: screenshot_magicavoxel(a.out))

    f = sub.add_parser("ref", help="reference study tools")
    f.add_argument("action", choices=["grid", "crop", "palette", "sample", "cutout"])
    f.add_argument("img")
    f.add_argument("args", nargs="*")
    f.add_argument("--step", type=int)
    f.add_argument("--zoom", type=int, default=3)
    f.add_argument("--k", type=int, default=16)
    f.add_argument("--box", type=int, nargs=4)
    f.add_argument("--keep", choices=["largest", "all"], default="largest")
    f.set_defaults(fn=cmd_ref)

    c = sub.add_parser("compare", help="side-by-side image")
    c.add_argument("imgs", nargs="+")
    c.add_argument("--out", default=os.path.join(OUT, "_ref", "compare.png"))
    c.set_defaults(fn=lambda a: (os.makedirs(os.path.dirname(a.out), exist_ok=True),
                                 side_by_side(a.imgs, labels=[os.path.basename(i) for i in a.imgs]).save(a.out),
                                 print(a.out)))

    e = sub.add_parser("extrude", help="image / pixel art -> voxels (no Claude)")
    e.add_argument("img")
    e.add_argument("--name", required=True)
    e.add_argument("--depth", type=int, default=4)
    e.add_argument("--inflate", action="store_true", help="rounded, thicker in the middle")
    e.add_argument("--pixel", type=int, help="pixel-art block size (auto-detected)")
    e.add_argument("--max-size", type=int, default=128)
    e.add_argument("--keep", choices=["largest", "all"], default="all")
    e.set_defaults(fn=cmd_extrude)

    cv = sub.add_parser("carve", help="front/side/top silhouettes -> voxels (no Claude)")
    cv.add_argument("--front", required=True)
    cv.add_argument("--side")
    cv.add_argument("--top")
    cv.add_argument("--side-from", choices=["left", "right"], default="left")
    cv.add_argument("--name", required=True)
    cv.add_argument("--height", type=int, default=64)
    cv.add_argument("--keep", choices=["largest", "all"], default="largest")
    cv.set_defaults(fn=cmd_carve)

    sp = sub.add_parser("sprites", help="sprite sheet + manifest.json")
    sp.add_argument("target", help="models/<name>.py or a .vox")
    sp.add_argument("--dirs", type=int, default=8)
    sp.add_argument("--el", type=float)
    sp.add_argument("--fov", type=float, default=0.0)
    sp.add_argument("--scale", type=int, default=4)
    sp.add_argument("--columns", type=int)
    sp.set_defaults(fn=cmd_sprites)

    ex = sub.add_parser("export", help="mesh export (OBJ / PLY / GLB)")
    ex.add_argument("target", help="models/<name>.py or a .vox")
    ex.add_argument("--format", choices=["obj", "ply", "glb"], default="glb")
    ex.add_argument("--scale", type=float, default=0.1, help="size of one voxel in output units")
    ex.set_defaults(fn=cmd_export)

    rc = sub.add_parser("recolor", help="palette variants")
    rc.add_argument("target", help="models/<name>.py or a .vox")
    rc.add_argument("--swap", nargs="+", help="name=#rrggbb (palette name or index)")
    rc.add_argument("--label", help="file label for --swap (default 'swap')")
    rc.add_argument("--hue", help="comma-separated hue rotations in degrees")
    rc.add_argument("--only", help="comma-separated palette names/indices --hue applies to")
    rc.set_defaults(fn=cmd_recolor)

    ins = sub.add_parser("install-skill", help="copy the /voxelize skill to your user skills folder")
    ins.add_argument("--dest", default="~/.claude/skills")
    ins.set_defaults(fn=cmd_install_skill)

    sub.add_parser("ui", help="start the web UI (--port, --no-browser)")

    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (RuntimeError, ValueError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
