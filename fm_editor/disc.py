"""Content-detected images; sector-preserving, atomic exports."""
from pathlib import Path
import os
import re
import struct
import tempfile
from core.cdrom import PS1DiscImage, encode_mode2_form1_sector, compute_edc, generate_ecc
from .bps import BpsWriter


class Disc(PS1DiscImage):
    def __init__(self, path):
        path = Path(path).resolve()
        if path.suffix.lower() == '.ccd':
            path = path.with_suffix('.img')
        elif path.suffix.lower() == '.cue':
            cue = path.read_text(errors='replace')
            files = re.findall(r'FILE\s+"([^"]+)"\s+BINARY', cue, re.I)
            tracks = re.findall(r'TRACK\s+\d+\s+(\S+)', cue, re.I)
            if len(files) != 1 or len(tracks) != 1:
                raise ValueError('Only single-data-track CUE images are supported. Convert multi-track images first.')
            path = path.parent / files[0]
        self.path = path.resolve()
        self.detected = None
        with path.open('rb') as f:
            size = path.stat().st_size
            for sector, offset in ((2352, 24), (2352, 16), (2336, 8), (2048, 0)):
                if size % sector:
                    continue
                f.seek(16 * sector + offset)
                if f.read(6) == b'\x01CD001':
                    self.detected = sector, offset
                    break
        if not self.detected:
            raise ValueError('Unsupported disc layout. Open raw IMG/BIN/ISO (2352, 2336, or 2048 bytes/sector), CUE, or CCD. CHD, PBP and archives must be converted/extracted first.')
        super().__init__(str(path))
        if 'SLUS_014.11' not in self.file_table or 'DATA/WA_MRG.MRG' not in self.file_table:
            raise ValueError('This editor currently patches the USA SLUS-01411 release only.')

    def _detect_sector_size(self):
        return self.detected[0]

    def read_user_data_sector(self, lba):
        s = self.read_sector(lba)
        return bytes(s[self.detected[1]:self.detected[1] + 2048])

    def extract_file(self, internal_path):
        entry = self.file_table[internal_path]
        out = bytearray()
        with self.path.open('rb') as f:
            f.seek(entry.lba * self.sector_size)
            for _ in range((entry.size + 2047) // 2048):
                s = f.read(self.sector_size)
                if len(s) != self.sector_size:
                    raise ValueError('Truncated disc file')
                out.extend(s[self.detected[1]:self.detected[1] + 2048])
        return bytes(out[:entry.size])

    def export(self, target, replacements, progress=lambda p, s: None, *, patch=False):
        target = Path(target).resolve()
        if patch and target.suffix.lower() != '.bps':
            raise ValueError('Choose a .bps filename for the patch.')
        if target == self.path or (target.exists() and os.path.samefile(target, self.path)):
            raise ValueError('Choose a new output file. The source disc is never overwritten.')
        patches = {}
        for key, data in replacements.items():
            entry = self.file_table[key]
            if len(data) != entry.size:
                raise ValueError(f'{key}: patch changed file size; export refused.')
            for i in range((len(data) + 2047) // 2048):
                patches[entry.lba + i] = data[i * 2048:(i + 1) * 2048]
        fd, temp = tempfile.mkstemp(prefix=target.name + '.', suffix='.partial', dir=target.parent)
        changed = 0
        try:
            with os.fdopen(fd, 'wb') as out, self.path.open('rb') as source:
                total = self.filesize // self.sector_size
                writer = BpsWriter(out, self.filesize) if patch else None
                for lba in range(total):
                    original = source.read(self.sector_size)
                    if len(original) != self.sector_size:
                        raise ValueError('The source disc was truncated during export.')
                    sector = bytearray(original)
                    data = patches.get(lba)
                    skip = self.detected[1]
                    if data is not None and sector[skip:skip + len(data)] != data:
                        if self.sector_size in (2352, 2336) and skip != 16:
                            sub = 18 if self.sector_size == 2352 else 2
                            if sector[sub] & 0x20:
                                raise ValueError(f'Patch overlaps XA Form 2 sector {lba}; export refused.')
                        sector[skip:skip + len(data)] = data
                        changed += 1
                        if self.sector_size == 2352:
                            if skip == 24:
                                encode_mode2_form1_sector(sector)
                            else:
                                struct.pack_into('<I', sector, 2064, compute_edc(sector[:2064], 2064))
                                sector[2068:2076] = bytes(8)
                                generate_ecc(sector, zero_address=False)
                        elif self.sector_size == 2336:
                            raw = bytearray(16) + sector
                            encode_mode2_form1_sector(raw)
                            sector = raw[16:]
                    if writer:
                        writer.sector(original, sector)
                    else:
                        out.write(sector)
                    if lba % 4096 == 0:
                        output_type = 'BPS patch' if patch else 'disc'
                        progress(lba / total, f'Writing {output_type} • {changed:,} modified sectors')
                if writer:
                    writer.finish()
                out.flush()
                os.fsync(out.fileno())
            if not patch:
                check = Disc(temp)
                for key, data in replacements.items():
                    if check.extract_file(key) != data:
                        raise ValueError(f'Export verification failed for {key}')
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        # Raw-sector images keep the original track layout and need a companion CUE.
        # A 2048-byte ISO can be opened directly and has no separate track metadata.
        if not patch and self.sector_size in (2352, 2336):
            if self.sector_size == 2336:
                mode = 'MODE2/2336'
            else:
                mode = 'MODE2/2352' if self.detected[1] == 24 else 'MODE1/2352'
            target.with_suffix('.cue').write_text(f'FILE "{target.name}" BINARY\n  TRACK 01 {mode}\n    INDEX 01 00:00:00\n', encoding='ascii')
        progress(1, f'Export finished • {changed:,} modified sectors')
        return changed
