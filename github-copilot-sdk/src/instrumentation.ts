/**
 * instrumentation.ts — GenAI span instrumentation for GitHub Copilot SDK sessions.
 *
 * Creates OpenTelemetry spans following the GenAI semantic conventions so that the
 * Dynatrace AI Observability app can display models, token usage, and prompt traces.
 *
 * Span hierarchy:
 *   invoke_agent (root, SERVER)
 *     ├── chat {model} (per-LLM-call, CLIENT)  ← required for AI Observability app
 *     ├── chat {model} (per-LLM-call, CLIENT)
 *     ├── execute_tool {toolName} (CLIENT)
 *     └── ...
 *
 * The AI Observability app filters on:
 *   fetch spans
 *   | filter isNotNull(gen_ai.provider.name)
 *   | filter in(llm.request.type, {"chat", "completion"})
 *
 * The `chat {model}` spans satisfy both filters via `gen_ai.provider.name` + `llm.request.type`.
 */

import { SpanKind, SpanStatusCode, context, trace, type Span } from "@opentelemetry/api";
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
 * Check whether prompt/completion content should be captured in spans.
 * Opt-in only — disabled by default for privacy.
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
  session: { on: (handler: (event: SdkEvent) => void) => (() => void) | void },
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

  const maybeUnsub = session.on((event: SdkEvent) => {
    switch (event.type) {
      // ────────────────────────────────────────────────────────────────────
      // Buffer user prompt for content capture
      // ────────────────────────────────────────────────────────────────────
      case "user.message": {
        const content = event.data.content as string | undefined;
        if (content) lastUserMessage = content;
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Buffer assistant message for content capture
      // ────────────────────────────────────────────────────────────────────
      case "assistant.message": {
        const content = event.data.content as string | undefined;
        if (content) lastAssistantMessage = content;
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Per-LLM-call span — this is what makes the AI Observability app work
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
            // GenAI semantic conventions (new — only gen_ai.provider.name)
            "gen_ai.provider.name": providerName,
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": eventModel,
            "gen_ai.response.model": eventModel,

            // Required: this is the attribute the AI Observability app filters on
            "llm.request.type": "chat",

            // Token usage (with standard aliases)
            ...(inputTokens != null && {
              "gen_ai.usage.input_tokens": inputTokens,
              "gen_ai.usage.prompt_tokens": inputTokens,
            }),
            ...(outputTokens != null && {
              "gen_ai.usage.output_tokens": outputTokens,
              "gen_ai.usage.completion_tokens": outputTokens,
            }),
            ...(cost != null && { "gen_ai.usage.cost": cost }),

            "gen_ai.response.finish_reasons": ["stop"],
          },
        }, rootCtx);

        // Opt-in: attach buffered user prompt and assistant message content
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
