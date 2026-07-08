package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetryNode(t *testing.T) {
	// CLI app: make run builds TypeScript, starts the OTel Collector (Docker),
	// then runs dist/index.js once. No triggerHaiku — the haiku request is
	// issued by make run itself.
	startMockOpenAIServer(t)
	startCLIApp(t, "langfuse/opentelemetry-node")

	auditSpan(t, "langfuse", "opentelemetry-node", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse-node"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
