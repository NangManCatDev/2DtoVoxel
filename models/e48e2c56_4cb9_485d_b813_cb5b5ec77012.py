"""Five voxel trees in stone tree pits — reference/e48e2c56-4cb9-485d-b813-cb5b5ec77012.png

Kit sheet: five broadleaf trees in a row, each standing in a square tree pit (a ring of
beige stone blocks) with a slate-blue iron tree grate around the trunk. Every tree, pit
included, is drawn inside its own m.part(), so each one is a separate object in the .vox.

The sheet is an orthographic view at az 45 / el 28 (the pit edges slope equally to both
sides), so a screen-horizontal row is a world diagonal: the trees are spaced along (+x, -y).

Crowns are described in REFERENCE PIXELS read off `voxtool ref grid`: each lobe is
(px, py, radius_px) and the trunk is a polyline of (px, py, radius_vox). screen_to_world()
turns a screen point plus a depth along the view direction into voxel coordinates, so the
front view matches the sheet by construction. Every lobe is also copied in front of and
behind itself on the same screen spot, which gives the crown depth without changing the
silhouette.

Layout (x right, y depth with y=0 front, z up):
  pit     BASE x BASE footprint, stone ring RING wide and STONE_H high in BLOCK-sized
          blocks; grate flush with the stone top: frame, bars at a 2-voxel pitch, corner
          plates with bolts; dark soil below
  trunk   from the pit centre, root flare over the grate, bark in vertical streaks;
          a branch from the trunk into every lobe
  crown   every lobe = a dark core covered by small leaf clumps spread evenly over it
          (Fibonacci lattice); each clump is light on top and dark underneath and the
          dark core shows in the crevices between them (the reference's cauliflower
          florets); all cores are drawn before any clump so no core fills a crevice.
          Then 1-voxel dents and bumps, the bumps on top a shade lighter (loose leaf cubes)
"""
import math

import numpy as np

from voxtool import Model

NAME = "e48e2c56_4cb9_485d_b813_cb5b5ec77012"
REFERENCE = "reference/e48e2c56-4cb9-485d-b813-cb5b5ec77012.png"
AZ, EL = 45, 28
VIEW = {"azimuth": AZ, "elevation": EL}
CUTOUT = {"keep": "all"}

# reference measurements (pixels of the reference image)
PX = 7.75          # pixels per voxel: a 25-voxel pit edge spans 137 px sideways
GY = 601           # screen y of a pit centre at ground level (the same for all five)

# pit
BASE, RING, STONE_H, BLOCK = 25, 4, 4, 5
# grid: pit centre of the left-most tree; the others follow along (+x, -y)
FIRST_X, FIRST_Y = 36, 186
GRID = (224, 224, 100)
MAX_DEPTH = 11     # how far lobe copies sit in front of / behind the lobe (voxels)
# foliage detail: clump coverage (number of clumps on a lobe = CLUMPS * (core radius /
# clump radius)^2; 4 just touch), clump radii
CLUMPS, CLUMP_R = 4.5, (1.9, 2.8)

LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3", "leaf4"]
BARK = ["bark0", "bark1", "bark2", "bark3"]
BARK_P = [0.45, 0.25, 0.18, 0.12]
STONES = ["stone0", "stone1", "stone2"]

