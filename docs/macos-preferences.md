# Manage macOS preferences

Use `macos` to find preference changes, select portable values, compare them with the current Mac, and apply them.

## Capture preference changes

Create two private snapshots around a change in System Settings:

```sh
mkdir -p .work/macos
chmod 700 .work/macos
./macos/macos snapshot .work/macos/before.plist
```

Change a preference in System Settings, then capture another snapshot:

```sh
./macos/macos snapshot .work/macos/after.plist
./macos/macos diff --snapshots .work/macos/before.plist .work/macos/after.plist
```

The diff prints changed keys without their values. Snapshots contain every domain returned by `defaults domains` and `defaults -currentHost domains`. They can include personal data, so keep them private and out of Git.

## Promote selected preferences

Promote only keys you want to manage across Macs. The command updates the manifest at `macos/preferences.plist`:

```sh
./macos/macos promote .work/macos/after.plist macos/preferences.plist \
  --select=-g:InitialKeyRepeat \
  --select=com.apple.dock:autohide-delay
```

`-g` selects the global user domain. Each `--select` names one top-level key that appears in the snapshot. Promotion reads only user preferences. Current-host preferences stay in snapshots and do not enter the portable manifest.

## Compare and apply the manifest

Compare the manifest with the current Mac, then preview its changes:

```sh
./macos/macos diff --live macos/preferences.plist
./macos/macos apply macos/preferences.plist --dry-run
```

Pass `--restart` with each affected application's bundle ID. The command gracefully quits running apps before applying preferences, then reopens them. If an app has unsaved work, macOS may ask you to save it or let the terminal control the app.

```sh
./macos/macos apply macos/preferences.plist \
  --backup .work/macos/pre-apply.plist \
  --restart com.apple.dock
```

`--backup` creates a private file and refuses to overwrite an existing path. Preview the rollback, then restore the changed top-level keys:

```sh
./macos/macos rollback .work/macos/pre-apply.plist --dry-run
./macos/macos rollback .work/macos/pre-apply.plist --restart com.apple.dock
```

Apply merges managed dictionary values into the current domain, preserves other keys, writes only changed domains, and verifies each write. Rollback restores only top-level keys that changed during that apply. Use `--restart` only for applications affected by the selected preferences. macOS may overwrite preference changes if an affected application stays open.

## Limits

`macos` manages values exposed through the `defaults` command. It does not capture or restore privacy permissions, Keychain data, power settings, network configuration, login items, or device-specific state outside the defaults domains. The tool uses only the Python standard library.
