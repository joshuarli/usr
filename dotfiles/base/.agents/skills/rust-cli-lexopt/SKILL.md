---
name: rust-cli-lexopt
description: Rewrite a Rust CLI to use lexopt only, driven by one declarative command schema that generates help and version output, with parser and metadata tests. Builds on design-cli.
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Declarative, Lexopt-Only Rust CLI

Read `design-cli` first and follow it: it owns surface preservation, the single schema, help, examples, bare invocation, version, the owned-tool footer, errors, and naming. This skill adds the Rust structure and the lexopt boundary. Apply only when migrating an existing Rust CLI to this architecture; otherwise report the evidence and change nothing. No business-logic changes, unrelated refactors, or unrelated dependencies.

## Inspect first

Read `Cargo.toml`, `Cargo.lock`, `main.rs`, every CLI module, tests, docs, build scripts, and every argument consumer. Inventory the surface as `design-cli` describes, including current help and version. Run the narrowest baseline tests and record preexisting failures.

## Parsing: lexopt only

- `lexopt` is the sole parser. Remove clap (and derive), structopt, argh, pico-args, and ad hoc per-command parsing from code, `Cargo.toml`, and `Cargo.lock`.
- No glob imports in the CLI (`use super::*`, `use crate::*`, `lexopt::prelude::*`); import what each module uses.
- Arguments stay `OsString`/`OsStr`; never convert lossily. Where a downstream contract needs UTF-8, reject non-UTF-8 with an explicit parse error.
- Make the boundary visible: build a `lexopt::Parser`, consume tokens with `Parser::next`, option values with `value` (`values` for a contiguous list), and match `Arg::Short`, `Arg::Long`, `Arg::Value` explicitly. Support long and short options, unambiguous clusters, `--opt=value`, `--`, and unknown-option errors. Parser tests use `Parser::from_args` or `from_iter`.
- Never use index arithmetic over `Vec<String>`. For an opaque tail after a required `--` (e.g. a guest command), find the `--`, parse the prefix with one new `lexopt::Parser`, keep the tail as `OsString`s in a type or function named for that boundary. `Parser::raw_args` is only for such tails.

## Structure

`src/main.rs` collects `args_os()`, calls `pub fn run<I, T>(args: I) -> ExitCode where I: IntoIterator<Item = T>, T: Into<OsString>`, and returns the code: no parsing, dispatch, help, or logic. Extra binary targets route through the same function, or the exception is documented.

```text
src/cli/  mod.rs  command.rs (shared metadata)  help.rs  error.rs  version.rs  <subcommand>.rs
build.rs  (if needed, for git metadata)
```

Each subcommand module owns its typed argument model, parser, spec, execution function, and focused tests; nested subcommands follow the same pattern.

## One schema in Rust

Implement the `design-cli` schema as shared metadata such as `CommandSpec { name, description, options, positionals, subcommands, examples }`, `OptionSpec { short, long, value_name, required, repeatable, default, env, help }`, and `PositionalSpec { name, required, repeatable, help }` (exact types may differ). Matching helpers consume `OptionSpec`, so no option spelling repeats as a string literal, and dispatch names tie to registered specs.

## Version

`build.rs` emits the short git SHA for the `design-cli` version line as a Cargo env var. It validates the SHA as hexadecimal, rejects `unknown` and `dirty`, honors a non-empty explicit override for release archives, documents the no-git-checkout policy, and reruns on git changes using `git rev-parse --git-dir` (`.git` is a file in worktrees).

## Errors and tests

Use typed errors for each `design-cli` usage error; help and version are successful early exits. Keep runtime error and exit-code semantics, and document any global-option placement change.

Beyond the `design-cli` tests, cover each command's parser, required, optional, and repeated values, `--`, clusters, `--opt=value`, the three `Arg` paths, opaque tails, non-UTF-8, and nested commands. Metadata tests fail on an unexplained option, missing description, name collision, unregistered command, hand-duplicated usage, or a parser repeating a spelling instead of using its `OptionSpec`.

## Finish

Verify with the compiler and focused tests and separate preexisting failures from regressions.

**The test:** `lexopt` is the only parser with no clap left, `src/cli` has no glob imports, `main.rs` is only the entrypoint, parsing and help share the schema, and the `design-cli` test holds.

**Report:** the `design-cli` report, plus global-option placement changes, extra binaries, checks not run, and preexisting failures.
