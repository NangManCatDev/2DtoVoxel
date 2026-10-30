"""Coastal pier props atlas — reference/복셀_해안_부두_소품_아틀라스-3.png

A kit sheet of eight voxel props on a dark gradient, seen from the front-left (orthographic,
about az 42 / el 24: every cube shows a diamond top, a darker left face and a lighter right one):
  rocks_large    stepped heap of pale stone cubes (edge 4-12) overgrown with moss clumps, with
                 seaweed blades on both flanks (top left)
  rocks_medium   lower heap: a tall cube at the back, a long block on the left, moss on top and
                 a seaweed patch on the right (top middle)
  lamp_post      wooden post on a two-step plinth with two rope rings and a collar, a cross arm
                 toward -x with a diagonal brace, a glowing lantern hanging from the arm (top right)
  seaweed_rocks / seaweed_tall / seaweed_clump   seaweed clumps (lime, green and dark teal blades
                 of stacked 1-unit cubes) with moss at the foot and a few small stones (bottom row)
  bollard_short / bollard_tall   mooring posts on a wide base with iron bolts, two rope rings and
                 a rope loop hanging off the right corner (bottom right)

Scale: one design unit = PX reference px (seaweed cubes and the stone mottling are one unit).
Pieces are placed from sheet pixels: the point at height z that the VIEW camera shows at sheet
pixel (u, v) has exactly one ground position (raw()), so a stone cube is given by the sheet
position of its top-face centre, its edge and its depth b inside the heap (units behind the heap's
ground centre; None = a cube resting on the ground). Seaweed blades are given by the sheet
position of their tip and of their foot. Lower pieces of the sheet stand closer to the camera, so
the bottom row is in front of the top row. Every prop is its own m.part().
Stone, wood and rope are painted from the reference last (leaves keep their ramps).
Score at RES 1: iou 0.792, dE 18.7 (first build 0.735 / 21.8; chunkier blades, LEAF_RATE 0.45,
overshot the outline to 0.786).
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_2239_2"
REFERENCE = "reference/복셀_해안_부두_소품_아틀라스-3.png"
VIEW = {"azimuth": 42, "elevation": 24, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 1

PX = 8.0                    # reference px per design unit
MARGIN = 6
HEIGHT = 82
LEAF_RATE = 0.3             # chance per cube that a seaweed blade grows a side cube (0.45 overshot)
ARM_Z = 62                  # underside of the lamp's cross arm
FOOT_JITTER = 35            # px a measured blade's foot may move back into the clump
RING_H = 3                  # height of one rope ring (two per post, one voxel apart)

A_R, E_R = math.radians(VIEW["azimuth"]), math.radians(VIEW["elevation"])
SA, CA, SE, CE = math.sin(A_R), math.cos(A_R), math.sin(E_R), math.cos(E_R)
FWD = np.array([SA * CE, CA * CE, -SE])

STONE = ["stone0", "stone1", "stone2", "stone3"]
STONE_TOP = ["stop0", "stop1", "stop2", "stop3"]          # the same shades lit from above
MOSS = ["moss0", "moss1", "moss2", "moss3"]
WOOD = ["wood0", "wood1", "wood2", "wood3"]
ROPE = ["rope0", "rope1", "rope2"]
BLADES = {
    "lime": ["lime0", "lime1", "lime2", "lime3"],
    "green": ["grn0", "grn1", "grn2"],
    "teal": ["teal0", "teal1", "teal2"],
}

# ---------------------------------------------------------------- measured on the sheet
# heaps: ground centre c (px); cubes (u, v of the top-face centre, edge or (x, y) edges, depth b);
# moss lobes (u, v, r units); blades (u tip, v tip, v foot, family, width); fillers
# (count, u0, u1, v foot 0, v foot 1)
HEAPS = {
    "rocks_large": {
        "c": (333, 482),
        "cubes": [(361, 125, 12, 6), (294, 225, 11, 2), (372, 248, 4, 4), (374, 280, 9, -2),
                  (236, 320, 10, -4), (520, 320, 6, 2), (172, 388, 6, -6), (240, 405, 9, -10),
                  (365, 420, 10, -8), (103, 412, 6, -4), (550, 418, 7, -6), (124, 459, 6, None),
                  (299, 456, 6, -14), (192, 502, 6, None), (346, 524, 7, None), (445, 516, 6, None),
                  (499, 490, 5, None)],
        "moss": [(272, 118, 3), (298, 100, 2.5), (255, 160, 2.5), (232, 205, 2),
                 (440, 228, 3), (478, 265, 3), (528, 318, 3), (556, 332, 2),
                 (300, 385, 3.5), (268, 402, 2.5), (90, 355, 3), (66, 362, 2),
                 (188, 450, 3), (198, 500, 3), (168, 530, 2.5), (243, 462, 2.5), (268, 446, 2),
                 (420, 500, 3), (440, 488, 2.5), (575, 430, 3), (592, 414, 2),
                 (245, 520, 2.5), (250, 560, 2)],
        "blades": [(140, 232, 485, "lime", 2), (175, 212, 480, "lime", 1), (192, 168, 470, "lime", 2),
                   (207, 200, 470, "teal", 1), (228, 150, 460, "teal", 2), (160, 280, 490, "green", 1),
                   (118, 330, 490, "lime", 1),
                   (432, 222, 540, "teal", 2), (447, 275, 545, "lime", 2), (470, 330, 545, "green", 1),
                   (487, 295, 550, "lime", 1), (507, 360, 545, "green", 1), (522, 345, 540, "lime", 2),
                   (545, 405, 530, "teal", 1), (410, 300, 540, "lime", 1)],
        "fill": [(14, 115, 230, 460, 500), (16, 405, 560, 505, 550)],
    },
    "rocks_medium": {
        "c": (890, 477),
        "cubes": [(870, 232, 12, 6), (941, 293, 5, 2), (942, 331, 10, -2), (766, 343, (12, 17), -4),
                  (847, 420, 7, -10), (982, 455, (13, 12), -14), (1110, 421, 4, -4), (780, 517, 7, None)],
        "moss": [(760, 290, 4), (800, 300, 3), (740, 315, 2.5), (870, 400, 3.5), (900, 420, 3),
                 (920, 445, 3), (895, 462, 2.5), (1080, 520, 3), (1100, 532, 2), (670, 378, 2),
                 (885, 525, 2.5)],
        "blades": [(1045, 210, 535, "lime", 2), (1027, 255, 530, "teal", 2), (975, 245, 520, "lime", 1),
                   (1077, 295, 535, "lime", 1), (1000, 370, 530, "lime", 1), (1040, 370, 540, "green", 1),
                   (1045, 410, 545, "lime", 1), (1092, 390, 535, "teal", 1), (1060, 330, 535, "teal", 1),
                   (720, 430, 565, "lime", 1), (775, 415, 565, "lime", 2), (683, 465, 560, "green", 1),
                   (752, 455, 570, "lime", 1), (700, 470, 565, "teal", 1), (805, 470, 570, "green", 1)],
        "fill": [(14, 970, 1095, 505, 545), (10, 680, 810, 545, 575)],
    },
    "seaweed_rocks": {
        "c": (175, 885),
        "cubes": [(125, 803, 7, 2), (57, 880, 5, None), (180, 890, 7, None), (237, 917, 4, None)],
        "moss": [(90, 905, 4), (140, 900, 4.5), (195, 880, 4), (235, 905, 3.5), (270, 885, 3),
                 (160, 860, 3.5), (115, 870, 3), (60, 900, 3), (200, 850, 3), (130, 935, 2.5),
                 (180, 925, 3), (100, 925, 3), (230, 930, 3)],
        "blades": [(185, 660, 905, "lime", 2), (255, 712, 900, "lime", 1), (62, 758, 890, "lime", 1),
                   (75, 705, 880, "teal", 1), (145, 730, 890, "green", 1), (215, 760, 895, "teal", 1),
                   (300, 790, 905, "teal", 1), (108, 700, 885, "lime", 1), (165, 690, 895, "green", 1)],
        "fill": [(30, 50, 300, 845, 915)],
    },
    "seaweed_tall": {
        "c": (490, 890),
        "cubes": [(377, 855, 4, 1), (503, 917, 4, None), (528, 898, 4, None)],
        "moss": [(390, 905, 4), (430, 890, 4.5), (470, 905, 4), (520, 895, 4), (560, 905, 4),
                 (595, 915, 3.5), (450, 860, 3), (545, 870, 3), (410, 870, 3), (470, 925, 3),
                 (420, 925, 3.5), (545, 935, 3)],
        "blades": [(470, 648, 915, "teal", 2), (465, 705, 915, "lime", 2), (535, 665, 905, "lime", 2),
                   (565, 705, 905, "teal", 1), (370, 745, 900, "lime", 1), (432, 715, 905, "teal", 1),
                   (500, 710, 910, "lime", 1), (605, 760, 905, "teal", 1), (540, 725, 905, "teal", 1),
                   (400, 760, 905, "lime", 1), (585, 730, 905, "lime", 1)],
        "fill": [(32, 365, 610, 850, 925)],
    },
    "seaweed_clump": {
        "c": (800, 900),
        "cubes": [(717, 906, 5, None), (825, 898, 5, None), (850, 926, 5, None)],
        "moss": [(690, 870, 4), (720, 890, 4), (770, 905, 4), (810, 915, 4), (860, 905, 4),
                 (900, 890, 4), (690, 840, 3), (880, 860, 3), (790, 880, 3.5), (760, 935, 3),
                 (700, 920, 3.5), (840, 940, 3.5), (900, 925, 3)],
        "blades": [(845, 742, 925, "teal", 2), (755, 750, 920, "lime", 2), (820, 767, 920, "lime", 1),
                   (705, 775, 915, "teal", 1), (900, 770, 915, "lime", 1), (735, 805, 920, "teal", 1),
                   (875, 800, 920, "lime", 1), (670, 820, 905, "lime", 1), (915, 835, 910, "teal", 1),
                   (780, 840, 925, "lime", 1), (855, 835, 925, "lime", 1), (805, 855, 930, "teal", 1)],
        "fill": [(30, 670, 920, 860, 935)],
    },
}

LAMP_AT = (1404, 587)              # ground centre of the lamp's plinth (px)
BOLLARDS = {      # ground centre (px), base edge/height, post edge/top, rope rings, loop reach/drop
    "bollard_short": {"at": (1070, 923), "base": (17, 7), "post": (11, 30), "rings": (13, 17),
                      "bolts": [(1106, 872), (1016, 862)], "side": (5, 2), "front": (0, 2), "loop": (10, 17)},
    "bollard_tall": {"at": (1373, 933), "base": (19, 9), "post": (11, 38), "rings": (19, 23),
                     "bolts": [(1417, 883), (1313, 843)], "side": (4, 3), "front": (0, 2), "loop": (7.5, 18)},
}
# rope loop outline: (reach along the corner diagonal, drop below the top ring), as fractions
LOOP = [(0.0, 0.0), (0.45, 0.03), (0.8, 0.2), (1.0, 0.5), (0.95, 0.78), (0.72, 0.97), (0.48, 0.92),
        (0.36, 0.66), (0.24, 0.36), (0.1, 0.12)]


def raw(u, v, z=0.0):
    """World (x, y) before the grid shift of the point at height z that the VIEW camera shows at
    sheet pixel (u, v) (sheet origin = world origin on the ground)."""
    a = u / PX
    b = (-v / PX - z * CE) / SE
    return np.array([a * CA + b * SA, -a * SA + b * CA])


def cube_geom(c, cube):
    """(x0, y0, sx, sy, top) of a heap cube before the shift."""
    u, v, s, b = cube
    sx, sy = (s, s) if np.isscalar(s) else s
    top = float(min(sx, sy)) if b is None else ((c[1] - v) / PX - b * SE) / CE
    x, y = raw(u, v, top)
    return x - sx / 2, y - sy / 2, sx, sy, top


def layout():
    """Grid shift (added to raw()) and grid size, from every piece's footprint."""
    pts = []
    for h in HEAPS.values():
        for cube in h["cubes"]:
            x0, y0, sx, sy, _ = cube_geom(h["c"], cube)
            pts += [(x0, y0), (x0 + sx, y0 + sy)]
        pts += [raw(bl[0], bl[2]) for bl in h["blades"]]
    for u, v in [LAMP_AT] + [b["at"] for b in BOLLARDS.values()]:
        g = raw(u, v)
        pts += [g - 32, g + 32] if (u, v) == LAMP_AT else [g - 18, g + 18]
    pts = np.array(pts, float)
    lo, hi = pts.min(0) - MARGIN, pts.max(0) + MARGIN
    shift = -np.floor(lo)
    W, D = (int(math.ceil(s)) for s in hi + shift)
    return shift, (W, D, HEIGHT)


