"""Stone cottage with a teal tiled roof — reference/0b0c324b-36f8-4af1-8219-fcf075e98c05.png

Layout (x right, y depth with y=0 front, z up):
  main body    x HX0..HX1, y HY0..HY1, two storeys, walls up to z=EAVE, solid
  main roof    gable, ridge along x, chunky 2x2 tile courses, overhang OH
  front gable  cross-gable over the left WING_W voxels of the front, ridge along y,
               steeper than the main roof so its peak meets the main ridge
  side wing    one storey on the +x side, set back 2 from the front and deeper than
               the main body; lean-to roof falling toward +x. Behind the main body it
               runs EXT_IN voxels further in (that part shows right of the back corner)
  right gable  +x end of the main roof, small window just above the wing roof
  chimney      back-right, stone with a teal cap, a little above the ridge
  front        door in a stone surround under a teal tiled awning on dark brackets,
               three windows with stone sills/lintels; quoins on every visible corner
  walls        stone blocks (bricks texture) + random stones standing 1 proud
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0918"
REFERENCE = "reference/0b0c324b-36f8-4af1-8219-fcf075e98c05.png"
VIEW = {"azimuth": 321, "elevation": 14, "fov": 15}

HX0, HX1 = 4, 68          # main body x range [HX0, HX1)
HY0, HY1 = 8, 48          # main body y range
EAVE = 50                 # first z above the main walls
OH = 2                    # roof overhang
OH_L = 2                  # main roof overhang at the far (-x) gable end
WING_W = 30               # front cross-gable spans x HX0..HX0+WING_W
WING_OH_L = 2             # overhang of its left eave
MAIN_RISE = 2             # rise per 2-voxel tile course of the main roof (skin is 3 thick)
WING_RISE = 2.5           # front gable: steeper, so its peak meets the main ridge
EXT_X1 = HX1 + 16         # side wing x range [HX1, EXT_X1)
EXT_Y0, EXT_Y1 = HY0 + 2, HY1 + 17
EXT_EAVE = 23             # underside of the side-wing roof at its outer edge
EXT_IN = 12               # behind the main body the wing roof runs this far in (-x)
EXT_OH_BACK = 4           # the wing roof overhangs its back wall further
DOOR_X, DOOR_W, DOOR_Z, DOOR_H = HX0 + 17, 12, 3, 18
UP_Z, LOW_Z = 37, 11      # window bottoms (upper / lower storey)
WIN_W, WIN_H = 9, 11

WALLS = ["wall", "wall2", "wall3"]
ROOF = ["roof0", "roof1", "roof2"]


def palette(m: Model):
    # base = reference front sample / 0.9 (preview shades front x0.9, +x side x0.7)
    p = m.pal
    p.add("wall", "#e6d2b8"); p.add("wall2", "#dfcaae"); p.add("wall3", "#ebd9c0")
    p.add("wall_hi", "#eddcc4")
    p.add("quoin", "#ead8bf"); p.add("quoin2", "#e0ccb1"); p.add("mortar", "#bba78c")
    p.add("trim", "#f0e2cb")
    p.add("roof0", "#0e5a65"); p.add("roof1", "#0a4a54"); p.add("roof2", "#156c78")
    p.add("roof_dk", "#06424c")
    p.add("frame", "#2c1e15"); p.add("glass", "#4f5c6c"); p.add("glass_hi", "#6a7788")
    p.add("door", "#5e3820"); p.add("door_dk", "#45281a"); p.add("iron", "#161514")
    p.add("wood", "#4a2c18")


# ---------------------------------------------------------------- helpers

def hash2(a, b, salt=0):
    """Deterministic pseudo-random [0, 1) per integer pair (numpy arrays ok)."""
    h = (np.asarray(a, np.int64) * 73856093) ^ (np.asarray(b, np.int64) * 19349663) ^ (salt * 83492791 + 1)
    return ((h * 2654435761) % (2 ** 32)) / 2 ** 32


def roofs(m: Model):
    """All roofs as one height map: per column the highest of main / front gable /
    side wing wins. Returns (top, thick) maps; the roof occupies z in [top-thick, top)."""
    W, D, H = m.v.shape
    X, Y = np.meshgrid(np.arange(W), np.arange(D), indexing="ij")
    top = np.zeros((W, D), int)
    thick = np.zeros((W, D), int)
    course = np.zeros((W, D), int)
    along = np.zeros((W, D), int)

    def take(mask, t, th, c, a):
        win = mask & (t >= top)
        top[win], thick[win], course[win], along[win] = t[win], th, c[win], a[win]

    # main roof, ridge along x
    main = (X >= HX0 - OH_L) & (X < HX1 + OH) & (Y >= HY0 - OH) & (Y < HY1 + OH)
    dm = np.minimum(Y - (HY0 - OH), (HY1 + OH - 1) - Y)
    take(main, EAVE + MAIN_RISE * (dm // 2) + 3, 3, dm // 2, X)
    # front cross-gable, ridge along y up to the main ridge
    wing = (X >= HX0 - WING_OH_L) & (X < HX0 + WING_W + OH) & (Y >= HY0 - OH) & (Y < (HY0 + HY1) // 2)
    dw = np.minimum(X - (HX0 - WING_OH_L), (HX0 + WING_W + OH - 1) - X)
    take(wing, EAVE + np.floor(WING_RISE * (dw // 2)).astype(int) + 4, 4, dw // 2 + 50, Y)
    # side wing lean-to, falling toward +x
    ext = ((X >= HX1) & (X < EXT_X1 + OH) & (Y >= EXT_Y0 - OH) & (Y < EXT_Y1 + EXT_OH_BACK)) | \
          ((X >= HX1 - EXT_IN) & (X < HX1) & (Y >= HY1) & (Y < EXT_Y1 + EXT_OH_BACK))
    de = (EXT_X1 + OH - 1) - X
    take(ext, EXT_EAVE + 2 * (de // 2) + 3, 3, de // 2 + 100, Y)

    # tiles 4 long, staggered per course, one shade each
    tile = (along + 2 * (course % 2)) // 4
    r = hash2(course, tile, 5)
    shade = np.where(r < 0.45, 0, np.where(r < 0.75, 1, 2))
    shade = np.where((course % 2 == 1) & (shade == 2), 0, shade)
    ids = np.array([m.pal.idx(c) for c in ROOF], np.uint8)[shade]
    Z = np.arange(H)[None, None, :]
    mask = (top[..., None] > 0) & (Z < top[..., None]) & (Z >= (top - thick)[..., None])
    m.v[mask] = np.broadcast_to(ids[..., None], mask.shape)[mask]
    # everything under the top layer is only seen on the course lips: shadow colour
    m.v[mask & (Z < (top - 1)[..., None])] = m.pal.idx("roof_dk")
    return top, thick


def fill_under(m: Model, under, x0, y0, w, d, z0, c):
    """Fills (x0, y0, w, d) from z0 up to the roof underside map `under` (x, y)."""
    under = under[x0:x0 + w, y0:y0 + d]
    Z = np.arange(m.v.shape[2])[None, None, :]
    sub = m.v[x0:x0 + w, y0:y0 + d]
    sub[(Z >= z0) & (Z < under[..., None]) & (sub == 0)] = m.pal.idx(c)


def fbox(m: Model, face: str, u, z, w, h, d0, dd, c, **kw):
    """Box on a wall face. front: plane y=HY0, u = x. right / ext: planes x=HX1-1 /
    x=EXT_X1-1, u = y. d0 = depth into the wall (0 = outer layer, -1 = in front)."""
    if face == "front":
        m.box(u, HY0 + d0, z, w, dd, h, c, **kw)
    else:
        px = HX1 - 1 if face == "right" else EXT_X1 - 1
        m.box(px - d0 - dd + 1, u, z, dd, w, h, c, **kw)


def window(m: Model, face: str, u: int, z: int, w: int = WIN_W, h: int = WIN_H):
    """Dark 2x2 frame recessed 1, slate panes, stone jambs, sill and lintel."""
    fbox(m, face, u - 2, z, 2, h, 0, 1, "trim")                       # jambs
    fbox(m, face, u + w, z, 2, h, 0, 1, "trim")
    fbox(m, face, u, z, w, h, 0, 3, None)                             # opening
    fbox(m, face, u, z, w, h, 1, 1, "frame")
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 1, 1, None)
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, 2, 1, "glass")
    fbox(m, face, u + 1, z + h - 1 - (h - 2) // 2, 2, (h - 2) // 2, 2, 1, "glass_hi")  # glint
    fbox(m, face, u + w // 2, z + 1, 1, h - 2, 1, 1, "frame")         # mullion
    fbox(m, face, u + 1, z + h // 2, w - 2, 1, 1, 1, "frame")         # transom
    fbox(m, face, u - 2, z - 2, w + 4, 2, -1, 2, "trim")              # sill
    fbox(m, face, u - 2, z + h, w + 4, 3, -1, 2, "trim")              # lintel


def quoins(m: Model, cx: int, cy: int, sx: int, sy: int, top: int, row: int = 5):
    """Corner stones standing 1 proud at wall corner (cx, cy); sx/sy = outward."""
    for i, z in enumerate(range(0, top - 2, row)):
        sh = min(row - 1, top - z)
        lf, ls = (8, 5) if i % 2 == 0 else (5, 8)
        col = "quoin" if i % 2 == 0 else "quoin2"
        x0 = cx if sx < 0 else cx - lf + 1
        m.box(x0 + (-1 if sx < 0 else 1), cy + sy, z, lf, 1, sh, col, only_empty=True)
        y0 = cy if sy < 0 else cy - ls + 1
        m.box(cx + sx, y0, z, 1, ls, sh, col, only_empty=True)
        if z + sh < top:   # recessed joint above each stone
            m.box(min(cx, cx - sx * (lf - 1)), cy, z + sh, lf, 1, 1, "mortar", only_filled=True)
            m.box(cx, min(cy, cy - sy * (ls - 1)), z + sh, 1, ls, 1, "mortar", only_filled=True)


def relief(m: Model, face: str, n: int, u0, u1, z0, z1, salt=0):
    """n random stones (3-5 wide, 2 tall) standing 1 proud of a flat wall stretch.
    face '-y' looks from the front, '+x' from the right; only lands on plain wall."""
    occ = m.v > 0
    W = m.v.shape[0]
    if face == "-y":
        depth = np.argmax(occ, axis=1)                       # (x, z)
        has = occ.any(axis=1)
        col = np.take_along_axis(m.v, depth[:, None, :], 1)[:, 0, :]
    else:
        depth = W - 1 - np.argmax(occ[::-1], axis=0)         # (y, z)
        has = occ.any(axis=0)
        col = np.take_along_axis(m.v, depth[None], 0)[0]
    walls = [m.pal.idx(c) for c in WALLS]
    rng = np.random.default_rng(1000 + salt)
    for _ in range(n):
        w, h = int(rng.integers(3, 6)), 2
        u, z = int(rng.integers(u0, u1 - w)), int(rng.integers(z0, z1 - h))
        dd, hh, cc = depth[u:u + w, z:z + h], has[u:u + w, z:z + h], col[u:u + w, z:z + h]
        if not hh.all() or (dd != dd[0, 0]).any() or not np.isin(cc, walls).all():
            continue
        d = int(dd[0, 0])
        if face == "-y" and d > 0:
            m.box(u, d - 1, z, w, 1, h, "wall_hi", only_empty=True)
        elif face == "+x" and d < W - 1:
            m.box(d + 1, u, z, 1, w, h, "wall_hi", only_empty=True)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(EXT_X1 + OH + 2, EXT_Y1 + EXT_OH_BACK + 1, 78, seed=3)
    palette(m)
    W, D = HX1 - HX0, HY1 - HY0

    # --- walls (solid) and roofs; gable / lean-to infill up to the roof underside
    m.box(HX0, HY0, 0, W, D, EAVE, "wall")
    m.box(HX1, EXT_Y0, 0, EXT_X1 - HX1, EXT_Y1 - EXT_Y0, EXT_EAVE, "wall")
    m.box(HX1 - EXT_IN, HY1, 0, EXT_IN, EXT_Y1 - HY1, EXT_EAVE, "wall")
    top, thick = roofs(m)
    under = top - thick
    # the side wing only rises to its own roof, not to the main roof's overhang above it
    ext_under = EXT_EAVE + 2 * (((EXT_X1 + OH - 1) - np.arange(m.v.shape[0])) // 2)
    ext_under = np.minimum(under, ext_under[:, None])
    fill_under(m, under, HX0, HY0, W, D, EAVE, "wall")
    fill_under(m, ext_under, HX1, EXT_Y0, EXT_X1 - HX1, EXT_Y1 - EXT_Y0, 0, "wall")
    fill_under(m, ext_under, HX1 - EXT_IN, HY1, EXT_IN, EXT_Y1 - HY1, 0, "wall")
    m.bricks(WALLS, target="wall", bw=6, bh=3, p=[0.5, 0.25, 0.25])

    # --- chimney (back right, through the back slope)
    cx0, cy0 = HX1 - 10, HY1 - 2
    ct = 72                                                    # top layer of the cap
    m.box(cx0, cy0, EAVE - 6, 6, 6, ct - 2 - (EAVE - 6), "wall2")
    m.bricks(["wall", "wall3", "wall2"], target="wall2", bw=4, bh=2, region=(cx0, cy0, EAVE - 6, 6, 6, 30), salt=4)
    m.box(cx0 - 1, cy0 - 1, ct - 2, 8, 8, 2, "roof_dk")
    m.box(cx0 - 1, cy0 - 1, ct, 8, 8, 1, "roof0")
    m.box(cx0 - 1, cy0 - 1, ct, 4, 4, 1, "roof2")
    m.box(cx0 + 3, cy0 + 3, ct, 4, 4, 1, "roof2")

    # --- windows
    window(m, "front", HX0 + 15, UP_Z)
    window(m, "front", HX0 + 35, UP_Z)
    window(m, "front", HX0 + 41, LOW_Z)
    window(m, "right", HY0 + 13, EAVE - 5, w=7)
    window(m, "ext", EXT_Y0 + 22, LOW_Z - 1)

    # --- door: stone surround, panelled leaf recessed 1, handle, step
    dx, dz = DOOR_X, DOOR_Z
    for i, z in enumerate(range(0, DOOR_H + 3, 4)):
        wl = 3 if i % 2 == 0 else 2
        fbox(m, "front", dx - wl, z, wl, 3, -1, 1, "quoin" if i % 2 else "quoin2")
        fbox(m, "front", dx + DOOR_W, z, wl, 3, -1, 1, "quoin" if i % 2 else "quoin2")
    fbox(m, "front", dx - 3, dz + DOOR_H, DOOR_W + 6, 2, -1, 1, "trim")
    fbox(m, "front", dx, dz, DOOR_W, DOOR_H, -1, 3, None)
    fbox(m, "front", dx, dz, DOOR_W, DOOR_H, 1, 2, "door")
    pw = DOOR_W // 2 - 2
    for px in (dx + 1, dx + DOOR_W // 2 + 1):                 # panel grooves
        for pz, ph in ((dz + 2, 6), (dz + 10, 6)):
            fbox(m, "front", px, pz, pw, ph, 1, 1, "door_dk")
            fbox(m, "front", px + 1, pz + 1, pw - 2, ph - 2, 1, 1, "door")
    fbox(m, "front", dx + DOOR_W // 2 - 1, dz, 2 - DOOR_W % 2, DOOR_H, 1, 1, "door_dk")
    fbox(m, "front", dx + DOOR_W - 2, dz + 8, 1, 2, 0, 1, "iron")
    m.box(dx - 3, HY0 - 2, 0, DOOR_W + 6, 2, dz, "trim")

    # --- quoins
    quoins(m, HX0, HY0, -1, -1, EAVE)
    quoins(m, HX1 - 1, HY0, 1, -1, EAVE)
    quoins(m, EXT_X1 - 1, EXT_Y0, 1, -1, EXT_EAVE + OH)
    quoins(m, EXT_X1 - 1, EXT_Y1 - 1, 1, 1, EXT_EAVE + OH)

    # --- stones standing proud of the plain wall
    relief(m, "-y", 80, HX0 + 1, EXT_X1 - 1, 1, EAVE + 18, salt=1)
    relief(m, "+x", 55, EXT_Y0 + 1, EXT_Y1 - 1, 1, EAVE + 10, salt=2)

    # --- porch awning: three tile courses stepping down to the front, ends turned down
    ax0, ax1 = HX0 + 9, HX0 + 37
    for k in range(3):                                           # k=0 against the wall
        ztop = 31 - 2 * k
        for x in range(ax0, ax1):
            c = ROOF[((x - ax0 + 2 * k) // 4 + k) % 3]
            m.box(x, HY0 - 2 * (k + 1), ztop - 3, 1, 2, 3, c)
    for x in (ax0, ax1 - 1):
        m.box(x, HY0 - 6, 22, 1, 4, 2, "roof1")
    # brackets: dark wooden triangles under both ends
    for bx in (HX0 + 12, HX0 + 32):
        for j in range(5):
            under = 28 - 2 * ((j + 1) // 2)          # awning underside above this slice
            m.box(bx, HY0 - 1 - j, under - (6 - j), 2, 1, 6 - j, "wood")

    return m
