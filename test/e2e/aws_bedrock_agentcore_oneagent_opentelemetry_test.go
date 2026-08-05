package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// TestAWSBedrockAgentCoreOneAgentOpenTelemetry verifies this demo's hybrid
// instrumentation: a manually created span (gen_ai.* attributes around
// Bedrock AgentCore's invoke_harness, created via the plain OpenTelemetry
// API -- no SDK, no exporter, no TracerProvider; see main.py's docstring)
// gets correctly correlated into the same trace as OneAgent's own
// auto-instrumented HTTP entry span, while the accompanying
// gen_ai.client.* metrics are exported directly via a real OTel SDK
// MeterProvider/OTLP exporter (metrics only -- deliberately asymmetric with
// the span; see main.py for why).
//
// The span side depends on OneAgent's "OpenTelemetry (Python)" opt-in
// feature being enabled on the tenant (Settings > OneAgent features) -- see
// the PoC README's "Dynatrace prerequisites" section. Without it, OneAgent
// never intercepts the manually created span at all, and it is silently
// dropped (this app has no span exporter of its own to fall back to).
//
// MOCK_AGENTCORE=true is set for this suite (see e2e.yml /
// compute-e2e-matrix.sh): no AgentCore harness is available in this AWS
// account, so invoke_harness is replaced by an in-process fake stream shaped
// like a real InvokeHarness response. This means the test cannot confirm
// whether OneAgent has its own dedicated sensor for the bedrock-agentcore
// boto3 client -- no real botocore call to that service happens.
func TestAWSBedrockAgentCoreOneAgentOpenTelemetry(t *testing.T) {
	const service = "aws-bedrock-agentcore/oneagent-opentelemetry"

	startApp(t, "aws-bedrock-agentcore/oneagent-opentelemetry")
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

	report := buildReport("aws-bedrock-agentcore", "oneagent-opentelemetry", GenericProfile, mergeSpans(spans))
	report.Note = "MOCK_AGENTCORE=true: no AgentCore harness available in this AWS account; " +
		"invoke_harness replaced by an in-process fake stream shaped like a real response. " +
		"This app has no OTel SDK span exporter of its own -- OneAgent's \"OpenTelemetry (Python)\" " +
		"opt-in feature captures the manually created span directly and correlates it into " +
		"OneAgent's own trace. Metrics (checked below) are exported separately via a real SDK exporter."
	writeReport(t, report)
	logAuditResult(t, report, len(spans))

	// The actual "does the combination work" check: the manually created span
	// must be correlated (same trace) with OneAgent's own HTTP entry span, and
	// every span in the trace must be OneAgent-sourced -- there is no other
	// span export path in this app, so any non-OneAgent-sourced span, or a
	// same-named span on a *different* trace, would mean OneAgent silently
	// failed to capture it (dropped, not merely disconnected).
	if len(spans) < 2 {
		t.Errorf("expected at least 2 spans in the trace (OneAgent's HTTP entry span + the manually "+
			"created gen_ai span), found %d -- OneAgent may not have captured the manual span at all",
			len(spans))
	}
	for _, span := range spans {
		if src := fmt.Sprint(span["dt.openpipeline.source"]); src != "oneagent" {
			t.Errorf("expected every span in this trace to be OneAgent-sourced (no other span export "+
				"path exists in this app), found span %q with dt.openpipeline.source=%q", span["span.name"], src)
		}
	}

	// A regression check for the specific bug this test caught before the fix:
	// an earlier version of this app also configured its own OTel SDK span
	// exporter, which produced a *second*, disconnected copy of the same
	// invoke_harness span (same name, different trace, non-oneagent source).
	// Confirm that duplicate is really gone, not just currently absent.
	assertNoMatchingSpan(t, fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == %q
| filter span.name == "invoke_harness"
| filter dt.openpipeline.source != "oneagent"`, service))

	// The metric the AI Observability app's cost/latency charts read. Unlike
	// the span, this app exports it via a real OTel SDK MeterProvider/OTLP
	// exporter (main.py's setup_metrics_instrumentation()) -- confirmed
	// empirically that PPX's span-derived metric extraction, which covers
	// this same pair of metrics for OneAgent-sourced spans, was not
	// producing data for this span on the tested tenant (waited 24+ minutes,
	// zero datapoints), so direct export is the only path that works here.
	assertGenAIDurationMetric(t, service)
}
