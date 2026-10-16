package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/test/e2e/internal/process"
)

func repoRoot() string {
	_, f, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(f), "..", "..")
}

// startApp runs make install then starts make run in <repoRoot>/<appDir>.
// Registers cleanup to stop the app and, for apps with a collector, make stop.
func startApp(t *testing.T, appDir string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	// install only needs PATH and HOME — no credentials required for package installation
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.Start(dir)
	if err != nil {
		t.Fatalf("start app %s: %v", appDir, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop app %s: %v", appDir, err)
		}
		// noop for apps without a stop target (e.g. plain oneagent apps)
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// startAppWithTarget runs make install then starts make <target> in
// <repoRoot>/<appDir>, waiting for the HTTP readiness endpoint like startApp.
// Use for HTTP apps that need a non-default make target (e.g. "run-collector").
func startAppWithTarget(t *testing.T, appDir, target string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.StartWithTarget(dir, target)
	if err != nil {
		t.Fatalf("start app %s (%s): %v", appDir, target, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop app %s: %v", appDir, err)
		}
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// startCLIApp runs make install then starts make run in <repoRoot>/<appDir>
// without waiting for an HTTP readiness endpoint. The app emits telemetry
// autonomously; use assertGenAISpan to wait for spans.
func startCLIApp(t *testing.T, appDir string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.StartCLI(dir)
	if err != nil {
		t.Fatalf("start cli app %s: %v", appDir, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop cli app %s: %v", appDir, err)
		}
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// startCLIAppWithTarget runs make install then starts make <target> in <repoRoot>/<appDir>.
// Use when a non-default make target is needed (e.g. "run-openpipeline").
func startCLIAppWithTarget(t *testing.T, appDir, target string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.StartCLIWithTarget(dir, target)
	if err != nil {
		t.Fatalf("start cli app %s (%s): %v", appDir, target, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop cli app %s: %v", appDir, err)
		}
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// runCLIAppWithTarget is like startCLIAppWithTarget but blocks until make <target>
// exits, so slow startups (image pull, model load) don't eat the span poll timeout.
func runCLIAppWithTarget(t *testing.T, appDir, target string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)
	t.Cleanup(func() {
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})

	for _, args := range [][]string{{"install"}, {"-e", target}} {
		cmd := exec.Command("make", args...)
		cmd.Dir = dir
		cmd.Env = os.Environ()
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			t.Fatalf("make %v in %s: %v", args, appDir, err)
		}
	}
}
