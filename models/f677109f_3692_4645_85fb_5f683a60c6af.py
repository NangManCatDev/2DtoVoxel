"""Six hanging moss clumps — reference/f677109f-3692-4645-85fb-5f683a60c6af.png

Kit sheet (3 x 2): six floating clumps of moss built from loose cubes, yellow-green
("light") and dark teal-green ("dark"). Each clump is a flat canopy of jumbled cubes
with strands of single cubes hanging from its front edge. Every clump is drawn inside
its own m.part(), so each one is a separate object in the .vox.

Camera: orthographic az AZ / el EL, read off the cube top faces (each top is a rhombus
whose two edges give the azimuth from their widths and the elevation from their slopes).

Layout: the sheet is read through that camera. A clump's cubes sit on a CUBE-voxel
lattice (jittered), and a cube is kept where its projection falls inside the reference
cutout, so the front view matches the sheet by construction. The depth the single view
cannot show comes from a simple structure per clump:
  canopy  horizontal slab, TC cubes thick, everything behind the clump's front edge
  strands vertical columns of cubes hanging from the front edge, one cube deep
The front edge is a polyline read off the sheet (where the canopy ends and the strands
begin, reference pixels); its depth is DEPTH[row], the top row behind the bottom row
(like a shelf seen from above), so the clumps never overlap in the grid.
The colour of every cube (light / dark) is read from the reference at its projection.
"""
import math

import numpy as np
from PIL import Image

from voxtool import Model
from voxtool.reftools import cutout

NAME = "f677109f_3692_4645_85fb_5f683a60c6af"
REFERENCE = "reference/f677109f-3692-4645-85fb-5f683a60c6af.png"
AZ, EL = 37, 22
VIEW = {"azimuth": AZ, "elevation": EL}
CUTOUT = {"keep": "all"}
RES = 1

PX = 9.0           # reference pixels per voxel (a cube is ~36 px across)
CUBE = 4           # cube edge (voxels)
TC = 2             # canopy thickness (cube layers)
KEEP = 0.92        # share of a cube's projection that must lie inside the cutout
KEEP_STRAND = 0.85 # the same for strand cubes (CUBE, then CUBE - 1 to fill thin bits)
OVERLAP = 16       # voxels a new cube may share with cubes already placed (of 64)
TOP_POKE = 2     # how far canopy cubes may rise above the TC layers
DEPTH = {0: 44.0, 1: 0.0}    # depth of the front edge per sheet row (voxels, along the view)
MARGIN = 2
RG_SPLIT = 0.72    # red/green ratio above which a cube reads as yellow-green (else teal)

# box = reference pixel box of the clump; edge = front edge of the canopy (left -> right)
PIECES = [
    dict(name="moss1", row=0, box=(55, 45, 530, 450), edge=[(55, 225), (300, 255), (530, 245)]),
    dict(name="moss2", row=0, box=(580, 55, 910, 480), edge=[(580, 230), (745, 260), (910, 250)]),
    dict(name="moss3", row=0, box=(960, 80, 1485, 430), edge=[(960, 215), (1220, 235), (1485, 225)]),
    dict(name="moss4", row=1, box=(90, 480, 505, 940), edge=[(90, 620), (300, 690), (505, 700)]),
    dict(name="moss5", row=1, box=(560, 510, 950, 905), edge=[(560, 660), (750, 690), (950, 640)]),
    dict(name="moss6", row=1, box=(1045, 495, 1480, 990), edge=[(1045, 640), (1260, 690), (1480, 640)]),
]

# cube colours in two families (base = top face; the preview shades the front x0.9 and the
# left side x0.76, FACE_SHADE). The hue of the reference picks the family, the brightness
# of its faces the shade within it (the top face counts double). Fitting the shade over
# all eight colours instead lowers ΔE a little but turns most cubes a muddy olive and
# loses the yellow-green / teal contrast that defines the sheet.
FAMILIES = {
    "yellow": {"light": "#a2b35b", "light_mid": "#8d9f4b", "olive": "#73863c"},
    "teal": {"teal_lt": "#4a7048", "teal": "#355a3a", "teal_dk": "#264632"},
}
COLOURS = {k: v for fam in FAMILIES.values() for k, v in fam.items()}
FACE_SHADE = (1.0, 0.9, 0.76)
FACE_WEIGHT = (2.0, 1.0, 1.0)


