"""Cream sandstone staircase between stepped side walls — reference/8cb03861-6046-46e0-bff9-f48d54cdf1b2.png

Layout (x across the stair, y depth with y=0 front, z up):
  slab      thin paving slab at ground level between the walls, y 0..Y_R1; the left wall
            is flush with its front, the right wall starts 8 behind it (as in the reference)
  stairs    N_RISERS risers of RISE x RUN; the last one is the top landing, which runs to
            the back
  walls     left/right walls (WT_L / WT_R thick), 4 flat-topped segments each (SEGS_L/R,
            climbing slower than the stairs); the front block of every segment reads as a
            cube (grooves), the front cubes are split at mid height, a cube at each back
            corner sticks up BP_UP
  underside steps up toward the back (UNDER) - the reference's lower-left edge climbs
            faster than the wall tops; risers always reach down to the step below
  surface   paving tiles with thin joints on every top, darker block courses on the
            risers, big blocks on the wall faces (some set back 1), chipped notches,
            a few yellowish stones
  camera    stairs climb away from the camera, the left wall's outer face is visible
            (camera at front-left -> positive azimuth)
"""
import numpy as np

from voxtool import Model

NAME = "model_1028_0626"
REFERENCE = "reference/8cb03861-6046-46e0-bff9-f48d54cdf1b2.png"
VIEW = {"azimuth": 30, "elevation": 30, "fov": 0}

RISE = 7             # step height
RUN = 13             # step depth
N_RISERS = 7         # the 7th riser is the top landing
SW = 66              # stair width between the walls
WT_L, WT_R = 10, 14  # wall thickness (the right one reads thicker in the reference)
SLAB_H = 2           # ground slab thickness
Y_R1 = 23            # first riser, measured from the slab front
TOP_D = 31           # top landing depth
BACK_POST = 12       # back corner cubes: depth ...
BP_UP = 4            # ... and how far they stick up
POST_D = 11          # depth of the cube at the front of each wall segment
CRACK_AT = 0.43      # the front cubes are split at this fraction of their height

RISERS = [Y_R1 + k * RUN for k in range(N_RISERS)]        # y of riser 1..7
GY = RISERS[-1] + TOP_D
# wall segments: (front y, top z). The reference is not symmetric: the left wall starts
# flush with the slab front and its posts sit just before risers 1/3/5, the right wall
# starts behind the slab edge and its posts sit 3-5 before risers 2/4/6.
SEGS_L = [(0, 24), (RISERS[0] - 1, 34), (RISERS[2] - 1, 45), (RISERS[4] - 1, 57)]
SEGS_R = [(8, 27), (RISERS[1] - 3, 36), (RISERS[3] - 4, 43), (RISERS[5] - 5, 50)]
# the underside steps up toward the back (the left wall's lower edge in the reference
# climbs faster than its top edges): bottom z per left-wall segment, applied by y
UNDER = [0, 4, 9, 15]
GZ = max(t for _, t in SEGS_L + SEGS_R) + BP_UP
GX = WT_L + SW + WT_R
XL0, XL1 = 0, WT_L               # left wall
XS0, XS1 = WT_L, WT_L + SW       # stairs
XR0, XR1 = WT_L + SW, GX         # right wall
WALLS = [(XL0, XL1, SEGS_L), (XR0, XR1, SEGS_R)]

STONES = ["stone", "stone2", "stone3", "stone4"]
TILES = ["tile", "tile2", "tile3", "tile4", "ochre", "ochre2"]
TILE_P = [0.32, 0.24, 0.2, 0.15, 0.05, 0.04]
RISER_STONES = ["riser", "riser2", "riser3"]


def palette(m: Model):
    # tops sample ~#e6dbca, left faces ~#b0a796 (/0.76 -> #e7dcc5), yellow tiles ~#dcc9aa
    p = m.pal
    p.add("stone", "#e6dac6"); p.add("stone2", "#e1d4bf"); p.add("stone3", "#ebe0ce")
    p.add("stone4", "#ddcfb8")
    p.add("tile", "#e8ddcc"); p.add("tile2", "#e3d6c2"); p.add("tile3", "#ede4d5")
    p.add("tile4", "#dfd1bb")
    p.add("ochre", "#ddc9a6"); p.add("ochre2", "#e2d1b2")
    # risers read darker in the reference (~#b5a78f..#bcb09b on the front -> /0.9)
    p.add("riser", "#d1c3aa"); p.add("riser2", "#cbbca3"); p.add("riser3", "#d6c9b2")
    p.add("joint", "#d2c4ad")
    p.add("notch", "#a99a83")


# ---------------------------------------------------------------- helpers

def top_z(m: Model, x, y):
    """z of the topmost filled voxel in column (x, y), or -1."""
    col = m.v[x, y, :] > 0
    if not col.any():
        return -1
    return int(len(col) - 1 - np.argmax(col[::-1]))


