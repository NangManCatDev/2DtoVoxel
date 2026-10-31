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


def _plant_model():
    m = Model(40, 40, 50, seed=4)
    m.pal.ramp("leaf", ["#0a2c0d", "#1b561e", "#276d29", "#388a36"])
    m.pal.add("tip", "#6aa83a")
    m.pal.ramp("bark", ["#8a542a", "#6e4220"])
    return m


def test_tube_bends_and_tapers():
    m = _plant_model()
    m.tube([(5, 20, 0), (10, 20, 20), (20, 20, 30)], [3, 2, 1], ["bark0", "bark1"])
    assert m.v[5, 20, 0] and m.v[20, 20, 30] and not m.v[5, 20, 30]
    width = lambda z: int((m.v[:, :, z] > 0).sum())                 # noqa: E731
    assert width(1) > width(28) > 0                                  # thick at the foot, thin at the end
    assert {m.pal.idx("bark0"), m.pal.idx("bark1")} <= set(np.unique(m.v).tolist())   # bark streaks


def test_foliage_is_lumpy_shaded_and_respects_lobe_size():
    m = _plant_model()
    m.tube([(20, 20, 0), (20, 20, 30)], 1.5, "bark0")
    n = m.foliage([(20, 20, 30, 9)], ["leaf0", "leaf1", "leaf2", "leaf3"], tips="tip")
    filled = m.v > 0
    xs = np.nonzero(m.v[:, :, 18:] > 0)[0]
    assert n > 800 and xs.max() - xs.min() <= 2 * 9 + 4              # outline wobbles around r
    front = filled.any(axis=1)                                       # seen from the front: no see-through gaps
    X, Z = np.meshgrid(np.arange(40), np.arange(50), indexing="ij")
    assert front[(X - 20) ** 2 + (Z - 30) ** 2 <= 6 ** 2].all()
    assert m.v[20, 20, 25] == m.pal.idx("bark0")                     # leaves grow around the trunk
    leaf_ids = [m.pal.idx(f"leaf{i}") for i in range(4)]
    counts = [int((m.v == i).sum()) for i in leaf_ids]
    assert min(counts) > 0 and (m.v == m.pal.idx("tip")).any()       # shades from dark to light
    ball = Model(40, 40, 50)
    ball.pal.add("a", "#000000")
    ball.ellipsoid(20, 20, 30, 9, 9, 9, "a")

    def lumpiness(f):             # exposed faces per volume^(2/3): about 7 for a ball
        dirs = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
        return sum(int((f & ~render._shift(f, d)).sum()) for d in dirs) / f.sum() ** (2 / 3)
    assert lumpiness(filled & (m.v != m.pal.idx("bark0"))) > 1.5 * lumpiness(ball.v > 0)


def test_tree_styles_and_explicit_lobes():
    for style in ("round", "column", "cone", "tiered", "branched", "spread"):
        m = _plant_model()
        info = m.tree(20, 20, 0, 45, ["leaf0", "leaf1", "leaf2", "leaf3"], ["bark0", "bark1"], style=style)
        assert info["lobes"] and (m.v > 0).sum() > 500, style
        top_trunk = max(z for x, y, z in info["trunk"])
        assert top_trunk <= max(lb[2] + lb[3] for lb in info["lobes"])   # the trunk ends inside the crown
    m = _plant_model()
    info = m.tree(20, 20, 0, 40, ["leaf0", "leaf1"], "bark0", lobes=[(20, 20, 30, 7), (14, 20, 22, 5)])
    assert len(info["lobes"]) == 2


def test_crown_depth_rounds_a_flat_crown_without_tilting_it():
    m = _plant_model()
    view = {"azimuth": 45, "elevation": 30}
    a, e = np.radians(45), np.radians(30)
    right, back = np.array([np.cos(a), -np.sin(a)]), np.array([np.sin(a), np.cos(a)])
    spots = ((-6, 30), (0, 30), (6, 30), (0, 36))                             # touching lobes: one crown
    flat = [(20 + u * right[0], 20 + u * right[1], z, 4.0) for u, z in spots]
    deep = m.crown_depth(flat, 20, 20, view)
    rel = np.array([p[:2] for p in deep]) - [20, 20]
    u, s, z = rel @ right, rel @ back, np.array([p[2] for p in deep])
    assert len(deep) > len(flat) and s.min() < -3 and s.max() > 3          # depth in front and behind
    width = 6 + 4 - (-6 - 4)
    assert (s.max() - s.min() + 8) / width > 0.7                            # about as deep as wide
    screen = np.stack([u, z * np.cos(e) + s * np.sin(e)], 1)                # seen from the reference's side
    given = np.array([(uu, zz * np.cos(e)) for uu, zz in spots])
    assert np.abs(screen[:, None] - given[None]).sum(-1).min(axis=1).max() < 1.5   # same outline
    info = m.tree(20, 20, 0, 40, ["leaf0", "leaf1"], "bark0", lobes=flat, view=view)
    assert len(info["lobes"]) > len(flat)


