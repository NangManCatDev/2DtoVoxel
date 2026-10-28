"""Bookshop inn — reference/d3ce6e3e-f63e-49ee-b6b9-8b4dae4b813c.png

Two-storey cream stone house with a teal tile roof, seen from the front-left.

Layout (x right, y depth with y=0 front, z up):
  main body     x HX0..HX1, y HY0..HY1, gable roof (ridge along x, slope 1), stepped tile
                courses, gable ends left/right with dark bargeboards
  centre bay    x CX0..CX1 projects 2 in front, steep front-facing cross gable with timber
                framing (posts, two beams, king post), arched double door with a stone
                surround, book plaque, two steps with cheek blocks
  dormers       two gabled dormers on the front slope, symmetric about the centre bay
  chimneys      left one at the gable end on the ridge, right one a bit inside the right end
  front         2+2 upper windows, wide window under a teal awning (left), two windows under
                a long awning (right), hanging book sign left of the door
  left side     two windows, quoins on every corner, plinth course
"""
import numpy as np

from voxtool import Model

NAME = "d3ce6e3e_f63e_49ee_b6b9_8b4dae4b813c"
REFERENCE = "reference/d3ce6e3e-f63e-49ee-b6b9-8b4dae4b813c.png"
VIEW = {"azimuth": 31, "elevation": 7, "fov": 10}   # perspective reference, fitted

HX0, HX1 = 4, 118     # main body x range [HX0, HX1)
HY0, HY1 = 8, 50      # main body y range (front wall at HY0)
EAVE = 45             # underside of the main roof at its front edge
OVH = 3               # main roof overhang
STEP = 2              # tile course width (horizontal) for all roofs
ROOF_T = 3            # roof skin thickness
HIP_R = 2.5           # the right end of the main roof is a steep hip (rise per voxel)

CX0, CX1 = 41, 74     # centre bay x range (centre x = 57)
CF = HY0 - 2          # centre bay front face
CROSS_SLOPE = 1.35
RIDGE_Y = (HY0 - OVH + HY1 + OVH - 1) // 2   # 27

DORMERS = (22, 92)    # dormer centre x (symmetric about the bay)
DY = HY0 + 2          # dormer front wall
D_EAVE = EAVE + 11
D_SLOPE = 0.8

AW_D = 6              # awning depth
AW_Z = 25             # awning underside at the front edge
UP_Z, UP_H = 31, 11   # upper-floor windows
LO_Z, LO_H = 7, 11    # lower-floor windows
DOOR_Z = 4            # door threshold (two steps of 2)
DOOR_X0, DOOR_X1 = 51, 64

ROOF = ["roof", "roof_hi", "roof_dk"]
ROOF_P = [0.6, 0.2, 0.2]


def palette(m: Model):
    # base colours ~ reference front samples / 0.9 (preview shades the front x0.9, left x0.76)
    p = m.pal
    p.add("wall", "#fde3b8"); p.add("wall2", "#f3d8ac"); p.add("wall3", "#ffeac3")
    p.add("trim", "#ffedcc"); p.add("trim2", "#f6dfb8")
    p.add("stone", "#f3d6ab"); p.add("stone2", "#e6c89d")
    p.add("roof", "#0a7881"); p.add("roof_hi", "#0e848c"); p.add("roof_dk", "#076b74")
    p.add("timber", "#5e3c24"); p.add("timber_dk", "#3f2717")
    p.add("frame", "#452c1a"); p.add("glass", "#4d5d72")
    p.add("door", "#643b20"); p.add("door_dk", "#47291a")
    p.add("iron", "#262321")
    p.add("pot", "#5a5a5e"); p.add("pot_dk", "#3d3d42")
    p.add("sign", "#0b6f77"); p.add("book", "#f4e8cf"); p.add("book_ln", "#8a7458")


# ---------------------------------------------------------------- roofs

def plane(x0, x1, y0, y1, z0, slope, ridge):
    return dict(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, slope=slope, ridge=ridge)


MAIN = dict(plane(HX0 - 2, HX1 + OVH, HY0 - OVH, HY1 + OVH, EAVE, 1.0, "x"), hip_r=HIP_R)
CROSS = plane(CX0 - 2, CX1 + 2, CF - 2, RIDGE_Y + 1, EAVE, CROSS_SLOPE, "y")


