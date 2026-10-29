import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { bindings, defineConfig, triggers } from "cf/config";
import * as entrypoint from "./src/index.js" with { type: "cf-worker" };

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const setupSh = readFileSync(join(repoRoot, "host", "setup.sh"), "utf8");

export default defineConfig({
	worker: {
		name: "usr-setup",
		compatibilityDate: "2026-10-28",
		entrypoint,
		env: {
			SETUP_SH: bindings.text(setupSh),
		},
		triggers: [triggers.fetch({ pattern: "17166969.xyz/setup.sh", zone: "17166969.xyz" })],
	},
});
