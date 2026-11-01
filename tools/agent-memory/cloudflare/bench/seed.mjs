import { readFileSync } from "node:fs";

const MIGRATION = new URL("../migrations/0001_init.sql", import.meta.url);

function statements(sql) {
  return sql.split(";").map((statement) => statement.trim()).filter(Boolean);
}

export async function seedDatabase(db) {
  for (const statement of statements(readFileSync(MIGRATION, "utf8"))) {
    await db.prepare(statement).run();
  }
}
