"""Voxel building DSL used by model scripts in models/.

Coordinates: x = right, y = depth (y=0 is the FRONT, MagicaVoxel's default view side),
z = up. Boxes are given as position + size: box(x, y, z, w, d, h, c) fills
x..x+w-1, y..y+d-1, z..z+h-1. Anything outside the grid is clipped silently.

Colors are referenced by palette name (registered with m.pal.add) or by index.
Drawing inside `with m.part("name"):` saves those voxels as a separate object.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterable, Sequence, Union

import numpy as np

from .vox_io import MAX_DIM, VoxModel, VoxScene, backup_if_edited, merge_models, read_vox, write_vox

Color = Union[str, int, None]   # None = carve (set empty)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class Palette:
    def __init__(self):
        self.rgba = np.zeros((256, 4), np.uint8)
        self.names: dict[str, int] = {}
        self.materials: dict[int, dict[str, str]] = {}
        self._next = 1

    def add(self, name: str, hex_color: str, *, emit: float = 0.0, glass: float = 0.0,
            metal: float = 0.0, rough: float = 0.5) -> int:
        """Registers a named color. emit>0 makes it glow in MagicaVoxel's renderer
        (lanterns, lit windows); glass>0 makes it transparent."""
        if name in self.names:
            raise ValueError(f"color {name!r} already defined")
        if self._next > 255:
            raise ValueError("palette full (255 colors)")
        idx = self._next
        self._next += 1
        self.rgba[idx] = (*hex_rgb(hex_color), 255)
        self.names[name] = idx
        if emit > 0:
            self.materials[idx] = {"_type": "_emit", "_emit": f"{emit:g}", "_flux": "2", "_ldr": "0"}
        elif glass > 0:
            self.materials[idx] = {"_type": "_glass", "_trans": f"{glass:g}", "_rough": "0.1", "_ior": "0.5"}
        elif metal > 0:
            self.materials[idx] = {"_type": "_metal", "_metal": f"{metal:g}", "_rough": f"{rough:g}"}
        return idx

    def ramp(self, name: str, hex_colors: Sequence[str], **mat) -> list[str]:
        """Registers name0, name1, ... (shade variants of one material). Returns the names."""
        out = []
        for i, h in enumerate(hex_colors):
            self.add(f"{name}{i}", h, **mat)
            out.append(f"{name}{i}")
        return out

    def idx(self, c: Color) -> int:
        if c is None:
            return 0
        if isinstance(c, (int, np.integer)):
            return int(c)
        try:
            return self.names[c]
        except KeyError:
            raise KeyError(f"unknown color {c!r}; defined: {sorted(self.names)}") from None

    def is_emissive(self, idx: int) -> bool:
        return self.materials.get(idx, {}).get("_type") == "_emit"


class Model:
    def __init__(self, w: int, d: int, h: int, seed: int = 0):
        """Each saved object is limited to MAX_DIM per axis; a bigger grid is fine
        as long as m.part() splits it into objects that fit (checked on save)."""
        self.v = np.zeros((w, d, h), np.uint8)
        self.pal = Palette()
        self.rng = np.random.default_rng(seed)
        self.part_names: list[str] = []
        self.labels = np.zeros((w, d, h), np.uint8)   # voxel -> 1-based part index, 0 = no part

    @property
    def size(self) -> tuple[int, int, int]:
        return self.v.shape

    # ------------------------------------------------------------ helpers

    def _slices(self, x, y, z, w, d, h):
        W, D, H = self.v.shape
        x0, y0, z0 = max(x, 0), max(y, 0), max(z, 0)
        x1, y1, z1 = min(x + w, W), min(y + d, D), min(z + h, H)
        if x1 <= x0 or y1 <= y0 or z1 <= z0:
            return None
        return (slice(x0, x1), slice(y0, y1), slice(z0, z1))

    def _coords(self, sl):
        """Absolute coordinate grids (X, Y, Z) for a slice tuple."""
        return np.meshgrid(np.arange(sl[0].start, sl[0].stop),
                           np.arange(sl[1].start, sl[1].stop),
                           np.arange(sl[2].start, sl[2].stop), indexing="ij")

    def _paint(self, sl, mask, c: Color, only_empty=False, only_filled=False):
        region = self.v[sl]
        if only_empty:
            mask = mask & (region == 0)
        if only_filled:
            mask = mask & (region != 0)
        region[mask] = self.pal.idx(c)

    # ------------------------------------------------------------ primitives

    def set(self, x: int, y: int, z: int, c: Color):
        W, D, H = self.v.shape
        if 0 <= x < W and 0 <= y < D and 0 <= z < H:
            self.v[x, y, z] = self.pal.idx(c)

    def get(self, x: int, y: int, z: int) -> int:
        W, D, H = self.v.shape
        if 0 <= x < W and 0 <= y < D and 0 <= z < H:
            return int(self.v[x, y, z])
        return 0

    def box(self, x, y, z, w, d, h, c: Color, *, only_empty=False, only_filled=False):
        """Solid box. c=None carves."""
        sl = self._slices(x, y, z, w, d, h)
        if sl is not None:
            self._paint(sl, np.ones(self.v[sl].shape, bool), c, only_empty, only_filled)

    def carve(self, x, y, z, w, d, h):
        self.box(x, y, z, w, d, h, None)

    def shell(self, x, y, z, w, d, h, c: Color, t: int = 1, top=True, bottom=True):
        """Hollow box with wall thickness t (walls on all 4 sides, optional top/bottom)."""
        self.box(x, y, z, w, d, h, c)
        iz0 = z + (t if bottom else 0)
        iz1 = z + h - (t if top else 0)
        self.box(x + t, y + t, iz0, w - 2 * t, d - 2 * t, iz1 - iz0, None)

    def where(self, x, y, z, w, d, h, fn: Callable, c: Color, **kw):
        """Fills voxels in the box where fn(X, Y, Z) is True. X/Y/Z are absolute
        numpy coordinate arrays, so fn is written vectorised, e.g.
        lambda X, Y, Z: (X - 10)**2 + (Y - 10)**2 < 25"""
        sl = self._slices(x, y, z, w, d, h)
        if sl is None:
            return
        X, Y, Z = self._coords(sl)
        self._paint(sl, np.asarray(fn(X, Y, Z), bool), c, **kw)

    def paint_fn(self, x, y, z, w, d, h, fn: Callable, *, only_filled=True):
        """Recolors per voxel: fn(X, Y, Z) returns an array of palette indices
        (0 = leave unchanged). Use m.pal.idx('name') to get indices."""
        sl = self._slices(x, y, z, w, d, h)
        if sl is None:
            return
        X, Y, Z = self._coords(sl)
        new = np.broadcast_to(np.asarray(fn(X, Y, Z), np.uint8), X.shape)
        region = self.v[sl]
        mask = new > 0
        if only_filled:
            mask &= region > 0
        region[mask] = new[mask]

    def line(self, p0: Sequence[int], p1: Sequence[int], c: Color, r: int = 0):
        """3D line (Bresenham-like sampling). r>0 makes it a thick cube brush."""
        p0, p1 = np.array(p0, float), np.array(p1, float)
        n = int(np.max(np.abs(p1 - p0))) + 1
        for t in np.linspace(0, 1, n):
            px, py, pz = np.round(p0 + (p1 - p0) * t).astype(int)
            if r:
                self.box(px - r, py - r, pz - r, 2 * r + 1, 2 * r + 1, 2 * r + 1, c)
            else:
                self.set(px, py, pz, c)

    def ellipsoid(self, cx, cy, cz, rx, ry, rz, c: Color, **kw):
        self.where(int(cx - rx), int(cy - ry), int(cz - rz), int(2 * rx + 2), int(2 * ry + 2), int(2 * rz + 2),
                   lambda X, Y, Z: ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2 <= 1.0,
                   c, **kw)

    def cylinder(self, cx, cy, z, r, h, c: Color, axis: str = "z", **kw):
        """Cylinder of radius r. For axis='z' the base center is (cx, cy, z);
        for axis 'x'/'y' the arguments are reinterpreted along that axis:
        axis='x': (cy, cz) = (cx, cy), starts at x=z;  axis='y': (cx, cz) = (cx, cy), starts at y=z."""
        r2 = r * r + r * 0.8  # slightly fuller circles look better at low res
        R = int(np.ceil(r))
        if axis == "z":
            self.where(int(cx) - R, int(cy) - R, z, 2 * R + 1, 2 * R + 1, h,
                       lambda X, Y, Z: (X - cx) ** 2 + (Y - cy) ** 2 <= r2, c, **kw)
        elif axis == "x":
            self.where(z, int(cx) - R, int(cy) - R, h, 2 * R + 1, 2 * R + 1,
                       lambda X, Y, Z: (Y - cx) ** 2 + (Z - cy) ** 2 <= r2, c, **kw)
        else:
            self.where(int(cx) - R, z, int(cy) - R, 2 * R + 1, h, 2 * R + 1,
                       lambda X, Y, Z: (X - cx) ** 2 + (Z - cy) ** 2 <= r2, c, **kw)

    def gable_roof(self, x, y, z, w, d, ridge: str, c: Color | Sequence[Color], *,
                   slope: float = 1.0, t: int = 2, fill: Color = None):
        """Gabled roof over footprint (x, y, w, d) starting at height z.
        ridge='x' -> ridge runs along x (slopes face -y/+y); ridge='y' -> along y.
        slope = rise per horizontal voxel. t = vertical thickness of the roof skin.
        c may be a list of colors: they alternate per course (horizontal step),
        which gives a shingle / plank look. fill (optional) fills the space
        below the skin (e.g. gable wall material)."""
        span = d if ridge == "x" else w
        half = (span - 1) / 2.0
        colors = list(c) if isinstance(c, (list, tuple)) else [c]
        top = z + int(np.ceil(half * slope)) + t + 1
        sl = self._slices(x, y, z, w, d, top - z)
        if sl is None:
            return
        X, Y, Z = self._coords(sl)
        a = (Y - y) if ridge == "x" else (X - x)
        dist = np.minimum(a, span - 1 - a)           # 0 at eave, grows toward ridge
        surf = z + np.floor(dist * slope).astype(int)  # underside height of the skin
        skin = (Z >= surf) & (Z < surf + t)
        course = dist.astype(int)
        region = self.v[sl]
        for i, col in enumerate(colors):
            m = skin & (course % len(colors) == i)
            region[m] = self.pal.idx(col)
        if fill is not None:
            below = (Z < surf) & (Z >= z)
            region[below & (region == 0)] = self.pal.idx(fill)

    def gable_wall(self, x, y, z, w, d, ridge: str, c: Color, *, slope: float = 1.0,
                   region: tuple | None = None):
        """Solid infill under a gable_roof with the same footprint/z/slope, so it meets
        the roof skin exactly. region=(x, y, w, d) limits the fill (e.g. to the wall
        footprint, leaving the roof overhang open)."""
        span = d if ridge == "x" else w
        half = (span - 1) / 2.0
        top = z + int(np.ceil(half * slope)) + 1
        def fn(X, Y, Z):
            a = (Y - y) if ridge == "x" else (X - x)
            dist = np.minimum(a, span - 1 - a)
            return Z < z + np.floor(dist * slope)
        rx, ry, rw, rd = region if region else (x, y, w, d)
        self.where(rx, ry, z, rw, rd, top - z, fn, c)

    def shed_roof(self, x, y, z, w, d, down: str, c: Color | Sequence[Color], *,
                  slope: float = 0.5, t: int = 2):
        """Lean-to roof (porch awning) over footprint (x, y, w, d). z is the underside
        height at the LOW edge; the roof rises by `slope` per voxel away from the low
        edge. down = side of the low edge: '-y' (low at front), '+y', '-x', '+x'.
        A color list alternates per course, like gable_roof."""
        span = d if down in ("-y", "+y") else w
        colors = list(c) if isinstance(c, (list, tuple)) else [c]
        top = z + int(np.ceil((span - 1) * slope)) + t + 1
        sl = self._slices(x, y, z, w, d, top - z)
        if sl is None:
            return
        X, Y, Z = self._coords(sl)
        if down == "-y":
            a = Y - y
        elif down == "+y":
            a = (y + d - 1) - Y
        elif down == "-x":
            a = X - x
        else:
            a = (x + w - 1) - X
        surf = z + np.floor(a * slope).astype(int)
        skin = (Z >= surf) & (Z < surf + t)
        course = np.floor(a * slope).astype(int)
        region = self.v[sl]
        for i, col in enumerate(colors):
            region[skin & (course % len(colors) == i)] = self.pal.idx(col)

    def stairs(self, x, y, z, w, steps: int, c: Color, *, rise: int = 1, run: int = 2, direction: str = "-y"):
        """Stairs going down toward `direction` ('-y', '+y', '-x', '+x').
        (x, y, z) is the corner of the top step at its highest point's base."""
        for i in range(steps):
            h = (steps - i) * rise
            off = i * run
            if direction == "-y":
                self.box(x, y - off - run + 1, z, w, run, h, c)
            elif direction == "+y":
                self.box(x, y + off, z, w, run, h, c)
            elif direction == "-x":
                self.box(x - off - run + 1, y, z, run, w, h, c)
            else:
                self.box(x + off, y, z, run, w, h, c)

    # ------------------------------------------------------------ organic / texture helpers

    def vary(self, colors: Sequence[Color], *, target: Color | Iterable[Color], p: Sequence[float] | None = None,
             region: tuple | None = None):
        """Randomly re-colors voxels of `target` color(s) with a choice from `colors`
        (weights p). Breaks up flat surfaces. region = (x, y, z, w, d, h) or None for all."""
        sl = self._slices(*region) if region else (slice(None),) * 3
        if sl is None:
            return
        tgt = [target] if isinstance(target, (str, int)) else list(target)
        idxs = [self.pal.idx(t) for t in tgt]
        sub = self.v[sl]
        mask = np.isin(sub, idxs)
        n = int(mask.sum())
        if n == 0:
            return
        choice = self.rng.choice([self.pal.idx(c) for c in colors], size=n, p=p)
        sub[mask] = choice

    def bricks(self, colors: Sequence[Color], *, target: Color | Iterable[Color], bw: int = 6, bh: int = 3,
               mortar: Color = None, p: Sequence[float] | None = None, region: tuple | None = None,
               salt: int = 0):
        """Re-colors voxels of `target` in a running-bond block pattern (stone / brick
        walls). Each block gets one color from `colors` (weights p); `mortar`, if
        given, colors the joints. The horizontal coordinate is x+y, so the pattern
        wraps continuously around corners of x- and y-facing walls."""
        sl = self._slices(*region) if region else tuple(slice(0, s) for s in self.v.shape)
        if sl is None:
            return
        tgt = [target] if isinstance(target, (str, int)) else list(target)
        sub = self.v[sl]
        mask = np.isin(sub, [self.pal.idx(t) for t in tgt])
        X, Y, Z = self._coords(sl)
        u = X + Y
        row = Z // bh
        off = (row % 2) * (bw // 2)
        col = (u + off) // bw
        h = (col.astype(np.uint64) * np.uint64(73856093)) ^ (row.astype(np.uint64) * np.uint64(19349663)) \
            ^ np.uint64(salt * 83492791 + 1)
        h = ((h * np.uint64(2654435761)) % np.uint64(2 ** 32)).astype(np.float64) / 2 ** 32
        cum = np.cumsum(p if p is not None else np.full(len(colors), 1 / len(colors)))
        pick = np.searchsorted(cum / cum[-1], h, side="right").clip(0, len(colors) - 1)
        idx = np.array([self.pal.idx(c) for c in colors], np.uint8)[pick]
        if mortar is not None:
            joint = ((u + off) % bw == 0) | (Z % bh == 0)
            idx = np.where(joint, np.uint8(self.pal.idx(mortar)), idx)
        sub[mask] = idx[mask]

    def blob(self, cx, cy, cz, rx, ry, rz, colors: Sequence[Color], *, noise: float = 0.35,
             density: float = 1.0, p: Sequence[float] | None = None, only_empty=True):
        """Noisy ellipsoid — bushes, foliage, rocks. noise roughens the boundary,
        density < 1 makes it airy. Colors chosen randomly (weights p)."""
        sl = self._slices(int(cx - rx - 1), int(cy - ry - 1), int(cz - rz - 1),
                          int(2 * rx + 3), int(2 * ry + 3), int(2 * rz + 3))
        if sl is None:
            return
        X, Y, Z = self._coords(sl)
        dist = ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2
        jitter = self.rng.uniform(-noise, noise, X.shape)
        mask = (dist + jitter <= 1.0) & (self.rng.random(X.shape) < density)
        region = self.v[sl]
        if only_empty:
            mask &= region == 0
        idx = np.array([self.pal.idx(c) for c in colors], np.uint8)
        region[mask] = self.rng.choice(idx, size=int(mask.sum()), p=p)

    def vine(self, x, y, z, length: int, colors: Sequence[Color], *, wall: str = "-y",
             drift: float = 0.35, leaf: float = 0.6, spread: int = 1):
        """Climbing vine growing DOWN from (x, y, z) along a wall surface.
        wall = which side of the wall the vine hangs on ('-y' = in front of a
        front-facing wall, '-x' = in front of a left-facing wall, '+x', '+y').
        With probability `leaf` a leaf cluster sprouts up to `spread` voxels
        sideways, sometimes one voxel further out from the wall."""
        out = {"-y": (0, -1), "+y": (0, 1), "-x": (-1, 0), "+x": (1, 0)}[wall]
        along_x = wall in ("-y", "+y")
        px, py, pz = x, y, z
        for _ in range(length):
            if pz < 0:
                break
            self.set(px, py, pz, self.rng.choice(colors))
            if self.rng.random() < leaf:
                for _ in range(int(self.rng.integers(1, 3))):
                    s = int(self.rng.integers(-spread, spread + 1))
                    o = int(self.rng.random() < 0.3)
                    lx = px + (s if along_x else 0) + out[0] * o
                    ly = py + (0 if along_x else s) + out[1] * o
                    lz = pz + int(self.rng.integers(-1, 1))
                    self.set(lx, ly, lz, self.rng.choice(colors))
            pz -= 1
            if self.rng.random() < drift:
                step = int(self.rng.integers(-1, 2))
                if along_x:
                    px += step
                else:
                    py += step

    def scatter_on_top(self, region: tuple, colors: Sequence[Color], prob: float, *, target=None):
        """Places voxels on top of exposed surfaces inside region (flowers on bushes,
        moss on stones). target restricts to surfaces of those colors."""
        sl = self._slices(*region)
        if sl is None:
            return
        sub = self.v[sl]
        filled = sub > 0
        if target is not None:
            tgt = [target] if isinstance(target, (str, int)) else list(target)
            filled = np.isin(sub, [self.pal.idx(t) for t in tgt])
        above_empty = np.zeros_like(filled)
        above_empty[:, :, :-1] = sub[:, :, 1:] == 0
        cand = filled & above_empty & (self.rng.random(sub.shape) < prob)
        xs, ys, zs = np.nonzero(cand)
        idx = np.array([self.pal.idx(c) for c in colors], np.uint8)
        sub[xs, ys, zs + 1] = self.rng.choice(idx, size=len(xs))

    def sprinkle(self, colors: Sequence[Color], prob: float, *, target: Color | Iterable[Color],
                 region: tuple | None = None, surface_only=True):
        """Recolors random voxels of `target` (e.g. blue flowers inside a bush)."""
        sl = self._slices(*region) if region else (slice(None),) * 3
        if sl is None:
            return
        tgt = [target] if isinstance(target, (str, int)) else list(target)
        sub = self.v[sl]
        mask = np.isin(sub, [self.pal.idx(t) for t in tgt])
        if surface_only:
            filled = sub > 0
            interior = np.zeros_like(filled)
            interior[1:-1, 1:-1, 1:-1] = (filled[2:, 1:-1, 1:-1] & filled[:-2, 1:-1, 1:-1] &
                                          filled[1:-1, 2:, 1:-1] & filled[1:-1, :-2, 1:-1] &
                                          filled[1:-1, 1:-1, 2:] & filled[1:-1, 1:-1, :-2])
            mask &= ~interior
        mask &= self.rng.random(sub.shape) < prob
        idx = np.array([self.pal.idx(c) for c in colors], np.uint8)
        sub[mask] = self.rng.choice(idx, size=int(mask.sum()))

    # ------------------------------------------------------------ importing .vox files

    @classmethod
    def from_vox(cls, path: str, *, seed: int = 0, prefix: str = "v") -> "Model":
        """New model holding a .vox file (a base made by `voxtool extrude/carve`, or a
        model edited in MagicaVoxel) to add details to with the DSL."""
        src = merge_models(read_vox(path))
        m = cls(*src.shape, seed=seed)
        m.paste_vox(path, prefix=prefix)
        return m

    def paste_vox(self, path: str, x: int = 0, y: int = 0, z: int = 0, *, prefix: str = "v") -> dict[int, str]:
        """Pastes a .vox at (x, y, z) (non-empty voxels only, clipped to the grid). Its colours
        join the palette as <prefix><index>, reusing a palette entry with the same colour and
        material; materials (glow, glass, metal) are kept. Returns {file index: palette name}."""
        scene = read_vox(path)
        src = merge_models(scene)
        mapping: dict[int, str] = {}
        for idx in (int(i) for i in np.unique(src[src > 0])):
            rgb = tuple(int(c) for c in scene.palette[idx][:3])
            mat = scene.materials.get(idx)
            same = next((n for n, i in self.pal.names.items()
                         if tuple(int(c) for c in self.pal.rgba[i][:3]) == rgb and self.pal.materials.get(i) == mat), None)
            if same:
                mapping[idx] = same
                continue
            name = f"{prefix}{idx}"
            while name in self.pal.names:
                name += "_"
            new = self.pal.add(name, "#%02x%02x%02x" % rgb)
            if mat and mat.get("_type", "_diffuse") != "_diffuse":
                self.pal.materials[new] = dict(mat)
            mapping[idx] = name
        lut = np.zeros(256, np.uint8)
        for idx, name in mapping.items():
            lut[idx] = self.pal.idx(name)
        W, D, H = self.v.shape
        x1, y1, z1 = min(x + src.shape[0], W), min(y + src.shape[1], D), min(z + src.shape[2], H)
        if x1 > x >= 0 and y1 > y >= 0 and z1 > z >= 0:
            sub = lut[src[:x1 - x, :y1 - y, :z1 - z]]
            np.copyto(self.v[x:x1, y:y1, z:z1], sub, where=sub > 0)
        return mapping

    # ------------------------------------------------------------ transforms

    def mirror_x(self, x0: int, x1: int):
        """Copies the slab x0..x1-1 mirrored onto the other side of the grid center."""
        W = self.v.shape[0]
        src = self.v[x0:x1]
        np.copyto(self.v[W - x1:W - x0], src[::-1], where=src[::-1] > 0)

    def copy(self, x, y, z, w, d, h, dx, dy, dz):
        """Copies a box region to an offset (non-empty voxels only)."""
        sl = self._slices(x, y, z, w, d, h)
        if sl is None:
            return
        src = self.v[sl].copy()
        xs, ys, zs = np.nonzero(src)
        for a, b, cc, col in zip(xs + sl[0].start + dx, ys + sl[1].start + dy, zs + sl[2].start + dz,
                                 src[xs, ys, zs]):
            self.set(a, b, cc, int(col))

    # ------------------------------------------------------------ parts

    @contextmanager
    def part(self, name: str):
        """Voxels changed inside `with m.part(name):` are saved as their own named
        object in the .vox (kit sheets: each piece can be selected and moved on its
        own in MagicaVoxel). Voxels never touched inside a part block go to 'rest'.
        Without any part the file holds one object, as before."""
        if len(self.part_names) >= 255:
            raise ValueError("too many parts (255)")
        before = self.v.copy()
        yield
        self.part_names.append(name)
        self.labels[self.v != before] = len(self.part_names)

    def _part_masks(self) -> list[tuple[str, np.ndarray]]:
        filled = self.v > 0
        groups = [(n, filled & (self.labels == i + 1)) for i, n in enumerate(self.part_names)]
        groups.append(("rest", filled & (self.labels == 0)))
        return [(n, mk) for n, mk in groups if mk.any()]

    # ------------------------------------------------------------ output

    def stats(self) -> str:
        filled = self.v > 0
        if not filled.any():
            return "empty model"
        xs, ys, zs = np.nonzero(filled)
        used = np.unique(self.v[filled])
        inv = {i: n for n, i in self.pal.names.items()}
        counts = ", ".join(f"{inv.get(int(i), i)}={int((self.v == i).sum())}" for i in used)
        out = (f"grid {self.v.shape}, voxels {int(filled.sum())}, "
               f"bbox x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}] z[{zs.min()},{zs.max()}]\n"
               f"colors: {counts}")
        if self.part_names:
            out += "\nparts: " + ", ".join(f"{n}={int(mk.sum())}" for n, mk in self._part_masks())
        return out

    def to_scene(self) -> VoxScene:
        if not self.part_names:
            models = [VoxModel(self.v)]
        else:
            models = []
            for name, mk in self._part_masks():
                xs, ys, zs = np.nonzero(mk)
                lo = (int(xs.min()), int(ys.min()), int(zs.min()))
                sl = (slice(lo[0], xs.max() + 1), slice(lo[1], ys.max() + 1), slice(lo[2], zs.max() + 1))
                models.append(VoxModel(np.where(mk[sl], self.v[sl], 0).astype(np.uint8), lo, name))
        for vm in models:
            if max(vm.voxels.shape) > MAX_DIM:
                raise ValueError(f"object {vm.name or 'model'!r} spans {vm.voxels.shape}; each object must be "
                                 f"<= {MAX_DIM} per axis - split the grid with m.part()")
        return VoxScene(models, self.pal.rgba.copy(), dict(self.pal.materials))

    def save(self, path: str) -> str | None:
        """Writes the .vox. If the existing file was saved by MagicaVoxel (hand edits),
        it is first copied to <name>_edited_<time>.vox; returns that backup path."""
        scene = self.to_scene()             # size checks first, so a failed save backs up nothing
        backup = backup_if_edited(path)
        write_vox(path, scene)
        return backup
