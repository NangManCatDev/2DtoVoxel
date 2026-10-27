"""Game-asset outputs from a voxel grid.

mesh export : OBJ (+ .mtl + palette texture, like MagicaVoxel's own export),
              PLY (vertex colours) and GLB (glTF 2.0 binary, vertex colours, glowing
              colours as emissive materials). Faces of one colour are merged into big
              rectangles (greedy meshing). Axes: Y up, 1 voxel = `scale` units, the
              model stands on y=0 centred on x/z, its front facing +Z.
sprites     : renders N directions into one transparent sprite sheet + manifest.json;
              every frame has the same size and the model's ground centre at the same
              anchor point, so switching directions in a game doesn't make it jump.
recolor     : palette variants (named colour swaps or hue rotation) as new palettes.
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import struct

import numpy as np
from PIL import Image

from .render import _shift, render_iso

# (u, w) axes per face axis, cyclic so that u x w points along +axis
_UW = {0: (1, 2), 1: (2, 0), 2: (0, 1)}


# ---------------------------------------------------------------- greedy meshing

def greedy_quads(v: np.ndarray) -> list[tuple]:
    """Exposed faces merged per colour: (axis, sign, layer, u, w, du, dw, colour)."""
    filled = v > 0
    out = []
    for axis in range(3):
        ua, wa = _UW[axis]
        for sign in (1, -1):
            n = [0, 0, 0]
            n[axis] = sign
            exposed = np.where(filled & ~_shift(filled, tuple(n)), v, 0)
            layers = np.transpose(exposed, (axis, ua, wa))
            for i in np.nonzero(layers.reshape(layers.shape[0], -1).any(axis=1))[0]:
                sl = layers[i]
                done = np.zeros(sl.shape, bool)
                for u, w in zip(*np.nonzero(sl)):
                    if done[u, w]:
                        continue
                    c = sl[u, w]
                    w2 = w + 1
                    while w2 < sl.shape[1] and sl[u, w2] == c and not done[u, w2]:
                        w2 += 1
                    u2 = u + 1
                    while u2 < sl.shape[0] and (sl[u2, w:w2] == c).all() and not done[u2, w:w2].any():
                        u2 += 1
                    done[u:u2, w:w2] = True
                    out.append((axis, sign, int(i), int(u), int(w), int(u2 - u), int(w2 - w), int(c)))
    return out


def quads_to_arrays(quads, shape, scale: float = 1.0):
    """-> positions [Q, 4, 3], normals [Q, 3], colours [Q] in Y-up output space,
    corners counter-clockwise seen from outside."""
    Q = len(quads)
    pos = np.zeros((Q, 4, 3), np.float32)
    nrm = np.zeros((Q, 3), np.float32)
    col = np.zeros(Q, np.int32)
    for k, (axis, sign, i, u, w, du, dw, c) in enumerate(quads):
        ua, wa = _UW[axis]
        plane = i + (1 if sign > 0 else 0)
        uv = [(u, w), (u + du, w), (u + du, w + dw), (u, w + dw)]
        if sign < 0:
            uv = uv[::-1]
        for j, (pu, pw) in enumerate(uv):
            pos[k, j, axis], pos[k, j, ua], pos[k, j, wa] = plane, pu, pw
        nrm[k, axis] = sign
        col[k] = c
    W, D, _ = shape
    # voxel (x, y, z) z-up, front at y=0  ->  (x - W/2, z, -(y - D/2)) y-up, front towards +z
    # (a proper rotation, so the counter-clockwise winding is kept)
    pos = np.stack([pos[..., 0] - W / 2, pos[..., 2], -(pos[..., 1] - D / 2)], -1) * scale
    nrm = np.stack([nrm[:, 0], nrm[:, 2], -nrm[:, 1]], -1)
    return pos.astype(np.float32), nrm.astype(np.float32), col


# ---------------------------------------------------------------- writers

def write_obj(path: str, v: np.ndarray, palette: np.ndarray, *, scale: float = 1.0):
    pos, nrm, col = quads_to_arrays(greedy_quads(v), v.shape, scale)
    base = os.path.splitext(path)[0]
    name = os.path.basename(base)
    tex = np.zeros((1, 256, 3), np.uint8)
    tex[0, :] = palette[:256, :3]
    Image.fromarray(tex, "RGB").save(base + "_palette.png")
    with open(base + ".mtl", "w", encoding="utf-8") as f:
        f.write(f"newmtl palette\nKd 1 1 1\nmap_Kd {name}_palette.png\n")
    normals = {(1, 0, 0): 1, (-1, 0, 0): 2, (0, 1, 0): 3, (0, -1, 0): 4, (0, 0, 1): 5, (0, 0, -1): 6}
    lines = [f"# 2DtoVoxel export: {len(pos)} quads", f"mtllib {name}.mtl", "usemtl palette"]
    lines += ["vn 1 0 0", "vn -1 0 0", "vn 0 1 0", "vn 0 -1 0", "vn 0 0 1", "vn 0 0 -1"]
    lines += [f"vt {(i + 0.5) / 256:.6f} 0.5" for i in range(256)]
    lines += [f"v {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}" for p in pos.reshape(-1, 3)]
    for q in range(len(pos)):
        n = normals[tuple(int(k) for k in nrm[q])]
        t = col[q] + 1
        lines.append("f " + " ".join(f"{q * 4 + j + 1}/{t}/{n}" for j in range(4)))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return [path, base + ".mtl", base + "_palette.png"]


def write_ply(path: str, v: np.ndarray, palette: np.ndarray, *, scale: float = 1.0):
    pos, _, col = quads_to_arrays(greedy_quads(v), v.shape, scale)
    Q = len(pos)
    rgb = palette[col, :3].astype(np.uint8)
    verts = np.zeros(Q * 4, dtype=[("p", "<f4", 3), ("c", "u1", 3)])
    verts["p"] = pos.reshape(-1, 3)
    verts["c"] = np.repeat(rgb, 4, axis=0)
    faces = np.zeros(Q, dtype=[("n", "u1"), ("i", "<i4", 4)])
    faces["n"] = 4
    faces["i"] = np.arange(Q * 4, dtype=np.int32).reshape(Q, 4)
    header = (f"ply\nformat binary_little_endian 1.0\ncomment 2DtoVoxel export\nelement vertex {Q * 4}\n"
              "property float x\nproperty float y\nproperty float z\n"
              "property uchar red\nproperty uchar green\nproperty uchar blue\n"
              f"element face {Q}\nproperty list uchar int vertex_indices\nend_header\n")
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(verts.tobytes())
        f.write(faces.tobytes())
    return [path]


def write_glb(path: str, v: np.ndarray, palette: np.ndarray, emissive: set[int] | None = None, *,
              scale: float = 1.0, name: str = "model"):
    emissive = emissive or set()
    pos, nrm, col = quads_to_arrays(greedy_quads(v), v.shape, scale)
    groups = [("solid", ~np.isin(col, list(emissive)))] + \
             [(f"glow_{c}", col == c) for c in sorted(emissive) if (col == c).any()]
    bin_parts, views, accessors, prims, materials = [], [], [], [], []
    offset = 0

    def add(data: bytes, target: int) -> int:
        nonlocal offset
        pad = (-len(data)) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        bin_parts.append(data + b"\0" * pad)
        offset += len(data) + pad
        return len(views) - 1

    for gname, sel in groups:
        if not sel.any():
            continue
        p = pos[sel].reshape(-1, 3)
        n = np.repeat(nrm[sel], 4, axis=0)
        c = np.repeat(np.concatenate([palette[col[sel], :3], np.full((sel.sum(), 1), 255)], 1), 4, axis=0)
        q = sel.sum()
        idx = (np.arange(q, dtype=np.uint32)[:, None] * 4 + np.array([0, 1, 2, 0, 2, 3], np.uint32)).reshape(-1)
        a0 = len(accessors)
        accessors += [
            {"bufferView": add(p.astype("<f4").tobytes(), 34962), "componentType": 5126, "count": len(p),
             "type": "VEC3", "min": p.min(0).tolist(), "max": p.max(0).tolist()},
            {"bufferView": add(n.astype("<f4").tobytes(), 34962), "componentType": 5126, "count": len(n), "type": "VEC3"},
            {"bufferView": add(c.astype(np.uint8).tobytes(), 34962), "componentType": 5121, "normalized": True,
             "count": len(c), "type": "VEC4"},
            {"bufferView": add(idx.astype("<u4").tobytes(), 34963), "componentType": 5125, "count": len(idx),
             "type": "SCALAR"},
        ]
        if gname == "solid":
            mat = {"name": "voxels", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0,
                                                              "roughnessFactor": 1}}
        else:
            rgb = (palette[int(gname.split("_")[1]), :3] / 255).round(4).tolist()
            mat = {"name": gname, "emissiveFactor": rgb,
                   "pbrMetallicRoughness": {"baseColorFactor": rgb + [1], "metallicFactor": 0, "roughnessFactor": 1}}
        materials.append(mat)
        prims.append({"attributes": {"POSITION": a0, "NORMAL": a0 + 1, "COLOR_0": a0 + 2}, "indices": a0 + 3,
                      "material": len(materials) - 1})

    binary = b"".join(bin_parts)
    gltf = {"asset": {"version": "2.0", "generator": "2DtoVoxel"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": name}], "meshes": [{"name": name, "primitives": prims}],
            "materials": materials, "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(binary)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(binary)))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(binary), b"BIN\0") + binary)
    return [path]


# ---------------------------------------------------------------- sprites

DIR_NAMES = {4: ["front", "left", "back", "right"],
             8: ["front", "front-left", "left", "back-left", "back", "back-right", "right", "front-right"]}


def sprite_sheet(v: np.ndarray, palette: np.ndarray, emissive: set[int] | None, out_dir: str, name: str, *,
                 dirs: int = 8, elevation: float = 30.0, fov: float = 0.0, scale: int = 4,
                 columns: int | None = None) -> dict:
    """Renders `dirs` directions (azimuth 0 = looking at the model's front) with crisp
    pixels and a transparent background. Writes <name>_sheet.png, one PNG per frame and
    manifest.json; returns the manifest."""
    os.makedirs(out_dir, exist_ok=True)
    W, D, _ = v.shape
    frames = []
    for k in range(dirs):
        az = k * 360.0 / dirs
        img, info = render_iso(v, palette, azimuth=az, elevation=elevation, fov=fov, scale=scale, ss=1,
                               outline=False, emissive=emissive, transparent=True, pad=2, return_info=True)
        anchor = info["project"](np.array([[W / 2, D / 2, 0.0]]))[0]
        frames.append((az, img, anchor))
    left = max(a[0] for _, _, a in frames)
    right = max(im.width - a[0] for _, im, a in frames)
    top = max(a[1] for _, _, a in frames)
    bottom = max(im.height - a[1] for _, im, a in frames)
    fw, fh = int(math.ceil(left + right)), int(math.ceil(top + bottom))
    ax, ay = int(math.ceil(left)), int(math.ceil(top))
    cols = columns or min(dirs, 8)
    rows = int(math.ceil(dirs / cols))
    sheet = Image.new("RGBA", (fw * cols, fh * rows), (0, 0, 0, 0))
    names = DIR_NAMES.get(dirs, [f"az{int(round(az)):03d}" for az, _, _ in frames])
    manifest = {"name": name, "frame_width": fw, "frame_height": fh, "anchor": [ax, ay],
                "anchor_note": "pixel of the model's ground centre in every frame",
                "elevation": elevation, "fov": fov, "scale": scale, "sheet": f"{name}_sheet.png", "frames": []}
    for k, (az, img, anchor) in enumerate(frames):
        frame = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        frame.paste(img, (int(round(ax - anchor[0])), int(round(ay - anchor[1]))), img)
        fname = f"{name}_{k:02d}_{names[k]}.png"
        frame.save(os.path.join(out_dir, fname))
        x, y = (k % cols) * fw, (k // cols) * fh
        sheet.paste(frame, (x, y))
        manifest["frames"].append({"index": k, "direction": names[k], "azimuth": az, "file": fname,
                                   "x": x, "y": y, "w": fw, "h": fh})
    sheet.save(os.path.join(out_dir, manifest["sheet"]))
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


# ---------------------------------------------------------------- palette variants

def recolor(palette: np.ndarray, *, swaps: dict[int, str] | None = None, hue: float = 0.0,
            only: set[int] | None = None, skip: set[int] | None = None) -> np.ndarray:
    """New palette: `swaps` {index: '#rrggbb'} replace colours; `hue` rotates hue (degrees)
    of `only` (default: every colour except `skip`, e.g. glowing ones)."""
    out = palette.copy()
    if hue:
        for i in range(1, 256):
            if (only is not None and i not in only) or (skip and i in skip):
                continue
            r, g, b = (palette[i, :3] / 255.0).tolist()
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            r, g, b = colorsys.hls_to_rgb((h + hue / 360.0) % 1.0, l, s)
            out[i, :3] = np.round(np.array([r, g, b]) * 255)
    for i, hx in (swaps or {}).items():
        hx = hx.lstrip("#")
        out[i, :3] = [int(hx[k:k + 2], 16) for k in (0, 2, 4)]
    return out
