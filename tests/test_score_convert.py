"""Reference cutout, scoring, camera fitting and the no-LLM conversions."""
import numpy as np
from PIL import Image, ImageDraw

from conftest import load_hut, make_silhouette, make_sprite
from voxtool.convert import carve, detect_pixel_size, extrude
from voxtool.reftools import cutout
from voxtool.score import fit_camera, score_model


def test_cutout_removes_plain_background_and_shadow(tmp_path):
    im = Image.new("RGB", (200, 160), (232, 229, 224))
    dr = ImageDraw.Draw(im)
    dr.ellipse([40, 120, 170, 150], fill=(205, 202, 198))           # soft floor shadow
    dr.rectangle([60, 30, 140, 130], fill=(180, 60, 50))            # the object
    p = tmp_path / "ref.png"
    im.save(p)
    a = np.asarray(cutout(str(p)))[..., 3] > 0
    assert a[80, 100] and not a[5, 5] and not a[145, 50]            # object kept, bg + shadow gone
    assert abs(a.sum() - 81 * 101) / (81 * 101) < 0.05


def test_cutout_keep_largest_drops_neighbours(tmp_path):
    im = Image.new("RGB", (200, 100), (240, 240, 240))
    dr = ImageDraw.Draw(im)
    dr.rectangle([20, 20, 120, 90], fill=(30, 90, 160))
    dr.rectangle([180, 40, 199, 90], fill=(30, 90, 160))           # cut off at the edge
    p = tmp_path / "ref.png"
    im.save(p)
    assert not (np.asarray(cutout(str(p), keep="largest"))[..., 3] > 0)[60, 190]
    assert (np.asarray(cutout(str(p), keep="all"))[..., 3] > 0)[60, 190]


def test_score_of_matching_render_is_high_and_wrong_camera_lower(workspace):
    m = load_hut(workspace)
    ref = str(workspace / "reference" / "hut.png")
    good, img = score_model(m.v, m.pal.rgba, set(), ref, {"azimuth": 30, "elevation": 25})
    bad, _ = score_model(m.v, m.pal.rgba, set(), ref, {"azimuth": 120, "elevation": 60})
    assert good["iou"] > 0.95 and good["delta_e"] < 10
    assert bad["iou"] < good["iou"] - 0.1
    assert len(good["regions"]) == 9 and img.width > img.height


def test_fit_camera_recovers_the_reference_angle(workspace):
    m = load_hut(workspace)
    best = fit_camera(m.v, str(workspace / "reference" / "hut.png"), fovs=(0,))[0]
    az = (best["azimuth"] - 30 + 180) % 360 - 180
    assert abs(az) <= 15 and abs(best["elevation"] - 25) <= 10


def test_pixel_size_detection_and_extrude(tmp_path):
    p = make_sprite(tmp_path / "s.png", scale=8)
    assert detect_pixel_size(np.asarray(Image.open(p))) == 8
    flat = extrude(str(p), depth=3)
    assert flat.v.shape == (10, 3, 11)                              # cropped to the sprite, 3 deep
    assert len(flat.pal.names) == 2
    puffy = extrude(str(p), depth=3, inflate=True)
    assert puffy.v.shape[1] == 5 and (puffy.v > 0).sum() < (flat.v > 0).sum() * 5 / 3


def test_carve_front_side_top_makes_a_cylinder(tmp_path):
    f = make_silhouette(tmp_path / "f.png", "rect")
    s = make_silhouette(tmp_path / "s.png", "rect")
    t = make_silhouette(tmp_path / "t.png", "circle", (200, 200))
    m = carve(str(f), str(s), str(t), height=40)
    W, D, H = m.v.shape
    assert H == 40 and abs(W - D) <= 1
    expected = np.pi * (W / 2) ** 2 * H
    assert abs((m.v > 0).sum() - expected) / expected < 0.12
