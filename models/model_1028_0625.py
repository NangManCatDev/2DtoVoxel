"""Stone gateway — reference/9e3b4c5c-2ca6-4c6c-aef4-b6ef7f479c18.png

Layout (x right, y depth with y=0 front, z up; one visible stone cube = C = 2 voxels):
  body      BW x BD x BH block of mixed cream / tan / grey ashlar (1-cube stones,
            2-cube stones and some big 2x2-cube blocks)
  plinth    bottom course protrudes 1 voxel all round
  quoins    every other 2-cube course protrudes 1 at the four vertical corners
  passage   OPEN_W wide straight through (along y), floor of grey 1-cube tiles
            flush with the ground; the back opening is NARROW narrower on each side,
            so its jambs show through the front arch
  arch      pilaster jambs with bases, stepped segmental voussoir band,
            trapezoid keystone that drops a voxel below the crown
  slab      capping slab overhanging OV on all sides, taller corner blocks,
            cream edge stones and grey stones on top
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1028_0625"
REFERENCE = "reference/9e3b4c5c-2ca6-4c6c-aef4-b6ef7f479c18.png"
VIEW = {"azimuth": -32, "elevation": 22, "fov": 25}

C = 2                    # voxels per visible stone cube
M = 4                    # margin around the body (overhang, caps, protrusions)
APRON = 6                # floor tiles continuing behind the back opening
BW, BD, BH = 46, 22, 40  # body size; the slab starts at z = BH
BX0, BY0 = M, M
BX1, BY1 = BX0 + BW, BY0 + BD
PLINTH = 4
OPEN_W = 20
PX0 = BX0 + (BW - OPEN_W) // 2
PX1 = PX0 + OPEN_W
JAMB_W, JAMB_P = 3, 2    # pilaster width / protrusion
SPRING, CROWN = 26, 32   # arch springing height / underside of the crown
ARCH_T = 4               # voussoir band thickness
NARROW = 2               # back opening is this much narrower on each side
BACK_T = 3               # depth of that narrower back section
OV = 2                   # slab overhang
SLAB_T = 3

WALL = ["cream", "cream2", "tan", "tan2", "grey", "grey2"]
WALL_P = [0.48, 0.30, 0.07, 0.03, 0.08, 0.04]       # small stones: mostly plain cream
BIG_P = [0.15, 0.10, 0.30, 0.10, 0.22, 0.13]        # big blocks: the tan / grey accents
TOP_EDGE = ["top_cream", "top_cream2", "top_grey"]
TOP_EDGE_P = [0.5, 0.3, 0.2]
TOP_IN = ["top_grey", "top_grey2", "top_grey3"]
TOP_IN_P = [0.4, 0.3, 0.3]
INNER = ["in1", "in2", "in3", "grey2"]
INNER_P = [0.35, 0.3, 0.2, 0.15]
FLOOR = ["floor", "floor2", "floor3"]
ARCH = ["arch", "arch2", "cream2"]


def palette(m: Model):
    # front faces render x0.9, the right side x0.7, tops x1.0
    p = m.pal
    p.add("wall", "#f3dcc0")
    p.add("cream", "#fbe4c8"); p.add("cream2", "#f2dbbf")
    p.add("tan", "#f7d6ab"); p.add("tan2", "#eccb9e")
    p.add("grey", "#d3c0b0"); p.add("grey2", "#c6b4a7")
    # passage walls sit in shadow in the reference: greyer, darker stones
    p.add("in1", "#bca897"); p.add("in2", "#ae9b8b"); p.add("in3", "#cab6a2")
    p.add("arch", "#fde6c8"); p.add("arch2", "#f8d8a8"); p.add("key", "#fbdcaa")
    p.add("top_cream", "#ddc6aa"); p.add("top_cream2", "#d5bea4")
    p.add("top_grey", "#cbbcaf"); p.add("top_grey2", "#c2b4a9"); p.add("top_grey3", "#d4c6ba")
    p.add("floor", "#a2938a"); p.add("floor2", "#978981"); p.add("floor3", "#ac9e94")


# ---------------------------------------------------------------- hashing / textures

def _mix(*arrs, salt=0):
    """Deterministic per-cell random number in [0, 1) from integer coordinates."""
    arrs = np.broadcast_arrays(*[np.atleast_1d(np.asarray(a, np.int64)) for a in arrs])
    h = np.full(arrs[0].shape, salt * 0x9E3779B1 + 0x85EBCA6B, np.uint64)
    with np.errstate(over="ignore"):   # wrap-around multiply is the point
        for a in arrs:
            h = (h ^ (a + 4096).astype(np.uint64)) * np.uint64(0x100000001B3)
            h ^= h >> np.uint64(29)
        h = h * np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(31)
    return (h % np.uint64(1 << 24)).astype(np.float64) / (1 << 24)


def _pick(m: Model, h, colors, p):
    cum = np.cumsum(p) / np.sum(p)
    lut = np.array([m.pal.idx(c) for c in colors], np.uint8)
    return lut[np.searchsorted(cum, h, side="right").clip(0, len(colors) - 1)]


def _course_hash(U, V, salt, big_p=0.14):
    """Random value per stone on a face with along-coordinate U and course
    coordinate V: running bond of 2-cube stones, some split into 1-cube stones,
    and some big 2x2-cube blocks laid over them. Returns (value, is_big)."""
    row = V // C
    off = (row % 2) * C
    c2 = (U + off) // (2 * C)
    c1 = (U + off) // C
    split = _mix(row, c2, salt=salt) < 0.4
    h = _mix(row, np.where(split, c1, c2 * 2 + 100000), salt=salt + 1)
    brow = V // (2 * C)
    bc = (U + (brow % 2) * C) // (2 * C)
    big = _mix(brow, bc, salt=salt + 2) < big_p
    return np.where(big, _mix(brow, bc, salt=salt + 3), h), big


def paint_stones(m: Model, colors, p, *, big=None, target="wall", salt=0, region=None, top=False):
    """Recolors `target` voxels stone by stone. Vertical faces use U = x + y
    (wraps around corners like bricks()), top=True lays the stones out in x/y.
    big = (colors, p) for the big 2x2-cube blocks (default: same as the small ones)."""
    tgt = [m.pal.idx(t) for t in ([target] if isinstance(target, str) else target)]
    region = region or (0, 0, 0) + m.v.shape
    bcol, bp = big or (colors, p)

    def fn(X, Y, Z):
        h, is_big = _course_hash(X, Y, salt) if top else _course_hash(X + Y, Z, salt)
        col = np.where(is_big, _pick(m, h, bcol, bp), _pick(m, h, colors, p))
        return np.where(np.isin(m.v[X, Y, Z], tgt), col, 0).astype(np.uint8)

    m.paint_fn(*region, fn)


def paint_tiles(m: Model, region, colors, salt=0):
    """1-cube floor tiles with a random shade each, on voxels with nothing above."""
    def fn(X, Y, Z):
        col = _pick(m, _mix(X // C, Y // C, salt=salt), colors, [0.4, 0.35, 0.25])
        return np.where(m.v[X, Y, Z + 1] == 0, col, 0).astype(np.uint8)
    m.paint_fn(*region, fn)


# ---------------------------------------------------------------- arch

def arch_masks(X, Z, x0, x1):
    """(opening, band, outer) masks in the x/z plane for an opening [x0, x1):
    vertical jambs up to SPRING, then a semi-elliptic top reaching CROWN. The curve
    is tested at stone-cube centres, so it steps a whole cube at a time."""
    cx, hw, rise = (x0 + x1) / 2, (x1 - x0) / 2, CROWN - SPRING
    qx = x0 + ((X - x0) // C) * C + C / 2
    qz = SPRING + ((Z - SPRING) // C) * C + C / 2
    dx, dz = qx - cx, np.maximum(qz - SPRING, 0)
    opening = ((dx / hw) ** 2 + (dz / rise) ** 2 < 1) & (Z >= 1)
    e_out = (dx / (hw + ARCH_T)) ** 2 + (dz / (rise + ARCH_T)) ** 2
    e_mid = (dx / (hw + ARCH_T - 1.5)) ** 2 + (dz / (rise + ARCH_T - 1.5)) ** 2
    band = (e_out < 1) & ~opening & (Z >= SPRING - 2)
    return opening, band, band & (e_mid >= 1)


def _layers(y_face, out, n):
    """(y start, depth) of the n voxel layers standing out of the wall whose
    outermost layer is y_face; out = -1 for the front, +1 for the back."""
    return (y_face - n, n) if out < 0 else (y_face + 1, n)


def arch_face(m: Model, x0, x1, y_face, out, proud=JAMB_P):
    """Voussoir band + keystone in front of the wall layer y_face. The inner ring
    stands out `proud` (like the jambs), the stepped outer ring 1."""
    cx, hw, rise = (x0 + x1) / 2, (x1 - x0) / 2, CROWN - SPRING
    xs = np.arange(x0 - ARCH_T - 1, x1 + ARCH_T + 1)
    zs = np.arange(SPRING - 2, CROWN + ARCH_T + 1)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    _, band, outer = arch_masks(X, Z, x0, x1)
    theta = np.arctan2(np.maximum(Z + 0.5 - SPRING, 1e-3) / rise, (X + 0.5 - cx) / hw)
    stone = np.floor(np.clip(theta, 0, math.pi - 1e-6) / (math.pi / 9)).astype(int)
    col = _pick(m, _mix(stone, out, salt=11), ARCH, [0.45, 0.35, 0.2])
    for (i, k), on in np.ndenumerate(band):
        if on:
            y, n = _layers(y_face, out, 1 if outer[i, k] else proud)
            m.box(int(xs[i]), y, int(zs[k]), 1, n, 1, int(col[i, k]))
    # keystone: trapezoid hanging 1 below the crown, standing out one more
    kx = int(round(cx))
    y, n = _layers(y_face, out, proud + 1)
    for z in range(CROWN - 1, CROWN + 6):
        half = 2 + (z - (CROWN - 1)) // 4
        m.box(kx - half, y, z, 2 * half, n, 1, "key")


def jambs(m: Model, x0, x1, y_face, out):
    """Pilasters either side of the opening [x0, x1), with a wider base block.
    Returns the pilaster shaft boxes (including the jamb's inner face layer)."""
    shafts = []
    for xa, bx in ((x0 - JAMB_W, x0 - JAMB_W - 1), (x1, x1)):
        y, n = _layers(y_face, out, JAMB_P)
        m.box(xa, y, 0, JAMB_W, n, SPRING, "wall")
        shafts.append((xa, y, 5, JAMB_W, n + 1, SPRING - 5))
        y, n = _layers(y_face, out, JAMB_P + 1)
        m.box(bx, y, 0, JAMB_W + 1, n, 5, "wall")
    return shafts


# ---------------------------------------------------------------- build

def quoin_boxes():
    """Protruding corner stones: every other 2-cube course, both faces of each corner."""
    L = 2 * C
    out = []
    for k, z in enumerate(range(PLINTH, BH - 2, 2 * C)):
        if k % 2:
            continue
        for sx in (-1, 1):
            for sy in (-1, 1):
                x0 = BX0 - 1 if sx < 0 else BX1 - L
                y0 = BY0 - 1 if sy < 0 else BY1 - L
                yf = BY0 - 1 if sy < 0 else BY1
                xf = BX0 - 1 if sx < 0 else BX1
                out.append((x0, yf, z, L + 1, 1, 2 * C))
                out.append((xf, y0, z, 1, L + 1, 2 * C))
    return out


def build() -> Model:
    m = Model(BW + 2 * M, BD + M + APRON, BH + SLAB_T + 2, seed=5)
    palette(m)

    # --- masses
    m.box(BX0, BY0, 0, BW, BD, BH, "wall")
    m.box(BX0 - 1, BY0 - 1, 0, BW + 2, BD + 2, PLINTH, "wall")
    quoins = quoin_boxes()
    for q in quoins:
        m.box(*q, "wall")
    bx0, bx1 = PX0 + NARROW, PX1 - NARROW
    pilasters = jambs(m, PX0, PX1, BY0, -1)

    # --- capping slab with taller corner blocks
    sx0, sy0, sw, sd = BX0 - OV, BY0 - OV, BW + 2 * OV, BD + 2 * OV
    m.box(sx0, sy0, BH, sw, sd, SLAB_T, "wall")
    caps = []
    for cx in (sx0, sx0 + sw - 5):
        for cy in (sy0, sy0 + sd - 5):
            caps.append((cx, cy, BH - 1, 5, 5, SLAB_T + 2))
            m.box(*caps[-1], "wall")

    # --- passage (floor layer z=0 stays), wide at the front, narrower at the back
    W, D, H = m.v.shape
    X, Z = np.meshgrid(np.arange(W), np.arange(H), indexing="ij")
    open_front, _, _ = arch_masks(X, Z, PX0, PX1)
    open_back, _, _ = arch_masks(X, Z, bx0, bx1)
    for y in range(D):
        sl = m.v[:, y, :]
        sl[open_back if y >= BY1 - BACK_T else open_front] = 0
    # the back narrowing reads like a pilaster from inside: base block at its foot
    nb = BY1 - BACK_T - 1
    m.box(PX0, nb, 0, NARROW + 1, 1, 5, "wall")
    m.box(bx1 - 1, nb, 0, NARROW + 1, 1, 5, "wall")

    # --- stone texture, then the elements that read as single stones
    paint_stones(m, WALL, WALL_P, big=(WALL, BIG_P), salt=1)
    for b in pilasters:             # pilasters: light stones, one per 2-voxel course
        for z in range(b[2], b[2] + b[5], C):
            col = int(_pick(m, _mix(b[0], z, salt=31), ARCH, [0.45, 0.35, 0.2])[0])
            m.box(b[0], b[1], z, b[3], b[4], C, col, only_filled=True)
    for x in (PX0 - 1, PX1):        # shadowed passage walls
        paint_stones(m, INNER, INNER_P, target=WALL, salt=3, region=(x, BY0 + 1, 1, 1, nb - BY0 - 1, BH))
    for i, q in enumerate(quoins + caps):
        m.box(*q, int(_pick(m, _mix(i, salt=21), WALL, WALL_P)[0]), only_filled=True)
    top_layer(m, sx0, sy0, sw, sd, BH + SLAB_T - 1)

    # --- arches and keystones on both faces (the back one flatter, no pilasters)
    arch_face(m, PX0, PX1, BY0, -1)
    arch_face(m, bx0, bx1, BY1 - 1, 1, proud=1)

    # --- floor tiles through the passage, out to the jamb bases on both sides
    m.box(PX0, BY0 - JAMB_P - 1, 0, OPEN_W, BD + JAMB_P + 1 + APRON, 1, "floor", only_empty=True)
    paint_tiles(m, (PX0, 0, 0, OPEN_W, D, 1), FLOOR)
    return m


def top_layer(m: Model, x0, y0, w, d, z0):
    """Recolors the exposed tops of the slab and corner blocks: cream stones along
    the edge ring, greyer stones inside (tops render brighter than the reference)."""
    sub = m.v[x0:x0 + w, y0:y0 + d, z0:]
    exposed = sub > 0
    exposed[:, :, :-1] &= sub[:, :, 1:] == 0
    X, Y = np.meshgrid(np.arange(x0, x0 + w), np.arange(y0, y0 + d), indexing="ij")
    edge = (X < x0 + C) | (X >= x0 + w - C) | (Y < y0 + C) | (Y >= y0 + d - C)
    h, _ = _course_hash(X, Y, 7, big_p=0.0)
    col = np.where(edge, _pick(m, h, TOP_EDGE, TOP_EDGE_P), _pick(m, h, TOP_IN, TOP_IN_P))
    sub[exposed] = np.broadcast_to(col[:, :, None], sub.shape)[exposed]
