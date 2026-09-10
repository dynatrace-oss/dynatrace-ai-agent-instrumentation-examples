/**
 * instrumentation.ts: manual GenAI span augmentation for GitHub Copilot SDK sessions.
 *
 * Builds OpenTelemetry spans following the GenAI semantic conventions from the SDK's
 * session event stream. Use this for application-specific spans, custom tools, or
 * business attributes on top of (or instead of) the Copilot runtime's own native OTel
 * telemetry (`CopilotClient` `TelemetryConfig`).
 *
 * Span hierarchy:
 *   invoke_agent (root, SERVER)
 *     ├── chat {model} (per-LLM-call, CLIENT)
 *     ├── chat {model} (per-LLM-call, CLIENT)
 *     ├── execute_tool {toolName} (CLIENT)
 *     └── ...
 *
 * Do not run this alongside native runtime telemetry without deduplication: both can
 * represent the same inferences and double-count LLM calls and tokens.
 */

import { SpanKind, SpanStatusCode, context, trace, type Span } from "@opentelemetry/api";
import type { CopilotSession } from "@github/copilot-sdk";
import { getTracer, getMeter } from "./telemetry.js";

// ─── Metrics ────────────────────────────────────────────────────────────────

const meter = getMeter("copilot-sdk-agent");

export const llmTokensTotal = meter.createCounter("copilot_sdk.llm.tokens.total", {
  description: "Total LLM tokens by model, direction, and type",
});

export const llmLatency = meter.createHistogram("copilot_sdk.llm.latency", {
  description: "LLM response latency in milliseconds",
  unit: "ms",
});

export const toolsExecuted = meter.createCounter("copilot_sdk.tools.executed", {
  description: "Tool executions by name and outcome",
});

// ─── Types ──────────────────────────────────────────────────────────────────

/**
 * Copilot SDK session events use dot-notation names:
 *   user.message, assistant.message, assistant.usage,
 *   tool.execution_start, tool.execution_complete,
 *   session.shutdown, session.error
 *
 * The event shape is: { id, timestamp, type, data }
 */
interface SdkEvent {
  type: string;
  data: Record<string, unknown>;
}

// ─── Configuration ──────────────────────────────────────────────────────────

/**
 * Determine the GenAI provider name.
 * Returns the configured PROVIDER_TYPE or defaults to "github.copilot".
 */
function getProviderName(): string {
  return process.env.PROVIDER_TYPE || "github.copilot";
}

/**
 * Check whether message content should be captured in spans.
 * Opt-in only, disabled by default: prompts, responses, and tool payloads can
 * contain source code and other sensitive data.
 */
function shouldCaptureContent(): boolean {
  return process.env.OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT === "true";
}

// ─── Session Telemetry ──────────────────────────────────────────────────────

/**
 * Subscribe to a Copilot SDK session's events and create OTel spans/metrics.
 *
 * Call this after creating or resuming a session:
 *
 *   const session = await client.createSession(options);
 *   const cleanup = subscribeSessionTelemetry(session, session.sessionId, model);
 *   // ... use session ...
 *   cleanup(); // on session end
 *
 * @returns An unsubscribe/cleanup function.
 */
