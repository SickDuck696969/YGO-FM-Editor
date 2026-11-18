const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");
const { crc32 } = require("node:zlib");

const buildDisc = runInNewContext(
  readFileSync(require.resolve("../web/disc-output.js"), "utf8") +
    "\nbuildDisc",
  { Blob, Uint8Array, Uint32Array, TextDecoder, DataView },
);

test("reconstruct and verify a disc from unchanged spans and literal edits", async () => {
  const source = Buffer.from("hello world");
  const edited = Buffer.from("hello there");
  const header = Buffer.concat([
    Buffer.from("BPS1"),
    Buffer.from([0x8b, 0x8b, 0x80, 0x94, 0x91]),
    Buffer.from("there"),
  ]);
  const checks = Buffer.alloc(12);
  checks.writeUInt32LE(crc32(source), 0);
  checks.writeUInt32LE(crc32(edited), 4);
  checks.writeUInt32LE(
    crc32(Buffer.concat([header, checks.subarray(0, 8)])),
    8,
  );
  const patch = Buffer.concat([header, checks]);
  assert.equal(
    await (await buildDisc(new Blob([source]), patch)).text(),
    "hello there",
  );
  await assert.rejects(buildDisc(new Blob([edited]), patch), /checksum/i);
  patch[8] ^= 1;
  await assert.rejects(buildDisc(new Blob([source]), patch), /checksum/i);
});
