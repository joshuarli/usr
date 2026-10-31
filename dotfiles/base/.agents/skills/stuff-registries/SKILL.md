---
name: stuff-registries
description: "Apply when publishing or consuming packages through the 17166969.xyz registries (crates, npm, pypi) or working in ~/d/stuff. Covers the publish CLIs, shared state, R2 sync, and cf auth. Skip Cloudflare Worker development and package-manager work that does not touch these registries."
---

# stuff registries

`~/d/stuff` runs three static package registries on one platform: `mycrates` (Cargo sparse), `mynpm` (npm), and `mypypi` (Python wheels). Each publication is an immutable generation; `current` is a pointer to one. The Cloudflare Worker serves the site layout from R2, so publishing is always **build state → publish site → sync R2**.

| Registry | Public root | Client endpoint |
| --- | --- | --- |
| Cargo native | `https://crates.17166969.xyz` | `sparse+https://crates.17166969.xyz/current/registry/` |
| Cargo mirror | same host | `sparse+https://crates.17166969.xyz/current/crates-io/` |
| npm | `https://npm.17166969.xyz` | `https://npm.17166969.xyz/current/` |
| PyPI | `https://pypi.17166969.xyz` | `https://pypi.17166969.xyz/current/simple/` |
| Aggregate | `https://stuff.17166969.xyz` | `/llms.txt` for inventory |

`~/d/stuff/README.md` is the authoritative guide; each crate under `crates/` has its own README. `stuff ls|search|diff|doctor` reads catalogs and checks artifacts.

## State and auth

- Publication state lives in `${XDG_STATE_HOME:-$HOME/.local/state}/stuff/<registry>/` (`mycrates/{state,site,token}`, `mynpm/site`, `mypypi/site`, ...). It is the source of truth and is outside the checkout; back it up, never treat a fresh checkout as enough.
- If state is missing, rebuild it before publishing or the next publish replaces the live registry with the caller's subset:
  - `deploy/r2-pull.py stuff-mycrates "$H/pull-mycrates"`, then `mycrates init`, `mycrates config set-public-base-url https://crates.17166969.xyz`, `mycrates adopt --from-site ...`
  - `deploy/r2-pull.py stuff-mynpm "$H/mynpm/site/mirror"`, then `mynpm adopt --site-dir ...`
  - `deploy/r2-pull.py stuff-mypypi "$H/mypypi/site"`
- Syncs need an authenticated `cf` CLI. Check with `cf r2 buckets list` (read-only). Conditional promotion prefers `R2_S3_ENDPOINT`, `R2_S3_ACCESS_KEY_ID`, `R2_S3_SECRET_ACCESS_KEY`; without them set `R2_PROMOTE_UNCONDITIONAL=1` to promote through `cf`, accepting that a competing publisher is not detected.

## Cargo

Source repos own their crate list and call the shared script; `STUFF_DIR` must point at this checkout because the script builds the binaries there:

```sh
STUFF_DIR=/Users/josh/d/stuff CRATES="pkg-a pkg-b" R2_PROMOTE_UNCONDITIONAL=1 \
  /Users/josh/d/stuff/deploy/publish-mycrates.sh
```

It starts a local publish server, runs `cargo publish -p` in dependency order, republishes the site with the public URL, and syncs R2. `cargo publish` refuses a dirty tree, so commit crate-source changes first. Versions already published in the native index cannot be replaced, only yanked.

- **Native vs mirror.** First-party crates go to the native index (`current/registry/`). Upstream crates come from the archive (`current/crates-io/`), usually via source replacement. Native crates may depend on crates.io crates; those resolve through the mirror or crates.io.
- **Consuming a native crate.** Configure `[registries.mycrates] index = "sparse+https://crates.17166969.xyz/current/registry/"` and depend on `{ version = "...", registry = "mycrates" }`.
- **Native → native dependencies.** A plain path dependency is rewritten to crates.io when published. Name the registry on the workspace dependency so the published manifest keeps the same-registry link, e.g. `age-core = { version = "0.12.0", path = "age-core", registry = "mycrates" }`. Local builds still use the path; packing uses the registry.
- **Verification quirk.** `mycrates` writes `"auth-required": false` into the generated index config but `serve-publish` requires its token for blob GETs, so verifying a crate that depends on another native crate fails with a 401 on download. Publish the dependency first (it verifies normally), then publish the dependent crate with `--no-verify`; prove the result by consuming it from the registry. This is a tool gap, not a reason to publish the dependency to crates.io.
- **Adding upstream deps to the mirror.** Import the lockfile that needs them, then fetch and publish:
  `mycrates import-lock Cargo.lock --project <id> --state-dir "$STATE"`,
  `mycrates plan`, `mycrates fetch`, `mycrates verify`, `mycrates publish`, then `deploy/r2-sync.sh "$SITE" stuff-mycrates`.
  `deploy/import-cargo-locks.sh` imports many lockfiles. `doctor` lists unsupported sources; native registry packages are expected to be skipped.
- A manual publish still needs the token file, `CARGO_REGISTRIES_MYCRATES_INDEX` pointing at the local static server, and `CARGO_REGISTRIES_MYCRATES_TOKEN` from `$STATE/../token`. Hold `deploy/publish-lock.sh` around the transaction.

## npm and PyPI

- npm: `STUFF_DIR=... LOCKFILE=pnpm-lock.yaml PROJECT=<id> deploy/publish-mynpm.sh` (source repos wrap this in `make publish-mynpm`). `TARGETS` adds non-host platforms; state is the `mynpm/site` mirror.
- PyPI: `STUFF_DIR=... PACKAGES="name==version ..." PLATFORM=linux-aarch64 deploy/publish-mypypi.sh` (source repos wrap this in `make publish-mypypi`). Wheels are validated on a native runner; publish once per platform against the same state/site. Linux uses `deploy/mypypi-container.sh`.
- Both scripts publish a site generation and sync R2 in one transaction under the registry's publish lock.

## Verify

After a deploy run `deploy/deployed-smoke.sh` (read-only, no credentials) or `stuff doctor --remote --sample-artifacts`. It checks active generations, pinned catalogs, reachable endpoints, and one hash-verified artifact per registry. Roll back a bad cargo/npm/pypi generation with `deploy/r2-rollback.sh <bucket> <generation>`, which verifies the target manifest before moving `current`.

**Report:** which registry and packages were published, the generation synced, the auth mode used, the check run and its result, and anything left unverified.
