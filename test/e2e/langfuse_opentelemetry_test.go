package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetry(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startOpenAICompatibleMock(t, "OPENAI_API_KEY", "OPENAI_API_BASE")
	startCLIApp(t, "langfuse/opentelemetry")

	// The AI Observability app charts both gen_ai.client.operation.duration and
	// gen_ai.client.token.usage; the collector path derives duration via the
	// built-in span_metrics connector and token usage via signal_to_metrics, both
	// wired in otel-collector-config.yaml.
	auditSpanWithMetrics(t, "langfuse", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"langfuse", genAIClientMetrics)
}
