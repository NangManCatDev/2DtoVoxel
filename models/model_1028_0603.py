"""Stone garden wall with a coping cap — reference/2e3a65b7-001b-4dfe-be96-f97c25a0aad7.png

Layout (x right, y depth with y=0 front, z up):
  body     x WX0..WX1 (120 long), y BY0..BY1 (18 deep), 3 courses of COURSE voxels
           stones are boxes sitting in front of a recessed mortar core (joints 1 wide,
           2 deep), chipped corners / stepped edge notches / small 1-voxel holes;
           some stones set back by 1, the right corner stones protrude by 1 and wrap
           around the end face
  cap      coping slabs over the whole top, CAP_H thick, overhanging 1 at the ends and
           2 at front/back; slab joints are 1-voxel grooves on the front face that run
           over the top in a stepped line, a few slabs sit 1 lower
  camera   the long front face recedes to the left, the right end face is visible
           (camera at front-right -> negative azimuth)
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0603"
REFERENCE = "reference/2e3a65b7-001b-4dfe-be96-f97c25a0aad7.png"
VIEW = {"azimuth": 326, "elevation": 22, "fov": 45}

LEN = 130            # body length
DEPTH = 13           # body depth
COURSE = 12          # stone course height (incl. 1-voxel joint on top)
COURSES = 3
CAP_H = 5            # coping thickness
CAP_OV_L, CAP_OV_R = 1, 2   # cap overhang at the left/right ends
CAP_OV_FB = 2        # cap overhang at front/back
JOINT_D = 2          # how far joints sit behind the stone faces
STONE_T = 3          # stone thickness in front of the core

GX = LEN + CAP_OV_L + CAP_OV_R
GY = DEPTH + 2 * CAP_OV_FB
WX0, WX1 = CAP_OV_L, CAP_OV_L + LEN
BY0, BY1 = CAP_OV_FB, CAP_OV_FB + DEPTH
BODY_H = COURSE * COURSES
GZ = BODY_H + CAP_H
CORNERS = [13, 12, 12]   # width (along x) of the right corner stone per course

# stone starts per course along the front face, bottom course first (body x, 0..LEN),
# read off the reference with perspective corrected; the corner stone follows
FRONT_COURSES = [
    [0, 17, 23, 50, 55, 79, 93],
    [0, 11, 41, 66, 85, 99],
    [0, 6, 27, 49, 54, 74, 98, 111],
]
# the back face is not visible: a simple running bond
BACK_COURSES = [
    [0, 20, 43, 67, 92],
    [0, 12, 33, 56, 80, 104],
    [0, 24, 48, 73, 97],
]
# coping slab joints (cap x) and slabs that sit one voxel lower
CAP_JOINTS = [22, 43, 69, 80, 96, 118]
CAP_LOW = {4}

STONES = ["stone", "stone2", "stone3", "stone4"]


def palette(m: Model):
    # top of the cap samples ~#dcd3c7, front faces ~#c6b9a6 (/0.9), end face ~#9b9081 (/0.7)
    p = m.pal
    p.add("stone", "#dccdb8"); p.add("stone2", "#d6c7b2"); p.add("stone3", "#e0d2be")
    p.add("stone4", "#d2c3ad")
    p.add("fleck", "#cbbda8"); p.add("fleck2", "#e2d6c5")
    p.add("mortar", "#b0a390")
    # cap top is lighter and greyer than its front face (~#bfb4a3 in the reference)
    p.add("cap", "#ded5c8"); p.add("cap2", "#d9cfc1"); p.add("cap3", "#e4dccf")
    p.add("capside", "#d5c9b7")


# ---------------------------------------------------------------- helpers

def chip_stone(m: Model, x0, x1, y_face, z0, z1, face: str):
    """Chips a stone's outer face: stepped corner notches, edge notches and small
    holes. face '-y' (front, y_face = outermost y) or '+y' (back)."""
    rng = m.rng
    w, h = x1 - x0, z1 - z0
    dy = 1 if face == "-y" else -1

    def cut(x, z, cw, ch, depth=1):
        for k in range(depth):
            y = y_face + dy * k
            m.box(x, y, z, cw, 1, ch, None)

    # stepped corner notches (staircase of 2 levels)
    for cx, cz, sx, sz in ((x0, z0, 1, 1), (x1, z0, -1, 1), (x0, z1, 1, -1), (x1, z1, -1, -1)):
        if rng.random() < 0.65:
            a, b = int(rng.integers(2, 5)), int(rng.integers(1, 3))
            # a wide x b tall, plus a narrower but taller step
            for cw, ch in ((a, b), (max(a - 2, 1), b + 1)):
                cut(cx if sx > 0 else cx - cw, cz if sz > 0 else cz - ch, cw, ch)
            if rng.random() < 0.3:
                cut(cx if sx > 0 else cx - 1, cz if sz > 0 else cz - 1, 1, 1, 2)
    # notches along the top and bottom edges
    for _ in range(int(rng.integers(1, 4))):
        cw = int(rng.integers(2, 6))
        x = int(rng.integers(x0 + 2, max(x0 + 3, x1 - cw - 1)))
        if rng.random() < 0.5:
            cut(x, z1 - 1, cw, 1); cut(x + 1, z1 - 2, max(cw - 2, 1), 1)
        else:
            cut(x, z0, cw, 1)
    # notches along the left/right edges
    for _ in range(int(rng.integers(0, 3))):
        ch = int(rng.integers(2, 4))
        z = int(rng.integers(z0 + 1, max(z0 + 2, z1 - ch)))
        if rng.random() < 0.5:
            cut(x0, z, 1, ch)
        else:
            cut(x1 - 1, z, 1, ch)
    # small holes in the face
    for _ in range(int(rng.integers(0, 3))):
        if w > 6 and h > 5:
            hx = int(rng.integers(x0 + 2, x1 - 2))
            hz = int(rng.integers(z0 + 2, z1 - 3))
            cut(hx, hz, 1, int(rng.integers(1, 3)))


def stone_course(m: Model, joints, r: int, face: str):
    """One course of stones along a long face. joints are body-x positions of the
    stone starts; the last stone runs to the corner stone."""
    z0 = r * COURSE
    z1 = z0 + COURSE - 1
    edges = list(joints) + [LEN - CORNERS[r]]
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        if b - a < 2:
            continue
        x0, x1 = WX0 + a, WX0 + b - 1
        setback = int(m.rng.random() < 0.25)
        col = STONES[int(m.rng.integers(len(STONES)))]
        if face == "-y":
            y_face = BY0 + setback
            m.box(x0, y_face, z0, x1 - x0, STONE_T - setback, z1 - z0, col)
        else:
            y_face = BY1 - 1 - setback
            m.box(x0, BY1 - STONE_T, z0, x1 - x0, STONE_T - setback, z1 - z0, col)
        chip_stone(m, x0, x1, y_face, z0, z1, face)


def corner_stones(m: Model):
    """Full-depth corner stones at the right end, protruding 1 at the front."""
    for r in range(COURSES):
        z0 = r * COURSE
        z1 = z0 + COURSE - 1
        col = STONES[(r + 2) % len(STONES)]
        x0, x1 = WX1 - CORNERS[r], WX1
        m.box(x0, BY0 - 1, z0, x1 - x0, DEPTH + 1, z1 - z0, col)
        chip_stone(m, x0, x1, BY0 - 1, z0, z1, "-y")
        chip_stone(m, x0, x1, BY1 - 1, z0, z1, "+y")
        # chips on the end face (x-facing): stepped notches at the edges
        ex = x1 - 1
        for _ in range(int(m.rng.integers(2, 5))):
            cy = int(m.rng.integers(BY0, BY1 - 2))
            cz = z1 - 1 if m.rng.random() < 0.5 else z0
            m.box(ex, cy, cz, 1, int(m.rng.integers(2, 4)), 1, None)
        if m.rng.random() < 0.6:
            m.box(ex, int(m.rng.integers(BY0 + 2, BY1 - 3)), int(m.rng.integers(z0 + 2, z1 - 3)), 1, 1, 2, None)


def coping(m: Model):
    z0 = BODY_H
    m.box(0, 0, z0, GX, GY, CAP_H, "capside")
    edges = [0] + CAP_JOINTS + [GX]
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        if i in CAP_LOW:
            m.box(a, 0, GZ - 1, b - a, GY, 1, None)
    # slab joints: groove on the front/back face, stepped line over the top
    for j in CAP_JOINTS:
        m.box(j, 0, z0, 1, 1, CAP_H, None)
        m.box(j, GY - 1, z0, 1, 1, CAP_H, None)
        x = j
        for y in range(GY):
            if y > 0 and m.rng.random() < 0.18:
                step = int(m.rng.choice([-2, -1, 1, 2]))
                lo, hi = min(x, x + step), max(x, x + step)
                for xx in range(lo, hi + 1):
                    _carve_top(m, xx, y)
                x += step
            _carve_top(m, x, y)
    # chipped front/top edge notches and corner notches
    for _ in range(14):
        x = int(m.rng.integers(1, GX - 3))
        w = int(m.rng.integers(1, 4))
        for xx in range(x, x + w):
            _carve_top(m, xx, 0)
        if m.rng.random() < 0.5:
            _carve_top(m, x, 1)
    # the topmost voxel of every column is top-surface colour
    cap = m.v[:, :, z0:]
    filled = cap > 0
    top = np.where(filled.any(axis=2), CAP_H - 1 - np.argmax(filled[:, :, ::-1], axis=2), -1)
    xs, ys = np.nonzero(top >= 0)
    cap[xs, ys, top[xs, ys]] = m.pal.idx("cap")
    # subtle colour patches on the top
    m.bricks(["cap", "cap2", "cap3"], target="cap", bw=7, bh=2, p=[0.5, 0.3, 0.2], salt=3,
             region=(0, 0, z0, GX, GY, CAP_H))


def _carve_top(m: Model, x, y):
    """Removes the topmost filled cap voxel at column (x, y)."""
    for z in range(GZ - 1, BODY_H + CAP_H - 3, -1):
        if m.get(x, y, z):
            m.set(x, y, z, None)
            return


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(GX, GY, GZ, seed=7)
    palette(m)

    # recessed mortar core
    m.box(WX0, BY0 + JOINT_D, 0, LEN - 1, DEPTH - 2 * JOINT_D, BODY_H, "mortar")

    for r in range(COURSES):
        stone_course(m, FRONT_COURSES[r], r, "-y")
        stone_course(m, BACK_COURSES[r], r, "+y")
    corner_stones(m)

    # weathering flecks on the stone faces
    m.sprinkle(["fleck", "fleck2"], 0.035, target=STONES)

    coping(m)
    return m
