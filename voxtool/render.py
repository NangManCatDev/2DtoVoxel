"""Software preview renderer for voxel grids (no MagicaVoxel needed).

render_iso   : orthographic 3/4 view with face shading + ambient occlusion
render_ortho : flat front/back/left/right/top views (for checking proportions)
render_sheet : iso + all ortho views on one labelled PNG
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BG = (233, 230, 225)
POLY_LIMIT = 150_000   # with more visible faces than this, render_iso rasterises with numpy (z-buffer)
MAX_PX = 3000          # longest side of a render_iso image; bigger models are drawn at a smaller scale

# face normals and base brightness (light from upper-front-left)
FACES = {
    (0, 0, 1): 1.00,
    (0, -1, 0): 0.90,
    (-1, 0, 0): 0.76,
    (1, 0, 0): 0.70,
    (0, 1, 0): 0.62,
    (0, 0, -1): 0.50,
}

# unit-cube face corners per normal (counter-clockwise doesn't matter for PIL)
_CORNERS = {
    (0, 0, 1): [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    (0, 0, -1): [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
    (0, -1, 0): [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
    (0, 1, 0): [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
    (-1, 0, 0): [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],
    (1, 0, 0): [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
}


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _shift(a: np.ndarray, d: tuple[int, int, int]) -> np.ndarray:
    """out[p] = a[p + d], zero outside."""
    out = np.zeros_like(a)
    src = tuple(slice(max(k, 0), a.shape[i] + min(k, 0)) for i, k in enumerate(d))
    dst = tuple(slice(max(-k, 0), a.shape[i] + min(-k, 0)) for i, k in enumerate(d))
    out[dst] = a[src]
    return out


def coarsen(v: np.ndarray, k: int) -> np.ndarray:
    """k x k x k blocks -> one voxel each, coloured like the block's topmost voxel."""
    X, Y, Z = (-(-s // k) * k for s in v.shape)
    p = np.zeros((X, Y, Z), np.uint8)
    p[:v.shape[0], :v.shape[1], :v.shape[2]] = v
    b = p.reshape(X // k, k, Y // k, k, Z // k, k).transpose(0, 2, 4, 5, 1, 3)[:, :, :, ::-1]
    b = b.reshape(X // k, Y // k, Z // k, -1)
    return np.take_along_axis(b, np.argmax(b > 0, axis=-1)[..., None], -1)[..., 0]


def _ao(filled: np.ndarray, n: tuple[int, int, int]) -> np.ndarray:
    """Number of filled voxels around the empty cell in front of each face (0..8)."""
    axes = [i for i in range(3) if n[i] == 0]
    cnt = np.zeros(filled.shape, np.int8)
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            if a == 0 and b == 0:
                continue
            d = list(n)
            d[axes[0]] += a
            d[axes[1]] += b
            cnt += _shift(filled, tuple(d))
    return cnt


class Camera:
    """azimuth 0 = looking straight at the front (-Y face), 90 = at the left side
    (-X face); elevation = degrees above the horizon; fov = vertical field of view in
    degrees, 0 = orthographic. A perspective camera is placed so the whole grid fits,
    and projected sizes are normalised so 1 voxel at the grid centre = 1 unit."""

    def __init__(self, shape, azimuth: float = 30.0, elevation: float = 30.0, fov: float = 0.0):
        A, E = math.radians(azimuth), math.radians(elevation)
        self.fwd = np.array([math.sin(A) * math.cos(E), math.cos(A) * math.cos(E), -math.sin(E)])
        self.right = np.array([math.cos(A), -math.sin(A), 0.0])
        self.up = np.array([math.sin(E) * math.sin(A), math.sin(E) * math.cos(A), math.cos(E)])
        self.center = np.array(shape, float) / 2
        self.fov = float(fov or 0)
        if self.fov > 0:
            radius = 0.5 * float(np.linalg.norm(shape))
            self.dist = radius / math.sin(math.radians(self.fov) / 2) * 1.02
            self.pos = self.center - self.fwd * self.dist

    def project(self, p: np.ndarray) -> np.ndarray:
        """World points [..., 3] -> screen [..., 2] (x right, y down), voxel units."""
        q = p - (self.pos if self.fov > 0 else self.center)
        x, y = q @ self.right, q @ self.up
        if self.fov > 0:
            k = self.dist / np.maximum(q @ self.fwd, 1e-3)
            x, y = x * k, y * k
        return np.stack([x, -y], axis=-1)

    def depth(self, p: np.ndarray) -> np.ndarray:
        """Larger = farther from the camera (for painter's ordering)."""
        if self.fov > 0:
            return np.linalg.norm(p - self.pos, axis=-1)
        return p @ self.fwd

    def visible(self, n: tuple[int, int, int], coords: np.ndarray) -> np.ndarray:
        """Which voxel faces with normal n (at voxel coords [N, 3]) face the camera."""
        if self.fov <= 0:
            return np.full(len(coords), float(np.dot(n, self.fwd)) < 0)
        a = next(i for i in range(3) if n[i])
        s = n[a]
        plane = coords[:, a] + (1 if s > 0 else 0)
        return s * (self.pos[a] - plane) > 0


def _faces(v: np.ndarray, palette: np.ndarray, cam: Camera, emissive: set[int]) -> dict | None:
    """Exposed voxel faces turned toward the camera: corners [N, 4, 3], depth [N] (larger =
    farther), shaded rgb [N, 3] uint8, voxel coords [N, 3] and normal [N] (index into FACES)."""
    filled = v > 0
    out = {k: [] for k in ("corners", "depth", "rgb", "coords", "normal")}
    for fi, (n, base) in enumerate(FACES.items()):
        exposed = filled & ~_shift(filled, n)
        xs, ys, zs = np.nonzero(exposed)
        if len(xs) == 0:
            continue
        coords = np.stack([xs, ys, zs], axis=1)
        vis = cam.visible(n, coords)
        if not vis.any():
            continue  # face points away from camera
        xs, ys, zs, coords = xs[vis], ys[vis], zs[vis], coords[vis]
        ao = _ao(filled, n)[xs, ys, zs]
        cols = v[xs, ys, zs]
        rgb = palette[cols, :3].astype(np.float32)
        shade = base * (1.0 - 0.055 * ao)
        is_emit = np.isin(cols, list(emissive)) if emissive else np.zeros(len(cols), bool)
        shade = np.where(is_emit, 1.0, shade)
        out["rgb"].append(np.clip(rgb * shade[:, None], 0, 255))
        out["corners"].append(coords[:, None, :] + np.array(_CORNERS[n], float)[None])
        out["depth"].append(cam.depth(coords + 0.5))
        out["coords"].append(coords)
        out["normal"].append(np.full(len(coords), fi))
    if not out["depth"]:
        return None
    f = {k: np.concatenate(a) for k, a in out.items()}
    f["rgb"] = f["rgb"].astype(np.uint8)
    return f


def _raster(polys: np.ndarray, depth: np.ndarray, W: int, H: int, budget: int = 4_000_000) -> np.ndarray:
    """Z-buffer for many quads: index of the nearest face per pixel [H, W], -1 where empty.
    Each quad (pixel coordinates [N, 4, 2]) is sampled on a k x k grid of its own (u, v)
    coordinates, k chosen so samples are under a pixel apart; a pixel keeps the nearest face
    any sample landed in. Same visibility as drawing far to near, without a Python loop per face."""
    order = np.argsort(depth, kind="stable")              # rank 0 = nearest
    p = polys[order]
    n = len(order)
    buf = np.full(W * H, n, np.int32 if n < 2 ** 31 - 1 else np.int64)
    edge = np.linalg.norm(p - np.roll(p, 1, axis=1), axis=-1).max(axis=1)
    ks = np.ceil(edge * 1.25).astype(np.int64) + 1
    for k in np.unique(ks):
        sel = np.nonzero(ks == k)[0]
        t = (np.arange(k) + 0.5) / k
        u, w = (a.ravel() for a in np.meshgrid(t, t, indexing="ij"))
        wts = np.stack([(1 - u) * (1 - w), u * (1 - w), u * w, (1 - u) * w], axis=1)   # bilinear [k*k, 4]
        step = max(1, budget // (k * k))
        for c in range(0, len(sel), step):
            rank = sel[c:c + step]
            xy = np.einsum("sc,nci->nsi", wts, p[rank])
            x = np.floor(xy[..., 0]).astype(np.int64)
            y = np.floor(xy[..., 1]).astype(np.int64)
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            np.minimum.at(buf, (y * W + x)[ok], np.broadcast_to(rank[:, None], x.shape)[ok].astype(buf.dtype))
    buf = buf.reshape(H, W)
    return np.where(buf < n, order[np.minimum(buf, n - 1)], -1)


def face_buffer(v: np.ndarray, palette: np.ndarray, cam: Camera, to_px, W: int, H: int,
                emissive: set[int] | None = None):
    """Nearest visible face per pixel of a W x H canvas, where to_px maps Camera.project output
    (voxel units [..., 2]) to pixels. Returns (face index [H, W], -1 = empty; faces from _faces)."""
    f = _faces(v, palette, cam, emissive or set()) if (v > 0).any() else None
    if f is None:
        return np.full((H, W), -1), None
    return _raster(to_px(cam.project(f["corners"])), f["depth"], W, H), f


def render_iso(v: np.ndarray, palette: np.ndarray, *, azimuth: float = 30.0, elevation: float = 30.0,
               fov: float = 0.0, scale: float = 6, outline: bool = True, emissive: set[int] | None = None,
               bg=BG, pad: int = 12, ss: int = 2, transparent: bool = False, return_info: bool = False,
               max_px: int = MAX_PX):
    """3/4 view of the grid (see Camera for azimuth/elevation/fov).
    ss = supersampling (1 = crisp pixel edges, for sprites); transparent=True gives an
    RGBA image with an empty background. return_info=True also returns a dict whose
    'project' maps world points [..., 3] to output-image pixel coordinates. The scale is
    lowered so the image stays within max_px; models with more than POLY_LIMIT visible faces
    are drawn with a z-buffer (no outlines or supersampling: their faces are tiny anyway)."""
    emissive = emissive or set()
    cam = Camera(v.shape, azimuth, elevation, fov)

    f = _faces(v, palette, cam, emissive) if (v > 0).any() else None
    if f is None:
        img = Image.new("RGBA" if transparent else "RGB", (64, 64), (0, 0, 0, 0) if transparent else bg)
        return (img, {"project": lambda p: np.zeros(np.shape(p)[:-1] + (2,))}) if return_info else img

    pts = cam.project(f["corners"])               # [N, 4, 2] in voxel units
    big = len(f["depth"]) > POLY_LIMIT
    if big:
        ss = 1
    extent = float((pts.reshape(-1, 2).max(axis=0) - pts.reshape(-1, 2).min(axis=0)).max())
    scale = min(scale, max_px / max(extent, 1.0))
    s = scale * ss
    polys = pts * s
    depths, colors = f["depth"], f["rgb"]

    lo = polys.reshape(-1, 2).min(axis=0)
    hi = polys.reshape(-1, 2).max(axis=0)
    off = -lo + pad * ss
    W, H = (hi - lo + 2 * pad * ss).astype(int) + 1
    polys = polys + off
    if big:
        ids = _raster(polys, depths, int(W), int(H))
        hit = ids >= 0
        arr = np.zeros((int(H), int(W), 4 if transparent else 3), np.uint8)
        if not transparent:
            arr[:] = bg
        arr[hit, :3] = colors[ids[hit]]
        if transparent:
            arr[..., 3] = hit * 255
        img = Image.fromarray(arr, "RGBA" if transparent else "RGB")
    else:
        order = np.argsort(-depths, kind="stable")  # far first
        if transparent:
            img = Image.new("RGBA", (int(W), int(H)), (0, 0, 0, 0))
        else:
            img = Image.new("RGB", (int(W), int(H)), bg)
        dr = ImageDraw.Draw(img)
        for i in order:
            c = tuple(int(k) for k in colors[i])
            pts = [tuple(p) for p in polys[i]]
            if transparent:
                c = c + (255,)
            if outline:
                oc = tuple(int(k * 0.9) for k in c[:3]) + c[3:]
                dr.polygon(pts, fill=c, outline=oc)
            else:
                dr.polygon(pts, fill=c)
    if ss > 1:
        img = img.resize((int(W) // ss, int(H) // ss), Image.LANCZOS)
    if not return_info:
        return img
    return img, {"camera": cam, "project": lambda p: (cam.project(np.asarray(p, float)) * s + off) / ss}


ORTHO_VIEWS = {
    # name: (axis looked along, flip that axis?, screen-x axis, flip screen-x?)
    "front": (1, False, 0, False),   # from -Y, x to the right
    "back": (1, True, 0, True),      # from +Y
    "left": (0, False, 1, True),     # from -X, front (y=0) on the right
    "right": (0, True, 1, False),    # from +X
    "top": (2, True, 0, False),      # from +Z, front at the bottom
}


def render_ortho(v: np.ndarray, palette: np.ndarray, view: str, *, scale: int = 4,
                 bg=BG, grid: int = 0) -> Image.Image:
    """Flat orthographic view; nearer voxels are slightly brighter.
    grid>0 draws a faint line every `grid` voxels (useful for measuring)."""
    axis, flip, sx_axis, sx_flip = ORTHO_VIEWS[view]
    a = v
    if flip:
        a = np.flip(a, axis)
    filled = a > 0
    hit = filled.any(axis=axis)
    first = np.argmax(filled, axis=axis)
    col = np.take_along_axis(a, np.expand_dims(first, axis), axis).squeeze(axis)
    depth = first / max(a.shape[axis] - 1, 1)

    # remaining 2D array axes (in order) after removing `axis`
    rem = [i for i in range(3) if i != axis]
    rgb = palette[col, :3].astype(np.float32) * (1.0 - 0.35 * depth)[..., None]
    out = np.where(hit[..., None], rgb, np.array(bg, np.float32)).astype(np.uint8)
    # arrange as image rows/cols: screen x = sx_axis, screen y = the other remaining axis (upwards)
    sy_axis = [i for i in rem if i != sx_axis][0]
    if rem.index(sx_axis) != 1:
        out = out.transpose(1, 0, 2)  # now [sy, sx]
    if sx_flip:
        out = out[:, ::-1]
    if view == "top":
        out = out[::-1]          # y=0 (front) at the bottom
    else:
        out = out[::-1]          # z up
    img = Image.fromarray(np.ascontiguousarray(out)).resize((out.shape[1] * scale, out.shape[0] * scale),
                                                            Image.NEAREST)
    if grid:
        dr = ImageDraw.Draw(img)
        lc = (200, 60, 60)
        for gx in range(0, out.shape[1] + 1, grid):
            dr.line([(gx * scale, 0), (gx * scale, img.height)], fill=lc, width=1)
        for gy in range(0, out.shape[0] + 1, grid):
            y = img.height - gy * scale
            dr.line([(0, y), (img.width, y)], fill=lc, width=1)
    _ = sy_axis
    return img


def render_sheet(v: np.ndarray, palette: np.ndarray, *, title: str = "", azimuth: float = 30.0,
                 elevation: float = 30.0, fov: float = 0.0, emissive: set[int] | None = None,
                 iso_scale: int = 6) -> Image.Image:
    big = max(v.shape)
    cap = MAX_PX if big <= 256 else 1600          # keep sheets of huge models readable as one image
    iso = render_iso(v, palette, azimuth=azimuth, elevation=elevation, fov=fov, scale=iso_scale, emissive=emissive,
                     max_px=cap)
    iso2 = render_iso(v, palette, azimuth=azimuth + 180, elevation=elevation, fov=fov,
                      scale=max(iso_scale // 2, 2), emissive=emissive, max_px=cap // 2)
    if big <= 320:
        osc = max(2, min(5, 320 // big))
        views = [(name, render_ortho(v, palette, name, scale=osc, grid=10)) for name in ORTHO_VIEWS]
    else:                                          # one pixel per voxel, grid every 100, shrunk to 400 px
        views = []
        for name in ORTHO_VIEWS:
            im = render_ortho(v, palette, name, scale=1, grid=100)
            k = min(1.0, 400 / max(im.size))
            views.append((name, im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.BOX)))
    views.append((f"iso {azimuth + 180:g}°", iso2))

    font = _font(16)
    label_h = 22
    gap = 14
    # ortho grid: 3 columns x 2 rows
    cw = max(im.width for _, im in views)
    ch = max(im.height for _, im in views) + label_h
    grid_w = 3 * cw + 2 * gap
    grid_h = 2 * ch + gap
    iso_w = max(iso.width, 200)  # leave room for the label on tiny models
    W = iso_w + gap * 3 + grid_w
    H = max(iso.height + label_h, grid_h) + gap * 2 + (28 if title else 0)
    sheet = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    y0 = gap
    if title:
        dr.text((gap, gap), title, fill=(40, 40, 40), font=_font(20))
        y0 += 28
    cam = f"iso az={azimuth:g}° el={elevation:g}°" + (f" fov={fov:g}°" if fov else "")
    dr.text((gap, y0), cam, fill=(60, 60, 60), font=font)
    sheet.paste(iso, (gap, y0 + label_h))
    gx0 = iso_w + gap * 2
    for i, (name, im) in enumerate(views):
        cx = gx0 + (i % 3) * (cw + gap)
        cy = y0 + (i // 3) * (ch + gap)
        dr.text((cx, cy), name, fill=(60, 60, 60), font=font)
        sheet.paste(im, (cx, cy + label_h))
    return sheet
