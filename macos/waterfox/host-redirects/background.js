const REDIRECTS = {
    "www.reddit.com": "old.reddit.com",
    "new.reddit.com": "old.reddit.com",
};

const PATTERNS = Object.keys(REDIRECTS).map(h => "*://" + h + "/*");

browser.webRequest.onBeforeRequest.addListener(
    function(details) {
        const url = new URL(details.url);
        const dest = REDIRECTS[url.hostname];
        if (dest) {
            url.hostname = dest;
            return { redirectUrl: url.href };
        }
    },
    { urls: PATTERNS, types: ["main_frame"] },
    ["blocking"]
);
