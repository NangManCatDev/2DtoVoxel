"""MagicaVoxel .vox reader / writer.

Format reference: https://github.com/ephtracy/voxel-model/blob/master/MagicaVoxel-file-format-vox.txt
                  https://github.com/ephtracy/voxel-model/blob/master/MagicaVoxel-file-format-vox-extension.txt

Grid convention everywhere in this project: array indexed [x, y, z], Z is up,
value 0 = empty, 1..255 = palette index.
"""
from __future__ import annotations

import os
import shutil
import struct
import time
from dataclasses import dataclass, field

import numpy as np

MAX_DIM = 256

# Chunks write_vox produces. MagicaVoxel adds others when it saves (rOBJ, rCAM, NOTE, ...),
# which is how a file with hand edits is recognised before a build overwrites it.
WRITER_CHUNKS = {b"MAIN", b"SIZE", b"XYZI", b"nTRN", b"nGRP", b"nSHP", b"LAYR", b"RGBA", b"MATL"}


@dataclass
class VoxModel:
    voxels: np.ndarray                       # uint8 [x, y, z]
    offset: tuple[int, int, int] = (0, 0, 0)  # world position of voxel (0,0,0)
    name: str = ""


@dataclass
class VoxScene:
    models: list[VoxModel]
    palette: np.ndarray                      # uint8 [256, 4]; row i = color index i (row 0 unused)
    materials: dict[int, dict[str, str]] = field(default_factory=dict)


# ---------------------------------------------------------------- writing

def _str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<i", len(b)) + b


def _dict(d: dict[str, str]) -> bytes:
    out = struct.pack("<i", len(d))
    for k, v in d.items():
        out += _str(k) + _str(str(v))
    return out


def _chunk(cid: bytes, content: bytes, children: bytes = b"") -> bytes:
    return cid + struct.pack("<ii", len(content), len(children)) + content + children


def write_vox(path: str, scene: VoxScene) -> None:
    body = b""
    for m in scene.models:
        v = m.voxels
        if any(s > MAX_DIM for s in v.shape):
            raise ValueError(f"model {m.name!r} is {v.shape}; each model must be <= {MAX_DIM} per axis")
        xs, ys, zs = np.nonzero(v)
        cols = v[xs, ys, zs]
        xyzi = np.stack([xs, ys, zs, cols], axis=1).astype(np.uint8)
        body += _chunk(b"SIZE", struct.pack("<iii", *v.shape))
        body += _chunk(b"XYZI", struct.pack("<i", len(xyzi)) + xyzi.tobytes())

    # Scene graph: root nTRN(0) -> nGRP(1) -> [nTRN -> nSHP] per model.
    n = len(scene.models)
    body += _chunk(b"nTRN", struct.pack("<i", 0) + _dict({}) + struct.pack("<iiii", 1, -1, -1, 1) + _dict({}))
    child_ids = [2 + 2 * i for i in range(n)]
    body += _chunk(b"nGRP", struct.pack("<i", 1) + _dict({}) + struct.pack("<i", n)
                   + b"".join(struct.pack("<i", c) for c in child_ids))
    for i, m in enumerate(scene.models):
        sx, sy, sz = m.voxels.shape
        ox, oy, oz = m.offset
        # MagicaVoxel places a model by its center: center = floor(size / 2)
        t = f"{ox + sx // 2} {oy + sy // 2} {oz + sz // 2}"
        attrs = {"_name": m.name} if m.name else {}
        body += _chunk(b"nTRN", struct.pack("<i", child_ids[i]) + _dict(attrs)
                       + struct.pack("<iiii", child_ids[i] + 1, -1, 0, 1) + _dict({"_t": t}))
        body += _chunk(b"nSHP", struct.pack("<i", child_ids[i] + 1) + _dict({})
                       + struct.pack("<ii", 1, i) + _dict({}))

    body += _chunk(b"LAYR", struct.pack("<i", 0) + _dict({}) + struct.pack("<i", -1))

    # RGBA chunk: entry k holds color index k+1
    pal = np.asarray(scene.palette, dtype=np.uint8)
    rgba = np.zeros((256, 4), np.uint8)
    rgba[:255] = pal[1:256]
    body += _chunk(b"RGBA", rgba.tobytes())

    for idx, props in sorted(scene.materials.items()):
        body += _chunk(b"MATL", struct.pack("<i", idx) + _dict(props))

    with open(path, "wb") as f:
        f.write(b"VOX " + struct.pack("<i", 200))
        f.write(_chunk(b"MAIN", b"", body))


# ---------------------------------------------------------------- reading

class _Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.p = data, pos

    def i32(self) -> int:
        (v,) = struct.unpack_from("<i", self.d, self.p)
        self.p += 4
        return v

    def s(self) -> str:
        n = self.i32()
        v = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return v

    def dct(self) -> dict[str, str]:
        return {self.s(): self.s() for _ in range(self.i32())}


