"""
Stone brick walls and pillars kit.
4 modular wall structures with professional game-ready quality.
"""

NAME = "model_1031_0653"
REFERENCE = "reference/화면_캡처_2026-10-31_065321.png"
VIEW = {"azimuth": 0, "elevation": 40, "fov": 0}
CUTOUT = {"keep": "all"}

RES = 3


def build():
    from voxtool.model import Model

    # Dimensions
    BRICK = 3      # Brick unit size (higher RES = bigger design units)
    MORTAR = 1     # Mortar/gap between bricks
    DEPTH = 5      # Wall depth (front to back)
    BASE = 2       # Base platform height
    UNIT = BRICK + MORTAR

    # Brick counts per wall: (width, height)
    W1 = (4, 2)    # Left wall (shorter)
    W2 = (4, 4)    # Center-left wall (tallest)
    W3 = (4, 3)    # Center-right wall
    W4 = (2, 3)    # Right pillar (narrow)

    walls = [W1, W2, W3, W4]
    max_h = max(w[1] for w in walls)

    # Grid dimensions
    total_w = sum(w[0] for w in walls) * BRICK + 15
    total_d = DEPTH + 8
    total_h = max_h * UNIT + BASE + 3

    m = Model(total_w, total_d, total_h, seed=0x1031, res=RES)

    # Professional color palette
    m.pal.add("brick_light", "#d4a574", emit=0)    # Light tan (front face highlight)
    m.pal.add("brick_mid", "#c9945c", emit=0)      # Medium tan (front main)
    m.pal.add("brick_dark", "#9b7642", emit=0)     # Dark tan (mortar shadow)
    m.pal.add("mortar", "#7a6d5c", emit=0)         # Mortar color
    m.pal.add("shadow", "#5a5246", emit=0)         # Deep shadow (base)

    def wall_section(x, y, z, w_bricks, h_bricks, label):
        """Draw a wall with professional brick pattern and shading"""
        with m.part(label):
            # Base platform with shadow gradient
            m.box(x, y, z, w_bricks * BRICK, DEPTH, BASE, "shadow")
            # Base light edge
            m.box(x, y, z + BASE - 1, w_bricks * BRICK, DEPTH, 1, "mortar")

            # Brick courses with alternating pattern
            for row in range(h_bricks):
                for col in range(w_bricks):
                    bx = x + col * BRICK
                    by = y
                    bz = z + BASE + row * UNIT

                    # Brick color varies by row for depth
                    if row % 3 == 0:
                        color = "brick_light"
                    elif row % 3 == 1:
                        color = "brick_mid"
                    else:
                        color = "brick_dark"

                    # Front brick face
                    m.box(bx, by, bz, BRICK, BRICK, BRICK, color)

                    # Mortar line (front edge)
                    m.box(bx + BRICK, by, bz, MORTAR, BRICK, BRICK, "mortar")

                    # Back depth (darker for shadow effect)
                    if DEPTH > BRICK:
                        m.box(bx, by + BRICK, bz, BRICK, DEPTH - BRICK, BRICK, "brick_dark")

            # Top capping stone
            top_z = z + BASE + h_bricks * UNIT
            m.box(x, y, top_z, w_bricks * BRICK, DEPTH, 2, "brick_light")

    # Position walls
    x_start = 3
    y_start = 3
    z_start = 0

    wall_section(x_start, y_start, z_start, W1[0], W1[1], "wall1")
    x_start += W1[0] * BRICK + 4

    wall_section(x_start, y_start, z_start, W2[0], W2[1], "wall2")
    x_start += W2[0] * BRICK + 4

    wall_section(x_start, y_start, z_start, W3[0], W3[1], "wall3")
    x_start += W3[0] * BRICK + 4

    wall_section(x_start, y_start, z_start, W4[0], W4[1], "wall4")

    return m
