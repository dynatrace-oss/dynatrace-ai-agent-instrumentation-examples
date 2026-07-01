package e2e

import (
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/test/e2e/internal/dynatrace"
)

var dtClient *dynatrace.Client

// testRunID is a nanosecond-precision identifier generated once per test suite
// run. It is propagated to every app process via OTEL_RESOURCE_ATTRIBUTES so
// that OTel SDK apps (Python Resource.create(), Node.js NodeSDK auto-detection)
// include it as a span resource attribute. scopedDQL in audit_test.go then
// filters DQL queries to only spans carrying this ID, giving exact per-run
// isolation even when two pipelines execute simultaneously.
//
// OneAgent apps are excluded from this mechanism — see scopedDQL for details.
var testRunID string

// suiteStartTime is recorded at suite startup and used by scopedDQL as a
// timestamp lower-bound for OneAgent spans, which do not carry test.run.id.
var suiteStartTime time.Time

func TestMain(m *testing.M) {
	testRunID = fmt.Sprintf("%d", time.Now().UnixNano())
	suiteStartTime = time.Now()

	// Inject test.run.id into every child process started by startApp /
	// startCLIApp. process.Start uses cmd.Env = os.Environ(), so any variable
	// set here is inherited. The OTel SDK merges OTEL_RESOURCE_ATTRIBUTES
	// automatically; no app code changes are required.
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
