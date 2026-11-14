---
name: stuff-registries
description: "Apply when publishing or consuming packages through the 17166969.xyz registries (crates, npm, pypi, oci) with the installed `stuff` CLI, or when inspecting their published state. Covers publishes, republish, rollback, and doctor. Skip Cloudflare Worker development and package-manager work that does not touch these registries."
---

# stuff registries

`stuff` is one installed CLI that publishes Cargo, npm, PyPI, OCI and the artifact mirror. OpenOrange on Lisa serves the registries over tailnet HTTPS. Each publication is an immutable generation; the shared coordinator selects `current` and serializes writers across machines.

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

- Install the current native CLI and an owner-only `${XDG_CONFIG_HOME:-$HOME/.config}/stuff/credentials.json` (mode 600). Its endpoint is `https://stuff.17166969.xyz`; it contains the publishing service keys and coordinator token. Keep backing-store keys on Lisa. Never print the file or put its secrets in argv. `STUFF_CREDENTIAL_FILE` selects a different protected file. The retired `cf_profile` field is rejected; Cloudflare login is unnecessary.
- Scripts that need `R2_S3_*` (`deploy/r2-pull.py`, `make gc`, the OCI writer host) obtain service gateway exports with `eval "$(stuff credentials BUCKET)"`. This does not grant a write lease; the supported writer and GC helpers acquire their own coordinator leases.
- Promotion uses a renewable server lease and a conditional coordinator revision. A competing writer gets exit `3`; wait for it to finish and retry against the new live generation. Explicit maintenance `R2_S3_*` credentials cannot override a configured publishing service.
- The remote service is authoritative. Publishes fetch its live generation and manifest, stage locally in `${XDG_STATE_HOME:-$HOME/.local/state}/stuff/<registry>/` (with caching in `${XDG_CACHE_HOME:-$HOME/.cache}/stuff/<registry>/`), upload missing immutable objects, and activate through the coordinator. A fresh machine needs the CLI, service credential file and Tailscale access, without copied local publication state. Lisa can publish through the same HTTPS endpoint.

## Procedures

Do not restate the publish runbooks here. Run `stuff publish --help` for current flags, and read `stuff/docs/PUBLISHING.md` for the full procedure, adoption, and native-vs-mirror rules.

**Report:** which registry and packages were published, the generation synced, the auth mode used, the check run and its result, and anything left unverified.
