import type { Principal } from "../auth.js";
import {
  commitSnapshot,
  deleteObjectIfGcEligible,
  deleteSnapshots,
  markSnapshotVerified,
  markUnreferencedObjects,
  readKnownObjects,
  readSnapshot,
  readSnapshotChunks,
  readSnapshotObjects,
  readSnapshots,
  readUnreferencedObjects,
  type SnapshotChunkRow,
  type SnapshotObjectRow,
  type SnapshotRow,
} from "../db.js";
import { json, methodNotAllowed } from "../errors.js";
import { reportError } from "../observe-channel.js";
import { serverTiming } from "../observe.js";
import {
  GC_GRACE_SECONDS,
  MAX_PAGE,
  PROTOCOL,
  decodeCursor,
  decodeDigest,
  decodeGcRequest,
  decodeSnapshotCommit,
  decodeSnapshotVerifyRequest,
  encodeCursor,
} from "../protocol.js";
import type { Env } from "../index.js";
import {
  boundOrigin,
  readJson,
  refuse,
  versionOrError,
  type SyncTiming,
} from "./shared.js";

const SNAPSHOTS_PATH = "/api/v1/sync/snapshots";
const SNAPSHOT_PREFIX = "/api/v1/sync/snapshots/";
const GC_PATH = "/api/v1/sync/gc";
const DAY_SECONDS = 86_400;
const WEEK_SECONDS = 604_800;
const MAX_GC_SWEEP = 200;
const MAX_GC_PRUNE = 1;

function snapshotJson(row: SnapshotRow): Record<string, unknown> {
  return {
    id: row.id,
    origin_host: row.origin_host,
    created_at: row.created_at,
    schema_version: row.schema_version,
    db_digest: row.db_digest,
    db_size: row.db_size,
    objects: row.objects,
    object_bytes: row.object_bytes,
    verified_at: row.verified_at,
    revision: row.revision,
  };
}

function chunkJson(row: SnapshotChunkRow): Record<string, unknown> | null {
  if (row.encoding === null || row.ciphertext_size === null) return null;
  return {
    ordinal: row.ordinal,
    plaintext_digest: row.plaintext_digest,
    size: row.size,
    ciphertext_digest: row.ciphertext_digest,
    encoding: row.encoding,
    ciphertext_size: row.ciphertext_size,
  };
}

function objectJson(row: SnapshotObjectRow): Record<string, unknown> | null {
  if (row.ciphertext_digest === null || row.encoding === null || row.ciphertext_size === null) return null;
  return {
    plaintext_digest: row.plaintext_digest,
    size: row.size,
    ciphertext_digest: row.ciphertext_digest,
    encoding: row.encoding,
    ciphertext_size: row.ciphertext_size,
  };
}

function limitParameter(value: string | null): number | null {
  if (value === null) return 100;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 1 && parsed <= MAX_PAGE ? parsed : null;
}

function retainedSnapshotIds(rows: readonly SnapshotRow[], now: number): Set<string> {
  const keep = new Set<string>();
  if (rows.length === 0) return keep;
  const sorted = [...rows].sort((a, b) => b.created_at - a.created_at || b.id.localeCompare(a.id));
  const newest = sorted[0];
  if (newest !== undefined) keep.add(newest.id);
  const verified = sorted.filter((row) => row.verified_at !== null);
  const newestVerified = verified[0];
  if (newestVerified !== undefined && now - newestVerified.created_at <= 4 * WEEK_SECONDS) {
    keep.add(newestVerified.id);
  }
  const days = new Map<number, SnapshotRow>();
  const weeks = new Map<number, SnapshotRow>();
  for (const row of sorted) {
    const day = Math.floor(row.created_at / DAY_SECONDS);
    const week = Math.floor(row.created_at / WEEK_SECONDS);
    if (!days.has(day)) days.set(day, row);
    if (!weeks.has(week)) weeks.set(week, row);
  }
  const today = Math.floor(now / DAY_SECONDS);
  const thisWeek = Math.floor(now / WEEK_SECONDS);
  for (const [day, row] of days) {
    if (today - day < 7) keep.add(row.id);
  }
  for (const [week, row] of weeks) {
    if (thisWeek - week < 4) keep.add(row.id);
  }
  return keep;
}

