import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

export const BUNDLE_PATH = fileURLToPath(
  new URL("../.cloudflare/output/v0/workers/default/bundle/index.js", import.meta.url),
);

export async function loadWorker() {
  if (!existsSync(BUNDLE_PATH)) {
    throw new Error("missing worker bundle; run `make worker-bundle` first");
  }
  const module = await import(pathToFileURL(BUNDLE_PATH).href);
  return module.default;
}

export function countingBinding(name, methods) {
  const calls = {};
  const binding = {};
  for (const method of methods) {
    calls[method] = 0;
    binding[method] = async () => {
      calls[method] += 1;
      throw new Error(`${name}.${method} is not expected in this test`);
    };
  }
  return { binding, calls };
}

export function environment(overrides = {}) {
  const db = countingBinding("DB", ["prepare", "batch", "exec", "dump", "withSession"]);
  const bucket = countingBinding("BUCKET", ["head", "get", "put", "delete", "list", "createMultipartUpload"]);
  return {
    env: { READERS: "reader@example.test", DB: db.binding, BUCKET: bucket.binding, ...overrides },
    calls: { db: db.calls, bucket: bucket.calls },
  };
}

export function context(identity) {
  return { access: { getIdentity: () => identity } };
}

export function request(path, init = {}) {
  return new Request(`https://memories.test${path}`, init);
}
