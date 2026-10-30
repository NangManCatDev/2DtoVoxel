"""Paving-stone slab — reference/a3eb63d7-6160-47f0-979b-8f1464fb6e4d.png

Layout (x right, y depth with y=0 front, z up):
  slab       W x D footprint, H tall, viewed from the front-right corner
  base       z 0..BASE-1, continuous under everything (bottom of the grooves)
  stones     81 rectangles in 3 colours (slate blue, lilac grey, warm beige), separated
             by 1-voxel grooves that run down to the base. Each stone column is
             top layer (stone colour) / body band (darker side colour) / bed (dark),
             matching the light upper band and dark lower band on the reference's sides.
  layout     TILES was read from a top-down unwarp of the reference (rectify()/segment(),
             switch RECTIFY on to regenerate output/_scratch/<NAME>_top.png and _tiles.png).
             Stones are drawn largest first; each stone cuts a 1-voxel groove into the
             stones it touches, so the reference's L-shaped stones come out naturally.
"""
from pathlib import Path

import numpy as np

from voxtool import Model

NAME = "a3eb63d7_6160_47f0_979b_8f1464fb6e4d"
REFERENCE = "reference/a3eb63d7-6160-47f0-979b-8f1464fb6e4d.png"
VIEW = {"azimuth": 321, "elevation": 36, "fov": 0}

W, D = 128, 107     # slab footprint
H = 11              # total height
BASE = 2            # continuous base under the grooves
BAND = 5            # upper light band of each stone (top layer + body)

# (x, y, w, d, colour) of each stone top
TILES = [
    # front row
    (0, 0, 11, 13, "lilac"),
    (12, 0, 7, 12, "beige"),
    (20, 0, 8, 11, "beige"),
    (29, 0, 10, 11, "blue"),
    (40, 0, 5, 10, "beige"),
    (46, 0, 12, 12, "beige"),
    (59, 0, 7, 12, "beige"),
    (67, 0, 28, 24, "blue"),
    (97, 0, 13, 9, "beige"),
    (111, 0, 17, 9, "lilac"),
    (97, 10, 6, 7, "lilac"),
    (104, 10, 8, 7, "beige"),
    (114, 10, 14, 6, "blue"),
    (19, 12, 26, 20, "blue"),
    (46, 13, 5, 7, "beige"),
    (52, 13, 5, 7, "lilac"),
    (58, 13, 8, 11, "beige"),
    (0, 14, 8, 11, "blue"),
    (9, 14, 9, 19, "beige"),
    (112, 17, 8, 7, "beige"),
    (121, 17, 7, 7, "beige"),
    (97, 18, 14, 6, "blue"),
    (46, 21, 10, 11, "beige"),
    # second band
    (58, 25, 14, 18, "lilac"),
    (73, 25, 18, 18, "lilac"),
    (92, 25, 5, 9, "beige"),
    (98, 25, 27, 17, "lilac"),      # L-shaped: (121, 25) and (126, 36) cut into it
    (121, 25, 7, 10, "lilac"),
    (0, 26, 7, 14, "beige"),
    (28, 33, 21, 20, "beige"),      # L-shaped: (46, 33) cuts its top-right corner
    (46, 33, 11, 10, "beige"),
    (8, 34, 19, 17, "blue"),        # L-shaped: (0, 47) cuts its bottom-left corner
    (92, 35, 5, 8, "beige"),
    (126, 36, 2, 6, "beige"),
    (0, 41, 7, 5, "beige"),
    (98, 43, 8, 7, "beige"),
    (107, 43, 5, 7, "blue"),
    (113, 43, 15, 20, "blue"),
    (50, 44, 11, 22, "beige"),
    (62, 44, 15, 16, "lilac"),
    (78, 44, 18, 13, "lilac"),
    (0, 47, 11, 19, "blue"),
    (97, 51, 6, 12, "lilac"),
    (104, 51, 8, 7, "beige"),
    (12, 52, 15, 14, "beige"),
    (39, 54, 10, 12, "beige"),
    (28, 55, 10, 11, "blue"),
    (78, 58, 18, 8, "blue"),
    (104, 59, 8, 4, "lilac"),
    (62, 61, 15, 12, "blue"),
    # back half
    (97, 64, 11, 10, "beige"),
    (109, 64, 19, 25, "lilac"),     # L-shaped: (108, 85) cuts its bottom-left corner
    (0, 67, 17, 16, "blue"),
    (18, 67, 9, 14, "lilac"),
    (28, 67, 27, 24, "lilac"),      # L-shaped: (18, 82) cuts its bottom-left corner
    (56, 67, 5, 6, "beige"),
    (78, 67, 18, 15, "lilac"),
    (56, 74, 7, 8, "lilac"),
    (64, 74, 13, 8, "beige"),
    (97, 75, 10, 11, "lilac"),
    (18, 82, 13, 9, "beige"),
    (56, 83, 15, 13, "lilac"),
    (72, 83, 5, 9, "lilac"),
    (78, 83, 16, 9, "blue"),
    (0, 84, 7, 7, "beige"),
    (8, 84, 9, 7, "lilac"),
    (108, 85, 11, 14, "blue"),
    (95, 87, 12, 9, "lilac"),
    (120, 90, 8, 9, "lilac"),
    (0, 92, 20, 15, "blue"),
    (21, 92, 7, 7, "lilac"),
    (29, 92, 18, 15, "lilac"),
    (48, 92, 7, 4, "blue"),
    (73, 93, 20, 14, "lilac"),
    (48, 97, 16, 10, "blue"),
    (65, 97, 7, 2, "beige"),
    (95, 97, 12, 10, "beige"),
    (21, 100, 7, 7, "beige"),
    (65, 100, 7, 7, "beige"),
    (108, 100, 10, 7, "lilac"),
    (120, 100, 8, 7, "lilac"),
]

