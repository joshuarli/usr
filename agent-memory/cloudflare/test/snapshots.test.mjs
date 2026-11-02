import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { Miniflare } from "miniflare";

import { seedDatabase } from "../bench/seed.mjs";
import { loadWorker, request } from "./harness.mjs";

const worker = await loadWorker();
const COLLECTOR = "collector-client.access";
const OTHER_COLLECTOR = "other-client.access";
const ORIGIN = "origin-a";
const OTHER_ORIGIN = "origin-b";

function digest(value) {
  return createHash("sha256").update(value).digest("hex");
}

async function runtime(t) {
  const miniflare = new Miniflare({
    modules: true,
    script: "export default { fetch() { return new Response('ok'); } }",
    compatibilityDate: "2026-08-06",
    d1Databases: ["DB"],
    r2Buckets: ["BUCKET"],
  });
  t.after(() => miniflare.dispose());
  const db = await miniflare.getD1Database("DB");
  await seedDatabase(db);
  const collectorRow = db.prepare(
    "INSERT INTO collector(service_token_id, origin_host, label, created_at, disabled) VALUES(?, ?, ?, ?, 0)",
  );
  await collectorRow.bind(COLLECTOR, ORIGIN, "test", 0).run();
  await collectorRow.bind(OTHER_COLLECTOR, OTHER_ORIGIN, "test", 0).run();
  return {
    db,
    bucket: await miniflare.getR2Bucket("BUCKET"),
    env: {
      READERS: "reader@example.test",
      ACCESS_TEAM_DOMAIN: "team.example.test",
      ACCESS_AUD: "test-audience",
      DB: db,
      BUCKET: await miniflare.getR2Bucket("BUCKET"),
    },
  };
}

function collector(client = COLLECTOR) {
  return { access: { getIdentity: async () => ({ service_token_id: client }) } };
}

function postJson(path, value) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  });
}

async function putCiphertext(env, data, ciphertext, client = COLLECTOR) {
  const response = await worker.fetch(request(`/api/v1/sync/objects/${digest(ciphertext)}`, {
    method: "PUT",
    headers: {
      "X-Plaintext-Digest": digest(data),
      "X-Plaintext-Size": String(data.byteLength),
      "X-Encoding": "identity",
    },
    body: ciphertext,
  }), env, collector(client));
  assert.equal(response.status, 200, await response.clone().text());
  return { plaintext: digest(data), size: data.byteLength, ciphertext: digest(ciphertext) };
}

async function storeObject(env, data, client = COLLECTOR) {
  return await putCiphertext(env, data, Buffer.concat([Buffer.from("ciphertext:"), data]), client);
}

function snapshotFor(chunks, objects, { idSeed = "snapshot", createdAt = Date.now() / 1000 } = {}) {
  const dbDigest = digest(idSeed);
  return {
    id: dbDigest,
    created_at: createdAt,
    schema_version: 10,
    db_digest: dbDigest,
    db_size: chunks.reduce((total, chunk) => total + chunk.size, 0),
    chunks: chunks.map((chunk) => ({
      plaintext_digest: chunk.plaintext,
      size: chunk.size,
      ciphertext_digest: chunk.ciphertext,
    })),
    objects: objects.map((object) => ({ plaintext_digest: object.plaintext, size: object.size })),
  };
}

async function commitSnapshot(env, snapshot, baseRevision, client = COLLECTOR) {
  const response = await worker.fetch(postJson("/api/v1/sync/snapshots", {
    protocol: 1,
    origin: ORIGIN,
    base_revision: baseRevision,
    snapshot,
  }), env, collector(client));
  return { response, body: await response.json() };
}

async function listSnapshots(env, query = "", client = COLLECTOR) {
  const response = await worker.fetch(request(`/api/v1/sync/snapshots?origin=${ORIGIN}${query}`), env, collector(client));
  return { response, body: await response.json() };
}

async function detail(env, id, client = COLLECTOR) {
  const response = await worker.fetch(request(`/api/v1/sync/snapshots/${id}?origin=${ORIGIN}`), env, collector(client));
  return { response, body: await response.json() };
}