def tile_tops(m: Model, x0, y0, x1, y1, row_d=(6, 8), tile_w=(7, 15), salt=0):
    """Paving tiles on the top surface of region [x0,x1) x [y0,y1): rows along y,
    each row split into tiles of random width; tile joints get the joint colour."""
    rng = np.random.default_rng(salt)
    y = y0
    while y < y1:
        d = int(rng.integers(row_d[0], row_d[1] + 1))
        ye = min(y + d, y1)
        x = x0 - int(rng.integers(0, tile_w[0]))
        while x < x1:
            w = int(rng.integers(tile_w[0], tile_w[1] + 1))
            col = TILES[int(rng.choice(len(TILES), p=TILE_P))]
            for xx in range(max(x, x0), min(x + w, x1)):
                for yy in range(y, ye):
                    z = top_z(m, xx, yy)
                    if z < 0:
                        continue
                    joint = (xx == x and xx > x0) or (yy == y and yy > y0)
                    m.set(xx, yy, z, "joint" if joint else col)
            x += w
        y = ye


def face_blocks(m: Model, axis: str, plane: int, u0, u1, z0, z1, course=(5, 9), blk=(8, 18),
                salt=0, joints=True, inward=1, setback_p=0.0, stones=None):
    """Stone blocks on a vertical face. axis 'x' = face at x=plane spanning y in [u0,u1);
    axis 'y' = face at y=plane spanning x in [u0,u1). Only filled voxels are recoloured.
    With setback_p a block is pushed 1 voxel into the wall (inward = +1/-1 along the axis)."""
    rng = np.random.default_rng(salt)
    z = z0
    while z < z1:
        h = int(rng.integers(course[0], course[1] + 1))
        ze = min(z + h, z1)
        u = u0 - int(rng.integers(0, blk[0]))
        while u < u1:
            w = int(rng.integers(blk[0], blk[1] + 1))
            pool = stones or STONES
            col = pool[int(rng.integers(len(pool)))]
            if rng.random() < 0.04:
                col = "ochre"
            back = rng.random() < setback_p
            for uu in range(max(u, u0), min(u + w, u1)):
                for zz in range(z, ze):
                    x, y = (plane, uu) if axis == "x" else (uu, plane)
                    if not m.get(x, y, zz):
                        continue
                    j = joints and ((uu == u and uu > u0) or (zz == z and zz > z0))
                    c = "joint" if j else col
                    if back:
                        m.set(x, y, zz, None)
                        x, y = (x + inward, y) if axis == "x" else (x, y + inward)
                        if not m.get(x, y, zz):
                            continue
                    m.set(x, y, zz, c)
            u += w
        z = ze


def groove(m: Model, cells, inward):
    """Carves 1-voxel grooves at the given cells; the voxel behind shows as a joint."""
    dx, dy, dz = inward
    for x, y, z in cells:
        if m.get(x, y, z):
            m.set(x, y, z, None)
            if m.get(x + dx, y + dy, z + dz):
                m.set(x + dx, y + dy, z + dz, "joint")


def post_joints(m: Model):
    """The front block of every wall segment reads as a separate cube: a groove over
    its top and down the visible side, and the front cubes are split at mid height."""
    for x0, x1, segs in WALLS:
        # x0 is the visible side of both walls (left outer face, right inner face)
        joints_y = [(y0 + POST_D, top) for y0, top in segs] + [(GY - BACK_POST, segs[-1][1])]
        for y, top in joints_y:
            groove(m, [(x, y, top - 1) for x in range(x0, x1)], (0, 0, -1))
            groove(m, [(x0, y, z) for z in range(under_z(y), top - 1)], (1, 0, 0))
        y0, top = segs[0]
        zc = int(top * CRACK_AT)
        groove(m, [(x, y0, zc) for x in range(x0, x1)], (0, 1, 0))
        groove(m, [(x0, y, zc) for y in range(y0 + 1, y0 + POST_D)], (1, 0, 0))


def notches(m: Model, axis: str, plane: int, inward: int, u0, u1, z0, z1, n, salt=0):
    """Small chipped notches (1 deep slits and L-shaped corners) on a vertical face."""
    rng = np.random.default_rng(salt)
    for _ in range(n):
        u = int(rng.integers(u0 + 1, max(u0 + 2, u1 - 2)))
        z = int(rng.integers(z0 + 1, max(z0 + 2, z1 - 4)))
        kind = rng.random()
        if kind < 0.55:          # vertical slit
            cells = [(0, k) for k in range(int(rng.integers(2, 5)))]
        elif kind < 0.8:         # L notch
            cells = [(0, 0), (1, 0), (0, 1), (0, 2)]
        else:                    # small square
            cells = [(0, 0), (1, 0), (0, 1), (1, 1)]
        for du, dz in cells:
            x, y = (plane, u + du) if axis == "x" else (u + du, plane)
            if m.get(x, y, z + dz):
                m.set(x, y, z + dz, None)
                # the voxel behind the hole shows as a dark recess
                bx, by = (x + inward, y) if axis == "x" else (x, y + inward)
                if m.get(bx, by, z + dz):
                    m.set(bx, by, z + dz, "notch")