# cx = screen x of the pit centre; lobes (px, py, r_px); trunk (px, py, r_vox) bottom-up
TREES = [
    dict(name="round", cx=237,
         lobes=[(237, 170, 60), (150, 220, 45), (320, 210, 45), (75, 310, 45), (100, 390, 45),
                (165, 450, 50), (300, 440, 50), (395, 290, 45), (410, 360, 48), (380, 420, 40),
                (235, 290, 70), (160, 320, 55), (310, 330, 55)],
         trunk=[(237, 601, 3.4), (237, 560, 3.0), (236, 480, 2.7), (240, 400, 2.3), (237, 320, 1.8)]),
    dict(name="tall", cx=650,
         lobes=[(655, 78, 45), (620, 150, 55), (690, 150, 50), (530, 230, 45), (525, 320, 42),
                (560, 400, 55), (750, 220, 45), (760, 330, 40), (720, 420, 50), (640, 250, 60),
                (600, 330, 55), (690, 330, 55), (540, 190, 36), (775, 170, 30)],
         trunk=[(650, 601, 3.4), (650, 560, 3.0), (650, 450, 2.7), (648, 330, 2.3), (655, 230, 1.9),
                (655, 140, 1.5)]),
    dict(name="dome", cx=1052,
         lobes=[(1040, 190, 50), (970, 230, 45), (1130, 220, 40), (1200, 300, 50), (1238, 380, 45),
                (880, 320, 50), (850, 390, 40), (920, 460, 45), (1150, 430, 55), (1050, 330, 65),
                (980, 380, 60), (1110, 330, 55), (950, 280, 55), (1090, 260, 55)],
         trunk=[(1052, 601, 3.4), (1052, 560, 3.0), (1050, 480, 2.8), (1045, 420, 2.4), (1050, 320, 1.8)]),
    dict(name="tall_irregular", cx=1475,
         lobes=[(1490, 100, 55), (1385, 160, 45), (1560, 170, 45), (1620, 210, 40), (1650, 280, 40),
                (1335, 280, 45), (1430, 260, 60), (1540, 250, 55), (1490, 360, 65), (1340, 400, 50),
                (1390, 455, 50), (1610, 360, 50), (1570, 450, 55), (1450, 180, 50)],
         trunk=[(1475, 601, 3.4), (1475, 560, 3.0), (1478, 470, 2.7), (1470, 380, 2.4), (1480, 250, 2.0),
                (1490, 150, 1.5)]),
    dict(name="leaning", cx=1882,
         lobes=[(2020, 160, 60), (2060, 220, 55), (2110, 280, 40), (1950, 200, 45), (1900, 240, 45),
                (1840, 280, 40), (1990, 290, 65), (1900, 330, 60), (2050, 405, 62), (1780, 320, 35),
                (1760, 370, 40), (1765, 445, 52), (1830, 420, 40), (1850, 340, 45)],
         trunk=[(1882, 601, 3.4), (1885, 560, 3.0), (1895, 450, 2.7), (1955, 380, 2.4), (2000, 300, 2.0),
                (2030, 220, 1.6)]),
]


def palette(m: Model):
    p = m.pal
    p.add("leaf0", "#0b3310"); p.add("leaf1", "#134a18"); p.add("leaf2", "#1c6121")
    p.add("leaf3", "#28772b"); p.add("leaf4", "#3a9038"); p.add("leaf_sh", "#082409")
    p.add("bark0", "#8a5a32"); p.add("bark1", "#75492a"); p.add("bark2", "#9d6a3d"); p.add("bark3", "#5c3a1f")
    p.add("stone0", "#e4d6be"); p.add("stone1", "#dacaae"); p.add("stone2", "#ece2d0")
    p.add("stone3", "#c9b394"); p.add("stone_dk", "#a8916f")
    p.add("iron", "#4b6a6a"); p.add("iron_dk", "#2f4445"); p.add("iron_lt", "#648584")
    p.add("bolt", "#9db7b2"); p.add("soil", "#17150f")


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
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h


def _box_around(pts, pad):
    pts = np.array(pts, float)
    lo = np.floor(pts.min(axis=0) - pad).astype(int)
    hi = np.ceil(pts.max(axis=0) + pad).astype(int) + 1
    return (*lo, *(hi - lo))


