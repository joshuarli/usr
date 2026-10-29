import assert from 'node:assert/strict';
import guard, { checkGitCommand } from './base/.pi/agent/extensions/git-execution-guard.js';

assert.deepEqual(checkGitCommand('echo hello'), { command: 'echo hello' });
assert.deepEqual(checkGitCommand('cat .git/config'), { command: 'cat .git/config' });
assert.match(checkGitCommand('git commit -m message').command, /^export GIT_EDITOR=: GIT_SEQUENCE_EDITOR=: GIT_MERGE_AUTOEDIT=no\n/);
assert.match(checkGitCommand('cd repo && git rebase main').command, /git rebase main$/);
assert.equal(checkGitCommand('git commit --no-verify -m skip').block, true);
assert.equal(checkGitCommand('git -C repo push --no-verify').block, true);

let callback;
guard({ on(event, handler) { assert.equal(event, 'tool_call'); callback = handler; } });
const other = { toolName: 'read', input: { command: 'git commit -m test' } };
assert.equal(callback(other), undefined);
assert.equal(other.input.command, 'git commit -m test');
const bash = { toolName: 'bash', input: { command: 'git commit -m test' } };
assert.equal(callback(bash), undefined);
assert.match(bash.input.command, /^export GIT_EDITOR=:/);
const blocked = { toolName: 'bash', input: { command: 'git commit --no-verify' } };
assert.equal(callback(blocked).block, true);
assert.equal(blocked.input.command, 'git commit --no-verify');
console.log('pi git guard: tests passed');
