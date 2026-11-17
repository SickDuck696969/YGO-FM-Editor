"""Remove the obsolete card-frame renderer patch from previously exported ROMs.

The Workshop no longer supports per-card frame colors. Older Workshop builds
installed three renderer hooks; this recognizes only their exact hook and code
signatures so exporting an older patched image can restore the retail routines.
"""

from __future__ import annotations

import hashlib


_HOOKS = {
    0x15518: (bytes.fromhex("4865070800000000"), bytes.fromhex("1c00bf8f1800b28f")),
    0x70C4: (bytes.fromhex("7065070800000000"), bytes.fromhex("f100023c1e000324")),
    0x19BFC: (bytes.fromhex("9a65070c"), bytes.fromhex("00011324")),
}
_CAVES = (
    (0x1C9D20, 160, "962d7df323b2d55cf032f7a1634e2090d15e7a96d036221328524677fcf0cf78"),
    (0x1C9DC0, 168, "17da52486c1ad6c8fe716da5245384b12fc9347e9fb57234ee365f09c21fd530"),
    (0x1C9E68, 120, "8ee04fab059bf7f64cb859fcb3c6d963918cce9db68da5f339bcb9740d062a04"),
)
_CAVE_END = 0x1C9EE0


def remove_legacy_frame_color_patch(exe: bytearray) -> bool:
    """Restore exact old Workshop frame hooks; return whether they were found."""
    hook_matches = {
        offset: exe[offset:offset + len(installed)] == installed
        for offset, (installed, _original) in _HOOKS.items()
    }
    if not any(hook_matches.values()):
        return False

    if not all(hook_matches.values()):
        raise ValueError(
            "This ROM has a partial or modified legacy card-frame hook. "
            "Open the unpatched source image before exporting."
        )

    for offset, length, expected_hash in _CAVES:
        payload = bytes(exe[offset:offset + length])
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ValueError(
                "This ROM’s old card-frame code was modified and cannot be safely "
                "removed. Open the unpatched source image before exporting."
            )

    for offset, (_installed, original) in _HOOKS.items():
        exe[offset:offset + len(original)] = original
    exe[0x1C9D20:_CAVE_END] = bytes(_CAVE_END - 0x1C9D20)
    return True
