"""Stone bench, wooden barrel and two capped stone posts — reference/a3441cb3-1f83-4468-b60f-8728a3c5723c.png

Kit sheet, four separate objects (m.part), laid out so the camera sees them in a row
like the reference (x right-down on screen, y right-up, camera at the +x/-y corner).
Measured from the reference at ~6 px per voxel.

  bench     length along x (BENCH_L). Two stone legs: plinth (blocks, staggered) /
            middle (two courses) / top slab; the seat (3 planks + aprons + end cleats
            with bolts) spans between the legs, its top SEAT_TOP below the leg tops.
  barrel    round, slightly bulged (BR_END -> BR_MID), staves with dark seams, two iron
            hoops with rivets, recessed plank lid inside a rim of stave ends, iron tap on
            the screen-left side (pointing -y).
  pillar_a/b  stone base (3x3 staggered blocks) / shaft (two courses) / dark slate cap
            (two slabs).

Stone pieces are built from blocks (stone_block); seams() darkens one voxel row where two
blocks meet and mottle() gives the stone its blotchy texture.
"""
import numpy as np

from voxtool import Model

NAME = "a3441cb3_1f83_4468_b60f_8728a3c5723c"
REFERENCE = "reference/a3441cb3-1f83-4468-b60f-8728a3c5723c.png"
VIEW = {"azimuth": 317, "elevation": 31, "fov": 0}
CUTOUT = {"keep": "all"}

# ---------------------------------------------------------------- dimensions
# bench (local coords, x along the bench)
BENCH_O = (1, 1)            # world x, y of the bench's min corner
BENCH_L = 113               # total length (both plinths included)
LEG_L = 21                  # plinth length along x
BENCH_W = 35                # plinth width along y
PLINTH_H = 8
MID_H = 21                  # middle courses
SLAB_H = 5
LEG_H = PLINTH_H + MID_H + SLAB_H   # 34
SEAT_TOP = 29               # top of the seat planks
PLANK_T = 3                 # plank thickness
APRON_B = 20                # bottom of the side aprons

# the other pieces are placed relative to the bench's front-bottom corner
# (x = BENCH_O x + BENCH_L, y = BENCH_O y), measured on the reference
FRONT = (BENCH_O[0] + BENCH_L, BENCH_O[1])

# barrel
BARREL_C = (FRONT[0] + 30.0, FRONT[1] + 76.0)   # centre
BARREL_H = 45
BR_END, BR_MID = 20.5, 21.5  # radius at the ends / at mid height
RIM = 3                     # rim (stave ends) width
LID_DROP = 3                # lid below the rim top
HOOPS = [(8, 5), (33, 5)]   # (z, height)
STAVES = 14

# pillars: (x, y) of the min corner; measured as their front-bottom corner (x max, y min)
P_BASE, P_BASE_H = 24, 9
PILLARS = {"pillar_a": (FRONT[0] + 88 - P_BASE, FRONT[1] + 115),
           "pillar_b": (FRONT[0] + 139 - P_BASE, FRONT[1] + 125)}
GRID = (FRONT[0] + 141, FRONT[1] + 125 + P_BASE + 2, 50)
P_SHAFT, P_SHAFT_H = 18, 25
P_CAP, P_CAP_H = 20, 7


def palette(m: Model):
    p = m.pal
    # stone: reference top #d4ccbf, -Y faces ~#c0b6a8 / 0.9
    p.add("st0", "#d3cabc"); p.add("st1", "#cac0b1"); p.add("st2", "#bfb4a4")
    p.add("st3", "#a8a29c"); p.add("st4", "#928d8b")
    p.add("seam", "#6e655c")
    # slate caps: top #475357, sides darker
    p.add("cap_top", "#4b585c"); p.add("cap_hi", "#5e777b"); p.add("cap_lo", "#3f4b4f")
    p.add("cap_side", "#3a454a"); p.add("cap_seam", "#22292c")
    # seat wood: top #6e564c, side #71513e / 0.9
    p.add("plank0", "#70584d"); p.add("plank1", "#7b6152"); p.add("plank2", "#644e45")
    p.add("plank_hi", "#87695a")
    p.add("plank_side", "#7c5944"); p.add("apron", "#785542"); p.add("cleat", "#5a3f31")
    p.add("wood_gap", "#2c221e")
    # barrel wood: staves #815e48 / 0.9
    p.add("stave0", "#8a644d"); p.add("stave1", "#7e5b46"); p.add("stave2", "#94705a")
    p.add("stave3", "#73523f"); p.add("stave_seam", "#3b2b23")
    p.add("rim_top", "#90705b"); p.add("lid0", "#76594c"); p.add("lid1", "#6c5145")
    p.add("lid2", "#806254")
    # iron
    p.add("iron", "#3c4549"); p.add("rivet", "#5f6e73"); p.add("bolt", "#2d3236")
    p.add("tap", "#405057"); p.add("tap_hi", "#5a7178")


