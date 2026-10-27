"""플레이어의 집 (auto) — reference/플레이어의집_레퍼런스.png

Cream stone cottage seen from the front-left. Grid kept under 110 on every axis.

Layout (x right, y depth with y=0 front, z up):
  main body     x HX0..HX1 (72), y HY0..HY1 (52), walls up to EAVE, floor raised to FLOOR
  main roof     gable with the ridge along x, teal planks; the ridge sits forward of centre
                (front pitch ~0.95, back ~0.68); overhangs the left gable, stops at a thick
                crow-stepped stone parapet on the right gable
  roof skirt    over the door section the main roof runs further down in front of the wall
  porch awning  lean-to over the whole front, just under the eave beam, scalloped edge
  front         red double door with glass panes, porch landing + 3 steps, iron railing,
                two 2x2 windows, lit lanterns left of the door and past the right corner
  left side     small gable window, quoins, big unlit lantern on a bracket, climbing vines
  planters      along the left wall and in front of the windows, bushes with blue flowers,
                vines hanging over the edges
"""
import math

from voxtool import Model

NAME = "player_house_auto"
REFERENCE = "reference/플레이어의집_레퍼런스.png"
VIEW = {"azimuth": 30, "elevation": 14}

HX0, W = 16, 72          # main body x range [HX0, HX1)
HX1 = HX0 + W
HY0, D = 20, 52          # main body y range [HY0, HY1)
HY1 = HY0 + D
FLOOR = 10               # porch landing / ground floor level
EAVE = FLOOR + 38        # first z above the walls
RISE = 19                # eave -> ridge
RIDGE_F = 22             # ridge distance from the front roof edge; the ridge sits forward
                         # (reference: the front rake of the left gable is shorter than the back)
OVH = 2                  # roof overhang at the front eave and the left gable (none at the back)
WALL_T = 3
PARAPET_T = 5            # crow-stepped right gable; the roof stops at its inner face
DOOR_X, DOOR_W, DOOR_H = HX0 + 13, 14, 20
DOOR_TOP = FLOOR + DOOR_H
SKIRT_X1 = HX0 + 30      # the roof skirt (lower main roof) covers x < SKIRT_X1
SKIRT_D = 8              # how far the skirt runs past the eave
AW_D = 15                # porch awning depth in front of the wall
AW_SLOPE = 0.9
AW_TOP = EAVE - 4        # awning height where it meets the wall
LAND_D = 10              # porch landing depth
STEP_RUN, STEPS = 3, 3
WIN_Z = DOOR_TOP - 13    # window bottom (tops stay just clear of the awning edge in VIEW)

GRID = (HX1 + 8, HY1 + 3, 74)


def palette(m: Model):
    # base colours ~ reference samples / face shading (front x0.9, left x0.76)
    p = m.pal
    p.add("wall", "#d2b793"); p.add("wall2", "#c8ac88"); p.add("wall3", "#dbc29f")
    # the reference's left wall reads lighter/warmer than its front (lantern glow)
    p.add("lwall", "#f0d2ab"); p.add("lwall2", "#e5c69f"); p.add("lwall3", "#f5dbb8")
    p.add("trim", "#f3e4cc")
    p.add("quoin", "#e0cdb0"); p.add("quoin2", "#d3bea0"); p.add("mortar", "#8a7559")
    p.add("stone", "#efd9bc"); p.add("stone2", "#e4cdb0"); p.add("groove", "#a99376")
    p.add("roof", "#04848e"); p.add("roof_hi", "#0b9aa4"); p.add("roof_dk", "#02737d")
    p.add("iron", "#221e1b"); p.add("iron2", "#2f2a26")
    p.add("door", "#77231d"); p.add("door_dk", "#4f1712"); p.add("door_frame", "#3a1c15")
    p.add("glass", "#8d8396"); p.add("win_frame", "#2b2423"); p.add("win_dark", "#2a2220")
    p.add("lamp", "#ffd04a", emit=4.0); p.add("lamp_off", "#3a2e26")
    p.add("soil", "#3b2a1c")
    p.add("leaf0", "#16300d"); p.add("leaf1", "#22461a"); p.add("leaf2", "#30601e"); p.add("leaf3", "#4a7a2c")
    p.add("flower0", "#3e6be0"); p.add("flower1", "#6d92f6"); p.add("flower2", "#5a4fd0")


LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3"]
LEAF_P = [0.25, 0.35, 0.28, 0.12]
FLOWERS = ["flower0", "flower1", "flower2"]
PLANKS = ["roof_hi", "roof", "roof_dk"]