def read_vox(path: str) -> VoxScene:
    """Reads a .vox file. Model offsets are resolved from nTRN translations
    (frame 0, rotations ignored) so models can be merged into one grid."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"VOX ":
        raise ValueError("not a .vox file")

    sizes, grids = [], []
    palette = None
    materials: dict[int, dict[str, str]] = {}
    nodes: dict[int, tuple] = {}

    p = 8 + 12  # skip header + MAIN chunk header
    while p < len(data):
        cid = data[p:p + 4]
        n_content, _n_children = struct.unpack_from("<ii", data, p + 4)
        c0 = p + 12
        r = _Reader(data, c0)
        if cid == b"SIZE":
            sizes.append(struct.unpack_from("<iii", data, c0))
        elif cid == b"XYZI":
            cnt = r.i32()
            arr = np.frombuffer(data, np.uint8, cnt * 4, c0 + 4).reshape(-1, 4)
            g = np.zeros(sizes[-1], np.uint8)
            g[arr[:, 0], arr[:, 1], arr[:, 2]] = arr[:, 3]
            grids.append(g)
        elif cid == b"RGBA":
            rgba = np.frombuffer(data, np.uint8, 256 * 4, c0).reshape(256, 4)
            palette = np.zeros((256, 4), np.uint8)
            palette[1:256] = rgba[:255]
        elif cid == b"MATL":
            idx = r.i32()
            materials[idx] = r.dct()
        elif cid == b"nTRN":
            nid = r.i32(); attrs = r.dct(); child = r.i32(); r.i32(); r.i32()
            frames = [r.dct() for _ in range(r.i32())]
            nodes[nid] = ("T", attrs, child, frames[0] if frames else {})
        elif cid == b"nGRP":
            nid = r.i32(); r.dct()
            nodes[nid] = ("G", [r.i32() for _ in range(r.i32())])
        elif cid == b"nSHP":
            nid = r.i32(); r.dct()
            models = []
            for _ in range(r.i32()):
                models.append(r.i32()); r.dct()
            nodes[nid] = ("S", models)
        p = c0 + n_content  # children of MAIN are walked flat

    if palette is None:
        palette = _default_palette()

    offsets: dict[int, tuple[int, int, int]] = {}
    names: dict[int, str] = {}

    def walk(nid: int, t: np.ndarray, name: str):
        node = nodes.get(nid)
        if node is None:
            return
        if node[0] == "T":
            _, attrs, child, frame = node
            tt = t + np.array([int(v) for v in frame.get("_t", "0 0 0").split()])
            walk(child, tt, attrs.get("_name", name))
        elif node[0] == "G":
            for c in node[1]:
                walk(c, t, name)
        else:
            for mid in node[1]:
                sx, sy, sz = sizes[mid]
                offsets[mid] = (int(t[0]) - sx // 2, int(t[1]) - sy // 2, int(t[2]) - sz // 2)
                names[mid] = name

    if nodes:
        walk(0, np.zeros(3, int), "")

    models = [VoxModel(g, offsets.get(i, (0, 0, 0)), names.get(i, "")) for i, g in enumerate(grids)]
    return VoxScene(models, palette, materials)


def chunk_ids(path: str) -> set[bytes]:
    """Ids of the chunks inside MAIN (empty set if the file isn't a .vox)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"VOX ":
        return set()
    ids, p = set(), 8 + 12
    while p + 12 <= len(data):
        ids.add(data[p:p + 4])
        (n_content,) = struct.unpack_from("<i", data, p + 4)
        p += 12 + n_content
    return ids


def backup_if_edited(path: str) -> str | None:
    """If `path` was last saved by MagicaVoxel (i.e. may hold hand edits), copies it to
    <name>_edited_<time>.vox next to it and returns that path; otherwise None."""
    if not os.path.isfile(path) or not (chunk_ids(path) - WRITER_CHUNKS):
        return None
    stem, ext = os.path.splitext(path)
    dst = f"{stem}_edited_{time.strftime('%Y%m%d-%H%M%S')}{ext}"
    shutil.copy2(path, dst)
    return dst


def merge_models(scene: VoxScene) -> np.ndarray:
    """Flattens all models of a scene into one grid (for rendering)."""
    if len(scene.models) == 1:
        return scene.models[0].voxels
    lo = np.min([m.offset for m in scene.models], axis=0)
    hi = np.max([np.add(m.offset, m.voxels.shape) for m in scene.models], axis=0)
    out = np.zeros(hi - lo, np.uint8)
    for m in scene.models:
        o = np.subtract(m.offset, lo)
        s = m.voxels.shape
        region = out[o[0]:o[0] + s[0], o[1]:o[1] + s[1], o[2]:o[2] + s[2]]
        np.copyto(region, m.voxels, where=m.voxels > 0)
    return out


def _default_palette() -> np.ndarray:
    # Only needed for files without an RGBA chunk; a neutral ramp is good enough for previews.
    pal = np.zeros((256, 4), np.uint8)
    ramp = np.linspace(40, 255, 255).astype(np.uint8)
    pal[1:, 0] = pal[1:, 1] = pal[1:, 2] = ramp
    pal[1:, 3] = 255
    return pal
