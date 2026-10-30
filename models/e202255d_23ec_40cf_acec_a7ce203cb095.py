"""
Building elements kit: stone walls, wooden fence, gate, stairs.
Various architectural blocks with textured surfaces.
"""

from voxtool.model import Model

NAME = "e202255d_23ec_40cf_acec_a7ce203cb095"
REFERENCE = "reference/e202255d-23ec-40cf-acec-a7ce203cb095.png"
CUTOUT = {"keep": "all"}

VIEW = {"azimuth": 0, "elevation": 66, "fov": 0}

RES = 1

def build() -> Model:
    m = Model(160, 120, 30, seed=0xabc123, res=RES)

    # Palette
    m.pal.add("stone_light", "#d1ba9d", emit=0)
    m.pal.add("stone_mid", "#b29d85", emit=0)
    m.pal.add("stone_dark", "#8f7e6d", emit=0)
    m.pal.add("stone_dark2", "#6a5848", emit=0)
    m.pal.add("wood_dark", "#543829", emit=0)
    m.pal.add("wood_mid", "#6d4d37", emit=0)
    m.pal.add("stone_shade", "#3a2e25", emit=0)

    base_z = 0
    base_h = 4

    # Top row: 4 walls with different heights
    with m.part("wall_1"):
        build_wall(m, 10, 20, base_z, 12, 6, base_h)  # Short

    with m.part("wall_2"):
        build_wall(m, 30, 20, base_z, 12, 10, base_h)  # Tall

    with m.part("wall_3"):
        build_wall(m, 50, 20, base_z, 12, 10, base_h)  # Tall

    with m.part("wall_4"):
        build_wall(m, 70, 20, base_z, 12, 6, base_h)  # Short

    # Bottom row: fence, fence, gate, stairs
    with m.part("fence_1"):
        build_fence(m, 10, 70, base_z, 12, 8, base_h)

    with m.part("fence_2"):
        build_fence(m, 30, 70, base_z, 12, 8, base_h)

    with m.part("gate"):
        build_gate(m, 50, 70, base_z, 12, 12, base_h)

    with m.part("stairs"):
        build_stairs(m, 70, 70, base_z, 12, 8, base_h)

    return m


def build_wall(m: Model, x: int, y: int, z: int, width: int, wall_h: int, base_h: int):
    """Stone block wall"""
    wall_z = z + base_h
    block_size = 2

    # Stone blocks
    for row in range((wall_h + block_size - 1) // block_size):
        for col in range((width + block_size - 1) // block_size):
            bx = x + col * block_size
            by = y + row * block_size
            bz = wall_z + row * block_size

            color = "stone_light" if (row + col) % 2 == 0 else "stone_dark"

            # Main block
            m.box(bx, by, bz, block_size, block_size, block_size, color)

            # Shading
            if col % 2 == 0:
                m.box(bx, by, bz, block_size, block_size, 1, "stone_dark2")

    # Base
    m.box(x - 2, y - 2, z, width + 4, width + 4, base_h, "stone_shade")


def build_fence(m: Model, x: int, y: int, z: int, width: int, fence_h: int, base_h: int):
    """Wooden fence"""
    fence_z = z + base_h
    post_spacing = 3
    post_width = 1

    num_posts = 5
    for i in range(num_posts):
        px = x + i * post_spacing

        # Vertical post
        m.box(px, y, fence_z, post_width, 2, fence_h, "wood_dark")

    # Horizontal rails
    m.box(x - 1, y - 1, fence_z + 2, width + 2, 1, 1, "wood_mid")
    if fence_h >= 4:
        m.box(x - 1, y - 1, fence_z + fence_h // 2, width + 2, 1, 1, "wood_mid")

    # Base
    m.box(x - 2, y - 2, z, width + 4, width + 4, base_h, "stone_shade")


def build_gate(m: Model, x: int, y: int, z: int, width: int, gate_h: int, base_h: int):
    """Stone gate frame with wooden door"""
    gate_z = z + base_h
    pillar_w = 2

    # Left stone pillar
    m.box(x, y, gate_z, pillar_w, 3, gate_h, "stone_dark2")
    m.box(x, y, gate_z, pillar_w, 1, 2, "stone_dark")

    # Right stone pillar
    m.box(x + width - pillar_w, y, gate_z, pillar_w, 3, gate_h, "stone_dark2")
    m.box(x + width - pillar_w, y, gate_z, pillar_w, 1, 2, "stone_dark")

    # Wooden door
    door_width = width - pillar_w * 2 - 1
    m.box(x + pillar_w, y, gate_z + 1, door_width, 1, gate_h - 2, "wood_dark")

    # Cross brace
    m.box(x + pillar_w, y, gate_z + gate_h // 2, door_width, 1, 1, "wood_mid")

    # Base
    m.box(x - 2, y - 2, z, width + 4, width + 4, base_h, "stone_shade")


def build_stairs(m: Model, x: int, y: int, z: int, width: int, num_steps: int, base_h: int):
    """Stone staircase"""
    stair_z = z + base_h
    step_height = 2
    step_depth = 2

    for step in range(num_steps):
        step_y = y + step * step_depth
        step_h = step * step_height

        # Step block
        m.box(x, step_y, stair_z + step_h, width, step_depth, step_height,
              "stone_light" if step % 2 == 0 else "stone_mid")

        # Shade on front
        m.box(x, step_y, stair_z + step_h, width, 1, step_height, "stone_dark2")

    # Base
    m.box(x - 2, y - 2, z, width + 4, num_steps * step_depth + 4, base_h, "stone_shade")
