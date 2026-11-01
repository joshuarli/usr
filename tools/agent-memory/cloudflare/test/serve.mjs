import { createServer } from "node:http";
import { existsSync } from "node:fs";

const BUNDLE = new URL("../.cloudflare/output/v0/workers/default/bundle/index.js", import.meta.url);
const READER = "bench-reader@example.test";

function fail(message) {
  console.error(message);
  process.exit(2);
}

if (!existsSync(BUNDLE)) fail("missing worker bundle; run `npm run build` in tools/agent-memory/cloudflare");

let Miniflare;
try {
  ({ Miniflare } = await import("miniflare"));
} catch {
  fail("worker bench dependencies are missing; run `npm ci` in tools/agent-memory/cloudflare");
}

const { seedDatabase } = await import("../bench/seed.mjs");

const miniflare = new Miniflare({
  modules: true,
  script: "export default { fetch() { return new Response('worker bench placeholder'); } };",
  compatibilityDate: "2026-08-06",
  d1Databases: ["DB"],
  r2Buckets: ["BUCKET"],
});

const counters = new Map();
let requests = 0;

function bump(key) {
  counters.set(key, (counters.get(key) ?? 0) + 1);
}

function countedStatement(statement) {
  return new Proxy(statement, {
    get(target, property) {
      const value = Reflect.get(target, property);
      if (typeof value !== "function") return value;
      return (...args) => {
        bump("d1." + String(property));
        const result = value.apply(target, args);
        return property === "bind" ? countedStatement(result) : result;
      };
    },
  });
}

function countedBinding(binding, label) {
  return new Proxy(binding, {
    get(target, property) {
      const value = Reflect.get(target, property);
      if (typeof value !== "function") return value;
      return (...args) => {
        bump(label + "." + String(property));
        const result = value.apply(target, args);
        return label === "d1" && result !== null && typeof result === "object" && typeof result.first === "function"
          ? countedStatement(result)
          : result;
      };
    },
  });
}

const db = await miniflare.getD1Database("DB");
await seedDatabase(db);
const env = {
  READERS: READER,
  DB: countedBinding(db, "d1"),
  BUCKET: countedBinding(await miniflare.getR2Bucket("BUCKET"), "r2"),
};

const { default: worker } = await import(BUNDLE.href);

function identityFor(header) {
  return header === "reader" ? { email: READER } : null;
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks);
}

function send(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(body));
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    if (url.pathname === "/__bench/status") {
      send(response, 200, { requests, counters: Object.fromEntries(counters) });
      return;
    }
    if (url.pathname === "/__bench/reset") {
      counters.clear();
      requests = 0;
      send(response, 200, { requests, counters: {} });
      return;
    }
    const body = await readBody(request);
    const method = request.method ?? "GET";
    const forwarded = new Request(`http://127.0.0.1${request.url}`, {
      method,
      headers: request.headers,
      body: method === "GET" || method === "HEAD" || body.length === 0 ? undefined : body,
    });
    requests += 1;
    const result = await worker.fetch(forwarded, env, {
      access: { getIdentity: async () => identityFor(request.headers["x-bench-principal"]) },
    });
    response.writeHead(result.status, Object.fromEntries(result.headers));
    response.end(Buffer.from(await result.arrayBuffer()));
  } catch (error) {
    send(response, 500, { error: String(error) });
  }
});

server.listen(0, "127.0.0.1", () => {
  console.log(JSON.stringify({ port: server.address().port }));
});

async function shutdown() {
  server.close();
  await miniflare.dispose();
  process.exit(0);
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, shutdown);
}
