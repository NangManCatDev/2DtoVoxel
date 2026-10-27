"""Image -> voxel conversions that need no LLM (fast, free, deterministic).

extrude : one image (pixel art, an icon, a sprite) -> a slab of voxels; inflate=True
          makes it rounded and thicker in the middle, like a pillow.
carve   : front (+ side, + top) silhouettes -> their intersection (visual hull), each
          surface voxel coloured from the view that sees it most directly.

Both return a Model whose palette is named c1, c2, ... A result can serve as the base
of a model script (Model.from_vox) that Claude or you then refine with the DSL.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .model import Model
from .reftools import cutout
from .vox_io import MAX_DIM


def detect_pixel_size(rgba: np.ndarray, max_k: int = 32) -> int:
    """Block size of upscaled pixel art (e.g. 8 for a 16x16 sprite saved at 128x128), else 1."""
    H, W = rgba.shape[:2]
    a = rgba.astype(np.int16)
    for k in range(min(max_k, H // 2, W // 2), 1, -1):
        h, w = H // k * k, W // k * k
        block = a[:h:k, :w:k]
        up = np.repeat(np.repeat(block, k, axis=0), k, axis=1)
        diff = np.abs(up - a[:h, :w]).max(axis=-1)
        if (diff <= 10).mean() > 0.985:
            return k
    return 1


def load_image(path: str, *, pixel: int | None = None, max_size: int = 128, cutout_kw: dict | None = None):
    """-> (rgb uint8 [H, W, 3], mask bool [H, W]) at voxel resolution (one pixel per voxel),
    cropped to the object."""
    rgba = np.asarray(cutout(path, **(cutout_kw or {})))
    k = pixel or detect_pixel_size(rgba)
    if k > 1:
        rgba = rgba[k // 2::k, k // 2::k]            # one sample per block centre
    mask = rgba[..., 3] > 127
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError(f"no object found in {path}")
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = rgba.shape[:2]
    if max(H, W) > max_size:                          # photos/renders: shrink, averaging colours
        s = max_size / max(H, W)
        im = Image.fromarray(rgba, "RGBA").resize((max(1, round(W * s)), max(1, round(H * s))), Image.BOX)
        rgba = np.asarray(im)
    return rgba[..., :3].copy(), rgba[..., 3] > 127


def _quantize(colors: np.ndarray, n: int = 255) -> tuple[np.ndarray, np.ndarray]:
    """[N, 3] uint8 -> (index per colour [N], palette [K, 3]) with K <= n."""
    uniq, inv = np.unique(colors.reshape(-1, 3), axis=0, return_inverse=True)
    if len(uniq) <= n:
        return inv.reshape(-1), uniq
    im = Image.fromarray(colors.reshape(1, -1, 3).astype(np.uint8), "RGB").quantize(n, method=Image.MEDIANCUT)
    pal = np.array(im.getpalette()[:n * 3], np.uint8).reshape(-1, 3)
    return np.asarray(im).reshape(-1), pal


def _model_from(grid_rgb: np.ndarray, filled: np.ndarray, seed: int = 0) -> Model:
    if max(filled.shape) > MAX_DIM:
        raise ValueError(f"result {filled.shape} exceeds {MAX_DIM} per axis; lower max_size/height")
    m = Model(*filled.shape, seed=seed)
    idx, pal = _quantize(grid_rgb[filled])
    for i, c in enumerate(pal):
        m.pal.add(f"c{i + 1}", "#%02x%02x%02x" % tuple(int(k) for k in c))
    m.v[filled] = (idx + 1).astype(np.uint8)
    return m


def extrude(path: str, *, depth: int = 4, inflate: bool = False, pixel: int | None = None,
            max_size: int = 128, cutout_kw: dict | None = None) -> Model:
    """Image x -> model x, image up -> model z, thickness along y (front at y=0)."""
    from scipy import ndimage
    rgb, mask = load_image(path, pixel=pixel, max_size=max_size, cutout_kw=cutout_kw)
    rgb, mask = rgb[::-1].transpose(1, 0, 2), mask[::-1].T     # -> [x, z], z up
    W, H = mask.shape
    if inflate:
        D = 2 * depth - 1
        dt = ndimage.distance_transform_edt(mask)
        t = 1 + np.round((depth - 1) * np.sqrt(dt / max(dt.max(), 1))).astype(int)
        Y = np.arange(D)[None, :, None]
        filled = mask[:, None, :] & (np.abs(Y - (depth - 1)) <= (t[:, None, :] - 1))
    else:
        D = depth
        filled = np.repeat(mask[:, None, :], D, axis=1)
    grid_rgb = np.repeat(rgb[:, None, :, :], D, axis=1)
    return _model_from(grid_rgb, filled)


def _view(path, size, cutout_kw, *, flip=False):
    """Silhouette + colours of one view resized to `size` = (cols, rows) -> arrays [col, row-from-bottom]."""
    rgb, mask = load_image(path, max_size=4096, cutout_kw=cutout_kw)
    im = Image.fromarray(np.dstack([rgb, mask * 255]).astype(np.uint8), "RGBA").resize(size, Image.BOX)
    a = np.asarray(im)
    if flip:
        a = a[:, ::-1]
    return a[::-1, :, :3].transpose(1, 0, 2), (a[::-1, :, 3] > 127).T


def carve(front: str, side: str | None = None, top: str | None = None, *, height: int = 64,
          side_from: str = "left", cutout_kw: dict | None = None) -> Model:
    """Visual hull of up to three orthographic silhouettes.
    front: seen from the front (x right, z up). side: seen from the left (front of the
    object on the right of the image) or from the right with side_from='right'.
    top: seen from above with the front at the bottom of the image."""
    f_rgb, f_mask = load_image(front, max_size=4096, cutout_kw=cutout_kw)
    H = height
    W = max(1, round(H * f_mask.shape[1] / f_mask.shape[0]))
    if side:
        s_rgb, s_mask = load_image(side, max_size=4096, cutout_kw=cutout_kw)
        D = max(1, round(H * s_mask.shape[1] / s_mask.shape[0]))
    elif top:
        t_rgb, t_mask = load_image(top, max_size=4096, cutout_kw=cutout_kw)
        D = max(1, round(W * t_mask.shape[0] / t_mask.shape[1]))
    else:
        D = max(1, W // 2)

    fr, fm = _view(front, (W, H), cutout_kw)                                   # [x, z]
    hull = np.repeat(fm[:, None, :], D, axis=1)
    views = [("front", fr)]
    if side:
        # left view: image column 0 = back of the object, last column = front (y = 0)
        sr, sm = _view(side, (D, H), cutout_kw, flip=(side_from == "left"))       # [y, z]
        hull &= sm[None, :, :]
        views.append(("side", sr))
    if top:
        tr, tm = _view(top, (W, D), cutout_kw)                                 # [x, y] (front at y=0)
        hull &= tm[:, :, None]
        views.append(("top", tr))

    # colour each voxel from the view where it is shallowest (closest to that view's surface)
    big = 10 ** 6
    depth = {}
    cumy = np.cumsum(hull, axis=1)
    depth["front"] = np.where(hull, cumy, big)
    if side:
        cumx = np.cumsum(hull, axis=0) if side_from == "left" else np.cumsum(hull[::-1], axis=0)[::-1]
        depth["side"] = np.where(hull, cumx, big)
    if top:
        cumz = np.cumsum(hull[:, :, ::-1], axis=2)[:, :, ::-1]
        depth["top"] = np.where(hull, cumz, big)
    names = [n for n, _ in views]
    best = np.argmin(np.stack([depth[n] for n in names]), axis=0)
    grid = np.zeros(hull.shape + (3,), np.uint8)
    for i, (n, col) in enumerate(views):
        sel = hull & (best == i)
        if n == "front":
            src = np.broadcast_to(col[:, None, :, :], hull.shape + (3,))
        elif n == "side":
            src = np.broadcast_to(col[None, :, :, :], hull.shape + (3,))
        else:
            src = np.broadcast_to(col[:, :, None, :], hull.shape + (3,))
        grid[sel] = src[sel]
    return _model_from(grid, hull)


def base_script(name: str, base_vox: str, reference: str, how: str, *, score_view: dict | None = None) -> str:
    """Model script that starts from a converted base and is ready for DSL details."""
    sv = f"\nSCORE_VIEW = {score_view!r}   # camera the reference was drawn from" if score_view else ""
    return f'''"""{name} — {reference} converted with `voxtool {how}`.

The voxels come from {base_vox}. Add details with the DSL below, or re-run the
conversion to regenerate the base. See README for the DSL reference.
"""
from voxtool import Model

NAME = "{name}"
REFERENCE = "{reference}"
VIEW = {{"azimuth": 30, "elevation": 20}}{sv}


def build() -> Model:
    m = Model.from_vox("{base_vox}")
    return m
'''
