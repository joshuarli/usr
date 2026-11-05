import test from "node:test"
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"

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
  assert.deepEqual(replies.find((r) => r.id === 2)?.result?.tools?.map((t) => t.name), [
    "worker_model_check", "worker_start", "worker_status", "worker_resume", "worker_cancel",
  ])
  assert.equal(replies.find((r) => r.id === 3)?.error?.code, -32602)
})
