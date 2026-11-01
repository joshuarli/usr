# Resume the Cloudflare agent-memories sync

The first real sync is partly delivered. Finish it after the D1 free-tier
row-write limit resets at `2026-11-02T00:00:00Z`.

## Current state

- The Worker `usr-memories` serves `https://memories.17166969.xyz`. Its D1
  database is `9870c4da-3758-4f0c-ab6d-2372eb34009b`; its R2 bucket is
  `usr-memories`.
- The collector origin is `fbb5b1b8df3f401d34bebab633e59301`, label `sentry`.
  The service token `usr-memories-collector` is bound to that origin.
- `age` 1.3.2 is installed. `~/.agent-sessions/age.key`,
  `age-recovery.key`, `age.recipients`, and `cloudflare-token.json` are mode
  `0600`.
- `~/.agent-sessions/config.json` uses `transport: "cloudflare"` with the
  Worker URL, token, recipients, and identity paths.
- Cloudflare holds 259 committed generations, revision 259, and 19,077
  stored objects. The local archive has 2,191 generations.
- 1,932 generations, 36,719 objects, and 2.40 GB are still pending.
- No recovery snapshot is committed, `learning_projection` is off, and the
  mirror LaunchAgent is not installed.
- The old SSH central block is at `.work/tmp/config.json.ssh-central`.
  `.work/` is disposable; copy it elsewhere before cleaning that directory.
- `com.josh.agent-learning` now runs against `~/.agent-sessions`. Leave it
  there.

The sync stopped when D1 refused a generation commit with `exceeded D1's free
tier daily row write limit`. The Worker reports every unclassified commit
error as `503 generation commit failed`, which hid the cause. The retry after
that reported `manifest object is not stored`: a re-encrypted manifest reused
the earlier plaintext row, so the commit named a ciphertext D1 never recorded.
Commit `628101c` makes the client commit the ciphertext the server actually
stored. Its test suite passed:

```sh
TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I agent-memory/tests/test_mirror.py
```

## Resume after the reset

1. Confirm the Worker and config still answer:

   ```sh
   agent-sessions mirror doctor
   agent-sessions mirror status --json
   ```

   Expect `remote=ok`, `pinned=True`, and `revision=259`.

2. Run the sync:

   ```sh
   TMPDIR="$PWD/.work/tmp" agent-sessions mirror sync --remote cloudflare
   ```

   Expect `committed=N duplicate=M ... store=usr-memories revision=R`. The
   1,932 pending generations need about 77k D1 row writes, so they should fit
   in one daily allowance. If the run stops again, save the last error from
   `mirror status --json` before retrying.

3. Confirm the backlog is empty:

   ```sh
   agent-sessions mirror status --json
   agent-sessions mirror doctor
   ```

   Expect `generations=0`, `objects=0`, `bytes=0`, `pinned=true`, and
   `last_error=null`. A non-empty backlog is safe to retry; accepted
   generations are not sent again.

4. Check the recovery snapshot:

   ```sh
   agent-sessions mirror snapshots
   ```

   The sync creates one. `agent-sessions mirror verify --objects` downloads
   every pinned object and is the stronger check, but it re-downloads about
   3.6 GB.

   The snapshot commit inserts about 57k `snapshot_object` rows, about 2k
   `snapshot_chunk` rows, and updates about 57k `remote_object` rows. If D1
   counts updates toward the free-tier limit, one snapshot batch exceeds
   100k rows even on a fresh day. The archive generations are already durable
   when this happens, so the learning data and transcripts remain restorable
   from the collector. To finish the snapshot, either upgrade the account to
   Workers Paid or change the Worker to split the snapshot commit across
   batches. Do not treat a snapshot error as lost archive data.

5. Read the projection disclosure, then enable the searchable projection:

   ```sh
   agent-sessions mirror enable --searchable-learning
   ```

   The command prints: `claims and applicability text will be stored in D1
   and indexed by FTS5; records still travel inside the encrypted recovery
   snapshot when this is off`. It requeues every live experience. Expect
   `searchable_learning=1 requeued=N`.

6. Send the projection:

   ```sh
   TMPDIR="$PWD/.work/tmp" agent-sessions mirror sync --remote cloudflare
   ```

   This writes the learning delta, then refreshes the snapshot. Check
   `mirror status --json` for a clean `last_error`.

7. Install the mirror LaunchAgent:

   ```sh
   tmp=.work/tmp/com.josh.agent-sessions-mirror.plist
   sed -e 's|@@HOME@@|/Users/josh|g' \
       -e 's|@@STATE_DIR@@|/Users/josh/.agent-sessions|g' \
       -e 's|@@REMOTE@@|cloudflare|g' \
       dotfiles/launchd/com.josh.agent-sessions-mirror.plist.in > "$tmp"
   plutil -lint "$tmp"
   install -m 600 "$tmp" "$HOME/Library/LaunchAgents/com.josh.agent-sessions-mirror.plist"
   launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.josh.agent-sessions-mirror.plist"
   launchctl print "gui/$(id -u)/com.josh.agent-sessions-mirror" | head
   ```

   The agent runs `agent-sessions mirror sync --remote cloudflare --json`
   every 900 seconds. An overlapping run exits 0 with `overlapped=1`; an
   unreachable mirror exits non-zero and keeps the backlog.

8. Move the recovery material offline. Copy
   `~/.agent-sessions/cloudflare-token.json` and
   `~/.agent-sessions/age-recovery.key` into the password manager, then
   remove the recovery key from `~/.agent-sessions`. Keep the token file at
   mode `0600`. The 1Password CLI could not reach its desktop app on
   2026-11-01, so this step was not done.

9. Remove the synthetic token copy after the real token works:

   ```sh
   rm -f .work/secrets/collector.token
   ```

   To smoke-test the Worker afterward, point the script at the real token:

   ```sh
   MEMORIES_TOKEN_FILE="$HOME/.agent-sessions/cloudflare-token.json" \
     sh agent-memory/cloudflare/scripts/smoke-deployed.sh
   ```

10. Optional: read the captured traces and profiles in the Cloudflare
    dashboard. `make observe` prints the URLs and the serving deployment.

## Do not

- Do not run `agent-sessions mirror adopt`. The pin to `usr-memories` is
  correct.
- Do not delete the D1 `remote_object` row for manifest ciphertext
  `0db0c41ab6c1f1316bef412bd222d74bed1a35c938186974c186c3ee9b8cf5b3`.
  The fixed client reuses it when it retries generation 260.
- Do not enable `learning_projection` before the archive backlog is empty.
- Do not run `sh sync`, host setup scripts, or any installer without asking.

## Reference

- Campaign record: [CAMPAIGN-AGENT-MEMORIES-CLOUDFLARE.md](CAMPAIGN-AGENT-MEMORIES-CLOUDFLARE.md)
- Operating guide: [agent-memory/README.md](../agent-memory/README.md)
- LaunchAgent template: [com.josh.agent-sessions-mirror.plist.in](../dotfiles/launchd/com.josh.agent-sessions-mirror.plist.in)