def hash01(a, b, c, salt=0):
    a, b, c = (np.floor(np.asarray(t, float)).astype(np.int64) for t in (a, b, c))
    h = (a * 73856093) ^ (b * 19349663) ^ (c * 83492791) ^ (salt * 2654435761 + 12345)
    h = (h * 2654435761) % (2 ** 32)
    return h.astype(np.float64) / 2 ** 32


def palette(m: Model):
    p = m.pal
    for n, hx in zip(STONE, ("#8f8780", "#a39a91", "#b6ada3", "#c8bfb4")):
        p.add(n, hx)
    for n, hx in zip(STONE_TOP, ("#b9ad9f", "#c9bcad", "#d6c9b8", "#e2d5c4")):
        p.add(n, hx)
    p.add("stone", "#a39a91")
    for n, hx in zip(MOSS, ("#24480a", "#3d710d", "#5d9a12", "#83bd18")):
        p.add(n, hx)
    p.add("moss_tip", "#a6d42a")
    for n, hx in zip(BLADES["lime"], ("#4d860c", "#6fab0e", "#92c818", "#b0dc2c")):
        p.add(n, hx)
    for n, hx in zip(BLADES["green"], ("#1c5418", "#2c7020", "#43902a")):
        p.add(n, hx)
    for n, hx in zip(BLADES["teal"], ("#02302a", "#05463a", "#0b5c49")):
        p.add(n, hx)
    for n, hx in zip(WOOD, ("#3e2316", "#4d2c1b", "#5b3420", "#6a3f27")):
        p.add(n, hx)
    for n, hx in zip(ROPE, ("#a87538", "#cd9a58", "#e2ba7c")):
        p.add(n, hx)
    p.add("iron", "#5a606c")
    p.add("iron_hi", "#7a8290")
    p.add("frame", "#2e1b10")
    p.add("glow0", "#fff6c0", emit=1.0)
    p.add("glow1", "#ffd44a", emit=1.0)
    p.add("glow2", "#f39a1e", emit=0.8)


