import { execFileSync } from "node:child_process"

type ExportedCredential = {
  integrationID?: string
  active?: boolean
  value?: { type?: string; access?: string; refresh?: string; expires?: number }
}

function isUsableAccess(token: string): boolean {
  return typeof token === "string" && token.length > 0 && token.length < 4096
}

/**
 * Best-effort: if OPENCODE_API_KEY is unset, reuse the active OpenCode CLI OAuth
 * credential so the Pi SDK opencode-go provider can authenticate. Never logs or
 * returns the secret. Falls back silently when unavailable or malformed.
 */
export function ensureOpenCodeApiKey(env: NodeJS.ProcessEnv = process.env): void {
  if (typeof env.OPENCODE_API_KEY === "string" && env.OPENCODE_API_KEY.trim()) return
  try {
    const raw = execFileSync("opencode", ["auth", "export"], {
      encoding: "utf8",
      timeout: 10_000,
      maxBuffer: 1_000_000,
      stdio: ["ignore", "pipe", "ignore"],
    })
    const creds = JSON.parse(raw) as unknown
    if (!Array.isArray(creds)) return
    const match = (creds as ExportedCredential[]).find(
      (c) => c?.active && c.integrationID === "opencode" && c.value?.type === "oauth",
    )
    const access = match?.value?.access
    if (isUsableAccess(access as string)) env.OPENCODE_API_KEY = access as string
  } catch {
    // Local convenience only; explicit OPENCODE_API_KEY or Pi auth still required if this fails.
  }
}
