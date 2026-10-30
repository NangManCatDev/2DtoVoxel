"""Hanging moss kit — reference/c292f7f1-fbf0-482c-9040-be5180b7bb89.png

Kit sheet: six clumps of hanging moss built from loose cubes, on a dark olive backdrop.
Each clump is a "mat" (a slab of cubes a few cubes deep, running along world x) with
strands of cubes dripping down from it and a few loose drops below. Cubes are lime (lit,
sticking out) or teal (recessed); every cube has one flat colour.

The sheet is seen from the front-right and a little above (az 330 / el 15, orthographic:
the right side faces of the cubes show, top faces are thin). Every clump is described in
REFERENCE PIXELS read off `voxtool ref grid` (mat top/bottom outline, strand columns,
drops); to_world() turns a reference pixel plus a world depth y into world (x, z), so the
front view matches the sheet by construction. Each clump is its own m.part().

The reference's cut-out (moss vs backdrop) decides where cubes go inside those outlines,
so the mats stay as airy as in the picture: coverage() = share of moss over a cube's
screen footprint. Each cube takes the palette colour nearest to the reference under its
front face (ref_color), so lime and teal cubes sit where the picture has them.

Layout (x right, y depth with y=0 front, z up):
  mat     one world lattice of CELL cells per depth layer (LAYERS), sheared with depth so
          each layer covers the same outline on screen; front layer sparse, back layer full
  strand  cubes stacked down from the strand top, each one shifted up to 2 voxels sideways
          and sized 2-4 to follow the reference; a second cube beside it where the strand
          is two cubes wide; gaps of up to MAX_GAP voxels (loose cubes below a strand)
  drop    a single loose cube, nudged onto the reference's cube
"""
import math
import os

import numpy as np

from voxtool import Model

