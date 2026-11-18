"""Read and edit Yu-Gi-Oh! Forbidden Memories PlayStation save data."""
from __future__ import annotations

import math
import struct
from pathlib import Path

from .memory_card import seal, validate_state

STATE_SIZE = 0x680
SAVE_HEADER_SIZE = 0x200
PRIMARY_OFFSET = SAVE_HEADER_SIZE
DUPLICATE_OFFSET = SAVE_HEADER_SIZE + STATE_SIZE
CARD_QUANTITIES_OFFSET = 0x50
CAMPAIGN_FLAGS_OFFSET = 0x418
PLAYER_NAME_OFFSET = 0x40C
DECK_SIZE = 40
CARD_COUNT = 722
TOURNAMENT_COMPLETE_FLAG = 0x47
CAMPAIGN_FLAG_DEFEATED_BASE = 0x1F
FREE_DUEL_UNLOCK_FLAG_BASE = 0x6E0

# These are documented campaign milestones, not guesses at arbitrary scene
# indices. Checkpoints update the story bits and the corresponding Free Duel
# unlocks while preserving unrelated collection/password flags.
CAMPAIGN_CHECKPOINTS = {
    "festival": {
        "label": "Festival challenge unlocked",
        "flags": (0x48, 0x49, 0x4A, 0x4B, 0x6F),
        "duelists": (),
    },
    "tournament": {
        "label": "Tournament complete · returned to Egypt",
        "flags": (TOURNAMENT_COMPLETE_FLAG,),
        "duelists": tuple(range(9, 18)),
    },
    "ruins": {
        "label": "Forbidden Ruins opened",
        "flags": (0x50, 0x51, 0x52, 0x53),
        "duelists": (18,),
    },
    "hidden_grounds": {
        "label": "Hidden Dueling Grounds discovered",
        "flags": (0x5A,),
        "duelists": (),
    },
    "high_mages": {
        "label": "All five shrines cleared · High Mages defeated",
        "flags": (0x35, 0x37, 0x39, 0x3B, 0x3D, 0x5D, 0x6D),
        "duelists": tuple(range(21, 31)),
    },
    "labyrinth": {
        "label": "Labyrinth Mage defeated four times",
        "flags": (0x69, 0x6A, 0x6B, 0x6C),
        "duelists": (31,),
    },
    "lecture": {"label": "Heard Simon’s evening lecture", "flags": (110,), "duelists": ()},
    "shrine": {"label": "Saw the mages waiting for Seto", "flags": (77,), "duelists": ()},
    "seto_first": {"label": "Defeated Seto at the festival grounds", "flags": (), "duelists": (7,)},
    "kidnapping": {"label": "Witnessed Teana’s kidnapping", "flags": (92,), "duelists": ()},
    "shop": {"label": "Visited the hidden card shop", "flags": (94,), "duelists": ()},
    "map": {"label": "Examined the map inside the ruins", "flags": (84,), "duelists": ()},
    "drawing": {"label": "Examined the drawing in the ruins", "flags": (96,), "duelists": ()},
}


class SaveDataError(ValueError):
    """The selected file does not contain a valid FM save."""


