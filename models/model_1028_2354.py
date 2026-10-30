"""K9 Thunder 155 mm self-propelled howitzer — reference/99826_112131_1035.jpg

Layout (x across, y depth with y=0 front, z up; about 12 voxels per metre):
  the vehicle faces -y; its right side is the x=VX0 face (the long side seen in the photo)
  tracks       TRACK_W wide on both sides, a loop around the raised front sprocket,
               6 road wheels and the rear idler; wheels visible inside the loop
  upper hull   full width over the tracks (sponsons) from TRACK_TOP to HULL_TOP,
               nose vertical up to KNEE_Z then a sloped glacis; lower hull between the tracks
  turret       big box over the rear half, mantlet centred on its front face; turret and
               gun are swung GUN_TRAV degrees toward +x about the ring centre (turret frame)
  gun          52-calibre barrel: cradle sleeve, fume extractor, multi-baffle muzzle brake,
               raised GUN_ELEV degrees
  details      cupola + MG, sight window, bent whip antennas, light guards on the nose corners,
               travel lock (open), deck boxes, engine grille, red marker lights
  paint        4-tone camo (green, brown, tan, black) from a smoothed 3D noise field
"""
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import Delaunay

from voxtool import Model

NAME = "model_1028_2354"
REFERENCE = "reference/99826_112131_1035.jpg"
VIEW = {"azimuth": 34, "elevation": 6, "fov": 45}

# ---- key dimensions
VX0, VW = 6, 44              # vehicle x range [VX0, VX0+VW); x=VX0 is the vehicle's right side
VCX = VX0 + VW / 2
TRACK_W = 8
HULL_L = 86
TRACK_TOP = 14               # top of the track loop = underside of the sponsons
HULL_TOP = 23                # deck height behind the glacis
NOSE_TOP = 21                # top of the vertical nose plate; the deck rises from here ...
GLACIS_RUN = 10              # ... to HULL_TOP over this many voxels
FENDER_OUT = 4               # sponson fronts over the tracks stick out past the nose plate
TURRET_W, TURRET_TOP = 34, 37
TURRET_FRONT, TURRET_BACK = -20, 28   # turret extent along its own axis around the ring centre
RING_BACK = 25               # ring centre this far in front of the hull rear (rear bustle overhangs)
TRUNNION_V, TRUNNION_Z = -16, 32
GUN_TRAV, GUN_ELEV = 2, 10.5  # degrees: turret swung toward +x, barrel raised
BARREL_L = 103               # trunnion -> muzzle (long: the muzzle is nearest the camera)

_T, _E = math.radians(GUN_TRAV), math.radians(GUN_ELEV)
_REACH = -TRUNNION_V + BARREL_L * math.cos(_E)          # horizontal ring centre -> muzzle
NOSE_Y = max(3, math.ceil(_REACH * math.cos(_T) - (HULL_L - RING_BACK)) + 6)
REAR_Y = NOSE_Y + HULL_L
RING_Y = REAR_Y - RING_BACK
GRID = (max(VX0 + VW + 6, math.ceil(VCX + _REACH * math.sin(_T) + 6)),
        REAR_Y + 6,
        max(TURRET_TOP + 14, math.ceil(TRUNNION_Z + BARREL_L * math.sin(_E) + 6)))


def deck_z(y: float) -> int:
    """First empty z above the upper hull at depth y (glacis near the nose)."""
    return int(min(HULL_TOP, NOSE_TOP + max(y - NOSE_Y, 0) * (HULL_TOP - NOSE_TOP) / GLACIS_RUN))

SPROCKET = (NOSE_Y + 4, 7, 4)                 # (y, z, r) in continuous coordinates
IDLER = (REAR_Y - 6, 9, 4)
ROAD_Y = np.linspace(NOSE_Y + 15, REAR_Y - 17, 6)
ROAD_Z, ROAD_R = 6, 4


def palette(m: Model):
    p = m.pal
    p.add("camo", "#808080")                  # placeholder, replaced by the camo tones
    # camo tones sampled from the reference (brighter bases scored worse: the photo's
    # lit side is already close to these values)
    p.add("c_green", "#2f4d41"); p.add("c_brown", "#545536")
    p.add("c_tan", "#b9ad76"); p.add("c_black", "#161a17")
    p.add("hull_dk", "#161a14"); p.add("shadow", "#0b0d0c")
    p.add("track", "#141716"); p.add("track2", "#252a26")
    p.add("rubber", "#101211"); p.add("wheel", "#2d3527"); p.add("hub", "#4f5540")
    p.add("fume", "#2b4258"); p.add("brake", "#213a35"); p.add("brake_dk", "#0d1614")
    p.add("glass", "#cfd0e6"); p.add("lamp", "#f2f0d0"); p.add("red", "#c0261c")
    p.add("iron", "#1a1d1b"); p.add("grille", "#1d221c")


