# Updating macos-lean scripts across macOS versions

How to correctly audit and update a launchd service-disabling script when
moving to a new macOS release. Written after updating from Sequoia (15) to
Tahoe (26), where several assumptions broke.

## The core problem

Apple can change three things independently between releases:

1. **Plist filename** — the file in `/System/Library/Launch{Agents,Daemons}/`
2. **Label** — the `Label` key inside the plist (what `launchctl` uses)
3. **Existence** — the service may be added, removed, or split

On Sequoia, filenames and labels were generally identical. On Tahoe, Apple
diverged them in several cases:

| Plist filename | Actual Label |
|---|---|
| `com.apple.corespeechd.system.plist` | `com.apple.corespeechd_system` |
| `com.apple.findmymac.plist` | `com.apple.findmymacd` |
| `com.apple.mDNSResponder.plist` | `com.apple.mDNSResponder.reloaded` |
| `com.apple.CommCenter-osx.plist` | `com.apple.CommCenter` |
| `com.apple.Maps.pushdaemon.plist` | `com.apple.Maps.mapspushd` |
| `com.apple.imtransferagent.plist` | `com.apple.imcore.imtransferagent` |
| `com.apple.MENotificationAgent.plist` | `com.apple.MENotificationService` |
| `com.apple.macos.studentd.plist` | `com.apple.studentd` |
| `com.apple.sidecar-hid-relay.plist` | `com.apple.sidecar-display-agent` |
| `com.apple.avconferenced.plist` | `com.apple.videoconference.camera` |

The last one is dangerous: `avconferenced.plist` contains the label
`videoconference.camera`, which is the Mac's camera service. A script that
targets `com.apple.avconferenced` is a harmless no-op (wrong label), but if
you "fix" it by looking up what plist that label lives in, you'll disable the
camera.

`launchctl disable` and `launchctl bootout` operate on **labels**, not
filenames. Using a filename as a label is a silent no-op — no error, no
effect.

## The right workflow

### Step 1: Build a label→filename index

Extract the canonical label from every plist on the system:

```sh
for f in /System/Library/LaunchAgents/*.plist; do
  label=$(plutil -extract Label raw "$f" 2>/dev/null) && \
    printf '%s\t%s\n' "$label" "$f"
done > /tmp/user-agent-labels.tsv

for f in /System/Library/LaunchDaemons/*.plist; do
  label=$(sudo plutil -extract Label raw "$f" 2>/dev/null) && \
    printf '%s\t%s\n' "$label" "$f"
done > /tmp/system-daemon-labels.tsv
```

Also include `/Library/LaunchAgents/` and `/Library/LaunchDaemons/` for
third-party services.

### Step 2: Extract effective labels from your existing script

```sh
# Use the script's own --dry-run output so variable-expanded labels are included.
# This catches cases like:
#   disable_system "$CORESPEECH_SYSTEM_LABEL"
#   disable_user "${FACETIME_AGENT_LABEL}"
# and third-party labels such as io.kandji.Kandji.
./macos-lean.sh --dry-run \
  | rg -o '(com|io)\.[A-Za-z0-9._-]+' \
  | sort -u > /tmp/script-labels.txt
```

If your script has labels that only appear outside `--dry-run`, extract those
separately. The goal is the **effective** label list, not just literal strings
present in source.

### Step 3: Find dead labels

```sh
comm -23 /tmp/script-labels.txt \
  <(cut -f1 /tmp/user-agent-labels.tsv /tmp/system-daemon-labels.tsv | sort -u)
```

Every line of output is a label your script targets that doesn't exist on the
new OS. These are silent no-ops — not errors, just wasted lines.

### Step 4: Find new services worth disabling

```sh
# All real labels not in the script
comm -23 \
  <(cut -f1 /tmp/user-agent-labels.tsv /tmp/system-daemon-labels.tsv | sort -u) \
  /tmp/script-labels.txt \
  | rg -i '(intellig|siri|analytic|telemetry|biome|trial|diagnos|ml|track|game|find.?my|screen.?time|health|news|weather)' \
  | sort
```

Adjust the pattern to match your disable categories.

### Step 5: Verify labels you want to preserve

For every `ensure_user`/`ensure_system` call (services you want to keep
running), confirm the label is still correct:

```sh
plutil -extract Label raw /System/Library/LaunchAgents/com.apple.avconferenced.plist
# Should print: com.apple.videoconference.camera
```

This catches the `avconferenced` → `videoconference.camera` class of bug.

### Step 6: Check for removed APIs

Some `tmutil`, `pmset`, `networksetup`, and `defaults` verbs/keys change
between releases. Test each one:

```sh
tmutil disablelocal 2>&1  # "Unrecognized verb" on Tahoe
```

## Traps

### Trap 1: filename ≠ label

Already covered above. **Never assume the plist filename is the label.**
Always `plutil -extract Label raw`.

