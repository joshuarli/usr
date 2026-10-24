# `agent-vm`: a disposable coding-agent shell

`agent-vm` is a small macOS wrapper around [smolvm](https://github.com/smol-machines/smolvm). It launches an ephemeral Linux VM with the host's current working directory mounted **read/write at the same absolute path**. A project at `~/d/project` therefore appears at `~/d/project` inside the VM, and shell `$HOME` uses the same path string. The guest home itself is private VM storage, **not** a mount of the host home.

Install smolvm 1.28.1 or newer separately. That release added `--block-private`.

```sh
brew install smol-machines/tap/smolvm
```

After syncing `usr` so `~/.local/bin/agent-vm` is on your `PATH`:

```sh
cd ~/d/project
agent-vm                              # interactive bash; changes to project are live
agent-vm -- npx --yes opencode-ai     # run a coding agent inside the VM
agent-vm --ro ~/d/reference --rw ~/d/other -- bash
agent-vm --offline -- git status
agent-vm --dry-run -- bash           # inspect the full smolvm invocation
```

The default image is `node:24-bookworm` (Node/npm, Git and Bash). Select another with `--image IMAGE`. The VM is deleted after the command exits, so installations and logins *inside the VM* are ephemeral, while changes under authorized host mounts persist. For repeated agent sessions, bake the binaries into an OCI image and pass it with `--image`; this wrapper intentionally does not install packages, retain authentication state, or maintain a background VM.

## Host paths and skills

The current directory is always read/write. Repeat `--rw DIR` or `--ro DIR` for additional directories. Relative paths are resolved on the host against the launch directory; each guest destination uses the corresponding original absolute path. When launching from a symlinked directory, the host source is resolved physically and the guest path retains the logical location. Only directories can be mounted. Overlapping host sources or guest destinations are rejected, even when one is read-only, so an alias cannot silently defeat that permission.

Without mounting your host home, `agent-vm` additionally grants **read-only** access to these *tracked* resources from `~/usr/dotfiles/base`:

- `.agents/skills`: provided in the guest's `~/.agents/skills`, `~/.claude/skills` and `~/.gemini/antigravity-cli/skills` discovery paths.
- `.codex/AGENTS.md`: copied as the canonical `~/.codex/AGENTS.md` and exposed through the Claude, Grok, Muse, OpenCode, Antigravity, DeepSeek and Command Code global-instruction adapters.
- `.claude/agents` and `.grok/agents`: exposed in the corresponding guest home directories.

Pass `--usr DIR` if the repository is not at `~/usr`, or `--no-config` to skip loading these resources. Project-local instructions and skills remain visible in the writable project mount. This does **not** mount host agent caches, saved logins, API keys, SSH sockets, `.gitconfig` or your other dotfiles. It also does not copy harness preferences such as `settings.json` / `config.toml`: those may contain machine-dependent hooks and host paths.

The guest starts as root with `IS_SANDBOX=1` for Claude Code compatibility; Git marks **only the mounted working directory** as safe in its ephemeral global config to avoid the host-UID ownership warning. The guest is a separate Linux environment, not macOS, and host-installed executables are not available there.

## Network and credentials

Networking is enabled by default for coding-agent APIs and package registries, but `--block-private` blocks access to private/LAN, host-loopback, and link-local addresses. For a tighter egress policy, explicitly permit destinations:

```sh
agent-vm --allow-host-pattern api.anthropic.com -- claude
agent-vm --allow-host registry.npmjs.org -- npx --yes opencode-ai
agent-vm --offline -- bash
```

`--allow-host` admits a domain and its subdomains; `--allow-host-pattern` admits an exact hostname or a `*.example.com` pattern. A supplied allowlist restricts other external destinations. `--credential` accepts smolvm's host-side credential binding syntax, without injecting a plaintext key into the guest:

```sh
agent-vm --allow-host-pattern api.anthropic.com \
  --credential anthropic=ANTHROPIC_API_KEY@api.anthropic.com -- claude
```

The corresponding environment variable must exist in the host process. Smolvm's credential substitution applies only to supported HTTPS requests; verify your agent's protocol and login mode. Never forward the real host key or reuse a host login directory as an extra mount.

## Security contract

- The VM can read and **modify every file in the project mount**, including `.env`, Git hooks, build scripts and files that may later execute on macOS. **Do not run an untrusted agent against a repository containing secrets or host-executed persistence surfaces you cannot review.** A VM protects the rest of the host, not the explicitly writable repository.
- A symlink inside a mounted directory is resolved in the *guest filesystem*. An absolute or relative link whose destination is outside all authorized mounts should be dangling or resolve only to guest-private storage, not to the host file. Links to paths inside another authorized mount remain accessible. Hardlinks and copies **inside** an authorized mount are not protected by path isolation.
- The wrapper rejects mounts of the whole home (or its ancestors) and common credential directories, even if requested explicitly. Additional mounts are still grants of authority: review them carefully.
- Guest processes can send readable project content to any network destination allowed by the policy, including the model provider. The VM does not provide data-loss prevention or prevent prompt injection.
- Use `--dry-run` to see precisely what is mounted. No SSH agent forwarding, sockets, plaintext secrets, or automatic host environment passthrough are enabled.

Smolvm and libkrun are part of the trusted computing base. The symlink behavior above depends on their virtiofs implementation: **validate it on your macOS/smolvm version before trusting sensitive host boundaries**. The optional integration test launches a real VM, checks read/write propagation and confirms both absolute and relative links cannot read an unmounted sibling file:

```sh
python3 -I dotfiles/agent-vm-test.py
python3 -I dotfiles/agent-vm-test.py --live    # macOS + installed smolvm; pulls alpine
```

The wrapper tests cover arguments, collision rejection, and guest config bootstrap. A real macOS/smolvm run is still required to verify hypervisor isolation; passing argument checks does not prove that boundary.
