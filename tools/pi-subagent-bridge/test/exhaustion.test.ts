import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  DEFAULT_EXHAUSTION_MS, ExhaustionStore, resetDurationMs, routeKey,
} from "../src/exhaustion.ts"

const NOW = Date.parse("2026-11-24T00:00:00.000Z")
const DAY = 86_400_000

test("a stated provider reset becomes an absolute deadline, and no reset gets a bounded backoff", async () => {
  assert.equal(resetDurationMs("opencode API error (429): GoUsageLimitError - monthly, resets in 5d"), 5 * DAY)
  assert.equal(resetDurationMs("quota exhausted, resets in about 6 days"), 6 * DAY)
  assert.equal(resetDurationMs("429 GoUsageLimitError - monthly, resets in 14d 3h"), 14 * DAY + 3 * 3_600_000)
  assert.equal(resetDurationMs("rate limited; retry_after_s: 45"), 45_000)
  assert.equal(resetDurationMs("insufficient credits"), null)

  const dir = mkdtempSync(join(tmpdir(), "exhaustion-"))
  try {
    const go = { executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" }
    const command = { executor: "command-code" as const, model: "deepseek/deepseek-v4.1-flash" }
    const now = () => NOW
    const store = new ExhaustionStore(dir, now)
    await store.record(command, "Insufficient credits")
    await store.record(go, "429 GoUsageLimitError - monthly, resets in 5d")

    assert.equal(store.active(routeKey(command))?.until, NOW + DEFAULT_EXHAUSTION_MS)
    assert.equal(store.active(routeKey(go))?.until, NOW + 5 * DAY)
    assert.equal(store.activeRoutes().length, 2)

    const later = new ExhaustionStore(dir, () => NOW + DEFAULT_EXHAUSTION_MS + 1)
    assert.equal(later.active(routeKey(command)), null)
    assert.ok(later.active(routeKey(go)))
    const afterReset = new ExhaustionStore(dir, () => NOW + 5 * DAY + 1)
    assert.equal(afterReset.activeRoutes().length, 0)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("repeated status observations cannot extend a provider's stated reset", async () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-repeat-"))
  try {
    const store = new ExhaustionStore(dir, () => NOW)
    const route = { executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" }
    await store.record(route, "429 resets in 5d")
    await store.record(route, "429 resets in 10d")
    assert.equal(store.active(routeKey(route))?.until, NOW + 5 * DAY)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("a stale lock left by a dead process does not wedge the store", async () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-lock-"))
  try {
    const lock = join(dir, "exhaustion.lock")
    mkdirSync(lock)
    writeFileSync(join(lock, "pid"), "2147483647")
    const store = new ExhaustionStore(dir)
    await store.record({ executor: "codex", model: "gpt-6.1-terra" }, "429 quota, resets in 1h")
    assert.ok(store.active(routeKey({ executor: "codex", model: "gpt-6.1-terra" })))
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("a malformed or unknown-version exhaustion store fails loudly", () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-bad-"))
  try {
    const store = new ExhaustionStore(dir)
    writeFileSync(join(dir, "exhaustion.json"), JSON.stringify({ schema_version: 2, routes: {} }))
    assert.throws(() => store.active(routeKey({ executor: "codex", model: "gpt-6.1-terra" })), /Invalid provider exhaustion store/)
    writeFileSync(join(dir, "exhaustion.json"), "{not json")
    assert.throws(() => store.active(routeKey({ executor: "codex", model: "gpt-6.1-terra" })))
  } finally { rmSync(dir, { recursive: true, force: true }) }
})
