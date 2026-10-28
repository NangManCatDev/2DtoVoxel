"""Courthouse — reference/08df6fd3-ccba-4543-ad5d-c715e6681e72.png

Layout (x right, y depth with y=0 front, z up; u = position along a wall face,
left->right as seen from outside; symmetric about the centre line x = CX - 0.5):
  main body   x 3..136 (W=134), y 22..79 (D=58), cream stone walls up to the cornice
              top (EAVE=52): plinth, string course between the floors, dentil cornice,
              rusticated quoins on every corner
  windows     2 per floor on each front wing, 1 per floor on the sides; stone surround
              with sill, capped lintel + keystone, brown frame, 2x2 bluish panes
  portico     u 37..97, 9 deep: raised landing (z 10), 4 steps between two cheek blocks,
              outer columns on pedestals, inner columns beside the brown double door,
              shaded wall behind, entablature with dentils, stepped pediment (dark brown
              tympanum, gold scales-of-justice medallion on a stone plaque)
  roof        teal hipped roof of 2-voxel courses (steeper at the hipped ends, flat top
              at z 70, dark tile joints), gabled roof behind the pediment, 2 front dormers
              + 1 on the left hip, 2 chimneys with dark caps, cupola just behind the
              pediment with a teal pyramid + finial
"""
import numpy as np

from voxtool import Model

NAME = "model_1029_0313"
REFERENCE = "reference/08df6fd3-ccba-4543-ad5d-c715e6681e72.png"
VIEW = {"azimuth": 17, "elevation": 12, "fov": 0}

HX0, W = 3, 134             # main body x range [HX0, HX1)
HX1 = HX0 + W
HY0, D = 22, 58             # main body y range [HY0, HY1)
HY1 = HY0 + D
CX = HX0 + W // 2           # 70: symmetric pieces are [CX - k, CX + k)
CY = HY0 + D // 2           # 48

PLINTH = 4
Z_W1, Z_W2 = 9, 30          # bottom of the window openings (ground / upper floor)
WIN_W, WIN_H = 9, 11
BAND_Z = 24                 # string course between the floors
FRIEZE = 45                 # cornice: fillet 45, dentils 46..48, corona 49..51
EAVE = 52                   # top of the cornice = roof base
ROOF_INSETS = (0, 2, 4, 6, 8, 9, 11, 13, 14)   # per 2-high course, front/back slopes (y)
ROOF_X_INSETS = (0, 1, 2, 4, 5, 6, 7, 9, 10)    # the hipped ends (x) are steeper
ROOF_TOP = EAVE + 2 * len(ROOF_INSETS)         # 70

FLOOR = 10                  # portico landing (door 10..31)
STEPS = 4
PHW = 30                    # portico half width -> x [CX-30, CX+30)
PD = 9                      # portico depth in front of the wall
PY0 = HY0 - PD              # 10
STEP_RUN = 3
COL_TOP = 40                # outer pier shafts end here; capitals 40..44
ENT_Z = 44                  # portico entablature 44..52
PED_HW = 33                 # pediment / portico gable half width
PED_SLOPE = 0.55

DOR_W, DOR_H, DOR_D = 15, 11, 14
CH_TOP = 74                 # chimney stone top
CUP_Y = HY0 + 13            # cupola centre: just behind the pediment, not mid-roof
CUP_Z = 64                  # base of the cupola's stepped tiers


def palette(m: Model):
    # base colours ~ reference front samples / 0.9 (the preview shades fronts x0.9)
    p = m.pal
    p.add("stone", "#ffe6b9"); p.add("stone2", "#f9dcae"); p.add("stone3", "#ffebc4")
    p.add("joint", "#f0d4a8")
    p.add("trim", "#ffefcc")
    p.add("base", "#f5d9ad")
    p.add("porch", "#d2b48a"); p.add("porch2", "#c9aa80")      # wall in the portico's shade
    p.add("col", "#fff0d0"); p.add("col2", "#fbe6c0")
    p.add("roof", "#04717a"); p.add("roof2", "#067f88"); p.add("roof_dk", "#035f66")
    p.add("tile_gap", "#03454b")
    p.add("frame", "#5e3d28"); p.add("glass", "#435068")
    p.add("door", "#593522"); p.add("door_dk", "#3c2416")
    p.add("tymp", "#4c2d18")
    p.add("gold", "#e3a227"); p.add("gold_hi", "#fbd04c"); p.add("gold_dk", "#a06814")
    p.add("cap", "#40464e"); p.add("cap2", "#2d3238")


