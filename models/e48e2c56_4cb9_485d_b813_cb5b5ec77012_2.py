"""Five voxel trees in stone tree pits — reference/e48e2c56-4cb9-485d-b813-cb5b5ec77012.png

Kit sheet: five broadleaf trees in a row, each standing in a square tree pit (a ring of
beige stone blocks) with a slate-blue iron grate around the trunk. Every tree, pit
included, is drawn inside its own m.part(), so each one is a separate object in the .vox.

The sheet is an orthographic view at az 45 / el 28, so a screen-horizontal row is a world
diagonal: the pits sit along (+x, -y) on integer voxels.

Everything above the pits is described in REFERENCE PIXELS read off `voxtool ref crop`:
trunks and visible limbs are polylines of (px, py, radius_vox), crown lobes are
(px, py, radius_px). world() turns a reference pixel plus a depth s along the view direction
into voxel coordinates, so the front view lines up with the sheet by construction.

Crowns use the library's foliage(): every lobe is the FRONT of a slab of copies at the same
height going back through the crown (deeper near the crown's middle), so the clusters
that face the camera sit where the reference shows them and the crown has real depth from
other angles. Every lobe also gets a hidden limb from the trunk. Lobes are drawn a little
big; fit_to_reference() then trims leaves and limbs that land on the reference's
background (outline shrunk by MARGIN: a cube overhangs its centre), and removes the leaves
in front of bark wherever the reference shows bark (the branches seen through the crowns).
fill_gaps() adds leaf clumps where the reference shows leaves but nothing lands, and bark
knots in the trunk's plane where it shows bark. Finally paint_reference() takes the colours
(cluster light/shade, bark, stone stains) from the picture.

Layout (x right, y depth with y=0 front, z up):
  pit     BASE x BASE, stone ring RING wide and STONE_H high in BLOCK-long blocks; grate
          flush with the stone top: frame + bars at a GRATE pitch, corner plates with
          bolts, dark soil below
  trunk   from the pit centre, root flare over the grate, bark in vertical streaks
  crown   foliage() clusters, dark core in the crevices, light cube tips on top
"""
import math
import os

import numpy as np
from scipy import ndimage

from voxtool import Model
from voxtool.score import reference_cutout

NAME = "e48e2c56_4cb9_485d_b813_cb5b5ec77012_2"
REFERENCE = "reference/e48e2c56-4cb9-485d-b813-cb5b5ec77012.png"
AZ, EL = 45, 28
VIEW = {"azimuth": AZ, "elevation": EL}
CUTOUT = {"keep": "all"}
RES = 1

# reference measurements (pixels of the reference image)
PX = 7.86          # pixels per voxel: a 25-voxel pit spans 278 px sideways (25 * sqrt2 * PX)
GY = 600           # screen y of a pit centre at ground level
CX0 = 239          # screen x of the left-most pit centre

# pit
BASE, RING, STONE_H, BLOCK = 25, 3, 4, 5
GRATE = 3          # bar pitch: 1-voxel bars, 2 x 2 holes (BASE - 2 * RING - 1 must divide by it)
GRID = (224, 224, 100)
X0, Y0 = 32, 184   # voxel of the left-most pit centre; the others follow along (+x, -y)

# crown
GROW = 1.1         # lobe radii are drawn this much bigger, fit_to_reference trims them
DEPTH_K = 0.7      # crown depth relative to its width
DMAX = 11          # deepest a lobe's front sits in front of the trunk (voxels)
CLUMP = 1.8
MARGIN = -4        # px of slack around the reference outline before a voxel is cut; negative:
                   # a voxel's centre must be this far inside (its cube overhangs its centre)
SPLITS = (470, 804, 1288, 1702)   # screen x between the trees (the crowns don't overlap there)
BARK_SHARE = 0.3   # a leaf in front of bark goes when this much of its footprint is bark in the reference

LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3", "leaf4"]
BARK = ["bark1", "bark1", "bark0", "bark0", "bark2", "bark3"]
PIT_COLOURS = ["stone0", "stone1", "stone2", "seam", "stone_dk", "iron", "iron_dk", "iron_lt", "bolt", "soil"]

C = math.sqrt(0.5)
SE, CE = math.sin(math.radians(EL)), math.cos(math.radians(EL))
OX, OY = X0 + 0.5, Y0 + 0.5      # physical centre of the first pit

