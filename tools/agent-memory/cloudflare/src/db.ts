export interface StoreMeta {
  readonly id: string;
  readonly created_at: number;
}

export interface OriginState {
  readonly revision: number;
  readonly tombstone_watermark: number;
}

export interface RemoteObjectRow {
  readonly plaintext_digest: string;
  readonly plaintext_size: number;
  readonly encoding: string;
  readonly ciphertext_digest: string;
  readonly ciphertext_size: number;
}

export interface NewRemoteObject {
  readonly plaintext_digest: string;
  readonly plaintext_size: number;
  readonly encoding: string;
  readonly ciphertext_digest: string;
  readonly ciphertext_size: number;
  readonly origin_host: string;
  readonly created_at: number;
}

const QUERY_CHUNK = 90;

export async function readStoreMeta(db: D1Database): Promise<StoreMeta | null> {
  return await db.prepare("SELECT id, created_at FROM store_meta LIMIT 1").first<StoreMeta>();
}

export async function readOriginState(db: D1Database, origin: string): Promise<OriginState> {
  const sync = await db.prepare("SELECT revision FROM origin_sync WHERE origin_host = ?")
    .bind(origin)
    .first<{ readonly revision: number }>();
  const tombstone = await db.prepare("SELECT COALESCE(MAX(revision), 0) AS watermark FROM tombstone WHERE origin_host = ?")
    .bind(origin)
    .first<{ readonly watermark: number }>();
  return {
    revision: sync?.revision ?? 0,
    tombstone_watermark: tombstone?.watermark ?? 0,
  };
}

export async function readKnownObjects(
  db: D1Database,
  origin: string,
  digests: readonly string[],
): Promise<readonly RemoteObjectRow[]> {
  const rows: RemoteObjectRow[] = [];
  for (let start = 0; start < digests.length; start += QUERY_CHUNK) {
    const chunk = digests.slice(start, start + QUERY_CHUNK);
    const placeholders = chunk.map(() => "?").join(",");
    const result = await db.prepare(
      `SELECT plaintext_digest, plaintext_size, encoding, ciphertext_digest, ciphertext_size
       FROM remote_object WHERE origin_host = ? AND plaintext_digest IN (${placeholders})`,
    ).bind(origin, ...chunk).all<RemoteObjectRow>();
    rows.push(...result.results);
  }
  return rows;
}

export async function readObjectByCiphertext(
  db: D1Database,
  origin: string,
  ciphertext: string,
): Promise<RemoteObjectRow | null> {
  return await db.prepare(
    `SELECT plaintext_digest, plaintext_size, encoding, ciphertext_digest, ciphertext_size
     FROM remote_object WHERE origin_host = ? AND ciphertext_digest = ?`,
  ).bind(origin, ciphertext).first<RemoteObjectRow>();
}

export async function insertRemoteObject(db: D1Database, object: NewRemoteObject): Promise<void> {
  await db.prepare(
    `INSERT OR IGNORE INTO remote_object(
       plaintext_digest, plaintext_size, encoding, ciphertext_digest, ciphertext_size,
       origin_host, created_at
     ) VALUES(?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    object.plaintext_digest,
    object.plaintext_size,
    object.encoding,
    object.ciphertext_digest,
    object.ciphertext_size,
    object.origin_host,
    object.created_at,
  ).run();
}

export async function readObjectByPlaintext(
  db: D1Database,
  origin: string,
  plaintext: string,
): Promise<RemoteObjectRow | null> {
  return await db.prepare(
    `SELECT plaintext_digest, plaintext_size, encoding, ciphertext_digest, ciphertext_size
     FROM remote_object WHERE origin_host = ? AND plaintext_digest = ?`,
  ).bind(origin, plaintext).first<RemoteObjectRow>();
}
