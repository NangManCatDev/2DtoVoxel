"""항구의 목재 부두 세트 — reference/복셀_항구의_목재_부두_세트-1.png

Kit sheet of three wooden harbour docks, each drawn inside m.part() so the .vox holds one
object per piece:
  straight   S_LEN x WIDTH deck between four tall corner posts, legs under the middle
  t          stem T_STEM long (x) running into a crossbar T_CB_D deep x T_CB long (y);
             seven tall posts (crossbar corners, far middle, two at the stem end)
  bent       back segment along y (B_BACK long, B_DEPTH deep: the sheet draws it deeper
             than a standard run) and a front segment turning B_TURN degrees toward the
             viewer (B_FRONT), mitred joint; five tall posts, legs under the bend

Shared look (x to the right/back, y depth with y=0 front, z up): POST x POST posts H_POST
tall with a beige end-grain cap and a dark wet foot; deck top at DECK_TOP made of
PLANK_T-thick planks with a groove every PITCH, raised nails and an edge beam frame
BEAM_H tall under it. The deck's long edges run through the post centres (EDGE), its ends
reach the posts' outer faces. LEG x LEG legs where the sheet shows them; iron mooring rings
(plate + hanging loop) and iron bands on the outer posts.

The sheet is an oblique drawing in which each piece is drawn at a slightly different
angle (the T's crossbar is level on screen), so no single camera fits all three; the
pieces stay axis-aligned (modular, they snap together in MagicaVoxel) and VIEW is the best
compromise. layout() puts each piece's screen bbox centre where the sheet has it.
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_2239_4"
REFERENCE = "reference/복셀_항구의_목재_부두_세트-1.png"
VIEW = {"azimuth": 58, "elevation": 40}
CUTOUT = {"keep": "all"}
RES = 1

# shared dimensions (design voxels)
POST, H_POST = 8, 32
DECK_TOP = 24                   # top surface of the planks
PLANK_T, BEAM_H = 2, 6
PITCH = 5                       # 4-voxel plank + 1-voxel groove
WIDTH = 30                      # outer width of a deck run (outer post faces)
EDGE = POST // 2                # the deck's long edges run through the post centres
LEG = 6
LEG_H = DECK_TOP - PLANK_T - BEAM_H
RING_TOP = DECK_TOP + 3         # top of a mooring ring's wall plate
BAND_Z = DECK_TOP - 6
WET_Z, WET2_Z = 12, 6           # posts darken below these heights

# pieces
S_LEN = 76                          # straight dock length (x)
T_STEM, T_CB, T_CB_D = 50, 84, 30   # T: stem length (x), crossbar length (y), crossbar depth (x)
T_WING = 20                         # the stem joins the crossbar off-centre: short wing on the front (-y)
B_BACK, B_FRONT = 40, 44            # bent: back segment length (y) and front segment length
B_DEPTH = 36                        # bent: the back segment is deeper (x) than a standard run
B_TURN = 45                         # bent: the front segment turns this far from -y toward -x
DIAG_PITCH = 7                      # 45-degree planks: a groove every 7 voxel diagonals (~PITCH)

# sheet layout: screen bbox centre (reference px) of each piece, and px per voxel there
SHEET = {"straight": (353, 368), "t": (1113, 351), "bent": (1845, 368)}
PX_PER_VOX = 7.7
MARGIN = 4

PLANKS = ["plank", "plank2", "plank3"]
POSTS = ["post", "post2", "post3"]


def palette(m: Model):
    p = m.pal
    # top faces as sampled; side faces = sample / 0.9 (front) or / 0.76 (left)
    p.add("plank", "#b07048"); p.add("plank2", "#a1623f"); p.add("plank3", "#bc7c50")
    p.add("groove", "#5a321f"); p.add("nail", "#4a4c50")
    p.add("beam", "#7a4529")
    p.add("post", "#6e3c25"); p.add("post2", "#7f4930"); p.add("post3", "#5e321e")
    p.add("wet_mid", "#573124"); p.add("wet", "#45291f"); p.add("wet2", "#2c1e1d")
    p.add("cap", "#dab78f"); p.add("cap_lt", "#e8cba6"); p.add("cap_dk", "#b98e66")
    p.add("iron", "#2c393f"); p.add("iron_lt", "#4f636c"); p.add("iron_dk", "#1a2226")


# ---------------------------------------------------------------- layout

def _screen_axes():
    a, e = math.radians(VIEW["azimuth"]), math.radians(VIEW["elevation"])
    right = np.array([math.cos(a), -math.sin(a), 0.0])
    up = np.array([math.sin(e) * math.sin(a), math.sin(e) * math.cos(a), math.cos(e)])
    return a, e, right, up


def layout(pieces: dict) -> tuple[dict, tuple]:
    """Origins for the pieces so that each one's screen bbox centre under VIEW (orthographic)
    sits where SHEET has it relative to the T; plus the grid size. Each piece is first built
    alone at (0, 0) to measure its size and screen bbox. pieces: name -> (size, build fn)."""
    a, e, right, up = _screen_axes()
    org = {}
    for k, ((w, d), fn) in pieces.items():
        t = Model(w + 2 * MARGIN, d + 2 * MARGIN, H_POST + 2, seed=0)
        palette(t)
        fn(t, MARGIN, MARGIN)
        p = np.argwhere(t.v > 0) + 0.5 - [MARGIN, MARGIN, 0]
        su, sv = p @ right, p @ up
        cu, cv = (su.min() + su.max()) / 2, (sv.min() + sv.max()) / 2
        tu = (SHEET[k][0] - SHEET["t"][0]) / PX_PER_VOX - cu       # wanted screen pos of the origin
        tv = -(SHEET[k][1] - SHEET["t"][1]) / PX_PER_VOX - cv
        depth = tv / math.sin(e)
        org[k] = (tu * math.cos(a) + depth * math.sin(a), -tu * math.sin(a) + depth * math.cos(a))
    mx = min(o[0] for o in org.values())
    my = min(o[1] for o in org.values())
    org = {k: (int(round(o[0] - mx)) + MARGIN, int(round(o[1] - my)) + MARGIN) for k, o in org.items()}
    W = max(org[k][0] + pieces[k][0][0] for k in pieces) + MARGIN
    D = max(org[k][1] + pieces[k][0][1] for k in pieces) + MARGIN
    return org, (W, D, H_POST + 2)


# ---------------------------------------------------------------- helpers

def wood(m: Model, x, y, w, d, h):
    """Post / leg block: vertical grain streaks, darkening (wet) toward the foot."""
    m.box(x, y, 0, w, d, h, "post")
    ids = np.array([m.pal.idx(c) for c in POSTS], np.uint8)
    wet, wet2, mid = m.pal.idx("wet"), m.pal.idx("wet2"), m.pal.idx("wet_mid")

    def colour(X, Y, Z):
        col = (np.floor(X).astype(np.int64) * 7 + np.floor(Y).astype(np.int64) * 13) % 5
        base = ids[np.select([col == 0, col == 3], [1, 2], 0)]
        base = np.where(m.rng.random(X.shape) < 0.12, ids[m.rng.integers(0, 3, X.shape)], base)
        z = Z + m.rng.random(X.shape) * 3
        return np.where(z < WET2_Z, wet2, np.where(z < WET_Z, wet, np.where(z < WET_Z + 4, mid, base)))
    m.paint_fn(x, y, 0, w, d, h, colour)


def post(m: Model, x, y, ring: str | None = None, band: bool = False):
    """Tall corner post with a bevelled end-grain cap; optional mooring ring on a face."""
    wood(m, x, y, POST, POST, H_POST)
    z = H_POST - 1
    m.box(x, y, z, POST, POST, 1, "cap_dk")
    m.box(x + 1, y + 1, z, POST - 2, POST - 2, 1, "cap")
    m.where(x + 2, y + 2, z, POST - 4, POST - 4, 1, lambda X, Y, Z: m.rng.random(X.shape) < 0.6, "cap_lt")
    for cx in (x, x + POST - 1):            # bevelled corners
        for cy in (y, y + POST - 1):
            m.box(cx, cy, z, 1, 1, 1, None)
    if band:
        m.box(x - 1, y - 1, BAND_Z, POST + 2, POST + 2, 1, "iron", only_empty=True)
    if ring:
        mooring_ring(m, x, y, ring)


def mooring_ring(m: Model, x, y, face: str):
    """Iron wall plate with a knob and a ring hanging below it, on one face of the post
    at (x, y). Face-local a = along the face from its middle, o = offset out (1 = touching)."""
    c = POST // 2

    def put(a0, o0, z0, wa, wo, hz, col):
        if face == "-y":
            m.box(x + c + a0, y - o0 - wo + 1, z0, wa, wo, hz, col)
        elif face == "+y":
            m.box(x + c + a0, y + POST - 1 + o0, z0, wa, wo, hz, col)
        elif face == "-x":
            m.box(x - o0 - wo + 1, y + c + a0, z0, wo, wa, hz, col)
        else:
            m.box(x + POST - 1 + o0, y + c + a0, z0, wo, wa, hz, col)

    t = RING_TOP
    put(-2, 1, t - 4, 4, 1, 4, "iron")              # plate
    put(-1, 2, t - 4, 2, 1, 2, "iron_lt")           # knob
    put(-3, 3, t - 13, 7, 2, 10, "iron")            # chunky ring hanging off the knob
    put(-1, 3, t - 11, 3, 2, 7, None)               # its hole (the post shows through)
    put(-3, 3, t - 13, 7, 2, 1, "iron_dk")          # shaded underside
    put(-3, 4, t - 4, 7, 1, 1, "iron_lt")           # lit top edge


def deck(m: Model, ox, oy, w, d, inside, along, joint=None, lines=None):
    """Plank deck over the plan mask inside(X, Y) (absolute design coords, vectorised) in
    the box (ox, oy, w, d): planks across the `along` coordinate with a groove where its
    floor is a multiple of PITCH (or where lines(X, Y), if given) and wherever joint(X, Y),
    raised nails in the middle of the planks, an edge beam frame underneath."""
    z0 = DECK_TOP - PLANK_T
    m.where(ox, oy, z0, w, d, PLANK_T, lambda X, Y, Z: inside(X, Y), "plank")
    ids = np.array([m.pal.idx(c) for c in PLANKS], np.uint8)

    def colour(X, Y, Z):
        k = np.floor(along(X, Y) / PITCH).astype(np.int64)
        pick = ids[np.abs(k * 7 + 3) % 5 % 3]
        grain = m.rng.random(X.shape) < 0.15
        return np.where(grain, ids[m.rng.integers(0, 3, X.shape)], pick)
    m.paint_fn(ox, oy, z0, w, d, PLANK_T, colour)

    def groove(X, Y):
        g = lines(X, Y) if lines is not None else np.floor(along(X, Y)) % PITCH == 0
        if joint is not None:
            g |= joint(X, Y)
        return inside(X, Y) & g
    m.where(ox, oy, DECK_TOP - 1, w, d, 1, lambda X, Y, Z: groove(X, Y), None)
    m.where(ox, oy, z0, w, d, 1, lambda X, Y, Z: groove(X, Y), "groove", only_filled=True)

    def core(X, Y, e):
        return inside(X - e, Y) & inside(X + e, Y) & inside(X, Y - e) & inside(X, Y + e)

    m.where(ox, oy, z0 - BEAM_H, w, d, BEAM_H, lambda X, Y, Z: inside(X, Y) & ~core(X, Y, 2), "beam")
    m.where(ox, oy, DECK_TOP, w, d, 1,
            lambda X, Y, Z: core(X, Y, 2) & ~groove(X, Y) & (np.floor(along(X, Y)) % PITCH == 2)
            & (m.rng.random(X.shape) < 0.07), "nail")


def legs(m: Model, spots):
    for x, y in spots:
        wood(m, int(round(x)), int(round(y)), LEG, LEG, LEG_H)


# ---------------------------------------------------------------- pieces

def straight_piece(m: Model, ox, oy):
    L, W = S_LEN, WIDTH
    deck(m, ox, oy, L, W,
         lambda X, Y: (X >= ox + 1) & (X < ox + L - 1) & (Y >= oy + EDGE) & (Y < oy + W - EDGE),
         lambda X, Y: X - ox)
    # leg positions as measured on the sheet: front one 3/4 along, back one near the left end
    legs(m, [(ox + 0.72 * L - LEG / 2, oy + EDGE + 1), (ox + 0.2 * L - LEG / 2, oy + W - EDGE - LEG + 2)])
    post(m, ox, oy + W - POST, "-x")
    post(m, ox, oy, "-y", band=True)
    post(m, ox + L - POST, oy + W - POST, "+y")
    post(m, ox + L - POST, oy, "-y")


def t_piece(m: Model, ox, oy):
    sy0 = oy + T_WING                        # stem's outer low-y side
    sx1 = ox + T_STEM                        # crossbar's near (low-x) side
    fx = sx1 + T_CB_D                        # crossbar's far side

    def in_stem_band(Y):
        return (Y >= sy0 + EDGE) & (Y < sy0 + WIDTH - EDGE)

    def inside(X, Y):
        stem = (X >= ox + 1) & (X < sx1 + EDGE) & in_stem_band(Y)
        cb = (X >= sx1 + EDGE) & (X < fx - EDGE) & (Y >= oy + 1) & (Y < oy + T_CB - 1)
        return stem | cb

    deck(m, ox, oy, fx - ox, T_CB, inside,
         lambda X, Y: np.where(in_stem_band(Y), X - ox, Y - oy),     # wings: planks along x
         lambda X, Y: (X >= sx1 + EDGE)
         & ((np.floor(Y) == sy0 + EDGE - 1) | (np.floor(Y) == sy0 + WIDTH - EDGE)))
    wing = (oy + T_CB + sy0 + WIDTH) / 2     # middle of the long (high-y) wing
    legs(m, [(sx1 - LEG + 2, sy0 + EDGE - 2),             # front side of the stem, at the crossbar
             (sx1 + EDGE - 2, wing - 3), (fx - EDGE - LEG + 2, wing - 3)])
    post(m, ox, sy0 + WIDTH - POST)                         # F
    post(m, ox, sy0, "-y", band=True)                       # G
    post(m, sx1, oy + T_CB - POST)                          # B
    post(m, sx1, oy, "-y", band=True)                       # E
    post(m, fx - POST, oy + T_CB - POST, "+x")              # A
    post(m, fx - POST, oy + T_CB // 2 - POST // 2, "+x")    # C
    post(m, fx - POST, oy, "-y")                            # D


def _turn():
    t = math.radians(B_TURN)
    return math.sin(t), math.cos(t)      # front segment direction (-s, -c), across it (c, -s)


def bent_size() -> tuple[int, int]:
    """Footprint: how far the front segment (with its end posts) reaches past the bend centre."""
    s, c = _turn()
    rx = int(math.ceil(B_FRONT * s + (WIDTH / 2) * c + POST / 2)) + 1
    ry = int(math.ceil(B_FRONT * c + (WIDTH / 2) * s + POST / 2)) + 1
    return rx + B_DEPTH // 2, ry + B_BACK


def bent_piece(m: Model, ox, oy):
    s, c = _turn()
    W, D = bent_size()
    bx0 = ox + W - B_DEPTH                   # back segment's outer low-x side
    yb = oy + D - B_BACK                     # bend line
    cx, cy = bx0 + B_DEPTH / 2, yb           # bend centre
    hb = B_DEPTH / 2 - EDGE                  # back segment's deck half-width
    hw = WIDTH / 2 - EDGE                    # front segment's (edges through the post centres)
    h = 0.5 / m.res

    def uv(X, Y):                            # u along the front segment, v across it
        dx, dy = X + h - cx, Y + h - cy
        return -(dx * s + dy * c), dx * c - dy * s, dx, dy

    def inside(X, Y):
        u, v, dx, dy = uv(X, Y)
        back = (np.abs(dx) < hb) & (dy >= 0) & (dy < B_BACK - 1)
        front = (u >= 0) & (u < B_FRONT) & (np.abs(v) < hw)
        wedge = (dy < 0) & (u < 0) & (dx < hb) & (v < hw)       # outer side of the mitre
        return back | front | wedge

    diag = B_TURN == 45                      # 45 degrees: grooves follow whole voxel diagonals

    def front_along(X, Y, u):
        if not diag:
            return u
        k = np.floor((cx + cy - X - Y) * m.res + 1e-6) / m.res    # diagonal index, step 1/sqrt(2)
        return k * PITCH / DIAG_PITCH

    def along(X, Y):
        u, v, dx, dy = uv(X, Y)
        return np.where(dy > u, dy, front_along(X, Y, u))   # back: planks along x; front: across it

    def lines(X, Y):
        u, v, dx, dy = uv(X, Y)
        a = front_along(X, Y, u)
        front = np.round(a * DIAG_PITCH / PITCH) % DIAG_PITCH == 0 if diag else np.floor(a) % PITCH == 0
        return np.where(dy > u, np.floor(dy) % PITCH == 0, front)

    def mitre(X, Y):
        u, v, dx, dy = uv(X, Y)
        return np.abs(dy - u) < 0.75

    deck(m, ox, oy, W, D, inside, along, mitre, lines)

    def at(u, v):                            # plan point of front-segment coords
        return cx - u * s + v * c, cy - u * c - v * s

    fl, fr = at(B_FRONT - POST / 2, -hw), at(B_FRONT - POST / 2, hw)
    m1, m2 = at(B_FRONT / 2, -hw), at(B_FRONT / 2, hw)
    legs(m, [(cx - hb - 2, yb - 2), (m1[0] - 3, m1[1] - 3), (m2[0] - 3, m2[1] - 3),
             (cx - hb + 5, yb + B_BACK // 2 - 6)])            # centre support under the back segment
    post(m, bx0, yb + B_BACK - POST, "-x")                                  # L
    post(m, bx0 + B_DEPTH - POST, yb + B_BACK - POST, "+y", band=True)      # back corner
    ry = cy + (hb * c - hw) / s                                             # outer mitre corner
    post(m, bx0 + B_DEPTH - POST, int(round(ry)) - POST // 2, "-y")
    post(m, int(round(fl[0])) - POST // 2, int(round(fl[1])) - POST // 2, "-x", band=True)
    post(m, int(round(fr[0])) - POST // 2, int(round(fr[1])) - POST // 2, "-y")


# ---------------------------------------------------------------- build

def build() -> Model:
    org, grid = layout({"straight": ((S_LEN, WIDTH), straight_piece),
                        "t": ((T_STEM + T_CB_D, T_CB), t_piece),
                        "bent": (bent_size(), bent_piece)})
    m = Model(*grid, seed=29, res=RES)
    palette(m)
    with m.part("straight_dock"):
        straight_piece(m, *org["straight"])
    with m.part("t_dock"):
        t_piece(m, *org["t"])
    with m.part("bent_dock"):
        bent_piece(m, *org["bent"])
    return m
