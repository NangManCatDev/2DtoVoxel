"""Village props kit — reference/72f2ebd7-3c87-41bb-9212-1a8051536984.png

A kit sheet of three props seen from the front-right (az 315, el 30, orthographic):
a wooden hand cart, a stone fountain with an iron spout, and a roped log bundle with a
burlap sack. Each prop is its own part (object) in the .vox. They stand on one ground
plane, placed so each one lands where the sheet has it (screen x ~ X + Y), which puts
them on a diagonal going back-right.

Layout (x right, y depth with y=0 front, z up; local coords per piece):
  cart      body CL x CW, floor at BED, sides up to TOP; handles run +x past the body,
            front posts are legs to the ground; two spoked wheels with iron tyres on the
            -y / +y sides; iron corner brackets with rivets
  fountain  basin FW x FD x FH (walls WALL thick, floor at BASIN_FLOOR), pillar at the
            back centre up to PILLAR_H with a capping slab; iron spout plate + pipe on the
            pillar front pointing -y
  logs      2 rows of 4 square logs (LOG section, LOG_LEN long along y), ring end grain,
            2 rope loops (one round the bundle, one along it) crossing on top
  sack      burlap sack beside the logs (+x side, toward the back), tied neck, open collar
"""
import numpy as np

from voxtool import Model

NAME = "model_1029_0155"
REFERENCE = "reference/72f2ebd7-3c87-41bb-9212-1a8051536984.png"
VIEW = {"azimuth": 315, "elevation": 30, "fov": 0}
CUTOUT = {"keep": "all"}

GRID = (286, 224, 76)

# piece origins (world x, y) — near ground corners measured on the sheet
CART = (2, 15)
FOUNT = (132, 88)
LOGS = (201, 163)

# cart
CL, CW = 72, 48            # body length (x) and width (y)
POST = 6                   # corner post section
BED, TOP = 22, 44          # floor bottom / top of the side boards
HANDLE = 54                # handle length past the body
WHEEL_R, WHEEL_X = 25, 37  # wheel radius; axle position along the body
TYRE_T = 6                 # wheel thickness (y)
# axle stub between the body side and each wheel: the sheet draws the cart turned a
# few degrees, so its near wheel sits further out and the far one hides behind the body
GAP_NEAR, GAP_FAR = 8, 2

# fountain
FW, FD, FH = 60, 52, 22    # basin
WALL, BASIN_FLOOR = 7, 5
PIL_W, PIL_D, PILLAR_H = 26, 18, 64
CAP_T, CAP_O = 7, 2        # capping slab thickness / overhang

# logs + sack
LOG, LOG_LEN = 13, 38
SACK_C = (64, 43)          # sack centre in log-bundle coords
SACK_HW = (11.5, 12.5)     # half-widths of the squarish sack base (x, y)
NECK_Z, SACK_H = 31, 41    # tie at the neck, top of the collar

WOOD = ["wood", "wood_lt", "wood_dk"]
STONE = ["stone", "stone2", "stone3"]
BARK = ["bark", "bark2", "bark3", "bark_lt"]
SACKS = ["sack", "sack2", "sack3"]


