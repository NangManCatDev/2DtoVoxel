"""도로 — reference/도로_레퍼런스.png

A straight stretch of old paved road, seen from the front-left corner in warm
evening light. The reference is cropped (the road runs off the frame on both
ends), so this is a road tile of LENGTH voxels with straight cut ends.

Cross-section (y=0 front -> back, the road runs along x):
  near verge   grass tufts on the ground in front of the near curb
  near curb    big squared blocks (CURB_W deep, uneven heights) with dark joints
  near gutter  sunken channel of small blue-grey cobbles (2 rows)
  edge row     raised rectangular stones along the road edge
  road         flagstones on a MOD grid: big 2x2, 2x1 and small 1x1 stones,
               slightly uneven tops, mossy joints with yellow-green patches
  far side     mirror of the near side + a low sandy ledge behind the far curb
               with tall grass tufts
"""
import numpy as np
from scipy import ndimage

from voxtool import Model

NAME = "model_1028_0407"
REFERENCE = "reference/도로_레퍼런스.png"
# fit-camera picks a flat view (the cropped reference silhouette is almost a rectangle);
# this one matches the curb slopes (-0.5 far / -0.75 near) and the tile edge directions
VIEW = {"azimuth": 48, "elevation": 35, "fov": 25}

# --- plan (y widths, front to back)
LENGTH = 182          # along x
MOD = 7               # paver module: 6-voxel stone + 1 joint
ROAD_MODS = 10        # road width in modules
VERGE = 3             # grass strip in front of the near curb
CURB_W = 12
GUTTER_W = 9
EDGE_W = 5
ROAD_W = ROAD_MODS * MOD
LEDGE_W = 5           # sandy ledge behind the far curb

Y_CURB_N = VERGE
Y_GUT_N = Y_CURB_N + CURB_W
Y_EDGE_N = Y_GUT_N + GUTTER_W
Y_ROAD = Y_EDGE_N + EDGE_W
Y_EDGE_F = Y_ROAD + ROAD_W
Y_GUT_F = Y_EDGE_F + EDGE_W
Y_CURB_F = Y_GUT_F + GUTTER_W
Y_LEDGE = Y_CURB_F + CURB_W
DEPTH = Y_LEDGE + LEDGE_W

# --- heights (first empty z above each surface)
GUT_Z = 5             # gutter cobble tops (2 below the road)
BED_Z = 4             # mortar bed under the road (visible in the joints)
ROAD_Z = 7            # flagstone tops
EDGE_Z = 9            # raised edge stones
CURB_Z = 15           # curb block tops (+-2 per block)
LEDGE_Z = 10          # sandy ledge behind the far curb
HEIGHT = 26

# flagstone hues: (light, mid, dark) per hue, tops are lit at x1.0 in the preview
# (darker / more orange variants matching the reference mean ~#a58162 scored worse)
PAVE_HUES = {
    "sand": ("#f0bf86", "#e2ae79", "#d09c6a"),
    "tan": ("#dcaa7c", "#cf9d70", "#bb8a60"),
    "rose": ("#d6aa8e", "#c79a80", "#b38a74"),
    "mauve": ("#bba096", "#a98f88", "#968078"),
    "ochre": ("#e6b16e", "#d6a062", "#c08b52"),
}
PAVE_P = [0.32, 0.27, 0.18, 0.08, 0.15]
MOSS_SIGMA, MOSS_THR = 3.0, 0.38     # patch size / how much of the road gets dense moss


def palette(m: Model):
    p = m.pal
    for name, ramp in PAVE_HUES.items():
        p.ramp(name, ramp)
    # stone blocks: warm sun-lit top layer, cooler pinkish-grey body (shaded faces)
    p.ramp("edge", ["#c8ada4", "#b89c94", "#a58a84"])
    p.ramp("edgetop", ["#eebd8c", "#dcab80", "#c99a72"])
    p.ramp("cob", ["#8e8288", "#7a6f78", "#665d66"])          # gutter cobbles, blue-grey
    p.ramp("curb", ["#d2b8ac", "#c2a89e", "#ae948c"])
    p.ramp("curbtop", ["#fcd39a", "#f0c28c", "#ddb07e"])
    p.add("rim", "#7e5e46")                                    # worn stone edges
    p.ramp("ledge", ["#e4b06a", "#d39f5e", "#bf8c50"])
    p.add("bed", "#4a3b24"); p.add("joint", "#3a2f22")
    p.ramp("moss", ["#6c5f0c", "#8b7510", "#a68f1e"])
    p.ramp("grass", ["#5e5212", "#8a7a18", "#b09a28", "#d6b23a"])


def shades(name: str) -> list[str]:
    return [f"{name}0", f"{name}1", f"{name}2"]


# ---------------------------------------------------------------- helpers

