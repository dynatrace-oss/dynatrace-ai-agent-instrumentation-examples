package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetry(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startOpenAICompatibleMock(t, "OPENAI_API_KEY", "OPENAI_API_BASE")
	startCLIApp(t, "langfuse/opentelemetry")

	auditSpan(t, "langfuse", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)

	// The AI Observability app charts gen_ai.client.operation.duration; the
	// collector path gets it from the built-in span pipeline.
	assertGenAIDurationMetric(t, "langfuse")
}