### Trap 2: `launchctl print-disabled` shows stale entries

```sh
launchctl print-disabled gui/$(id -u) | rg imtransfer
# "com.apple.imtransferservices.IMTransferAgent" => disabled
```

This shows entries you've disabled in the past, even if the label no longer
exists. It proves nothing about what labels are currently valid. Don't use it
as a source of truth for label names.

### Trap 3: `fd`/`find` by filename confirms existence, not correctness

```sh
fd -e plist avconferenced /System/Library/LaunchAgents
# /System/Library/LaunchAgents/com.apple.avconferenced.plist
```

The file exists — but its label is `videoconference.camera`. Finding the plist
file only tells you Apple ships it; it says nothing about what label
`launchctl` will accept.

### Trap 4: some labels are dangerous to disable

Before disabling a new label, check what it actually does. The name is not
always obvious:

- `avconferenced` → camera (not FaceTime)
- `videoconference.camera` → also camera (name matches, but lives in
  `avconferenced.plist`)
- `facetimemessagestored` → FaceTime (the actual FaceTime service on Tahoe)

When in doubt, read the plist's `ProgramArguments` to see what binary it
launches, or check `launchctl print gui/$(id -u)/com.apple.LABEL` for a
running service's description.

### Trap 5: `|| true` masks failures

Every `launchctl bootout ... || true` silently eats errors, including "no such
label." Your script will report success even if it targeted the wrong label.
Consider logging failures:

```sh
launchctl bootout "gui/${UID}/com.apple.foo" 2>/dev/null || echo "  (not loaded)"
```

## Verification

After all edits, run a full label audit.

These snippets assume a shell with process substitution and brace expansion
such as `bash` or `zsh`, not strict POSIX `sh`:

```bash
# Build real-label index
bash -c '
for f in /System/Library/Launch{Agents,Daemons}/*.plist \
         /Library/Launch{Agents,Daemons}/*.plist; do
  [ -f "$f" ] && plutil -extract Label raw "$f" 2>/dev/null
done
' | sort -u > /tmp/all-real-labels.txt

# Extract effective script labels
./macos-lean-tahoe.sh --dry-run \
  | rg -o '(com|io)\.[A-Za-z0-9._-]+' \
  | sort -u > /tmp/script-labels.txt

# Show mismatches
comm -23 /tmp/script-labels.txt /tmp/all-real-labels.txt
# Empty output = all labels valid
```

Run `dash -n macos-lean-tahoe.sh` for syntax, and `--dry-run` to review the
full list before applying.

## macOS 27 (Golden Gate) readiness — macos-lean.sh

`macos-lean.sh` is the canonical script; the versioned scripts are frozen.
It was built while still on Tahoe (27 labels unverifiable without booting
27), so it contains **no hardcoded 27-only labels**. Instead it is
version-tolerant:

- Every label is validated against a live index (cached per OS build in
  `/tmp/macos-lean-index-<build>.txt`). Unknown labels print `STALE` and
  are skipped in apply mode — never silent no-ops. Revert still attempts
  them, to clear orphaned `disabled.plist` entries from older releases.
- `--audit` runs the Steps 3–5 workflow built in: stale targets, stale
  preserve checks, and candidate new services. No sudo, no changes.
- Apply snapshots `print-disabled` state to `~/.local/state/macos-lean/`.
- Fixed dead check: `com.apple.Passwords.MenuBarExtra` is a LoginItem, not
  a launchd job — removed from preserve checks.
- Added from Tahoe `--audit` findings: `InstallerDiagnostics.installerdiagd`
  and `installerdiagwatcher` (installer telemetry, system daemons).

### Trap 6: sort/comm locale must agree

`comm` compares using the current locale, so files sorted under different
collations produce false uniques. The first `--audit` mixed a `LC_ALL=C`
sort with a locale-aware `comm` and reported dozens of bogus STALE/NEW
lines. Rule: force one locale for the whole pipeline (`export LC_ALL=C`),
or at minimum sort both inputs and run `comm` under the same one.

### Tahoe audit dispositions (keep-list, do not disable)

- `backgroundtaskmanagement.agent` / `backgroundtaskmanagementd` — Login
  Items infrastructure and background-task consent; 27's Background App
  Activity UI sits on top. Disabling breaks login items.
- `sysdiagnose` / `sysdiagnose_agent` / `sysdiagnose_helper` — on-demand
  manual diagnostic collection. Keep; you want it when things break.

### After upgrading to 27

1. `./macos-lean.sh --audit` — review STALE and NEW? lines.
2. For each NEW? label, read the plist's `ProgramArguments` before touching
   it (names lie — see Trap 4).
3. `./macos-lean.sh --dry-run`, then apply, then reboot.
4. Manual 27 items no script can cover: Settings > General > Login Items &
   Extensions > Background App Activity; MDM restriction profiles for Siri /
   Apple Intelligence policy (survive upgrades, unlike `disabled.plist`).