def palette(m: Model):
    for name, hex_ in COLOURS.items():
        m.pal.add(name, hex_)


# ---------------------------------------------------------------- camera
_A, _E = math.radians(AZ), math.radians(EL)
cA, sA, cE, sE = math.cos(_A), math.sin(_A), math.cos(_E), math.sin(_E)


def to_screen(p):
    """World points [..., 3] -> (u right, v down) in voxel units (render.Camera without its centre)."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    return x * cA - y * sA, -(x * sE * sA + y * sE * cA + z * cE)


def from_screen(u, h):
    """Screen u plus depth h (along the view, horizontal) -> world (x, y)."""
    return u * cA + h * sA, -u * sA + h * cA


def depth_of(x, y):
    return x * sA + y * cA


# ---------------------------------------------------------------- reading the sheet

_GRID = np.stack(np.meshgrid(*[np.arange(5) / 4] * 3, indexing="ij"), -1).reshape(-1, 3)


class Sheet:
    def __init__(self):
        self.mask = np.asarray(cutout(REFERENCE, keep="all"))[..., 3] > 127
        self.rgb = np.asarray(Image.open(REFERENCE).convert("RGB")).astype(np.float32)
        self.H, self.W = self.mask.shape

    def px(self, p):
        u, v = to_screen(p)
        return u * PX, v * PX

    def coverage(self, P, s, box):
        """For cubes of size s at low corners P [N, 3]: share of their projection (5x5x5
        sample points, corners included) inside the cutout and the clump's box."""
        pts = P[:, None, :] + _GRID[None] * s
        x, y = self.px(pts)
        xi, yi = np.round(x).astype(int), np.round(y).astype(int)
        ok = (xi >= box[0]) & (xi < box[2]) & (yi >= box[1]) & (yi < box[3])
        hit = np.zeros(xi.shape, bool)
        hit[ok] = self.mask[yi[ok], xi[ok]]
        return hit.mean(axis=1)

    def samples(self, p):
        """Reference colour (3x3 px mean) at the projections of points p [N, 3], and
        whether each lands inside the cutout."""
        x, y = self.px(p)
        xi = np.clip(np.round(x).astype(int), 1, self.W - 2)
        yi = np.clip(np.round(y).astype(int), 1, self.H - 2)
        patch = np.stack([self.rgb[yi + dy, xi + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        return patch.mean(axis=0), self.mask[yi, xi]


def face_points(x, y, z, s):
    """Centres of the three faces the camera sees (top, front, left)."""
    return np.array([(x + s / 2, y + s / 2, z + s), (x + s / 2, y, z + s / 2), (x, y + s / 2, z + s / 2)], float)


# ---------------------------------------------------------------- one clump

def edge_v(piece, u):
    """Screen v (voxel units) of the clump's front edge at screen u."""
    xs = [a / PX for a, _ in piece["edge"]]
    vs = [b / PX for _, b in piece["edge"]]
    return float(np.interp(u, xs, vs))


def clump(sheet: Sheet, piece: dict, rng) -> list:
    """Cubes (x, y, z, size, kind) in continuous world coordinates."""
    box = piece["box"]
    u0, u1 = box[0] / PX, box[2] / PX
    v_top, v_bot = box[1] / PX, box[3] / PX
    h0 = DEPTH[piece["row"]]
    um = (u0 + u1) / 2
    zb = (-edge_v(piece, um) - h0 * sE) / cE          # bottom of the canopy

    def h_edge(u):
        return (-edge_v(piece, u) - zb * cE) / sE

    # canopy candidates: every integer position in the slab behind the front edge
    h_lo = min(h_edge(u) for u in np.linspace(u0, u1, 20))
    h_hi = (-v_top - zb * cE) / sE + 2
    corners = [from_screen(u, h) for u in (u0, u1) for h in (h_lo, h_hi)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    X, Y, Z = np.meshgrid(np.arange(math.floor(min(xs)) - CUBE, math.ceil(max(xs)) + 1),
                          np.arange(math.floor(min(ys)) - CUBE, math.ceil(max(ys)) + 1),
                          np.arange(TC * CUBE + TOP_POKE + 1) + math.floor(zb), indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], -1).astype(float)
    cu = (P[:, 0] + CUBE / 2) * cA - (P[:, 1] + CUBE / 2) * sA
    ch = depth_of(P[:, 0] + CUBE / 2, P[:, 1] + CUBE / 2)
    he = (-np.interp(cu, [a / PX for a, _ in piece["edge"]], [b / PX for _, b in piece["edge"]])
          - zb * cE) / sE
    P = P[(cu >= u0) & (cu <= u1) & (ch >= he + CUBE * 0.5)]
    canopy = P

    # strand candidates: a curtain one cube deep hanging from the front edge
    rows = []
    for u in np.arange(u0, u1, 1.0):
        h = h_edge(u) + CUBE * 0.5
        x, y = from_screen(u, h)
        z_min = (-v_bot - h * sE) / cE - CUBE
        for z in np.arange(math.floor(zb) - CUBE, z_min, -1.0):
            rows.append((x - CUBE / 2, y - CUBE / 2, z))
    strands = np.array(rows, float)

    # pack: best-covered candidates first, each cube may overlap the others only a little
    lo = np.floor(np.vstack([canopy, strands]).min(axis=0)) - 1
    hi = np.ceil(np.vstack([canopy, strands]).max(axis=0)) + CUBE + 2
    occ = np.zeros((hi - lo).astype(int), bool)
    cubes = []
    small = strands + (CUBE - (CUBE - 1)) / 2
    for P, s, need in ((canopy, CUBE, KEEP), (strands, CUBE, KEEP_STRAND), (small, CUBE - 1, KEEP_STRAND)):
        cov = sheet.coverage(P, s, box)
        sel = cov >= need
        P, cov = P[sel], cov[sel]
        order = np.argsort(-(cov + rng.uniform(0, 0.04, len(cov))))
        limit = OVERLAP * s ** 3 // CUBE ** 3
        for x, y, z in P[order]:
            i, j, k = (np.round(np.array([x, y, z]) - lo)).astype(int)
            block = occ[i:i + s, j:j + s, k:k + s]
            if block.sum() > limit:
                continue
            block[...] = True
            cubes.append([x, y, z, s])

    # colour per cube: family from the hue (red/green), then the shade whose preview look
    # (top / front / left face) comes closest to what the reference shows on those faces
    fams = {}
    for fam, cols in FAMILIES.items():
        names = list(cols)
        base = np.array([[int(cols[n][i:i + 2], 16) for i in (1, 3, 5)] for n in names], float)
        fams[fam] = (names, base[:, None, :] * np.array(FACE_SHADE)[None, :, None])
    out = []
    for x, y, z, s in cubes:
        ref, ok = sheet.samples(face_points(x, y, z, s))
        if not ok.any():
            ok[:] = True
        r, g, _ = ref[ok].mean(axis=0)
        names, shaded = fams["yellow" if r / max(g, 1.0) > RG_SPLIT else "teal"]
        w = ok * np.array(FACE_WEIGHT)
        err = (((shaded - ref[None]) ** 2).sum(-1) * w[None]).sum(-1)
        out.append((x, y, z, s, names[int(np.argmin(err))]))
    return out


# ---------------------------------------------------------------- build

def build() -> Model:
    rng = np.random.default_rng(11)
    sheet = Sheet()
    pieces = [(p, clump(sheet, p, rng)) for p in PIECES]
    allc = np.array([c[:3] for _, cs in pieces for c in cs], float)
    lo = np.floor(allc.min(axis=0)) - MARGIN
    hi = np.ceil(allc.max(axis=0)) + CUBE + MARGIN
    W, D, H = (hi - lo).astype(int)
    m = Model(int(W), int(D), int(H), seed=5, res=RES)
    palette(m)
    for p, cs in pieces:
        with m.part(p["name"]):
            for x, y, z, s, kind in cs:
                m.box(int(round(x - lo[0])), int(round(y - lo[1])), int(round(z - lo[2])), s, s, s, kind)
    return m