async function verify(env, id, client = COLLECTOR) {
  const response = await worker.fetch(postJson(`/api/v1/sync/snapshots/${id}/verify`, {
    protocol: 1,
    origin: ORIGIN,
  }), env, collector(client));
  return { response, body: await response.json() };
}

async function gc(env, apply, client = COLLECTOR) {
  const response = await worker.fetch(postJson("/api/v1/sync/gc", {
    protocol: 1,
    origin: ORIGIN,
    apply,
  }), env, collector(client));
  return { response, body: await response.json() };
}

function count(db, table) {
  return db.prepare(`SELECT count(*) AS count FROM ${table}`).first();
}

test("a snapshot commits with its chunks and pinned objects and re-acks", async (t) => {
  const { db, env } = await runtime(t);
  const first = await storeObject(env, Buffer.from("first snapshot chunk"));
  const second = await storeObject(env, Buffer.from("second snapshot chunk"));
  const pinned = await storeObject(env, Buffer.from("pinned archive object"));
  const secondPinned = await storeObject(env, Buffer.from("second pinned archive object"));
  const snapshot = snapshotFor([first, second], [pinned, secondPinned]);

  const committed = await commitSnapshot(env, snapshot, 0);
  assert.equal(committed.response.status, 200, JSON.stringify(committed.body));
  assert.equal(committed.body.duplicate, false);
  assert.equal(committed.body.revision, 1);
  assert.equal(committed.body.snapshot, snapshot.id);
  assert.equal(committed.body.objects, 2);
  assert.equal(committed.body.object_bytes, pinned.size + secondPinned.size);
  assert.equal((await count(db, "snapshot")).count, 1);
  assert.equal((await count(db, "snapshot_chunk")).count, 2);
  assert.equal((await count(db, "snapshot_object")).count, 2);

  const fetched = await detail(env, snapshot.id);
  assert.equal(fetched.response.status, 200, JSON.stringify(fetched.body));
  assert.equal(fetched.body.snapshot.id, snapshot.id);
  assert.deepEqual(fetched.body.chunks.map((chunk) => chunk.ordinal), [0, 1]);
  assert.equal(fetched.body.chunks[0].encoding, "identity");
  assert.deepEqual(
    new Set(fetched.body.objects.map((object) => object.ciphertext_digest)),
    new Set([pinned.ciphertext, secondPinned.ciphertext]),
  );
  assert.equal((await listSnapshots(env)).body.snapshots.length, 1);

  const duplicate = await commitSnapshot(env, snapshot, 99);
  assert.equal(duplicate.response.status, 200, JSON.stringify(duplicate.body));
  assert.equal(duplicate.body.duplicate, true);
  assert.equal(duplicate.body.revision, 1);
  assert.equal((await count(db, "snapshot")).count, 1);

  const secondSnapshot = snapshotFor([first], [], { idSeed: "second snapshot" });
  const stale = await commitSnapshot(env, secondSnapshot, 0);
  assert.equal(stale.response.status, 409);
  assert.equal(stale.body.error.code, "stale_revision");
  assert.equal((await count(db, "snapshot")).count, 1);
});

test("snapshot listings paginate with an opaque cursor", async (t) => {
  const { env } = await runtime(t);
  const now = Date.now() / 1000;
  for (let index = 0; index < 3; index += 1) {
    const chunk = await storeObject(env, Buffer.from(`paginated snapshot ${index}`));
    const snapshot = snapshotFor([chunk], [], { idSeed: `paginated-${index}`, createdAt: now + index });
    assert.equal((await commitSnapshot(env, snapshot, index)).response.status, 200);
  }
  const first = await listSnapshots(env, "&limit=2");
  assert.equal(first.response.status, 200, JSON.stringify(first.body));
  assert.equal(first.body.snapshots.length, 2);
  assert.ok(first.body.next_cursor);
  const second = await listSnapshots(env, `&limit=2&before=${encodeURIComponent(first.body.next_cursor)}`);
  assert.equal(second.response.status, 200, JSON.stringify(second.body));
  assert.equal(second.body.snapshots.length, 1);
  assert.equal(second.body.next_cursor, null);
  assert.notEqual(first.body.snapshots[0].id, second.body.snapshots[0].id);
});

