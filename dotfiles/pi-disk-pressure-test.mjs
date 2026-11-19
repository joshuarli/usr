import assert from 'node:assert/strict';
import { homedir } from 'node:os';
import { join } from 'node:path';
import diskPressure from './base/.pi/agent/extensions/disk-pressure.js';

let handler;
let result = { code: 0, stdout: '', killed: false, truncated: false };
let calls = 0;
const signal = new AbortController().signal;
diskPressure({
    on(event, callback) { assert.equal(event, 'before_agent_start'); handler = callback; },
    async exec(command, args, options) {
        calls++;
        assert.equal(command, 'python3');
        assert.deepEqual(args, ['-I', '-S', join(homedir(), '.local/bin/agent-disk-pressure'), 'notify']);
        assert.deepEqual(options, { timeout: 2000, maxBuffer: 4096, signal });
        if (result instanceof Error) throw result;
        return result;
    },
});
const old = process.env.USR_SCOPED_WORKER;
try {
    delete process.env.USR_SCOPED_WORKER;
    assert.equal(await handler({}, { signal }), undefined);
    assert.equal(calls, 1);
    result.stdout = 'System disk pressure: fixture\n';
    assert.deepEqual(await handler({}, { signal }), {
        message: { customType: 'usr-disk-pressure', content: 'System disk pressure: fixture', display: false },
    });
    for (const failure of [
        { code: 2, stdout: 'partial', killed: false, truncated: false },
        { code: 0, stdout: 'partial', killed: true, truncated: false },
        { code: 0, stdout: 'partial', killed: false, truncated: true },
        new Error('missing executable'),
    ]) {
        result = failure;
        assert.equal(await handler({}, { signal }), undefined);
    }
    const before = calls;
    process.env.USR_SCOPED_WORKER = '1';
    assert.equal(await handler({}, { signal }), undefined);
    assert.equal(calls, before);
} finally {
    if (old === undefined) delete process.env.USR_SCOPED_WORKER;
    else process.env.USR_SCOPED_WORKER = old;
}
console.log('pi disk pressure: healthy, pressure, error, timeout and scoped-worker checks passed');
