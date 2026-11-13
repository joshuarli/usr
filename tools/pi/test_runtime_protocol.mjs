#!/usr/bin/env node
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";

const runtime = process.argv[2];
const museBin = process.argv[3] || process.env.MUSE_BIN || "muse";
if (!runtime) throw new Error("usage: node test_runtime_protocol.mjs RUNTIME_DIRECTORY [MUSE_EXECUTABLE]");
const packageRoot = join(resolve(runtime), "node_modules", "pi-muse-subscription");
const manifest = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
const suffix = manifest.pi.extensions[0].endsWith(".js") ? "js" : "ts";
const agent = mkdtempSync(join(tmpdir(), "muse-host-fixture-"));
const scopedWorkspace = join(agent, "worktree");
mkdirSync(scopedWorkspace);
const xdg = join(agent, ".config");
const env = { ...process.env, HOME: agent, XDG_CONFIG_HOME: xdg,
  XDG_DATA_HOME: join(agent, ".local", "share"), MUSE_NO_AUTO_UPDATE: "1",
  MUSE_CONTRIBUTOR_MODE: "off", PI_OFFLINE: "1" };
const version = spawnSync(museBin, ["--version"], { env, encoding: "utf8", timeout: 5000 });
if (version.error || version.status !== 0) {
  rmSync(agent, { recursive: true, force: true });
  throw new Error("Muse executable unavailable in disposable environment: " + String(version.error ?? version.stderr));
}

const [{ MuseHost }, { McpBridge }] = await Promise.all([
  import(pathToFileURL(join(packageRoot, `src/host.${suffix}`)).href),
  import(pathToFileURL(join(packageRoot, `src/bridge.${suffix}`)).href),
]);
const bridge = new McpBridge();
let host;
try {
  let hostError = "";
  try {
    host = await MuseHost.open({
      cwd: scopedWorkspace,
      model: "muse-spark-1.3",
      systemPrompt: "fixture",
      tools: [{ name: "read", description: "fixture", parameters: { type: "object" } }],
      toolsHash: "fixture",
      open: { kind: "fresh" },
      ephemeral: false,
    }, {
      museBin,
      contributorMode: "off",
      bridge,
      baseDir: join(agent, ".pi", "agent", "muse-sdk"),
      userConfigDir: join(xdg, "muse"),
      skillsOff: async () => ({}),
      env,
    });
  } catch (error) {
    hostError = String(error);
  }
  if (!host) throw new Error("Muse session/start failed: " + hostError);
  const hostXdg = host.xdg;
  if (!hostXdg) throw new Error("Muse host did not create its private XDG config");
  const trustPath = join(hostXdg, "muse", "trust.json");
  const authPath = join(hostXdg, "muse", "auth.json");
  if (existsSync(trustPath)) throw new Error("Muse host unexpectedly created private workspace trust");
  if (existsSync(authPath)) throw new Error("Muse fixture unexpectedly linked account authentication");
  if (host.busy || !host.sessionId) throw new Error("Muse host did not stop at session/start");
  await host.close();
  console.log("ok: installed Muse accepted scoped session/start before turn/start, with no trust.json or auth.json");
} finally {
  if (host) await host.close();
  bridge.close();
  rmSync(agent, { recursive: true, force: true });
}
