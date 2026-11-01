import assert from "node:assert/strict";
import { generateKeyPairSync, sign as nodeSign } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import { BUNDLE_PATH, context, environment, loadWorker, request } from "./harness.mjs";

const worker = await loadWorker();
const reader = context({ email: "reader@example.test" });

function assertSecurityHeaders(response) {
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.match(response.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.match(response.headers.get("server-timing"), /^d1;dur=\d+\.\d, r2;dur=\d+\.\d$/);
}

test("an Access identity is required before routing", async () => {
  const { env } = environment();
  for (const absent of [null, {}]) {
    const response = await worker.fetch(request("/api/v1/status"), env, absent);
    assert.equal(response.status, 403);
    assertSecurityHeaders(response);
    const body = await response.json();
    assert.equal(body.error.code, "forbidden");
  }
  const unknown = await worker.fetch(request("/does-not-exist"), env, {});
  assert.equal(unknown.status, 403);
});

test("an identity that throws while reading Access is refused", async () => {
  const { env } = environment();
  const hostile = { access: { getIdentity: () => { throw new Error("boom"); } } };
  const response = await worker.fetch(request("/api/v1/status"), env, hostile);
  assert.equal(response.status, 403);
});

test("a principal outside READERS is refused", async () => {
  const { env } = environment();
  for (const identity of [{ email: "stranger@example.test" }, { service_token_id: "token-id" }, { email: "reader@example.test", service_token_id: "token-id" }]) {
    const response = await worker.fetch(request("/api/v1/status"), env, context(identity));
    assert.equal(response.status, 403);
  }
});

test("a configured reader reads status from D1 without touching R2", async () => {
  const { env, calls } = environment({ READERS: " Reader@Example.test , other@example.test " });
  const response = await worker.fetch(request("/api/v1/status"), env, context({ email: "READER@example.test" }));
  assert.equal(response.status, 200);
  assertSecurityHeaders(response);
  assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
  assert.deepEqual(await response.json(), {
    protocol: 1,
    store_id: "usr-memories",
    principal: { kind: "reader", email: "reader@example.test" },
    ready: true,
    counts: {},
  });
  assert.deepEqual(calls.db, { prepare: 1, first: 1, batch: 0, exec: 0, dump: 0, withSession: 0 });
  assert.deepEqual(calls.bucket, { head: 0, get: 0, put: 0, delete: 0, list: 0, createMultipartUpload: 0 });
});

test("a bound collector token reads status for its origin", async () => {
  const { env, calls } = environment({}, { collectors: { "token-id": { origin_host: "origin-a" } } });
  const response = await worker.fetch(request("/api/v1/status"), env, context({ service_token_id: "token-id" }));
  assert.equal(response.status, 200);
  assertSecurityHeaders(response);
  const body = await response.json();
  assert.deepEqual(body.principal, { kind: "collector", origin_host: "origin-a" });
  assert.deepEqual(calls.db, { prepare: 2, first: 2, batch: 0, exec: 0, dump: 0, withSession: 0 });
});

test("an unknown or disabled collector token is refused", async () => {
  const { env } = environment({}, { collectors: { "disabled-id": { origin_host: "origin-a", disabled: true } } });
  for (const token of ["missing-id", "disabled-id"]) {
    const response = await worker.fetch(request("/api/v1/status"), env, context({ service_token_id: token }));
    assert.equal(response.status, 403);
  }
});

test("HEAD returns the status headers without a body", async () => {
  const { env } = environment();
  const response = await worker.fetch(request("/api/v1/status", { method: "HEAD" }), env, reader);
  assert.equal(response.status, 200);
  assertSecurityHeaders(response);
  assert.equal(await response.text(), "");
});

test("an unconfigured READERS list fails closed", async () => {
  const { env } = environment({ READERS: "" });
  const response = await worker.fetch(request("/api/v1/status"), env, reader);
  assert.equal(response.status, 403);
});

test("wrong methods and unknown routes return the JSON envelope", async () => {
  const { env } = environment();
  const wrong = await worker.fetch(request("/api/v1/status", { method: "POST" }), env, reader);
  assert.equal(wrong.status, 405);
  assert.equal(wrong.headers.get("allow"), "GET, HEAD");
  assert.equal((await wrong.json()).error.code, "method_not_allowed");
  const missing = await worker.fetch(request("/api/v1/memories"), env, reader);
  assert.equal(missing.status, 404);
  assertSecurityHeaders(missing);
  assert.equal((await missing.json()).error.code, "not_found");
});

test("a missing or failing store reports unavailable", async () => {
  for (const options of [{ storeMeta: null }, { dbFailure: "prepare" }, { dbFailure: "query" }]) {
    const { env } = environment({}, options);
    const response = await worker.fetch(request("/api/v1/status"), env, reader);
    assert.equal(response.status, 503);
    assertSecurityHeaders(response);
    assert.equal((await response.json()).error.code, "unavailable");
  }
  const { env } = environment({}, { dbFailure: "query", collectors: { "token-id": { origin_host: "origin-a" } } });
  const response = await worker.fetch(request("/api/v1/status"), env, context({ service_token_id: "token-id" }));
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error.code, "unavailable");
});