def dormer_plane(cx):
    return plane(cx - 11, cx + 12, DY - 3, RIDGE_Y + 1, D_EAVE, D_SLOPE, "y")


def under(p, X, Y):
    """Underside height of a stepped gable roof plane, and the course index."""
    if p["ridge"] == "x":
        a, a0, a1 = Y, p["y0"], p["y1"]
    else:
        a, a0, a1 = X, p["x0"], p["x1"]
    dist = np.minimum(a - a0, a1 - 1 - a)
    course = dist // STEP
    rise = np.floor(course * STEP * p["slope"]).astype(int)
    if p.get("hip_r"):                      # steep hipped end on the +x side
        hip = np.floor((p["x1"] - 1 - X) * p["hip_r"]).astype(int)
        course = np.where(hip < rise, hip // STEP, course)
        rise = np.minimum(rise, hip)
    return p["z0"] + rise, course


def inside(p, X, Y):
    return (X >= p["x0"]) & (X < p["x1"]) & (Y >= p["y0"]) & (Y < p["y1"])


def main_top(X, Y):
    u, _ = under(MAIN, X, Y)
    return np.where(inside(MAIN, X, Y), u + ROOF_T, -1)


def paint_roof(m: Model, p, *, above_main=False):
    """Stepped tile skin with per-tile colour variation. above_main: only where the
    skin rises above the main roof (valleys of dormers / cross gable)."""
    W, D, H = m.v.shape
    x0, x1 = max(p["x0"], 0), min(p["x1"], W)
    y0, y1 = max(p["y0"], 0), min(p["y1"], D)
    X, Y, Z = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1), np.arange(H), indexing="ij")
    u, course = under(p, X, Y)
    skin = (Z >= u) & (Z < u + ROOF_T)
    if above_main:
        skin &= Z >= main_top(X, Y)
    along = X if p["ridge"] == "x" else Y
    tile = (along + course * 2) // 4
    h = ((tile.astype(np.uint64) * np.uint64(73856093)) ^ (course.astype(np.uint64) * np.uint64(19349663)))
    h = ((h * np.uint64(2654435761)) % np.uint64(2 ** 32)).astype(np.float64) / 2 ** 32
    pick = np.searchsorted(np.cumsum(ROOF_P), h, side="right").clip(0, len(ROOF) - 1)
    idx = np.array([m.pal.idx(c) for c in ROOF], np.uint8)[pick]
    sub = m.v[x0:x1, y0:y1, :]
    sub[skin] = idx[skin]


def fill_under(m: Model, p, x0, x1, y0, y1, c="wall", z0=0):
    """Solid body under roof plane p in the columns [x0,x1) x [y0,y1)."""
    m.where(x0, y0, z0, x1 - x0, y1 - y0, m.v.shape[2] - z0,
            lambda X, Y, Z: Z < under(p, X, Y)[0], c)


def bargeboard(m: Model, p, y, x0, x1):
    """Dark board under the front edge of a y-ridge roof plane (at depth y)."""
    for x in range(x0, x1):
        u = int(under(p, np.array(x), np.array(y))[0])
        m.box(x, y, u - 2, 1, 1, 2, "timber_dk")


# ---------------------------------------------------------------- facade helpers

def fbox(m: Model, face: str, fpos: int, u: int, z: int, w: int, h: int, d0: int, dd: int, c):
    """Box on a wall face. face 'front': wall plane y=fpos, u = x; face 'left': wall plane
    x=fpos, u = y. d0 = depth into the wall (0 = outer layer, -1 = one voxel proud)."""
    if face == "front":
        m.box(u, fpos + d0, z, w, dd, h, c)
    else:
        m.box(fpos + d0, u, z, dd, w, h, c)


