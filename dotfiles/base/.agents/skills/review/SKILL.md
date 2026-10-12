---
name: review
description: "Use for /review: a thorough review of the current branch, task, or session, answering whether this change is right, safe, and finished. The scoped sibling of ultrareview; a router to the other skills."
disable-model-invocation: true
---

# Review

Review the change in front of you, not the repository. This is `ultrareview` narrowed to a change set, and it shares that skill's lens table, entry shape, and P1 to P4 definitions: read its `SKILL.md` instead of copying them here. Follow this skill's steps, not its. Review only: report what you find and do not edit code. You may fix docs and comments that the change made stale.

## Rules

- **Scope is the change set plus its intent.** The change set is everything on the branch since it left the default branch (`git diff $(git merge-base HEAD origin/HEAD)`), plus staged, unstaged, and untracked files, plus work from this session even if committed. State the intent in one line, taken from the request, the conversation, and the commit messages, and mark it assumed if you inferred it. An empty change set is a result: say so and stop.
- **Judge the change, not the surroundings.** Pre-existing problems are out of scope unless the change depends on them, worsens them, or its safety rests on them.
- **Same bar as `ultrareview`:** big picture, evidence for every finding, no nitpicks a linter would catch, and an empty result is valid.
- **Follow the repo's instructions.** Read its AGENTS.md. Verify with the narrowest check that covers the change, not the whole suite, and report before starting anything expensive. No formatters, no commits, no pushes.

## Steps

1. **Scope.** Build the change set and the one-line intent. Read the full diff, then the code around each hunk and every caller of a changed symbol.
2. **Intent.** Does the change do what was asked, with nothing missing and nothing extra? A behavior change, or a change to an API, type, schema, permission, invariant, or transaction boundary that nobody asked for is a finding, and one the owner must be told about whatever its priority. A new dependency is not a finding by itself; check that it was vetted and stays within the project's performance gates.
3. **Blast radius.** This is the main lens here. Use `blast-radius` to find what the change breaks beyond the diff, and prove the one fact its safety depends on. Check any measured claim in the branch with `benchmark-checklist`.
4. **Lenses.** Apply the `ultrareview` lens table to the touched areas only and skip rows the change does not reach. Add `reference-parity` when the change replaces something, and `root-cause` if it fixes a bug without showing the cause. Rows that matter most for a change: `test-audit` on the tests the change adds or should have added, judged against `renovate-tests`: prefer one deterministic, isolated boundary test over several trivial unit tests, mocks, or coverage-driven additions, and flag those as findings; `dead-code-archaeology` on what it orphaned; `single-source-of-truth` on facts it duplicated; `deslop` for needless complexity it introduced, reported and not applied. Use `orchestrate` only when the change is too large to review alone.
5. **Docs.** Run `docs-refresh` scoped to the change. Do not refresh docs the change did not touch.
6. **Prove the top.** A P1 or P2 stands only after you have proven the fact it depends on Otherwise mark it `unproven` or downgrade it.
7. **Report** in the reply. Write no file unless asked, and if asked, write `REVIEW.md` in the `ultrareview` shape.

**The test:** the author can act on every finding without asking what you meant, and nothing the change breaks beyond the diff is left unexamined.

**Reply:** the intent line and the change set reviewed; a verdict (`ready`, `fix P1 and P2 first`, or `rethink`); findings in the `ultrareview` entry shape, most severe first; docs you changed; checks run and not run; open decisions.
