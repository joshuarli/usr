export type ProbeVerdict = "ok" | "quota" | "auth" | "rate-limited" | "unknown"

export function classifyProbeResponse(status: number, body: string): ProbeVerdict {
  const text = body.toLowerCase()
  if (status === 401 || status === 403) return "auth"
  if (status === 429) {
    if (/usage limit|quota|insufficient|credit|resets? in|billing|goressagelimiterror/.test(text)) return "quota"
    return "rate-limited"
  }
  if (status >= 200 && status < 300) return "ok"
  return "unknown"
}

export type JobBlock = "quota" | "auth" | "provider-stall"

export function classifyJobBlock(input: {
  state: string
  lastText: string
  elapsedMs: number
  wallMs: number
  stderrTail: string
  probe?: ProbeVerdict | null
}): JobBlock | null {
  if (input.state === "succeeded") return null
  if (input.probe === "quota") return "quota"
  const err = input.stderrTail.toLowerCase()
  if (/usage limit|goressagelimiterror|quota|insufficient|resets? in|credit/.test(err)) return "quota"
  if (input.probe === "auth" || /missingcredentials|missingsessionid|unauthorized|\b401\b|\b403\b/.test(err)) return "auth"
  if (!input.lastText.trim() && input.elapsedMs >= input.wallMs * 0.85) return "provider-stall"
  return null
}

export function scoutFindingOk(answer: string): boolean {
  return /python\/ledger\.py/i.test(answer)
    && /lines?\s*[67]\b|:\s*[67]\b/i.test(answer)
    && /debit/i.test(answer)
}

export function renameEvidenceOk(files: Record<string, string>): string | null {
  for (const [name, text] of Object.entries(files)) {
    if (/balance_after|balanceAfter/.test(text)) return name + " retains the old name"
  }
  for (const name of ["python", "ts", "rust", "python-test", "ts-check"]) {
    if (!/settled_balance/.test(files[name] ?? "")) return name + " lacks settled_balance"
  }
  return null
}

export type PilotVerdict = "passed" | "blocked" | "failed"

export function pilotVerdict(input: {
  tasks: { key: string; state?: string; checks?: boolean; block?: JobBlock | null }[]
  continuation: {
    attempted: boolean
    accepted?: boolean
    identity?: boolean
    checks?: boolean
    block?: JobBlock | null
    nativeSession?: boolean
    reason?: string
  } | null
}): PilotVerdict {
  const required = ["scout", "fix", "multi"]
  const byKey = new Map(input.tasks.map(t => [t.key, t]))
  const ok = (t?: { state?: string; checks?: boolean }) => t?.state === "succeeded" && t.checks === true
  const allTasksOk = required.every(key => ok(byKey.get(key)))
  const c = input.continuation
  const contOk = c?.attempted === true && c.accepted === true && c.identity === true && c.checks === true
  let hardFail = false
  for (const t of input.tasks) {
    if (t.state === "succeeded" && t.checks !== true) hardFail = true
    if (t.state !== undefined && t.state !== "succeeded" && !t.block) hardFail = true
  }
  if (c?.attempted === true && !c.block) {
    if (c.accepted === true && (c.identity !== true || c.checks !== true)) hardFail = true
    if (c.accepted === false && c.nativeSession === true) hardFail = true
  }
  if (allTasksOk && contOk) return "passed"
  return hardFail ? "failed" : "blocked"
}
