"""Street props kit — reference/06693603-1b73-49f7-a4b2-51cb6dd7278f.png

A kit sheet of three loose props, all seen from the front-right: the long front faces
(-y) run down-right to the nearest corner, the short +x ends run up-right (camera
azimuth 315). Scale: about 8 reference px per voxel. Every prop is its own m.part(),
so the .vox holds one named object per prop that can be moved on its own.

Layout (x right, y depth with y=0 front, z up). The props stand on z=0 and are placed
so their nearest bottom corners land where the sheet has them, which puts them on a
diagonal (each one further back than the one before):
  drain    x 0..99,   y 0..36    stone gutter: front curb, sunken grey channel with an
                                 iron grate, back curb of two stone rows
  crate    x 98..132, y 47..69   plank crate: 3 boards a side with dark gaps, corner
                                 posts with bolts, handle slots in the ends, three corked
                                 potions inside (big purple, amber, small violet)
  planter  x 126..195, y 93..122 3-course stone trough full of leaves, vines hanging over
                                 the front and the right end, violet and pale flowers
"""
import numpy as np

from voxtool import Model

NAME = "model_1029_0011"
REFERENCE = "reference/06693603-1b73-49f7-a4b2-51cb6dd7278f.png"
VIEW = {"azimuth": 315, "elevation": 34}
CUTOUT = {"keep": "all"}

GRID = (200, 128, 40)

# drain: depths of the three strips (front to back) and their top heights
DR_X, DR_Y, DR_L = 0, 0, 100
FC_D, CH_D, BC_D = 6, 18, 13
FC_H, CH_H, BC_H = 10, 5, 10
GRATE_X, GRATE_W = 58, 20          # along the channel
GRATE_Y, GRATE_D = 3, 13           # from the front of the channel

# crate: body without the corner posts (posts stick out 1 on every side)
CR_X, CR_Y = 99, 48
CR_W, CR_D, CR_H = 33, 21, 17
WALL_T, BOARD = 2, 5
FLOOR_Z = 6                        # potions stand on packing this high

# planter
PL_X, PL_Y = 126, 93
PL_W, PL_D = 70, 30
COURSE, COURSES = 7, 3
PL_H = COURSE * COURSES + 1        # the top course is one taller
PL_T = 5

STONES = ["stone0", "stone1", "stone2", "stone3"]
COBBLES = ["cob0", "cob1", "cob2"]
WOODS = ["wood0", "wood1", "wood2"]
PSTONES = ["pst0", "pst1", "pst2"]
LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3", "leaf4"]
LEAF_P = [0.3, 0.25, 0.2, 0.15, 0.1]


def palette(m: Model):
    p = m.pal
    # drain stone (front sample / 0.9), blue-grey mottling, channel slate
    p.add("stone0", "#cdbfb1"); p.add("stone1", "#c4b4a5"); p.add("stone2", "#d6cabd"); p.add("stone3", "#bba999")
    p.add("spot0", "#a69a92"); p.add("spot1", "#b4aaa6"); p.add("sjoint", "#857870")
    p.add("cob0", "#686162"); p.add("cob1", "#5a5455"); p.add("cob2", "#757070")
    p.add("cjoint", "#383334"); p.add("chwall", "#6a6466")
    p.add("iron", "#6a4c42", metal=0.6, rough=0.4); p.add("iron_dk", "#4a352e", metal=0.6, rough=0.4)
    p.add("hole", "#1c1818")
    # crate wood
    p.add("wood0", "#7c5740"); p.add("wood1", "#6f4d38"); p.add("wood2", "#86624a")
    p.add("wood_lt", "#9b7356"); p.add("grain", "#5a3d2c"); p.add("gap", "#2a1b15")
    p.add("post", "#5e3f2f"); p.add("inner", "#3d2a20"); p.add("bolt", "#3a3639", metal=0.5)
    # potions
    p.add("purple", "#7a4594"); p.add("purple_dk", "#55306a")
    p.add("amber", "#e2a743"); p.add("amber_dk", "#b9802e")
    p.add("violet", "#6a3f8f"); p.add("violet_dk", "#45285e")
    p.add("glass", "#dcdbe4"); p.add("glass2", "#b9b5c0"); p.add("glass_hi", "#f6f5fa")
    p.add("cork", "#d9a65e"); p.add("cork_dk", "#b07f40")
    # planter stone, soil, leaves, flowers
    p.add("pst0", "#d2c6b6"); p.add("pst1", "#c7baa9"); p.add("pst2", "#dcd1c2")
    p.add("pjoint", "#8a8078"); p.add("pspot", "#b3a798"); p.add("soil", "#2b2a1f")
    p.add("leaf0", "#406c2b"); p.add("leaf1", "#2f5024"); p.add("leaf2", "#1d3717")
    p.add("leaf3", "#548b31"); p.add("leaf4", "#6ba13f")
    p.add("wood_in", "#4a3326")
    p.add("petal", "#7656b8"); p.add("petal_dk", "#5a3f96")
    p.add("petal_pale", "#aab4e6"); p.add("petal_pale2", "#c9cff0"); p.add("fl_center", "#f0eef5")


