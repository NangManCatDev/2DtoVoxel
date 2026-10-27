"""플레이어의 집 — reference/플레이어의집_레퍼런스.png

Layout (x right, y depth with y=0 front, z up):
  main body     x 18..87, y 20..59, walls up to z=43, raised floor at z=9
  main roof     gable, ridge along x, teal planks; left gable overhangs,
                right end is a crow-stepped stone parapet
  porch awning  roof skirt as steep as the main roof over the whole front,
                scalloped edge; the main roof drops lower over the door section
  front         double red door + 3-step stairs, landing with iron railing,
                two 2x2 windows, lit lanterns left of the door and at the right end
  left side     small gable window, quoins, big unlit wall lantern, climbing vines
  planters      along the left wall and in front of the windows (top ~ floor
                level), bushes with blue flowers, vines draping over the edges
"""
from voxtool import Model

NAME = "player_house"
REFERENCE = "reference/플레이어의집_레퍼런스.png"
VIEW = {"azimuth": 36, "elevation": 18}

HX0, HX1 = 18, 88   # main body x range [HX0, HX1)
HY0, HY1 = 24, 64   # main body y range
FLOOR = 12          # top of the porch / floor level (3 steps of 4)
EAVE = 52           # first z above the walls
WALL_T = 3
DOOR_TOP = FLOOR + 21
AW_Y0 = 12          # front edge of the porch awning (12 deep)
PL_Y0 = 12          # front edge of the porch platform; 2 steps of 4 deep in front of it


def palette(m: Model):
    # base colors are calibrated so the shaded preview faces match the reference
    # (front face ~ x0.9, left face ~ x0.76)
    p = m.pal
    p.add("wall", "#dcc3a0"); p.add("wall2", "#d4ba96"); p.add("wall3", "#e3cca9")
    p.add("trim", "#e8d7bd")
    p.add("quoin", "#dcc8aa"); p.add("quoin2", "#cfb999"); p.add("mortar", "#7d6a52")
    p.add("stone", "#d2bb9a"); p.add("stone2", "#c6af8e"); p.add("groove", "#8f7a5c")
    p.add("roof", "#0b8691"); p.add("roof_hi", "#1ba3ad"); p.add("roof_dk", "#056a73")
    p.add("iron", "#1f1c19"); p.add("iron2", "#2e2925")
    p.add("door", "#8c2b22"); p.add("door_dk", "#5c1a15"); p.add("door_frame", "#3b1e17")
    p.add("glass", "#8a8094"); p.add("win_frame", "#2a2321"); p.add("win_dark", "#2b2420")
    p.add("lamp", "#ffd84a", emit=4.0); p.add("lamp_off", "#3a2e26")
    p.add("soil", "#3b2a1c")
    p.add("leaf0", "#16300d"); p.add("leaf1", "#24481a"); p.add("leaf2", "#33621f"); p.add("leaf3", "#4f7a2e")
    p.add("flower0", "#3e6be0"); p.add("flower1", "#6d92f6"); p.add("flower2", "#6a4fc8")


LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3"]
LEAF_P = [0.25, 0.35, 0.28, 0.12]
FLOWERS = ["flower0", "flower1", "flower2"]
PLANKS = ["roof_hi", "roof", "roof_dk"]


# ---------------------------------------------------------------- face helper

def fbox(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int, c):
    """Box relative to a main-body wall face. u = position along the face
    (left->right as seen from outside), d0 = depth into the wall (0 = outer wall
    layer, -1 = one voxel in front of the wall), dd = thickness inward."""
    if face == "front":
        m.box(HX0 + u, HY0 + d0, z, w, dd, h, c)
    elif face == "back":
        m.box(HX1 - u - w, HY1 - d0 - dd, z, w, dd, h, c)
    elif face == "left":
        m.box(HX0 + d0, HY1 - u - w, z, dd, w, h, c)
    elif face == "right":
        m.box(HX1 - d0 - dd, HY0 + u, z, dd, w, h, c)


