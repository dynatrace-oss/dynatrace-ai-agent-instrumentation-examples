package e2e

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

// TestLangGraphOneAgent verifies OneAgent capture of the LangGraph demo and
// that the OpenPipeline redaction rule (openpipeline-langgraph.yaml, routed on
// dt.service.name == "langgraph/oneagent (langgraph-oneagent)") anonymizes
// input messages that mention "secret". It sends one secret and one benign
// request and asserts the first is redacted server-side while the second
// passes through.
//
// The redaction assertions require the langgraph-redact-secrets pipeline and
// its routing entry to be deployed in the target tenant (see the demo's
// openpipeline-langgraph.yaml). Without it, spans are still captured but not
// redacted, and the redaction assertions fail.
func TestLangGraphOneAgent(t *testing.T) {
	startApp(t, "langgraph/oneagent")

	runMakeTarget(t, "langgraph/oneagent", "request-secret")
	runMakeTarget(t, "langgraph/oneagent", "request")

	const svc = `| filter service.name == "langgraph/oneagent"
| filter dt.openpipeline.source == "oneagent"`

	// Secret-bearing input must be redacted by the OpenPipeline rule.
	assertSpanExists(t, scopedDQL(`fetch spans
`+svc+`
| filter `+"`gen_ai.input.messages`"+` == "***REDACTED***"
| sort timestamp desc
| limit 1`))

	// Benign input must pass through unmodified.
	assertSpanExists(t, scopedDQL(`fetch spans
`+svc+`
| filter contains(toString(`+"`gen_ai.input.messages`"+`), "cherry blossoms")
| sort timestamp desc
| limit 1`))

	// The secret content must never be stored in any form.
	assertNoMatchingSpan(t, scopedDQL(`fetch spans
`+svc+`
| filter contains(toString(`+"`gen_ai.input.messages`"+`), "launch codes")
| limit 1`))

	auditSpan(t, "langgraph", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.response.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
