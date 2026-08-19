You are refactoring an existing Rust CLI into a mature, explicit command-line design.

First inspect the repository before editing:

- Read Cargo.toml, Cargo.lock, src/main.rs, src/lib.rs if present, all CLI-related modules, tests, README/docs, build scripts, and every current argument consumer.
- Inventory the complete existing CLI surface:
  - executable name
  - subcommands and nested subcommands
  - aliases
  - global options
  - command-local options
  - short and long flags
  - positional arguments
  - required/optional/repeated values
  - defaults
  - environment-variable inputs
  - exit-code behavior
  - existing help/version behavior
- Run the narrowest useful baseline tests before changing code.
- Preserve existing command semantics unless this request explicitly changes them.

## Non-negotiable design

### 1. Use lexopt exclusively

Use `lexopt` as the only argument-parser dependency.

Do not use:

- clap
- clap derive
- structopt
- argh
- pico-args
- custom parser libraries
- ad hoc parsing in individual commands

Remove obsolete Clap dependencies and derives from Cargo.toml and Cargo.lock.

Do not use glob imports anywhere in the CLI implementation. In particular, do
not use `use super::*`, `use crate::*`, or `use lexopt::prelude::*`. Import the
specific command metadata, helpers, and lexopt types each module uses. This is
intentional: a reader should be able to see which code is using lexopt and
which shared contracts a command depends on.

Use `OsString`/`OsStr`-aware parsing. Do not lossy-convert command-line arguments to UTF-8 merely for convenience.
If a downstream domain contract genuinely requires UTF-8, reject a non-UTF-8
value explicitly with a parse error; preserve opaque command tails and paths as
`OsString` values.

Support the normal lexopt semantics for:

- long options
- short options
- short-option clusters where unambiguous
- options with values
- `--option=value`
- `--`
- positional arguments
- unknown-option errors

The implementation must visibly use lexopt as the parsing boundary:

- construct a `lexopt::Parser` from the argument iterator
- consume tokens with `Parser::next`
- consume option values with `Parser::value` (or `Parser::values` when the
  option intentionally owns a contiguous value list)
- match `lexopt::Arg::Short`, `Arg::Long`, and `Arg::Value` explicitly
- use `Parser::from_args`/`from_iter` in focused parser tests
- use `Parser::raw_args` only for an intentionally opaque tail after a
  required `--` separator, such as a guest command and its arguments

Do not replace lexopt with manual index arithmetic over `Vec<String>`. If a
command has a required opaque tail, it is acceptable to materialize that
command's remaining raw arguments, locate the required `--` boundary, and
construct one new `lexopt::Parser` for the isolated structured prefix. That
prefix must still be parsed entirely with lexopt; preserve only the post-`--`
tail as `OsString` values. Document this boundary rather than hiding it behind
a generic second parser.

### 2. src/main.rs is the sole CLI entrypoint

`src/main.rs` must contain only binary entrypoint responsibilities:

- collect `std::env::args_os()`
- call the CLI dispatcher
- convert the result into the process exit code

No argument parsing, command dispatch logic, help rendering, or business logic may live in `main.rs`.

All CLI behavior must flow through a single function such as:

```rust
pub fn run<I, T>(args: I) -> ExitCode
where
    I: IntoIterator<Item = T>,
    T: Into<OsString>;
```

Adapt the exact signature to the project’s architecture, but keep parsing centralized.

If the repository has multiple binary targets, route them through the same CLI implementation or clearly document why another target is not part of this CLI.

### 3. Split subcommands into modules

Use this general structure:

```text
src/main.rs
src/cli/
  mod.rs
  command.rs         # shared command/argument metadata
  help.rs            # generated help renderer
  error.rs           # parse and presentation errors
  version.rs         # embedded version information
  <subcommand>.rs
  <another-command>.rs
build.rs             # if needed for git metadata
```

Each subcommand must have its own module:

```text
src/cli/run.rs
src/cli/check.rs
src/cli/status.rs
```

Each subcommand module owns:

- its typed argument model
- its parser
- its command metadata/specification
- its command execution function
- focused parser/help tests

Nested subcommands should follow the same pattern.

### 4. Create one declarative command schema

Do not maintain separate lists for:

- parser spellings
- help text
- usage strings
- required arguments
- defaults
- value names
- command summaries

Define a shared metadata model, for example:

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

The exact types may differ, but the design must satisfy these invariants:

- every command has a specification
- every option spelling comes from the specification
- every positional argument is described in the specification
- every option and positional argument has a non-empty brief explanation
- every command has one non-empty canonical description; do not maintain both
  a summary and a long description for the same command
- names are unique within their scope
- short/long collisions are rejected by tests or construction
- usage lines are rendered from metadata rather than manually duplicated
- help output is rendered from metadata rather than hardcoded help blobs

Descriptions are necessarily textual data, but they must live in the command schema and be rendered from it. Do not create separate `FOO_HELP` constants or hand-maintained multi-line help strings.

The same schema must drive:

1. lexopt token recognition
2. argument validation
3. usage generation
4. command help
5. complete top-level help
6. metadata invariant tests

Use explicit option-matching helpers that consume `OptionSpec` values so option
spellings are not repeated as string literals in command parsers. Keep command
dispatch names tied to the registered `CommandSpec` values as well.

### 5. Every command gets its own help

Every command and nested command must support:

```text
tool command -h
tool command --help
```

Help must:

