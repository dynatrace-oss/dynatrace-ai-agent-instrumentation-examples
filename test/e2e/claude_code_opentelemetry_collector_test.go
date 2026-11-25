package e2e

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"
)

func TestClaudeCodeOpenTelemetryCollector(t *testing.T) {
	startAnthropicCompatibleMock(t)

	// The target starts the repository's collector enrichment example, executes
	// one headless Claude Code run, flushes native telemetry, and exits. The local
	// Anthropic-compatible mock is used when no real CI credential is configured.
	// The mock requests two tools in one turn: Read, which the Makefile allows
	// (--allowedTools), and Bash, which it denies (--disallowedTools). The run then
	// ends with a text answer, so the test also asserts the tool_decision and
	// tool_result logs, the execute_tool span and its duration metric.
	// With real credentials the mock is off and the tool calls depend on the model,
	// so the tool assertions below are only guaranteed against the mock.
	startCLIAppWithTarget(t, "ai-coding-agents/claude-code", "run-collector")

	anchor := `fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.llm_request"
| filter gen_ai.operation.name == "chat"
| filter gen_ai.provider.name == "anthropic"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(gen_ai.response.model)
| filter isNotNull(gen_ai.usage.input_tokens)
| filter isNotNull(gen_ai.usage.output_tokens)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`

	// Claude Code exports no GenAI metrics of its own; the collector's
	// signal_to_metrics connector derives these from the enriched spans. The
	// cache-token counters are not asserted: the mock reports zero cache tokens,
	// and pollMetricExists requires a non-zero sum.
	auditSpanWithMetrics(t, "claude-code", "opentelemetry-collector", GenericProfile, anchor, "claude-code",
		append([]string{
			"gen_ai.client.inference.usage.input_tokens",
			"gen_ai.client.inference.usage.output_tokens",
		}, genAIClientMetrics...),
		"Backend mocked when Anthropic credentials are absent: an in-process httptest server serves the Messages API via ANTHROPIC_BASE_URL.")
	assertSpanWithAttrs(t, scopedDQL(anchor), []string{
		"gen_ai.provider.name",
		"gen_ai.operation.name",
		"gen_ai.request.model",
		"gen_ai.response.model",
		"gen_ai.usage.input_tokens",
		"gen_ai.usage.output_tokens",
	}, nil)

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.interaction"
| filter gen_ai.operation.name == "invoke_agent"
| filter gen_ai.provider.name == "anthropic"
| sort timestamp desc
| limit 1`), []string{
		"gen_ai.agent.name",
		"gen_ai.agent.id",
	}, nil)

	// The assistant response never reaches a span; the collector maps the
	// assistant_response log event instead (the Makefile sets
	// OTEL_LOG_ASSISTANT_RESPONSES=1).
	assertSpanWithAttrs(t, scopedDQL(`fetch logs, from: now()-10m
| filter service.name == "claude-code"
| filter event.name == "assistant_response"
| filter gen_ai.operation.name == "chat"
| sort timestamp desc
| limit 1`), []string{
		"gen_ai.provider.name",
		"gen_ai.response.model",
		"gen_ai.output.messages",
	}, nil)

	// Permission decisions: Read is allowed and Bash denied by the Makefile flags.
	assertSpanWithAttrs(t, scopedDQL(`fetch logs, from: now()-10m
| filter service.name == "claude-code"
| filter event.name == "tool_decision"
| filter tool_name == "Read" and decision == "accept"
| sort timestamp desc
| limit 1`), []string{"tool_use_id"}, nil)
	assertSpanWithAttrs(t, scopedDQL(`fetch logs, from: now()-10m
| filter service.name == "claude-code"
| filter event.name == "tool_decision"
| filter tool_name == "Bash" and decision == "reject"
| sort timestamp desc
| limit 1`), []string{"tool_use_id"}, nil)

	// Successful execution of the allowed tool.
	assertSpanWithAttrs(t, scopedDQL(`fetch logs, from: now()-10m
| filter service.name == "claude-code"
| filter event.name == "tool_result"
| filter tool_name == "Read" and success == "true"
| sort timestamp desc
| limit 1`), []string{"duration_ms"}, nil)

	// The collector maps claude_code.tool to an execute_tool span.
	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.tool"
| filter gen_ai.operation.name == "execute_tool"
| filter gen_ai.tool.name == "Read"
| sort timestamp desc
| limit 1`), []string{
		"gen_ai.provider.name",
		"gen_ai.conversation.id",
	}, nil)

	// The duration metric derived from claude_code.tool.execution. pollMetricExists
	// does not filter by dimension, so query the execute_tool operation directly.
	assertExecuteToolDurationMetric(t, "claude-code")

	// Mock traffic carries the ci-mock tag. Skipped when real credentials turn the
	// mock off.
	t.Run("mock traffic is tagged", func(t *testing.T) {
		if os.Getenv("ANTHROPIC_API_KEY") != "mock-key-for-e2e" {
			t.Skip("real Anthropic credentials set: the mock is off")
		}
		assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.llm_request"
| filter deployment.environment.name == "ci-mock"
| limit 1`), 3*time.Minute)
	})
}

// assertExecuteToolDurationMetric polls until gen_ai.client.operation.duration has
// a non-zero data point for the service with gen_ai.operation.name == execute_tool.
func assertExecuteToolDurationMetric(t *testing.T, service string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	dql := fmt.Sprintf("timeseries val = sum(gen_ai.client.operation.duration), by: {service.name, gen_ai.operation.name}, from: %q\n"+
		"| filter service.name == %q and gen_ai.operation.name == \"execute_tool\"\n"+
		"| filter arraySum(val) > 0",
		suiteStartTime.UTC().Format(time.RFC3339), service)

	for {
		records, err := dtClient.Execute(ctx, dql)
		if err == nil && len(records) > 0 {
			return
		}
		select {
		case <-ctx.Done():
			t.Errorf("gen_ai.client.operation.duration for execute_tool not found for service %q within timeout", service)
			return
		case <-time.After(15 * time.Second):
		}
	}
}