# ---------------------------------------------------------------- shared helpers

def first_hit(m: Model, p0):
    """First filled voxel along the camera ray through world point p0 (design units), or None."""
    ts = np.arange(-500.0, 500.0, 0.25 / m.res)
    pts = p0[None, :] + ts[:, None] * FWD[None, :]
    idx = np.floor(pts * m.res).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(m.v.shape)), axis=1)
    if not ok.any():
        return None
    hit = m.v[tuple(idx[ok].T)] > 0
    if not hit.any():
        return None
    return pts[ok][int(np.argmax(hit))]


def wood(m: Model, x, y, z, w, d, h, salt=0):
    """Wooden block with vertical grain streaks (one colour per column, changing every 5 up)."""
    m.box(x, y, z, w, d, h, WOOD[1])
    ids = np.array([m.pal.idx(c) for c in WOOD], np.uint8)
    p = np.cumsum([0.2, 0.35, 0.3, 0.15])

    def fn(X, Y, Z):
        k = np.searchsorted(p, hash01(X, Y, np.floor(Z / 5), salt + 3) * 0.999, side="right")
        return ids[np.clip(k, 0, len(ids) - 1)]
    m.paint_fn(x, y, z, w, d, h, fn)


def rope_ring(m: Model, cx, cy, half, z, h):
    """Square rope ring of half-width `half` around a post centred on (cx, cy): twisted stripes."""
    for k, c in enumerate(ROPE):
        m.where(cx - half, cy - half, z, 2 * half, 2 * half, h,
                lambda X, Y, Z, k=k: (np.floor(X) + np.floor(Y) + np.floor(Z)) % 3 == k, c, only_empty=True)


