---
name: double-take
description: "Use for /double-take or 'dig deeper': treat the last change or review as the pattern, find what still contradicts it and where the same defect shape recurs, fix the trivial ones, and report the rest."
disable-model-invocation: true
---

# Double Take

The first pass finds what you went looking for. The second asks what that pass left inconsistent and where the same shape lives elsewhere. A rule changed in one place nearly always has stragglers, and a cleanup you just made usually has a twin.

This is a re-review of the change itself, not a search for other places it belongs. Use `sweep` for that.

Scope is the change or finding set from this session, or the one the user names. Do not widen to a whole-repo audit unless asked.

## Steps

1. **Name the pattern** in one sentence: the defect class the change removed, or the rule it introduced.
2. **Find contradictions.** Search for every place that still says or does the opposite: skills, docs, configs, tests, examples, callers, comments. Search by the rule's vocabulary and by the old spelling, using `rg` or an existing check, not rereading.
3. **Find recurrences.** Search the scope for the same shape elsewhere: the same duplicated statement, redundant guard, stale pointer, or prose standing in for a check. Say which parts of the scope you did not search.
4. **Audit your own change.** Look for statements you duplicated, a new rule with no owner or enforcement, a description or doc you left stale, and anything the change made redundant.
5. **Prove each finding** with a `file:line` and the command that found it. Drop what you cannot show.
6. **Apply only the trivial fixes:** contradictions to the rule you just applied, and duplicates you introduced, within scope and with no contract change. Report everything else with a recommendation and wait for the owner.
7. **Check narrowly** with the cheapest command that covers what you touched.

An empty result is valid. Say which searches came up empty so the owner can trust it.

**The test:** every finding has a command that reproduces it, and a second `double-take` over the same scope would find nothing new.

**Reply:** the pattern; contradictions fixed; recurrences found, each with a recommendation; cleanups to your own change; searches that found nothing; checks run.
