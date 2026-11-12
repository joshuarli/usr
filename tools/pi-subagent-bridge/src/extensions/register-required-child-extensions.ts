import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { registerRequiredChildExtensions } from "pi-subagents/required-child-extensions"

export default function registerRequiredChildExtensionsExtension(pi: ExtensionAPI): void {
  const payload = process.env.USR_REQUIRED_CHILD_EXTENSIONS_JSON
  if (!payload) return
  const parsed = JSON.parse(payload) as { sessionId?: string; extensions?: Array<{ id: string; path: string }> }
  if (typeof parsed.sessionId !== "string" || !Array.isArray(parsed.extensions) || parsed.extensions.length === 0)
    throw new Error("USR_REQUIRED_CHILD_EXTENSIONS_JSON must carry a sessionId and nonempty extensions")
  const registration = registerRequiredChildExtensions({
    sessionId: parsed.sessionId,
    extensions: parsed.extensions.map((entry) => ({ id: entry.id, path: entry.path })),
    requireForAllRunners: true,
  })
  pi.on("session_shutdown", () => registration.dispose())
}
