"""Write a linear BPS patch while the disc exporter produces sectors."""
import struct
import zlib


def number(value):
    data = bytearray()
    while value >= 128:
        data.append(value & 127)
        value = (value >> 7) - 1
    data.append(value | 128)
    return data


class BpsWriter:
    def __init__(self, output, size):
        self.output = output
        self.size = size
        self.position = self.unchanged = 0
        self.source_crc = self.target_crc = self.patch_crc = 0
        self.write(b'BPS1' + number(size) + number(size) + number(0))

    def write(self, data):
        self.output.write(data)
        self.patch_crc = zlib.crc32(data, self.patch_crc)

    def flush_unchanged(self):
        if self.unchanged:
            self.write(number((self.unchanged - 1) << 2))
            self.unchanged = 0

    def sector(self, original, edited):
        self.position += len(original)
        self.source_crc = zlib.crc32(original, self.source_crc)
        self.target_crc = zlib.crc32(edited, self.target_crc)
        if original == edited:
            self.unchanged += len(original)
            return
        # Split at unchanged gaps so a changed card and its sector ECC can
        # share one sector without embedding the unchanged payload in between.
        start = last = None
        cursor = 0
        for i, (before, after) in enumerate(zip(original, edited)):
            if before == after:
                continue
            if start is not None and i - last > 6:
                self.literal(edited, cursor, start, last + 1)
                cursor, start = last + 1, None
            if start is None:
                start = i
            last = i
        self.literal(edited, cursor, start, last + 1)
        self.unchanged += len(edited) - last - 1

    def literal(self, data, cursor, start, end):
        self.unchanged += start - cursor
        self.flush_unchanged()
        self.write(number(((end - start - 1) << 2) | 1))
        self.write(data[start:end])

    def finish(self):
        if self.position != self.size:
            raise ValueError('Source image size changed during export.')
        self.flush_unchanged()
        self.write(struct.pack('<II', self.source_crc, self.target_crc))
        self.output.write(struct.pack('<I', self.patch_crc))
