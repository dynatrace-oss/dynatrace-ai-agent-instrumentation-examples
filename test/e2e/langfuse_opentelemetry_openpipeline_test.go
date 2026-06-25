package e2e

import "testing"

func TestLangfuseOpenTelemetryOpenPipeline(t *testing.T) {
	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no collector).
	// Attribute transformation happens server-side via the OpenPipeline langfuse-ai-spans pipeline.
	// isNull(ai.observability.ingest_path) ensures we only match spans that bypassed the collector.
	startCLIAppWithTarget(t, "langfuse/opentelemetry", "run-openpipeline")

	auditSpan(t, "langfuse", "opentelemetry-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
