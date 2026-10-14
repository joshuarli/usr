---
name: rust-cli-lexopt
description: Rewrite a Rust CLI to use lexopt only, driven by one declarative command schema that generates help and version output, with parser and metadata tests.
disable-model-invocation: true
---

# Declarative, Lexopt-Only Rust CLI

One command schema drives parsing, validation, help, version, errors, and tests, with the lexopt boundary explicit in the source. Apply only when migrating an existing Rust CLI to this architecture; otherwise report the evidence and change nothing. Preserve command names, valid invocations, aliases (unless removal is documented), defaults, environment behavior, output formats, exit codes, and side effects. No business-logic changes, unrelated refactors, or unrelated dependencies.

## Inspect first

Read `Cargo.toml`, `Cargo.lock`, `main.rs`, every CLI module, tests, docs, build scripts, and every argument consumer. Inventory the surface: executable name, subcommands (nested too), aliases, global and local options, short and long flags, positionals (required, optional, repeated), defaults, environment inputs, exit codes, current help and version. Run the narrowest baseline tests and record preexisting failures.

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

## One schema

Keep no separate lists of spellings, help, usage, defaults, value names, or summaries. Shared metadata such as `CommandSpec { name, description, options, positionals, subcommands, examples }`, `OptionSpec { short, long, value_name, required, repeatable, default, env, help }`, `PositionalSpec { name, required, repeatable, help }` (exact types may differ) with these invariants:

- every command has a spec and exactly one non-empty canonical description; every option and positional is explained;
- every option spelling comes from a spec (matching helpers consume `OptionSpec`; no repeated string literals), and dispatch names tie to registered specs;
- names are unique per scope; short and long collisions are rejected by construction or test;
- usage and help are rendered from metadata, never hand-written.

## Help and version

- `tool cmd -h|--help` (nested too) prints to stdout, exits 0, and works before required-argument validation. It shows usage, every option and positional with default, value name, required and repeated status, env inputs, nested commands, and examples, all generated.
- `tool -h|--help` is one deterministic recursive reference: usage, common options once, then every command and nested command with usage, description, own options, and positionals. No short command index followed by duplicated descriptions, no concatenated standalone pages; command blocks note that common options are inherited, while standalone pages show them.
- `-v|--version` prints the package version and a short git SHA embedded at build time, e.g. `tool 1.4.0 (git abc123456789)`. Never run git at runtime. If `-v` already means something else, keep that and provide only `--version`, and report the conflict. `build.rs` emits the SHA as a Cargo env var, validates it as hexadecimal, rejects `unknown`/`dirty`, honors a non-empty explicit override for release archives, documents the no-git-checkout policy, and reruns on git changes using `git rev-parse --git-dir` (`.git` is a file in worktrees).

## Errors and tests

Typed errors for unknown commands and options, missing and invalid values, missing or unexpected positionals, and duplicate non-repeatable options go to stderr with a nonzero exit, naming the command or argument. Help and version are successful early exits. Input never panics. Keep runtime error and exit-code semantics, and document any global-option placement change.

Test the observable contract: each command's parser, `-h` and `--help`, top-level help shape and ordering, version and embedded SHA, unknown and missing and invalid input, required, optional, and repeated values, `--`, clusters, `--opt=value`, the three `Arg` paths, opaque tails, non-UTF-8, nested commands. Metadata tests fail on an unexplained option, missing description, name collision, unregistered command, hand-duplicated usage, or a parser repeating a spelling instead of using its `OptionSpec`. Prefer string assertions or the project's snapshot convention; add no snapshot dependency.

## Finish

Update README and docs to match generated help. Verify with the compiler and focused tests and separate preexisting failures from regressions. Done when lexopt is the only parser with no clap left, no glob imports under `src/cli`, main is only the entrypoint, each subcommand has a module and spec, parsing and help share the schema, every command supports help, version carries the SHA, output is deterministic, tests exist, and behavior is preserved.

**Reply:** surface migrated, deviations (global-option placement, `-v` conflicts, extra binaries), checks run and not run, preexisting failures.
