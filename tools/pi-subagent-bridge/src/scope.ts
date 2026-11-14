import type { Tier } from "./tier-policy.ts"

const ATTEMPT_LIMITS = [1, 2] as const
type AttemptLimit = (typeof ATTEMPT_LIMITS)[number]
const PATH_LIMIT = 512

/** The public scope contract and its decoder share the same limits and field set. */
export const SCOPE_SCHEMA = {
  type: "object",
  properties: {
    base_revision: { type: "string", pattern: "^[a-f0-9]{40}$" },
    writable_paths: { type: "array", maxItems: 20, uniqueItems: true,
      items: { type: "string", minLength: 1, maxLength: PATH_LIMIT },
      description: "Exact files or directory prefixes ending in /; empty only for scout" },
    acceptance_proof: { type: "string", minLength: 1, maxLength: 2000, pattern: "\\S" },
    attempt_limit: { type: "integer", enum: ATTEMPT_LIMITS },
    stop_on: { type: "string", minLength: 1, maxLength: 2000, pattern: "\\S" },
  },
  required: ["base_revision", "writable_paths", "acceptance_proof", "attempt_limit", "stop_on"],
  additionalProperties: false,
} as const

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}
export function requiredText(value: unknown, name: string, max = 2000): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new Error("Invalid " + name)
  return value
}
function isAttemptLimit(value: unknown): value is AttemptLimit {
  return ATTEMPT_LIMITS.some(limit => value === limit)
}
function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string")
}

export function parseScope(value: unknown, tier: Tier, expectedRevision?: string) {
  if (!isRecord(value)) throw new Error("scope must be an object")
  const fields = SCOPE_SCHEMA.properties
  for (const key of SCOPE_SCHEMA.required) {
    if (!Object.hasOwn(value, key)) throw new Error("Missing scope field: " + key)
  }
  for (const key of Object.keys(value)) {
    if (!Object.hasOwn(fields, key)) throw new Error("Unknown scope field: " + key)
  }
  const base_revision = requiredText(value.base_revision, "base_revision", 40)
  if (!new RegExp(fields.base_revision.pattern).test(base_revision)) throw new Error("base_revision must be 40 hex characters")
  if (expectedRevision !== undefined && base_revision !== expectedRevision) throw new Error("base_revision differs from HEAD")
  if (!isStringList(value.writable_paths) || value.writable_paths.length > fields.writable_paths.maxItems)
    throw new Error("writable_paths must name at most " + fields.writable_paths.maxItems + " exact files or directories")
  const writable_paths = [...value.writable_paths]
  if (tier === "scout" ? writable_paths.length > 0 : writable_paths.length === 0)
    throw new Error("scouts are read-only; writers need specific writable_paths")
  for (const path of writable_paths) {
    const segments = (path.endsWith("/") ? path.slice(0, -1) : path).split("/")
    if (path.startsWith("/") || path.length > fields.writable_paths.items.maxLength || path.includes("\\") || /[*?[\]\u0000]/.test(path) ||
        segments.some(segment => !segment || segment === "." || segment === ".." || segment === ".git" || segment === ".work"))
      throw new Error("Invalid writable path: " + path)
  }
  if (new Set(writable_paths).size !== writable_paths.length) throw new Error("Duplicate writable_paths")
  const acceptance_proof = requiredText(value.acceptance_proof, "acceptance_proof", fields.acceptance_proof.maxLength)
  const stop_on = requiredText(value.stop_on, "stop_on", fields.stop_on.maxLength)
  if (!isAttemptLimit(value.attempt_limit)) throw new Error("attempt_limit must be " + ATTEMPT_LIMITS.join(" or "))
  return { base_revision, writable_paths, acceptance_proof, attempt_limit: value.attempt_limit, stop_on }
}
export type Scope = ReturnType<typeof parseScope>