# top-surface corners in the reference (pixels): x=0/y=0 left, x=W/y=0 front,
# x=W/y=D right, x=0/y=D back
REF_CORNERS = {(0, 0): (31, 479), (1, 0): (892, 939), (1, 1): (1505, 486), (0, 1): (637, 64)}
RECTIFY = False     # True: write the top-down unwarp + detected stones to output/_scratch/
RECT_PX = 10        # pixels per voxel in the unwarped image


# ---------------------------------------------------------------- reference study helpers

def homography(pairs):
    """3x3 matrix mapping (u, v) -> (px, py) for four point pairs."""
    A, b = [], []
    for (u, v), (x, y) in pairs.items():
        A.append([u, v, 1, 0, 0, 0, -u * x, -v * x]); b.append(x)
        A.append([0, 0, 0, u, v, 1, -u * y, -v * y]); b.append(y)
    h = np.linalg.solve(np.array(A, float), np.array(b, float))
    return np.append(h, 1).reshape(3, 3)


def rectify():
    """Unwarps the reference's top surface: column = x * RECT_PX, row = y * RECT_PX
    (front edge on top), then runs segment() on it."""
    from PIL import Image
    img = np.asarray(Image.open(REFERENCE).convert("RGB"))
    Hm = homography(REF_CORNERS)
    cols, rows = W * RECT_PX, D * RECT_PX
    u, v = np.meshgrid((np.arange(cols) + 0.5) / cols, (np.arange(rows) + 0.5) / rows)
    p = Hm @ np.stack([u.ravel(), v.ravel(), np.ones(u.size)])
    px = np.clip(np.round(p[0] / p[2]).astype(int), 0, img.shape[1] - 1)
    py = np.clip(np.round(p[1] / p[2]).astype(int), 0, img.shape[0] - 1)
    out = img[py, px].reshape(rows, cols, 3)
    path = Path("output/_scratch") / f"{NAME}_top.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(path)
    print("rectified ->", path)
    segment(out)


