"""Helpers for studying a reference image before/while modelling."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .render import _font


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def grid_overlay(path: str, step: int = 50) -> Image.Image:
    """Reference with a labelled pixel grid, so positions can be read off precisely."""
    im = load_rgb(path)
    dr = ImageDraw.Draw(im)
    font = _font(11)
    for x in range(0, im.width, step):
        major = x % (step * 2) == 0
        dr.line([(x, 0), (x, im.height)], fill=(255, 0, 0) if major else (255, 140, 140), width=1)
        dr.text((x + 2, 2), str(x), fill=(200, 0, 0), font=font)
    for y in range(0, im.height, step):
        major = y % (step * 2) == 0
        dr.line([(0, y), (im.width, y)], fill=(0, 0, 255) if major else (140, 140, 255), width=1)
        dr.text((2, y + 2), str(y), fill=(0, 0, 200), font=font)
    return im


def crop(path: str, x0: int, y0: int, x1: int, y1: int, zoom: int = 3, step: int = 10) -> Image.Image:
    """Zoomed crop (nearest-neighbour) with a grid every `step` source pixels,
    labelled in source coordinates — for counting voxels / reading details."""
    im = load_rgb(path).crop((x0, y0, x1, y1))
    im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
    if step:
        dr = ImageDraw.Draw(im)
        font = _font(10)
        for sx in range((x0 // step + 1) * step, x1, step):
            px = (sx - x0) * zoom
            dr.line([(px, 0), (px, im.height)], fill=(255, 0, 0), width=1)
            if sx % (step * 5) == 0:
                dr.text((px + 2, 2), str(sx), fill=(255, 0, 0), font=font)
        for sy in range((y0 // step + 1) * step, y1, step):
            py = (sy - y0) * zoom
            dr.line([(0, py), (im.width, py)], fill=(0, 0, 255), width=1)
            if sy % (step * 5) == 0:
                dr.text((2, py + 2), str(sy), fill=(0, 0, 255), font=font)
    return im


def cutout(path: str, *, thr: float = 24.0, shadow: bool = True, keep: str = "largest") -> Image.Image:
    """Removes the background of a reference image -> RGBA (alpha = object mask).

    Images that already have transparency use their alpha. Otherwise the background
    colour is estimated from the border, and only background-like pixels connected to
    the border are removed, so similar colours inside the object survive. shadow=True
    also removes soft grey floor shadows. keep='largest' keeps only the biggest object
    (drops neighbours cut off at the image edge); keep='all' keeps every object."""
    from scipy import ndimage

    src = Image.open(path)
    rgb = np.asarray(src.convert("RGB")).astype(np.float32)
    if src.mode in ("RGBA", "LA", "P") and "A" in src.convert("RGBA").getbands():
        alpha = np.asarray(src.convert("RGBA"))[..., 3]
        if (alpha < 250).mean() > 0.01:              # real transparency present
            fg = alpha > 127
            return _mask_to_rgba(rgb, _keep(fg, keep, ndimage))

    b = 4
    border = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3),
                             rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(rgb - bg, axis=-1)
    bgish = dist < thr
    if shadow:
        lum, bg_lum = rgb.mean(-1), bg.mean()
        chroma, bg_chroma = rgb.max(-1) - rgb.min(-1), bg.max() - bg.min()
        bgish |= ((np.abs(chroma - bg_chroma) < 14) & (lum <= bg_lum + 8) & (lum > bg_lum * 0.55)
                  & (dist < thr * 4))
    labels, _ = ndimage.label(bgish)
    edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    background = np.isin(labels, edge[edge > 0])
    # Background-like areas enclosed by the object: a see-through opening (e.g. under an
    # arch, cut off from the outside by a contact shadow) if a good part of it is almost
    # exactly the background colour; otherwise a pale part of the object.
    enclosed = bgish & ~background
    el, ne = ndimage.label(enclosed)
    openings = np.zeros_like(enclosed)
    if ne:
        ids = np.arange(1, ne + 1)
        size = ndimage.sum(enclosed, el, ids)
        core = ndimage.mean(dist < 8, el, ids)
        openings = np.isin(el, ids[(size > enclosed.size * 0.0005) & (core > 0.3)])
    background |= openings
    # letterbox bars: uniform full-width rows / full-height columns at the image edge
    for axis in (0, 1):
        n = rgb.shape[axis]
        for idx in list(range(min(8, n))) + list(range(n - 1, max(n - 9, -1), -1)):
            line = np.take(rgb, idx, axis=axis)
            if (~np.take(background, idx, axis=axis)).mean() > 0.9 and line.std(axis=0).max() < 12:
                if axis == 0:
                    background[idx] = True
                else:
                    background[:, idx] = True
    fg = ndimage.binary_opening(~background, iterations=1)
    small_holes = ndimage.binary_fill_holes(fg) & ~fg & ~openings
    return _mask_to_rgba(rgb, _keep(fg | small_holes, keep, ndimage))


def _keep(fg: np.ndarray, keep: str, ndimage) -> np.ndarray:
    if keep != "largest" or not fg.any():
        return fg
    labels, n = ndimage.label(fg)
    sizes = ndimage.sum(fg, labels, range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def _mask_to_rgba(rgb: np.ndarray, fg: np.ndarray) -> Image.Image:
    out = np.dstack([rgb.astype(np.uint8), (fg * 255).astype(np.uint8)])
    return Image.fromarray(out, "RGBA")


def sample(path: str, points: list[tuple[int, int]], radius: int = 2) -> list[str]:
    """Median color (hex) of a small square around each point."""
    a = np.asarray(load_rgb(path)).astype(int)
    out = []
    for x, y in points:
        patch = a[max(y - radius, 0):y + radius + 1, max(x - radius, 0):x + radius + 1].reshape(-1, 3)
        r, g, b = np.median(patch, axis=0).astype(int)
        out.append(f"#{r:02x}{g:02x}{b:02x}")
    return out


def dominant_colors(path: str, k: int = 16, box: tuple[int, int, int, int] | None = None,
                    iters: int = 20, seed: int = 0) -> list[tuple[str, float]]:
    """k-means palette of the image (or a box region). Returns (hex, share) sorted by share."""
    im = load_rgb(path)
    if box:
        im = im.crop(box)
    a = np.asarray(im).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(seed)
    if len(a) > 60000:
        a = a[rng.choice(len(a), 60000, replace=False)]
    cent = a[rng.choice(len(a), k, replace=False)]
    for _ in range(iters):
        lab = np.argmin(((a[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
        for j in range(k):
            pts = a[lab == j]
            if len(pts):
                cent[j] = pts.mean(0)
    lab = np.argmin(((a[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
    share = np.bincount(lab, minlength=k) / len(a)
    order = np.argsort(-share)
    return [("#%02x%02x%02x" % tuple(int(c) for c in cent[j]), float(share[j])) for j in order]


def swatches(colors: list[tuple[str, float]]) -> Image.Image:
    font = _font(12)
    im = Image.new("RGB", (260, 22 * len(colors)), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for i, (h, s) in enumerate(colors):
        dr.rectangle([0, i * 22, 40, i * 22 + 20], fill=h)
        dr.text((48, i * 22 + 3), f"{h}  {s * 100:.1f}%", fill=(0, 0, 0), font=font)
    return im


def side_by_side(paths_or_images: list, height: int = 520, labels: list[str] | None = None) -> Image.Image:
    ims = [p if isinstance(p, Image.Image) else load_rgb(p) for p in paths_or_images]
    ims = [im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS) for im in ims]
    gap, lh = 12, 24
    W = sum(im.width for im in ims) + gap * (len(ims) + 1)
    out = Image.new("RGB", (W, height + lh + gap * 2), (245, 245, 245))
    dr = ImageDraw.Draw(out)
    font = _font(16)
    x = gap
    for i, im in enumerate(ims):
        if labels:
            dr.text((x, gap // 2), labels[i], fill=(30, 30, 30), font=font)
        out.paste(im, (x, gap + lh))
        x += im.width + gap
    return out
