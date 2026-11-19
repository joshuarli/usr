# Copy-on-write worktrees: practical options

Reviewed 2026-11-19. Keep Git's linked-worktree model and `usr`'s ownership/retirement boundary. Evaluate CoW as an optional creation/cache-seeding backend. It can reduce duplicated data; it cannot establish that an old checkout or build has stopped.

## What is shared

[Git worktrees](https://git-scm.com/docs/git-worktree) already share repository history and objects. Each checkout still has its own working files, index and HEAD. Native `git worktree add` does not expose a general reflink checkout option in the current documented command. Large per-lane build directories and ignored dependencies are another source of duplication; measure their actual contribution before changing the checkout algorithm.

APFS supports independently writable clones sharing unchanged extents. [Apple's APFS guidance](https://developer.apple.com/documentation/foundation/about-apple-file-system) describes clone behavior; [Apple DTS](https://developer.apple.com/forums/thread/743665) confirms `cp -c`. Linux exposes [FICLONE](https://man7.org/linux/man-pages/man2/ioctl_ficlone.2.html) on supporting filesystems, with both files on the same filesystem and subsequent writes kept private. Filesystem support, not musl versus glibc, is the determining feature. Btrfs and reflink-enabled XFS are useful Linux targets. Do not assume ordinary ext4 offers reflinks.

## Current tools

| Tool | Actual approach | Assessment for usr |
| --- | --- | --- |
| [Worktrunk](https://worktrunk.dev/step/#wt-step-copy-ignored) | Ordinary Git checkout plus per-file CoW for ignored dependencies/caches where supported | Useful cache-seeding implementation. Use explicit allowlists; the default copies all ignored files, and unsupported filesystems fall back to full copies. Adopting the whole manager overlaps lifecycle ownership. |
| [josharian/git-cow-worktree](https://github.com/josharian/git-cow-worktree) | Narrow `git worktree add` replacement. Git creates metadata first; matching tracked files are cloned and hashed, index stat data is reconstructed, and ordinary checkout fills missing/stale paths | Best small add-only comparison candidate. Go; the maintainer warns that it is generated code and should be treated cautiously. Correctness and crash handling need qualification. |
| [gabrielkoerich/git-cow](https://github.com/gabrielkoerich/git-cow) | Rust CLI/library, maintained template checkout, selected ignored-directory seeding and ordinary Git fallback | Interesting Rust candidate. Linux invokes `cp --reflink=always`; verify the actual Alpine tool, not just Rust dependency count. Template warming and expiry add lifecycle obligations. |
| [simgit](https://github.com/abendrothj/simgit) | Cached baselines, reflinks or Linux FUSE overlays, managed ephemeral/persistent worktrees, GC and repair | Directly targets many agents, but adds another state/lock/mount lifecycle. Evaluate as an alternative manager, not another cleaner layered onto usr. |
| [git-worktree-apfs](https://github.com/dannolan/git-worktree-apfs) | Clone a clean source checkout at the requested source HEAD | Useful macOS reference. A Linux build is not Linux CoW support. |

No wrapper was installed or benchmarked on the user's machines for this review. README support claims are not proof of a musl release, source isolation or a production-ready lifecycle.

## CoW is not automatically a speed win

Worktrunk's [tracked-file CoW investigation](https://github.com/max-sixty/worktrunk/issues/3150) reports about 3.5 seconds for Git checkout on an APFS `rust-lang/rust` checkout with roughly 60,000 tracked files. Serial per-file clones took about 6.25 seconds; parallel clones plateaued around 3.2–3.7 seconds. These are upstream reported measurements, not usr measurements. Large tracked binaries benefited more; small source files were dominated by metadata work.

Worktrunk also [reverted atomic directory cloning](https://github.com/max-sixty/worktrunk/pull/640) because it made the interactive shell unresponsive. Whole-directory cloning may look excellent in a single elapsed-time number while hurting the host. The related tracked-CoW [issue #4238](https://github.com/max-sixty/worktrunk/issues/4238) is closed; it is not a shipped Worktrunk tracked-checkout feature.

The likely first target is explicitly allowed, quiescent build-cache seeding, provided those caches dominate measured duplicated storage. This is an engineering hypothesis. Source-only CoW can still be worthwhile for disk savings even when checkout latency is unchanged.

## Required boundaries

- Keep one lifecycle owner. A new template is another retained checkout; record who owns it and when it is safe to reclaim. Do not enable a wrapper's independent GC alongside usr.
- Let Git allocate the new worktree's metadata. Copying a linked checkout's `.git` pointer can make two directories share one HEAD/index. A naive `--no-checkout` plus copied files plus `reset --hard` can rewrite the files and destroy sharing; index reconciliation matters.
- Never hardlink mutable worktree files or build outputs. Hardlinks share writes; reflinks isolate them.
- Seed only an explicit allowlist of relocatable caches. Exclude secrets, `.env`, agent/session state, sockets, locks and active scratch. A per-file clone is not a consistent snapshot of a concurrently changing build directory. Python virtualenvs and other build artifacts may embed absolute paths.
- Require CoW for large cache seeds. GNU [`cp --reflink=always`](https://www.gnu.org/software/coreutils/manual/html_node/cp-invocation.html) fails when sharing is unsupported; `auto` can allocate a full copy. Skip optional cache seeding when unavailable or under pressure, rather than unexpectedly filling disk. Plain Git checkout remains the portable source fallback.
- Measure controlled filesystem available-space deltas and exclusive/shared accounting where available. Summed directory `du` values can count shared extents more than once. Include edits and real builds after creation; initial savings can erode.
- Check requested HEAD, clean status, file contents/modes, source isolation, branch identity and supported fallback. Never infer these from a fast clone or an exit code alone.

For a dedicated Linux workspace pool, [Btrfs subvolume snapshots](https://btrfs.readthedocs.io/en/latest/btrfs-subvolume.html) offer tree-level snapshots, but require an intentional subvolume layout and separate Git metadata setup. Nested subvolumes are not recursively snapshotted. [OverlayFS](https://docs.kernel.org/filesystems/overlayfs.html) adds mount/upper/lower/work lifetime and filesystem identity considerations. Do not make that the default ext4 workaround while lifecycle reliability is being repaired. Switching to Jujutsu is unnecessary solely for CoW; [jjCoW](https://github.com/Cyberistic/jjCoW) labels itself experimental.

## Bounded evaluation

Compare ordinary Git, allowlisted CoW cache seeding, and one add-only adapter on native APFS and one native Linux reflink filesystem. Include ext4 as the fallback lane. Use usr plus a representative large Rust/C++ project such as bctl or python-build; record exact revisions and cache contents.

Measure creation latency, first verified build time, available-space delta before/after creation and build, and responsiveness under concurrent creation. Include an unsupported filesystem, dirty seed, ignored private data, different requested HEAD, interrupted creation, stale template, concurrent add/retire, and a still-active lane. Show that fallback cannot silently byte-copy a large cache under pressure.

Accept a backend only with source isolation, correct Git metadata, recoverable interruption and demonstrated disk or build-time benefit. Preserve `worktree-retire` and explicit campaign ownership. Do not assume a checkout-speed improvement, and do not add a daemon or host-filesystem migration just to complete this spike.
