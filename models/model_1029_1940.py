"""Five tall voxel trees in stone tree pits — reference/411116c5-948a-4926-8c88-94d93fec422d.png

Kit sheet: five tall, narrow trees in a row, each in a square tree pit (a ring of beige stone
blocks around a dark slate-green iron grate with bolted corner plates). Every tree, pit
included, is drawn inside its own m.part(), so each one is a separate object in the .vox.

  1 column    dense spindle crown (cypress), trunk only at the foot
  2 tiered    pointed top tuft over two broad tiers, trunk showing between them
  3 branched  straight trunk with six round leaf clusters on visible side branches
  4 cone      pointed top on a broad lumpy lower crown
  5 topiary   pointed top, a round tier, then clusters alternating left and right

The sheet is an orthographic view at az 45 / el ~33 (the pit edges slope equally to both
sides), so a screen-horizontal row is a world diagonal: the trees are spaced along (+x, -y).

Crowns are described in REFERENCE PIXELS read off `voxtool ref grid`: each lobe is
(px, py, radius_px) and the trunk is a polyline of (px, py, radius_vox). screen_to_world()
puts them on the trunk's plane; crown_depth() turns each crown into a round, upright one
with the same outline, foliage() covers it with leaf clumps over a dark core,
carve_to_reference() trims leaves that land on the sheet's background, and
paint_reference() takes the sheet's shading last.

Layout (x right, y depth with y=0 front, z up):
  pit     BASE x BASE footprint, stone ring RING wide and STONE_H high in BLOCK-long
          blocks; grate flush with the stone top: frame, bars at a GRATE_PITCH pitch,
          corner plates with bolts; dark soil below
  trunk   from the pit centre up into the crown (it stops inside it), root flare over the
          grate, bark streaks; the limbs seen in the sheet, thin branches into the crown
  crown   foliage() over the measured lobes (LOBE_SCALE x their measured radius), spread
          through the crown's depth
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_1940"
REFERENCE = "reference/411116c5-948a-4926-8c88-94d93fec422d.png"
AZ, EL = 45, 33
VIEW = {"azimuth": AZ, "elevation": EL}
CUTOUT = {"keep": "all"}
RES = 1

# reference measurements (pixels of the reference image)
PX = 7.78          # pixels per voxel: a 25-voxel pit edge spans 137.5 px sideways
GY = 613           # screen y of a pit centre at ground level (the same for all five)

# pit
BASE, RING, STONE_H, BLOCK = 25, 3, 4, 5
GRATE_PITCH = 3
# grid: pit centre of the left-most tree; the others follow along (+x, -y)
FIRST_X, FIRST_Y = 36, 186
GRID = (224, 224, 112)
LOBE_SCALE = 1.15  # measured lobe radii fall a little short of the sheet's lumpy outline
CLUMP = 1.7        # foliage clump radius (voxels)

LEAVES = ["leaf0", "leaf1", "leaf2", "leaf3", "leaf4"]
BARK = ["bark0", "bark1", "bark2", "bark3"]
STONES = ["stone0", "stone1", "stone2"]

# cx = screen x of the pit centre; lobes (px, py, r_px); trunk (px, py, r_vox) bottom-up;
# branch = (r0, r1) of the limbs into the lobes; depth = scale of the lobe copies' depth
TREES = [
    dict(name="column", cx=276.5, branch=(1.5, 1.0), depth=1.0,
         lobes=[(278, 60, 30), (283, 105, 45), (262, 150, 45), (310, 160, 42),
                (240, 210, 45), (310, 215, 45), (235, 275, 45), (320, 280, 45),
                (235, 340, 45), (320, 340, 45), (232, 405, 45), (318, 405, 45),
                (245, 455, 40), (310, 455, 42),
                (275, 200, 55), (277, 300, 60), (277, 400, 60)],
         trunk=[(277, 613, 3.2), (277, 560, 2.8), (275, 480, 2.5), (265, 380, 2.2), (280, 280, 1.9),
                (270, 180, 1.5), (277, 100, 1.0)]),
    dict(name="tiered", cx=676.5, branch=(1.6, 1.0), depth=1.0,
         lobes=[(677, 55, 28), (675, 100, 42), (665, 145, 50), (705, 140, 35),
                (630, 240, 40), (720, 260, 48), (670, 265, 45),
                (615, 370, 52), (705, 400, 62), (610, 440, 40), (650, 460, 40), (740, 440, 40)],
         trunk=[(676, 613, 3.2), (676, 560, 2.8), (674, 480, 2.5), (676, 340, 2.2), (670, 200, 1.8),
                (677, 100, 1.2)]),
    dict(name="branched", cx=1075, branch=(2.0, 1.3), depth=0.6,
         lobes=[(1070, 50, 38), (1095, 110, 50), (1050, 110, 28),
                (1022, 182, 50), (1140, 230, 55),
                (975, 280, 42), (1015, 305, 52),
                (1148, 385, 58), (997, 415, 52)],
         trunk=[(1075, 613, 3.0), (1073, 560, 2.6), (1072, 470, 2.4), (1077, 350, 2.2), (1080, 230, 1.9),
                (1078, 150, 1.6), (1080, 80, 1.1)],
         limbs=[[(1068, 485, 2.3), (1040, 452, 1.8), (1012, 425, 1.4)],
                [(1082, 485, 2.3), (1110, 450, 1.8), (1135, 405, 1.4)],
                [(1072, 378, 2.0), (1045, 352, 1.6), (1020, 318, 1.3)],
                [(1080, 312, 1.9), (1108, 287, 1.5), (1135, 245, 1.2)],
                [(1075, 242, 1.7), (1050, 217, 1.4), (1028, 190, 1.1)]]),
    dict(name="cone", cx=1488, branch=(1.6, 1.0), depth=1.0,
         lobes=[(1483, 75, 30), (1483, 120, 45), (1490, 175, 55), (1555, 200, 38), (1450, 215, 35),
                (1420, 310, 50), (1395, 395, 45), (1430, 460, 50),
                (1490, 330, 65), (1480, 420, 65),
                (1575, 375, 42), (1545, 430, 50), (1465, 490, 35)],
         trunk=[(1488, 613, 3.2), (1486, 560, 2.8), (1483, 500, 2.5), (1495, 380, 2.2), (1500, 260, 1.8),
                (1490, 150, 1.4), (1485, 80, 1.0)]),
    dict(name="topiary", cx=1888.5, branch=(1.7, 1.1), depth=0.8,
         lobes=[(1888, 65, 30), (1885, 115, 45), (1885, 158, 55),
                (1850, 262, 42), (1925, 268, 48), (1885, 290, 42),
                (1840, 378, 44), (1935, 425, 55), (1835, 467, 40)],
         trunk=[(1888, 613, 3.0), (1888, 560, 2.6), (1887, 450, 2.4), (1890, 330, 2.1), (1888, 220, 1.8),
                (1888, 120, 1.3)]),
]


def palette(m: Model):
    p = m.pal
    p.add("leaf0", "#0a2c0d"); p.add("leaf1", "#123f15"); p.add("leaf2", "#1b561e")
    p.add("leaf3", "#276d29"); p.add("leaf4", "#388a36"); p.add("leaf_sh", "#061d08")
    p.add("bark0", "#8a542a"); p.add("bark1", "#6e4220"); p.add("bark2", "#9c6334"); p.add("bark3", "#55331a")
    p.add("stone0", "#e6d8bd"); p.add("stone1", "#dccdb0"); p.add("stone2", "#efe4cf")
    p.add("stone3", "#c4ad8c"); p.add("stone_dk", "#a8916f")
    p.add("iron", "#2c4846"); p.add("iron_dk", "#182727"); p.add("iron_lt", "#3f625f")
    p.add("bolt", "#9db7b2"); p.add("leaf_tip", "#5d9b3c"); p.add("soil", "#14140d")


# ---------------------------------------------------------------- geometry helpers

def screen_to_world(centre, u, v, s=0.0):
    """Screen offset (u right, v up, in voxels) from a pit centre at ground level plus a
    depth s (positive = away from the camera) -> continuous world (x, y, z)."""
    c = math.sqrt(0.5)
    se, ce = math.sin(math.radians(EL)), math.cos(math.radians(EL))
    return (centre[0] + (u + s) * c, centre[1] + (s - u) * c, (v - s * se) / ce)


def ref_to_screen(tree, px, py):
    return (px - tree["cx"]) / PX, (GY - py) / PX


def _hash(*a):
    h = np.uint64(1469598103934665603)
    for k, x in enumerate(a):
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h


# ---------------------------------------------------------------- pieces

def pit(m: Model, xc, yc):
    """Stone tree pit centred on voxel (xc, yc) with an iron grate flush with its top."""
    x0, y0 = xc - BASE // 2, yc - BASE // 2
    n = BASE - 2 * RING
    m.box(x0, y0, 0, BASE, BASE, STONE_H, "stone0")
    m.carve(x0 + RING, y0 + RING, 0, n, n, STONE_H)
    ids = np.array([m.pal.idx(c) for c in STONES], np.uint8)
    seam, dark = m.pal.idx("stone3"), m.pal.idx("stone_dk")

    def stones(X, Y, Z):
        bx, by = (X - x0) // BLOCK, (Y - y0) // BLOCK
        c = ids[(_hash(bx, by) % np.uint64(3)).astype(int)]
        edge = ((X - x0) % BLOCK == BLOCK - 1) | ((Y - y0) % BLOCK == BLOCK - 1) | (Z == STONE_H - 1) & (
            ((X - x0) % BLOCK == 0) | ((Y - y0) % BLOCK == 0))
        c = np.where(edge, seam, c)
        return np.where(_hash(X, Y, Z) % np.uint64(100) < 2, dark, c)
    m.paint_fn(x0, y0, 0, BASE, BASE, STONE_H, stones)

    gz = STONE_H - 1
    gx, gy = x0 + RING, y0 + RING
    m.box(gx, gy, 0, n, n, 2, "soil")
    m.where(gx, gy, gz, n, n, 1, lambda X, Y, Z: ((X - gx) % GRATE_PITCH == 0) | ((Y - gy) % GRATE_PITCH == 0)
            | (X == gx + n - 1) | (Y == gy + n - 1), "iron")
    m.where(gx, gy, gz - 1, n, n, 1, lambda X, Y, Z: ((X - gx) % GRATE_PITCH == 0) | ((Y - gy) % GRATE_PITCH == 0),
            "iron_dk")                                                         # shadowed bars below
    for cx, cy in ((gx, gy), (gx + n - 3, gy), (gx, gy + n - 3), (gx + n - 3, gy + n - 3)):
        m.box(cx, cy, gz, 3, 3, 1, "iron_lt")                                 # corner plates
        m.set(cx + 1, cy + 1, gz + 1, "bolt")


def tree(m: Model, t: dict, centre):
    """centre = exact (continuous) pit centre: the crown and trunk use it so they land on the
    reference's pixels; the pit snaps to the voxel grid (off by half a voxel at most)."""
    xc, yc = math.floor(centre[0]), math.floor(centre[1])
    pit(m, xc, yc)
    world = lambda px, py: screen_to_world(centre, *ref_to_screen(t, px, py))     # noqa: E731
    measured = [(*world(px, py), pr / PX * LOBE_SCALE) for px, py, pr in t["lobes"]]
    crown = m.crown_depth(measured, *centre, VIEW)
    top = max(z for _, _, z, _ in crown) - 2
    trunk = [(world(px, py), r) for px, py, r in t["trunk"]]
    trunk = [n for n in trunk if n[0][2] <= top] or trunk[:2]                       # stops inside the crown
    m.tube([p for p, _ in trunk], [r for _, r in trunk], BARK)
    base = trunk[0][0]
    for k in range(5):                                                    # root flare over the grate
        a = math.radians(20 + 72 * k)
        m.tube([(base[0], base[1], 8), (base[0] + 3.5 * math.cos(a), base[1] + 3.5 * math.sin(a), 5),
                (base[0] + 6 * math.cos(a), base[1] + 6 * math.sin(a), STONE_H + 0.5)], [2.4, 1.8, 1.1], BARK)
    for limb in t.get("limbs", []):                                       # limbs seen in the sheet
        m.tube([world(px, py) for px, py, _ in limb], [r for _, _, r in limb], BARK)
    r0, r1 = t["branch"]
    points = [p for p, _ in trunk]
    for cx, cy, cz, r in crown[::max(1, len(crown) // len(measured))]:  # thin branches out through the crown
        z = min(max(cz - 8, points[min(2, len(points) - 1)][2]), points[-1][2])
        start = [p for p in points if p[2] <= z][-1] if any(p[2] <= z for p in points) else points[0]
        m.tube([start, (cx, cy, cz)], [r0, r1], BARK)
    m.foliage(crown, LEAVES, clump=CLUMP, core="leaf_sh", tips="leaf_tip")


def build() -> Model:
    m = Model(*GRID, seed=11, res=RES)
    palette(m)
    c = math.sqrt(0.5)
    for i, t in enumerate(TREES):
        U = (t["cx"] - TREES[0]["cx"]) / PX
        with m.part(f"tree{i + 1}_{t['name']}"):
            tree(m, t, (FIRST_X + 0.5 + U * c, FIRST_Y + 0.5 - U * c))
    m.carve_to_reference(REFERENCE, VIEW, only=LEAVES + ["leaf_sh", "leaf_tip"], cutout=CUTOUT)
    m.paint_reference(REFERENCE, VIEW, cutout=CUTOUT)
    return m
