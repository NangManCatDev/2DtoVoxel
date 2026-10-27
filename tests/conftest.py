import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def run_voxtool(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Runs the CLI in a separate process with `cwd` as the workspace."""
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "voxtool", *args], cwd=cwd, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise AssertionError(f"voxtool {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """An empty workspace with a tiny model script and its reference image."""
    (tmp_path / "models").mkdir()
    (tmp_path / "reference").mkdir()
    (tmp_path / "models" / "hut.py").write_text(HUT_SCRIPT, encoding="utf-8")
    # reference: render the hut itself, so a perfect build scores ~1.0
    sys.path.insert(0, str(tmp_path))
    from voxtool.render import render_iso
    m = load_hut(tmp_path)
    img = render_iso(m.v, m.pal.rgba, azimuth=30, elevation=25, scale=6, outline=False)
    img.save(tmp_path / "reference" / "hut.png")
    return tmp_path


def load_hut(ws: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("hut", ws / "models" / "hut.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()


HUT_SCRIPT = '''"""hut — test model."""
from voxtool import Model

NAME = "hut"
REFERENCE = "reference/hut.png"
VIEW = {"azimuth": 30, "elevation": 25}


def build() -> Model:
    m = Model(24, 20, 20, seed=1)
    m.pal.add("wall", "#dcc3a0"); m.pal.add("roof", "#0b8691"); m.pal.add("roof2", "#1ba3ad")
    m.pal.add("door", "#8c2b22"); m.pal.add("lamp", "#ffd84a", emit=4)
    m.shell(3, 4, 0, 18, 12, 9, "wall", t=1, top=False)
    roof = (2, 3, 9, 20, 14)
    m.gable_wall(*roof, "x", "wall", region=(3, 4, 18, 12))
    m.gable_roof(*roof, "x", ["roof", "roof2"], t=1)
    m.box(10, 4, 0, 3, 1, 5, "door")
    m.set(14, 3, 5, "lamp")
    return m
'''


def make_sprite(path: Path, scale: int = 8) -> Path:
    """16x16 two-colour sprite on a transparent background, upscaled `scale` times."""
    a = np.zeros((16, 16, 4), np.uint8)
    a[4:12, 3:13] = (220, 40, 40, 255)
    a[12:15, 5:11] = (240, 220, 180, 255)
    Image.fromarray(np.repeat(np.repeat(a, scale, 0), scale, 1), "RGBA").save(path)
    return path


def make_silhouette(path: Path, shape: str, size=(200, 300)) -> Path:
    im = Image.new("RGB", size, (235, 232, 228))
    dr = ImageDraw.Draw(im)
    box = [20, 20, size[0] - 20, size[1] - 20]
    (dr.ellipse if shape == "circle" else dr.rectangle)(box, fill=(60, 120, 200))
    im.save(path)
    return path
