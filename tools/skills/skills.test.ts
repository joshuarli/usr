import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { spawnSync } from 'node:child_process'
const repo = resolve(import.meta.dirname, '../..'), cli = join(repo, 'tools/skills/skills.ts')
const run = (...args: string[]) => spawnSync(process.execPath, [cli, ...args], { cwd: repo, encoding: 'utf8' })
function fixture(fn: (root: string, skill: string) => void) {
  const tmp = join(repo, '.work/tmp'); mkdirSync(tmp, { recursive: true }); const root = mkdtempSync(join(tmp, 'skills-'))
  try { const skill = join(root, 'alpha'); mkdirSync(skill); writeFileSync(join(skill, 'SKILL.md'), '---\nname: alpha\ndescription: "Use it. Skip other work."\nmetadata:\n  opencode/slash: "true"\n---\n\n**Report:** Done.\n'); fn(root, skill) } finally { rmSync(root, { recursive: true, force: true }) }
}
test('generation derives and removes adapters, detects drift and is idempotent', () => fixture((root, skill) => {
  const file = join(skill, 'SKILL.md'), yaml = join(skill, 'agents/openai.yaml'), original = readFileSync(file, 'utf8')
  writeFileSync(file, original.replace('metadata:', 'disable-model-invocation: true\nmetadata:'))
  assert.equal(run('generate', '--root', root).status, 0)
  assert.match(readFileSync(file, 'utf8'), /opencode\/autoinvoke: "false"/); assert.equal(readFileSync(yaml, 'utf8'), 'policy:\n  allow_implicit_invocation: false\n')
  assert.equal(run('generate', '--check', '--root', root).status, 0)
  writeFileSync(yaml, 'policy:\n  allow_implicit_invocation: true\n'); assert.equal(run('check', '--root', root).status, 1)
  assert.equal(run('generate', '--check', '--root', root).status, 1); assert.match(readFileSync(yaml, 'utf8'), /true/)
  writeFileSync(file, readFileSync(file, 'utf8').replace('disable-model-invocation: true\n', ''))
  assert.equal(run('generate', '--root', root).status, 0); assert.equal(readFileSync(file, 'utf8'), original); assert.equal(existsSync(yaml), false)
  assert.equal(run('generate', '--check', '--root', root).status, 0)
}))
test('malformed frontmatter and unknown references fail', () => fixture((root, skill) => {
  const file = join(skill, 'SKILL.md'), original = readFileSync(file, 'utf8')
  writeFileSync(file, original.replace('metadata:', 'metadata:\n    nested: bad')); const invalid = run('check', '--root', root)
  assert.equal(invalid.status, 1); assert.match(invalid.stderr, /SKILL.md:5:/)
  writeFileSync(file, original + '\n| Task | Skill |\n| --- | --- |\n| x | `missing` |\n'); assert.equal(run('check', '--root', root).status, 1)
}))
test('links do not change invocation', () => fixture((root, skill) => {
  mkdirSync(join(root, 'beta')); writeFileSync(join(root, 'beta/SKILL.md'), '---\nname: beta\ndescription: Explicit\ndisable-model-invocation: true\n---\n\n**Report:** Done.\n')
  writeFileSync(join(skill, 'SKILL.md'), readFileSync(join(skill, 'SKILL.md'), 'utf8') + '\n[beta](../beta/SKILL.md)\n')
  assert.equal(run('generate', '--root', root).status, 0); assert.equal(run('check', '--root', root).status, 0)
  const refs = JSON.parse(run('refs', 'alpha', '--json', '--root', root).stdout); assert.equal(refs[0].invocation, 'explicit')
}))
test('real tree is current', () => { assert.equal(run('check').status, 0); assert.equal(run('generate', '--check').status, 0) })