async function commit(
  request: Request,
  env: Env,
  principal: Principal,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const commitBody = decodeSnapshotCommit(body.value);
  if (commitBody === null) return refuse(400, "invalid_request", "invalid snapshot commit", timing);
  const mismatch = boundOrigin(principal, commitBody.origin, timing);
  if (mismatch !== null) return mismatch;
  const { snapshot } = commitBody;

  const started = performance.now();
  try {
    const duplicate = await readSnapshot(env.DB, commitBody.origin, snapshot.id);
    if (duplicate !== null) {
      if (duplicate.db_digest !== snapshot.db_digest || duplicate.db_size !== snapshot.db_size) {
        return refuse(409, "conflict", "snapshot id is bound to a different database", timing);
      }
      return json(200, {
        protocol: PROTOCOL,
        origin: commitBody.origin,
        snapshot: duplicate.id,
        revision: duplicate.revision,
        duplicate: true,
        chunks: null,
        objects: duplicate.objects,
        object_bytes: duplicate.object_bytes,
      }, false, { "Server-Timing": serverTiming(timing) });
    }

    const chunkDigests = snapshot.chunks.map((chunk) => chunk.plaintext_digest);
    const objectDigests = snapshot.objects.map((object) => object.plaintext_digest);
    const knownChunks = new Map((await readKnownObjects(env.DB, commitBody.origin, chunkDigests))
      .map((row) => [row.plaintext_digest, row]));
    for (const chunk of snapshot.chunks) {
      const known = knownChunks.get(chunk.plaintext_digest);
      if (known === undefined || known.plaintext_size !== chunk.size || known.ciphertext_digest !== chunk.ciphertext_digest) {
        return refuse(409, "missing_object", "snapshot chunk is not stored", timing);
      }
    }
    const knownObjects = new Map((await readKnownObjects(env.DB, commitBody.origin, objectDigests))
      .map((row) => [row.plaintext_digest, row]));
    for (const object of snapshot.objects) {
      const known = knownObjects.get(object.plaintext_digest);
      if (known === undefined || known.plaintext_size !== object.size) {
        return refuse(409, "missing_object", "snapshot object is not stored", timing);
      }
    }
    const result = await commitSnapshot(env.DB, {
      origin_host: commitBody.origin,
      id: snapshot.id,
      created_at: snapshot.created_at,
      schema_version: snapshot.schema_version,
      db_digest: snapshot.db_digest,
      db_size: snapshot.db_size,
      chunks: snapshot.chunks,
      objects: snapshot.objects,
    }, commitBody.base_revision);
    return json(200, {
      protocol: PROTOCOL,
      origin: commitBody.origin,
      snapshot: snapshot.id,
      revision: result.revision,
      duplicate: false,
      chunks: snapshot.chunks.length,
      objects: snapshot.objects.length,
      object_bytes: snapshot.objects.reduce((total, object) => total + object.size, 0),
    }, false, { "Server-Timing": serverTiming(timing) });
  } catch (error) {
    const message = String(error);
    if (message.includes("stale_revision")) {
      return refuse(409, "stale_revision", "base revision is stale", timing);
    }
    if (message.includes("UNIQUE constraint failed")) {
      return refuse(409, "conflict", "snapshot already exists", timing);
    }
    reportError("snapshots.commit", error);
    return refuse(503, "unavailable", "snapshot commit failed", timing);
  } finally {
    timing.d1 += performance.now() - started;
  }
}

