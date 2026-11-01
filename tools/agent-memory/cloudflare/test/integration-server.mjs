#!/usr/bin/env node
import { createServer } from "node:http";

import { Miniflare } from "miniflare";

import { seedDatabase } from "../bench/seed.mjs";
import { loadWorker } from "./harness.mjs";

const worker = await loadWorker();
const collectors = JSON.parse(process.env.COLLECTORS ?? "[]");

const miniflare = new Miniflare({
  modules: true,
  script: "export default { fetch() { return new Response('ok'); } }",
  compatibilityDate: "2026-08-06",
  d1Databases: ["DB"],
  r2Buckets: ["BUCKET"],
});
const db = await miniflare.getD1Database("DB");
await seedDatabase(db);
const insert = db.prepare(
  "INSERT INTO collector(service_token_id, origin_host, label, created_at, disabled) VALUES(?, ?, ?, ?, 0)",
);
for (const collector of collectors) {
  await insert.bind(collector.client_id, collector.origin, "integration", 0).run();
}
const env = {
  READERS: "reader@example.test",
  ACCESS_TEAM_DOMAIN: "team.example.test",
  ACCESS_AUD: "test-audience",
  DB: db,
  BUCKET: await miniflare.getR2Bucket("BUCKET"),
};

function identityFor(request) {
  const client = request.headers["cf-access-client-id"];
  if (typeof client === "string" && client !== "") return { service_token_id: client };
  const reader = request.headers["x-test-reader"];
  if (typeof reader === "string" && reader !== "") return { email: reader };
  return null;
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks);
}

const server = createServer(async (request, response) => {
  try {
    const body = await readBody(request);
    const method = request.method ?? "GET";
    const forwarded = new Request(`https://memories.test${request.url}`, {
      method,
      headers: request.headers,
      body: method === "GET" || method === "HEAD" || body.length === 0 ? undefined : body,
    });
    const result = await worker.fetch(forwarded, env, {
      access: { getIdentity: async () => identityFor(request) },
    });
    response.writeHead(result.status, Object.fromEntries(result.headers));
    response.end(Buffer.from(await result.arrayBuffer()));
  } catch (error) {
    response.writeHead(500, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: String(error) }));
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
