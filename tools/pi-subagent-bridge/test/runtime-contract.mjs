import { spawnSync } from 'node:child_process'
const args = process.argv.slice(2)
if (args.length && (args.length !== 2 || args[0] !== '--adapter' || !['codex', 'command-code', 'antigravity', 'pi'].includes(args[1]))) throw new Error('usage: test:runtime-contract [--adapter codex|command-code|antigravity|pi]')
const files = args[1] === 'pi' ? ['integration', 'tier-policy', 'native-delegation'] : args[1] ? [args[1] === 'command-code' ? 'command' : args[1], 'no-pi', 'session', 'owner'] : ['codex', 'command', 'antigravity', 'hybrid', 'session', 'owner', 'inspect', 'server', 'no-pi']
const result = spawnSync(process.execPath, [...(args[1] === 'pi' ? ['--import', './.dev/lib/node_modules/tsx/dist/loader.mjs'] : []), '--test', ...files.map(file => `test/${file}.test.ts`)], { stdio: 'inherit', env: { ...process.env, TSX_TSCONFIG_PATH: 'tsconfig.tsx.json' } })
process.exitCode = result.status ?? 1