async function list(
  request: Request,
  env: Env,
  principal: Principal,
  url: URL,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "GET") return methodNotAllowed(["GET"], { "Server-Timing": serverTiming(timing) });
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  const origin = url.searchParams.get("origin");
  if (origin === null) return refuse(400, "invalid_request", "origin is required", timing);
  const mismatch = boundOrigin(principal, origin, timing);
  if (mismatch !== null) return mismatch;
  const limit = limitParameter(url.searchParams.get("limit"));
  if (limit === null) return refuse(400, "invalid_request", "limit is invalid", timing);
  const beforeValue = url.searchParams.get("before");
  let before: { readonly createdAt: number; readonly id: string } | null = null;
  if (beforeValue !== null) {
    const parts = decodeCursor(beforeValue);
    const createdAt = parts === null || parts.length !== 2 ? null : Number(parts[0]);
    const id = parts === null || parts.length !== 2 ? null : decodeDigest(parts[1]);
    if (createdAt === null || !Number.isFinite(createdAt) || id === null) {
      return refuse(400, "invalid_request", "before is invalid", timing);
    }
    before = { createdAt, id };
  }
  const started = performance.now();
  try {
    const rows = await readSnapshots(env.DB, origin, limit + 1, before);
    const page = rows.slice(0, limit);
    const last = page.at(-1);
    return json(200, {
      protocol: PROTOCOL,
      origin,
      snapshots: page.map(snapshotJson),
      next_cursor: rows.length > limit && last !== undefined
        ? encodeCursor([String(last.created_at), last.id])
        : null,
    }, false, { "Server-Timing": serverTiming(timing) });
  } finally {
    timing.d1 += performance.now() - started;
  }
}

async function detail(
  request: Request,
  env: Env,
  principal: Principal,
  id: string,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "GET") return methodNotAllowed(["GET"], { "Server-Timing": serverTiming(timing) });
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  const started = performance.now();
  try {
    const row = await readSnapshot(env.DB, principal.origin_host, id);
    if (row === null) return refuse(404, "not_found", "snapshot not found", timing);
    const chunks = await readSnapshotChunks(env.DB, principal.origin_host, id);
    const objects = await readSnapshotObjects(env.DB, principal.origin_host, id);
    const chunkJsonRows = chunks.map(chunkJson);
    const objectJsonRows = objects.map(objectJson);
    if (chunkJsonRows.some((item) => item === null) || objectJsonRows.some((item) => item === null)) {
      return refuse(409, "missing_object", "snapshot references an object that is not stored", timing);
    }
    const chunkBytes = chunks.reduce((total, chunk) => total + chunk.size, 0);
    if (chunkBytes !== row.db_size || chunks.length === 0) {
      return refuse(503, "unavailable", "snapshot chunks do not cover the database", timing);
    }
    return json(200, {
      protocol: PROTOCOL,
      origin: principal.origin_host,
      snapshot: snapshotJson(row),
      chunks: chunkJsonRows,
      objects: objectJsonRows,
    }, false, { "Server-Timing": serverTiming(timing) });
  } finally {
    timing.d1 += performance.now() - started;
  }
}

