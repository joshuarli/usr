const GIT_COMMAND = /(?:^|[;&|(\n]\s*|\b(?:sudo|env)\s+)git(?=\s|$)/m;
const NO_VERIFY = /(?:^|\s)--no-verify(?=\s|$)/m;
const NO_EDITOR = 'export GIT_EDITOR=: GIT_SEQUENCE_EDITOR=: GIT_MERGE_AUTOEDIT=no\n';

export function checkGitCommand(command) {
    if (!GIT_COMMAND.test(command)) return { command };
    if (NO_VERIFY.test(command)) {
        return { block: true, reason: 'Git hook bypass (--no-verify) is not allowed; fix the hook failure instead.' };
    }
    return { command: NO_EDITOR + command };
}

export default function gitExecutionGuard(pi) {
    pi.on('tool_call', (event) => {
        if (event.toolName !== 'bash' || typeof event.input?.command !== 'string') return;
        const result = checkGitCommand(event.input.command);
        if (result.block) return { block: true, reason: result.reason };
        event.input.command = result.command;
    });
}
