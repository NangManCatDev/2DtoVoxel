"""Measured comparison between a model and its reference image.

score_model  : silhouette IoU, colour difference (CIE ΔE) and per-region misses for
               one camera, plus a diff image (missing = red, extra = blue).
fit_camera   : searches azimuth / elevation / field of view for the camera whose
               silhouette best matches the reference (fast point-splat silhouettes).

The reference is cut out (background removed), then the render is scaled and moved so
its area and centroid match the reference before anything is measured, so the model's
absolute size and position in the image don't matter, only its shape and colours.
"""
from __future__ import annotations

import json
import math
import os
import time

import numpy as np
from PIL import Image, ImageDraw

from .render import BG, FACES, Camera, _faces, _font, _raster, _shift, render_iso
from .reftools import cutout

WORK_H = 320        # reference silhouette height used for scoring (px)
FIT_H = 160         # lower resolution for the camera search
REGION_NAMES = [["top-left", "top", "top-right"], ["left", "center", "right"],
                ["bottom-left", "bottom", "bottom-right"]]


# ---------------------------------------------------------------- reference

def reference_cutout(path: str, cache_dir: str | None = None, **kw) -> Image.Image:
    """Cached cutout (keyed by file + settings) since builds repeat it every iteration."""
    if cache_dir:
        key = f"{os.path.splitext(os.path.basename(path))[0]}_{kw.get('keep', 'largest')}"
        cached = os.path.join(cache_dir, f"{key}_cutout.png")
        if os.path.isfile(cached) and os.path.getmtime(cached) >= os.path.getmtime(path):
            return Image.open(cached).convert("RGBA")
        im = cutout(path, **kw)
        os.makedirs(cache_dir, exist_ok=True)
        im.save(cached)
        return im
    return cutout(path, **kw)


def _fit_height(rgba: Image.Image, height: int, margin: float = 0.08):
    """Crops to the object, pads by `margin` and scales so the object is `height` px tall.
    Returns (rgb float array, mask bool array)."""
    a = np.asarray(rgba)[..., 3] > 127
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        raise ValueError("reference cutout is empty (try --keep all or a cleaner image)")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    m = int(max(x1 - x0, y1 - y0) * margin)
    box = (max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, rgba.width), min(y1 + m, rgba.height))
    crop = rgba.crop(box)
    k = height / (y1 - y0)
    crop = crop.resize((max(1, round(crop.width * k)), max(1, round(crop.height * k))), Image.LANCZOS)
    arr = np.asarray(crop).astype(np.float32)
    return arr[..., :3], arr[..., 3] > 127


# ---------------------------------------------------------------- alignment + metrics

