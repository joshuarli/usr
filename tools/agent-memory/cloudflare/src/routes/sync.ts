import type { Principal } from "../auth";
import {
  insertRemoteObject,
  readKnownObjects,
  readObjectByCiphertext,
  readObjectByPlaintext,
  readOriginState,
  readStoreMeta,
  type OriginState,
  type RemoteObjectRow,
  type StoreMeta,
} from "../db";
import { SECURITY_HEADERS, failure, json, methodNotAllowed } from "../errors";
import { serverTiming } from "../observe";
import {
  MAX_JSON_BYTES,
  MAX_OBJECT_BYTES,
  PROTOCOL,
  decodeDigest,
  decodeHello,
  decodeMissingRequest,
  isRecord,
} from "../protocol";
import type { Env } from "../index";

export interface SyncTiming {
  d1: number;
  r2: number;
}

const HELLO_PATH = "/api/v1/sync/hello";
const MISSING_PATH = "/api/v1/sync/objects/missing";
const OBJECT_PREFIX = "/api/v1/sync/objects/";
const ENCODINGS = new Set(["identity", "zlib"]);

type BodyResult =
  | { readonly ok: true; readonly value: unknown }
  | { readonly ok: false; readonly response: Response };

type BoundedBody =
  | { readonly ok: true; readonly bytes: Uint8Array }
  | { readonly ok: false; readonly tooLarge: boolean };

function headers(timing: SyncTiming, extra: Readonly<Record<string, string>> = {}): Headers {
  return new Headers({ ...SECURITY_HEADERS, "Server-Timing": serverTiming(timing), ...extra });
}

function refuse(status: number, code: Parameters<typeof failure>[1], message: string, timing: SyncTiming): Response {
  return failure(status, code, message, { "Server-Timing": serverTiming(timing) });
}

