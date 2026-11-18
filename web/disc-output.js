/* Reconstruct the desktop writer's SourceRead / TargetRead BPS stream using
   read-only Blob slices. Verify the exact source and final image before download. */
const crcTable = Uint32Array.from({ length: 256 }, (_, value) => {
  for (let i = 0; i < 8; i++)
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});
function updateCrc(data, crc = 0xffffffff) {
  for (const byte of data) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8);
  return crc;
}
async function blobCrc(blob) {
  const reader = blob.stream().getReader();
  let crc = 0xffffffff;
  while (true) {
    const { value, done } = await reader.read();
    if (done) return (crc ^ 0xffffffff) >>> 0;
    crc = updateCrc(value, crc);
  }
}
async function buildDisc(source, patch) {
  const footer = patch.length - 12;
  if (footer < 7 || new TextDecoder().decode(patch.subarray(0, 4)) !== "BPS1")
    throw Error("Invalid BPS header.");
  const view = new DataView(patch.buffer, patch.byteOffset, patch.length);
  const checksum = (offset) => view.getUint32(offset, true);
  if (
    (updateCrc(patch.subarray(0, -4)) ^ 0xffffffff) >>> 0 !==
    checksum(footer + 8)
  )
    throw Error("Patch checksum failed.");
  let cursor = 4;
  function number() {
    let value = 0,
      step = 1;
    while (cursor < footer) {
      const byte = patch[cursor++];
      value += (byte & 127) * step;
      if (byte & 128) return value;
      step *= 128;
      value += step;
    }
    throw Error("Truncated BPS integer.");
  }
  if (number() !== source.size || number() !== source.size)
    throw Error("Disc size mismatch.");
  const metadata = number();
  cursor += metadata;
  let position = 0;
  const parts = [];
  while (cursor < footer) {
    const action = number(),
      size = Math.floor(action / 4) + 1;
    if (position + size > source.size) throw Error("Invalid BPS extent.");
    if (action % 4 === 0) parts.push(source.slice(position, position + size));
    else if (action % 4 === 1 && cursor + size <= footer) {
      parts.push(patch.subarray(cursor, cursor + size));
      cursor += size;
    } else throw Error("Invalid editor patch command.");
    position += size;
  }
  const output = new Blob(parts);
  if (
    position !== source.size ||
    (await blobCrc(source)) !== checksum(footer) ||
    (await blobCrc(output)) !== checksum(footer + 4)
  )
    throw Error("Disc checksum verification failed.");
  return output;
}
