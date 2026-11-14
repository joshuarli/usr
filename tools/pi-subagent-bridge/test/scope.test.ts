import test from "node:test"
import assert from "node:assert/strict"
import { parseScope, SCOPE_SCHEMA } from "../src/scope.ts"

function scope() {
  return { base_revision: "a".repeat(40), writable_paths: ["src/"],
    acceptance_proof: "Run the focused check", attempt_limit: 1, stop_on: "Scope expansion" }
}

test("scope construction rejects unknown fields and absent required fields", () => {
  assert.equal(SCOPE_SCHEMA.additionalProperties, false)
  assert.throws(() => parseScope({ ...scope(), model: "unapproved" }, "worker"), /Unknown scope field: model/)
  for (const field of SCOPE_SCHEMA.required) {
    const missing: Record<string, unknown> = scope()
    delete missing[field]
    assert.throws(() => parseScope(missing, "worker"), field)
  }
  for (const invalid of [null, [], "scope"]) assert.throws(() => parseScope(invalid, "worker"), /scope must be an object/)
})

test("scope construction preserves read-only and write-boundary restrictions", () => {
  assert.throws(() => parseScope(scope(), "scout"), /scouts are read-only/)
  const readOnly = { ...scope(), writable_paths: [] }
  assert.deepEqual(parseScope(readOnly, "scout"), readOnly)
  assert.throws(() => parseScope({ ...readOnly, network: true }, "scout"), /no network/)
  assert.throws(() => parseScope(readOnly, "worker"), /writers need specific writable_paths/)
  for (const path of ["", "/tmp/", "../outside", "src/../outside", ".git/config", ".work/state", "src/*", "src\\file"]) {
    assert.throws(() => parseScope({ ...scope(), writable_paths: [path] }, "worker"), /Invalid writable path/, path)
  }
  assert.throws(() => parseScope({ ...scope(), writable_paths: ["src/", "src/"] }, "worker"), /Duplicate writable_paths/)
  const input = scope(), parsed = parseScope(input, "worker", input.base_revision)
  input.writable_paths.push("unapproved/")
  assert.deepEqual(parsed.writable_paths, ["src/"])
  assert.throws(() => parseScope(scope(), "worker", "b".repeat(40)), /differs from HEAD/)
})

test("scope decoder applies its public field bounds", () => {
  assert.deepEqual(SCOPE_SCHEMA.properties.attempt_limit.enum, [1, 2])
  for (const attempt_limit of [0, 1.5, 3, "1"]) {
    assert.throws(() => parseScope({ ...scope(), attempt_limit }, "worker"), /attempt_limit/)
  }
  assert.throws(() => parseScope({ ...scope(), acceptance_proof: " " }, "worker"), /Invalid acceptance_proof/)
  assert.throws(() => parseScope({ ...scope(), network: "true" }, "worker"), /network must be a boolean/)
  const max = SCOPE_SCHEMA.properties.writable_paths.maxItems
  assert.throws(() => parseScope({ ...scope(), writable_paths: Array.from({ length: max + 1 }, (_, i) => `src/${i}`) }, "worker"), /writable_paths must name at most/)
})
