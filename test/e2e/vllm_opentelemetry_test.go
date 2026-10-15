package e2e

import (
	"context"
	"testing"
	"time"
)

func TestVLLMOpenTelemetry(t *testing.T) {
	// CLI app: make e2e starts vLLM (CPU image) with traceidratio 0.25, exporting
	// its own spans to Dynatrace, then makes 20 OpenInference-traced client calls.
	startCLIAppWithTarget(t, "vllm/opentelemetry", "e2e")

	auditSpan(t, "vllm", "opentelemetry", GenericProfile,
		scopedDQL(`fetch spans, from: now()-15m
| filter service.name == "vllm/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`))

	// Client gen_ai spans are not sampled: all 20 must arrive.
	assertSpanExists(t, scopedDQL(`fetch spans, from: now()-15m
| filter service.name == "vllm/opentelemetry" and isNotNull(gen_ai.request.model)
| summarize n = count()
| filter n >= 20`))

	// vLLM keeps some llm_request spans, each joined to a client trace.
	vllmSpans := scopedDQL(`fetch spans, from: now()-15m
| filter service.name == "vllm" and span.name == "llm_request"
| join [
    fetch spans, from: now()-15m
    | filter service.name == "vllm/opentelemetry" and isNotNull(gen_ai.request.model)
    | fields trace.id
  ], on: { trace.id }
| summarize n = count()`)
	assertSpanExists(t, vllmSpans+"\n| filter n > 0")

	// After ingestion settles, vLLM must have dropped some: fewer than 20.
	time.Sleep(30 * time.Second)
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	if _, err := dtClient.PollUntilSpans(ctx, vllmSpans+"\n| filter n < 20", 15*time.Second); err != nil {
		t.Fatalf("expected vLLM to sample out some of 20 llm_request spans: %v", err)
	}
}
