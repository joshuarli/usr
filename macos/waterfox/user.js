// ── DNS ───────────────────────────────────────────────────────────────────────
// Disable DoH entirely — queries go through the local Unbound resolver instead
user_pref("network.trr.mode", 5);

// ── Network ───────────────────────────────────────────────────────────────────
user_pref("network.http.max-connections", 900);
user_pref("network.http.max-persistent-connections-per-server", 10);
user_pref("network.http.speculative-parallel-limit", 0);   // no speculative pre-connects
user_pref("network.prefetch-next", false);                 // no <link rel="prefetch">
user_pref("network.predictor.enabled", false);             // no predictive prefetching
user_pref("network.dns.max_high_priority_threads", 8);
user_pref("network.dns.echconfig.enabled", true);          // Encrypted Client Hello
user_pref("network.http.http3.enabled", true);             // QUIC / HTTP3

// ── Cache ─────────────────────────────────────────────────────────────────────
user_pref("browser.cache.memory.enable", true);
user_pref("browser.cache.memory.capacity", 1048576); // 1 GB
user_pref("browser.cache.disk.capacity", 4000000);

// ── Rendering ─────────────────────────────────────────────────────────────────
user_pref("gfx.webrender.all", true);                      // GPU compositing
user_pref("nglayout.initialpaint.delay", 0);               // paint immediately, don't wait 250ms
user_pref("content.notify.interval", 100000);              // flush layout more frequently (default 120000µs)

// ── Request handling ──────────────────────────────────────────────────────────
user_pref("network.http.pacing.requests.enabled", false);  // no request throttling on fast connections
user_pref("network.ssl_tokens_cache_capacity", 32768);     // TLS session cache (default 2048) — fewer full handshakes

// ── Disk I/O ──────────────────────────────────────────────────────────────────
user_pref("browser.sessionstore.interval", 60000);         // save session every 60s not 15s

// ── Clear on shutdown ─────────────────────────────────────────────────────────
user_pref("privacy.clearOnShutdown.offlineApps", true);
user_pref("privacy.clearOnShutdown_v2.formdata", true);

// ── Security ──────────────────────────────────────────────────────────────────
user_pref("dom.security.https_only_mode", true);           // HTTPS-only mode

// ── Passwords / Autofill ──────────────────────────────────────────────────────
user_pref("signon.rememberSignons", false);
user_pref("signon.autofillForms", false);
user_pref("signon.management.page.breach-alerts.enabled", false);
user_pref("extensions.formautofill.addresses.enabled", false);
user_pref("extensions.formautofill.creditCards.enabled", false);
user_pref("browser.formfill.enable", false);

// ── New tab ───────────────────────────────────────────────────────────────────
user_pref("browser.startup.homepage", "about:blank");
user_pref("browser.newtabpage.enabled", false);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("browser.newtabpage.activity-stream.feeds.topsites", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.highlights", false);
user_pref("browser.newtabpage.activity-stream.section.highlights.includeBookmarks", false);
user_pref("browser.newtabpage.activity-stream.section.highlights.includeVisited", false);

// ── URL bar ───────────────────────────────────────────────────────────────────
user_pref("browser.urlbar.suggest.engines", false);
user_pref("browser.urlbar.suggest.openpage", false);
user_pref("browser.urlbar.suggest.quickactions", false);
user_pref("browser.urlbar.suggest.recentsearches", false);
user_pref("browser.urlbar.suggest.topsites", false);

// ── UX ────────────────────────────────────────────────────────────────────────
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.toolbars.bookmarks.visibility", "always");
user_pref("general.autoScroll", false);
user_pref("general.smoothScroll", false);
user_pref("layout.spellcheckDefault", 0);
user_pref("media.hardwaremediakeys.enabled", false);
user_pref("media.videocontrols.picture-in-picture.video-toggle.enabled", false);

// ── Autoplay ──────────────────────────────────────────────────────────────────
user_pref("media.autoplay.default", 5);                    // block all autoplay

// ── Enhanced Tracking Protection ─────────────────────────────────────────────
// Redundant with uBlock Origin — uBO's lists are a superset. Disabling avoids
// processing every request twice.
user_pref("privacy.trackingprotection.enabled", false);
user_pref("privacy.trackingprotection.pbmode.enabled", false);
user_pref("privacy.trackingprotection.socialtracking.enabled", false);
user_pref("privacy.trackingprotection.cryptomining.enabled", false);
user_pref("privacy.trackingprotection.fingerprinting.enabled", false);
user_pref("privacy.trackingprotection.emailtracking.pbmode.enabled", false);

// ── Safe Browsing ─────────────────────────────────────────────────────────────
// Uses a local blocklist, not real-time URL checks. uBO covers this.
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.safebrowsing.phishing.enabled", false);

// ── Background services / updates ─────────────────────────────────────────────
user_pref("app.update.auto", false);
user_pref("browser.search.update", false);
user_pref("app.normandy.enabled", false);                  // remote experiment system
user_pref("app.shield.optoutstudies.enabled", false);      // Firefox studies
user_pref("extensions.pocket.enabled", false);             // Pocket integration

// ── Notifications / background push ───────────────────────────────────────────
user_pref("dom.serviceWorkers.enabled", true);             // keep: needed for SW caching
user_pref("dom.webnotifications.enabled", false);
user_pref("dom.push.enabled", false);

// ── Extensions ────────────────────────────────────────────────────────────────
user_pref("extensions.autoDisableScopes", 0);              // allow sideloaded extensions (profile/extensions/) to auto-enable