# cx = measured screen x of the pit centre; trunk / limbs (px, py, r_vox) bottom-up; lobes (px, py, r_px)
TREES = [
    dict(name="round", cx=239,
         trunk=[(239, 600, 3.0), (239, 545, 2.8), (240, 480, 2.6), (240, 420, 2.2), (238, 340, 1.7),
                (240, 250, 1.2)],
         limbs=[[(232, 440, 1.5), (190, 410, 1.2), (140, 390, 0.9)],
                [(232, 480, 1.4), (200, 470, 1.1), (165, 460, 0.9)],
                [(248, 470, 1.5), (280, 430, 1.2), (310, 395, 0.9)],
                [(245, 400, 1.3), (275, 350, 1.0), (290, 320, 0.8)],
                [(237, 400, 1.3), (210, 350, 1.0), (185, 320, 0.8)]],
         lobes=[(225, 170, 55), (300, 165, 45), (145, 220, 45), (330, 210, 50), (405, 290, 55),
                (400, 380, 58), (80, 310, 55), (90, 405, 50), (160, 450, 50), (175, 300, 55),
                (265, 300, 65), (320, 450, 50), (340, 330, 50), (130, 360, 40)]),
    dict(name="tall", cx=647,
         trunk=[(647, 600, 3.0), (645, 540, 2.8), (640, 460, 2.5), (636, 380, 2.2), (640, 300, 1.9),
                (650, 220, 1.5), (658, 140, 1.1)],
         limbs=[[(640, 400, 1.5), (680, 375, 1.2), (720, 345, 0.9)],
                [(638, 330, 1.3), (610, 300, 1.0), (585, 280, 0.8)],
                [(640, 470, 1.4), (605, 450, 1.1), (575, 430, 0.9)],
                [(648, 480, 1.3), (685, 450, 1.0), (715, 430, 0.8)]],
         lobes=[(668, 95, 60), (612, 150, 50), (715, 165, 45), (760, 205, 40), (538, 232, 45),
                (612, 250, 55), (700, 260, 55), (530, 330, 50), (565, 415, 58), (748, 330, 48),
                (722, 430, 55), (665, 320, 40)]),
    dict(name="dome", cx=1052,
         trunk=[(1052, 600, 3.1), (1050, 540, 2.9), (1048, 470, 2.6), (1045, 420, 2.3), (1040, 340, 1.8),
                (1038, 260, 1.3)],
         limbs=[[(1040, 470, 1.6), (1000, 455, 1.3), (960, 440, 1.0), (930, 430, 0.8)],
                [(1058, 460, 1.5), (1090, 430, 1.2), (1115, 400, 0.9)],
                [(1040, 360, 1.2), (1000, 320, 0.9)],
                [(1045, 360, 1.2), (1090, 300, 0.9)]],
         lobes=[(1038, 200, 55), (950, 245, 45), (1128, 230, 48), (1200, 295, 55), (1240, 390, 48),
                (885, 320, 58), (850, 385, 42), (922, 450, 48), (1160, 410, 62), (1020, 350, 65),
                (1095, 295, 58), (965, 300, 50), (930, 380, 45)]),
    dict(name="tall_irregular", cx=1476,
         trunk=[(1476, 600, 3.1), (1477, 540, 2.9), (1472, 470, 2.6), (1470, 410, 2.3), (1480, 330, 1.9),
                (1495, 240, 1.5), (1500, 160, 1.1)],
         limbs=[[(1490, 330, 1.5), (1550, 315, 1.2), (1610, 300, 0.9)],
                [(1468, 460, 1.4), (1430, 445, 1.1), (1395, 430, 0.9)],
                [(1480, 480, 1.4), (1515, 460, 1.1), (1545, 440, 0.9)],
                [(1478, 360, 1.3), (1440, 330, 1.0), (1410, 300, 0.8)]],
         lobes=[(1492, 100, 60), (1392, 158, 50), (1530, 195, 55), (1622, 210, 45), (1332, 280, 48),
                (1430, 262, 62), (1650, 285, 45), (1490, 345, 68), (1365, 400, 62), (1385, 460, 48),
                (1628, 370, 58), (1585, 445, 58), (1560, 270, 40)]),
    dict(name="leaning", cx=1882,
         trunk=[(1884, 600, 3.0), (1888, 540, 2.8), (1893, 490, 2.6), (1902, 450, 2.5), (1920, 400, 2.3),
                (1960, 350, 2.0), (1990, 305, 1.7), (2005, 250, 1.4), (2020, 190, 1.1)],
         limbs=[[(1905, 430, 1.6), (1860, 400, 1.3), (1820, 380, 1.0), (1790, 370, 0.8)],
                [(1893, 480, 1.5), (1860, 460, 1.2), (1820, 450, 0.9)],
                [(1915, 420, 1.4), (1950, 420, 1.1), (1985, 410, 0.9)],
                [(1985, 320, 1.5), (2030, 300, 1.2), (2070, 280, 0.9)]],
         lobes=[(2020, 150, 55), (2088, 180, 42), (2112, 250, 40), (1930, 210, 48), (2060, 270, 65),
                (1850, 255, 42), (1890, 315, 62), (1778, 335, 58), (2035, 400, 68), (1765, 452, 55),
                (1830, 415, 40), (1965, 285, 40)]),
]