# ---------------------------------------------------------------- stone helpers

class Stone:
    """Block bookkeeping: each stone_block gets an id so seams() can find where blocks meet."""

    def __init__(self, m: Model):
        self.m = m
        self.ids = np.zeros(m.v.shape, np.int32)
        self.next = 1

    def block(self, x, y, z, w, d, h, c=None):
        """Solid stone block; without c it gets a random tint (st0..st2) of its own."""
        if c is None:
            c = TINTS[self.m.rng.choice(len(TINTS), p=[0.35, 0.45, 0.2])]
        self.m.box(x, y, z, w, d, h, c)
        self.ids[max(x, 0):x + w, max(y, 0):y + d, max(z, 0):z + h] = self.next
        self.next += 1


def _shift(a, axis, s):
    out = np.zeros_like(a)
    if s > 0:
        sl_dst = [slice(None)] * 3; sl_dst[axis] = slice(0, -s)
        sl_src = [slice(None)] * 3; sl_src[axis] = slice(s, None)
    else:
        sl_dst = [slice(None)] * 3; sl_dst[axis] = slice(-s, None)
        sl_src = [slice(None)] * 3; sl_src[axis] = slice(0, s)
    out[tuple(sl_dst)] = a[tuple(sl_src)]
    return out


def seams(m: Model, ids, colors, seam):
    """One voxel row of `seam` where two different blocks of `colors` meet."""
    stone = np.isin(m.v, [m.pal.idx(c) for c in colors]) & (ids > 0)
    mark = np.zeros_like(stone)
    for axis in range(3):
        nb = _shift(ids, axis, 1)
        mark |= stone & (nb > 0) & (nb != ids)
    m.v[mark] = m.pal.idx(seam)


def stone_texture(m: Model, *, noise=0.3, spot_p=0.12):
    """Keeps each block's tint but shifts single voxels one shade lighter/darker, then
    adds grey blotches (whole 2x2x2 cells)."""
    lut = np.array([m.pal.idx(c) for c in TINTS])
    stone = np.isin(m.v, lut)
    lvl = np.argmax(m.v[..., None] == lut, axis=-1)
    step = m.rng.choice([-1, 0, 1], size=m.v.shape, p=[noise / 2, 1 - noise, noise / 2])
    m.v[stone] = lut[np.clip(lvl + step, 0, len(lut) - 1)][stone]
    mottle(m, TINTS, None, target=TINTS, spots=["st3", "st4"], spot_p=spot_p, vary=False)


