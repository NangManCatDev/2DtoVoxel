"""Five spreading voxel trees in stone tree pits — reference/c1c2607b-d235-4765-a8e6-feab0d7757bc.png

Kit sheet: five broadleaf trees in a row (round, tall, wide dome, tall irregular, leaning),
each standing in a square tree pit (a ring of beige stone blocks) with a slate-green iron
grate around a buttressed trunk. Every tree, pit included, is drawn inside its own m.part(),
so each one is a separate object in the .vox.

The sheet is an orthographic view at az 45 / el ~35 (the pit edges slope equally to both
sides and the top diamond drops 0.58 px per px sideways), so a screen-horizontal row is a
world diagonal: the trees are spaced along (+x, -y).

Crowns, limbs and trunks are described in REFERENCE PIXELS read off `voxtool ref grid`:
a lobe is (px, py, radius_px), a trunk / limb is a polyline. screen_to_world() turns a
screen point plus a depth along the view direction into voxel coordinates, so the front
view matches the sheet by construction.

Layout (x right, y depth with y=0 front, z up):
  pit     BASE x BASE footprint, stone ring RING wide and STONE_H high in BLOCK-sized
          blocks; grate flush with the stone top: frame, bars every GRATE_P, corner
          plates with bolts; dark soil below
  trunk   from the pit centre, buttress roots over the grate, bark in vertical streaks;
          the big limbs seen in the sheet, plus a thin branch into every lobe
  crown   the lobes measured on the sheet lie in the trunk's plane; m.crown_depth() spreads
          them through a round, upright crown with the same outline (copies along each lobe's
          line of sight, inside the ellipsoid that outline implies), and m.foliage() covers them with small leaf clumps over a dark
          core, yellow-green single cubes on top. Leaves outside the sheet's outline are
          then cut (m.carve_to_reference)
"""
import math

import numpy as np

from voxtool import Model

NAME = "c1c2607b_d235_4765_a8e6_feab0d7757bc"
REFERENCE = "reference/c1c2607b-d235-4765-a8e6-feab0d7757bc.png"
AZ, EL = 45, 35
VIEW = {"azimuth": AZ, "elevation": EL}
CUTOUT = {"keep": "all"}
RES = 1

# reference measurements (pixels of the reference image)
PX = 8.18          # pixels per voxel: the 24-voxel pit's half diagonal spans 139 px sideways
GY = 591           # screen y of a pit centre at ground level (the same for all five)

# pit
BASE, RING, STONE_H, BLOCK, GRATE_P = 24, 4, 4, 4, 3
# grid: pit centre of the left-most tree; the others follow along (+x, -y); room around the
# crowns for crown_depth's copies behind / in front of them
FIRST_X, FIRST_Y = 48, 192
GRID = (242, 242, 104)
LOBE_SCALE = 1.15  # lobe radii measured on the sheet fall a little short of its lumpy outline
CLUMP = 1.6        # foliage clump radius: the sheet's leaf clusters are 1-2 voxels
TRUNK_K = 0.88     # trunk radius factor (the measured radii include the bark's knobs)

LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3", "leaf4", "leaf5"]
BARK = ["bark0", "bark1", "bark2", "bark3"]
BARK_P = [0.42, 0.26, 0.18, 0.14]
STONES = ["stone0", "stone1", "stone2"]