def window(m: Model, face, fpos, u, z, w=9, h=UP_H, cols=2, surround=True):
    fbox(m, face, fpos, u, z, w, h, 0, 2, "frame")
    fbox(m, face, fpos, u + 1, z + 1, w - 2, h - 2, 0, 2, None)
    fbox(m, face, fpos, u + 1, z + 1, w - 2, h - 2, 2, 1, "glass")
    pw = (w - 1) // cols
    for k in range(1, cols):
        fbox(m, face, fpos, u + k * pw, z + 1, 1, h - 2, 1, 1, "frame")   # mullions
    fbox(m, face, fpos, u + 1, z + (h - 1) // 2, w - 2, 1, 1, 1, "frame")  # transom
    fbox(m, face, fpos, u - 2, z - 2, w + 4, 2, -2, 2, "trim")              # sill
    if surround:
        fbox(m, face, fpos, u - 1, z + h, w + 2, 1, -1, 1, "trim")          # lintel
        fbox(m, face, fpos, u - 1, z, 1, h, -1, 1, "trim2")
        fbox(m, face, fpos, u + w, z, 1, h, -1, 1, "trim2")


def quoin_front(m: Model, x, y, z0, z1, outward: int):
    """Alternating long/short corner stones on a front face, 1 proud; outward = -1 grows
    to the left of x, +1 to the right."""
    for i, z in enumerate(range(z0, z1 - 2, 3)):
        ln = 5 if i % 2 == 0 else 3
        x0 = x if outward > 0 else x - ln + 1
        c = "trim" if i % 2 == 0 else "trim2"
        m.box(x0, y - 1, z, ln, 1, 2, c)


def quoin_side(m: Model, x, y, z0, z1, toward: int):
    """Same on a left (-x) face; toward = +1 grows to +y."""
    for i, z in enumerate(range(z0, z1 - 2, 3)):
        ln = 3 if i % 2 == 0 else 5
        y0 = y if toward > 0 else y - ln + 1
        c = "trim2" if i % 2 == 0 else "trim"
        m.box(x - 1, y0, z, 1, ln, 2, c)


def awning(m: Model, x0, x1, brackets):
    y0 = HY0 - AW_D
    m.shed_roof(x0, y0, AW_Z, x1 - x0, AW_D, "-y", ROOF, slope=0.5, t=2)
    m.box(x0, y0, AW_Z - 2, x1 - x0, 1, 2, "roof_dk")                 # front fascia
    m.vary(ROOF, target=ROOF, p=ROOF_P, region=(x0, y0, AW_Z - 2, x1 - x0, AW_D, 8))
    for x in range(x0 + 2, x1 - 1, 4):
        m.set(x, y0 + 1, AW_Z - 3, "timber_dk")                          # little corbels
    for bx in brackets:
        m.box(bx, HY0 - 1, AW_Z - 9, 2, 1, 9, "timber")                  # wall post
        m.box(bx, y0 + 1, AW_Z - 2, 2, AW_D - 2, 2, "timber")            # arm
        for k in range(AW_D - 2):                                         # diagonal brace
            m.box(bx, HY0 - 2 - k, AW_Z - 8 + k + 1, 2, 1, 2, "timber_dk")


def dormer(m: Model, cx):
    p = dormer_plane(cx)
    fill_under(m, p, cx - 7, cx + 8, DY, RIDGE_Y + 1, z0=EAVE)
    paint_roof(m, p, above_main=True)
    bargeboard(m, p, DY - 1, cx - 9, cx + 10)
    window(m, "front", DY, cx - 4, D_EAVE - 6, w=9, h=9)


def chimney(m: Model, x0, x1, top):
    y0, y1 = RIDGE_Y - 2, RIDGE_Y + 3
    m.box(x0, y0, EAVE, x1 - x0, y1 - y0, top - EAVE, "wall")
    m.box(x0 - 1, y0 - 1, top - 3, x1 - x0 + 2, y1 - y0 + 2, 3, "trim")    # cap
    m.box(x0 + 1, y0, top - 7, 3, 1, 1, "trim2")                           # little relief
    px = (x0 + x1) // 2 - 3
    for i, dx in enumerate((0, 3)):
        for j, dy in enumerate((0, 3)):
            m.box(px + dx, y0 + 1 + dy, top, 3, 3, 4, "pot" if (i + j) % 2 == 0 else "pot_dk")


def sign(m: Model):
    """Iron bracket left of the door with a hanging book shield."""
    sx0, sx1, sy = 39, 47, HY0 - 5
    m.box(36, HY0 - 1, 24, 2, 1, 8, "iron")                                # wall plate
    m.box(37, sy, 29, 1, HY0 - 1 - sy, 1, "iron")                          # arm out
    m.box(37, sy, 29, sx1 - 37 + 1, 1, 1, "iron")                          # arm across
    m.line((37, HY0 - 2, 26), (37, sy + 1, 29), "iron")
    for cx in (sx0 + 1, sx1 - 2):
        m.box(cx, sy, 26, 1, 1, 3, "iron")                                 # chains
    m.box(sx0, sy, 15, sx1 - sx0, 1, 11, "timber_dk")                      # shield
    for k in range(3):                                                     # pointed bottom
        m.box(sx0 + 1 + k, sy, 12 + k, sx1 - sx0 - 2 - 2 * k, 1, 1, "timber_dk")
    m.box(sx0 + 1, sy, 16, sx1 - sx0 - 2, 1, 9, "sign")
    m.box(sx0 + 2, sy, 18, sx1 - sx0 - 4, 1, 5, "book")
    m.box((sx0 + sx1) // 2, sy, 18, 1, 1, 5, "book_ln")


def door(m: Model):
    x0, x1, z0 = DOOR_X0, DOOR_X1, DOOR_Z
    w, h = x1 - x0, 18
    cxm = (x0 + x1 - 1) // 2
    # arched stone surround, 2 proud layers
    m.box(x0 - 3, CF - 1, z0, w + 6, 1, h + 4, "trim")
    for dz, inset in ((h + 2, 3), (h + 3, 5)):
        m.box(x0 - 3, CF - 1, z0 + dz, inset, 1, 2, None)
        m.box(x1 + 3 - inset, CF - 1, z0 + dz, inset, 1, 2, None)
    m.box(cxm - 1, CF - 2, z0 + h + 1, 3, 1, 3, "trim")                   # keystone
    # opening, door leaves recessed 2, rounded top corners in stone
    m.carve(x0, CF - 1, z0, w, 4, h)
    m.box(x0, CF + 2, z0, w, 1, h, "door_dk")
    m.box(x0, CF + 1, z0, w, 1, h, "door")
    for x in range(x0 + 2, x1, 3):
        m.box(x, CF + 1, z0, 1, 1, h, "door_dk")                          # plank joints
    m.box(x0, CF + 1, z0 + 3, w, 1, 1, "door_dk"); m.box(x0, CF + 1, z0 + 12, w, 1, 1, "door_dk")
    m.box(cxm, CF + 1, z0, 1, 1, h, "timber_dk")                          # meeting stile
    for dz, inset in ((h - 1, 3), (h - 2, 1)):
        m.box(x0, CF - 1, z0 + dz, inset, 3, 1, "trim2")
        m.box(x1 - inset, CF - 1, z0 + dz, inset, 3, 1, "trim2")
    for hx in (cxm - 2, cxm + 2):
        m.box(hx, CF, z0 + 8, 1, 1, 3, "iron")                              # ring handles
    # book plaque above the arch
    pz = z0 + h + 4
    m.box(cxm - 5, CF - 1, pz, 11, 1, 6, "trim")
    m.box(cxm - 3, CF - 1, pz + 6, 7, 1, 1, "trim")
    m.box(cxm - 4, CF - 2, pz + 1, 9, 1, 4, "trim2")
    m.box(cxm - 3, CF - 3, pz + 2, 3, 1, 2, "book"); m.box(cxm + 1, CF - 3, pz + 2, 3, 1, 2, "book")
    m.box(cxm, CF - 3, pz + 2, 1, 1, 2, "book_ln")


def steps(m: Model):
    m.box(41, CF - 6, 0, 33, 6, 2, "stone")
    m.box(48, CF - 3, 2, 19, 3, 2, "stone")
    m.box(48, CF - 3, 3, 19, 1, 1, "stone2")
    for x0 in (44, 66):
        m.box(x0, CF - 5, 0, 5, 5, 6, "trim")
        m.box(x0, CF - 5, 5, 5, 5, 1, "trim2")


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(HX1 + OVH + 1, HY1 + OVH + 1, 84, seed=11)
    palette(m)
    W, D = HX1 - HX0, HY1 - HY0

    # --- main body + attic (solid; openings are carved with depth)
    fill_under(m, MAIN, HX0, HX1, HY0, HY1)
    paint_roof(m, MAIN)
    for y in range(MAIN["y0"], MAIN["y1"]):                                # left gable bargeboard
        u = int(under(MAIN, np.array(HX0 - 1), np.array(y))[0])
        m.box(HX0 - 1, y, u - 2, 1, 1, 2, "timber_dk")

    # --- centre bay with its front cross gable
    m.carve(CX0, MAIN["y0"], EAVE, CX1 - CX0, CF - MAIN["y0"], 30)        # main eave in front of it
    fill_under(m, CROSS, CX0, CX1, CF, RIDGE_Y + 1)
    paint_roof(m, CROSS, above_main=True)
    bargeboard(m, CROSS, CF - 1, CX0 - 1, CX1 + 1)

    for cx in DORMERS:
        dormer(m, cx)

    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=6, bh=3, p=[0.5, 0.3, 0.2])
    # scattered proud stones (small cross / bar reliefs on the plaster)
    for x, z in ((20, 26), (37, 37), (64, 12), (88, 26), (108, 12), (36, 4), (70, 40), (112, 30)):
        m.box(x, HY0 - 1, z, 3, 1, 1, "trim2", only_empty=True)
        m.box(x + 1, HY0 - 1, z + 1, 1, 1, 1, "trim2", only_empty=True)
    for y, z in ((14, 24), (40, 14), (20, 46), (34, 52), (44, 36)):
        m.box(HX0 - 1, y, z, 1, 3, 1, "trim2", only_empty=True)
        m.box(HX0 - 1, y + 1, z + 1, 1, 1, 1, "trim2", only_empty=True)

    # --- plinth
    m.box(HX0 - 1, HY0 - 1, 0, W + 2, D + 2, 2, "stone")
    m.box(CX0 - 1, CF - 1, 0, CX1 - CX0 + 2, 2, 2, "stone")
    m.box(HX0 - 1, HY0 - 1, 2, W + 2, 1, 1, "stone2", only_empty=True)

    # --- quoins
    quoin_front(m, HX0, HY0, 2, EAVE, +1)
    quoin_side(m, HX0, HY0, 2, EAVE, +1)
    quoin_side(m, HX0, HY1 - 1, 2, EAVE, -1)
    quoin_front(m, HX1 - 1, HY0, 2, EAVE, -1)
    quoin_front(m, CX0, CF, 2, 30, +1)
    quoin_front(m, CX1 - 1, CF, 2, 30, -1)

    # --- eave corbels
    for x in list(range(HX0 + 2, CX0 - 2, 11)) + list(range(CX1 + 3, HX1 - 1, 11)):
        m.box(x, HY0 - 2, EAVE - 3, 3, 2, 3, "timber")
        m.box(x, HY0 - 1, EAVE - 4, 3, 1, 1, "timber_dk")
    for y in range(HY0 + 3, HY1 - 2, 11):
        m.box(HX0 - 2, y, EAVE - 3, 2, 3, 3, "timber")

    # --- centre bay timber framing (posts stop under the bargeboard)
    def gable_u(x):
        return int(under(CROSS, np.array(x), np.array(CF))[0]) - 2
    lo_beam, up_beam = EAVE - 10, EAVE + 7
    for x in list(range(CX0, CX0 + 3)) + list(range(CX1 - 3, CX1)) + [56, 57, 58]:
        z0 = up_beam + 2 if 56 <= x <= 58 else lo_beam - 4
        m.box(x, CF - 1, z0, 1, 1, gable_u(x) - z0, "timber")
    m.box(CX0, CF - 1, lo_beam, CX1 - CX0, 1, 2, "timber")                # lower beam
    m.box(CX0 + 3, CF - 1, up_beam, CX1 - CX0 - 6, 1, 2, "timber")        # upper beam
    for x in (CX0, CX1 - 3):
        m.box(x, CF - 2, lo_beam - 4, 3, 1, 3, "timber_dk")                # post corbels
    window(m, "front", CF, 53, lo_beam + 4, w=9, h=10)

    # --- windows
    for x in (8, 26, 78, 96):
        window(m, "front", HY0, x, UP_Z)
    window(m, "front", HY0, 10, LO_Z + 1, w=21, h=LO_H, cols=4)
    for x in (77, 95):
        window(m, "front", HY0, x, LO_Z)
    for z in (UP_Z, LO_Z + 2):
        window(m, "left", HX0, (HY0 + HY1) // 2 - 4, z)

    # --- awnings
    awning(m, HX0, CX0 - 2, (HX0 + 2, CX0 - 8))
    awning(m, CX1 - 2, HX1 - 1, (CX1, (CX1 + HX1) // 2, HX1 - 5))

    door(m)
    steps(m)
    sign(m)

    # --- chimneys
    ridge_top = EAVE + (RIDGE_Y - MAIN["y0"]) // STEP * STEP + ROOF_T
    chimney(m, HX0 + 3, HX0 + 12, ridge_top + 5)
    chimney(m, HX1 - 16, HX1 - 7, ridge_top + 2)

    return m
