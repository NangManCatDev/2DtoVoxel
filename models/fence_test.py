"""Fence and wall test model"""

from voxtool.model import Model

NAME = "fence_test"
REFERENCE = "reference/fence.png"

VIEW = {"azimuth": 0, "elevation": 40, "fov": 0}

RES = 1

def build() -> Model:
    m = Model(160, 100, 40, seed=0x12345, res=RES)

    # Palette
    m.pal.add("stone_light", "#d9c8ae", emit=0)
    m.pal.add("stone_mid", "#a89170", emit=0)
    m.pal.add("stone_dark", "#6d5d4d", emit=0)
    m.pal.add("wood_dark", "#4a3520", emit=0)
    m.pal.add("wood_light", "#8b6f47", emit=0)

    # Simple fence structure
    base_z = 0
    base_h = 2

    # Stone wall bases
    for i in range(4):
        x = 10 + i * 40
        m.box(x, 20, base_z, 20, 15, base_h, "stone_dark")
        m.box(x + 2, 22, base_z + base_h, 16, 11, 12, "stone_light")
        m.box(x + 4, 24, base_z + base_h + 2, 12, 7, 8, "stone_mid")

    return m
