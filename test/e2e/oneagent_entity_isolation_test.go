package e2e

import (
	"context"
	"fmt"
	"os"
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
// The test is scoped to the current job run via the NIGHTLY_START_TIME env var
// (set by the CI workflow at job start). It skips when that variable is absent
// so that it does not interfere with per-suite PR runs or local executions.
func TestOneAgentEntityIsolation(t *testing.T) {
	startTimeStr := os.Getenv("NIGHTLY_START_TIME")
	if startTimeStr == "" {
		t.Skip("NIGHTLY_START_TIME not set — skipping entity isolation check (only runs in oneagent-nightly CI job)")
	}

	// Validate the timestamp so a malformed value produces a clear error.
	if _, err := time.Parse(time.RFC3339, startTimeStr); err != nil {
		t.Fatalf("NIGHTLY_START_TIME %q is not a valid RFC3339 timestamp: %v", startTimeStr, err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	// Fetch a window wide enough to cover the whole nightly job, then narrow
	// to spans generated on or after job start to exclude any leftover spans
	// from a previous run.
	dql := fmt.Sprintf(`fetch spans, from: now()-4h
| filter dt.openpipeline.source == "oneagent" and isNotNull(gen_ai.provider.name)
| filter isNotNull(dt.smartscape.service)
| filter timestamp >= "%s"
| summarize services = collectDistinct(service.name), by: {dt.smartscape.service}
| filter arraySize(services) > 1`, startTimeStr)

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
