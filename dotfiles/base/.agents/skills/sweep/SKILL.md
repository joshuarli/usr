---
name: sweep
description: "Use for /sweep: double-take the last turn's fix or improvement, then with the owner's confirmation search the wider repo for other places it applies. Fix the mechanical ones and report the rest."
disable-model-invocation: true
---

# Sweep

The last turn fixed one instance. The owner wants the rest of that kind found: other places where the same fix or improvement would apply, even though nothing there is wrong in the same visible way.

This is a search for candidates, not a re-review. `double-take` asks what the change left inconsistent. `sweep` runs it first so the pattern is sound, then asks where else the change belongs.

## Rules

- **Double-take first.** Run the `double-take` skill over the last turn's change before generalizing it. A rule that is wrong or half-applied here would be copied to every site.
- **Confirm before the broad search.** After the double-take, stop and ask the owner. Show the transformation, the patterns and directories you propose to search, and anything the double-take left open. Search nothing beyond the double-take's scope until they answer.
- **State the transformation first.** One sentence of the form "when X, do Y instead", general enough to match other sites and narrow enough to match no false ones. If the last turn made more than one change, sweep each separately.
- **Search by shape, not by name.** Use the vocabulary of the old form, its common misspellings and aliases, and the structure around it, with `rg` or `fd`. Do not reread the repo. Stay within the repo the change lives in, and say which directories you did not search.
- **Classify every hit.** Each candidate is one of: applies as is, applies with a judgment call, or looks alike and does not apply. Keep the last group, with the reason, so the owner can see what you ruled out.
- **Prove each candidate** with a `file:line` and the command that found it. Drop what you cannot show.
- **Apply only the mechanical ones:** sites where the transformation applies unchanged, with no contract change and no new decision. Report the judgment calls with a recommendation and wait.
- **Do not grow the change.** A candidate that needs a new design, a new dependency, or a contract change is a finding, not an edit. File it per the `todo` skill if the owner asks.

## Steps

1. Run `double-take` on the last turn's change and apply its trivial fixes.
2. Name the transformation, list the files the last turn touched, and propose the search: patterns and directories.
3. Stop and wait for the owner to confirm or adjust the search.
4. Search the repo for the shape, and group the hits by owner or layer. When the hits span many directories or layers, fan the search out to read-only children per `orchestrate`.
5. Classify each hit and prove it.
6. Apply the mechanical group, one logical change per kind. When one script or codemod covers every site, write and run it per `orchestrate` instead of editing by hand.
7. Check narrowly with the cheapest command that covers what you touched.

An empty sweep is valid. Say which searches came up empty so the owner can trust it.

**The test:** the owner approved the search before it ran, a rerun of the same searches finds no unclassified hit, and every edit is an instance of the stated transformation.

**Report:** at the checkpoint, the double-take result, the transformation, and the proposed search. After the sweep, sites fixed; judgment calls with a recommendation; sites ruled out and why; directories not searched; checks run.
