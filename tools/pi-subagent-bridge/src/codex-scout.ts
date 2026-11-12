import { execFileSync } from "node:child_process"
import { closeSync, constants, fstatSync, openSync, readSync } from "node:fs"
import { createInterface } from "node:readline"

const tools = [
  { name: "read_file", annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false }, description: "Read up to 128 KiB from a regular file. Paths can be relative to the worktree or absolute.", inputSchema: { type: "object", properties: { path: { type: "string" }, offset: { type: "integer", minimum: 0 } }, required: ["path"], additionalProperties: false } },
  { name: "search_files", annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false }, description: "Search file contents with a ripgrep regular expression. Results include file names and line numbers.", inputSchema: { type: "object", properties: { pattern: { type: "string" }, path: { type: "string" } }, required: ["pattern"], additionalProperties: false } },
  { name: "list_files", annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false }, description: "List files under a path using ripgrep's ignore rules.", inputSchema: { type: "object", properties: { path: { type: "string" } }, additionalProperties: false } },
]
function read(path: string, offset: number): string {
  if (!Number.isSafeInteger(offset) || offset < 0) throw new Error("Invalid offset")
  const fd = openSync(path, constants.O_RDONLY | constants.O_NONBLOCK)
  try {
    if (!fstatSync(fd).isFile()) throw new Error("Not a regular file")
    const bytes = Buffer.alloc(128 * 1024), count = readSync(fd, bytes, 0, bytes.length, offset)
    return bytes.subarray(0, count).toString("utf8")
  } finally { closeSync(fd) }
}
function rg(args: string[]): string {
  try { return execFileSync("rg", args, { encoding: "utf8", timeout: 10000, maxBuffer: 1024 * 1024 }) }
  catch (error) {
    if (typeof error === "object" && error !== null && "status" in error && error.status === 1) return ""
    throw error
  }
}
function call(name: unknown, value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid arguments")
  const args = value as Record<string, unknown>
  const path = args.path === undefined ? "." : args.path
  if (typeof path !== "string" || !path || path.includes("\0")) throw new Error("Invalid path")
  if (name === "read_file") return read(path, args.offset === undefined ? 0 : Number(args.offset))
  if (name === "list_files") return rg(["--files", "--", path])
  if (name === "search_files" && typeof args.pattern === "string" && args.pattern.length <= 2000)
    return rg(["--line-number", "--no-heading", "--color", "never", "-e", args.pattern, "--", path])
  throw new Error("Invalid tool or arguments")
}
const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })
lines.on("line", (line) => {
  let request: { id?: unknown; method?: string; params?: { name?: unknown; arguments?: unknown; protocolVersion?: string } }
  try { request = JSON.parse(line) } catch { return }
  if (request.id === undefined) return
  let result: unknown
  if (request.method === "initialize") result = { protocolVersion: request.params?.protocolVersion ?? "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "bridge-scout", version: "1" } }
  else if (request.method === "tools/list") result = { tools }
  else if (request.method === "tools/call") {
    try { result = { content: [{ type: "text", text: call(request.params?.name, request.params?.arguments ?? {}) }] } }
    catch (error) { result = { isError: true, content: [{ type: "text", text: String(error) }] } }
  } else if (request.method === "ping") result = {}
  else { process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: request.id, error: { code: -32601, message: "Method not found" } }) + "\n"); return }
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: request.id, result }) + "\n")
})
