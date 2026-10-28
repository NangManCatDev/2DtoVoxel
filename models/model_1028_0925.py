"""Stone bell tower with a lean-to annex — reference/3495e1a7-1df2-4063-84f5-e1adf489b6b2.png

Layout (x right, y depth with y=0 front, z up):
  tower        x TX0..TX1, y Y0..Y1 (30x30), stone body up to CORNICE, protruding cornice
               band, open bell storey (round arch on every face, bronze bell inside) up to
               BELL_TOP, stepped teal pyramid roof with a 3-voxel overhang
  annex        x AX0..AX1 (30 wide), same depth, flush with the tower front, walls to ANNEX_H
  annex roof   teal lean-to falling to +x in 3-voxel courses. As in the reference, its upper
               courses only exist behind the line of sight past the tower's back-right corner
               (in front of that the annex has a flat terrace behind a low parapet), so the
               tower's right face and its window stay visible from the reference camera
  front        brown door with stone jambs under a small teal awning on wooden brackets,
               tall narrow tower window, 2x2 annex window; quoins on every corner
  right side   narrow tower window above the annex, annex window
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1028_0925"
REFERENCE = "reference/3495e1a7-1df2-4063-84f5-e1adf489b6b2.png"
VIEW = {"azimuth": -33, "elevation": 17}

OX, OY = 4, 8            # margin for quoins, roof overhang and the awning
TW, TD, AW = 30, 30, 30  # tower width/depth, annex width
TX0, TX1 = OX, OX + TW
AX0, AX1 = TX1, TX1 + AW
Y0, Y1 = OY, OY + TD
WALL_T = 3
CORNICE = 59             # bottom of the band between the body and the bell storey
BELL_Z = 63              # bell storey floor
BELL_TOP = 85            # first z of the pyramid roof
BELL_IN = 1              # bell storey inset from the tower body on every side
ROOF_OVER = 3            # pyramid roof overhang past the bell storey
ROOF_STEPS = (2, 3, 2, 3, 2, 3)   # inset per roof course; every course rises 3 (top is 4x4)
ANNEX_H = 38             # annex wall top
SHED_OVER = 2            # lean-to overhang past the annex walls
COURSE_W, COURSE_RISE = 3, 2
DOOR_U, DOOR_Z, DOOR_W, DOOR_H = 13, 2, 9, 21
WIN_Z = 41               # tower window bottom
AWIN_Z = 14              # annex window bottom


def palette(m: Model):
    # base colours ~ reference front-face samples / 0.9
    p = m.pal
    p.add("wall", "#ffe5bf"); p.add("wall2", "#f6dab3"); p.add("wall3", "#ffeccb")
    p.add("mortar", "#ebcfa9"); p.add("base", "#dcc4a3")
    p.add("quoin", "#f0d7b4"); p.add("quoin2", "#e3c9a5")
    p.add("trim", "#f6e0bf"); p.add("arch", "#f7e3c5")
    p.add("shadow", "#24190f"); p.add("shadow2", "#35271a")
    p.add("roof", "#0f6c78"); p.add("roof_hi", "#178290"); p.add("roof_dk", "#0a5864")
    p.add("door", "#5e3820"); p.add("door_dk", "#44281a"); p.add("door_frame", "#3a2214")
    p.add("wood", "#5c321b"); p.add("wood_dk", "#3e2112")
    p.add("win_frame", "#3d2617"); p.add("glass", "#545b67"); p.add("glass_hi", "#727b8b")
    p.add("iron", "#1c1a18")
    p.add("bell", "#8c6c44"); p.add("bell_dk", "#634a2e")


WALLS = ["wall", "wall2", "wall3"]
ROOFS = ["roof", "roof_hi", "roof_dk"]


# ---------------------------------------------------------------- face helper

class Face:
    """One outer wall face of a box body. u runs left->right as seen from outside,
    d0 = depth into the wall (0 = outer layer, -1 = one voxel in front of it)."""

    def __init__(self, x0, y0, x1, y1, side):
        self.x0, self.y0, self.x1, self.y1, self.side = x0, y0, x1, y1, side

    def box(self, m: Model, u, z, w, h, d0, dd, c, **kw):
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        if self.side == "front":
            m.box(x0 + u, y0 + d0, z, w, dd, h, c, **kw)
        elif self.side == "back":
            m.box(x1 - u - w, y1 - d0 - dd, z, w, dd, h, c, **kw)
        elif self.side == "left":
            m.box(x0 + d0, y1 - u - w, z, dd, w, h, c, **kw)
        else:  # right
            m.box(x1 - d0 - dd, y0 + u, z, dd, w, h, c, **kw)

    def xyz(self, u, z, d):
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        return {"front": (x0 + u, y0 + d, z), "back": (x1 - 1 - u, y1 - 1 - d, z),
                "left": (x0 + d, y1 - 1 - u, z), "right": (x1 - 1 - d, y0 + u, z)}[self.side]


def tower_face(side):
    return Face(TX0, Y0, TX1, Y1, side)


def belfry_face(side):
    return Face(TX0 + BELL_IN, Y0 + BELL_IN, TX1 - BELL_IN, Y1 - BELL_IN, side)


def annex_face(side):
    return Face(AX0, Y0, AX1, Y1, side)


# ---------------------------------------------------------------- details

def retile(m: Model, target, colors, p, size=(2, 2, 2), region=None, salt=0):
    """Recolours voxels of `target` per size-block (roof tiles) with a hashed pick."""
    sl = m._slices(*region) if region else tuple(slice(0, s) for s in m.v.shape)
    if sl is None:
        return
    tgt = [target] if isinstance(target, str) else list(target)
    sub = m.v[sl]
    mask = np.isin(sub, [m.pal.idx(t) for t in tgt])
    X, Y, Z = m._coords(sl)
    a, b, c = (X // size[0]).astype(np.uint64), (Y // size[1]).astype(np.uint64), (Z // size[2]).astype(np.uint64)
    h = (a * np.uint64(73856093)) ^ (b * np.uint64(19349663)) ^ (c * np.uint64(83492791)) ^ np.uint64(salt + 1)
    h = ((h * np.uint64(2654435761)) % np.uint64(2 ** 32)).astype(np.float64) / 2 ** 32
    cum = np.cumsum(p) / np.sum(p)
    pick = np.searchsorted(cum, h, side="right").clip(0, len(colors) - 1)
    idx = np.array([m.pal.idx(col) for col in colors], np.uint8)[pick]
    sub[mask] = idx[mask]


def quoins(m: Model, cx, cy, sx, sy, z0, z1, period=4):
    """Protruding corner stones at wall corner voxel (cx, cy); sx/sy = outward direction."""
    for i, z in enumerate(range(z0, z1 - 1, period)):
        h = min(period - 1, z1 - z)
        lf, ls = (5, 3) if i % 2 == 0 else (3, 5)
        col = "quoin" if i % 2 == 0 else "quoin2"
        x_lo = cx - lf + 1 if sx > 0 else cx - 1
        m.box(x_lo, cy + sy, z, lf + 1, 1, h, col)          # on the y-facing wall
        y_lo = cy - ls + 1 if sy > 0 else cy - 1
        m.box(cx + sx, y_lo, z, 1, ls + 1, h, col)          # on the x-facing wall


def relief_stones(m: Model, f: Face, n, u0, u1, z0, z1):
    """Scatters n blocks (3-5 x 2) protruding 1 from plain wall, clear of openings,
    trim and other stones (a 1-voxel margin of plain wall all around)."""
    plain = {m.pal.idx(c) for c in WALLS + ["mortar"]}
    placed = 0
    for _ in range(n * 40):
        if placed >= n:
            break
        w = int(m.rng.integers(3, 6))
        u = int(m.rng.integers(u0, max(u0 + 1, u1 - w)))
        z = 3 * int(m.rng.integers(z0 // 3, max(z0 // 3 + 1, (z1 - 2) // 3)))
        ok = all(m.get(*f.xyz(uu, zz, 0)) in plain and m.get(*f.xyz(uu, zz, -1)) == 0
                 for uu in range(u - 1, u + w + 1) for zz in range(z - 1, z + 3))
        if ok:
            f.box(m, u, z, w, 2, -1, 1, "wall3" if placed % 2 else "wall")
            placed += 1


def window(m: Model, f: Face, u, z, w, h, *, cross=False, frame=True):
    """Dark frame, glass recessed 2, protruding stone surround (jambs, lintel, sill)."""
    if frame:
        f.box(m, u - 2, z, 2, h, -1, 1, "trim")                 # jambs
        f.box(m, u + w, z, 2, h, -1, 1, "trim")
        f.box(m, u - 3, z + h, w + 6, 2, -1, 1, "trim")          # lintel
        f.box(m, u - 3, z - 2, w + 6, 2, -1, 1, "trim")          # sill
        f.box(m, u - 3, z - 1, w + 6, 1, -2, 1, "trim")
    f.box(m, u, z, w, h, -1, 4, None)                            # opening
    f.box(m, u, z, w, h, 1, 1, "win_frame")
    f.box(m, u + 1, z + 1, w - 2, h - 2, 1, 1, None)
    f.box(m, u + 1, z + 1, w - 2, h - 2, 2, 1, "glass")
    f.box(m, u + 1, z + h - 4, w - 2, 3, 2, 1, "glass_hi")       # sky reflection on top panes
    f.box(m, u, z + h // 2, w, 1, 1, 1, "win_frame")             # transom
    if cross:
        f.box(m, u + w // 2, z, 1, h, 1, 1, "win_frame")         # mullion


def arch_opening(m: Model, f: Face, u, z, w, spring, wall_t=WALL_T, blind=False):
    """Round-topped opening through the wall with a protruding voussoir ring.
    blind=True only recesses it 2 deep with a dark back (no see-through)."""
    r = w / 2.0
    for du in range(w):
        dx = du + 0.5 - r
        top = spring + int(round(math.sqrt(max(r * r - dx * dx, 0.0))))
        if blind:
            f.box(m, u + du, z, 1, top - z, 0, 2, None)
            f.box(m, u + du, z, 1, top - z, 2, 1, "shadow")
        else:
            f.box(m, u + du, z, 1, top - z, 0, wall_t, None)
        f.box(m, u + du, top, 1, 2, -1, 1, "arch")               # ring
    for du in (-1, w):                                            # ring ends / jamb stones
        f.box(m, u + du, z, 1, spring - z + 2, -1, 1, "arch")
    f.box(m, u - 2, z - 1, w + 4, 1, -1, 1, "trim")               # ledge under the arch


def bell(m: Model, cx, cy, zb, H=10):
    """Bronze bell (wide lip at the bottom) hanging from a wooden yoke."""
    for k in range(H):
        t = k / (H - 1)                    # 0 = lip, 1 = crown
        r = 4.3 - 2.4 * t ** 0.8
        col = "bell_dk" if k in (1, 5) else "bell"
        m.cylinder(cx, cy, zb + k, r, 1, col)
    m.box(int(cx) - 1, int(cy) - 1, zb + H, 2, 2, 1, "bell_dk")   # crown loop
    m.box(int(cx), int(cy), zb - 1, 1, 1, 2, "iron")               # clapper


def pyramid_roof(m: Model):
    over = ROOF_OVER - BELL_IN
    x0, y0 = TX0 - over, Y0 - over
    w, d = TW + 2 * over, TD + 2 * over
    z, ins = BELL_TOP, 0
    m.box(x0, y0, z, w, d, 3, "roof")                               # eave course
    for step in ROOF_STEPS:
        z, ins = z + 3, ins + step
        m.box(x0 + ins, y0 + ins, z, w - 2 * ins, d - 2 * ins, 3, "roof")
    retile(m, "roof", ROOFS, [0.5, 0.25, 0.25], size=(3, 3, 3), region=(x0, y0, BELL_TOP, w, d, 30), salt=3)


def cut_y(x):
    """Front edge (y) of the lean-to roof at column x: the line of sight from the
    reference camera past the tower's back-right corner."""
    k = 1.0 / math.tan(math.radians(abs(VIEW["azimuth"])))
    return Y1 - k * (x - TX1)


