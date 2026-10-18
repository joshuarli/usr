#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
test_root=$(mktemp -d "$work_root/gh-cancel-pr-runs.XXXXXX")
trap 'rm -rf "$test_root"' 0
trap 'exit 1' HUP INT TERM

mock_bin="$test_root/bin"
mkdir -p "$mock_bin"
cat > "$mock_bin/gh" <<'EOF'
#!/bin/sh
case "$1 $2" in
    "pr view")
        printf '%s\n' commit-sha
        ;;
    "run list")
        exit "${GH_RUN_LIST_STATUS:-0}"
        ;;
    *)
        exit 64
        ;;
esac
EOF
chmod +x "$mock_bin/gh"

if output=$(PATH="$mock_bin:$PATH" GH_RUN_LIST_STATUS=37 \
    sh "$repo_root/dotfiles/base/.local/bin/gh-cancel-pr-runs" \
    --repo owner/name 2>&1); then
    status=0
else
    status=$?
fi
[ "$status" -eq 37 ] || {
    printf 'failed gh run list exited %s instead of 37\n%s\n' "$status" "$output" >&2
    exit 1
}

output=$(PATH="$mock_bin:$PATH" GH_RUN_LIST_STATUS=0 \
    sh "$repo_root/dotfiles/base/.local/bin/gh-cancel-pr-runs" \
    --repo owner/name 2>&1)
[ "$output" = 'no active runs found for commit-sha' ] || {
    printf 'unexpected output for an empty successful list:\n%s\n' "$output" >&2
    exit 1
}
