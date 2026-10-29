---
name: double-take
description: "Use for /double-take or 'dig deeper': treat the last change or review as the pattern, find what still contradicts it and where the same defect shape recurs, fix the trivial ones, report the rest, and offer to widen the search to the rest of the repo."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Double Take

The first pass finds what you went looking for. The second asks what that pass left inconsistent and where the same shape lives elsewhere. A rule changed in one place nearly always has stragglers, and a cleanup you just made usually has a twin.

Scope is the change or finding set from this session, or the one the user names. The first pass re-reviews that change only. Widening to the rest of the repo is a second pass that only the owner starts.

## Steps

1. **Name the pattern** in one sentence: the defect class the change removed, or the rule it introduced.
2. **Find contradictions.** Search for every place that still says or does the opposite: skills, docs, configs, tests, examples, callers, comments. Search by the rule's vocabulary and by the old spelling, using `rg` or an existing check, not rereading.
3. **Find recurrences.** Search the scope for the same shape elsewhere: the same duplicated statement, redundant guard, stale pointer, or prose standing in for a check. Say which parts of the scope you did not search.
4. **Audit your own change.** Look for statements you duplicated, a new rule with no owner or enforcement, a description or doc you left stale, and anything the change made redundant.
5. **Prove each finding** with a `file:line` and the command that found it. Drop what you cannot show.
6. **Apply only the trivial fixes:** contradictions to the rule you just applied, and duplicates you introduced, within scope and with no contract change. Report everything else with a recommendation and wait for the owner.
7. **Check narrowly** with the cheapest command that covers what you touched.
8. **Ask whether to widen.** End the report with a yes/no question: search the rest of the repo for other places this change applies? Show the transformation, the patterns, and the directories you would search. Search nothing beyond the scope until the owner answers. On no, stop. Under sleep, do not ask: state the default (do not widen) in the report and proceed.

## Widening

Runs only after a yes.

- **State the transformation** in one sentence, "when X, do Y instead", general enough to match other sites and narrow enough to match no false ones. If the change was several, widen each separately.
- **Repeat steps 2 to 7 across the repo, by shape and not by name:** the old form's vocabulary, its aliases and misspellings, and the structure around it, with `rg` or `fd`. Do not reread the repo. Say which directories you did not search. When hits span many layers, fan the search out to read-only children per `orchestrate`.
- **Classify every hit:** applies as is, applies with a judgment call, or looks alike and does not apply. Keep the last group with its reason.
- **Apply only the mechanical ones:** the transformation applies unchanged, with no contract change and no new decision. When one script or codemod covers every site, write and run it per `orchestrate`. Report judgment calls with a recommendation and wait.
- **Do not grow the change.** A candidate that needs a new design, a new dependency, or a contract change is a finding, not an edit. File it per the `todo` skill if the owner asks.

An empty result is valid. Say which searches came up empty so the owner can trust it.

**The test:** every finding has a command that reproduces it, a second `double-take` over the same scope would find nothing new, and nothing outside the scope was searched without a yes.

**Report:** the pattern; contradictions fixed; recurrences found, each with a recommendation; cleanups to your own change; searches that found nothing; checks run; then the widening question. After a yes, add the sites fixed, judgment calls with a recommendation, sites ruled out and why, directories not searched, and checks run.
