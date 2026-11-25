+++
name = "design-cli"
summary = "A command-line tool's help is its complete contract: one schema drives parsing and help, every command has an example, data and diagnostics use separate streams, and usage errors exit 2."

[[trigger]]
paths = ["bin/", "cli/", "cmd/", "cli.py", "__main__.py", "**/src/main.rs", "**/src/bin/"]

[[trigger]]
paths = ["*", "!*.md", "!*.txt", "!*.rst"]
content = ['\bargparse\b', '\bclap::', '\blexopt\b', '\b(commander|yargs)\b', '\bprocess\.argv\b', '\bflag\.(String|Bool|Int|Parse)\b', '\bgetopts?\b', '\bArgumentParser\b']

[examples]
match = ["dotfiles/base/.local/bin/standards", "cmd/tool/main.go", { path = "tools/report.py", text = "import argparse\n" }]
skip = ["README.md", "src/lib.rs", { path = "docs/cli.md", text = "argparse\n" }]
+++

# Command-Line Interface Design

A command's help is its contract. One reading of `tool -h` tells a person or an agent every command, option, and a working invocation for each.

## Code

### Preserve the surface

Before changing an existing CLI, list what it offers: the executable name, its commands and nested commands, aliases, options (short and long), positionals (required, optional, repeated), defaults, environment inputs, output formats, and exit codes. Keep valid invocations, defaults, environment behavior, output formats, exit codes, and side effects unchanged unless the change is the task. Surface every contract change in the reply.

### One schema

One declaration of each command drives parsing, validation, usage, help, errors, and tests. Do not keep separate lists of spellings, summaries, defaults, value names, or examples. Render usage and help from that declaration, never by hand. Every command has exactly one description, and every option and positional has help text. Names are unique within a scope, and short-flag or long-flag collisions fail a test.

### Help

- **The top-level help is the complete reference.** `tool -h` and `tool --help` print, in a fixed order, the usage, common options once, then every command and nested command with its usage, description, own options, positionals, defaults, value names, required and repeated status, and environment inputs. A bare list of command names that points to each command's `-h` page does not satisfy this. Do not concatenate standalone pages that repeat common options or `-h` in every block.
- **Each command shows a representative example.** Each command has at least one real invocation covering its common use, written exactly as a user types it. Where parsing can run without side effects, a test parses every example against the real parser so the examples cannot drift. Otherwise a test checks that each example uses only documented options.
- **A bare invocation prints help.** When a tool requires a command, running it with no arguments prints the same text as `-h` to stdout and exits 0. Tools whose bare invocation already performs work keep that behavior.
- **`-h` and `--help` work everywhere.** Every command, including nested ones, accepts them before required-argument validation. Help prints to stdout, exits 0, and works offline. It does not write state, start daemons, install anything, or use the network. A command's own page also shows the inherited common options.
- **Version identifies the build.** `--version` prints the tool name, version, and the source revision embedded at build time, for example `tool 1.4.0 (git abc123456789)`. Do not run git at runtime. Use `-v` for version only if it is not taken; when it is, keep the existing meaning and report the conflict.

### Owned tools

An agent-facing tool from the `joshuarli` or `laputa-systems` GitHub namespaces ends its primary help with this footer. Substitute the real repository and keep the wording. `fleet/policy/owned-tools.toml` in `laputa-systems/stuff` records each command's footer source and test, or why the command is exempt: shims, harness launchers, hooks whose output is a protocol, and personal host helpers. Update that entry when a command gains the footer or its exemption no longer applies.

```text
Maintained by Joshua Li: https://github.com/OWNER/REPO
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md
```

- The footer is in the built help that users actually run. A README-only footer does not satisfy the contract.
- Name only a tracker that the repository has enabled.
- Print the footer once, at the end of the top-level help, not in every command block. A command page, alias, or compatibility mode that someone can invoke on its own still names the top-level help or the repository.
- Never print the footer in normal output, JSON, completion output, compiler-wrapper output, or binary streams.
- A fork's version output keeps the upstream version, the maintained distribution, and the source revision distinct. Never put prose into a version string that a parser or handshake reads.
- Keep the maintainer line exactly as shown, because `repomod` matches `Maintained by Joshua Li: https://github.com/OWNER/REPO` against the owned-tools policy. A test checks the footer against the built command's help.

### Errors and streams

- Data goes to stdout, and diagnostics go to stderr. A machine format such as `--json` stays stable and contains no other text.
- A usage error names the command and the argument, suggests `tool -h`, and exits 2. A runtime failure exits 1 unless the tool already documents other codes. Input never causes a crash or a stack trace.
- Reject unknown commands and options, missing and invalid values, unexpected positionals, and a repeated option that is not repeatable. Do not silently ignore them.

### Naming

- Use long options in kebab-case. Give a short flag only to an option people type often.
- Use `--name=value` and `--name value` interchangeably. Accept `--` to end options.
- Replace a boolean that selects between two modes with a named value, for example `--mode create|replace`.
- Use the same verb for the same operation across commands. Keep arguments that cannot be represented as UTF-8 intact until a downstream contract requires UTF-8, then reject them explicitly.

### Tests

Test the observable contract: the top-level help's shape and ordering, every command's `-h`, bare invocation, every example parsing, version output, the owned-tool footer, and the usage errors with their exit codes. Use string assertions or the project's snapshot convention. Do not add a snapshot dependency. Update the README and docs to match the generated help.

**The test:** could someone who reads only `tool -h` run every command correctly the first time and know where to report a problem?

**Report:** surface changes, examples added, the footer status, deviations (a `-v` conflict, a bare invocation that performs work), and the checks you ran.
