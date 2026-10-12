---
name: rust-cli-lexopt
description: Rewrite a Rust CLI to use lexopt only, driven by one declarative command schema that generates help and version output, with parser and metadata tests.
disable-model-invocation: true
---

# Make the Rust CLI Declarative, Lexopt-Only, and Self-Describing

Establish one authoritative command schema that drives parsing, validation, help, version, error behavior, and tests, without changing business logic.

Apply only when migrating an existing Rust CLI to this architecture; otherwise report the evidence and change nothing. The intended changes are: replace the parser with lexopt, remove Clap and its dependency surface, centralize CLI behavior under the schema and modules below, and add generated help, version, and tests. Preserve command names, valid invocations, aliases (unless removal is documented), defaults, environment behavior, output formats, exit codes, and side effects.

## Inspect first

Read `Cargo.toml`, `Cargo.lock`, `src/main.rs`, `src/lib.rs` if present, every CLI module, tests, README and docs, build scripts, and every argument consumer. Inventory the whole surface: executable name, subcommands and nested subcommands, aliases, global and local options, short and long flags, positionals (required, optional, repeated), defaults, environment inputs, exit codes, and current help and version behavior. Run the narrowest baseline tests and record preexisting failures.

## 1. lexopt only

`lexopt` is the sole parser. No clap (or derive), structopt, argh, pico-args, custom parser libraries, or ad hoc per-command parsing. Remove Clap dependencies and derives from `Cargo.toml` and `Cargo.lock`.

No glob imports in the CLI: no `use super::*`, `use crate::*`, `use lexopt::prelude::*`. Import the specific metadata, helpers, and lexopt types each module uses, so a reader can see what uses lexopt.

Parse `OsString`/`OsStr`-aware and never lossy-convert arguments. If a downstream contract needs UTF-8, reject a non-UTF-8 value with an explicit parse error; keep opaque command tails and paths as `OsString`.

Support lexopt semantics: long options, short options, short clusters where unambiguous, option values, `--option=value`, `--`, positionals, and unknown-option errors. Make lexopt visibly the parsing boundary:

- construct a `lexopt::Parser` from the argument iterator and consume tokens with `Parser::next`
- consume option values with `Parser::value` (`Parser::values` for a contiguous list the option owns)
- match `lexopt::Arg::Short`, `Arg::Long`, and `Arg::Value` explicitly
- use `Parser::from_args` or `from_iter` in parser tests
- use `Parser::raw_args` only for an intentionally opaque tail after a required `--`, such as a guest command and its arguments

Never replace lexopt with index arithmetic over `Vec<String>`. For a required opaque tail, materialize that command's remaining raw arguments, locate the required `--`, build one new `lexopt::Parser` for the structured prefix (parsed entirely with lexopt), and keep only the post-`--` tail as `OsString`s. Document that boundary instead of hiding it behind a generic second parser.

## 2. main.rs is the sole entrypoint

`src/main.rs` collects `std::env::args_os()`, calls the dispatcher, and converts the result to an exit code. No argument parsing, dispatch, help rendering, or business logic. All behavior flows through one function, adapted to the project:

```rust
pub fn run<I, T>(args: I) -> ExitCode
where
    I: IntoIterator<Item = T>,
    T: Into<OsString>;
```

Multiple binary targets route through the same implementation, or the skipped target is documented with the reason.

## 3. One module per subcommand

```text
src/main.rs
src/cli/
  mod.rs
  command.rs         # shared command/argument metadata
  help.rs            # generated help renderer
  error.rs           # parse and presentation errors
  version.rs         # embedded version information
  <subcommand>.rs    # one per subcommand, nested ones follow the same pattern
build.rs             # if needed for git metadata
```

Each subcommand module owns its typed argument model, parser, command spec, execution function, and focused parser and help tests.

## 4. One declarative schema

Do not maintain separate lists for parser spellings, help text, usage strings, required arguments, defaults, value names, or summaries. Define shared metadata, for example:

```rust
struct CommandSpec {
    name: &'static str,
    description: &'static str,
    options: &'static [OptionSpec],
    positionals: &'static [PositionalSpec],
    subcommands: &'static [&'static CommandSpec],
    examples: &'static [&'static str],
}

struct OptionSpec {
    short: Option<char>,
    long: &'static str,
    value_name: Option<&'static str>,
    required: bool,
    repeatable: bool,
    default: Option<&'static str>,
    env: Option<&'static str>,
    help: &'static str,
}

struct PositionalSpec {
    name: &'static str,
    required: bool,
    repeatable: bool,
    help: &'static str,
}
```

The exact types may differ, but these invariants hold:

- every command has a spec, every option spelling comes from a spec, and every positional is described
- every option and positional has a non-empty explanation, and every command has exactly one non-empty canonical description (no summary plus long description for the same command)
- names are unique within their scope, and short and long collisions are rejected by tests or construction
- usage lines and help output are rendered from metadata, never hand-written; no separate `FOO_HELP` constants or multi-line help strings

