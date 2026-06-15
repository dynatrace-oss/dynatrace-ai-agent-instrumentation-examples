package process

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"time"
)

// App represents a demo app started via "make run".
type App struct {
	cmd *exec.Cmd
}

// Start runs "make run" in dir as a background process and waits for port 8000
// to accept connections before returning.
func Start(dir string) (*App, error) {
	cmd := exec.Command("make", "run")
	cmd.Dir = dir
	cmd.Env = os.Environ()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
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

// Stop kills the app process.
func (a *App) Stop() error {
	if a.cmd.Process == nil {
		return nil
	}
	if err := a.cmd.Process.Kill(); err != nil {
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
