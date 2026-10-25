from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
LAUNCHER = ROOT / "dotfiles" / "base" / ".local" / "bin" / "pinact"
RULE_FAMILIES = {
    "artipacked": "checkout-credentials",
    "checkout-credentials": "checkout-credentials",
    "cyclic-job-needs": "needs-cycle",
    "credential-exposure": "credential-exposure",
    "dangerous-trigger": "dangerous-trigger",
    "dangerous-triggers": "dangerous-trigger",
    "excessive-permissions": "excessive-permissions",
    "expression-syntax": "expression-syntax",
    "invalid-event-filter": "event-filter",
    "needs-cycle": "needs-cycle",
    "template-injection": "template-injection",
    "undefined-property": "undefined-property",
    "unpinned-uses": "unpinned-uses",
    "workflow-syntax": "event-filter",
    "yaml-syntax": "yaml-syntax",
}
DEFECTS = (
    ("actionlint/filter-typo.yml", 3, "event-filter", 2),
    ("catalog/rg-release.yml", 39, "unpinned-uses", 1),
    ("catalog/rg-release.yml", 39, "checkout-credentials", 3),
    ("catalog/rg-release.yml", 50, "unpinned-uses", 1),
    ("catalog/rg-release.yml", 64, "unpinned-uses", 1),
    ("custom/dangerous-checkout.yml", 1, "dangerous-trigger", 3),
    ("custom/dangerous-checkout.yml", 8, "checkout-credentials", 3),
    ("custom/dangerous-checkout.yml", 11, "template-injection", 3),
    ("custom/excessive-permissions.yml", 2, "excessive-permissions", 3),
    ("custom/expression-syntax.yml", 4, "expression-syntax", 2),
    ("custom/needs-cycle.yml", 3, "needs-cycle", 2),
    ("custom/secret-output.yml", 7, "credential-exposure", 3),
    ("custom/yaml-syntax.yml", 3, "yaml-syntax", 2),
    ("jactionlint/readme-example.yml", 3, "event-filter", 2),
    ("jactionlint/readme-example.yml", 8, "unpinned-uses", 1),
    ("jactionlint/readme-example.yml", 8, "checkout-credentials", 3),
    ("jactionlint/readme-example.yml", 9, "template-injection", 3),
    ("jactionlint/readme-example.yml", 10, "undefined-property", 2),
    ("repomod/mactop-release.yml", 20, "unpinned-uses", 1),
    ("repomod/mactop-release.yml", 20, "checkout-credentials", 3),
    ("repomod/mactop-release.yml", 23, "unpinned-uses", 1),
    ("repomod/mactop-release.yml", 37, "unpinned-uses", 1),
    ("repomod/mactop-release.yml", 51, "unpinned-uses", 1),
    ("repomod/zzz-release.yml", 23, "unpinned-uses", 1),
    ("repomod/zzz-release.yml", 23, "checkout-credentials", 3),
    ("repomod/zzz-release.yml", 27, "unpinned-uses", 1),
    ("repomod/zzz-release.yml", 46, "unpinned-uses", 1),
    ("repomod/zzz-release.yml", 57, "unpinned-uses", 1),
    ("usr/test.yml", 10, "checkout-credentials", 3),
    ("zizmor/artipacked.yml", 8, "checkout-credentials", 3),
    ("zizmor/template-injection.yml", 8, "template-injection", 3),
)
VALID = (
    "custom/safe-checkout.yml",
    "custom/safe-dynamic-input.yml",
    "repomod/test.yml",
)


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, check=False)


def lint_records(command: list[str], cwd: Path, environment: dict[str, str]) -> list[dict[str, object]]:
    result = run(command, cwd, environment)
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or f"{command[0]} exited {result.returncode}")
    if result.stderr:
        raise RuntimeError(f"{command[0]} wrote unexpected stderr: {result.stderr.strip()}")
    records = json.loads(result.stdout)
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise RuntimeError(f"{command[0]} returned invalid finding JSON")
    return records


def observations(records: list[dict[str, object]]) -> set[tuple[str, int, str]]:
    found = set()
    for record in records:
        path = record.get("filepath")
        line = record.get("line")
        rule = record.get("id")
        if not isinstance(path, str) or not isinstance(line, int) or not isinstance(rule, str):
            raise RuntimeError("linter returned an invalid finding record")
        family = RULE_FAMILIES.get(rule)
        if family is not None:
            found.add((Path(path).as_posix(), line, family))
    return found