STONES = ["stone", "stone2", "stone3"]
ROOFS = ["roof", "roof2", "roof_dk"]


# ---------------------------------------------------------------- helpers

def fbox(m: Model, face: str, u: int, z: int, w: int, h: int, d0: int, dd: int, c):
    """Box relative to a main-body wall face. u = position along the face (left->right
    seen from outside), d0 = depth into the wall (0 = outer layer, -1 = one voxel in
    front of the wall), dd = thickness inward."""
    if face == "front":
        m.box(HX0 + u, HY0 + d0, z, w, dd, h, c)
    elif face == "back":
        m.box(HX1 - u - w, HY1 - d0 - dd, z, w, dd, h, c)
    elif face == "left":
        m.box(HX0 + d0, HY1 - u - w, z, dd, w, h, c)
    elif face == "right":
        m.box(HX1 - d0 - dd, HY0 + u, z, dd, w, h, c)


def sym(m: Model, x, y, z, w, d, h, c):
    """Box plus its mirror image across the centre line."""
    m.box(x, y, z, w, d, h, c)
    m.box(2 * CX - x - w, y, z, w, d, h, c)


def window(m: Model, face: str, u: int, z: int, w: int = WIN_W, h: int = WIN_H, d0: int = 0,
           surround: bool = True):
    """Opening (u, z, w, h): brown frame recessed 1 with a cross, panes recessed 2;
    optional stone surround with sill, capped lintel and keystone."""
    if surround:
        fbox(m, face, u - 2, z - 1, w + 4, h + 2, d0 - 1, 1, "trim")      # jambs + lintel
        fbox(m, face, u - 3, z - 2, w + 6, 1, d0 - 2, 2, "trim")          # sill
        fbox(m, face, u - 3, z + h + 1, w + 6, 2, d0 - 2, 2, "trim")      # cap
        fbox(m, face, u - 1, z + h + 3, w + 2, 1, d0 - 1, 1, "trim")      # cap top
        fbox(m, face, u + w // 2 - 1, z + h, 3, 3, d0 - 3, 1, "stone3")    # keystone
    fbox(m, face, u, z, w, h, d0 - 1, 3, None)
    fbox(m, face, u, z, w, h, d0 + 1, 1, "frame")
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, d0 + 1, 1, None)
    fbox(m, face, u + 1, z + 1, w - 2, h - 2, d0 + 2, 1, "glass")
    fbox(m, face, u + w // 2, z + 1, 1, h - 2, d0 + 1, 1, "frame")     # mullion
    fbox(m, face, u + 1, z + h // 2, w - 2, 1, d0 + 1, 1, "frame")     # transom


def quoins(m: Model, cx: int, cy: int, sx: int, sy: int, z0: int = PLINTH, z1: int = FRIEZE):
    """Rusticated corner stones at wall corner voxel (cx, cy); sx/sy = outward direction.
    Alternating long/short blocks, 3 high, with an open joint row between them."""
    xs, ys = cx + sx, cy + sy
    for i, z in enumerate(range(z0, z1 - 2, 4)):
        lf, ls = (6, 3) if i % 2 == 0 else (3, 6)
        col = "stone3" if i % 2 == 0 else "trim"
        m.box(min(xs, xs - sx * (lf - 1)), ys, z, lf, 1, 3, col)
        m.box(xs, min(ys, ys - sy * (ls - 1)), z, 1, ls, 3, col)


def ring(m: Model, z: int, h: int, off: int, c, only=None):
    """1-voxel band around the main body, `off` voxels outside the wall faces.
    only(X, Y) can thin it out (dentils)."""
    x0, y0, x1, y1 = HX0 - off, HY0 - off, HX1 + off - 1, HY1 + off - 1

    def fn(X, Y, Z):
        edge = (X == x0) | (X == x1) | (Y == y0) | (Y == y1)
        return edge & (only(X, Y) if only else True)
    m.where(x0, y0, z, x1 - x0 + 1, y1 - y0 + 1, h, fn, c)


def dormer(m: Model, face: str, u0: int, w: int = DOR_W, d0: int = 2):
    """Dormer standing on the cornice, front wall d0 behind the wall face: window,
    stepped stone gable with trim, teal gable roof running back into the main roof."""
    z0 = EAVE
    fbox(m, face, u0 - 1, z0 + 1, w + 2, 30, 0, d0, None)          # clear the roof in front
    fbox(m, face, u0 - 1, z0, w + 2, 1, -1, d0 + 1, "trim")         # ledge
    fbox(m, face, u0, z0, w, DOR_H, d0, DOR_D, "stone")
    zg = z0 + DOR_H
    for i in range(-1, w + 1):
        dist = min(i, w - 1 - i)
        top = zg + int(max(dist, 0) * 0.8)
        if 0 <= i < w:
            fbox(m, face, u0 + i, zg, 1, top - zg, d0, DOR_D, "stone")
            fbox(m, face, u0 + i, top - 1, 1, 2, d0 - 1, 1, "trim")         # raking trim
        fbox(m, face, u0 + i, top - (1 if dist < 0 else 0), 1, 2, d0, DOR_D, "roof")
    ww = 7
    wu = u0 + (w - ww) // 2
    fbox(m, face, wu - 1, z0 + 1, ww + 2, DOR_H - 1, d0 - 1, 1, "trim")      # flat surround
    window(m, face, wu, z0 + 2, w=ww, h=8, d0=d0, surround=False)


def tile_joints(m: Model):
    """Dark gaps between the roof tiles: every 6th voxel along each 2-high course,
    offset by 3 per course (running bond). The top course stays plain so the flat
    roof top gets no diagonal stripes."""
    roofs = [m.pal.idx(c) for c in ROOFS]
    gap = m.pal.idx("tile_gap")
    W_, D_, H_ = m.size

    def fn(X, Y, Z):
        cur = m.v[X, Y, Z]
        joint = (X + Y + 3 * ((Z - EAVE) // 2)) % 6 == 0
        return np.where(np.isin(cur, roofs) & joint & (Z < ROOF_TOP - 2), gap, 0)
    m.paint_fn(0, 0, EAVE, W_, D_, H_ - EAVE, fn)


def chimney(m: Model, x: int, y: int, w: int = 8, d: int = 8):
    m.box(x, y, EAVE, w, d, CH_TOP - EAVE, "stone")
    m.box(x - 1, y - 1, CH_TOP, w + 2, d + 2, 2, "trim")
    m.box(x + 1, y + 1, CH_TOP + 2, w - 2, d - 2, 2, "cap")
    m.box(x + 2, y + 2, CH_TOP + 4, w - 4, d - 4, 1, "cap2")


def medallion(m: Model, y: int, cz: float = 59.5, r: float = 6.6):
    """Gold disc facing -y at plane y with a darker rim and a raised scales motif."""
    cx = CX - 0.5
    d2 = lambda X, Z: (X - cx) ** 2 + (Z - cz) ** 2
    reg = (CX - 8, y, int(cz - r) - 1, 16, 1, int(2 * r) + 3)
    m.where(*reg, lambda X, Y, Z: d2(X, Z) <= r * r, "gold")
    m.where(*reg, lambda X, Y, Z: (d2(X, Z) <= r * r) & (d2(X, Z) > (r - 1.1) ** 2), "gold_dk")
    yr, g, z0 = y - 1, "gold_hi", int(cz - 5.5)
    m.box(CX - 3, yr, z0, 6, 1, 1, g)            # foot
    m.box(CX - 1, yr, z0 + 1, 2, 1, 8, g)        # post
    m.box(CX - 6, yr, z0 + 9, 12, 1, 1, g)       # beam
    m.box(CX - 1, yr, z0 + 10, 2, 1, 1, g)       # knob
    for s in (-1, 1):                            # pans on strings
        mx = lambda x: x if s < 0 else 2 * CX - 1 - x
        m.line((mx(CX - 6), yr, z0 + 8), (mx(CX - 7), yr, z0 + 5), g)
        m.line((mx(CX - 5), yr, z0 + 8), (mx(CX - 3), yr, z0 + 5), g)
        x0 = min(mx(CX - 7), mx(CX - 3))
        m.box(x0, yr, z0 + 4, 5, 1, 1, g)
        m.box(x0 + 1, yr, z0 + 3, 3, 1, 1, g)


def cupola(m: Model):
    """Lantern right behind the pediment: stone pedestal rising out of the roof,
    2 stepped base tiers, body with corner pilasters and 2 windows per face,
    cornice, 3-course teal pyramid, 2-tier finial."""
    cy = CUP_Y
    m.box(CX - 10, cy - 10, EAVE, 20, 20, CUP_Z - EAVE, "stone")
    m.box(CX - 12, cy - 12, CUP_Z, 24, 24, 2, "trim")
    m.box(CX - 11, cy - 11, CUP_Z + 2, 22, 22, 2, "stone3")
    m.box(CX - 10, cy - 10, CUP_Z + 4, 20, 20, 2, "trim")
    zb = CUP_Z + 6
    m.box(CX - 8, cy - 8, zb, 16, 16, 9, "stone")
    for sx in (-1, 1):                              # corner pilasters
        for sy in (-1, 1):
            m.box(CX - 9 if sx < 0 else CX + 6, cy - 9 if sy < 0 else cy + 6, zb, 3, 3, 9, "trim")
    for a in (-5, 2):                               # 2 windows on every face
        m.box(CX + a, cy - 8, zb + 2, 3, 1, 6, None); m.box(CX + a, cy - 7, zb + 2, 3, 1, 6, "glass")
        m.box(CX + a, cy + 7, zb + 2, 3, 1, 6, None); m.box(CX + a, cy + 6, zb + 2, 3, 1, 6, "glass")
        m.box(CX - 8, cy + a, zb + 2, 1, 3, 6, None); m.box(CX - 7, cy + a, zb + 2, 1, 3, 6, "glass")
        m.box(CX + 7, cy + a, zb + 2, 1, 3, 6, None); m.box(CX + 6, cy + a, zb + 2, 1, 3, 6, "glass")
    zc = zb + 9
    m.box(CX - 11, cy - 11, zc, 22, 22, 2, "trim")
    for k, s in enumerate((18, 14, 10)):
        m.box(CX - s // 2, cy - s // 2, zc + 2 + 2 * k, s, s, 2, "roof")
    zf = zc + 8
    m.box(CX - 2, cy - 2, zf, 4, 4, 2, "trim")
    m.box(CX - 1, cy - 1, zf + 2, 2, 2, 2, "trim")


# ---------------------------------------------------------------- build

def build() -> Model:
    m = Model(140, HY1 + 3, 96, seed=3)
    palette(m)

    # --- walls, plinth, string course, cornice
    m.shell(HX0, HY0, 0, W, D, EAVE, "stone", t=3, top=False, bottom=False)
    for z in range(PLINTH):
        ring(m, z, 1, 1, "base")
    ring(m, PLINTH - 1, 1, 1, "trim")
    ring(m, BAND_Z, 2, 1, "trim")
    ring(m, FRIEZE, 1, 1, "trim")
    ring(m, FRIEZE + 1, 3, 1, "trim", only=lambda X, Y: (X + Y) % 4 < 2)   # dentils
    ring(m, FRIEZE + 4, 3, 1, "stone3")
    for z in range(FRIEZE + 4, EAVE):
        ring(m, z, 1, 2, "trim")
    quoins(m, HX0, HY0, -1, -1)
    quoins(m, HX1 - 1, HY0, 1, -1)
    quoins(m, HX0, HY1 - 1, -1, 1)
    quoins(m, HX1 - 1, HY1 - 1, 1, 1)

    # --- windows
    for u in (10, 25, W - 25 - WIN_W, W - 10 - WIN_W):
        for z in (Z_W1, Z_W2):
            window(m, "front", u, z)
            window(m, "back", u, z)
    for u in (52, W - 52 - WIN_W):
        for z in (Z_W1, Z_W2):
            window(m, "back", u, z)
    for face in ("left", "right"):
        for z in (Z_W1, Z_W2):
            window(m, face, (D - WIN_W) // 2, z)

    # --- main hipped roof
    for k, (iy_, ix_) in enumerate(zip(ROOF_INSETS, ROOF_X_INSETS)):
        m.box(HX0 + ix_, HY0 + iy_, EAVE + 2 * k, W - 2 * ix_, D - 2 * iy_, 2, "roof")

    # --- portico: landing, steps, cheeks
    px0 = CX - PHW
    m.box(px0, PY0, 0, 2 * PHW, PD, FLOOR, "base")
    m.box(px0, PY0, FLOOR - 1, 2 * PHW, PD, 1, "trim")
    for i in range(STEPS):
        h = FLOOR - 2 * (i + 1)
        y0 = PY0 - STEP_RUN * (i + 1)
        m.box(CX - 15, y0, 0, 30, STEP_RUN, h, "base")
        m.box(CX - 15, y0, h - 1, 30, STEP_RUN, 1, "trim")
    cy0 = PY0 - STEP_RUN * STEPS
    sym(m, CX - 23, cy0, 0, 8, PY0 - cy0, 6, "base")
    sym(m, CX - 23, cy0, 5, 8, PY0 - cy0, 1, "trim")
    sym(m, CX - 22, cy0 + 2, 6, 6, PY0 - cy0 - 2, 4, "stone3")
    sym(m, CX - 22, cy0 + 2, FLOOR - 1, 6, PY0 - cy0 - 2, 1, "trim")

    # outer piers (deep, on pedestals that rise from the ground)
    sym(m, CX - 31, PY0 - 1, 0, 11, PD + 1, FLOOR + 2, "base")
    sym(m, CX - 31, PY0 - 1, FLOOR + 1, 11, PD + 1, 1, "trim")
    sym(m, CX - 30, PY0, FLOOR + 2, 9, 6, COL_TOP - FLOOR - 2, "col")
    sym(m, CX - 31, PY0 - 1, FLOOR + 2, 11, 8, 2, "trim")
    sym(m, CX - 31, PY0 - 1, COL_TOP, 11, 8, 2, "trim")
    sym(m, CX - 32, PY0 - 2, COL_TOP + 2, 13, 10, 2, "stone3")

    # wall inside the portico is in shade
    m.box(px0, HY0, FLOOR, 2 * PHW, 1, ENT_Z - FLOOR, "porch", only_filled=True)

    # inner columns beside the door (free-standing, 2 off the wall), carrying a beam
    iy = HY0 - 7
    sym(m, CX - 19, iy, FLOOR, 9, 6, 3, "trim")
    sym(m, CX - 18, iy + 1, FLOOR + 3, 7, 4, 37 - FLOOR - 3, "col")
    sym(m, CX - 19, iy, 37, 9, 6, 2, "trim")
    sym(m, CX - 19, iy, 39, 9, 6, 2, "stone3")
    m.box(CX - 19, iy, 41, 38, 7, 3, "trim")

    # double door
    dz = FLOOR + 21
    m.box(CX - 10, HY0 - 1, FLOOR, 20, 1, dz + 3 - FLOOR, "trim")        # frame
    m.box(CX - 12, HY0 - 2, dz + 3, 24, 2, 2, "trim")                    # cornice
    m.box(CX - 11, HY0 - 1, dz + 5, 22, 1, 1, "stone3")
    m.box(CX - 7, HY0 - 1, FLOOR, 14, 3, dz - FLOOR, None)
    m.box(CX - 7, HY0 + 2, FLOOR, 14, 1, dz - FLOOR, "door_dk")
    for lx in (CX - 7, CX):
        m.box(lx, HY0 + 1, FLOOR, 7, 1, dz - FLOOR, "door")
        for pz, ph in ((FLOOR + 2, 6), (FLOOR + 10, 5), (FLOOR + 17, 3)):   # sunk panels
            m.box(lx + 2, HY0 + 1, pz, 3, 1, ph, None)
        m.box(lx + 1, HY0 + 1, FLOOR, 1, 1, dz - FLOOR, "door")
    m.box(CX - 1, HY0 + 1, FLOOR, 2, 1, dz - FLOOR, "door_dk")            # meeting stiles
    for kx in (CX - 4, CX + 2):                                          # gold knockers
        m.box(kx, HY0, FLOOR + 10, 2, 1, 3, "gold")
        m.box(kx, HY0, FLOOR + 11, 2, 1, 1, None)

    # entablature
    m.box(px0, PY0, ENT_Z, 2 * PHW, PD, 3, "trim")
    m.box(px0, PY0, ENT_Z + 3, 2 * PHW, PD, 2, "stone3")
    for x in range(px0, CX + PHW, 4):
        m.box(x, PY0 - 1, ENT_Z + 3, 2, 1, 2, "trim")
    for y in range(PY0, HY0, 4):
        sym(m, px0 - 1, y, ENT_Z + 3, 1, 2, 2, "trim")
    m.box(px0 - 2, PY0 - 2, ENT_Z + 5, 2 * PHW + 4, PD + 2, 3, "trim")

    # pediment + gabled roof running back to the cupola
    gx0, gw = CX - PED_HW, 2 * PED_HW
    gy0, gy1 = PY0 - 2, CUP_Y
    m.gable_roof(gx0, gy0, EAVE, gw, gy1 - gy0, "y", "roof", slope=PED_SLOPE, t=2, fill="stone")
    for i in range(gw):
        surf = EAVE + int(np.floor(min(i, gw - 1 - i) * PED_SLOPE))
        x = gx0 + i
        m.box(x, gy0, EAVE, 1, 2, surf - EAVE, None)                     # open the tympanum
        m.box(x, gy0 - 1, surf - 2, 1, 3, 4, "trim")                     # stepped raking cornice
        if px0 <= x < CX + PHW:
            m.box(x, PY0, EAVE, 1, 1, max(surf - 2 - EAVE, 0), "tymp")
            m.box(x, PY0 - 1, EAVE, 1, 1, 1, "trim")                     # sill ledge
            if CX - 9 <= x < CX + 9:                                     # medallion plaque
                m.box(x, PY0 - 1, EAVE, 1, 1, max(min(67, surf - 1) - EAVE, 0), "stone3")
    medallion(m, PY0 - 2)

    # --- dormers, chimneys, cupola
    dormer(m, "front", 15)
    dormer(m, "front", W - 15 - DOR_W)
    dormer(m, "left", 10, w=13)
    chimney(m, HX0 + 2, HY0 + 14, w=6, d=14)     # long stack along the left hip
    chimney(m, HX0 + 113, HY0 + 17)
    cupola(m)

    # --- textures
    m.bricks(STONES, target="stone", bw=6, bh=4, mortar="joint", p=[0.5, 0.3, 0.2])
    m.bricks(["porch", "porch2"], target="porch", bw=6, bh=4, p=[0.6, 0.4])
    m.bricks(["col", "col2"], target="col", bw=4, bh=3, p=[0.6, 0.4], salt=2)
    m.bricks(ROOFS, target="roof", bw=5, bh=2, p=[0.55, 0.25, 0.2], salt=5)
    tile_joints(m)
    return m
