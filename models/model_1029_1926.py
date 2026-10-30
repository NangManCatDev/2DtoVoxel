"""Flowering bush kit — reference/3105ce3b-9e9e-4240-b115-0bbd057be957.png

A kit sheet of three chunky voxel bushes (small, medium, large) seen from the front-left at
about az 45 / el 30 (orthographic: every cube shows equal left and right faces). Each bush is
a heap of interpenetrating leaf cubes (edge ~4 units, some 3-6) around a dark core, olive on
top and green to teal-dark lower down, dotted with cream five-cell flowers (plus shapes with
an orange centre) that face the viewer.

Scale: a leaf cube's edge is ~37 reference px -> PX = 9.25 px per design unit, flower cells
are 2 units. Bushes are measured on the sheet (their ground centre in px, silhouette
widths/heights in units) and placed on the ground so the camera sees them side by side: the
sheet's left -> right runs along (+x, -y) in the world, so the large bush is at the front
right and the small one at the back left. Every bush is its own m.part() (movable object).

Bush shape = union of ellipsoid lobes (offsets along the screen-right axis `a`, the depth
axis `b` and up), clipped at z = 0:
  bush_small   dome plus a low lobe bulging to the front left, three flowers and a bud
  bush_medium  round lobe with a bump on the top left, five flowers
  bush_large   left/right lobes, a far-right shoulder, a taller centre and a peak, six flowers
Flowers are placed by casting the reference pixel of each flower centre into the model; the
leaves between each flower cell and the camera are cleared so the plus stays whole.
Score at RES 1: iou 0.868, dE 25.9 (res 2 only gave dE 25.6, so RES stays 1 for editing).
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_1926"
REFERENCE = "reference/3105ce3b-9e9e-4240-b115-0bbd057be957.png"
VIEW = {"azimuth": 45, "elevation": 30, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 1

PX = 9.25                    # reference px per design unit
MARGIN = 6
SPACING = 4.0                # leaf cube lattice step (jittered)
CUBE_SIZES = (4, 5, 6)
CUBE_P = (0.6, 0.3, 0.1)
SHELL = 0.6                  # cubes are centred between this and the lobe surface (f = 1)
CORE = 0.86                  # solid dark core inside f <= CORE
PETAL = 2                    # flower cell edge
TOP_TINT = True              # lighter olive skin on the exposed top of each leaf cube

# ground centre on the sheet (px), lobes (da, db, cz, Ra, Rb, Rz) in units, flower centres (px)
BUSHES = {
    "bush_small": {
        "at": (228, 574),
        "lobes": [(1, -2, 6, 17, 17, 18), (-8, -5, 4, 13, 12, 10)],
        "flowers": [(243, 430), (138, 548), (335, 528)],
        "buds": [(180, 455)],
    },
    "bush_medium": {
        "at": (722, 572),
        "lobes": [(0, -2, 14, 24, 22, 27), (-8, 0, 26, 11, 11, 11)],
        "flowers": [(636, 322), (782, 297), (855, 393), (552, 480), (727, 450)],
        "buds": [],
    },
    "bush_large": {
        "at": (1454, 586),
        "lobes": [(-27, -2, 6, 18, 17, 22), (21, 0, 9, 20, 19, 28), (35, 0, 10, 12, 14, 21),
                  (-2, 1, 10, 19, 20, 30), (-3, 5, 31, 14, 12, 13)],
        "flowers": [(1388, 275), (1357, 400), (1553, 375), (1730, 433), (1200, 505), (1697, 568)],
        "buds": [],
    },
}

LEAVES = ["g0", "g1", "g2", "g3", "g4"]          # dark teal -> light olive
CAPS = ["c0", "c1", "c2", "c3", "c4"]


def palette(m: Model):
    p = m.pal
    p.add("core", "#0f2e26")
    for name, hx in zip(LEAVES, ("#1d4434", "#2b5230", "#3e6236", "#56713b", "#75833f")):
        p.add(name, hx)
    for name, hx in zip(CAPS, ("#7a9350", "#8f9f56", "#a4aa5c", "#b9b562", "#cdbf68")):
        p.add(name, hx)
    p.add("petal", "#fde5ba")
    p.add("pistil", "#f6a832")


# ---------------------------------------------------------------- camera geometry

def axes(view=VIEW):
    """Screen right, screen up and viewing direction of the orthographic VIEW camera (as in
    render.Camera), plus the ground axes a (screen right) and b (away from the camera)."""
    A, E = math.radians(view["azimuth"]), math.radians(view["elevation"])
    right = np.array([math.cos(A), -math.sin(A), 0.0])
    up = np.array([math.sin(E) * math.sin(A), math.sin(E) * math.cos(A), math.cos(E)])
    fwd = np.array([math.sin(A) * math.cos(E), math.cos(A) * math.cos(E), -math.sin(E)])
    a = right[:2]
    b = np.array([math.sin(A), math.cos(A)])
    return right, up, fwd, a, b


RIGHT, UP, FWD, A_AX, B_AX = axes()


def ground_offset(du, dv):
    """Ground move (dx, dy) in units that shifts a point by (du, dv) sheet px (v down)."""
    mat = np.array([[RIGHT[0], RIGHT[1]], [-UP[0], -UP[1]]])
    return np.linalg.solve(mat, np.array([du, dv], float) / PX)


def layout():
    """World ground centre of every bush (shifted into the grid), the grid size and the
    world point under the first bush's sheet anchor."""
    names = list(BUSHES)
    u0, v0 = BUSHES[names[0]]["at"]
    cen = {k: ground_offset(b["at"][0] - u0, b["at"][1] - v0) for k, b in BUSHES.items()}
    lo, hi, top = np.full(2, np.inf), np.full(2, -np.inf), 0.0
    for k, b in BUSHES.items():
        for da, db, cz, ra, rb, rz in b["lobes"]:
            c = cen[k] + da * A_AX + db * B_AX
            ext = np.sqrt((ra * A_AX) ** 2 + (rb * B_AX) ** 2)
            lo, hi = np.minimum(lo, c - ext), np.maximum(hi, c + ext)
            top = max(top, cz + rz)
    shift = MARGIN - lo
    cen = {k: c + shift for k, c in cen.items()}
    W, D = (int(math.ceil(s)) for s in hi - lo + 2 * MARGIN)
    return cen, (W, D, int(math.ceil(top + MARGIN))), np.array([*cen[names[0]], 0.0])


