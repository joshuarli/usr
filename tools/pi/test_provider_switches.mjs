#!/usr/bin/env node
// Real pinned SDK lifecycle, without sockets, provider requests or host state.
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = fileURLToPath(new URL('../..', import.meta.url));
const scratch = join(repo, '.work/tmp');
mkdirSync(scratch, { recursive: true });
const root = mkdtempSync(join(scratch, 'pi-provider-switches-'));
let session;
try {
    const agentDir = join(root, 'agent');
    const cwd = join(root, 'workspace');
    mkdirSync(agentDir);
    mkdirSync(cwd);
    const switches = JSON.parse(readFileSync(join(repo, 'harnesses.json'), 'utf8'));
    switches.pi = true;
    switches['opencode-go'] = false;
    switches.devin = true;
    const config = join(root, 'harnesses.json');
    const save = () => writeFileSync(config, JSON.stringify(switches));
    save();
    for (const relative of ['tools/pi-subagent-bridge/src/harnesses.ts', 'dotfiles/base/.pi/agent/extensions/provider-switches.js']) {
        const destination = join(root, relative);
        mkdirSync(new URL('.', pathToFileURL(destination)), { recursive: true });
        copyFileSync(join(repo, relative), destination);
    }
    mkdirSync(join(agentDir, 'extensions'));
    const installedExtension = join(agentDir, 'extensions/provider-switches.js');
    symlinkSync(join(root, 'dotfiles/base/.pi/agent/extensions/provider-switches.js'), installedExtension);
    Object.assign(process.env, { HOME: root, PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: '1', PI_SKIP_VERSION_CHECK: '1' });
    let requests = 0;
    globalThis.fetch = async () => { requests++; throw new Error('Provider requests are forbidden in this fixture'); };
    const sdk = await import('../pi-subagent-bridge/node_modules/@earendil-works/pi-coding-agent/dist/index.js');
    const models = {};
    for (const provider of ['opencode-go', 'devin']) {
        models[provider] = { baseUrl: 'http://127.0.0.1:9/v1', api: 'openai-completions', apiKey: 'fixture-only',
            models: [{ id: 'fixture', name: 'Fixture', reasoning: false, input: ['text'], contextWindow: 64000, maxTokens: 1024 }] };
    }
    writeFileSync(join(agentDir, 'models.json'), JSON.stringify({ providers: models }));
    const modelRuntime = await sdk.ModelRuntime.create({ authPath: join(agentDir, 'auth.json'), modelsPath: join(agentDir, 'models.json') });
    const settingsManager = sdk.SettingsManager.inMemory({ packages: [], retry: { enabled: false }, compaction: { enabled: false }, cacheWarming: 'off' });
    const loader = new sdk.DefaultResourceLoader({ cwd, agentDir, settingsManager, noExtensions: true, noSkills: true,
        noPromptTemplates: true, noThemes: true, noContextFiles: true,
        additionalExtensionPaths: [installedExtension] });
    await loader.reload();
    assert.deepEqual(loader.getExtensions().errors, []);
    assert.equal(loader.getExtensions().extensions.length, 1, JSON.stringify(loader.getExtensions().extensions.map(extension => extension.path)));
    ({ session } = await sdk.createAgentSession({ cwd, agentDir, modelRuntime, model: modelRuntime.getModel('opencode-go', 'fixture'),
        settingsManager, sessionManager: sdk.SessionManager.inMemory(cwd), resourceLoader: loader, tools: [] }));
    await session.bindExtensions({});
    let streams = 0;
    let abortedStreams = 0;
    session.agent.streamFunction = async (_model, _context, options) => {
        if (options?.signal?.aborted) abortedStreams++;
        else streams++;
        throw new Error('Fixture stream boundary');
    };
    await session.prompt('must be consumed', { source: 'rpc' });
    assert.equal(streams, 0);
    assert.equal(abortedStreams, 0, 'blocked input must never enter the agent loop');
    await session.sendCustomMessage({ customType: 'fixture', content: 'blocked custom turn', display: false }, { triggerTurn: true });
    assert.equal(streams, 0, 'custom turns must be aborted before any live provider stream');
    await session.setModel(modelRuntime.getModel('devin', 'fixture'));
    await session.prompt('enabled explicit selection');
    assert.equal(streams, 1, 'an enabled model must still reach the stream boundary');
    switches.devin = false;
    save();
    await session.prompt('switch changed while session remained open');
    assert.equal(streams, 1);
    switches['opencode-go'] = true;
    save();
    await session.setModel(modelRuntime.getModel('opencode-go', 'fixture'));
    await session.prompt('reenabled selection');
    assert.equal(streams, 2);
    assert.equal(requests, 0);
    console.log('pi provider switches SDK: blocked RPC/custom turns, live changes and enabled selections; zero provider requests');
} finally {
    try { session?.dispose(); }
    finally { rmSync(root, { recursive: true, force: true }); }
}