def test_carve_to_reference_cuts_what_the_reference_lacks(workspace, monkeypatch):
    monkeypatch.chdir(workspace)
    m = load_hut(workspace)
    hut = m.v > 0
    m.pal.add("extra", "#ff00ff")
    m.box(21, 0, 0, 3, 2, 14, "extra")                # a post beside the front-right corner, not in the reference
    removed = m.carve_to_reference("reference/hut.png", {"azimuth": 30, "elevation": 25}, only="extra")
    assert removed > 0 and (m.v == m.pal.idx("extra")).sum() < 3 * 2 * 14 * 0.5
    assert np.array_equal(m.v[hut] > 0, np.ones(int(hut.sum()), bool))   # `only` protects the rest


def test_loose_pieces_per_object_and_remove_loose():
    m = Model(20, 20, 20, res=2)
    m.pal.add("a", "#888888")
    m.box(2, 2, 0, 6, 6, 6, "a")                      # the body
    m.set(8, 8, 6, "a")                               # touches the body's corner only: attached
    m.box(2, 2, 8, 2, 2, 1, "a")                      # a slab hovering over it: 4 design voxels
    m.set(15, 15, 15, "a")                            # a speck
    with m.part("post"):
        m.box(14, 2, 0, 2, 2, 5, "a")                 # its own object, not a loose piece of the body
    pieces = m.loose_pieces()
    assert [(p["part"], p["voxels"]) for p in pieces] == [("rest", 32), ("rest", 8)]
    assert pieces[1]["at"] == (15.5, 15.5, 15.5)      # design units
    assert m.remove_loose(max_voxels=1) == 8 and len(m.loose_pieces()) == 1
    assert m.remove_loose(max_voxels=None) == 32 and m.loose_pieces() == []
    assert (m.v > 0).sum() == (6 * 6 * 6 + 1 + 2 * 2 * 5) * 8


def test_damage_breaks_the_model_without_leaving_anything_floating(workspace):
    from scipy import ndimage
    removed = []
    for level in (1, 3):
        m = load_hut(workspace)
        before = int((m.v > 0).sum())
        info = m.damage(level, seed=3)
        assert info["removed"] > 0 and info["holes"] > 0 and (m.v > 0).sum() < before
        labels, n = ndimage.label(m.v > 0, structure=np.ones((3, 3, 3), bool))
        assert set(range(1, n + 1)) <= set(np.unique(labels[:, :, 0]))    # every piece rests on the ground
        assert "crack" in m.pal.names and "wall_burnt" in m.pal.names
        removed.append(info["removed"])
    assert removed[1] > removed[0] * 3


def test_depth_report_flags_a_flat_board():
    from voxtool.__main__ import depth_report
    view = {"azimuth": 20, "elevation": 25}
    board, cube = Model(30, 30, 30), Model(30, 30, 30)
    for m in (board, cube):
        m.pal.add("a", "#888888")
    board.box(5, 14, 0, 20, 2, 20, "a")               # a crown filled in as a layer facing the camera
    cube.box(5, 5, 0, 20, 20, 20, "a")
    assert depth_report(board, view)[1] and "(thin)" in depth_report(board, view)[0]
    assert not depth_report(cube, view)[1]


def test_coarsen_keeps_the_top_colour_of_each_block():
    v = np.zeros((6, 6, 6), np.uint8)
    v[:, :, 0] = 1
    v[2, 2, 1] = 2
    c = coarsen(v, 3)
    assert c.shape == (2, 2, 2) and c[0, 0, 0] == 2 and c[1, 1, 0] == 1 and c[0, 0, 1] == 0
