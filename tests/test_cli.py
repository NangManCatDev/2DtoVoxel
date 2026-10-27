"""The voxtool command line, run in a temporary workspace."""
import re
import struct

from conftest import make_sprite, run_voxtool


def test_build_writes_previews_and_scores(workspace):
    r = run_voxtool(workspace, "build", "models/hut.py")
    out = workspace / "output" / "hut"
    for f in ("hut.vox", "hut_iso.png", "hut_sheet.png", "hut_compare.png", "hut_score.png", "hut_scores.jsonl"):
        assert (out / f).exists(), f
    m = re.search(r"score: iou=([\d.]+) dE=([\d.]+)", r.stdout)
    assert m and float(m.group(1)) > 0.95


def test_rebuild_backs_up_a_file_saved_by_magicavoxel(workspace):
    run_voxtool(workspace, "build", "models/hut.py", "--no-score")
    vox = workspace / "output" / "hut" / "hut.vox"
    data = bytearray(vox.read_bytes())               # pretend MagicaVoxel saved it (adds rOBJ)
    struct.pack_into("<i", data, 16, struct.unpack_from("<i", data, 16)[0] + 12)
    vox.write_bytes(bytes(data) + b"rOBJ" + struct.pack("<ii", 0, 0))
    r = run_voxtool(workspace, "build", "models/hut.py", "--no-score")
    assert "backup:" in r.stdout
    assert len(list((workspace / "output" / "hut").glob("hut_edited_*.vox"))) == 1


def test_extrude_creates_a_script_that_builds(workspace):
    make_sprite(workspace / "reference" / "sprite.png")
    run_voxtool(workspace, "extrude", "reference/sprite.png", "--name", "sprite", "--depth", "2")
    assert (workspace / "models" / "sprite.base.vox").exists()
    script = (workspace / "models" / "sprite.py").read_text(encoding="utf-8")
    assert "Model.from_vox" in script and "SCORE_VIEW" in script
    assert (workspace / "output" / "sprite" / "sprite.vox").exists()


def test_exports_sprites_and_recolor(workspace):
    run_voxtool(workspace, "export", "models/hut.py", "--format", "glb")
    run_voxtool(workspace, "sprites", "models/hut.py", "--dirs", "4", "--scale", "2")
    run_voxtool(workspace, "recolor", "models/hut.py", "--swap", "roof=#a33b2b", "--label", "red")
    out = workspace / "output" / "hut"
    assert (out / "export" / "hut.glb").exists()
    assert (out / "sprites" / "manifest.json").exists()
    assert (out / "variants" / "hut_red.vox").exists()


def test_ref_sample_accepts_both_coordinate_styles(workspace):
    a = run_voxtool(workspace, "ref", "sample", "reference/hut.png", "10,10", "20,20").stdout
    b = run_voxtool(workspace, "ref", "sample", "reference/hut.png", "10", "10", "20", "20").stdout
    assert a == b and a.count("#") == 2
    bad = run_voxtool(workspace, "ref", "sample", "reference/hut.png", "10", "10", "20", check=False)
    assert bad.returncode != 0 and "x,y pairs" in bad.stderr
