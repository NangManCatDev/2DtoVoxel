"""Five tall voxel trees in stone tree pits — reference/411116c5-948a-4926-8c88-94d93fec422d.png

Kit sheet: five tall, narrow trees in a row, each standing in a square tree pit (a ring of beige
stone blocks around a recessed slate-green iron grate with bolted corner plates). Every tree, pit
included, is its own m.part(), so each one is a separate object in the .vox.

  1 column    dense spindle crown (cypress), the trunk spiralling through it
  2 tiered    pointed top over two broad tiers, trunk showing between them
  3 branched  straight trunk with round leaf clusters on visible side limbs
  4 cone      pointed top on a broad lumpy lower crown
  5 topiary   pointed top, then round clusters alternating left and right

Camera: orthographic az 45 / el 33.8 - measured on the pits (the top diamond of a pit is
sin(el) as high as it is wide: 152 / 273 px). A screen row of the sheet is a world diagonal,
so the trees stand along (+x, -y).

Scale: a pit edge is PIT = 25 units; the pits measured on the sheet (stone pixels) give the
pixels per unit (~7.8) and each tree's anchor (the screen point of its pit's top centre).

Trunks and crowns are read off the reference itself. Its pixels are split into leaf (green),
wood (brown) and pit; each tree's leaf and wood masks are covered greedily by disks (deepest
uncovered pixel first, radius = distance to the outline). Every disk becomes a ball whose
centre lies in the vertical plane through the tree's axis (facing the camera) - an
orthographic ball projects to exactly that disk, so the front view matches the sheet. Wood
balls that would sink below the grate (the root flare drawn in front of the trunk) slide along
the view ray onto the grate. The leaf balls are the crown's lobes: m.crown_depth() spreads
them through the crown's depth (copies straight behind / in front of each lobe at its own
height, as deep as the crown is wide there, as far as the outline allows), so every crown is
round seen from above and from the side, not only as deep as its single lobes.

Layout (x right, y depth with y=0 front, z up):
  pit     PIT x PIT, stone ring RING wide and STONE_H high in BLOCK-long blocks; grate one
          unit below the stone top: bars at a GRATE_PITCH pitch, corner plates with bolts,
          dark soil below
  wood    bark in vertical streaks (3 units tall)
  leaves  dark core, surface shaded per small clump (light on top, dark in the crevices
          between clumps), crevices sunk one voxel, loose 1-unit cubes on top
  paint   paint_reference() colours the leaves and bark the sheet shows (last); the grate
          and stone blocks keep their own pattern (painting them smeared it)

Outline: balls are filled GROW past their radius (no see-through gaps between them) and then
trimmed TRIM deep against the sheet's background only (not at leaf/wood borders); no leaf
stays in front of the wood the sheet shows. The score is very sensitive to the silhouette's
area here (narrow trees far from the centroid; before crown_depth: TRIM 0.5 -> 0.922, 0.55 ->
0.923, 0.65 -> 0.871). The build prints the area-alignment scale next to the measured one to
check this. Score: iou 0.924, dE 10.0 with lobes only as deep as themselves; with crown_depth
(round from every side, about twice the leaf voxels) iou 0.910, dE 10.1.
"""
import functools
import math
import os

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from voxtool import Model

NAME = "model_1029_2017"
REFERENCE = "reference/411116c5-948a-4926-8c88-94d93fec422d.png"
AZ, EL = 45, 33.8
VIEW = {"azimuth": AZ, "elevation": EL, "fov": 0}
CUTOUT = {"keep": "all"}
RES = 1
PAINT = True

TREE_NAMES = ["column", "tiered", "branched", "cone", "topiary"]

# pit
PIT, RING, STONE_H, BLOCK = 25, 3, 4, 5
GRATE_PITCH = 3
GROUND = STONE_H - 1         # top of the grate (roots rest on it)
MARGIN = 4

# reading the sheet
STOP_R = 0.45                # disk cover stops at disks smaller than this (units)
GROW = 0.6                   # balls are filled this much (voxels) past their radius, so no gaps open between
TRIM = 0.6                   # ...then a voxel stays only if its centre is this deep (units) inside the sheet's mask
THIN = 0.5                   # (or this share of the local half-width, where the shape is thinner)
WOOD_STOP = 0.2              # thin limbs seen through the crowns are only a few pixels wide
CLUMP = 2.6                  # leaf clump spacing (units)
P_DENT, P_TIP, P_SIDE = 0.05, 0.16, 0.06
P_CREVICE = (0.15, 0.7)      # surface voxels this close to a clump border (share of CLUMP) sink, with this chance

