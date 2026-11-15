import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { spawnSync, execFileSync } from 'node:child_process'
import { protocolPilot } from './protocol.mjs'
import { bridgePilot } from './bridge-pilot.mjs'
import { livePilot } from './live-pilot.mjs'

const root = fileURLToPath(new URL('../../../../', import.meta.url))
const pin = JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8'))
const scratch = join(root, '.work/tmp'), installHome = join(scratch, 'fx-spike/installed-home'), binary = join(installHome, '.local/bin/fx')
const args = process.argv.slice(2), mode = args[0] ?? '--local'
const liveProfile = mode === '--live' ? args[1] : undefined
if (args.length > (mode === '--live' ? 2 : 1) || !['--setup', '--local-protocol', '--local', '--live', '--bench'].includes(mode) || (mode === '--live' && args.length === 2 && !args[1])) throw new Error('usage: spike:fx [--setup|--local-protocol|--local|--live [profile]|--bench]')
mkdirSync(scratch, { recursive: true })
if (mode === '--setup') {
  const result = spawnSync('python3', ['-I', fileURLToPath(new URL('./setup.py', import.meta.url)), installHome], { stdio: 'inherit', timeout: 300000, env: { ...process.env, TMPDIR: scratch } })
  process.exitCode = result.status ?? 1
} else if (mode === '--live') {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') throw new Error('This pin qualifies only native macOS ARM64; Linux artifacts require separate qualification')
  if (!existsSync(binary)) throw new Error('Pinned FX missing; run npm run spike:fx -- --setup')
  const binaryHash = createHash('sha256').update(readFileSync(binary)).digest('hex')
  if (binaryHash !== pin.binary_sha256) throw new Error('FX binary does not match the checked-in release pin')
  const outcome = await livePilot(binary, scratch, liveProfile)
  process.exitCode = outcome.exitCode
} else {
  if (process.platform !== 'darwin' || process.arch !== 'arm64') throw new Error('This pin qualifies only native macOS ARM64; Linux artifacts require separate qualification')
  if (!existsSync(binary)) throw new Error('Pinned FX missing; run npm run spike:fx -- --setup')
  const binaryHash = createHash('sha256').update(readFileSync(binary)).digest('hex')
  if (binaryHash !== pin.binary_sha256) throw new Error('FX binary does not match the checked-in release pin')
  console.log(JSON.stringify({ mode, runtime: pin.version, provider: 'loopback fixture only', live_account: false, production_routing: false }))
  const source_revision = execFileSync('git', ['-C', root, 'rev-parse', 'HEAD'], { encoding: 'utf8', timeout: 10000 }).trim()
  const tracked_source_dirty = spawnSync('git', ['-C', root, 'diff', '--quiet', 'HEAD', '--', 'tools/pi-subagent-bridge/src', 'tools/pi-subagent-bridge/experiment', 'tools/pi-subagent-bridge/package.json'], { timeout: 10000 }).status !== 0
  const report = { source_revision, tracked_source_dirty, pin, installed_binary_bytes: statSync(binary).size, platform: process.platform + '-' + process.arch, protocol: mode === '--local-protocol' || mode === '--local' ? await protocolPilot(binary, scratch) : undefined, bridge: mode === '--local' || mode === '--bench' ? await bridgePilot(binary, scratch, { benchmark: mode === '--bench' }) : undefined }
  const output = join(scratch, mode === '--bench' ? 'fx-benchmark.json' : 'fx-qualification.json')
  writeFileSync(output, JSON.stringify(report, null, 2))
  const deferred = report.bridge?.benchmark?.status === 'deferred'
  if (deferred) process.exitCode = 75
  console.log(JSON.stringify({ status: deferred ? 'deferred' : 'passed', report: output, protocol_root: report.protocol?.root, bridge_root: report.bridge?.root, benchmark: report.bridge?.benchmark }))
}