def tube(m: Model, p0, p1, r0, r1):
    """Round limb from p0 to p1 (continuous coords), radius r0 -> r1, bark in vertical
    streaks (colour per voxel column, changing every 3 voxels up)."""
    sl = m._slices(*_box_around([p0, p1], max(r0, r1) + 1))
    if sl is None:
        return
    X, Y, Z = m._coords(sl)
    P = np.stack([X + 0.5, Y + 0.5, Z + 0.5], -1)
    a, b = np.array(p0, float), np.array(p1, float)
    d = b - a
    t = np.clip(((P - a) @ d) / max(d @ d, 1e-9), 0, 1)
    dist = np.linalg.norm(P - (a + t[..., None] * d), axis=-1)
    mask = dist <= r0 + (r1 - r0) * t
    pick = (_hash(X, Y, Z // 3) % np.uint64(1000)).astype(float) / 1000
    cum = np.cumsum(BARK_P)
    idx = np.array([m.pal.idx(c) for c in BARK], np.uint8)[np.searchsorted(cum, pick, side="right").clip(0, 3)]
    region = m.v[sl]
    region[mask] = idx[mask]


def _ball(m: Model, centre, r, noise):
    """(slices, X, Y, Z, mask) of a noisy ball over empty voxels, or None."""
    sl = m._slices(*_box_around([centre], r + 1.5))
    if sl is None:
        return None
    X, Y, Z = m._coords(sl)
    cx, cy, cz = centre
    d = np.sqrt((X + 0.5 - cx) ** 2 + (Y + 0.5 - cy) ** 2 + (Z + 0.5 - cz) ** 2) / r
    mask = (d + m.rng.uniform(-noise, noise, X.shape) <= 1.0) & (m.v[sl] == 0)
    return sl, X, Y, Z, mask


def _even_dirs(m: Model, n):
    """n unit vectors spread evenly over a sphere (Fibonacci lattice), randomly turned and
    jittered a little, so clumps cover a lobe without leaving holes."""
    k = np.arange(n) + 0.5
    zc = 1 - 2 * k / n
    a = math.pi * (1 + math.sqrt(5)) * k + float(m.rng.uniform(0, 2 * math.pi))
    rr = np.sqrt(1 - zc ** 2)
    d = np.stack([rr * np.cos(a), rr * np.sin(a), zc], -1) + m.rng.normal(0, 0.12, (n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _core_r(r):
    """Core radius of a lobe of outer radius r: the clumps on it end just past r
    (like the lumpy edge the lobe radii were measured on)."""
    return max(r - 0.85 * sum(CLUMP_R) / 2, 2.2)


def leaf_core(m: Model, centre, r):
    """Dark inner mass of a lobe; it shows through the crevices between the clumps."""
    b = _ball(m, centre, _core_r(r), 0.12)
    if b:
        sl, _, _, _, mask = b
        m.v[sl][mask] = m.pal.idx("leaf_sh")


def leaf_clumps(m: Model, centre, r):
    """Covers a lobe with small leaf clumps (the cauliflower look of the reference): each
    clump is a little noisy ball, light on its top and dark underneath, and the lower half
    of the lobe is shaded darker as a whole."""
    rm, rk = sum(CLUMP_R) / 2, _core_r(r)
    n = max(5, round(CLUMPS * (rk / rm) ** 2))
    ids = np.array([m.pal.idx(c) for c in LEAVES], np.uint8)
    for d in _even_dirs(m, n):
        rc = float(m.rng.uniform(*CLUMP_R))
        c = np.array(centre) + d * rk * float(m.rng.uniform(0.95, 1.1))
        b = _ball(m, c, rc, 0.3)
        if not b:
            continue
        sl, X, Y, Z, mask = b
        t = 0.9 * (Z + 0.5 - c[2]) / rc + 0.6 * d[2] + m.rng.uniform(-0.15, 0.15, X.shape)
        m.v[sl][mask] = ids[np.digitize(t, [-0.5, 0.0, 0.45, 0.85])][mask]


def _nb(a, d):
    """a shifted so that out[x] = a[x + d] (zero outside)."""
    p = np.pad(a, 1)
    W, D, H = a.shape
    return p[1 + d[0]:1 + d[0] + W, 1 + d[1]:1 + d[1] + D, 1 + d[2]:1 + d[2] + H]


def roughen(m: Model, region, p_cut=0.06, p_add=0.05, p_up=0.14):
    """Single loose leaf cubes over the clumps: dents a share of the exposed leaf voxels,
    then grows 1-voxel bumps out of the surface (sideways ones keep the colour; the more
    frequent ones on top are a shade lighter - the bright cube tops of the reference)."""
    sl = m._slices(*region)
    if sl is None:
        return
    sub = m.v[sl]
    leaf_ids = [m.pal.idx(c) for c in LEAVES]
    lighter = np.arange(256, dtype=np.uint8)
    for a, b in zip(leaf_ids, leaf_ids[1:] + leaf_ids[-1:]):
        lighter[a] = b
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    leaf = np.isin(sub, leaf_ids)
    exposed = np.zeros_like(leaf)
    for d in dirs:
        exposed |= _nb(sub, d) == 0
    sub[leaf & exposed & (m.rng.random(sub.shape) < p_cut)] = 0
    for d in dirs[:5]:
        back = (-d[0], -d[1], -d[2])
        src = _nb(sub, back)
        grow = (sub == 0) & np.isin(src, leaf_ids) & (m.rng.random(sub.shape) < (p_up if d[2] == 1 else p_add))
        sub[grow] = (lighter[src] if d[2] == 1 else src)[grow]


# ---------------------------------------------------------------- pieces

def pit(m: Model, xc, yc):
    """Stone tree pit centred on voxel (xc, yc) with an iron grate flush with its top."""
    x0, y0 = xc - BASE // 2, yc - BASE // 2
    n = BASE - 2 * RING
    m.box(x0, y0, 0, BASE, BASE, STONE_H, "stone0")
    m.carve(x0 + RING, y0 + RING, 0, n, n, STONE_H)
    ids = np.array([m.pal.idx(c) for c in STONES], np.uint8)
    seam, dark = m.pal.idx("stone3"), m.pal.idx("stone_dk")

    def stones(X, Y, Z):
        bx, by = (X - x0) // BLOCK, (Y - y0) // BLOCK
        c = ids[(_hash(bx, by) % np.uint64(3)).astype(int)]
        edge = ((X - x0) % BLOCK == BLOCK - 1) | ((Y - y0) % BLOCK == BLOCK - 1) | (Z == STONE_H - 1) & (
            ((X - x0) % BLOCK == 0) | ((Y - y0) % BLOCK == 0))
        c = np.where(edge, seam, c)
        return np.where(_hash(X, Y, Z) % np.uint64(100) < 6, dark, c)
    m.paint_fn(x0, y0, 0, BASE, BASE, STONE_H, stones)

    gz = STONE_H - 1
    m.box(x0 + RING, y0 + RING, 0, n, n, 2, "soil")
    m.box(x0 + RING - 1, y0 + RING - 1, gz, n + 2, n + 2, 1, "iron")           # frame
    gx, gy = x0 + RING, y0 + RING
    m.carve(gx, gy, gz, n, n, 1)
    m.where(gx, gy, gz, n, n, 1, lambda X, Y, Z: ((X - gx) % 2 == 0) | ((Y - gy) % 2 == 0), "iron")
    m.box(gx, gy, gz - 1, n, n, 1, "iron_dk", only_empty=True)                 # shadowed bars below
    m.where(gx, gy, gz - 1, n, n, 1, lambda X, Y, Z: ((X - gx) % 2 == 1) & ((Y - gy) % 2 == 1), None)
    for cx, cy in ((x0 + RING - 1, y0 + RING - 1), (x0 + BASE - RING - 2, y0 + RING - 1),
                   (x0 + RING - 1, y0 + BASE - RING - 2), (x0 + BASE - RING - 2, y0 + BASE - RING - 2)):
        m.box(cx, cy, gz, 3, 3, 1, "iron_lt")                                 # corner plates
        m.set(cx + 1, cy + 1, gz + 1, "bolt")


def tree(m: Model, t: dict, xc, yc):
    centre = (xc + 0.5, yc + 0.5)
    pit(m, xc, yc)

    # trunk polyline + root flare over the grate
    nodes = []
    for px, py, r in t["trunk"]:
        u, v = ref_to_screen(t, px, py)
        nodes.append((screen_to_world(centre, u, v), r))
    for (a, ra), (b, rb) in zip(nodes, nodes[1:]):
        tube(m, a, b, ra, rb)
    base = nodes[0][0]
    ang0 = float(m.rng.uniform(0, 90))
    for k in range(5):
        a = math.radians(ang0 + 72 * k)
        tube(m, (base[0], base[1], 7), (base[0] + 5.5 * math.cos(a), base[1] + 5.5 * math.sin(a), STONE_H + 0.5),
             2.3, 1.2)

    def trunk_at(z):
        for (a, _), (b, _) in zip(nodes, nodes[1:]):
            if a[2] <= z <= b[2]:
                f = (z - a[2]) / max(b[2] - a[2], 1e-6)
                return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
        return nodes[-1][0]

    # lobes in screen units; the crown's u extent sets how deep the copies may go
    lobes = [(*ref_to_screen(t, px, py), pr / PX - 0.5) for px, py, pr in t["lobes"]]
    umin = min(u - r for u, _, r in lobes)
    umax = max(u + r for u, _, r in lobes)
    uc, rc = (umin + umax) / 2, (umax - umin) / 2
    z_fork = nodes[2][0][2]
    z_top = nodes[-1][0][2]

    for u, v, r in lobes:
        main = screen_to_world(centre, u, v)
        zs = min(max(main[2] - 8, z_fork), z_top)
        tube(m, trunk_at(zs), main, 1.7, 1.0)                                  # branch into the lobe
    spheres = []
    for u, v, r in lobes:
        depth = min(0.5 * math.sqrt(max(rc ** 2 - (u - uc) ** 2, 0.0)), MAX_DEPTH)
        offsets = [0.0] if depth < 3 else [-depth, 0.0, depth]
        spheres += [(screen_to_world(centre, u, v, s), r) for s in offsets]
    for p, r in spheres:          # all cores first, so no core fills a crevice between clumps
        leaf_core(m, p, r)
    for p, r in spheres:
        leaf_clumps(m, p, r)
    roughen(m, (xc - 45, yc - 45, 6, 90, 90, GRID[2]))


def build() -> Model:
    m = Model(*GRID, seed=7)
    palette(m)
    c = math.sqrt(0.5)
    for i, t in enumerate(TREES):
        U = (t["cx"] - TREES[0]["cx"]) / PX
        xc, yc = FIRST_X + round(U * c), FIRST_Y - round(U * c)
        with m.part(f"tree{i + 1}_{t['name']}"):
            tree(m, t, xc, yc)
    return m
