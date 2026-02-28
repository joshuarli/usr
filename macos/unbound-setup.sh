#!/usr/bin/env bash
set -euo pipefail

# ── helpers ────────────────────────────────────────────────────────────────────
info() { printf '\e[1;32m==> \e[0m%s\n' "$*"; }
warn() { printf '\e[1;33mwarn:\e[0m %s\n' "$*"; }
die()  { printf '\e[1;31merr:\e[0m %s\n' "$*" >&2; exit 1; }

# ── preflight ──────────────────────────────────────────────────────────────────
command -v brew &>/dev/null || die "Homebrew not found"

BREW_PREFIX=$(brew --prefix)
CONF_DIR="$BREW_PREFIX/etc/unbound"
CONF="$CONF_DIR/unbound.conf"

# ── install ────────────────────────────────────────────────────────────────────
if brew list unbound &>/dev/null; then
    info "unbound already installed"
else
    info "Installing unbound..."
    brew install unbound
fi

# ── tuning: auto-detect cores and compute cache slabs ─────────────────────────
NUM_THREADS=$(sysctl -n hw.physicalcpu)
SLABS=1
while (( SLABS < NUM_THREADS )); do (( SLABS *= 2 )); done

info "Detected $NUM_THREADS physical cores → $SLABS cache slabs"

# ── config ─────────────────────────────────────────────────────────────────────
info "Writing $CONF"
mkdir -p "$CONF_DIR"

cat > "$CONF" <<EOF
server:
    # ── Interface ───────────────────────────────────────────────────────────────
    interface: 127.0.0.1
    interface: ::1
    port: 53
    do-ip4: yes
    do-ip6: yes
    do-udp: yes
    do-tcp: yes

    # ── Access control ──────────────────────────────────────────────────────────
    access-control: 0.0.0.0/0 refuse
    access-control: ::0/0 refuse
    access-control: 127.0.0.0/8 allow
    access-control: ::1 allow

    # ── Identity ────────────────────────────────────────────────────────────────
    hide-identity: yes
    hide-version: yes
    username: ""  # don't drop priv

    # ── No DNSSEC, no qname minimisation ────────────────────────────────────────
    qname-minimisation: no

    # ── Cache ───────────────────────────────────────────────────────────────────
    cache-min-ttl: 300          # ignore TTLs under 5 min, stops cache thrashing
    cache-max-ttl: 86400
    cache-max-negative-ttl: 30
    prefetch: yes               # refresh records before expiry in background
    neg-cache-size: 8m

    # ── Serve stale ─────────────────────────────────────────────────────────────
    # answer instantly from cache while refreshing in background
    serve-expired: yes
    serve-expired-ttl: 86400
    serve-expired-reply-ttl: 30

    # ── Threading (auto-tuned) ──────────────────────────────────────────────────
    num-threads: $NUM_THREADS
    msg-cache-slabs: $SLABS
    rrset-cache-slabs: $SLABS
    infra-cache-slabs: $SLABS
    key-cache-slabs: $SLABS

    # ── Memory ──────────────────────────────────────────────────────────────────
    msg-cache-size: 64m
    rrset-cache-size: 128m

    # ── Network buffers ─────────────────────────────────────────────────────────
    so-rcvbuf: 4m
    so-sndbuf: 4m
    edns-buffer-size: 1472      # 1500 MTU - 28 byte headers, avoids fragmentation

    # ── Misc ────────────────────────────────────────────────────────────────────
    minimal-responses: yes
    rrset-roundrobin: yes

    # ── DNS rebinding protection (free, keep it) ─────────────────────────────────
    private-address: 10.0.0.0/8
    private-address: 172.16.0.0/12
    private-address: 192.168.0.0/16
    private-address: 169.254.0.0/16
    private-address: fd00::/8
    private-address: fe80::/10

    # ── Logging ─────────────────────────────────────────────────────────────────
    verbosity: 0
    log-queries: no
    log-replies: no

# ── Forward all queries to Cloudflare ───────────────────────────────────────────
forward-zone:
    name: "."
    forward-addr: 1.1.1.1
    forward-addr: 1.0.0.1
EOF

# ── service ────────────────────────────────────────────────────────────────────
info "Restarting unbound service..."
sudo brew services stop unbound 2>/dev/null || true
sudo brew services start unbound

# give it a moment to bind to port 53
sleep 1

# sanity check it's running before touching DNS settings
sudo brew services list | grep -q 'unbound.*started' \
    || die "unbound failed to start — run: sudo brew services list"

# ── system DNS ────────────────────────────────────────────────────────────────
# 1.1.1.1 is the fallback in case unbound goes down — remove if you prefer hard failure
info "Setting DNS on all active network services..."
while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    printf '   %-35s → 127.0.0.1 (fallback: 1.1.1.1)\n' "$svc"
    sudo networksetup -setdnsservers "$svc" 127.0.0.1 1.1.1.1
done < <(networksetup -listallnetworkservices | grep -v '^\*' | tail -n +2)

# ── verify ────────────────────────────────────────────────────────────────────
info "Verifying..."
if ! dig @127.0.0.1 example.com +short | grep -q '.'; then
    die "unbound not responding — check logs: log2 /var/log/unbound.log"
fi

COLD=$(dig @127.0.0.1 example.com | awk '/Query time/ {print $4}')
WARM=$(dig @127.0.0.1 example.com | awk '/Query time/ {print $4}')

printf '\n'
info "Cold query: ${COLD}ms"
info "Warm query: ${WARM}ms (from cache)"
printf '\n'
info "All done."
info "Monitor stats:  sudo unbound-control stats_noreset"
info "Flush cache:    sudo unbound-control flush_zone ."
info "Reload config:  sudo unbound-control reload"