def palette(m: Model):
    p = m.pal
    p.add("leaf_core", "#06200a")
    p.add("leaf0", "#0d3812"); p.add("leaf1", "#144a19"); p.add("leaf2", "#1c5c20")
    p.add("leaf3", "#266e28"); p.add("leaf4", "#358234"); p.add("leaf_tip", "#46983f")
    p.add("bark0", "#6b4523"); p.add("bark1", "#5a3818"); p.add("bark2", "#7e5530"); p.add("bark3", "#4a2d12")
    p.add("stone0", "#e6dbc5"); p.add("stone1", "#ddd0b6"); p.add("stone2", "#ece3d1")
    p.add("seam", "#c2b294"); p.add("stone_dk", "#a8977a")
    p.add("iron", "#4c615d"); p.add("iron_dk", "#2c3936"); p.add("iron_lt", "#61766f")
    p.add("bolt", "#9db0a8"); p.add("soil", "#120e08")


# ---------------------------------------------------------------- reference <-> world

def world(px, py, s=0.0):
    """Physical point (voxel centres at i + 0.5) seen at reference pixel (px, py), s voxels
    behind the plane through the pit centres (negative = towards the camera)."""
    u, v = (px - CX0) / PX, (GY - py) / PX
    return np.array([OX + (u + s) * C, OY + (s - u) * C, (v - s * SE) / CE])


def lib(p):
    """Physical point -> library coordinate (the DSL puts voxel i at i)."""
    return np.asarray(p, float) - 0.5


def screen(P):
    """Physical points [N, 3] -> reference pixels (px, py) and depth s."""
    dx, dy = P[:, 0] - OX, P[:, 1] - OY
    u, s = (dx - dy) * C, (dx + dy) * C
    v = P[:, 2] * CE + s * SE
    return CX0 + u * PX, GY - v * PX, s


def _hash(*a):
    h = np.uint64(1469598103934665603)
    for k, x in enumerate(a):
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h


# ---------------------------------------------------------------- pieces

def pit(m: Model, xc, yc):
    """Stone tree pit centred on voxel (xc, yc) with an iron grate flush with its top."""
    x0, y0 = xc - BASE // 2, yc - BASE // 2
    n = BASE - 2 * RING
    m.box(x0, y0, 0, BASE, BASE, STONE_H, "stone0")
    m.carve(x0 + RING, y0 + RING, 0, n, n, STONE_H)
    ids = np.array([m.pal.idx(c) for c in ("stone0", "stone1", "stone2")], np.uint8)
    seam, dark = m.pal.idx("seam"), m.pal.idx("stone_dk")

    def stones(X, Y, Z):
        bx, by = (X - x0) // BLOCK, (Y - y0) // BLOCK
        c = ids[(_hash(bx, by) % np.uint64(3)).astype(int)]
        edge = ((X - x0) % BLOCK == BLOCK - 1) | ((Y - y0) % BLOCK == BLOCK - 1)
        c = np.where(edge, seam, c)
        return np.where(_hash(X, Y, Z) % np.uint64(100) < 5, dark, c)
    m.paint_fn(x0, y0, 0, BASE, BASE, STONE_H, stones)

    gx, gy, gz = x0 + RING, y0 + RING, STONE_H - 1
    bars = lambda X, Y, Z: ((X - gx) % GRATE == 0) | ((Y - gy) % GRATE == 0)          # noqa: E731
    m.box(gx, gy, 0, n, n, 1, "soil")
    m.where(gx, gy, gz, n, n, 1, bars, "iron")
    m.where(gx, gy, gz, n, n, 1, lambda X, Y, Z: (X == gx) | (Y == gy) | (X == gx + n - 1) | (Y == gy + n - 1),
            "iron_dk")
    m.where(gx, gy, gz - 1, n, n, 1, bars, "iron_dk")
    for cx, cy in ((gx, gy), (gx + n - 3, gy), (gx, gy + n - 3), (gx + n - 3, gy + n - 3)):
        m.box(cx, cy, gz, 3, 3, 1, "iron_lt")                                 # corner plates
        m.set(cx + 1, cy + 1, gz + 1, "bolt")


