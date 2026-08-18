package e2e

import (
	"testing"
)

func TestCrewAIOpenTelemetryCollector(t *testing.T) {
	// make run-collector routes the app through a local OTel Collector, which
	// derives gen_ai.invoke_agent.duration and gen_ai.invoke_workflow.duration
	// from the CrewAI spans via two span_metrics connectors. Traceloop.init pins
	// service.name on the Resource, so the collector renames it to
	// "crewai-collector" with a resource processor; that keeps this data set
	// distinct from the direct-export test (service.name == "crewai"), so a
	// derived metric can never be satisfied by the other run.
	startAppWithTarget(t, "crewai/opentelemetry", "run-collector")
	triggerHaiku(t, false)

	// genAIClientMetrics is deliberately not asserted here. CrewAI reaches its
	// model through LiteLLM and no gen_ai.client.* metric has been observed from
	// this demo on any tenant — a pre-existing regression tracked separately. The
	// two durations below do not depend on it: they are derived at the collector
	// from spans, which do arrive.
	//
	// The metric branches key on traceloop.span.kind and span name rather than on
	// gen_ai.operation.name, because opentelemetry-instrumentation-crewai sets
	// "invoke_agent" on the kickoff, agent and task spans alike — three nested
	// boundaries — and filtering on the enum would record the same wall-clock
	// three times. See the comments in the demo's otel-collector-config.yaml.
	metrics := []string{
		"gen_ai.invoke_agent.duration",
		"gen_ai.invoke_workflow.duration",
	}

	auditSpanWithMetrics(t, "crewai", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "crewai-collector"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"crewai-collector", metrics)
}
