export const PROTOCOL = 1;
export const MAX_JSON_BYTES = 8 * 1024 * 1024;
export const MAX_OBJECT_BYTES = 8 * 1024 * 1024;
export const MAX_MISSING_OBJECTS = 20_000;
export const MAX_CURSOR_CHARS = 512;
export const MAX_CURSOR_PARTS = 4;
export const MAX_CURSOR_PART_CHARS = 256;

export const ERROR_CODES = [
  "forbidden",
  "not_found",
  "method_not_allowed",
  "unavailable",
  "invalid_request",
  "unsupported_version",
  "payload_too_large",
] as const;

const DIGEST = /^[0-9a-f]{64}$/;
const ORIGIN = /^[A-Za-z0-9._-]{1,128}$/;
const BASE64URL = /^[A-Za-z0-9_-]+$/;

export interface HelloRequest {
  readonly protocol: 1;
  readonly origin: string;
}

export interface MissingObject {
  readonly plaintext_digest: string;
  readonly size: number;
}

export interface MissingRequest {
  readonly protocol: 1;
  readonly origin: string;
  readonly objects: readonly MissingObject[];
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

export function decodeDigest(value: unknown): string | null {
  return typeof value === "string" && DIGEST.test(value) ? value : null;
}

export function decodeOrigin(value: unknown): string | null {
  return typeof value === "string" && ORIGIN.test(value) ? value : null;
}

export function decodeProtocol(value: unknown): 1 | null {
  return value === PROTOCOL ? PROTOCOL : null;
}

function decodeSize(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= MAX_OBJECT_BYTES
    ? value
    : null;
}

export function decodeHello(value: unknown): HelloRequest | null {
  if (!isRecord(value) || !exactKeys(value, ["protocol", "origin"])) return null;
  if (decodeProtocol(value.protocol) === null) return null;
  const origin = decodeOrigin(value.origin);
  return origin === null ? null : { protocol: PROTOCOL, origin };
}

function decodeMissingObject(value: unknown): MissingObject | null {
  if (!isRecord(value) || !exactKeys(value, ["plaintext_digest", "size"])) return null;
  const plaintext = decodeDigest(value.plaintext_digest);
  const size = decodeSize(value.size);
  return plaintext === null || size === null ? null : { plaintext_digest: plaintext, size };
}

export function decodeMissingRequest(value: unknown): MissingRequest | null {
  if (!isRecord(value) || !exactKeys(value, ["protocol", "origin", "objects"])) return null;
  if (decodeProtocol(value.protocol) === null) return null;
  const origin = decodeOrigin(value.origin);
  if (origin === null || !Array.isArray(value.objects)) return null;
  if (value.objects.length > MAX_MISSING_OBJECTS) return null;
  const objects: MissingObject[] = [];
  const digests = new Set<string>();
  for (const entry of value.objects) {
    const object = decodeMissingObject(entry);
    if (object === null || digests.has(object.plaintext_digest)) return null;
    digests.add(object.plaintext_digest);
    objects.push(object);
  }
  return { protocol: PROTOCOL, origin, objects };
}

function encodeBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeBase64Url(value: string): Uint8Array | null {
  if (!BASE64URL.test(value)) return null;
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  try {
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
  } catch {
    return null;
  }
}

function validCursorPart(value: unknown): value is string {
  return typeof value === "string" && value !== "" && value.length <= MAX_CURSOR_PART_CHARS;
}

export function encodeCursor(parts: readonly string[]): string {
  if (parts.length === 0 || parts.length > MAX_CURSOR_PARTS || !parts.every(validCursorPart)) {
    throw new Error("cursor parts are invalid");
  }
  const encoded = encodeBase64Url(new TextEncoder().encode(JSON.stringify(parts)));
  if (encoded.length > MAX_CURSOR_CHARS) throw new Error("cursor is too long");
  return encoded;
}

export function decodeCursor(value: string): readonly string[] | null {
  if (value === "" || value.length > MAX_CURSOR_CHARS) return null;
  const bytes = decodeBase64Url(value);
  if (bytes === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
  if (!Array.isArray(parsed) || parsed.length === 0 || parsed.length > MAX_CURSOR_PARTS) return null;
  if (!parsed.every(validCursorPart)) return null;
  return parsed;
}
