"""Limestone harbour pier module set — reference/복셀_항구_석회암_부두_모듈_세트-2.png

Kit sheet of four pier modules, each its own m.part() (a separate object in the .vox):

  wall      long straight quay wall (top left), three bollards on the front edge
  corner    L-shaped corner quay (top right): one arm along -x, one along +y from the
            outer corner, bollards at the left end, on the corner and at the far end
  stairs    quay block with a flight of five steps cut into its front (bottom left)
  platform  low square landing (bottom right), bollards front-left, back and right

Every module: cream limestone ashlar walls in running bond (COURSE high, BLOCK long) under a
coping course that overhangs one unit, a tiled deck (TILE x TILE slabs), grey boulders along
the foot of every side, teal algae creeping up the lowest ALGAE units (jagged, dithered), and
brown timber mooring bollards (post, rope band, cap, a foot block; on the quay edge the post
runs SKIRT units down the face).

Camera: the sheet is not one consistent camera - the straight wall and the stairs are seen
from az ~ -22, the corner and the platform from az ~ -45 (all at el ~ 22, near-orthographic),
so one compromise view is used (az -35 = the area-weighted mean; -40 scored 0.833 vs 0.848)
and every module stays axis-aligned (a kit should snap to a grid). Each module is built in its
own grid, then placed so the centre of its projected bounding box lands on the centre of its
blob on the cut-out sheet (sheet_boxes(), PX sheet pixels per unit); the build prints both
sizes so the module dimensions can be matched. Changing VIEW re-lays the sheet out.

Colour: RES 2 gives half-unit joints between blocks, tiles and step slabs. paint_reference()
only touches boulders and algae (tol 15): painting the limestone too lowered dE (18.7 -> 13.9)
but smeared the block pattern and whitened the right-hand faces (the sheet is lit from the
right, the preview shades +x faces at 0.7). Score: iou 0.847, dE 16.6.

Layout (x right, y depth with y=0 front, z up); module sizes in units at the top.
"""
import functools
import math
import os

import numpy as np
from scipy import ndimage

from voxtool import Model

