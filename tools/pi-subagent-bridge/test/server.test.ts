import test from "node:test"
import assert from "node:assert/strict"
import { spawn, spawnSync } from "node:child_process"
import { copyFileSync, mkdirSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { TIERS } from "../src/tier-policy.ts"
import { SCOPE_SCHEMA } from "../src/scope.ts"

const server = fileURLToPath(new URL("../src/server.ts", import.meta.url))

test("stdio MCP handshake, tool discovery and malformed tool rejection need no OpenCode installation", async () => {
  const child = spawn(process.execPath, ["--experimental-strip-types", server], { stdio: ["pipe", "pipe", "pipe"] })
  const requests = [
    { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "1" } } },
    { jsonrpc: "2.0", method: "notifications/initialized" },
    { jsonrpc: "2.0", id: 2, method: "tools/list" },
    { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "arbitrary_shell", arguments: {} } },
  ]
  child.stdin.end(requests.map((request) => JSON.stringify(request)).join("\n") + "\n")
  let output = ""
  for await (const chunk of child.stdout) output += chunk.toString()
  const code = await new Promise<number | null>((resolve, reject) => {
    child.on("error", reject)
    child.on("close", resolve)
  })
  assert.equal(code, 0)
  const replies = output.trim().split("\n").map((line: string) => JSON.parse(line))
  assert.equal(replies.length, 3)
  assert.equal(replies.find((r) => r.id === 1)?.result?.protocolVersion, "2025-06-18")
  assert.deepEqual(replies.find((r) => r.id === 2)?.result?.tools?.map((t: { name: string }) => t.name), [
    "worker_model_check", "worker_start", "worker_status", "worker_resume", "worker_steer", "worker_cancel",
  ])
  const steer = replies.find((r) => r.id === 2)?.result?.tools
    ?.find((t: { name: string }) => t.name === "worker_steer")
  assert.equal(steer?.inputSchema?.type, "object")
  assert.deepEqual(steer?.inputSchema?.required, ["cwd", "session_id", "note"])
  assert.equal(replies.find((r) => r.id === 3)?.error?.code, -32602)
})

test("MCP discovery shares policy schemas and rejects malformed scopes before loading providers", () => {
  const root = mkdtempSync(join(tmpdir(), "usr-mcp-policy-"))
  try {
    const source = join(root, "src")
    mkdirSync(source)
    for (const file of ["server.ts", "commands.ts", "policy.ts", "tier-policy.ts", "scope.ts"]) {
      copyFileSync(fileURLToPath(new URL("../src/" + file, import.meta.url)), join(source, file))
    }
    const scope = { base_revision: "a".repeat(40), writable_paths: ["src/"],
      acceptance_proof: "Run a focused check", attempt_limit: 1, stop_on: "Scope expansion", extra: true }
    const requests = [
      { jsonrpc: "2.0", id: 1, method: "tools/list" },
      { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "worker_start",
        arguments: { cwd: "/no-worktree", title: "test", tier: "worker", scope, brief: "Work" } } },
      { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "worker_model_check",
        arguments: { cwd: "/no-worktree", tier: "god" } } },
      { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "worker_model_check",
        arguments: { cwd: "/no-worktree", tier: "worker", extra: true } } },
    ]
    const child = spawnSync(process.execPath, ["--experimental-strip-types", join(source, "server.ts")], {
      cwd: root, env: { ...process.env, PATH: "", USR_OPENCODE_WORKER_TEST: "" },
      input: requests.map(request => JSON.stringify(request)).join("\n") + "\n",
      encoding: "utf8", timeout: 10000,
    })
    assert.equal(child.status, 0, child.stderr)
    const replies = child.stdout.trim().split("\n").map(line => JSON.parse(line))
    const start = replies.find(reply => reply.id === 1)?.result?.tools.find((tool: { name: string }) => tool.name === "worker_start")
    assert.deepEqual(start.inputSchema.properties.tier.enum, TIERS)
    assert.deepEqual(start.inputSchema.properties.scope, SCOPE_SCHEMA)
    for (const [id, message] of [[2, /Unknown scope field: extra/], [3, /Unknown Pi tier/], [4, /Unknown tool argument: extra/]] as const) {
      const result = replies.find(reply => reply.id === id)?.result
      assert.equal(result?.isError, true)
      assert.match(result.content[0].text, message)
    }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