# cx = screen x of the pit centre; lobes (px, py, r_px); trunk (px, py, r_vox) bottom-up;
# limbs (r0, r1, [(px, py), ...]) starting on the trunk
TREES = [
    dict(name="round", cx=261,
         lobes=[(250, 200, 52), (185, 225, 40), (330, 210, 45), (385, 240, 36), (60, 298, 42),
                (130, 280, 38), (175, 315, 50), (255, 290, 60), (330, 300, 50), (400, 330, 52),
                (440, 365, 32), (90, 385, 55), (175, 390, 48), (360, 400, 46), (425, 460, 50),
                (128, 462, 36), (215, 450, 28), (320, 450, 28)],
         trunk=[(261, 588, 3.8), (262, 530, 3.4), (266, 460, 3.0), (272, 390, 2.5), (265, 320, 2.0),
                (255, 240, 1.5)],
         limbs=[(2.0, 1.1, [(258, 470), (200, 440), (135, 405)]),
                (1.8, 1.0, [(276, 445), (330, 425), (390, 410), (430, 440)]),
                (1.6, 1.0, [(268, 400), (220, 350), (175, 320)]),
                (1.6, 1.0, [(272, 380), (330, 330), (395, 300)]),
                (1.4, 0.9, [(262, 460), (215, 455), (150, 465)])]),
    dict(name="tall", cx=652,
         lobes=[(680, 60, 40), (655, 115, 50), (605, 100, 30), (745, 150, 38), (720, 125, 35),
                (545, 185, 45), (610, 190, 40), (530, 245, 42), (600, 260, 50), (770, 225, 48),
                (700, 230, 40), (510, 330, 32), (560, 330, 45), (790, 325, 45), (720, 320, 40),
                (540, 410, 42), (600, 440, 38), (730, 385, 50), (750, 455, 42), (695, 290, 35)],
         trunk=[(652, 588, 3.8), (655, 520, 3.3), (656, 420, 2.8), (658, 300, 2.3), (662, 200, 1.7),
                (668, 110, 1.2)],
         limbs=[(2.0, 1.1, [(656, 445), (700, 400), (745, 360)]),
                (1.8, 1.0, [(652, 425), (600, 395), (555, 370)]),
                (1.6, 1.0, [(658, 330), (720, 280), (775, 245)]),
                (1.5, 0.9, [(656, 300), (600, 260), (550, 215)]),
                (1.4, 0.9, [(660, 230), (720, 180), (750, 155)])]),
    dict(name="dome", cx=1053,
         lobes=[(1015, 255, 42), (1080, 270, 35), (1160, 290, 45), (1220, 320, 38), (1260, 360, 40),
                (905, 330, 38), (960, 320, 40), (870, 400, 48), (900, 470, 40), (960, 400, 50),
                (1050, 350, 55), (1130, 360, 50), (1200, 420, 45), (1255, 460, 42), (1165, 470, 40),
                (980, 465, 30), (1110, 440, 30)],
         trunk=[(1053, 588, 3.9), (1056, 520, 3.5), (1058, 450, 3.0), (1060, 390, 2.4), (1050, 320, 1.8),
                (1030, 270, 1.3)],
         limbs=[(2.2, 1.2, [(1050, 465), (980, 452), (920, 440), (875, 420)]),
                (2.2, 1.2, [(1064, 455), (1130, 432), (1200, 410), (1250, 380)]),
                (1.8, 1.0, [(1056, 405), (1010, 340), (990, 290)]),
                (1.8, 1.0, [(1062, 405), (1120, 340), (1170, 300)]),
                (1.4, 0.9, [(1060, 470), (1150, 470), (1230, 465)])]),
    dict(name="tall_irregular", cx=1491,
         lobes=[(1440, 75, 45), (1470, 120, 40), (1535, 140, 42), (1585, 175, 32), (1335, 185, 40),
                (1400, 195, 45), (1460, 210, 40), (1380, 255, 28), (1500, 290, 55), (1560, 250, 40),
                (1640, 270, 45), (1665, 330, 32), (1600, 330, 40), (1420, 340, 45), (1360, 410, 48),
                (1450, 410, 40), (1620, 415, 48), (1560, 470, 42), (1470, 465, 32), (1530, 380, 40)],
         trunk=[(1491, 588, 3.8), (1494, 520, 3.3), (1505, 420, 2.8), (1510, 320, 2.3), (1510, 230, 1.8),
                (1485, 140, 1.3), (1450, 90, 1.0)],
         limbs=[(2.0, 1.1, [(1497, 440), (1430, 410), (1365, 400)]),
                (1.8, 1.0, [(1508, 350), (1570, 310), (1640, 280)]),
                (1.6, 1.0, [(1505, 400), (1560, 420), (1625, 420)]),
                (1.5, 0.9, [(1508, 270), (1440, 230), (1375, 200)]),
                (1.4, 0.9, [(1510, 240), (1550, 190), (1580, 170)])]),
    dict(name="leaning", cx=1910,
         lobes=[(2065, 115, 45), (2010, 150, 38), (1945, 200, 48), (1885, 230, 30), (2085, 210, 45),
                (2100, 290, 42), (2010, 250, 50), (1960, 310, 40), (1830, 310, 48), (1770, 385, 55),
                (1795, 452, 38), (1870, 360, 40), (1920, 355, 35), (2060, 385, 45), (2070, 460, 40),
                (2110, 500, 22), (1850, 430, 30)],
         trunk=[(1910, 588, 3.9), (1912, 520, 3.5), (1930, 450, 3.1), (1960, 390, 2.7), (1995, 320, 2.2),
                (2020, 250, 1.8), (2045, 170, 1.3), (2065, 120, 1.0)],
         limbs=[(2.4, 1.3, [(1908, 455), (1885, 400), (1870, 340)]),
                (2.0, 1.1, [(1905, 470), (1840, 445), (1775, 420)]),
                (1.8, 1.0, [(1968, 392), (2040, 385), (2100, 380)]),
                (1.6, 1.0, [(1995, 330), (2060, 300), (2110, 280)]),
                (1.4, 0.9, [(1960, 395), (2020, 430), (2075, 470)])]),
]


