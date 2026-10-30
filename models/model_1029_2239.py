"""어시장 소품 아틀라스 — reference/복셀_어시장_소품_아틀라스-4.png

A kit sheet of fish-market props, every piece its own m.part() object:
  stall          wooden counter (3 bins: silver fish / salmon on a tray / fish on ice,
                 framed front panels), 4 posts (back ones taller), side rafters that follow
                 a sagging striped awning (9 cream/blue stripes, front valance with tabs),
                 side tie beams + knee braces, back beam, post caps
  lantern        iron lantern with glowing panes on a bracket off the back-right post
  crate_fish     slatted crate, corner posts, ice + 3 silver fish + parsley
  crate_salmon   the same crate with 3 salmon fillets
  barrel         bulging staved barrel, 2 iron hoops, sunken lid, bung
  net            heap of blue net with a cream rope lattice, brown rope loops, floats
  basket_round   round wicker basket with a blue band and two ear handles
  basket_rect    rectangular wicker basket with a blue band and end handles

The sheet is one camera (VIEW) over all pieces. Each piece is placed on the ground
(z=0) where the sheet draws it: ANCHOR holds the reference pixel under the piece's
centre and ground() turns it into grid x/y for the current VIEW, so a camera change
moves the layout with it. Coordinates: x right, y depth (y=0 front), z up.
"""
import math

import numpy as np

from voxtool import Model

