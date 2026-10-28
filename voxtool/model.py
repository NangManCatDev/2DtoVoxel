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
