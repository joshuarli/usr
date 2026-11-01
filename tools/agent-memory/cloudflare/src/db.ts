export interface StoreMeta {
  readonly id: string;
  readonly created_at: number;
}

export async function readStoreMeta(db: D1Database): Promise<StoreMeta | null> {
  return await db.prepare("SELECT id, created_at FROM store_meta LIMIT 1").first<StoreMeta>();
}
