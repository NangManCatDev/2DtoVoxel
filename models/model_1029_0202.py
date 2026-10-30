"""Town props kit — reference/48e39248-3654-4eef-b2d0-1b04dceea3e6.png

A kit sheet of three loose props in patinated teal iron on sandstone, seen from the
front-right: front faces (-y) run down-right to the nearest corner, +x ends run up-right.
Scale: about PX reference px per voxel. Every prop is its own m.part(), so the .vox holds
one named object per prop that can be moved on its own in MagicaVoxel.

Layout (x right, y depth with y=0 front, z up). Each prop stands on z=0; its stone base's
nearest bottom corner (front-right) is placed where the sheet has it (ANCHOR, solved for
the VIEW camera by floor_offset), which puts the props on a diagonal going back.
  mailbox  base 22x22: big 2x2 base course, 16x16 three-course stone shaft, iron box
           18x18 with a recessed door, letter slot under a hood, brass envelope plaque,
           grooved sides, stepped roof and a cube finial
  bell     stone slab 45x17 (two courses), two iron posts 30 apart (plinth, collar, 5x5
           shaft, bolted capital, cap, finial), crossbar with a centre clamp, brass bell
           on a yoke, pull rope with a brass weight
  clock    base 19x19, 11x11 lower and 9x9 upper stone shaft, iron post with an arm along
           +x carrying a square clock (dial front and back, brass hands and markers,
           crest on top), scroll brackets down to the pillar
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_0202"
REFERENCE = "reference/48e39248-3654-4eef-b2d0-1b04dceea3e6.png"
VIEW = {"azimuth": 325, "elevation": 20, "fov": 0}
CUTOUT = {"keep": "all"}

PX = 8.0                    # reference px per voxel
# nearest bottom corner (front-right of the stone base) of each prop in the sheet, px
ANCHOR = {"mailbox": (395, 751), "bell": (1073, 755), "clock": (1481, 748)}
MARGIN, GRID_H = 3, 92

# mailbox
MB_BASE, MB_BASE_H = 20, 9
MB_SHAFT, MB_COURSES = 14, (6, 6, 6)
MB_BODY, MB_BODY_H = 16, 22          # incl. the 2-high plinth band
MB_ROOF = [(20, 2), (18, 2), (14, 2), (8, 1), (6, 1), (4, 3)]    # (width, height) tiers
# bell frame
BL_W, BL_D, BL_COURSES = 45, 17, (6, 7)
BL_POSTS = (7, 37)                   # post centre x (local)
BL_CY = 8                            # post / bell centre y
POST = [(9, 4), (7, 3), (5, 32), (7, 6), (9, 3), (5, 2), (3, 3)]  # (width, height) bottom up
BAR_Z, BAR_H = 40, 4                 # crossbar, above the slab top
BELL_Z = 22                          # bell lip, above the slab top
BELL_TOP = 15                        # bell height above the lip
BELL_PROFILE = [(0, 2, 7.5), (2, 2, 7.0), (4, 5, 6.0), (9, 3, 5.2), (12, 2, 4.2), (14, 1, 3.0)]
WEIGHT_Z = 7
# clock post
CL_BASE, CL_BASE_H = 19, 9
CL_LOW, CL_LOW_COURSES = 11, (7, 7, 6)
CL_UP, CL_UP_COURSES = 9, (8, 8, 8, 8)
CL_POST = [(7, 4), (5, 8), (7, 4), (9, 3), (5, 2), (3, 3)]
CLK_X, CLK_W, CLK_D = 21, 23, 7      # clock box (local x, width along x, depth)
CLK_Z, CLK_H = 51, 23
ARM_Z = 74

STONES = ["st0", "st1", "st2", "st3"]
STONE_P = [0.35, 0.25, 0.25, 0.15]
TEAL = ["tl0", "tl1", "tl2"]


def palette(m: Model):
    p = m.pal
    # sandstone (front sample / 0.9), grey-blue mottling, dark joints
    p.add("st0", "#e4d9c4"); p.add("st1", "#d9ccb5"); p.add("st2", "#ece4d2"); p.add("st3", "#cdbfa6")
    p.add("spot0", "#c2b5a2"); p.add("spot1", "#aea8a6"); p.add("joint", "#a89880"); p.add("groove", "#7c6e5e")
    # patinated iron
    p.add("tl0", "#3c5758", metal=0.4, rough=0.6); p.add("tl1", "#324647", metal=0.4, rough=0.6)
    p.add("tl2", "#456566", metal=0.4, rough=0.6); p.add("tl3", "#5b8482", metal=0.4, rough=0.6)
    p.add("tl_dk", "#1c2727"); p.add("bolt", "#6f9895", metal=0.6, rough=0.4)
    p.add("hole", "#0f1414")
    # bell brass
    p.add("gd0", "#d9b47a", metal=0.7, rough=0.35); p.add("gd1", "#c39b62", metal=0.7, rough=0.35)
    p.add("gd2", "#f0d293", metal=0.7, rough=0.35); p.add("gd_dk", "#8a663b", metal=0.7, rough=0.35)
    # small brass fittings (plaque, clock markers and hands)
    p.add("br0", "#dcaa50", metal=0.7, rough=0.35); p.add("br_dk", "#8a6430")
    p.add("rope0", "#8e5636"); p.add("rope1", "#6e4026")
    # clock dial
    p.add("dial0", "#cfc7b8"); p.add("dial1", "#c0b7a7"); p.add("dial_rim", "#77736b")


# ---------------------------------------------------------------- helpers

def floor_offset(du, dv, view=VIEW):
    """Ground-plane move (dx, dy) in voxels that shifts a point by (du, dv) reference px on
    screen (v pointing down) under the orthographic VIEW camera (axes as in render.Camera)."""
    a, e = math.radians(view["azimuth"]), math.radians(view["elevation"])
    mat = np.array([[math.cos(a), -math.sin(a)],
                    [-math.sin(e) * math.sin(a), -math.sin(e) * math.cos(a)]])
    return np.linalg.solve(mat, np.array([du, dv], float) / PX)


def course(m: Model, x, y, z, w, d, h, cuts_x=(), cuts_y=(), *, groove=True):
    """One course of dressed stone over (x, y, w, d) from z, h tall, split into blocks at the
    absolute positions cuts_x / cuts_y (1-voxel dark joints there), one shade per block.
    With groove the bottom layer is inset by one and dark: the joint under the course."""
    xs, ys = [x, *cuts_x, x + w], [y, *cuts_y, y + d]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            c = str(m.rng.choice(STONES, p=STONE_P))
            m.box(xs[i], ys[j], z, xs[i + 1] - xs[i], ys[j + 1] - ys[j], h, c)
    for cx in cuts_x:
        m.box(cx, y, z, 1, d, h, "joint")
    for cy in cuts_y:
        m.box(x, cy, z, w, 1, h, "joint")
    if groove:
        m.box(x, y, z, w, d, 1, None)
        m.box(x + 1, y + 1, z, w - 2, d - 2, 1, "groove")


def corner(c, w):
    """Low edge of a run w long centred on c (continuous: voxel i spans i..i+1, so an odd
    run centres on i + 0.5, an even one on a whole number)."""
    return int(math.floor(c - w / 2 + 0.5))


def shaft(m: Model, cx, cy, z, size, courses):
    """Square stone shaft centred on (cx, cy) (see corner): courses stacked from z, the
    block joints alternate side per course. Returns the top z."""
    x0, y0 = corner(cx, size), corner(cy, size)
    for i, h in enumerate(courses):
        k = size // 3 if i % 2 else size - size // 3
        course(m, x0, y0, z, size, size, h, cuts_x=(x0 + k,), cuts_y=(y0 + size - k,))
        z += h
    return z


def stack(m: Model, cx, cy, z, tiers, c="tl0"):
    """Square tiers (width, height) stacked from z, centred on (cx, cy). Returns the top z."""
    for w, h in tiers:
        m.box(corner(cx, w), corner(cy, w), z, w, w, h, c)
        z += h
    return z


def rounded(X, Z, x, z, w, h, r):
    """True inside the rectangle (x, z, w, h) with corners cut by r (staircase chamfer)."""
    dx = np.minimum(X - x, x + w - 1 - X)
    dz = np.minimum(Z - z, z + h - 1 - Z)
    return (dx >= 0) & (dz >= 0) & (dx + dz >= r)


# ---------------------------------------------------------------- props

def mailbox(m: Model, x0, y0):
    B = MB_BASE
    cx, cy = x0 + B / 2, y0 + B / 2
    course(m, x0, y0, 0, B, B, MB_BASE_H, cuts_x=(x0 + B // 2,), cuts_y=(y0 + B // 2,), groove=False)
    z = shaft(m, cx, cy, MB_BASE_H, MB_SHAFT, MB_COURSES)

    # iron box: plinth band, body, cornice
    W = MB_BODY
    bx, by, bz = int(cx - W / 2), int(cy - W / 2), z
    m.box(bx - 1, by - 1, bz, W + 2, W + 2, 2, "tl1")
    m.box(bx, by, bz + 2, W, W, MB_BODY_H - 3, "tl0")
    top = bz + MB_BODY_H
    m.box(bx - 1, by - 1, top - 1, W + 2, W + 2, 1, "tl1")
    # stepped roof + finial
    stack(m, cx, cy, top, MB_ROOF)

    # front door: recessed panel inside a 2-voxel frame
    m.box(bx + 2, by, bz + 3, W - 4, 1, MB_BODY_H - 6, None)
    m.box(bx + 2, by + 1, bz + 3, W - 4, 1, MB_BODY_H - 6, "tl1")
    # letter slot with a rim and a hood
    sz = bz + MB_BODY_H - 7
    m.box(bx + 3, by, sz - 1, W - 6, 1, 4, "tl2")
    m.box(bx + 4, by, sz, W - 8, 3, 2, None)
    m.box(bx + 4, by + 3, sz, W - 8, 1, 2, "hole")
    m.box(bx + 3, by - 1, sz + 3, W - 6, 1, 1, "tl2")
    # brass envelope plaque (border, flap "V")
    px, pz = bx + (W - 8) // 2, bz + 5
    m.box(px, by, pz, 8, 1, 7, "br_dk")
    m.box(px + 1, by - 1, pz + 1, 6, 1, 5, "br0")
    for i, dz in enumerate((4, 3, 2, 2, 3, 4)):
        m.set(px + 1 + i, by - 1, pz + 1 + dz, "br_dk")
    # latch on the right edge of the door
    m.box(bx + W - 3, by - 1, bz + 8, 1, 1, 4, "tl2")
    # grooves on the sides: vertical planks
    for gy in (by + W // 3, by + 2 * W // 3):
        m.box(bx + W - 1, gy, bz + 3, 1, 1, MB_BODY_H - 6, "tl_dk")
    for gx in (bx + W // 3, bx + 2 * W // 3):
        m.box(gx, by + W - 1, bz + 3, 1, 1, MB_BODY_H - 6, "tl_dk")


def bell_frame(m: Model, x0, y0):
    z = 0
    for i, h in enumerate(BL_COURSES):
        cuts = (x0 + 11, x0 + 23, x0 + 34) if i == 0 else (x0 + 6, x0 + 17, x0 + 29, x0 + 40)
        course(m, x0, y0, z, BL_W, BL_D, h, cuts_x=cuts, cuts_y=(() if i == 0 else (y0 + 9,)), groove=i > 0)
        z += h
    z0 = z
    cy = y0 + BL_CY
    for px in BL_POSTS:
        stack(m, x0 + px + 0.5, cy + 0.5, z0, POST)
        # bolts on the plinth and the capital (front and right faces)
        for bz in (z0 + 2, z0 + 41):
            m.set(x0 + px - 2, cy - 5 if bz == z0 + 2 else cy - 4, bz, "bolt")
            m.set(x0 + px + (5 if bz == z0 + 2 else 4), cy + 2, bz, "bolt")
    # crossbar between the posts, clamp in the middle
    xa, xb = x0 + BL_POSTS[0], x0 + BL_POSTS[1]
    bcx = (xa + xb) // 2
    m.box(xa, cy - 1, z0 + BAR_Z, xb - xa, 3, BAR_H, "tl0")
    m.box(bcx - 3, cy - 2, z0 + BAR_Z - 1, 7, 5, BAR_H + 2, "tl1")
    m.box(bcx - 3, cy - 2, z0 + BAR_Z + BAR_H + 1, 7, 5, 1, "tl2")
    # yoke and bell
    lip = z0 + BELL_Z
    m.box(bcx - 1, cy - 1, lip + BELL_TOP, 3, 3, BAR_Z - BELL_Z - BELL_TOP, "tl1")
    for dz, h, r in BELL_PROFILE:
        m.where(int(bcx - r - 1), int(cy - r - 1), lip + dz, int(2 * r + 3), int(2 * r + 3), h,
                lambda X, Y, Z, r=r: np.abs(X - bcx) ** 2.5 + np.abs(Y - cy) ** 2.5 <= r ** 2.5 + 0.5, "gd0")
    m.box(bcx - 8, cy - 8, lip + 1, 17, 17, 1, "gd_dk", only_filled=True)    # band above the lip
    m.box(bcx - 8, cy - 8, lip + 8, 17, 17, 1, "gd1", only_filled=True)      # waist band
    # pull rope from the rim with a brass weight
    rx, ry = bcx + 3, cy - 1
    m.box(rx, ry, z0 + WEIGHT_Z + 3, 1, 1, BELL_Z - WEIGHT_Z - 3, "rope0")
    for zz in range(z0 + WEIGHT_Z + 3, lip, 3):
        m.set(rx, ry, zz, "rope1")
    m.box(rx - 1, ry - 1, z0 + WEIGHT_Z, 3, 3, 3, "gd1")


def clock_post(m: Model, x0, y0):
    B = CL_BASE
    cx, cy = x0 + B // 2, y0 + B // 2
    course(m, x0, y0, 0, B, B, CL_BASE_H, cuts_x=(x0 + 9,), cuts_y=(y0 + 10,), groove=False)
    z = shaft(m, cx + 0.5, cy + 0.5, CL_BASE_H, CL_LOW, CL_LOW_COURSES)
    z = shaft(m, cx + 0.5, cy + 0.5, z, CL_UP, CL_UP_COURSES)
    stack(m, cx + 0.5, cy + 0.5, z, CL_POST)
    m.set(cx - 1, cy - 4, z + 2, "bolt")
    m.set(cx + 4, cy + 1, z + 2, "bolt")

    # arm along +x from the post to past the clock centre
    ccx = x0 + CLK_X + CLK_W // 2
    m.box(cx + 2, cy - 1, ARM_Z, ccx + 4 - (cx + 2), 3, 3, "tl0")
    m.box(ccx + 4, cy - 1, ARM_Z - 1, 2, 3, 4, "tl1")                  # end cap

    # clock box with cut corners
    X0, Y0 = x0 + CLK_X, cy - CLK_D // 2
    m.where(X0, Y0, CLK_Z, CLK_W, CLK_D, CLK_H,
            lambda X, Y, Z: rounded(X, Z, X0, CLK_Z, CLK_W, CLK_H, 3), "tl0")
    m.where(X0, Y0 + 1, CLK_Z, CLK_W, CLK_D - 2, CLK_H,                 # darker band round the edge
            lambda X, Y, Z: rounded(X, Z, X0, CLK_Z, CLK_W, CLK_H, 3), "tl1", only_filled=True)
    m.where(X0 + 1, Y0 + 1, CLK_Z + 1, CLK_W - 2, CLK_D - 2, CLK_H - 2,
            lambda X, Y, Z: rounded(X, Z, X0 + 1, CLK_Z + 1, CLK_W - 2, CLK_H - 2, 3), "tl0")
    czc = CLK_Z + CLK_H // 2
    for face, inner in ((Y0, Y0 + 1), (Y0 + CLK_D - 1, Y0 + CLK_D - 2)):
        dial = lambda X, Y, Z: rounded(X, Z, X0 + 3, CLK_Z + 3, CLK_W - 6, CLK_H - 6, 2)
        m.where(X0 + 3, face, CLK_Z + 3, CLK_W - 6, 1, CLK_H - 6, dial, None)
        m.where(X0 + 3, inner, CLK_Z + 3, CLK_W - 6, 1, CLK_H - 6, dial, "dial_rim")
        m.where(X0 + 4, inner, CLK_Z + 4, CLK_W - 8, 1, CLK_H - 8,
                lambda X, Y, Z: rounded(X, Z, X0 + 4, CLK_Z + 4, CLK_W - 8, CLK_H - 8, 2), "dial0")
        m.where(X0 + 4, inner, CLK_Z + 4, CLK_W - 8, 1, CLK_H - 8,
                lambda X, Y, Z: (X - ccx) - (Z - czc) > 4, "dial1", only_filled=True)
        # hands: hour to ~10, minute to ~2, hub
        m.line((ccx, face, czc), (ccx - 5, face, czc + 4), "br0")
        m.line((ccx, face, czc), (ccx + 6, face, czc + 4), "br0")
        m.set(ccx, face, czc, "br_dk")
    # brass markers: top and bottom of the front frame, middle of the right side
    m.box(ccx - 1, Y0 - 1, CLK_Z + CLK_H - 3, 3, 1, 2, "br0")
    m.box(ccx - 1, Y0 - 1, CLK_Z + 1, 3, 1, 2, "br0")
    m.box(X0 + CLK_W, Y0 + 2, czc - 1, 1, 3, 3, "br0")
    # crest on the clock top, encasing the arm
    stack(m, ccx + 0.5, cy + 0.5, CLK_Z + CLK_H, [(7, 3), (5, 2), (3, 3)])

    # brackets to the pillar: wall plate, lower brace with a scroll, upper scroll under the arm
    px = cx + CL_UP // 2 + 1
    m.box(px, cy - 2, CLK_Z - 4, 1, 5, 12, "tl1")
    m.box(px, cy - 1, CLK_Z, X0 - px, 3, 3, "tl0")
    m.box(px + 2, cy - 1, CLK_Z - 5, 2, 3, 5, "tl0")
    m.box(px + 2, cy - 1, CLK_Z - 7, 4, 3, 3, "tl1")
    m.box(px + 1, cy - 1, ARM_Z - 5, 2, 3, 5, "tl0")
    m.box(px + 3, cy - 1, ARM_Z - 6, 3, 3, 2, "tl0")
    m.box(px + 5, cy - 1, ARM_Z - 4, 1, 3, 3, "tl0")


# ---------------------------------------------------------------- build

def layout():
    """Local origins (x, y) of the three props, from where the sheet has their nearest
    bottom corners, shifted so everything is inside the grid. Also returns the grid size."""
    widths = {"mailbox": MB_BASE, "bell": BL_W, "clock": CL_BASE}
    extent = {"mailbox": (MB_BASE + 1, MB_BASE + 1), "bell": (BL_W, BL_D), "clock": (CLK_X + CLK_W + 2, CL_BASE)}
    u0, v0 = ANCHOR["mailbox"]
    org = {}
    for k, (u, v) in ANCHOR.items():
        dx, dy = floor_offset(u - u0, v - v0)
        org[k] = (dx - widths[k], dy)
    mx = min(o[0] for o in org.values()) - MARGIN
    my = min(o[1] for o in org.values()) - MARGIN
    org = {k: (int(round(x - mx)), int(round(y - my))) for k, (x, y) in org.items()}
    W = max(org[k][0] + extent[k][0] for k in org) + MARGIN
    D = max(org[k][1] + extent[k][1] for k in org) + MARGIN
    return org, (W, D, GRID_H)


def build() -> Model:
    org, grid = layout()
    m = Model(*grid, seed=7)
    palette(m)
    with m.part("mailbox"):
        mailbox(m, *org["mailbox"])
    with m.part("bell_frame"):
        bell_frame(m, *org["bell"])
    with m.part("clock_post"):
        clock_post(m, *org["clock"])
    # weathering: patina on the iron, mottled sandstone
    m.vary(TEAL, target="tl0", p=[0.7, 0.15, 0.15])
    m.sprinkle(["tl3"], 0.025, target=TEAL)
    m.sprinkle(["spot0", "spot1"], 0.05, target=STONES)
    m.vary(["gd0", "gd2"], target="gd0", p=[0.8, 0.2])
    return m
