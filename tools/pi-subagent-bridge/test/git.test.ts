import test from "node:test"
import assert from "node:assert/strict"
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { inspectionGit } from "../src/git.ts"

test("inspection git uses low priority wrappers and falls back when absent", () => {
  const dir = mkdtempSync(join(tmpdir(), "bridge-git-")), log = join(dir, "log")
  const oldPath = process.env.PATH, oldLog = process.env.BRIDGE_TEST_LOG
  try {
    for (const [name, body] of Object.entries({
      git: 'printf "git %s\\n" "$*" >> "$BRIDGE_TEST_LOG"\nprintf "result\\n"',
      nice: 'printf "nice %s\\n" "$*" >> "$BRIDGE_TEST_LOG"\nshift 2\nexec "$@"',
      ionice: 'printf "ionice %s\\n" "$*" >> "$BRIDGE_TEST_LOG"\nshift\nexec "$@"',
    })) {
      const file = join(dir, name)
      writeFileSync(file, "#!/bin/sh\n" + body + "\n")
      chmodSync(file, 0o755)
    }
    process.env.PATH = dir
    process.env.BRIDGE_TEST_LOG = log
    assert.equal(inspectionGit("/repo", "status"), "result")
    const first = readFileSync(log, "utf8")
    assert.match(first, /nice -n 19/)
    if (process.platform === "linux") assert.match(first, /ionice -c3/)
    rmSync(join(dir, "nice"))
    assert.equal(inspectionGit("/repo", "status"), "result")
    assert.match(readFileSync(log, "utf8"), /git -C \/repo status/)
  } finally {
    if (oldPath === undefined) delete process.env.PATH; else process.env.PATH = oldPath
    if (oldLog === undefined) delete process.env.BRIDGE_TEST_LOG; else process.env.BRIDGE_TEST_LOG = oldLog
    rmSync(dir, { recursive: true, force: true })
  }
})
