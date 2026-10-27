"""vox_io, the building DSL and the renderer."""
import struct

import numpy as np

from voxtool import Model, merge_models, read_vox
from voxtool.render import render_iso
from voxtool.vox_io import backup_if_edited, chunk_ids


def small_model():
    m = Model(12, 10, 14, seed=3)
    m.pal.add("a", "#ff0000")
    m.pal.add("b", "#00ff00")
    m.pal.add("lamp", "#ffd84a", emit=3)
    m.pal.add("glass", "#9fd3ff", glass=0.5)
    m.shell(1, 1, 0, 10, 8, 8, "a", top=False)
    m.gable_roof(0, 0, 8, 12, 10, "x", ["a", "b"], t=1)
    m.set(5, 0, 3, "lamp")
    m.box(2, 1, 3, 2, 1, 2, "glass")
    return m


def test_roundtrip_keeps_voxels_palette_materials(tmp_path):
    m = small_model()
    p = tmp_path / "m.vox"
    m.save(str(p))
    s = read_vox(str(p))
    assert len(s.models) == 1
    assert np.array_equal(s.models[0].voxels, m.v)
    assert np.array_equal(s.palette[1:5], m.pal.rgba[1:5])
    assert s.materials == m.pal.materials


def _add_chunk(path, cid: bytes):
    """Appends an extra chunk inside MAIN, like MagicaVoxel's rOBJ/rCAM when it saves."""
    data = bytearray(path.read_bytes())
    extra = cid + struct.pack("<ii", 0, 0)
    n_children = struct.unpack_from("<i", data, 16)[0]
    struct.pack_into("<i", data, 16, n_children + len(extra))
    path.write_bytes(bytes(data) + extra)


def test_backup_only_for_files_saved_by_magicavoxel(tmp_path):
    m = small_model()
    p = tmp_path / "m.vox"
    assert m.save(str(p)) is None                 # nothing to back up yet
    assert m.save(str(p)) is None                 # our own file: overwritten silently
    _add_chunk(p, b"rOBJ")
    assert b"rOBJ" in chunk_ids(str(p))
    backup = m.save(str(p))
    assert backup and backup.endswith(".vox") and "_edited_" in backup
    assert b"rOBJ" in chunk_ids(backup)           # the copy is the edited file
    assert backup_if_edited(str(p)) is None       # the new file is ours again


def test_parts_become_separate_objects(tmp_path):
    m = Model(40, 10, 10)
    m.pal.add("a", "#ff0000")
    with m.part("left"):
        m.box(0, 0, 0, 5, 5, 5, "a")
    with m.part("right"):
        m.box(30, 2, 1, 4, 4, 4, "a")
    p = tmp_path / "kit.vox"
    m.save(str(p))
    s = read_vox(str(p))
    assert sorted(x.name for x in s.models) == ["left", "right"]
    assert int((merge_models(s) > 0).sum()) == 5 ** 3 + 4 ** 3


def test_paste_and_from_vox_keep_colours_and_glow(tmp_path):
    src = small_model()
    p = tmp_path / "src.vox"
    src.save(str(p))
    m = Model.from_vox(str(p))
    assert np.array_equal(m.v > 0, src.v > 0)
    lamp = m.v[5, 0, 3]
    assert tuple(m.pal.rgba[lamp][:3]) == (0xff, 0xd8, 0x4a) and m.pal.is_emissive(int(lamp))
    big = Model(30, 30, 30)
    big.paste_vox(str(p), 10, 10, 5)
    assert int((big.v > 0).sum()) == int((src.v > 0).sum())


def test_render_orthographic_perspective_transparent():
    m = small_model()
    ortho = np.asarray(render_iso(m.v, m.pal.rgba, azimuth=30, elevation=25, scale=4))
    persp = np.asarray(render_iso(m.v, m.pal.rgba, azimuth=30, elevation=25, fov=40, scale=4))
    assert ortho.shape != persp.shape or not np.array_equal(ortho, persp)
    img, info = render_iso(m.v, m.pal.rgba, scale=3, ss=1, transparent=True, return_info=True)
    a = np.asarray(img)
    assert img.mode == "RGBA" and a[..., 3].max() == 255 and a[0, 0, 3] == 0
    x, y = info["project"](np.array([[6.0, 5.0, 0.0]]))[0]
    assert 0 <= x < img.width and 0 <= y < img.height


def test_gable_roof_is_symmetric():
    m = Model(10, 12, 12)
    m.pal.add("r", "#000000")
    m.gable_roof(0, 0, 0, 10, 12, "x", "r", t=1)
    filled = m.v > 0
    assert np.array_equal(filled, filled[:, ::-1, :])