def main() -> int:
    jactionlint = shutil.which("jactionlint")
    if jactionlint is None:
        raise RuntimeError("jactionlint is required for the local differential corpus")
    version = run([jactionlint, "--version"], FIXTURES, dict(os.environ))
    if version.returncode != 0:
        raise RuntimeError(version.stderr.strip() or "cannot read jactionlint version")
    scratch = ROOT / ".work" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["TMPDIR"] = str(scratch)
    files = sorted(path.relative_to(FIXTURES).as_posix() for path in FIXTURES.rglob("*.yml"))
    inputs = ["--", *files]
    commands = {
        "jactionlint": {
            profile: [jactionlint, f"--profile={profile}", "--no-online", "--format=json", *inputs]
            for profile in ("correctness", "default")
        },
        "pinact": {
            profile: [sys.executable, "-I", str(LAUNCHER), "lint", f"--profile={profile}", "--format=json", *inputs]
            for profile in ("correctness", "default")
        },
    }
    results: dict[str, set[tuple[str, int, str]]] = {}
    raw: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(dict)
    for tool, profiles in commands.items():
        combined: set[tuple[str, int, str]] = set()
        for profile, command in profiles.items():
            records = lint_records(command, FIXTURES, environment)
            raw[tool][profile] = records
            combined.update(observations(records))
        results[tool] = combined

    print(f"jactionlint: {version.stdout.splitlines()[0]}")
    print(f"fixtures: {len(files)} files across 7 source families")
    print(f"expected defects: {len(DEFECTS)}; weight denominator: {sum(item[3] for item in DEFECTS)}")
    print("family\tdefects\tweight\tjactionlint\tpinact\tjactionlint exact\tpinact exact")
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for path, line, family, weight in DEFECTS:
        family_counts[family]["defects"] += 1
        family_counts[family]["weight"] += weight
        for tool in results:
            if any(found_path == path and found_family == family for found_path, _, found_family in results[tool]):
                family_counts[family][tool] += 1
            if (path, line, family) in results[tool]:
                family_counts[family][f"{tool}-exact"] += 1
    for family in sorted(family_counts):
        counts = family_counts[family]
        print(
            f"{family}\t{counts['defects']}\t{counts['weight']}\t"
            f"{counts['jactionlint']}\t{counts['pinact']}\t"
            f"{counts['jactionlint-exact']}\t{counts['pinact-exact']}"
        )
    total_weight = sum(item[3] for item in DEFECTS)
    for tool in results:
        found_weight = sum(
            weight
            for path, line, family, weight in DEFECTS
            if (path, line, family) in results[tool]
        )
        category_weight = sum(
            weight
            for path, _, family, weight in DEFECTS
            if any(found_path == path and found_family == family for found_path, _, found_family in results[tool])
        )
        print(
            f"{tool} weighted recall: {found_weight}/{total_weight} exact; "
            f"{category_weight}/{total_weight} defect category"
        )
        missed = [
            f"{path}:{line}:{family}"
            for path, line, family, _ in DEFECTS
            if not any(found_path == path and found_family == family for found_path, _, found_family in results[tool])
        ]
        print(f"{tool} missed: {', '.join(missed) if missed else 'none'}")
        expected_families = {(path, family) for path, _, family, _ in DEFECTS}
        other_rules: Counter[str] = Counter()
        for records in raw[tool].values():
            for record in records:
                path = record.get("filepath")
                rule = record.get("id")
                family = RULE_FAMILIES.get(rule) if isinstance(rule, str) else None
                if isinstance(path, str) and isinstance(rule, str) and (
                    family is None or (Path(path).as_posix(), family) not in expected_families
                ):
                    other_rules[rule] += 1
        rendered = ", ".join(f"{rule}×{count}" for rule, count in sorted(other_rules.items()))
        print(f"{tool} other rule findings (unscored): {rendered or 'none'}")

    print("valid files\tjactionlint correctness errors\tpinact correctness errors")
    for path in VALID:
        counts = []
        for tool in raw:
            errors = [
                record
                for record in raw[tool]["correctness"]
                if record.get("filepath") == path and record.get("severity") == "error"
            ]
            counts.append(str(len(errors)))
        print(f"{path}\t{counts[0]}\t{counts[1]}")

    snapshots = {path: (FIXTURES / path).read_bytes() for path in files}
    fix = run(
        [sys.executable, "-I", str(LAUNCHER), "fix", "--diff", *files],
        FIXTURES,
        environment,
    )
    if fix.returncode not in {0, 1}:
        raise RuntimeError(fix.stderr.strip() or f"pinact fix --diff exited {fix.returncode}")
    if any((FIXTURES / path).read_bytes() != data for path, data in snapshots.items()):
        raise RuntimeError("pinact fix --diff changed a corpus fixture")
    print(
        f"fix --diff safety: rc={fix.returncode}; source bytes unchanged across "
        f"{len(files)} files; no fixture was written"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"pinact corpus: {error}", file=sys.stderr)
        raise SystemExit(2) from None
