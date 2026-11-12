#!/usr/bin/env node
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, chmodSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

if (!process.argv[2]) throw new Error("usage: test_sdk_protocol.mjs RUNTIME_DIRECTORY");
const runtime = resolve(process.argv[2]);
const root = mkdtempSync(join(tmpdir(), 'pi-sdk-protocol-'));
const agentDir = join(root, 'agent');
const cwd = join(root, 'workspace');
mkdirSync(join(agentDir, 'agents'), { recursive: true });
mkdirSync(cwd);
Object.assign(process.env, { HOME: root, XDG_CONFIG_HOME: join(root, 'config'), XDG_DATA_HOME: join(root, 'data'),
  PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: '1', PI_SKIP_VERSION_CHECK: '1', OPENCODE_API_KEY: 'fixture-only',
  PI_SUBAGENT_MAX_DEPTH: '2', npm_config_registry: 'http://127.0.0.1:9' });
const networkGuard = join(root, 'network.mjs');
writeFileSync(networkGuard, `const original = globalThis.fetch; globalThis.fetch = (input, init) => {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('Fixture denied network: ' + url.hostname);
  return original(input, init);
};`);
process.env.NODE_OPTIONS = '--import ' + pathToFileURL(networkGuard).href;
await import(pathToFileURL(networkGuard).href);
const bin = join(root, 'bin');
mkdirSync(bin);
for (const command of ['npm', 'npx']) {
  writeFileSync(join(bin, command), '#!/bin/sh\nprintf called > "' + join(root, command + '.called') + '"\nexit 99\n');
  chmodSync(join(bin, command), 0o755);
}
process.env.PATH = bin + ':' + process.env.PATH;
const requests = [];
const server = createServer(async (request, response) => {
  let raw = '';
  for await (const chunk of request) raw += chunk;
  const body = JSON.parse(raw);
  requests.push({ path: request.url, body });
  response.writeHead(200, { 'content-type': 'text/event-stream' });
  const chunk = (delta, finish_reason = null) => response.write('data: ' + JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', created: 1,
    model: body.model, choices: [{ index: 0, delta, finish_reason }] }) + '\n\n');
  chunk({ role: 'assistant', content: 'PROOF: deterministic fixture completion' });
  chunk({}, 'stop');
  response.end('data: [DONE]\n\n');
});
await new Promise(resolveListen => server.listen(0, '127.0.0.1', resolveListen));
const baseUrl = 'http://127.0.0.1:' + server.address().port + '/v1';
writeFileSync(join(agentDir, 'models.json'), JSON.stringify({ providers: { 'opencode-go': { baseUrl, api: 'openai-completions', apiKey: 'fixture-only',
  models: [{ id: 'deepseek-v4.1-flash', name: 'Fixture of pinned worker', reasoning: true, contextWindow: 64000, maxTokens: 4096,
    input: ['text'], thinkingLevelMap: { high: 'high', max: 'max' } }] } } }));
writeFileSync(join(agentDir, 'settings.json'), JSON.stringify({ packages: [], subagents: { async: true } }));
writeFileSync(join(agentDir, 'agents/worker.md'), '---\nname: worker\ndescription: local protocol fixture\nmodel: opencode-go/deepseek-v4.1-flash\nthinking: high\ntools: read\n---\nReturn the requested proof.\n');
const pkg = join(runtime, 'node_modules');
const { ModelRuntime, DefaultResourceLoader, SettingsManager, SessionManager, createAgentSession } =
  await import(pathToFileURL(join(pkg, '@earendil-works/pi-coding-agent/dist/index.js')).href);
const responses = new Map();
const completions = [];
let session;
let rpc;
let runId;
let completed = false;
try {
  const modelRuntime = await ModelRuntime.create({ authPath: join(agentDir, 'auth.json'), modelsPath: join(agentDir, 'models.json') });
  const settingsManager = SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } });
  const loader = new DefaultResourceLoader({ cwd, agentDir, settingsManager, noExtensions: true, noSkills: true, noPromptTemplates: true,
    noThemes: true, noContextFiles: true, additionalExtensionPaths: [join(pkg, 'pi-subagents/index.ts')], extensionFactories: [pi => {
      rpc = (method, params) => new Promise((resolveReply, rejectReply) => {
        const requestId = 'fixture-' + responses.size;
        responses.set(requestId, true);
        const timer = setTimeout(() => { unsubscribe(); rejectReply(new Error('RPC timeout: ' + method)); }, 20000);
        const unsubscribe = pi.events.on('subagents:rpc:v1:reply:' + requestId, reply => { clearTimeout(timer); unsubscribe(); resolveReply(reply); });
        pi.events.emit('subagents:rpc:v1:request', { version: 1, requestId, method, params });
      });
      pi.events.on('subagent:async-complete', event => completions.push(event));
    }] });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  assert.equal(loader.getExtensions().extensions.length, 2, "Scoped SDK fixture must load only subagents and its RPC adapter, without intercom");
  ({ session } = await createAgentSession({ cwd, agentDir, modelRuntime, model: modelRuntime.getModel('opencode-go', 'deepseek-v4.1-flash'),
    thinkingLevel: 'high', settingsManager, sessionManager: SessionManager.create(cwd, join(root, 'sessions')), resourceLoader: loader, noTools: 'builtin' }));
  await session.bindExtensions({});
  assert.equal((await rpc('ping', {})).success, true);
  const spawned = await rpc('spawn', { agent: 'worker', task: 'Return the deterministic fixture proof.', async: true, cwd, worktree: false,
    model: 'opencode-go/deepseek-v4.1-flash:high', options: { agentScope: 'user' } });
  assert.equal(spawned.success, true, JSON.stringify(spawned));
  const id = spawned.data.details.asyncId ?? spawned.data.details.runId;
  runId = id;
  assert.ok(id);
  const deadline = Date.now() + 30000;
  let status;
  while (Date.now() < deadline) {
    status = await rpc('status', { id });
    if (completions.some(event => event.runId === id || event.id === id)) break;
    await new Promise(resolvePoll => setTimeout(resolvePoll, 100));
  }
  assert.ok(requests.length > 0, JSON.stringify(status));
  assert.ok(requests.every(request => request.body.model === 'deepseek-v4.1-flash'));
  const completion = completions.find(event => event.runId === id || event.id === id);
  assert.ok(completion, JSON.stringify(status));
  assert.equal(completion.success, true, JSON.stringify(completion));
  assert.match(JSON.stringify(completion.results), /PROOF: deterministic fixture completion/);
  for (const command of ['npm', 'npx']) assert.equal(existsSync(join(root, command + '.called')), false);
  completed = true;
  console.log('ok: actual SDK RPC and detached child completed through a local pinned-model fixture');
} finally {
  let safeToRemove = completed || !runId;
  if (runId && !completed) {
    const stopped = await rpc('stop', { id: runId });
    if (stopped.success) {
      const deadline = Date.now() + 10000;
      while (Date.now() < deadline) {
        if (completions.some(event => event.runId === runId || event.id === runId)) { safeToRemove = true; break; }
        await new Promise(resolvePoll => setTimeout(resolvePoll, 100));
      }
    }
  }
  session?.dispose();
  await new Promise(resolveClose => server.close(resolveClose));
  if (safeToRemove) rmSync(root, { recursive: true, force: true });
  else throw new Error('No terminal proof for owned fixture child; preserve and inspect ' + root);
}
