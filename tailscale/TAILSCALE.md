# Tailscale security hardening runbook

Use this runbook to review and harden an owner-managed tailnet from a trusted Mac. It records the settings applied to this tailnet and the checks still pending.

Threat assumption: a compromised or stale node could try to join the tailnet or reach other devices. The assets are the tailnet devices and services reachable through them.

## Prepare a safe maintenance session

1. Set the CLI path for this Mac:

   ```sh
   TAILSCALE_CLI=/Applications/Tailscale.app/Contents/MacOS/Tailscale
   ```

2. Check the current CLI version and supported commands:

   ```sh
   "$TAILSCALE_CLI" version
   "$TAILSCALE_CLI" --help
   "$TAILSCALE_CLI" set --help
   "$TAILSCALE_CLI" lock --help
   ```

3. Confirm your current SSH path to every remote host before changing its settings. Keep a separate recovery path available.

   Never stop or restart `tailscaled` over Tailscale SSH on that same device. The daemon restart drops the SSH session before the command can confirm recovery. Use a local console or a separate management path, and verify it works before restarting the daemon.

4. Record required inbound connections before enabling shields-up or changing SSH settings. Both can interrupt access.

## Inspect the current tailnet

Run these read-only checks on the Mac:

```sh
"$TAILSCALE_CLI" status
"$TAILSCALE_CLI" get --json
"$TAILSCALE_CLI" status --json
"$TAILSCALE_CLI" whoami
"$TAILSCALE_CLI" ip -4
"$TAILSCALE_CLI" ip -6
"$TAILSCALE_CLI" serve status --json
"$TAILSCALE_CLI" funnel status --json
"$TAILSCALE_CLI" exit-node list
"$TAILSCALE_CLI" dns status
"$TAILSCALE_CLI" syspolicy list
"$TAILSCALE_CLI" lock status
"$TAILSCALE_CLI" lock log
```

Check which nodes are online, which routes they advertise, whether any exit nodes or public services are configured, and whether Tailnet Lock is enabled. Check every online node before changing remote preferences.

## Disable unused route acceptance and enable updates

Disable route acceptance when this device does not need subnet routes:

```sh
"$TAILSCALE_CLI" set --accept-routes=false
```

Enable automatic updates on each online CLI-managed device:

```sh
"$TAILSCALE_CLI" set --auto-update=true
```

For a remote Linux node, use its verified SSH path:

```sh
ssh root@<node> '/usr/bin/tailscale set --auto-update=true'
```

Replace `<node>` with the actual host name before running the command.