def lobe_dist(lobes, g):
    """f(X, Y, Z): smallest normalised ellipsoid distance to the bush's lobes (1 = surface)."""
    def f(X, Y, Z):
        d = np.full(np.shape(X), np.inf)
        for da, db, cz, ra, rb, rz in lobes:
            cx, cy = g + da * A_AX + db * B_AX
            a = (X - cx) * A_AX[0] + (Y - cy) * A_AX[1]
            b = (X - cx) * B_AX[0] + (Y - cy) * B_AX[1]
            d = np.minimum(d, np.sqrt((a / ra) ** 2 + (b / rb) ** 2 + ((Z - cz) / rz) ** 2))
        return d
    return f


# ---------------------------------------------------------------- bush pieces

def leaf_cubes(m: Model, lobes, g):
    """Solid dark core, then jittered leaf cubes in the shell, inner ones first so the cubes
    that stick out stay whole. Colour follows height with a lot of randomness."""
    f = lobe_dist(lobes, g)
    hw = 0.5 / m.res
    lo = np.array([math.inf] * 3)
    hi = np.array([-math.inf] * 3)
    for da, db, cz, ra, rb, rz in lobes:
        c = np.array([*(g + da * A_AX + db * B_AX), cz])
        ext = np.array([*np.sqrt((ra * A_AX) ** 2 + (rb * B_AX) ** 2), rz])
        lo, hi = np.minimum(lo, c - ext), np.maximum(hi, c + ext)
    lo[2] = 0
    x0, y0 = int(lo[0]) - 2, int(lo[1]) - 2
    w, d, h = int(hi[0] - lo[0]) + 5, int(hi[1] - lo[1]) + 5, int(hi[2]) + 3
    m.where(x0, y0, 0, w, d, h, lambda X, Y, Z: f(X + hw, Y + hw, Z + hw) <= CORE, "core")

    gx = np.arange(lo[0], hi[0] + SPACING, SPACING)
    gy = np.arange(lo[1], hi[1] + SPACING, SPACING)
    gz = np.arange(0.5, hi[2] + SPACING, SPACING)
    P = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
    P = P + m.rng.uniform(-0.4, 0.4, P.shape) * SPACING
    fd = f(P[:, 0], P[:, 1], P[:, 2])
    keep = (fd >= SHELL) & (fd <= 1.0 + m.rng.uniform(-0.15, 0.05, len(P))) & (P[:, 2] >= 1.0)
    P, fd = P[keep], fd[keep]
    order = np.argsort(fd)
    top = max(hi[2], 1.0)
    for p in P[order]:
        s = int(m.rng.choice(CUBE_SIZES, p=CUBE_P))
        k = int(np.clip(np.floor(p[2] / top * 4.0 + m.rng.normal(-0.5, 1.1)), 0, 4))
        m.box(int(round(p[0] - s / 2)), int(round(p[1] - s / 2)), int(round(p[2] - s / 2)), s, s, s, LEAVES[k])


