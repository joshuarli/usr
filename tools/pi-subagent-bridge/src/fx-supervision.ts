import { closeSync, openSync, readFileSync, readdirSync, readSync, renameSync, statSync, writeFileSync } from "node:fs"
import { join } from "node:path"

export type ExhaustionWatch = { dir: string; retry_after_seconds: number }

/**
 * Scan appended FX session-log records for a quota failure or a provider-declared retry delay
 * beyond the job's bound. Content predating the job (resumed sessions) is baselined, never matched.
 */
export function exhaustionWatcher(exhaustion: ExhaustionWatch, jobStartedMs: number): () => boolean {
  const exhaustionOffsets = new Map<string, number>()
  return function exhaustionHit(): boolean {
    let entries
    try { entries = readdirSync(exhaustion.dir, { withFileTypes: true }) } catch { return false }
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const path = join(exhaustion.dir, entry.name, "log.jsonl")
      let stat
      try { stat = statSync(path) } catch { continue }
      let offset = exhaustionOffsets.get(path)
      if (offset === undefined) {
        offset = stat.mtimeMs < jobStartedMs ? stat.size : 0
        exhaustionOffsets.set(path, offset)
      }
      if (stat.size <= offset) { if (stat.size < offset) exhaustionOffsets.set(path, 0); continue }
      let chunk = ""
      try {
        const fd = openSync(path, "r")
        try {
          const buffer = Buffer.alloc(stat.size - offset)
          const got = readSync(fd, buffer, 0, buffer.length, offset)
          chunk = buffer.subarray(0, got).toString("utf8")
        } finally { closeSync(fd) }
      } catch { continue }
      const lastNewline = chunk.lastIndexOf("\n")
      if (lastNewline < 0) continue
      exhaustionOffsets.set(path, offset + lastNewline + 1)
      for (const line of chunk.slice(0, lastNewline).split("\n")) {
        if (line.includes('"failure":"quota"')) return true
        const retry = /"retry_after_s":(\d+)/.exec(line)
        if (retry && Number(retry[1]) > exhaustion.retry_after_seconds) return true
      }
    }
    return false
  }
}

const MAX_SECRET_BYTES = 16_384

/** Read secret environment values from their 0600 files at spawn time so job records never hold them. */
export function secretEnvironment(base: NodeJS.ProcessEnv, files: Record<string, string> | undefined): NodeJS.ProcessEnv {
  const env = { ...base }
  for (const [name, path] of Object.entries(files ?? {})) {
    const content = readFileSync(path, "utf8")
    if (Buffer.byteLength(content) > MAX_SECRET_BYTES) throw new Error("secret env file too large: " + name)
    env[name] = content.trimEnd()
  }
  return env
}

export function writeReceipt(output: string, receipt: Record<string, unknown>): void {
  const temporary = output + ".tmp"
  writeFileSync(temporary, JSON.stringify(receipt), { mode: 0o600 })
  renameSync(temporary, output)
}
