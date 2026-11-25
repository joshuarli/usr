+++
name = "rust-api"
summary = "Public Rust items follow the Rust API Guidelines checklist and the library rules of Microsoft's Pragmatic Rust Guidelines: predictable names and conversions, well-behaved errors, documented failures, and future-proof types."

[[trigger]]
paths = ["*.rs"]
content = ['^\s*pub\s+((async|const|unsafe|extern\s+"[^"]+")\s+)*(fn|struct|enum|trait|type|const|static|mod|use|union|macro)\b', '#\[macro_export\]']

[[trigger]]
paths = ["Cargo.toml"]
content = ['^\[features\]', '^(description|license|repository|documentation|keywords|categories)\s*=']

[examples]
match = [
  { path = "crates/core/src/lib.rs", text = "pub fn parse(input: &str) -> Result<Doc, Error> {\n" },
  { path = "src/lib.rs", text = "    pub(crate) fn helper() {}\npub struct Doc;\n" },
  { path = "Cargo.toml", text = "[features]\ndefault = []\n" },
]
skip = [
  { path = "src/lib.rs", text = "pub(crate) fn helper() {}\n" },
  { path = "src/main.rs", text = "fn main() {}\n" },
  { path = "docs/api.md", text = "pub fn parse()\n" },
]
+++

# Rust public APIs

This extends the `rust` standard, which carries Google's Rust Style Guide, for items other crates can name: public items of library crates and of workspace crates used by siblings. Rules come from the [Rust API Guidelines checklist](https://rust-lang.github.io/api-guidelines/checklist.html) (IDs `C-*`) and the library chapters of Microsoft's [Pragmatic Rust Guidelines](https://microsoft.github.io/rust-guidelines/) (IDs `M-*`), paraphrased; read the linked rule before applying it. Where `rust` already states a rule (conversion prefixes, accessors, `Default`, `From` constructors, `non_exhaustive`, `must_use`, `is_empty`, Cargo compatibility), that statement owns it. For an application's internal `pub` items, `rust`'s directness rule wins: apply only naming, `Debug`, and error rules there.

## Code

### Names

- Casing follows RFC 430 (C-CASE). Iterator methods are `iter`, `iter_mut`, and `into_iter`, and their types are named to match (C-ITER, C-ITER-TY). Related names use one word order (C-WORD-ORDER).
- Feature names say what they enable, without placeholder words such as `use-` or `with-` (C-FEATURE). Features only add functionality (M-FEATURES-ADDITIVE).
- Each public item is reachable through one public path (M-SINGLE-ITEM-PATH). Do not glob re-export (M-NO-GLOB-REEXPORTS); mark a deliberate `pub use` with `#[doc(inline)]` (M-DOC-INLINE).

### Types and traits

- Public types implement `Debug`, and its output is never empty (C-DEBUG, C-DEBUG-NONEMPTY, M-PUBLIC-DEBUG). Types users read implement `Display` (M-PUBLIC-DISPLAY).
- Types are `Send` and `Sync` where their design allows; a type that stops being `Send` is a breaking change (C-SEND-SYNC, M-TYPES-SEND).
- Collections implement `FromIterator` and `Extend` (C-COLLECT). Serde support sits behind an optional `serde` feature (C-SERDE). Binary number types support hex, octal, and binary formatting (C-NUM-FMT).
- Only smart pointers implement `Deref` and `DerefMut`, and smart pointers add no inherent methods (C-DEREF, C-SMART-PTR). Constructors are static inherent methods (C-CTOR). Conversions live on the most specific type involved (C-CONV-SPECIFIC).
- Functions return values instead of taking out-parameters (C-NO-OUT), and let callers decide where data is copied or placed (C-CALLER-CONTROL). Generic readers and writers take `R: Read` and `W: Write` by value (C-RW-VALUE).
- A trait that may be used as `dyn` stays object-safe (C-OBJECT). Seal a trait that downstream crates must not implement (C-SEALED).
- Structs keep fields private unless the struct is plain data whose fields are its contract (C-STRUCT-PRIVATE). A newtype hides its representation and guards its invariant in its constructor (C-NEWTYPE-HIDE, M-STRONG-TYPES-GUARD). A data structure does not repeat bounds that derives already add (C-STRUCT-BOUNDS).
- Arguments carry meaning through types, not bare `bool` or `Option` (C-CUSTOM-TYPE). A complex value gets a builder that validates in `build()` (C-BUILDER, M-BUILD-RESULT).
- Do not expose another crate's types in the public API unless that dependency is deliberately public and stable (M-DONT-LEAK-TYPES, C-STABLE). Public dependencies of a stable crate are themselves stable.
- Use `async fn` instead of returning `impl Future` by hand (M-ASYNC-FN). Avoid public mutable statics (M-AVOID-STATICS).

### Errors and failure

- Error types are meaningful and well-behaved: they implement `std::error::Error`, `Display`, and `Debug`, are `Send + Sync + 'static`, and are never `()` (C-GOOD-ERR).
- Functions validate their arguments (C-VALIDATE). A detected programming bug panics with a helpful message instead of returning an error (M-PANIC-ON-BUG, M-PANIC-MESSAGE).
- Destructors never fail, and a destructor that may block has a non-blocking alternative such as an explicit `close` (C-DTOR-FAIL, C-DTOR-BLOCK).

### Documentation

- The crate root documents the crate with examples (C-CRATE-DOC). Primary entry points have runnable examples that use `?`, not `unwrap` (C-EXAMPLE, C-QUESTION-MARK); an example on every item is not required.
- Function docs have `# Errors`, `# Panics`, and `# Safety` sections where they apply (C-FAILURE, M-CANONICAL-DOCS). The first sentence fits on one line (M-FIRST-DOC-SENTENCE). Link related items in prose (C-LINK), and hide unhelpful implementation details (C-HIDDEN).

### Lint overrides

- Override a lint with `#[expect(lint, reason = "...")]`, not `#[allow]`, so a stale override fails (M-LINT-OVERRIDE-EXPECT).

### Verify

- Run `cargo doc --no-deps` for the affected crates with `RUSTDOCFLAGS="-D rustdoc::broken_intra_doc_links"`, and the doc tests with `cargo test --doc`.
- For a published crate, run `cargo semver-checks` when the repository already uses it; otherwise check representative downstream calls by hand, as `rust` requires.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Fill `Cargo.toml` metadata for published crates: `description`, `license`, `repository`, `documentation`, `keywords`, and `categories` (C-METADATA). Release notes record every significant change (C-RELNOTES).
- Enable the rustc lints `missing_debug_implementations` and `unreachable_pub`, and the Clippy lints `allow_attributes` and `allow_attributes_without_reason` to enforce `#[expect]`. Fix the findings instead of suppressing them.
- Replace `#[allow]` overrides with `#[expect]` and a reason, deleting any the compiler reports as unfulfilled.

**Report:** public items changed and whether each change is breaking; lints enabled; downstream checks run.