def palette(m: Model):
    p = m.pal
    p.add("leaf0", "#12300c"); p.add("leaf1", "#1a4612"); p.add("leaf2", "#255f19"); p.add("leaf3", "#337a24")
    p.add("leaf4", "#4d982f"); p.add("leaf5", "#80c040"); p.add("leaf_sh", "#0e260a")
    p.add("bark0", "#9a6234"); p.add("bark1", "#83532b"); p.add("bark2", "#ab703d"); p.add("bark3", "#5c3a19")
    p.add("stone0", "#ece1ca"); p.add("stone1", "#e0d3b8"); p.add("stone2", "#d4c6a8")
    p.add("stone3", "#b9ab8c"); p.add("stone_dk", "#a09477")
    p.add("iron", "#344b4b"); p.add("iron_dk", "#1f2d2d"); p.add("iron_lt", "#4a6463")
    p.add("bolt", "#a8bdb7"); p.add("soil", "#120c06")


# ---------------------------------------------------------------- geometry helpers

def screen_to_world(centre, u, v, s=0.0):
    """Screen offset (u right, v up, in voxels) from a pit centre at ground level plus a
    depth s (positive = away from the camera) -> continuous world (x, y, z)."""
    c = math.sqrt(0.5)
    se, ce = math.sin(math.radians(EL)), math.cos(math.radians(EL))
    return (centre[0] + (u + s) * c, centre[1] + (s - u) * c, (v - s * se) / ce)


def ref_to_screen(tree, px, py):
    return (px - tree["cx"]) / PX, (GY - py) / PX


