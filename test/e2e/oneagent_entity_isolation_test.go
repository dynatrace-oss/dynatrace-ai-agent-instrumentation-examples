package e2e

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"
)

// oneagentSuites lists every service.name value produced by the oneagent-nightly
// consolidated job. The isolation check waits until all of them appear in
// Dynatrace (with dt.smartscape.service set) before asserting entity isolation,
// ensuring enrichment is complete and avoiding false passes from partial data.
var oneagentSuites = []string{
	"aws-bedrock/oneagent",
	"anthropic/oneagent",
	"openai/oneagent",
	"ollama/oneagent",
	"groq/oneagent",
	"cohere/oneagent",
}

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
	if _, err := time.Parse(time.RFC3339, startTimeStr); err != nil {
		t.Fatalf("NIGHTLY_START_TIME %q is not a valid RFC3339 timestamp: %v", startTimeStr, err)
	}

	// Step 1: wait until enriched spans from all expected services are visible.
	// This guards against a false pass caused by dt.smartscape.service enrichment
	// not yet being complete when the check runs.
	t.Log("waiting for enriched spans from all oneagent services...")
	waitCtx, waitCancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer waitCancel()

	if err := pollUntilAllServicesEnriched(waitCtx, t, startTimeStr); err != nil {
		t.Fatalf("timed out waiting for enriched spans from all oneagent services: %v", err)
	}
	t.Log("all services have enriched spans — running entity isolation check")

	// Step 2: assert no SERVICE entity contains spans from more than one service.name.
	assertCtx, assertCancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer assertCancel()

	mergeDQL := fmt.Sprintf(`fetch spans, from: now()-4h
| filter dt.openpipeline.source == "oneagent" and isNotNull(gen_ai.provider.name)
| filter isNotNull(dt.smartscape.service)
| filter timestamp >= "%s"
| summarize services = collectDistinct(service.name), by: {dt.smartscape.service}
| filter arraySize(services) > 1`, startTimeStr)

	records, err := dtClient.Execute(assertCtx, mergeDQL)
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

// pollUntilAllServicesEnriched polls DT until every service in oneagentSuites
// has at least one span with dt.smartscape.service set, confirming that the
// Dynatrace enrichment pipeline has processed spans from the full run.
func pollUntilAllServicesEnriched(ctx context.Context, t *testing.T, startTimeStr string) error {
	t.Helper()

	// Build a DQL query that returns one row per service.name that has at least
	// one enriched span since job start.
	dql := fmt.Sprintf(`fetch spans, from: now()-4h
| filter dt.openpipeline.source == "oneagent" and isNotNull(gen_ai.provider.name)
| filter isNotNull(dt.smartscape.service)
| filter timestamp >= "%s"
| summarize count = count(), by: {service.name}`, startTimeStr)

	for {
		records, err := dtClient.Execute(ctx, dql)
		if err != nil {
			return fmt.Errorf("DQL query failed: %w", err)
		}

		seen := make(map[string]bool, len(records))
		for _, r := range records {
			if svc, ok := r["service.name"].(string); ok {
				seen[svc] = true
			}
		}

		missing := make([]string, 0)
		for _, svc := range oneagentSuites {
			if !seen[svc] {
				missing = append(missing, svc)
			}
		}

		if len(missing) == 0 {
			return nil
		}

		t.Logf("waiting for enriched spans from: %v", missing)
		select {
		case <-ctx.Done():
			return fmt.Errorf("context deadline exceeded; still missing enriched spans for: %v", missing)
		case <-time.After(15 * time.Second):
		}
	}
}
