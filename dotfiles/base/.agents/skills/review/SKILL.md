---
name: review
description: "Use for a requested read-only review, or a focused independent completion review of a consequential, high-risk implementation when uncertainty and impact justify it. Report demonstrated defects and supported risks. Skip routine implementation requests and changes, and repository-wide audits."
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Review

Review the requested change or the focused high-risk work, not the repository. This is read-only: report findings without editing code, docs, or tickets. Keep focused completion review separate from [ultrareview](../ultrareview/SKILL.md), which has broader effects.

## Rules

- **Keep the requested scope.** Review the files, behavior, decisions, or change set the user named, plus the surrounding code needed to judge it. For a requested branch review, include the branch diff and staged, unstaged, and untracked work; do not expand a focused review to every branch change. State the intent in one line, taken from the request and relevant decision history, and mark it assumed if you inferred it. An empty requested change set is a result: say so and stop.
- **Judge the change, not the surroundings.** Pre-existing problems are out of scope unless the change depends on them, worsens them, or its safety rests on them.
- **Independent review when justified.** For a consequential, uncertain review, give one independent reviewer the same intent, change, and relevant surrounding code. Prefer a different model family when allowed by [orchestrate](../orchestrate/SKILL.md). Do not add a paid provider or override model policy. The independent reviewer does not delegate another review. Independence helps find errors; agreement does not prove correctness, and a supported minority finding does not lose by vote.
- **The parent owns the verdict.** Reproduce or otherwise establish important findings. Distinguish defects from unsupported possibilities and explain why rejected findings are wrong. Do not invoke `ultrareview` as a shortcut.
- **Evidence for every finding:** judge the change's behavior and scope, skip linter-level nitpicks, and allow an empty result.
- **Follow the repo's instructions.** Read its AGENTS.md. Verify with the narrowest check that covers the change, not the whole suite, and report before starting anything expensive. No formatters, no commits, no pushes.

## Steps

1. **Scope.** Build the change set and the one-line intent. Read the full diff, then the code around each hunk and every caller of a changed symbol.
2. **Intent.** Does the change do what was asked, with nothing missing and nothing extra? A behavior change, or a change to an API, type, schema, permission, invariant, or transaction boundary that nobody asked for is a finding, and one the owner must be told about whatever its priority. A new dependency is not a finding by itself; check that it was vetted and stays within the project's performance gates.
3. **Consequences.** Use `blast-radius` only when a consequential change has a downstream safety assumption that source search cannot settle. Check measured claims with `benchmark-checklist`.
4. **Focused methods.** Apply only methods that match the changed surface. Use `reference-parity` for replacements and `root-cause` when a bug fix lacks an established cause. Inspect tests and duplicated facts when the review depends on them. Use `orchestrate` only when the change is too large to review alone.
5. **Prove findings.** A high-priority finding stands only after you establish the fact it depends on. Otherwise mark it `unproven` or lower its priority. Explain why a rejected finding is unsupported or incorrect.
6. **Report** findings in the reply. File no ticket or RFC during review-only work.

**The test:** every finding has evidence, the verdict reflects the strongest supported evidence, and review-only work leaves no edits.

**Report:** the intent line and change set reviewed; a verdict; findings, most severe first; evidence checked; checks run and not run; and open decisions.
