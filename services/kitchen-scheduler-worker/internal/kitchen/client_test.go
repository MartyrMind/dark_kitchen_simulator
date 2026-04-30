package kitchen

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientGetDispatchCandidates(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("kitchen_id") != "1" || r.URL.Query().Get("station_type") != "grill" {
			t.Fatalf("query = %s", r.URL.RawQuery)
		}
		_ = json.NewEncoder(w).Encode([]DispatchCandidate{{StationID: "7", Status: "available", Health: "ok"}})
	}))
	defer server.Close()

	got, err := NewClient(server.URL, server.Client()).GetDispatchCandidates(context.Background(), "1", "grill", "corr-1")
	if err != nil {
		t.Fatalf("GetDispatchCandidates() error = %v", err)
	}
	if got[0].StationID != "7" {
		t.Fatalf("StationID = %q", got[0].StationID)
	}
}

func TestClientDeliverTaskToKDS(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/internal/kds/stations/7/tasks" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		var payload KdsDeliveryRequest
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode = %v", err)
		}
		if payload.IdempotencyKey != "task-1:dispatch:v1" {
			t.Fatalf("idempotency key = %q", payload.IdempotencyKey)
		}
		_, _ = w.Write([]byte(`{"kds_task_id":9,"task_id":"task-1","station_id":7,"status":"displayed"}`))
	}))
	defer server.Close()

	got, err := NewClient(server.URL, server.Client()).DeliverTaskToKDS(context.Background(), "7", KdsDeliveryRequest{
		TaskID:                   "task-1",
		OrderID:                  "order-1",
		KitchenID:                "1",
		StationType:              "grill",
		Operation:                "cook",
		EstimatedDurationSeconds: 10,
		IdempotencyKey:           "task-1:dispatch:v1",
	}, "corr-1")
	if err != nil {
		t.Fatalf("DeliverTaskToKDS() error = %v", err)
	}
	if got.KdsTaskID != "9" || got.StationID != "7" {
		t.Fatalf("response = %#v", got)
	}
}
