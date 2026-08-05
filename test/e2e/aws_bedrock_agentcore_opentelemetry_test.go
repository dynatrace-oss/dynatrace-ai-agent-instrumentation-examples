package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// TestAWSBedrockAgentCoreOpenTelemetryOneAgent verifies that a manually
// created OTel SDK span (gen_ai.* attributes around Bedrock AgentCore's
// invoke_harness) coexists correctly with OneAgent's own auto-instrumentation
// running in the same process: both must land in the same trace, and both
// must deliver data the AI Observability app reads (spans + gen_ai.client.*
// metrics).
//
// MOCK_AGENTCORE=true is set for this suite (see e2e.yml /
// compute-e2e-matrix.sh): no AgentCore harness is available in this AWS
// account, so invoke_harness is replaced by an in-process fake stream shaped
// like a real InvokeHarness response. This means the test cannot confirm
// whether OneAgent has its own dedicated sensor for the bedrock-agentcore
// boto3 client -- no real botocore call to that service happens. It only
// confirms that OneAgent's unrelated auto-instrumentation (FastAPI/Starlette)
// and this app's manually created OTel span end up correlated in one trace,
// and that both deliver data correctly.
func TestAWSBedrockAgentCoreOpenTelemetryOneAgent(t *testing.T) {
	const service = "aws-bedrock-agentcore/opentelemetry-oneagent"

	startApp(t, "aws-bedrock-agentcore/opentelemetry")
	triggerAgentCoreHarness(t)

	dql := fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == %q
| filter gen_ai.provider.name == "aws.bedrock_agentcore"
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time desc
| limit 1`, service)

	ctx, cancel := context.WithTimeout(context.Background(), spanPollTimeout())
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, scopedDQL(dql), 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatalf("no spans returned from DT")
	}
	assertNotErrorSpan(t, records[0])

	spans := fetchTraceSpans(t, ctx, records[0])

	report := buildReport("aws-bedrock-agentcore", "opentelemetry-oneagent", GenericProfile, mergeSpans(spans))
	report.Note = "MOCK_AGENTCORE=true: no AgentCore harness available in this AWS account; " +
		"invoke_harness replaced by an in-process fake stream shaped like a real response. " +
		"Confirms OneAgent's auto-instrumentation and this app's manually created OTel SDK span " +
		"coexist in one trace and both land correctly in Dynatrace -- does NOT confirm whether " +
		"OneAgent has its own sensor for the bedrock-agentcore boto3 client, since no real call " +
		"to that service happens."
	writeReport(t, report)
	logAuditResult(t, report, len(spans))

	// The actual "does the combination work" check: at least one *other* span
	// in the same trace must be OneAgent-sourced, proving OneAgent's own
	// auto-instrumentation (of the FastAPI/Starlette layer) and this app's
	// manually created OTel SDK span ended up correlated in a single trace,
	// rather than on two disjoint traces or OneAgent dropping the request
	// entirely (see the fastapi-sync-botocore-span-propagation write-up in the
	// ai-observability-workspace repo for a case where that happens).
	foundOneAgentSpan := false
	for _, span := range spans {
		if fmt.Sprint(span["dt.openpipeline.source"]) == "oneagent" {
			foundOneAgentSpan = true
			break
		}
	}
	if !foundOneAgentSpan {
		t.Errorf("expected at least one OneAgent-sourced span (dt.openpipeline.source == \"oneagent\") "+
			"in the same trace as the manually created gen_ai span; found %d spans total, none OneAgent-sourced",
			len(spans))
	}

	// The metric the AI Observability app's cost/latency charts read. Emitted
	// directly via the OTel Metrics API in main.py -- span attributes alone
	// are not enough for OTel-sourced telemetry (see the PoC README).
	assertGenAIDurationMetric(t, service)
}
