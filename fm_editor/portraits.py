"""Read and replace the 48x48 opponent pictures stored in WA_MRG.MRG."""
import struct
from PIL import Image

BASE = 0xF55000
RECORD = 0x980
SIDE = 48


def read(wa, portrait_id):
    if not 0 <= portrait_id < 40:
        raise ValueError('Portrait index is outside the game portrait bank.')
    start = BASE + portrait_id * RECORD
    rec = wa[start:start + RECORD]
    if len(rec) != RECORD:
        raise ValueError('Portrait record is truncated.')
    palette = []
    for i in range(64):
        word = struct.unpack_from('<H', rec, 0x900 + i * 2)[0]
        channels = tuple(min(255, ((word >> shift) & 31) * 255 // 31) for shift in (0, 5, 10))
        palette.append(channels)
    out = Image.new('RGB', (SIDE, SIDE))
    out.putdata([palette[min(index, 63)] for index in rec[:0x900]])
    return out


def write(wa, portrait_id, image):
    if not 1 <= portrait_id <= 39:
        raise ValueError('Only the 39 duelist portraits can be replaced.')
    image = image.convert('RGB')
    width, height = image.size
    scale = max(SIDE / width, SIDE / height)
    image = image.resize((max(SIDE, round(width * scale)), max(SIDE, round(height * scale))), Image.Resampling.LANCZOS)
    left, top = (image.width - SIDE) // 2, (image.height - SIDE) // 2
    image = image.crop((left, top, left + SIDE, top + SIDE))
    q = image.quantize(colors=63, method=Image.Quantize.MEDIANCUT)
    raw = q.tobytes()
    palette = (q.getpalette() or [])[:63 * 3]
    palette.extend([0] * (63 * 3 - len(palette)))
    pixels = bytes(min(63, i + 1) for i in raw)
    colors = bytearray(128)
    for i in range(63):
        r, g, b = palette[i * 3:i * 3 + 3]
        word = ((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)) or 0x8000
        struct.pack_into('<H', colors, (i + 1) * 2, word)
    start = BASE + portrait_id * RECORD
    wa[start:start + 0x900] = pixels
    wa[start + 0x900:start + 0x980] = colors