- print to stdout
- exit successfully
- work before required-argument validation
- show the command’s complete usage
- show all local options
- show all positional arguments
- show defaults, value names, required/repeated status, and environment inputs where relevant
- show nested subcommands if applicable
- show examples when provided

`-h` and `--help` must be generated from the command specification, not implemented as special hardcoded text.

### 6. Top-level help must describe the entire CLI

The following must expose the complete CLI surface:

```text
tool -h
tool --help
```

Do not print only a short subcommand list.

Top-level help must include, in deterministic order:

- full executable usage
- global/common options, shown once
- one generated command reference containing every command and nested command
- each command’s usage, canonical description, options, positional arguments,
  defaults, value names, and required/repeated markers

Do not print a short `Commands:` index followed by a second copy of the same
descriptions. Do not concatenate complete standalone command pages. The root
view should be a compact reference, while `tool command --help` remains the
detailed page with examples and any command-specific narrative.

Show inherited/common options once at the root. Command blocks should list only
their command-specific options, with one note explaining that common options
are inherited. A standalone command page must still show the complete option
set, including inherited options.

For example, a readable generated root view should have this shape:

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

The command reference must be rendered recursively from the shared schema. A
user must be able to understand the complete command surface from this one
invocation without repeatedly calling `--help` on every subcommand. Do not
maintain a second hand-written top-level help document.

### 7. Add -v/--version with compile-time git SHA

Implement:

```text
tool -v
tool --version
```

The version output must include:

- the package version
- the git short SHA embedded at build time

Example shape:

```text
tool 1.4.0 (git abc123456789)
```

Do not execute git at runtime.

If the project has no build script, add one that obtains the short SHA and emits a Cargo rustc environment variable, then embed it with `env!` or `concat!`.

For example, the resulting code may use:

```rust
pub const VERSION: &str = concat!(
    env!("CARGO_PKG_VERSION"),
    " (git ",
    env!("SMOLCLI_GIT_SHA"),
    ")"
);
```

Use a clear, documented policy when building outside a Git checkout. Do not silently emit an unknown value or omit the SHA. If an explicit build-environment override is necessary for release archives, it must still be a non-empty compile-time SHA value.
Validate that the embedded value has the expected hexadecimal short-SHA shape;
do not accept arbitrary labels such as `unknown` or `dirty` in its place.

Add appropriate Cargo rerun directives for Git metadata.

### 8. Define predictable error behavior

Use typed errors for:

- unknown commands
- unknown options
- missing option values
- invalid option values
- missing required positionals
- unexpected positionals
- duplicate non-repeatable options

Requirements:

- parse errors go to stderr
- parse errors use a nonzero exit code
- errors identify the relevant command/argument
- errors include concise usage guidance when useful
- help and version are successful early exits
- avoid panics for user input
- preserve existing runtime error and exit-code semantics

Global options must have clearly defined placement rules. Preserve existing behavior where possible and document any intentional change.

### 9. Test the observable contract

Add focused tests covering:

- every command’s parser
- every command’s `-h` and `--help`
- top-level complete help, including the compact reference shape and the
  absence of a duplicate command index
- `-v` and `--version`
- embedded git SHA presence
- unknown commands/options
- missing values
- invalid values
- required positionals
- optional and repeated values
- `--`
- short-option clusters
- `--option=value`
- `lexopt::Arg::Short`, `Arg::Long`, and `Arg::Value` paths
- opaque post-`--` tails preserved without option reinterpretation
- non-UTF-8 arguments where relevant
- nested commands
- deterministic help ordering

Add metadata invariant tests that fail if:

- an option has no explanation
- a positional has no explanation
- a command has no description
- an option name collides with another option
- a command is omitted from the registered command tree
- a manually duplicated usage/help string is introduced
- a command parser repeats an option spelling instead of matching its
  `OptionSpec`

Prefer stable string assertions or existing project snapshot conventions. Do not add a snapshot dependency unless necessary.

### 10. Keep the migration coherent

Do not change business logic while migrating the parser.

Preserve:

- command names
- existing valid invocations
- aliases, unless intentionally removed and documented
- defaults
- environment-variable behavior
- output formats
- exit codes
- side effects

Update relevant README/docs so the documented CLI matches generated help.

Do not introduce unrelated dependencies or unrelated refactors.

## Acceptance criteria

The refactor is complete only when all of the following are true:

- `lexopt` is the only CLI parser.
- CLI modules use explicit imports; no `use super::*`, `use crate::*`, or
  `use lexopt::prelude::*` remains under `src/cli`.
- No Clap parser, derive, or help definition remains.
- `src/main.rs` is only the binary entrypoint.
- Every subcommand has its own `src/cli/<subcommand>.rs` module.
- Every command has a shared metadata specification.
- Parser behavior and help rendering use the same metadata.
- Every flag and positional argument has a brief explanation.
- Every command supports `-h` and `--help`.
- Top-level `-h`/`--help` prints the complete recursive CLI surface.
- Top-level help is one readable generated command reference, not a short
  command index plus duplicated command pages.
- `-v`/`--version` includes the package version and compile-time git short SHA.
- Help and version output are deterministic.
- Focused tests cover the parser contract and metadata invariants.
- Existing behavior is preserved unless explicitly changed.
- The project compiles and its relevant tests pass.

The architectural principle I would insist on is: **one command schema, three
consumers—parsing, validation, and help rendering**. The second principle is
that the lexopt boundary should remain visible in the source: explicit imports,
explicit `Arg` matching, and no manual parser hidden behind generic helpers.
That is what makes the lexopt design mature rather than merely lightweight.
