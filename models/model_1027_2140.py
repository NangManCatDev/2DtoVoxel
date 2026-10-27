"""건물 키트 — reference/건물_레퍼런스.png

The reference is a modular kit sheet: the player's house (the same building as
reference/플레이어의집_레퍼런스.png, so models/player_house.py is reused as is) and
loose pieces in a row to its right. Every piece is drawn inside m.part(), so the
.vox holds one named object per piece that can be moved on its own in MagicaVoxel.

Layout (x right, y depth with y=0 front, z up):
  house    x 0..93          player_house build, pasted with its left edge at x=0
  wall     x 121..177, y 20..26, h 30   stucco wall: stacked corner piers, 2 windows,
                            raised plaster patches, vines on the right
  roof     floats ROOF_GAP above the wall, front flush with it: 3-high attic slab,
           gable roof (ridge along x), left gable window, front skirt dropped in the middle
  arch     x 206..239, y 40..46, h 40   block arch, voussoir ring with keystone, cap,
                            bushes + blue flowers on top, vines hanging down
  planter  x 197..246, y 0..11          stacked pillar on the left end, bushes, draping vines
  stairs   x 239..276, y 12..26         platform + iron railing, 5 steps down toward +x
  awning   floats above the stairs: shed canopy with scalloped edge, wooden wall
           brackets (long post + brace left, short post right), 2 lit lanterns
"""
import numpy as np

from models import player_house as ph
from models.player_house import FLOWERS, LEAF_P, LEAVES, PLANKS, lantern, stepped_grooves
from voxtool import Model

NAME = "model_1027_2140"
REFERENCE = "reference/건물_레퍼런스.png"
# the sheet's front edges are nearly level, so a bit flatter than the house alone (36)
VIEW = {"azimuth": 30, "elevation": 18}

# wider than one MagicaVoxel object; fine because every piece is its own part
GRID = (280, 68, 82)

# Piece positions: the left-most visible corner of each piece is placed where the
# reference sheet has it (screen u = 0.866x - 0.5y at az 30). The arch stands far
# back so its base shows above the planter, which is at the very front.
# wall piece (windows 9x11 like the house)
WALL_X, WALL_Y = 121, 20
WALL_W, WALL_T, WALL_H = 56, 6, 30
WIN_Z = 11
# roof piece: floats above the wall piece, front flush with it
ROOF_GAP, ROOF_D, SLAB = 4, 30, 3
# stone arch
ARCH_X, ARCH_Y = 206, 40
ARCH_W, ARCH_T, ARCH_H = 33, 6, 40     # about 1.3x the wall piece, as in the sheet
OPEN_R, SPRING = 7.5, 21      # opening half-width; height where the round top starts
# planter (stacked pillar left of PLANT_X)
PLANT_X, PLANT_Y = 204, 1
PLANT_W, PLANT_D, PLANT_H = 42, 9, 9
# stairs piece: platform, flight down toward +x
STAIR_X, STAIR_Y = 239, 12
PLAT_W, PLAT_D, PLAT_H = 17, 14, 18
STEP_RISE, STEP_RUN = 3, 4
# awning piece: floats above the stairs, low edge at the front
AWN_X, AWN_Y, AWN_Z = STAIR_X - 3, STAIR_Y + 1, 38
AWN_W, AWN_D, AWN_SLOPE = 34, 14, 0.6

STUCCO = ["stucco", "stucco2", "stucco3"]
BLOCKS = ["block", "block2", "block3"]
SHADE_P = [0.5, 0.3, 0.2]


def palette(m: Model):
    ph.palette(m)   # first, so the indices match the house build that gets pasted in
    p = m.pal
    # the loose pieces are lit brighter than the shaded house front (front sample / 0.9)
    p.add("stucco", "#f0d8b8"); p.add("stucco2", "#e7cfae"); p.add("stucco3", "#f6e4c8")
    p.add("block", "#eed8b9"); p.add("block2", "#e2cba9"); p.add("block3", "#d6bd9a")
    p.add("joint", "#a48d6c")
    p.add("wood", "#4f2a1a"); p.add("wood_dk", "#331a10")


