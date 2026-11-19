import { spawn } from "node:child_process"

// Starts a detached process-group leader and exits at once, so the started process is reparented away from the caller's tree.
const [executable, ...args] = process.argv.slice(2)
if (!executable) process.exit(2)
const child = spawn(executable, args, { detached: true, stdio: "ignore", env: process.env, cwd: process.cwd() })
child.once("error", () => process.exit(1))
child.once("spawn", () => { process.stdout.write(String(child.pid) + "\n"); child.unref(); process.exit(0) })