def blade(m: Model, x, y, h, fam, w):
    """Seaweed blade: a column of w x w cubes leaning to one side (a step every few cubes, now
    and then back), with single leaf cubes sticking out, dark at the foot and lighter toward
    the tip (the top two cubes of a wide blade are single)."""
    rng = m.rng
    ramp = BLADES[fam]
    axis = int(rng.integers(2))
    lean = float(rng.choice([-1, 1]))
    px, py = float(x), float(y)
    run = int(rng.integers(3, 7))
    n = max(int(round(h)), 2)
    for z in range(n):
        t = z / (n - 1)
        k = int(np.clip(t * len(ramp) + rng.uniform(-0.4, 0.4), 0, len(ramp) - 1))
        ww = 1 if (w > 1 and z >= n - 2) else w
        m.box(round(px), round(py), z, ww, ww, 1, ramp[k], only_empty=True)
        if z < n - 2 and rng.random() < LEAF_RATE:
            ox, oy = [(-1, 0), (ww, 0), (0, -1), (0, ww)][int(rng.integers(4))]
            m.box(round(px) + ox, round(py) + oy, z, 1, 1, int(rng.integers(1, 3)), ramp[k], only_empty=True)
        run -= 1
        if run == 0:
            step = lean if rng.random() < 0.75 else -lean
            if axis == 0:
                px += step
            else:
                py += step
            run = int(rng.integers(3, 7))