test("snapshot references must be stored and mapped", async (t) => {
  const { env } = await runtime(t);
  const stored = await storeObject(env, Buffer.from("stored snapshot chunk"));
  const missing = { plaintext: digest("never stored"), size: 12, ciphertext: digest("never stored ciphertext") };

  const absent = await commitSnapshot(env, snapshotFor([missing], []), 0);
  assert.equal(absent.response.status, 409);
  assert.equal(absent.body.error.code, "missing_object");

  const wrongCiphertext = { ...stored, ciphertext: digest("different ciphertext") };
  const unmapped = await commitSnapshot(env, snapshotFor([wrongCiphertext], []), 0);
  assert.equal(unmapped.response.status, 409);
  assert.equal(unmapped.body.error.code, "missing_object");

  const wrongObjectSize = { plaintext: stored.plaintext, size: stored.size + 1 };
  const badObject = await commitSnapshot(env, snapshotFor([stored], [wrongObjectSize]), 0);
  assert.equal(badObject.response.status, 409);
  assert.equal(badObject.body.error.code, "missing_object");

  const idMismatch = snapshotFor([stored], []);
  idMismatch.id = digest("different id");
  const badId = await commitSnapshot(env, idMismatch, 0);
  assert.equal(badId.response.status, 400);
  assert.equal(badId.body.error.code, "invalid_request");

  const badSize = snapshotFor([stored], []);
  badSize.db_size += 1;
  const badSum = await commitSnapshot(env, badSize, 0);
  assert.equal(badSum.response.status, 400);
  assert.equal(badSum.body.error.code, "invalid_request");
});

test("verification records the collector attestation once", async (t) => {
  const { db, env } = await runtime(t);
  const chunk = await storeObject(env, Buffer.from("verification chunk"));
  const snapshot = snapshotFor([chunk], []);
  assert.equal((await commitSnapshot(env, snapshot, 0)).response.status, 200);

  const first = await verify(env, snapshot.id);
  assert.equal(first.response.status, 200, JSON.stringify(first.body));
  assert.equal(first.body.duplicate, false);
  assert.ok(first.body.verified_at > 0);
  const stored = await db.prepare("SELECT verified_at FROM snapshot WHERE id = ?").bind(snapshot.id).first();
  assert.equal(stored.verified_at, first.body.verified_at);

  const second = await verify(env, snapshot.id);
  assert.equal(second.response.status, 200);
  assert.equal(second.body.duplicate, true);
  assert.equal(second.body.verified_at, first.body.verified_at);

  const foreign = await commitSnapshot(env, snapshotFor([chunk], [], { idSeed: "foreign" }), 1, OTHER_COLLECTOR);
  assert.equal(foreign.response.status, 403);
  const unknown = await verify(env, digest("unknown snapshot"));
  assert.equal(unknown.response.status, 404);
});

