"""Glowing water raindrop (a falling drop drawn as a long square streak) —
reference/1aac502e-faee-4daf-bc5f-4aa8a1dc45be.png

Not an icicle: the material is clear water (glass, water blue), lit from inside.

Layout (x/y the square cross-section with y=0 front, z up, tip at z=0):
  cap      small CAP_W square block on top of the column
  column   S x S square streak, MAIN_H tall, read as stacked segments (SEGS) with
           a light seam between them
  tail     stepped taper under the column (TIERS, top to bottom), ending in a thin
           2 x 2 tip — the leading end of the falling drop
  surface  the inner blocks seen through the water make the faces alternate light/dark
           down the column: FRONT_BANDS / LEFT_BANDS (measured from the column top);
           the two silhouette edges (back-left, front-right) glow blue with a cyan glint
           band next to them, the taper gets bluer and glows toward the tip
  inside   clear water glass with a thin emissive core down the middle (the glow)
  camera   front-left, looking slightly down (positive azimuth)
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0808"
REFERENCE = "reference/1aac502e-faee-4daf-bc5f-4aa8a1dc45be.png"
VIEW = {"azimuth": 36, "elevation": 27, "fov": 0}

S = 12                      # column cross-section
MAIN_H = 92                 # column height
CAP_W, CAP_H = 8, 3         # cap on top
TIERS = [(10, 10), (6, 9), (4, 2), (2, 3)]   # (width, height) of the taper, top to bottom
TIER_DY = -1                # the taper sits one voxel toward the front (not the tip)
SEGS = [14, 22, 20, 18]     # segment lengths from the column top (the rest is the last one)
# face tones by depth below the column top: (from, to, colour)
FRONT_BANDS = [(0, 19, "f_a"), (19, 31, "f_b"), (31, 36, "f_a"), (36, 47, "f_c"),
               (47, 74, "f_d"), (74, MAIN_H, "f_e")]
LEFT_BANDS = [(0, 13, "l_a"), (13, 25, "l_b"), (25, 34, "l_a"), (34, 46, "l_c"),
              (46, 74, "l_d"), (74, MAIN_H, "l_e")]
F_CYAN, F_RIM = 2, 2        # front face: cyan band, then the glowing edge (from the right)
L_GLINT, L_RIM = 2, 1       # left face: glint band, then the glowing edge (from the back)
# taper colours per tier, top to bottom: (front, left)
TIER_COLORS = [("t2_front", "t2_left"), ("t3_front", "t3_left"), ("t4", "t4"), ("tip", "tip")]

TAIL_H = sum(h for _, h in TIERS)
Z_MAIN = TAIL_H                         # column bottom
Z_TOP = Z_MAIN + MAIN_H                 # column top
GZ = Z_TOP + CAP_H


def palette(m: Model):
    p = m.pal
    # front faces sampled along x=530 (/0.9), left faces along x=475 (/0.76, clipped)
    p.add("water", "#a9c6ea", glass=0.5)
    p.add("f_a", "#a3b2cf", glass=0.5)
    p.add("f_b", "#8096b5", glass=0.5)
    p.add("f_c", "#6b82a2", glass=0.5)
    p.add("f_d", "#99adca", glass=0.5)
    p.add("f_e", "#dde9f9", glass=0.5)
    p.add("l_a", "#ffffff", glass=0.5)
    p.add("l_b", "#768db2", glass=0.5)
    p.add("l_c", "#a8bfe4", glass=0.5)
    p.add("l_d", "#fbffff", glass=0.5)
    p.add("l_e", "#6da0e2", glass=0.5)
    p.add("f_cyan", "#85d1ff", glass=0.5)
    p.add("seam", "#e6f0fb", glass=0.5)
    p.add("top", "#8ab4e6", glass=0.5)
    p.add("cap_top", "#c6e1f9", glass=0.5)
    # the taper reads bluer and glows more toward the tip
    p.add("t2_front", "#abd8ff", glass=0.5)
    p.add("t2_left", "#c8e2f8", emit=0.3)
    p.add("t3_front", "#e8f4ff", glass=0.5)
    p.add("t3_left", "#86befa", emit=0.3)
    p.add("t4", "#51a9f2", emit=0.5)
    p.add("tip", "#e9fcfe", emit=0.6)
    # glowing edges / glint / core
    p.add("glint", "#b4e2fc", emit=0.4)
    p.add("rim_l", "#8cb4e8", emit=0.5)
    p.add("rim_f", "#68b2ec", emit=0.5)
    p.add("core", "#cfeaff", emit=0.6)


# ---------------------------------------------------------------- helpers

def shift(a: np.ndarray, d) -> np.ndarray:
    """out[p] = a[p + d], False outside the grid."""
    out = np.zeros_like(a)
    src = tuple(slice(max(k, 0), a.shape[i] + min(k, 0)) for i, k in enumerate(d))
    dst = tuple(slice(max(-k, 0), a.shape[i] + min(-k, 0)) for i, k in enumerate(d))
    out[dst] = a[src]
    return out


def exposed(m: Model, d) -> np.ndarray:
    """Filled voxels whose neighbour in direction d is empty."""
    f = m.v > 0
    return f & ~shift(f, d)


def paint(m: Model, mask: np.ndarray, color: str):
    m.v[mask & (m.v > 0)] = m.pal.idx(color)


def levels():
    """(z0, z1, x offset, y offset, width) of every stacked block, bottom to top."""
    out, z = [], 0
    for w, h in reversed(TIERS):
        o = (S - w) // 2
        out.append((z, z + h, o, o + (TIER_DY if w > 2 else 0), w))
        z += h
    out.append((Z_MAIN, Z_TOP, 0, 0, S))
    o = (S - CAP_W) // 2
    out.append((Z_TOP, GZ, o, o, CAP_W))
    return out


def seams():
    """z of the seam row at the bottom of every column segment except the last."""
    out, z = [], Z_TOP
    for n in SEGS:
        z -= n
        out.append(z)
    return out


def depth_band(Z, bands):
    """(mask, colour) pairs for bands measured downward from the column top."""
    d = Z_TOP - 1 - Z
    return [((d >= a) & (d < b), c) for a, b, c in bands]


# ---------------------------------------------------------------- parts

def body(m: Model):
    for z0, z1, ox, oy, w in levels():
        m.box(ox, oy, z0, w, w, z1 - z0, "water")


def core(m: Model):
    c = S // 2 - 1
    m.box(c, c, 6, 2, 2, GZ - 8, "core")


def surface(m: Model):
    X, Y, Z = np.indices(m.v.shape)
    side_y = exposed(m, (0, -1, 0)) | exposed(m, (0, 1, 0))
    side_x = exposed(m, (-1, 0, 0)) | exposed(m, (1, 0, 0))
    main = (Z >= Z_MAIN) & (Z < Z_TOP)
    # column: tones by depth, then the seams between segments (side faces only)
    for mask, c in depth_band(Z, FRONT_BANDS):
        paint(m, side_y & main & mask, c)
    for mask, c in depth_band(Z, LEFT_BANDS):
        paint(m, side_x & main & mask, c)
    for z in seams():
        paint(m, (side_x | side_y) & (Z == z), "seam")
    # cyan band + glowing edge on the front face (right), glint + glowing edge on the left
    paint(m, side_y & main & (X >= S - F_CYAN - F_RIM), "f_cyan")
    paint(m, side_y & main & (X >= S - F_RIM), "rim_f")
    paint(m, side_x & main & (Y >= S - L_GLINT - L_RIM), "glint")
    paint(m, side_x & main & (Y >= S - L_RIM), "rim_l")
    # taper, tier by tier (levels() lists them tip first)
    for (z0, z1, ox, oy, w), (front, left) in zip(levels(), reversed(TIER_COLORS)):
        zs = (Z >= z0) & (Z < z1)
        paint(m, side_y & zs, front)
        paint(m, side_x & zs, left)
        if w == TIERS[0][0]:
            paint(m, zs & side_x & (X == ox) & (Y == oy + w - 1), "rim_l")
            paint(m, zs & side_y & (Y == oy) & (X == ox + w - 1), "rim_f")
    # cap sides and tops
    cap = Z >= Z_TOP
    paint(m, side_y & cap, "f_a")
    paint(m, side_x & cap, "l_a")
    top = exposed(m, (0, 0, 1))
    paint(m, top, "top")
    paint(m, top & cap, "cap_top")


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(S, S, GZ, seed=1)
    palette(m)
    body(m)
    core(m)
    surface(m)
    return m
