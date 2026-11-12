#!/usr/bin/env node
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, watch, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const runtimeArg = process.argv[2];
const baselineCatalog = process.argv.includes("--baseline-catalog");
const runtime = runtimeArg ? resolve(runtimeArg) : undefined;
if (!runtime) throw new Error("usage: node verify-extensions.mjs RUNTIME_DIRECTORY");
const pkg = join(runtime, "node_modules");
const agentDir = mkdtempSync(join(tmpdir(), "pi-extension-loader-"));
const binDir = join(agentDir, "bin");
mkdirSync(binDir);
const museLog = join(agentDir, "muse.log");
const muse = join(binDir, "muse-fixture");
writeFileSync(muse, "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"" + museLog + "\"\nexit 78\n");
chmodSync(muse, 0o755);
for (const name of ["npm", "npx"]) {
  const marker = join(agentDir, name + ".called");
  const path = join(binDir, name);
  writeFileSync(path, "#!/bin/sh\nprintf called > \"" + marker + "\"\nexit 99\n");
  chmodSync(path, 0o755);
}
process.env.HOME = agentDir;
process.env.XDG_DATA_HOME = join(agentDir, ".local", "share");
process.env.XDG_CONFIG_HOME = join(agentDir, ".config");
process.env.PI_CODING_AGENT_DIR = join(agentDir, ".pi", "agent");
const intercomConfig = join(process.env.PI_CODING_AGENT_DIR, "intercom");
mkdirSync(intercomConfig, { recursive: true });
writeFileSync(join(intercomConfig, "config.json"), JSON.stringify({ enabled: false, confirmSend: true, inboundTrigger: "never" }));
process.env.PI_OFFLINE = "1";
process.env.PI_SKIP_VERSION_CHECK = "1";
process.env.PI_MUSE_SDK_MUSE_PATH = muse;
process.env.npm_config_registry = "http://127.0.0.1:9";
process.env.PATH = binDir + ":" + process.env.PATH;
const { DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager, createAgentSession, getAgentDir } =
  await import(pathToFileURL(join(pkg, "@earendil-works/pi-coding-agent/dist/index.js")).href);
const cwd = join(agentDir, "project");
const modelRuntime = await ModelRuntime.create({
  authPath: join(agentDir, "auth.json"),
  modelsPath: join(agentDir, "models.json"),
});
const settingsManager = SettingsManager.inMemory({});
const loader = new DefaultResourceLoader({
  cwd,
  agentDir: getAgentDir(),
  settingsManager,
  noExtensions: true,
  noSkills: true,
  noPromptTemplates: true,
  noThemes: true,
  noContextFiles: true,
  additionalExtensionPaths: [
    join(pkg, "pi-subagents/index.ts"),
    join(pkg, "@dataforxyz/agent-intercom-pi/index.ts"),
    join(pkg, "pi-muse-subscription/src/index.ts"),
  ],
});
let session;
try {
  await loader.reload();
  const { errors, extensions } = loader.getExtensions();
  if (errors.length) throw new Error("Pi extension initialization failed: " + errors.map(e => String(e.path) + ": " + String(e.error)).join("; "));
  if (extensions.length !== 3) throw new Error("Expected subagents, intercom, and Muse extensions");
  const created = await createAgentSession({
    cwd,
    agentDir: getAgentDir(),
    modelRuntime,
    settingsManager,
    sessionManager: SessionManager.inMemory(cwd),
    resourceLoader: loader,
    noTools: "builtin",
  });
  session = created.session;
  await session.bindExtensions({});
  if (!session.getAllTools().some(tool => tool.name === "intercom_send"))
    throw new Error("Intercom tools did not bind to the real SDK");
  if (baselineCatalog && !existsSync(museLog)) {
    await new Promise((resolveWait, rejectWait) => {
      const watcher = watch(agentDir, (_event, name) => {
        if (name === "muse.log" && existsSync(museLog)) {
          watcher.close();
          clearTimeout(timeout);
          resolveWait();
        }
      });
      const timeout = setTimeout(() => {
        watcher.close();
        rejectWait(new Error("Local Muse catalog fixture was not invoked during session binding"));
      }, 5000);
    });
  }
  const museModels = modelRuntime.getAllModels("muse-sdk");
  if (!museModels.some(model => model.id === "muse-spark-1.3") || !modelRuntime.hasConfiguredAuth("muse-sdk"))
    throw new Error("Muse provider did not register its bundled model catalog during extension binding");
  if (baselineCatalog) {
    if (!existsSync(museLog) || !readFileSync(museLog, "utf8").includes("serve --no-session-log"))
      throw new Error("Baseline Muse catalog failure was not observed");
  } else {
    await new Promise(resolveWait => setTimeout(resolveWait, 250));
    if (existsSync(museLog)) throw new Error("Offline runtime attempted an automatic Muse catalog refresh");
    if (!museModels.some(model => model.id === "muse-ember-1.0"))
      throw new Error("Bundled Muse catalog lacks the pinned Ember model");
  }
  for (const name of ["npm", "npx"])
    if (existsSync(join(agentDir, name + ".called"))) throw new Error("Runtime invoked " + name);
  console.log("ok: Pi SDK bound subagents, intercom, and Muse; " +
    (baselineCatalog ? "known baseline catalog refresh was contained (offline policy remains unverified)" : "offline catalog policy and pinned Muse models verified") +
    "; npm and npx were unused");
} finally {
  if (session) await session.extensionRunner.emit({ type: "session_shutdown" });
  session?.dispose();
  rmSync(agentDir, { recursive: true, force: true });
}