NAME = "c292f7f1_fbf0_482c_9040_be5180b7bb89"
REFERENCE = "reference/c292f7f1-fbf0-482c-9040-be5180b7bb89.png"
AZ, EL = 330, 15
VIEW = {"azimuth": AZ, "elevation": EL, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 1

PX = 8.0                   # reference px per voxel (a 3-voxel mat cube is ~33 px wide, front + side)
IMG_W, IMG_H = 1536, 1024
DEPTH = 10                 # mat depth along world y (voxels)
CELL = 3                   # mat lattice pitch = the usual cube size
LAYERS = [0.45, 0.7, 1.0]  # front .. back layer: chance that a cell (with moss in the reference) gets a cube
SIZES, SIZE_P = (2, 3, 4), (0.15, 0.65, 0.2)
STRAND_BONUS = {c: 0.05 * c for c in (4, 3, 2)}    # strand cube sizes tried, bigger ones preferred
COVER, COVER_R = 0.7, 0.55  # a cube needs this share of moss in the reference within COVER_R x its size
COVER_SIDE = 0.85          # ... and a strand's second cube this much
MAX_GAP = 6                # voxels a strand may skip to reach a loose cube below it
STRAND_Y = DEPTH // 3
FRONT_SHADE = 0.9          # the preview's front-face shading (reference colour / this = base colour)
MARGIN = 4

# name, base colour (reference front faces / 0.9). No near-black: the reference's darkest
# patches are shadows between cubes, which MagicaVoxel renders by itself.
MOSS = [("lime_hi", "#9eb243"), ("lime", "#7c9330"), ("olive", "#5a7524"), ("green", "#34571f"),
        ("teal_hi", "#2f7058"), ("teal", "#1f6a55"), ("teal_dk", "#11544a")]
L_WEIGHT = 0.5             # lightness counts half when matching a cube to the reference (hue decides)

# Clumps in reference pixels: mat outline top/bottom as (px, py) polylines, strands as
# (px, py_top, py_bottom), drops as (px, py, size).
PIECES = [
    dict(name="moss_long",
         top=[(55, 95), (80, 72), (130, 58), (300, 62), (350, 88), (450, 88), (500, 98), (700, 100),
              (750, 180), (880, 185), (900, 228), (1000, 250), (1060, 300)],
         bot=[(55, 220), (150, 265), (215, 315), (300, 330), (450, 320), (560, 355), (700, 370),
              (1000, 405), (1060, 365)],
         strands=[(242, 330, 490), (385, 320, 455), (585, 370, 560), (720, 370, 495), (822, 390, 555)],
         drops=[(400, 352, 3), (1045, 345, 2), (612, 425, 2), (845, 460, 3)]),
    dict(name="moss_hook",
         top=[(1035, 130), (1100, 108), (1200, 100), (1235, 72), (1270, 92), (1350, 98), (1420, 108),
              (1450, 185), (1485, 190)],
         bot=[(1035, 210), (1100, 235), (1200, 255), (1300, 262), (1420, 255), (1485, 235)],
         strands=[(1092, 235, 290), (1140, 230, 255), (1318, 255, 425), (1395, 250, 600),
                  (1425, 250, 470)],
         drops=[(1460, 300, 2), (1458, 420, 3), (1240, 270, 2), (1335, 330, 2)]),
    dict(name="moss_curtain",
         top=[(52, 562), (100, 555), (200, 552), (250, 545), (300, 600), (400, 602), (440, 628),
              (500, 632), (530, 655)],
         bot=[(52, 640), (100, 700), (200, 692), (300, 700), (400, 720), (450, 705), (530, 690)],
         strands=[(112, 700, 925), (255, 700, 870), (345, 720, 815), (415, 720, 925)],
         drops=[(155, 820, 3), (135, 912, 2)]),
    dict(name="moss_small",
         top=[(575, 722), (600, 695), (660, 672), (760, 662), (820, 680), (900, 700), (930, 738),
              (955, 742)],
         bot=[(575, 760), (600, 790), (700, 800), (800, 795), (900, 790), (955, 778)],
         strands=[(625, 790, 915), (740, 800, 905), (855, 790, 965), (785, 790, 830)],
         drops=[(630, 890, 2)]),
    dict(name="moss_tuft",
         top=[(1030, 558), (1080, 552), (1140, 542), (1180, 528), (1240, 540), (1270, 590),
              (1315, 615)],
         bot=[(1030, 610), (1080, 655), (1240, 660), (1315, 645)],
         strands=[(1088, 650, 700), (1192, 660, 735)],
         drops=[(1105, 690, 2)]),
    dict(name="moss_ledge",
         top=[(1008, 828), (1060, 795), (1150, 792), (1250, 795), (1350, 788), (1420, 778),
              (1480, 795), (1500, 830)],
         bot=[(1008, 880), (1060, 900), (1250, 905), (1400, 900), (1500, 870)],
         strands=[(1288, 900, 970), (1398, 895, 935), (1100, 890, 920)],
         drops=[]),
]


def palette(m: Model):
    for name, hex_color in MOSS:
        m.pal.add(name, hex_color)


# ------------------------------------------------------------------ reference pixels <-> world

def _axes():
    A, E = math.radians(AZ), math.radians(EL)
    right = (math.cos(A), -math.sin(A))
    up = (math.sin(E) * math.sin(A), math.sin(E) * math.cos(A), math.cos(E))
    return right, up


RIGHT, UP = _axes()


def to_world(px, py, y):
    """Reference pixel (px, py) seen at world depth y -> world (x, z), before the grid offset."""
    u, v = px / PX, -py / PX
    x = (u - RIGHT[1] * y) / RIGHT[0]
    z = (v - UP[0] * x - UP[1] * y) / UP[2]
    return x, z


def to_screen(x, y, z):
    """World point (before the grid offset) -> reference pixel."""
    u = RIGHT[0] * x + RIGHT[1] * y
    v = UP[0] * x + UP[1] * y + UP[2] * z
    return u * PX, -v * PX


def _frame():
    """Grid size and (whole-voxel) offset so the whole sheet fits with a margin."""
    pts = [to_world(px, py, y) for px in (0, IMG_W) for py in (0, IMG_H) for y in (0, DEPTH)]
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    off = (MARGIN - math.floor(min(xs)), MARGIN, MARGIN - math.floor(min(zs)))
    size = (math.ceil(max(xs) - min(xs)) + 2 * MARGIN, DEPTH + 2 * MARGIN,
            math.ceil(max(zs) - min(zs)) + 2 * MARGIN)
    return size, off


GRID, OFF = _frame()


def _profile(pts, px):
    a = np.array(pts, float)
    return float(np.interp(px, a[:, 0], a[:, 1]))


# ------------------------------------------------------------------ what the reference shows

_REF = {}


def _reference():
    if not _REF:
        from PIL import Image
        from voxtool.score import reference_cutout
        cut = np.asarray(reference_cutout(REFERENCE, os.path.join("output", "_ref"), **CUTOUT))
        _REF["mask"] = cut[..., 3] > 127
        _REF["rgb"] = np.asarray(Image.open(REFERENCE).convert("RGB")).astype(np.float64)
    return _REF


def _window(px, py, r):
    x0, x1 = int(max(px - r, 0)), int(min(px + r, IMG_W))
    y0, y1 = int(max(py - r, 0)), int(min(py + r, IMG_H))
    return (slice(y0, y1), slice(x0, x1)) if x1 > x0 and y1 > y0 else None


def coverage(x, y, z, c):
    """Share of moss (not backdrop) in the reference over the screen footprint of a size-c
    cube with its low corner at world (x, y, z)."""
    sl = _window(*to_screen(x + c / 2, y + c / 2, z + c / 2), COVER_R * c * PX)
    return float(_reference()["mask"][sl].mean()) if sl else 0.0


def ref_color(m: Model, x, y, z, c):
    """Palette colour nearest (CIE Lab) to the reference's median colour under the cube's
    front face, the front shading taken out."""
    from voxtool.score import _lab
    ref = _reference()
    sl = _window(*to_screen(x + c / 2, y, z + c / 2), 0.4 * c * PX)
    pix = ref["rgb"][sl][ref["mask"][sl]] if sl else np.zeros((0, 3))
    if len(pix) < 4:
        return "teal_dk"
    want = _lab(np.clip(np.median(pix, axis=0) / FRONT_SHADE, 0, 255))
    names = [n for n, _ in MOSS]
    base = _lab(m.pal.rgba[[m.pal.idx(n) for n in names], :3].astype(np.float64))
    d = base - want
    d[:, 0] *= L_WEIGHT
    return names[int(np.argmin(np.linalg.norm(d, axis=1)))]


# ------------------------------------------------------------------ cubes (world coords, low corner, size)

def mat_cubes(m: Model, p):
    """One world lattice of CELL-sized cells per depth layer, sheared with depth so every
    layer covers the same outline on screen. A cell gets a cube when its centre lies inside
    the outline and the reference shows moss over the cube (smaller cubes at the fringe)."""
    out = []
    px0, px1 = p["top"][0][0], p["top"][-1][0]
    py0, py1 = min(q[1] for q in p["top"]), max(q[1] for q in p["bot"])
    for li, prob in enumerate(LAYERS):
        yl = round(li * (DEPTH - CELL) / (len(LAYERS) - 1))
        corners = [to_world(px, py, yl + CELL / 2) for px in (px0, px1) for py in (py0, py1)]
        xa, xb = min(c[0] for c in corners) - CELL, max(c[0] for c in corners) + CELL
        za, zb = min(c[1] for c in corners) - CELL, max(c[1] for c in corners) + CELL
        ox, oz = to_world(0, 0, yl + CELL / 2)          # lattice origin follows the shear
        x = xa - ((xa - ox) % CELL)
        while x <= xb:
            z = za - ((za - oz) % CELL)
            while z <= zb:
                sx, sy = to_screen(x + CELL / 2, yl + CELL / 2, z + CELL / 2)
                if px0 <= sx <= px1 and _profile(p["top"], sx) <= sy <= _profile(p["bot"], sx):
                    c = int(m.rng.choice(SIZES, p=SIZE_P))
                    j = [int(m.rng.choice([-1, 0, 0, 0, 1])) for _ in range(3)]
                    cx, cz = round(x + (CELL - c) / 2) + j[0], round(z + (CELL - c) / 2) + j[2]
                    cy = int(np.clip(yl + j[1], 0, DEPTH - c))
                    while c > min(SIZES) and coverage(cx, cy, cz, c) < COVER:
                        c -= 1                              # a smaller cube at the fringe
                    if coverage(cx, cy, cz, c) >= COVER and m.rng.random() < prob:
                        out.append((cx, cy, cz, c))
                z += CELL
            x += CELL
    return out


def strand_cubes(m: Model, s):
    """Cubes stacked down from py_top to py_bottom, each one placed (shift, size) where the
    reference shows the most moss; a second cube beside it where the strand is wider."""
    px, py0, py1 = s
    out = []
    y = STRAND_Y
    wx, wz = to_world(px, py0, y + 1.5)
    x, top = round(wx - 1.5), round(wz + 1.5)
    bottom = to_world(px, py1, y + 1.5)[1]
    gap = 0
    while top > bottom - 1:
        best = None
        for c in STRAND_BONUS:
            for dx in range(-2, 3):
                cov = coverage(x + dx, y, top - c, c)
                score = cov + STRAND_BONUS[c] - 0.04 * abs(dx)
                if cov >= COVER and (best is None or score > best[0]):
                    best = (score, c, x + dx)
        if best is None:
            top -= 1
            gap += 1
            if gap > MAX_GAP:
                break
            continue
        _, c, x = best
        gap = 0
        out.append((x, y + int(m.rng.integers(-1, 2)), top - c, c))
        for side in (x - c, x + c):
            if coverage(side, y, top - c, c) >= COVER_SIDE:
                out.append((side, y + int(m.rng.integers(-1, 2)), top - c, c))
                break
        top -= c
    return out


def drop_cube(px, py, c):
    """A loose cube near (px, py), moved (up to 3 voxels) and sized onto the reference's."""
    wx, wz = to_world(px, py, STRAND_Y + c / 2)
    x0, z0 = round(wx - c / 2), round(wz - c / 2)
    best = None
    for cc in (c - 1, c, c + 1):
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                cov = coverage(x0 + dx, STRAND_Y, z0 + dz, cc)
                score = cov + 0.05 * cc - 0.02 * (abs(dx) + abs(dz))
                if cc >= 2 and cov >= COVER and (best is None or score > best[0]):
                    best = (score, (x0 + dx, STRAND_Y, z0 + dz, cc))
    return [best[1]] if best else []


def clump(m: Model, p):
    cubes = mat_cubes(m, p)
    for s in p["strands"]:
        cubes += strand_cubes(m, s)
    for d in p["drops"]:
        cubes += drop_cube(*d)
    for x, y, z, c in sorted(cubes, key=lambda k: -k[1]):          # back to front
        m.box(x + OFF[0], y + OFF[1], z + OFF[2], c, c, c, ref_color(m, x, y, z, c))


def build() -> Model:
    m = Model(*GRID, seed=11, res=RES)
    palette(m)
    for i, p in enumerate(PIECES):
        with m.part(f"{i + 1}_{p['name']}"):
            clump(m, p)
    return m