test("gc keeps the newest verified snapshot and sweeps only old unreferenced objects", async (t) => {
  const { db, bucket, env } = await runtime(t);
  const now = Date.now() / 1000;
  const stale = await storeObject(env, Buffer.from("stale unreferenced"));
  const oldChunk = await storeObject(env, Buffer.from("old snapshot chunk"));
  const oldPinned = await storeObject(env, Buffer.from("old pinned object"));
  const retainedChunk = await storeObject(env, Buffer.from("retained snapshot chunk"));
  const newestChunk = await storeObject(env, Buffer.from("newest snapshot chunk"));

  const oldSnapshot = snapshotFor([oldChunk], [oldPinned], { idSeed: "old", createdAt: now - 35 * 86_400 });
  assert.equal((await commitSnapshot(env, oldSnapshot, 0)).response.status, 200);
  const retained = snapshotFor([retainedChunk], [], { idSeed: "retained", createdAt: now - 2 * 86_400 });
  assert.equal((await commitSnapshot(env, retained, 1)).response.status, 200);
  const newest = snapshotFor([newestChunk], [], { idSeed: "newest", createdAt: now });
  assert.equal((await commitSnapshot(env, newest, 2)).response.status, 200);

  const markOld = db.prepare("UPDATE snapshot SET created_at = ?, verified_at = ? WHERE id = ?");
  await markOld.bind(now - 35 * 86_400, now - 34 * 86_400, oldSnapshot.id).run();
  await markOld.bind(now - 2 * 86_400, now - 86_400, retained.id).run();

  const dryRun = await gc(env, false);
  assert.equal(dryRun.response.status, 200, JSON.stringify(dryRun.body));
  assert.equal(dryRun.body.apply, false);
  assert.equal(dryRun.body.snapshots_pruned, 1);
  assert.equal(dryRun.body.snapshots_retained, 2);
  assert.equal(dryRun.body.objects_marked, 3);
  assert.equal(dryRun.body.objects_swept, 0);
  assert.equal((await count(db, "snapshot")).count, 3);

  const applied = await gc(env, true);
  assert.equal(applied.response.status, 200, JSON.stringify(applied.body));
  assert.equal(applied.body.snapshots_pruned, 1);
  assert.equal(applied.body.objects_marked, 3);
  assert.equal((await count(db, "snapshot")).count, 2);
  const removed = await db.prepare("SELECT count(*) AS count FROM snapshot WHERE id = ?").bind(oldSnapshot.id).first();
  assert.equal(removed.count, 0);

  const expire = db.prepare("UPDATE remote_object SET gc_pending_at = ? WHERE plaintext_digest = ?");
  for (const object of [stale, oldChunk, oldPinned]) {
    await expire.bind(now - 3_601, object.plaintext).run();
  }
  const swept = await gc(env, true);
  assert.equal(swept.response.status, 200, JSON.stringify(swept.body));
  assert.equal(swept.body.objects_swept, 3);
  for (const object of [stale, oldChunk, oldPinned]) {
    assert.equal(await bucket.get(`v1/o/${object.ciphertext}`), null);
    const row = await db.prepare("SELECT count(*) AS count FROM remote_object WHERE plaintext_digest = ?")
      .bind(object.plaintext).first();
    assert.equal(row.count, 0);
  }
  assert.notEqual(await bucket.get(`v1/o/${retainedChunk.ciphertext}`), null);
  assert.notEqual(await bucket.get(`v1/o/${newestChunk.ciphertext}`), null);
});

test("gc prunes one snapshot per batch and keeps the rest referenced", async (t) => {
  const { db, env } = await runtime(t);
  const now = Date.now() / 1000;
  const firstChunk = await storeObject(env, Buffer.from("first prunable chunk"));
  const secondChunk = await storeObject(env, Buffer.from("second prunable chunk"));
  const newestChunk = await storeObject(env, Buffer.from("newest chunk"));
  const first = snapshotFor([firstChunk], [], { idSeed: "first prunable", createdAt: now - 35 * 86_400 });
  const second = snapshotFor([secondChunk], [], { idSeed: "second prunable", createdAt: now - 34 * 86_400 });
  const newest = snapshotFor([newestChunk], [], { idSeed: "newest", createdAt: now });
  assert.equal((await commitSnapshot(env, first, 0)).response.status, 200);
  assert.equal((await commitSnapshot(env, second, 1)).response.status, 200);
  assert.equal((await commitSnapshot(env, newest, 2)).response.status, 200);

  const one = await gc(env, true);
  assert.equal(one.response.status, 200, JSON.stringify(one.body));
  assert.equal(one.body.snapshots_pruned, 1);
  assert.equal(one.body.objects_marked, 1);
  assert.equal((await count(db, "snapshot")).count, 2);
  const pending = await db.prepare(
    "SELECT plaintext_digest FROM remote_object WHERE gc_pending_at IS NOT NULL",
  ).all();
  const pendingDigests = new Set(pending.results.map((row) => row.plaintext_digest));
  assert.equal(pendingDigests.size, 1);
  assert.ok(pendingDigests.has(firstChunk.plaintext) !== pendingDigests.has(secondChunk.plaintext));
  assert.equal(pendingDigests.has(newestChunk.plaintext), false);

  const two = await gc(env, true);
  assert.equal(two.response.status, 200, JSON.stringify(two.body));
  assert.equal(two.body.snapshots_pruned, 1);
  assert.equal(two.body.objects_marked, 1);
  assert.equal((await count(db, "snapshot")).count, 1);
  const remaining = await db.prepare("SELECT count(*) AS count FROM snapshot WHERE id = ?").bind(newest.id).first();
  assert.equal(remaining.count, 1);
});