LEAVES = ["leaf1", "leaf2", "leaf3", "leaf4"]
BARK = ["bark0", "bark1", "bark2", "bark3"]
STONES = ["stone0", "stone1", "stone2"]

_A, _E = math.radians(AZ), math.radians(EL)
RIGHT = np.array([math.cos(_A), -math.sin(_A), 0.0])                                   # screen right
UP = np.array([math.sin(_E) * math.sin(_A), math.sin(_E) * math.cos(_A), math.cos(_E)])  # screen up
FWD = np.array([math.sin(_A) * math.cos(_E), math.cos(_A) * math.cos(_E), -math.sin(_E)])  # view direction


def palette(m: Model):
    p = m.pal
    p.add("leaf0", "#0b2109")
    p.add("leaf1", "#13431a"); p.add("leaf2", "#1b5822"); p.add("leaf3", "#276d2e"); p.add("leaf4", "#358239")
    p.add("leaf_tip", "#4a9a4b")
    p.add("bark0", "#3d230c"); p.add("bark1", "#55321a"); p.add("bark2", "#6e4422"); p.add("bark3", "#8a5a30")
    p.add("stone0", "#ece4d0"); p.add("stone1", "#e0d3ba"); p.add("stone2", "#d3c3a6"); p.add("seam", "#b9a98c")
    p.add("iron", "#3b5755"); p.add("iron_lt", "#4f6d6a"); p.add("bolt", "#a5bab6"); p.add("soil", "#0e110c")


def _hash01(*a):
    h = np.uint64(1469598103934665603)
    for k, x in enumerate(a):
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([73856093, 19349663, 83492791][k % 3]))
        h = (h * np.uint64(1099511628211)) % np.uint64(2 ** 32)
    return h.astype(np.float64) / 2 ** 32


# ---------------------------------------------------------------- reading the sheet

@functools.lru_cache(maxsize=1)
def reference():
    """(alpha, leaf, wood, stone) masks of the cut-out sheet (the same cutout the score uses)."""
    from voxtool.score import reference_cutout
    im = reference_cutout(REFERENCE, os.path.join(os.getcwd(), "output", "_ref"), **CUTOUT)
    a = np.asarray(im).astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    alpha = a[..., 3] > 127
    leaf = alpha & (G > R + 6) & (G > B + 8)
    wood = alpha & (R > G * 1.12) & (B < R * 0.62) & (R < 225)
    stone = alpha & (R >= 120) & (B >= R * 0.62) & (R > B + 12) & ~leaf
    return alpha, leaf, wood, stone


@functools.lru_cache(maxsize=1)
def sheet_layout():
    """Per tree: its column range on the sheet and the screen point (cu, cv) of its pit's top
    centre, from the pit's left and right stone corners; plus the pixels per unit."""
    alpha, _, _, stone = reference()
    cols = np.r_[False, alpha.sum(axis=0) > 2, False]
    edges = np.flatnonzero(cols[1:] != cols[:-1])
    runs = sorted(zip(edges[::2], edges[1::2]), key=lambda r: r[1] - r[0])[-len(TREE_NAMES):]
    trees, pxs = [], []
    for name, (x0, x1) in zip(TREE_NAMES, sorted(runs)):
        ys, xs = np.nonzero(stone[:, x0:x1])
        xl, xr = xs.min(), xs.max() + 1
        yl = ys[xs <= xl + 2].min()
        yr = ys[xs >= xr - 3].min()
        pxs.append((xr - xl) / (PIT * (abs(RIGHT[0]) + abs(RIGHT[1]))))
        trees.append(dict(name=name, x0=int(x0), x1=int(x1), cu=x0 + (xl + xr) / 2, cv=(yl + yr) / 2))
    return trees, float(np.median(pxs))


