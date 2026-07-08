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

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	auditSpan(t, "aws-strands", "oneagent", BedrockProfile, awsStrandsDQL)
}
