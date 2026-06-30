package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetryNode(t *testing.T) {
	// CLI app: make run builds TypeScript, starts the OTel Collector (Docker),
	// then runs dist/index.js once. No triggerHaiku — the haiku request is
	// issued by make run itself.
	startCLIApp(t, "langfuse/opentelemetry-node")

	auditSpan(t, "langfuse", "opentelemetry-node", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse-node"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
