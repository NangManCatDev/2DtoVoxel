from voxtool import Model, Palette

NAME = "e202255d_23ec_40cf_acec_a7ce203cb095_2"
REFERENCE = "reference/e202255d-23ec-40cf-acec-a7ce203cb095.png"
VIEW = {"azimuth": 30, "elevation": 25, "fov": 0}

BRICK_SIZE = 2
FOUNDATION = 1

def brick_wall(m, x, y, z, width, height, depth=2):
    """Build a brick wall with mortar lines."""
    brick_color = "stone_light"
    mortar_color = "mortar"

    for row in range(height):
        for col in range(width):
            if (row + col) % 2 == 0:
                m.box(x + col * BRICK_SIZE, y, z + row * BRICK_SIZE,
                      BRICK_SIZE, depth, BRICK_SIZE, brick_color)
            else:
                m.box(x + col * BRICK_SIZE, y, z + row * BRICK_SIZE,
                      BRICK_SIZE, depth, BRICK_SIZE, brick_color)

def picket_fence(m, x, y, z, length, height=6):
    """Build a picket fence."""
    post_color = "wood_dark"
    picket_color = "wood_dark"

    # Posts
    post_spacing = 3
    for i in range(0, length, post_spacing):
        m.box(x + i, y, z, 2, 1, height, post_color)

    # Pickets
    picket_spacing = 2
    for i in range(0, length, picket_spacing):
        m.box(x + i, y, z + 2, 1, 1, height - 2, picket_color)

def stone_gate(m, x, y, z, width=8, height=10):
    """Build a stone gate with wooden door."""
    stone_color = "stone_light"
    wood_color = "wood_dark"

    # Pillars
    m.box(x, y, z, 2, 2, height, stone_color)
    m.box(x + width - 2, y, z, 2, 2, height, stone_color)

    # Top lintel
    m.box(x, y, z + height - 2, width, 2, 2, stone_color)

    # Wooden door with X pattern
    door_x = x + 2
    door_z = z + 1
    m.box(door_x, y, door_z, width - 4, 1, height - 3, wood_color)

    # Door planks
    plank_width = (width - 4) // 3
    for i in range(3):
        m.box(door_x + i * plank_width, y, door_z, plank_width, 1, height - 3, wood_color)

def stone_stairs(m, x, y, z, width=8, steps=4):
    """Build stone stairs."""
    stone_color = "stone_light"

    for i in range(steps):
        step_height = i + 1
        m.box(x, y, z + i * 2, width, 2, step_height * 2, stone_color)

def build():
    m = Model(80, 30, 20, res=1)

    # Palette
    m.pal.add("stone_light", "#c9b99a")
    m.pal.add("stone_dark", "#6b5d52")
    m.pal.add("mortar", "#7a6d63")
    m.pal.add("wood_dark", "#5a4a3a")
    m.pal.add("wood_light", "#8b7a6b")

    # Foundation/base for all pieces
    base_z = 0

    # Row 1: Various stone walls
    with m.part("wall_1"):
        m.box(2, 0, base_z, 14, 2, 1, "stone_dark")  # Foundation
        brick_wall(m, 2, 0, base_z + 1, 7, 4)  # Wall

    with m.part("wall_2"):
        m.box(20, 0, base_z, 18, 2, 1, "stone_dark")  # Foundation
        brick_wall(m, 20, 0, base_z + 1, 9, 5)  # Taller wall

    with m.part("wall_3"):
        m.box(42, 0, base_z, 20, 2, 1, "stone_dark")  # Foundation
        brick_wall(m, 42, 0, base_z + 1, 10, 5)  # Wide wall

    with m.part("wall_4"):
        m.box(66, 0, base_z, 10, 2, 1, "stone_dark")  # Foundation
        brick_wall(m, 66, 0, base_z + 1, 5, 4)  # Small wall

    # Row 2: Fences and gates
    with m.part("fence_1"):
        m.box(2, 0, base_z + 20, 10, 1, 1, "stone_dark")  # Foundation
        picket_fence(m, 2, 0, base_z + 21, 10, 5)

    with m.part("fence_2"):
        m.box(16, 0, base_z + 20, 10, 1, 1, "stone_dark")  # Foundation
        picket_fence(m, 16, 0, base_z + 21, 10, 6)

    with m.part("gate"):
        stone_gate(m, 32, 0, base_z + 20, 10, 9)

    with m.part("stairs"):
        m.box(50, 0, base_z + 20, 12, 2, 1, "stone_dark")  # Foundation
        stone_stairs(m, 50, 0, base_z + 21, 12, 4)

    return m
