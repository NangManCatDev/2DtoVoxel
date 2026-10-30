"""돌 바닥 타일 — reference/0e0548e3-8d29-4297-8423-9735c79d751b.png

A rectangular floor slab of loose flagstones seen from the front corner at an
isometric angle, cool lavender-grey stone in a dark room with a warm light at the
back-left. There is no base slab: the outer stones show their own sides.

Layout (y=0 front; x runs along the front-right edge of the view, y along the long
front-left edge):
  stones   random packing on a CELL grid: squares and 2:1-ish rectangles from
           5 to 20 voxels, 1-voxel dark joints, tops at TILE_Z +-1
  tops     mottled rose / lilac / slate stone, a dotted light rim along every top
           edge, dark grey cross-shaped stains and blotchy stain patches
  glints   wet, glossy patches: pale blue-white speckles (several spots) and warm
           gold speckles where the back-left light hits
  sides    cooler, darker lavender body under the top layer
"""
import numpy as np
from scipy import ndimage

from voxtool import Model

NAME = "model_1028_0457"
REFERENCE = "reference/0e0548e3-8d29-4297-8423-9735c79d751b.png"
# fit-camera prefers az 231 (same silhouette from the back corner); this is the front
# corner, with a little more perspective than fit-camera found (the far edges of the
# reference converge): fov 10 scored best of 5 / 10 / 12 / 15
VIEW = {"azimuth": 51, "elevation": 35, "fov": 10}

# --- plan
CELL = 3              # layout unit: a stone is k*CELL voxels including its 1-voxel joint
X_CELLS = 37          # front-right edge
Y_CELLS = 43          # front-left edge (the long side)
W = X_CELLS * CELL - 1
D = Y_CELLS * CELL - 1
SIZES = (2, 3, 4, 5, 6, 7, 8)              # stone side in cells
SIZE_P = (0.08, 0.20, 0.24, 0.17, 0.13, 0.11, 0.07)
SQUARE_P = 0.55                             # chance a stone is square

# --- heights (first empty z above each surface)
BED_Z = 4             # dark mortar filling the joints (2 below a normal top)
TILE_Z = 6            # normal stone top
TILE_JITTER = (-1, 0, 0, 0, 0, 1)
FOOT_H = 2            # darker bottom layers of each stone
HEIGHT = TILE_Z + 2

# stone hues (light, mid, dark, rim); tops render at x1.0
HUES = {
    "rose": ("#a798a4", "#a294a0", "#9b8d9a", "#c6aeb2"),
    "lilac": ("#9d94a9", "#988fa4", "#90889d", "#b9a8b6"),
    "slate": ("#877f93", "#827a8f", "#7b7388", "#a69299"),
    "warm": ("#bea6a6", "#b8a0a1", "#b09899", "#dcbfb6"),
}
# hue odds in the lit back-left (near GLOW) and the dim front-right
HUE_P_LIT = {"rose": 0.55, "lilac": 0.25, "slate": 0.20}
HUE_P_DIM = {"rose": 0.30, "lilac": 0.25, "slate": 0.45}

# wet / lit spots in plan fractions (u along x, v along y), measured on the reference
WET_SPOTS = [(0.25, 0.81, 0.10), (0.36, 0.85, 0.07), (0.14, 0.38, 0.08),
             (0.54, 0.35, 0.07), (0.63, 0.79, 0.04)]
GLINT_SPOTS = [(0.49, 0.85, 0.10), (0.68, 0.92, 0.08), (0.08, 0.61, 0.07),
               (0.35, 0.74, 0.09)]
GLOW = (0.45, 0.85, 0.30, 0.22)            # warm light pool: centre u, v and radii


def palette(m: Model):
    p = m.pal
    for name, ramp in HUES.items():
        p.ramp(name, ramp)                                   # <hue>3 = dotted top-edge rim
    p.ramp("body", ["#766c8a", "#6e6584", "#655c7a"])        # stone sides
    p.add("foot", "#564e66")                                 # darker, grimy bottom of the sides
    p.add("joint", "#2c2632")
    p.ramp("stain", ["#857e8f", "#777083", "#6a6476"])
    p.ramp("damp", ["#8c8b9e", "#7e7c91", "#706e84"])        # dark glossy wet stone
    p.ramp("wet", ["#e6ecf6", "#c4d4ee", "#a6b4d2"])
    p.ramp("glint", ["#ecd2bc", "#dcbca8", "#c9a99e"])


def shades(name: str) -> list[str]:
    return [f"{name}0", f"{name}1", f"{name}2"]


# ---------------------------------------------------------------- layout

def pick(rng, run: int) -> int:
    """Stone size (cells) that fits a free run without leaving a 1-cell sliver."""
    s = min(int(rng.choice(SIZES, p=SIZE_P)), run)
    if run - s == 1:
        s = s - 1 if s - 1 >= 2 else s + 1
    return s


