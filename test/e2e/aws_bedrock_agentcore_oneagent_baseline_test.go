package e2e

import (
	"fmt"
	"testing"
	"time"
)

// TestAWSBedrockAgentCoreOneAgentBaseline is a throwaway diagnostic (branch
// experiment/agentcore-oneagent-baseline, not meant to be merged). The real
// PoC (aws-bedrock-agentcore/opentelemetry on the PR branch) establishes its
// own OTel SDK TracerProvider/MeterProvider in-process, and OneAgent produced
// zero spans for that process across two separate CI runs -- not just a
// trace-correlation mismatch, no OneAgent-sourced span at all, anywhere.
//
// This app is identical except main.py never calls setup_instrumentation():
// its OTel API calls (get_tracer/get_meter/create_counter/...) fall back to
// no-op proxies, and trace.set_tracer_provider()/metrics.set_meter_provider()
// are never invoked. If OneAgent's FastAPI/Starlette sensor fires here, that
// isolates the app's own OTel SDK provider setup as the specific cause of the
// zero-span result on the real PoC.
func TestAWSBedrockAgentCoreOneAgentBaseline(t *testing.T) {
	const service = "aws-bedrock-agentcore/opentelemetry-oneagent"

	startApp(t, "aws-bedrock-agentcore/opentelemetry")
	triggerAgentCoreHarness(t)

	assertSpanExistsWithin(t, fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == %q
| filter dt.openpipeline.source == "oneagent"
| sort start_time desc
| limit 1`, service), 3*time.Minute)
}
