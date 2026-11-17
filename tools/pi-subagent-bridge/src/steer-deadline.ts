import { AsyncLocalStorage } from "node:async_hooks"

const deadline = new AsyncLocalStorage<number>()
export const STEER_DEADLINE_MS = 12_000

export class SteerDeadlineError extends Error {
  constructor() { super("Steer deadline reached; inspect the session before retrying") }
}

export function steerDeadline<T>(work: () => T): T {
  return deadline.run(Date.now() + STEER_DEADLINE_MS, work)
}

export function steerCleanup<T>(work: () => T): T {
  return deadline.run(Date.now() + 2000, work)
}

export function deadlineTimeout(limit: number): number {
  const until = deadline.getStore()
  if (until === undefined) return limit
  const remaining = until - Date.now()
  if (remaining <= 0) throw new SteerDeadlineError()
  return Math.max(1, Math.min(limit, remaining))
}

export async function beforeDeadline<T>(operation: Promise<T> | T): Promise<T> {
  const until = deadline.getStore()
  if (until === undefined) return await operation
  const milliseconds = deadlineTimeout(STEER_DEADLINE_MS)
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([Promise.resolve(operation), new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new SteerDeadlineError()), milliseconds)
    })])
  } finally { if (timer) clearTimeout(timer) }
}
