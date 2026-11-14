/** Coordinator enrollment and transport settings never enter scoped worker processes. */
export function workerEnvironment(source: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const env = { ...source, USR_SCOPED_WORKER: "1" }
  stripIntercomEnvironment(env)
  return env
}

/** Also protect direct SDK worker launches and everything they subsequently spawn. */
export function stripIntercomEnvironment(env: NodeJS.ProcessEnv): void {
  for (const key of Object.keys(env)) {
    if (key.startsWith("AGENT_INTERCOM_") || key.startsWith("PI_INTERCOM_")) delete env[key]
  }
}