def tree(m: Model, t: dict, xc, yc):
    pit(m, xc, yc)
    trunk =[(world(px, py), r) for px, py, r in t["trunk"]]
    m.tube([lib(p) for p, _ in trunk], [r for _, r in trunk], BARK)
    foot = trunk[0][0]
    r0 = trunk[0][1]
    for a in float(m.rng.uniform(0, 2 * math.pi)) + np.arange(5) * 2 * math.pi / 5:
        d = np.array([math.cos(a), math.sin(a), 0.0])
        m.tube([lib(foot + [0, 0, 8]), lib(foot + d * r0 * 1.3 + [0, 0, STONE_H + 1.2]),
                lib(foot + d * r0 * 2.4 + [0, 0, STONE_H + 0.2])], [r0 * 0.75, r0 * 0.55, r0 * 0.3], BARK)
    for limb in t["limbs"]:
        m.tube([lib(world(px, py)) for px, py, _ in limb], [r for _, _, r in limb], BARK)

    zs = np.array([p[2] for p, _ in trunk])

    def trunk_at(z):
        z = float(np.clip(z, zs[2], zs[-1]))
        for (a, _), (b, _) in zip(trunk, trunk[1:]):
            if a[2] <= z <= b[2]:
                return a + (b - a) * (z - a[2]) / max(b[2] - a[2], 1e-6)
        return trunk[-1][0]

    # crown: every lobe is the front of a slab of copies going back through the crown
    uv = [((px - CX0) / PX, (GY - py) / PX, r * GROW / PX) for px, py, r in t["lobes"]]
    umin, umax = min(u - r for u, _, r in uv), max(u + r for u, _, r in uv)
    uc, R = (umin + umax) / 2, (umax - umin) / 2
    lobes = []
    for (px, py, _), (u, v, r) in zip(t["lobes"], uv):
        sf = float(np.clip(DEPTH_K * math.sqrt(max(R * R - (u - uc) ** 2, 0.0)) - 0.5 * r, 0, DMAX))
        front = world(px, py, -sf)
        n = 1 if sf < 2 else int(math.ceil(2 * sf / (0.9 * r))) + 1
        for k in np.linspace(0, 2 * sf, n):
            lobes.append((*lib(front + [k * C, k * C, 0]), r))
        mid = front + [sf * C, sf * C, 0]
        start = trunk_at(mid[2] - r)
        m.tube([lib(start), lib((start + mid) / 2 + [0, 0, r * 0.3]), lib(mid)], [1.4, 1.0, 0.7], BARK)
    m.foliage(lobes, LEAVES, clump=CLUMP, core="leaf_core", tips="leaf_tip")


# ---------------------------------------------------------------- fitting to the reference

_MASKS = {}


def _ref_masks():
    """(foreground, bark-brown, leaf-green) masks of the reference cutout."""
    if not _MASKS:
        im = np.asarray(reference_cutout(REFERENCE, os.path.join(os.getcwd(), "output", "_ref"),
                                         **CUTOUT)).astype(np.float32)
        fg = im[..., 3] > 127
        R, G, B = im[..., 0], im[..., 1], im[..., 2]
        brown = fg & (R > 1.1 * G) & (R > 1.3 * B + 4)
        _MASKS["m"] = (fg, brown, fg & (G > 1.08 * R + 2) & (G > 1.25 * B + 2))
        # share of bark pixels under a voxel's footprint (a leaf cube overhangs its centre)
        _MASKS["bark_share"] = ndimage.uniform_filter(brown.astype(np.float32), size=round(PX * 1.2))
    return _MASKS["m"]


def _project(m: Model, xs):
    """Filled voxels of one tree (screen x in [xs[0], xs[1]) px): index array, colours,
    reference pixel (ix, iy, clipped), inside-image flag, depth s and screen cell (cu, cv)."""
    fg = _ref_masks()[0]
    pts = np.argwhere(m.v > 0)
    px, py, s = screen((pts + 0.5) / m.res)
    sel = (px >= xs[0]) & (px < xs[1])
    pts, px, py, s = pts[sel], px[sel], py[sel], s[sel]
    H, W = fg.shape
    ix, iy = np.floor(px).astype(int), np.floor(py).astype(int)
    inside = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    cu, cv = np.round((px - CX0) / PX).astype(int), np.round((GY - py) / PX).astype(int)
    return pts, m.v[tuple(pts.T)], ix.clip(0, W - 1), iy.clip(0, H - 1), inside, s, cu, cv


def _cell_min(cu, cv, s, sel, box):
    """Smallest s per screen cell over the voxels in sel, inf where none; box = (cu0, cv0, w, h)."""
    buf = np.full(box[2:], np.inf)
    np.minimum.at(buf, (cu[sel] - box[0], cv[sel] - box[1]), s[sel])
    return buf