NAME = "model_1029_2239_3"
REFERENCE = "reference/복셀_항구_석회암_부두_모듈_세트-2.png"
AZ, EL = -35, 22
VIEW = {"azimuth": AZ, "elevation": EL, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 2
PAINT, PAINT_TOL = True, 15

PX = 9.0                    # sheet pixels per unit
MARGIN = 3                  # empty border of the grid
RIM = 6                     # room for boulders around each module's footprint

# shared masonry
COURSE, BLOCK, TILE = 3, 6, 6
COPING = 3                  # coping course height (overhangs OVER)
OVER = 1
ALGAE = 5.0                 # mean height of the algae line
ROCK_DROP = 1.5             # ...lower on the boulders
SKIRT = 7                   # bollard post below the deck top on a quay edge

# modules (units)
WALL_L, WALL_D, WALL_H = 113, 16, 20
WALL_END = 7                # raised coping block at the wall's right end
CORNER_A, CORNER_B, CORNER_W, CORNER_H = 58, 66, 22, 21      # arm along -x, arm along +y, width
STAIR_L, STAIR_D, STAIR_H = 78, 22, 20
STAIR_X0, STAIR_X1 = 21, 57                                   # notch of the flight (x, from the left end)
STEPS, RISE, RUN = 5, 4, 3
SLAB = 9                    # step slab length
PLAT_L, PLAT_D, PLAT_H = 48, 35, 12

LIME = ["lime0", "lime1", "lime2", "lime3", "lime4", "lime5"]      # light -> dark
ROCK = ["rock0", "rock1", "rock2", "rock3"]
ALG = ["alg0", "alg1", "alg2", "alg3", "alg4"]
WOOD = ["wood0", "wood1", "wood2", "wood3"]
ROPE = ["rope0", "rope1", "rope2"]


def palette(m: Model):
    p = m.pal
    p.add("lime0", "#fde6c4"); p.add("lime1", "#f7dbb5"); p.add("lime2", "#f0d0a8"); p.add("lime3", "#e7c59c")
    p.add("lime4", "#dcbd96"); p.add("lime5", "#cdae8a")
    p.add("lime_g", "#e9dccd"); p.add("joint", "#c9aa88"); p.add("stone", "#f0d0a8"); p.add("step", "#f0d0a8")
    p.add("rock", "#8e8790")
    p.add("rock0", "#aba4a7"); p.add("rock1", "#968f96"); p.add("rock2", "#817b81"); p.add("rock3", "#6c696d")
    p.add("alg0", "#4b6567"); p.add("alg1", "#28555b"); p.add("alg2", "#0f3f4b"); p.add("alg3", "#062d3c")
    p.add("alg4", "#021d2a")
    p.add("wood", "#5c3223")
    p.add("wood0", "#6e3d2b"); p.add("wood1", "#5a3122"); p.add("wood2", "#46251a"); p.add("wood3", "#311810")
    p.add("wood_top", "#9a5a3e")
    p.add("rope0", "#c9a274"); p.add("rope1", "#a37a50"); p.add("rope2", "#e2c393")


def _hash01(*a):
    h = np.uint64(1469598103934665603)
    for k, x in enumerate(a):
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h.astype(np.float64) / 2 ** 32


def recolor(m: Model, region, fn, target):
    """Like paint_fn, but only voxels of the `target` colours change (neighbouring modules and
    details drawn earlier are left alone). fn(X, Y, Z) -> palette indices, 0 = keep."""
    sl = m._slices(*region)
    if sl is None:
        return
    X, Y, Z = m._coords(sl)
    sub = m.v[sl]
    new = np.broadcast_to(np.asarray(fn(X, Y, Z), np.uint8), sub.shape)
    mask = np.isin(sub, [m.pal.idx(t) for t in target]) & (new > 0)
    sub[mask] = new[mask]


def carve_colors(m: Model, region, target):
    sl = m._slices(*region)
    if sl is not None:
        sub = m.v[sl]
        sub[np.isin(sub, [m.pal.idx(t) for t in target])] = 0


# ---------------------------------------------------------------- masonry

def masonry(m: Model, region, deck, salt):
    """Limestone: deck tiles on the top layer (z >= deck - 1), running-bond ashlar below; one
    shade per block (LIME is light -> dark), the courses near the waterline a shade or two
    darker (wet stone), a few grey-weathered blocks."""
    ids = np.array([m.pal.idx(c) for c in LIME], np.uint8)
    grey = m.pal.idx("lime_g")
    joint = m.pal.idx("joint")
    r = m.res

    def fn(X, Y, Z):
        top = np.floor(Z) >= deck - 1
        tile = _hash01(np.floor(X / TILE), np.floor(Y / TILE), salt)
        row = np.floor(Z / COURSE)
        off = np.floor(_hash01(row, salt, 5) * BLOCK)      # each course shifted at random
        u = X + Y + off                                    # runs on around corners
        bi = np.floor(u / BLOCK)
        along = u - bi * BLOCK                             # position inside the block
        half = _hash01(bi, row, salt + 21) < 0.3           # some blocks are two short ones
        key = 4 * bi + np.where(half, 2 * (along >= BLOCK / 2), 1)
        h = np.where(top, tile, _hash01(key, row, salt + 7))
        k = np.searchsorted([0.3, 0.6, 0.85], h, side="right")      # 0..3
        k = k + (~top & (Z < ALGAE + 7)) + (~top & (Z < ALGAE + 3))
        col = ids[k.clip(0, len(ids) - 1)]
        col = np.where(~top & (_hash01(key, row, salt + 13) < 0.1), grey, col)
        if r < 2:           # a whole unit of joint is far thicker than the sheet's hairlines
            return col
        # thin joints (one voxel at res >= 2): lowest voxel row of a course, first voxel of a block / tile
        jz = ~top & (np.floor(Z * r + 1e-6) % (COURSE * r) == 0)
        a = np.floor(along * r + 1e-6)
        ju = ~top & ((a == 0) | (half & (a == BLOCK * r // 2)))
        jt = top & ((np.floor(X * r + 1e-6) % (TILE * r) == 0) | (np.floor(Y * r + 1e-6) % (TILE * r) == 0))
        return np.where(jz | ju | jt, joint, col)
    recolor(m, region, fn, ["stone"])


def algae(m: Model, region, salt):
    """Teal growth on the lowest units of stone and boulders: a jagged line per column,
    dithered bands getting darker toward the water."""
    ids = np.array([m.pal.idx(c) for c in ALG], np.uint8)

    def growth(drop):
        def fn(X, Y, Z):
            xi, yi = np.floor(X), np.floor(Y)
            u = xi - yi
            line = ALGAE - drop + 1.3 * np.sin(u * 0.41 + salt) + 0.9 * np.sin(u * 0.13 + 2.0 * salt) \
                + 2.4 * (_hash01(xi, yi, salt) - 0.5)
            d = line - np.floor(Z) + 1.0 * (_hash01(xi, yi, np.floor(Z) + 977 * salt) - 0.5)
            band = np.digitize(d, [0.0, 1.5, 3.0, 4.5, 6.0])          # 0 = above the line
            return np.where(band > 0, ids[(band - 1).clip(0, len(ids) - 1)], 0)
        return fn
    recolor(m, region, growth(0.0), LIME + ["lime_g", "joint"])
    recolor(m, region, growth(ROCK_DROP), ROCK)          # boulders stay grey higher up


# ---------------------------------------------------------------- boulders

def rock(m: Model, rng, x, y, w, d, h):
    """Grey boulder: a box with chipped top corners, sometimes a smaller block on top."""
    m.box(x, y, 0, w, d, h, "rock", only_empty=True)
    for cx in (x, x + w - 1):
        for cy in (y, y + d - 1):
            if rng.random() < 0.55:
                carve_colors(m, (cx, cy, h - 1, 1, 1, 1), ["rock"])
    if w >= 6 and rng.random() < 0.35:
        tw = int(rng.integers(3, w - 2))
        tx = x + int(rng.integers(1, w - tw))
        m.box(tx, y + 1, h, tw, max(d - 2, 2), int(rng.integers(2, 4)), "rock", only_empty=True)


def rocks_along(m: Model, rng, side, x0, y0, w, d, skip=(), big=False):
    """Boulders along one side ('-y', '+y', '-x', '+x') of the footprint (x0, y0, w, d),
    half sunk into the wall; `skip` = ranges along the side left clear."""
    length = w if side in ("-y", "+y") else d
    t = int(rng.integers(-3, 1))
    while t < length:
        rw = int(rng.integers(5, 10))
        gap = int(rng.choice([1, 3, 5, 8, 12], p=[0.15, 0.25, 0.25, 0.2, 0.15]))
        rh = int(rng.integers(6, 14 if big else 12))
        out = int(rng.integers(2, 5))
        inn = 2
        if not any(a - 2 <= t + rw / 2 <= b + 2 for a, b in skip):
            if side == "-y":
                box = (x0 + t, y0 - out, rw, out + inn)
            elif side == "+y":
                box = (x0 + t, y0 + d - inn, rw, out + inn)
            elif side == "-x":
                box = (x0 - out, y0 + t, out + inn, rw)
            else:
                box = (x0 + w - inn, y0 + t, out + inn, rw)
            rock(m, rng, *box, rh)
        t += rw + gap


def rock_ring(m: Model, rng, rects, skip=None):
    """Boulders around every side of each footprint rect; corner boulders are bigger."""
    skip = skip or {}
    for i, (x0, y0, w, d) in enumerate(rects):
        for side in ("-y", "+x", "-x", "+y"):
            rocks_along(m, rng, side, x0, y0, w, d, skip.get((i, side), ()))
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + d), (x0 + w, y0 + d)):
            s = int(rng.integers(7, 10))
            rock(m, rng, cx - s // 2 - 1, cy - s // 2 - 1, s, s, int(rng.integers(8, 12)))


def texture_rocks(m: Model, region, salt):
    ids = np.array([m.pal.idx(c) for c in ROCK], np.uint8)
    cum = np.cumsum([0.22, 0.34, 0.28, 0.16])

    def fn(X, Y, Z):
        h = _hash01(np.floor(X), np.floor(Y), np.floor(Z) + 31 * salt)     # the sheet's grain: one unit
        return ids[np.searchsorted(cum, h * cum[-1], side="right").clip(0, len(ids) - 1)]
    recolor(m, region, fn, ["rock"])


# ---------------------------------------------------------------- bollards

def bollard(m: Model, px, py, deck, skirt=0, foot=(1, 1)):
    """Timber mooring bollard: 4 x 4 post with its low corner at (px, py), standing on the deck
    (and running `skirt` units down a quay face), a rope band and a cap one unit wider all
    round, a foot block on the deck beside it (foot = direction (dx, dy))."""
    z0 = deck - skirt
    m.box(px, py, z0, 4, 4, deck + 4 - z0, "wood")
    fx = px + (4 if foot[0] > 0 else -3) if foot[0] else px + 1
    fy = py + (4 if foot[1] > 0 else -3) if foot[1] else py + 1
    m.box(fx, fy, deck, 3, 3, 3, "wood", only_empty=True)
    m.box(px - 1, py - 1, deck + 2, 6, 6, 3, "rope1")
    m.box(px - 1, py - 1, deck + 5, 6, 6, 3, "wood")
    ids = np.array([m.pal.idx(c) for c in WOOD], np.uint8)
    rope = np.array([m.pal.idx(c) for c in ROPE], np.uint8)
    top = m.pal.idx("wood_top")

    def wood(X, Y, Z):
        streak = _hash01(np.floor(X), np.floor(Y), np.floor(Z / 2))
        c = ids[(streak * 3.2).astype(int).clip(0, 3)]
        return np.where(np.floor(Z) >= deck + 7, top, c)

    def ropes(X, Y, Z):
        k = (np.floor(Z * m.res) + np.floor((X + Y) * m.res / 2)) % 2
        return np.where(_hash01(np.floor(X), np.floor(Y), np.floor(Z)) < 0.2, rope[2], rope[k.astype(int)])
    region = (px - 3, py - 3, z0, 10, 10, deck + 8 - z0)
    recolor(m, region, wood, ["wood"])
    recolor(m, region, ropes, ["rope1"])


# ---------------------------------------------------------------- modules (local coords, then placed)

def body(m: Model, x, y, w, d, h):
    """Wall block with its coping course overhanging OVER on every side."""
    m.box(x, y, 0, w, d, h - COPING, "stone")
    m.box(x - OVER, y - OVER, h - COPING, w + 2 * OVER, d + 2 * OVER, COPING, "stone")


def finish(m: Model, rng, region, deck, rects, salt, skip=None):
    masonry(m, region, deck, salt)
    rock_ring(m, rng, rects, skip)
    texture_rocks(m, region, salt)
    algae(m, region, salt)


def wall(m: Model, rng, ox, oy):
    x, y = ox + RIM, oy + RIM
    body(m, x, y, WALL_L, WALL_D, WALL_H)
    m.box(x + WALL_L - WALL_END, y - OVER, WALL_H, WALL_END + OVER, WALL_D + 2 * OVER, 2, "stone")   # raised end block
    region = (ox, oy, 0, WALL_L + 2 * RIM, WALL_D + 2 * RIM, WALL_H + 10)
    finish(m, rng, region, WALL_H, [(x, y, WALL_L, WALL_D)], 1)
    for bx in (7, 48, WALL_L - 13):
        bollard(m, x + bx - 2, y - 2, WALL_H, SKIRT, foot=(1, 0))


def corner(m: Model, rng, ox, oy):
    x, y = ox + RIM, oy + RIM
    A, B, W, H = CORNER_A, CORNER_B, CORNER_W, CORNER_H
    body(m, x, y, A, W, H)
    body(m, x + A - W, y, W, B, H)
    m.carve(x + A - W, y + W - OVER, H - COPING, OVER, OVER, COPING)      # inner corner of the coping
    m.box(x + A - W - OVER, y + W, H - COPING, W + 2 * OVER, OVER, COPING, "stone")
    region = (ox, oy, 0, A + 2 * RIM, B + 2 * RIM, H + 10)
    finish(m, rng, region, H, [(x, y, A, W), (x + A - W, y, W, B)], 2)
    bollard(m, x + 5, y - 2, H, SKIRT, foot=(1, 0))
    bollard(m, x + A - 3, y - 2, H, SKIRT, foot=(-1, 1))
    bollard(m, x + A - 2, y + B - 9, H, SKIRT, foot=(-1, 0))


def stairs(m: Model, rng, ox, oy):
    x, y = ox + RIM, oy + RIM
    L, D, H = STAIR_L, STAIR_D, STAIR_H
    body(m, x, y, L, D, H)
    depth = STEPS * RUN
    nx, nw = x + STAIR_X0, STAIR_X1 - STAIR_X0
    m.carve(nx, y - OVER, 0, nw, depth + OVER, H)
    region = (ox, oy, 0, L + 2 * RIM, D + 2 * RIM, H + 10)
    skip = {(0, "-y"): [(STAIR_X0 - 2, STAIR_X1 + 2)]}
    masonry(m, region, H, 3)
    rock_ring(m, rng, [(x, y, L, D)], skip)
    # no boulder in front of the flight
    carve_colors(m, (nx - 1, oy, 0, nw + 2, RIM + 2, H), ["rock"])
    texture_rocks(m, region, 3)
    algae(m, region, 3)
    # the flight (after the algae: the steps are kept clean), step 0 at the front, climbing toward +y
    for i in range(STEPS):
        y0 = y + i * RUN - (2 if i == 0 else 0)
        m.box(nx, y0, 0, nw, y + depth - y0, RISE * (i + 1), "step")
    ids = np.array([m.pal.idx(c) for c in LIME[:4]], np.uint8)
    joint, r = m.pal.idx("joint"), m.res

    def steps(X, Y, Z):
        s = np.floor(Z / RISE)
        slab = np.floor((X - nx) / SLAB + 0.5 * (s % 2))
        col = ids[(_hash01(slab, s, 41) * 3.4).astype(int).clip(0, 3)]
        if r < 2:
            return col
        j = (np.floor((X - nx) * r + 0.5 * (s % 2) * SLAB * r + 1e-6) % (SLAB * r) == 0) \
            | (np.floor(Z * r + 1e-6) % (RISE * r) == 0)
        return np.where(j, joint, col)
    recolor(m, (nx, y - 2, 0, nw, depth + 2, H), steps, ["step"])
    bollard(m, x + 8, y + 3, H, 0, foot=(1, 1))
    bollard(m, x + 67, y + 13, H, 0, foot=(1, 1))


def platform(m: Model, rng, ox, oy):
    x, y = ox + RIM, oy + RIM
    L, D, H = PLAT_L, PLAT_D, PLAT_H
    body(m, x, y, L, D, H)
    region = (ox, oy, 0, L + 2 * RIM, D + 2 * RIM, H + 10)
    finish(m, rng, region, H, [(x, y, L, D)], 4)
    bollard(m, x + 4, y - 2, H, SKIRT - 2, foot=(1, 1))
    bollard(m, x + 12, y + D - 9, H, 0, foot=(1, 1))
    bollard(m, x + L - 2, y + D - 8, H, SKIRT - 2, foot=(-1, 0))


# local footprint (w, d) and builder; the sheet position is read off the reference
MODULES = {
    "wall": ((WALL_L + 2 * RIM, WALL_D + 2 * RIM), wall),
    "corner": ((CORNER_A + 2 * RIM, CORNER_B + 2 * RIM), corner),
    "stairs": ((STAIR_L + 2 * RIM, STAIR_D + 2 * RIM), stairs),
    "platform": ((PLAT_L + 2 * RIM, PLAT_D + 2 * RIM), platform),
}
SHEET = {"wall": (0, 0), "corner": (0, 1), "stairs": (1, 0), "platform": (1, 1)}   # (row, column) on the sheet


@functools.lru_cache(maxsize=1)
def sheet_boxes():
    """Bounding box (x0, y0, x1, y1) in reference pixels of each module on the cut-out sheet
    (the same cutout the score uses): the four biggest blobs, by row and column."""
    from voxtool.score import reference_cutout
    im = reference_cutout(REFERENCE, os.path.join(os.getcwd(), "output", "_ref"), **CUTOUT)
    a = np.asarray(im)[..., 3] > 127
    lab, _ = ndimage.label(ndimage.binary_opening(a, iterations=2))
    sizes = np.bincount(lab.ravel())[1:]
    boxes = []
    for k in np.argsort(-sizes)[:4] + 1:
        ys, xs = np.nonzero(lab == k)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    rows = sorted(boxes, key=lambda b: b[1] + b[3])
    grid = [sorted(rows[:2]), sorted(rows[2:])]
    return {n: grid[r][c] for n, (r, c) in SHEET.items()}


def axes():
    A, E = math.radians(AZ), math.radians(EL)
    right = np.array([math.cos(A), -math.sin(A), 0.0])
    up = np.array([math.sin(E) * math.sin(A), math.sin(E) * math.cos(A), math.cos(E)])
    return right, up


def screen_box(v: np.ndarray, res: int):
    """Projected bounding box (u0, v0, u1, v1) of a voxel grid's filled voxels in units
    (orthographic under VIEW, v down)."""
    right, up = axes()
    idx = np.argwhere(v > 0).astype(float)
    corners = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)], float)
    u = idx @ right
    w = -(idx @ up)
    cu, cw = corners @ right, -(corners @ up)
    return np.array([(u.min() + cu.min()), (w.min() + cw.min()), (u.max() + cu.max()), (w.max() + cw.max())]) / res


