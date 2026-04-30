package kitchen

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
)

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

func (c *Client) GetDispatchCandidates(ctx context.Context, kitchenID, stationType, correlationID string) ([]DispatchCandidate, error) {
	path := "/internal/kds/dispatch-candidates?kitchen_id=" + url.QueryEscape(kitchenID) + "&station_type=" + url.QueryEscape(stationType)
	var out []DispatchCandidate
	err := c.doJSON(ctx, http.MethodGet, path, nil, correlationID, &out)
	return out, err
}

func (c *Client) DeliverTaskToKDS(ctx context.Context, stationID string, req KdsDeliveryRequest, correlationID string) (KdsDeliveryResponse, error) {
	var out KdsDeliveryResponse
	err := c.doJSON(ctx, http.MethodPost, "/internal/kds/stations/"+url.PathEscape(stationID)+"/tasks", req, correlationID, &out)
	if err != nil && isConflict(err) {
		return out, nil
	}
	return out, err
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
	req.Header.Set("X-Request-ID", "worker-request")
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
	return fmt.Sprintf("kitchen http status %d", e.statusCode)
}

func isConflict(err error) bool {
	var httpErr httpError
	return errors.As(err, &httpErr) && httpErr.statusCode == http.StatusConflict
}