def window(m: Model, face: str, u: int, z: int, w: int = 9, h: int = 11):
    """Dark frame, 2x2 lavender panes recessed 2, stone sill + lintel."""
    fbox(m, face, u, z, w, h, 0, 2, "win_frame")
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 0, 2, None)          # opening
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 2, 1, "glass")
    fbox(m, face, u + w // 2, z + 1, 1, h - 2, 1, 1, "win_frame")   # mullion
    fbox(m, face, u + 1, z + h // 2, w - 2, 1, 1, 1, "win_frame")   # transom
    fbox(m, face, u - 1, z - 1, w + 2, 1, -2, 2, "trim")            # sill
    fbox(m, face, u, z - 2, w, 1, -1, 1, "trim")
    fbox(m, face, u - 1, z + h, w + 2, 1, -1, 1, "trim")            # lintel


def quoins(m: Model, cx: int, cy: int, sx: int, sy: int):
    """Protruding corner stones at wall corner (cx, cy); sx/sy = outward direction."""
    for i, z in enumerate(range(0, EAVE - 1, 5)):
        lf, ls = (5, 3) if i % 2 == 0 else (3, 5)
        col = "quoin" if i % 2 == 0 else "quoin2"
        # stones on the y-facing wall (protrude in y) and on the x-facing wall (protrude in x)
        x0 = cx if sx < 0 else cx - lf + 1
        m.box(x0 + (-1 if sx < 0 else 1), cy + sy, z, lf, 1, 4, col)
        y0 = cy if sy < 0 else cy - ls + 1
        m.box(cx + sx, y0, z, 1, ls, 4, col)
        # dark joint line under each stone row
        m.box(min(cx, cx + sx * lf), cy + sy, z + 4, lf + 1, 1, 1, None)
        m.box(cx + sx, min(cy, cy + sy * ls), z + 4, 1, ls + 1, 1, None)
        m.box(min(cx, cx - sx * (lf - 1)), cy, z + 4, lf, 1, 1, "mortar", only_filled=True)
        m.box(cx, min(cy, cy - sy * (ls - 1)), z + 4, 1, ls, 1, "mortar", only_filled=True)


def lantern(m: Model, cx: int, cy: int, z0: int, *, glass_h: int = 4, lit: bool = True) -> int:
    """5x5 iron lantern standing on z0; returns the z of its top hook."""
    g = "lamp" if lit else "lamp_off"
    m.box(cx - 1, cy - 1, z0, 3, 3, 1, "iron")
    m.box(cx - 2, cy - 2, z0 + 1, 5, 5, 1, "iron")
    m.box(cx - 2, cy - 2, z0 + 2, 5, 5, glass_h, g)
    for dx in (-2, 2):
        for dy in (-2, 2):
            m.box(cx + dx, cy + dy, z0 + 2, 1, 1, glass_h, "iron")
    if not lit:  # unlit lantern reads as a solid dark body with a cross on each face
        m.box(cx - 2, cy, z0 + 2, 5, 1, glass_h, "iron2")
        m.box(cx, cy - 2, z0 + 2, 1, 5, glass_h, "iron2")
        m.box(cx - 2, cy - 2, z0 + 2 + glass_h // 2, 5, 5, 1, "iron2")
    zt = z0 + 2 + glass_h
    m.box(cx - 2, cy - 2, zt, 5, 5, 1, "iron")
    m.box(cx - 1, cy - 1, zt + 1, 3, 3, 1, "iron")
    m.set(cx, cy, zt + 2, "iron")
    return zt + 2


def planter_box(m: Model, x, y, w, d, h):
    m.box(x, y, 0, w, d, h, "stone")
    m.carve(x + 2, y + 2, 2, w - 4, d - 4, h)
    m.box(x + 2, y + 2, 2, w - 4, d - 4, h - 3, "soil")
    m.box(x, y, h - 1, w, d, 1, "trim", only_filled=True)   # coping


def stepped_grooves(m: Model, face_axis: str, fixed: int, a0: int, a1: int, z0: int, amp: int = 3):
    """Zig-zag stair-step relief line painted on a planter face."""
    for a in range(a0, a1):
        tri = abs(((a - a0) // 2) % (2 * amp) - amp)
        if face_axis == "y":
            m.box(a, fixed, z0 + tri, 1, 1, 1, "groove", only_filled=True)
        else:
            m.box(fixed, a, z0 + tri, 1, 1, 1, "groove", only_filled=True)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(100, 68, 82, seed=7)
    palette(m)
    W, D = HX1 - HX0, HY1 - HY0

    # --- body: walls, foundation, attic
    m.shell(HX0, HY0, 0, W, D, EAVE, "wall", t=WALL_T, top=False, bottom=False)
    m.box(HX0, HY0, 0, W, D, FLOOR, "wall")
    roof_fp = (HX0 - 2, HY0 - 2, W - 3 + 2, D + 4)        # roof stops at the right parapet
    m.gable_wall(*roof_fp[:2], EAVE, *roof_fp[2:], "x", "wall", region=(HX0, HY0, W, D))

    # crow-stepped parapet on the right gable end
    px, step = HX1 - 3, 4
    for y in range(HY0 - 2, HY1 + 2):
        dist = min(y - (HY0 - 2), (HY1 + 1) - y)
        top = EAVE + step * (dist // step) + step
        m.box(px, y, EAVE - 3, 3, 1, top - (EAVE - 3), "wall")
        m.box(px - 1, y, top - 1, 5, 1, 1, "trim")
    apex_y = (HY0 - 2 + HY1 + 1) // 2
    apex_top = EAVE + step * (21 // step) + step
    m.box(px, apex_y - 1, apex_top, 3, 3, 2, "trim")
    m.box(px + 1, apex_y, apex_top + 2, 1, 1, 2, "trim")

    m.bricks(["wall", "wall2", "wall3"], target="wall", bw=7, bh=4, p=[0.5, 0.3, 0.2])

    # --- main roof; it drops 7 courses lower over the door section
    m.gable_roof(*roof_fp[:2], EAVE, *roof_fp[2:], "x", PLANKS, t=2)
    for k in range(1, 8):
        m.box(HX0 - 2, HY0 - 2 - k, EAVE - k, 50 - (HX0 - 2), 1, 2, PLANKS[(-k) % len(PLANKS)])

    # --- cornices and fascia
    m.box(HX0 - 1, HY0 - 1, EAVE - 2, 1, D + 2, 2, "trim")          # left eave ledge
    m.box(50, HY0 - 1, EAVE - 2, HX1 - 50, 1, 2, "trim")            # beam over the windows
    m.box(HX0 - 1, HY0 - 1, 0, W + 2, 1, 1, "stone2")               # plinth front
    m.box(HX0 - 1, HY0, 0, 1, D, 1, "stone2")                       # plinth left

    quoins(m, HX0, HY0, -1, -1)
    quoins(m, HX1 - 1, HY0, 1, -1)
    quoins(m, HX0, HY1 - 1, -1, 1)
    quoins(m, HX1 - 1, HY1 - 1, 1, 1)

    # --- interior (hollow, so openings have depth)
    m.carve(HX0 + WALL_T, HY0 + WALL_T, FLOOR, W - 2 * WALL_T, D - 2 * WALL_T, EAVE - FLOOR)

    # --- porch awning: same pitch as the main roof, its top just under the beam;
    #     scalloped front edge right above the door top
    aw_x1 = HX1 + 3
    aw_z = DOOR_TOP + 3
    m.shed_roof(HX0, AW_Y0, aw_z, aw_x1 - HX0, HY0 - AW_Y0, "-y", PLANKS, slope=1.0)
    for x in range(HX0, aw_x1):
        k = (x - HX0) % 5
        if k <= 2:
            m.set(x, AW_Y0, aw_z - 1, "roof")
        if k == 1:
            m.set(x, AW_Y0, aw_z - 2, "roof_dk")

    # --- front door (double, red, glass upper panes)
    dx0, dw, dh = 31, 14, DOOR_TOP - FLOOR
    m.carve(dx0, HY0, FLOOR, dw, WALL_T, dh)
    m.box(dx0 - 1, HY0, FLOOR, 1, 1, dh + 1, "door_frame")
    m.box(dx0 + dw, HY0, FLOOR, 1, 1, dh + 1, "door_frame")
    m.box(dx0 - 1, HY0, FLOOR + dh, dw + 2, 1, 1, "door_frame")
    for lx in (dx0, dx0 + dw // 2):
        lw = dw // 2
        m.box(lx, HY0 + 1, FLOOR, lw, 1, dh, "door")
        for pz in (FLOOR + 8, FLOOR + 14):                      # two glass panes
            m.carve(lx + 1, HY0 + 1, pz, lw - 2, 1, 5)
            m.box(lx + 1, HY0 + 2, pz, lw - 2, 1, 5, "glass")
        m.box(lx + 2, HY0 + 1, FLOOR + 1, lw - 4, 1, 5, "door_dk")  # lower panel inset
    m.box(dx0 + dw // 2 - 1, HY0 + 1, FLOOR, 2, 1, dh, "door_dk")    # meeting stiles
    m.box(dx0 + dw // 2 - 2, HY0, FLOOR + 9, 1, 1, 3, "iron")        # handles
    m.box(dx0 + dw // 2 + 1, HY0, FLOOR + 9, 1, 1, 3, "iron")

    # --- porch platform, stairs, railing
    pl_d = HY0 - PL_Y0
    m.box(HX0, PL_Y0, 0, 32, pl_d, FLOOR, "stone")
    m.box(HX0, PL_Y0, FLOOR - 1, 32, pl_d, 1, "trim")
    st_x, st_w = 29, 18
    for i, h in enumerate((8, 4)):                                   # 12 -> 8 -> 4 -> 0
        sy = PL_Y0 - 4 * (i + 1)
        m.box(st_x, sy, 0, st_w, 4, h, "stone2")
        m.box(st_x, sy, h - 1, st_w, 4, 1, "trim")
    rx = HX0 + 3                                                  # railing near the quoin corner
    m.box(rx, PL_Y0 + 1, FLOOR + 5, 2, pl_d - 2, 1, "iron")          # top rail
    m.box(rx, PL_Y0 + 1, FLOOR, 1, pl_d - 2, 1, "iron2")             # bottom rail
    for y in range(PL_Y0 + 1, HY0 - 1, 3):
        m.box(rx, y, FLOOR, 1, 1, 6, "iron")
    for y in (PL_Y0 + 1, HY0 - 2):
        m.box(rx, y, FLOOR, 2, 1, 7, "iron")                          # end posts

    # --- windows (top aligned with the door top)
    wz = DOOR_TOP - 11
    window(m, "front", 37, wz)     # x 55..63
    window(m, "front", 51, wz)     # x 69..77
    window(m, "back", 14, wz)
    window(m, "back", 46, wz)
    window(m, "right", 16, wz)
    # small attic window on the left gable, centred under the ridge
    gy = (HY0 + HY1) // 2 - 2
    m.carve(HX0, gy, EAVE + 9, 1, 4, 6)
    m.box(HX0 + 1, gy, EAVE + 9, 1, 4, 6, "win_dark")
    m.box(HX0 - 1, gy - 1, EAVE + 8, 1, 6, 1, "trim")

    # --- lanterns
    # left of the door: bracket from the front wall, lantern under the awning
    lx, ly, arm_z = 24, HY0 - 5, DOOR_TOP + 2
    m.box(lx - 1, HY0 - 1, arm_z - 4, 3, 1, 6, "iron")               # wall plate
    m.box(lx, ly, arm_z, 1, HY0 - 1 - ly, 1, "iron")                 # arm
    m.line((lx, HY0 - 2, arm_z - 3), (lx, ly + 2, arm_z), "iron")    # brace
    top = lantern(m, lx, ly, arm_z - 10)
    m.box(lx, ly, top, 1, 1, arm_z - top, "iron")                    # chain
    # right end: bracket from the front-right corner, lantern beyond the corner
    rlx, rly, rarm_z = 90, AW_Y0 + 4, DOOR_TOP
    m.box(HX1 - 2, HY0 - 1, rarm_z - 4, 2, 1, 6, "iron")
    m.box(HX1 - 1, rly, rarm_z, 1, HY0 - 1 - rly, 1, "iron")
    m.box(HX1 - 1, rly, rarm_z, rlx - HX1 + 2, 1, 1, "iron")
    m.line((HX1 - 1, HY0 - 2, rarm_z - 3), (HX1 - 1, rly + 3, rarm_z), "iron")
    top = lantern(m, rlx, rly, rarm_z - 10)
    m.box(rlx, rly, top, 1, 1, rarm_z - top, "iron")
    # big unlit lantern on the left wall, near the back
    bx, by, barm_z = 7, HY1 - 10, EAVE - 6
    m.box(HX0 - 1, by - 1, barm_z - 8, 1, 3, 10, "iron")
    m.box(bx, by, barm_z, HX0 - 1 - bx, 1, 1, "iron")
    m.box(bx - 1, by, barm_z + 1, 4, 1, 1, "iron")
    m.line((HX0 - 2, by, barm_z - 6), (bx + 3, by, barm_z), "iron")
    top = lantern(m, bx, by, barm_z - 14, glass_h=7, lit=False)
    m.box(bx, by, top, 1, 1, barm_z - top, "iron")

    # --- planters (top at about floor level)
    lp_y0, lp_y1 = HY0 + 2, HY1 - 2                   # along the left wall
    planter_box(m, 8, lp_y0, HX0 - 8, lp_y1 - lp_y0, FLOOR)
    rp_y0 = 6                                         # in front of the windows
    planter_box(m, 49, rp_y0, 49, HY0 - 1 - rp_y0, FLOOR + 1)
    stepped_grooves(m, "x", 8, lp_y0 + 2, lp_y1 - 2, 2, amp=2)
    stepped_grooves(m, "y", rp_y0, 51, 96, 2, amp=3)
    stepped_grooves(m, "y", PL_Y0, HX0 + 1, st_x - 1, 2, amp=2)

    # bushes: dense, rising to about the window sills
    for y in range(lp_y0 + 3, lp_y1 - 1, 5):
        m.blob(12.5, y, FLOOR + 2, 4.2, 3.8, 3.8, LEAVES, p=LEAF_P, noise=0.45, density=0.9)
    rp_cy = (rp_y0 + HY0 - 1) / 2
    for x in range(53, 97, 5):
        m.blob(x, rp_cy, FLOOR + 3, 4.6, 5.5, 4.4, LEAVES, p=LEAF_P, noise=0.45, density=0.9)
    m.sprinkle(FLOWERS, 0.13, target=LEAVES, region=(4, lp_y0 - 2, 0, 16, lp_y1 - lp_y0 + 4, 30))
    m.sprinkle(FLOWERS, 0.17, target=LEAVES, region=(46, rp_y0 - 3, 0, 54, HY0 - rp_y0 + 2, 30))

    # vines: climbing the left wall, front-right corner, and draping over planters
    for y0 in (HY0 + 12, HY0 + 18, HY0 + 23):
        m.vine(HX0 - 1, y0, EAVE - 3, EAVE - FLOOR - 3, LEAVES[:3], wall="-x", drift=0.3, leaf=0.95, spread=2)
    m.vine(84, HY0 - 1, EAVE - 3, EAVE - FLOOR - 5, LEAVES[:3], wall="-y", drift=0.3, leaf=0.95, spread=2)
    m.vine(HX1, HY0 + 1, DOOR_TOP, 20, LEAVES[1:], wall="+x", drift=0.3, leaf=0.6)
    for x in (51, 56, 62, 67, 73, 79, 85, 91, 95):
        m.vine(x, rp_y0 - 1, FLOOR + 1, int(m.rng.integers(4, 9)), LEAVES[1:], wall="-y", drift=0.4, leaf=0.7)
    for y in range(lp_y0 + 3, lp_y1, 6):
        m.vine(7, y, FLOOR, int(m.rng.integers(4, 9)), LEAVES[1:], wall="-x", drift=0.4, leaf=0.7)

    return m