def palette(m: Model):
    p = m.pal
    # cart wood + iron (between the lit top and the shaded side samples)
    p.add("wood", "#82604c"); p.add("wood_lt", "#937058"); p.add("wood_dk", "#6b4d3d")
    p.add("wood_gap", "#3a2a22")
    p.add("iron", "#56676c", metal=0.6); p.add("iron_dk", "#38444a", metal=0.6)
    p.add("rivet", "#8a9a9e", metal=0.6)
    # fountain stone
    p.add("stone", "#d4c4b1"); p.add("stone2", "#c9baa6"); p.add("stone3", "#dfd1bf")
    p.add("stone4", "#bba995"); p.add("stone_g", "#aea5a0"); p.add("joint", "#8c7d6d")
    p.add("basin", "#988a7a")
    p.add("spout", "#3f5a5c", metal=0.5); p.add("spout_dk", "#26363a", metal=0.5)
    p.add("spout_lt", "#5f7d7f", metal=0.5)
    # logs
    p.add("end", "#c8a074"); p.add("end2", "#b88c62"); p.add("end3", "#a97f58")
    p.add("ring", "#946d4c")
    p.add("pith", "#6a4c36")
    p.add("bark", "#5f4436"); p.add("bark2", "#6e5243"); p.add("bark3", "#4a352b")
    p.add("bark_lt", "#86654d")
    p.add("rope", "#c4ad95"); p.add("rope2", "#9f8871")
    # sack
    p.add("sack", "#9c7e64"); p.add("sack2", "#8a6d55"); p.add("sack3", "#ad8f73")
    p.add("sack_dk", "#5c4739"); p.add("sack_in", "#33271f")


# ---------------------------------------------------------------- helpers

def plank(m: Model, x, y, z, w, d, h, salt=0):
    """Wooden board with a per-board tone and grain streaks running along its long axis
    (each streak keeps one tone for a stretch, like the reference's smooth planks)."""
    tone = WOOD[(x * 7 + y * 13 + z * 5 + salt) % 3]
    m.box(x, y, z, w, d, h, tone)
    axis = int(np.argmax((w, d, h)))
    idx = [m.pal.idx(c) for c in WOOD]
    it = m.pal.idx(tone)

    def grain(X, Y, Z):
        C = (X, Y, Z)
        a, b = [C[i] for i in range(3) if i != axis]
        run = C[axis] // 11
        hsh = (a * 73 + b * 151 + run * 37 + salt * 11) % 17
        return np.where(hsh < 3, idx[2], np.where(hsh == 7, idx[1], it))
    m.paint_fn(x, y, z, w, d, h, grain)


def bracket(m: Model, x, y, z, w, d, h):
    """Iron plate (1 voxel thick, sitting on a face) with rivets near its ends."""
    m.box(x, y, z, w, d, h, "iron")
    m.box(x, y, z + h - 1, w, d, 1, "iron_dk")
    long_x = w >= d
    n = w if long_x else d
    for i in (1, n - 2):
        for zz in (z + 1, z + h - 2):
            if long_x:
                m.set(x + i, y, zz, "rivet")
            else:
                m.set(x, y + i, zz, "rivet")


def disc(m: Model, cx, cz, y0, d, r0, r1, c, *, spokes=0, spoke_w=1.6):
    """Ring (r0 <= r < r1) in the plane y = y0..y0+d around (cx, cz); spokes>0 instead
    draws that many radial spokes between r0 and r1."""
    R = int(np.ceil(r1)) + 1

    def fn(X, Y, Z):
        dx, dz = X - cx, Z - cz
        rr = np.hypot(dx, dz)
        if not spokes:
            return (rr >= r0) & (rr < r1)
        ang = np.arctan2(dz, dx)
        k = np.round(ang / (2 * np.pi / spokes))
        off = np.abs(rr * np.sin(ang - k * 2 * np.pi / spokes))
        return (rr >= r0) & (rr < r1) & (off <= spoke_w)
    m.where(int(cx) - R, y0, int(cz) - R, 2 * R + 1, d, 2 * R + 1, fn, c)


