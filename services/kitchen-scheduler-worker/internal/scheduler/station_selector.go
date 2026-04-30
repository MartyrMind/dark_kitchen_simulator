package scheduler

import (
	"sort"

	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/kitchen"
)

func SelectStation(candidates []kitchen.DispatchCandidate) (kitchen.DispatchCandidate, bool) {
	filtered := make([]kitchen.DispatchCandidate, 0, len(candidates))
	for _, candidate := range candidates {
		if candidate.Status != "available" {
			continue
		}
		if candidate.Health != "ok" {
			continue
		}
		if candidate.VisibleBacklogSize >= candidate.VisibleBacklogLimit {
			continue
		}
		filtered = append(filtered, candidate)
	}
	if len(filtered) == 0 {
		return kitchen.DispatchCandidate{}, false
	}
	sort.Slice(filtered, func(i, j int) bool {
		left, right := filtered[i], filtered[j]
		if left.VisibleBacklogSize != right.VisibleBacklogSize {
			return left.VisibleBacklogSize < right.VisibleBacklogSize
		}
		if left.BusySlots != right.BusySlots {
			return left.BusySlots < right.BusySlots
		}
		return left.StationID < right.StationID
	})
	return filtered[0], true
}
