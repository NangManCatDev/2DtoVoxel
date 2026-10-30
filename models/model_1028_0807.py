"""Cream stone wall panel — reference/49857492-bc76-433b-88b4-b7cc91b06554.png

Layout (x right, y depth with y=0 front, z up):
  wall body     x X0..X0+L, y FY..FY+T, z 0..H, rubble texture (small 1-voxel relief tiles)
  front stones  ~30 big stepped "flagstones" protruding 2 voxels, placed from the
                reference (screen bboxes -> wall coordinates, perspective corrected)
  left end      8 stacked quoin cubes (5 tall + 1 recessed joint), protruding left
  right end     column of blocks sticking out to the right
  top           irregular coping blocks, a taller pile on the right corner
  back          mirror of the front relief (not visible in the reference)
"""
from voxtool import Model

NAME = "model_1028_0807"
REFERENCE = "reference/49857492-bc76-433b-88b4-b7cc91b06554.png"
VIEW = {"azimuth": 30, "elevation": 22, "fov": 0}   # perspective (fov 40) scored worse

L = 84          # wall length (x)
T = 16          # wall thickness (y)
H = 47          # wall body height (z), coping sits on top
X0 = 3          # left end of the wall body (quoins protrude to the left of it)
FY = 2          # front plane of the wall body (stones protrude to y = FY-2)
RELIEF = 2      # stone protrusion
Q_PITCH = 6     # quoin course height (5 stone + 1 joint)
Q_OUT = 2       # quoin protrusion beyond the left end

# reference front-plane quad in screen pixels (for placing stones)
S_LX, S_RX = 385, 1335
S_TL, S_TR = 205, 85
S_BL, S_BR = 935, 700
PERSP_K = 1.19   # far edge is ~1/1.19 the size of the near edge


def palette(m: Model):
    # front face renders x0.9, left face x0.76
    p = m.pal
    p.add("stone", "#f2e4cd"); p.add("stone2", "#ede0c8"); p.add("stone3", "#f6eada")
    p.add("rubble", "#e4d6c0"); p.add("rubble2", "#dbcdb6"); p.add("rubble3", "#eadcc7")
    p.add("joint", "#b7aa96")
    p.add("quoin", "#fdf2e4"); p.add("quoin2", "#f7ecdd")
    p.add("cap", "#f6eadb"); p.add("cap2", "#efe2cf")


STONES = ["stone", "stone2", "stone3"]
RUBBLE = ["rubble", "rubble2", "rubble3"]
CAPS = ["cap", "cap2", "stone3"]

# front stones as reference screen bboxes (x0, y0, x1, y1, kind): 'o' organic, 'r' blocky
FRONT_STONES = [
    # top row
    (435, 215, 550, 300, "r"), (555, 210, 690, 305, "o"), (800, 205, 935, 300, "o"),
    (875, 262, 980, 370, "o"), (1050, 120, 1150, 228, "o"), (1130, 170, 1250, 340, "o"),
    (1255, 275, 1320, 410, "r"),
    # middle row
    (575, 305, 820, 565, "o"), (450, 380, 525, 480, "o"), (370, 320, 455, 415, "r"),
    (830, 360, 980, 460, "o"), (985, 350, 1145, 500, "o"), (1230, 425, 1295, 530, "r"),
    (500, 460, 640, 580, "o"),
    # lower row
    (525, 555, 700, 810, "o"), (785, 520, 975, 740, "o"), (1015, 505, 1140, 640, "o"),
    (1150, 510, 1270, 680, "o"), (405, 545, 460, 610, "r"), (435, 680, 500, 790, "r"),
    (1030, 670, 1150, 770, "r"), (1160, 690, 1235, 745, "r"), (1240, 670, 1300, 720, "r"),
    (1270, 570, 1320, 660, "r"), (815, 745, 935, 830, "r"), (540, 800, 670, 885, "r"),
    (700, 650, 790, 790, "r"), (370, 600, 420, 760, "r"), (380, 770, 440, 900, "r"),
]


# ---------------------------------------------------------------- helpers

def scr2wall(sx: float, sy: float) -> tuple[float, float]:
    """Reference screen point on the front plane -> (x, z) in voxels."""
    s = min(max((sx - S_LX) / (S_RX - S_LX), 0.0), 1.0)
    t = s / (PERSP_K - (PERSP_K - 1) * s)          # undo perspective foreshortening
    yt = S_TL + (S_TR - S_TL) * s
    yb = S_BL + (S_BR - S_BL) * s
    v = (yb - sy) / (yb - yt)
    return X0 + t * L, v * H