test("the deployed bundle carries no test hook", async () => {
  const source = readFileSync(BUNDLE_PATH, "utf8");
  assert.doesNotMatch(source, /x-test-access|__TEST_ACCESS__/);
});

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function accessToken(privateKey, claims, header = { alg: "RS256", kid: "key-1", typ: "JWT" }) {
  const signingInput = `${encode(header)}.${encode(claims)}`;
  const signature = nodeSign("RSA-SHA256", Buffer.from(signingInput), privateKey).toString("base64url");
  return `${signingInput}.${signature}`;
}

function serviceClaims(domain, audience, overrides = {}) {
  return {
    type: "app",
    aud: [audience],
    exp: Math.floor(Date.now() / 1000) + 600,
    iat: Math.floor(Date.now() / 1000) - 10,
    iss: `https://${domain}`,
    sub: "",
    common_name: "integration-client.access",
    ...overrides,
  };
}

async function withKeyset(jwk, kid, action) {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (input) => {
    calls.push(String(input));
    return Response.json({ keys: [{ ...jwk, kid, alg: "RS256" }] });
  };
  try {
    return { result: await action(), calls };
  } finally {
    globalThis.fetch = original;
  }
}

test("a verified Access assertion authenticates a collector by its client id", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = publicKey.export({ format: "jwk" });
  const domain = "team-integration.example.test";
  const audience = "integration-audience";
  const clientId = "integration-client.access";
  const assertion = accessToken(privateKey, serviceClaims(domain, audience));
  const { env, calls } = environment(
    { ACCESS_TEAM_DOMAIN: domain, ACCESS_AUD: audience },
    { collectors: { [clientId]: { origin_host: "origin-a" } } },
  );
  const exchange = await withKeyset(jwk, "key-1", () => worker.fetch(
    request("/api/v1/status", { headers: { "Cf-Access-Jwt-Assertion": assertion } }),
    env,
    {},
  ));
  assert.equal(exchange.result.status, 200);
  assert.deepEqual((await exchange.result.json()).principal, { kind: "collector", origin_host: "origin-a" });
  assert.deepEqual(exchange.calls, [`https://${domain}/cdn-cgi/access/certs`]);
  assert.deepEqual(calls.db, { prepare: 2, first: 2, batch: 0, exec: 0, dump: 0, withSession: 0 });
});

test("a forged or mis-scoped Access assertion is refused before D1", async () => {
  const real = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const attacker = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = real.publicKey.export({ format: "jwk" });
  const cases = [
    { domain: "forged-team.example.test", token: accessToken(attacker.privateKey, serviceClaims("forged-team.example.test", "aud")) },
    { domain: "scope-team.example.test", token: accessToken(real.privateKey, serviceClaims("scope-team.example.test", "other-audience")) },
  ];
  for (const item of cases) {
    const { env, calls } = environment({ ACCESS_TEAM_DOMAIN: item.domain, ACCESS_AUD: "aud" });
    const response = await withKeyset(jwk, "key-1", () => worker.fetch(
      request("/api/v1/status", { headers: { "Cf-Access-Jwt-Assertion": item.token } }),
      env,
      {},
    )).then((exchange) => exchange.result);
    assert.equal(response.status, 403);
    assert.equal((await response.json()).error.code, "forbidden");
    assert.deepEqual(calls.db, { prepare: 0, first: 0, batch: 0, exec: 0, dump: 0, withSession: 0 });
  }
});
