# Runtime independence verification

## Accepted local boundary

The bridge core installs and executes Codex work without Pi packages, a Pi runtime link, Pi credentials or provider caches. Pi remains an optional supported adapter. FX has not been installed, investigated or integrated by this execution.

Implementation checkpoints are `d68a1ba` and `d6154fc`. The final test extension also exercises network denial, public watch/campaign observation and owner interruption. Production policy JSON matched the original generation byte for byte. Public worker commands, owner protocol v1 and persisted session formats are unchanged.

Orchestration consumes the typed `PiAdapter` factory. `pi-adapter.ts` owns conversion from the legacy wire port. `optional-pi.ts` loads Pi execution support only when selected. Historical Pi file observation remains usable without the SDK. Existing subprocess adapters retain their launch protocols, typed selections and recorded native identities.

Pi steering remains live. Codex and Command Code steering interrupt the owned process, prove termination and resume the recorded session. Existing Pi nesting ceilings and subprocess leaf restrictions remain intact. Codex scout tool restrictions, Command Code plan mode and Git scope verification retain their existing limits. Git verification does not provide host containment.

The core-only registration mode preserves dependency links, foreign registrations and companions. Normal full installation still uses the pinned Pi closure. Core development installs only the existing development tools. No production dependency was added.

## Execution evidence

Execution began at `67ecf3b7b8235c712462c592bff78983690f2b8a` on macOS ARM64. The pre-existing change to `dotfiles/base/.codex/config.toml` was excluded from all commits. Initial Node was 26.7.0. Final full-suite and isolated-core checks used the managed Node 26.13.1.

Before developer setup, `npm test` exited 127 because `.dev/bin/tsrs` was absent. After setup, the baseline passed 227 tests and skipped the opt-in live Muse smoke test. Its runner reported 81.18 seconds. The policy generation check exited zero. These are test execution records, not controlled performance measurements.

The no-Pi regression failed against the original server with `TRAPPED Pi access: ./pi-port.ts`. The fixed fixture physically copies source without runtime packages. Its private HOME contains no Pi credentials or provider caches. Module loading, credential reads, HTTP requests and Pi/npm/npx runtime spawning are trapped.

The following checks exited zero:

| Check | Result |
| --- | --- |
| Bridge `npm test` | 228 passed; one opt-in live Muse skip |
| Fresh core-only dev install, then `npm run test:core` | 217 passed; zero skips; no Pi packages or runtime symlink |
| `npm run test:no-pi` | Public CLI/MCP lifecycle, continuation, owner steering/replay/interruption, watch/campaign and PATH fallback passed |
| `npm run test:runtime-contract` | 120 passed; zero skips |
| `npm run test:runtime-contract -- --adapter pi` | 16 passed; zero skips |
| `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_offline.py` | 14 passed against the pinned release closure |
| `python3 -I tools/pi/test_sync_bridge_offline.py` in a disposable checkout | One passed; no npm installation at runtime |
| Claude and Pi registration test files | Five passed each |
| OpenCode registration test file | Six passed |
| `node tools/policy/generate.ts --check` | Passed; production policy source unchanged |
| `node --test tools/policy/generate.test.ts` | Ten passed |
| `python3 -I dotfiles/orchestrate-test.py` | Eight passed |
| Changed Python Ruff/ty checks, shell syntax/ShellCheck, TypeScript checks | Passed |

An independent read-only scout review used the original bridge generation, rather than the modified admission path. It found lost executable discovery in minimal MCP environments. Appending conventional tool paths after caller PATH fixes that regression. The hostile fixture verifies both caller precedence and scratch-HOME executable discovery. A second focused review of the typed boundary reported no demonstrated P1/P2 defects. The parent checked the changes and clean review worktree independently.

The isolated checkout initially omitted registration helpers and launcher fixtures. Copying those repository inputs corrected fixture setup. A separate failure showed that requiring the SDK for historical file reads broke observation. The adapter now distinguishes SDK execution from file operations; all 65 focused observation fixtures passed without Pi packages.

## Qualification limits and stop point

Milestone A is accepted for the local macOS deterministic and pinned-Pi offline gates. Stop before FX-0. The result is runtime independence, not an FX verdict or a production replacement claim.

The following proof remains external:

- Native Linux x86-64 musl and ARM64 musl: rerun the core, runtime-contract, no-Pi and pinned-Pi offline checks on each native host.
- Live provider/account behavior: the live Muse smoke test remains opt-in. Deterministic Codex/Command Code/Antigravity results do not establish subscription entitlement or live task quality.
- Agentctl: its real integration was not run. Owner v1 public IPC and replay were exercised locally.
- Controlled startup/RSS, dependency footprint and accepted-task comparisons: no performance result is claimed. FX qualification and its benchmark commands are outside this launch.

Pi and Intercom installations are preserved. No production route changed, no remote was updated and no FX spike was started. The review checkout and private fixture logs remain under `.work/` as local acceptance evidence.
