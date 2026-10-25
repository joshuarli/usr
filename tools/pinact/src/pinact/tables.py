"""Closed-world tables for workflow/action validation.

Each table lists only values whose universe is truly closed in the upstream
documentation. Source URLs are recorded here so a reader can re-check each
claim without trusting this file.

Sources:
- workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- events that trigger workflows: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- permissions: https://docs.github.com/en/actions/reference/workflows-and-actions/permissions
- metadata syntax for actions: https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax
- expression contexts: https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
- expression functions: https://docs.github.com/en/actions/reference/workflows-and-actions/expressions
"""

WORKFLOW_TOP_KEYS = frozenset({
    "name", "run-name", "on", "permissions", "env", "defaults",
    "concurrency", "jobs",
})

ACTION_TOP_KEYS = frozenset({
    "name", "description", "author", "inputs", "outputs", "runs", "branding",
})

JOB_KEYS = frozenset({
    "name", "needs", "permissions", "runs-on", "environment", "concurrency",
    "outputs", "env", "defaults", "if", "steps", "strategy",
    "services", "uses", "with", "secrets", "timeout-minutes",
    "continue-on-error", "container",
})

STEP_KEYS = frozenset({
    "id", "name", "if", "uses", "run", "with", "env", "shell",
    "working-directory", "continue-on-error", "timeout-minutes",
})

RUNS_KEYS = frozenset({"using", "main", "image", "steps", "pre", "post", "pre-if"})

PERMISSION_SCOPES = frozenset({
    "actions", "attestations", "checks", "contents", "deployments",
    "discussions", "id-token", "issues", "models", "packages", "pages",
    "pull-requests", "repository-projects", "security-events", "statuses",
})

PERMISSION_VALUES = frozenset({"read", "write", "none"})

PERMISSION_SHORTHANDS = frozenset({"read-all", "write-all", "{}"})

EVENTS = frozenset({
    "branch_protection_rule", "check_run", "check_suite", "create",
    "delete", "deployment", "deployment_status", "discussion",
    "discussion_comment", "fork", "gollum", "issue_comment", "issues",
    "label", "merge_group", "milestone", "page_build", "project",
    "project_card", "project_column", "public", "pull_request",
    "pull_request_review", "pull_request_review_comment",
    "pull_request_target", "push", "registry_package", "release",
    "repository_dispatch", "schedule", "status", "watch",
    "workflow_call", "workflow_dispatch", "workflow_run",
})
