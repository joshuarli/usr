import { homedir } from 'node:os';
import { join } from 'node:path';

export default function diskPressure(pi) {
    pi.on('before_agent_start', async (_event, ctx) => {
        if (process.env.USR_SCOPED_WORKER === '1') return;
        try {
            const result = await pi.exec('python3', [
                '-I', '-S', join(homedir(), '.local/bin/agent-disk-pressure'), 'notify',
            ], { timeout: 2000, maxBuffer: 4096, signal: ctx.signal });
            if (result.code !== 0 || result.killed || result.truncated || !result.stdout.trim()) return;
            return { message: {
                customType: 'usr-disk-pressure', content: result.stdout.trim(), display: false,
            } };
        } catch {
            // An advisory check cannot prevent an unrelated run from starting.
        }
    });
}
