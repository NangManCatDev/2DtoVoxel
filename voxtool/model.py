"""Voxel building DSL used by model scripts in models/.

Coordinates: x = right, y = depth (y=0 is the FRONT, MagicaVoxel's default view side),
z = up. Boxes are given as position + size: box(x, y, z, w, d, h, c) fills
x..x+w-1, y..y+d-1, z..z+h-1. Anything outside the grid is clipped silently.

Colors are referenced by palette name (registered with m.pal.add) or by index.
Drawing inside `with m.part("name"):` saves those voxels as a separate object.

Model(w, d, h, res=r) keeps every coordinate in these design units but fills an r times
finer voxel grid: a box covers r*w voxels, round shapes and roofs come out smoother, and
textures get finer. Code that indexes m.v directly works in voxels (multiply by m.res).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Callable, Iterable, Sequence, Union

import numpy as np

from .reftools import quantize
from .vox_io import MAX_DIM, VoxScene, backup_if_edited, merge_models, read_vox, split_grid, write_vox

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

    def material_args(self, idx: int) -> dict:
        """add() keyword arguments that give a new colour the glass / metal material of idx."""
        m = self.materials.get(idx, {})
        if m.get("_type") == "_glass":
            return {"glass": float(m.get("_trans", 0.5))}
        if m.get("_type") == "_metal":
            return {"metal": float(m.get("_metal", 0.5)), "rough": float(m.get("_rough", 0.5))}
        return {}


class Model:
    def __init__(self, w: int, d: int, h: int, seed: int = 0, *, res: int = 1):
        """A w x d x h grid in design units, stored as (w*res, d*res, h*res) voxels. Objects
        bigger than MAX_DIM per axis are split into tiles when saved."""
        if int(res) < 1:
            raise ValueError("res must be a whole number >= 1")
        self.res = int(res)
        self.dims = (w, d, h)
        self.v = np.zeros((w * self.res, d * self.res, h * self.res), np.uint8)
        self.pal = Palette()
        self.rng = np.random.default_rng(seed)
        self.part_names: list[str] = []
        self.labels: np.ndarray | None = None   # voxel -> 1-based part index, 0 = no part (made by part())

    @property
    def size(self) -> tuple[int, int, int]:
        """Size of the voxel grid (dims * res)."""
        return self.v.shape

    # ------------------------------------------------------------ helpers

    def _slices(self, x, y, z, w, d, h):
        r = self.res
        W, D, H = self.v.shape
        x0, y0, z0 = max(round(x * r), 0), max(round(y * r), 0), max(round(z * r), 0)
        x1, y1, z1 = min(round((x + w) * r), W), min(round((y + d) * r), D), min(round((z + h) * r), H)
        if x1 <= x0 or y1 <= y0 or z1 <= z0:
            return None
        return (slice(x0, x1), slice(y0, y1), slice(z0, z1))

    def _coords(self, sl):
        """Coordinate grids (X, Y, Z) in design units for a slice tuple: the position of each
        voxel's low corner, so integer tests like X < 5 split exactly between design voxels."""
        axes = [np.arange(s.start, s.stop) for s in sl]
        if self.res > 1:
            axes = [a / self.res for a in axes]
        return np.meshgrid(*axes, indexing="ij")

    def _centred(self, *arrays):
        """Shifts _coords output so round shapes (tested at each voxel) sit where they do at
        res 1 instead of half a design voxel off; no-op at res 1."""
        o = 0.5 / self.res - 0.5
        return [a + o for a in arrays] if o else list(arrays)

    def _steps(self, a):
        """floor() at voxel resolution, in design units (stair steps of roofs)."""
        return np.floor(a * self.res) / self.res if self.res > 1 else np.floor(a)

    def _paint(self, sl, mask, c: Color, only_empty=False, only_filled=False):
        region = self.v[sl]
        if only_empty:
            mask = mask & (region == 0)
        if only_filled:
            mask = mask & (region != 0)
        region[mask] = self.pal.idx(c)

    # ------------------------------------------------------------ primitives

    def set(self, x: int, y: int, z: int, c: Color):
        if self.res > 1:
            self.box(x, y, z, 1, 1, 1, c)
            return
        W, D, H = self.v.shape
        if 0 <= x < W and 0 <= y < D and 0 <= z < H:
            self.v[x, y, z] = self.pal.idx(c)

    def get(self, x: int, y: int, z: int) -> int:
        """Colour index at a design voxel (its low corner when res > 1)."""
        W, D, H = self.dims
        if 0 <= x < W and 0 <= y < D and 0 <= z < H:
            r = self.res
            return int(self.v[x * r, y * r, z * r])
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
        n = int(np.max(np.abs(p1 - p0)) * self.res) + 1
        for t in np.linspace(0, 1, n):
            p = p0 + (p1 - p0) * t
            if self.res > 1:            # brush follows the line at voxel resolution
                lo = p - r
                self.box(*(np.round(lo * self.res) / self.res), 2 * r + 1, 2 * r + 1, 2 * r + 1, c)
                continue
            px, py, pz = np.round(p).astype(int)
            if r:
                self.box(px - r, py - r, pz - r, 2 * r + 1, 2 * r + 1, 2 * r + 1, c)
            else:
                self.set(px, py, pz, c)

    def ellipsoid(self, cx, cy, cz, rx, ry, rz, c: Color, **kw):
        def fn(X, Y, Z):
            X, Y, Z = self._centred(X, Y, Z)
            return ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2 <= 1.0
        self.where(int(cx - rx), int(cy - ry), int(cz - rz), int(2 * rx + 2), int(2 * ry + 2), int(2 * rz + 2),
                   fn, c, **kw)

    def cylinder(self, cx, cy, z, r, h, c: Color, axis: str = "z", **kw):
        """Cylinder of radius r. For axis='z' the base center is (cx, cy, z);
        for axis 'x'/'y' the arguments are reinterpreted along that axis:
        axis='x': (cy, cz) = (cx, cy), starts at x=z;  axis='y': (cx, cz) = (cx, cy), starts at y=z."""
        r2 = r * r + r * 0.8 / self.res  # slightly fuller circles look better at low res
        R = int(np.ceil(r))
        cen = self._centred
        if axis == "z":
            self.where(int(cx) - R, int(cy) - R, z, 2 * R + 1, 2 * R + 1, h,
                       lambda X, Y, Z: sum((a - b) ** 2 for a, b in zip(cen(X, Y), (cx, cy))) <= r2, c, **kw)
        elif axis == "x":
            self.where(z, int(cx) - R, int(cy) - R, h, 2 * R + 1, 2 * R + 1,
                       lambda X, Y, Z: sum((a - b) ** 2 for a, b in zip(cen(Y, Z), (cx, cy))) <= r2, c, **kw)
        else:
            self.where(int(cx) - R, z, int(cy) - R, 2 * R + 1, h, 2 * R + 1,
                       lambda X, Y, Z: sum((a - b) ** 2 for a, b in zip(cen(X, Z), (cx, cy))) <= r2, c, **kw)

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
        dist = np.minimum(a, span - 1 / self.res - a)  # 0 at eave, grows toward ridge
        surf = z + self._steps(dist * slope)            # underside height of the skin
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
            dist = np.minimum(a, span - 1 / self.res - a)
            return Z < z + self._steps(dist * slope)
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
        last = 1 / self.res                   # distance from a voxel's low corner to the far edge
        if down == "-y":
            a = Y - y
        elif down == "+y":
            a = (y + d - last) - Y
        elif down == "-x":
            a = X - x
        else:
            a = (x + w - last) - X
        surf = z + self._steps(a * slope)
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
        X, Y, Z = self._centred(*self._coords(sl))
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

    # ------------------------------------------------------------ plants: limbs, leafy crowns, trees

    def tube(self, points: Sequence[Sequence[float]], radius, c: Color | Sequence[Color], *, smooth: bool = True,
             only_empty: bool = False):
        """Round limb along a polyline (trunks, branches, roots, pipes). radius is one value or one
        per point (taper). smooth=True runs a Catmull-Rom curve through the points so a limb bends
        instead of kinking. A list of colours gives bark: vertical streaks, 3 voxels tall."""
        pts = np.asarray(points, float).reshape(-1, 3)
        rad = np.broadcast_to(np.asarray(radius, float), (len(pts),)).astype(float)
        if smooth and len(pts) > 2:
            pts, rad = _catmull_rom(pts, rad)
        cols = [c] if c is None or isinstance(c, (str, int)) else list(c)
        ids = np.array([self.pal.idx(k) for k in cols], np.uint8)
        r = self.res
        for a, b, ra, rb in zip(pts[:-1], pts[1:], rad[:-1], rad[1:]):
            lo = np.floor(np.minimum(a, b) - max(ra, rb) - 1)
            sl = self._slices(*lo, *(np.ceil(np.maximum(a, b) + max(ra, rb) + 1) - lo + 1))
            if sl is None:
                continue
            X, Y, Z = self._centred(*self._coords(sl))
            P = np.stack([X, Y, Z], -1)
            d = b - a
            t = np.clip(((P - a) @ d) / max(float(d @ d), 1e-9), 0, 1)
            mask = np.linalg.norm(P - (a + t[..., None] * d), axis=-1) <= ra + (rb - ra) * t
            region = self.v[sl]
            if only_empty:
                mask &= region == 0
            if len(ids) > 1:
                pick = _hash01(np.round(X * r), np.round(Y * r), np.floor(Z * r / 3), 17)
                col = ids[np.minimum((pick * len(ids)).astype(int), len(ids) - 1)]
                region[mask] = col[mask]
            else:
                region[mask] = ids[0]

    def foliage(self, lobes: Sequence[Sequence[float]], colors: Sequence[Color], *, clump: float = 1.8,
                density: float = 1.0, core: Color = None, tips: Color = None, tip_rate: float = 0.15,
                only_empty: bool = True) -> int:
        """Leafy crown in the look of voxel-art trees and bushes: clusters of small leaf clumps.
        Every lobe (cx, cy, cz, r) is covered with sub-lobes about a third its size, and every
        sub-lobe with clumps of radius `clump` (a few voxels each, jagged at the voxel level), so
        the outline is lumpy at several scales instead of a smooth ball; it wobbles around r from
        each lobe's centre (measure r on the reference's outline). Inside, a dark core (the
        darkest colour, or `core`) makes the gaps between clumps read as shadow. colors run from
        dark to light: a voxel is lighter at the top of its clump, on the outside of the crown and
        higher up. tips = optional colour for scattered single cubes on top (bright leaf tips).
        density > 1 packs more clumps. Draw trunk and limbs first; with only_empty the leaves
        grow around them. Returns the number of voxels placed."""
        from scipy.spatial import cKDTree
        rng = self.rng
        lobes = np.asarray(lobes, float).reshape(-1, 4)
        ids = np.array([self.pal.idx(k) for k in colors], np.uint8)
        core_id = self.pal.idx(core) if core is not None else ids[0]
        # sub-lobes spread over each lobe; their centres reach to the lobe's surface, some poke out
        subs = []
        for cx, cy, cz, r in lobes:
            rs = max(r / 2.6, clump * 1.8)
            if rs >= r * 0.75:
                subs.append((cx, cy, cz, r))
                continue
            n = max(4, int(round(density * 2.0 * (r / rs) ** 2)))
            dirs = _sphere_dirs(rng, n)
            rad = rs * rng.uniform(0.75, 1.25, n)
            dist = np.maximum(r - rad - clump * 0.3 + rs * rng.uniform(-0.4, 0.3, n), 0)  # outline wobbles around r
            subs += [(*p, q) for p, q in zip(np.array([cx, cy, cz]) + dirs * dist[:, None], rad)]
            subs.append((cx, cy, cz, max(r - rs * 1.8, rs)))     # fills the middle of the lobe
        subs = np.array(subs, float)
        # clumps over every sub-lobe's surface
        cen, rad = [], []
        for cx, cy, cz, r in subs:
            n = max(5, int(round(density * 2.0 * (r / clump) ** 2)))
            dirs = _sphere_dirs(rng, n)
            rc = clump * rng.uniform(0.75, 1.25, n)
            cen.append(np.array([cx, cy, cz]) + dirs * np.maximum(r - rc * 0.6 - clump * rng.uniform(0, 0.5, n), 0)[:, None])
            rad.append(rc)
        cen, rad = np.concatenate(cen), np.concatenate(rad)
        lo = np.floor(np.minimum(cen.min(0) - rad.max(), (subs[:, :3] - subs[:, 3:]).min(0)) - 1)
        hi = np.ceil(np.maximum(cen.max(0) + rad.max(), (subs[:, :3] + subs[:, 3:]).max(0)) + 1)
        sl = self._slices(*lo, *(hi - lo + 1))
        if sl is None:
            return 0
        X, Y, Z = self._centred(*self._coords(sl))
        P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        region = self.v[sl]
        free = (region == 0).ravel() if only_empty else np.ones(P.shape[0], bool)
        # dark core: the sub-lobes shrunk by about a clump
        d_sub, i_sub = cKDTree(subs[:, :3]).query(P, k=min(4, len(subs)))
        d_sub, i_sub = d_sub.reshape(len(P), -1), i_sub.reshape(len(P), -1)
        in_core = (d_sub <= np.maximum(subs[i_sub, 3] - clump * 1.4, 0.8)).any(axis=1)
        # clumps: inside when within the clump's radius, with a jagged voxel-level edge
        d, i = cKDTree(cen).query(P, k=min(3, len(cen)))
        d, i = d.reshape(len(P), -1), i.reshape(len(P), -1)
        jag = 1 + 0.28 * (_hash01(*(np.round(P * self.res).T), 5) - 0.5) * 2
        inside = d <= rad[i] * jag[:, None]
        hit = inside.any(axis=1)
        k = np.where(inside, d / rad[i], np.inf).argmin(axis=1)            # the clump each voxel belongs to
        c = cen[i[np.arange(len(P)), k]]
        rc = rad[i[np.arange(len(P)), k]]
        top = (P[:, 2] - c[:, 2]) / rc                                       # -1 under its clump .. 1 on top
        out = np.linalg.norm(c - subs[i_sub[:, 0], :3], axis=1) / subs[i_sub[:, 0], 3]   # outer clumps lighter
        zl, zh = (cen[:, 2] - rad).min(), (cen[:, 2] + rad).max()
        h = (P[:, 2] - zl) / max(zh - zl, 1e-6)
        t = 0.55 * top + 0.45 * (out - 0.6) + 0.35 * (h - 0.5) + 0.3 * (_hash01(*(np.round(P * self.res).T), 9) - 0.5)
        shade = ids[np.clip(np.floor((t + 0.75) / 1.5 * len(ids)), 0, len(ids) - 1).astype(int)]
        val = np.where(hit, shade, np.where(in_core, core_id, 0)).astype(np.uint8)
        put = (val > 0) & free
        new = region.reshape(-1).copy()
        new[put] = val[put]
        new = new.reshape(region.shape)
        if tips is not None:          # single bright cubes on the top surface of the leaves
            leaf = np.isin(new, ids) & (new != region)
            top_free = np.zeros_like(leaf)
            top_free[:, :, :-1] = new[:, :, 1:] == 0
            pick = leaf & top_free & (rng.random(leaf.shape) < tip_rate)
            new[pick] = self.pal.idx(tips)
        region[...] = new
        return int(put.sum())

    def crown_depth(self, lobes: Sequence[Sequence[float]], x: float, y: float, view: dict, *,
                    fill: float = 1.0) -> list:
        """Lobes measured on the reference all lie in one plane: the vertical plane through the
        trunk at (x, y) that faces the camera of `view`. That outline is right from the front but
        flat from the side. This turns them into a round crown with the same outline: it fits the
        upright ellipsoid whose outline from `view` has the measured width and height (round seen
        from above when the outline allows it), then places copies of every lobe along that
        lobe's own line of sight, wherever the line runs inside the ellipsoid. Moving along the
        line of sight keeps the outline from the reference's side exactly; staying inside the
        ellipsoid keeps the crown round and upright from every other side. fill < 1 spaces the
        copies further apart. Pass the result to foliage() or tree(lobes=...). Never fill a
        crown's outline with a flat layer of voxels, or copy lobes along the line of sight
        without such a bound - that gives the flat or tilted boards this replaces."""
        rng = self.rng
        a, e = np.radians(view.get("azimuth", 30)), np.radians(view.get("elevation", 30))
        right, back = np.array([np.cos(a), -np.sin(a)]), np.array([np.sin(a), np.cos(a)])
        ce, se = np.cos(e), np.sin(e)
        L = np.asarray(lobes, float).reshape(-1, 4)
        rel = L[:, :2] - [x, y]
        u, s0, r = rel @ right, rel @ back, L[:, 3]
        v = L[:, 2] * ce + s0 * se                     # screen height of each lobe (voxel units)
        # lobes whose outlines touch form one cluster (a tier, a cluster on a branch, the whole
        # crown of a cypress); each cluster gets its own ellipsoid, so gaps between tiers stay open
        group = np.arange(len(L))
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                if np.hypot(u[i] - u[j], v[i] - v[j]) < (r[i] + r[j]) * 0.95:
                    gi, gj = group[i], group[j]
                    group[group == gj] = gi
        out = []
        for g in np.unique(group):
            k = group == g
            out += self._depth_cluster(x, y, right, back, ce, se, u[k], s0[k], L[k, 2], r[k], fill, rng)
        return out

    @staticmethod
    def _depth_cluster(x, y, right, back, ce, se, u, s0, z, r, fill, rng) -> list:
        """crown_depth() for one cluster of touching lobes (screen coords u, depth s0, height z)."""
        v = z * ce + s0 * se
        uc, A = ((u - r).min() + (u + r).max()) / 2, ((u + r).max() - (u - r).min()) / 2
        vc, h = ((v - r).min() + (v + r).max()) / 2, ((v + r).max() - (v - r).min()) / 2
        # ellipsoid semi-axes: A across, B in depth, C up; its outline is A wide and
        # sqrt((C cos e)^2 + (B sin e)^2) high. Prefer B = A (round from above).
        B, C = A, np.sqrt(max(h ** 2 - (A * se) ** 2, 0.0)) / max(ce, 1e-6)
        if C < 0.45 * h / max(ce, 1e-6):                # outline too low for a round crown: shallower
            C = 0.45 * h / max(ce, 1e-6)
            B = np.sqrt(max(h ** 2 - (C * ce) ** 2, 0.0)) / max(se, 1e-6) if se > 1e-3 else A
        zc = vc / max(ce, 1e-6)                          # centre on the trunk's plane (s = 0)
        out = []
        for ui, si, zi, ri in zip(u, s0, z, r):
            a2, b2, c2 = (max(q - ri * 0.6, ri * 0.5) for q in (A, B, C))   # keep whole lobes inside
            # point on the line of sight: (ui, si + t ce, zi - t se); inside where q(t) <= 0
            qa = (ce / b2) ** 2 + (se / c2) ** 2
            qb = 2 * (si * ce / b2 ** 2 - (zi - zc) * se / c2 ** 2)
            qc = ((ui - uc) / a2) ** 2 + (si / b2) ** 2 + ((zi - zc) / c2) ** 2 - 1
            disc = qb ** 2 - 4 * qa * qc
            if disc <= 0:
                ts = np.array([0.0])                     # the line misses the ellipsoid: keep the lobe
            else:
                t1, t2 = (-qb - np.sqrt(disc)) / (2 * qa), (-qb + np.sqrt(disc)) / (2 * qa)
                step = max(ri * 1.1 / max(fill, 0.1), 1.0)
                n = max(1, int((t2 - t1) // step) + 1)
                ts = (t1 + t2) / 2 + (np.arange(n) - (n - 1) / 2) * step
            for t in ts:
                p = np.array([x, y]) + right * ui + back * (si + t * ce)
                out.append((p[0], p[1], zi - t * se + rng.normal(0, ri * 0.1), ri * rng.uniform(0.88, 1.0)))
        return out

    def tree(self, x: float, y: float, z: float, height: float, leaves: Sequence[Color],
             bark: Color | Sequence[Color], *, style: str = "round", width: float | None = None,
             trunk: tuple[float, float] | None = None, lobes: Sequence[Sequence[float]] | None = None,
             lean: tuple[float, float] = (0.0, 0.0), roots: bool = True, limbs: bool = True,
             clump: float = 1.8, density: float = 1.0, tips: Color = None, view: dict | None = None) -> dict:
        """A whole tree standing at (x, y, z): trunk with a root flare, a limb into each lobe of the
        crown, and a foliage() crown. Give the crown's lobes yourself as (cx, cy, cz, r) - for
        example read off the reference, then also pass the reference's `view` so they are spread
        through the crown's depth (crown_depth) - or let `style` lay them out: 'round', 'column'
        (cypress), 'cone' (fir), 'tiered' (crown in separate layers), 'branched' (round clusters on
        side limbs) or 'spread' (wide flat dome). width = crown diameter (default from style and
        height); trunk = (radius at the foot, radius at the top); lean = (dx, dy) of the top.
        Returns {'trunk': points, 'lobes': lobes} for further detail."""
        rng = self.rng
        H = float(height)
        W = float(width) if width else H * {"column": 0.28, "cone": 0.42, "spread": 0.8}.get(style, 0.5)
        r0, r1 = trunk if trunk else (max(1.0, H * 0.045), max(0.6, H * 0.016))
        foot = np.array([x, y, z], float)
        tip = foot + np.array([lean[0], lean[1], H * 0.92])
        axis = lambda f: foot + (tip - foot) * f                                        # noqa: E731
        if lobes is None:
            lobes = _crown_lobes(style, axis, H, W, rng)
        lobes = [tuple(map(float, lb)) for lb in lobes]
        crown = self.crown_depth(lobes, x, y, view) if view is not None else lobes   # limbs go to `lobes` only
        top = max(crown, key=lambda lb: lb[2] + lb[3])          # the trunk ends inside the highest lobe
        f_top = float(np.clip((top[2] - top[3] * 0.3 - foot[2]) / (tip[2] - foot[2]), 0.3, 1.0))
        stem = [axis(f) + np.r_[rng.normal(0, H * 0.012, 2), 0] * (0 < f < f_top)
                for f in np.linspace(0, f_top, 6)]
        self.tube(stem, np.linspace(r0, r1, len(stem)), bark)
        if roots:
            for a in rng.uniform(0, 2 * np.pi) + np.arange(5) * 2 * np.pi / 5:
                d = np.array([np.cos(a), np.sin(a), 0.0])
                self.tube([foot + [0, 0, r0 * 2.2], foot + d * r0 * 1.6 + [0, 0, r0 * 0.6], foot + d * r0 * 2.8],
                          [r0 * 0.75, r0 * 0.5, r0 * 0.3], bark)
        if limbs:              # about one limb per lobe given, spread through the crown's depth
            z0 = stem[1][2]
            for cx, cy, cz, r in crown[::max(1, len(crown) // len(lobes))]:
                f = float(np.clip((cz - r * 0.9 - foot[2]) / max(tip[2] - foot[2], 1e-6), (z0 - foot[2]) / H, 0.95))
                start = axis(f)
                end = np.array([cx, cy, cz])
                if np.linalg.norm(end - start) < r * 0.6:
                    continue
                mid = start + (end - start) * 0.55 + [0, 0, r * 0.3]
                self.tube([start, mid, end], [r0 * 0.55, r0 * 0.4, r0 * 0.25], bark)
        self.foliage(crown, leaves, clump=clump, density=density, tips=tips)
        return {"trunk": [tuple(p) for p in stem], "lobes": [tuple(map(float, lb)) for lb in crown]}

    def carve_to_reference(self, reference: str, view: dict, *, only=None, margin: float = 0.5,
                           cutout: dict | None = None) -> int:
        """Removes the voxels the reference shows as background: seen through `view`, with the
        model's outline scaled to the reference's height and centred on it, any voxel whose centre
        lands outside the reference's cutout (grown by `margin` voxels) is cut. Good for organic
        outlines (crowns, bushes, rocks) that primitives only approximate. Get the camera and the
        overall proportions right first (fit-camera, then a score with few red/blue areas): a wrong
        camera or height cuts real parts. only = colour name(s) that may be cut (e.g. the leaves,
        to keep a trunk or base intact). Returns the number of voxels removed."""
        from scipy import ndimage
        from .score import reference_transform
        emissive = {i for i in self.pal.materials if self.pal.is_emissive(i)}
        ref, cam, to_px, px_per_voxel = reference_transform(
            self.v, self.pal.rgba, emissive, reference, view, cutout_kw=cutout,
            cache_dir=os.path.join(os.getcwd(), "output", "_ref"), by="bbox")
        near = ndimage.distance_transform_edt(ref[..., 3] <= 127) <= max(margin * px_per_voxel, 0.5)
        pts = np.argwhere(self.v > 0)
        if only is not None:
            names = [only] if isinstance(only, (str, int)) else list(only)
            pts = pts[np.isin(self.v[tuple(pts.T)], [self.pal.idx(c) for c in names])]
        if not len(pts):
            return 0
        px = np.floor(to_px(cam.project(pts + 0.5))).astype(np.int64)
        H, W = near.shape
        ok = (px[:, 0] >= 0) & (px[:, 0] < W) & (px[:, 1] >= 0) & (px[:, 1] < H)
        keep = np.zeros(len(pts), bool)
        keep[ok] = near[px[ok, 1], px[ok, 0]]
        cut = pts[~keep]
        self.v[tuple(cut.T)] = 0
        return len(cut)

    # ------------------------------------------------------------ loose pieces

    def _components(self):
        """For every object (each part, or the whole model): (part name, low corner, component
        labels over its bounding box, voxels per label, label of the biggest one = its body)."""
        from scipy import ndimage
        for part, mask in (self._part_masks() if self.part_names else [("model", self.v > 0)]):
            xs, ys, zs = np.nonzero(mask)
            if not len(xs):
                continue
            lo = np.array([xs.min(), ys.min(), zs.min()])
            sl = tuple(slice(a, b + 1) for a, b in zip(lo, (xs.max(), ys.max(), zs.max())))
            labels, n = ndimage.label(mask[sl], structure=np.ones((3, 3, 3), bool))   # edges/corners connect
            sizes = np.bincount(labels.ravel(), minlength=n + 1)
            sizes[0] = 0
            yield part, lo, labels, sizes, int(sizes.argmax())

    def loose_pieces(self) -> list[dict]:
        """Groups of voxels that touch nothing else of their object (each part is its own
        object; touching by an edge or a corner counts). The biggest group of an object is its
        body and isn't listed. Specks left by carving, a crown that misses its trunk or a roof
        hovering over its walls show up here - and so does anything meant to float (sparks, a
        separate prop that belongs in its own part()). Returns [{"part", "voxels", "at"}],
        biggest first; "at" is the piece's centre in design units."""
        from scipy import ndimage
        out = []
        for part, lo, labels, sizes, body in self._components():
            loose = [k for k in range(1, len(sizes)) if k != body]
            if not loose:
                continue
            centres = ndimage.center_of_mass(labels > 0, labels, loose)
            for k, c in zip(loose, centres):
                at = (np.array(c) + lo + 0.5) / self.res
                out.append({"part": part, "voxels": int(sizes[k]), "at": tuple(round(float(q), 1) for q in at)})
        return sorted(out, key=lambda p: -p["voxels"])

    def remove_loose(self, max_voxels: float | None = 8) -> int:
        """Deletes loose pieces (see loose_pieces) of at most max_voxels design voxels (res³
        voxels each, so the same call works at any res); None deletes every loose piece, which
        also drops separate objects that aren't in their own part(). Call it after carving and
        before paint_reference. Returns the number of voxels removed."""
        removed = 0
        for _, lo, labels, sizes, body in self._components():
            small = np.ones(len(sizes), bool) if max_voxels is None else sizes <= max_voxels * self.res ** 3
            small[[0, body]] = False
            cut = small[labels]
            if cut.any():
                idx = np.argwhere(cut) + lo
                self.v[tuple(idx.T)] = 0
                removed += len(idx)
        return removed

    # ------------------------------------------------------------ damage

    def damage(self, level: float = 1.0, *, seed: int = 0, debris: float = 0.35, scorch: bool = True) -> dict:
        """Wrecks the model in place for damaged / ruined variants (game assets that swap from
        intact to broken). level 1 = chipped edges, a few holes and cracks; 2 = bigger holes, more
        cracks; 3 = a caved-in top as well. Sizes follow the model's size, so it looks the same
        at any res. Pieces left floating fall as rubble, and part of what breaks off lies in piles
        on the ground (`debris` = share kept); scorch darkens the broken edges. Glowing colours
        are only removed, never darkened. Returns counts of what happened."""
        from scipy import ndimage
        rng = np.random.default_rng(seed)
        v = self.v
        filled = v > 0
        if not filled.any() or level <= 0:
            return {"removed": 0, "debris": 0}
        before = v.copy()
        xs, ys, zs = np.nonzero(filled)
        lo, hi = np.array([xs.min(), ys.min(), zs.min()]), np.array([xs.max(), ys.max(), zs.max()])
        size = float((hi - lo).max() + 1)
        ground = int(zs.min())
        nb = sum(_shift_fill(filled, d) for d in _DIRS6)            # filled neighbours per voxel
        exposed = filled & (nb < 6)
        # 1. chipped edges and corners: voxels with three or more open sides
        chip = filled & (nb <= 3) & (rng.random(v.shape) < min(0.12 * level, 0.6))
        chip[:, :, ground] = False
        v[chip] = 0
        # 2. holes: noisy balls carved around surface points (not in the bottom layer)
        cand = np.argwhere(exposed & (np.arange(v.shape[2])[None, None, :] > ground + 1))
        holes = []
        if len(cand):
            for _ in range(int(round(level * (2 + size / 40)))):
                c = cand[rng.integers(len(cand))]
                r = size * rng.uniform(0.03, 0.05 + 0.02 * level)
                holes.append((c, r))
                self._carve_ball(c, r, rng)
        # 3. a caved-in top for heavy damage
        if level >= 2.5:
            top = cand[cand[:, 2] >= lo[2] + 0.7 * (hi[2] - lo[2])] if len(cand) else cand
            if len(top):
                c = top[rng.integers(len(top))]
                r = size * 0.2 * min(level / 3, 1.5)
                holes.append((c, r))
                self._carve_ball(c, r, rng, squash=0.7)
        # 4. cracks: short walks over the surface, mostly up and down, each step carved or darkened
        crack_id = self._damage_colour("crack", "#2b2724")
        cracked = np.zeros(v.shape, bool)
        surf = np.argwhere((v > 0) & (sum(_shift_fill(v > 0, d) for d in _DIRS6) < 6))
        for _ in range(int(round(level * (3 + size / 25)))) if len(surf) else []:
            p = surf[rng.integers(len(surf))].astype(float)
            step = np.array([rng.normal(0, 0.5), rng.normal(0, 0.5), rng.choice([-1.0, 1.0])])
            for _ in range(int(size * rng.uniform(0.08, 0.2))):
                q = np.round(p).astype(int)
                if not (np.all(q >= 0) and np.all(q < v.shape)) or v[tuple(q)] == 0:
                    break
                cracked[tuple(q)] = True
                p += step / np.linalg.norm(step)
                step += rng.normal(0, 0.35, 3)
        v[cracked & (rng.random(v.shape) < 0.5)] = 0
        v[cracked & (v > 0)] = crack_id
        # 5. pieces the damage cut off from the ground fall and become rubble (touching edges or
        #    corners counts as connected; decorations that were never connected stay put)
        def grounded(a):
            labels, _ = ndimage.label(a, structure=np.ones((3, 3, 3), bool))
            return np.isin(labels, list(set(np.unique(labels[:, :, ground])) - {0}))
        floating = (v > 0) & ~grounded(v > 0) & grounded(before > 0)
        fallen = np.argwhere(floating)
        fallen_col = v[floating]
        v[floating] = 0
        # 6. rubble: part of what broke off lies in piles below where it came from
        broken = np.argwhere((before > 0) & (v == 0))
        cols = before[tuple(broken.T)]
        keep = rng.random(len(broken)) < debris
        pieces = np.concatenate([broken[keep], fallen]) if len(fallen) else broken[keep]
        piece_col = np.concatenate([cols[keep], fallen_col]) if len(fallen) else cols[keep]
        centre = (lo + hi) / 2
        placed = 0
        for (px, py, _), col in zip(pieces, piece_col):
            out = np.array([px, py], float) - centre[:2]
            out = out / (np.linalg.norm(out) + 1e-6) * rng.uniform(0, 3)       # rolls away from the middle
            x = int(round(px + out[0] + rng.normal(0, 1.5)))
            y = int(round(py + out[1] + rng.normal(0, 1.5)))
            if not (0 <= x < v.shape[0] and 0 <= y < v.shape[1]):
                continue
            column = np.nonzero(v[x, y, ground:])[0]
            z = ground + (column.max() + 1 if len(column) else 0)
            if z < v.shape[2]:
                v[x, y, z] = col
                placed += 1
        # 7. scorch: darken what lies next to the holes and cracks
        if scorch:
            hurt = ndimage.binary_dilation((before > 0) & (v == 0) | cracked, iterations=max(1, int(size / 40)))
            near = hurt & (v > 0) & (v != crack_id)
            for c in np.unique(v[near]):
                if self.pal.is_emissive(int(c)):
                    continue
                dark = self._damage_colour(f"{self._name_of(int(c))}_burnt",
                                           "#%02x%02x%02x" % tuple(int(k * 0.55) for k in self.pal.rgba[c][:3]))
                sel = near & (v == c) & (rng.random(v.shape) < 0.6)
                v[sel] = dark
        return {"removed": int(((before > 0) & (v == 0)).sum()), "debris": placed, "holes": len(holes),
                "fallen": int(len(fallen))}

    def _carve_ball(self, c, r, rng, squash: float = 1.0):
        """Carves a noisy ball of radius r (voxels) around voxel c; squash < 1 flattens it."""
        R = int(np.ceil(r * 1.3))
        sl = tuple(slice(max(int(k) - R, 0), min(int(k) + R + 1, n)) for k, n in zip(c, self.v.shape))
        X, Y, Z = np.meshgrid(*(np.arange(s.start, s.stop) for s in sl), indexing="ij")
        d = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2 + ((Z - c[2]) / squash) ** 2) / max(r, 0.5)
        self.v[sl][d + rng.uniform(-0.25, 0.25, X.shape) <= 1] = 0

    def _damage_colour(self, name: str, hex_color: str) -> int:
        if name in self.pal.names:
            return self.pal.names[name]
        if self.pal._next > 255:                      # palette full: the darkest existing colour
            used = [i for i in self.pal.names.values()]
            return min(used, key=lambda i: int(self.pal.rgba[i][:3].sum()))
        return self.pal.add(name, hex_color)

    def _name_of(self, idx: int) -> str:
        return next((n for n, i in self.pal.names.items() if i == idx), str(idx))

    # ------------------------------------------------------------ colours from the reference

    def paint_reference(self, reference: str, view: dict, *, colors: int = 96, tol: float | None = 30.0,
                        only=None, blend: float = 1.0, cutout: dict | None = None) -> int:
        """Colours every voxel the reference image shows with the reference's own pixels, seen
        through `view` (the camera the reference was drawn from: VIEW / SCORE_VIEW after
        fit-camera) with the score's alignment. Shading, stains, patterns and gradients then come
        from the picture instead of hand-placed voxels, and get finer with res. Call it last, once
        the shape is final; voxels the reference doesn't show keep their colours.
        tol = largest colour change a voxel accepts (CIE Lab distance with lightness counted at
        half), so where the shape is a little off a wall doesn't take the colour of the bush in
        front of it, while shade and highlights still come through (None = accept everything).
        colors = palette entries for the painted colours, shared out per original colour by voxel
        count and named <colour>_r1, <colour>_r2, ... (capped by the free slots). only = colour
        name(s) that may be repainted (default: everything except glowing colours); blend < 1
        mixes with the current colours; cutout = the script's CUTOUT. Returns voxels painted."""
        from .score import _lab, reference_colors
        emissive = [i for i in self.pal.materials if self.pal.is_emissive(i)]
        coords, rgb = reference_colors(self.v, self.pal.rgba, set(emissive), reference, view, cutout_kw=cutout,
                                       cache_dir=os.path.join(os.getcwd(), "output", "_ref"))
        cur = self.v[tuple(coords.T)]
        base = self.pal.rgba[cur, :3].astype(np.float64)
        ok = ~np.isin(cur, emissive)
        if only is not None:
            names = [only] if isinstance(only, (str, int)) else list(only)
            ok &= np.isin(cur, [self.pal.idx(c) for c in names])
        if tol is not None:     # lightness counts half: shade and highlights change it, a wrong material changes hue
            d = _lab(rgb) - _lab(base)
            ok &= np.sqrt((d[:, 0] / 2) ** 2 + d[:, 1] ** 2 + d[:, 2] ** 2) <= tol
        coords, rgb, cur, base = coords[ok], rgb[ok], cur[ok], base[ok]
        if not len(cur):
            return 0
        if blend < 1:
            rgb = blend * rgb + (1 - blend) * base
        budget = min(colors, 256 - self.pal._next)
        if budget < 1:
            raise ValueError("palette full: paint_reference needs free colour slots (255 at most)")
        names = {i: n for n, i in self.pal.names.items()}
        groups, counts = np.unique(cur, return_counts=True)
        top = np.argsort(-counts)[:budget]           # fewer slots than colours: the smallest stay unpainted
        groups, counts = groups[top], counts[top]
        shares = np.maximum(1, np.floor(budget * counts / counts.sum())).astype(int)
        while shares.sum() > budget:
            shares[np.argmax(shares)] -= 1
        painted = 0
        for g, n in zip(groups, shares):
            sel = cur == g
            idx, pal = quantize(rgb[sel], int(n))
            lut, j = [], 0
            for c in pal:
                j += 1
                while f"{names.get(int(g), g)}_r{j}" in self.pal.names:
                    j += 1
                lut.append(self.pal.add(f"{names.get(int(g), g)}_r{j}", "#%02x%02x%02x" % tuple(int(k) for k in c),
                                        **self.pal.material_args(int(g))))
            self.v[tuple(coords[sel].T)] = np.array(lut, np.uint8)[idx]
            painted += int(sel.sum())
        return painted

    # ------------------------------------------------------------ importing .vox files

    @classmethod
    def from_vox(cls, path: str, *, seed: int = 0, prefix: str = "v", res: int = 1) -> "Model":
        """New model holding a .vox file (a base made by `voxtool extrude/carve`, or a
        model edited in MagicaVoxel) to add details to with the DSL. With res > 1 each
        voxel of the file becomes a res x res x res block."""
        src = merge_models(read_vox(path))
        m = cls(*src.shape, seed=seed, res=res)
        m.paste_vox(path, prefix=prefix)
        return m

    def paste_vox(self, path: str, x: int = 0, y: int = 0, z: int = 0, *, prefix: str = "v") -> dict[int, str]:
        """Pastes a .vox at (x, y, z) (non-empty voxels only, clipped to the grid; each file voxel
        becomes one design voxel). Its colours join the palette as <prefix><index>, reusing a
        palette entry with the same colour and material; materials (glow, glass, metal) are kept.
        Returns {file index: palette name}."""
        scene = read_vox(path)
        src = merge_models(scene)
        r = self.res
        if r > 1:
            src = src.repeat(r, 0).repeat(r, 1).repeat(r, 2)
            x, y, z = x * r, y * r, z * r
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
        r = self.res
        x0, x1 = x0 * r, x1 * r
        W = self.v.shape[0]
        src = self.v[x0:x1]
        np.copyto(self.v[W - x1:W - x0], src[::-1], where=src[::-1] > 0)

    def copy(self, x, y, z, w, d, h, dx, dy, dz):
        """Copies a box region to an offset (non-empty voxels only)."""
        sl = self._slices(x, y, z, w, d, h)
        if sl is None:
            return
        r = self.res
        src = self.v[sl].copy()
        xs, ys, zs = np.nonzero(src)
        dst = np.stack([xs + sl[0].start + round(dx * r), ys + sl[1].start + round(dy * r),
                        zs + sl[2].start + round(dz * r)])
        ok = np.all((dst >= 0) & (dst < np.array(self.v.shape)[:, None]), axis=0)
        self.v[tuple(dst[:, ok])] = src[xs[ok], ys[ok], zs[ok]]

    # ------------------------------------------------------------ parts

    @contextmanager
    def part(self, name: str):
        """Voxels changed inside `with m.part(name):` are saved as their own named
        object in the .vox (kit sheets: each piece can be selected and moved on its
        own in MagicaVoxel). Voxels never touched inside a part block go to 'rest'.
        Without any part the file holds one object, as before."""
        if len(self.part_names) >= 255:
            raise ValueError("too many parts (255)")
        if self.labels is None:
            self.labels = np.zeros(self.v.shape, np.uint8)
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
        res = f" (res {self.res}: design grid {self.dims})" if self.res > 1 else ""
        out = (f"grid {self.v.shape}{res}, voxels {int(filled.sum())}, "
               f"bbox x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}] z[{zs.min()},{zs.max()}]\n"
               f"colors: {counts}")
        if self.part_names:
            out += "\nparts: " + ", ".join(f"{n}={int(mk.sum())}" for n, mk in self._part_masks())
        tiles = sum(1 for m in self.to_scene().models if m.group) if max(self.v.shape) > MAX_DIM else 0
        if tiles:
            out += f"\nsaved as {tiles} tiles of at most {MAX_DIM} per axis (objects over {MAX_DIM} are split)"
        return out

    def to_scene(self) -> VoxScene:
        """One object per part ('rest' holds voxels drawn outside parts), or the whole grid
        without parts. An object over MAX_DIM per axis is cut into tiles of at most MAX_DIM,
        kept together in a MagicaVoxel group named after it."""
        if not self.part_names:
            models = split_grid(self.v)
        else:
            models = []
            for name, mk in self._part_masks():
                xs, ys, zs = np.nonzero(mk)
                lo = (int(xs.min()), int(ys.min()), int(zs.min()))
                sl = (slice(lo[0], xs.max() + 1), slice(lo[1], ys.max() + 1), slice(lo[2], zs.max() + 1))
                models += split_grid(np.where(mk[sl], self.v[sl], 0).astype(np.uint8), lo, name)
        return VoxScene(models, self.pal.rgba.copy(), dict(self.pal.materials))

    def save(self, path: str) -> str | None:
        """Writes the .vox. If the existing file was saved by MagicaVoxel (hand edits),
        it is first copied to <name>_edited_<time>.vox; returns that backup path."""
        scene = self.to_scene()             # size checks first, so a failed save backs up nothing
        backup = backup_if_edited(path)
        write_vox(path, scene)
        return backup


# ---------------------------------------------------------------- helpers for plants

def _hash01(a, b, c, salt: int = 0) -> np.ndarray:
    """Deterministic pseudo-random value in [0, 1) per integer coordinate triple."""
    u = lambda v: np.asarray(v).astype(np.int64).astype(np.uint64)                    # noqa: E731
    h = (u(a) * np.uint64(73856093)) ^ (u(b) * np.uint64(19349663)) ^ (u(c) * np.uint64(83492791)) \
        ^ np.uint64((salt * 2654435761) % 2 ** 32)
    return ((h * np.uint64(2654435761)) % np.uint64(2 ** 32)).astype(np.float64) / 2 ** 32


def _sphere_dirs(rng, n: int) -> np.ndarray:
    """n unit vectors spread evenly over a sphere (Fibonacci lattice), turned and jittered at random."""
    k = np.arange(n) + 0.5
    z = 1 - 2 * k / n
    a = np.pi * (1 + 5 ** 0.5) * k + rng.uniform(0, 2 * np.pi)
    r = np.sqrt(np.maximum(1 - z ** 2, 0))
    d = np.stack([r * np.cos(a), r * np.sin(a), z], 1) + rng.normal(0, 0.15, (n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _catmull_rom(pts: np.ndarray, rad: np.ndarray, step: float = 1.5):
    """Points (and radii, linearly) along a Catmull-Rom curve through pts, about `step` apart."""
    P = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    out_p, out_r = [], []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = P[i:i + 4]
        n = max(2, int(np.ceil(np.linalg.norm(p2 - p1) / step)))
        t = np.linspace(0, 1, n, endpoint=False)[:, None]
        out_p.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                            + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
        out_r.append(rad[i] + (rad[i + 1] - rad[i]) * t[:, 0])
    out_p.append(pts[-1:])
    out_r.append(rad[-1:])
    return np.vstack(out_p), np.concatenate(out_r)


def _crown_lobes(style: str, axis, H: float, W: float, rng) -> list:
    """Lobes (cx, cy, cz, r) for tree(style=...); axis(f) is the point at fraction f up the trunk."""
    R = W / 2
    out = []

    def ring(f, dist, r_lobe, n):
        c = axis(f)
        for a in rng.uniform(0, 2 * np.pi) + np.arange(n) * 2 * np.pi / n:
            d = dist * rng.uniform(0.85, 1.15)
            out.append((c[0] + d * np.cos(a), c[1] + d * np.sin(a), c[2] + rng.normal(0, r_lobe * 0.25),
                        r_lobe * rng.uniform(0.85, 1.15)))

    if style == "round":
        c = axis(0.66)
        out.append((*c, R * 0.7))
        for d in _sphere_dirs(rng, 10):
            out.append((*(c + d * np.array([R * 0.55, R * 0.55, H * 0.2])), R * 0.45))
    elif style in ("column", "cone"):
        f0 = 0.14 if style == "column" else 0.18
        n = max(4, int(round((0.97 - f0) * H / (R * 0.8))))
        for f in np.linspace(f0, 0.97, n):
            t = (f - f0) / (0.97 - f0)
            prof = np.sin(np.pi * min(1.0, 0.15 + t)) ** 0.6 if style == "column" else 0.95 * (1 - t) ** 0.9 + 0.05
            rr = max(R * prof, R * 0.25)
            out.append((*axis(f), rr * 0.85))
            if rr > R * 0.4:
                ring(f, rr * 0.45, rr * 0.55, 3)
    elif style == "tiered":                       # layers small enough to leave the trunk showing between them
        gap = 0.24 * H
        for j in range(3):
            f, rr = 0.3 + j * 0.24, R * (1 - 0.22 * j)
            r_l = min(rr * 0.4, gap * 0.42)
            out.append((*axis(f), r_l))
            ring(f, rr * 0.6, r_l, 5)
        out.append((*axis(0.97), min(R * 0.3, gap * 0.4)))
    elif style == "branched":
        a = rng.uniform(0, 2 * np.pi)
        for j in range(6):
            f = 0.35 + 0.55 * j / 5
            c, d = axis(f), R * (0.8 - 0.35 * j / 6)
            out.append((c[0] + d * np.cos(a), c[1] + d * np.sin(a), c[2] + R * 0.2, R * (0.42 - 0.12 * j / 6)))
            a += np.pi * rng.uniform(0.6, 1.0)
        out.append((*axis(0.97), R * 0.38))
    elif style == "spread":
        c = axis(0.72)
        for d in _sphere_dirs(rng, 14):
            d[2] = abs(d[2]) * 0.5
            out.append((*(c + d * np.array([R * 0.75, R * 0.75, H * 0.12])), R * 0.32))
        out.append((*c, R * 0.45))
    else:
        raise ValueError(f"unknown tree style {style!r}: round, column, cone, tiered, branched or spread")
    return out


_DIRS6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _shift_fill(a: np.ndarray, d) -> np.ndarray:
    """out[p] = a[p + d] as int (0 outside the grid), for counting filled neighbours."""
    out = np.zeros(a.shape, np.int8)
    src = tuple(slice(max(k, 0), a.shape[i] + min(k, 0)) for i, k in enumerate(d))
    dst = tuple(slice(max(-k, 0), a.shape[i] + min(-k, 0)) for i, k in enumerate(d))
    out[dst] = a[src]
    return out
