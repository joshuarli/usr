---
name: settle
description: "Use for /settle: prepare a repository to move to another computer by finding unmerged and local-only work, identifying what must travel, and separating it from regenerable data. Skip campaign shutdown, routine cleanup, and generic session handoffs."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Settle

Prepare the active repository so the owner can continue on a fresh host. Make clear which source changes and local files must be carried, which data can be rebuilt, and what the chosen transfer method will omit. This is a portability review, not a campaign winddown: do not stop active work unless asked. Before leaving a job running, establish whether it is resumable, the exact command that resumes it, and whether a second instance would write concurrently to the same state.

## Inventory

**Inventory the repository state.** Read the repository instructions and applicable docs for local data, build output, and releases. Establish the current branch and head, working tree state, upstream relationship, local branches, linked worktrees, stashes, and each worktree's status. If submodules exist, inspect their recursive status and local work too. Inspect untracked and ignored project data, especially `.work/`, build output, and local configuration. Use targeted listings and sizes; do not dump generated trees into the transcript. If a candidate may contain credentials, identify its path and handling needs without printing its contents.

**Inventory state outside the repository.** A clean tree does not make a project portable. Find the durable store that records progress — a checkpoint table, object store, or queue — and record its name and how the new host reaches it.

**Check all local work.** For each branch, worktree, stash, or submodule that may contain work, compare its commits and file changes with the intended integration branch. Inspect relevant dirty source files and untracked files directly. For saved snapshots, validation copies, and caches, compare them with the current source before treating a difference as new work. A non-ancestor commit may already be patch-equivalent; establish that before proposing a merge. Do not assume remote-tracking refs are current unless the repository was fetched.

## Make it transferable

Classify each relevant item by what the owner needs on the new host:

- **Integrate only authorized source work.** Preserve distinct or incomplete work on its existing branch when merging would lose context or change behavior. Never discard dirty work.
- **Preserve required local files.** Move durable source or notes out of disposable scratch locations only when the request authorizes the move. Otherwise report their exact paths and keep them intact. Keep useful ignored artifacts under a known repo-local path when they have a concrete consumer.
- **Treat scratch as scratch.** Do not delete `.work/` wholesale or mistake an old validation snapshot for a source branch. Verify that nothing the resume path needs lives only there; if it does, move it into the repository first.
- **Carry external progress by reference.** When a campaign's progress lives in a database, object store, or queue, name the store, record how the new host authenticates to it, and state whether restarting is idempotent. Resume from that store; do not copy it, and do not depend on the old machine's process state.
- **Separate rebuildable output.** Identify regenerable output such as `target/` by the command that rebuilds it. Recommend or remove it only within the owner's requested cleanup scope.
- **Handle host setup deliberately.** List the exact commands that recreate host authentication (`gh auth login`, `gcloud auth application-default login`) and which component consumes each credential; separate credentials for one service fail independently, so one can expire while the other works. Do not copy credentials or broad agent-session logs into the repository. Identify sensitive paths without exposing their contents.

**Respect the transfer method.** A fresh clone gets only refs available from its remote; local-only commits, branches, stashes, and submodule commits need to be published or transferred separately. A full repository copy can carry local Git refs and stashes, but ignored and untracked files travel only if the copy includes them. A Git bundle omits the working tree and ignored files. If the method is still unknown and it changes whether local work survives, finish the inventory first, then ask which method they will use. Never push or publish without authorization. Do not apply or drop stashes as part of inspection.

**Preserve authorization boundaries.** Commit only your own changes; never commit the user's uncommitted work as part of an inventory. Do not run blanket clean/reset commands or remove preserved data based on its directory name alone. If the user authorizes a merge or cleanup, make the smallest safe changes and keep unrelated working-tree changes untouched.

## Verify and report

**Verify portability.** After changes, recheck affected branch, stash, submodule, and worktree state; confirm every intended source change is reachable through the chosen transfer method; and inspect remaining local-only data. Run the narrowest relevant check for integrated code or content. Do not claim the destination host is ready if the transfer itself has not been performed or tested.

**Prove the resume path.** Name a copy-pasteable resume command and exercise its read-only parts from a clean checkout of the transfer target; commit it in the repository. An inventory that is not exercised this way is not verified.

**The test:** after the stated transfer, the owner can recover all intended source work and required local project data without relying on the old machine's processes or unlisted files.

**Report:**

- what source work was integrated, preserved on a branch, or remains dirty;
- which local files must travel and their exact paths;
- which external store holds progress, and how the new host reaches it;
- what is safe to regenerate or remove, and the rebuild command where known;
- what the chosen transfer carries and omits;
- any manual host setup or owner action still required;
- checks run and what could not be verified.
