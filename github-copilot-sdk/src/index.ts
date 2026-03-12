/**
 * index.ts — Minimal GitHub Copilot SDK agent with Dynatrace instrumentation.
 *
 * Demonstrates how to:
 * 1. Initialize OpenTelemetry for Dynatrace OTLP export
 * 2. Create a Copilot SDK session with tools
 * 3. Subscribe to session events for GenAI span instrumentation
 * 4. Send a message and observe the results in Dynatrace AI Observability
 */

import { initTelemetry, shutdownTelemetry } from "./telemetry.js";

// IMPORTANT: Initialize telemetry before importing the SDK
// so that any auto-instrumented HTTP calls are captured.
initTelemetry();

import { CopilotClient, defineTool } from "@github/copilot-sdk";
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
  const client = new CopilotClient({
    githubToken: process.env.GH_TOKEN,
  });

  await client.start();
  console.log("Copilot SDK client started");

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
    onPermissionRequest: async () => ({ kind: "approved" }),
  });

  console.log(`Session created: ${session.sessionId}`);

  // ── Subscribe to session events for telemetry ──
  const cleanupTelemetry = subscribeSessionTelemetry(
    session,
    session.sessionId,
    model,
  );

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
  cleanupTelemetry();
  await session.destroy();
  await client.stop();
  await shutdownTelemetry();
  console.log("Done. Traces and metrics exported to Dynatrace.");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
