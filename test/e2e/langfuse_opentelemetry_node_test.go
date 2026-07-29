package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetryNode(t *testing.T) {
	// CLI app: make run builds TypeScript, starts the OTel Collector (Docker),
	// then runs dist/index.js once. No triggerHaiku — the haiku request is
	// issued by make run itself.
	startOpenAICompatibleMock(t, "OPENAI_API_KEY", "OPENAI_API_BASE")
	startCLIApp(t, "langfuse/opentelemetry-node")

	// The AI Observability app charts both gen_ai.client.operation.duration and
	// gen_ai.client.token.usage; the collector path derives duration via the
	// built-in spanmetrics connector and token usage via signal_to_metrics, both
	// wired in ../opentelemetry/otel-collector-config.yaml (shared by this and the
	// Python variant).
	auditSpanWithMetrics(t, "langfuse", "opentelemetry-node", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse-node"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"langfuse-node", genAIClientMetrics)
}