# ---------------------------------------------------------------- pieces

def heap(m: Model, h, shift):
    c = h["c"]
    for cube in h["cubes"]:
        x0, y0, sx, sy, top = cube_geom(c, cube)
        m.box(round(x0 + shift[0]), round(y0 + shift[1]), 0, sx, sy, max(1, round(top)), "stone")
    lobes = []
    for u, v, r in h["moss"]:
        p0 = np.array([*(raw(u, v) + shift), 0.0])
        hit = first_hit(m, p0)
        if hit is not None:
            q = hit - FWD * r * 0.3
            lobes.append((q[0], q[1], max(q[2], r * 0.5), r))
            continue
        # nothing behind that pixel: a clump at the heap's centre depth, hanging down as a
        # mossy vine until it reaches a stone or the ground (no floating clumps)
        z = max((c[1] - v) / PX / CE, r * 0.6)
        x, y = raw(u, v, z) + shift
        while z >= r * 0.5:
            lobes.append((x, y, z, r))
            if m.get(int(x), int(y), max(int(z - r), 0)):
                break
            z -= r * 1.3
    if lobes:
        m.foliage(lobes, MOSS, clump=1.3, tips="moss_tip", tip_rate=0.2)
    rng = m.rng
    # listed blades keep their tip; their foot moves back by up to FOOT_JITTER px (shorter
    # blade, same outline) so a clump has depth
    blades = [(u, vt, vf - rng.uniform(0, FOOT_JITTER), fam, w) for u, vt, vf, fam, w in h["blades"]]
    tips = sorted((bl[0], bl[1]) for bl in blades)
    tu, tv = np.array(tips, float).T
    for n, u0, u1, f0, f1 in h.get("fill", []):
        for _ in range(n):
            u = rng.uniform(u0, u1)
            fv = rng.uniform(f0, f1)
            env = float(np.interp(u, tu, tv))
            tip = fv - (fv - env) * rng.uniform(0.4, 0.9)
            fam = str(rng.choice(["lime", "green", "teal"], p=[0.45, 0.25, 0.3]))
            blades.append((u, tip, fv, fam, int(rng.choice([1, 2], p=[0.6, 0.4]))))
    for u, vt, vf, fam, w in blades:
        x, y = raw(u, vf) + shift
        hgt = (vf - vt) / (PX * CE)
        blade(m, x - w / 2, y - w / 2, hgt, fam, w)


def lamp_post(m: Model, shift):
    gx, gy = np.round(raw(*LAMP_AT) + shift)
    W = lambda x, y, z, w, d, h, salt=0: wood(m, gx + x, gy + y, z, w, d, h, salt)   # noqa: E731
    W(-7, -7, 0, 14, 14, 5, 1)              # plinth
    W(-6, -6, 5, 12, 12, 4, 2)              # upper step
    W(-5, -5, 9, 10, 10, 9, 3)              # core under the rope
    W(-5, -5, 18, 10, 10, 4, 4)             # collar
    W(-3, -3, 22, 6, 6, 48, 5)              # shaft
    W(-4, -4, 70, 8, 8, 4, 6)               # cap
    W(-28, -2, ARM_Z, 36, 4, 6, 7)          # cross arm (lantern side = -x)
    W(-22, -3, ARM_Z - 1, 3, 6, 8, 8)       # strap the lantern hangs from
    m.line((gx - 4, gy, 50), (gx - 15, gy, ARM_Z - 1), WOOD[2], r=1)   # brace
    rope_ring(m, gx, gy, 6, 9, 4)
    rope_ring(m, gx, gy, 6, 14, 4)
    # lantern under the arm
    lx, ly = gx - 20, gy
    m.box(lx - 5, ly - 5, 41, 10, 10, 2, "frame")
    m.box(lx - 4, ly - 4, 43, 8, 8, 9, "glow1")
    ids = [m.pal.idx(c) for c in ("glow0", "glow1", "glow2")]

    def glass(X, Y, Z):
        along = np.minimum(np.abs(X + 0.5 - lx), np.abs(Y + 0.5 - ly))
        t = np.maximum(along / 4.0, np.abs(Z + 0.5 - 47.5) / 4.5)
        return np.where(t < 0.55, ids[0], np.where(t < 0.85, ids[1], ids[2])).astype(np.uint8)
    m.paint_fn(lx - 4, ly - 4, 43, 8, 8, 9, glass)
    for dx in (-4, 3):
        for dy in (-4, 3):
            m.box(lx + dx, ly + dy, 43, 1, 1, 9, "frame")
    m.box(lx - 5, ly - 5, 52, 10, 10, 1, "frame")
    m.box(lx - 3, ly - 3, 53, 6, 6, 2, "frame")
    m.box(lx - 1, ly - 1, 55, 2, 2, 1, "iron")
    m.box(lx - 1, ly, 56, 1, 1, ARM_Z - 57, "iron")          # chain up to the strap


