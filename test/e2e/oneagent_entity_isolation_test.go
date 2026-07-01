package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// TestOneAgentEntityIsolation verifies that no Smartscape SERVICE entity
// accumulates spans from more than one service.name value during this nightly
// run. It is designed to run as the final step of the oneagent-nightly
// consolidated CI job, after all six per-service suite tests have completed.
//
// Entity merging is the root cause described in AI-167: when multiple demo
// services run on the same CI runner, OneAgent can group them under the same
// process group fingerprint, producing a single SERVICE entity that carries
// spans from unrelated services. This makes the Smartscape topology in the
// GenAI Observability app meaningless.
//
// The query looks for any dt.smartscape.service value associated with spans
// from more than one service.name within the last 3 hours. If any such entity
// exists the test fails and logs the offending entity IDs and the merged
// service names so that the root cause can be diagnosed.
func TestOneAgentEntityIsolation(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	dql := `fetch spans, from: now()-3h
| filter dt.openpipeline.source == "oneagent" and isNotNull(gen_ai.provider.name)
| filter isNotNull(dt.smartscape.service)
| summarize services = collectDistinct(service.name), by: {dt.smartscape.service}
| filter arraySize(services) > 1`

	records, err := dtClient.Execute(ctx, dql)
	if err != nil {
		t.Fatalf("entity isolation DQL query failed: %v", err)
	}
	if len(records) == 0 {
		t.Log("entity isolation OK: all oneagent services map to distinct SERVICE entities")
		return
	}
	for _, r := range records {
		t.Errorf("entity merging detected: dt.smartscape.service=%v contains spans from multiple services: %v",
			r["dt.smartscape.service"], fmt.Sprint(r["services"]))
	}
}
