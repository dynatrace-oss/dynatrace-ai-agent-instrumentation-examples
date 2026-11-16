package e2e

import (
	"testing"
)

func TestOGXOpenTelemetry(t *testing.T) {
	startApp(t, "ogx/opentelemetry")
	triggerHaiku(t, false)

	// Spans come from opentelemetry-instrumentation-openai-v2 wrapping the
	// openai client OGX uses to call Ollama.
	auditSpan(t, "ogx", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ogx/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
