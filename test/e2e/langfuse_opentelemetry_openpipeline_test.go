package e2e

import "testing"

func TestLangfuseOpenTelemetryOpenPipeline(t *testing.T) {
	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no collector).
	// Attribute transformation happens server-side via the OpenPipeline langfuse-ai-spans pipeline.
	// isNull(ai.observability.ingest_path) ensures we only match spans that bypassed the collector.
	startCLIAppWithTarget(t, "langfuse/opentelemetry", "run-openpipeline")

	// gen_ai.client.operation.duration and gen_ai.client.token.usage are both
	// extracted by samplingAwareHistogramMetric / samplingAwareValueMetric
	// processors in openpipeline-langfuse.yaml (spans routed to the custom
	// pipeline bypass the built-in span pipeline that would otherwise produce
	// duration on the collector path).
	auditSpanWithMetrics(t, "langfuse", "opentelemetry-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"langfuse-openpipeline", genAIClientMetrics)
}