function contentLength(request: Request): number | null {
  const value = request.headers.get("Content-Length");
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

async function readBounded(request: Request, limit: number): Promise<BoundedBody> {
  const declared = contentLength(request);
  if (request.headers.get("Content-Length") !== null && declared === null) {
    return { ok: false, tooLarge: false };
  }
  if (declared !== null && declared > limit) return { ok: false, tooLarge: true };
  const reader = request.body?.getReader();
  if (reader === undefined) return { ok: true, bytes: new Uint8Array() };
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      return { ok: false, tooLarge: true };
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { ok: true, bytes };
}

async function readJson(request: Request, timing: SyncTiming): Promise<BodyResult> {
  const body = await readBounded(request, MAX_JSON_BYTES);
  if (!body.ok) {
    return {
      ok: false,
      response: body.tooLarge
        ? refuse(413, "payload_too_large", "request body exceeds the limit", timing)
        : refuse(400, "invalid_request", "content length is invalid", timing),
    };
  }
  if (body.bytes.byteLength === 0) {
    return { ok: false, response: refuse(400, "invalid_request", "request body is required", timing) };
  }
  try {
    return { ok: true, value: JSON.parse(new TextDecoder().decode(body.bytes)) };
  } catch {
    return { ok: false, response: refuse(400, "invalid_request", "request body is not valid JSON", timing) };
  }
}

function mapping(row: RemoteObjectRow): Record<string, unknown> {
  return {
    plaintext_digest: row.plaintext_digest,
    plaintext_size: row.plaintext_size,
    encoding: row.encoding,
    ciphertext_digest: row.ciphertext_digest,
    ciphertext_size: row.ciphertext_size,
  };
}

function versionOrError(value: unknown, timing: SyncTiming): Response | null {
  if (!isRecord(value)) return refuse(400, "invalid_request", "request body must be an object", timing);
  if (!Object.hasOwn(value, "protocol")) return refuse(400, "invalid_request", "protocol is required", timing);
  if (value.protocol !== PROTOCOL) return refuse(400, "unsupported_version", "protocol version is not supported", timing);
  return null;
}

function boundOrigin(principal: Principal, origin: string, timing: SyncTiming): Response | null {
  if (principal.kind !== "collector" || principal.origin_host !== origin) {
    return refuse(403, "forbidden", "origin does not match the collector binding", timing);
  }
  return null;
}

async function hello(request: Request, env: Env, principal: Principal, timing: SyncTiming): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const helloBody = decodeHello(body.value);
  if (helloBody === null) return refuse(400, "invalid_request", "invalid hello request", timing);
  const mismatch = boundOrigin(principal, helloBody.origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  let store: StoreMeta | null;
  let state: OriginState;
  try {
    store = await readStoreMeta(env.DB);
    state = await readOriginState(env.DB, helloBody.origin);
  } finally {
    timing.d1 += performance.now() - started;
  }
  if (store === null) return refuse(503, "unavailable", "store is not provisioned", timing);
  return json(200, {
    protocol: PROTOCOL,
    store_id: store.id,
    origin: helloBody.origin,
    revision: state.revision,
    tombstone_watermark: state.tombstone_watermark,
    learning: { revision: 0, digest: null, records: 0 },
  }, false, { "Server-Timing": serverTiming(timing) });
}

async function missing(request: Request, env: Env, principal: Principal, timing: SyncTiming): Promise<Response> {
  if (request.method !== "POST") return methodNotAllowed(["POST"], { "Server-Timing": serverTiming(timing) });
  const body = await readJson(request, timing);
  if (!body.ok) return body.response;
  const version = versionOrError(body.value, timing);
  if (version !== null) return version;
  const missingBody = decodeMissingRequest(body.value);
  if (missingBody === null) return refuse(400, "invalid_request", "invalid missing-objects request", timing);
  const mismatch = boundOrigin(principal, missingBody.origin, timing);
  if (mismatch !== null) return mismatch;
  const started = performance.now();
  let known: readonly RemoteObjectRow[];
  try {
    known = await readKnownObjects(env.DB, missingBody.origin, missingBody.objects.map((object) => object.plaintext_digest));
  } finally {
    timing.d1 += performance.now() - started;
  }
  const present = new Set(known.map((row) => row.plaintext_digest));
  return json(200, {
    protocol: PROTOCOL,
    origin: missingBody.origin,
    missing: missingBody.objects.filter((object) => !present.has(object.plaintext_digest)),
    known: known.map(mapping),
  }, false, { "Server-Timing": serverTiming(timing) });
}

function plaintextSize(request: Request): number | null {
  const value = request.headers.get("X-Plaintext-Size");
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 && parsed <= MAX_OBJECT_BYTES ? parsed : null;
}

async function putObject(
  request: Request,
  env: Env,
  principal: Principal,
  ciphertext: string,
  timing: SyncTiming,
): Promise<Response> {
  const declared = contentLength(request);
  if (declared !== null && declared > MAX_OBJECT_BYTES) {
    return refuse(413, "payload_too_large", "object body exceeds the limit", timing);
  }
  const plaintext = decodeDigest(request.headers.get("X-Plaintext-Digest"));
  const size = plaintextSize(request);
  const encoding = request.headers.get("X-Encoding");
  if (plaintext === null || size === null || encoding === null || !ENCODINGS.has(encoding)) {
    return refuse(400, "invalid_request", "object headers are invalid", timing);
  }
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  const existing = await readObjectByCiphertext(env.DB, principal.origin_host, ciphertext);
  if (existing !== null) {
    if (existing.plaintext_digest !== plaintext || existing.plaintext_size !== size || existing.encoding !== encoding) {
      return refuse(409, "conflict", "ciphertext is already bound to another object", timing);
    }
    const head = await env.BUCKET.head(`v1/o/${ciphertext}`);
    if (head !== null) {
      return json(200, { stored: false, object: mapping(existing) }, false, {
        "Server-Timing": serverTiming(timing),
      });
    }
  }
  const body = await readBounded(request, MAX_OBJECT_BYTES);
  if (!body.ok) {
    return body.tooLarge
      ? refuse(413, "payload_too_large", "object body exceeds the limit", timing)
      : refuse(400, "invalid_request", "content length is invalid", timing);
  }
  if (body.bytes.byteLength === 0) {
    return refuse(400, "invalid_request", "request body is required", timing);
  }
  const received = body.bytes.byteLength;
  const started = performance.now();
  try {
    await env.BUCKET.put(`v1/o/${ciphertext}`, body.bytes, { sha256: ciphertext });
  } catch {
    timing.r2 += performance.now() - started;
    return refuse(400, "invalid_request", "ciphertext failed storage validation", timing);
  }
  timing.r2 += performance.now() - started;
  await insertRemoteObject(env.DB, {
    plaintext_digest: plaintext,
    plaintext_size: size,
    encoding,
    ciphertext_digest: ciphertext,
    ciphertext_size: received,
    origin_host: principal.origin_host,
    created_at: Date.now() / 1000,
  });
  const stored = await readObjectByPlaintext(env.DB, principal.origin_host, plaintext);
  if (stored === null) {
    return refuse(409, "conflict", "ciphertext is already bound to another plaintext", timing);
  }
  return json(200, {
    stored: stored.ciphertext_digest === ciphertext,
    object: mapping(stored),
  }, false, { "Server-Timing": serverTiming(timing) });
}

async function readObject(
  env: Env,
  principal: Principal,
  ciphertext: string,
  timing: SyncTiming,
): Promise<Response> {
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  const started = performance.now();
  let row: RemoteObjectRow | null;
  try {
    row = await readObjectByCiphertext(env.DB, principal.origin_host, ciphertext);
  } finally {
    timing.d1 += performance.now() - started;
  }
  if (row === null) return refuse(404, "not_found", "object not found", timing);
  const stored = await env.BUCKET.get(`v1/o/${ciphertext}`);
  if (stored === null) return refuse(404, "not_found", "object not found", timing);
  return new Response(stored.body, {
    status: 200,
    headers: headers(timing, {
      "Content-Type": "application/octet-stream",
      "Content-Length": String(row.ciphertext_size),
      "X-Plaintext-Digest": row.plaintext_digest,
      "X-Plaintext-Size": String(row.plaintext_size),
      "X-Encoding": row.encoding,
    }),
  });
}

export async function handleSync(
  request: Request,
  env: Env,
  principal: Principal,
  pathname: string,
  timing: SyncTiming,
): Promise<Response | null> {
  if (pathname === HELLO_PATH) {
    if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
    return await hello(request, env, principal, timing);
  }
  if (pathname === MISSING_PATH) {
    if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
    return await missing(request, env, principal, timing);
  }
  if (!pathname.startsWith(OBJECT_PREFIX)) return null;
  const ciphertext = decodeDigest(pathname.slice(OBJECT_PREFIX.length));
  if (ciphertext === null) return refuse(404, "not_found", "route not found", timing);
  if (principal.kind !== "collector") return refuse(403, "forbidden", "collector token required", timing);
  if (request.method === "PUT") return await putObject(request, env, principal, ciphertext, timing);
  if (request.method === "GET") return await readObject(env, principal, ciphertext, timing);
  return methodNotAllowed(["GET", "PUT"], { "Server-Timing": serverTiming(timing) });
}