def _hash(*a):
    h = np.uint64(1469598103934665603)
    for k, x in enumerate(a):
        x = np.floor(np.asarray(x, float)).astype(np.int64).astype(np.uint64)
        h = h ^ (x * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h


def _box_around(pts, pad):
    pts = np.array(pts, float)
    lo = np.floor(pts.min(axis=0) - pad).astype(int)
    hi = np.ceil(pts.max(axis=0) + pad).astype(int) + 1
    return (*lo, *(hi - lo))


def _mid(m: Model, X, Y, Z):
    """Voxel centres in design units."""
    h = 0.5 / m.res
    return X + h, Y + h, Z + h


def tube(m: Model, p0, p1, r0, r1):
    """Round limb from p0 to p1 (continuous coords), radius r0 -> r1, bark in vertical
    streaks (colour per design column, changing every 3 units up)."""
    sl = m._slices(*_box_around([p0, p1], max(r0, r1) + 1))
    if sl is None:
        return
    X, Y, Z = m._coords(sl)
    P = np.stack(_mid(m, X, Y, Z), -1)
    a, b = np.array(p0, float), np.array(p1, float)
    d = b - a
    t = np.clip(((P - a) @ d) / max(d @ d, 1e-9), 0, 1)
    dist = np.linalg.norm(P - (a + t[..., None] * d), axis=-1)
    mask = dist <= r0 + (r1 - r0) * t
    pick = (_hash(X, Y, Z / 3) % np.uint64(1000)).astype(float) / 1000
    cum = np.cumsum(BARK_P)
    idx = np.array([m.pal.idx(c) for c in BARK], np.uint8)[np.searchsorted(cum, pick, side="right").clip(0, 3)]
    region = m.v[sl]
    region[mask] = idx[mask]


# ---------------------------------------------------------------- pieces

def pit(m: Model, xc, yc):
    """Stone tree pit centred on (xc, yc) with an iron grate flush with its top."""
    x0, y0 = xc - BASE // 2, yc - BASE // 2
    n = BASE - 2 * RING
    m.box(x0, y0, 0, BASE, BASE, STONE_H, "stone0")
    m.carve(x0 + RING, y0 + RING, 0, n, n, STONE_H)
    ids = np.array([m.pal.idx(c) for c in STONES], np.uint8)
    seam, dark = m.pal.idx("stone3"), m.pal.idx("stone_dk")
    top = STONE_H - 1 / m.res

    def stones(X, Y, Z):
        bx, by = np.floor((X - x0) / BLOCK), np.floor((Y - y0) / BLOCK)
        c = ids[(_hash(bx, by) % np.uint64(3)).astype(int)]
        fx, fy = (X - x0) % BLOCK, (Y - y0) % BLOCK
        last = BLOCK - 1 / m.res
        edge = (fx >= last) | (fy >= last) | ((Z >= top) & ((fx < 1 / m.res) | (fy < 1 / m.res)))
        c = np.where(edge, seam, c)
        return np.where(_hash(X * m.res, Y * m.res, Z * m.res) % np.uint64(100) < 6, dark, c)
    m.paint_fn(x0, y0, 0, BASE, BASE, STONE_H, stones)

    gz = STONE_H - 1
    m.box(x0 + RING, y0 + RING, 0, n, n, 2, "soil")
    m.box(x0 + RING - 1, y0 + RING - 1, gz, n + 2, n + 2, 1, "iron")           # frame
    gx, gy = x0 + RING, y0 + RING
    m.carve(gx, gy, gz, n, n, 1)
    m.where(gx, gy, gz, n, n, 1, lambda X, Y, Z: ((X - gx) % GRATE_P < 1) | ((Y - gy) % GRATE_P < 1), "iron")
    m.box(gx, gy, gz - 1, n, n, 1, "iron_dk", only_empty=True)                 # shadowed bars below
    m.where(gx, gy, gz - 1, n, n, 1, lambda X, Y, Z: ((X - gx) % GRATE_P >= 1) & ((Y - gy) % GRATE_P >= 1), None)
    for cx, cy in ((x0 + RING - 1, y0 + RING - 1), (x0 + BASE - RING - 2, y0 + RING - 1),
                   (x0 + RING - 1, y0 + BASE - RING - 2), (x0 + BASE - RING - 2, y0 + BASE - RING - 2)):
        m.box(cx, cy, gz, 3, 3, 1, "iron_lt")                                 # corner plates
        m.box(cx + 1, cy + 1, gz + 1, 1, 1, 1, "bolt")


def tree(m: Model, t: dict, xc, yc):
    centre = (xc + 0.5, yc + 0.5)
    pit(m, xc, yc)

    def world(px, py, s=0.0):
        return screen_to_world(centre, *ref_to_screen(t, px, py), s)

    # lobes as measured: in the trunk's plane, r = the outline radius on the sheet (a little
    # short of the lumpy outline, hence LOBE_SCALE); crown_depth() makes the crown round and
    # upright with the same outline
    lobes = [(*world(px, py), pr / PX * LOBE_SCALE) for px, py, pr in t["lobes"]]
    crown = m.crown_depth(lobes, *centre, VIEW)
    top = max(z for _, _, z, _ in crown) - 2

    # trunk polyline (it stops inside the crown) + buttress roots over the grate
    nodes = [(world(px, py), r * TRUNK_K) for px, py, r in t["trunk"]]
    nodes = [n for n in nodes if n[0][2] <= top] or nodes[:2]
    for (a, ra), (b, rb) in zip(nodes, nodes[1:]):
        tube(m, a, b, ra, rb)
    base = nodes[0][0]
    ang0 = float(m.rng.uniform(0, 90))
    for k in range(5):
        a = math.radians(ang0 + 72 * k + float(m.rng.uniform(-12, 12)))
        tube(m, (base[0], base[1], 9), (base[0] + 4.5 * math.cos(a), base[1] + 4.5 * math.sin(a), STONE_H + 0.5),
             2.2, 1.6)

    # the big limbs seen in the sheet
    for r0, r1, pts in t["limbs"]:
        ps = [world(px, py) for px, py in pts]
        lens = [math.dist(a, b) for a, b in zip(ps, ps[1:])]
        tot, run = sum(lens), 0.0
        for a, b, ln in zip(ps, ps[1:], lens):
            ra = r0 + (r1 - r0) * run / tot
            run += ln
            tube(m, a, b, ra, r0 + (r1 - r0) * run / tot)

    def trunk_at(z):
        for (a, _), (b, _) in zip(nodes, nodes[1:]):
            if a[2] <= z <= b[2]:
                f = (z - a[2]) / max(b[2] - a[2], 1e-6)
                return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
        return nodes[-1][0]

    z_fork = nodes[min(2, len(nodes) - 1)][0][2]
    z_top = nodes[-1][0][2]
    for cx, cy, cz, r in crown[::max(1, len(crown) // len(lobes))]:          # thin branches through the crown
        zs = min(max(cz - 8, z_fork), z_top)
        tube(m, trunk_at(zs), (cx, cy, cz), 1.3, 0.8)

    # crown: covered with leaf clumps
    m.foliage(crown, LEAVES[:5], core="leaf_sh", tips="leaf5", clump=CLUMP)


def build() -> Model:
    m = Model(*GRID, seed=11, res=RES)
    palette(m)
    c = math.sqrt(0.5)
    for i, t in enumerate(TREES):
        U = (t["cx"] - TREES[0]["cx"]) / PX
        xc, yc = FIRST_X + round(U * c), FIRST_Y - round(U * c)
        with m.part(f"tree{i + 1}_{t['name']}"):
            tree(m, t, xc, yc)
    # leaves the lobes' round shapes put outside the sheet's outline (trunks and pits stay); no
    # margin: a kept voxel already reaches ~half a voxel past its centre
    m.carve_to_reference(REFERENCE, VIEW, only=LEAVES + ["leaf_sh"], margin=0, cutout=CUTOUT)
    # the sheet's own shading: leaves accept bigger changes (light tops / dark crevices) than
    # bark, stone and iron, which must not take a neighbouring material's colour
    m.paint_reference(REFERENCE, VIEW, colors=110, tol=45, only=LEAVES + ["leaf_sh"], cutout=CUTOUT)
    m.paint_reference(REFERENCE, VIEW, colors=90, tol=30, cutout=CUTOUT,
                      only=BARK + STONES + ["stone3", "stone_dk", "iron", "iron_dk", "iron_lt", "soil"])
    return m
