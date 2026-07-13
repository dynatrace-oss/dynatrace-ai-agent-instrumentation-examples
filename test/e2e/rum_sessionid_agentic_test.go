package e2e

import (
	"crypto/rand"
	"fmt"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	startApp(t, "rum/opentelemetry")

	// One UUID for the whole test — mirrors what the browser does with sessionStorage.
	// All three requests share it so gen_ai.conversation.id is consistent across
	// multiple traceIDs, which is the agentic session-stitching pattern.
	conversationID := newUUID(t)
	for range 3 {
		triggerRUMMusicAgent(t, conversationID)
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

// newUUID returns a random UUID v4, matching the format crypto.randomUUID() produces in the browser.
func newUUID(t *testing.T) string {
	t.Helper()
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		t.Fatalf("generate UUID: %v", err)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}