def layout(rng) -> list[tuple[int, int, int, int]]:
    """Random packing of the cell grid, row by row. The rectangle below a free cell
    is always free (tiles are placed top-down), so only the run along x limits a tile."""
    taken = np.zeros((X_CELLS, Y_CELLS), bool)
    tiles = []
    for j in range(Y_CELLS):
        for i in range(X_CELLS):
            if taken[i, j]:
                continue
            run = 0
            while i + run < X_CELLS and not taken[i + run, j]:
                run += 1
            w = pick(rng, run)
            d = w if rng.random() < SQUARE_P else int(rng.choice(SIZES, p=SIZE_P))
            d = max(min(d, 2 * w + 1), (w + 1) // 2)          # no long planks
            d = min(d, Y_CELLS - j)
            if Y_CELLS - j - d == 1:
                d = d - 1 if d - 1 >= 2 else d + 1
            taken[i:i + w, j:j + d] = True
            tiles.append((i, j, w, d))
    return tiles


# ---------------------------------------------------------------- helpers

def blob(u, v, cu, cv, ru, rv=None) -> np.ndarray:
    rv = ru if rv is None else rv
    return np.exp(-(((u - cu) / ru) ** 2 + ((v - cv) / rv) ** 2))


def smooth_noise(m: Model, shape, sigma: float) -> np.ndarray:
    f = ndimage.gaussian_filter(m.rng.random(shape), sigma)
    return (f - f.min()) / max(np.ptp(f), 1e-6)


def top_z(m: Model) -> np.ndarray:
    """z of the highest voxel per column (-1 = empty)."""
    filled = m.v != 0
    z = filled.shape[2] - 1 - np.argmax(filled[:, :, ::-1], axis=2)
    return np.where(filled.any(axis=2), z, -1)


def paint_tops(m: Model, mask: np.ndarray, colors: list[str], only: set[int] | None = None):
    """Recolour the top voxel of every column in mask with a random colour from colors
    (only over stone tops, never the joints)."""
    tz = top_z(m)
    xs, ys = np.nonzero(mask & (tz >= BED_Z))
    zs = tz[xs, ys]
    if only is not None:
        keep = np.isin(m.v[xs, ys, zs], list(only))
        xs, ys, zs = xs[keep], ys[keep], zs[keep]
    idx = np.array([m.pal.idx(c) for c in colors], np.uint8)
    m.v[xs, ys, zs] = m.rng.choice(idx, size=len(xs))


def stone(m: Model, x, y, w, d, top: int, hue: str):
    m.box(x, y, 0, w, d, FOOT_H, "foot")
    m.box(x, y, FOOT_H, w, d, top - 1 - FOOT_H, "body1")
    m.box(x, y, top - 1, w, d, 1, f"{hue}1")


def rim(m: Model, x, y, w, d, top: int, hue: str):
    """Dotted light line along the top edges (every other voxel)."""
    z, c = top - 1, f"{hue}3"
    for k in range(0, w, 2):
        m.set(x + k, y, z, c)
        m.set(x + k, y + d - 1, z, c)
    for k in range(0, d, 2):
        m.set(x, y + k, z, c)
        m.set(x + w - 1, y + k, z, c)


def crosses(m: Model, n: int, stone_idx: set[int]):
    """Small plus-shaped dark stains scattered over the stone tops."""
    mask = np.zeros((W, D), bool)
    for _ in range(n):
        cx, cy = int(m.rng.integers(2, W - 2)), int(m.rng.integers(2, D - 2))
        r = int(m.rng.choice([1, 1, 2]))
        mask[cx - r:cx + r + 1, cy] = True
        mask[cx, cy - r:cy + r + 1] = True
        if r == 2 and m.rng.random() < 0.5:
            mask[cx - 1:cx + 2, cy - 1:cy + 2] = True
    paint_tops(m, mask, shades("stain")[1:], only=stone_idx)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(W, D, HEIGHT, seed=7)
    palette(m)
    rng = m.rng

    m.box(1, 1, 0, W - 2, D - 2, BED_Z, "joint")

    hues = list(HUE_P_LIT)
    lit_p, dim_p = np.array(list(HUE_P_LIT.values())), np.array(list(HUE_P_DIM.values()))
    for i, j, w, d in layout(rng):
        x, y = i * CELL, j * CELL
        sw, sd = w * CELL - 1, d * CELL - 1
        u, v = (i + w / 2) / X_CELLS, (j + d / 2) / Y_CELLS
        g = blob(u, v, GLOW[0], GLOW[1], 2.2 * GLOW[2], 2.2 * GLOW[3])
        hue = hues[int(rng.choice(len(hues), p=g * lit_p + (1 - g) * dim_p))]
        if rng.random() < 0.8 * blob(u, v, *GLOW):
            hue = "warm"
        top = TILE_Z + int(rng.choice(TILE_JITTER))
        stone(m, x, y, sw, sd, top, hue)
        rim(m, x, y, sw, sd, top, hue)

    for hue in HUES:
        m.vary(shades(hue), target=f"{hue}1", p=[0.25, 0.5, 0.25])
    m.vary(shades("body"), target="body1", p=[0.25, 0.5, 0.25])

    stone_idx = {m.pal.idx(f"{h}{k}") for h in HUES for k in range(4)}
    U, V = np.meshgrid(np.arange(W) / W, np.arange(D) / D, indexing="ij")

    # blotchy stain patches + small crosses
    field = smooth_noise(m, (W, D), 4.0)
    dens = np.clip((field - 0.55) * 2.2, 0, 0.9)
    paint_tops(m, rng.random((W, D)) < dens, shades("stain"), only=stone_idx)
    crosses(m, 70, stone_idx)

    # wet blue-white speckle and warm gold glints
    wet = np.clip(sum(blob(U, V, cu, cv, r) for cu, cv, r in WET_SPOTS), 0, 1)
    paint_tops(m, rng.random((W, D)) < 0.9 * np.clip(wet * 1.6, 0, 1), shades("damp"), only=stone_idx)
    damp_idx = {m.pal.idx(c) for c in shades("damp")}
    paint_tops(m, rng.random((W, D)) < 0.5 * wet ** 1.5, shades("wet"), only=stone_idx | damp_idx)
    glint = sum(blob(U, V, cu, cv, r) for cu, cv, r in GLINT_SPOTS)
    paint_tops(m, rng.random((W, D)) < 0.45 * np.clip(glint, 0, 1), shades("glint"), only=stone_idx)

    return m
