import { readdirSync, statSync } from "node:fs"
import { join, relative } from "node:path"
import { fileURLToPath } from "node:url"

export type SourceStat = { size: number; mtimeMs: number }
export type SourceSnapshot = ReadonlyMap<string, SourceStat>

const SRC = fileURLToPath(new URL(".", import.meta.url))

function walk(root: string): Array<string> {
  const found: Array<string> = []
  const visit = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name)
      if (entry.isDirectory()) visit(full)
      else if (entry.name.endsWith(".ts")) found.push(full)
    }
  }
  visit(root)
  found.push(join(root, "..", "package.json"))
  found.push(join(root, "../../..", "harnesses.json"))
  return found
}

export function snapshotSource(root: string = SRC): SourceSnapshot {
  const out = new Map<string, SourceStat>()
  for (const file of walk(root)) {
    try {
      const stat = statSync(file)
      out.set(relative(root, file), { size: stat.size, mtimeMs: stat.mtimeMs })
    } catch { /* a vanished file is reported by sourceChanged */ }
  }
  return out
}

/** First path whose stat differs from the snapshot, or null when the source is unchanged. */
export function sourceChanged(snapshot: SourceSnapshot, root: string = SRC): string | null {
  const current = snapshotSource(root)
  for (const [path, stat] of snapshot) {
    const now = current.get(path)
    if (!now || now.size !== stat.size || now.mtimeMs !== stat.mtimeMs) return path
  }
  if (current.size !== snapshot.size) return [...current.keys()].find(path => !snapshot.has(path)) ?? "source tree"
  return null
}
