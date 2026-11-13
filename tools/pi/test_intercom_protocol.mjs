#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [runtimeArg, scratchArg] = process.argv.slice(2);
assert(runtimeArg, "usage: test_intercom_protocol.mjs RUNTIME_ROOT [SCRATCH_ROOT]");
const runtimeRoot = resolve(runtimeArg);
const packageRoot = join(runtimeRoot, "node_modules/@dataforxyz/agent-intercom-pi");
const manifest = JSON.parse(await readFile(join(packageRoot, "package.json"), "utf8"));
const extensionEntry = manifest.pi.extensions[0];
const compiled = extensionEntry.endsWith(".js");
const loader = join(runtimeRoot, "node_modules/tsx/dist/loader.mjs");
const brokerPath = join(packageRoot, compiled ? "broker/broker.js" : "broker/broker.ts");
const brokerArgs = compiled ? [] : ["--import", loader];
for (const path of compiled ? [brokerPath] : [loader, brokerPath]) {
  await readFile(path);
}

const scratchBase = scratchArg ? resolve(scratchArg) : tmpdir();
await mkdir(scratchBase, { recursive: true });
const scratch = await mkdtemp(join(scratchBase, "ic-"));
const home = join(scratch, "h");
const agentDir = join(scratch, "a");
const intercomDir = join(agentDir, "intercom");
await mkdir(join(home, ".pi/agent"), { recursive: true });
await mkdir(intercomDir, { recursive: true });

const env = {
  ...process.env,
  HOME: home,
  XDG_CONFIG_HOME: join(home, '.config'),
  XDG_DATA_HOME: join(home, '.local/share'),
  PI_CODING_AGENT_DIR: agentDir,
  PI_OFFLINE: "1",
  PI_SKIP_VERSION_CHECK: "1",
  npm_config_registry: "http://127.0.0.1:9",
};
delete env.AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH;
delete env.AGENT_INTERCOM_REMOTE_ACCESS_CREDENTIAL_PATH;
delete env.AGENT_INTERCOM_BOSS_RUN_ID;

Object.assign(process.env, env);
for (const key of ['AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH', 'AGENT_INTERCOM_REMOTE_ACCESS_CREDENTIAL_PATH', 'AGENT_INTERCOM_BOSS_RUN_ID'])
  delete process.env[key];

const configPath = join(intercomDir, "config.json");
await writeFile(configPath, `${JSON.stringify({
  brokerCommand: process.execPath,
  brokerArgs,
  confirmSend: true,
  inboundTrigger: "never",
}, null, 2)}\n`, { mode: 0o600 });

const importFromRuntime = async (relativePath) => import(pathToFileURL(join(packageRoot, relativePath)).href);
const [{ IntercomClient }, { loadConfig }, extensionModule] = await Promise.all([
  importFromRuntime(compiled ? "broker/client.js" : "broker/client.ts"),
  importFromRuntime(compiled ? "config.js" : "config.ts"),
  importFromRuntime(extensionEntry),
]);
const config = loadConfig();
assert.equal(config.confirmSend, true, "the consumer profile requires confirmation by default");
assert.equal(config.inboundTrigger, "never", "the consumer profile must not auto-wake from inbound messages");

const handlers = new Map();
const registeredTools = new Map();
const sentToAgent = [];
const eventListeners = new Map();
const piEvents = {
  on(name, handler) {
    const listeners = eventListeners.get(name) ?? new Set();
    listeners.add(handler);
    eventListeners.set(name, listeners);
    return () => listeners.delete(handler);
  },
  emit(name, payload) {
    for (const listener of eventListeners.get(name) ?? []) listener(payload);
  },
};
const pi = {
  events: piEvents,
  on(name, handler) {
    const items = handlers.get(name) ?? [];
    items.push(handler);
    handlers.set(name, items);
  },
  registerTool(tool) {
    registeredTools.set(tool.name, tool);
  },
  registerCommand() {},
  registerShortcut() {},
  registerMessageRenderer() {},
  getSessionName: () => "fixture-receiver",
  appendEntry() {},
  sendMessage(message, options) {
    sentToAgent.push({ message, options });
  },
};
const sessionId = "session-intercom-fixture-receiver";
const ctx = {
  mode: "interactive",
  hasUI: false,
  cwd: scratch,
  model: { id: "fixture-model" },
  isIdle: () => true,
  sessionManager: { getSessionId: () => sessionId },
};

const nodePath = process.execPath;
const broker = spawn(nodePath, [...brokerArgs, brokerPath], {
  cwd: packageRoot,
  env,
  stdio: ["ignore", "pipe", "pipe"],
});
let brokerOutput = "";
broker.stdout.setEncoding("utf8").on("data", (chunk) => { brokerOutput += chunk; });
broker.stderr.setEncoding("utf8").on("data", (chunk) => { brokerOutput += chunk; });
const peer = new IntercomClient();
const peerReceived = [];
let cleanupError;

