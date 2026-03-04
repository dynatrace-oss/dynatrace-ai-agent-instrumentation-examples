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
 *   | filter isNotNull(gen_ai.system) or isNotNull(gen_ai.provider.name)
 *   | filter in(llm.request.type, {"chat", "completion"})
 *
 * The `chat {model}` spans satisfy both filters via `gen_ai.system` + `llm.request.type`.
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
 * Subset of Copilot SDK session events relevant to telemetry.
 * Adapt these types to match your SDK version's event shapes.
 */
interface UsageEvent {
  type: "assistant_usage";
  model: string;
  inputTokens?: number;
  outputTokens?: number;
  cost?: number;
  duration?: number;
}

interface MessageEvent {
  type: "assistant_message";
  content: string;
}

interface ToolStartEvent {
  type: "tool_start";
  toolName: string;
  toolCallId: string;
  arguments?: Record<string, unknown>;
}

interface ToolCompleteEvent {
  type: "tool_complete";
  toolCallId: string;
  success: boolean;
  error?: { message: string; code?: string };
}

interface ShutdownEvent {
  type: "session_shutdown";
  shutdownType: string;
}

interface ErrorEvent {
  type: "session_error";
  errorType: string;
  message: string;
}

type SessionEvent =
  | UsageEvent
  | MessageEvent
  | ToolStartEvent
  | ToolCompleteEvent
  | ShutdownEvent
  | ErrorEvent
  | { type: string; [key: string]: unknown };

// ─── Configuration ──────────────────────────────────────────────────────────

/**
 * Determine the GenAI system/provider name.
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
  session: { on: (handler: (event: SessionEvent) => void) => (() => void) | void },
  sessionId: string,
  model: string,
): () => void {
  const tracer = getTracer("copilot-sdk-agent.session");
  const providerName = getProviderName();

  // ── Session-level accumulators ──
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  // Buffer for optional content capture
  let lastAssistantMessage = "";

  // ── Root span: one per session ──
  const rootSpan = tracer.startSpan("invoke_agent", {
    kind: SpanKind.SERVER,
    attributes: {
      "gen_ai.system": providerName,
      "gen_ai.provider.name": providerName,
      "gen_ai.operation.name": "invoke_agent",
      "gen_ai.request.model": model,
      "session.id": sessionId,
    },
  });

  // Track active tool spans for cleanup
  const activeToolSpans = new Map<string, Span>();

  const maybeUnsub = session.on((event: SessionEvent) => {
    switch (event.type) {
      // ────────────────────────────────────────────────────────────────────
      // Per-LLM-call span — this is what makes the AI Observability app work
      // ────────────────────────────────────────────────────────────────────
      case "assistant_usage": {
        const e = event as UsageEvent;

        // Update session-level totals on root span
        if (e.inputTokens != null) totalInputTokens += e.inputTokens;
        if (e.outputTokens != null) totalOutputTokens += e.outputTokens;
        rootSpan.setAttribute("gen_ai.usage.input_tokens", totalInputTokens);
        rootSpan.setAttribute("gen_ai.usage.output_tokens", totalOutputTokens);
        rootSpan.setAttribute("gen_ai.response.model", e.model);

        // Create a per-LLM-call child span
        const rootCtx = trace.setSpan(context.active(), rootSpan);
        const llmSpan = tracer.startSpan(`chat ${e.model}`, {
          kind: SpanKind.CLIENT,
          attributes: {
            // Required: GenAI semantic conventions
            "gen_ai.system": providerName,
            "gen_ai.provider.name": providerName,
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": e.model,
            "gen_ai.response.model": e.model,

            // Required: this is the attribute the AI Observability app filters on
            "llm.request.type": "chat",

            // Token usage (with standard aliases)
            ...(e.inputTokens != null && {
              "gen_ai.usage.input_tokens": e.inputTokens,
              "gen_ai.usage.prompt_tokens": e.inputTokens,
            }),
            ...(e.outputTokens != null && {
              "gen_ai.usage.output_tokens": e.outputTokens,
              "gen_ai.usage.completion_tokens": e.outputTokens,
            }),
            ...(e.cost != null && { "gen_ai.usage.cost": e.cost }),

            "gen_ai.response.finish_reasons": ["stop"],
          },
        }, rootCtx);

        // Opt-in: attach buffered assistant message content
        if (shouldCaptureContent() && lastAssistantMessage) {
          llmSpan.setAttribute("gen_ai.completion.0.role", "assistant");
          llmSpan.setAttribute("gen_ai.completion.0.content", lastAssistantMessage.substring(0, 1024));
        }
        lastAssistantMessage = "";
        llmSpan.end();

        // Record metrics
        if (e.inputTokens != null) {
          llmTokensTotal.add(e.inputTokens, { model: e.model, direction: "input", token_type: "prompt" });
        }
        if (e.outputTokens != null) {
          llmTokensTotal.add(e.outputTokens, { model: e.model, direction: "output", token_type: "completion" });
        }
        if (e.duration != null) {
          llmLatency.record(e.duration, { model: e.model, provider: providerName });
        }
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Buffer assistant message for content capture
      // ────────────────────────────────────────────────────────────────────
      case "assistant_message": {
        const e = event as MessageEvent;
        if (e.content) lastAssistantMessage = e.content;
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Tool execution spans
      // ────────────────────────────────────────────────────────────────────
      case "tool_start": {
        const e = event as ToolStartEvent;
        const rootCtx = trace.setSpan(context.active(), rootSpan);
        const toolSpan = tracer.startSpan(`execute_tool ${e.toolName}`, {
          kind: SpanKind.CLIENT,
          attributes: {
            "gen_ai.system": providerName,
            "gen_ai.provider.name": providerName,
            "gen_ai.tool.name": e.toolName,
            "gen_ai.tool.call.id": e.toolCallId,
            "gen_ai.operation.name": "execute_tool",
          },
        }, rootCtx);
        activeToolSpans.set(e.toolCallId, toolSpan);
        break;
      }

      case "tool_complete": {
        const e = event as ToolCompleteEvent;
        const toolSpan = activeToolSpans.get(e.toolCallId);
        if (toolSpan) {
          if (!e.success) {
            toolSpan.setStatus({ code: SpanStatusCode.ERROR, message: e.error?.message });
          }
          toolsExecuted.add(1, { tool_name: "unknown", outcome: e.success ? "success" : "error" });
          toolSpan.end();
          activeToolSpans.delete(e.toolCallId);
        }
        break;
      }

      // ────────────────────────────────────────────────────────────────────
      // Session lifecycle
      // ────────────────────────────────────────────────────────────────────
      case "session_error": {
        const e = event as ErrorEvent;
        rootSpan.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
        rootSpan.setAttribute("error.type", e.errorType);
        break;
      }

      case "session_shutdown": {
        rootSpan.setAttribute("gen_ai.response.finish_reasons",
          [(event as ShutdownEvent).shutdownType === "error" ? "error" : "stop"]);
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
