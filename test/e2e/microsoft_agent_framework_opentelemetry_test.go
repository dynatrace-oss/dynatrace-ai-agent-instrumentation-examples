package e2e

import (
	"testing"
)

func TestMicrosoftAgentFrameworkOpenTelemetry(t *testing.T) {
	startCLIApp(t, "microsoft-agent-framework/opentelemetry")

	// make run exports straight to Dynatrace. The framework emits both
	// gen_ai.client.* metrics natively, so no backfill is needed on this path.
	// The agent/tool/workflow duration metrics are NOT checked here — they are
	// derived by the collector, which this target does not start. See
	// TestMicrosoftAgentFrameworkOpenTelemetryCollector.
	auditSpanWithMetrics(t, "microsoft-agent-framework", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "microsoft-agent-framework"
| filter gen_ai.provider.name == "microsoft.agent_framework" or gen_ai.system == "microsoft.agent_framework"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"microsoft-agent-framework", genAIClientMetrics)
}
