"""Flowering bush kit — reference/a59210a5-cb2b-4ef2-97fd-f4ff3a09d0c0.png

A kit sheet of three round bushes (small, medium, large) seen from the front-right
(az 315, el 30, orthographic). Each bush is its own part (object) in the .vox. They stand
on one ground line running along the camera's right vector, so on the sheet they sit side
by side at the same depth.

Each bush is a dome made of lobes (ellipsoids: centre on the ground line + height zc,
radii R, R, Rz, all in design units):
  core     dark shadow fill at CORE x the lobe radii (the dark gaps between leaves)
  leaves   cubes of about LEAF scattered on the lobe surfaces (centres between SHELL
           fractions of the radius), drawn inner first so the outermost cubes stay whole.
           Colour runs teal (deep, low) -> green -> olive -> yellow (out, high); the top
           voxel layer of each cube is a lighter tone (the lit top face of the sheet)
  flowers  cream 4-petal flowers with a golden centre where the sheet shows them: the
           sheet position is mapped onto the bush's projected bbox and a ray from the
           camera finds the leaf surface there
"""
import math

import numpy as np

from voxtool import Model

NAME = "a59210a5_cb2b_4ef2_97fd_f4ff3a09d0c0"
REFERENCE = "reference/a59210a5-cb2b-4ef2-97fd-f4ff3a09d0c0.png"
VIEW = {"azimuth": 315, "elevation": 30, "fov": 0}
CUTOUT = {"keep": "all"}

RES = 1
GRID = (166, 166, 64)

PX = 9.09                  # sheet pixels per design unit (small bush: 400 px ~ 44 units)
ORIGIN = (8.0, 8.0)        # ground point that sheet x = 0 maps to
LEAF_SIZES = (3, 4, 4, 4, 5)
LEAF = 4                   # typical leaf cube edge
CORE = 0.70                # shadow core / lobe radius
SHELL = (0.66, 1.0)        # leaf cube centres between these fractions of the lobe radius
COVER = 2.0                # leaf cubes per leaf-sized patch of lobe surface
OUTER, OUTER_KEEP = 0.89, 0.45   # beyond OUTER only this share of cubes stays: spiky rim
PETAL = 2.5                # flower petal cube edge (~0.6 leaf on the sheet)
POLLEN = 2                 # flower centre cube edge
FLOWER_R = 2.2             # petal offset from the flower centre

# per bush: sheet x of its centre (px), lobes (dx, dy, zc, R, Rz) relative to that centre
# (dx along the screen-right ground direction, dy away from the camera), its bbox on the
# sheet and its flowers (sheet px). Each bush is a low dome (centre near the ground) with
# humps on top; the bigger bushes sit a little further back (their ground line is higher).
BUSHES = {
    "bush_small": dict(
        sheet_x=215,
        lobes=[(0, 0, 3, 20, 20.3)],
        bbox=(15, 378, 415, 712),
        flowers=[(290, 462), (187, 542), (152, 557)]),
    "bush_medium": dict(
        sheet_x=735,
        lobes=[(0, 4, 4, 28.5, 26.5),
               (-2, 4, 31, 11, 7)],
        bbox=(455, 238, 1017, 733),
        flowers=[(733, 375), (578, 465), (898, 425), (825, 497)]),
    "bush_large": dict(
        sheet_x=1398,
        lobes=[(3.5, 6, 5, 34.3, 33.8),
               (-20, 6, 4, 17.7, 22),
               (-1, 6, 39, 8, 7)],
        bbox=(1037, 148, 1760, 748),
        flowers=[(1390, 238), (1165, 425), (1550, 405), (1083, 478), (1302, 493),
                 (1445, 563), (1672, 538)]),
}

# leaf tones from deep to lit: (side colour, lit top colour)
TONES = [("teal", "teal_t"), ("teal_g", "teal_g_t"), ("green", "green_t"),
         ("olive", "olive_t"), ("yellow", "yellow_t")]
TONE_CUTS = [0.46, 0.60, 0.73, 0.85]


def palette(m: Model):
    p = m.pal
    p.add("shade", "#11201c")
    p.add("teal", "#2a4436"); p.add("teal_t", "#2f4c3c")
    p.add("teal_g", "#3f5c3a"); p.add("teal_g_t", "#48663f")
    p.add("green", "#627536"); p.add("green_t", "#6f823a")
    p.add("olive", "#8a8c36"); p.add("olive_t", "#b4a83e")
    p.add("yellow", "#96953f"); p.add("yellow_t", "#d9c254")
    p.add("petal", "#fde9b2"); p.add("pollen", "#f0b030")


# ---------------------------------------------------------------- camera helpers

def camera(view):
    A, E = math.radians(view["azimuth"]), math.radians(view["elevation"])
    fwd = np.array([math.sin(A) * math.cos(E), math.cos(A) * math.cos(E), -math.sin(E)])
    right = np.array([math.cos(A), -math.sin(A), 0.0])
    up = np.array([math.sin(E) * math.sin(A), math.sin(E) * math.cos(A), math.cos(E)])
    return fwd, right, up


