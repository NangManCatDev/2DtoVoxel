"""Medieval stone and wood game assets: 4 walls, 2 fences, 1 gate, 1 stairs."""

from voxtool.model import Model, Palette

NAME = "e202255d_23ec_40cf_acec_a7ce203cb095_4"
REFERENCE = "reference/e202255d-23ec-40cf-acec-a7ce203cb095.png"
VIEW = {"azimuth": 45, "elevation": 30, "fov": 35}
CUTOUT = {"keep": "all"}

RES = 1

def brick_wall(m, x, y, z, width, height, depth=1):
    """Simple brick wall with staggered pattern."""
    for row in range(height):
        for col in range(width):
            if (row + col) % 2 == 0:
                color = "stone_light" if row % 3 == 0 else "stone_mid"
            else:
                color = "stone_dark" if row % 4 == 2 else "stone_shadow"
            m.box(x + col, y + row, z, 1, depth, 1, color)

def base_platform(m, x, y, z, width, depth):
    """Stone foundation/platform."""
    for dx in range(width):
        for dy in range(depth):
            color = "stone_mid" if (dx + dy) % 2 == 0 else "stone_dark"
            m.box(x + dx, y, z + dy, 1, 1, 1, color)

def build():
    m = Model(200, 50, 100, seed=42, res=RES)

    # Palette setup
    m.pal.add("stone_light", "#d1ba9d")
    m.pal.add("stone_mid", "#b29d85")
    m.pal.add("stone_dark", "#8f7e6d")
    m.pal.add("stone_shadow", "#6a5848")
    m.pal.add("stone_black", "#3a2e25")
    m.pal.add("wood_light", "#a87d50")
    m.pal.add("wood_mid", "#7d5f42")
    m.pal.add("wood_dark", "#5c4830")

    # Wall 1: Short horizontal wall
    with m.part("wall_short"):
        base_platform(m, 5, 0, 0, 13, 2)
        brick_wall(m, 5, 0, 2, 13, 4, 2)
        for x in range(5, 18):
            m.box(x, 0, 6, 1, 2, 1, "stone_mid")

    # Wall 2: Tall wall
    with m.part("wall_tall"):
        base_platform(m, 25, 0, 0, 16, 2)
        brick_wall(m, 25, 0, 2, 16, 6, 2)
        for x in range(25, 41):
            m.box(x, 0, 8, 1, 2, 1, "stone_mid")

    # Wall 3: Square fortress
    with m.part("wall_square"):
        base_platform(m, 50, 0, 0, 15, 3)
        brick_wall(m, 50, 0, 2, 15, 5, 3)
        for x in range(50, 65):
            m.box(x, 0, 7, 1, 3, 1, "stone_mid")

    # Wall 4: Tall tower
    with m.part("tower"):
        base_platform(m, 75, 0, 0, 8, 2)
        brick_wall(m, 75, 0, 2, 8, 6, 2)
        for x in range(75, 83):
            m.box(x, 0, 8, 1, 2, 1, "stone_mid")

    # Fence 1: Wooden palisade short
    with m.part("fence_short"):
        base_platform(m, 10, 15, 0, 10, 2)
        for i in range(10):
            m.box(10 + i, 15, 2, 1, 1, 4, "wood_dark")

    # Fence 2: Wooden palisade tall
    with m.part("fence_tall"):
        base_platform(m, 30, 15, 0, 10, 2)
        for i in range(10):
            m.box(30 + i, 15, 2, 1, 1, 6, "wood_dark")

    # Gate: Wood gate with stone pillars
    with m.part("gate"):
        base_platform(m, 55, 15, 0, 10, 2)
        # Stone pillars
        m.box(55, 15, 2, 2, 2, 5, "stone_mid")
        m.box(62, 15, 2, 2, 2, 5, "stone_mid")
        # Wood gate
        m.box(57, 15, 2, 4, 1, 5, "wood_dark")

    # Stairs
    with m.part("stairs"):
        base_platform(m, 90, 15, 0, 12, 3)
        for step in range(5):
            for x in range(3):
                for y in range(2):
                    color = "stone_light" if step % 2 == 0 else "stone_mid"
                    m.box(90 + x, 15 + y, step + 2, 1, 1, 1, color)
            for y in range(2):
                m.box(93 + step, 15 + y, step + 2, 1, 1, 1, "stone_dark")

    return m
