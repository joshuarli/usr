TS_TAILNET ?= -
POLICY = policy.json
API = https://api.tailscale.com/api/v2/tailnet/$(TS_TAILNET)/acl
REMOTE = .work/tmp/policy.remote.json

.DEFAULT_GOAL := check

check:
	jaq empty $(POLICY)

fetch:
	@TS_API_KEY=$$(vault get TS_API_KEY 2>/dev/null); \
	[ -n "$$TS_API_KEY" ] || { echo "Failed to get TS_API_KEY from vault" >&2; exit 1; }; \
	mkdir -p .work/tmp; \
	curl -sS --fail-with-body -u "$$TS_API_KEY:" -H 'Accept: application/json' $(API) -o $(REMOTE); \
	jaq empty $(REMOTE)

apply: check
	@TS_API_KEY=$$(vault get TS_API_KEY 2>/dev/null); \
	[ -n "$$TS_API_KEY" ] || { echo "Failed to get TS_API_KEY from vault" >&2; exit 1; }; \
	ETAG=$$(curl -sS --fail-with-body -u "$$TS_API_KEY:" -H 'Accept: application/hujson' -D - -o /dev/null $(API) | tr -d '\r' | rg -i '^etag:' | cut -d' ' -f2-); \
	if [ -n "$$ETAG" ]; then SETMATCH="-H \"If-Match: $$ETAG\""; else SETMATCH=""; fi; \
	curl -sS --fail-with-body -u "$$TS_API_KEY:" -H 'Content-Type: application/hujson' $$SETMATCH --data-binary "@$(POLICY)" $(API)
