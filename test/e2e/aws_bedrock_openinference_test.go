package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)

	auditSpan(t, "aws-bedrock", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