# ---------------------------------------------------------------- parts

def under_z(y):
    """Bottom of the structure at depth y (stepped underside)."""
    z = 0
    for (y0, _), b in zip(SEGS_L, UNDER):
        if y >= y0:
            z = b
    return z


def underside(m: Model):
    """Carves everything below the stepped underside. Under the stairs it never rises
    above the tread in front, so every riser face reaches down to the step below."""
    for y in range(GY):
        b = under_z(y)
        k = sum(1 for r in RISERS if r <= y)          # risers at or in front of y
        b_st = 0 if k == 0 else min(b, SLAB_H + (k - 1) * RISE)
        if b:
            m.box(XL0, y, 0, WT_L, 1, b, None)
            m.box(XR0, y, 0, WT_R, 1, b, None)
        if b_st:
            m.box(XS0, y, 0, SW, 1, b_st, None)


def slab(m: Model):
    m.box(XS0, 0, 0, SW, Y_R1, SLAB_H, "stone")


def stairs(m: Model):
    for k, y in enumerate(RISERS, start=1):
        m.box(XS0, y, 0, SW, GY - y, SLAB_H + k * RISE, "stone")


def wall(m: Model, x0, x1, segs):
    for j, (y0, top) in enumerate(segs):
        y1 = segs[j + 1][0] if j + 1 < len(segs) else GY
        m.box(x0, y0, 0, x1 - x0, y1 - y0, top, "stone")
    m.box(x0, GY - BACK_POST, 0, x1 - x0, BACK_POST, segs[-1][1] + BP_UP, "stone")


def texture(m: Model):
    # risers: one course of blocks each
    for k, y in enumerate(RISERS, start=1):
        face_blocks(m, "y", y, XS0, XS1, SLAB_H + (k - 1) * RISE, SLAB_H + k * RISE,
                    course=(RISE, RISE), blk=(9, 18), salt=100 + k, stones=RISER_STONES)
    # slab front edge, and the (hidden) back face
    face_blocks(m, "y", 0, XS0, XS1, 0, SLAB_H, course=(SLAB_H, SLAB_H), blk=(10, 20), salt=99)
    face_blocks(m, "y", GY - 1, 0, GX, 0, GZ, course=(6, 11), blk=(10, 22), salt=98)
    # walls: outer/inner faces and the segment fronts
    for side, (x0, x1, segs) in enumerate(WALLS):
        y_front = segs[0][0]
        # visible face (x0): big blocks, some set back one voxel for a rough face
        face_blocks(m, "x", x0, y_front, GY, 0, GZ, course=(6, 11), blk=(10, 22),
                    salt=200 + side * 10, inward=1, setback_p=0.28)
        face_blocks(m, "x", x1 - 1, y_front, GY, 0, GZ, course=(6, 11), blk=(10, 22),
                    salt=205 + side * 10)
        for j, (y0, top) in enumerate(segs):
            face_blocks(m, "y", y0, x0, x1, 0, top, blk=(x1 - x0, x1 - x0), salt=300 + side * 10 + j)
        face_blocks(m, "y", GY - BACK_POST, x0, x1, segs[-1][1], GZ, blk=(x1 - x0, x1 - x0),
                    salt=320 + side)
    # paving on every top surface
    for k, y in enumerate(RISERS):
        y_end = RISERS[k + 1] if k + 1 < len(RISERS) else GY
        tile_tops(m, XS0, y, XS1, y_end, salt=400 + k)
    tile_tops(m, XS0, 0, XS1, Y_R1, salt=399)
    for side, (x0, x1, segs) in enumerate(WALLS):
        tile_tops(m, x0, segs[0][0], x1, GY, row_d=(8, 14), tile_w=(x1 - x0, x1 - x0), salt=500 + side)
    # chipped notches on the visible wall faces
    for side, (x0, x1, segs) in enumerate(WALLS):
        notches(m, "x", x0, 1, segs[0][0], GY, 0, GZ, 80 if side == 0 else 45, salt=600 + side)
        for j, (y0, top) in enumerate(segs):
            notches(m, "y", y0, 1, x0, x1, 0, top, 3, salt=610 + j * 2 + side)
    post_joints(m)


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(GX, GY, GZ, seed=5)
    palette(m)
    slab(m)
    stairs(m)
    for x0, x1, segs in WALLS:
        wall(m, x0, x1, segs)
    underside(m)
    texture(m)
    return m
