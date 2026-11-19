"""
Card Graphics Extractor and Injector for Yu-Gi-Oh! Forbidden Memories.

Directly extracts and injects authentic in-game card artwork from DATA/WA_MRG.MRG:
  - 722 Card Miniatures (40x32, 64-color CLUT) located at sectors 0..721.
  - 722 Large Card Artworks (102x96, 256-color CLUT) located at sectors 722..5775 (7 sectors per card).
"""

import struct
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# WA_MRG layout for card graphics
SECTOR_SIZE = 2048
MINI_START_SECTOR = 0           # 40x32 miniatures (1 sector each, 722 cards)
MINI_PIXELS = 40 * 32           # 1280 bytes
MINI_CLUT_COLORS = 64           # 128 bytes (uint16 BGR555 LE)

LARGE_START_SECTOR = 722        # 102x96 large artwork (7 sectors = 14336 bytes each)
LARGE_SECTORS_PER_CARD = 7
LARGE_WIDTH = 102
LARGE_HEIGHT = 96
LARGE_PIXELS = LARGE_WIDTH * LARGE_HEIGHT  # 9792 bytes
LARGE_CLUT_COLORS = 256         # 512 bytes (uint16 BGR555 LE)
CARD_RECORD_TITLE_OFFSET = 10304
CARD_RECORD_THUMBNAIL_OFFSET = 10976
CARD_RECORD_SIZE = LARGE_SECTORS_PER_CARD * SECTOR_SIZE
TITLE_WIDTH = 96
TITLE_HEIGHT = 14
TITLE_BYTES = TITLE_WIDTH * TITLE_HEIGHT // 2


def bgr555_to_rgb(val: int) -> Tuple[int, int, int]:
    """Converts 16-bit PS1 BGR555 color into 24-bit RGB (r, g, b)."""
    r = (val & 0x1F) << 3
    g = ((val >> 5) & 0x1F) << 3
    b = ((val >> 10) & 0x1F) << 3
    return (r, g, b)


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Converts 24-bit RGB color into 16-bit PS1 BGR555."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


