#!/bin/sh
# Tests for the yt-dlp shim: it installs the upstream nightly zipapp, verifies its checksum,
# checks for updates at most once a day, and runs the installed version with unchanged arguments.

set -u

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
shim="$script_dir/base/.local/bin/yt-dlp"
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
scratch=$(mktemp -d "$work_root/yt-dlp-shim.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
mock_bin="$scratch/bin"
mkdir -p "$mock_bin"

cat > "$mock_bin/curl" <<'EOF'
#!/bin/sh
set -eu

url=
output=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) output=$2; shift 2 ;;
        -w) shift 2 ;;
        --connect-timeout|--max-time) shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done
printf '%s\n' "$url" >> "$SHIM_TEST_LOG"

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

emit() {
    if [ -n "$output" ]; then
        cat > "$output"
    else
        cat
    fi
}

case "$url" in
    */releases/latest)
        if [ "${SHIM_TEST_OFFLINE:-false}" = true ]; then exit 22; fi
        printf '%s\n' "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/tag/${SHIM_TEST_TAG}"
        ;;
    */download/*/SHA2-256SUMS)
        sum=$(sha256_of "$SHIM_TEST_ASSET_FILE")
        if [ "${SHIM_TEST_BAD_SUM:-false}" = true ]; then
            sum=0000000000000000000000000000000000000000000000000000000000000000
        fi
        printf '%s  yt-dlp\n' "$sum" | emit
        ;;
    */download/*/yt-dlp)
        [ -n "$output" ] || exit 1
        cat "$SHIM_TEST_ASSET_FILE" > "$output"
        ;;
    *)
        exit 22
        ;;
esac
EOF
chmod +x "$mock_bin/curl"

make_asset() {
    asset_path="$scratch/asset-$1"
    {
        printf '#!/bin/sh\n'
        printf "printf '%%s' 'mock-yt-dlp %s'\n" "$1"
        printf 'printf " [%%s]" "$@"\n'
        printf 'printf "\\n"\n'
    } > "$asset_path"
    printf '%s\n' "$asset_path"
}

run_shim() {
    shim_data=$1
    shim_state=$2
    shim_log=$3
    shim_tag=$4
    shim_asset=$5
    shift 5
    env XDG_DATA_HOME="$shim_data" XDG_STATE_HOME="$shim_state" \
        PATH="$mock_bin:/usr/bin:/bin:/usr/sbin:/sbin" \
        SHIM_TEST_LOG="$shim_log" SHIM_TEST_TAG="$shim_tag" \
        SHIM_TEST_ASSET_FILE="$shim_asset" \
        SHIM_TEST_BAD_SUM="${bad_sum:-false}" \
        SHIM_TEST_OFFLINE="${offline:-false}" \
        "$shim" "$@"
}

case_n=0
nfailed=0
run_case() {
    case_n=$((case_n + 1))
    case_label=$1
    shift
    if (set -e; "$@"); then
        printf 'ok: %s\n' "$case_label"
    else
        printf 'FAIL case %d: %s\n' "$case_n" "$case_label" >&2
        nfailed=$((nfailed + 1))
    fi
}

case_cold_install() {
    data="$scratch/cold/data"
    state="$scratch/cold/state"
    log="$scratch/cold/curl.log"
    tag=2026.10.29.232701
    asset=$(make_asset "$tag")
    bad_sum=false
    offline=false
    out=$(run_shim "$data" "$state" "$log" "$tag" "$asset" -f best https://example.test/v)
    [ "$out" = "mock-yt-dlp $tag [-f] [best] [https://example.test/v]" ]
    [ -x "$data/yt-dlp/yt-dlp" ]
    [ "$(cat "$state/yt-dlp/version")" = "$tag" ]
    [ "$(grep -c '/releases/latest' "$log")" -eq 1 ]
}

case_skips_check_within_a_day() {
    data="$scratch/cached/data"
    state="$scratch/cached/state"
    log="$scratch/cached/curl.log"
    tag=2026.10.29.232701
    asset=$(make_asset "$tag")
    bad_sum=false
    offline=false
    run_shim "$data" "$state" "$log" "$tag" "$asset" --version >/dev/null
    out=$(run_shim "$data" "$state" "$log" "$tag" "$asset" --version)
    [ "$out" = "mock-yt-dlp $tag [--version]" ]
    [ "$(grep -c '/releases/latest' "$log")" -eq 1 ]
}

case_updates_after_a_day() {
    data="$scratch/update/data"
    state="$scratch/update/state"
    log="$scratch/update/curl.log"
    first=2026.10.29.232701
    second=2026.10.31.000000
    first_asset=$(make_asset "$first")
    second_asset=$(make_asset "$second")
    bad_sum=false
    offline=false
    run_shim "$data" "$state" "$log" "$first" "$first_asset" --version >/dev/null
    printf '0\n' > "$state/yt-dlp/checked"
    out=$(run_shim "$data" "$state" "$log" "$second" "$second_asset" --version)
    [ "$out" = "mock-yt-dlp $second [--version]" ]
    [ "$(cat "$state/yt-dlp/version")" = "$second" ]
    [ "$(grep -c '/releases/latest' "$log")" -eq 2 ]
}

case_same_version_skips_download() {
    data="$scratch/same/data"
    state="$scratch/same/state"
    log="$scratch/same/curl.log"
    tag=2026.10.29.232701
    asset=$(make_asset "$tag")
    bad_sum=false
    offline=false
    run_shim "$data" "$state" "$log" "$tag" "$asset" --version >/dev/null
    printf '0\n' > "$state/yt-dlp/checked"
    out=$(run_shim "$data" "$state" "$log" "$tag" "$asset" --version)
    [ "$out" = "mock-yt-dlp $tag [--version]" ]
    [ "$(grep -c '/releases/latest' "$log")" -eq 2 ]
    [ "$(grep -c 'SHA2-256SUMS' "$log")" -eq 1 ]
}

case_bad_checksum_keeps_installed_version() {
    data="$scratch/badsum/data"
    state="$scratch/badsum/state"
    log="$scratch/badsum/curl.log"
    first=2026.10.29.232701
    second=2026.10.31.000000
    first_asset=$(make_asset "$first")
    second_asset=$(make_asset "$second")
    bad_sum=false
    offline=false
    run_shim "$data" "$state" "$log" "$first" "$first_asset" --version >/dev/null
    printf '0\n' > "$state/yt-dlp/checked"
    bad_sum=true
    out=$(run_shim "$data" "$state" "$log" "$second" "$second_asset" --version 2>"$scratch/badsum.err")
    [ "$out" = "mock-yt-dlp $first [--version]" ]
    [ "$(cat "$state/yt-dlp/version")" = "$first" ]
    grep -q 'checksum mismatch' "$scratch/badsum.err"
}

case_failed_check_uses_installed_version() {
    data="$scratch/offline/data"
    state="$scratch/offline/state"
    log="$scratch/offline/curl.log"
    tag=2026.10.29.232701
    asset=$(make_asset "$tag")
    bad_sum=false
    offline=false
    run_shim "$data" "$state" "$log" "$tag" "$asset" --version >/dev/null
    printf '0\n' > "$state/yt-dlp/checked"
    offline=true
    out=$(run_shim "$data" "$state" "$log" "$tag" "$asset" --version 2>"$scratch/offline.err")
    [ "$out" = "mock-yt-dlp $tag [--version]" ]
    grep -q 'update check failed' "$scratch/offline.err"
}

case_failed_check_without_install_fails() {
    data="$scratch/noinstall/data"
    state="$scratch/noinstall/state"
    log="$scratch/noinstall/curl.log"
    tag=2026.10.29.232701
    asset=$(make_asset "$tag")
    bad_sum=false
    offline=true
    if out=$(run_shim "$data" "$state" "$log" "$tag" "$asset" --version 2>"$scratch/noinstall.err"); then
        return 1
    fi
    [ -z "$out" ]
    grep -q 'update check failed and no version is installed' "$scratch/noinstall.err"
}

run_case 'a cold start installs the nightly and passes arguments through' case_cold_install
run_case 'a second run within a day does not check upstream' case_skips_check_within_a_day
run_case 'an expired check installs a newer nightly' case_updates_after_a_day
run_case 'an expired check with the same nightly does not download it again' case_same_version_skips_download
run_case 'a bad checksum keeps the installed version' case_bad_checksum_keeps_installed_version
run_case 'a failed check uses the installed version' case_failed_check_uses_installed_version
run_case 'a failed check without an install fails' case_failed_check_without_install_fails

echo "testing finished."
[ "$nfailed" -eq 0 ]
