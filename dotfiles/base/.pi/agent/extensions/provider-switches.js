import { realpathSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const MANAGED_PROVIDERS = new Set(['opencode-go', 'devin']);

export function providerBlockReason(provider, switches) {
    if (!switches.pi) return 'Pi is disabled in usr/harnesses.json.';
    if (MANAGED_PROVIDERS.has(provider) && !switches[provider]) {
        return `Pi provider '${provider}' is disabled in usr/harnesses.json. Choose an enabled provider/model with /model or --provider and --model.`;
    }
    return undefined;
}

export function registerProviderSwitches(pi, readSwitches) {
    function blocked(ctx, provider = ctx.model?.provider) {
        let reason;
        try {
            reason = providerBlockReason(provider, readSwitches());
        } catch (error) {
            reason = `Cannot read usr/harnesses.json: ${error instanceof Error ? error.message : String(error)}`;
        }
        if (!reason) return false;
        // Pi records an abort requested in before_agent_start and applies it
        // before the first request. Throwing alone is insufficient: extension
        // errors are reported by its runner, then normal execution continues.
        ctx.abort();
        if (ctx.hasUI) ctx.ui.notify(reason, 'error');
        else console.error(reason);
        return true;
    }

    // Consume user/RPC prompts before auto-compaction or the agent loop starts.
    pi.on('input', (_event, ctx) => blocked(ctx) ? { action: 'handled' } : undefined);
    pi.on('session_start', (_event, ctx) => { blocked(ctx); });
    pi.on('model_select', (event, ctx) => { blocked(ctx, event.model.provider); });
    // Custom-message turns and a switch changed during an existing session
    // still stop, without silently selecting a different model.
    pi.on('before_agent_start', (_event, ctx) => { blocked(ctx); });
    pi.on('before_provider_request', (_event, ctx) => { blocked(ctx); });
    pi.on('session_before_compact', (_event, ctx) => blocked(ctx) ? { cancel: true } : undefined);
    pi.on('cache_warming_decision', (_event, ctx) => blocked(ctx) ? { action: 'stop' } : undefined);
}

export default async function providerSwitches(pi) {
    // Pi's extension loader preserves an installed symlink's pathname in
    // import.meta.url. Resolve its tracked source before locating the checkout.
    const source = dirname(realpathSync(fileURLToPath(import.meta.url)));
    const helper = pathToFileURL(resolve(source, '../../../../../tools/pi-subagent-bridge/src/harnesses.ts'));
    const { readHarnessSwitches } = await import(helper.href);
    registerProviderSwitches(pi, readHarnessSwitches);
}
