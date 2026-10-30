"""Two-storey stone house, flat teal roof — reference/6239c4cb-1dc9-443f-aa3d-eae4e77d8fca.png

Layout (x right, y depth with y=0 front, z up); the reference looks at the
front-right corner (front face with the door on the image left, right face on
the image right):
  body          x HX0..HX1 (68), y HY0..HY1 (52), walls up to EAVE (48), hollow,
                light sandstone with a running-bond texture and a few raised stones
  quoins        protruding corner stones in 6-voxel courses, long/short alternating
  roof          flat slab overhanging 2 (one 4-voxel cube course), a 4x4 parapet ring
                inset 1 on top, raised corner posts at the two back corners,
                roof surface in 4x4 teal tiles
  front         door (brown, recessed, stone jambs + threshold) under a teal awning on
                two dark wooden brackets; windows upper-left, upper-middle, lower-right
  right side    two stacked windows, centred
  windows       dark brown frame with a cross, grey glass recessed, stone lintel + sill
"""
from voxtool import Model

NAME = "model_1028_0922_2"
REFERENCE = "reference/6239c4cb-1dc9-443f-aa3d-eae4e77d8fca.png"
VIEW = {"azimuth": -42, "elevation": 15, "fov": 18}

C = 4                    # one roof cube
W, D = 73, 51            # body footprint
HX0, HY0 = 4, 10         # body origin (room for overhang, awning, quoins)
HX1, HY1 = HX0 + W, HY0 + D
EAVE = 50                # first z above the walls
WALL_T = 3
OVER = 2                 # roof overhang
SLAB = C                 # roof slab thickness
PARA = 3                 # parapet height
PARA_W = C               # parapet width
POST = 3                 # extra height of the back corner posts
# parapet inset from the slab edge per side: flush on the left/back, a ledge in front
P_IN = {"left": 0, "back": 0, "front": 2, "right": 1}
Q_H = 6                  # quoin course height (5 stone + 1 joint)
Q_OUT = 1                # quoin protrusion (2 sticks out past the reference edges)

WIN_W, WIN_H = 9, 11
UP_Z, LOW_Z = 33, 10     # window bottoms per storey
UP_U = (17, 44)          # upper front windows
LOW_U = 48               # lower front window
DOOR_U, DOOR_W = 22, 10  # door opening on the front face
DOOR_Z, DOOR_TOP = 2, 21
AW_Z = DOOR_TOP + 2      # awning underside
AW_D = 5                 # awning depth


def palette(m: Model):
    # base colours ~ reference samples / preview shading (front x0.9, top x1.0)
    p = m.pal
    p.add("wall", "#f8dfc0"); p.add("wall2", "#f0d5b5"); p.add("wall3", "#fce6ca")
    p.add("stone_hi", "#fde8ce")
    p.add("quoin", "#e0caae"); p.add("quoin2", "#d6bfa3")
    p.add("trim", "#f4dec2"); p.add("trim2", "#e8cfb0")
    p.add("roof", "#106a78"); p.add("roof2", "#0d616e"); p.add("roof3", "#13727f")
    p.add("door", "#5f3420"); p.add("door_dk", "#3e2213")
    p.add("frame", "#2a1a10"); p.add("glass", "#5a6068")
    p.add("wood", "#563019"); p.add("iron", "#1c1b1b")


WALLS = ["wall", "wall2", "wall3"]
ROOFS = ["roof", "roof2", "roof3"]


# ---------------------------------------------------------------- face helper

def fbox(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int, c, **kw):
    """Box relative to a wall face. u = position along the face (left->right seen
    from outside), d0 = depth into the wall (0 = outer layer, -1 = one voxel in
    front of it), dd = thickness inward."""
    if face == "front":
        m.box(HX0 + u, HY0 + d0, z, w, dd, h, c, **kw)
    elif face == "back":
        m.box(HX1 - u - w, HY1 - d0 - dd, z, w, dd, h, c, **kw)
    elif face == "left":
        m.box(HX0 + d0, HY1 - u - w, z, dd, w, h, c, **kw)
    elif face == "right":
        m.box(HX1 - d0 - dd, HY0 + u, z, dd, w, h, c, **kw)


def ledge(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int):
    """Stone band made of C-long blocks in alternating shades."""
    for i, uu in enumerate(range(u, u + w, C)):
        fbox(m, face, uu, z, min(C, u + w - uu), h, d0, dd, "trim" if i % 2 == 0 else "trim2")