async function verify(
  request: Request,
  env: Env,
  principal: Principal,
  id: string,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const verifyBody = decodeSnapshotVerifyRequest(body.value);
  if (verifyBody === null) return refuse(400, "invalid_request", "invalid snapshot verification", timing);
  const mismatch = boundOrigin(principal, verifyBody.origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  try {
    const existing = await readSnapshot(env.DB, verifyBody.origin, id);
    if (existing === null) return refuse(404, "not_found", "snapshot not found", timing);
    const verifiedAt = await markSnapshotVerified(env.DB, verifyBody.origin, id, Date.now() / 1000);
    return json(200, {
      protocol: PROTOCOL,
      origin: verifyBody.origin,
      snapshot: id,
      verified_at: verifiedAt,
      duplicate: existing.verified_at !== null,
    }, false, { "Server-Timing": serverTiming(timing) });
  } finally {
    timing.d1 += performance.now() - started;
  }
}

async function gc(
  request: Request,
  env: Env,
  principal: Principal,
  timing: SyncTiming,
): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const gcBody = decodeGcRequest(body.value);
  if (gcBody === null) return refuse(400, "invalid_request", "invalid gc request", timing);
  const mismatch = boundOrigin(principal, gcBody.origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  try {
    const now = Date.now() / 1000;
    const snapshots = await readSnapshots(env.DB, gcBody.origin, 1_000);
    const retained = retainedSnapshotIds(snapshots, now);
    const pruned = snapshots.filter((row) => !retained.has(row.id)).map((row) => row.id);
    const pruneBatch = gcBody.apply ? pruned.slice(0, MAX_GC_PRUNE) : pruned;
    if (gcBody.apply && pruneBatch.length > 0) await deleteSnapshots(env.DB, pruneBatch);
    const excluded = gcBody.apply ? pruneBatch : pruned;
    const pending = await readUnreferencedObjects(env.DB, gcBody.origin, excluded);
    const markable = pending.filter((row) => row.gc_pending_at === null);
    if (gcBody.apply && markable.length > 0) {
      await markUnreferencedObjects(env.DB, gcBody.origin, now, excluded);
    }
    const cutoff = now - GC_GRACE_SECONDS;
    const sweepable = await readUnreferencedObjects(env.DB, gcBody.origin, excluded, cutoff);
    const batch = gcBody.apply ? sweepable.slice(0, MAX_GC_SWEEP) : sweepable;
    let swept = 0;
    let sweptBytes = 0;
    const deletedKeys: string[] = [];
    for (const row of batch) {
      if (gcBody.apply) {
        const deleted = await deleteObjectIfGcEligible(env.DB, gcBody.origin, row.plaintext_digest, cutoff, excluded);
        if (!deleted) continue;
        deletedKeys.push(`v1/o/${row.ciphertext_digest}`);
      }
      swept += 1;
      sweptBytes += row.ciphertext_size;
    }
    if (deletedKeys.length > 0) await env.BUCKET.delete(deletedKeys);
    return json(200, {
      protocol: PROTOCOL,
      origin: gcBody.origin,
      apply: gcBody.apply,
      snapshots_retained: snapshots.length - pruneBatch.length,
      snapshots_pruned: pruneBatch.length,
      objects_marked: markable.length,
      bytes_marked: markable.reduce((total, row) => total + row.ciphertext_size, 0),
      objects_swept: swept,
      bytes_swept: sweptBytes,
    }, false, { "Server-Timing": serverTiming(timing) });
  } finally {
    timing.d1 += performance.now() - started;
  }
}

export async function handleSnapshots(
  request: Request,
  env: Env,
  principal: Principal,
  pathname: string,
  url: URL,
  timing: SyncTiming,
): Promise<Response | null> {
  if (pathname === SNAPSHOTS_PATH) {
    if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
    if (request.method === "POST") return await commit(request, env, principal, timing);
    if (request.method === "GET") return await list(request, env, principal, url, timing);
    return methodNotAllowed(["GET", "POST"], { "Server-Timing": serverTiming(timing) });
  }
  if (pathname === GC_PATH) {
    if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
    return await gc(request, env, principal, timing);
  }
  if (!pathname.startsWith(SNAPSHOT_PREFIX)) return null;
  const rest = pathname.slice(SNAPSHOT_PREFIX.length);
  const [id, action, ...extra] = rest.split("/");
  if (extra.length > 0 || id === undefined || action !== undefined && action !== "verify") {
    return refuse(404, "not_found", "route not found", timing);
  }
  const snapshotId = decodeDigest(id);
  if (snapshotId === null) return refuse(404, "not_found", "route not found", timing);
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  if (action === "verify") return await verify(request, env, principal, snapshotId, timing);
  return await detail(request, env, principal, snapshotId, timing);
}
