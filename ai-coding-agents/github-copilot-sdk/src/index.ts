/**
 * index.ts — Minimal GitHub Copilot SDK agent with Dynatrace instrumentation.
 *
 * Two mutually exclusive telemetry modes, selected with COPILOT_TELEMETRY_MODE:
 *
 *   manual (default): this example's OTel bootstrap plus spans synthesized from the
 *                     session event stream, exported straight to Dynatrace.
 *   native:           the Copilot runtime's own OTel export via TelemetryConfig.
 *                     No manual exporters, no synthesized LLM spans.
 *
 * Never run both: they represent the same inferences and double-count calls and tokens.
 */

import { initTelemetry, shutdownTelemetry } from "./telemetry.js";

const telemetryMode =
  process.env.COPILOT_TELEMETRY_MODE === "native" ? "native" : "manual";

// IMPORTANT: Initialize telemetry before importing the SDK
// so that any auto-instrumented HTTP calls are captured.
if (telemetryMode === "manual") {
  initTelemetry();
}

import { CopilotClient, defineTool, approveAll } from "@github/copilot-sdk";
import { subscribeSessionTelemetry } from "./instrumentation.js";

// ── Define tools ────────────────────────────────────────────────────────────

const getCurrentTime = defineTool("get_current_time", {
  description: "Get the current date and time",
  handler: async () => {
    return new Date().toISOString();
  },
});

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  // In native mode the runtime exports its own traces, metrics, and OTel events.
  // TelemetryConfig has no per-client headers field, so point it at an authenticated
  // OTLP gateway or Collector that forwards to Dynatrace.
  const client = new CopilotClient({
    gitHubToken: process.env.GH_TOKEN,
    ...(telemetryMode === "native" && {
      telemetry: {
        otlpEndpoint: process.env.COPILOT_OTLP_ENDPOINT,
        otlpProtocol: "http/protobuf",
        captureContent: false,
      },
    }),
  });

  await client.start();
  console.log(`Copilot SDK client started (telemetry mode: ${telemetryMode})`);

  const model = process.env.PROVIDER_MODEL || "claude-sonnet-4-5-20250929";

  const session = await client.createSession({
    model: model,
    tools: [getCurrentTime],
    availableTools: ["get_current_time"],
    systemMessage: {
      mode: "append",
      content: "You are a helpful assistant. Answer questions concisely.",
    },
    streaming: true,
    onPermissionRequest: approveAll,
  });

  console.log(`Session created: ${session.sessionId}`);

  // ── Subscribe to session events for telemetry (manual mode only) ──
  const cleanupTelemetry =
    telemetryMode === "manual"
      ? subscribeSessionTelemetry(session, session.sessionId, model)
      : () => {};

  // ── Send a message ──
  const prompt = process.argv[2] || "What time is it?";
  console.log(`\nSending: "${prompt}"\n`);

  // Listen for response chunks
  let content = "";
  session.on("assistant.message_delta", (event) => {
      content += event.data.deltaContent;
  });
  session.on("session.idle", () => {
      console.log(); // New line when done
  });

  const response = await session.sendAndWait({ prompt });
  console.log(`Response: ${content ?? "(no response)"}\n`);

  // ── Cleanup ──
  // client.stop() closes all active sessions, so the session needs no separate teardown.
  cleanupTelemetry();
  await client.stop();
  if (telemetryMode === "manual") {
    await shutdownTelemetry();
  }
  console.log(`Done. Telemetry mode: ${telemetryMode}.`);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
