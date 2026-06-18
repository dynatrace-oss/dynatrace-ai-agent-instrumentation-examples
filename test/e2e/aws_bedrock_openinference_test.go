package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)

	assertSpanExists(t,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| limit 1`,
	)
}
