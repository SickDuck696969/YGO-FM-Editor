"""Fresh PS1 memory cards, using the retail save integrity algorithm."""
import binascii
import functools
import operator
import struct
from collections import Counter

REGIONS = ((0, 0x340, 0x378, 15, 0x37C), (0x380, 0x6C, 0x3F8, 4, 0x3FC), (0x400, 0x204, 0x624, 8, 0x604))


def mask_words(crc, count):
    lo = hi = crc | crc << 16
    for _ in range(count):
        n = (((hi << 31) | (lo >> 1)) ^ (lo << 12)) & 0xFFFFFFFF
        hi = (hi * 2 + (lo & 1)) & 0xFFFFFFFF
        lo = n ^ (n >> 20)
        yield lo


def seal(state):
    for start, length, last, count, check in REGIONS:
        crc = binascii.crc_hqx(state[start:start + length], 0)
        struct.pack_into('<HH', state, check, crc, crc)
        for i, word in enumerate(mask_words(crc, count)):
            struct.pack_into('<I', state, last - i * 4, word)


def validate_state(state):
    if len(state) != 0x680:
        return False
    for start, length, last, count, check in REGIONS:
        crc = binascii.crc_hqx(state[start:start + length], 0)
        if struct.unpack_from('<HH', state, check) != (crc, crc):
            return False
        for i, word in enumerate(mask_words(crc, count)):
            if struct.unpack_from('<I', state, last - i * 4)[0] != word:
                return False
    return True


def frame_checksum(frame):
    frame[127] = functools.reduce(operator.xor, frame[:127], 0)
    return frame


def create_card(executable, deck, name='PLAYER', starchips=0):
    if len(deck) != 40 or any(type(c) is not int or not 1 <= c <= 722 for c in deck):
        raise ValueError('Starter deck must contain exactly 40 card IDs between 1 and 722.')
    if max(Counter(deck).values()) > 3:
        raise ValueError('The starter deck allows at most three copies of each card.')
    if not 1 <= len(name) <= 6 or not name.isascii() or not all(c.isalnum() or c == ' ' for c in name):
        raise ValueError('Player name: 1–6 English letters, digits, or spaces.')
    if not 0 <= starchips <= 999999:
        raise ValueError('Starchips must be 0–999999.')
    state = bytearray(0x680)
    struct.pack_into('<40H', state, 0, *sorted(deck))
    # Inventory excludes the forty cards held in the deck.
    for cid in deck:
        flag = 0x120 + cid
        state[0x418 + (flag >> 3)] |= 0x80 >> (flag & 7)
    fullwidth = ''.join(chr(ord(c) + 0xFEE0) if c != ' ' else '\u3000' for c in name.ljust(6))
    state[0x40C:0x418] = fullwidth.encode('shift_jis')
    checksum = functools.reduce(operator.xor, state[0x40C:0x418], 0)
    struct.pack_into('<I', state, 0x334, 0x464D00 | checksum)
    struct.pack_into('<I', state, 0x404, 1)
    struct.pack_into('<I', state, 0x5E0, starchips)
    state[0x5DC] = 0x30
    seal(state)
    header = executable[0x1C4800:0x1C4A00]
    if len(header) != 512 or header[:2] != b'SC':
        raise ValueError('The ROM has no recognized save icon/header template.')
    card = bytearray(128 * 1024)
    frame = bytearray(128)
    frame[:2] = b'MC'
    card[:128] = frame_checksum(frame)
    for block in range(1, 16):
        frame = bytearray(128)
        frame[0] = 0xA0
        frame[8:10] = b'\xff\xff'
        if block == 1:
            frame[0] = 0x51
            struct.pack_into('<I', frame, 4, 8192)
            filename = b'BASLUS-01411-YUGIOH'
            frame[10:10 + len(filename)] = filename
        card[block * 128:(block + 1) * 128] = frame_checksum(frame)
    for index in range(16, 36):
        frame = bytearray(128)
        frame[:4] = b'\xff' * 4
        frame[8:10] = b'\xff\xff'
        card[index * 128:(index + 1) * 128] = frame_checksum(frame)
    card[8192:8192 + 512] = header
    card[0x2200:0x2880] = state
    card[0x2880:0x2F00] = state
    assert validate_state(state)
    return bytes(card)