class SaveDataDocument:
    """A memory-card image or single-save file, preserving all unrelated bytes."""

    def __init__(self, raw: bytes, payload: bytes, blocks: list[int] | None):
        self.raw = bytearray(raw)
        self.payload = bytearray(payload)
        self.blocks = blocks
        self.state_offset = self._choose_valid_state()
        self._state = bytearray(self.payload[self.state_offset:self.state_offset + STATE_SIZE])

    @classmethod
    def open(cls, path: str | Path) -> "SaveDataDocument":
        raw = Path(path).read_bytes()
        if len(raw) >= 128 * 1024 and raw[:2] == b"MC":
            return cls._from_memory_card(raw)
        if len(raw) >= DUPLICATE_OFFSET + STATE_SIZE and raw[:2] == b"SC":
            return cls(raw, raw, None)
        raise SaveDataError("This file is not a supported DuckStation .mcd card or FM .mcs save file.")

    @classmethod
    def _from_memory_card(cls, raw: bytes) -> "SaveDataDocument":
        failures = []
        for first_block in range(1, 16):
            frame_start = first_block * 128
            frame = raw[frame_start:frame_start + 128]
            if len(frame) != 128 or frame[0] != 0x51:
                continue
            size = struct.unpack_from("<I", frame, 4)[0]
            if size <= 0 or size > 15 * 8192:
                size = 8192
            needed = max(1, math.ceil(size / 8192))
            blocks = []
            current = first_block
            seen = set()
            for _ in range(needed):
                if current not in range(1, 16) or current in seen:
                    break
                seen.add(current)
                blocks.append(current)
                current_frame = raw[current * 128:(current + 1) * 128]
                next_block = struct.unpack_from("<H", current_frame, 8)[0]
                if len(blocks) < needed:
                    if next_block == 0xFFFF:
                        break
                    current = next_block
            if not blocks:
                continue
            payload = b"".join(raw[b * 8192:(b + 1) * 8192] for b in blocks)
            if len(payload) < DUPLICATE_OFFSET + STATE_SIZE:
                continue
            try:
                return cls(raw, payload, blocks)
            except SaveDataError as exc:
                name = frame[10:30].split(b"\0", 1)[0].decode("ascii", "replace")
                failures.append(f"{name or f'block {first_block}'}: {exc}")
        detail = "\n".join(failures[:4])
        if detail:
            raise SaveDataError("No valid Forbidden Memories save was found on this memory card.\n" + detail)
        raise SaveDataError("No FM save file was found on this memory card.")

    def _choose_valid_state(self) -> int:
        valid = [offset for offset in (PRIMARY_OFFSET, DUPLICATE_OFFSET)
                 if len(self.payload) >= offset + STATE_SIZE
                 and validate_state(self.payload[offset:offset + STATE_SIZE])]
        if not valid:
            raise SaveDataError("The save file's primary and backup data both fail the game's integrity checks.")
        return valid[0]

    @property
    def state(self) -> bytearray:
        return self._state

    def player_name(self) -> str:
        raw_name = bytes(self.state[PLAYER_NAME_OFFSET:PLAYER_NAME_OFFSET + 12])
        try:
            text = raw_name.decode("shift_jis").split("\0", 1)[0]
        except UnicodeDecodeError:
            return "PLAYER"
        chars = []
        for char in text:
            code = ord(char)
            if code == 0x3000:
                chars.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                chars.append(chr(code - 0xFEE0))
            elif char.isascii():
                chars.append(char)
        return "".join(chars).rstrip() or "PLAYER"

    def set_player_name(self, name: str) -> None:
        if not 1 <= len(name) <= 6 or not name.isascii() or not all(c.isalnum() or c == " " for c in name):
            raise SaveDataError("Player name must be 1–6 English letters, digits, or spaces.")
        fullwidth = "".join(chr(ord(c) + 0xFEE0) if c != " " else "\u3000" for c in name.ljust(6))
        encoded = fullwidth.encode("shift_jis")
        state = self.state
        state[PLAYER_NAME_OFFSET:PLAYER_NAME_OFFSET + 12] = encoded
        checksum = 0
        for value in encoded:
            checksum ^= value
        old_code = struct.unpack_from("<I", state, 0x334)[0]
        struct.pack_into("<I", state, 0x334, (old_code & 0xFFFFFF00) | checksum)

    def starchips(self) -> int:
        return struct.unpack_from("<I", self.state, 0x5E0)[0]

    def set_starchips(self, value: int) -> None:
        if not 0 <= value <= 999999:
            raise SaveDataError("Starchips must be between 0 and 999,999.")
        struct.pack_into("<I", self.state, 0x5E0, value)

    def duel_record(self) -> tuple[int, int]:
        return struct.unpack_from("<HH", self.state, 0x518)

    def set_duel_record(self, wins: int, losses: int) -> None:
        if not 0 <= wins <= 65535 or not 0 <= losses <= 65535:
            raise SaveDataError("Duel wins and losses must be between 0 and 65,535.")
        struct.pack_into("<HH", self.state, 0x518, wins, losses)

    def deck(self) -> list[int]:
        return list(struct.unpack_from("<40H", self.state, 0))

    def set_deck(self, deck: list[int]) -> None:
        if len(deck) != DECK_SIZE or any(card not in range(0, CARD_COUNT + 1) for card in deck):
            raise SaveDataError("The deck must contain 40 slots with card IDs 1–722 or empty slots.")
        struct.pack_into("<40H", self.state, 0, *deck)

    def card_quantity(self, card_id: int) -> int:
        if card_id not in range(1, CARD_COUNT + 1):
            raise SaveDataError("Card ID must be between 1 and 722.")
        return self.state[CARD_QUANTITIES_OFFSET + card_id - 1]

    def set_card_quantity(self, card_id: int, quantity: int) -> None:
        if card_id not in range(1, CARD_COUNT + 1) or not 0 <= quantity <= 250:
            raise SaveDataError("Trunk copies must be between 0 and 250.")
        self.state[CARD_QUANTITIES_OFFSET + card_id - 1] = quantity

    def tournament_complete(self) -> bool:
        return self.campaign_flag(TOURNAMENT_COMPLETE_FLAG)

    def campaign_checkpoint(self, checkpoint: str) -> bool:
        """Return whether every known flag for a named milestone is set."""
        try:
            definition = CAMPAIGN_CHECKPOINTS[checkpoint]
        except KeyError as exc:
            raise SaveDataError(f"Unknown campaign checkpoint: {checkpoint}.") from exc
        flags = definition["flags"]
        duelists = definition["duelists"]
        return all(self.campaign_flag(flag) for flag in flags) and all(
            self.campaign_flag(CAMPAIGN_FLAG_DEFEATED_BASE + duelist)
            for duelist in duelists
        )

    def set_campaign_checkpoint(self, checkpoint: str, enabled: bool) -> None:
        """Set or clear the story and duelist-unlock flags for a milestone."""
        try:
            definition = CAMPAIGN_CHECKPOINTS[checkpoint]
        except KeyError as exc:
            raise SaveDataError(f"Unknown campaign checkpoint: {checkpoint}.") from exc
        for flag in definition["flags"]:
            self.set_campaign_flag(flag, enabled)
        for duelist in definition["duelists"]:
            self.set_campaign_flag(CAMPAIGN_FLAG_DEFEATED_BASE + duelist, enabled)
            self.set_campaign_flag(FREE_DUEL_UNLOCK_FLAG_BASE + duelist, enabled)

    def campaign_flag(self, flag: int) -> bool:
        if not 0 <= flag <= 0x7FF:
            raise SaveDataError("Campaign flag is out of range.")
        offset = CAMPAIGN_FLAGS_OFFSET + flag // 8
        return bool(self.state[offset] & (0x80 >> (flag & 7)))

    def set_campaign_flag(self, flag: int, enabled: bool) -> None:
        if not 0 <= flag <= 0x7FF:
            raise SaveDataError("Campaign flag is out of range.")
        offset = CAMPAIGN_FLAGS_OFFSET + flag // 8
        mask = 0x80 >> (flag & 7)
        if enabled:
            self.state[offset] |= mask
        else:
            self.state[offset] &= ~mask

    def to_bytes(self) -> bytes:
        state = bytearray(self._state)
        seal(state)
        self._state = state
        self.payload[PRIMARY_OFFSET:PRIMARY_OFFSET + STATE_SIZE] = state
        self.payload[DUPLICATE_OFFSET:DUPLICATE_OFFSET + STATE_SIZE] = state
        if self.blocks is None:
            self.raw[:len(self.payload)] = self.payload[:len(self.raw)]
        else:
            for index, block in enumerate(self.blocks):
                start = index * 8192
                self.raw[block * 8192:(block + 1) * 8192] = self.payload[start:start + 8192]
        return bytes(self.raw)
