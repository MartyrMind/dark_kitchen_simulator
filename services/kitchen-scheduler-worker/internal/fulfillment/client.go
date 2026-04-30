package fulfillment

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sync/atomic"
)

var ErrNotFound = errors.New("fulfillment task not found")

type Client struct {
	baseURL string
	http    *http.Client
}

func NewClient(baseURL string, httpClient *http.Client) *Client {
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	return &Client{baseURL: baseURL, http: httpClient}
}

func (c *Client) GetTaskSnapshot(ctx context.Context, taskID, correlationID string) (TaskSnapshot, error) {
	var out TaskSnapshot
	err := c.doJSON(ctx, http.MethodGet, "/internal/tasks/"+taskID, nil, correlationID, &out)
	if errors.Is(err, ErrNotFound) {
		return TaskSnapshot{}, err
	}
	return out, err
}

func (c *Client) GetDispatchReadiness(ctx context.Context, taskID, correlationID string) (DispatchReadiness, error) {
	var out DispatchReadiness
	err := c.doJSON(ctx, http.MethodGet, "/internal/tasks/"+taskID+"/dispatch-readiness", nil, correlationID, &out)
	return out, err
}

func (c *Client) MarkDisplayed(ctx context.Context, taskID string, req MarkDisplayedRequest, correlationID string) (MarkDisplayedResponse, error) {
	var out MarkDisplayedResponse
	err := c.doJSON(ctx, http.MethodPost, "/internal/tasks/"+taskID+"/mark-displayed", req, correlationID, &out)
	if err != nil && isConflict(err) {
		return out, nil
	}
	return out, err
}

func (c *Client) DispatchFailed(ctx context.Context, taskID string, req DispatchFailedRequest, correlationID string) error {
	return c.doJSON(ctx, http.MethodPost, "/internal/tasks/"+taskID+"/dispatch-failed", req, correlationID, nil)
}

func (c *Client) doJSON(ctx context.Context, method, path string, body any, correlationID string, out any) error {
	var reader *bytes.Reader
	if body == nil {
		reader = bytes.NewReader(nil)
	} else {
		payload, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(payload)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Request-ID", newRequestID())
	if correlationID != "" {
		req.Header.Set("X-Correlation-ID", correlationID)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		return ErrNotFound
	}
	if resp.StatusCode == http.StatusConflict {
		return httpError{statusCode: resp.StatusCode}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return httpError{statusCode: resp.StatusCode}
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

type httpError struct {
	statusCode int
}

func (e httpError) Error() string {
	return fmt.Sprintf("fulfillment http status %d", e.statusCode)
}

func isConflict(err error) bool {
	var httpErr httpError
	return errors.As(err, &httpErr) && httpErr.statusCode == http.StatusConflict
}

func newRequestID() string {
	return fmt.Sprintf("worker-%d", nextRequestID())
}

var requestCounter uint64

func nextRequestID() uint64 {
	return atomic.AddUint64(&requestCounter, 1)
}