def ground_centre(sheet_x, dx=0.0, dy=0.0):
    """Ground point of a bush: sheet x along the screen-right direction, dy straight back."""
    fwd, right, _ = camera(VIEW)
    back = np.array([fwd[0], fwd[1], 0.0])
    back /= np.linalg.norm(back)
    p = np.array([ORIGIN[0], ORIGIN[1], 0.0]) + right * (sheet_x / PX + dx) + back * dy
    return p


def screen_of(points):
    """Orthographic screen coords (x right, y down) in design units, relative to the origin."""
    _, right, up = camera(VIEW)
    return np.stack([points @ right, -(points @ up)], axis=-1)


def surface_hit(m: Model, sx, sy):
    """First filled voxel along the camera ray through screen point (sx, sy)."""
    fwd, right, up = camera(VIEW)
    p0 = right * sx - up * sy
    ts = np.arange(-400, 400, 0.25 / m.res)
    pts = p0[None] + ts[:, None] * fwd[None]
    idx = np.floor(pts * m.res).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(m.v.shape)), axis=1)
    hit = np.zeros(len(ts), bool)
    hit[ok] = m.v[tuple(idx[ok].T)] > 0
    if not hit.any():
        return None
    return pts[int(np.argmax(hit))]


# ---------------------------------------------------------------- bush pieces

def ellipsoid_area(a, b, c):
    p = 1.6075
    return 4 * math.pi * (((a * b) ** p + (a * c) ** p + (b * c) ** p) / 3) ** (1 / p)


def lobe_list(spec):
    out = []
    for dx, dy, zc, R, Rz in spec["lobes"]:
        g = ground_centre(spec["sheet_x"], dx, dy)
        out.append((g[0], g[1], zc, R, Rz))
    return out


def core(m: Model, lobes):
    for cx, cy, zc, R, Rz in lobes:
        m.ellipsoid(cx, cy, zc, R * CORE, R * CORE, Rz * CORE, "shade")


def leaves(m: Model, lobes):
    rng = m.rng
    top = max(zc + Rz for _, _, zc, _, Rz in lobes)
    pts, outs = [], []
    for cx, cy, zc, R, Rz in lobes:
        n = int(COVER * ellipsoid_area(R, R, Rz) / LEAF ** 2)
        d = rng.normal(size=(n, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        u = rng.uniform(*SHELL, n)
        p = np.array([cx, cy, zc]) + d * np.array([R, R, Rz]) * u[:, None]
        keep = (p[:, 2] > 0.5) & ((u < OUTER) | (rng.random(n) < OUTER_KEEP))
        pts.append(p[keep])
        outs.append(u[keep])
    p = np.concatenate(pts)
    u = np.concatenate(outs)
    order = np.argsort(u)                  # inner cubes first, outer ones drawn over them
    o = (u - SHELL[0]) / (SHELL[1] - SHELL[0])
    h = np.clip(p[:, 2] / top, 0, 1)
    s = 0.65 * o + 0.35 * h + rng.normal(0, 0.13, len(u))
    tone = np.searchsorted(TONE_CUTS, s)
    t = 1 / m.res                          # one voxel thick lit top
    for i in order:
        size = int(rng.choice(LEAF_SIZES))
        x0, y0 = round(p[i, 0] - size / 2), round(p[i, 1] - size / 2)
        z0 = max(0, round(p[i, 2] - size / 2))
        side, lit = TONES[tone[i]]
        m.box(x0, y0, z0, size, size, size, side)
        m.box(x0, y0, z0 + size - t, size, size, t, lit)


def flower(m: Model, c):
    """4-petal flower facing the camera, centred on point c: petal cubes above, below,
    left and right of it on screen, a golden centre cube just in front of them."""
    fwd, right, up = camera(VIEW)
    for off in (right, -right, up, -up):
        q = c + off * FLOWER_R - PETAL / 2
        m.box(*q, PETAL, PETAL, PETAL, "petal")
    q = c - fwd * 0.8 - POLLEN / 2
    m.box(*q, POLLEN, POLLEN, POLLEN, "pollen")


def flowers(m: Model, spec, mask):
    """Places the sheet's flowers: sheet px -> this bush's projected bbox -> surface hit."""
    xs, ys, zs = np.nonzero(mask)
    pts = (np.stack([xs, ys, zs], axis=1) + 0.5) / m.res
    scr = screen_of(pts)
    lo, hi = scr.min(axis=0) - 0.7, scr.max(axis=0) + 0.7
    bx0, by0, bx1, by1 = spec["bbox"]
    fwd, _, _ = camera(VIEW)
    for fx, fy in spec["flowers"]:
        sx = lo[0] + (fx - bx0) / (bx1 - bx0) * (hi[0] - lo[0])
        sy = lo[1] + (fy - by0) / (by1 - by0) * (hi[1] - lo[1])
        hit = surface_hit(m, sx, sy)
        if hit is not None:
            flower(m, hit - fwd * 1.5)


def bush(m: Model, name):
    spec = BUSHES[name]
    lobes = lobe_list(spec)
    before = m.v > 0
    core(m, lobes)
    leaves(m, lobes)
    flowers(m, spec, (m.v > 0) & ~before)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=11, res=RES)
    palette(m)
    for name in BUSHES:
        with m.part(name):
            bush(m, name)
    return m