def pit_pixels(t, shape, px):
    """Pixels of the sheet crop (columns from t['x0']) inside the projection of the pit box."""
    H, W = shape
    a = ((np.arange(W) + t["x0"] + 0.5 - t["cu"]) / px)[None, :]
    s = (-(np.arange(H) + 0.5 - t["cv"]) / px)[:, None]
    half = PIT / 2 / math.sqrt(0.5) - np.abs(a) + 1.0 / px
    se, ce = math.sin(_E), math.cos(_E)
    return (s / se <= half) & ((s + STONE_H * ce) / se >= -half)


def tree_masks(t, px):
    """Leaf and wood masks of one tree (crop of the sheet from column t['x0']): stray object
    pixels (dark crevices, antialiasing) take the class of the nearest classified pixel."""
    alpha, leaf, wood, _ = reference()
    sl = np.s_[:, t["x0"]:t["x1"]]
    a = alpha[sl]
    pit = pit_pixels(t, a.shape, px)
    cls = np.zeros(a.shape, np.uint8)
    cls[leaf[sl] & ~pit] = 1
    cls[wood[sl]] = 2
    todo = a & (cls == 0) & ~pit
    if todo.any():
        iy, ix = ndimage.distance_transform_edt(cls == 0, return_distances=False, return_indices=True)
        cls[todo] = cls[iy, ix][todo]
    # brownish stone shadows on the pit are not wood: drop small brown specks lying on the pit
    lab, n = ndimage.label(cls == 2)
    if n:
        sizes = np.bincount(lab.ravel())[1:]
        on_pit = np.bincount(lab[pit], minlength=n + 1)[1:]
        drop = np.flatnonzero((on_pit > 0.5 * sizes) & (sizes < 2.5 * px * px)) + 1
        cls[np.isin(lab, drop)] = 0
    return cls == 1, cls == 2, a


def disk_cover(mask, stop):
    """Greedy cover of a mask by disks (x, y, r) in pixels: each disk sits on the uncovered pixel
    deepest inside the mask, radius = its distance to the outline; stops below `stop`."""
    edt = ndimage.distance_transform_edt(mask)
    ys, xs = np.nonzero(edt >= stop)
    order = np.argsort(-edt[ys, xs], kind="stable")
    covered = np.zeros(mask.shape, bool)
    H, W = mask.shape
    disks = []
    for y, x in zip(ys[order], xs[order]):
        if covered[y, x]:
            continue
        r = float(edt[y, x])
        k = int(math.ceil(r))
        y0, y1, x0, x1 = max(y - k, 0), min(y + k + 1, H), max(x - k, 0), min(x + k + 1, W)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        covered[y0:y1, x0:x1] |= (yy - y) ** 2 + (xx - x) ** 2 <= r * r
        disks.append((x + 0.5, y + 0.5, r))
    return disks


def balls(t, mask, px, stop=STOP_R):
    """Balls (centre relative to the pit's top centre, radius) in units for the disks covering
    a mask: centres in the vertical plane through the axis; any ball that would sink below
    the grate slides along the view ray (same screen spot) until it rests on it."""
    out = []
    for x, y, r in disk_cover(mask, max(stop * px, 1.0)):
        a = (x + t["x0"] - t["cu"]) / px
        s = -(y - t["cv"]) / px
        rad = max((r - 0.5) / px, 0.3)
        p = a * RIGHT + np.array([0.0, 0.0, s / math.cos(_E)])
        low = GROUND - STONE_H + 0.6 * rad - p[2]
        if low > 0:
            p = p - FWD * (low / math.sin(_E))
        out.append((p, rad))
    return out


# ---------------------------------------------------------------- voxel helpers

def fill_balls(m: Model, items, centre):
    """Bool grid of the voxels inside the balls (grown by GROW voxels, so neighbouring balls
    leave no see-through gaps; trim() then restores the outline)."""
    r_ = m.res
    out = np.zeros(m.v.shape, bool)
    shape = np.array(m.v.shape)
    for p, rad in items:
        c = (np.asarray(centre) + p) * r_
        rv = rad * r_
        lo = np.maximum(np.floor(c - rv - 1).astype(int), 0)
        hi = np.minimum(np.ceil(c + rv + 1).astype(int) + 1, shape)
        if (hi <= lo).any():
            continue
        ax = [np.arange(lo[k], hi[k]) + 0.5 - c[k] for k in range(3)]
        d2 = ax[0][:, None, None] ** 2 + ax[1][None, :, None] ** 2 + ax[2][None, None, :] ** 2
        lim = rv + GROW
        out[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] |= d2 <= lim * lim
    return out


