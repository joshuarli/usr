+++
name = "swift"
summary = "Swift follows the Swift API Design Guidelines for clear, fluent names and labels, documents every declaration, and keeps Swift 6 data-race safety without unchecked escapes."

[[trigger]]
paths = ["*.swift"]

[examples]
match = ["Sources/Bylaws/Rule.swift", "Package.swift", "Tests/BylawsTests/RuleTests.swift"]
skip = ["README.md", "Sources/shim.c", "Package.resolved"]
+++

# Swift

Rules for naming, labels, and documentation come from the [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/). Concurrency rules follow the Swift 6 language mode and the [Swift 6.2 release](https://www.swift.org/blog/swift-6.2-released/). A forked repository follows its upstream's conventions where they differ.

## Code

### Fundamentals

- Clarity at the point of use matters most; judge a declaration by how its call site reads. Clarity beats brevity.
- Write a doc comment for every declaration. Start with a one-sentence summary fragment ending in a period: what a function does and returns, what a subscript accesses, what an initializer creates, what anything else is. Use symbol markup (`- Parameter`, `- Returns`, `- Throws`). If an API is hard to describe simply, reconsider its design.
- Document the complexity of a computed property that is not O(1).

### Names

- Include every word needed to avoid ambiguity (`remove(at:)`), and omit words that repeat type information (`remove(_:)`, not `removeElement(_:)`).
- Name variables, parameters, and associated types by role, not type (`greeting`, not `string`). Precede a weakly typed parameter (`Any`, `AnyObject`, `Int`, `String`) with a noun describing its role.
- Call sites read as grammatical English (`x.insert(y, at: z)`). Factory methods begin with `make`.
- Name by side effect: noun phrases for methods without side effects (`distance(to:)`), imperative verbs for mutating ones (`sort()`). Pair mutating and nonmutating forms as `sort()`/`sorted()`, `stripNewlines()`/`strippingNewlines()`, or `formUnion(_:)`/`union(_:)`.
- Boolean properties and nonmutating methods read as assertions (`isEmpty`, `intersects(_:)`). Protocols describing what something is are nouns (`Collection`); capability protocols end in `able`, `ible`, or `ing`.
- Types and protocols use `UpperCamelCase`; everything else `lowerCamelCase`. Acronyms that are all caps in American English are uniformly upper or lower case (`utf8Bytes`, `userSMTPServer`).
- Use terms of art only for their established meaning, avoid nonstandard abbreviations, and follow precedent (`Array`, `sin(x)`).

### Conventions and labels

- Prefer methods and properties to free functions, except with no obvious `self`, an unconstrained generic, or established notation. Do not overload on return type alone.
- Prefer one method with default parameters, placed last, over a family of overloads. Use `#fileID` in production APIs.
- Omit all labels when arguments cannot be usefully distinguished (`min(_:_:)`). Omit the first label for a value-preserving conversion initializer (`String(x)`); use a descriptive label for a narrowing one (`truncating:`).
- Label a first argument that starts a prepositional phrase at the preposition (`removeBoxes(havingLength:)`), unless the first two arguments form one abstraction (`moveTo(x:y:)`). Fold a first argument that completes a grammatical phrase into the base name (`addSubview(_:)`). Label arguments with defaults, and all others.
- Label tuple members and name closure parameters. Name overloads that could collide under unconstrained polymorphism apart (`append(contentsOf:)`).

### Values, errors, and access

- Prefer structs and enums; use a class for identity or reference semantics.
- Throw for recoverable failures, and use typed `throws(E)` when callers switch over a closed error set. Use `precondition` or `fatalError` only for programmer errors. Do not `try!`, force-unwrap, or declare implicitly unwrapped optionals for values that can be absent at run time.
- Give each declaration the narrowest access level that works (`private`, `fileprivate`, `internal`, `package`, `public`).

### Concurrency

- Keep Swift 6 data-race safety intact. Do not add `@unchecked Sendable`, `nonisolated(unsafe)`, or `@preconcurrency` imports without a comment stating the invariant that makes them safe.
- Prefer structured concurrency (`async let`, task groups) to unstructured `Task {}`, and avoid `Task.detached`. Every task has an owner that awaits or cancels it, and long-running work checks `Task.isCancelled` or calls `Task.checkCancellation()`.
- Isolate UI and shared mutable state to an actor or `@MainActor`. Mark work that must leave its actor with `@concurrent`. Do not mix Dispatch queues with actor isolation for the same state.
- `Span` gives checked access to contiguous memory and `InlineArray` fixed-size inline storage; prefer them to unsafe pointers where the deployment target allows.

### Verify

- Run `swift build` and `swift test` (or the repository's Xcode scheme) on the affected targets, and fix new warnings rather than suppressing them.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Build in the Swift 6 language mode: a 6.x `swift-tools-version` uses it unless `swiftLanguageModes` says otherwise. Remove `@preconcurrency` imports and unchecked conformances as their dependencies gain `Sendable` annotations.
- Consider `.treatAllWarnings(as: .error)` in package settings, and main-actor default isolation (`-default-isolation MainActor`) for app targets. Check the installed toolchain's SwiftPM documentation for exact setting names before enabling either.

**Report:** language mode and concurrency settings; unchecked escapes removed or kept with their reason; public names changed and whether each is breaking.
