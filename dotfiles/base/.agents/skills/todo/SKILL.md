---
name: todo
description: "Apply when asked to save, defer, or ticket something for later (\"save this as a todo\"), or to keep a review's findings: file ABC-123 tickets with a P1 to P4 priority, and RFCs for designs. Skip work being done now and TODO comments in code."
---

# Todo

A deferred item is a ticket in a committed file, not a code comment, a chat reply, or memory. One shape means any ticket can be picked up cold, and review findings and todos are the same thing.

## Backlog

`TODO.md` at the repo root is the source of truth. Create an absent file with `Prefix: ABC` and `Next: 1`; choose a 3–4 uppercase letter prefix from the repo name and never change it. Use `todo list --json` to find possible matches and `todo show ABC-123 --json` for the full record. Use `todo add --json -` and `todo edit ABC-123 --json -` with JSON on standard input, and `todo close ABC-123` when done. Run `todo check` after changes. See `tools/todo/README.md` in the dotfiles repository for the record schema and commands. The CLI allocates IDs and orders tickets; never manually rewrite the backlog for these operations. Areas describe the affected domain, including Delegation.

Each ticket needs a problem title, area, evidence locations, problem and impact, smallest recommendation, implementation skill or `none`, and S/M/L effort. Say `unproven` for a P1 or P2 you could not prove. Link a design RFC when needed.

Rate by impact times likelihood, never by effort.

- **P1, fix now:** data loss or corruption, a security exposure, silently wrong results, or a broken build, release, or recovery path, on a reachable path.
- **P2, fix soon:** a real defect or structural risk that will cause incidents or tax every change, likely but not yet hit.
- **P3, plan:** a clear payoff at scale and no urgency.
- **P4, optional:** cheap, and never a nitpick.

## Filing

- **Filing is not doing.** Read only enough to fill `Where`, and make no code change for the ticket. File one ticket per independent item, and extend a match found with `todo list` and `todo show` instead of duplicating it.
- **Priority comes from the user.** When they give none, choose from the definitions and say it was assumed.
- **A review finding is a ticket as it stands.** An open decision that blocks one is a draft RFC linked from it.
- **Code never cites ticket IDs.** A reminder the code needs becomes a test or a check.
- A commit that finishes a ticket ends its body with `Closes ABC-123`.
- **Close a ticket with `todo close` when it is done.** Git history is the record, and no done list is kept. Delete its RFC in the same change when the RFC section calls that RFC done.
- **Campaign lanes never write `TODO.md`.** A lane reports a deferred item and the integrator files it.

## RFC

Write an RFC when a ticket's design is more than a few lines or needs the owner's sign-off. It lives at `docs/rfc/ABC-123-<slug>.md`, is linked from the ticket's `Design` field, and follows `technical-writing` in explanation mode.

It opens with `# ABC-123: <title>` and `Status: draft | accepted | rejected | superseded by ABC-456`, then the sections Summary, Motivation, Design, Alternatives considered, Open questions, and Decision.

**Delete an RFC when it is done.** Done means the design is in the code, or the RFC was rejected or superseded. Move any fact a future reader still needs into the doc that owns the topic, drop the ticket's `Design` link, and delete the file. Git history is the record. Do not leave a done list, and do not leave an accepted RFC next to code that already follows it. A draft stays. An accepted RFC that is still the spec to build stays, and is not rewritten in place.

**The test:** a newcomer can take the top ticket, find where to start, and begin without asking what it meant, and no ID appears twice in the file's history.

**Report:** the tickets and RFCs filed (ID, title, priority, given or assumed), the files changed, and that nothing was committed.
