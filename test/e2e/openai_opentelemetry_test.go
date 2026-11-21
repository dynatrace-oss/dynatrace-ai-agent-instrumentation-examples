package e2e

import (
	"testing"
)

func TestOpenAIOpenTelemetry(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "openai/opentelemetry")

	// request-trigger-guardrail sends a jailbreak topic directly to Dynatrace
	// (bypasses the collector) and is always run after the normal request.
	makeRequest(t, "openai/opentelemetry", "request-trigger-guardrail")

	auditSpan(t, "openai", "opentelemetry", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| sort start_time asc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)

	// The guardrail-triggering request is always sent last, so the latest span
	// is the one with prompt_filter_results populated (AR-015).
	auditSpan(t, "openai", "opentelemetry-guardrail", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| sort start_time desc
| limit 1`)
}
