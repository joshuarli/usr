import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  ERROR_CODES,
  MAX_CURSOR_CHARS,
  MAX_JSON_BYTES,
  MAX_MISSING_OBJECTS,
  MAX_OBJECT_BYTES,
  PROTOCOL,
  decodeCursor,
  decodeDigest,
  decodeHello,
  decodeMissingRequest,
  decodeOrigin,
  encodeCursor,
} from "../src/protocol.ts";

const FIXTURE = JSON.parse(
  readFileSync(new URL("../../tests/fixtures/mirror_protocol.json", import.meta.url), "utf8"),
);

test("the Worker constants match the shared protocol fixture", () => {
  assert.equal(PROTOCOL, FIXTURE.protocol);
  assert.equal(MAX_JSON_BYTES, FIXTURE.limits.json_bytes);
  assert.equal(MAX_OBJECT_BYTES, FIXTURE.limits.object_bytes);
  assert.equal(MAX_MISSING_OBJECTS, FIXTURE.limits.missing_objects);
  assert.equal(MAX_CURSOR_CHARS, FIXTURE.limits.cursor_chars);
  assert.deepEqual([...ERROR_CODES].sort(), [...FIXTURE.error_codes].sort());
});

test("digest and origin validators agree with every fixture", () => {
  for (const item of FIXTURE.digests) {
    assert.equal(decodeDigest(item.value) === null, !item.ok, item.name);
  }
  for (const item of FIXTURE.origins) {
    assert.equal(decodeOrigin(item.value) === null, !item.ok, item.name);
  }
});

test("hello and missing-object validators agree with every fixture", () => {
  for (const item of FIXTURE.hello) {
    const decoded = decodeHello(item.value);
    assert.equal(decoded === null, !item.ok, item.name);
    if (decoded !== null) {
      assert.equal(decoded.protocol, PROTOCOL);
      assert.equal(decoded.origin, item.value.origin);
    }
  }
  for (const item of FIXTURE.missing) {
    const decoded = decodeMissingRequest(item.value);
    assert.equal(decoded === null, !item.ok, item.name);
    if (decoded !== null) assert.equal(decoded.objects.length, item.value.objects.length);
  }
});

test("cursor round trips and rejects every invalid fixture", () => {
  for (const item of FIXTURE.cursors) {
    if (item.parts !== undefined) {
      if (item.ok) {
        const encoded = encodeCursor(item.parts);
        assert.ok(encoded.length <= MAX_CURSOR_CHARS, item.name);
        if (item.encoded !== undefined) assert.equal(encoded, item.encoded, item.name);
        assert.deepEqual(decodeCursor(encoded), item.parts, item.name);
      } else {
        assert.throws(() => encodeCursor(item.parts), item.name);
      }
    } else {
      assert.equal(decodeCursor(item.value) === null, !item.ok, item.name);
    }
  }
});

test("a missing-object request over the count limit is refused", () => {
  const objects = Array.from({ length: MAX_MISSING_OBJECTS + 1 }, (_value, index) => ({
    plaintext_digest: index.toString(16).padStart(64, "0"),
    size: 0,
  }));
  assert.equal(decodeMissingRequest({ protocol: 1, origin: "origin-a", objects }), null);
});
