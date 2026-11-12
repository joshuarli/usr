#!/usr/bin/env node
// Smoke-test the full Pi extension loader without credentials or model calls.
// Runs using only a checked-in, extracted runtime closure. No npm/network.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const runtime = process.argv[2];
if (!runtime) throw new Error("usage: node verify-extensions.mjs RUNTIME_DIRECTORY");
const pkg = join(runtime, "node_modules");
process.env.PI_OFFLINE = "1";
process.env.PI_SKIP_VERSION_CHECK = "1";
const { DefaultResourceLoader, SettingsManager } = await import(pathToFileURL(
  join(pkg, "@earendil-works/pi-coding-agent/dist/index.js")).href);
const agentDir = mkdtempSync(join(tmpdir(), "pi-extension-loader-"));
try {
  const loader = new DefaultResourceLoader({
    cwd: agentDir,
    agentDir,
    settingsManager: SettingsManager.inMemory({}),
    noExtensions: true,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    additionalExtensionPaths: [
      join(pkg, "pi-subagents/index.ts"),
      join(pkg, "@dataforxyz/agent-intercom-pi/index.ts"),
    ],
  });
  await loader.reload();
  const { errors, extensions } = loader.getExtensions();
  if (errors.length) {
    throw new Error("Pi extension initialization failed: " + errors.map(e =>
      String(e.path) + ": " + String(e.error)).join("; "));
  }
  if (extensions.length < 2) throw new Error("Both Pi extensions were not loaded");
  console.log("ok: Pi SDK loaded " + extensions.length +
    " local extensions with offline package mode");
} finally {
  rmSync(agentDir, { recursive: true, force: true });
}
