package e2e

import (
	"testing"
)

func TestGoogleADKZeroCode(t *testing.T) {
	// Same agent as google-adk/opentelemetry, with no OTel code in the app:
	// opentelemetry-instrument builds the providers from OTEL_* env vars before
	// app.py is imported, so instrumentation is deployment config rather than a
	// source change. The audit verifies that env-only configuration reaches the
	// same attribute coverage as the in-code variant.
	//
	// make run-collector routes the app through a local OTel Collector, which
	// repairs the two gaps ADK leaves. ADK splits the GenAI semantics over two
	// nested spans per LLM call: gen_ai.provider.name and the token counts on
	// call_llm, the message content and gen_ai.operation.name on the child
	// "generate_content <model>" span. Every GenAI view in the app admits a span
	// only if gen_ai.system or gen_ai.provider.name is set, and the Prompts stream
	// then drops rows with no input and no output, so on a direct export call_llm
	// passes the first gate and fails the second while generate_content does the
	// reverse: spans reach Distributed Tracing but no prompt is ever displayed.
	// The collector sets a provider on the content-bearing span and mirrors
	// gen_ai.response.model from the request model.
	startAppWithTarget(t, "google-adk/zero-code", "run-collector")
	triggerResearch(t)

	// The derived gen_ai.invoke_agent.duration / gen_ai.execute_tool.duration
	// metrics are absent by design; this config runs no span_metrics connector.
	// See google-adk/opentelemetry for that setup.
	auditSpanWithMetrics(t, "google-adk", "zero-code", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk-zero-code"
| filter gen_ai.provider.name == "gemini"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"google-adk-zero-code", genAIClientMetrics)

	// Regression guard for the split above: a span must satisfy the app's GenAI
	// gate and carry message content at the same time, which is what makes the
	// Prompts view populate. Asserting the two conditions on separate spans would
	// pass on a raw ADK export and still show an empty view.
	assertSpanExists(t, `fetch spans, from: now()-10m
| filter service.name == "google-adk-zero-code"
| filter isNotNull(gen_ai.system) or isNotNull(gen_ai.provider.name)
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| limit 1`)

	// ADK's own spans are all span.kind=internal, so no service is detected in
	// SDv2 without an entry-point instrumentation. The FastAPI instrumentation,
	// loaded by opentelemetry-instrument, is what produces the SERVER span.
	assertSpanExists(t, `fetch spans, from: now()-10m
| filter service.name == "google-adk-zero-code"
| filter span.kind == "server"
| limit 1`)
}
