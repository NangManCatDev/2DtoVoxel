"""Mesh export, sprite sheets and palette variants."""
import json
import struct

import numpy as np

from conftest import load_hut
from voxtool.export import greedy_quads, recolor, sprite_sheet, write_glb, write_obj, write_ply
from voxtool.render import _shift


def exposed_faces(v):
    filled = v > 0
    return sum(int((filled & ~_shift(filled, n)).sum())
               for n in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))


def test_greedy_quads_cover_every_face_with_fewer_quads(workspace):
    m = load_hut(workspace)
    quads = greedy_quads(m.v)
    assert sum(du * dw for *_, du, dw, _ in quads) == exposed_faces(m.v)
    assert len(quads) < exposed_faces(m.v) / 2


def test_glb_is_valid_gltf(workspace, tmp_path):
    m = load_hut(workspace)
    p = tmp_path / "hut.glb"
    write_glb(str(p), m.v, m.pal.rgba, {m.pal.idx("lamp")}, scale=0.1)
    raw = p.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", raw)
    assert (magic, version, length) == (b"glTF", 2, len(raw))
    jlen, jtype = struct.unpack_from("<I4s", raw, 12)
    g = json.loads(raw[20:20 + jlen])
    blen, btype = struct.unpack_from("<I4s", raw, 20 + jlen)
    assert jtype == b"JSON" and btype == b"BIN\0" and blen == g["buffers"][0]["byteLength"]
    names = [g["materials"][pr["material"]]["name"] for pr in g["meshes"][0]["primitives"]]
    assert names[0] == "voxels" and any(n.startswith("glow_") for n in names)
    pos = g["accessors"][g["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    assert pos["min"][1] == 0.0                                     # stands on the ground


def test_obj_and_ply_files(workspace, tmp_path):
    m = load_hut(workspace)
    files = write_obj(str(tmp_path / "hut.obj"), m.v, m.pal.rgba)
    assert all((tmp_path / f.split("\\")[-1].split("/")[-1]).exists() for f in files)
    obj = (tmp_path / "hut.obj").read_text()
    assert obj.count("\nf ") == len(greedy_quads(m.v))
    write_ply(str(tmp_path / "hut.ply"), m.v, m.pal.rgba)
    assert (tmp_path / "hut.ply").read_bytes().startswith(b"ply\nformat binary_little_endian")


def test_sprite_sheet_frames_share_size_and_anchor(workspace, tmp_path):
    m = load_hut(workspace)
    man = sprite_sheet(m.v, m.pal.rgba, set(), str(tmp_path), "hut", dirs=8, scale=2)
    assert [f["direction"] for f in man["frames"]][:3] == ["front", "front-left", "left"]
    assert len({(f["w"], f["h"]) for f in man["frames"]}) == 1
    assert (tmp_path / "hut_sheet.png").exists() and (tmp_path / "manifest.json").exists()


def test_recolor_swaps_and_rotates_only_selected():
    pal = np.zeros((256, 4), np.uint8)
    pal[1] = (200, 30, 30, 255)
    pal[2] = (30, 30, 200, 255)
    out = recolor(pal, swaps={2: "#00ff00"})
    assert tuple(out[2][:3]) == (0, 255, 0) and tuple(out[1][:3]) == (200, 30, 30)
    rot = recolor(pal, hue=120, only={1})
    assert tuple(rot[1][:3]) != (200, 30, 30) and tuple(rot[2][:3]) == (30, 30, 200)
