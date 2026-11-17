"""Extract the card type, attribute and Guardian Star icons from WA_MRG.MRG."""
from PIL import Image


# The retail card-view texture and palette, recorded relative to WA_MRG.MRG.
CARD_SHEET = 0xEFE800
CARD_PALETTES = 0xF06800
ATTRIBUTE_PALETTE = 0x1E00

# The card-description glyph page holds the 24 type icons followed by the
# ten Guardian Star glyphs (Mars through Venus).
BOOT_SECTOR = 0x1690
ICON_SECTOR = BOOT_SECTOR + 16
ICON_CLUT_SECTOR = BOOT_SECTOR + 48
SECTOR_SIZE = 2048


def _rgb15(word):
    return ((word & 31) << 3, ((word >> 5) & 31) << 3, ((word >> 10) & 31) << 3)


def _glyph_icon(wa, number):
    if not 0 <= number <= 33:
        return None
    page_at = ICON_SECTOR * SECTOR_SIZE
    clut_at = ICON_CLUT_SECTOR * SECTOR_SIZE
    page = wa[page_at:page_at + 16 * SECTOR_SIZE]
    cluts = wa[clut_at:clut_at + 2 * SECTOR_SIZE]
    if len(page) != 16 * SECTOR_SIZE or len(cluts) != 2 * SECTOR_SIZE:
        return None

    u = ((number & 7) * 16 - 0x80) & 0xFF
    v = (number & 0x38) * 2
    row = min(number, 0x18)
    cx = 0x200 + (row & 15) * 16
    cy = 0xF9 + (row >> 4)
    palette_at = (cy - 0xF8) * 512 + (cx - 0x200) * 2
    if not any(cluts[palette_at:palette_at + 32]):
        return None

    image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    pixels = image.load()
    visible = False
    for y in range(16):
        for x in range(16):
            tx = u + x
            packed = page[(v + y) * 128 + tx // 2]
            color_index = packed >> (4 * (tx & 1)) & 15
            offset = palette_at + color_index * 2
            word = cluts[offset] | cluts[offset + 1] << 8
            alpha = 0 if color_index == 0 or word == 0 else 255
            pixels[x, y] = (*_rgb15(word), alpha)
            visible = visible or alpha != 0
    return image if visible else None


def _attribute_icon(wa, number):
    if not 0 <= number < 8:
        return None
    palette_at = CARD_PALETTES + ATTRIBUTE_PALETTE + 0x20 * number
    if len(wa) < max(CARD_SHEET + (144 + 16) * 128, palette_at + 32):
        return None

    image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    pixels = image.load()
    visible = False
    for y in range(16):
        for x in range(16):
            tx = 16 * number + x
            packed = wa[CARD_SHEET + (128 + y) * 128 + tx // 2]
            color_index = packed >> (4 * (tx & 1)) & 15
            offset = palette_at + color_index * 2
            word = wa[offset] | wa[offset + 1] << 8
            alpha = 0 if color_index == 0 or word == 0 else 255
            pixels[x, y] = (*_rgb15(word), alpha)
            visible = visible or alpha != 0
    return image if visible else None


def extract_card_list_icons(wa):
    """Return original game sprites indexed by card type, attribute and star ID."""
    return {
        'type': [_glyph_icon(wa, i) for i in range(24)],
        'attribute': [_attribute_icon(wa, i) for i in range(8)],
        'guardian': [None] + [_glyph_icon(wa, 0x17 + i) for i in range(1, 11)],
    }