def wheel(m: Model, cx, y0, cz, outward, gap):
    """Spoked wheel in the plane y0..y0+TYRE_T, gap voxels off the body side.
    outward = -1 for the -y side, +1 for +y."""
    R = WHEEL_R
    disc(m, cx, cz, y0, TYRE_T, R - 3.2, R, "iron")              # tyre
    disc(m, cx, cz, y0 + 1, TYRE_T - 2, R - 7.5, R - 3.2, "wood_dk")  # felloe
    disc(m, cx, cz, y0 + 1, 3, 4, R - 7, "wood", spokes=8, spoke_w=1.9)   # 8 spokes
    # hub: from the outer face of the wheel in to the body side (bridges the gap)
    if outward < 0:
        hub_y, hub_d = y0 - 2, TYRE_T + 2 + gap
        cap_y = hub_y
    else:
        hub_y, hub_d = y0 - gap, TYRE_T + 2 + gap
        cap_y = y0 + TYRE_T
    m.cylinder(cx, cz, hub_y, 4.2, hub_d, "wood_dk", axis="y")
    m.cylinder(cx, cz, cap_y, 4.4, 2, "iron", axis="y")
    m.cylinder(cx, cz, cap_y - 1 if outward < 0 else cap_y + 2, 2.2, 1, "iron_dk", axis="y")
    # tyre studs: darker iron every few degrees on the outer face
    m.where(int(cx) - R - 1, y0, int(cz) - R - 1, 2 * R + 3, TYRE_T, 2 * R + 3,
            lambda X, Y, Z: (np.hypot(X - cx, Z - cz) >= R - 3.2)
            & (np.round(np.degrees(np.arctan2(Z - cz, X - cx)) / 15) % 2 == 0)
            & ((Y == y0) | (Y == y0 + TYRE_T - 1)), "iron_dk", only_filled=True)


def ashlar(m: Model, region, bw, bh, salt=0):
    """Stone-block texture with joints on everything stone-coloured in region, then
    mottling (light/dark/grey speckles) like the reference's weathered blocks."""
    m.bricks(STONE + ["stone4"], target="stone", bw=bw, bh=bh, mortar="joint",
             p=[0.4, 0.3, 0.2, 0.1], region=region, salt=salt)
    m.sprinkle(["stone4", "stone3", "stone_g", "stone2"], 0.18,
               target=STONE + ["stone4"], region=region)


# ---------------------------------------------------------------- cart

def cart_piece(m: Model):
    ox, oy = CART
    P = POST
    # under-frame beams that become the handles, crossbars
    for by in (3, CW - 7):
        plank(m, ox + 2, oy + by, BED - 4, CL - 2 + HANDLE, 4, 4, salt=1)
        m.box(ox + CL + HANDLE - 4, oy + by - 1, BED - 5, 5, 6, 6, "iron")     # tip caps
        m.box(ox + CL + HANDLE - 1, oy + by + 1, BED - 3, 1, 2, 2, "rivet")
    for bx in (P, CL - P - 4):
        plank(m, ox + bx, oy + 3, BED - 8, 4, CW - 6, 4, salt=2)
    plank(m, ox + CL + 4, oy + 3, BED - 4, 4, CW - 6, 3, salt=3)            # front stretcher

    # floor planks along x with dark gaps
    for i, py in enumerate(range(3, CW - 3, 7)):
        plank(m, ox + 3, oy + py, BED, CL - 6, min(6, CW - 3 - py), 3, salt=i)
    # side boards: 3 planks each with a gap between, top rail on top
    for sy in (0, CW - 3):
        for i, z in enumerate(range(BED, TOP - 3, 6)):
            plank(m, ox + P, oy + sy, z, CL - 2 * P, 3, 5, salt=10 + i)
            m.box(ox + P, oy + sy, z + 5, CL - 2 * P, 3, 1, "wood_gap")
        plank(m, ox + P, oy + sy - (1 if sy == 0 else 0), TOP - 3, CL - 2 * P, 4, 3, salt=20)
    # end boards (back x=0, front x=CL-3)
    for ex in (0, CL - 3):
        for i, z in enumerate(range(BED, TOP - 3, 6)):
            plank(m, ox + ex, oy + P, z, 3, CW - 2 * P, 5, salt=30 + i)
            m.box(ox + ex, oy + P, z + 5, 3, CW - 2 * P, 1, "wood_gap")
        plank(m, ox + ex - (1 if ex == 0 else 0), oy + P, TOP - 3, 4, CW - 2 * P, 3, salt=40)
    # corner posts; the two at the handle end run down to the ground as legs
    for px in (0, CL - P):
        for py in (0, CW - P):
            z0 = 0 if px else BED - 8
            plank(m, ox + px, oy + py, z0, P, P, TOP + 3 - z0, salt=50)
            m.box(ox + px, oy + py, TOP + 2, P, P, 1, "wood_lt")
            # iron corner brackets wrapping both outer faces
            fy = oy + (-1 if py == 0 else CW)
            fx = ox + (-1 if px == 0 else CL)
            xs = ox + (px if px == 0 else px - 3)
            ys = oy + (py if py == 0 else py - 3)
            for zb in (TOP - 7, BED + 2):
                bracket(m, xs, fy, zb, P + 3, 1, 6)
                bracket(m, fx, ys, zb, 1, P + 3, 6)
            if px:   # iron shoe on the legs
                m.box(ox + px - 1, oy + py - 1, 0, P + 2, P + 2, 3, "iron_dk")
    # wheels on both sides of the axle
    wheel(m, ox + WHEEL_X, oy - TYRE_T - GAP_NEAR, WHEEL_R, -1, GAP_NEAR)
    wheel(m, ox + WHEEL_X, oy + CW + GAP_FAR, WHEEL_R, +1, GAP_FAR)


