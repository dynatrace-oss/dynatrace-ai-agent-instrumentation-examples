package e2e

import (
	"testing"
)

func TestCohereOneAgent(t *testing.T) {
	startCohereCompatibleMock(t)
	startApp(t, "cohere/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "cohere", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "cohere/oneagent"
| filter gen_ai.provider.name == "cohere"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
