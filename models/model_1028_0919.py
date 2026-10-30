"""Cream stone cottage with a teal tiled roof — reference/1f334f11-65dc-4598-b632-6f054a6e65b5.png

Layout (x right, y depth with y=0 front, z up):
  body        x HX0..HX1 (40), y HY0..HY1 (38), solid stone walls up to EAVE, plinth course
  main roof   gable, ridge along x, staircase tile courses (2 deep x 3 rise), overhang OV,
              ridge cap of separate tiles
  front       door (left) with stone jambs, lintel and threshold step, small 2x2 window
              (right), tall wall dormer above the door: front flush with the wall, own
              gabled roof (ridge along y), 2x2 window
  right       gable end: two stacked 2x2 windows with lintels and sills, chimney at the
              back of the gable with a teal cap
  quoins      alternating long/short corner stones on all four corners
  walls       running-bond blocks plus scattered proud stones
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0919"
REFERENCE = "reference/1f334f11-65dc-4598-b632-6f054a6e65b5.png"
VIEW = {"azimuth": 318, "elevation": 16, "fov": 5}

HX0, HY0 = 4, 4
W, D = 42, 36                # body footprint
HX1, HY1 = HX0 + W, HY0 + D
PLINTH = 2                   # base course height
EAVE = 40                    # first z above the eave walls
OV = 3                       # roof overhang (eaves and gables)
RUN, RISE, TILE_T = 2, 3, 4  # roof course depth, rise per course, skin thickness
ROOF_Z = EAVE - RISE         # underside of the eave course
QH = 5                       # quoin course height (4 stone + 1 joint)

# front openings (u = voxels from the left front corner)
DOOR_U, DOOR_W, DOOR_Z, DOOR_H = 11, 9, PLINTH + 1, 22
FWIN_U, FWIN_Z = 27, 14                  # small front window
# dormer (front wall flush with the main front wall)
DCX = 19                                 # dormer centre, u
DOR_HALF = 8                             # dormer walls DCX-8 .. DCX+8
DOR_OV = 2                               # dormer roof overhang past its walls
DOR_RZ = EAVE + 11                       # dormer roof underside at its eaves
DOR_D = 14                               # how far the dormer runs back into the main roof
DWIN_Z = EAVE + 1
# right gable windows (u = voxels from the front corner)
SWIN_U = 12
SWIN_LO_Z, SWIN_LO_H = 13, 14
SWIN_HI_Z, SWIN_HI_H = EAVE - 2, 12
# chimney on the back half of the right gable
CH_X0, CH_Y0, CH_W, CH_TOP = HX1 - 6, HY0 + 23, 6, EAVE + 37


def palette(m: Model):
    # base colours ~ reference samples / face shading (front x0.9, right side x0.7)
    p = m.pal
    p.add("wall", "#f3dcbf"); p.add("wall2", "#ebd3b5"); p.add("wall3", "#f8e4ca")
    p.add("joint", "#e6cdae")
    p.add("quoin", "#f1d9bc"); p.add("quoin2", "#e9d0b1")
    p.add("trim", "#f7e2c7"); p.add("plinth", "#e4cbab")
    p.add("roof", "#136a77"); p.add("roof_dk", "#0c5965"); p.add("roof_hi", "#1a7986")
    p.add("ridge", "#106471")
    p.add("door", "#6c3b20"); p.add("door_dk", "#4c2814"); p.add("knob", "#1b1612")
    p.add("win_frame", "#3e2618"); p.add("glass", "#8f9ab3")


ROOF_TILES = ["roof", "roof", "roof_dk", "roof_hi"]


# ---------------------------------------------------------------- helpers

def fbox(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int, c):
    """Box relative to a body wall face. u = position along the face (left->right as
    seen from outside), d0 = depth into the wall (0 = outer layer, -1 = one voxel proud),
    dd = thickness inward."""
    if face == "front":
        m.box(HX0 + u, HY0 + d0, z, w, dd, h, c)
    elif face == "back":
        m.box(HX1 - u - w, HY1 - d0 - dd, z, w, dd, h, c)
    elif face == "left":
        m.box(HX0 + d0, HY1 - u - w, z, dd, w, h, c)
    elif face == "right":
        m.box(HX1 - d0 - dd, HY0 + u, z, dd, w, h, c)


def tile_index(m: Model, a, b, c, salt=0):
    """Deterministic per-tile pick from ROOF_TILES for integer tile coords a, b, c."""
    h = (a.astype(np.int64) * 73856093) ^ (b.astype(np.int64) * 19349663) ^ (c.astype(np.int64) * 83492791 + salt)
    h = (h * 2654435761) % 1000003
    lut = np.array([m.pal.idx(t) for t in ROOF_TILES], np.uint8)
    return lut[h % len(ROOF_TILES)]


def course_roof(m: Model, x, y, w, d, z0, ridge: str, run: int, rise: int, t: int,
                *, fill: str | None = None, fill_region=None, salt=0):
    """Gable roof built from tile courses: every `run` voxels from the eave the roof
    steps up by `rise`; the skin is `t` thick. ridge='x' -> slopes face -y/+y.
    Tiles are 3 voxels long along the ridge, in running bond, each with its own shade.
    fill paints the space under the skin (inside fill_region=(x, y, w, d))."""
    span = d if ridge == "x" else w
    top = z0 + (span // 2 // run + 1) * rise + t + 1

    def under(X, Y):
        a = (Y - y) if ridge == "x" else (X - x)
        dist = np.minimum(a, span - 1 - a)
        course = dist // run
        return course, z0 + course * rise, a

    def skin(X, Y, Z):
        _, u, _ = under(X, Y)
        return (Z >= u) & (Z < u + t)

    m.where(x, y, z0, w, d, top - z0, skin, "roof")

    def colour(X, Y, Z):
        course, _, a = under(X, Y)
        along = X if ridge == "x" else Y
        side = (a >= span / 2).astype(np.int64)
        tile = (along + (course % 2) * 1 + 1000) // 3
        return tile_index(m, course + 50 * side, tile, side, salt)

    m.paint_fn(x, y, z0, w, d, top - z0,
               lambda X, Y, Z: np.where(skin(X, Y, Z), colour(X, Y, Z), 0).astype(np.uint8))
    if fill:
        rx, ry, rw, rd = fill_region or (x, y, w, d)
        m.where(rx, ry, z0, rw, rd, top - z0,
                lambda X, Y, Z: Z < under(X, Y)[1], fill, only_empty=True)


def quoins(m: Model, cx: int, cy: int, sx: int, sy: int, top: int = EAVE):
    """Proud corner stones at wall corner (cx, cy); sx/sy = outward direction."""
    for i, z0 in enumerate(range(PLINTH, top - 1, QH)):
        h = min(QH - 1, top - z0)
        la, lb = (6, 3) if i % 2 == 0 else (3, 6)
        col = "quoin" if i % 2 == 0 else "quoin2"
        x0 = cx + sx if sx < 0 else cx - la + 1
        m.box(x0, cy + sy, z0, la + 1, 1, h, col)
        y0 = cy + sy if sy < 0 else cy - lb + 1
        m.box(cx + sx, y0, z0, 1, lb + 1, h, col)


def window(m: Model, face: str, u: int, z: int, w: int = 7, h: int = 11, *, lintel=True, sill=True):
    """Dark frame, 2x2 panes recessed 1, stone lintel and sill."""
    fbox(m, face, u, z, w, h, 0, 2, "win_frame")
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 0, 1, None)
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 1, 1, "glass")
    fbox(m, face, u + w // 2, z + 1, 1, h - 2, 0, 1, "win_frame")    # mullion
    fbox(m, face, u + 1, z + h // 2, w - 2, 1, 0, 1, "win_frame")    # transom
    if sill:
        fbox(m, face, u - 2, z - 2, w + 4, 2, -2, 2, "trim")
    if lintel:
        fbox(m, face, u - 2, z + h + 1, w + 4, 3, -1, 1, "trim")
    return (u - 3, z - 3, u + w + 3, z + h + 5)        # keep-out rect for wall stones


def proud_stones(m: Model, face: str, length: int, n: int, keep: list, z1: int = EAVE - 2):
    """Scatter 1-voxel-proud wall stones on a face, away from corners and openings."""
    placed = 0
    for _ in range(n * 20):
        if placed >= n:
            break
        w = int(m.rng.integers(2, 4))
        h = int(m.rng.integers(1, 3))
        u = int(m.rng.integers(8, length - 8 - w))
        z = int(m.rng.integers(PLINTH + 2, z1 - h))
        if any(u + w > a and u < c and z + h > b and z < d for a, b, c, d in keep):
            continue
        fbox(m, face, u, z, w, h, -1, 1, "wall3" if placed % 2 else "wall2")
        keep.append((u - 2, z - 2, u + w + 2, z + h + 2))
        placed += 1


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(HX1 + OV + 1, HY1 + OV + 1, CH_TOP + 4, seed=3)
    palette(m)

    # --- body + plinth
    m.box(HX0, HY0, 0, W, D, EAVE, "wall")
    m.box(HX0 - 1, HY0 - 1, 0, W + 2, D + 2, PLINTH, "plinth")

    # --- main roof with gable infill
    rx, ry, rw, rd = HX0 - OV, HY0 - OV, W + 2 * OV, D + 2 * OV
    course_roof(m, rx, ry, rw, rd, ROOF_Z, "x", RUN, RISE, TILE_T,
                fill="wall", fill_region=(HX0, HY0, W, D))
    top_course = ROOF_Z + ((rd // 2 - 1) // RUN) * RISE + TILE_T
    for i, x in enumerate(range(rx, rx + rw, 3)):       # ridge cap: separate tiles
        m.box(x, ry + rd // 2 - 2, top_course, min(3, rx + rw - x), 4, 3,
              "ridge" if i % 2 else "roof")
        m.box(x, ry + rd // 2 - 2, top_course + 2, 1, 4, 1, "roof_dk", only_filled=True)

    # --- dormer: walls flush with the front, own gable roof (ridge along y)
    dx0, dx1 = HX0 + DCX - DOR_HALF, HX0 + DCX + DOR_HALF + 1
    m.carve(dx0, HY0 - OV, EAVE - RISE, dx1 - dx0, OV, TILE_T + RISE)   # main eave in front
    drx0, drw = dx0 - DOR_OV, (dx1 - dx0) + 2 * DOR_OV
    course_roof(m, drx0, HY0 - DOR_OV, drw, DOR_D + DOR_OV, DOR_RZ, "y", 2, 2, 3, salt=7)

    def dormer_under(X, Y, Z):
        a = X - drx0
        dist = np.minimum(a, drw - 1 - a)
        return Z < DOR_RZ + (dist // 2) * 2

    m.where(dx0, HY0, EAVE - RISE, dx1 - dx0, DOR_D, DOR_RZ + 20 - EAVE, dormer_under, "wall")

    # --- chimney (before the wall texture so it gets blocks too)
    m.box(CH_X0, CH_Y0, EAVE, CH_W, CH_W, CH_TOP - EAVE, "wall")

    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=5, bh=3, mortar="joint", p=[0.5, 0.3, 0.2])

    m.box(CH_X0 - 1, CH_Y0 - 1, CH_TOP, CH_W + 2, CH_W + 2, 3, "roof")
    for dx in (0, 4):
        for dy in (0, 4):
            m.box(CH_X0 - 1 + dx, CH_Y0 - 1 + dy, CH_TOP + 2, 4, 4, 1, "roof_hi" if (dx + dy) % 8 else "roof")
    m.box(CH_X0 - 1, CH_Y0 - 1, CH_TOP, CH_W + 2, CH_W + 2, 1, "roof_dk")

    # --- quoins
    quoins(m, HX0, HY0, -1, -1)
    quoins(m, HX1 - 1, HY0, 1, -1)
    quoins(m, HX0, HY1 - 1, -1, 1)
    quoins(m, HX1 - 1, HY1 - 1, 1, 1)

    # --- front door: recessed panelled door, stone jambs, lintel, threshold step
    keep_front = []
    fbox(m, "front", DOOR_U, DOOR_Z, DOOR_W, DOOR_H, 0, 2, None)
    fbox(m, "front", DOOR_U, DOOR_Z, DOOR_W, DOOR_H, 1, 1, "door")
    for pz, ph in ((DOOR_Z + 2, 8), (DOOR_Z + 12, 7)):
        for pu in (DOOR_U + 1, DOOR_U + DOOR_W // 2 + 1):
            fbox(m, "front", pu, pz, DOOR_W // 2 - 2, ph, 1, 1, "door_dk")
            fbox(m, "front", pu, pz + 1, DOOR_W // 2 - 2, ph - 2, 1, 1, "door")
    fbox(m, "front", DOOR_U + DOOR_W - 2, DOOR_Z + 9, 1, 2, 0, 1, "knob")
    for i, z in enumerate(range(DOOR_Z, DOOR_Z + DOOR_H, 4)):
        jw = 3 if i % 2 == 0 else 2
        h = min(3, DOOR_Z + DOOR_H - z)
        fbox(m, "front", DOOR_U - jw, z, jw, h, -1, 1, "trim")
        fbox(m, "front", DOOR_U + DOOR_W, z, jw, h, -1, 1, "trim")
    fbox(m, "front", DOOR_U - 4, DOOR_Z + DOOR_H, DOOR_W + 8, 3, -1, 1, "trim")      # lintel
    fbox(m, "front", DOOR_U - 4, 0, DOOR_W + 8, DOOR_Z, -3, 3, "trim")                # step
    keep_front.append((DOOR_U - 6, 0, DOOR_U + DOOR_W + 6, DOOR_Z + DOOR_H + 5))

    keep_front.append(window(m, "front", FWIN_U, FWIN_Z))
    # dormer window: sill only, the roof sits right above it
    keep_front.append(window(m, "front", DCX - 3, DWIN_Z, lintel=False))

    # --- right gable windows
    keep_right = [window(m, "right", SWIN_U, SWIN_LO_Z, h=SWIN_LO_H),
                  window(m, "right", SWIN_U, SWIN_HI_Z, h=SWIN_HI_H)]

    # --- unseen sides, kept simple
    keep_back = [window(m, "back", 8, FWIN_Z), window(m, "back", 25, FWIN_Z)]
    keep_left = [window(m, "left", D - SWIN_U - 7, SWIN_LO_Z, h=SWIN_LO_H),
                 window(m, "left", D - SWIN_U - 7, SWIN_HI_Z, h=SWIN_HI_H)]

    proud_stones(m, "front", W, 7, keep_front)
    proud_stones(m, "right", D, 7, keep_right)
    proud_stones(m, "back", W, 4, keep_back)
    proud_stones(m, "left", D, 4, keep_left)
    return m
