package e2e

import (
	"context"
	"testing"
	"time"
)

const awsStrandsDQL = `fetch spans, from: now()-10m
| filter service.name == "aws-strands/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| limit 1`

func TestAWSStrandsOneAgent(t *testing.T) {
	startApp(t, "aws-strands/oneagent")

	// Retry up to 3 times: OneAgent's strands-agents sensor may need additional
	// warm-up time after the first request before it starts capturing spans.
	const maxAttempts = 3
	var gotSpans bool
	for attempt := range maxAttempts {
		triggerAgent(t)
		ctx, cancel := context.WithTimeout(context.Background(), 4*time.Minute)
		_, err := dtClient.PollUntilSpans(ctx, scopedDQL(awsStrandsDQL), 15*time.Second)
		cancel()
		if err == nil {
			gotSpans = true
			break
		}
		if attempt < maxAttempts-1 {
			t.Logf("attempt %d/%d: no spans captured yet, retrying trigger", attempt+1, maxAttempts)
		}
	}
	if !gotSpans {
		t.Fatalf("no spans captured after %d trigger attempts", maxAttempts)
	}
	triggerAgentGuardrail(t)

	// triggerAgent and triggerAgentGuardrail each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail)
	// trace deterministically.
	auditSpan(t, "aws-strands", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// The guardrail-triggering request is always sent last, so the latest
	// matching span is the one that actually tripped the guardrail.
	auditOneAgentGuardrailSpan(t, "aws-strands", "oneagent",
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.guardrail.input.content)
| sort start_time desc
| limit 1`)
}