def stone(m: Model, x, y, w, d, z0, z1, color: str, *, bevel: bool = True,
          chamfer: str | None = None, top: str | None = None):
    """Block of one colour (mid shade) from z0 to z1 (exclusive). bevel rounds the
    four top corners; chamfer (a colour) steps the whole top rim down by one voxel and
    paints the step, so stones read as separate pieces with dark worn edges; top
    paints the top layer in another colour (sun-lit top, cooler body)."""
    m.box(x, y, z0, w, d, z1 - z0, color)
    if top:
        m.box(x, y, z1 - 1, w, d, 1, top)
    if chamfer and w > 3 and d > 3 and z1 - z0 > 1:
        m.box(x, y, z1 - 1, w, d, 1, None)
        m.box(x + 1, y + 1, z1 - 1, w - 2, d - 2, 1, top or color)
        m.box(x, y, z1 - 2, w, d, 1, chamfer)
        m.box(x + 1, y + 1, z1 - 2, w - 2, d - 2, 1, color)
    elif bevel and w > 2 and d > 2:
        for cx in (x, x + w - 1):
            for cy in (y, y + d - 1):
                m.set(cx, cy, z1 - 1, None)


def texture(m: Model, names: list[str], p=(0.25, 0.5, 0.25)):
    """Mottled voxel texture: every voxel of the mid shade becomes light/mid/dark."""
    m.vary(names, target=names[1], p=list(p))


def row_of_blocks(m: Model, y, d, z0, top, color, lengths, jitter, *, gaps=(1,), gap_color=None,
                  gap_h=4, bevel=True, top_color=None, chamfer=None) -> list[int]:
    """Blocks laid end to end along x; joints of a width picked from `gaps`, filled
    gap_h high with gap_color. Returns the x of each joint wider than 1."""
    x = int(m.rng.integers(-lengths[1] + 2, 1))
    wide = []
    while x < LENGTH:
        L = int(m.rng.integers(lengths[0], lengths[1] + 1))
        t = top + int(m.rng.choice(jitter))
        g = int(m.rng.choice(gaps))
        stone(m, x, y, L, d, z0, t, color, bevel=bevel, top=top_color, chamfer=chamfer)
        if gap_color:
            m.box(x + L, y, z0, g, d, gap_h, gap_color)
        if g > 1:
            wide.append(x + L)
        x += L + g
    return wide


def flagstones(m: Model):
    """Random packing of 2x2 / 2x1 / 1x1 stones on the MOD grid of the road."""
    rng = m.rng
    nx = (LENGTH + MOD - 1) // MOD + 1
    ny = ROAD_MODS
    taken = np.zeros((nx, ny), bool)
    hues = list(PAVE_HUES)
    for i in range(-1, nx - 1):
        for j in range(ny):
            if taken[i + 1, j]:
                continue
            r = rng.random()
            w, d = (2, 2) if r < 0.42 else (2, 1) if r < 0.52 else (1, 2) if r < 0.62 else (1, 1)
            if i + 1 + w > nx or j + d > ny or taken[i + 1:i + 1 + w, j:j + d].any():
                w, d = 1, 1
            taken[i + 1:i + 1 + w, j:j + d] = True
            x, y = i * MOD + 1, Y_ROAD + j * MOD + 1
            sw, sd = w * MOD - 1, d * MOD - 1
            # irregular joints: sometimes pull one side in by a voxel
            if rng.random() < 0.3:
                sw -= 1
                x += int(rng.integers(0, 2))
            if rng.random() < 0.3:
                sd -= 1
                y += int(rng.integers(0, 2))
            top = ROAD_Z + int(rng.choice([0, 0, 0, 0, -1, 1]))
            hue = hues[int(rng.choice(len(hues), p=PAVE_P))]
            stone(m, x, y, sw, sd, BED_Z, top, f"{hue}1", chamfer="rim")


def smooth_noise(m: Model, shape, sigma: float) -> np.ndarray:
    """Low-frequency noise in 0..1 (moss patches)."""
    f = ndimage.gaussian_filter(m.rng.random(shape), sigma)
    return (f - f.min()) / max(np.ptp(f), 1e-6)


def moss(m: Model):
    """Yellow-green moss growing up the flagstone joints (never on top of a stone),
    denser in patches."""
    y0, d = Y_EDGE_N, ROAD_W + 2 * EDGE_W
    field = smooth_noise(m, (LENGTH, d), MOSS_SIGMA)
    joint = m.v[0:LENGTH, y0:y0 + d, BED_Z] == 0          # columns between stones
    sl = m.v[0:LENGTH, y0:y0 + d, BED_Z:ROAD_Z]
    idx = np.array([m.pal.idx(c) for c in shades("moss")], np.uint8)
    for k in range(sl.shape[2]):
        layer = sl[:, :, k]
        below = m.v[0:LENGTH, y0:y0 + d, BED_Z + k - 1]
        # thin speckle everywhere at the bottom; higher layers only inside patches
        thr = MOSS_THR + 0.08 * k if k else -1.0
        p = 0.8 if k else 0.45
        cand = joint & (layer == 0) & (below != 0) & (field > thr) & (m.rng.random(layer.shape) < p)
        layer[cand] = m.rng.choice(idx, size=int(cand.sum()))