def segment(top, thresh=135, gap_px=4):
    """Finds the stone tops in the unwarped image (bright regions between dark grooves)
    and prints them as voxel rectangles (x, y, w, d, colour). Overlay -> _scratch."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    lum = top.astype(float).mean(-1)
    mask = ndimage.binary_erosion(lum > thresh, iterations=2)
    lab, n = ndimage.label(mask)
    R = RECT_PX
    tiles = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        if (xs.stop - xs.start) < 2 * R or (ys.stop - ys.start) < 2 * R:
            continue
        x0px, x1px = xs.start - 2, xs.stop + 2
        y0px, y1px = ys.start - 2, ys.stop + 2
        x0 = 0 if x0px < 15 else int((x0px - gap_px) // R) + 1
        y0 = 0 if y0px < 15 else int((y0px - gap_px) // R) + 1
        x1 = W if x1px > W * R - 15 else int((x1px + gap_px) // R)
        y1 = D if y1px > D * R - 15 else int((y1px + gap_px) // R)
        rgb = np.median(top[sl][lab[sl] == i], axis=0)
        r, g, b = rgb
        cls = "blue" if rgb.mean() < 165 else ("beige" if r > b else "lilac")
        tiles.append((x0, y0, x1 - x0, y1 - y0, cls, tuple(int(c) for c in rgb)))
    tiles.sort(key=lambda t: (t[1], t[0]))
    print(f"TILES ({len(tiles)}):")
    for t in tiles:
        print(f"    ({t[0]}, {t[1]}, {t[2]}, {t[3]}, \"{t[4]}\"),  # {t[5]}")
    ov = Image.fromarray(top).convert("RGB")
    dr = ImageDraw.Draw(ov)
    col = {"blue": (0, 0, 255), "lilac": (255, 0, 255), "beige": (255, 140, 0)}
    for x, y, w, d, c, _ in tiles:
        dr.rectangle([x * R, y * R, (x + w) * R - 1, (y + d) * R - 1], outline=col[c], width=3)
    ov.save(Path("output/_scratch") / f"{NAME}_tiles.png")
    check_tiles([t[:5] for t in tiles])


def check_tiles(tiles, overlaps=True):
    """Prints stone pairs that touch along an edge without a groove (one of them loses
    a row) and, if overlaps, pairs that overlap (intended for L-shaped stones)."""
    for i, (x, y, w, d, _) in enumerate(tiles):
        for j in range(i + 1, len(tiles)):
            X, Y, Wj, Dj, _ = tiles[j]
            ox = min(x + w, X + Wj) - max(x, X)
            oy = min(y + d, Y + Dj) - max(y, Y)
            touch = (ox == 0 and oy > 0) or (oy == 0 and ox > 0)
            if touch or (overlaps and ox > 0 and oy > 0):
                print(f"  {'touch' if touch else 'overlap'}: {tiles[i][:4]} {tiles[j][:4]}")


# ---------------------------------------------------------------- model

def palette(m: Model):
    # tops = reference top samples; sides = reference front-side samples / 0.9
    p = m.pal
    p.add("blue", "#9694aa"); p.add("blue_side", "#7b7992")
    p.add("lilac", "#b9b1c0"); p.add("lilac_side", "#978ea7")
    p.add("beige", "#c2b6ba"); p.add("beige_side", "#9e92a0")
    p.add("bed", "#665e70")
    p.add("base", "#4f4858")


def stone_map() -> np.ndarray:
    """(W, D) map of 1-based TILES index per column, 0 = groove."""
    lab = np.zeros((W, D), int)
    order = sorted(range(len(TILES)), key=lambda i: -TILES[i][2] * TILES[i][3])
    for i in order:
        x, y, w, d, _ = TILES[i]
        # groove along the four edges (not the diagonal corners, so stones that only
        # meet corner-to-corner keep their corners)
        lab[max(x - 1, 0):x + w + 1, y:y + d] = 0
        lab[x:x + w, max(y - 1, 0):y + d + 1] = 0
        lab[x:x + w, y:y + d] = i + 1
    return lab


def build() -> Model:
    if RECTIFY:
        rectify()
    check_tiles(TILES, overlaps=False)
    m = Model(W, D, H)
    palette(m)
    m.box(0, 0, 0, W, D, BASE, "base")
    lab = stone_map()
    for i, (_, _, _, _, c) in enumerate(TILES, 1):
        xs, ys = np.nonzero(lab == i)
        if xs.size == 0:
            print("  stone fully covered:", TILES[i - 1])
            continue
        m.v[xs, ys, BASE:H - BAND] = m.pal.idx("bed")
        m.v[xs, ys, H - BAND:H - 1] = m.pal.idx(f"{c}_side")
        m.v[xs, ys, H - 1] = m.pal.idx(c)
    return m
