import { readFileSync, renameSync, writeFileSync } from "node:fs"
import {
  createAgentSession, createExtensionRuntime, ModelRuntime, SessionManager, SettingsManager,
  type ResourceLoader,
} from "@earendil-works/pi-coding-agent"

type Job = {
  cwd: string
  model: { providerID: string; id: string; variant?: string }
  readOnly: boolean
  prompt: string
  sessionDir: string
  priorSessionFile?: string
  resultPath: string
}
type Result = {
  state: "succeeded" | "failed" | "cancelled"
  error: string | null
  text: string | null
  sessionFile: string | null
  usage: unknown
}

function persist(path: string, result: Result): void {
  const temporary = path + "." + process.pid + ".tmp"
  writeFileSync(temporary, JSON.stringify(result), { mode: 0o600, flag: "wx" })
  renameSync(temporary, path)
}

function resourceLoader(): ResourceLoader {
  return {
    getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
    getSkills: () => ({ skills: [], diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () =>
      "You are a single-purpose coding subagent. Follow the assigned scope exactly. " +
      "Never delegate, create or switch branches, commit, push, or extend the write boundary. " +
      "Stop and report any blocker. Return verifiable evidence, not unsupported claims.",
    getSystemPromptSource: () => undefined,
    getAppendSystemPrompt: () => [],
    getAppendSystemPromptSources: () => [],
    extendResources: () => {},
    reload: async () => {},
  }
}

async function run(job: Job): Promise<Result> {
  const runtime = await ModelRuntime.create()
  const model = runtime.getModel(job.model.providerID, job.model.id)
  if (!model || !runtime.hasConfiguredAuth(job.model.providerID))
    throw new Error("Pinned Pi provider/model is unavailable or has no configured credentials")
  const thinking = job.model.variant
  if (thinking !== "medium" && thinking !== "high" && thinking !== "max")
    throw new Error("Unsupported Pi thinking tier")
  const manager = job.priorSessionFile
    ? SessionManager.open(job.priorSessionFile, job.sessionDir, job.cwd)
    : SessionManager.create(job.cwd, job.sessionDir)
  const tools = job.readOnly
    ? ["read", "grep", "find", "ls"]
    : ["read", "bash", "edit", "write", "grep", "find", "ls"]
  const { session } = await createAgentSession({
    cwd: job.cwd, modelRuntime: runtime, model, thinkingLevel: thinking,
    sessionManager: manager,
    settingsManager: SettingsManager.inMemory({
      compaction: { enabled: false }, retry: { enabled: false },
    }),
    resourceLoader: resourceLoader(),
    tools,
  })
  try {
    if (session.model?.provider !== job.model.providerID || session.model.id !== job.model.id ||
        session.thinkingLevel !== thinking ||
        !session.getAvailableThinkingLevels().includes(thinking))
      throw new Error("Pi silently replaced or clamped the pinned model/effort")
    const active = session.getActiveToolNames().slice().sort()
    if (active.join("\0") !== tools.slice().sort().join("\0"))
      throw new Error("Pi effective tool list does not match the approved allowlist")
    await session.prompt(job.prompt)
    const last = session.messages.slice().reverse().find((m) => m.role === "assistant")
    const text = session.getLastAssistantText() ?? null
    const sessionFile = session.sessionFile ?? null
    if (!last || last.role !== "assistant")
      return { state: "failed", text, sessionFile, error: "Pi returned no assistant message", usage: null }
    const usage = last.usage ?? null
    if (last.stopReason === "aborted")
      return { state: "cancelled", text, sessionFile, error: "Pi aborted", usage }
    if (last.stopReason === "error")
      return { state: "failed", text, sessionFile, error: last.errorMessage ?? "Pi provider error", usage }
    if (last.stopReason !== "stop")
      return { state: "failed", text, sessionFile, error: "Pi stopped with " + last.stopReason, usage }
    if (!text)
      return { state: "failed", text, sessionFile, error: "Pi finished without text proof", usage }
    return { state: "succeeded", text, sessionFile, error: null, usage }
  } finally {
    session.dispose()
  }
}

async function main(): Promise<void> {
  if (process.argv.length !== 3) throw new Error("usage: sdk-worker.ts JOB_JSON")
  const job = JSON.parse(readFileSync(process.argv[2], "utf8")) as Job
  if (!job || typeof job.cwd !== "string" || typeof job.prompt !== "string" ||
      typeof job.resultPath !== "string" || typeof job.sessionDir !== "string")
    throw new Error("Malformed SDK job")
  try {
    persist(job.resultPath, await run(job))
  } catch (error) {
    persist(job.resultPath, {
      state: "failed", text: null, sessionFile: job.priorSessionFile ?? null,
      error: error instanceof Error ? error.message : String(error), usage: null,
    })
    process.exitCode = 1
  }
}

void main().catch((error) => {
  process.stderr.write(String(error) + "\n")
  process.exitCode = 1
})