test("gc retains daily snapshots even when none are verified", async (t) => {
  const { db, env } = await runtime(t);
  const now = Date.now() / 1000;
  const chunks = [];
  for (const [index, age] of [[0, 3], [1, 2], [2, 0]]) {
    const chunk = await storeObject(env, Buffer.from(`unverified snapshot ${index}`));
    chunks.push(chunk);
    const snapshot = snapshotFor([chunk], [], { idSeed: `unverified-${index}`, createdAt: now - age * 86_400 });
    assert.equal((await commitSnapshot(env, snapshot, index)).response.status, 200);
  }
  const report = await gc(env, false);
  assert.equal(report.response.status, 200, JSON.stringify(report.body));
  assert.equal(report.body.snapshots_retained, 3);
  assert.equal(report.body.snapshots_pruned, 0);
  assert.equal((await count(db, "snapshot")).count, 3);
  for (const chunk of chunks) {
    assert.notEqual(await env.BUCKET.get(`v1/o/${chunk.ciphertext}`), null);
  }
});

test("a tombstone deletes its generation rows and lets gc sweep the manifest", async (t) => {
  const { db, bucket, env } = await runtime(t);
  const chunk = await storeObject(env, Buffer.from("tombstoned generation chunk"));
  const manifest = await storeObject(env, Buffer.from("tombstoned generation manifest"));
  const now = Date.now() / 1000;
  const inserted = await db.prepare(
    `INSERT INTO generation(origin_host, harness, native_id, manifest_digest, source_digest,
       source_size, captured_at, committed_at, revision, manifest_object)
     VALUES(?, 'codex', 'native-gc', ?, ?, ?, ?, ?, 1, ?)`,
  ).bind(ORIGIN, digest("native-gc-manifest"), chunk.plaintext, chunk.size, now, now, manifest.ciphertext).run();
  const generationId = inserted.meta.last_row_id;
  await db.prepare(
    "INSERT INTO generation_object(generation, ordinal, plaintext_digest, size) VALUES(?, 0, ?, ?)",
  ).bind(generationId, chunk.plaintext, chunk.size).run();
  await db.prepare("INSERT OR IGNORE INTO origin_sync(origin_host, revision, last_change_at) VALUES(?, 1, NULL)")
    .bind(ORIGIN).run();
  await db.prepare("UPDATE origin_sync SET revision = 1 WHERE origin_host = ?").bind(ORIGIN).run();

  const pushed = await worker.fetch(postJson("/api/v1/sync/tombstones", {
    protocol: 1, origin: ORIGIN, base_revision: 1,
    tombstones: [{ harness: "codex", native_id: "native-gc", scope: "global", forgotten_at: now }],
  }), env, collector());
  assert.equal(pushed.status, 200, await pushed.text());
  assert.equal((await count(db, "generation")).count, 0);
  assert.equal((await count(db, "generation_object")).count, 0);

  const marked = await gc(env, true);
  assert.equal(marked.response.status, 200, JSON.stringify(marked.body));
  assert.equal(marked.body.objects_marked, 2);
  const expire = db.prepare("UPDATE remote_object SET gc_pending_at = ? WHERE plaintext_digest = ?");
  await expire.bind(now - 3_601, chunk.plaintext).run();
  await expire.bind(now - 3_601, manifest.plaintext).run();
  const swept = await gc(env, true);
  assert.equal(swept.response.status, 200, JSON.stringify(swept.body));
  assert.equal(swept.body.objects_swept, 2);
  assert.equal(await bucket.get(`v1/o/${manifest.ciphertext}`), null);
  assert.equal(await bucket.get(`v1/o/${chunk.ciphertext}`), null);
});