def bollard(m: Model, b, shift):
    gx, gy = np.round(raw(*b["at"]) + shift)
    bs, bh = b["base"]
    ps, top = b["post"]
    lo = -(bs // 2)
    wood(m, gx + lo, gy + lo, 0, bs, bs, bh, 11)
    pl = -(ps // 2)
    wood(m, gx + pl, gy + pl, bh, ps, ps, top - bh, 12)
    cx, cy = gx + pl + ps / 2, gy + pl + ps / 2
    half = ps / 2 + 1
    r1, r2 = b["rings"]
    rope_ring(m, cx, cy, half, r1, RING_H)
    rope_ring(m, cx, cy, half, r2, RING_H)
    # bolts: on the left (-x) face, the front (-y) face and on top of the base
    sy, sz = b["side"]
    m.box(gx + lo - 1, gy + sy, sz, 3, 3, 3, "iron")
    fx, fz = b["front"]
    m.box(gx + fx - 1, gy + lo - 1, fz, 3, 3, 3, "iron")
    for u, v in b["bolts"]:
        x, y = raw(u, v, bh + 1.5) + shift
        m.box(round(x - 1.5), round(y - 1.5), bh, 3, 3, 3, "iron")
    m.sprinkle(["iron_hi"], 0.3, target="iron")
    # rope loop hanging off the right corner (+x, -y), in the vertical plane along the diagonal
    corner = np.array([cx + ps / 2, cy - ps / 2])
    d = np.array([1.0, -1.0]) / math.sqrt(2)
    zt = r2 + RING_H
    span, drop = b["loop"]
    pts = [(*(corner + d * (s * span + 0.8)), zt - t * drop) for s, t in LOOP]
    m.tube(pts, 1.2, ROPE, only_empty=True)


# ---------------------------------------------------------------- build

def build() -> Model:
    shift, grid = layout()
    m = Model(*grid, seed=7, res=RES)
    palette(m)
    for name, h in HEAPS.items():
        with m.part(name):
            heap(m, h, shift)
    with m.part("lamp_post"):
        lamp_post(m, shift)
    for name, b in BOLLARDS.items():
        with m.part(name):
            bollard(m, b, shift)
    stone_texture(m)
    # shading and grain of the big flat materials from the picture; leaves keep their own ramps
    m.paint_reference(REFERENCE, VIEW, colors=80, tol=30, cutout=CUTOUT,
                      only=STONE + STONE_TOP + WOOD + ROPE)
    return m


def stone_texture(m: Model):
    """Pale stone mottled in one-unit cells (mostly the middle shades), lighter on top faces."""
    ids = np.array([m.pal.idx(c) for c in STONE], np.uint8)
    p = np.cumsum([0.1, 0.3, 0.42, 0.18])
    v = m.v
    mask = v == m.pal.idx("stone")
    X, Y, Z = (a / m.res for a in np.nonzero(mask))
    k = np.searchsorted(p, hash01(X, Y, Z, 21) * 0.999, side="right")
    v[mask] = ids[np.clip(k, 0, len(ids) - 1)]
    open_top = np.ones(v.shape, bool)
    open_top[:, :, :-1] = v[:, :, 1:] == 0
    for c, top in zip(STONE, STONE_TOP):
        v[(v == m.pal.idx(c)) & open_top] = m.pal.idx(top)
