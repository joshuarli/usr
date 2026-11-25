#!/bin/sh
# Tests the cargo wrappers: with kache installed they invoke it with the same
# argv cargo used to give the compiler, and without kache or clang they fall
# back to rustc, cc, or c++, passing every argument through unchanged.

set -u

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
wrappers="$script_dir/base/.local/bin"
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
scratch=$(mktemp -d "$work_root/cargo-wrappers.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0

make_fake() {
    fake_dir=$1
    fake_name=$2
    mkdir -p "$fake_dir"
    cat > "$fake_dir/$fake_name" <<'EOF'
#!/bin/sh
{
    printf '%s\n' "$0"
    for argument in "$@"; do
        printf '%s\n' "$argument"
    done
} >> "$CARGO_WRAPPER_TEST_LOG"
EOF
    chmod +x "$fake_dir/$fake_name"
}

full="$scratch/full"
clang_only="$scratch/clang-only"
plain="$scratch/plain"
for tool in kache clang clang++ cc c++ rustc; do
    make_fake "$full" "$tool"
done
for tool in clang clang++ cc c++ rustc; do
    make_fake "$clang_only" "$tool"
done
for tool in cc c++ rustc; do
    make_fake "$plain" "$tool"
done

run_wrapper() {
    wrapper_dir=$1
    wrapper_name=$2
    wrapper_log=$3
    shift 3
    : > "$wrapper_log"
    PATH="$wrapper_dir" CARGO_WRAPPER_TEST_LOG="$wrapper_log" \
        /bin/sh "$(case $wrapper_name in */*) printf '%s' "$wrapper_name" ;; *) printf '%s' "$wrappers/$wrapper_name" ;; esac)" "$@"
}

expect_argv() {
    expected_log=$1
    expected_log_file="$scratch/expected"
    shift
    printf '%s\n' "$@" > "$expected_log_file"
    if ! cmp -s "$expected_log_file" "$expected_log"; then
        printf 'expected argv:\n' >&2
        cat "$expected_log_file" >&2
        printf 'actual argv:\n' >&2
        cat "$expected_log" >&2
        return 1
    fi
}

case_config_names_the_wrappers() {
    config="$script_dir/base/.cargo/config.toml"
    grep -Fx 'rustc-wrapper = ".cargo/bin/kache"' "$config" >/dev/null
    grep -Fx 'HOST_CC = "cargo-wrapper-cc"' "$config" >/dev/null
    grep -Fx 'HOST_CXX = "cargo-wrapper-cxx"' "$config" >/dev/null
    grep -Fx 'CC_KNOWN_WRAPPER_CUSTOM = "kache"' "$config" >/dev/null
    if grep -Eq 'kache clang' "$config"; then
        return 1
    fi
    for wrapper in cargo-wrapper-cc cargo-wrapper-cxx; do
        [ -x "$wrappers/$wrapper" ]
    done
}

case_kache_wraps_every_compiler() {
    log="$scratch/full.log"
    run_wrapper "$full" cargo-wrapper-cc "$log" -c "a file.c"
    expect_argv "$log" "$full/kache" clang -c "a file.c"
    run_wrapper "$full" cargo-wrapper-cxx "$log" -c "b file.cc"
    expect_argv "$log" "$full/kache" clang++ -c "b file.cc"
}

case_clang_without_kache_is_used_directly() {
    log="$scratch/clang-only.log"
    run_wrapper "$clang_only" cargo-wrapper-cc "$log" -c "a file.c"
    expect_argv "$log" "$clang_only/clang" -c "a file.c"
    run_wrapper "$clang_only" cargo-wrapper-cxx "$log" -c "b file.cc"
    expect_argv "$log" "$clang_only/clang++" -c "b file.cc"
}

case_plain_host_tools_are_the_last_resort() {
    log="$scratch/plain.log"
    run_wrapper "$plain" cargo-wrapper-cc "$log" -c "a file.c"
    expect_argv "$log" "$plain/cc" -c "a file.c"
    run_wrapper "$plain" cargo-wrapper-cxx "$log" -c "b file.cc"
    expect_argv "$log" "$plain/c++" -c "b file.cc"
}

case_rustc_wrapper_keeps_hyphenated_cargo_variables() {
    command -v python3 >/dev/null
    home="$scratch/home"
    mkdir -p "$home/.cargo/bin"
    wrapper=$(sed -n 's/^rustc-wrapper = "\(.*\)"$/\1/p' "$script_dir/base/.cargo/config.toml")
    printf '%s\n' '#!/usr/bin/env python3' 'import os' 'print(os.environ.get("CARGO_BIN_EXE_hyphen-bin", "missing"))' > "$home/$wrapper"
    chmod +x "$home/$wrapper"
    [ "$(env 'CARGO_BIN_EXE_hyphen-bin=/target/hyphen-bin' "$home/$wrapper")" = /target/hyphen-bin ]
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

run_case 'the cargo config names the wrapper programs' case_config_names_the_wrappers
run_case 'kache wraps clang and clang++ with unchanged argv' case_kache_wraps_every_compiler
run_case 'the rustc wrapper is a program that keeps hyphenated Cargo variables' case_rustc_wrapper_keeps_hyphenated_cargo_variables
run_case 'clang is used directly when kache is absent' case_clang_without_kache_is_used_directly
run_case 'cc and c++ are the last resort when clang is absent' case_plain_host_tools_are_the_last_resort

echo "testing finished."
[ "$nfailed" -eq 0 ]
