#!/usr/bin/env python3
"""Fixed receiver entry point for the SSH transport."""
import sys

from agent_memory.store import Store, StoreError, default_state_dir
from agent_memory.transfer import receiver


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "ingest":
        argv = argv[1:]
    state_dir = argv[0] if argv else str(default_state_dir())
    try:
        with Store(state_dir) as store:
            receiver(store, sys.stdin.buffer, sys.stdout.buffer)
    except (StoreError, OSError) as exc:
        print("agent-sessions-serve: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
