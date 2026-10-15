package e2e

import (
	"testing"
)

func TestVLLMOpenTelemetry(t *testing.T) {
	// CLI app: make e2e starts vLLM (CPU image) exporting its own spans to
	// Dynatrace, then runs client.py once against it.
	startCLIAppWithTarget(t, "vllm/opentelemetry", "e2e")

	auditSpan(t, "vllm", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-15m
| filter service.name == "vllm/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`)

	// vLLM's llm_request span must join the client's trace via traceparent.
	assertSpanExists(t, `fetch spans, from: now()-15m
| filter service.name == "vllm" and span.name == "llm_request"
| join [
    fetch spans, from: now()-15m
    | filter service.name == "vllm/opentelemetry" and isNotNull(gen_ai.request.model)
    | fields trace.id
  ], on: { trace.id }
| limit 1`)
}
