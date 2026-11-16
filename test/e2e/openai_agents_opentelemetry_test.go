package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestOpenAIAgentsOpenTelemetry(t *testing.T) {
	startApp(t, "openai-agents/opentelemetry")
	conversationID := triggerCSAgent(t)

	auditSpan(t, "openai-agents", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai-cs-agents"
| filter gen_ai.provider.name == "azure.ai.openai" or gen_ai.system == "azure.ai.openai"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)

	// The two turns share one conversation_id but land in separate traces. Assert
	// that gen_ai.conversation.id stitches them: one conversation spanning >= 2
	// traces. This only passes if the app stamps conversation.id on the spans.
	//
	// This is a plain existence assertion, not an auditSpan call: the query ends in
	// a summarize, so its single record holds only `traces` — no trace.id and no
	// gen_ai.* attributes. Feeding that to auditSpan made every required check fail
	// and overwrote the real (PASS) report for this suite, since both audits share
	// the reports/openai-agents-opentelemetry.{json,md} filename.
	assertSpanExistsWithin(t, scopedDQL(fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "openai-cs-agents"
| filter gen_ai.conversation.id == "%s"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2
| limit 1`, conversationID)), 5*time.Minute)
}