def stone_mask(w: int, h: int, kind: str, rng):
    """Boolean (w, h) mask of one stone face: blocky with notched corners, or a
    stepped organic blob (superellipse + jitter)."""
    import numpy as np
    if kind == "r":
        mk = np.ones((w, h), bool)
        for cx, cz in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if rng.random() < 0.35 and w > 3 and h > 3:
                mk[cx, cz] = False
        return mk
    # chunky stepped polygon: a jittered superellipse on a coarse grid (2-voxel cells
    # for big stones), so the outline steps in blocks like the reference
    cell = 2 if min(w, h) >= 10 else 1
    cw, ch = -(-w // cell), -(-h // cell)
    i = (np.arange(cw) + 0.5) / cw * 2 - 1
    k = (np.arange(ch) + 0.5) / ch * 2 - 1
    I, K = np.meshgrid(i, k, indexing="ij")
    p = rng.uniform(1.4, 2.2)
    r = np.abs(I) ** p + np.abs(K) ** p
    r = r + rng.uniform(-0.3, 0.3, r.shape) * np.clip(r, 0.3, 1.0)
    mc = r <= 1.0
    mc[cw // 2, ch // 2] = True
    return np.repeat(np.repeat(mc, cell, 0), cell, 1)[:w, :h]


def front_stone(m: Model, x0: int, z0: int, w: int, h: int, kind: str):
    mk = stone_mask(w, h, kind, m.rng)
    c = STONES[int(m.rng.integers(len(STONES)))]
    m.where(x0, FY - RELIEF, z0, w, RELIEF, h,
            lambda X, Y, Z: mk[X - x0, Z - z0], c)


def rubble(m: Model, n: int):
    """Small 1-voxel tiles scattered over the front plane between the stones."""
    for _ in range(n):
        w, h = int(m.rng.integers(2, 5)), int(m.rng.integers(2, 4))
        x = int(m.rng.integers(X0, X0 + L - w + 1))
        z = int(m.rng.integers(0, H - h + 1))
        m.box(x, FY - 1, z, w, 1, h, RUBBLE[int(m.rng.integers(3))], only_empty=True)


# ---------------------------------------------------------------- build

def build() -> Model:
    W = X0 + L + 3
    D = FY + T + RELIEF
    m = Model(W, D, H + 6, seed=11)
    palette(m)

    # --- body with rubble texture
    m.box(X0, FY, 0, L, T, H, "rubble")
    m.bricks(RUBBLE, target="rubble", bw=4, bh=3, p=[0.45, 0.3, 0.25])

    # --- front stones from the reference layout
    for sx0, sy0, sx1, sy1, kind in FRONT_STONES:
        xa, _ = scr2wall(sx0, (sy0 + sy1) / 2)
        xb, _ = scr2wall(sx1, (sy0 + sy1) / 2)
        _, zt = scr2wall((sx0 + sx1) / 2, sy0)
        _, zb = scr2wall((sx0 + sx1) / 2, sy1)
        x0, x1 = round(xa), round(xb)
        z0, z1 = max(round(zb), 0), min(round(zt), H)
        if kind == "o":     # the bbox includes the stone's lit side faces
            x0, x1, z0, z1 = x0 + 1, x1 - 1, z0 + 1, z1 - 1
        if x1 - x0 >= 2 and z1 - z0 >= 2:
            front_stone(m, x0, z0, x1 - x0, z1 - z0, kind)
    rubble(m, 40)

    # --- left end: stacked quoin cubes with recessed joints
    for i, z in enumerate(range(0, H, Q_PITCH)):
        out = Q_OUT if i % 2 == 0 else Q_OUT - 1
        h = min(Q_PITCH - 1, H - z)
        m.box(X0 - out, FY - 1, z, out + 3, T + 2, h, "quoin" if i % 2 == 0 else "quoin2")
        m.box(X0 - out, FY - 1, z + h, out + 1, T + 2, 1, None)        # dark joint
        m.box(X0, FY, z + h, 1, T, 1, "joint", only_empty=True)

    # --- right end: blocks sticking out to the right
    z = 0
    while z < H:
        h = int(m.rng.integers(4, 8))
        out = int(m.rng.integers(2, 4))
        m.box(X0 + L - 4, FY - 1, z, 4 + out, T + 2, min(h - 1, H - z), CAPS[int(m.rng.integers(3))])
        z += h

    # --- coping: short irregular blocks along the top, small cubes lying on them
    x = X0 - Q_OUT
    while x < X0 + L + 2:
        w = int(m.rng.integers(4, 10))
        h = int(m.rng.integers(1, 3))
        dy = int(m.rng.integers(0, 2))
        m.box(x, FY - 1 + dy, H, w, T + 2 - dy, h, CAPS[int(m.rng.integers(3))])
        x += w
    for _ in range(14):
        w, d = int(m.rng.integers(2, 5)), int(m.rng.integers(2, 6))
        x = int(m.rng.integers(X0, X0 + L - w))
        y = int(m.rng.integers(FY, FY + T - d))
        m.box(x, y, H + 1, w, d, 1, CAPS[int(m.rng.integers(3))], only_empty=True)
    m.box(X0 + L - 12, FY - 1, H, 14, T + 2, 2, "cap")                 # right corner pile
    m.box(X0 + L - 7, FY, H + 2, 8, T, 1, "cap2")
    m.box(X0 - Q_OUT, FY - 1, H, 7, T + 2, 2, "quoin")                 # left quoin cap
    m.box(X0 - Q_OUT + 1, FY + 1, H + 2, 5, T - 3, 1, "quoin2")

    # --- back: mirror of the front relief
    back = FY + T
    m.v[:, back:back + RELIEF, :] = m.v[:, FY - RELIEF:FY, :][:, ::-1, :]

    return m
