import { randomUUID } from "node:crypto"
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { isRecord } from "./scope.ts"

export const DEFAULT_EXHAUSTION_MS = 60 * 60 * 1000
export const MAX_EXHAUSTION_MS = 30 * 24 * 60 * 60 * 1000

export type RouteRef =
  | { readonly executor: "command-code" | "codex"; readonly model: string }
  | { readonly executor: "pi"; readonly providerID: string; readonly id: string }

export type ExhaustedRoute = { readonly until: number; readonly reason: string; readonly recorded_at: string }

type StoreFile = { readonly schema_version: 1; readonly routes: Record<string, ExhaustedRoute> }

const UNIT = "days?|hours?|minutes?|mins?|seconds?|secs?|d|h|m|s"
const RESET_PHRASE = new RegExp(`(?:resets?|try again|retry[\\s_-]?after)\\s*(?:in|after|:)?\\s*(?:about\\s+)?((?:\\d+\\s*(?:${UNIT})\\s*){1,6})`, "i")
const PART = new RegExp(`(\\d+)\\s*(${UNIT})\\b`, "gi")
const RETRY_FIELD = new RegExp(`retry[\\s_-]?after[\\s_-]?s?\\s*[:=]\\s*(\\d+)(?:\\s*(${UNIT}))?`, "i")
const UNIT_MS: Record<string, number> = {
  d: 86_400_000, day: 86_400_000, days: 86_400_000,
  h: 3_600_000, hour: 3_600_000, hours: 3_600_000,
  m: 60_000, min: 60_000, mins: 60_000, minute: 60_000, minutes: 60_000,
  s: 1000, sec: 1000, secs: 1000, second: 1000, seconds: 1000,
}

export function routeKey(route: RouteRef): string {
  return route.executor === "pi" ? `pi:${route.providerID}/${route.id}` : `${route.executor}:${route.model}`
}

/** A provider-stated reset delay, or null when the error gives none. */
export function resetDurationMs(error: unknown): number | null {
  const text = typeof error === "string" ? error : JSON.stringify(error ?? "")
  const field = RETRY_FIELD.exec(text)
  let total = 0, parts = 0
  if (field) {
    const unitMs = UNIT_MS[(field[2] ?? "s").toLowerCase()]
    if (unitMs && Number(field[1]) > 0) { total = Number(field[1]) * unitMs; parts++ }
  }
  if (!parts) {
    const phrase = RESET_PHRASE.exec(text)
    if (phrase) {
      for (const match of phrase[1].matchAll(PART)) {
        const unit = UNIT_MS[match[2].toLowerCase()]
        if (unit) { total += Number(match[1]) * unit; parts++ }
      }
    }
  }
  if (!parts) return null
  return Math.min(MAX_EXHAUSTION_MS, Math.max(1000, total))
}

export function exhaustionUntil(error: unknown, now: number): number {
  return now + (resetDurationMs(error) ?? DEFAULT_EXHAUSTION_MS)
}

function errorText(error: unknown): string {
  return typeof error === "string" ? error : JSON.stringify(error ?? "")
}

function lockHolderAlive(lock: string): boolean {
  let pid: number
  try { pid = Number(readFileSync(join(lock, "pid"), "utf8").trim()) }
  catch { return false }
  if (!Number.isSafeInteger(pid) || pid <= 0) return false
  try { process.kill(pid, 0); return true }
  catch (error) { return (error as NodeJS.ErrnoException).code !== "ESRCH" }
}

async function withLock<T>(lock: string, work: () => T): Promise<T> {
  const deadline = Date.now() + 2000
  for (;;) {
    try {
      mkdirSync(lock, { mode: 0o700 })
      try { writeFileSync(join(lock, "pid"), String(process.pid), { mode: 0o600 }) }
      catch (error) { rmSync(lock, { recursive: true, force: true }); throw error }
      break
    } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "EEXIST")) throw error
      if (!lockHolderAlive(lock)) { rmSync(lock, { recursive: true, force: true }); continue }
      if (Date.now() >= deadline) throw new Error("Provider exhaustion store is locked; inspect and retry safely")
      await new Promise(resolve => setTimeout(resolve, 10))
    }
  }
  try { return work() } finally { rmSync(lock, { recursive: true, force: true }) }
}

export class ExhaustionStore {
  private readonly file: string
  private readonly lock: string
  private readonly clock: () => number
  constructor(dir: string, clock: () => number = Date.now) {
    this.file = join(dir, "exhaustion.json")
    this.lock = join(dir, "exhaustion.lock")
    this.clock = clock
  }

  private read(): StoreFile {
    let raw: string
    try { raw = readFileSync(this.file, "utf8") }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return { schema_version: 1, routes: {} }
      throw error
    }
    const value: unknown = JSON.parse(raw)
    if (!isRecord(value) || value.schema_version !== 1 || !isRecord(value.routes))
      throw new Error("Invalid provider exhaustion store " + this.file + "; remove it to reset")
    const routes: Record<string, ExhaustedRoute> = {}
    for (const [key, entry] of Object.entries(value.routes)) {
      if (!isRecord(entry) || typeof entry.until !== "number" || !Number.isFinite(entry.until) ||
          typeof entry.reason !== "string" || typeof entry.recorded_at !== "string")
        throw new Error("Invalid provider exhaustion entry " + key + " in " + this.file)
      routes[key] = { until: entry.until, reason: entry.reason, recorded_at: entry.recorded_at }
    }
    return { schema_version: 1, routes }
  }

  private write(data: StoreFile): void {
    const tmp = this.file + "." + randomUUID() + ".tmp"
    try {
      writeFileSync(tmp, JSON.stringify(data), { mode: 0o600 })
      renameSync(tmp, this.file)
    } finally {
      rmSync(tmp, { force: true })
    }
  }

  active(key: string): ExhaustedRoute | null {
    const entry = this.read().routes[key]
    return entry && entry.until > this.clock() ? entry : null
  }

  /** All still-active entries, for admission notices; expired entries are ignored, not silently rewritten. */
  activeRoutes(): Array<{ key: string; route: ExhaustedRoute }> {
    const now = this.clock()
    return Object.entries(this.read().routes).filter(([, route]) => route.until > now)
      .map(([key, route]) => ({ key, route }))
  }

  async record(route: RouteRef, error: unknown): Promise<ExhaustedRoute> {
    return withLock(this.lock, () => {
      const data = this.read(), now = this.clock(), key = routeKey(route)
      const existing = data.routes[key]
      if (existing && existing.until > now) return existing
      const entry: ExhaustedRoute = {
        until: exhaustionUntil(error, now), reason: errorText(error).slice(0, 500),
        recorded_at: new Date(now).toISOString(),
      }
      data.routes[key] = entry
      this.write(data)
      return entry
    })
  }
}
