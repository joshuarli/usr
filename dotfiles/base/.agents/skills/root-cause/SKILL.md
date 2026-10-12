---
name: root-cause
description: "Apply when a test, build, or behavior fails and the cause is not yet established, or when a first fix did not work. Skip failures whose cause the error message already states."
---

# Root Cause

A fix without an established cause is a guess that happens to pass. Find the cause with the cheapest experiment that can refute your theory, then fix it where it originates.

- **Reproduce first, and make it small and fast.** Get a command or test that fails on demand, then shrink the input and the code path until every remaining piece is needed. That repro is your feedback loop, so it must run in seconds: one test by name, a minimal input, no full build. If it is slow, speeding it up is step one of the debugging. If you cannot reproduce it, say so and do not claim a fix.
- **Test one hypothesis at a time.** Know what it predicts and make the cheapest observation that would refute it. A code change is an experiment only if you predicted its outcome; do not edit to see whether it helps. After three refuted hypotheses, stop and recheck what you treated as fact: the exact error text, which binary, branch, config, cache, or dependency version is running, and the code between the input and the symptom.
- **Bisect when the cause is not obvious after two hypotheses.** Halve the space mechanically: the input (shrink it), the history (`git bisect run` with the repro), the code path (check state at the midpoint), or the environment (config, versions, platform). Halving beats reasoning once reasoning has failed twice.
- **Observe, do not infer.** Look at the real value where it first goes wrong: log or assert at the boundary, read the actual data, and read the pinned dependency's source rather than recalling its behavior. Read the first error, not the last. Remove the instrumentation afterwards.
- **Fix at the origin,** the first place state becomes wrong, not where it surfaces. Search for the same mistake in sibling code. A retry, sleep, longer timeout, swallowed error, loosened assertion, or special case for the failing input is a fix only when it is the actual cause.
- **A flaky failure is a real race or a hidden input** (time, ordering, shared state, randomness, ports). Loop the repro, or fix the seed or the clock, until it fails deterministically. Never retry to green.
- **Keep the repro as the regression test,** at the narrowest level that fails for the cause. Show it failing before the fix and passing after.
- **Close the loop narrowly:** the repro, then the tests of the touched area by name. Widen only for a stated integration risk.

**The test:** state the cause in one sentence, name the observation that proves it, and show the repro failing before the fix and passing after.

**Reply:** the cause, how it was established and which hypotheses were refuted, where the fix is, the regression test, and the checks run.
