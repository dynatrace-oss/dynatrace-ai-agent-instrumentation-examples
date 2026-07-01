package e2e

import (
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/test/e2e/internal/dynatrace"
)

var dtClient *dynatrace.Client

// testRunID is a unique identifier for this test run, injected into every app
// as an OTEL resource attribute so DQL queries are scoped to spans from this
// run only — preventing interference between concurrent or recent pipeline runs.
var testRunID string

func TestMain(m *testing.M) {
	testRunID = fmt.Sprintf("%d", time.Now().UnixNano())
	// Propagate to all child processes started by startApp/startCLIApp.
	// The OTel SDK merges OTEL_RESOURCE_ATTRIBUTES automatically into the resource.
	existing := os.Getenv("OTEL_RESOURCE_ATTRIBUTES")
	runAttr := "test.run.id=" + testRunID
	if existing != "" {
		runAttr = existing + "," + runAttr
	}
	os.Setenv("OTEL_RESOURCE_ATTRIBUTES", runAttr)

	dtClient = dynatrace.New(mustEnv("DT_APPS_ENDPOINT"), mustEnv("DT_API_TOKEN"))
	os.Exit(m.Run())
}

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		panic("required env var not set: " + key)
	}
	return v
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