def keep_map(edt, px, depth):
    """Pixels of a sheet mask where a voxel centre may land: at least `depth` units inside the
    outline, but only ~half as deep where the shape is thin (limbs, single leaf cubes)."""
    local = ndimage.maximum_filter(edt, size=int(2 * px) + 1)
    return edt >= np.maximum(np.minimum(depth * px, THIN * local), 1.0)


def on_mask(m: Model, t, idx, centre, px, keep):
    """For voxel indices idx [N, 3]: does the voxel's centre land on `keep` (crop from
    column t['x0'])?"""
    xy = np.floor(project_px(t, (idx + 0.5) / m.res, centre, px)).astype(int)
    xy[:, 0] -= t["x0"]
    ok = (xy[:, 0] >= 0) & (xy[:, 0] < keep.shape[1]) & (xy[:, 1] >= 0) & (xy[:, 1] < keep.shape[0])
    res = np.zeros(len(idx), bool)
    res[ok] = keep[xy[ok, 1], xy[ok, 0]]
    return res


def trim(m: Model, vox, t, centre, px, keep):
    """vox (bool grid) minus the voxels whose centre falls outside the sheet mask."""
    idx = np.argwhere(vox)
    vox[tuple(idx[~on_mask(m, t, idx, centre, px, keep)].T)] = False
    return vox


def _bbox(mask, pad=1):
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - pad, 0)
    hi = np.minimum(idx.max(0) + pad + 1, mask.shape)
    return tuple(slice(a, b) for a, b in zip(lo, hi))


def _exposed(occ):
    """Filled voxels with at least one empty neighbour."""
    p = np.pad(occ, 1)
    out = np.zeros(occ.shape, bool)
    for ax in range(3):
        for d in (-1, 1):
            out |= ~np.roll(p, d, axis=ax)[1:-1, 1:-1, 1:-1]
    return out & occ


def project_px(t, pts, centre, px):
    """Sheet pixel (x, y) of world points (units) for the tree anchored at `centre`."""
    q = pts - np.asarray(centre)
    return np.stack([t["cu"] + px * (q @ RIGHT), t["cv"] - px * (q @ UP)], -1)


# ---------------------------------------------------------------- pieces

def pit(m: Model, X0, Y0):
    """Stone tree pit with its low corner at (X0, Y0)."""
    P, Rg, H = PIT, RING, STONE_H
    m.box(X0, Y0, 0, P, P, H, "stone0")
    m.carve(X0 + Rg, Y0 + Rg, 0, P - 2 * Rg, P - 2 * Rg, H)
    ids = np.array([m.pal.idx(c) for c in STONES], np.uint8)
    seam = m.pal.idx("seam")

    def stones(X, Y, Z):
        lx, ly = np.floor(X - X0).astype(int), np.floor(Y - Y0).astype(int)
        row = (ly < Rg) | (ly >= P - Rg)                       # front / back rows run along x
        along = np.where(row, lx, ly)
        side = np.where(row, ly >= P - Rg, lx >= P - Rg)
        blk = along // BLOCK
        c = ids[(_hash01(blk, side, row) * len(ids)).astype(int)]
        return np.where(along % BLOCK == BLOCK - 1, seam, c)
    m.paint_fn(X0, Y0, 0, P, P, H, stones)

    n = P - 2 * Rg
    gx, gy, gz = X0 + Rg, Y0 + Rg, GROUND - 1
    m.box(gx, gy, 0, n, n, gz, "soil")
    m.where(gx, gy, gz, n, n, 1, lambda X, Y, Z: (np.floor(X - gx) % GRATE_PITCH == 0)
            | (np.floor(Y - gy) % GRATE_PITCH == 0) | (np.floor(X - gx) == n - 1) | (np.floor(Y - gy) == n - 1), "iron")
    for cx, cy in ((gx, gy), (gx + n - 3, gy), (gx, gy + n - 3), (gx + n - 3, gy + n - 3)):
        m.box(cx, cy, gz, 3, 3, 1, "iron_lt")
        m.box(cx + 1, cy + 1, gz + 1, 1, 1, 1, "bolt")