Check the changed settings with `tailscale get --json` where supported. On older clients without `get`, use `tailscale debug prefs` and confirm `AutoUpdate.Apply` is `true`. Auto-update support depends on the operating system and installation method. See [Tailscale update guidance](https://tailscale.com/kb/1067/update).

Do not enable shields-up without confirming that the device needs no inbound tailnet connections. Do not change SSH preferences until you know whether the device uses Tailscale SSH, OpenSSH over Tailscale, or both.

## Enable or verify Tailnet Lock

Tailnet Lock setup requires at least two signing nodes. A signer can authorize new node keys and changes to the trusted signer list. Trust only devices you are willing to grant those powers. Confirm each signer is under your control and reachable. Collect its key using `tailscale lock status` on that node.

Initialize once, using the trusted public keys and the keys for every intended signer:

```sh
"$TAILSCALE_CLI" lock init --gen-disablements 2 --gen-disablement-for-support \
  <mac-tlpub-key> <threadripper-tlpub-key> <oracle-tlpub-key>
```

Store both disablement secrets in separate secure locations when the command prints them. They are not recoverable from this file. Verify Tailnet Lock on every online node:

```sh
"$TAILSCALE_CLI" lock status
"$TAILSCALE_CLI" lock log
"$TAILSCALE_CLI" ping --c=1 <remote-node>
```

Run `tailscale lock status` on each remote node too. A returning unsigned node must be signed by a trusted signer with `tailscale lock sign <node-name-or-id>`.

Tailnet Lock and device approval cannot be enabled at the same time. This tailnet uses Tailnet Lock. Do not enable device approval unless you choose to replace Tailnet Lock after reviewing the tradeoff. See [Tailnet Lock documentation](https://tailscale.com/docs/features/tailnet-lock).

## Review access policy and device inventory

Review the tailnet policy for least-privilege access between users, devices, and services. Check Tailscale SSH rules separately from network access rules. Keep SSH settings aligned with the policy and the SSH path you need.

Review auth keys for unnecessary keys, long expiration periods, or broad reusable keys. Use short-lived, tagged, or ephemeral keys where they fit the workload.

Remove stale devices only after confirming ownership. The Tailscale CLI used for this runbook has no remote-device removal command. Remove nodes in the admin console or use the [Tailscale device API](https://tailscale.com/kb/1260/device-remove). Removing a device disconnects it immediately. An unapproved device may be able to rejoin if device approval is not enabled; Tailnet Lock instead requires a trusted signature.

## Verify SSH access after changes

After changing a remote setting, reconnect through the same SSH path you used before the change. For Tailscale SSH, the local wrapper checks the host key against the node identity advertised by Tailscale:

```sh
"$TAILSCALE_CLI" ssh root@<node> '/usr/bin/tailscale lock status'
```

Do not bypass an OpenSSH host-key warning. Verify the node identity or resolve the host-key change before trusting a plain SSH connection.

## Record this tailnet's completed checks

Date: 2026-10-25. This Mac uses Tailscale 1.104.1. `threadripper` uses 1.102.5. `oracle` uses 1.96.4.

- [x] Inspected local preferences, peer status, route advertisements, exit-node status, DNS, serve, and funnel.
- [x] Confirmed there were no subnet routers, exit nodes, Serve services, or Funnel services in use.
- [x] Set `accept-routes=false` on this Mac because no subnet routes were needed.
- [x] Enabled auto-update on this Mac, `threadripper`, and `oracle`.
- [x] Verified `accept-routes=false` and `auto-update=true` on this Mac.
- [x] Verified auto-update on `threadripper` with `tailscale get --json` and on `oracle` with `tailscale debug prefs`.
- [x] Enabled Tailnet Lock on this Mac, `threadripper`, and `oracle`.
- [x] Removed `oracle` from the trusted signing keys because you do not trust that host as a signer. Its node remains in the tailnet.
- [x] Added `box` as a trusted signer after verifying its Tailnet Lock key over Tailscale SSH.
- [x] Verified Tailnet Lock on all four nodes when `box` was added as a signer. The Mac, `threadripper`, and `box` are trusted signers; `oracle` remains signed by the Mac and has no signer privileges.
- [x] Confirmed a new SSH connection to `threadripper` worked after its settings change.
- [x] Preserved the existing SSH settings and enabled `shields-up` after confirming no inbound tailnet access is needed.
- [x] Stored the two Tailnet Lock disablement secrets separately in secure locations.
- [x] Pruned the stale devices from the tailnet.
- [x] Confirmed this Mac does not need inbound access from `threadripper`.
- [x] Confirmed no other tailnet device needs inbound access to this Mac and set `shields-up=true`.

## Finish the remaining decisions and admin work

- [ ] Review the tailnet policy through the Tailscale API. The installed client CLI has no policy command. Use a read-only token with `policy_file:read` and its required device-read scopes. Review grants, ACLs, and SSH rules before proposing changes.
- [ ] Review auth keys and remove unused keys. This needs admin-console or API access and confirmation of which automation still depends on each key.
- [ ] Review whether `report-posture` should be enabled. Leave it off unless the tailnet policy uses device posture and you accept the associated device information reporting.
- [ ] Review Tailscale SSH on `threadripper` and `oracle` against the tailnet SSH policy. Both currently have the Tailscale SSH server enabled. Do not disable it until you confirm your required SSH path.
- [ ] Resolve `oracle`'s OpenSSH host-key warning before using plain `ssh root@oracle` again. Tailscale SSH successfully verified the node identity and was used for the auto-update change.
- [ ] Check update settings on offline devices you plan to keep when they next come online.
- [x] Restored `box`'s Tailscale service from its local console after the remote restart cut off the SSH connection.
- [x] Verified public DNS on `box`; `getent hosts www.google.com` returns an address through local Unbound.
- [ ] Restore MagicDNS lookups on `box`. Its Unbound resolver returns `NXDOMAIN` for tailnet hostnames, and direct queries to its local Quad100 resolver return `SERVFAIL`. The `tailscale` client is 1.102.5 while the running daemon is 1.90.9, so `tailscale dns status` returns 404. Restart the daemon only from a local console or a separate management path.

The CLI does not manage the tailnet ACL policy, device approval, or auth-key inventory in the commands available on this Mac. Device approval is not a pending toggle while Tailnet Lock is enabled.
