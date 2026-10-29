# Manage macOS preferences

Use `macos` to find preference changes, select portable values, compare them with the current Mac, and apply them.

## Capture preference changes

Create two private snapshots around a change in System Settings:

```sh
mkdir -p .work/macos
chmod 700 .work/macos
./host/macos/macos snapshot .work/macos/before.plist
```

Change a preference in System Settings, then capture another snapshot:

```sh
./host/macos/macos snapshot .work/macos/after.plist
./host/macos/macos diff --snapshots .work/macos/before.plist .work/macos/after.plist
```

The diff prints changed keys without their values. Snapshots contain every domain returned by `defaults domains` and `defaults -currentHost domains`. They can include personal data, so keep them private and out of Git.

## Promote selected preferences

Promote only keys you want to manage across Macs. The command updates the manifest at `host/macos/preferences.plist`:

```sh
./host/macos/macos promote .work/macos/after.plist host/macos/preferences.plist \
  --select=-g:InitialKeyRepeat \
  --select=com.apple.dock:autohide-delay
```

`-g` selects the global user domain. Each `--select` names one top-level key that appears in the snapshot. Promotion reads only user preferences. Current-host preferences stay in snapshots and do not enter the portable manifest.

Promotion copies selected values as-is; review the manifest for personal paths, account data, and device identifiers before checking it in.

## Compare and apply the manifest

Compare the manifest with the current Mac, then preview its changes:

```sh
./host/macos/macos diff --live host/macos/preferences.plist
./host/macos/macos apply host/macos/preferences.plist --dry-run
```

Pass `--restart` with each affected application's bundle ID. The command quits running apps before applying preferences, then reopens them. macOS may ask you to save unsaved work.

```sh
./host/macos/macos apply host/macos/preferences.plist \
  --backup .work/macos/pre-apply.plist \
  --restart com.apple.dock
```

`--backup` creates a private file and refuses to overwrite an existing path. Preview the rollback, then restore the changed top-level keys:

```sh
./host/macos/macos rollback .work/macos/pre-apply.plist --dry-run
./host/macos/macos rollback .work/macos/pre-apply.plist --restart com.apple.dock
```

Apply merges managed dictionary values into the current domain, preserves other keys, writes only changed domains, and verifies each write. Rollback restores only top-level keys that changed during that apply. An affected app can overwrite preferences if it stays open.

## Limits

`macos` manages values exposed through the `defaults` command. It does not capture or restore privacy permissions, Keychain data, power settings, network configuration, login items, or device-specific state outside the defaults domains.