def mottle(m: Model, colors, p, *, target, spots=None, spot_p=0.12, cell=2, region=None, vary=True):
    """Per-voxel colour from `colors` (weights p) plus blotches: `spots` colours painted
    on whole cell^3 cells with probability spot_p."""
    if vary:
        m.vary(colors, target=target, p=p, region=region)
    if not spots:
        return
    W, D, H = m.v.shape
    cells = m.rng.random((W // cell + 1, D // cell + 1, H // cell + 1))
    X, Y, Z = np.indices(m.v.shape)
    blot = cells[X // cell, Y // cell, Z // cell] < spot_p
    tgt = np.isin(m.v, [m.pal.idx(c) for c in colors])
    if region:
        x, y, z, w, d, h = region
        box = np.zeros_like(tgt)
        box[x:x + w, y:y + d, z:z + h] = True
        tgt &= box
    pick = m.rng.choice([m.pal.idx(c) for c in spots], size=m.v.shape)
    sel = tgt & blot & (m.rng.random(m.v.shape) < 0.75)
    m.v[sel] = pick[sel]


# ---------------------------------------------------------------- bench

def grain(m: Model, region, colors, p, *, target, seg=(4, 14)):
    """Wood grain along x: every (y, z) row is cut into runs of random length, each run
    one colour from `colors` (weights p). Only recolours voxels of `target`."""
    x, y, z, w, d, h = region
    lut = np.array([m.pal.idx(c) for c in colors], np.uint8)
    tgt = [m.pal.idx(c) for c in target]
    off = m.rng.integers(0, 64, size=(d, h))
    run = m.rng.integers(seg[0], seg[1], size=(d, h))
    cum = np.cumsum(p) / np.sum(p)

    def fn(X, Y, Z):
        yy, zz = Y - y, Z - z
        k = (X + off[yy, zz]) // run[yy, zz]
        hsh = ((k * 73856093) ^ (yy * 19349663) ^ (zz * 83492791)) % 1009 / 1009.0
        col = lut[np.searchsorted(cum, hsh, side="right").clip(0, len(lut) - 1)]
        return np.where(np.isin(m.v[X, Y, Z], tgt), col, 0)
    m.paint_fn(x, y, z, w, d, h, fn)


def bench_leg(st: Stone, x0, y0):
    """One stone leg; (x0, y0) = min corner of its plinth."""
    m = st.m
    # plinth: 2 x 3 blocks, some set back one voxel from the outside
    xs = [0, 10, LEG_L]
    ys = [0, 12, 23, BENCH_W]
    inset = [[(0, 1), (1, 0), (0, 0)], [(0, 0), (1, 0), (0, 1)]]
    for i in range(2):
        for j in range(3):
            ix, iy = inset[i][j]
            bx0, bx1 = xs[i] + (ix if i == 0 else 0), xs[i + 1] - (ix if i == 1 else 0)
            by0 = ys[j] + (iy if j == 0 else 0)
            by1 = ys[j + 1] - (iy if j == 2 else 0)
            st.block(x0 + bx0, y0 + by0, 0, bx1 - bx0, by1 - by0, PLINTH_H)
    # middle: two courses with staggered joints
    mx0, mx1, my0, my1 = 3, LEG_L - 3, 2, BENCH_W - 2
    z1 = PLINTH_H + 11
    for a, b in ((my0, 18), (18, my1)):
        st.block(x0 + mx0, y0 + a, PLINTH_H, mx1 - mx0, b - a, z1 - PLINTH_H)
    for a, b in ((my0, 11), (11, 25), (25, my1)):
        st.block(x0 + mx0, y0 + a, z1, mx1 - mx0, b - a, PLINTH_H + MID_H - z1)
    # top slab: two blocks, overhanging the middle by one voxel
    zs = PLINTH_H + MID_H
    for a, b in ((1, 15), (15, BENCH_W - 1)):
        st.block(x0 + 2, y0 + a, zs, LEG_L - 4, b - a, SLAB_H)


def bench(m: Model, st: Stone):
    bx, by = BENCH_O
    bench_leg(st, bx, by)
    bench_leg(st, bx + BENCH_L - LEG_L, by)
    sx0, sx1 = bx + LEG_L - 3, bx + BENCH_L - LEG_L + 3     # seat ends sit against the middles
    sy0, sy1 = by + 3, by + BENCH_W - 2
    zt = SEAT_TOP - PLANK_T
    # aprons (set back one voxel under the planks) + two cross battens
    for y in (sy0 + 1, sy1 - 4):
        m.box(sx0, y, APRON_B, sx1 - sx0, 3, zt - APRON_B, "apron")
    for x in (sx0 + 20, sx1 - 23):
        m.box(x, sy0 + 1, zt - 3, 3, sy1 - sy0 - 2, 3, "apron")
    # three top planks with dark gaps
    w = sy1 - sy0
    cuts = [sy0, sy0 + w // 3, sy0 + 2 * w // 3, sy1]
    for i in range(3):
        a, b = cuts[i] + (1 if i else 0), cuts[i + 1]
        m.box(sx0, a, zt, sx1 - sx0, b - a, PLANK_T, f"plank{i % 3}")
        if i:
            m.box(sx0, cuts[i], zt, sx1 - sx0, 1, PLANK_T - 1, "wood_gap")
    # wood grain streaks along the planks
    grain(m, (sx0, sy0, zt, sx1 - sx0, sy1 - sy0, PLANK_T), ["plank_hi", "plank1", "plank2", "plank0"],
          [0.15, 0.3, 0.25, 0.3], target=["plank0", "plank1", "plank2"])
    # front edge of the seat shows its side colour
    m.box(sx0, sy0, zt, sx1 - sx0, 1, PLANK_T - 1, "plank_side", only_filled=True)
    # end cleats with bolts against each leg, on the visible (-y) side
    for x in (sx0, sx1 - 4):
        m.box(x, sy0 - 1, APRON_B - 2, 4, 3, SEAT_TOP - APRON_B + 1, "cleat")
        for z in (APRON_B + 1, SEAT_TOP - 4):
            m.box(x + 1, sy0 - 1, z, 2, 1, 2, "bolt")
    # bolts on the plank ends
    for i in range(3):
        yc = (cuts[i] + cuts[i + 1]) // 2
        for x in (sx0 + 2, sx1 - 4):
            m.box(x, yc - 1, SEAT_TOP - 1, 2, 2, 1, "bolt")


# ---------------------------------------------------------------- barrel

def barrel(m: Model):
    cx, cy = BARREL_C
    H = BARREL_H
    R = int(np.ceil(BR_MID)) + 2
    x0, y0 = int(cx) - R - 1, int(cy) - R - 1
    span = 2 * R + 3

    def rad(Z):
        return BR_END + (BR_MID - BR_END) * np.sin(np.pi * (Z + 0.5) / H)

    def dist(X, Y):
        return np.hypot(X + 0.5 - cx, Y + 0.5 - cy)

    def stave(X, Y):
        a = (np.arctan2(Y + 0.5 - cy, X + 0.5 - cx) + np.pi) / (2 * np.pi) * STAVES
        return a.astype(int) % STAVES, a % 1.0

    # body below the lid, rim ring above it (stave ends at uneven heights)
    lid_z = H - LID_DROP
    m.where(x0, y0, 0, span, span, lid_z, lambda X, Y, Z: dist(X, Y) <= rad(Z), "stave0")

    def rim(X, Y, Z):
        s, _ = stave(X, Y)
        top = H - (s % 3 == 1)
        d = dist(X, Y)
        return (d <= rad(Z)) & (d > rad(Z) - RIM) & (Z < top)
    m.where(x0, y0, lid_z, span, span, LID_DROP, rim, "stave0")

    # stave colours, dark seams between staves
    ramp = [m.pal.idx(c) for c in ("stave0", "stave1", "stave2", "stave3")]
    order = m.rng.permutation(STAVES)

    def stave_col(X, Y, Z):
        s, f = stave(X, Y)
        lut = np.array(ramp, np.uint8)
        col = lut[order[s] % 4]
        grain = m.rng.random(X.shape) < 0.08
        col = np.where(grain, lut[(order[s] + 2) % 4], col)
        arc = 2 * np.pi * BR_MID / STAVES
        return np.where(f * arc < 0.9, np.uint8(m.pal.idx("stave_seam")), col)
    m.paint_fn(x0, y0, 0, span, span, H, stave_col)

    # lid: planks along x, dark gaps
    def lid(X, Y, Z):
        k = np.floor((Y + 0.5 - cy + 2) / 8).astype(int)
        col = np.array([m.pal.idx(c) for c in ("lid0", "lid1", "lid2")], np.uint8)[k % 3]
        gap = ((Y + 0.5 - cy + 2) % 8) < 1
        inside = dist(X, Y) <= rad(Z) - RIM
        return np.where(inside, np.where(gap, np.uint8(m.pal.idx("stave_seam")), col), 0)
    m.paint_fn(x0, y0, lid_z - 1, span, span, 1, lid)
    # light tops on the stave ends
    filled = m.v[x0:x0 + span, y0:y0 + span, lid_z:H + 1] > 0
    above = np.zeros_like(filled)
    above[:, :, :-1] = filled[:, :, 1:]
    tops = filled & ~above
    sub = m.v[x0:x0 + span, y0:y0 + span, lid_z:H + 1]
    keep_seam = sub == m.pal.idx("stave_seam")
    sub[tops & ~keep_seam] = m.pal.idx("rim_top")

    # iron hoops (one voxel proud) with rivets
    for hz, hh in HOOPS:
        m.where(x0, y0, hz, span, span, hh,
                lambda X, Y, Z: (dist(X, Y) <= rad(Z) + 1.2) & (dist(X, Y) > rad(Z) - 1.5), "iron")

        # rivets: a 2x2 stud standing out of the hoop at every stave centre
        zr = hz + hh // 2 - 1
        for s in range(STAVES):
            a = (s + 0.5) / STAVES * 2 * np.pi - np.pi
            r = rad(zr) + 1.6
            px, py = int(np.floor(cx + r * np.cos(a))), int(np.floor(cy + r * np.sin(a)))
            m.box(px, py, zr, 1, 1, 2, "rivet")

    # tap on the screen-left side, pointing -y
    tx = int(round(cx - 15))
    ys = int(np.floor(cy - np.sqrt(BR_MID ** 2 - 15 ** 2)))   # barrel surface at that x
    m.box(tx - 2, ys - 5, 8, 4, 7, 4, "tap")                  # pipe
    m.box(tx - 2, ys - 6, 3, 4, 4, 9, "tap")                  # spout
    m.box(tx - 2, ys - 6, 11, 4, 4, 1, "tap_hi")
    m.box(tx - 1, ys - 3, 12, 2, 2, 3, "tap")                 # handle stem
    m.box(tx - 3, ys - 3, 15, 5, 2, 2, "tap_hi")              # handle bar


# ---------------------------------------------------------------- pillars

def pillar(st: Stone, x0, y0):
    m = st.m
    # base: 3 x 3 blocks of 8, outer faces set back 0/1 voxel
    inset = {(0, 0): 0, (1, 0): 1, (2, 0): 0, (0, 1): 1, (2, 1): 1, (0, 2): 0, (1, 2): 1, (2, 2): 0}
    b = P_BASE // 3
    for i in range(3):
        for j in range(3):
            k = inset.get((i, j), 0)
            bx0 = i * b + (k if i == 0 else 0)
            bx1 = (i + 1) * b - (k if i == 2 else 0)
            by0 = j * b + (k if j == 0 else 0)
            by1 = (j + 1) * b - (k if j == 2 else 0)
            st.block(x0 + bx0, y0 + by0, 0, bx1 - bx0, by1 - by0, P_BASE_H)
    # shaft: two courses, joints staggered
    o = (P_BASE - P_SHAFT) // 2
    z0, zc, z1 = P_BASE_H, P_BASE_H + 15, P_BASE_H + P_SHAFT_H
    for xa, xb in ((0, 9), (9, P_SHAFT)):
        for ya, yb in ((0, 10), (10, P_SHAFT)):
            st.block(x0 + o + xa, y0 + o + ya, z0, xb - xa, yb - ya, zc - z0)
    for xa, xb in ((0, 12), (12, P_SHAFT)):
        for ya, yb in ((0, 6), (6, P_SHAFT)):
            st.block(x0 + o + xa, y0 + o + ya, zc, xb - xa, yb - ya, z1 - zc)
    # slate cap: two slabs
    c = (P_BASE - P_CAP) // 2
    half = P_CAP // 2
    m.box(x0 + c, y0 + c, z1, P_CAP, P_CAP, P_CAP_H, "cap_side")
    m.box(x0 + c, y0 + c, z1 + P_CAP_H - 1, P_CAP, P_CAP, 1, "cap_top")
    m.box(x0 + c + half, y0 + c, z1, 1, P_CAP, P_CAP_H, "cap_seam")
    region = (x0 + c, y0 + c, z1, P_CAP, P_CAP, P_CAP_H)
    mottle(m, ["cap_top"], None, target="cap_top", spots=["cap_hi", "cap_lo"], spot_p=0.3, region=region)
    m.sprinkle(["cap_lo", "cap_hi"], 0.12, target="cap_side", region=region)


# ---------------------------------------------------------------- build

TINTS = ["st0", "st1", "st2"]     # stone shades, light -> dark


def build() -> Model:
    m = Model(*GRID, seed=7)
    palette(m)
    st = Stone(m)

    with m.part("bench"):
        bench(m, st)
    with m.part("barrel"):
        barrel(m)
    for name, (px, py) in PILLARS.items():
        with m.part(name):
            pillar(st, px, py)

    # stone texture (all parts at once; recolouring keeps the part labels)
    seams(m, st.ids, TINTS, "seam")
    stone_texture(m)
    return m
