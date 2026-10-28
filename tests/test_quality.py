"""High-resolution work: big grids saved as tiles, res, the z-buffer renderer, painting from
the reference and zoomed comparisons."""
import numpy as np

from conftest import load_hut, run_voxtool
from voxtool import Model, merge_models, read_vox
from voxtool import render
from voxtool.render import coarsen, render_iso
from voxtool.score import _lab


def _iou(a, b):
    return (a & b).sum() / max((a | b).sum(), 1)


def test_big_grid_is_saved_as_grouped_tiles(tmp_path):
    m = Model(300, 20, 10)
    m.pal.add("a", "#ff0000")
    m.box(0, 0, 0, 300, 20, 2, "a")
    with m.part("tower"):
        m.box(10, 5, 2, 4, 4, 8, "a")
    p = tmp_path / "big.vox"
    m.save(str(p))
    s = read_vox(str(p))
    assert sorted((x.name, x.group) for x in s.models) == [("rest_0_0_0", "rest"), ("rest_1_0_0", "rest"),
                                                           ("tower", "")]
    assert all(max(x.voxels.shape) <= 256 for x in s.models)
    assert np.array_equal(merge_models(s), m.v)
    plain = Model(260, 4, 4)
    plain.pal.add("a", "#ff0000")
    plain.box(0, 0, 0, 260, 4, 4, "a")
    assert {x.group for x in plain.to_scene().models} == {"model"} and "2 tiles" in plain.stats()


def test_res_keeps_design_units_and_refines_shapes(tmp_path):
    lo, hi = Model(20, 20, 20), Model(20, 20, 20, res=3)
    for m in (lo, hi):
        m.pal.add("a", "#ff0000")
        m.box(2, 2, 0, 6, 4, 3, "a")
        m.where(10, 0, 0, 10, 4, 4, lambda X, Y, Z: X < 13, "a")
        m.ellipsoid(10, 12, 12, 5, 5, 5, "a")
        m.set(0, 0, 19, "a")
    assert hi.v.shape == hi.size == (60, 60, 60) and hi.dims == (20, 20, 20)
    assert (hi.v[6:24, 6:18, 0:9] > 0).all() and int((hi.v[:, :, :9] > 0).sum()) > 0
    assert (hi.v[30:39, 0:12, 0:12] > 0).all() and not hi.v[39:42, 0:12, 0:12].any()   # X < 13 is exact
    assert hi.get(0, 0, 19) and (hi.v[0:3, 0:3, 57:60] > 0).all()
    blocks = (hi.v.reshape(20, 3, 20, 3, 20, 3) > 0).mean(axis=(1, 3, 5)) >= 0.5
    assert _iou(lo.v > 0, blocks) > 0.9                       # same shapes, just finer
    roof = Model(10, 12, 12, res=2)
    roof.pal.add("r", "#000000")
    roof.gable_roof(0, 0, 0, 10, 12, "x", "r", t=1)
    assert np.array_equal(roof.v > 0, (roof.v > 0)[:, ::-1, :])
    p = tmp_path / "lo.vox"
    lo.save(str(p))
    assert int((Model.from_vox(str(p), res=2).v > 0).sum()) == 8 * int((lo.v > 0).sum())


def test_zbuffer_render_matches_the_polygon_render(monkeypatch):
    m = Model(30, 24, 20, seed=1)
    m.pal.add("a", "#c08040"); m.pal.add("b", "#3070c0")
    m.box(2, 2, 0, 26, 20, 8, "a")
    m.gable_roof(1, 1, 8, 28, 22, "x", ["a", "b"], t=2)
    m.ellipsoid(15, 12, 18, 4, 4, 3, "b")
    kw = dict(azimuth=35, elevation=25, scale=4, ss=1, transparent=True, outline=False)
    a = np.asarray(render_iso(m.v, m.pal.rgba, **kw))
    monkeypatch.setattr(render, "POLY_LIMIT", 0)
    b = np.asarray(render_iso(m.v, m.pal.rgba, **kw))
    assert a.shape == b.shape and _iou(a[..., 3] > 0, b[..., 3] > 0) > 0.97
    both = (a[..., 3] > 0) & (b[..., 3] > 0)
    assert np.abs(a[both, :3].astype(int) - b[both, :3]).mean() < 8


def test_paint_reference_brings_back_the_reference_colours(workspace, monkeypatch):
    monkeypatch.chdir(workspace)
    m = load_hut(workspace)
    wall, lamp = m.pal.idx("wall"), m.pal.idx("lamp")
    m.pal.rgba[wall, :3] = (180, 180, 180)                 # a wrong, grey wall
    before = m.v.copy()
    n = m.paint_reference("reference/hut.png", {"azimuth": 30, "elevation": 25})
    painted = m.v != before
    assert n > 100 and int(painted.sum()) == n
    assert np.array_equal(m.v > 0, before > 0)             # colours only, the shape is untouched
    cols = m.pal.rgba[m.v[painted & (before == wall)], :3].astype(float)
    assert np.linalg.norm(_lab(cols.mean(axis=0)) - _lab(np.array([0xdc, 0xc3, 0xa0], float))) < 10
    assert (m.v[before == lamp] == lamp).all()             # glowing colours are left alone
    assert any(name.startswith("wall_r") for name in m.pal.names)


def test_res_override_and_zoom(workspace):
    script = workspace / "models" / "hut.py"
    bad = run_voxtool(workspace, "build", "models/hut.py", "--res", "2", check=False)
    assert bad.returncode != 0 and "RES" in bad.stderr
    s = script.read_text(encoding="utf-8")
    script.write_text(s.replace('NAME = "hut"', 'NAME = "hut"\nRES = 1')
                      .replace("Model(24, 20, 20, seed=1)", "Model(24, 20, 20, seed=1, res=RES)"), encoding="utf-8")
    r = run_voxtool(workspace, "build", "models/hut.py", "--res", "2")
    assert "grid (48, 40, 40)" in r.stdout and "score: iou=" in r.stdout
    z = run_voxtool(workspace, "score", "models/hut.py", "--zoom", "top-left")
    assert "zoom top-left" in z.stdout and (workspace / "output" / "hut" / "hut_zoom_top-left.png").exists()
    box = run_voxtool(workspace, "score", "models/hut.py", "--zoom", "20,20,120,120")
    assert "iou=" in box.stdout
    bad = run_voxtool(workspace, "score", "models/hut.py", "--zoom", "nowhere", check=False)
    assert bad.returncode != 0 and "--zoom takes" in bad.stderr


def test_recolor_and_export_handle_grids_over_256(workspace):
    m = Model(300, 8, 4)
    m.pal.add("a", "#336699")
    m.box(0, 0, 0, 300, 8, 4, "a")
    m.save(str(workspace / "wide.vox"))
    run_voxtool(workspace, "recolor", "wide.vox", "--hue", "90")
    run_voxtool(workspace, "export", "wide.vox", "--format", "glb")
    s = read_vox(str(workspace / "output" / "wide" / "variants" / "wide_hue90.vox"))
    assert len(s.models) == 2 and merge_models(s).shape == (300, 8, 4)
    assert (workspace / "output" / "wide" / "export" / "wide.glb").stat().st_size > 0


def test_coarsen_keeps_the_top_colour_of_each_block():
    v = np.zeros((6, 6, 6), np.uint8)
    v[:, :, 0] = 1
    v[2, 2, 1] = 2
    c = coarsen(v, 3)
    assert c.shape == (2, 2, 2) and c[0, 0, 0] == 2 and c[1, 1, 0] == 1 and c[0, 0, 1] == 0
