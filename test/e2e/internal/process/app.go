package process

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"syscall"
	"time"
)

// App represents a demo app started via "make run".
type App struct {
	cmd *exec.Cmd
}

// Start runs "make run" in dir as a background process and waits for port 8000
// to accept connections before returning.
// -e makes environment variables take priority over makefile variable assignments,
// so credentials passed via the test environment override any app-local .env file.
func Start(dir string) (*App, error) {
	cmd := exec.Command("make", "-e", "run")
	cmd.Dir = dir
	cmd.Env = os.Environ()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("make run: %w", err)
	}
	a := &App{cmd: cmd}
	if err := a.waitReady(90 * time.Second); err != nil {
		_ = a.Stop()
		return nil, err
	}
	return a, nil
}

// StartCLI runs "make run" in dir as a background process without waiting for
// an HTTP readiness endpoint. Use this for CLI-style apps that emit telemetry
// autonomously without an HTTP interface.
// -e makes environment variables take priority over makefile variable assignments,
// so credentials passed via the test environment override any app-local .env file.
func StartCLI(dir string) (*App, error) {
	cmd := exec.Command("make", "-e", "run")
	cmd.Dir = dir
	cmd.Env = os.Environ()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("make run: %w", err)
	}
	return &App{cmd: cmd}, nil
}

// StartCLIWithTarget runs "make -e <target>" in dir as a background process
// without waiting for an HTTP readiness endpoint. Use this when a non-default
// make target is needed (e.g. "run-openpipeline" instead of "run").
func StartCLIWithTarget(dir, target string) (*App, error) {
	cmd := exec.Command("make", "-e", target)
	cmd.Dir = dir
	cmd.Env = os.Environ()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("make %s: %w", target, err)
	}
	return &App{cmd: cmd}, nil
}

// Stop kills the process group of the app, ensuring all child processes
// (e.g. uvicorn workers) are terminated along with the main process.
func (a *App) Stop() error {
	if a.cmd.Process == nil {
		return nil
	}
	pgid, err := syscall.Getpgid(a.cmd.Process.Pid)
	if err != nil {
		return a.cmd.Process.Kill()
	}
	if err := syscall.Kill(-pgid, syscall.SIGKILL); err != nil {
		return err
	}
	_ = a.cmd.Wait()
	return nil
}

func (a *App) waitReady(timeout time.Duration) error {
	client := &http.Client{Timeout: time.Second}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		resp, err := client.Get("http://localhost:8000/health")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("app not ready on /health after %v", timeout)
}
