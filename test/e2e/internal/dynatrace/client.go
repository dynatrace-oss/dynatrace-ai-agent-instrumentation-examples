package dynatrace

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

// Client queries the Dynatrace platform storage API.
type Client struct {
	endpoint string
	token    string
	http     *http.Client
}

func New(endpoint, token string) *Client {
	return &Client{
		endpoint: strings.TrimRight(endpoint, "/"),
		token:    token,
		http:     &http.Client{Timeout: httpTimeout()},
	}
}

// httpTimeout is the per-request HTTP timeout for DT platform API calls. It must
// exceed the server-side requestTimeoutMilliseconds (25s) with headroom for
// gateway latency. Defaults to 60s; override with E2E_DT_HTTP_TIMEOUT (a Go
// duration, e.g. "90s").
func httpTimeout() time.Duration {
	if v := os.Getenv("E2E_DT_HTTP_TIMEOUT"); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return 60 * time.Second
}

type executeRequest struct {
	Query                      string `json:"query"`
	RequestTimeoutMilliseconds int    `json:"requestTimeoutMilliseconds"`
}

type queryResponse struct {
	State        string       `json:"state"`
	RequestToken string       `json:"requestToken"`
	Result       *queryResult `json:"result"`
	Error        *queryError  `json:"error"`
}

type queryResult struct {
	Records []map[string]interface{} `json:"records"`
}

type queryError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Execute runs dql once and returns whatever records DT returns (no retry).
func (c *Client) Execute(ctx context.Context, dql string) ([]map[string]interface{}, error) {
	return c.execute(ctx, dql)
}

// PollUntilSpans repeatedly executes the DQL query until at least one record is
// returned or the context deadline is reached.
func (c *Client) PollUntilSpans(ctx context.Context, dql string, interval time.Duration) ([]map[string]interface{}, error) {
	var lastErr error
	for {
		records, err := c.execute(ctx, dql)
		switch {
		case err != nil:
			// Transient query failures (slow gateway, HTTP client timeout, 5xx)
			// should not abort the poll — keep retrying until the context
			// deadline. Only surface the error if the deadline is hit.
			lastErr = err
		case len(records) > 0:
			return records, nil
		}
		select {
		case <-ctx.Done():
			if lastErr != nil {
				return nil, fmt.Errorf("timed out waiting for DT spans (last query error: %w)", lastErr)
			}
			return nil, fmt.Errorf("timed out waiting for DT spans: %w", ctx.Err())
		case <-time.After(interval):
		}
	}
}

func (c *Client) execute(ctx context.Context, dql string) ([]map[string]interface{}, error) {
	body, err := json.Marshal(executeRequest{
		Query:                      dql,
		RequestTimeoutMilliseconds: 25000,
	})
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		c.endpoint+"/platform/storage/query/v1/query:execute",
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Api-Token "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("DT API returned HTTP %d: %s", resp.StatusCode, b)
	}

	var qr queryResponse
	if err := json.NewDecoder(resp.Body).Decode(&qr); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	if qr.Error != nil {
		return nil, fmt.Errorf("DT API error %d: %s", qr.Error.Code, qr.Error.Message)
	}

	if qr.State == "RUNNING" {
		return c.poll(ctx, qr.RequestToken)
	}
	if qr.State != "SUCCEEDED" {
		return nil, fmt.Errorf("unexpected query state: %s", qr.State)
	}
	if qr.Result == nil {
		return nil, nil
	}
	return qr.Result.Records, nil
}

func (c *Client) poll(ctx context.Context, token string) ([]map[string]interface{}, error) {
	for {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet,
			c.endpoint+"/platform/storage/query/v1/query:poll?requestToken="+url.QueryEscape(token),
			nil,
		)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Api-Token "+c.token)

		resp, err := c.http.Do(req)
		if err != nil {
			return nil, err
		}
		if resp.StatusCode >= 400 {
			b, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			return nil, fmt.Errorf("DT API returned HTTP %d: %s", resp.StatusCode, b)
		}

		var qr queryResponse
		decErr := json.NewDecoder(resp.Body).Decode(&qr)
		resp.Body.Close()
		if decErr != nil {
			return nil, fmt.Errorf("decode poll response: %w", decErr)
		}

		switch qr.State {
		case "SUCCEEDED":
			if qr.Result == nil {
				return nil, nil
			}
			return qr.Result.Records, nil
		case "RUNNING":
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(2 * time.Second):
			}
		default:
			msg := qr.State
			if qr.Error != nil {
				msg = qr.Error.Message
			}
			return nil, fmt.Errorf("query failed: %s", msg)
		}
	}
}