test("an object replacement swaps ciphertext mappings under the foreign key", async (t) => {
  const { db, bucket, env } = await runtime(t);
  const manifestData = Buffer.from('{"manifest":"synthetic"}');
  const oldCiphertext = Buffer.concat([Buffer.from("old:"), manifestData]);
  const oldObject = await putCiphertext(env, manifestData, oldCiphertext);
  const newCiphertext = Buffer.concat([Buffer.from("new:"), manifestData]);
  const newObject = await putCiphertext(env, manifestData, newCiphertext);

  await db.prepare("INSERT INTO origin_sync(origin_host, revision, last_change_at) VALUES(?, 0, NULL)")
    .bind(ORIGIN).run();
  await db.prepare(
    `INSERT INTO generation(
       origin_host, harness, native_id, manifest_digest, source_digest, source_size,
       captured_at, committed_at, revision, manifest_object
     ) VALUES(?, 'codex', 'native-1', ?, ?, 0, 1, 1, 1, ?)`,
  ).bind(ORIGIN, oldObject.plaintext, digest("source"), oldObject.ciphertext).run();

  const replaced = await worker.fetch(postJson(`/api/v1/sync/objects/${oldObject.plaintext}/replace`, {
    protocol: 1,
    origin: ORIGIN,
    plaintext_digest: oldObject.plaintext,
    plaintext_size: manifestData.byteLength,
    encoding: "identity",
    ciphertext_digest: newObject.ciphertext,
    ciphertext_size: newCiphertext.byteLength,
  }), env, collector());
  assert.equal(replaced.status, 200, await replaced.clone().text());
  const body = await replaced.json();
  assert.equal(body.replaced, true);
  assert.equal(body.object.ciphertext_digest, newObject.ciphertext);
  const row = await db.prepare("SELECT ciphertext_digest FROM remote_object WHERE plaintext_digest = ?")
    .bind(oldObject.plaintext).first();
  assert.equal(row.ciphertext_digest, newObject.ciphertext);
  const generation = await db.prepare("SELECT manifest_object FROM generation WHERE origin_host = ?")
    .bind(ORIGIN).first();
  assert.equal(generation.manifest_object, newObject.ciphertext);
  assert.notEqual(await bucket.get(`v1/o/${newObject.ciphertext}`), null);

  const idempotent = await worker.fetch(postJson(`/api/v1/sync/objects/${oldObject.plaintext}/replace`, {
    protocol: 1,
    origin: ORIGIN,
    plaintext_digest: oldObject.plaintext,
    plaintext_size: manifestData.byteLength,
    encoding: "identity",
    ciphertext_digest: newObject.ciphertext,
    ciphertext_size: newCiphertext.byteLength,
  }), env, collector());
  assert.equal(idempotent.status, 200);
  assert.equal((await idempotent.json()).replaced, false);

  const absentCiphertext = digest("never uploaded replacement");
  const absent = await worker.fetch(postJson(`/api/v1/sync/objects/${oldObject.plaintext}/replace`, {
    protocol: 1,
    origin: ORIGIN,
    plaintext_digest: oldObject.plaintext,
    plaintext_size: manifestData.byteLength,
    encoding: "identity",
    ciphertext_digest: absentCiphertext,
    ciphertext_size: 10,
  }), env, collector());
  assert.equal(absent.status, 409);
  assert.equal((await absent.json()).error.code, "missing_object");

  const foreign = await worker.fetch(postJson(`/api/v1/sync/objects/${oldObject.plaintext}/replace`, {
    protocol: 1,
    origin: ORIGIN,
    plaintext_digest: oldObject.plaintext,
    plaintext_size: manifestData.byteLength,
    encoding: "identity",
    ciphertext_digest: newObject.ciphertext,
    ciphertext_size: newCiphertext.byteLength,
  }), env, collector(OTHER_COLLECTOR));
  assert.equal(foreign.status, 403);
});

test("snapshot routes are scoped to the collector origin", async (t) => {
  const { env } = await runtime(t);
  const chunk = await storeObject(env, Buffer.from("scoped snapshot chunk"));
  const snapshot = snapshotFor([chunk], []);
  assert.equal((await commitSnapshot(env, snapshot, 0)).response.status, 200);

  const foreignList = await listSnapshots(env, "", OTHER_COLLECTOR);
  assert.equal(foreignList.response.status, 403);
  const foreignDetail = await detail(env, snapshot.id, OTHER_COLLECTOR);
  assert.equal(foreignDetail.response.status, 404);
  const foreignVerify = await verify(env, snapshot.id, OTHER_COLLECTOR);
  assert.equal(foreignVerify.response.status, 403);
  const foreignGc = await gc(env, false, OTHER_COLLECTOR);
  assert.equal(foreignGc.response.status, 403);
});