def _centroid(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    return np.array([xs.mean(), ys.mean()])


def align_render(render: Image.Image, ref_mask: np.ndarray):
    """Scales an RGBA render so its silhouette area equals the reference's and moves it
    so the centroids coincide. Returns (rgb float, mask bool) on the reference canvas."""
    ra = np.asarray(render)[..., 3] > 127
    if not ra.any():
        return np.zeros(ref_mask.shape + (3,), np.float32), np.zeros_like(ref_mask)
    k = math.sqrt(ref_mask.sum() / ra.sum())
    img = render.resize((max(1, round(render.width * k)), max(1, round(render.height * k))), Image.LANCZOS)
    off = np.round(_centroid(ref_mask) - _centroid(np.asarray(img)[..., 3] > 127)).astype(int)
    canvas = Image.new("RGBA", (ref_mask.shape[1], ref_mask.shape[0]), (0, 0, 0, 0))
    canvas.paste(img, (int(off[0]), int(off[1])), img)
    arr = np.asarray(canvas).astype(np.float32)
    return arr[..., :3], arr[..., 3] > 127


def _lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _blur(rgb: np.ndarray, radius: float) -> np.ndarray:
    from scipy import ndimage
    return np.stack([ndimage.gaussian_filter(rgb[..., i], radius) for i in range(3)], -1)


def measure(ref_rgb, ref_mask, ren_rgb, ren_mask) -> dict:
    inter, union = ref_mask & ren_mask, ref_mask | ren_mask
    iou = float(inter.sum() / max(union.sum(), 1))
    de_map = np.linalg.norm(_lab(_blur(ref_rgb, 1.5)) - _lab(_blur(ren_rgb, 1.5)), axis=-1)
    de = float(de_map[inter].mean()) if inter.any() else 100.0
    ys, xs = np.nonzero(ref_mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    regions = []
    for r in range(3):
        for c in range(3):
            sl = (slice(y0 + (y1 - y0) * r // 3, y0 + (y1 - y0) * (r + 1) // 3),
                  slice(x0 + (x1 - x0) * c // 3, x0 + (x1 - x0) * (c + 1) // 3))
            area = max(int(ref_mask[sl].sum()), 1)
            cell_inter = inter[sl]
            regions.append({"region": REGION_NAMES[r][c],
                            "missing": round(float((ref_mask[sl] & ~ren_mask[sl]).sum() / area), 3),
                            "extra": round(float((ren_mask[sl] & ~ref_mask[sl]).sum() / area), 3),
                            "delta_e": round(float(de_map[sl][cell_inter].mean()), 1) if cell_inter.any() else None})
    return {"iou": round(iou, 4), "delta_e": round(de, 2), "regions": regions, "_de_map": de_map}


def diff_image(ref_rgb, ref_mask, ren_rgb, ren_mask, de_map, title: str) -> Image.Image:
    """reference | aligned render | overlay (red = missing, blue = extra, inside: ΔE heat)."""
    H, W = ref_mask.shape
    bg = np.array(BG, np.float32)
    ref_img = np.where(ref_mask[..., None], ref_rgb, bg)
    ren_img = np.where(ren_mask[..., None], ren_rgb, bg)
    gray = ref_rgb.mean(-1, keepdims=True) * 0.35 + 255 * 0.65
    over = np.where(ref_mask[..., None], gray, bg)
    t = np.clip(de_map / 30.0, 0, 1)[..., None]                       # 0 good .. 30+ bad
    heat = (1 - t) * np.array([90, 190, 110]) + t * np.array([235, 170, 40])
    inter = ref_mask & ren_mask
    over = np.where(inter[..., None], over * 0.45 + heat * 0.55, over)
    over = np.where((ref_mask & ~ren_mask)[..., None], np.array([225, 60, 60]), over)
    over = np.where((ren_mask & ~ref_mask)[..., None], np.array([60, 110, 230]), over)
    panels = [Image.fromarray(np.clip(p, 0, 255).astype(np.uint8)) for p in (ref_img, ren_img, over)]
    gap, head = 12, 40
    sheet = Image.new("RGB", (W * 3 + gap * 4, H + head + gap), (245, 245, 245))
    dr = ImageDraw.Draw(sheet)
    dr.text((gap, 8), title, fill=(30, 30, 30), font=_font(18))
    labels = ["reference (cut out)", "build (aligned)", "red = missing · blue = extra · green→orange = colour diff"]
    for i, p in enumerate(panels):
        x = gap + i * (W + gap)
        sheet.paste(p, (x, head))
        dr.text((x, head - 14), labels[i], fill=(90, 90, 90), font=_font(11))
    return sheet


# ---------------------------------------------------------------- scoring one camera

def _render_scale(v: np.ndarray) -> float:
    s = 420 / max(v.shape)
    return int(np.clip(round(s), 2, 8)) if s >= 1.5 else s   # big models: below a pixel per voxel is enough


def score_model(v, palette, emissive, ref_path: str, view: dict, *, cutout_kw: dict | None = None,
                cache_dir: str | None = None):
    """Returns (metrics dict, diff image)."""
    ref = reference_cutout(ref_path, cache_dir, **(cutout_kw or {}))
    ref_rgb, ref_mask = _fit_height(ref, WORK_H)
    ren = render_iso(v, palette, azimuth=view.get("azimuth", 30), elevation=view.get("elevation", 30),
                     fov=view.get("fov", 0), scale=_render_scale(v), emissive=emissive, outline=False,
                     transparent=True)
    ren_rgb, ren_mask = align_render(ren, ref_mask)
    met = measure(ref_rgb, ref_mask, ren_rgb, ren_mask)
    de_map = met.pop("_de_map")
    met["view"] = {k: view.get(k, d) for k, d in (("azimuth", 30), ("elevation", 30), ("fov", 0))}
    title = (f"IoU {met['iou']:.3f}   ΔE {met['delta_e']:.1f}   "
             f"(az {met['view']['azimuth']:g}° el {met['view']['elevation']:g}° fov {met['view']['fov']:g}°)")
    return met, diff_image(ref_rgb, ref_mask, ren_rgb, ren_mask, de_map, title)


# ---------------------------------------------------------------- the model laid over the full-size reference

def place_on_reference(v, palette, emissive, ref_path: str, view: dict, *, cutout_kw: dict | None = None,
                       cache_dir: str | None = None, min_face_px: float = 0.0):
    """Lays the model over the full-resolution reference cutout with the score's alignment
    (equal silhouette area, matching centroids). Returns (reference rgba [H, W, 4], q, face
    index per pixel [H*q, W*q] with -1 = none, faces from render._faces): the face buffer is
    q times finer than the reference when voxel faces would otherwise be under min_face_px."""
    ref = np.asarray(reference_cutout(ref_path, cache_dir, **(cutout_kw or {})))
    ref_mask = ref[..., 3] > 127
    if not ref_mask.any():
        raise ValueError("reference cutout is empty (try CUTOUT = {'keep': 'all'} or a cleaner image)")
    cam = Camera(v.shape, view.get("azimuth", 30), view.get("elevation", 30), view.get("fov", 0))
    f = _faces(v, palette, cam, emissive or set()) if (v > 0).any() else None
    if f is None:
        raise ValueError("the model is empty")
    pts = cam.project(f["corners"])
    flat = pts.reshape(-1, 2)
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    ys = np.nonzero(ref_mask)[0]
    s0 = (ys.max() - ys.min() + 1) / max(hi[1] - lo[1], 1e-6)       # first pass at the reference's height
    W0, H0 = (np.ceil((hi - lo) * s0) + 3).astype(int)
    m0 = _raster((pts - lo) * s0 + 1, f["depth"], int(W0), int(H0)) >= 0
    k = math.sqrt(ref_mask.sum() / max(m0.sum(), 1))
    c0, cr = _centroid(m0) + 0.5, _centroid(ref_mask) + 0.5
    q = max(1, min(4, math.ceil(min_face_px / (s0 * k)))) if min_face_px else 1
    H, W = ref_mask.shape
    ids = _raster((((pts - lo) * s0 + 1 - c0) * k + cr) * q, f["depth"], W * q, H * q)
    return ref, q, ids, f


def reference_colors(v, palette, emissive, ref_path: str, view: dict, *, cutout_kw: dict | None = None,
                     cache_dir: str | None = None):
    """Colour of every voxel the reference shows, read from the reference's own pixels: the mean
    over the pixels each visible face covers, divided by that face's preview shading (top 1.0,
    front 0.9, left 0.76, ...) so a preview reproduces the reference, then averaged over the
    voxel's visible faces by pixel count. Returns (voxel coords [M, 3], rgb float [M, 3])."""
    ref, q, ids, f = place_on_reference(v, palette, emissive, ref_path, view, cutout_kw=cutout_kw,
                                        cache_dir=cache_dir, min_face_px=1.5)
    yy, xx = np.nonzero(ids >= 0)
    ry, rx = yy // q, xx // q
    inside = ref[ry, rx, 3] > 127
    fid, ry, rx = ids[yy[inside], xx[inside]], ry[inside], rx[inside]
    n = len(f["depth"])
    cnt = np.bincount(fid, minlength=n).astype(np.float64)
    sums = np.stack([np.bincount(fid, weights=ref[ry, rx, c].astype(np.float64), minlength=n) for c in range(3)], 1)
    seen = cnt > 0
    shade = np.array(list(FACES.values()))[f["normal"][seen]]
    face_rgb = sums[seen] / cnt[seen, None] / shade[:, None]
    w = cnt[seen]
    keys, inv = np.unique(np.ravel_multi_index(f["coords"][seen].T, v.shape), return_inverse=True)
    tot = np.bincount(inv, weights=w)
    rgb = np.stack([np.bincount(inv, weights=face_rgb[:, c] * w) for c in range(3)], 1) / tot[:, None]
    return np.stack(np.unravel_index(keys, v.shape), axis=1), np.clip(rgb, 0, 255)


def zoom_box(ref_mask: np.ndarray, where: str) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) in reference pixels for a region name of the score's 3 x 3 grid
    (top-left ... bottom-right, with a small margin) or for 'x0,y0,x1,y1'."""
    H, W = ref_mask.shape
    names = [n for row in REGION_NAMES for n in row]
    if where in names:
        ys, xs = np.nonzero(ref_mask)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        r, c = divmod(names.index(where), 3)
        ch, cw = (y1 - y0) / 3, (x1 - x0) / 3
        my, mx = ch * 0.1, cw * 0.1
        box = (x0 + c * cw - mx, y0 + r * ch - my, x0 + (c + 1) * cw + mx, y0 + (r + 1) * ch + my)
    else:
        try:
            box = tuple(float(k) for k in where.replace(" ", "").split(","))
        except ValueError:
            box = ()
        if len(box) != 4:
            raise ValueError(f"--zoom takes a region ({', '.join(names)}) or x0,y0,x1,y1 in reference pixels")
    x0, y0, x1, y1 = (int(round(k)) for k in box)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise ValueError(f"zoom box {box} is outside the {W}x{H} reference or too small")
    return x0, y0, x1, y1


def zoom_image(v, palette, emissive, ref_path: str, view: dict, where: str, *, cutout_kw: dict | None = None,
               cache_dir: str | None = None):
    """Close-up of one area at the reference's full resolution, aligned like the score:
    reference | build | difference. Returns (metrics of the area, image)."""
    ref, _, ids, f = place_on_reference(v, palette, emissive, ref_path, view, cutout_kw=cutout_kw,
                                        cache_dir=cache_dir)
    ref_mask, ren_mask = ref[..., 3] > 127, ids >= 0
    ren_rgb = np.zeros(ref.shape[:2] + (3,), np.float32)
    ren_rgb[ren_mask] = f["rgb"][ids[ren_mask]]
    x0, y0, x1, y1 = zoom_box(ref_mask, where)
    sl = (slice(y0, y1), slice(x0, x1))
    crop = [ref[sl][..., :3].astype(np.float32), ref_mask[sl], ren_rgb[sl], ren_mask[sl]]
    if not crop[1].any():
        raise ValueError(f"the reference shows nothing inside {x0},{y0},{x1},{y1}")
    met = measure(*crop)
    de_map = met.pop("_de_map")
    k = max(1, 480 // (y1 - y0))                     # small areas are enlarged so voxels stay visible
    big = [np.repeat(np.repeat(a, k, 0), k, 1) for a in (*crop, de_map)]
    met["box"] = [x0, y0, x1, y1]
    title = f"{where}  ({x0},{y0})-({x1},{y1}) of the reference   IoU {met['iou']:.3f}   ΔE {met['delta_e']:.1f}"
    return met, diff_image(*big, title)


def summary_line(met: dict) -> str:
    """One line for logs: overall numbers + the worst regions."""
    worst = sorted(met["regions"], key=lambda r: r["missing"] + r["extra"], reverse=True)[:3]
    parts = []
    for r in worst:
        if r["missing"] + r["extra"] < 0.05:
            continue
        what = "missing" if r["missing"] >= r["extra"] else "extra"
        parts.append(f"{r['region']} {what} {max(r['missing'], r['extra']) * 100:.0f}%")
    return f"iou={met['iou']:.3f} dE={met['delta_e']:.1f}" + (f" worst: {', '.join(parts)}" if parts else "")


def append_history(path: str, met: dict):
    rec = {"t": time.time(), **{k: met[k] for k in ("iou", "delta_e", "view")}}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------- camera search

def _surface_points(v: np.ndarray) -> np.ndarray:
    filled = v > 0
    exposed = np.zeros_like(filled)
    for n in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        exposed |= filled & ~_shift(filled, n)
    return np.argwhere(exposed).astype(np.float32) + 0.5


def _splat_iou(p2: np.ndarray, ref_mask: np.ndarray, ref_area: float, ref_c: np.ndarray, ndimage) -> float:
    span = p2.max(axis=0) - p2.min(axis=0) + 1
    ys = np.nonzero(ref_mask)[0]
    k = (ys.max() - ys.min() + 1) / span[1]
    H, W = ref_mask.shape
    for _ in range(2):          # second pass corrects the scale so areas match
        q = np.round((p2 - p2.mean(axis=0)) * k + ref_c).astype(int)
        ok = (q[:, 0] >= 0) & (q[:, 0] < W) & (q[:, 1] >= 0) & (q[:, 1] < H)
        m = np.zeros((H, W), bool)
        m[q[ok, 1], q[ok, 0]] = True
        r = max(1, int(math.ceil(k * 0.55)))
        m = ndimage.binary_dilation(m, structure=np.ones((2 * r + 1, 2 * r + 1), bool))
        area = m.sum()
        if area == 0:
            return 0.0
        k *= math.sqrt(ref_area / area)
    return float((m & ref_mask).sum() / max((m | ref_mask).sum(), 1))


def fit_camera(v: np.ndarray, ref_path: str, *, fovs=(0, 25, 45), cutout_kw: dict | None = None,
               cache_dir: str | None = None, top: int = 5) -> list[dict]:
    """Coarse grid over the full circle of azimuths, then a finer search around the best
    candidates. Returns the best views, each {'azimuth','elevation','fov','iou'} (splat IoU)."""
    from scipy import ndimage
    ref = reference_cutout(ref_path, cache_dir, **(cutout_kw or {}))
    _, ref_mask = _fit_height(ref, FIT_H, margin=0.25)
    ref_area, ref_c = float(ref_mask.sum()), _centroid(ref_mask)
    pts = _surface_points(v)
    if len(pts) > 30000:                       # subsample big models; silhouettes barely change
        pts = pts[np.random.default_rng(0).choice(len(pts), 30000, replace=False)]

    def evaluate(az, el, fov):
        cam = Camera(v.shape, az, el, fov)
        return _splat_iou(cam.project(pts), ref_mask, ref_area, ref_c, ndimage)

    results = {}
    for fov in fovs:
        for el in range(0, 61, 10):
            for az in range(0, 360, 15):
                results[(az, el, fov)] = evaluate(az, el, fov)
    for (az0, el0, fov0) in sorted(results, key=results.get, reverse=True)[:3]:
        for daz in range(-12, 13, 3):
            for de in (-6, -3, 0, 3, 6):
                for dfov in ((-10, 0, 10) if fov0 else (0,)):
                    key = ((az0 + daz) % 360, int(np.clip(el0 + de, 0, 80)), max(0, fov0 + dfov))
                    if key not in results:
                        results[key] = evaluate(*key)
    best = sorted(results.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [{"azimuth": az, "elevation": el, "fov": fov, "iou": round(iou, 4)} for (az, el, fov), iou in best]