def tuft(m: Model, x, y, z, n: int = 7, h: int = 5, r: int = 2):
    """Clump of grass blades: n single-voxel columns around (x, y) standing on z."""
    names = shades("grass") + ["grass3"]
    for _ in range(n):
        bx = x + int(m.rng.integers(-r, r + 1))
        by = y + int(m.rng.integers(-r, r + 1))
        bh = int(m.rng.integers(max(1, h - 3), h + 1))
        if m.get(bx, by, z) != 0:
            continue
        for k in range(bh):
            c = names[min(3, 1 + (k * 3) // max(bh, 1))] if k else names[0]
            m.set(bx, by, z + k, c)


def ground_z(m: Model, x, y) -> int:
    """First empty z above the column at (x, y)."""
    col = np.nonzero(m.v[x, y, :])[0] if 0 <= x < m.size[0] and 0 <= y < m.size[1] else []
    return int(col[-1]) + 1 if len(col) else 0


def tufts_along(m: Model, y, every: int, n: int, h: int, r: int = 2, chance: float = 1.0):
    x = int(m.rng.integers(0, every))
    while x < LENGTH:
        if m.rng.random() < chance:
            yy = y + int(m.rng.integers(-1, 2))
            tuft(m, x, yy, ground_z(m, x, yy), n=n, h=h, r=r)
        x += every + int(m.rng.integers(-every // 3, every // 3 + 1))


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(LENGTH, DEPTH, HEIGHT, seed=11)
    palette(m)

    # mortar bed under road + edge rows, gutter beds
    m.box(0, Y_EDGE_N, 0, LENGTH, Y_GUT_F - Y_EDGE_N, BED_Z, "bed")
    m.box(0, Y_GUT_N, 0, LENGTH, GUTTER_W, 1, "joint")
    m.box(0, Y_GUT_F, 0, LENGTH, GUTTER_W, 1, "joint")

    # road
    flagstones(m)

    # raised edge stones on both sides of the road
    for y in (Y_EDGE_N, Y_EDGE_F):
        row_of_blocks(m, y, EDGE_W, 0, EDGE_Z, "edge1", (10, 14), [0, 0, -1, 1], top_color="edgetop1")

    # gutters: two rows of small cobbles in running bond
    for yg in (Y_GUT_N, Y_GUT_F):
        for r, (dy, dd) in enumerate(((0, 4), (5, 4))):
            row_of_blocks(m, yg + dy, dd, 1, GUT_Z, "cob1", (4, 6), [0, 0, 1], bevel=False)

    # curbs: big uneven blocks, some set apart so their sunlit end faces show
    curb_gaps = {}
    for yc in (Y_CURB_N, Y_CURB_F):
        curb_gaps[yc] = row_of_blocks(m, yc, CURB_W, 0, CURB_Z, "curb1", (11, 15), [-3, -1, 0, 0, 1],
                                      gaps=(1, 1, 2, 3), gap_color="joint", gap_h=GUT_Z,
                                      top_color="curbtop1", chamfer="curb2")

    # sandy ledge behind the far curb
    m.box(0, Y_LEDGE, 0, LENGTH, LEDGE_W, LEDGE_Z, "ledge1")

    # mottled textures
    for hue in PAVE_HUES:
        texture(m, shades(hue))
    for name in ("edge", "edgetop", "cob", "curb", "curbtop", "ledge"):
        texture(m, shades(name))

    moss(m)

    # grass: tall tufts on the far ledge, in the gutters, at the near curb's foot,
    # sprouting from the wide curb joints
    tufts_along(m, Y_LEDGE + 2, 9, 16, 7, r=2, chance=0.85)
    tufts_along(m, Y_CURB_N - 2, 7, 14, 7, r=2, chance=0.9)
    tufts_along(m, Y_GUT_F + GUTTER_W - 2, 16, 9, 5, r=1, chance=0.75)
    tufts_along(m, Y_GUT_N + 1, 20, 8, 4, r=1, chance=0.6)
    tufts_along(m, Y_ROAD + ROAD_W // 2, 30, 6, 3, r=8, chance=0.6)
    for yc, xs in curb_gaps.items():
        for x in xs:
            for yy in range(yc + 2, yc + CURB_W - 1, 4):
                if m.rng.random() < 0.6:
                    tuft(m, x, yy, GUT_Z, n=5, h=int(m.rng.integers(5, 10)), r=0)

    return m
