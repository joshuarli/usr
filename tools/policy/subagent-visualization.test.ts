import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { POLICY } from "../pi-subagent-bridge/src/policy.ts"
import { main } from "./subagent-visualization.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const DESTINATION = "docs/subagents.html"

function fixture() {
  mkdirSync(join(ROOT, ".work/tmp"), { recursive: true })
  const root = mkdtempSync(join(ROOT, ".work/tmp", "visualization-"))
  mkdirSync(join(root, "docs"))
  return { root, path: join(root, DESTINATION), close: () => rmSync(root, { recursive: true, force: true }) }
}

test("renders a self-contained HTML visualization with layered lane strength", () => {
  const f = fixture()
  try {
    assert.equal(main([], f.root), 0)
    const html = readFileSync(f.path, "utf8")
    assert.match(html, /^<!doctype html>/)
    assert.match(html, /Generated from tools\/policy\/subagent-visualization\.ts/)
    assert.match(html, /<style>/)
    assert.doesNotMatch(html, /<script|<link|src="https?:/)
    for (const label of ["Bridge primary", "Bridge fallback", "Native", "Pilot / opt-in", "Undefined"]) {
      assert.ok(html.includes(label), `missing lane kind ${label}`)
    }
    assert.match(html, /thinking level/)
    assert.match(html, /Route rank/)
    assert.match(html, /<svg[^>]*role="img"/)
    assert.match(html, /<path class="edge"/)
    assert.match(html, /<foreignObject/)
    for (const tier of POLICY.tiers) {
      for (const route of POLICY.rootRoutes[tier]) {
        const id = route.executor === "pi" ? `${route.providerID}/${route.model}` : route.model
        assert.ok(html.includes(id), `missing route ${id}`)
      }
    }
    const mtime = statSync(f.path).mtimeMs
    assert.equal(main([], f.root), 0)
    assert.equal(statSync(f.path).mtimeMs, mtime)
  } finally { f.close() }
})

test("check mode detects a stale HTML output without repairing it", () => {
  const f = fixture()
  try {
    assert.equal(main([], f.root), 0)
    const original = readFileSync(f.path, "utf8")
    const stale = original.replace("Subagent architecture", "stale title")
    writeFileSync(f.path, stale)
    assert.equal(main(["--check"], f.root), 1)
    assert.equal(readFileSync(f.path, "utf8"), stale)
    assert.equal(main([], f.root), 0)
    assert.equal(main(["--check"], f.root), 0)
  } finally { f.close() }
})
