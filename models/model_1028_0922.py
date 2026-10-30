"""Narrow 3-storey stone town house — reference/56c88955-6d32-4868-9261-2c84db3db7d4.png

Layout (x right, y depth with y=0 front, z up):
  body        cream stone, x HX0..HX1 (42), y HY0..HY1 (38), walls up to EAVE (58)
  roof        steep stepped gable (ridge along x, pitch ~1.5), teal tiles in courses
              RUN deep, overhangs 3 at the front/back and 2 at both gable ends
  front (-y)  centred column: door with stone jambs, lintel and step; first-floor
              window with sill + lintel; a gabled dormer with a small window above
  right (+x)  gable wall with two windows (lower one between the front storeys,
              upper one in the gable), sills and lintels
  corners     protruding long/short quoins on all four corners
  back/left   same openings as front/right (not visible in the reference)
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0922"
REFERENCE = "reference/56c88955-6d32-4868-9261-2c84db3db7d4.png"
VIEW = {"azimuth": -40, "elevation": 18}

HX0, W = 3, 44          # body x range [HX0, HX1)
HY0, D = 4, 39          # body y range [HY0, HY1)
HX1, HY1 = HX0 + W, HY0 + D
EAVE = 58               # first z above the walls
WALL_T = 3
OVER, OVER_X = 3, 2     # roof overhang at the front/back, at the gable ends
RUN, SLOPE, SKIN = 3, 1.5, 5   # main roof course depth, pitch, vertical skin thickness

QH, QP, QBASE = 6, 1, 8  # quoin course height (incl. 1 joint), protrusion, base course

COL = HX0 + W // 2      # centre of the front opening column
DOOR_Z, DOOR_W, DOOR_H = 3, 9, 20
WIN_W, WIN_H = 9, 13
W1_Z = 35               # front first-floor window bottom
SW_LO, SW_HI = 20, 49   # right-side window bottoms
SIDE_U = D // 2 - WIN_W // 2 - 1   # right-side window position along the face

# dormer
DM_W = 19
DM_X0 = COL - DM_W // 2
DM_Y0 = HY0             # dormer front face (right behind the first roof course)
DM_EAVE = EAVE + 10     # underside of the dormer roof eave
DM_OVER = 1             # dormer roof overhang in front of its face
DM_RUN, DM_SLOPE, DM_SKIN = 2, 1.5, 4
DM_WIN_W, DM_WIN_H, DM_WIN_Z = 9, 11, EAVE + 6


def palette(m: Model):
    # base colours ~ reference face colour / shading (front x0.9, right x0.7)
    p = m.pal
    p.add("wall", "#f0d6b6"); p.add("wall2", "#eacfae"); p.add("wall3", "#f4dbbd")
    p.add("mortar", "#dcc09d")
    p.add("quoin", "#eed4b3"); p.add("quoin2", "#e6cba9")
    p.add("trim", "#f3dcbf")
    p.add("roof", "#0a5c68"); p.add("roof2", "#08535e"); p.add("roof3", "#0c6573")
    p.add("roof_dk", "#064652")
    p.add("door", "#6e3a1e"); p.add("door_dk", "#4c2815"); p.add("iron", "#1c1a19")
    p.add("frame", "#2d1b12"); p.add("glass", "#66717c")


ROOF = ["roof", "roof2", "roof3"]


# ---------------------------------------------------------------- helpers

def fbox(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int, c):
    """Box relative to a body wall face. u = position along the face (left->right
    seen from outside), d0 = depth into the wall (0 = outer layer, -1 = one voxel
    in front of the wall), dd = thickness inward."""
    if face == "front":
        m.box(HX0 + u, HY0 + d0, z, w, dd, h, c)
    elif face == "back":
        m.box(HX1 - u - w, HY1 - d0 - dd, z, w, dd, h, c)
    elif face == "right":
        m.box(HX1 - d0 - dd, HY0 + u, z, dd, w, h, c)
    elif face == "left":
        m.box(HX0 + d0, HY1 - u - w, z, dd, w, h, c)


def window(m: Model, face: str, u: int, z: int, w: int = WIN_W, h: int = WIN_H,
           ext: int = 4, sill_h: int = 3, lintel_h: int = 4):
    """Dark frame with 2x2 panes recessed into the wall, stone sill + lintel and
    jamb stones."""
    fbox(m, face, u, z, w, h, 0, 2, None)                          # reveal
    fbox(m, face, u, z, w, h, 1, 1, "frame")
    for pu, pw in ((u + 1, w // 2 - 1), (u + w // 2 + 1, w - w // 2 - 2)):
        for pz, ph in ((z + 1, h // 2 - 1), (z + h // 2 + 1, h - h // 2 - 2)):
            fbox(m, face, pu, pz, pw, ph, 1, 1, None)
            fbox(m, face, pu, pz, pw, ph, 2, 1, "glass")
    fbox(m, face, u - ext, z - sill_h, w + 2 * ext, sill_h, -2, 2, "trim")   # sill
    fbox(m, face, u - ext, z + h, w + 2 * ext, lintel_h, -2, 2, "trim")      # lintel
    fbox(m, face, u - 1, z, 1, h, -1, 1, "quoin2")                           # jambs
    fbox(m, face, u + w, z, 1, h, -1, 1, "quoin2")


def door(m: Model, u: int):
    z, w, h = DOOR_Z, DOOR_W, DOOR_H
    fbox(m, "front", u, z, w, h, 0, 2, None)
    fbox(m, "front", u, z, w, h, 1, 1, "door")
    for pu in (u + 1, u + w // 2 + 1):                       # 4 sunken panels
        for pz, ph in ((z + 1, 8), (z + 10, h - 11)):
            fbox(m, "front", pu, pz, w // 2 - 1, ph, 1, 1, "door_dk")
    fbox(m, "front", u + w // 2, z, 1, h, 1, 1, "door_dk")    # centre plank joint
    fbox(m, "front", u + w - 2, z + 9, 1, 2, 0, 1, "iron")    # handle
    # stone surround: jambs, lintel, step
    for ju in (u - 3, u + w):
        for k, jz in enumerate(range(z, z + h, 5)):
            fbox(m, "front", ju, jz, 3, 4, -1, 1, "quoin" if k % 2 else "quoin2")
    fbox(m, "front", u - 5, z + h, w + 10, 5, -2, 2, "trim")
    fbox(m, "front", u - 5, 0, w + 10, z, -4, 4, "trim")
    fbox(m, "front", u - 5, z - 1, w + 10, 1, -4, 4, "quoin")


def quoins(m: Model, cx: int, cy: int, sx: int, sy: int):
    """Protruding corner stones at corner voxel (cx, cy); sx/sy = outward direction.
    The bottom course is a bigger base stone."""
    courses = [(0, QBASE, 8, 5, QP + 1)] + [(z, QH, 7, 4, QP) for z in range(QBASE, EAVE, QH)]
    for i, (z, qh, l1, l2, qp) in enumerate(courses):
        la, lb = (l1, l2) if i % 2 == 0 else (l2, l1)
        col = "quoin" if i % 2 == 0 else "quoin2"
        hz = min(qh - 1, EAVE - z)
        # stone on the y-facing wall: runs along x, protrudes in y
        xa0 = min(cx - sx * (la - 1), cx + sx * qp)
        m.box(xa0, min(cy + sy, cy + sy * qp), z, la + qp, qp, hz, col)
        # stone on the x-facing wall: runs along y, protrudes in x
        yb0 = min(cy - sy * (lb - 1), cy + sy * qp)
        m.box(min(cx + sx, cx + sx * qp), yb0, z, qp, lb + qp, hz, col)


def roof_top(dist, run: int, slope: float, z0: int):
    """Top z (exclusive) of a stepped roof course `dist` voxels in from the eave:
    courses `run` deep, rising `run * slope` each (rounded)."""
    return z0 + 3 + int((dist // run) * run * slope + 0.5)


def tile_paint(m: Model, x0, y0, z0, w, d, h, along: str, course_fn, tile_w: int = 4):
    """Recolours roof voxels into tiles: per-tile colour, dark joints between tiles.
    along = axis the tile rows run along; course_fn(other coord) -> course index."""
    ids = [m.pal.idx(c) for c in ROOF]
    dk = m.pal.idx("roof_dk")
    targets = set(ids)

    def fn(X, Y, Z):
        a, b = (X, Y) if along == "x" else (Y, X)
        k = course_fn(b)
        off = (k % 2) * (tile_w // 2)
        t = (a + off) // tile_w
        hsh = (t * 73856093 ^ k * 19349663 ^ (Z // 7) * 83492791) % 7
        out = np.array(ids)[np.clip(hsh % 3, 0, 2)]
        joint = (a + off) % tile_w == 0
        out = np.where(joint, dk, out)
        cur = m.v[X, Y, Z]
        return np.where(np.isin(cur, list(targets)), out, 0)

    m.paint_fn(x0, y0, z0, w, d, h, fn)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(HX1 + 3, HY1 + OVER + 1, roof_top((D + 2 * OVER) // 2, RUN, SLOPE, EAVE) + 2, seed=11)
    palette(m)

    # --- body (hollow), gable walls under the stepped roof
    m.shell(HX0, HY0, 0, W, D, EAVE, "wall", t=WALL_T, top=False, bottom=True)
    ry0, ry1 = HY0 - OVER, HY1 + OVER
    rx0, rx1 = HX0 - OVER_X, HX1 + OVER_X
    for y in range(HY0, HY1):
        top = roof_top(min(y - ry0, ry1 - 1 - y), RUN, SLOPE, EAVE)
        for gx in (HX0, HX1 - WALL_T):
            m.box(gx, y, EAVE, WALL_T, 1, top - SKIN - EAVE, "wall")

    # --- openings, before texturing so the reveals get stone colours too
    door(m, COL - DOOR_W // 2)
    window(m, "front", W // 2 - WIN_W // 2, W1_Z)
    window(m, "back", W // 2 - WIN_W // 2, W1_Z)
    window(m, "back", W // 2 - WIN_W // 2, SW_LO - 6)
    for face in ("right", "left"):
        window(m, face, SIDE_U, SW_LO, ext=3)
        window(m, face, SIDE_U, SW_HI, ext=3)

    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=5, bh=3, p=[0.55, 0.25, 0.2])

    # a few raised stones on the walls (as in the reference)
    for u, z in ((4, 46), (11, 31), (31, 38), (34, 12), (6, 20), (36, 27)):
        fbox(m, "front", u, z, 3, 2, -1, 1, "wall3")
    for u, z in ((4, 40), (30, 30), (8, 8), (31, 58), (6, 54), (28, 12)):
        fbox(m, "right", u, z, 3, 2, -1, 1, "wall3")

    # --- quoins on the four corners
    quoins(m, HX0, HY0, -1, -1)
    quoins(m, HX1 - 1, HY0, 1, -1)
    quoins(m, HX0, HY1 - 1, -1, 1)
    quoins(m, HX1 - 1, HY1 - 1, 1, 1)

    # --- main roof: stepped courses, ridge along x
    for y in range(ry0, ry1):
        top = roof_top(min(y - ry0, ry1 - 1 - y), RUN, SLOPE, EAVE)
        m.box(rx0, y, top - SKIN, rx1 - rx0, 1, SKIN, "roof")
    tile_paint(m, rx0, ry0, EAVE - 3, rx1 - rx0, ry1 - ry0, m.v.shape[2], "x",
               lambda Y: (Y - ry0).clip(0, None) // RUN)

    # --- dormer: cream body + stepped gable roof, merging into the main roof
    dx0, dx1 = DM_X0, DM_X0 + DM_W
    drx0, drx1 = dx0 - 2, dx1 + 2
    dy1 = (HY0 + HY1) // 2
    for x in range(dx0, dx1):
        top = roof_top(min(x - drx0, drx1 - 1 - x), DM_RUN, DM_SLOPE, DM_EAVE)
        m.box(x, DM_Y0, EAVE + 1, 1, dy1 - DM_Y0, top - DM_SKIN - EAVE - 1, "wall")
    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=5, bh=3, p=[0.55, 0.25, 0.2],
             region=(dx0, DM_Y0, EAVE, DM_W, 3, 30), salt=3)
    for x in range(drx0, drx1):
        top = roof_top(min(x - drx0, drx1 - 1 - x), DM_RUN, DM_SLOPE, DM_EAVE)
        m.box(x, DM_Y0 - DM_OVER, top - DM_SKIN, 1, dy1 - DM_Y0 + DM_OVER, DM_SKIN, "roof")
    tile_paint(m, drx0, DM_Y0 - DM_OVER, DM_EAVE - 2, drx1 - drx0, dy1 - DM_Y0 + DM_OVER, 30, "y",
               lambda X: (X - drx0).clip(0, drx1 - drx0) // DM_RUN, tile_w=3)
    # dormer window, sill and side stones
    wu = COL - DM_WIN_W // 2
    wz = DM_WIN_Z
    m.box(wu, DM_Y0, wz, DM_WIN_W, 2, DM_WIN_H, None)
    m.box(wu, DM_Y0 + 1, wz, DM_WIN_W, 1, DM_WIN_H, "frame")
    for pu in (wu + 1, wu + DM_WIN_W // 2 + 1):
        for pz in (wz + 1, wz + DM_WIN_H // 2 + 1):
            m.box(pu, DM_Y0 + 1, pz, DM_WIN_W // 2 - 1, 2, DM_WIN_H // 2 - 1, None)
            m.box(pu, DM_Y0 + 2, pz, DM_WIN_W // 2 - 1, 1, DM_WIN_H // 2 - 1, "glass")
    m.box(dx0 - 1, DM_Y0 - 2, wz - 3, DM_W + 2, 3, 3, "trim")
    for jx in (wu - 1, wu + DM_WIN_W):
        m.box(jx, DM_Y0 - 1, wz, 1, 1, DM_WIN_H, "quoin2")

    return m