async function waitFor(predicate, label, timeoutMs = 7000) {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    if (predicate()) return;
    if (broker.exitCode !== null || broker.signalCode !== null) {
      throw new Error(`broker exited before ${label}: ${brokerOutput}`);
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 20));
  }
  throw new Error(`timed out waiting for ${label}${brokerOutput ? `; broker: ${brokerOutput}` : ""}`);
}

try {
  extensionModule.default(pi);
  const startHandlers = handlers.get("session_start") ?? [];
  assert.equal(startHandlers.length, 1, "the real intercom extension registers its session_start handler");
  startHandlers[0]({}, ctx);

  await waitFor(() => brokerOutput.includes("Intercom broker started"), "the real package broker to listen");
  await peer.connect({
    name: "authorized-fixture-peer",
    cwd: scratch,
    model: "fixture-model",
    pid: process.pid,
    startedAt: Date.now(),
    lastActivity: Date.now(),
    status: "idle",
  }, "session-intercom-fixture-peer");
  peer.on("message", (from, message, deliveryId) => {
    peerReceived.push({ from, message });
    peer.acknowledgeMessage(deliveryId);
  });

  let sessions = [];
  const registrationDeadline = Date.now() + 7000;
  while (Date.now() < registrationDeadline) {
    sessions = await peer.listSessions();
    if (sessions.some((session) => session.id === sessionId)) break;
    await new Promise((resolveWait) => setTimeout(resolveWait, 20));
  }
  assert(sessions.some((session) => session.id === sessionId), "the real broker lists the extension session next to the local fixture peer");

  const sendResult = await peer.send(sessionId, { text: "fixture intercom receive proof" });
  assert.equal(sendResult.accepted, true, "broker accepted local fixture peer delivery");
  assert.equal(sendResult.delivered, true, "real extension acknowledged durable message receipt");

  await waitFor(() => sentToAgent.some((entry) => entry.message?.customType === "intercom_message"), "the real extension to deliver the received message");
  const delivery = sentToAgent.find((entry) => entry.message?.customType === "intercom_message");
  assert.match(delivery.message.content, /fixture intercom receive proof/);
  assert.deepEqual(delivery.options, { deliverAs: "followUp" }, "inboundTrigger=never queues the message without waking the model");
  assert.equal(sentToAgent.some((entry) => entry.options?.triggerTurn === true), false, "inbound fixture traffic caused no automatic model turn");

  const sendTool = registeredTools.get("intercom_send");
  assert(sendTool, "the real extension registered its split send tool");
  const confirmations = [];
  const confirmedContext = {
    ...ctx,
    hasUI: true,
    ui: {
      confirm: async (title, message) => {
        confirmations.push({ title, message });
        return true;
      },
    },
  };
  const outbound = await sendTool.execute(
    "fixture-intercom-send",
    { to: "session-intercom-fixture-peer", message: "fixture intercom send proof" },
    undefined,
    undefined,
    confirmedContext,
  );
  assert.equal(confirmations.length, 1, "confirmSend=true asks the UI before a non-reply send");
  assert.equal(confirmations[0].title, "Send Message");
  assert.equal(outbound.details.delivered, true, "the real extension reports confirmed local peer delivery");
  await waitFor(() => peerReceived.some((entry) => entry.message.content.text === "fixture intercom send proof"), "the fixture peer to receive the confirmed message");
  assert.equal(peerReceived.find((entry) => entry.message.content.text === "fixture intercom send proof").from.id, sessionId);

  console.log("ok: extracted Pi Intercom broker routed messages both ways between the real extension and an authorized local peer; confirmSend=true used UI confirmation and inboundTrigger=never caused no automatic wake");
} finally {
  const shutdownHandlers = handlers.get("session_shutdown") ?? [];
  for (const handler of shutdownHandlers) {
    try {
      await handler();
    } catch (error) {
      cleanupError ??= error;
    }
  }
  for (const client of [peer]) {
    try {
      await client.disconnect(true);
    } catch (error) {
      cleanupError ??= error;
    }
  }
  if (broker.exitCode === null && broker.signalCode === null) {
    broker.kill("SIGTERM");
    const ended = await Promise.race([
      new Promise((resolveWait) => broker.once("exit", () => resolveWait(true))),
      new Promise((resolveWait) => setTimeout(() => resolveWait(false), 1500)),
    ]);
    if (!ended && broker.exitCode === null && broker.signalCode === null) {
      broker.kill("SIGKILL");
      await new Promise((resolveWait) => broker.once("exit", resolveWait));
    }
  }
  await rm(scratch, { recursive: true, force: true });
  if (cleanupError) throw cleanupError;
}