NAME = "model_1029_2239"
REFERENCE = "reference/복셀_어시장_소품_아틀라스-4.png"
# fit-camera found az 321 el 30 for the first draft; with the layout following the camera,
# az 325 el 28 scored best (the stall's long side is drawn flatter than the crates')
VIEW = {"azimuth": 325, "elevation": 28, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 1

PX = 10.0          # reference pixels per voxel (post widths, awning tabs)
# reference pixel of the ground point under each piece's centre
ANCHOR = {
    "stall": (435, 745),
    "crate_fish": (1058, 279),
    "crate_salmon": (1401, 307),
    "barrel": (1037, 655),
    "net": (1410, 680),
    "basket_round": (988, 912),
    "basket_rect": (1348, 922),
}
# half extents (x-, x+, y-, y+) of each piece around its centre, for the grid size
EXTENT = {
    "stall": (40, 48, 20, 19),
    "crate_fish": (13, 13, 12, 12),
    "crate_salmon": (13, 13, 12, 12),
    "barrel": (12, 12, 12, 12),
    "net": (25, 21, 25, 21),
    "basket_round": (17, 17, 17, 17),
    "basket_rect": (19, 19, 10, 10),
}

# stall
POST = 5
STRIPE, N_STRIPE = 7, 9
AWN_W = STRIPE * N_STRIPE          # awning between the posts
ST_W = AWN_W + 2 * POST            # outer width (x)
ST_D = 34                          # outer depth (y)
CTR_H = 15                         # counter height
ZF, ZB = 54, 66                    # awning top at the front / back edge
HEM = 6                            # front valance drop
BIN_DEPTH = 5                      # bins sunk into the counter top
LANTERN_Z = 40                     # lantern base
LANTERN_OUT = 6                    # lantern centre past the back-right post (x)
# crates (outer w, d, rim height)
CRATE_FISH = (23, 21, 12)
CRATE_SALMON = (24, 21, 12)
# barrel
BAR_H, BAR_RE, BAR_RM = 24, 8.4, 10.4
HOOPS = ((5, 8), (17, 20))
# net heap
NET_R, NET_H = 19, 25
# baskets
RB_RT, RB_RB, RB_H = 11.0, 9.5, 15
REC_W, REC_D, REC_H = 31, 14, 11

WOOD = ["wood", "wood_md", "wood_lt"]
LEAVES = ["leaf", "leaf2", "leaf3"]
ICE = ["ice", "ice2", "ice3"]


def palette(m: Model):
    p = m.pal
    p.add("wood_lt", "#d4803f"); p.add("wood", "#b8642f"); p.add("wood_md", "#9c5428")
    p.add("wood_dk", "#743c1b"); p.add("wood_dd", "#4e2611"); p.add("wood_gap", "#301509")
    p.add("cream", "#fde9cf"); p.add("cream2", "#f1d6b4")
    p.add("blue", "#167ab2"); p.add("blue2", "#0e67a2"); p.add("blue3", "#0a5689")
    p.add("iron", "#2a2830"); p.add("iron2", "#45424e")
    p.add("glow", "#ffae18", emit=1.0); p.add("glow2", "#ffe27a", emit=1.0)
    p.add("fish_w", "#f2f4f8"); p.add("fish_s", "#b6c8dc"); p.add("fish_b", "#4c74a2")
    p.add("fish_d", "#2a466a"); p.add("eye", "#10141c")
    p.add("salm", "#fb5c2a"); p.add("salm2", "#e2442a"); p.add("salm_l", "#ffc2a2")
    p.add("ice", "#eef3f8"); p.add("ice2", "#cfe0ee"); p.add("ice3", "#a9c6df")
    p.add("leaf", "#4c8a1c"); p.add("leaf2", "#2f6412"); p.add("leaf3", "#6eae2e")
    p.add("stave", "#d6843e"); p.add("stave2", "#c27032"); p.add("stave3", "#aa5e28")
    p.add("stave_gap", "#5a2a12"); p.add("hoop", "#4e5870"); p.add("hoop2", "#363c4e")
    p.add("lid", "#6e4840"); p.add("bung", "#c8903e")
    p.add("wick", "#d68e44"); p.add("wick2", "#b46a2c"); p.add("wick3", "#8a4618")
    p.add("wband", "#2a6ca0"); p.add("wband2", "#1c5482")
    p.add("net", "#1d6294"); p.add("net2", "#0f4470"); p.add("net3", "#2c7cb0")
    p.add("rope", "#eed4ac"); p.add("rope2", "#d2b28c")
    p.add("brope", "#a6642c"); p.add("brope2", "#7c4820")
    p.add("float_w", "#f2ebe0"); p.add("float_b", "#1a6aa4")


# ---------------------------------------------------------------- layout

def ground(u: float, v: float) -> np.ndarray:
    """Grid offset (x, y) from the stall centre of the ground point VIEW draws at
    reference pixel (u, v), PX pixels per voxel (orthographic)."""
    a, e = math.radians(VIEW["azimuth"]), math.radians(VIEW["elevation"])
    right = (math.cos(a), -math.sin(a))
    down = (-math.sin(e) * math.sin(a), -math.sin(e) * math.cos(a))
    u0, v0 = ANCHOR["stall"]
    return np.linalg.solve(np.array([right, down]), np.array([u - u0, v - v0]) / PX)


def layout():
    """Piece centres in grid coordinates and the grid size."""
    rel = {k: ground(*uv) for k, uv in ANCHOR.items()}
    lo = np.min([[c[0] - EXTENT[k][0], c[1] - EXTENT[k][2]] for k, c in rel.items()], axis=0)
    hi = np.max([[c[0] + EXTENT[k][1], c[1] + EXTENT[k][3]] for k, c in rel.items()], axis=0)
    centres = {k: tuple(np.round(c - lo).astype(int)) for k, c in rel.items()}
    size = tuple(np.ceil(hi - lo).astype(int) + 1)
    return centres, (int(size[0]), int(size[1]), ZB + 8)


# ---------------------------------------------------------------- small helpers

def screen_right() -> np.ndarray:
    a = math.radians(VIEW["azimuth"])
    return np.array([math.cos(a), -math.sin(a)])


def toward_camera() -> np.ndarray:
    a = math.radians(VIEW["azimuth"])
    return np.array([-math.sin(a), -math.cos(a)])


def grain(m: Model, region, colors=WOOD, p=(0.45, 0.4, 0.15)):
    m.vary(list(colors), target=list(colors), p=list(p), region=region)


def fish(m: Model, x, y, z, along="y", head=-1, kind="silver", L=14, hw=2):
    """A plump fish lying flat, centre line at x (along='y') or y (along='x'), head at the
    low end (head=-1) or high end (+1), at most 2*hw+1 wide. Silver fish: rounded body in
    layers (each one narrower), dark blue-grey back, pale flanks, eyes, forked tail.
    Salmon: a flat fillet, pointed at both ends, with light fat stripes."""
    if kind == "salmon":                       # half widths along the fish, head first
        prof = [max(1, round(hw * math.sin(math.pi * (i + 0.5) / L) ** 0.5)) for i in range(L)]
    else:
        nb = L - 3
        prof = [max(1, round(hw * math.sin(math.pi * (i + 0.8) / (nb + 0.6)) ** 0.6)) for i in range(nb)]
        prof += [0, 1, 2]
    n = len(prof)

    def put(i, j, k, c):
        s = i if head < 0 else n - 1 - i
        if along == "y":
            m.set(x + j, y + s, z + k, c)
        else:
            m.set(x + s, y + j, z + k, c)

    for i, w in enumerate(prof):
        for j in range(-w, w + 1):
            if kind == "salmon":
                put(i, j, 0, "salm2")
                if abs(j) < w or w == 1:
                    put(i, j, 1, "salm_l" if (i + j) % 4 == 0 else "salm2" if abs(j) == w - 1 else "salm")
            elif i >= n - 3:                                           # tail fin
                put(i, j, 0, "fish_b" if abs(j) < 2 else "fish_s")
            else:
                top = w - abs(j)                                       # rounded body: layers 0..top
                for k in range(min(top, 2) + 1):
                    if k < min(top, 2):
                        c = "fish_s"
                    elif j == 0 and 1 < i < n - 4:
                        c = "fish_b"
                    elif abs(j) == w:
                        c = "fish_w"
                    else:
                        c = "fish_s" if abs(j) == 1 else "fish_w"
                    put(i, j, k, c)
    if kind != "salmon":
        ie = 2 if hw <= 2 else 3
        for j in (-1, 1):
            put(ie, j * max(prof[ie] - 1, 1), 1, "eye")


def parsley(m: Model, pts, z):
    for (px, py) in pts:
        m.blob(px, py, z, 1.7, 1.7, 1.1, LEAVES, noise=0.45, density=0.85, p=[0.45, 0.3, 0.25])


def ice_bed(m: Model, x, y, z, w, d, h, bumps=0.25):
    m.box(x, y, z, w, d, h, "ice")
    m.vary(ICE, target="ice", p=[0.45, 0.35, 0.2], region=(x, y, z, w, d, h))
    m.scatter_on_top((x, y, z, w, d, h), ICE, bumps, target=ICE)


# ---------------------------------------------------------------- stall

def awning_z(y, ya, yb):
    """Top of the awning at depth y: sags like cloth, flat at the front, steep at the back."""
    t = np.clip((y - ya) / (yb - ya), 0, 1)
    return np.floor(ZF + (ZB - ZF) * t ** 2)


def counter(m: Model, x0, y0):
    W, D, H = ST_W, ST_D, CTR_H
    x1, y1 = x0 + W, y0 + D
    m.box(x0 + 1, y0 + 1, 0, W - 2, D - 2, H, "wood_md")              # carcass (recessed panels)
    m.paint_fn(x0, y0, 0, W, D, H, lambda X, Y, Z: np.where(Z % 4 == 3, m.pal.idx("wood_dk"), 0))
    m.box(x0 - 1, y0 - 1, 0, W + 2, D + 2, 2, "wood_dk")               # plinth, 1 proud
    m.box(x0, y0, H - 2, W, D, 2, "wood_lt")                           # top rim
    m.box(x0, y0, H - 3, W, D, 1, "wood", only_empty=True)
    bw = (W - 4 - 4) // 3
    divs = [x0 + 2 + bw, x0 + 4 + 2 * bw]
    for dx in divs:                                                    # stiles on the front / back
        m.box(dx - 1, y0, 2, 4, D, H - 4, "wood")
    for dy in (y0 + D // 2 - 1,):                                      # stile on the ends
        m.box(x0, dy, 2, W, 3, H - 4, "wood")
    # bins
    m.carve(x0 + 2, y0 + 2, H - BIN_DEPTH, W - 4, D - 4, BIN_DEPTH)
    m.box(x0 + 2, y0 + 2, H - BIN_DEPTH - 1, W - 4, D - 4, 1, "wood_dd")
    for dx in divs:
        m.box(dx, y0 + 2, H - BIN_DEPTH, 2, D - 4, BIN_DEPTH, "wood_lt")
    zb = H - BIN_DEPTH
    by0, bd = y0 + 2, D - 4
    bins = [(x0 + 2, bw), (divs[0] + 2, bw), (divs[1] + 2, x1 - 2 - divs[1] - 2)]

    fl = min(bd - 4, 21)                                               # fish length
    by0f = by0 + (bd - fl) // 2 - 1                                    # fish start, centred in depth

    # left bin: silver fish on parsley
    bx, w = bins[0]
    m.box(bx, by0, zb, w, bd, 2, "leaf2")
    m.vary(LEAVES, target="leaf2", p=[0.4, 0.4, 0.2], region=(bx, by0, zb, w, bd, 2))
    for k, fx in enumerate(range(bx + 3, bx + w - 2, 7)):
        fish(m, fx, by0f + (k % 2) * 2, zb + 2, along="y", head=-1, L=fl, hw=3)
    parsley(m, [(bx + 1, by0 + 1), (bx + w - 2, by0 + bd - 2), (bx + w - 2, by0 + 2), (bx + 2, by0 + bd - 2)],
            zb + 3)

    # middle bin: salmon fillets on ice in a dark tray
    bx, w = bins[1]
    m.box(bx, by0, zb, w, bd, 3, "wood_dk")
    m.carve(bx + 1, by0 + 1, zb, w - 2, bd - 2, 3)
    ice_bed(m, bx + 1, by0 + 1, zb, w - 2, bd - 2, 2, bumps=0.1)
    for k, fx in enumerate(range(bx + 3, bx + w - 2, 7)):
        fish(m, fx, by0f + 1 + (k % 2) * 2, zb + 2, along="y", head=-1, kind="salmon", L=fl - 2, hw=3)
    parsley(m, [(bx + 2, by0 + bd - 2), (bx + w - 2, by0 + 2), (bx + w - 3, by0 + bd - 3)], zb + 3)

    # right bin: crushed ice heaped over two fish
    bx, w = bins[2]
    for k, fx in enumerate((bx + 5, bx + 14)):
        fish(m, fx, by0f + 2 * k, zb + 2, along="y", head=-1, L=fl, hw=3)
    ice_bed(m, bx, by0, zb, w, bd, 3, bumps=0.3)
    m.sprinkle(["ice", "ice2"], 0.35, target=["fish_s", "fish_b", "fish_w"],
               region=(bx, by0, zb, w, bd, 6))
    parsley(m, [(bx + 2, by0 + bd - 3), (bx + w - 3, by0 + 2), (bx + w - 2, by0 + bd - 6)], zb + 4)
    grain(m, (x0, y0, 0, W, D, H), colors=["wood", "wood_md"], p=(0.6, 0.4))


def post(m: Model, px, py, top):
    m.box(px, py, 0, POST, POST, top, "wood")
    grain(m, (px, py, 0, POST, POST, top), colors=["wood", "wood_md", "wood_lt"], p=(0.55, 0.3, 0.15))
    m.box(px - 1, py - 1, 0, POST + 2, POST + 2, 3, "wood_md")         # foot
    m.box(px - 1, py - 1, CTR_H, POST + 2, POST + 2, 3, "wood")         # collar over the counter


def stall(m: Model, cx, cy):
    x0, y0 = cx - ST_W // 2, cy - ST_D // 2
    x1, y1 = x0 + ST_W, y0 + ST_D
    ya, yb = y0 - 1, y1 - 1
    counter(m, x0, y0)
    zs = lambda y: int(awning_z(y + 0.5, ya, yb))

    # posts reach up to the rafters
    fy, by = y0, y1 - POST
    for px in (x0, x1 - POST):
        post(m, px, fy, zs(fy + 2) - 2)
        post(m, px, by, zs(by + 2) - 2)

    # rafters over the side posts, following the awning, ends sticking out at the front
    for px in (x0, x1 - POST):
        for y in range(y0 - 3, y1):
            z = zs(max(y, ya))
            m.box(px, y, z - 2, POST, 1, 4, "wood")
        grain(m, (px, y0 - 3, ZF - 4, POST, ST_D + 3, ZB - ZF + 8))
    # back beam under the awning's back edge, ends past the posts
    m.box(x0 - 3, y1 - 3, zs(y1 - 3) - 5, ST_W + 6, 2, 3, "wood_md")
    # side tie beams just under the rafters' front ends, knee braces from the front post
    # tops down to the back posts
    zt = ZF - 6
    for px in (x0 + 1, x1 - POST + 1):
        m.box(px, y0, zt, 3, ST_D, 3, "wood_md")
        for dx in (0, 1, 2):
            for dz in (0, 1):
                m.line((px + dx, y0 + POST, zt - dz), (px + dx, y1 - POST, zt - 17 - dz), "wood_md")
    # caps on the post tops
    for px in (x0, x1 - POST):
        for py in (fy, by):
            m.box(px, py, zs(py + 2) + 2, POST, POST, 3, "wood_lt")
            m.box(px, py, zs(py + 2) + 2, POST, POST, 2, "wood")

    # awning: 2 thick, stripes across x, front valance with a tab per stripe
    ax0 = x0 + POST
    blue_i, cream_i = m.pal.idx("blue"), m.pal.idx("cream")

    def cloth(X, Y, Z):
        top = awning_z(Y + 0.5, ya, yb)
        return (Z <= top) & (Z >= top - 1)
    m.where(ax0, ya, ZF - 2, AWN_W, ST_D, ZB - ZF + 4, cloth, "cream")
    m.box(ax0, ya, ZF - HEM, AWN_W, 1, HEM, "cream")
    for k in range(N_STRIPE):
        m.set(ax0 + k * STRIPE + 2, ya, ZF - HEM - 1, "cream")
    m.paint_fn(ax0, ya, ZF - HEM - 2, AWN_W, ST_D, ZB - ZF + HEM + 6,
               lambda X, Y, Z: np.where(((X - ax0) // STRIPE) % 2 == 1, blue_i, cream_i))
    m.vary(["blue", "blue2", "blue3"], target="blue", p=[0.5, 0.35, 0.15],
           region=(ax0, ya, ZF - HEM - 2, AWN_W, ST_D, ZB - ZF + HEM + 6))
    m.vary(["cream", "cream2"], target="cream", p=[0.75, 0.25],
           region=(ax0, ya, ZF - HEM - 2, AWN_W, ST_D, ZB - ZF + HEM + 6))
    return x1, y1


def lantern(m: Model, cx, cy, z0, arm_from):
    """Iron lantern with glowing panes hanging from a wooden arm that starts at x=arm_from."""
    x, y, b = cx - 2, cy - 2, 8                                        # b = body height
    m.box(x - 1, y - 1, z0, 7, 7, 1, "iron")                            # base plate
    m.box(x, y, z0 + 1, 5, 5, b, "glow")                               # glowing body
    m.box(x + 1, y + 1, z0 + 2, 3, 3, b - 2, "glow2")
    for ex in (x, x + 4):                                              # corner bars
        for ey in (y, y + 4):
            m.box(ex, ey, z0 + 1, 1, 1, b, "iron2")
    m.box(x, y, z0 + 1, 5, 5, 1, "iron")
    zr = z0 + b + 1
    m.box(x - 1, y - 1, zr, 7, 7, 1, "iron")                           # roof
    m.box(x, y, zr + 1, 5, 5, 1, "iron2")
    m.box(x + 1, y + 1, zr + 2, 3, 3, 2, "iron")
    m.box(cx, cy, zr + 4, 1, 1, 4, "iron2")                            # hook
    m.box(arm_from, cy - 1, zr + 8, cx - arm_from + 2, 2, 2, "wood_md")  # bracket arm
    m.box(arm_from, cy - 1, zr + 4, 1, 2, 4, "wood_md")
    m.line((arm_from, cy, zr + 4), (arm_from + 3, cy, zr + 7), "wood_md")


# ---------------------------------------------------------------- crates

def crate(m: Model, cx, cy, dims, content):
    W, D, H = dims
    x0, y0 = cx - W // 2, cy - D // 2
    m.box(x0, y0, 0, W, D, H, "wood_gap")                             # dark inner skin
    m.carve(x0 + 2, y0 + 2, 1, W - 4, D - 4, H)
    planks = [(0, 3), (4, 3), (8, H - 8)]
    for z, h in planks:                                                # slats proud of the gaps
        m.box(x0, y0, z, W, 1, h, "wood")
        m.box(x0, y0 + D - 1, z, W, 1, h, "wood")
        m.box(x0, y0, z, 1, D, h, "wood")
        m.box(x0 + W - 1, y0, z, 1, D, h, "wood")
    m.box(x0, y0, H - 1, W, D, 1, "wood_lt", only_filled=True)
    m.box(x0 + 1, y0 + 1, H - 1, W - 2, D - 2, 1, "wood_lt", only_filled=True)
    for px in (x0, x0 + W - 3):                                        # corner posts
        for py in (y0, y0 + D - 3):
            m.box(px, py, 0, 3, 3, H + 1, "wood_md")
            m.box(px, py, H, 3, 3, 1, "wood_lt")
    grain(m, (x0, y0, 0, W, D, H + 1), colors=["wood", "wood_md", "wood_lt"], p=(0.55, 0.3, 0.15))
    # contents
    ix, iy, iw, idd = x0 + 2, y0 + 2, W - 4, D - 4
    ice_bed(m, ix, iy, 1, iw, idd, H - 3, bumps=0.2)
    zt = H - 2
    if content == "fish":
        for k, fy in enumerate(range(iy + 3, iy + idd - 2, 5)):
            fish(m, ix + 2 + (k % 2) * 2, fy, zt, along="x", head=-1, L=14)
    else:
        for k, fy in enumerate(range(iy + 3, iy + idd - 2, 5)):
            fish(m, ix + 3 + (k % 2), fy, zt, along="x", head=-1, kind="salmon", L=13)
    parsley(m, [(ix + 1, iy + idd - 2), (ix + iw - 2, iy + 1), (ix + iw - 2, iy + idd - 2),
                (ix + iw // 2, iy + idd - 1)], zt + 1)


# ---------------------------------------------------------------- barrel

def barrel(m: Model, cx, cy):
    cen = m._centred

    def r_at(Z):
        return BAR_RE + (BAR_RM - BAR_RE) * (1 - ((Z + 0.5 - BAR_H / 2) / (BAR_H / 2)) ** 2)

    def rr(X, Y):
        X, Y = cen(X, Y)
        return np.hypot(X - cx, Y - cy)

    R = int(BAR_RM) + 3
    box = (cx - R, cy - R, 0, 2 * R + 1, 2 * R + 1, BAR_H)
    m.where(*box, lambda X, Y, Z: rr(X, Y) <= r_at(Z), "stave")
    for z0, z1 in HOOPS:                                               # iron hoops, 1 proud
        m.where(cx - R, cy - R, z0, 2 * R + 1, 2 * R + 1, z1 - z0,
                lambda X, Y, Z: rr(X, Y) <= r_at(Z) + 1.0, "hoop")
    # staves: colour by angle with a dark groove between them
    st = np.array([m.pal.idx(c) for c in ("stave", "stave2", "stave3", "stave2")], np.uint8)
    gap, hoop, hoop2 = m.pal.idx("stave_gap"), m.pal.idx("hoop"), m.pal.idx("hoop2")
    N = 18

    def colour(X, Y, Z):
        Xc, Yc = cen(X, Y)
        a = (np.arctan2(Yc - cy, Xc - cx) + np.pi) / (2 * np.pi) * N
        k = np.floor(a).astype(int) % N
        c = st[(k * 7) % len(st)]
        c = np.where(a % 1 < 0.16, gap, c)
        in_hoop = np.zeros(X.shape, bool)
        for z0, z1 in HOOPS:
            in_hoop |= (Z >= z0) & (Z < z1)
        c = np.where(in_hoop, np.where(Z % 3 == 0, hoop2, hoop), c)
        return c
    m.paint_fn(*box, colour)
    # top: rim of stave ends, sunken lid
    m.where(cx - R, cy - R, BAR_H - 2, 2 * R + 1, 2 * R + 1, 2,
            lambda X, Y, Z: rr(X, Y) <= r_at(Z) - 2.0, None)
    m.where(cx - R, cy - R, BAR_H - 3, 2 * R + 1, 2 * R + 1, 1,
            lambda X, Y, Z: rr(X, Y) <= r_at(Z) - 2.0, "lid")
    # bung on the side facing the camera's right
    d = screen_right() + 0.7 * toward_camera()
    d /= np.linalg.norm(d)
    bx, by = np.round(np.array([cx, cy]) + d * (BAR_RM + 0.2)).astype(int)
    m.box(bx - 1, by - 1, 10, 3, 3, 3, "bung")
    m.set(bx + int(np.sign(d[0])), by + int(np.sign(d[1])), 11, "wood_dd")


# ---------------------------------------------------------------- net heap

def net_heap(m: Model, cx, cy):
    px, py = cx - 4, cy + 2                                            # peak a little back-left

    def height(X, Y):
        d = np.hypot((X - px) / (NET_R - 1), (Y - py) / (NET_R - 1))
        dome = NET_H * np.clip(1 - d ** 2.1, 0, 1)
        ds = np.hypot((X - cx) / NET_R, (Y - cy) / NET_R)
        skirt = 5 * np.clip(1 - ds ** 3, 0, 1)
        dl = np.hypot((X - sx) / 9, (Y - sy) / 9)                      # net spilling out front-left
        spill = 7 * np.clip(1 - dl ** 2, 0, 1)
        return np.maximum(np.maximum(dome, skirt), spill)

    sd = -screen_right() - 0.2 * toward_camera()
    sx, sy = np.array([cx, cy]) + 15 * sd / np.linalg.norm(sd)
    R = NET_R + 6
    box = (cx - R, cy - R, 0, 2 * R + 1, 2 * R + 1, NET_H + 2)
    m.where(*box, lambda X, Y, Z: Z < height(X, Y), "net")
    m.vary(["net", "net2", "net3"], target="net", p=[0.5, 0.3, 0.2], region=box)
    rope, rope2 = m.pal.idx("rope"), m.pal.idx("rope2")

    def lattice(X, Y, Z):
        a = (np.arctan2(Y - py, X - px) + np.pi) / (2 * np.pi) * 30
        s = Z / 2.2
        on = ((a + s) % 3 < 0.7) | ((a - s) % 3 < 0.7)
        on |= (Z <= 1) & (np.hypot(X - cx, Y - cy) > NET_R - 1.5)     # rope hem round the base
        on &= Z < height(X, Y)                                        # only the heap, not the barrel
        return np.where(on, np.where((X + Y + Z) % 3 == 0, rope2, rope), 0)
    m.paint_fn(*box, lattice)

    # brown rope loops over the heap
    def on_heap(dx, dy, lift=1):
        x, y = px + dx, py + dy
        return (x, y, float(height(np.array(x, float), np.array(y, float))) + lift)
    loops = [[(0, 0), (-4, -4), (-8, -8), (-11, -12), (-8, -16), (-2, -17), (4, -15), (8, -12)],
             [(0, 0), (5, -2), (10, -3), (14, -1), (16, 4)]]
    for path in loops:
        pts = [on_heap(*p) for p in path]
        for a, b in zip(pts, pts[1:]):
            m.line(a, b, "brope")
            m.line((a[0], a[1], a[2] - 1), (b[0], b[1], b[2] - 1), "brope2")
    # floats round the base
    for (dx, dy, c) in ((-7, -12, "float_w"), (-2, -14, "float_b"), (13, 1, "float_b"),
                        (14, 11, "float_w"), (7, 17, "float_b"), (5, 14, "float_w")):
        m.box(cx + dx - 2, cy + dy - 2, 0, 4, 4, 4, c)


# ---------------------------------------------------------------- baskets

def wicker(m: Model, region, z_band):
    """Basket weave on the wicker voxels in region: two-voxel checker of light / mid,
    a darker weaver every third row, blue band rows z_band=(z0, z1)."""
    ids = {c: m.pal.idx(c) for c in ("wick", "wick2", "wick3", "wband", "wband2")}

    def colour(X, Y, Z):
        u = (X + Y) // 2
        c = np.where((u + Z) % 2 == 0, ids["wick"], ids["wick2"])
        c = np.where(Z % 3 == 2, np.where(u % 2 == 0, ids["wick2"], ids["wick3"]), c)
        band = (Z >= z_band[0]) & (Z < z_band[1])
        c = np.where(band, np.where((u + Z) % 2 == 0, ids["wband"], ids["wband2"]), c)
        return c
    m.paint_fn(*region, colour)


def ear_handle(m: Model, cx, cy, d, r_mid, span, z0, rise, c="wick"):
    """Arched loop standing on a rim in the vertical plane through direction d (a radial
    ear): a half ellipse span/2 wide either side of radius r_mid, rise high, 2 thick."""
    perp = np.array([-d[1], d[0]])
    for t in np.linspace(0, np.pi, 40):
        r = r_mid + span / 2 * math.cos(t)
        z = z0 + rise * math.sin(t)
        for s in (-0.5, 0.5):
            p = np.array([cx, cy]) + d * r + perp * s
            for dz in (0, 1):
                m.set(int(round(p[0])), int(round(p[1])), int(round(z)) + dz, c)


def basket_round(m: Model, cx, cy):
    cen = m._centred
    R = int(RB_RT) + 2

    def r_at(Z):
        return RB_RB + (RB_RT - RB_RB) * Z / RB_H

    def rr(X, Y):
        X, Y = cen(X, Y)
        return np.hypot(X - cx, Y - cy)
    box = (cx - R, cy - R, 0, 2 * R + 1, 2 * R + 1, RB_H)
    m.where(*box, lambda X, Y, Z: (rr(X, Y) <= r_at(Z)) & ((rr(X, Y) > r_at(Z) - 1.6) | (Z < 1)), "wick")
    wicker(m, box, (3, 6))
    m.where(cx - R, cy - R, RB_H - 1, 2 * R + 1, 2 * R + 1, 1,
            lambda X, Y, Z: (rr(X, Y) <= RB_RT + 0.6) & (rr(X, Y) > RB_RT - 2.2), "wick")   # rim
    d = screen_right()
    for s in (-1, 1):
        ear_handle(m, cx, cy, s * d, RB_RT - 0.5, 6, RB_H - 2, 5)


def basket_rect(m: Model, cx, cy):
    W, D, H = REC_W, REC_D, REC_H
    x0, y0 = cx - W // 2, cy - D // 2

    def body(X, Y, Z):
        dx = np.minimum(X - x0, x0 + W - 1 - X)
        dy = np.minimum(Y - y0, y0 + D - 1 - Y)
        return (dx >= 0) & (dy >= 0) & (dx + dy >= 2)                 # chamfered corners
    m.where(x0, y0, 0, W, D, H, body, "wick")
    m.where(x0 + 1, y0 + 1, 1, W - 2, D - 2, H, lambda X, Y, Z: body(X, Y, Z) & (
        np.minimum(X - x0, x0 + W - 1 - X) >= 1) & (np.minimum(Y - y0, y0 + D - 1 - Y) >= 1) &
        (np.minimum(X - x0, x0 + W - 1 - X) + np.minimum(Y - y0, y0 + D - 1 - Y) >= 3), None)
    wicker(m, (x0, y0, 0, W, D, H), (3, 5))
    m.where(x0, y0, H - 1, W, D, 1, body, "wick", only_filled=True)   # rim course
    # end handles: arches over both end walls
    for hx in (x0, x0 + W - 2):
        m.box(hx, cy - 4, H, 2, 2, 5, "wick")
        m.box(hx, cy + 2, H, 2, 2, 5, "wick")
        m.box(hx, cy - 4, H + 4, 2, 8, 2, "wick")
    m.paint_fn(x0, y0, H, W, D, 7, lambda X, Y, Z: np.where((X + Y + Z) % 2 == 0, m.pal.idx("wick2"), 0))


# ---------------------------------------------------------------- build

def build() -> Model:
    centres, size = layout()
    m = Model(*size, seed=7, res=RES)
    palette(m)
    with m.part("stall"):
        x1, y1 = stall(m, *centres["stall"])
    with m.part("lantern"):                    # off the back-right post
        lantern(m, x1 + LANTERN_OUT, y1 - 2, LANTERN_Z, arm_from=x1)
    with m.part("crate_fish"):
        crate(m, *centres["crate_fish"], CRATE_FISH, "fish")
    with m.part("crate_salmon"):
        crate(m, *centres["crate_salmon"], CRATE_SALMON, "salmon")
    with m.part("barrel"):
        barrel(m, *centres["barrel"])
    with m.part("net"):
        net_heap(m, *centres["net"])
    with m.part("basket_round"):
        basket_round(m, *centres["basket_round"])
    with m.part("basket_rect"):
        basket_rect(m, *centres["basket_rect"])
    # shading and stains from the reference; the net's rope lattice keeps its own pattern
    # (its diamonds don't line up with the drawn ones, painting would scramble them)
    keep = {"net", "net2", "net3", "rope", "rope2", "brope", "brope2", "float_w", "float_b"}
    m.paint_reference(REFERENCE, VIEW, cutout=CUTOUT, only=[n for n in m.pal.names if n not in keep])
    return m
