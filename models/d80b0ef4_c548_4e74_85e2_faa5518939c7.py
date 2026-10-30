"""Street lamp with a hanging lantern — reference/d80b0ef4-c548-4e74-85e2-faa5518939c7.png

Layout (x right, y depth with y=0 front, z up); scale: pole = 6 voxels square.
  stone base    stepped cream stone pedestal centred on the pole, 22 wide at the
                bottom: plinth 22 / step 16 / column 12 / cap 16 / top slab 14
  wooden pole   dark brown 6x6 post from the base to the top, with a 12-wide
                foot collar, 8-wide collars low and in the middle, a 6-tall
                top collar and a stacked finial (6 / 2 / 4 wide)
  arm           4-deep beam along +x from the top collar, a 4-step stair-step
                brace under it, an 8x8 end cap with a small cube on top
  lantern       hangs under the end cap: neck, stepped roof (6 / 8 / 14),
                10x10 glowing body with corner posts and 3 rails (2 panes per face),
                12-wide bottom plate and a small knob
"""
from voxtool import Model

NAME = "d80b0ef4_c548_4e74_85e2_faa5518939c7"
REFERENCE = "reference/d80b0ef4-c548-4e74-85e2-faa5518939c7.png"
VIEW = {"azimuth": 324, "elevation": 7, "fov": 0}

# --- key dimensions
PC = 11            # pole centre (x and y); the pole occupies PC-3 .. PC+3
POLE = 6
# stone base: (width, top z) per tier, bottom to top
BASE_TIERS = [(22, 9), (16, 14), (14, 24), (16, 28), (14, 30)]
FOOT_Z = 33        # top of the wooden foot collar
FOOT_W = 12
LOW_COLLAR = (46, 50)   # 8 wide
COLLAR_W = 8            # middle and top collars
MID_COLLAR = (85, 89)
TOP_COLLAR = (105, 111)
ARM_Z0, ARM_Z1 = 105, 110
ARM_D = 4
LANTERN_DX = 33    # lantern centre to pole centre along +x
LX = PC + LANTERN_DX
BODY_Z0 = 81       # bottom of the glowing lantern body
BODY_H = 13
BODY_W = 10

W, D, H = LX + 8, 2 * PC, 120


def palette(m: Model):
    # front faces are shaded x0.9 and +x faces x0.7 in the preview
    p = m.pal
    p.add("wood", "#5a3a2b"); p.add("wood_hi", "#664230"); p.add("wood_dk", "#4a3022")
    p.add("stone", "#f8e5cc"); p.add("stone2", "#eed8bc"); p.add("stone3", "#e2cbad")
    p.add("frame", "#533628")
    p.add("glow", "#f5ab36", emit=3.0)


def cbox(m: Model, cx: int, cy: int, z0: int, z1: int, w: int, c, d: int | None = None):
    """Box centred on (cx, cy) (centres sit on voxel boundaries), from z0 up to z1."""
    d = w if d is None else d
    m.box(cx - w // 2, cy - d // 2, z0, w, d, z1 - z0, c)


def stone_base(m: Model):
    z0 = 0
    for w, z1 in BASE_TIERS:
        cbox(m, PC, PC, z0, z1, w, "stone")
        z0 = z1
    m.bricks(["stone", "stone2", "stone3"], target="stone", bw=7, bh=4, p=[0.5, 0.3, 0.2], salt=3)


def pole(m: Model):
    top = TOP_COLLAR[1]
    cbox(m, PC, PC, BASE_TIERS[-1][1], top, POLE, "wood")
    cbox(m, PC, PC, BASE_TIERS[-1][1], FOOT_Z, FOOT_W, "wood_hi")
    cbox(m, PC, PC, *LOW_COLLAR, 8, "wood_hi")
    cbox(m, PC, PC, *MID_COLLAR, COLLAR_W, "wood_hi")
    cbox(m, PC, PC, *TOP_COLLAR, COLLAR_W, "wood_hi")
    # finial: cap, neck, cube
    cbox(m, PC, PC, top, top + 3, 6, "wood")
    cbox(m, PC, PC, top + 3, top + 5, 2, "wood_dk")
    cbox(m, PC, PC, top + 5, top + 8, 4, "wood")


def arm(m: Model):
    x0 = PC + POLE // 2
    m.box(x0, PC - ARM_D // 2, ARM_Z0, LX - x0, ARM_D, ARM_Z1 - ARM_Z0, "wood")
    # stair-step brace: 4 steps of 3 (the lowest one 4), highest step reaches furthest out
    bz = ARM_Z0 - 12
    for i in range(4):
        sx = x0 + max(0, 3 * i - 3)
        ex = x0 + 3 * i + 5
        z0 = bz + 3 * i - (1 if i == 0 else 0)
        m.box(sx, PC - ARM_D // 2, z0, ex - sx, ARM_D, bz + 3 * i + 3 - z0, "wood")
    # end cap with a small cube on top
    cbox(m, LX, PC, ARM_Z0 - 1, ARM_Z1, 8, "wood_hi")
    cbox(m, LX, PC, ARM_Z1, ARM_Z1 + 3, 4, "wood")


def lantern(m: Model):
    z_top = BODY_Z0 + BODY_H
    # hanger and stepped roof
    cbox(m, LX, PC, z_top + 7, ARM_Z0 - 1, 2, "frame")
    cbox(m, LX, PC, z_top + 4, z_top + 7, 6, "frame")
    cbox(m, LX, PC, z_top + 2, z_top + 4, 8, "frame")
    cbox(m, LX, PC, z_top, z_top + 2, 14, "frame")
    # body: glowing core one voxel in from the frame
    x0, y0 = LX - BODY_W // 2, PC - BODY_W // 2
    m.box(x0 + 1, y0 + 1, BODY_Z0, BODY_W - 2, BODY_W - 2, BODY_H, "glow")
    for dx in (0, BODY_W - 1):
        for dy in (0, BODY_W - 1):
            m.box(x0 + dx, y0 + dy, BODY_Z0, 1, 1, BODY_H, "frame")
    for z in (BODY_Z0, BODY_Z0 + BODY_H // 2, BODY_Z0 + BODY_H - 1):
        m.shell(x0, y0, z, BODY_W, BODY_W, 1, "frame", t=1, top=False, bottom=False)
    # bottom plate and knob
    cbox(m, LX, PC, BODY_Z0 - 2, BODY_Z0, 12, "frame")
    cbox(m, LX, PC, BODY_Z0 - 5, BODY_Z0 - 2, 4, "frame")


def build() -> Model:
    m = Model(W, D, H, seed=11)
    palette(m)
    stone_base(m)
    pole(m)
    arm(m)
    lantern(m)
    return m