The same schema drives lexopt token recognition, validation, usage, command help, complete top-level help, and the metadata tests. Use option-matching helpers that consume `OptionSpec` values, so spellings are not repeated as string literals in parsers, and tie dispatch names to registered `CommandSpec` values.

## 5. Per-command help

`tool command -h` and `--help` (nested commands too) print to stdout, exit successfully, and work before required-argument validation. They show complete usage, every local option and positional with defaults, value names, required and repeated status, environment inputs, nested subcommands, and examples when provided. All of it is generated from the spec.

## 6. Top-level help

`tool -h` and `--help` expose the complete CLI surface, deterministically ordered: full usage, common options shown once, and one generated command reference containing every command and nested command with usage, canonical description, options, positionals, defaults, value names, and required and repeated markers. No short `Commands:` index followed by duplicated descriptions, and no concatenated standalone pages. The root is a compact reference; `tool command --help` is the detailed page with examples. Command blocks list only their own options with one note that common options are inherited, while a standalone command page shows the full set including inherited ones. The reference is rendered recursively from the schema, with no second hand-written top-level document. Target shape:

```text
tool: Local worlds for the development environment.

Usage: tool [OPTIONS] <COMMAND>

Common options (shown once; command pages show placement):
  -f, --file PATH              Select the authored world file (default: world.toml)
  -h, --help                   Print the complete CLI reference
  -v, --version                Print the package version and Git commit

Every command also accepts -h/--help and -v/--version.

Command reference:

  tool check [OPTIONS]
    Validate the authored world without changing it.

  tool run [OPTIONS] MACHINE
    Run the selected machine in the foreground.
    Options:
      --env NAME=VALUE              Add an environment variable (repeatable)
    Arguments:
      MACHINE                       Logical machine name

  tool exec [OPTIONS] MACHINE -- COMMAND [ARG ...]
    Execute an opaque command tail through one machine.
    Options:
      --secret-env GUEST=HOST_ENV   Pass one selected host variable (repeatable)
    Arguments:
      MACHINE                       Logical machine name
      COMMAND [ARG ...]             Command and arguments after `--`
```

## 7. `-v` / `--version` with a compile-time git SHA

Output includes the package version and the short git SHA embedded at build time, for example `tool 1.4.0 (git abc123456789)`. Never execute git at runtime. If `-v` already means something else in the existing CLI, keep that meaning, provide only `--version`, and report the conflict. If there is no build script, add one that obtains the short SHA and emits a Cargo rustc environment variable, then embed it:

```rust
pub const VERSION: &str = concat!(
    env!("CARGO_PKG_VERSION"),
    " (git ",
    env!("SMOLCLI_GIT_SHA"),
    ")"
);
```

Define and document the policy for builds outside a Git checkout. Never silently emit an unknown value or omit the SHA. An explicit build-environment override for release archives must still be a non-empty compile-time SHA. Validate that the value is a hexadecimal short SHA, and reject labels such as `unknown` or `dirty`. Add Cargo rerun directives for Git metadata, resolving the real git directory with `git rev-parse --git-dir`, because `.git` is a file in a worktree.

## 8. Typed errors

Use typed errors for unknown commands, unknown options, missing option values, invalid option values, missing required positionals, unexpected positionals, and duplicate non-repeatable options. Parse errors go to stderr with a nonzero exit, identify the command or argument, and include concise usage when useful. Help and version are successful early exits. User input never panics. Preserve existing runtime error and exit-code semantics. Define global-option placement rules, preserve existing behavior where possible, and document intentional changes.

## 9. Tests

Test the observable contract: every command's parser and its `-h` and `--help`; top-level help, including the compact shape and the absence of a duplicate command index; `-v` and `--version`; the embedded SHA; unknown commands and options; missing and invalid values; required positionals; optional and repeated values; `--`; short clusters; `--option=value`; the `Arg::Short`, `Arg::Long`, and `Arg::Value` paths; opaque post-`--` tails preserved without option reinterpretation; non-UTF-8 arguments where relevant; nested commands; and deterministic help ordering.

Metadata tests fail when an option or positional has no explanation, a command has no description, an option name collides with another, a command is missing from the registered tree, a usage or help string is manually duplicated, or a parser repeats an option spelling instead of matching its `OptionSpec`. Prefer stable string assertions or the project's existing snapshot convention; add no snapshot dependency unless necessary.

## 10. Keep the migration coherent

No business logic changes, no unrelated dependencies or refactors. Update README and docs so the documented CLI matches generated help. Verify with the compiler and focused tests, classify every remaining exception, widen checks only where the boundary warrants it, and separate preexisting failures from regressions.

Done when lexopt is the only parser with no Clap remaining, no glob imports exist under `src/cli`, `src/main.rs` is only the entrypoint, each subcommand has its own `src/cli/<subcommand>.rs` module and spec, parsing and help share one schema, every flag and positional is explained, every command supports `-h`/`--help`, top-level help is one recursive reference, `--version` carries the compile-time SHA, output is deterministic, parser and metadata tests exist, behavior is preserved, and the project compiles and passes its tests.

**The principle:** one command schema drives parsing, validation, and help while the lexopt boundary stays explicit in the source.