# main roof footprint: overhangs left/front, stops at the parapet on the right
RX0, RY0 = HX0 - OVH, HY0 - OVH
RW, RD = (HX1 - PARAPET_T) - RX0, D + OVH
RIDGE_Y = RY0 + RIDGE_F
FRONT_SLOPE = RISE / RIDGE_F
BACK_SLOPE = RISE / (RY0 + RD - 1 - RIDGE_Y)


def roof_course(y: int) -> int:
    """Course number (0 at the eave) of the main roof at row y; negative in front of the eave."""
    return y - RY0 if y <= RIDGE_Y else RY0 + RD - 1 - y


def roof_z(y: int) -> int:
    """Underside of the main roof skin at row y (continues the front pitch past the eave)."""
    slope = FRONT_SLOPE if y <= RIDGE_Y else BACK_SLOPE
    return EAVE + math.floor(roof_course(y) * slope)


# ---------------------------------------------------------------- helpers

def quoins(m: Model, cx: int, cy: int, sx: int, sy: int, z1: int = EAVE):
    """Corner stones at wall corner (cx, cy), protruding 1 toward (sx, sy);
    rows alternate long/short on each face, with a recessed joint between rows."""
    for i, z in enumerate(range(0, z1 - 3, 5)):
        lx, ly = (6, 3) if i % 2 == 0 else (3, 6)
        col = "quoin" if i % 2 == 0 else "quoin2"
        x0 = cx - lx + 1 if sx > 0 else cx
        m.box(x0, cy + sy, z, lx, 1, 4, col)                     # on the y-facing wall
        y0 = cy - ly + 1 if sy > 0 else cy
        m.box(cx + sx, y0, z, 1, ly, 4, col)                     # on the x-facing wall
        m.box(cx + sx, cy + sy, z, 1, 1, 4, col)                 # corner column
        m.box(x0, cy, z + 4, lx, 1, 1, "mortar", only_filled=True)
        m.box(cx, y0, z + 4, 1, ly, 1, "mortar", only_filled=True)


