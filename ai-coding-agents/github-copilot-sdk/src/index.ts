/**
 * index.ts — GitHub Copilot SDK agent with native OpenTelemetry export.
 *
 * The Copilot runtime emits its own OTel traces and metrics using the GenAI
 * semantic conventions. Enabling them is configuration only: pass TelemetryConfig
 * to CopilotClient and point it at an OTLP endpoint. No manual spans are needed.
 *
 * Point COPILOT_OTLP_ENDPOINT at the OTel Collector from collector.yaml, which
 * converts the runtime's cumulative metrics to the delta temporality Dynatrace
 * requires and adds the Dynatrace auth header.
 */

import { CopilotClient, defineTool, approveAll } from "@github/copilot-sdk";

// ── Define tools ────────────────────────────────────────────────────────────

const getCurrentTime = defineTool("get_current_time", {
  description: "Get the current date and time",
  handler: async () => {
    return new Date().toISOString();
  },
});

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const otlpEndpoint = process.env.COPILOT_OTLP_ENDPOINT || "http://localhost:4318";

  // BYOK sessions bypass Copilot API authentication entirely, so skip the
  // logged-in-user lookup that would otherwise fail without GitHub credentials.
  const byokBaseURL = process.env.COPILOT_PROVIDER_BASE_URL;

  const client = new CopilotClient({
    gitHubToken: process.env.GH_TOKEN,
    ...(byokBaseURL && { useLoggedInUser: false }),

    // Native runtime telemetry. TelemetryConfig has no headers field, so this
    // must point at a Collector or gateway that authenticates to Dynatrace.
    telemetry: {
      otlpEndpoint,
      otlpProtocol: "http/protobuf",
      // Prompts, responses, and tool payloads can contain source code. Opt in
      // deliberately, never by default.
      captureContent: process.env.COPILOT_CAPTURE_CONTENT === "true",
    },
  });

  await client.start();
  console.log(`Copilot SDK client started, telemetry -> ${otlpEndpoint}`);

  const model = process.env.PROVIDER_MODEL || "claude-sonnet-4-5-20250929";

  const session = await client.createSession({
    model,
    tools: [getCurrentTime],
    availableTools: ["get_current_time"],
    systemMessage: {
      mode: "append",
      content: "You are a helpful assistant. Answer questions concisely.",
    },
    streaming: true,
    onPermissionRequest: approveAll,

    // BYOK: when set, the session talks to this OpenAI-compatible endpoint
    // instead of the Copilot API, which also bypasses Copilot authentication.
    // Used by the e2e suite to run against a mock; unset in normal use.
    ...(byokBaseURL && {
      provider: {
        type: "openai" as const,
        baseUrl: byokBaseURL,
        apiKey: process.env.COPILOT_PROVIDER_API_KEY,
      },
    }),
  });

  console.log(`Session created: ${session.sessionId}`);

  const prompt = process.argv[2] || "What time is it?";
  console.log(`\nSending: "${prompt}"\n`);

  let content = "";
  session.on("assistant.message_delta", (event) => {
    content += event.data.deltaContent;
  });

  const reply = await session.sendAndWait({ prompt });
  // Streaming deltas when available, otherwise the final message.
  console.log(`Response: ${content || reply?.data?.content || "(no response)"}\n`);

  // client.stop() closes all active sessions and flushes runtime telemetry.
  await client.stop();
  console.log("Done. Traces and metrics exported via the Collector.");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
