# Writing model scripts

**English** | [한국어](model-scripts.ko.md) · ← [Back to README](../README.md)

Every model is a Python file in `models/`. Claude writes and edits these scripts, and you can do the same: the `.vox` is always rebuilt from the script.

## What a script contains

| Name | Required | Meaning |
|---|---|---|
| `NAME` | yes | Output folder and file name |
| `build()` | yes | Returns a `Model` |
| `REFERENCE` | no | Path to the reference image; enables the comparison image and the score |
| `VIEW` | no | Preview camera, e.g. `{"azimuth": 36, "elevation": 18, "fov": 0}`. Azimuth 0 looks straight at the front, 90 at the left side; `fov` > 0 is a perspective camera |
| `SCORE_VIEW` | no | Camera used for scoring if it differs from `VIEW` (conversions score from the front) |
| `CUTOUT` | no | Background-removal settings, e.g. `{"keep": "all"}` for a sheet with several objects |

## Coordinates

`x` goes right, `y` goes into the scene (**`y = 0` is the front**, the side MagicaVoxel's default camera looks at), and `z` goes up. Boxes are given as position + size: `box(x, y, z, w, d, h, color)` fills `x … x+w-1` and so on. Anything outside the grid is clipped. A `region=` argument is always `(x, y, z, w, d, h)`. Each saved object can be at most 256 voxels per axis, with up to 255 colours.

## Example

```python
from voxtool import Model

NAME = "tiny_hut"
VIEW = {"azimuth": 36, "elevation": 20}


def build() -> Model:
    m = Model(40, 34, 32, seed=1)                  # grid size: x (width), y (depth), z (height)
    m.pal.add("wall", "#dcc3a0"); m.pal.add("wall2", "#d2b893")
    m.pal.add("roof", "#0b8691"); m.pal.add("roof_hi", "#1ba3ad")
    m.pal.add("door", "#8c2b22"); m.pal.add("glass", "#8a8094")
    m.pal.add("lamp", "#ffd84a", emit=4)            # glows in MagicaVoxel's Render tab
    m.pal.add("leaf", "#2c5a19"); m.pal.add("leaf2", "#3d7524")

    m.shell(6, 8, 0, 28, 18, 16, "wall", t=2, top=False)          # walls, y=8 is the front face
    m.bricks(["wall", "wall2"], target="wall", bw=6, bh=3)       # stone-block texture
    roof = (4, 6, 16, 32, 22)                                     # footprint x, y, z, w, d
    m.gable_wall(*roof, "x", "wall", region=(6, 8, 28, 18))       # gable ends under the roof
    m.gable_roof(*roof, "x", ["roof_hi", "roof"], t=2)            # ridge along x, striped planks
    m.box(17, 8, 0, 6, 2, 10, "door")                             # door, 2 deep
    m.box(9, 8, 6, 5, 1, 5, "glass"); m.box(26, 8, 6, 5, 1, 5, "glass")
    m.box(15, 7, 9, 1, 1, 2, "lamp")                              # lamp in front of the wall
    m.blob(10, 5, 2, 3.5, 2.5, 2.5, ["leaf", "leaf2"])            # bushes
    m.blob(30, 5, 2, 3.5, 2.5, 2.5, ["leaf", "leaf2"])
    return m
```

Save it as `models/tiny_hut.py` and run `voxtool build models/tiny_hut.py --open`:

![Preview of the tiny_hut example](images/example-tiny-hut.png)

For a full, real example (quoins, crow-stepped parapet, awning, lanterns, planters, vines) see [models/player_house.py](../models/player_house.py).

## DSL reference

All methods live on `Model` ([voxtool/model.py](../voxtool/model.py)). `c` is a palette name, a palette index, or `None` (carve).

| Group | Method | Purpose |
|---|---|---|
| Palette | `m.pal.add(name, hex, emit=0, glass=0, metal=0, rough=0.5)` | Register a named colour; `emit` glows, `glass` is transparent, `metal` metallic |
| | `m.pal.ramp(name, [hex, ...])` | Register `name0`, `name1`, … shade variants |
| Primitives | `box(x, y, z, w, d, h, c, only_empty=False, only_filled=False)` | Solid box (`c=None` carves) |
| | `carve(x, y, z, w, d, h)` | Empty a box |
| | `shell(x, y, z, w, d, h, c, t=1, top=True, bottom=True)` | Hollow box with wall thickness `t` |
| | `set(x, y, z, c)` / `get(x, y, z)` | Single voxel |
| | `line(p0, p1, c, r=0)` | 3D line; `r` gives it a cube brush |
| | `ellipsoid(cx, cy, cz, rx, ry, rz, c)` | Ellipsoid |
| | `cylinder(cx, cy, z, r, h, c, axis="z")` | Cylinder along z, x or y |
| | `where(x, y, z, w, d, h, fn, c)` | Fill where `fn(X, Y, Z)` (vectorized numpy) is true — any shape |
| | `paint_fn(x, y, z, w, d, h, fn)` | Recolour per voxel; `fn` returns palette indices |
| Architecture | `gable_roof(x, y, z, w, d, ridge, c, slope=1.0, t=2, fill=None)` | Gable roof; a colour list alternates per course (planks / shingles) |
| | `gable_wall(x, y, z, w, d, ridge, c, slope=1.0, region=None)` | Infill that meets that roof exactly (gable ends, attic) |
| | `shed_roof(x, y, z, w, d, down, c, slope=0.5, t=2)` | Lean-to roof / porch awning |
| | `stairs(x, y, z, w, steps, c, rise=1, run=2, direction="-y")` | Straight stairs |
| Texture & organic | `bricks(colors, target, bw=6, bh=3, mortar=None, p=None, region=None)` | Running-bond stone / brick pattern on existing voxels |
| | `vary(colors, target, p=None, region=None)` | Random recolour to break up flat surfaces |
| | `blob(cx, cy, cz, rx, ry, rz, colors, noise=0.35, density=1.0)` | Noisy ellipsoid: bushes, foliage, rocks |
| | `vine(x, y, z, length, colors, wall="-y", drift=0.35, leaf=0.6, spread=1)` | Vine hanging down a wall |
| | `sprinkle(colors, prob, target, region=None)` | Recolour random surface voxels (flowers in a bush) |
| | `scatter_on_top(region, colors, prob, target=None)` | Place voxels on top of exposed surfaces |
| Objects & files | `with m.part(name): ...` | Voxels drawn inside become a separate object in the `.vox` (kit sheets) |
| | `Model.from_vox(path)` / `m.paste_vox(path, x, y, z)` | Start from / paste in an existing `.vox` (a conversion, or a MagicaVoxel edit) |
| Transform & output | `mirror_x(x0, x1)` / `copy(x, y, z, w, d, h, dx, dy, dz)` | Mirror or duplicate a region |
| | `stats()` / `save(path)` | Summary (voxel count per colour) / write a `.vox` (backs up a MagicaVoxel-saved file first) |

## Conventions that pay off

- Put key dimensions in constants at the top (`FLOOR`, `EAVE`, …) and derive every other coordinate from them, so a proportion change is a one-line edit.
- Build order: walls → `bricks()` texture → roof → openings (carving) → decoration → plants (last, with `only_empty`).
- Check the per-colour counts in `stats()`: a colour with 0 voxels usually means a wrong `region` order.