CAMO = ["c_green", "c_brown", "c_tan", "c_black"]
CAMO_P = [0.32, 0.30, 0.27, 0.11]


# ---------------------------------------------------------------- helpers

def circle_hull(circles, n=32):
    """Convex hull (Delaunay) of circles (y, z, r) in the y-z plane."""
    pts = [(cy + r * math.cos(a), cz + r * math.sin(a)) for cy, cz, r in circles
           for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    return Delaunay(np.array(pts))


def in_hull(tri, Y, Z):
    p = np.stack([Y.ravel() + 0.5, Z.ravel() + 0.5], axis=1)
    return (tri.find_simplex(p) >= 0).reshape(Y.shape)


def tube(m: Model, p0, d, t0, t1, r0, r1, c):
    """Round tube along unit vector d from point p0 (continuous coords), from t0 to t1,
    radius r0 -> r1. c=None carves."""
    p0, d = np.asarray(p0, float), np.asarray(d, float)
    a, b = p0 + d * t0, p0 + d * t1
    rm = max(r0, r1) + 1
    lo = np.floor(np.minimum(a, b) - rm).astype(int)
    hi = np.ceil(np.maximum(a, b) + rm).astype(int)

    def fn(X, Y, Z):
        vx, vy, vz = X + 0.5 - p0[0], Y + 0.5 - p0[1], Z + 0.5 - p0[2]
        t = vx * d[0] + vy * d[1] + vz * d[2]
        r = r0 + (r1 - r0) * np.clip((t - t0) / (t1 - t0), 0, 1)
        return (t >= t0) & (t < t1) & (vx * vx + vy * vy + vz * vz - t * t <= r * r + 0.3)
    m.where(*lo, *(hi - lo), fn, c)


def polyline(m: Model, pts, c):
    """Thin line through continuous points."""
    for a, b in zip(pts, pts[1:]):
        m.line([v - 0.5 for v in a], [v - 0.5 for v in b], c)


class Turret:
    """Turret-local coordinates: u across (+u = toward +x), v along (-v = gun side), z up;
    rotated GUN_TRAV degrees about the ring centre (VCX, RING_Y)."""

    def __init__(self, m: Model):
        self.m = m
        self.c, self.s = math.cos(_T), math.sin(_T)

    def world(self, u, v, z=0.0):
        return (VCX + u * self.c - v * self.s, RING_Y + u * self.s + v * self.c, z)

    def local(self, X, Y):
        dx, dy = X + 0.5 - VCX, Y + 0.5 - RING_Y
        return dx * self.c + dy * self.s, -dx * self.s + dy * self.c

    def box(self, u, v, z, w, d, h, c, **kw):
        cs = [self.world(uu, vv) for uu in (u, u + w) for vv in (v, v + d)]
        x0, y0 = math.floor(min(p[0] for p in cs)) - 1, math.floor(min(p[1] for p in cs)) - 1
        x1, y1 = math.ceil(max(p[0] for p in cs)) + 1, math.ceil(max(p[1] for p in cs)) + 1

        def fn(X, Y, Z):
            U, V = self.local(X, Y)
            return (U >= u) & (U < u + w) & (V >= v) & (V < v + d)
        self.m.where(x0, y0, z, x1 - x0, y1 - y0, h, fn, c, **kw)

    def cyl(self, u, v, z, r, h, c, **kw):
        x, y, _ = self.world(u, v)
        self.m.cylinder(x - 0.5, y - 0.5, z, r, h, c, **kw)

    def line(self, pts, c):
        polyline(self.m, [self.world(u, v, z) for u, v, z in pts], c)


# ---------------------------------------------------------------- parts

def track(m: Model, x0: int, outer: int):
    """One track over x0..x0+TRACK_W; outer = -1 if its outside face is x0, +1 if x0+TRACK_W-1."""
    wheels = [SPROCKET, IDLER] + [(y, ROAD_Z, ROAD_R) for y in ROAD_Y]
    inner = circle_hull(wheels)
    outer_h = circle_hull([(cy, cz, r + 2) for cy, cz, r in wheels])
    y0, d, h = NOSE_Y - 1, HULL_L + 2, TRACK_TOP + 1
    m.where(x0, y0, 0, TRACK_W, d, h,
            lambda X, Y, Z: in_hull(outer_h, Y, Z) & ~in_hull(inner, Y, Z), "track")
    m.where(x0, y0, 0, TRACK_W, d, h, lambda X, Y, Z: (Y // 2 + Z // 2) % 2 == 0, "track2",
            only_filled=True)
    # dark space behind the wheels
    back_x = x0 + TRACK_W - 1 if outer < 0 else x0
    m.where(back_x, y0, 0, 1, d, h, lambda X, Y, Z: in_hull(inner, Y, Z), "shadow")
    face_x = x0 + 1 if outer < 0 else x0 + TRACK_W - 2
    for cy, cz, r in wheels:
        road = cz == ROAD_Z
        m.cylinder(cy - 0.5, cz - 0.5, x0 + 1, r, TRACK_W - 2, "rubber" if road else "wheel", axis="x")
        m.cylinder(cy - 0.5, cz - 0.5, face_x, r - 1.2, 1, None, axis="x")           # recessed disc
        m.cylinder(cy - 0.5, cz - 0.5, face_x - outer, r - 1.2, 1, "wheel", axis="x")
        m.cylinder(cy - 0.5, cz - 0.5, face_x, 1.0, 1, "hub", axis="x")
        if not road:                                                                 # sprocket/idler spokes
            m.box(face_x, int(cy) - 3, int(cz) - 1, 1, 6, 1, "hub")
            m.box(face_x, int(cy) - 1, int(cz) - 3, 1, 1, 6, "hub")
    for y in (ROAD_Y[1] + 5, ROAD_Y[3] + 5):                                         # return rollers
        m.cylinder(y - 0.5, 10.5, x0 + 2, 1.2, TRACK_W - 4, "rubber", axis="x")


def hull(m: Model):
    # sponsons + upper hull; vertical nose plate, then the glacis rising to the deck
    slope = (HULL_TOP - NOSE_TOP) / GLACIS_RUN
    m.where(VX0, NOSE_Y, TRACK_TOP, VW, HULL_L, HULL_TOP - TRACK_TOP,
            lambda X, Y, Z: Z + 0.5 <= NOSE_TOP + (Y + 0.5 - NOSE_Y) * slope, "camo")
    # lower hull between the tracks, front plate sloping back to the belly
    m.where(VX0 + TRACK_W, NOSE_Y, 3, VW - 2 * TRACK_W, HULL_L - 1, TRACK_TOP - 3,
            lambda X, Y, Z: (Y + 0.5 - NOSE_Y) >= (TRACK_TOP - Z - 0.5) * 0.9, "hull_dk")
    # fender lips along both sides and mudguards over the track fronts
    m.box(VX0 - 1, NOSE_Y + 1, TRACK_TOP, 1, HULL_L - 2, 1, "camo")
    m.box(VX0 + VW, NOSE_Y + 1, TRACK_TOP, 1, HULL_L - 2, 1, "camo")
    # fender noses: the sponsons over the tracks stick out past the nose plate,
    # with a mud flap under them
    for tx in (VX0, VX0 + VW - TRACK_W):
        m.box(tx, NOSE_Y - FENDER_OUT, TRACK_TOP - 1, TRACK_W + 1, FENDER_OUT, NOSE_TOP - TRACK_TOP, "camo")
        m.box(tx, NOSE_Y - FENDER_OUT, TRACK_TOP - 4, TRACK_W, 1, 3, "c_black")
    # corner mud guards flaring out from the fender noses
    for gx in (VX0 - 2, VX0 + VW):
        m.box(gx, NOSE_Y - FENDER_OUT, TRACK_TOP - 1, 2, FENDER_OUT + 4, NOSE_TOP - TRACK_TOP + 1, "camo")
    # tow hooks and red marker lights on the nose
    for hx in (VX0 + 11, VX0 + VW - 13):
        m.box(hx, NOSE_Y - 1, TRACK_TOP, 2, 1, 2, "iron")
    for rx in (VX0 + 3, VX0 + VW - 5):
        m.box(rx, NOSE_Y - 1, NOSE_TOP - 2, 2, 1, 1, "red")
    # bolt row along the top of the nose plate
    for bx in range(VX0 + 2, VX0 + VW - 1, 3):
        m.box(bx, NOSE_Y - 1, NOSE_TOP - 1, 1, 1, 1, "iron")


def light_guard(m: Model, x0: int, y0: int):
    """Headlight with a wire brush guard on the nose corners of the deck."""
    z0, w, d, h = deck_z(y0), 8, 5, 5
    m.box(x0 + 1, y0 + 1, z0, w - 2, d - 2, 2, "lamp")
    for dx in (0, w - 1):
        for dy in (0, d - 1):
            m.box(x0 + dx, y0 + dy, z0, 1, 1, h, "iron")
    m.box(x0, y0, z0 + h - 1, w, 1, 1, "iron")
    m.box(x0, y0 + d - 1, z0 + h - 1, w, 1, 1, "iron")
    m.box(x0, y0, z0 + h - 1, 1, d, 1, "iron")
    m.box(x0 + w - 1, y0, z0 + h - 1, 1, d, 1, "iron")
    for dx in (2, 5):
        m.box(x0 + dx, y0, z0 + 1, 1, 1, h - 2, "iron")
    m.box(x0, y0, z0 + 2, w, 1, 1, "iron")


def deck(m: Model):
    gy = NOSE_Y + 1
    light_guard(m, VX0 + 1, gy)
    light_guard(m, VX0 + VW - 9, gy)
    # travel lock (open, standing up to just under the barrel), hydraulic strut behind it
    tl_y = NOSE_Y + 5
    tz = deck_z(tl_y)
    cx = int(VCX) + 2
    for px in (cx - 4, cx + 3):
        m.box(px, tl_y, tz, 1, 2, 12, "camo")
    m.box(cx - 4, tl_y, tz + 11, 8, 2, 1, "camo")
    m.box(cx - 5, tl_y, tz + 12, 1, 2, 2, "camo")
    m.box(cx + 4, tl_y, tz + 12, 1, 2, 2, "camo")
    m.line((cx, tl_y + 8, deck_z(tl_y + 8)), (cx, tl_y + 2, tz + 8), "iron")
    # engine grille (far side, behind the glacis), driver's hatch, boxes
    for y in range(NOSE_Y + GLACIS_RUN + 1, NOSE_Y + GLACIS_RUN + 12, 2):
        m.box(VX0 + 22, y, HULL_TOP - 1, 14, 1, 1, "grille")
    m.cylinder(VX0 + 30, NOSE_Y + 9, deck_z(NOSE_Y + 9), 2.5, 1, "camo")
    m.box(VX0 + 2, NOSE_Y + 12, deck_z(NOSE_Y + 12) - 1, 8, 12, 3, "camo")
    # tall dark stowage box in front of the far turret cheek
    fy = int(RING_Y + TURRET_FRONT * math.cos(_T)) - 6
    m.box(VX0 + 27, fy, HULL_TOP, 14, 7, 9, "c_black")
    m.box(VX0 + 27, fy, HULL_TOP + 8, 14, 7, 1, "camo")
    # headlight / mirror post on the far front
    m.box(VX0 + 30, gy + 6, deck_z(gy + 6), 1, 1, 5, "iron")
    m.box(VX0 + 29, gy + 6, deck_z(gy + 6) + 5, 3, 1, 2, "iron")


def turret(m: Model, T: Turret):
    hw = TURRET_W / 2
    L = TURRET_BACK - TURRET_FRONT
    T.box(-hw, TURRET_FRONT, HULL_TOP, TURRET_W, L, TURRET_TOP - HULL_TOP, "camo")
    # chamfered top edges
    for u in (-hw, hw - 1):
        T.box(u, TURRET_FRONT, TURRET_TOP - 1, 1, L, 1, None)
    T.box(-hw, TURRET_FRONT, TURRET_TOP - 1, TURRET_W, 1, 1, None)
    # recessed, shadowed gun port around the mantlet
    T.box(-9, TURRET_FRONT, TRUNNION_Z - 7, 18, 1, 12, "hull_dk")
    # mantlet
    T.box(-6, TURRET_FRONT - 3, TRUNNION_Z - 5, 12, 3, 10, "c_green")
    T.box(-6, TURRET_FRONT - 3, TRUNNION_Z + 4, 1, 3, 1, None)
    T.box(5, TURRET_FRONT - 3, TRUNNION_Z + 4, 1, 3, 1, None)
    # sight window, cupola + MG, lifting eyes, rear basket
    T.box(-hw + 2, TURRET_FRONT + 1, TURRET_TOP, 6, 4, 2, "glass")
    T.cyl(0, -17, TURRET_TOP, 3.5, 3, "camo")
    T.box(-2, -20, TURRET_TOP + 3, 5, 6, 4, "camo")
    T.box(-1, -19, TURRET_TOP + 7, 3, 3, 1, "camo")
    T.line([(1, -20, TURRET_TOP + 5), (1, -30, TURRET_TOP + 6)], "iron")
    for u, v in ((6, -19), (-15, 20), (14, 20)):
        T.box(u, v, TURRET_TOP, 1, 1, 2, "iron")
    T.box(-hw + 1, TURRET_BACK, HULL_TOP + 2, TURRET_W - 2, 3, 1, "iron")
    for u in (-hw + 1, 0, hw - 2):
        T.box(u, TURRET_BACK, HULL_TOP + 2, 1, 3, 6, "iron")
    T.box(-hw + 1, TURRET_BACK + 2, HULL_TOP + 7, TURRET_W - 2, 1, 1, "iron")
    # loader's hatch ring with its lid standing open, periscope block behind the cupola
    T.box(-12, 1, TURRET_TOP, 7, 7, 1, "camo")
    T.box(-12, 0, TURRET_TOP + 1, 6, 1, 5, "camo")
    T.box(-11, -1, TURRET_TOP + 5, 4, 1, 2, "c_black")
    T.box(-6, -4, TURRET_TOP, 4, 3, 2, "camo")
    # antennas: whip from the rear-right roof corner bent forward over the roof,
    # a short mast in the middle and a rod by the cupola
    T.line([(-15, 24, TURRET_TOP), (-15, 22, TURRET_TOP + 3), (-15, 18, TURRET_TOP + 5),
            (-15, 12, TURRET_TOP + 6), (-15, 5, TURRET_TOP + 6)], "iron")
    T.line([(-15, 10, TURRET_TOP), (-15, 10, TURRET_TOP + 4)], "glass")
    T.line([(-13, -19, TURRET_TOP), (-11, -15, TURRET_TOP + 4)], "iron")


def gun(m: Model, T: Turret):
    p0 = np.array(T.world(0, TRUNNION_V, TRUNNION_Z))
    d = np.array([math.cos(_E) * math.sin(_T), -math.cos(_E) * math.cos(_T), math.sin(_E)])
    L = BARREL_L
    tube(m, p0, d, 0, 24, 3.0, 2.6, "camo")             # cradle / recoil sleeve
    tube(m, p0, d, 24, L - 11, 1.9, 1.6, "camo")
    tube(m, p0, d, 40, 48, 2.6, 2.6, "fume")            # fume extractor
    tube(m, p0, d, L - 16, L, 2.9, 3.0, "brake")        # muzzle brake
    for k in range(5):                                   # baffle slots
        t = L - 14 + 2.6 * k
        tube(m, p0, d, t, t + 1, 3.0, 3.0, "brake_dk")
    tube(m, p0, d, L - 3, L + 1, 1.2, 1.2, None)         # bore


def camo(m: Model, target: str, tones, p, sigma=(4, 6, 3), seed=3):
    """Replaces `target` voxels by camo tones. The first tones come from one smoothed 3D
    noise field (rank quantised); the last tone (black) from a second, finer field, so the
    black blobs don't sit inside rings of the lightest tone."""
    rng = np.random.default_rng(seed)
    f = ndimage.gaussian_filter(rng.standard_normal(m.size), sigma)
    g = ndimage.gaussian_filter(rng.standard_normal(m.size), [s * 0.7 for s in sigma])
    mask = m.v == m.pal.idx(target)
    vals = f[mask]
    base = np.asarray(p[:-1]) / sum(p[:-1])
    band = np.searchsorted(np.quantile(vals, np.cumsum(base)[:-1]), vals)
    band[g[mask] > np.quantile(g[mask], 1 - p[-1])] = len(tones) - 1
    m.v[mask] = np.array([m.pal.idx(t) for t in tones], np.uint8)[band]


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=5)
    palette(m)
    track(m, VX0, -1)
    track(m, VX0 + VW - TRACK_W, 1)
    hull(m)
    deck(m)
    T = Turret(m)
    turret(m, T)
    gun(m, T)
    camo(m, "camo", CAMO, CAMO_P)
    return m
