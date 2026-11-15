import { readdirSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
const files = readdirSync(new URL('.', import.meta.url)).filter(file => file.endsWith('.test.ts') && !['integration.test.ts', 'tier-policy.test.ts', 'muse-smoke.test.ts'].includes(file))
const result = spawnSync(process.execPath, ['--test', ...files.map(file => `test/${file}`)], { stdio: 'inherit' })
process.exitCode = result.status ?? 1
