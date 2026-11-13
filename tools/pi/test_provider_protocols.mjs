import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [runtimeArg, profile] = process.argv.slice(2);
assert(runtimeArg && ["full", "headless-usr"].includes(profile), "usage: node tools/verify-providers.mjs RUNTIME PROFILE");
const modules = join(resolve(runtimeArg), "node_modules");
const load = (path) => import(pathToFileURL(join(modules, path)).href);
const { createModels } = await load("@earendil-works/pi-ai/dist/index.js");
const { opencodeGoProvider } = await load("@earendil-works/pi-ai/dist/providers/opencode-go.js");
const models = createModels();
models.setProvider(opencodeGoProvider());
const proof = "PROOF: transport preserved";
const message = { id: "msg_fixture", type: "message", role: "assistant", model: "fixture", content: [], stop_reason: null,
  stop_sequence: null, usage: { input_tokens: 1, output_tokens: 0 } };
const response = { id: "resp_fixture", object: "response", created_at: 1, status: "completed",
  output: [{ id: "item_fixture", type: "message", role: "assistant", status: "completed",
    content: [{ type: "output_text", text: proof, annotations: [] }] }],
  usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2, input_tokens_details: { cached_tokens: 0 }, output_tokens_details: { reasoning_tokens: 0 } } };
const fixtures = {
  "openai-completions": [
    { id: "fixture", object: "chat.completion.chunk", choices: [{ index: 0, delta: { role: "assistant", content: proof }, finish_reason: null }] },
    { id: "fixture", object: "chat.completion.chunk", choices: [{ index: 0, delta: {}, finish_reason: "stop" }] },
  ],
  "anthropic-messages": [
    { type: "message_start", message },
    { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } },
    { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: proof } },
    { type: "content_block_stop", index: 0 },
    { type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: 1 } },
    { type: "message_stop" },
  ],
  "google-generative-ai": [{ candidates: [{ index: 0, content: { role: "model", parts: [{ text: proof }] }, finishReason: "STOP" }],
    usageMetadata: { promptTokenCount: 1, candidatesTokenCount: 1, totalTokenCount: 2 } }],
  "openai-responses": [
    { type: "response.created", response: { ...response, status: "in_progress", output: [] } },
    { type: "response.output_item.added", output_index: 0, item: { ...response.output[0], status: "in_progress", content: [] } },
    { type: "response.content_part.added", output_index: 0, content_index: 0, part: { type: "output_text", text: "", annotations: [] } },
    { type: "response.output_text.delta", output_index: 0, content_index: 0, delta: proof },
    { type: "response.output_item.done", output_index: 0, item: response.output[0] },
    { type: "response.completed", response },
  ],
};
const originalFetch = globalThis.fetch;
try {
  for (const [api, events] of Object.entries(fixtures)) {
    let calls = 0;
    globalThis.fetch = async (input) => {
      const url = new URL(typeof input === "string" || input instanceof URL ? input : input.url);
      assert.equal(url.hostname, "127.0.0.1", "provider fixture must stay offline");
      calls++;
      const body = events.map((event) => `${event.type ? `event: ${event.type}\n` : ""}data: ${JSON.stringify(event)}\n\n`).join("")
        + (api === "openai-completions" ? "data: [DONE]\n\n" : "");
      return new Response(body, { headers: { "content-type": "text/event-stream" } });
    };
    const model = models.getModels("opencode-go").find((model) => model.api === api);
    assert(model, `missing OpenCode Go protocol ${api}`);
    const result = await models.completeSimple({ ...model, baseUrl: "http://127.0.0.1:1/v1" },
      { messages: [{ role: "user", content: "Return proof", timestamp: 1 }] }, { apiKey: "fixture-only", maxTokens: 64 });
    assert.equal(result.stopReason, "stop", JSON.stringify(result));
    assert.equal(result.content.filter((part) => part.type === "text").map((part) => part.text).join(""), proof);
    assert.equal(calls, 1);
    console.log(`ok: OpenCode Go ${api} returned fixture completion`);
  }
  if (profile === "headless-usr") {
    for (const name of ["tsx", "esbuild", "@esbuild", "@aws-sdk", "@smithy", "@aws/lambda-invoke-store"])
      assert.equal(existsSync(join(modules, name)), false, `${name} must be absent`);
    for (const name of ["pi-subagents", "@dataforxyz/agent-intercom-pi", "pi-muse-subscription"]) {
      const root = join(modules, name);
      const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
      assert(manifest.pi.extensions.every((entry) => entry.endsWith(".js")));
      assert.equal(readdirSync(root, { recursive: true }).some((file) => String(file).endsWith(".ts")), false,
        `${name} must execute compiled JavaScript`);
    }
    const { amazonBedrockProvider } = await load("@earendil-works/pi-ai/dist/providers/amazon-bedrock.js");
    models.setProvider(amazonBedrockProvider());
    const model = models.getModels("amazon-bedrock")[0];
    assert(model);
    const result = await models.completeSimple(model, { messages: [] }, { apiKey: "fixture-only" });
    assert.equal(result.stopReason, "error");
    assert.match(result.errorMessage, /Amazon Bedrock is unavailable in pi-headless-usr/);
    const bundled = await load("@earendil-works/pi-coding-agent/dist/bundle/chunks/bedrock-converse-stream.js");
    assert.throws(() => bundled.stream(), (error) => {
      assert.match(error.message, /Amazon Bedrock is unavailable in pi-headless-usr/);
      assert.match(error.stack, /bedrock-converse-stream\.js:\d+:\d+/);
      return true;
    });
    console.log("ok: Bedrock fails explicitly through the SDK lazy API and bundled implementation");
  }
} finally {
  globalThis.fetch = originalFetch;
}
