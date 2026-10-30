"""
Stone architecture kit: 4 wall sections + 2 wooden fences + 1 arched gate + 1 staircase.
Each piece independently placeable. Reference shows isometric view with perspective shading.
"""
from voxtool.model import Model, Palette

NAME = "e202255d_23ec_40cf_acec_a7ce203cb095_3"
REFERENCE = "reference/e202255d-23ec-40cf-acec-a7ce203cb095.png"
RES = 1
CUTOUT = {"keep": "all"}

VIEW = {"azimuth": 45, "elevation": 35}

def add_stone_colors(pal):
    pal.add("stone_light", "#f5ead1", emit=0)
    pal.add("stone_mid", "#c9a878", emit=0)
    pal.add("stone_dark", "#7a6653", emit=0)
    pal.add("stone_shadow", "#3d3127", emit=0)
    pal.add("mortar", "#8f7e6d", emit=0)
    pal.add("wood_light", "#a0845e", emit=0)
    pal.add("wood_dark", "#5a3f2b", emit=0)
    pal.add("wood_mid", "#76573d", emit=0)

def add_stones_horizontal(m, x, y, z, w, h, d, col_light, col_dark, mortar_col):
    """Build a wall with horizontal stone pattern."""
    stone_h = 2
    for row in range(h):
        is_shadow = (row % 3 == 1)
        col = col_dark if is_shadow else col_light
        for bx in range(0, w, 4):
            bw = min(4, w - bx)
            m.box(x + bx, y, z + row * stone_h, bw, d, stone_h, col)

def add_base(m, x, y, z, w, d, col):
    """Add a base stone layer."""
    m.box(x, y, z, w, d, 1, col)

def build():
    m = Model(200, 200, 200, seed=42, res=RES)
    add_stone_colors(m.pal)

    # All pieces at roughly same height for kit sheet
    base_z = 10

    # Wall piece 1 (top-left) - horizontal wall 10x5
    with m.part("wall_1"):
        add_base(m, 0, 0, base_z, 10, 3, "mortar")
        add_stones_horizontal(m, 0, 0, base_z + 1, 10, 4, 3, "stone_light", "stone_dark", "mortar")

    # Wall piece 2 (top-middle) - taller wall 13x7
    with m.part("wall_2"):
        add_base(m, 20, 0, base_z, 13, 3, "mortar")
        add_stones_horizontal(m, 20, 0, base_z + 1, 13, 5, 3, "stone_light", "stone_dark", "mortar")

    # Wall piece 3 (top-right) - square wall 12x6
    with m.part("wall_3"):
        add_base(m, 45, 0, base_z, 12, 3, "mortar")
        add_stones_horizontal(m, 45, 0, base_z + 1, 12, 5, 3, "stone_light", "stone_dark", "mortar")

    # Wall piece 4 (top-far-right) - small wall 8x4
    with m.part("wall_4"):
        add_base(m, 70, 0, base_z, 8, 3, "mortar")
        add_stones_horizontal(m, 70, 0, base_z + 1, 8, 4, 3, "stone_light", "stone_dark", "mortar")

    # Fence piece 1 (bottom-left) - tall picket fence
    with m.part("fence_1"):
        add_base(m, 0, 50, base_z, 8, 2, "mortar")
        # Pickets
        for i in range(5):
            m.box(1 + i * 1, 50, base_z + 1, 1, 1, 6, "wood_light")
        # Horizontal rails
        m.box(0, 50, base_z + 2, 8, 1, 1, "wood_mid")
        m.box(0, 50, base_z + 4, 8, 1, 1, "wood_mid")

    # Fence piece 2 (bottom-middle) - picket fence variant
    with m.part("fence_2"):
        add_base(m, 20, 50, base_z, 8, 2, "mortar")
        # Pickets with different spacing
        for i in range(6):
            m.box(20 + i * 1, 50, base_z + 1, 1, 1, 6, "wood_light")
        # Rails
        m.box(20, 50, base_z + 2, 8, 1, 1, "wood_mid")
        m.box(20, 50, base_z + 4, 8, 1, 1, "wood_mid")

    # Arched gate (bottom-right) - stone with wooden door
    with m.part("gate"):
        # Stone posts and base
        add_base(m, 45, 50, base_z, 10, 3, "mortar")
        m.box(45, 50, base_z + 1, 2, 3, 6, "stone_light")  # Left post
        m.box(53, 50, base_z + 1, 2, 3, 6, "stone_light")  # Right post
        # Arch stones
        for bx in range(47, 53):
            m.box(bx, 50, base_z + 6, 1, 3, 1, "stone_dark")
        # Wooden door
        m.box(47, 50, base_z + 1, 6, 3, 4, "wood_dark")
        m.box(48, 50, base_z + 2, 1, 1, 2, "mortar")  # Door detail
        m.box(51, 50, base_z + 2, 1, 1, 2, "mortar")

    # Staircase (bottom-far-right) - 4-step structure
    with m.part("stairs"):
        step_w = 3
        step_d = 3
        for step in range(4):
            step_z = base_z + step
            step_x = 70 + step * step_w
            m.box(step_x, 50, step_z, step_w, step_d, 1, "stone_light")

    m.paint_reference(REFERENCE, VIEW)
    return m
