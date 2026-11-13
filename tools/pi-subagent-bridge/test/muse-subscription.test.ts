import test from "node:test"
import assert from "node:assert/strict"
import { copyFileSync, mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { pathToFileURL } from "node:url"

test("Muse resolution follows the pinned package entry for source and compiled runtimes", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "muse-profile-")))
  try {
    for (const extension of ["ts", "js"]) {
      const fixture = join(root, extension)
      const pkg = join(fixture, "node_modules/pi-muse-subscription")
      mkdirSync(join(pkg, "src"), { recursive: true })
      const source = join(fixture, "muse-subscription.ts")
      copyFileSync(new URL("../src/muse-subscription.ts", import.meta.url), source)
      writeFileSync(join(pkg, "package.json"), JSON.stringify({ pi: { extensions: [`./src/index.${extension}`] } }))
      writeFileSync(join(pkg, "src", `index.${extension}`), "export default () => {}\n")
      const { museExtensionPath } = await import(pathToFileURL(source).href)
      assert.equal(museExtensionPath(), join(pkg, "src", `index.${extension}`))
      writeFileSync(join(pkg, "package.json"), JSON.stringify({ pi: { extensions: ["../../other.js"] } }))
      assert.throws(() => museExtensionPath(), /Unsupported Muse extension entry point/)
    }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
