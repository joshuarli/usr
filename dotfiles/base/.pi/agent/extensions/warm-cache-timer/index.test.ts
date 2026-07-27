import type { Usage } from "@earendil-works/pi-ai";
import type { SessionEntry } from "@earendil-works/pi-coding-agent";
import { afterEach, describe, expect, it } from "vitest";
import {
	findLastCacheWrite,
	formatRemaining,
	resolveTTL,
	SHORT_TTL_MS,
	LONG_TTL_MS,
	statusLabel,
} from "./index.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function usage(overrides: Partial<Usage> = {}): Usage {
	return {
		input: 0,
		output: 0,
		cacheRead: 0,
		cacheWrite: 0,
		totalTokens: 0,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
		...overrides,
	};
}

function entry(
	overrides: Partial<SessionEntry> & { type: "message"; message: { role: "assistant" } },
): SessionEntry {
	return {
		type: "message",
		message: {
			role: "assistant",
			content: [],
			api: "openai-completions" as const,
			provider: "deepseek" as const,
			model: "deepseek-chat",
			usage: usage(),
			stopReason: "stop" as const,
			timestamp: 0,
			...overrides.message,
		},
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("formatRemaining", () => {
	it("returns 0s for zero or negative", () => {
		expect(formatRemaining(0)).toBe("0s");
		expect(formatRemaining(-1)).toBe("0s");
	});

	it("formats seconds", () => {
		expect(formatRemaining(1000)).toBe("1s");
		expect(formatRemaining(59_000)).toBe("59s");
	});

	it("formats minutes and seconds", () => {
		expect(formatRemaining(60_000)).toBe("1m 0s");
		expect(formatRemaining(90_000)).toBe("1m 30s");
		expect(formatRemaining(3599_000)).toBe("59m 59s");
	});

	it("formats hours and minutes", () => {
		expect(formatRemaining(3600_000)).toBe("1h 0m");
		expect(formatRemaining(3660_000)).toBe("1h 1m");
		expect(formatRemaining(86_400_000)).toBe("24h 0m");
	});
});

describe("resolveTTL", () => {
	afterEach(() => {
		delete process.env.PI_CACHE_RETENTION;
	});

	it("returns SHORT_TTL_MS by default", () => {
		expect(resolveTTL()).toBe(SHORT_TTL_MS);
	});

	it('returns SHORT_TTL_MS for "short"', () => {
		expect(resolveTTL("short")).toBe(SHORT_TTL_MS);
	});

	it('returns LONG_TTL_MS for "long"', () => {
		expect(resolveTTL("long")).toBe(LONG_TTL_MS);
	});

	it('returns 0 for "none"', () => {
		expect(resolveTTL("none")).toBe(0);
	});

	it("reads PI_CACHE_RETENTION env var when no argument", () => {
		process.env.PI_CACHE_RETENTION = "long";
		expect(resolveTTL()).toBe(LONG_TTL_MS);
		process.env.PI_CACHE_RETENTION = "none";
		expect(resolveTTL()).toBe(0);
	});
});

describe("findLastCacheWrite", () => {
	it("returns 0 for empty entries", () => {
		expect(findLastCacheWrite([])).toBe(0);
	});

	it("returns 0 when no entries have cache writes", () => {
		const entries: SessionEntry[] = [
			entry({ message: { role: "assistant", timestamp: 100, usage: usage({ cacheWrite: 0 }) } }),
		];
		expect(findLastCacheWrite(entries)).toBe(0);
	});

	it("returns timestamp of the last entry with cacheWrite > 0", () => {
		const entries: SessionEntry[] = [
			entry({ message: { role: "assistant", timestamp: 100, usage: usage({ cacheWrite: 500 }) } }),
			entry({ message: { role: "assistant", timestamp: 200, usage: usage({ cacheWrite: 0 }) } }),
			entry({ message: { role: "assistant", timestamp: 300, usage: usage({ cacheWrite: 100 }) } }),
		];
		expect(findLastCacheWrite(entries)).toBe(300);
	});

	it("skips non-assistant messages", () => {
		const entries: SessionEntry[] = [
			{
				type: "message",
				message: {
					role: "user",
					content: "hello",
					timestamp: 500,
				},
			},
			entry({ message: { role: "assistant", timestamp: 300, usage: usage({ cacheWrite: 100 }) } }),
		];
		expect(findLastCacheWrite(entries)).toBe(300);
	});

	it("skips compaction and branch_summary entries", () => {
		const entries: SessionEntry[] = [
			{ type: "compaction", summary: "summary", entryIds: [] },
			{ type: "branch_summary", summary: "summary", fromEntryId: "a", toEntryId: "b" },
			entry({ message: { role: "assistant", timestamp: 300, usage: usage({ cacheWrite: 100 }) } }),
		];
		expect(findLastCacheWrite(entries)).toBe(300);
	});
});

describe("statusLabel", () => {
	const BASE = 1_000_000_000_000; // arbitrary fixed point in time

	it("returns null when ttl is 0", () => {
		expect(statusLabel(0, 1000, 1000)).toBeNull();
	});

	it("returns null when lastWriteTimestamp is 0", () => {
		expect(statusLabel(300_000, 0, 1000)).toBeNull();
	});

	it('returns "cache: cold" when TTL has elapsed', () => {
		expect(statusLabel(SHORT_TTL_MS, BASE, BASE + SHORT_TTL_MS + 1)).toBe("cache: cold");
	});

	it("returns warm countdown when within TTL", () => {
		// Wrote at BASE, now is BASE + 60s -> 4m remaining of 5m TTL
		expect(statusLabel(SHORT_TTL_MS, BASE, BASE + 60_000)).toBe("cache warm: 4m 0s");
	});

	it("returns warm countdown at boundary", () => {
		// Wrote at BASE, now is 1s before TTL expiry -> 1s remaining
		expect(statusLabel(SHORT_TTL_MS, BASE, BASE + SHORT_TTL_MS - 1000)).toBe("cache warm: 1s");
	});

	it("returns cold exactly at TTL expiry", () => {
		expect(statusLabel(SHORT_TTL_MS, BASE, BASE + SHORT_TTL_MS)).toBe("cache: cold");
	});

	it("uses Date.now() when now is not provided", () => {
		const recent = Date.now() - 1000;
		const label = statusLabel(SHORT_TTL_MS, recent);
		expect(label).not.toBeNull();
		expect(label).toMatch(/^cache warm:/);
	});
});
