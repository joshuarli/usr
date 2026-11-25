import assert from 'node:assert/strict';
import { HARNESS_IDS } from '../tools/pi-subagent-bridge/src/harnesses.ts';
import { providerBlockReason, registerProviderSwitches } from './base/.pi/agent/extensions/provider-switches.js';

const switches = Object.fromEntries(HARNESS_IDS.map(id => [id, true]));
const handlers = new Map();
let reads = 0;
let failure;
registerProviderSwitches({ on(event, handler) { handlers.set(event, handler); } }, () => {
    reads++;
    if (failure) throw failure;
    return switches;
});
let aborted = 0;
const notifications = [];
const ctx = { model: { provider: 'opencode-go' }, hasUI: true,
    abort() { aborted++; }, ui: { notify(reason, type) { notifications.push({ reason, type }); } } };

for (const event of ['input', 'session_start', 'before_agent_start', 'before_provider_request', 'session_before_compact']) {
    assert.equal(handlers.get(event)({}, ctx), undefined);
}
assert.equal(aborted, 0);
switches['opencode-go'] = false;
assert.deepEqual(handlers.get('input')({ source: 'rpc' }, ctx), { action: 'handled' });
assert.equal(aborted, 1);
for (const event of ['session_start', 'before_agent_start', 'before_provider_request']) {
    handlers.get(event)({}, ctx);
}
assert.equal(aborted, 4);
assert.deepEqual(handlers.get('session_before_compact')({}, ctx), { cancel: true });
assert.equal(aborted, 5);
assert.deepEqual(handlers.get('cache_warming_decision')({}, ctx), { action: 'stop' });
assert.ok(notifications.every(({ reason, type }) => /opencode-go.*disabled/.test(reason) && type === 'error'));

ctx.model = { provider: 'devin' };
assert.equal(handlers.get('input')({}, ctx), undefined);
handlers.get('model_select')({ model: { provider: 'opencode-go' } }, ctx);
assert.equal(aborted, 7, 'model-selection event must check the newly selected provider');
assert.equal(ctx.model.provider, 'devin', 'the guard never substitutes a model');
switches.devin = false;
assert.deepEqual(handlers.get('input')({}, ctx), { action: 'handled' });
switches.devin = true;
assert.equal(handlers.get('input')({}, ctx), undefined, 'reenabling takes effect without reloading');
failure = new Error('bad switchboard');
assert.deepEqual(handlers.get('input')({}, ctx), { action: 'handled' });
assert.match(notifications.at(-1).reason, /bad switchboard/);
failure = undefined;
switches.pi = false;
assert.deepEqual(handlers.get('input')({}, ctx), { action: 'handled' });
assert.match(notifications.at(-1).reason, /^Pi is disabled/);
assert.equal(reads, 17);
assert.equal(providerBlockReason('custom-provider', { ...switches, pi: true }), undefined);
console.log('pi provider switches: prompt, model selection, custom turns, request, compaction and live-toggle guards passed');
