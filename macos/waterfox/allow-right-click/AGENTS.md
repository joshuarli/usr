# Allow Right-Click — Extension Architecture

Browser extension that restores right-click context menus, text selection, copy/paste, and drag on websites that block them. All extension code lives under `v3/` (Manifest V3).

## File Map

```
v3/
├── manifest.json              # MV3 config: permissions, service worker, action
├── worker.js                  # Background service worker — activation, message routing, automation
├── context.js                 # Context menu setup (loaded before worker.js)
├── _locales/{en,sv-SE}/       # i18n strings, used via chrome.i18n.getMessage()
├── data/
│   ├── icons/                 # Gray (inactive), blue (active), purple (automated)
│   ├── monitor.js             # Tiny content script injected by automation — sends 'simulate-click'
│   ├── options/               # Options page: hostname whitelist, permissions, factory reset
│   │   ├── index.html
│   │   ├── index.js
│   │   └── index.css
│   └── inject/                # Scripts injected into web pages
│       ├── core.js            # Entry point — toggles activation state, requests script injection
│       ├── mouse.js           # Right-click/long-press handler — unblocks overlay elements
│       ├── styles.js          # Injects CSS for selection highlight and pointer-events overrides
│       ├── test.js            # No-op script used to validate URL match patterns in options
│       ├── user-select/
│       │   ├── isolated.js    # Strips user-select:none from stylesheets and inline styles
│       │   └── main.js        # Overrides Selection.prototype.removeAllRanges to prevent deselection
│       └── listen/
│           ├── isolated.js    # Captures and stops propagation of blocked events (copy, cut, contextmenu, etc.)
│           └── main.js        # Overrides MouseEvent/ClipboardEvent.preventDefault and window.alert
```

## Activation Flow

1. **User clicks toolbar icon** → `worker.js:onClicked()` injects `core.js` into all frames via `chrome.scripting.executeScript`.
2. **`core.js`** checks `window.pointers.status`:
   - If `''` or `'removed'` → sets status to `'ready'`, sends `{method: 'inject'}` message listing which scripts to inject.
   - If `'ready'` → sets status to `'removed'`, runs all cleanup functions from `window.pointers.run`, dispatches `'arc-remove'` event (for MAIN world cleanup), restores cached inline styles from `window.pointers.cache`.
3. **`worker.js`** receives the `'inject'` message, updates the toolbar icon, then injects:
   - **Protected scripts** (isolated content-script world): `user-select/isolated.js`, `styles.js`, `mouse.js`, `listen/isolated.js`
   - **Unprotected scripts** (`world: 'MAIN'`): `user-select/main.js`, `listen/main.js`

Two injection worlds are needed because isolated scripts can't touch page JS globals (like `MouseEvent.prototype`), and MAIN world scripts can't use `chrome.*` APIs.

## What Each Injected Script Does

### `mouse.js` (isolated)
Listens for `mousedown` (button 2 = right-click) and `touchstart` (long-press) at the capture phase. On trigger:
- Temporarily sets `pointer-events: all` on `img`/`canvas`/`video` elements near the click.
- Calls `document.elementsFromPoint()` to find what's under the cursor.
- Prioritizes: video > image/canvas > text inputs. Sets `pointer-events: none` on overlapping overlay elements so the browser context menu targets the right thing.
- For elements with only a CSS background-image, creates a tiny invisible `<img>` at the click point so "Save Image" appears in the context menu.
- Registers a one-shot `click` listener to revert all changes after the context menu closes.

### `styles.js` (isolated)
Injects a `<style>` tag that forces a visible selection highlight (`::selection` with blue background) and overrides some known protection CSS classes.

### `user-select/isolated.js` (isolated)
- Iterates all `document.styleSheets` and rewrites `user-select: none` rules to `user-select: initial`.
- Uses a `MutationObserver` to catch dynamically added `<style>`/`<link>` elements and clean those too.
- Watches for inline `style` attribute changes that set `user-select: none` and overrides them.
- On `mousedown`, checks computed style and force-overrides `user-select` if still blocked.

### `user-select/main.js` (MAIN world)
Replaces `Selection.prototype.removeAllRanges` with a no-op so sites can't programmatically clear text selection. Restores the original on `'arc-remove'`.

### `listen/isolated.js` (isolated)
Adds capture-phase listeners that call `stopPropagation()` on: `dragstart`, `selectstart`, `copy`, `cut`, `contextmenu`, `mousedown`. Also intercepts `keydown` for Ctrl/Cmd+C/V/P/A and `paste` (plus a one-frame `input` suppression to prevent paste-revert tricks).

### `listen/main.js` (MAIN world)
Overrides page-global APIs via `Object.defineProperty`:
- `window.alert` → `console.info` (blocks "right-click disabled" popups)
- `MouseEvent.prototype.preventDefault` → no-op
- `MouseEvent.prototype.returnValue` → always returns `true`
- `ClipboardEvent.prototype.preventDefault` → no-op

All overrides are restored on `'arc-remove'`.

## Shared State: `window.pointers`

```js
window.pointers = {
  run: new Set(),    // Cleanup callbacks — each injected script adds one
  cache: new Map(),  // Maps DOM elements to {name, value} for inline style restoration
  status: ''         // '' → 'ready' → 'removed' → 'ready' → ...
};
```

- `window.pointers.record(element, styleName, originalValue)` — called by `user-select/isolated.js` before overriding an inline style, so `core.js` can restore it on deactivation.
- `window.pointers.run.add(fn)` — each script registers its teardown function here.
- The `'arc-remove'` DOM event bridges cleanup to MAIN world scripts that can't access `window.pointers`.

## Automation

Users can whitelist hostnames (via options page or context menu) for automatic activation.

- `worker.js` registers dynamic content scripts via `chrome.scripting.registerContentScripts` for each hostname pattern.
- When a matching page loads, `monitor.js` runs and sends `{method: 'simulate-click'}`, which calls `onClicked()` with `silent: true`.
- The `silent` flag sets `self.automated = true` before injecting `core.js`, so `core.js` forwards it to the worker, which uses the purple "automated" icon instead of the blue "active" icon.
- Hostname patterns are normalized: `example.com` → `*://example.com/*`.

## Sub-Frame Handling

- Clicking the icon injects `core.js` with `allFrames: true`, but each frame gets its own `window.pointers` instance.
- Sub-frames query the top frame's status via `{method: 'status'}` before deciding whether to activate. This prevents sub-frames from toggling out of sync with the top frame.
- The "Unblock Sub-Frame Elements" context menu item requests the optional `*://*/*` host permission, which is needed for cross-origin iframe injection.

## Context Menu

`context.js` creates five items on the toolbar icon's context menu:
1. **Automatically Activate on This Host** — adds current hostname to the whitelist
2. **Remove This Host from Activation List** — removes it
3. **Unblock Sub-Frame Elements** — requests host permission (disabled once granted)
4. **Test Right-Click** — opens `webbrowsertools.com/test-right-click`
5. **Options** — Firefox only (Chrome has a built-in options link)