# ---------------------------------------------------------------- fountain

def fountain_piece(m: Model):
    ox, oy = FOUNT
    # basin: thick walls, sunken stone floor
    m.box(ox, oy, 0, FW, FD, FH, "stone")
    m.carve(ox + WALL, oy + WALL, BASIN_FLOOR, FW - 2 * WALL, FD - 2 * WALL, FH)
    ashlar(m, (ox, oy, 0, FW, FD, FH), bw=25, bh=11)
    m.bricks(["basin", "stone4"], target=STONE + ["stone4", "stone_g"], bw=8, bh=50, mortar="joint",
             region=(ox + WALL, oy + WALL, 0, FW - 2 * WALL, FD - 2 * WALL, BASIN_FLOOR))

    # pillar at the back centre, flush with the back of the basin
    px = ox + (FW - PIL_W) // 2
    py = oy + FD - PIL_D
    m.box(px, py, 0, PIL_W, PIL_D, PILLAR_H, "stone")
    ashlar(m, (px, py, FH - 2, PIL_W, PIL_D, PILLAR_H - FH + 2), bw=14, bh=10, salt=3)
    # plinth course round the pillar foot, a step proud of it
    m.box(px - 2, py - 2, FH - 3, PIL_W + 4, PIL_D + 2, 5, "stone3")
    m.bricks(STONE, target="stone3", bw=9, bh=5, mortar="joint", region=(px - 2, py - 2, FH - 3, PIL_W + 4, 3, 5))
    m.box(px - 2, py - 2, FH + 1, PIL_W + 4, PIL_D + 2, 1, "stone2", only_filled=True)
    # capping slab: 4 stones with a cross joint on top
    cx0, cy0 = px - CAP_O, py - CAP_O
    cw, cd = PIL_W + 2 * CAP_O, PIL_D + 2 * CAP_O
    m.box(cx0, cy0, PILLAR_H, cw, cd, CAP_T, "stone3")
    m.box(cx0, cy0, PILLAR_H, cw, cd, 1, "joint")
    m.box(cx0 + cw // 2, cy0, PILLAR_H + 1, 1, cd, CAP_T - 1, "joint")
    m.box(cx0, cy0 + cd // 2, PILLAR_H + 1, cw, 1, CAP_T - 1, "joint")
    m.sprinkle(["stone4", "stone", "stone_g"], 0.18, target="stone3",
               region=(cx0, cy0, PILLAR_H, cw, cd, CAP_T))

    # iron spout: plate on the pillar front, pipe out toward -y, elbow down, nozzle
    sx = px + 2                     # plate sits left of centre, as on the sheet
    m.box(sx, py - 1, 44, 14, 1, 14, "spout")
    m.box(sx, py - 1, 57, 14, 1, 1, "spout_dk")
    for bx, bz in ((sx + 1, 45), (sx + 12, 45), (sx + 1, 56), (sx + 12, 56)):
        m.set(bx, py - 2, bz, "spout_lt")
    pcx = sx + 5
    m.box(pcx, py - 13, 49, 5, 12, 5, "spout")                  # pipe
    m.box(pcx, py - 13, 53, 5, 12, 1, "spout_lt")
    m.box(pcx, py - 13, 42, 5, 5, 12, "spout")                  # elbow down
    m.box(pcx - 1, py - 14, 40, 7, 7, 3, "spout_dk")             # nozzle collar
    m.carve(pcx + 1, py - 12, 40, 3, 3, 2)
    m.box(pcx + 1, py - 12, 42, 3, 3, 1, "spout_dk")


# ---------------------------------------------------------------- logs + sack

def log(m: Model, x, y, z, length, salt):
    """Square log along y with chamfered long edges, bark streaks and ring end grain."""
    L = LOG
    m.box(x, y, z, L, length, L, "bark")
    for ex, ez in ((x, z), (x + L - 1, z), (x, z + L - 1), (x + L - 1, z + L - 1)):
        m.carve(ex, y, ez, 1, length, 1)
    m.vary(BARK, target="bark", p=[0.35, 0.25, 0.25, 0.15], region=(x, y, z, L, length, L))
    # streaks along the grain: whole runs in y share a tone
    ib = [m.pal.idx(c) for c in BARK]

    def streak(X, Y, Z):
        h = (X * 31 + Z * 17 + salt * 7 + (Y // 9) * 3) % 11
        return np.where(h < 2, ib[2], np.where(h == 5, ib[3], 0))
    m.paint_fn(x, y, z, L, length, L, streak)
    # ring end grain on both ends; each log gets its own end tone and off-centre pith
    c = (L - 1) / 2
    ends = ("end", "end2", "end3")
    ie, ie2, ir, ip = (m.pal.idx(n) for n in (ends[salt % 3], ends[(salt + 1) % 3], "ring", "pith"))
    ocx, ocz = c + (salt % 3) - 1, c + ((salt // 2) % 3) - 1

    def rings(X, Y, Z):
        r = np.maximum(np.abs(X - x - ocx), np.abs(Z - z - ocz))
        col = np.where(r < 1, ip, np.where((r >= 2) & (r < 3), ir, np.where((r >= 4.5) & (r < 5.5), ir, ie)))
        col = np.where((r >= 3) & (r < 4.5) & ((X + Z) % 3 == 0), ie2, col)
        return col
    for ey in (y, y + length - 1):
        m.paint_fn(x, ey, z, L, 1, L, rings)


def log_piece(m: Model):
    ox, oy = LOGS
    # bottom row of 4, top row of 4 nudged sideways; ends staggered a little
    for i, dy in enumerate((2, 0, 3, 0)):
        log(m, ox + i * LOG, oy + dy, 0, LOG_LEN - dy, salt=i)
    for i, dy in enumerate((3, 1, 0, 2)):
        log(m, ox + 1 + i * LOG, oy + dy, LOG, LOG_LEN - dy - 1, salt=4 + i)

    W, H = 4 * LOG + 1, 2 * LOG
    ir, ir2 = m.pal.idx("rope"), m.pal.idx("rope2")

    def braid(X, Y, Z):
        return np.where(((X + Y + Z) // 2) % 2 == 0, ir, ir2)
    # loop 1: round the bundle (plane y = const), over the top and down both sides
    ry = oy + 14
    m.box(ox - 1, ry, H, W + 2, 3, 2, "rope")
    m.box(ox - 2, ry, 0, 2, 3, H + 1, "rope")
    m.box(ox + W, ry, 0, 2, 3, H + 1, "rope")
    m.paint_fn(ox - 2, ry, 0, W + 4, 3, H + 2, braid)
    # loop 2: along the logs (plane x = const), over the top and down both ends
    rx = ox + 2 * LOG - 1
    m.box(rx, oy - 2, H, 3, LOG_LEN + 3, 2, "rope")
    m.box(rx, oy - 2, 0, 3, 2, H + 1, "rope")
    m.box(rx, oy + LOG_LEN - 1, 0, 3, 2, H + 1, "rope")
    m.paint_fn(rx, oy - 2, 0, 3, LOG_LEN + 3, H + 2, braid)
    m.box(rx - 1, ry - 1, H + 1, 5, 5, 2, "rope2")             # knot where they cross


def sack_piece(m: Model):
    """Squarish burlap sack: wide flat-sided base tapering like a bell to a tied neck,
    with a square open collar on top and folds gathering toward the tie."""
    cx, cy = LOGS[0] + SACK_C[0], LOGS[1] + SACK_C[1]
    hx, hy = SACK_HW
    zs = [0, 2, 9, 16, 22, 27, NECK_Z]
    ss = [0.9, 1.0, 1.0, 0.9, 0.74, 0.56, 0.42]      # size of the cross-section per height
    R = int(max(hx, hy)) + 2

    def body(X, Y, Z):
        s = np.interp(Z, zs, ss)
        ang = np.arctan2(Y - cy, X - cx)
        s = s * (1 + 0.04 * np.sin(3 * ang + Z * 0.3))
        return (np.abs(X - cx) / (hx * s)) ** 6 + (np.abs(Y - cy) / (hy * s)) ** 6 <= 1.0
    m.where(cx - R, cy - R, 0, 2 * R + 1, 2 * R + 1, NECK_Z, body, "sack")
    reg = (cx - R, cy - R, 0, 2 * R + 1, 2 * R + 1, SACK_H + 1)
    m.vary(SACKS, target="sack", p=[0.45, 0.3, 0.25], region=reg)
    # folds: a few dark creases fanning down from the neck, irregular angles
    idk = m.pal.idx("sack_dk")
    creases = np.array([-2.6, -1.9, -1.2, -0.75, -0.2, 0.5, 1.3, 2.2])

    def folds(X, Y, Z):
        ang = np.arctan2(Y - cy, X - cx)
        d = np.min(np.abs(((ang[..., None] - creases) + np.pi) % (2 * np.pi) - np.pi), axis=-1)
        return np.where((d < 0.11) & (Z > 9 + (X + Y) % 6) & (Z < NECK_Z) & (Z > NECK_Z - 22), idk, 0)
    m.paint_fn(*reg, folds)
    # neck + tie
    m.box(cx - 4, cy - 4, NECK_Z - 1, 9, 9, 4, "sack2")
    m.box(cx - 5, cy - 5, NECK_Z, 11, 11, 2, "rope2")
    m.box(cx - 5, cy - 5, NECK_Z + 1, 11, 11, 1, "sack_dk")
    # square open collar, rolled lip, dark inside
    c0x, c0y = cx - 6, cy - 6
    m.box(c0x, c0y, NECK_Z + 3, 13, 13, SACK_H - NECK_Z - 3, "sack3")
    m.vary(SACKS, target="sack3", p=[0.4, 0.2, 0.4], region=(c0x, c0y, NECK_Z + 3, 13, 13, 10))
    m.box(c0x - 1, c0y - 1, SACK_H - 3, 15, 15, 3, "sack3")
    m.carve(c0x + 3, c0y + 3, NECK_Z + 5, 7, 7, SACK_H)
    m.box(c0x + 3, c0y + 3, NECK_Z + 4, 7, 7, 1, "sack_in")


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(*GRID, seed=7)
    palette(m)
    with m.part("cart"):
        cart_piece(m)
    with m.part("fountain"):
        fountain_piece(m)
    with m.part("logs"):
        log_piece(m)
    with m.part("sack"):
        sack_piece(m)
    return m