class CardGraphicsDatabase:
    """
    Manages loading, extracting, caching and modifying in-game card artwork.
    """

    def __init__(self):
        self._wa_bytes: Optional[bytes] = None
        self._custom_artworks: Dict[int, Image.Image] = {}
        self._cached_images: Dict[int, Image.Image] = {}

    def set_wa_data(self, wa_bytes: bytes):
        """Sets or updates the underlying WA_MRG data source."""
        self._wa_bytes = wa_bytes
        self._cached_images.clear()

    def has_data(self) -> bool:
        return self._wa_bytes is not None and len(self._wa_bytes) >= (LARGE_START_SECTOR + 722 * LARGE_SECTORS_PER_CARD) * SECTOR_SIZE

    def get_card_art(self, card_id: int) -> Optional["Image.Image"]:
        """
        Retrieves the 102x96 artwork for card_id (1..722).
        Returns custom artwork if authored, or original extracted game artwork.
        """
        if not HAS_PIL:
            return None

        if card_id in self._custom_artworks:
            return self._custom_artworks[card_id]

        if card_id in self._cached_images:
            return self._cached_images[card_id]

        if not self.has_data():
            return None

        extracted = self._extract_large_art(card_id)
        if extracted is not None:
            self._cached_images[card_id] = extracted
        return extracted

    def set_custom_art(self, card_id: int, image: "Image.Image"):
        """Stores a custom artwork image for a card."""
        if not HAS_PIL or not (1 <= card_id <= 722):
            return
        # Ensure 102x96 dimensions
        if image.size != (LARGE_WIDTH, LARGE_HEIGHT):
            resized = image.resize((LARGE_WIDTH, LARGE_HEIGHT), Image.Resampling.LANCZOS)
        else:
            resized = image.copy()
        original = self._cached_images.get(card_id)
        if original is None:
            original = self._extract_large_art(card_id)
        if original is not None and resized.convert("RGB").tobytes() == original.convert("RGB").tobytes():
            self.clear_custom_art(card_id)
        else:
            self._custom_artworks[card_id] = resized

    def has_custom_art(self, card_id: int) -> bool:
        return card_id in self._custom_artworks

    def clear_custom_art(self, card_id: int):
        """Removes custom artwork, reverting to original game art."""
        self._custom_artworks.pop(card_id, None)

    def _extract_large_art(self, card_id: int) -> Optional["Image.Image"]:
        """Extracts the 102x96 256-color image for card_id directly from WA_MRG."""
        if not (1 <= card_id <= 722) or self._wa_bytes is None:
            return None

        sec = LARGE_START_SECTOR + (card_id - 1) * LARGE_SECTORS_PER_CARD
        offset = sec * SECTOR_SIZE
        end_offset = offset + LARGE_SECTORS_PER_CARD * SECTOR_SIZE

        if end_offset > len(self._wa_bytes):
            return None

        block = self._wa_bytes[offset:end_offset]
        pixel_data = block[:LARGE_PIXELS]
        pal_data = block[LARGE_PIXELS : LARGE_PIXELS + LARGE_CLUT_COLORS * 2]

        palette = [
            bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0])
            for i in range(LARGE_CLUT_COLORS)
        ]

        img = Image.new('RGB', (LARGE_WIDTH, LARGE_HEIGHT))
        for y in range(LARGE_HEIGHT):
            row_off = y * LARGE_WIDTH
            for x in range(LARGE_WIDTH):
                idx = pixel_data[row_off + x]
                img.putpixel((x, y), palette[idx])

        return img

    def _extract_mini_art(self, card_id: int) -> Optional["Image.Image"]:
        """Extracts the 40x32 64-color miniature thumbnail for card_id."""
        if not (1 <= card_id <= 722) or self._wa_bytes is None:
            return None

        sec = MINI_START_SECTOR + (card_id - 1)
        offset = sec * SECTOR_SIZE
        if offset + SECTOR_SIZE > len(self._wa_bytes):
            return None

        sec_data = self._wa_bytes[offset : offset + SECTOR_SIZE]
        pixels = sec_data[:MINI_PIXELS]
        pal_data = sec_data[MINI_PIXELS : MINI_PIXELS + MINI_CLUT_COLORS * 2]

        palette = [
            bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0])
            for i in range(MINI_CLUT_COLORS)
        ]

        img = Image.new('RGB', (40, 32))
        for y in range(32):
            for x in range(40):
                idx = pixels[y * 40 + x] & 0x3F
                img.putpixel((x, y), palette[idx])

        return img

    @staticmethod
    def _palette_bytes(palette, color_count: int, transparent_zero: bool) -> bytearray:
        """Encode a Pillow palette as PS1 BGR555, with the game's reserved index 0."""
        result = bytearray(color_count * 2)
        for index in range(color_count):
            struct.pack_into('<H', result, index * 2, 0x8000)
        first = 1 if transparent_zero else 0
        available = min(len(palette) // 3, color_count - first)
        for color_index in range(available):
            index = first + color_index
            p = color_index * 3
            r, g, b = palette[p:p + 3]
            color = rgb_to_bgr555(r, g, b)
            # A zero CLUT word is transparent on PS1; preserve near-black as
            # the closest nonzero 5-bit color instead of making it disappear.
            if color == 0:
                color = 1
            struct.pack_into('<H', result, index * 2, color)
        return result

    @staticmethod
    def _thumbnail_source(image):
        """Center-crop to the 5:4 image window used by the duel thumbnail."""
        width, height = image.size
        ratio = 40 / 32
        if width / height > ratio:
            cropped_width = round(height * ratio)
            left = (width - cropped_width) // 2
            return image.crop((left, 0, left + cropped_width, height))
        cropped_height = round(width / ratio)
        top = (height - cropped_height) // 2
        return image.crop((0, top, width, top + cropped_height))

    @staticmethod
    def _title_plate(name: str) -> bytes:
        """Build the 96x14 4bpp card-name strip stored in each card art record."""
        if not HAS_PIL:
            return bytes(TITLE_BYTES)
        font = None
        windows = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        for candidate in (windows / 'times.ttf', windows / 'timesi.ttf',
                          Path('/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf'),
                          Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf')):
            try:
                font = ImageFont.truetype(str(candidate), 52)
                break
            except (OSError, ValueError):
                continue
        if font is None:
            font = ImageFont.load_default()
        probe = Image.new('L', (8, 56), 255)
        probe_draw = ImageDraw.Draw(probe)
        try:
            bounds = probe_draw.textbbox((0, 0), name, font=font, anchor='ls')
            text_width = max(1, bounds[2] - bounds[0])
            left_bearing = bounds[0]
            anchor = 'ls'
            text_y = 44
        except (TypeError, ValueError):
            bounds = probe_draw.textbbox((0, 0), name, font=font)
            text_width = max(1, bounds[2] - bounds[0])
            left_bearing = bounds[0]
            anchor = None
            text_y = 4
        margin, room = 12, (TITLE_WIDTH - 6) * 4
        strip = Image.new('L', (max(384, text_width + margin * 2), 56), 255)
        draw = ImageDraw.Draw(strip)
        position = (margin - left_bearing, text_y)
        if anchor:
            draw.text(position, name, font=font, fill=0, anchor=anchor)
        else:
            draw.text(position, name, font=font, fill=0)
        if text_width > room:
            fitted_width = max(1, round(text_width + margin * 2) * room // text_width)
            strip = strip.resize((fitted_width, 56), Image.Resampling.LANCZOS)
        strip = strip.crop((0, 0, 384, 56)).resize((TITLE_WIDTH, TITLE_HEIGHT), Image.Resampling.LANCZOS)
        pixels = strip.tobytes()
        plate = bytearray(TITLE_BYTES)
        thresholds = (247, 221, 179, 140, 109, 69, 23)
        for y in range(TITLE_HEIGHT):
            for x in range(TITLE_WIDTH):
                coverage = 255 - pixels[y * TITLE_WIDTH + x]
                ink = next((i + 1 for i, threshold in enumerate(thresholds) if coverage >= threshold), 0)
                offset = y * (TITLE_WIDTH // 2) + x // 2
                if x & 1:
                    plate[offset] = (plate[offset] & 0x0F) | (ink << 4)
                else:
                    plate[offset] = (plate[offset] & 0xF0) | ink
        return bytes(plate)

    def apply_to_wa(self, target_wa: bytearray, cards=None, original_cards=None) -> int:
        """
        Inject changed images and names into the art record and duel thumbnail
        copies in WA_MRG. Returns the number of card records touched.
        """
        if not HAS_PIL:
            return 0
        art_ids = set(self._custom_artworks)
        title_ids = set()
        if cards and original_cards:
            title_ids = {cid for cid, card in cards.items()
                         if cid in original_cards and card.name != original_cards[cid].name}
        touched = 0
        for card_id in sorted(art_ids | title_ids):
            if not (1 <= card_id <= 722):
                continue
            record_offset = (LARGE_START_SECTOR + (card_id - 1) * LARGE_SECTORS_PER_CARD) * SECTOR_SIZE
            record_end = record_offset + CARD_RECORD_SIZE
            if record_end > len(target_wa):
                raise ValueError(f'WA_MRG is truncated before card {card_id} artwork.')
            if card_id in art_ids:
                img = self._custom_artworks[card_id].convert('RGB')
                large = img.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
                large_palette = self._palette_bytes(large.getpalette()[:255 * 3], LARGE_CLUT_COLORS, True)
                large_pixels = bytes(value + 1 for value in large.tobytes())
                target_wa[record_offset:record_offset + LARGE_PIXELS] = large_pixels
                target_wa[record_offset + LARGE_PIXELS:record_offset + LARGE_PIXELS + 512] = large_palette

                mini_source = self._thumbnail_source(img).resize((40, 32), Image.Resampling.LANCZOS)
                mini = mini_source.quantize(colors=63, method=Image.Quantize.MEDIANCUT)
                mini_palette = self._palette_bytes(mini.getpalette()[:63 * 3], 64, True)
                mini_pixels = bytes(value + 1 for value in mini.tobytes())
                thumbnail = mini_pixels + bytes(mini_palette)
                # Duel hand/field uses this standalone copy; card-detail views
                # load the duplicate embedded in the seven-sector art record.
                standalone = (card_id - 1) * SECTOR_SIZE
                target_wa[standalone:standalone + len(thumbnail)] = thumbnail
                embedded = record_offset + CARD_RECORD_THUMBNAIL_OFFSET
                target_wa[embedded:embedded + len(thumbnail)] = thumbnail
            if card_id in title_ids:
                title = self._title_plate(cards[card_id].name)
                start = record_offset + CARD_RECORD_TITLE_OFFSET
                target_wa[start:start + TITLE_BYTES] = title
            touched += 1
        return touched
