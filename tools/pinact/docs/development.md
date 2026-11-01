# Pinact development

The source lives in `src/pinact/`; the launcher resolves this tree through the `sh sync`
links and runs under `python3 -I`. Pinact vendors pure-Python PyYAML 6.0.3 under
`src/pinact/_vendor/yaml/`; its MIT license and source details are in `PROVENANCE.txt`.

Run the focused suites from the repository root:

```sh
mkdir -p .work/tmp
for test in test_pinact.py tests/test_yaml.py tests/test_lint_rules.py tests/test_expressions.py tests/test_security.py tests/test_fix.py; do
  PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I "tools/pinact/$test" || exit
done
```

The differential corpus and its limits are described in the [coverage report](../tests/fixtures/coverage.md).
See the [compatibility report](compatibility.md) for the supported workflow surface and known gaps.