def wood(m: Model, t, centre, px):
    W = trim(m, fill_balls(m, t["wood"], centre) & (m.v == 0), t, centre, px, t["keep_wood"])
    sl = _bbox(W)
    sub = W[sl]
    X, Y, Z = np.meshgrid(*[np.arange(s.start, s.stop) for s in sl], indexing="ij")
    ids = np.array([m.pal.idx(c) for c in BARK], np.uint8)
    pick = _hash01(X, Y, Z // (3 * m.res))
    col = ids[np.searchsorted(np.cumsum([0.4, 0.3, 0.18, 0.12]), pick, side="right").clip(0, 3)]
    m.v[sl][sub] = col[sub]


def crown(m: Model, t, centre):
    """The leaf balls (lobes in the axis plane) spread through the crown's depth by crown_depth(),
    as balls relative to `centre` again."""
    c = np.asarray(centre, float)
    lobes = [(*(c + p), r) for p, r in t["leaf"]]
    return [(np.array(lb[:3]) - c, lb[3]) for lb in m.crown_depth(lobes, c[0], c[1], VIEW)]


def leaves(m: Model, t, centre, px):
    """Leaf voxels from the crown's lobes; shading per clump; loose cubes and dents inside the outline."""
    L = trim(m, fill_balls(m, crown(m, t, centre), centre) & (m.v == 0), t, centre, px, t["keep_leaf"])
    sl = _bbox(L, pad=2)
    v = m.v[sl]
    sub = L[sl]
    v[sub] = m.pal.idx("leaf2")
    exp = _exposed(v > 0) & sub
    pts = np.argwhere(sub) + 0.5                               # local voxel coords
    s = CLUMP * m.res
    g = [np.arange(-s, n + s, s) for n in sub.shape]
    lat = np.stack(np.meshgrid(*g, indexing="ij"), -1).reshape(-1, 3)
    lat = lat + m.rng.uniform(-0.35, 0.35, lat.shape) * s
    d, i = cKDTree(lat).query(pts, k=2)
    top = (pts[:, 2] - lat[i[:, 0], 2]) / s
    edge = (d[:, 1] - d[:, 0]) / s
    h = (pts[:, 2] - pts[:, 2].min()) / max(np.ptp(pts[:, 2]), 1)
    tt = 0.9 * top + 0.5 * (h - 0.5) + 0.25 * (m.rng.random(len(pts)) - 0.5)
    ids = np.array([m.pal.idx(c) for c in LEAVES], np.uint8)
    col = ids[np.digitize(tt, [-0.35, 0.0, 0.35])]
    col = np.where(edge < 0.12, m.pal.idx("leaf1"), col)
    e = exp[tuple(pts.astype(int).T)]
    col = np.where(e, col, m.pal.idx("leaf0"))
    v[tuple(pts.astype(int).T)] = col

    # loose cubes (only where the sheet shows leaves) and dents
    leaf_ids = np.array([m.pal.idx(c) for c in ["leaf1"] + LEAVES], np.uint8)
    org = np.array([s_.start for s_ in sl])

    def on_sheet(local):
        return on_mask(m, t, local + org, centre, px, t["keep_leaf"])

    surf = np.argwhere(exp & np.isin(v, leaf_ids))
    lighter = {m.pal.idx("leaf1"): "leaf2", m.pal.idx("leaf2"): "leaf3", m.pal.idx("leaf3"): "leaf4",
               m.pal.idx("leaf4"): "leaf_tip"}
    gap = np.full(v.shape, np.inf)                             # crevices between clumps sink in
    gap[tuple(pts.astype(int).T)] = edge
    roll = m.rng.random(len(surf))
    dent = surf[(roll < P_DENT) | ((gap[tuple(surf.T)] < P_CREVICE[0]) & (roll < P_CREVICE[1]))]
    filled = np.pad(v > 0, 1)
    behind = np.ones(len(dent), bool)        # only where the voxels behind it (seen from VIEW) keep the outline
    for d in ((1, 0, 0), (0, 1, 0), (0, 0, -1)):
        behind &= filled[tuple((dent + 1 + np.array(d)).T)]
    dent = dent[behind]
    for dirn, prob in (((0, 0, 1), P_TIP), ((1, 0, 0), P_SIDE), ((-1, 0, 0), P_SIDE), ((0, 1, 0), P_SIDE),
                       ((0, -1, 0), P_SIDE)):
        src = surf[m.rng.random(len(surf)) < prob]
        dst = src + np.array(dirn)
        ok = ((dst >= 0) & (dst < np.array(v.shape))).all(1)
        src, dst = src[ok], dst[ok]
        ok = (v[tuple(dst.T)] == 0) & on_sheet(dst)
        src, dst = src[ok], dst[ok]
        c = v[tuple(src.T)]
        if dirn[2] == 1:
            c = np.array([m.pal.idx(lighter.get(int(k), "leaf_tip")) for k in c], np.uint8)
        v[tuple(dst.T)] = c
    v[tuple(dent.T)] = 0


def tree(m: Model, t, X0, Y0, px):
    centre = (X0 + PIT / 2, Y0 + PIT / 2, STONE_H)
    pit(m, X0, Y0)
    wood(m, t, centre, px)
    leaves(m, t, centre, px)


# ---------------------------------------------------------------- build

def build() -> Model:
    trees, px = sheet_layout()
    c, se = math.sqrt(0.5), math.sin(_E)
    t0 = trees[0]
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for t in trees:
        leaf_px, wood_px, obj_px = tree_masks(t, px)
        # trimmed against the background only; where the sheet shows wood, no leaf in front of it
        outline = keep_map(ndimage.distance_transform_edt(obj_px), px, TRIM)
        t["keep_wood"] = outline
        t["keep_leaf"] = outline & ~wood_px     # (crown_depth's front copies would hide the trunk)
        t["leaf"] = balls(t, leaf_px, px)
        t["wood"] = balls(t, wood_px, px, WOOD_STOP)
        # ground offset of this pit from the first one: screen (du, dv) -> world (dx, dy)
        du, dv = (t["cu"] - t0["cu"]) / px, (t["cv"] - t0["cv"]) / px
        dx_m_dy, dx_p_dy = du / c, -dv / (se * c)
        t["g"] = np.array([(dx_m_dy + dx_p_dy) / 2, (dx_p_dy - dx_m_dy) / 2, 0.0])
        depth = np.array([math.sin(_A), math.cos(_A), 0.0])    # crown_depth() copies lobes along this
        half = max(abs(p @ RIGHT) + r for p, r in t["leaf"])   # ... at most as far as the crown is wide
        ext = [(p + s * half * depth, r) for p, r in t["leaf"] for s in (-1, 0, 1)] + t["wood"] \
            + [(np.array([sx, sy, -STONE_H]) * PIT / 2, 0.0) for sx in (-1, 1) for sy in (-1, 1)]
        for p, r in ext:
            lo = np.minimum(lo, t["g"] + p - r)
            hi = np.maximum(hi, t["g"] + p + r)
    shift = MARGIN - lo[:2]
    W, D = (int(math.ceil(v)) for v in hi[:2] - lo[:2] + 2 * MARGIN)
    H = int(math.ceil(hi[2] + STONE_H + MARGIN))
    print(f"sheet: {px:.2f} px/unit, anchors " + ", ".join(f"({t['cu']:.0f},{t['cv']:.0f})" for t in trees)
          + ", balls " + ", ".join(f"{len(t['leaf'])}+{len(t['wood'])}" for t in trees))

    m = Model(W, D, H, seed=7, res=RES)
    palette(m)
    for i, t in enumerate(trees):
        cx, cy = t["g"][:2] + shift
        X0, Y0 = int(round(cx - PIT / 2)), int(round(cy - PIT / 2))
        with m.part(f"tree{i + 1}_{t['name']}"):
            tree(m, t, X0, Y0, px)
    from voxtool.score import reference_transform
    ppv = reference_transform(m.v, m.pal.rgba, set(), REFERENCE, VIEW, cutout_kw=CUTOUT,
                              cache_dir=os.path.join(os.getcwd(), "output", "_ref"))[3] / m.res
    print(f"silhouette area -> {ppv:.3f} px/unit (sheet {px:.3f}; higher = model too small)")
    if PAINT:       # leaves and bark only: the grate and stone blocks keep their clean pattern
        m.paint_reference(REFERENCE, VIEW, cutout=CUTOUT, only=["leaf0", "leaf1", "leaf_tip"] + LEAVES + BARK)
    return m
