import test from "node:test"
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { homedir, tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { pathToFileURL } from "node:url"
import { existsSync, mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs"

const live = process.env.USR_PI_MUSE_SMOKE === "1"
const require = createRequire(import.meta.url)

test("one real Muse turn runs through the pi MCP server",
  { skip: !live && "set USR_PI_MUSE_SMOKE=1 (spends Muse subscription prompts)", timeout: 300000 },
  async () => {
    const pkgDir = dirname(require.resolve("pi-muse-subscription/package.json"))
    const source = (base: string) => {
      for (const extension of [".ts", ".js"]) {
        const candidate = join(pkgDir, "src", base + extension)
        if (existsSync(candidate)) return pathToFileURL(candidate).href
      }
      throw new Error(`pinned Muse adapter has no src/${base} module`)
    }
    const piAiCandidates = [
      join(pkgDir, "node_modules/@earendil-works/pi-ai/dist/index.js"),
      join(pkgDir, "../@earendil-works/pi-ai/dist/index.js"),
    ]
    const piAiPath = piAiCandidates.find((candidate) => existsSync(candidate))
    assert.ok(piAiPath, "pi-ai must be resolvable from the pinned Muse adapter")
    const piAi = pathToFileURL(piAiPath).href
    const [{ normalizeContext }, { McpBridge }, { museConfigDir, savedContributorMode },
           { AnchorRegistry }, { listSkillsOff }, { MuseHost }, { museModels },
           { API, MuseSdkProvider }] = await Promise.all([
      import(piAi), import(source("bridge")), import(source("config")),
      import(source("anchors")), import(source("home")), import(source("host")),
      import(source("models")), import(source("provider")),
    ])

    const root = realpathSync(mkdtempSync(join(tmpdir(), "usr-muse-smoke-")))
    const cwd = join(root, "ws")
    mkdirSync(cwd)
    writeFileSync(join(cwd, "note.txt"), "The magic word is pelican.\n")
    const baseDir = join(root, "agent")
    const userConfigDir = museConfigDir(process.env, homedir())
    const museBin = process.env.PI_MUSE_SDK_MUSE_PATH ?? "muse"
    const bridge = new McpBridge()
    const hostEnv = {
      museBin,
      contributorMode: savedContributorMode(userConfigDir) ?? "off",
      bridge,
      baseDir,
      userConfigDir,
      skillsOff: () => listSkillsOff(museBin, baseDir, process.env),
      env: process.env,
    }
    const model = {
      ...museModels()[0],
      id: process.env.PI_MUSE_SDK_MODEL ?? "muse-spark-1.3",
      api: API,
      provider: "muse-sdk",
      baseUrl: "",
    }
    const tools = [{ name: "read", description: "Read a text file and return its contents",
      parameters: { type: "object", properties: { path: { type: "string" } }, required: ["path"], additionalProperties: false } }]
    const userMessage = {
      role: "user",
      content: [{ type: "text", text: "Read note.txt with the read tool and tell me the magic word. One word." }],
      timestamp: Date.now(),
    }
    const messages: unknown[] = [userMessage]
    const systemPrompt = "You are a terse assistant in a test harness. Use tools when asked to read files."
    try {
      const provider = new MuseSdkProvider({
        registry: new AnchorRegistry(join(root, "anchors.jsonl")),
        openSession: (spec: never) => MuseHost.open(spec, hostEnv as never),
        cwd: () => cwd,
      })
      const result = await provider.streamSimple(
        model as never,
        normalizeContext({ systemPrompt, tools, messages: messages as never }),
        { reasoning: "low" } as never,
      ).result() as never as {
        stopReason: string; errorMessage?: string
        content: Array<{ type: string; name?: string; id?: string; arguments?: Record<string, unknown>; text?: string }>
      }
      assert.notEqual(result.stopReason, "error", result.errorMessage ?? "muse turn errored")
      const toolCall = result.content.find((part) => part.type === "toolCall")
      assert.equal(toolCall?.name, "read", "the Muse turn must call mcp__pi__read")
      const target = typeof toolCall.arguments?.path === "string" ? toolCall.arguments.path : "note.txt"
      messages.push(result as never)
      messages.push({
        role: "toolResult", toolCallId: toolCall.id, toolName: "read",
        content: [{ type: "text", text: "The magic word is pelican." }],
        isError: false, timestamp: Date.now(),
      } as never)
      const second = await provider.streamSimple(
        model as never,
        normalizeContext({ systemPrompt, tools, messages: messages as never }),
        { reasoning: "low" } as never,
      ).result() as never as { stopReason: string; errorMessage?: string; content: Array<{ type: string; text?: string }> }
      assert.notEqual(second.stopReason, "error", second.errorMessage ?? "muse follow-up turn errored")
      const answer = second.content.map((part) => part.text ?? "").join("")
      assert.match(answer.toLowerCase(), /pelican/, "the Muse turn must answer after the MCP tool round trip")
      provider.shutdown()
    } finally {
      bridge.close()
      rmSync(root, { recursive: true, force: true })
    }
  },
)
