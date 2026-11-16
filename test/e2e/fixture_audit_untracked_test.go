package e2e

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestUntrackedAttributes(t *testing.T) {
	known := map[string]bool{"gen_ai.request.model": true}
	span := map[string]interface{}{
		"gen_ai.request.model":     "gpt-4o",
		"gen_ai.agent.id":          "a1",
		"gen_ai.new.thing":         1,
		"gen_ai.empty":             "",
		"gen_ai.nil":               nil,
		"gen_ai.prompt.0.content":  "hi",
		"gen_ai.completion.3.role": "assistant",
		"service.name":             "svc",
		"llm.request.type":         "chat",
	}
	got := untrackedAttributes(span, known)
	want := []string{"gen_ai.agent.id", "gen_ai.new.thing"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestParseBaselineNames(t *testing.T) {
	data, err := os.ReadFile(filepath.Join(repoRoot(), "test", "e2e", "sdk-comparison-baseline.json"))
	if err != nil {
		t.Fatal(err)
	}
	names, err := parseBaselineNames(data)
	if err != nil {
		t.Fatal(err)
	}
	for _, n := range []string{"gen_ai.request.model", "gen_ai.usage.cache_read.input_tokens", "gen_ai.prompt.0.content", "dt.smartscape.service", "gen_ai.client.inference.duration"} {
		if !names[n] {
			t.Errorf("baseline name %q not found", n)
		}
	}
}
