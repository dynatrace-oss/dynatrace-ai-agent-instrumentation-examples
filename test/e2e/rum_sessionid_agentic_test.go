package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	startApp(t, "rum/opentelemetry")

	driveRUMBrowserSession(t)

	// This is the direct-export path (`make run`): the app ships spans and metrics
	// straight to Dynatrace with no collector. pydantic-ai emits
	// gen_ai.client.token.usage natively, so that is the only metric this path can
	// produce on its own, and the only one asserted here.
	//
	// The two duration metrics are NOT asserted here. On this path they come from
	// openpipeline-rum.yaml, which ships in this repo but is a tenant-side config: a
	// checkout alone does not make them exist, so asserting them would fail on any
	// tenant where the pipeline has not been deployed. They are covered by
	// TestRUMOpenTelemetryCollector instead, which derives them locally in a
	// collector and therefore passes from a clean checkout.
	metrics := []string{genAIClientTokenUsageMetric}

	auditSpanWithMetrics(t, "rum", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"rum/opentelemetry", metrics)

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.provider.name == "bedrock"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-azure", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.provider.name == "azure"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
}

// driveRUMBrowserSession drives a real browser via Playwright so the Dynatrace RUM
// JS fires, injects W3C traceparent headers, and generates session data visible in
// Experience Vitals. The script asks 6 questions across providers; the CI env
// triggers headless mode. Shared by the direct-export and collector tests, which
// exercise the same browser flow against differently-configured backends.
func driveRUMBrowserSession(t *testing.T) {
	t.Helper()
	cmd := exec.Command("make", "demo")
	cmd.Dir = filepath.Join(repoRoot(), "rum/opentelemetry")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make demo: %v", err)
	}
}