export function subscribeSessionTelemetry(
  session: CopilotSession,
  sessionId: string,
  model: string,
): () => void {
  const tracer = getTracer("copilot-sdk-agent.session");
  const providerName = getProviderName();

  // ── Session-level accumulators ──
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  // Buffers for optional content capture on per-LLM-call spans
  let lastUserMessage = "";
  let lastAssistantMessage = "";

  // ── Root span: one per session ──
  const rootSpan = tracer.startSpan("invoke_agent", {
    kind: SpanKind.SERVER,
    attributes: {
      "gen_ai.provider.name": providerName,
      "gen_ai.operation.name": "invoke_agent",
      "gen_ai.request.model": model,
      "session.id": sessionId,
    },
  });

  // Track active tool spans for cleanup
  const activeToolSpans = new Map<string, Span>();

  const maybeUnsub = session.on((rawEvent) => {
    const event = rawEvent as unknown as SdkEvent;
    switch (event.type) {
      // ────────────────────────────────────────────────────────────────────
      // Buffer user prompt for content capture
      // ────────────────────────────────────────────────────────────────────
      case "user.message": {
        const content = event.data.content as string | undefined;
        if (content) lastUserMessage += content;
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Buffer assistant message for content capture
      // ────────────────────────────────────────────────────────────────────
      case "assistant.message": {
        const content = event.data.content as string | undefined;
        if (content) lastAssistantMessage += content;
        break;
      }

      case "assistant.message_delta": {
        const content = event.data.deltaContent as string | undefined;
        if (content) lastAssistantMessage += content;
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Per-LLM-call span, one per inference
      // ────────────────────────────────────────────────────────────────────
      case "assistant.usage": {
        const d = event.data;
        const eventModel = d.model as string;
        const inputTokens = d.inputTokens as number | undefined;
        const outputTokens = d.outputTokens as number | undefined;
        const cost = d.cost as number | undefined;
        const duration = d.duration as number | undefined;

        // Update session-level totals on root span
        if (inputTokens != null) totalInputTokens += inputTokens;
        if (outputTokens != null) totalOutputTokens += outputTokens;
        rootSpan.setAttribute("gen_ai.usage.input_tokens", totalInputTokens);
        rootSpan.setAttribute("gen_ai.usage.output_tokens", totalOutputTokens);
        rootSpan.setAttribute("gen_ai.response.model", eventModel);

        // Create a per-LLM-call child span
        const rootCtx = trace.setSpan(context.active(), rootSpan);
        const llmSpan = tracer.startSpan(`chat ${eventModel}`, {
          kind: SpanKind.CLIENT,
          attributes: {
            // GenAI semantic conventions (gen_ai.system is deprecated)
            "gen_ai.provider.name": providerName,
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": eventModel,
            "gen_ai.response.model": eventModel,

            // Token usage
            ...(inputTokens != null && {
              "gen_ai.usage.input_tokens": inputTokens,
            }),
            ...(outputTokens != null && {
              "gen_ai.usage.output_tokens": outputTokens,
            }),
            ...(cost != null && { "gen_ai.usage.cost": cost }),

            "gen_ai.response.finish_reasons": ["stop"],
          },
        }, rootCtx);

        // Opt-in message content capture. The current GenAI conventions name these
        // gen_ai.input.messages / gen_ai.output.messages; the indexed attributes below
        // are the legacy form, kept until a tested migration lands.
        if (shouldCaptureContent()) {
          if (lastUserMessage) {
            llmSpan.setAttribute("gen_ai.prompt.0.role", "user");
            llmSpan.setAttribute("gen_ai.prompt.0.content", lastUserMessage.substring(0, 1024));
          }
          if (lastAssistantMessage) {
            llmSpan.setAttribute("gen_ai.completion.0.role", "assistant");
            llmSpan.setAttribute("gen_ai.completion.0.content", lastAssistantMessage.substring(0, 1024));
          }
        }
        lastUserMessage = "";
        lastAssistantMessage = "";
        llmSpan.end();

        // Record metrics
        if (inputTokens != null) {
          llmTokensTotal.add(inputTokens, { model: eventModel, direction: "input", token_type: "prompt" });
        }
        if (outputTokens != null) {
          llmTokensTotal.add(outputTokens, { model: eventModel, direction: "output", token_type: "completion" });
        }
        if (duration != null) {
          llmLatency.record(duration, { model: eventModel, provider: providerName });
        }
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Tool execution spans
      // ────────────────────────────────────────────────────────────────────
      case "tool.execution_start": {
        const toolName = event.data.toolName as string;
        const toolCallId = event.data.toolCallId as string;
        const rootCtx = trace.setSpan(context.active(), rootSpan);
        const toolSpan = tracer.startSpan(`execute_tool ${toolName}`, {
          kind: SpanKind.CLIENT,
          attributes: {
            "gen_ai.provider.name": providerName,
            "gen_ai.tool.name": toolName,
            "gen_ai.tool.call.id": toolCallId,
            "gen_ai.operation.name": "execute_tool",
          },
        }, rootCtx);
        activeToolSpans.set(toolCallId, toolSpan);
        break;
      }

      case "tool.execution_complete": {
        const toolCallId = event.data.toolCallId as string;
        const success = event.data.success as boolean;
        const error = event.data.error as { message?: string } | undefined;
        const toolSpan = activeToolSpans.get(toolCallId);
        if (toolSpan) {
          if (!success) {
            toolSpan.setStatus({ code: SpanStatusCode.ERROR, message: error?.message });
          }
          toolsExecuted.add(1, { tool_name: "unknown", outcome: success ? "success" : "error" });
          toolSpan.end();
          activeToolSpans.delete(toolCallId);
        }
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Session lifecycle
      // ────────────────────────────────────────────────────────────────────
      case "session.error": {
        const message = event.data.message as string ?? "";
        const errorType = event.data.errorType as string ?? "unknown";
        rootSpan.setStatus({ code: SpanStatusCode.ERROR, message });
        rootSpan.setAttribute("error.type", errorType);
        break;
      }

      case "session.shutdown": {
        const shutdownType = event.data.shutdownType as string ?? "routine";
        rootSpan.setAttribute("gen_ai.response.finish_reasons",
          [shutdownType === "error" ? "error" : "stop"]);
        // Clean up any orphaned tool spans
        for (const [id, span] of activeToolSpans) {
          span.setStatus({ code: SpanStatusCode.ERROR, message: "session_shutdown" });
          span.end();
          activeToolSpans.delete(id);
        }
        rootSpan.end();
        break;
      }

      default:
        break;
    }
  });

  const unsub = typeof maybeUnsub === "function" ? maybeUnsub : () => {};

  return () => {
    unsub();
    if (!rootSpan.isRecording) return;
    rootSpan.end();
  };
}
