# Host CPU budget

[`cpu-slot`](../dotfiles/linux/.local/bin/cpu-slot) gives heavy jobs on a Linux host a share of one CPU budget, so parallel lanes cannot stack builds, test containers and proof jobs onto every core. It is Linux-only because it pins jobs with `sched_setaffinity`.

## Pool and reserve

The pool is the host's CPUs minus a reserve that no job can take: CPUs `RESERVE` to `TOTAL - 1`, with `RESERVE` 8 by default (`CPU_SLOT_RESERVE` or `--reserve`). Each pool CPU is a lock file under `${XDG_STATE_HOME:-~/.local/state}/cpu-slot/`, held with `flock` for the job's lifetime, so a holder that crashes releases its CPUs. A job waits with backoff until enough CPUs are free. A request larger than the pool fails with exit 2 instead of waiting forever. `cpu-slot status` lists the held CPUs with each holder's pid, label and start time.

## Wrapping jobs

```sh
cpu-slot run --cpus 4 -- lake build
cpu-slot run --cpus 4 --name xsh-gate -- cargo dev gate src/lib.rs
cpu-slot run --cpus 8 --timeout 45m -- sh -c 'docker run --cpuset-cpus="$CPU_SLOT_CPUS" image cmd'
```

The command runs pinned to exactly the granted CPUs, with `CPU_SLOT_CPUS` (a comma list) and `CPU_SLOT_COUNT` set. Affinity does not reach into Docker containers, which `dockerd` starts, so pass `--cpuset-cpus="$CPU_SLOT_CPUS"` to `docker run`. `CPU_SLOT_COUNT` suits `-j` and job-count options.

## Timeouts and signals

The command runs in its own session. When it exits, times out (`--timeout`, exit 124), or `cpu-slot` receives SIGINT, SIGTERM or SIGHUP, every process still in that process group gets SIGTERM, then SIGKILL after `--grace` (default 10s). The CPUs are released only after the group is gone, so a timed-out step cannot leave a grandchild running on budgeted CPUs, unlike BusyBox `timeout`, which signals only its direct child.

A descendant that starts its own session leaves the process group. Use [`cpu-guard`](../dotfiles/base/.local/bin/cpu-guard), which tracks every descendant, for commands that do that or that may spin.
