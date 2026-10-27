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


def render_iso(v: np.ndarray, palette: np.ndarray, *, azimuth: float = 30.0, elevation: float = 30.0,
               fov: float = 0.0, scale: int = 6, outline: bool = True, emissive: set[int] | None = None,
               bg=BG, pad: int = 12, ss: int = 2, transparent: bool = False, return_info: bool = False):
    """3/4 view of the grid (see Camera for azimuth/elevation/fov).
    ss = supersampling (1 = crisp pixel edges, for sprites); transparent=True gives an
    RGBA image with an empty background. return_info=True also returns a dict whose
    'project' maps world points [..., 3] to output-image pixel coordinates."""
    emissive = emissive or set()
    cam = Camera(v.shape, azimuth, elevation, fov)
    s = scale * ss

    filled = v > 0
    if not filled.any():
        img = Image.new("RGBA" if transparent else "RGB", (64, 64), (0, 0, 0, 0) if transparent else bg)
        return (img, {"project": lambda p: np.zeros(np.shape(p)[:-1] + (2,))}) if return_info else img

    polys, depths, colors = [], [], []
    for n, base in FACES.items():
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
        rgb = np.clip(rgb * shade[:, None], 0, 255)
        corners = np.array(_CORNERS[n], float)
        pts = coords[:, None, :] + corners[None]
        polys.append(cam.project(pts) * s)
        depths.append(cam.depth(coords + 0.5))
        colors.append(rgb)

    polys = np.concatenate(polys)
    depths = np.concatenate(depths)
    colors = np.concatenate(colors).astype(np.uint8)
    order = np.argsort(-depths, kind="stable")  # far first

    lo = polys.reshape(-1, 2).min(axis=0)
    hi = polys.reshape(-1, 2).max(axis=0)
    off = -lo + pad * ss
    W, H = (hi - lo + 2 * pad * ss).astype(int) + 1
    if transparent:
        img = Image.new("RGBA", (int(W), int(H)), (0, 0, 0, 0))
    else:
        img = Image.new("RGB", (int(W), int(H)), bg)
    dr = ImageDraw.Draw(img)
    polys = polys + off
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
    iso = render_iso(v, palette, azimuth=azimuth, elevation=elevation, fov=fov, scale=iso_scale, emissive=emissive)
    iso2 = render_iso(v, palette, azimuth=azimuth + 180, elevation=elevation, fov=fov,
                      scale=max(iso_scale // 2, 2), emissive=emissive)
    big = max(v.shape)
    osc = max(2, min(5, 320 // big))
    views = [(name, render_ortho(v, palette, name, scale=osc, grid=10)) for name in ORTHO_VIEWS]
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
