---
name: architect
description: "Use for /architect or 'design this' on non-trivial work: sketch usage, types, signatures, and module boundaries before code, design it twice, implement against the sketch, and scrap it when workarounds repeat."
disable-model-invocation: true
---

# Architect

Jumping to code locks in the first shape you thought of. Sketch the shape cheaply, compare it with a structurally different one, and only then fill it in. The contract is the sketch, so a deviation is a signal, not friction to absorb.

## Steps

1. **Ground.** Read the code the change touches, its callers, its tests, and `git log` for why it is shaped this way. Naming a file is not grounding. Skip only for greenfield work with nothing to integrate.
2. **Usage first.** Write the caller's code as you want it to read. Derive the types from that, not the other way round.
3. **Sketch** types, signatures, and the module map with `todo!` or `not implemented` bodies and no logic. Use `make-invalid-states-unrepresentable` for the types and `api-surface-and-module-boundaries` for the edges.
4. **Design it twice.** Produce at least two structurally different whole shapes, even when the first looks sufficient. A point fix inside one shape is not a second candidate. Prefer the shape that hides more behind a smaller interface, and where a change that looks right from one file is right for the whole repo. Assume the next contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles.
5. **Choose and state the contract change.** Say why the loser lost. Surface any API, type, schema, or invariant change to the owner. Proceed without a checkpoint unless asked to stop.
6. **Implement against the sketch.** If a function needs a parameter the sketch did not foresee, decide whether the sketch, the requirement, or the implementation is wrong, and say which.
7. **Scrap when the pattern shows,** not on one edge case: the same workaround repeating across unrelated code, special-case branches for unrelated cases, types needing escape hatches (casts, optionals always set in practice), a lock added where the sketch said nothing was shared, callers needing the abstraction's internal rules. Subtract first, redesign as if the new constraints were day-one, and return to step 4. Complexity in the data is not complexity in the design.

Keep the sketch in the diff or the reply. Write no design file unless asked.

**The test:** a reviewer can read the usage and the types and predict the implementation, and the rejected shape's reason is one sentence.

**Reply:** the usage sketch, the two shapes and why one won, contract changes, and any deviation from the sketch found while implementing.