def window(m: Model, face: str, u: int, z: int, w: int = WIN_W, h: int = WIN_H):
    """Dark frame with a cross, glass recessed 2, stone lintel and sill."""
    fbox(m, face, u, z, w, h, 0, WALL_T, None)                    # opening
    fbox(m, face, u, z, w, h, 1, 1, "frame")
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 1, 1, None)
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 2, 1, "glass")
    fbox(m, face, u + w // 2, z + 1, 1, h - 2, 1, 1, "frame")     # mullion
    fbox(m, face, u + 1, z + h // 2, w - 2, 1, 1, 1, "frame")     # transom
    ledge(m, face, u - 2, z + h, w + 4, 3, -1, 1)                  # lintel
    ledge(m, face, u - 2, z - 3, w + 4, 3, -1, 1)                  # sill
    ledge(m, face, u - 2, z - 1, w + 4, 1, -2, 1)                  # sill nose


def quoins(m: Model, sx: int, sy: int):
    """Corner stones at the corner on side (sx, sy) (-1 = low side, +1 = high side).
    Each course: a stone on the y-facing wall and one on the x-facing wall, long and
    short alternating, protruding Q_OUT, with a recessed joint on top."""
    x_out = HX0 - Q_OUT if sx < 0 else HX1
    y_out = HY0 - Q_OUT if sy < 0 else HY1
    for i, z in enumerate(range(0, EAVE, Q_H)):
        lf, ls = (7, 5) if i % 2 == 0 else (5, 7)
        col = "quoin" if i % 2 == 0 else "quoin2"
        h = min(Q_H - 1, EAVE - z)
        xs = HX0 - Q_OUT if sx < 0 else HX1 - lf
        m.box(xs, y_out, z, lf + Q_OUT, Q_OUT, h, col)
        ys = HY0 - Q_OUT if sy < 0 else HY1 - ls
        m.box(x_out, ys, z, Q_OUT, ls + Q_OUT, h, col)


def raised_stones(m: Model, face: str, n: int, salt: int):
    """Scatter n slightly protruding stones over the plain parts of a wall face:
    a stone goes only where the wall around it is bare (no openings, ledges, quoins)."""
    rng = m.rng
    wall_ids = {m.pal.idx(c) for c in WALLS}
    span = W if face in ("front", "back") else D
    placed, tries = 0, 0
    while placed < n and tries < n * 40:
        tries += 1
        w, h = int(rng.integers(3, 6)), int(rng.integers(2, 4))
        u, z = int(rng.integers(2, span - w - 2)), int(rng.integers(1, EAVE - h - 1))
        ok = True
        for uu in range(u - 1, u + w + 1):
            for zz in range(z - 1, z + h + 1):
                if face == "front":
                    p_in, p_out = (HX0 + uu, HY0, zz), (HX0 + uu, HY0 - 1, zz)
                else:  # right
                    p_in, p_out = (HX1 - 1, HY0 + uu, zz), (HX1, HY0 + uu, zz)
                if m.get(*p_in) not in wall_ids or m.get(*p_out) != 0:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            fbox(m, face, u, z, w, h, -1, 1, "stone_hi")
            placed += 1


def roof_shades(m: Model):
    """Recolour every roof voxel per 4x4 cube: neighbouring cubes alternate between
    two close teals (a third one sprinkled in), so slab, parapet and tiles read as
    separate cubes."""
    ids = [m.pal.idx(c) for c in ROOFS]
    roof_ids = set(ids)
    sx, sy, sz = m.size
    for x in range(sx):
        for y in range(sy):
            for z in range(EAVE - 1, sz):
                if m.v[x, y, z] in roof_ids:
                    band = 0 if z < EAVE + SLAB else 1 + (z - EAVE - SLAB) // C
                    cx, cy = (x - HX0 + OVER) // C, (y - HY0 + OVER) // C
                    hsh = (cx * 73856093) ^ (cy * 19349663) ^ (band * 83492791)
                    k = 2 if (hsh >> 3) % 5 == 0 else (cx + cy + band) % 2
                    m.v[x, y, z] = ids[k]


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(HX1 + 4, HY1 + 4, EAVE + SLAB + PARA + POST + 2, seed=11)
    palette(m)

    # --- body
    m.shell(HX0, HY0, 0, W, D, EAVE, "wall", t=WALL_T, top=False, bottom=True)
    m.bricks(WALLS, target="wall", bw=8, bh=4, p=[0.55, 0.25, 0.2])

    # --- roof: slab with overhang, parapet ring, back corner posts
    rx0, ry0 = HX0 - OVER, HY0 - OVER
    rw, rd = W + 2 * OVER, D + 2 * OVER
    m.box(rx0, ry0, EAVE, rw, rd, SLAB, "roof")
    pz = EAVE + SLAB
    px0, py0 = rx0 + P_IN["left"], ry0 + P_IN["front"]
    px1, py1 = rx0 + rw - P_IN["right"], ry0 + rd - P_IN["back"]
    m.box(px0, py0, pz, px1 - px0, py1 - py0, PARA, "roof")
    m.carve(px0 + PARA_W, py0 + PARA_W, pz, px1 - px0 - 2 * PARA_W, py1 - py0 - 2 * PARA_W, PARA)
    for px in (px0, px1 - PARA_W):
        m.box(px, py1 - PARA_W, pz + PARA, PARA_W, PARA_W, POST, "roof")
    roof_shades(m)

    # --- quoins on all four corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            quoins(m, sx, sy)

    # --- windows
    for face, us in (("front", UP_U), ("back", UP_U),
                     ("right", ((D - WIN_W) // 2,)), ("left", ((D - WIN_W) // 2,))):
        for u in us:
            window(m, face, u, UP_Z)
    window(m, "front", LOW_U, LOW_Z)
    window(m, "right", (D - WIN_W) // 2, LOW_Z)
    window(m, "back", UP_U[0], LOW_Z)
    window(m, "left", (D - WIN_W) // 2, LOW_Z)

    # --- door: recessed planks, stone jambs, threshold
    dh = DOOR_TOP - DOOR_Z
    fbox(m, "front", DOOR_U, DOOR_Z, DOOR_W, dh, 0, WALL_T, None)
    fbox(m, "front", DOOR_U, DOOR_Z, DOOR_W, dh, 1, 1, "door")
    fbox(m, "front", DOOR_U, DOOR_Z, 1, dh, 1, 1, "door_dk")
    fbox(m, "front", DOOR_U + DOOR_W - 1, DOOR_Z, 1, dh, 1, 1, "door_dk")
    fbox(m, "front", DOOR_U, DOOR_TOP - 1, DOOR_W, 1, 1, 1, "door_dk")
    for pz0, ph in ((DOOR_Z + 2, 6), (DOOR_Z + 10, 6)):              # two panel insets
        fbox(m, "front", DOOR_U + 2, pz0, DOOR_W - 4, ph, 1, 1, "door_dk")
        fbox(m, "front", DOOR_U + 3, pz0 + 1, DOOR_W - 6, ph - 2, 1, 1, "door")
    fbox(m, "front", DOOR_U + DOOR_W - 3, DOOR_Z + 8, 1, 2, 0, 1, "iron")   # knob
    for i, z in enumerate(range(DOOR_Z, DOOR_TOP, 3)):                 # jambs
        lw = 3 if i % 2 == 0 else 2
        c = "trim" if i % 2 == 0 else "trim2"
        fbox(m, "front", DOOR_U - lw, z, lw, 3, -1, 1, c)
        fbox(m, "front", DOOR_U + DOOR_W, z, lw, 3, -1, 1, c)
    ledge(m, "front", DOOR_U - 3, 0, DOOR_W + 6, DOOR_Z, -2, 2)         # threshold

    # --- awning: two tiers of teal cubes on dark wooden brackets
    aw_u0, aw_w = DOOR_U - 12, 8 * C        # reaches further left of the door than right
    fbox(m, "front", aw_u0, AW_Z, aw_w, C + 1, -2, 2, "roof")            # back tier
    fbox(m, "front", aw_u0, AW_Z, aw_w, C, -AW_D, AW_D - 2, "roof")      # front tier
    for i, uu in enumerate(range(aw_u0, aw_u0 + aw_w, C)):
        c = ROOFS[i % 3]
        fbox(m, "front", uu, AW_Z, C, C + 1, -AW_D, AW_D, c, only_filled=True)
    for bu in (aw_u0 + 1, aw_u0 + aw_w - 4):
        fbox(m, "front", bu, AW_Z - 6, 3, 6, -2, 2, "wood")              # post on the wall
        fbox(m, "front", bu, AW_Z - 2, 3, 2, -AW_D + 1, AW_D - 1, "wood")  # arm

    # --- relief stones on the bare wall
    raised_stones(m, "front", 12, 1)
    raised_stones(m, "right", 9, 2)

    # --- hollow interior so the openings have depth
    m.carve(HX0 + WALL_T, HY0 + WALL_T, 1, W - 2 * WALL_T, D - 2 * WALL_T, EAVE - 1)
    return m
