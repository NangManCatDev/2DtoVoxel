"""The voxtool command line, run in a temporary workspace."""
import json
import re
import struct

from conftest import load_hut, make_silhouette, make_sprite, run_voxtool


def test_build_writes_previews_and_scores(workspace):
    r = run_voxtool(workspace, "build", "models/hut.py")
    out = workspace / "output" / "hut"
    for f in ("hut.vox", "hut_iso.png", "hut_sheet.png", "hut_turn.png", "hut_compare.png", "hut_score.png",
              "hut_scores.jsonl"):
        assert (out / f).exists(), f
    m = re.search(r"score: iou=([\d.]+) dE=([\d.]+)", r.stdout)
    assert m and float(m.group(1)) > 0.95
    assert re.search(r"^depth: [\d.]+$", r.stdout, re.M) and "loose:" not in r.stdout   # deep, in one piece


def test_extra_references_are_scored_and_fitted(workspace):
    from voxtool.render import render_iso
    m = load_hut(workspace)
    render_iso(m.v, m.pal.rgba, azimuth=100, elevation=25, scale=6, outline=False).save(
        workspace / "reference" / "hut_side.png")
    script = workspace / "models" / "hut.py"
    view = 'VIEW = {"azimuth": 30, "elevation": 25}'
    script.write_text(script.read_text(encoding="utf-8").replace(view, view + (
        '\nEXTRA_REFERENCES = [("reference/hut_side.png", {"azimuth": 100, "elevation": 25})]')), encoding="utf-8")
    r = run_voxtool(workspace, "build", "models/hut.py")
    side = re.search(r"^score hut_side\.png: iou=([\d.]+)", r.stdout, re.M)
    assert side and float(side.group(1)) > 0.95 and "score all 2 views: iou=" in r.stdout
    assert re.search(r"^score: iou=", r.stdout, re.M)                # REFERENCE's line, read by UI jobs
    rec = json.loads((workspace / "output" / "hut" / "hut_scores.jsonl").read_text().splitlines()[-1])
    assert rec["views"][0]["reference"] == "reference/hut_side.png"
    met = json.loads(run_voxtool(workspace, "score", "models/hut.py").stdout.splitlines()[-1])
    assert met["views"][0]["view"]["azimuth"] == 100
    fit = run_voxtool(workspace, "fit-camera", "models/hut.py", "--ref", "1", "--fovs", "0").stdout
    az = float(re.search(r'EXTRA_REFERENCES\[0\]: \("reference/hut_side.png", \{"azimuth": ([\d.]+)', fit).group(1))
    assert abs((az - 100 + 180) % 360 - 180) <= 15
    assert run_voxtool(workspace, "fit-camera", "models/hut.py", "--ref", "2", check=False).returncode != 0


def test_carve_script_scores_every_drawing(workspace):
    ref = workspace / "reference"
    make_silhouette(ref / "f.png", "rect")
    make_silhouette(ref / "s.png", "rect")
    make_silhouette(ref / "t.png", "circle", (200, 200))
    r = run_voxtool(workspace, "carve", "--front", "reference/f.png", "--side", "reference/s.png",
                    "--top", "reference/t.png", "--name", "vase", "--height", "40")
    script = (workspace / "models" / "vase.py").read_text(encoding="utf-8")
    assert '("reference/s.png", {"azimuth": 90' in script and '("reference/t.png", {"azimuth": 0, "elevation": 90' in script
    ious = [float(x) for x in re.findall(r"^score [st]\.png: iou=([\d.]+)", r.stdout, re.M)]
    assert len(ious) == 2 and min(ious) > 0.9


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
