export interface StoreMeta {
  readonly id: string;
  readonly created_at: number;
}

export interface OriginState {
  readonly revision: number;
  readonly tombstone_watermark: number;
}

export interface GenerationRow {
  readonly id: number;
  readonly origin_host: string;
  readonly harness: string;
  readonly native_id: string;
  readonly manifest_digest: string;
  readonly source_digest: string;
  readonly source_size: number;
  readonly captured_at: number;
  readonly committed_at: number;
  readonly revision: number;
  readonly manifest_object: string;
}

export interface GenerationChunk {
  readonly digest: string;
  readonly size: number;
}

export interface NewGeneration {
  readonly origin_host: string;
  readonly harness: string;
  readonly native_id: string;
  readonly manifest_digest: string;
  readonly source_digest: string;
  readonly source_size: number;
  readonly captured_at: number;
  readonly committed_at: number;
  readonly manifest_object: string;
  readonly objects: readonly GenerationChunk[];
}

export interface TombstoneRow {
  readonly origin_host: string;
  readonly harness: string;
  readonly native_id: string;
  readonly scope: string;
  readonly forgotten_at: number;
  readonly revision: number;
}

export interface TombstoneKey {
  readonly harness: string;
  readonly native_id: string;
}

export interface NewTombstone extends TombstoneKey {
  readonly scope: string;
  readonly forgotten_at: number;
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

const GENERATION_COLUMNS =
  "id, origin_host, harness, native_id, manifest_digest, source_digest, source_size, captured_at, committed_at, revision, manifest_object";

export async function readGenerationByManifest(
  db: D1Database,
  origin: string,
  manifest: string,
): Promise<GenerationRow | null> {
  return await db.prepare(
    `SELECT ${GENERATION_COLUMNS} FROM generation WHERE origin_host = ? AND manifest_digest = ?`,
  ).bind(origin, manifest).first<GenerationRow>();
}

export async function readObjectSizes(
  db: D1Database,
  origin: string,
  digests: readonly string[],
): Promise<ReadonlyMap<string, number>> {
  const sizes = new Map<string, number>();
  for (let start = 0; start < digests.length; start += QUERY_CHUNK) {
    const chunk = digests.slice(start, start + QUERY_CHUNK);
    const placeholders = chunk.map(() => "?").join(",");
    const result = await db.prepare(
      `SELECT plaintext_digest, plaintext_size FROM remote_object
       WHERE origin_host = ? AND plaintext_digest IN (${placeholders})`,
    ).bind(origin, ...chunk).all<{ readonly plaintext_digest: string; readonly plaintext_size: number }>();
    for (const row of result.results) sizes.set(row.plaintext_digest, row.plaintext_size);
  }
  return sizes;
}

export async function commitGeneration(
  db: D1Database,
  generation: NewGeneration,
  baseRevision: number,
): Promise<{ readonly id: number; readonly revision: number }> {
  const revision = baseRevision + 1;
  const statements: D1PreparedStatement[] = [
    db.prepare("INSERT OR IGNORE INTO origin_sync(origin_host, revision, last_change_at) VALUES(?, 0, NULL)")
      .bind(generation.origin_host),
    db.prepare(
      `INSERT INTO generation(
         origin_host, harness, native_id, manifest_digest, source_digest, source_size,
         captured_at, committed_at, revision, manifest_object
       ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(
      generation.origin_host,
      generation.harness,
      generation.native_id,
      generation.manifest_digest,
      generation.source_digest,
      generation.source_size,
      generation.captured_at,
      generation.committed_at,
      revision,
      generation.manifest_object,
    ),
  ];
  const ROWS_PER_STATEMENT = 32;
  for (let start = 0; start < generation.objects.length; start += ROWS_PER_STATEMENT) {
    const chunk = generation.objects.slice(start, start + ROWS_PER_STATEMENT);
    const values = chunk.map(() => "(?, ?, ?)").join(",");
    const params: (string | number)[] = [generation.origin_host, generation.manifest_digest];
    chunk.forEach((object, index) => {
      params.push(start + index, object.digest, object.size);
    });
    statements.push(
      db.prepare(
        `INSERT INTO generation_object(generation, ordinal, plaintext_digest, size)
         SELECT (SELECT id FROM generation WHERE origin_host = ? AND manifest_digest = ?),
                column1, column2, column3
         FROM (VALUES ${values})`,
      ).bind(...params),
    );
  }
  statements.push(
    db.prepare("UPDATE origin_sync SET revision = revision + 1, last_change_at = ? WHERE origin_host = ?")
      .bind(generation.committed_at, generation.origin_host),
  );
  const results = await db.batch(statements);
  const inserted = results[1];
  const id = inserted?.meta.last_row_id ?? 0;
  if (id <= 0) throw new Error("generation insert did not return an id");
  return { id, revision };
}

export async function readGenerations(
  db: D1Database,
  origin: string,
  after: number,
  limit: number,
): Promise<readonly GenerationRow[]> {
  const result = await db.prepare(
    `SELECT ${GENERATION_COLUMNS} FROM generation g
     WHERE g.origin_host = ? AND g.id > ?
       AND NOT EXISTS (
         SELECT 1 FROM tombstone t
         WHERE t.origin_host = g.origin_host AND t.harness = g.harness AND t.native_id = g.native_id
       )
     ORDER BY g.id LIMIT ?`,
  ).bind(origin, after, limit).all<GenerationRow>();
  return result.results;
}

export async function readTombstone(
  db: D1Database,
  origin: string,
  harness: string,
  native: string,
): Promise<TombstoneRow | null> {
  return await db.prepare(
    `SELECT origin_host, harness, native_id, scope, forgotten_at, revision
     FROM tombstone WHERE origin_host = ? AND harness = ? AND native_id = ?`,
  ).bind(origin, harness, native).first<TombstoneRow>();
}

export async function readTombstones(
  db: D1Database,
  origin: string,
  after: { readonly revision: number; readonly harness: string; readonly native_id: string } | null,
  limit: number,
): Promise<readonly TombstoneRow[]> {
  if (after === null) {
    const result = await db.prepare(
      `SELECT origin_host, harness, native_id, scope, forgotten_at, revision
       FROM tombstone WHERE origin_host = ? ORDER BY revision, harness, native_id LIMIT ?`,
    ).bind(origin, limit).all<TombstoneRow>();
    return result.results;
  }
  const result = await db.prepare(
    `SELECT origin_host, harness, native_id, scope, forgotten_at, revision
     FROM tombstone WHERE origin_host = ?
       AND (revision > ? OR (revision = ? AND (harness > ? OR (harness = ? AND native_id > ?))))
     ORDER BY revision, harness, native_id LIMIT ?`,
  ).bind(origin, after.revision, after.revision, after.harness, after.harness, after.native_id, limit)
    .all<TombstoneRow>();
  return result.results;
}

export async function readTombstoneKeys(
  db: D1Database,
  origin: string,
  keys: readonly TombstoneKey[],
): Promise<ReadonlyMap<string, TombstoneRow>> {
  const rows = new Map<string, TombstoneRow>();
  const PAIRS_PER_QUERY = 40;
  for (let start = 0; start < keys.length; start += PAIRS_PER_QUERY) {
    const chunk = keys.slice(start, start + PAIRS_PER_QUERY);
    const clauses = chunk.map(() => "(harness = ? AND native_id = ?)").join(" OR ");
    const params: string[] = [];
    for (const key of chunk) params.push(key.harness, key.native_id);
    const result = await db.prepare(
      `SELECT origin_host, harness, native_id, scope, forgotten_at, revision
       FROM tombstone WHERE origin_host = ? AND (${clauses})`,
    ).bind(origin, ...params).all<TombstoneRow>();
    for (const row of result.results) rows.set(`${row.harness}:${row.native_id}`, row);
  }
  return rows;
}

export async function pushTombstones(
  db: D1Database,
  origin: string,
  tombstones: readonly NewTombstone[],
  baseRevision: number,
): Promise<number> {
  const revision = baseRevision + 1;
  const statements: D1PreparedStatement[] = [
    db.prepare("INSERT OR IGNORE INTO origin_sync(origin_host, revision, last_change_at) VALUES(?, 0, NULL)")
      .bind(origin),
  ];
  for (const tombstone of tombstones) {
    statements.push(
      db.prepare(
        `INSERT INTO tombstone(origin_host, harness, native_id, scope, forgotten_at, revision)
         VALUES(?, ?, ?, ?, ?, ?)
         ON CONFLICT(origin_host, harness, native_id) DO UPDATE SET
           scope = excluded.scope, forgotten_at = excluded.forgotten_at, revision = excluded.revision
         WHERE excluded.forgotten_at > tombstone.forgotten_at`,
      ).bind(origin, tombstone.harness, tombstone.native_id, tombstone.scope, tombstone.forgotten_at, revision),
    );
  }
  statements.push(
    db.prepare("UPDATE origin_sync SET revision = revision + 1, last_change_at = ? WHERE origin_host = ?")
      .bind(Date.now() / 1000, origin),
  );
  await db.batch(statements);
  return revision;
}
