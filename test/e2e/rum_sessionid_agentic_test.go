package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	startApp(t, "rum/opentelemetry")

	// Drive a real browser via Playwright so the Dynatrace RUM JS fires, injects
	// W3C traceparent headers, and generates session data visible in Experience Vitals.
	// The script asks 6 questions across providers; CI env triggers headless mode.
	cmd := exec.Command("make", "trigger")
	cmd.Dir = filepath.Join(repoRoot(), "rum/opentelemetry")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make trigger: %v", err)
	}

	auditSpan(t, "rum", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.system == "bedrock"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-azure", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.system == "azure"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
}
