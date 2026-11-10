# Installing @laputa-systems/ui-dashboard

- Route the scope in `.npmrc`: `@laputa-systems:registry=https://npm.17166969.xyz/current/`.
- If the render path cannot run Node, add the package as a pinned dev dependency, copy `dist/styles.css` and `dist/tokens.css` into the source tree at build time, and make the existing asset staleness check cover them. `styles.css` imports `./tokens.css`, so keep both in one directory.
