/**
 * Warm Cache Timer - shows estimated prompt cache lifetime in the footer.
 *
 * Tracks the last assistant message that wrote to cache and displays a
 * countdown based on the configured cache retention TTL.
 *
 * OpenAI-compatible (DeepSeek, Codex, OpenAI):
 *   "short" (default) -> ~5 min idle eviction
 *   "long" (PI_CACHE_RETENTION=long) -> 24h via prompt_cache_retention
 *
 * The timer is a best-effort upper bound: providers may evict cache early
 * under load or memory pressure.
 */

import type { ExtensionAPI, ExtensionContext, SessionEntry } from "@earendil-works/pi-coding-agent";

export const SHORT_TTL_MS = 5 * 60 * 1000; // 5 minutes
export const LONG_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export function resolveTTL(retention?: string): number {
	const r = retention ?? process.env.PI_CACHE_RETENTION;
	if (r === "none") return 0;
	if (r === "long") return LONG_TTL_MS;
	return SHORT_TTL_MS;
}

export function formatRemaining(ms: number): string {
	if (ms <= 0) return "0s";
	const totalSeconds = Math.ceil(ms / 1000);
	if (totalSeconds < 60) return `${totalSeconds}s`;
	const minutes = Math.floor(totalSeconds / 60);
	const seconds = totalSeconds % 60;
	if (minutes < 60) return `${minutes}m ${seconds}s`;
	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;
	return `${hours}h ${remainingMinutes}m`;
}

export function findLastCacheWrite(entries: SessionEntry[]): number {
	let ts = 0;
	for (const entry of entries) {
		if (entry.type === "message" && entry.message.role === "assistant") {
			const usage = entry.message.usage;
			if (usage.cacheWrite > 0) {
				ts = Math.max(ts, entry.message.timestamp);
			}
		}
	}
	return ts;
}

export function statusLabel(ttl: number, lastWriteTimestamp: number, now?: number): string | null {
	if (ttl <= 0 || lastWriteTimestamp <= 0) return null;
	const elapsed = (now ?? Date.now()) - lastWriteTimestamp;
	const remaining = Math.max(0, ttl - elapsed);
	return remaining > 0 ? `cache warm: ${formatRemaining(remaining)}` : "cache: cold";
}

export default function (pi: ExtensionAPI) {
	let ttl = resolveTTL();
	let timer: ReturnType<typeof setInterval> | null = null;
	let lastWriteTimestamp = 0;
	let dim: ((s: string) => string) | null = null;

	function stopTimer(): void {
		if (timer) {
			clearInterval(timer);
			timer = null;
		}
	}

	function updateStatus(ctx: ExtensionContext): void {
		const label = statusLabel(ttl, lastWriteTimestamp);
		ctx.ui.setStatus("warm-cache", label ? (dim ? dim(label) : label) : undefined);
	}

	pi.on("session_start", async (_event, ctx) => {
		if (!ctx.hasUI) return;
		ttl = resolveTTL();
		dim = ctx.ui.theme ? ctx.ui.theme.fg.bind(ctx.ui.theme, "dim") : null;
		lastWriteTimestamp = findLastCacheWrite(ctx.sessionManager.getEntries());
		updateStatus(ctx);

		stopTimer();
		if (ttl > 0) {
			timer = setInterval(() => updateStatus(ctx), 1000);
		}
	});

	pi.on("message_end", async (event, ctx) => {
		if (event.message.role !== "assistant") return;
		if (event.message.usage.cacheWrite > 0) {
			lastWriteTimestamp = event.message.timestamp;
			updateStatus(ctx);
		}
	});

	pi.on("agent_settled", async (_event, ctx) => {
		updateStatus(ctx);
	});

	pi.on("session_shutdown", async () => {
		stopTimer();
		lastWriteTimestamp = 0;
	});
}
