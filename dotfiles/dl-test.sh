#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
test_root=$(mktemp -d "$work_root/dl.XXXXXX")
trap 'rm -rf "$test_root"' 0
trap 'exit 1' HUP INT TERM
mock_bin="$test_root/bin"
home="$test_root/home"
mkdir -p "$mock_bin" "$home" "$test_root/tmp"

cat > "$mock_bin/curl" <<'EOF'
#!/bin/sh
set -eu

url=
output=
headers=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) output=$2; shift 2 ;;
        -D) headers=$2; shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done

case "$url" in
    https://api.meta.ai/muse-code/channels/muse-stable)
        printf '%s\n' '{"version":"1.4.9-R6297.1","manifest_url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json"}'
        ;;
    'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json')
        printf '%s\n' '{"version":"1.4.9-R6297.1","artifacts":{"x86_linux":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_linux"},"aarch64_linux":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=aarch64_linux"},"x86_macos":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_macos"},"aarch64_macos":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=aarch64_macos"}}}'
        ;;
    https://lookaside.facebook.com/lookaside/muse/download/*)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: muse-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'muse-test-binary' > "$output"
        else
            exit 1
        fi
        ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/curl"

if output=$(HOME="$home" TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi

case "$output" in
    *"Installed $home/.local/bin/muse"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$home/.local/bin/muse")" = muse-test-binary ]