# ---------------------------------------------------------------- helpers

def stack(m: Model, x0, x1, y0, y1, h, z0=0):
    """Stacked stone blocks (corner piers, pillars) over x0..x1 / y0..y1: courses 4
    high with a recessed joint between them; every other course reaches one further
    at both x ends so the stack looks interlocked. The top course fills to z0+h."""
    i, z = 0, z0
    while z < z0 + h:
        last = z + 5 >= z0 + h
        hh = z0 + h - z if last else 4
        ext = 1 - i % 2
        m.box(x0 - ext, y0, z, x1 - x0 + 2 * ext, y1 - y0, hh, str(m.rng.choice(BLOCKS[:2])))
        if not last:
            m.box(x0, y0, z + 4, x1 - x0, y1 - y0, 1, "joint", only_filled=True)   # joint on the wall
            m.box(x0 + 1, y0 + 1, z + 4, x1 - x0 - 2, y1 - y0 - 2, 1, "joint")
        i, z = i + 1, z + 5


def patches(m: Model, y, x0, x1, z0, z1, n):
    """Raised plaster patches with stair-stepped tops, one voxel proud of a front
    wall whose face is at y (the chipped-stucco look of the reference)."""
    for _ in range(n):
        w = int(m.rng.integers(4, 10))
        h = int(m.rng.integers(2, 5))
        x = int(m.rng.integers(x0, max(x0 + 1, x1 - w)))
        z = int(m.rng.integers(z0, max(z0 + 1, z1 - h)))
        c = str(m.rng.choice(["stucco3", "stucco"]))
        while w > 1 and z < z1:
            m.box(x, y - 1, z, w, 1, min(h, z1 - z), c)
            s = int(m.rng.integers(1, 3))
            x, w = x + s, w - s - int(m.rng.integers(1, 3))
            z, h = z + h, int(m.rng.integers(1, 3))