def lean_to(m: Model):
    """Annex roof in 3-wide courses falling to +x, infill under it, terrace parapet."""
    x_end = AX1 + SHED_OVER
    k = 0
    while True:
        cx1 = x_end - COURSE_W * k
        cx0 = max(cx1 - COURSE_W, AX0)
        if cx1 <= AX0:
            break
        ztop = ANNEX_H + 3 + COURSE_RISE * k
        ys = max(int(math.ceil(cut_y(cx0))) - 1, Y0 - SHED_OVER)
        ye = Y1 + SHED_OVER
        if ys < ye:
            # gable infill under this course (inside the annex footprint only)
            iy0 = max(ys + 1, Y0)
            m.box(cx0, iy0, ANNEX_H, min(cx1, AX1) - cx0, Y1 - iy0, ztop - 3 - ANNEX_H, "wall")
            m.box(cx0, ys, ztop - 3, cx1 - cx0, ye - ys, 3, "roof")
        k += 1
    retile(m, "roof", ROOFS, [0.5, 0.25, 0.25], size=(COURSE_W, 3, 2),
           region=(AX0, 0, ANNEX_H - 2, AW + SHED_OVER + 2, Y1 + SHED_OVER + 2, 30), salt=11)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(AX1 + SHED_OVER + 3, Y1 + 5, BELL_TOP + 26, seed=5)
    palette(m)
    bx0, by0, bw_, bd_ = TX0 + BELL_IN, Y0 + BELL_IN, TW - 2 * BELL_IN, TD - 2 * BELL_IN

    # --- bodies (hollow, so openings have depth)
    m.shell(TX0, Y0, 0, TW, TD, CORNICE, "wall", t=WALL_T, top=False, bottom=False)
    m.box(TX0, Y0, CORNICE, TW, TD, BELL_Z - CORNICE, "wall")              # bell storey floor
    m.shell(bx0, by0, BELL_Z, bw_, bd_, BELL_TOP - BELL_Z, "wall", t=WALL_T, top=False, bottom=False)
    m.shell(AX0, Y0, 0, AW, TD, ANNEX_H, "wall", t=WALL_T, top=True, bottom=False)
    m.bricks(WALLS, target="wall", bw=6, bh=3, p=[0.5, 0.3, 0.2], mortar="mortar")
    m.box(TX0, Y0, 0, AX1 - TX0, TD, 2, "base", only_filled=True)        # base course

    # --- cornice band, protruding 2
    m.box(TX0 - 1, Y0 - 1, CORNICE, TW + 2, TD + 2, BELL_Z - CORNICE, "quoin")
    m.box(TX0 - 2, Y0 - 2, CORNICE + 1, TW + 4, TD + 4, BELL_Z - CORNICE - 1, "quoin")
    m.bricks(["quoin", "wall", "quoin2"], target="quoin", bw=5, bh=2, p=[0.5, 0.3, 0.2],
             region=(TX0 - 2, Y0 - 2, CORNICE, TW + 4, TD + 4, BELL_Z - CORNICE), salt=4)

    # --- quoins
    quoins(m, TX0, Y0, -1, -1, 2, CORNICE)
    quoins(m, TX0, Y1 - 1, -1, 1, 2, CORNICE)
    quoins(m, TX1 - 1, Y0, 1, -1, ANNEX_H + 1, CORNICE)
    quoins(m, TX1 - 1, Y1 - 1, 1, 1, ANNEX_H + 1, CORNICE)
    bx1, by1 = bx0 + bw_ - 1, by0 + bd_ - 1
    for cx, cy, sx, sy in ((bx0, by0, -1, -1), (bx0, by1, -1, 1), (bx1, by0, 1, -1), (bx1, by1, 1, 1)):
        quoins(m, cx, cy, sx, sy, BELL_Z, BELL_TOP)
    quoins(m, AX1 - 1, Y0, 1, -1, 2, ANNEX_H)
    quoins(m, AX1 - 1, Y1 - 1, 1, 1, 2, ANNEX_H)

    # --- bell storey: arches on all four faces, dark interior, bell
    aw, a_z, a_spring = 12, BELL_Z + 3, BELL_Z + 12
    for side in ("front", "right", "back", "left"):
        # back/left arches are blind niches so the open ones don't show the sky through
        arch_opening(m, belfry_face(side), (bw_ - aw) // 2, a_z, aw, a_spring,
                     blind=side in ("back", "left"))
    m.box(bx0 + WALL_T - 1, by0 + WALL_T - 1, BELL_Z, bw_ - 2 * WALL_T + 2, bd_ - 2 * WALL_T + 2,
          BELL_TOP - BELL_Z, "shadow", only_filled=True)
    m.box(bx0 + WALL_T, by0 + WALL_T, BELL_Z - 1, bw_ - 2 * WALL_T, bd_ - 2 * WALL_T, 1, "shadow2")
    # bell hangs front-left of centre, so from the camera it sits in the middle of the front arch
    bcx, bcy = bx0 + 7.5, by0 + 8.5
    bell(m, bcx, bcy, BELL_Z + 6)
    m.box(bx0 + WALL_T, int(bcy), BELL_Z + 17, bw_ - 2 * WALL_T, 2, 2, "wood_dk")      # yoke beam
    m.box(int(bcx), int(bcy), BELL_Z + 19, 1, 1, BELL_TOP - BELL_Z - 19, "wood_dk")    # hanger

    # --- pyramid roof
    pyramid_roof(m)

    # --- annex roof + terrace parapet
    lean_to(m)
    par_end = int(TX1 + (Y1 - Y0) * math.tan(math.radians(abs(VIEW["azimuth"]))))
    m.box(AX0 + WALL_T, Y0 + 2, ANNEX_H - 1, par_end - AX0 - WALL_T, TD - 2, 1, "quoin2",
          only_filled=True)                                                    # terrace floor
    m.box(AX0, Y0, ANNEX_H, par_end - AX0, 2, 2, "trim", only_empty=True)      # parapet

    # --- front door with jambs, awning on brackets
    tf = tower_face("front")
    tf.box(m, DOOR_U, DOOR_Z, DOOR_W, DOOR_H, -1, 4, None)
    tf.box(m, DOOR_U, DOOR_Z, DOOR_W, DOOR_H, 1, 1, "door")
    for du in range(0, DOOR_W, 3):
        tf.box(m, DOOR_U + du, DOOR_Z, 1, DOOR_H, 1, 1, "door_dk")       # plank joints
    for dz in (5, 14):
        tf.box(m, DOOR_U, DOOR_Z + dz, DOOR_W, 1, 1, 1, "door_dk")       # rails
    tf.box(m, DOOR_U + DOOR_W - 2, DOOR_Z + 10, 1, 1, 0, 1, "iron")      # knob
    tf.box(m, DOOR_U - 2, DOOR_Z, 2, DOOR_H + 1, -1, 1, "trim")          # jambs
    tf.box(m, DOOR_U + DOOR_W, DOOR_Z, 2, DOOR_H + 1, -1, 1, "trim")
    tf.box(m, DOOR_U - 2, DOOR_Z + DOOR_H, DOOR_W + 4, 2, -1, 1, "trim")  # lintel
    tf.box(m, DOOR_U - 1, 0, DOOR_W + 2, DOOR_Z, -2, 2, "base")           # threshold step

    aw_u0, aw_u1, aw_z = DOOR_U - 7, DOOR_U + DOOR_W + 8, DOOR_Z + DOOR_H + 4
    tf.box(m, aw_u0, aw_z + 2, aw_u1 - aw_u0, 3, -3, 3, "roof")           # back course
    tf.box(m, aw_u0, aw_z, aw_u1 - aw_u0, 3, -6, 3, "roof")               # front course
    retile(m, "roof", ROOFS, [0.5, 0.25, 0.25], size=(3, 3, 2),
           region=(TX0, 0, aw_z - 1, TW + 6, Y0 + 1, 8), salt=7)
    for bu in (aw_u0 + 2, aw_u1 - 4):
        tf.box(m, bu, aw_z - 6, 2, 6, -2, 2, "wood")                       # bracket post
        tf.box(m, bu, aw_z - 1, 2, 1, -5, 5, "wood_dk")                    # bracket arm

    # --- windows
    window(m, tf, 15, WIN_Z, 4, 13)
    window(m, tower_face("right"), 14, WIN_Z, 4, 13)
    window(m, tower_face("left"), 13, WIN_Z, 4, 13)
    window(m, tower_face("back"), 13, WIN_Z, 4, 13)
    window(m, annex_face("front"), 8, AWIN_Z, 8, 13, cross=True)
    window(m, annex_face("right"), 11, AWIN_Z, 6, 13, cross=False)
    window(m, annex_face("back"), 11, AWIN_Z, 8, 13, cross=True)
    window(m, tower_face("back"), 13, AWIN_Z, 4, 13)

    # --- scattered protruding stones, as on the reference walls
    relief_stones(m, tf, 7, 2, TW - 2, 3, CORNICE - 1)
    relief_stones(m, annex_face("front"), 5, 0, AW - 3, 3, ANNEX_H - 2)
    relief_stones(m, tower_face("right"), 3, 2, TD - 2, ANNEX_H + 2, CORNICE - 1)
    relief_stones(m, annex_face("right"), 4, 2, TD - 3, 3, ANNEX_H - 2)
    relief_stones(m, tower_face("left"), 5, 2, TD - 2, 3, CORNICE - 1)
    relief_stones(m, annex_face("back"), 4, 2, AW - 2, 3, ANNEX_H - 2)

    return m
