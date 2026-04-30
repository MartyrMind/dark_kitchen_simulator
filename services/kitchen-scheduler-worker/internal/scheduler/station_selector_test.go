package scheduler

import (
	"testing"

	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/kitchen"
)

func TestSelectStationFiltersAndSorts(t *testing.T) {
	selected, ok := SelectStation([]kitchen.DispatchCandidate{
		{StationID: "unhealthy", Status: "available", Health: "bad", VisibleBacklogSize: 0, VisibleBacklogLimit: 2},
		{StationID: "full", Status: "available", Health: "ok", VisibleBacklogSize: 2, VisibleBacklogLimit: 2},
		{StationID: "busy", Status: "available", Health: "ok", VisibleBacklogSize: 1, VisibleBacklogLimit: 3, BusySlots: 2},
		{StationID: "best", Status: "available", Health: "ok", VisibleBacklogSize: 1, VisibleBacklogLimit: 3, BusySlots: 1},
		{StationID: "closed", Status: "unavailable", Health: "ok", VisibleBacklogSize: 0, VisibleBacklogLimit: 3},
	})
	if !ok {
		t.Fatal("expected station")
	}
	if selected.StationID != "best" {
		t.Fatalf("selected = %q", selected.StationID)
	}
}

func TestSelectStationDeterministicTie(t *testing.T) {
	selected, ok := SelectStation([]kitchen.DispatchCandidate{
		{StationID: "b", Status: "available", Health: "ok", VisibleBacklogSize: 0, VisibleBacklogLimit: 3},
		{StationID: "a", Status: "available", Health: "ok", VisibleBacklogSize: 0, VisibleBacklogLimit: 3},
	})
	if !ok || selected.StationID != "a" {
		t.Fatalf("selected = %#v ok=%v", selected, ok)
	}
}

func TestIdempotencyKey(t *testing.T) {
	if got := KDSIdempotencyKey("task-1"); got != "task-1:dispatch:v1" {
		t.Fatalf("KDSIdempotencyKey() = %q", got)
	}
}