def window(m: Model, x, y, z, w=9, h=11):
    """Front window in a wall whose face is at y: dark frame, 2x2 panes recessed 2,
    light stone surround, sill and lintel (same style as the house)."""
    m.carve(x - 2, y - 1, z - 3, w + 4, 1, h + 5)             # no plaster patch over it
    m.box(x - 1, y - 1, z - 1, w + 2, 1, h + 2, "stucco3")    # surround
    m.box(x, y - 1, z, w, 2, h, "win_frame")
    m.carve(x + 1, y - 1, z + 1, w - 2, 2, h - 2)
    m.box(x + 1, y + 1, z + 1, w - 2, 1, h - 2, "glass")
    m.box(x + w // 2, y, z + 1, 1, 1, h - 2, "win_frame")      # mullion
    m.box(x + 1, y, z + h // 2, w - 2, 1, 1, "win_frame")      # transom
    m.box(x - 2, y - 2, z - 2, w + 4, 2, 1, "stucco3")         # sill
    m.box(x - 1, y - 2, z + h, w + 2, 1, 1, "stucco3")         # lintel


# ---------------------------------------------------------------- pieces

def house_piece(m: Model) -> int:
    """Pastes the player_house build with its left edge at x=0; returns its width."""
    house = ph.build()
    assert all(m.pal.names[n] == i for n, i in house.pal.names.items()), "palette mismatch"
    xs = np.nonzero(house.v.any(axis=(1, 2)))[0]
    src = house.v[xs.min():xs.max() + 1]
    dst = m.v[:src.shape[0], :src.shape[1], :src.shape[2]]
    np.copyto(dst, src, where=src > 0)
    return src.shape[0]


def wall_piece(m: Model):
    x0, y0, W, T, H = WALL_X, WALL_Y, WALL_W, WALL_T, WALL_H
    m.box(x0, y0, 0, W, T, H, "stucco")
    m.bricks(STUCCO, target="stucco", bw=7, bh=4, p=[0.6, 0.25, 0.15], region=(x0, y0, 0, W, T, H))
    patches(m, y0, x0 + 7, x0 + W - 7, 1, H, 24)
    for wx in (x0 + 13, x0 + 30):
        window(m, wx, y0, WIN_Z)
    stack(m, x0 - 1, x0 + 6, y0 - 1, y0 + T + 1, H)            # corner piers
    stack(m, x0 + W - 6, x0 + W + 1, y0 - 1, y0 + T + 1, H)
    m.box(x0 + 6, y0 - 1, 0, W - 12, 1, 1, "block3")            # plinth
    for vx, ln in ((x0 + 45, 24), (x0 + 48, 18)):
        m.vine(vx, y0 - 1, H - 1, ln, LEAVES[:3], wall="-y", drift=0.3, leaf=0.95, spread=2)


def roof_piece(m: Model):
    x0, y0, W, D = WALL_X, WALL_Y, WALL_W, ROOF_D
    z0 = WALL_H + ROOF_GAP
    zr = z0 + SLAB
    fp = (x0 - 2, y0 - 2, W + 4, D + 4)                         # 2 overhang all round
    m.box(x0, y0, z0, W, D, SLAB, "stucco")
    m.gable_wall(fp[0], fp[1], zr, fp[2], fp[3], "x", "stucco", region=(x0, y0, W, D))
    m.bricks(STUCCO, target="stucco", bw=7, bh=4, p=SHADE_P, region=(x0, y0, z0, W, D, 40))
    m.gable_roof(*fp[:2], zr, *fp[2:], "x", PLANKS, t=2)
    # front skirt dropped 4 courses in the middle (like the house over its door)
    sx0, sw = x0 + 18, 24
    for k in range(1, 5):
        m.box(sx0, fp[1] - k, zr - k, sw, 1, 2, PLANKS[(-k) % len(PLANKS)])
    # small attic window in the left gable, under the ridge
    gy = y0 + D // 2 - 2
    m.carve(x0, gy, zr + 6, 1, 4, 6)
    m.box(x0 + 1, gy, zr + 6, 1, 4, 6, "win_dark")
    m.box(x0 - 1, gy - 1, zr + 5, 1, 6, 1, "stucco3")


def arch_piece(m: Model):
    x0, y0, W, T, H = ARCH_X, ARCH_Y, ARCH_W, ARCH_T, ARCH_H
    cx = x0 + W // 2
    cap = H - 3
    m.box(x0, y0, 0, W, T, cap, "block")
    m.bricks(BLOCKS, target="block", bw=9, bh=5, mortar="joint", p=SHADE_P, region=(x0, y0, 0, W, T, cap))
    m.box(x0 - 1, y0 - 1, cap, W + 2, T + 2, H - cap, "block2")  # cap course, 1 proud
    m.box(x0 - 1, y0 - 1, cap, W + 2, T + 2, 1, "joint", only_filled=True)
    stack(m, x0 - 1, x0 + 6, y0 - 1, y0 + T + 1, cap - 1)       # corner piers
    stack(m, x0 + W - 6, x0 + W + 1, y0 - 1, y0 + T + 1, cap - 1)

    # voussoir ring, 1 proud, alternating stones, light keystone at the top
    def ring(X, Z):
        rr = (X - cx) ** 2 + (Z - SPRING) ** 2
        return (rr > OPEN_R ** 2) & (rr <= (OPEN_R + 3) ** 2) & (Z >= SPRING)
    m.where(x0, y0 - 1, SPRING, W, 1, cap - SPRING, lambda X, Y, Z: ring(X, Z), "block")
    ia, ib, ik = (m.pal.idx(c) for c in ("block", "block3", "stucco3"))

    def colour(X, Y, Z):
        k = np.floor(np.arctan2(Z - SPRING, X - cx) / (np.pi / 9)).astype(int)
        c = np.where(k == 4, ik, np.where(k % 2 == 0, ia, ib))
        return np.where(ring(X, Z), c, 0)
    m.paint_fn(x0, y0 - 1, SPRING, W, T + 1, cap - SPRING, colour)

    # opening: straight jambs up to SPRING, round top
    m.where(x0, y0 - 1, 0, W, T + 2, cap,
            lambda X, Y, Z: ((np.abs(X - cx) <= OPEN_R - 0.5) & (Z < SPRING))
            | ((X - cx) ** 2 + (Z - SPRING) ** 2 <= OPEN_R ** 2), None)

    # greenery on top, vines hanging down the front and the right end
    for x in range(x0 + 1, x0 + W + 1, 4):
        m.blob(x, y0 + (T - 1) / 2, H + 1, 3.2, T / 2 + 1.2, 2.4, LEAVES, p=LEAF_P, noise=0.5, density=0.85)
    m.sprinkle(FLOWERS, 0.12, target=LEAVES, region=(x0 - 4, y0 - 4, H - 1, W + 8, T + 8, 8))
    for vx, ln in ((cx - 8, 16), (cx - 4, 7), (cx + 7, 25), (cx + 10, 14)):
        m.vine(vx, y0 - 2, H - 1, ln, LEAVES[:3], wall="-y", drift=0.3, leaf=0.9, spread=1)
    m.vine(x0 + W + 1, y0 + 2, H - 1, 20, LEAVES[:3], wall="+x", drift=0.3, leaf=0.8)


def planter_piece(m: Model):
    x0, y0, W, D, H = PLANT_X, PLANT_Y, PLANT_W, PLANT_D, PLANT_H
    m.box(x0, y0, 0, W, D, H, "block")
    m.bricks(BLOCKS, target="block", bw=8, bh=4, p=SHADE_P, region=(x0, y0, 0, W, D, H))
    m.carve(x0 + 2, y0 + 2, 2, W - 4, D - 4, H)
    m.box(x0 + 2, y0 + 2, 2, W - 4, D - 4, H - 3, "soil")
    m.box(x0, y0, H - 1, W, D, 1, "stucco3", only_filled=True)   # coping
    stepped_grooves(m, "y", y0, x0 + 2, x0 + W - 6, 2, amp=2)
    stack(m, x0 - 6, x0, y0 - 1, y0 + D + 1, H + 5)               # pillar on the left end
    m.box(x0 + W - 4, y0, 0, 4, D, H + 4, "block2")               # post on the right end
    m.box(x0 + W - 5, y0 - 1, H + 3, 6, D + 2, 1, "stucco3")

    cy = y0 + (D - 1) / 2
    for x in range(x0 + 6, x0 + W - 4, 5):
        m.blob(x, cy, H + 2, 4.6, D / 2 + 0.8, 4.0, LEAVES, p=LEAF_P, noise=0.45, density=0.9)
    m.sprinkle(FLOWERS, 0.17, target=LEAVES, region=(x0 - 2, y0 - 3, 0, W + 4, D + 6, H + 10))
    for x in range(x0 + 5, x0 + W - 4, 4):
        m.vine(x, y0 - 1, H, int(m.rng.integers(5, 10)), LEAVES[1:], wall="-y", drift=0.4, leaf=0.7)


def stair_piece(m: Model):
    x0, y0, W, D, H = STAIR_X, STAIR_Y, PLAT_W, PLAT_D, PLAT_H
    m.box(x0, y0, 0, W, D, H, "block")
    m.bricks(BLOCKS, target="block", bw=8, bh=4, p=SHADE_P, region=(x0, y0, 0, W, D, H))
    patches(m, y0, x0 + 1, x0 + W - 1, 1, H - 2, 4)
    m.box(x0, y0, H - 1, W, D, 1, "stucco3")                       # top slab
    steps = H // STEP_RISE - 1
    m.stairs(x0 + W, y0 + 1, 0, D - 1, steps, "block2", rise=STEP_RISE, run=STEP_RUN, direction="+x")
    m.bricks(BLOCKS, target="block2", bw=2 * STEP_RUN, bh=STEP_RISE, mortar="joint", p=SHADE_P,
             region=(x0 + W, y0, 0, steps * STEP_RUN, D, H))       # one course per step
    for i in range(steps):                                         # lighter tread nosing
        m.box(x0 + W + i * STEP_RUN, y0 + 1, (steps - i) * STEP_RISE - 1, STEP_RUN, D - 1, 1, "stucco3")
    # iron railing along the front edge of the platform
    rx0, rx1, ry = x0 + 1, x0 + W - 2, y0 + 1
    m.box(rx0, ry, H + 5, rx1 - rx0, 1, 2, "iron")                 # top rail
    m.box(rx0, ry, H, rx1 - rx0, 1, 1, "iron2")                    # bottom rail
    for x in range(rx0 + 3, rx1 - 2, 2):
        m.box(x, ry, H, 1, 1, 5, "iron")                           # balusters
    for x in (rx0, rx1 - 2):
        m.box(x, ry, H, 2, 2, 7, "iron")                           # end posts


def awning_piece(m: Model):
    x0, y0, z0, W, D = AWN_X, AWN_Y, AWN_Z, AWN_W, AWN_D
    m.shed_roof(x0, y0, z0, W, D, "-y", PLANKS, slope=AWN_SLOPE, t=2)
    for x in range(x0, x0 + W):                                    # scalloped front edge
        k = (x - x0) % 5
        if k <= 2:
            m.set(x, y0, z0 - 1, "roof")
        if k == 1:
            m.set(x, y0, z0 - 2, "roof_dk")

    def under(y):   # first empty z under the roof skin at depth y
        return z0 + int(np.floor((y - y0) * AWN_SLOPE)) - 1

    back = y0 + D - 2
    m.box(x0, y0 + D - 1, under(y0 + D - 1) - 1, W, 1, 2, "wood_dk")   # ledger at the back
    for bx in (x0, x0 + W - 2):                                    # rafters under both side edges
        for y in range(y0 + 1, y0 + D):
            m.box(bx, y, under(y), 2, 1, 1, "wood")
    # left bracket: long post down the wall with a diagonal brace
    m.box(x0, back, z0 - 12, 2, 2, under(back) - (z0 - 12) + 1, "wood")
    m.line((x0, back - 1, z0 - 7), (x0, y0 + 5, under(y0 + 5)), "wood")
    m.line((x0 + 1, back - 1, z0 - 7), (x0 + 1, y0 + 5, under(y0 + 5)), "wood")
    # right bracket: short post
    m.box(x0 + W - 2, back, z0 - 2, 2, 2, under(back) - (z0 - 2) + 1, "wood")

    # lanterns: one under the front-left, one on an iron arm past the right edge
    lx, ly = x0 + 6, y0 + 3
    top = lantern(m, lx, ly, z0 - 10)
    m.box(lx, ly, top, 1, 1, under(ly) - top + 1, "iron")
    rx, ry = x0 + W + 2, y0 + 3
    m.box(x0 + W - 2, ry, under(ry), rx - (x0 + W - 2) + 1, 1, 1, "iron")
    top = lantern(m, rx, ry, z0 - 8)
    m.box(rx, ry, top, 1, 1, under(ry) - top, "iron")


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=11)
    palette(m)
    with m.part("house"):
        house_piece(m)
    with m.part("wall"):
        wall_piece(m)
    with m.part("roof"):
        roof_piece(m)
    with m.part("arch"):
        arch_piece(m)
    with m.part("planter"):
        planter_piece(m)
    with m.part("stairs"):
        stair_piece(m)
    with m.part("awning"):
        awning_piece(m)
    return m
