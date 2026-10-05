package e2e

import (
	"testing"
)

func TestLlamaStackOpenTelemetry(t *testing.T) {
	startApp(t, "llama-stack/opentelemetry")
	triggerHaiku(t, false)

	// Spans come from opentelemetry-instrumentation-openai-v2 wrapping the
	// openai client Llama Stack uses to call Ollama.
	auditSpan(t, "llama-stack", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "llama-stack/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
