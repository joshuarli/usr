#!/usr/bin/env python3
"""Find, and optionally delete, old remote branches associated with closed PRs.

Branch tip dates come from GitHub's API; branch deletion is performed with
``git push --force-with-lease`` so GitHub's own receive-pack verifies the
branch is still at the observed tip OID before the delete is applied. The
default behavior is a dry run. A branch is eligible for deletion only when:

* it is a branch in the current repository, not a fork's branch;
* it has no open pull request;
* every associated pull request is closed, merged, and at least one year old;
* its latest commit is at least one calendar year old; and
* it is neither the default nor a protected branch.

A branch whose tip moved after the snapshot is refused, reported, and left
for a later run; closed but unmerged pull requests are printed for review but
are never deleted. ``gh`` is used for all API reads; ``git`` is used only for
the lease-protected deletion.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    branch: str
    state: str
    closed_at: datetime | None
    merged_at: datetime | None
    url: str


@dataclass(frozen=True)
class Branch:
    name: str
    last_commit_at: datetime
    tip_oid: str
    protected: bool
    associated_pull_requests: tuple[PullRequest, ...]
    associated_pull_requests_complete: bool


def run_gh(arguments: Sequence[str]) -> str:
    """Run gh and return stdout, including useful errors for failed requests."""
    try:
        result = subprocess.run(
            ["gh", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("gh CLI is not installed or is not on PATH") from None
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip()
        message = f"gh {' '.join(arguments)} failed"
        if details:
            message += f": {details}"
        raise RuntimeError(message) from error
    return result.stdout


def run_gh_json(arguments: Sequence[str]) -> Any:
    output = run_gh(arguments)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"gh returned invalid JSON: {error}") from error


def parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise RuntimeError(f"missing or invalid {field_name} timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"invalid {field_name} timestamp: {value}") from error
    if timestamp.tzinfo is None:
        raise RuntimeError(f"{field_name} timestamp has no timezone: {value}")
    return timestamp.astimezone(timezone.utc)


def one_year_ago(now: datetime) -> datetime:
    """Return the same instant in the preceding calendar year."""
    try:
        return now.replace(year=now.year - 1)
    except ValueError:
        # February 29 does not exist in a non-leap preceding year.
        return now.replace(year=now.year - 1, day=28)


def repository_name() -> str:
    repository = run_gh_json(["repo", "view", "--json", "nameWithOwner"])
    name = repository.get("nameWithOwner") if isinstance(repository, dict) else None
    if not isinstance(name, str):
        raise RuntimeError("could not determine the current GitHub repository")
    return name


def default_branch_name() -> str:
    repository = run_gh_json(["repo", "view", "--json", "defaultBranchRef"])
    default_branch = (
        repository.get("defaultBranchRef") if isinstance(repository, dict) else None
    )
    branch_name = default_branch.get("name") if isinstance(default_branch, dict) else None
    if not isinstance(branch_name, str):
        raise RuntimeError("could not determine the repository's default branch")
    return branch_name


def closed_pull_requests(
    cutoff: datetime,
) -> dict[str, list[PullRequest]]:
    # GitHub search returns at most 1,000 results. This is preferable to
    # downloading every historical PR in a large repository.
    pulls = run_gh_json(
        [
            "pr",
            "list",
            "--state",
            "closed",
            "--limit",
            "1000",
            "--search",
            f"closed:<{cutoff.date().isoformat()}",
            "--json",
            "number,title,headRefName,isCrossRepository,closedAt,mergedAt,url",
        ]
    )
    if not isinstance(pulls, list):
        raise RuntimeError("expected a JSON array from gh pr list")
    by_branch: dict[str, list[PullRequest]] = {}

    for pull in pulls:
        if not isinstance(pull, dict) or pull.get("isCrossRepository") is not False:
            continue
        head_branch = pull.get("headRefName")
        if not isinstance(head_branch, str):
            continue

        closed_at = parse_timestamp(pull.get("closedAt"), "closedAt")
        if closed_at > cutoff:
            continue
        merged_at_value = pull.get("mergedAt")
        merged_at = (
            parse_timestamp(merged_at_value, "merged_at")
            if merged_at_value is not None
            else None
        )
        number = pull.get("number")
        title = pull.get("title")
        url = pull.get("url")
        if (
            not isinstance(number, int)
            or not isinstance(title, str)
            or not isinstance(url, str)
        ):
            raise RuntimeError("GitHub returned a pull request with invalid fields")

        by_branch.setdefault(head_branch, []).append(
            PullRequest(
                number,
                title,
                head_branch,
                "MERGED" if merged_at is not None else "CLOSED",
                closed_at,
                merged_at,
                url,
            )
        )

    return by_branch


def branches(repository: str, names: set[str]) -> dict[str, Branch]:
    """Fetch only candidate branch refs, avoiding a repository-wide scan."""
    owner, name = repository.split("/", 1)
    result: dict[str, Branch] = {}
    branch_names = sorted(names)

    for offset in range(0, len(branch_names), 50):
        batch = branch_names[offset : offset + 50]
        fields = []
        for index, branch_name in enumerate(batch):
            qualified_name = json.dumps(f"refs/heads/{branch_name}")
            fields.append(
                f"""
                branch_{index}: ref(qualifiedName: {qualified_name}) {{
                  name
                  branchProtectionRule {{
                    allowsDeletions
                  }}
                  associatedPullRequests(first: 100) {{
                    nodes {{
                      number
                      title
                      state
                      closedAt
                      mergedAt
                      url
                    }}
                    pageInfo {{
                      hasNextPage
                    }}
                  }}
                  target {{
                    ... on Commit {{
                      oid
                      committedDate
                    }}
                  }}
                }}
                """
            )

        query = f"""
          query($owner: String!, $name: String!) {{
            repository(owner: $owner, name: $name) {{
              {"".join(fields)}
            }}
          }}
        """
        response = run_gh_json(
            [
                "api",
                "graphql",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-f",
                f"query={query}",
            ]
        )
        data = response.get("data") if isinstance(response, dict) else None
        repository_data = (
            data.get("repository") if isinstance(data, dict) else None
        )
        if not isinstance(repository_data, dict):
            raise RuntimeError("GitHub returned invalid branch GraphQL data")

        for index, branch_name in enumerate(batch):
            branch_data = repository_data.get(f"branch_{index}")
            if branch_data is None:
                # The PR's branch may have been deleted already.
                continue
            if not isinstance(branch_data, dict):
                raise RuntimeError("GitHub returned an invalid branch GraphQL object")
            branch_target = branch_data.get("target")
            committed_date = (
                branch_target.get("committedDate")
                if isinstance(branch_target, dict)
                else None
            )
            tip_oid = branch_target.get("oid") if isinstance(branch_target, dict) else None
            if not isinstance(tip_oid, str) or len(tip_oid) != 40 or any(
                character not in "0123456789abcdef" for character in tip_oid
            ):
                raise RuntimeError(
                    f"GitHub returned an invalid branch tip OID for {branch_name!r}"
                )
            protection = branch_data.get("branchProtectionRule")
            associated = branch_data.get("associatedPullRequests")
            associated_nodes = (
                associated.get("nodes") if isinstance(associated, dict) else None
            )
            associated_page_info = (
                associated.get("pageInfo") if isinstance(associated, dict) else None
            )
            if not isinstance(associated_nodes, list) or not isinstance(
                associated_page_info, dict
            ):
                raise RuntimeError("GitHub returned invalid associated PR data")

            associated_pull_requests: list[PullRequest] = []
            for pull in associated_nodes:
                if not isinstance(pull, dict):
                    raise RuntimeError("GitHub returned an invalid associated PR")
                number = pull.get("number")
                title = pull.get("title")
                state = pull.get("state")
                url = pull.get("url")
                if (
                    not isinstance(number, int)
                    or not isinstance(title, str)
                    or not isinstance(state, str)
                    or not isinstance(url, str)
                ):
                    raise RuntimeError(
                        "GitHub returned an associated PR with invalid fields"
                    )
                closed_at_value = pull.get("closedAt")
                merged_at_value = pull.get("mergedAt")
                associated_pull_requests.append(
                    PullRequest(
                        number=number,
                        title=title,
                        branch=branch_name,
                        state=state,
                        closed_at=(
                            parse_timestamp(closed_at_value, "closedAt")
                            if closed_at_value is not None
                            else None
                        ),
                        merged_at=(
                            parse_timestamp(merged_at_value, "mergedAt")
                            if merged_at_value is not None
                            else None
                        ),
                        url=url,
                    )
                )
            result[branch_name] = Branch(
                name=branch_name,
                last_commit_at=parse_timestamp(committed_date, "commit date"),
                tip_oid=tip_oid,
                protected=protection is not None,
                associated_pull_requests=tuple(associated_pull_requests),
                associated_pull_requests_complete=(
                    associated_page_info.get("hasNextPage") is False
                ),
            )
    return result


def _git(arguments: Sequence[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
    }
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError("git CLI is not installed or is not on PATH") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("git push timed out") from None


def repository_remote() -> tuple[str, list[str]]:
    data = run_gh_json(["repo", "view", "--json", "url,sshUrl"])
    if not isinstance(data, dict):
        raise RuntimeError("could not determine the repository remote URL")
    protocol = run_gh(["config", "get", "git_protocol"]).strip() or "https"
    if protocol == "ssh":
        ssh_url = data.get("sshUrl")
        if not isinstance(ssh_url, str) or not ssh_url:
            raise RuntimeError("could not determine the repository SSH URL")
        return ssh_url, []
    url = data.get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("could not determine the repository HTTPS URL")
    return url, ["-c", "credential.helper=!gh auth git-credential"]


def branch_tip(repository: str, branch: str) -> str | None:
    """Return the current tip OID, or None if the branch no longer exists."""
    owner, name = repository.split("/", 1)
    query = """
      query($owner: String!, $name: String!, $ref: String!) {
        repository(owner: $owner, name: $name) {
          ref(qualifiedName: $ref) {
            target {
              ... on Commit {
                oid
              }
            }
          }
        }
      }
    """
    response = run_gh_json(
        [
            "api",
            "graphql",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"ref=refs/heads/{branch}",
            "-f",
            f"query={query}",
        ]
    )
    data = response.get("data") if isinstance(response, dict) else None
    repository_data = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository_data, dict):
        raise RuntimeError("GitHub returned invalid branch ref data")
    ref = repository_data.get("ref")
    if ref is None:
        return None
    if not isinstance(ref, dict):
        raise RuntimeError("GitHub returned an invalid branch ref object")
    target = ref.get("target")
    oid = target.get("oid") if isinstance(target, dict) else None
    if not isinstance(oid, str):
        raise RuntimeError("GitHub returned an invalid branch tip OID")
    return oid


def delete_branch(repository: str, branch: str, expected_oid: str) -> str:
    """Delete ``branch`` only if the remote tip is still ``expected_oid``.

    Returns "deleted", "advanced" (tip moved; reported for a later run), or
    "already-gone". Raises RuntimeError when the delete cannot be performed
    and the ref's state cannot explain the failure.
    """
    if len(expected_oid) != 40 or any(
        character not in "0123456789abcdef" for character in expected_oid
    ):
        raise RuntimeError(f"refusing to delete {branch!r}: invalid tip OID")

    url, extra = repository_remote()
    ref = f"refs/heads/{branch}"
    scratch = tempfile.mkdtemp(prefix="close-stale-prs-")
    try:
        init = _git(["init", "-q"], cwd=scratch)
        if init.returncode:
            raise RuntimeError(f"git init failed: {init.stderr.strip()}")
        push = _git(
            [*extra, "push", f"--force-with-lease={ref}:{expected_oid}", url, "--delete", ref],
            cwd=scratch,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if push.returncode == 0:
        return "deleted"
    detail = push.stderr.strip() or push.stdout.strip() or "git push failed"
    try:
        tip = branch_tip(repository, branch)
    except RuntimeError as error:
        raise RuntimeError(
            f"git push failed to delete {branch}: {detail}; "
            f"could not re-check the branch tip: {error}"
        ) from error
    if tip is None:
        return "already-gone"
    if tip != expected_oid:
        return "advanced"
    raise RuntimeError(f"git push failed to delete {branch}: {detail}")


def print_pull_request(pull: PullRequest) -> None:
    status = pull.state.lower()
    closed_at = pull.closed_at.date().isoformat() if pull.closed_at else "open"
    print(
        f"    PR #{pull.number} [{status}] {closed_at} "
        f"{pull.url} — {pull.title}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Examples:\n"
        "  close-stale-prs.py\n"
        "  close-stale-prs.py --delete\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="only report candidates; this is the default",
    )
    mode.add_argument(
        "--delete",
        action="store_true",
        help="delete eligible branches through the GitHub API",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    dry_run = not arguments.delete
    now = datetime.now(timezone.utc)
    cutoff = one_year_ago(now)
    repository = repository_name()
    default_branch = default_branch_name()

    print(f"Repository: {repository}")
    print(f"Cutoff:     {cutoff.isoformat()}")
    print(f"Mode:       {'dry run' if dry_run else 'delete'}")

    closed = closed_pull_requests(cutoff)
    remote_branches = branches(repository, set(closed))

    candidates = 0
    skipped = 0
    deletion_failed = False
    for branch_name in sorted(closed):
        branch = remote_branches.get(branch_name)
        if branch is None or branch.last_commit_at > cutoff:
            continue

        print(f"\n{branch_name} (last commit {branch.last_commit_at.isoformat()})")
        for pull in branch.associated_pull_requests:
            print_pull_request(pull)

        reasons: list[str] = []
        if not branch.associated_pull_requests_complete:
            reasons.append("has more than 100 associated pull requests")
        if any(pull.state == "OPEN" for pull in branch.associated_pull_requests):
            reasons.append("has an open pull request")
        if branch_name == default_branch:
            reasons.append("is the default branch")
        if branch.protected:
            reasons.append("is protected")
        if any(
            pull.closed_at is not None and pull.closed_at > cutoff
            for pull in branch.associated_pull_requests
        ):
            reasons.append("has a pull request closed after the cutoff")
        if any(pull.state == "CLOSED" for pull in branch.associated_pull_requests):
            reasons.append("has a closed but unmerged pull request")

        if reasons:
            skipped += 1
            print(f"    SKIP: {'; '.join(reasons)}")
            continue

        candidates += 1
        if dry_run:
            print("    DRY RUN: would delete")
        else:
            try:
                outcome = delete_branch(repository, branch_name, branch.tip_oid)
            except RuntimeError as error:
                print(f"    ERROR: {error}", file=sys.stderr)
                deletion_failed = True
                continue
            if outcome == "deleted":
                print("    DELETED")
            elif outcome == "advanced":
                skipped += 1
                print("    SKIP: branch advanced since the snapshot; left for a later run")
            else:
                skipped += 1
                print("    SKIP: branch no longer exists")

    print(f"\nEligible branches: {candidates}")
    print(f"Skipped branches:  {skipped}")
    return 1 if deletion_failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
