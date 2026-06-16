package e2e

import (
	"os"
	"testing"

	"github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/test/e2e/internal/dynatrace"
)

var dtClient *dynatrace.Client

func TestMain(m *testing.M) {
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