def window(m: Model, x: int, z: int, w: int = 9, h: int = 10, back: bool = False):
    """Dark frame, 2x2 lavender panes recessed, stone sill + lintel. Front (y=HY0) or back wall."""
    y_out, inward = (HY1 - 1, -1) if back else (HY0, 1)

    def slab(x0, z0, ww, hh, depth, c):          # depth 0 = outer wall layer, -1 = in front
        y = y_out + inward * depth
        m.box(x0, y, z0, ww, 1, hh, c)

    for d in range(2):
        slab(x, z, w, h, d, "win_frame")
        slab(x + 1, z + 1, w - 2, h - 2, d, None)
    slab(x + 1, z + 1, w - 2, h - 2, 2, "glass")
    slab(x + w // 2, z + 1, 1, h - 2, 1, "win_frame")           # mullion
    slab(x + 1, z + h // 2, w - 2, 1, 1, "win_frame")           # transom
    slab(x - 1, z - 1, w + 2, 1, -1, "trim")                    # sill
    slab(x, z - 2, w, 1, -1, "trim")
    slab(x - 1, z + h, w + 2, 1, -1, "trim")                    # lintel


def lantern(m: Model, cx: int, cy: int, z0: int, *, glass_h: int = 4, r: int = 2, lit: bool = True) -> int:
    """Iron lantern (2r+1 wide) standing on z0; returns the z of its top hook."""
    g = "lamp" if lit else "lamp_off"
    s = 2 * r + 1
    m.box(cx - r + 1, cy - r + 1, z0, s - 2, s - 2, 1, "iron")
    m.box(cx - r, cy - r, z0 + 1, s, s, 1, "iron")
    m.box(cx - r, cy - r, z0 + 2, s, s, glass_h, g)
    for dx in (-r, r):
        for dy in (-r, r):
            m.box(cx + dx, cy + dy, z0 + 2, 1, 1, glass_h, "iron")
    if not lit:   # an unlit lantern reads as a dark body with a cross on each face
        m.box(cx - r, cy, z0 + 2, s, 1, glass_h, "iron2")
        m.box(cx, cy - r, z0 + 2, 1, s, glass_h, "iron2")
        m.box(cx - r, cy - r, z0 + 2 + glass_h // 2, s, s, 1, "iron2")
    zt = z0 + 2 + glass_h
    m.box(cx - r, cy - r, zt, s, s, 1, "iron")
    m.box(cx - r + 1, cy - r + 1, zt + 1, s - 2, s - 2, 1, "iron")
    m.set(cx, cy, zt + 2, "iron")
    return zt + 2


def planter(m: Model, x, y, w, d, h):
    m.box(x, y, 0, w, d, h, "stone")
    m.carve(x + 2, y + 2, 2, w - 4, d - 4, h)
    m.box(x + 2, y + 2, 2, w - 4, d - 4, h - 3, "soil")
    m.box(x, y, h - 1, w, d, 1, "trim", only_filled=True)        # coping


def zigzag(m: Model, axis: str, fixed: int, a0: int, a1: int, z0: int, amp: int = 2):
    """Stair-stepped relief line on a stone face (axis = direction the face runs along)."""
    for a in range(a0, a1):
        tri = abs(((a - a0) // 2) % (2 * amp) - amp)
        if axis == "x":
            m.box(a, fixed, z0 + tri, 1, 1, 1, "groove", only_filled=True)
        else:
            m.box(fixed, a, z0 + tri, 1, 1, 1, "groove", only_filled=True)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=11)
    palette(m)

    # --- body: walls on a solid base, gable infill under the roof
    m.shell(HX0, HY0, 0, W, D, EAVE, "wall", t=WALL_T, top=False, bottom=False)
    m.box(HX0, HY0, 0, W, D, FLOOR, "wall")
    for y in range(HY0, HY1):                                         # gable infill
        m.box(HX0, y, EAVE, W, 1, roof_z(y) - EAVE, "wall")

    # crow-stepped parapet on the right gable; each step starts level with the roof
    px, step = HX1 - PARAPET_T, 4
    for y in range(RY0, RY0 + RD):
        c = roof_course(y)
        y_step = y - c % step if y <= RIDGE_Y else y + c % step     # eave-side start of the step
        top = roof_z(y_step) + 4
        m.box(px, y, EAVE - 3, PARAPET_T, 1, top - (EAVE - 3), "wall")
        m.box(px, y, top - 1, PARAPET_T + 1, 1, 1, "trim")
    m.box(px + 1, RIDGE_Y - 1, roof_z(RIDGE_Y) + 3, 3, 3, 1, "trim")   # small finial

    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=8, bh=5, p=[0.5, 0.3, 0.2])
    m.bricks(["lwall", "lwall2", "lwall3"], target=["wall", "wall2", "wall3"], bw=8, bh=5,
             p=[0.5, 0.3, 0.2], region=(HX0, HY0, 0, 1, D, GRID[2]))

    # --- main roof, plus the skirt that runs further down over the door section
    for y in range(RY0 - SKIRT_D, RY0 + RD):
        x1 = SKIRT_X1 if y < RY0 else RX0 + RW
        m.box(RX0, y, roof_z(y), x1 - RX0, 1, 2, PLANKS[roof_course(y) % len(PLANKS)])
    m.box(RX0, RIDGE_Y, roof_z(RIDGE_Y) + 2, RW, 1, 1, "roof_hi")     # ridge cap

    # --- cornices, eave beam, plinth
    m.box(HX0 - 1, HY0 - 1, EAVE - 2, 1, D + 2, 2, "trim")          # left eave ledge
    m.box(SKIRT_X1, HY0 - 1, EAVE - 2, HX1 - SKIRT_X1, 1, 2, "trim")  # beam over the awning
    m.box(HX0 - 1, HY0 - 1, 0, W + 2, 1, 1, "stone2")
    m.box(HX0 - 1, HY0, 0, 1, D, 1, "stone2")

    quoins(m, HX0, HY0, -1, -1)
    quoins(m, HX1 - 1, HY0, 1, -1)
    quoins(m, HX0, HY1 - 1, -1, 1)
    quoins(m, HX1 - 1, HY1 - 1, 1, 1)

    # --- hollow interior so the openings have depth
    m.carve(HX0 + WALL_T, HY0 + WALL_T, FLOOR, W - 2 * WALL_T, D - 2 * WALL_T, EAVE - FLOOR)

    # --- porch awning over the whole front, scalloped front edge
    aw_x0, aw_x1 = HX0 - 1, HX1 + 3
    aw_y0 = HY0 - 1 - AW_D
    aw_z = AW_TOP - math.floor((AW_D - 1) * AW_SLOPE)
    m.shed_roof(aw_x0, aw_y0, aw_z, aw_x1 - aw_x0, AW_D, "-y", PLANKS, slope=AW_SLOPE)
    for x in range(aw_x0, aw_x1):
        k = (x - aw_x0) % 5
        if k <= 2:
            m.set(x, aw_y0, aw_z - 1, "roof")
        if k == 1:
            m.set(x, aw_y0, aw_z - 2, "roof_dk")

    # --- front door: red double door, two glass panes per leaf
    m.carve(DOOR_X, HY0, FLOOR, DOOR_W, WALL_T, DOOR_H)
    m.box(DOOR_X - 1, HY0 - 1, FLOOR, 1, 1, DOOR_H + 1, "door_frame")
    m.box(DOOR_X + DOOR_W, HY0 - 1, FLOOR, 1, 1, DOOR_H + 1, "door_frame")
    m.box(DOOR_X - 1, HY0 - 1, FLOOR + DOOR_H, DOOR_W + 2, 1, 1, "door_frame")
    half = DOOR_W // 2
    for lx in (DOOR_X, DOOR_X + half):
        m.box(lx, HY0 + 1, FLOOR, half, 1, DOOR_H, "door")
        for pz in (FLOOR + 9, FLOOR + 15):
            m.carve(lx + 1, HY0 + 1, pz, half - 2, 1, 4)
            m.box(lx + 1, HY0 + 2, pz, half - 2, 1, 4, "glass")
        m.box(lx + 2, HY0 + 1, FLOOR + 2, half - 4, 1, 5, "door_dk")
    m.box(DOOR_X + half - 1, HY0 + 1, FLOOR, 2, 1, DOOR_H, "door_dk")
    m.box(DOOR_X + half - 2, HY0, FLOOR + 9, 1, 1, 3, "iron")
    m.box(DOOR_X + half + 1, HY0, FLOOR + 9, 1, 1, 3, "iron")

    # --- porch landing, steps, railing
    land_y0 = HY0 - LAND_D
    land_x1 = DOOR_X + DOOR_W + 4
    m.box(HX0, land_y0, 0, land_x1 - HX0, LAND_D, FLOOR, "stone")
    m.box(HX0, land_y0, FLOOR - 1, land_x1 - HX0, LAND_D, 1, "trim")
    st_x0, st_x1 = DOOR_X - 3, land_x1
    for i in range(STEPS):
        h = round(FLOOR * (STEPS - i) / (STEPS + 1))
        sy = land_y0 - STEP_RUN * (i + 1)
        m.box(st_x0, sy, 0, st_x1 - st_x0, STEP_RUN, h, "stone2")
        m.box(st_x0, sy, h - 1, st_x1 - st_x0, STEP_RUN, 1, "trim")
    rx = HX0 + 2
    m.box(rx, land_y0 + 1, FLOOR + 6, 1, LAND_D - 2, 1, "iron")       # top rail
    m.box(rx, land_y0 + 1, FLOOR, 1, LAND_D - 2, 1, "iron2")
    for y in range(land_y0 + 1, HY0 - 1, 3):                          # balusters with gaps
        m.box(rx, y, FLOOR, 1, 1, 6, "iron")
    for y in (land_y0 + 1, HY0 - 2):
        m.box(rx, y, FLOOR, 1, 1, 8, "iron")                          # end posts
        m.box(rx - 1, y, FLOOR + 7, 3, 1, 1, "iron2")

    # --- windows
    window(m, HX0 + 36, WIN_Z)
    window(m, HX0 + 49, WIN_Z)
    window(m, HX0 + 14, WIN_Z, back=True)
    window(m, HX0 + 48, WIN_Z, back=True)
    gy = RIDGE_Y - 2                                                  # attic window, left gable
    m.carve(HX0, gy, EAVE + 8, 1, 4, 6)
    m.box(HX0 + 1, gy, EAVE + 8, 1, 4, 6, "win_dark")
    m.box(HX0 - 1, gy - 1, EAVE + 7, 1, 6, 1, "trim")

    # --- lanterns
    # left of the door: scrolled bracket from the front wall, lantern under the awning
    lx, ly, arm_z = HX0 + 5, HY0 - 5, DOOR_TOP + 4
    m.box(lx - 1, HY0 - 1, arm_z - 5, 3, 1, 7, "iron")
    m.box(lx, ly, arm_z, 1, HY0 - 1 - ly, 1, "iron")
    m.line((lx, HY0 - 2, arm_z - 4), (lx, ly + 2, arm_z), "iron")
    top = lantern(m, lx, ly, arm_z - 10)
    m.box(lx, ly, top, 1, 1, arm_z - top, "iron")
    # right end: bracket from the front-right corner, lantern just under the awning's corner
    rlx, rly, rarm_z = HX1 + 1, HY0 - 6, aw_z - 1
    m.box(HX1 - 2, HY0 - 1, rarm_z - 5, 2, 1, 7, "iron")
    m.box(HX1 - 1, rly, rarm_z, 1, HY0 - 1 - rly, 1, "iron")
    m.box(HX1 - 1, rly, rarm_z, rlx - HX1 + 2, 1, 1, "iron")
    m.line((HX1 - 1, HY0 - 2, rarm_z - 4), (HX1 - 1, rly + 3, rarm_z), "iron")
    top = lantern(m, rlx, rly, rarm_z - 10)
    m.box(rlx, rly, top, 1, 1, rarm_z - top, "iron")
    # big unlit lantern on the left wall, near the back
    bx, by, barm_z = HX0 - 14, HY1 - 9, EAVE - 9
    m.box(HX0 - 1, by - 1, barm_z - 8, 1, 3, 10, "iron")
    m.box(bx, by, barm_z, HX0 - 1 - bx, 1, 1, "iron")
    m.box(bx - 1, by, barm_z + 1, 4, 1, 1, "iron")
    m.line((HX0 - 2, by, barm_z - 6), (bx + 4, by, barm_z), "iron")
    top = lantern(m, bx, by, barm_z - 13, glass_h=7, lit=False)
    m.box(bx, by, top, 1, 1, barm_z - top, "iron")

    # --- planters (top a little above the landing)
    ph = FLOOR + 1
    lp_x0, lp_y0, lp_y1 = HX0 - 11, HY0 - 1, HY1 + 1                # along the left wall
    planter(m, lp_x0, lp_y0, HX0 - lp_x0, lp_y1 - lp_y0, ph)
    rp_x0, rp_y0 = land_x1 + 1, HY0 - 17                              # in front of the windows
    rp_x1 = HX1 + 6
    planter(m, rp_x0, rp_y0, rp_x1 - rp_x0, HY0 - 1 - rp_y0, ph)
    zigzag(m, "y", lp_x0, lp_y0 + 2, lp_y1 - 2, 2)
    zigzag(m, "x", rp_y0, rp_x0 + 2, rp_x1 - 2, 2, amp=3)
    zigzag(m, "x", land_y0, HX0 + 1, st_x0 - 1, 1)

    # bushes, rising to about the window sills
    lcx = (lp_x0 + HX0) / 2
    for y in range(lp_y0 + 3, lp_y1 - 1, 5):
        m.blob(lcx, y, ph + 2, 4.6, 3.8, 4.2, LEAVES, p=LEAF_P, noise=0.45, density=0.9)
    rcy = (rp_y0 + HY0 - 1) / 2
    for x in range(rp_x0 + 3, rp_x1 - 3, 5):
        m.blob(x, rcy, ph + 1, 4.6, 6.0, 4.0, LEAVES, p=LEAF_P, noise=0.45, density=0.9)
    m.sprinkle(FLOWERS, 0.14, target=LEAVES, region=(0, lp_y0 - 3, 0, HX0 + 1, lp_y1 - lp_y0 + 6, 30))
    m.sprinkle(FLOWERS, 0.17, target=LEAVES, region=(rp_x0 - 3, rp_y0 - 3, 0, rp_x1 - rp_x0 + 8, HY0 - rp_y0 + 2, 30))

    # vines: climbing the left wall and the front-right section, hanging over the planters
    for y0 in (HY0 + 18, HY0 + 26, HY0 + 33):
        m.vine(HX0 - 1, y0, EAVE - 3, EAVE - ph - 2, LEAVES[:3], wall="-x", drift=0.3, leaf=0.95, spread=2)
    m.vine(HX0 + 64, HY0 - 1, AW_TOP - 2, AW_TOP - ph - 4, LEAVES[:3], wall="-y", drift=0.3, leaf=0.9, spread=2)
    for x in range(rp_x0 + 2, rp_x1 - 1, 5):
        m.vine(x, rp_y0 - 1, ph, int(m.rng.integers(4, 8)), LEAVES[1:], wall="-y", drift=0.4, leaf=0.7)
    for y in range(lp_y0 + 3, lp_y1, 6):
        m.vine(lp_x0 - 1, y, ph - 1, int(m.rng.integers(4, 8)), LEAVES[1:], wall="-x", drift=0.4, leaf=0.7)

    return m
