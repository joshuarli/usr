import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  ACCOUNT_EXHAUSTION_MS, DEFAULT_EXHAUSTION_MS, ExhaustionStore, accountKey, resetDurationMs, routeKey,
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
    // A hintless rate-limit or quota error keeps the bounded per-model backoff;
    // credit and billing errors are account-wide for 24 hours instead (tested below).
    await store.record(command, "429 quota exhausted")
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

test("credit and billing errors without a reset hint are recorded for 24 hours, not the 1-hour default", async () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-credit-"))
  try {
    const store = new ExhaustionStore(dir, () => NOW)
    const cases = [
      {
        route: { executor: "command-code" as const, model: "meta/muse-ember" },
        message: "Error: Insufficient credits for Command Code.\nBuy extra usage (pay-as-you-go at API cost, zero markup) or upgrade: https://commandcode.ai/billing",
      },
      { route: { executor: "codex" as const, model: "gpt-6.1-terra" }, message: "credits exhausted" },
      {
        route: { executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" },
        message: "account billing limit reached; add a payment method",
      },
    ]
    for (const { route, message } of cases) {
      const entry = await store.record(route, message)
      assert.equal(entry.until, NOW + ACCOUNT_EXHAUSTION_MS)
      assert.notEqual(entry.until, NOW + DEFAULT_EXHAUSTION_MS)
      assert.equal(store.activeRoute(route)?.until, NOW + ACCOUNT_EXHAUSTION_MS)
      assert.equal(store.active(routeKey(route)), null)
    }
    assert.equal(resetDurationMs("Error: Insufficient credits for Command Code. Buy extra usage"), null)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("credit exhaustion on one Command Code model exhausts every Command Code model through the admission lookup", async () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-account-"))
  try {
    const store = new ExhaustionStore(dir, () => NOW)
    const ember = { executor: "command-code" as const, model: "meta/muse-ember" }
    const deepseek = { executor: "command-code" as const, model: "deepseek/deepseek-v4.1-flash" }
    await store.record(ember, "Error: Insufficient credits for Command Code. Buy extra usage")

    assert.equal(store.activeRoute(ember)?.until, NOW + ACCOUNT_EXHAUSTION_MS)
    assert.equal(store.activeRoute(deepseek)?.until, NOW + ACCOUNT_EXHAUSTION_MS)
    assert.equal(store.activeRoute({ executor: "command-code" as const, model: "tencent/hy4" })?.until, NOW + ACCOUNT_EXHAUSTION_MS)
    // The account key must never block another executor or a Pi provider.
    assert.equal(store.activeRoute({ executor: "codex" as const, model: "gpt-6.1-terra" }), null)
    assert.equal(store.activeRoute({ executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" }), null)
    // The per-model key alone does not report the account exhaustion; the dual-key lookup does.
    assert.equal(store.active(routeKey(deepseek)), null)
    assert.ok(store.active(accountKey(ember)))

    const pi = { executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" }
    await store.record(pi, "credits exhausted")
    assert.equal(store.activeRoute({ executor: "pi" as const, providerID: "opencode-go", id: "muse-spark-1.3-contributor" })?.until, NOW + ACCOUNT_EXHAUSTION_MS)
    assert.equal(store.activeRoute({ executor: "pi" as const, providerID: "devin", id: "swe-2.1" }), null)

    const beforeExpiry = new ExhaustionStore(dir, () => NOW + ACCOUNT_EXHAUSTION_MS - 1)
    assert.ok(beforeExpiry.activeRoute(deepseek))
    const afterExpiry = new ExhaustionStore(dir, () => NOW + ACCOUNT_EXHAUSTION_MS + 1)
    assert.equal(afterExpiry.activeRoute(deepseek), null)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("a rate-limit 429 with a reset hint keeps the hinted duration and stays per model", async () => {
  const dir = mkdtempSync(join(tmpdir(), "exhaustion-ratelimit-"))
  try {
    const store = new ExhaustionStore(dir, () => NOW)
    const ember = { executor: "command-code" as const, model: "meta/muse-ember" }
    const deepseek = { executor: "command-code" as const, model: "deepseek/deepseek-v4.1-flash" }
    await store.record(ember, "429 rate limited; retry_after_s: 45")
    assert.equal(store.activeRoute(ember)?.until, NOW + 45_000)
    assert.equal(store.activeRoute(deepseek), null)
    assert.equal(store.active(accountKey(ember)), null)

    const go = { executor: "pi" as const, providerID: "opencode-go", id: "deepseek-v4.1-flash" }
    await store.record(go, "429 GoUsageLimitError - monthly, resets in 5d")
    assert.equal(store.activeRoute(go)?.until, NOW + 5 * DAY)
    assert.equal(store.activeRoute({ executor: "pi" as const, providerID: "opencode-go", id: "muse-spark-1.3-contributor" }), null)
    // A hintless rate limit keeps the 1-hour default and stays per model.
    const codex = { executor: "codex" as const, model: "gpt-6.1-terra" }
    await store.record(codex, "429 too many requests")
    assert.equal(store.activeRoute(codex)?.until, NOW + DEFAULT_EXHAUSTION_MS)
    assert.equal(store.activeRoute({ executor: "codex" as const, model: "gpt-6-luna" }), null)
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
