import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readlinkSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { delimiter, join } from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"

const source = fileURLToPath(new URL("../dev-install.sh", import.meta.url))
const packageJson = fileURLToPath(new URL("../package.json", import.meta.url))
const scratch = fileURLToPath(new URL("../../../.work/tmp/", import.meta.url))

function fixture() {
  mkdirSync(scratch, { recursive: true })
  const root = mkdtempSync(join(scratch, "pi-bridge-dev-install-"))
  const checkout = join(root, "checkout")
  const home = join(root, "home")
  const dataHome = join(root, "xdg-data")
  const runtime = join(dataHome, "pi-runtime/current/node_modules")
  const bin = join(root, "bin")
  mkdirSync(checkout, { recursive: true })
  mkdirSync(home, { recursive: true })
  mkdirSync(bin, { recursive: true })
  writeFileSync(join(checkout, "dev-install.sh"), readFileSync(source, "utf8"), { mode: 0o700 })
  writeFileSync(join(checkout, "package.json"), readFileSync(packageJson, "utf8"))
  writeFileSync(join(bin, "npm"), "#!/bin/sh\nprintf called > \"$NPM_CALLED\"\n", { mode: 0o700 })
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    HOME: home,
    XDG_DATA_HOME: dataHome,
    NPM_CALLED: join(root, "npm-called"),
    PATH: `${bin}${delimiter}${process.env.PATH ?? ""}`,
  }
  return { root, checkout, home, dataHome, runtime, env }
}

function run(checkout: string, env: NodeJS.ProcessEnv) {
  // POSIX /bin/sh, not whichever sh is first on PATH: a user shell shim may rewrite XDG variables.
  return spawnSync("/bin/sh", [join(checkout, "dev-install.sh")], { cwd: checkout, env, encoding: "utf8" })
}

test("creates a runtime symlink from XDG_DATA_HOME when node_modules is absent", () => {
  const f = fixture()
  try {
    mkdirSync(f.runtime, { recursive: true })
    const result = run(f.checkout, f.env)
    assert.equal(result.status, 0, result.stderr)
    assert.equal(readlinkSync(join(f.checkout, "node_modules")), f.runtime)
    assert.equal(existsSync(f.env.NPM_CALLED!), true)
  } finally { rmSync(f.root, { recursive: true, force: true }) }
})

test("uses HOME's local share when XDG_DATA_HOME is unset", () => {
  const f = fixture()
  try {
    const runtime = join(f.home, ".local/share/pi-runtime/current/node_modules")
    mkdirSync(runtime, { recursive: true })
    const env = { ...f.env }
    delete env.XDG_DATA_HOME
    const result = run(f.checkout, env)
    assert.equal(result.status, 0, result.stderr)
    assert.equal(readlinkSync(join(f.checkout, "node_modules")), runtime)
  } finally { rmSync(f.root, { recursive: true, force: true }) }
})

test("keeps an existing correct runtime symlink", () => {
  const f = fixture()
  try {
    mkdirSync(f.runtime, { recursive: true })
    symlinkSync(f.runtime, join(f.checkout, "node_modules"), "dir")
    const before = readlinkSync(join(f.checkout, "node_modules"))
    const result = run(f.checkout, f.env)
    assert.equal(result.status, 0, result.stderr)
    assert.equal(readlinkSync(join(f.checkout, "node_modules")), before)
    assert.equal(lstatSync(join(f.checkout, "node_modules")).isSymbolicLink(), true)
  } finally { rmSync(f.root, { recursive: true, force: true }) }
})

test("refuses a real node_modules directory", () => {
  const f = fixture()
  try {
    mkdirSync(join(f.checkout, "node_modules"))
    const result = run(f.checkout, f.env)
    assert.equal(result.status, 1)
    assert.match(result.stderr, /is not the usual runtime symlink/)
    assert.equal(existsSync(f.env.NPM_CALLED!), false)
  } finally { rmSync(f.root, { recursive: true, force: true }) }
})

test("reports how to install a missing runtime", () => {
  const f = fixture()
  try {
    const result = run(f.checkout, f.env)
    assert.equal(result.status, 1)
    assert.match(result.stderr, /run sh sync first/)
    assert.equal(existsSync(join(f.checkout, "node_modules")), false)
    assert.equal(existsSync(f.env.NPM_CALLED!), false)
  } finally { rmSync(f.root, { recursive: true, force: true }) }
})
