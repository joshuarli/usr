---
name: stuff-registries
description: "Apply when publishing or consuming packages through the 17166969.xyz registries (crates, npm, pypi, oci) with the installed `stuff` CLI, or when inspecting their published state. Covers publishes, republish, rollback, and doctor. Skip Cloudflare Worker development and package-manager work that does not touch these registries."
---

# stuff registries

`stuff` is one installed CLI that publishes four static registries: `crates` (Cargo sparse), `npm`, `pypi`, and `oci`. Each publication is an immutable generation and `current` points at one. The Worker serves the site layout from R2, so a publish is build state → publish site → sync R2, done by the CLI in one transaction under the registry's publish lock.

| Registry | Public root |
| --- | --- |
| crates | `https://crates.17166969.xyz` |
| npm | `https://npm.17166969.xyz` |
| pypi | `https://pypi.17166969.xyz` |
| aggregate | `https://stuff.17166969.xyz` (`/llms.txt` inventory) |

## When to use

Use this for any publish, rollback, or health check against these registries. Skip it in source repos whose `Makefile` already wraps the same command, unless that wrapper fails.

## Commands

- `stuff publish cargo -p NAME... [--registry NAME]` — `cargo publish` in dependency order; it refuses a dirty tree, so commit first.
- `stuff publish npm (--lockfile PATH --project ID | --tarball PATH...)` — publishes a site generation from a lockfile or first-party tarballs.
- `stuff publish pypi NAME==VERSION... [--allow-sdist]` — publishes wheels for the named distributions (prefers wheels; `--allow-sdist` permits sdist builds).
- `stuff publish oci (--image REPO=REF... | --layout DIR --repository NAME [--tag TAG])` — images or a layout directory.
- `stuff republish <registry>` — maintenance rebuild of a generation; the only command that accepts `--allow-drops`.
- `stuff rollback <registry> <generation>` — verifies the target manifest before moving `current`.
- `stuff doctor` — checks active generations, catalogs, endpoints, and one hash-verified artifact per registry; `--sample-artifacts` downloads and verifies one artifact per registry.

Publish, republish, and rollback take `--dry-run` to show the planned work and `--json` for machine-readable output. Exit codes: `0` ok or no-op, `2` usage/config, `3` conflict or stale generation, `4` integrity, `5` transport. Treat anything else as a bug.

Consumer repos call `stuff` from their `Makefile` publish-* targets with `STUFF ?= stuff`, so the binary can be swapped, e.g. `$(STUFF) publish cargo -p $(CRATES)`.

## Auth and state

- Minting goes through the `cf` profile named by `cf_profile` in `~/.config/stuff/config.json` (default `stuff`); `stuff` passes `--profile` itself, so publishing works from any repo without `cf auth activate`. If minting fails, log the profile in with `cf auth create stuff` and check with `cf --profile stuff auth whoami`; do not bind consumer directories.
- Scripts that need `R2_S3_*` themselves (`deploy/r2-pull.py`, `make gc`, the OCI writer host) mint them with `eval "$(stuff credentials BUCKET)"`; the old `deploy/publish` and `r2-sync.sh` wrappers are gone.
- Promotion uses the S3 transport with a conditional `If-Match` write, so a competing publisher gets exit `3`. It reads `R2_S3_ENDPOINT`, `R2_S3_ACCESS_KEY_ID`, and `R2_S3_SECRET_ACCESS_KEY`; when those are unset the CLI mints short-lived bucket-scoped values itself and stops before building if minting fails.
- Remote R2 is the authoritative source of truth. Publishes fetch the live generation and manifest directly, stage locally in `${XDG_STATE_HOME:-$HOME/.local/state}/stuff/<registry>/` (with caching in `${XDG_CACHE_HOME:-$HOME/.cache}/stuff/<registry>/`), upload missing immutable objects, and conditionally promote `current`. A fresh machine can publish immediately without copied local state.

## Procedures

Do not restate the publish runbooks here. Run `stuff publish --help` for current flags, and read `stuff/docs/PUBLISHING.md` for the full procedure, adoption, and native-vs-mirror rules.

**Report:** which registry and packages were published, the generation synced, the auth mode used, the check run and its result, and anything left unverified.
