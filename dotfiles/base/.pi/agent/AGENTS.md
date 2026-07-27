# pi Agent Extensions

This directory contains pi agent extensions and their tests.

## Running Tests

Each extension subdirectory with a `vitest.config.ts` can be tested independently:

```bash
cd ~/.pi/agent/extensions/<name> && npx vitest --run
```

Or run all extension tests from the top level:

```bash
make test
```

### Adding Tests to an Extension

1. Export utility functions from the extension's `index.ts` so they can be imported by tests
2. Create `index.test.ts` alongside `index.ts` importing from `./index.ts`
3. Add a `vitest.config.ts` with module aliases pointing to the pi installation:

```ts
import { defineConfig } from "vitest/config";
import path from "node:path";

const PI_ROOT = "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent";
const PI_NM = path.join(PI_ROOT, "node_modules", "@earendil-works");

export default defineConfig({
  resolve: {
    alias: {
      "@earendil-works/pi-coding-agent": path.join(PI_ROOT, "dist", "index.js"),
      "@earendil-works/pi-ai": path.join(PI_NM, "pi-ai"),
      "@earendil-works/pi-agent-core": path.join(PI_NM, "pi-agent-core"),
      "@earendil-works/pi-tui": path.join(PI_NM, "pi-tui"),
    },
  },
});
```