def fit_to_reference(m: Model, xs):
    """Cuts the leaves and limbs whose centre lands on the reference's background, and the
    leaves in front of bark where the reference shows bark (limbs seen through the crown).
    Pit voxels are never cut."""
    fg, brown, _ = _ref_masks()
    near = (ndimage.binary_dilation(fg, iterations=MARGIN) if MARGIN > 0 else
            ndimage.binary_erosion(fg, iterations=-MARGIN) if MARGIN < 0 else fg)
    pts, cols, ix, iy, inside, s, cu, cv = _project(m, xs)
    keep = np.isin(cols, [m.pal.idx(c) for c in PIT_COLOURS])
    bark = np.isin(cols, [m.pal.idx(c) for c in set(BARK)])
    cut = ~keep & ~(inside & near[iy, ix])
    box = (cu.min(), cv.min(), cu.max() - cu.min() + 1, cv.max() - cv.min() + 1)
    buf = ndimage.minimum_filter(_cell_min(cu, cv, s, bark, box), size=2)    # nearest bark per cell
    share = _MASKS["bark_share"][iy, ix]
    cut |= ~keep & ~bark & inside & (share > BARK_SHARE) & (s < buf[cu - box[0], cv - box[1]] - 0.5)
    m.v[tuple(pts[cut].T)] = 0
    return int(cut.sum())


def fill_gaps(m: Model, xs):
    """Screen cells (one voxel) above the pits where the reference shows leaves but no voxel
    lands get leaf clumps, just behind the crown's front surface around them. Cells where
    it shows bark but the front voxel isn't bark get a bark knot in the trunk's plane
    (s = 0); fit_to_reference then clears the leaves in front of it."""
    fg, brown, green = _ref_masks()
    pts, cols, ix, iy, inside, s, cu, cv = _project(m, xs)
    keep = np.isin(cols, [m.pal.idx(c) for c in PIT_COLOURS])
    bark = np.isin(cols, [m.pal.idx(c) for c in set(BARK)])
    pad = 4
    box = (cu.min() - pad, cv.min() - pad, cu.max() - cu.min() + 1 + 2 * pad, cv.max() - cv.min() + 1 + 2 * pad)
    nearest = _cell_min(cu, cv, s, np.ones_like(keep), box)
    covered = np.isfinite(nearest)
    bark_front = covered & (_cell_min(cu, cv, s, bark, box) <= nearest)
    front = ndimage.minimum_filter(_cell_min(cu, cv, s, ~keep, box), size=7)
    gu, gv = np.meshgrid(np.arange(box[2]) + box[0], np.arange(box[3]) + box[1], indexing="ij")
    qx = np.floor(CX0 + gu * PX).astype(int).clip(0, fg.shape[1] - 1)
    qy = np.floor(GY - gv * PX).astype(int).clip(0, fg.shape[0] - 1)
    above = (GY - gv * PX < GY - 12 * PX) & (CX0 + gu * PX >= xs[0]) & (CX0 + gu * PX < xs[1])
    lobes = [world(CX0 + gu[a, b] * PX, GY - gv[a, b] * PX, front[a, b] + 1 if np.isfinite(front[a, b]) else 0.0)
             for a, b in zip(*np.nonzero(green[qy, qx] & ~covered & above))]
    knots = [world(CX0 + gu[a, b] * PX, GY - gv[a, b] * PX, 0.0)
             for a, b in zip(*np.nonzero(brown[qy, qx] & ~bark_front & above))]
    if lobes:
        m.foliage([(*lib(p), 1.6) for p in lobes], LEAVES, clump=CLUMP, core="leaf_core", tips="leaf_tip")
    for p in knots:
        m.tube([lib(p - [0, 0, 0.6]), lib(p + [0, 0, 0.6])], 1.0, BARK)
    return len(lobes), len(knots)


def build() -> Model:
    m = Model(*GRID, seed=7, res=RES)
    palette(m)
    cuts = [0, *SPLITS, 1e9]
    for i, t in enumerate(TREES):
        k = round((t["cx"] - CX0) / PX * C)          # diagonal steps from the first pit
        xs = (cuts[i], cuts[i + 1])
        with m.part(f"tree{i + 1}_{t['name']}"):
            tree(m, t, X0 + k, Y0 - k)
            fit_to_reference(m, xs)
            fill_gaps(m, xs)
            fit_to_reference(m, xs)
    fit_to_reference(m, (-1e9, 1e9))      # clumps that spilled over a split into an earlier tree's range
    m.paint_reference(REFERENCE, VIEW, cutout=CUTOUT)
    return m
