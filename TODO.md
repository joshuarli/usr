Prefix: USR
Next: 75
















### USR-73 · P3 · The refactor-web-ui skill has only been applied to agentctl

- **Area:** Skills
- **Where:** dotfiles/base/.agents/skills/refactor-web-ui/SKILL.md; docs/CAMPAIGN-AGENTCTL-WEB-UI.md: Transfer after agentctl
- **Problem:** The skill was exercised and sharpened on one product only. Its rules have not been tested against a dashboard (stats), a developer tool with canvas rendering (stuff), or a reading/research product (discover), so overfit rules cannot yet be told apart from transferable ones.
- **Recommendation:** On separate requests, apply the skill to stats (with refactor-dashboard-ui owning metrics and trends), stuff (keep canvas rendering and its performance invariants), and discover (evidence and provenance hierarchy, mobile reading). Follow the campaign's Transfer section, and after the second product delete or move rules that turned out to be agentctl-specific.
- **Fix with:** none
- **Effort:** L


### USR-74 · P3 · Designed UIs lack the required make preview and shared golden dataset

- **Area:** Skills
- **Where:** refactor-web-ui skill: Preview and goldens; repos discover, niceforge, laputa-ui-dashboard, stats
- **Problem:** refactor-web-ui now requires every designed UI to ship `make preview` on one canonical mock dataset that its integration goldens also use. On 2026-11-15 discover, niceforge and laputa-ui-dashboard have no `make preview`; stats has one, but whether its preview data is the same dataset its tests use is unverified. agentctl conforms; stuff gains it in its redesign.
- **Recommendation:** Per repo, on its own request: extract the fixture its browser tests seed into one dataset module, serve it with `make preview`, and add a semantic golden over the same dataset. For stats, check that preview and tests share one dataset before changing anything.
- **Fix with:** none
- **Effort:** M