# ---------------------------------------------------------------- helpers

def _hash(a, b, salt):
    h = (a.astype(np.uint64) * np.uint64(73856093)) ^ (b.astype(np.uint64) * np.uint64(19349663)) \
        ^ np.uint64(salt * 83492791 + 1)
    return (h * np.uint64(2654435761)) % np.uint64(2 ** 32)


def lay_stones(m: Model, x0, x1, y0, y1, h, colors, lmin, lmax, *, dh=(0,), joint="sjoint"):
    """A row of stones along x (x0..x1, depth y0..y1, from the ground): random lengths
    lmin..lmax, colours and height offsets dh, a joint line where each stone starts."""
    x = x0
    while x < x1:
        ln = int(m.rng.integers(lmin, lmax + 1))
        if x1 - (x + ln) < lmin:          # no sliver at the end
            ln = x1 - x
        hh = h + int(m.rng.choice(dh))
        m.box(x, y0, 0, ln, y1 - y0, hh, str(m.rng.choice(colors)))
        if x > x0:
            m.box(x, y0, 0, 1, y1 - y0, hh, joint)
        x += ln


def paving(m: Model, x0, y0, z0, w, d, h, colors, joint, cw=6, cd=4, salt=0):
    """Recolours a filled box as setts seen from above: cw x cd cells, every other
    row shifted half a cell, one colour per cell, joint lines between cells."""
    idx = np.array([m.pal.idx(c) for c in colors], np.uint8)
    ij = np.uint8(m.pal.idx(joint))

    def fn(X, Y, Z):
        row = (Y - y0) // cd
        off = (row % 2) * (cw // 2)
        col = (X - x0 + off) // cw
        pick = idx[(_hash(col, row, salt) % np.uint64(len(idx))).astype(int)]
        jnt = ((X - x0 + off) % cw == 0) | ((Y - y0) % cd == 0)
        return np.where(jnt, ij, pick)
    m.paint_fn(x0, y0, z0, w, d, h, fn)


def potion(m: Model, cx, cy, z0, r, hb, neck, cork, liquid, liquid_dk, fill=0.68):
    """Corked flask standing at (cx, cy, z0): squat round body (a superellipsoid, so the
    shoulders stay wide) of radius r and height hb, liquid up to `fill` of it (darker on
    the far side), clear glass above with a highlight on the near-left, 3x3 neck, flared
    lip and a cork block."""
    zc, rz = z0 + 0.42 * hb, 0.58 * hb

    def body(X, Y, Z):
        rho = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / r
        return rho ** 3 + np.abs((Z - zc) / rz) ** 3 <= 1.0
    R = int(np.ceil(r)) + 1
    bx, by, bw = int(cx) - R, int(cy) - R, 2 * R + 2
    zl = int(round(fill * hb))
    m.where(bx, by, z0, bw, bw, hb, body, "glass")
    m.where(bx, by, z0, bw, bw, zl, body, liquid)
    m.where(bx, by, z0, bw, bw, zl, lambda X, Y, Z: body(X, Y, Z) & (X - cx + (cy - Y) > r * 0.5), liquid_dk)
    m.where(bx, by, z0 + zl, bw, bw, hb - zl,
            lambda X, Y, Z: body(X, Y, Z) & (X - cx < -r * 0.45) & (Y - cy < 0), "glass_hi")
    top = z0 + hb
    m.cylinder(cx, cy, top - 1, 1.2, neck + 1, "glass")
    m.cylinder(cx, cy, top + neck, 1.8, 1, "glass2")
    m.box(int(cx) - 1, int(cy) - 1, top + neck + 1, 3, 3, cork, "cork")
    m.box(int(cx) - 1, int(cy) - 1, top + neck + 1, 3, 3, 1, "cork_dk")


def top_z(m: Model, x, y) -> int:
    """Height of the first empty voxel above the highest filled one in column (x, y)."""
    zs = np.nonzero(m.v[x, y])[0]
    return int(zs.max()) + 1 if len(zs) else 0


def flower(m: Model, x, y, pale=False):
    """Flower resting on the foliage at (x, y): 2x2 light centre standing one voxel
    proud, four 3-long petals around it, darker voxels in the gaps between petals."""
    z = max(top_z(m, x + i, y + j) for i in range(-2, 4) for j in range(-2, 4)) - 1
    petal, tip = ("petal_pale", "petal_pale2") if pale else ("petal", "petal_dk")
    m.box(x - 3, y, z, 3, 2, 1, petal); m.box(x + 2, y, z, 3, 2, 1, petal)
    m.box(x, y - 3, z, 2, 3, 1, petal); m.box(x, y + 2, z, 2, 3, 1, petal)
    for dx, dy in ((-1, -1), (2, -1), (-1, 2), (2, 2)):
        m.set(x + dx, y + dy, z, tip)
    m.box(x, y, z - 1, 2, 2, 3, "fl_center")


# ---------------------------------------------------------------- pieces

def drain_piece(m: Model):
    x0, y0, L = DR_X, DR_Y, DR_L
    yc = y0 + FC_D                    # channel
    yb = yc + CH_D                    # back curb
    ye = yb + BC_D
    m.box(x0, yc, 0, L, CH_D, CH_H, "cob0")
    paving(m, x0, yc, 0, L, CH_D, CH_H, COBBLES, "cjoint", cw=6, cd=4, salt=1)
    lay_stones(m, x0, x0 + L, y0, yc, FC_H, STONES, 8, 16, dh=(0, 0, -1))
    half = yb + BC_D // 2
    lay_stones(m, x0, x0 + L, yb, half, BC_H, STONES, 10, 18, dh=(0, 0, 1))
    lay_stones(m, x0, x0 + L, half, ye, BC_H, STONES, 9, 16, dh=(0, -1, 0))
    m.box(x0, yb, BC_H, 12, ye - yb, 1, "stone2")       # raised stones at the back-left end
    m.box(x0, yb, BC_H, 12, 1, 1, "stone3")
    m.sprinkle(["spot0", "spot1"], 0.16, target=STONES, region=(x0, y0, 0, L, ye - y0, BC_H + 2))
    # the back curb's face along the channel is in shadow in the reference
    m.box(x0, yb, CH_H, L, 1, BC_H - CH_H - 1, "chwall", only_filled=True)

    # iron grate set into the channel floor: frame, bars along the channel with 2-wide
    # slots between them; the bars sit on a sooty lower course so the slots read dark
    gx, gy, gw, gd = x0 + GRATE_X, yc + GRATE_Y, GRATE_W, GRATE_D
    zt = CH_H - 1
    m.box(gx, gy, zt - 2, gw, gd, 3, "hole")
    m.box(gx, gy, zt, gw, gd, 1, "iron_dk")
    m.carve(gx + 1, gy + 1, zt - 1, gw - 2, gd - 2, 2)
    for y in range(gy + 3, gy + gd - 2, 3):
        m.box(gx + 1, y, zt, gw - 2, 1, 1, "iron")
        m.box(gx + 1, y, zt - 1, gw - 2, 1, 1, "hole")


def crate_piece(m: Model):
    x0, y0, W, D, H = CR_X, CR_Y, CR_W, CR_D, CR_H
    z0 = 1                                       # the posts are the feet
    m.shell(x0, y0, z0, W, D, H, "wood0", t=WALL_T, top=False)
    m.box(x0 + WALL_T, y0 + WALL_T, z0, W - 2 * WALL_T, D - 2 * WALL_T, FLOOR_Z - z0, "inner")
    sides = ((x0, y0, W, WALL_T), (x0, y0 + D - WALL_T, W, WALL_T),
             (x0, y0, WALL_T, D), (x0 + W - WALL_T, y0, WALL_T, D))
    n = H // BOARD                               # the top board takes the remainder
    for k in range(n):
        for sx, sy, sw, sd in sides:
            hb = BOARD if k < n - 1 else H - k * BOARD
            m.box(sx, sy, z0 + k * BOARD, sw, sd, hb, str(m.rng.choice(WOODS)), only_filled=True)
    m.sprinkle(["grain"], 0.1, target=WOODS, region=(x0, y0, z0, W, D, H))
    # the inside of the walls is in shadow
    t = WALL_T - 1
    for sx, sy, sw, sd in ((x0, y0 + t, W, 1), (x0, y0 + D - 1 - t, W, 1),
                           (x0 + t, y0, 1, D), (x0 + W - 1 - t, y0, 1, D)):
        m.box(sx, sy, FLOOR_Z, sw, sd, z0 + H - 1 - FLOOR_Z, "wood_in", only_filled=True)
    # dark gaps between the boards (not recessed: from above a groove shows the lit
    # top of the board below instead of a dark line)
    for k in range(1, H // BOARD):
        for sx, sy, sw, sd in sides:
            m.box(sx, sy, z0 + k * BOARD, sw, sd, 1, "gap", only_filled=True)
    for sx, sy, sw, sd in sides:                 # lighter top edge
        m.box(sx, sy, z0 + H - 1, sw, sd, 1, "wood_lt", only_filled=True)
    # handle slots in both ends
    for sx in (x0, x0 + W - WALL_T):
        m.carve(sx, y0 + D // 2 - 3, z0 + H - 5, WALL_T, 6, 2)
    # corner posts (1 proud of both faces, reaching the ground) with bolts
    for px in (x0 - 1, x0 + W - 2):
        for py in (y0 - 1, y0 + D - 2):
            m.box(px, py, 0, 3, 3, z0 + H + 1, "post")
            for bz in (3, z0 + H - 2):
                m.set(px + 1, py, bz, "bolt")
                m.set(px + 2, py + 1, bz, "bolt")
                m.set(px, py + 1, bz, "bolt")
                m.set(px + 1, py + 2, bz, "bolt")

    # potions
    potion(m, 108, 59, FLOOR_Z, 6, 18, 2, 4, "purple", "purple_dk", fill=0.78)
    potion(m, 123, 61, FLOOR_Z, 4.5, 16, 2, 3, "amber", "amber_dk", fill=0.85)
    potion(m, 117, 55, FLOOR_Z, 3.5, 11, 1, 2, "violet", "violet_dk", fill=0.72)


def planter_piece(m: Model):
    x0, y0, W, D, H, T = PL_X, PL_Y, PL_W, PL_D, PL_H, PL_T
    m.box(x0, y0, 0, W, D, H, "pst0")
    m.bricks(PSTONES, target="pst0", bw=12, bh=COURSE, mortar="pjoint", p=[0.45, 0.3, 0.25],
             region=(x0, y0, 0, W, D, H), salt=3)
    m.box(x0, y0, 0, W, D, 1, "pst1", only_filled=True)
    m.v[x0:x0 + W, y0:y0 + D, COURSE * COURSES:H] = m.v[x0:x0 + W, y0:y0 + D, COURSE * COURSES - 1:COURSE * COURSES]
    # recess the joints on the four outer faces
    jn = m.pal.idx("pjoint")
    for face in (m.v[x0:x0 + W, y0, 1:H], m.v[x0:x0 + W, y0 + D - 1, 1:H],
                 m.v[x0, y0:y0 + D, 1:H], m.v[x0 + W - 1, y0:y0 + D, 1:H]):
        face[face == jn] = 0
    m.sprinkle(["pspot", "pst2"], 0.1, target=PSTONES, region=(x0, y0, 0, W, D, H))
    m.carve(x0 + T, y0 + T, 2, W - 2 * T, D - 2 * T, H)
    m.box(x0 + T, y0 + T, 2, W - 2 * T, D - 2 * T, H - 3, "soil")

    # low foliage mound inside the rim (it barely rises above the back edge), spilling
    # over the front rim only where the vines hang, and over the back half of the right end
    for x in range(x0 + 5, x0 + W - 4, 5):
        m.blob(x + m.rng.uniform(-1, 1), y0 + T + 4, H - 1, 4.5, 5.5, 3.5, LEAVES, p=LEAF_P, noise=0.5,
               density=0.85)
        m.blob(x + m.rng.uniform(-1, 1), y0 + D - T - 4, H - 1, 4.5, 5.5, 3.0, LEAVES, p=LEAF_P, noise=0.5,
               density=0.85)
    for xa, xb in ((x0 + 15, x0 + 24), (x0 + 43, x0 + 62)):
        for x in range(xa, xb, 3):
            m.blob(x, y0 + 2, H, 2.6, 2.4, 1.8, LEAVES, p=LEAF_P, noise=0.5, density=0.8)
    for y in range(y0 + 17, y0 + D, 3):
        m.blob(x0 + W - 2, y, H, 2.4, 2.6, 1.8, LEAVES, p=LEAF_P, noise=0.5, density=0.8)

    # vines: two strands left of the middle of the front, a curtain right of it
    # reaching the ground, a few down the back half of the right end
    for x in (x0 + 17, x0 + 21):
        m.vine(x, y0 - 1, H, int(m.rng.integers(8, 15)), LEAVES[:4], wall="-y", drift=0.3, leaf=0.7)
    for x in range(x0 + 44, x0 + 62, 2):
        m.vine(x, y0 - 1, H, int(m.rng.integers(10, H + 1)), LEAVES[:4], wall="-y", drift=0.3, leaf=0.8)
    for y in range(y0 + 17, y0 + D - 1, 3):
        m.vine(x0 + W, y, H, int(m.rng.integers(8, H)), LEAVES[:4], wall="+x", drift=0.3, leaf=0.7)

    for fx, fy, pale in ((11, 23, False), (14, 14, False), (21, 20, True), (22, 8, False),
                         (45, 24, False), (43, 16, False), (38, 19, False), (57, 10, True)):
        flower(m, x0 + fx, y0 + fy, pale)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=7)
    palette(m)
    with m.part("drain"):
        drain_piece(m)
    with m.part("crate"):
        crate_piece(m)
    with m.part("planter"):
        planter_piece(m)
    return m
