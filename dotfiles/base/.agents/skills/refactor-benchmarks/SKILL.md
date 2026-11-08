---
name: refactor-benchmarks
description: "Apply when benchmarks are synthetic, overly micro, disconnected from real-world usage, or measuring trivial loop overhead instead of user-facing workflows. Restructure benchmarks around representative workloads, realistic fixtures, macro user journeys, and allocation tracking. Skip non-benchmark tests and isolated timing runs."
---

# Refactor Benchmarks

A benchmark is a claim about how real software performs under real use. Overly micro or synthetic benchmarks mislead: they measure compiler loop-unrolling, early-exit guards, mock closures, or cache hits that never occur in production, while missing the allocation churn, layout latency, and data complexity users actually feel.

This skill reshapes a benchmark suite around representative user workflows and realistic inputs, eliminating synthetic trivialities.

## Principles

1. **User workflows over micro-loops:** Measure what users wait on or systems pay for: opening a document, typing with live syntax highlighting, scrolling across pages, full-text search navigation, and multi-cursor batch edits. Never benchmark isolated getters, trivial boolean checks, or single-branch returns in isolation.
2. **Representative fixtures over synthetic loops:** Replace repetitive synthetic generators (such as modulo-generated repeated lines) with realistic, diverse files: real code across supported languages, real config files, realistic line lengths, mixed ASCII and UTF-8 text, realistic comment and string densities.
3. **Multi-tier scales:** Measure realistic file and input sizes representing real usage: small (quick configs: a few KB), typical (real modules: 50KB to 500KB), and heavy (large files: 5MB to 25MB).
4. **Track allocations, not just nanoseconds:** Hot interactive loops (steady-state typing, scrolling a rendered frame) must measure heap allocation counts and bytes (`alloc_count` and `alloc_bytes`). In high-performance software, hot path steady-state operations should ideally perform zero allocations per frame.
5. **No mock seams or synthetic shortcuts:** A benchmark that passes mock closures returning constant values or operates on empty shells measures the mock, not the engine. Always exercise the actual production layout, viewport, and rendering pipelines.

## Method

1. **Audit existing benchmarks:**
   - Classify each benchmark: workflow-driven, realistic micro, or synthetic triviality.
   - Flag benchmarks that take < 50 ns (measuring an if-statement or inline branch), benchmarks that use synthetic generators repeating 5 canned lines, and benchmarks using fake closures or mock callbacks.
2. **Prune synthetic trivialities:**
   - Delete benchmarks that measure trivial branch checks, constant-time property reads, or mock implementations.
   - Merge narrow unit-level micro-benchmarks into meaningful workflow benchmarks where the entire path is exercised.
3. **Assemble realistic fixtures:**
   - Use representative multi-language source trees or realistic generated files that exhibit natural syntax variance, nesting, comments, identifiers, and UTF-8 content.
4. **Write workflow benchmarks:**
   - **File opening and layout:** Loading file bytes, computing line indices, viewport initialization, and first-frame rendering.
   - **Interactive typing & steady-state render:** Typing characters in real files with live syntax highlighting, dirty line tracking, and ANSI frame emission. Track both wall time and allocation churn.
   - **Interactive navigation & scrolling:** Rapid scrolling (viewport shifting, soft-wrap calculation, incremental row diffing).
   - **Real-world search & replace:** Regex and literal search over realistic documents, match counting, navigation, and replacement batch application.
   - **Multi-cursor editing:** Concurrent edits across multiple carets in realistic code.
5. **Calibrate and verify:**
   - Ensure all benchmarks use `black_box` to prevent compiler dead-code elimination.
   - Measure separate from setup: prepare buffers and viewports before entering the timed block; do not measure temp file creation or fixture generation inside the timed region.
   - Verify with the project's benchmark harness (`cargo bench`, `rustybench`, etc.).

**Report:** benchmarks pruned, added, or refactored with names and motivations; fixture improvements; measured timing and allocation deltas on representative workflows; and remaining performance limiters discovered.