def first_hit(m: Model, p0):
    """First filled voxel along the camera ray through p0 (design units), or None."""
    ts = np.arange(-400.0, 400.0, 0.25 / m.res)
    pts = p0[None, :] + ts[:, None] * FWD[None, :]
    idx = np.floor(pts * m.res).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(m.v.shape)), axis=1)
    if not ok.any():
        return None
    hit = m.v[tuple(idx[ok].T)] > 0
    if not hit.any():
        return None
    return pts[ok][int(np.argmax(hit))]


def sheet_ray(px, anchor_px, anchor_world):
    """World point on the camera ray through a sheet pixel."""
    du, dv = (px[0] - anchor_px[0]) / PX, (px[1] - anchor_px[1]) / PX
    return anchor_world + du * RIGHT - dv * UP


def cell(m: Model, c, color):
    m.box(int(round(c[0] - PETAL / 2)), int(round(c[1] - PETAL / 2)), int(round(c[2] - PETAL / 2)),
          PETAL, PETAL, PETAL, color)


def flower(m: Model, c, bud=False):
    """Plus of PETAL cubes in the plane facing the camera (arms along screen right and up),
    orange centre. A bud is a single cream cell."""
    side = np.array([np.sign(A_AX[0]), np.sign(A_AX[1]), 0.0]) * PETAL
    offs = [np.zeros(3)] if bud else [np.zeros(3), side, -side, np.array([0, 0, PETAL]), np.array([0, 0, -PETAL])]
    for off in offs:                       # clear leaves between the cell and the camera
        for t in (PETAL, 2 * PETAL):
            cell(m, c + off - FWD * t, None)
    for off in offs[1:]:
        cell(m, c + off, "petal")
    cell(m, c, "petal" if bud else "pistil")


def flowers(m: Model, b, anchor_px, anchor_world):
    for pts, bud in ((b["flowers"], False), (b["buds"], True)):
        for px in pts:
            hit = first_hit(m, sheet_ray(px, anchor_px, anchor_world))
            if hit is not None:
                flower(m, hit - FWD * (0.8 if bud else 1.6), bud)


def tint_tops(m: Model):
    """Voxel level: leaf voxels whose top face is open get the lighter cap colour."""
    v = m.v
    open_top = np.ones(v.shape, bool)
    open_top[:, :, :-1] = v[:, :, 1:] == 0
    for leaf, cap in zip(LEAVES, CAPS):
        v[(v == m.pal.idx(leaf)) & open_top] = m.pal.idx(cap)


# ---------------------------------------------------------------- build

def build() -> Model:
    cen, grid, anchor_world = layout()
    m = Model(*grid, seed=11, res=RES)
    palette(m)
    anchor_px = BUSHES[next(iter(BUSHES))]["at"]
    for name, b in BUSHES.items():
        with m.part(name):
            leaf_cubes(m, b["lobes"], cen[name])
            flowers(m, b, anchor_px, anchor_world)
    if TOP_TINT:
        tint_tops(m)
    return m
