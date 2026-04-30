package fulfillment

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientGetTaskSnapshotAndHeaders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/internal/tasks/task-1" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if r.Header.Get("X-Correlation-ID") != "corr-1" {
			t.Fatalf("missing correlation header")
		}
		_ = json.NewEncoder(w).Encode(TaskSnapshot{TaskID: "task-1", Status: "queued"})
	}))
	defer server.Close()

	got, err := NewClient(server.URL, server.Client()).GetTaskSnapshot(context.Background(), "task-1", "corr-1")
	if err != nil {
		t.Fatalf("GetTaskSnapshot() error = %v", err)
	}
	if got.TaskID != "task-1" {
		t.Fatalf("TaskID = %q", got.TaskID)
	}
}

func TestClientMarkDisplayedPayload(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload MarkDisplayedRequest
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode = %v", err)
		}
		if payload.StationID != "station-1" || payload.KdsTaskID != "kds-1" {
			t.Fatalf("payload = %#v", payload)
		}
		_ = json.NewEncoder(w).Encode(MarkDisplayedResponse{TaskID: "task-1", Status: "displayed"})
	}))
	defer server.Close()

	_, err := NewClient(server.URL, server.Client()).MarkDisplayed(context.Background(), "task-1", MarkDisplayedRequest{
		StationID:    "station-1",
		KdsTaskID:    "kds-1",
		DisplayedAt:  "2026-04-30T10:00:00Z",
		DispatcherID: "worker-1",
	}, "corr-1")
	if err != nil {
		t.Fatalf("MarkDisplayed() error = %v", err)
	}
}
