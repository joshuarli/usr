---
name: reference-parity
description: "Apply when rewriting, porting, or replacing a component that has a reference implementation, spec, or earlier behavior to match. Skip greenfield work and refactors the existing suite already covers."
---

# Reference Parity

A rewrite is done when it is indistinguishable from the reference on every behavior that matters, and nobody wrote most of those behaviors down. Make the reference the oracle and run both.

- **Name the reference:** the old implementation, spec, or release, in a form that can run. If it cannot run, the oracle is its tests, recorded outputs, or spec examples, and you say which.
- **Inventory behaviors from the reference, not from the new design:** public surface (commands, flags, endpoints, functions), inputs and outputs, errors and exit codes, side effects, persisted formats, ordering, edge cases, config and environment. Read the reference's tests, docs, callers, and real data for what is relied on. Each behavior gets a test named for it, and a behavior with no test is not done.
- **Run both on the same inputs.** Feed one corpus to reference and port (existing fixtures, recorded real inputs, boundary cases, generated or fuzzed inputs with fixed seeds) and compare outputs, errors, and side effects, normalizing only the nondeterminism that is real (clock, ids, unordered output). Capture goldens from the reference once and commit them.
- **Keep the loop narrow.** Check one behavior with its single case, by name. Organize the corpus by behavior area so a failing area reruns alone, and run the full corpus at phase gates and the close. Shard or sample it for development if it is slow.
- **Breadth before depth.** Get every behavior to a first passing state end to end before perfecting one, and keep the unported behaviors listed. Speed, memory, and size parity come after functional parity: until then record the numbers against the reference and gate only egregious regressions.
- **A difference is a decision.** A deliberate difference (a bug not carried over, a changed format) is noted once with its reason. A quirk you cannot reproduce is an open item until decided. A bug found in the reference gets its own commit or finding; never carry it or fix it silently.
- **No vacuous parity.** Break the port on purpose and see the test fail, the same standard as the Oracle Test in `test-audit`. A comparison that normalizes away the difference proves nothing.
- **Finish** with no open behavior, then remove the reference path and any compatibility shim (`dead-code-archaeology`).

**The test:** pick any behavior of the reference at random. A test covers it, fails if the port gets it wrong, and passes.

**Reply:** the reference, behaviors still open, intentional differences, the narrow and full commands run, and what the corpus does not cover.
