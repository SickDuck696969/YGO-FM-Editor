"""Patch the USA results controller at the single-player trunk credit call."""
import hashlib
import struct

from .engine_patches import EnginePatchManager


ROLL_SITE = 0x12460
CREDIT_SITE = 0x12710
BODY = 0x1C9780  # Tail padding of the resident name bank, before the font.
ROLL = bytes.fromhex(
    '0486000c21800000e002848f1d80033c0a80013c38b322a43c0082a400140200'
    '03140200a85662ac3a00829000000000')
CREDIT = bytes.fromhex(
    '3c0044842586000c0000000027880008000000005d028293d002852780100200'
    '212045000000838c00000000180562940000000001004224180562a4ffff4230'
    '1027422c040040140f2702240000838c00000000180562a45d02829300000000'
    '0100423880100200212045000000838c000000001a0562940000000001004224'
    '1a0562a4ffff42301027422c3f0040140f2702240000838c278800081a0562a4')
CALL = struct.pack('<I', 0x0C000000 | (((0x80010000 + BODY - 0x800) >> 2) & 0x03FFFFFF))
PATCHED_CREDIT = CREDIT[:4] + CALL + CREDIT[8:]


def award_loop(count):
    # o32 stack frame, including 16 bytes for outgoing call arguments.
    # v0 points to DuelResultDisplayState and a0 holds the displayed card.
    words = (
        0x27BDFFE0, 0xAFBF001C, 0xAFB00018, 0xAFB10014,
        0x90480038, 0x90490039, 0x2D080003, 0x0009482B,
        0x15000002, 0x24110001, 0x00098840, 0x24100000 | count,
        # Credit each valid roll through Duel_AwardCard (including the first).
        0x2488FFFF, 0x2D0802D2, 0x11000003, 0, 0x0C008625, 0,
        0x2610FFFF, 0x12000005, 0,
        # Roll again with the same POW/TEC rank pool, then loop.
        0x0C008604, 0x02202021, 0x1000FFF4, 0x00402021,
        0x8FBF001C, 0x8FB00018, 0x8FB10014, 0x03E00008, 0x27BD0020,
    )
    return struct.pack('<30I', *words)


def _unused_name_space(exe):
    if any(exe[BODY:BODY + 120]):
        return False
    # Spaces encode as zero. Check referenced strings as well as padding.
    pointers = struct.unpack_from('<1024H', exe, 0x1C6000)
    for pointer in set(pointers):
        start = 0x1C0800 + pointer
        if BODY <= start < BODY + 120:
            return False
        if 0x1C6800 <= start < BODY:
            # Location 863 ends by transferring control to another text.
            # Previous exports truncated the final "Hiding " location's
            # three-byte text jump. The card serializer repairs that case.
            truncated = (pointer == pointers[863]
                         and exe[start:start + 7] == bytes.fromhex('23050c05061000')
                         and not any(exe[start + 7:BODY]))
            if (not truncated and exe.find(b'\xff', start, BODY) < 0
                    and exe.find(b'\xfd\x80\x8e', start, BODY) < 0):
                return False
    return True


def reward_layout(exe):
    if (len(exe) < 0x1C9800 or exe[:8] != b'PS-X EXE'
            or struct.unpack_from('<I', exe, 0x18)[0] != 0x80010000
            or struct.unpack_from('<I', exe, 0x1c)[0] < BODY + 120 - 0x800):
        return 'unsupported', None
    controller = (exe[0x120F0:ROLL_SITE] + exe[0x12490:0x126DC]
                  + exe[0x126E0:CREDIT_SITE] + exe[0x127B0:0x128B8])
    if (hashlib.sha256(controller).hexdigest() != '7047c0caadb67ff21a1b27c56d62638b7ae137a4d00ec29ea88b581e58670634'
            or hashlib.sha256(exe[0x12010:0x120F0]).hexdigest() != '3ebc4b7de43d56ccde2e61366f43f17e7b3d4e7ebf8b72eed61adb1b553aca67'):
        return 'unsupported', None
    roll, credit = exe[ROLL_SITE:0x12490], exe[CREDIT_SITE:0x127B0]
    count = exe[BODY + 44]
    if roll == ROLL and credit == PATCHED_CREDIT and 2 <= count <= 100 and exe[BODY:BODY + 120] == award_loop(count):
        return 'installed', count
    if not _unused_name_space(exe):
        return 'occupied', None
    if roll == ROLL and credit == CREDIT:
        return 'native', 1
    if EnginePatchManager.is_workshop_reward_engine(exe):
        return 'legacy', exe[0x21C0]
    return 'custom hooks', None


def set_reward_count(source, output, count):
    if not 1 <= count <= 100:
        raise ValueError('Choose between 1 and 100 cards per win.')
    kind, _ = reward_layout(source)
    if kind in ('unsupported', 'occupied'):
        raise ValueError('Cannot isolate the reward code or reserve space for it on this disc.')
    if output[ROLL_SITE:0x12490] != source[ROLL_SITE:0x12490] or output[CREDIT_SITE:0x127B0] != source[CREDIT_SITE:0x127B0]:
        raise ValueError('Another edit overlaps the victory routine.')
    if kind == 'installed' and output[BODY:BODY + 120] == source[BODY:BODY + 120]:
        output[BODY:BODY + 120] = bytes(120)
    if count > 1 and not _unused_name_space(output):
        raise ValueError('The edited names use the reward patch space. Shorten the card names or export with one drop.')
    output[ROLL_SITE:0x12490] = ROLL
    output[CREDIT_SITE:0x127B0] = CREDIT if count == 1 else PATCHED_CREDIT
    if count > 1:
        output[BODY:BODY + 120] = award_loop(count)
    if count > 1 and reward_layout(output) != ('installed', count):
        raise ValueError('The exported reward count or instructions failed verification.')