def ground_offset(du, dv):
    """Ground offset (x, y) in units that moves a module by (du, dv) screen units (v down)."""
    A, E = math.radians(AZ), math.radians(EL)
    r1, r2 = du, -dv / math.sin(E)
    return np.array([r1 * math.cos(A) + r2 * math.sin(A), -r1 * math.sin(A) + r2 * math.cos(A)])


def build() -> Model:
    H = max(WALL_H, CORNER_H, STAIR_H, PLAT_H) + 10
    boxes = sheet_boxes()
    local, offs = {}, {}
    for i, (name, (size, builder)) in enumerate(MODULES.items()):
        lm = Model(size[0], size[1], H, seed=11 + i, res=RES)
        palette(lm)
        builder(lm, np.random.default_rng(5 + i), 0, 0)
        sb = screen_box(lm.v, RES)
        rb = np.array(boxes[name], float) / PX
        offs[name] = ground_offset(*((rb[:2] + rb[2:]) / 2 - (sb[:2] + sb[2:]) / 2))
        local[name] = lm
        print(f"{name}: sheet {rb[2] - rb[0]:.0f} x {rb[3] - rb[1]:.0f}, model {sb[2] - sb[0]:.0f} x {sb[3] - sb[1]:.0f}"
              f" screen units (PX {PX})")
    lo = np.min(list(offs.values()), axis=0)
    hi = np.max([o + np.array(MODULES[n][0]) for n, o in offs.items()], axis=0)
    W, D = (int(math.ceil(v)) + 2 * MARGIN + 1 for v in hi - lo)
    m = Model(W, D, H, seed=11, res=RES)
    palette(m)
    r = RES
    placed = []
    for name, lm in local.items():
        ox, oy = (int(round(v)) for v in offs[name] - lo + MARGIN)
        sw, sd, sh = lm.v.shape
        dst = m.v[ox * r:ox * r + sw, oy * r:oy * r + sd, :sh]
        if (dst > 0).any() and ((dst > 0) & (lm.v > 0)).any():
            print(f"warning: {name} overlaps a module placed before it")
        with m.part(name):
            np.copyto(dst, lm.v, where=lm.v > 0)
        placed.append(f"{name} at ({ox},{oy})")
    print("modules: " + ", ".join(placed))
    from voxtool.score import reference_transform
    ppv = reference_transform(m.v, m.pal.rgba, set(), REFERENCE, VIEW, cutout_kw=CUTOUT,
                              cache_dir=os.path.join(os.getcwd(), "output", "_ref"))[3] * m.res
    print(f"score alignment: {ppv:.2f} px/unit (layout uses PX {PX})")
    if PAINT:       # the sheet's mottling on boulders and algae only: painted limestone lost its block
        #             pattern and the right-hand faces turned white (the sheet is lit from the right)
        n = m.paint_reference(REFERENCE, VIEW, cutout=CUTOUT, only=ROCK + ALG, tol=PAINT_TOL)
        print(f"painted {n} voxels from the sheet")
    return m
