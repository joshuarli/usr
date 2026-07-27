import { defineConfig } from "vitest/config";
import path from "node:path";

const PI_ROOT = "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent";
const PI_NM = path.join(PI_ROOT, "node_modules", "@earendil-works");

export default defineConfig({
	resolve: {
		alias: {
			"@earendil-works/pi-coding-agent": path.join(PI_ROOT, "dist", "index.js"),
			"@earendil-works/pi-ai": path.join(PI_NM, "pi-ai"),
			"@earendil-works/pi-agent-core": path.join(PI_NM, "pi-agent-core"),
			"@earendil-works/pi-tui": path.join(PI_NM, "pi-tui"),
		},
	},
});
