package kitchen

import (
	"encoding/json"
	"strconv"
)

type DispatchCandidate struct {
	StationID           string `json:"station_id"`
	StationType         string `json:"station_type"`
	Status              string `json:"status"`
	Capacity            int    `json:"capacity"`
	BusySlots           int    `json:"busy_slots"`
	VisibleBacklogSize  int    `json:"visible_backlog_size"`
	VisibleBacklogLimit int    `json:"visible_backlog_limit"`
	Health              string `json:"health"`
}

func (c *DispatchCandidate) UnmarshalJSON(data []byte) error {
	type candidateAlias struct {
		StationID           json.RawMessage `json:"station_id"`
		StationType         string          `json:"station_type"`
		Status              string          `json:"status"`
		Capacity            int             `json:"capacity"`
		BusySlots           int             `json:"busy_slots"`
		VisibleBacklogSize  int             `json:"visible_backlog_size"`
		VisibleBacklogLimit int             `json:"visible_backlog_limit"`
		Health              string          `json:"health"`
	}
	var raw candidateAlias
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	id, err := flexibleString(raw.StationID)
	if err != nil {
		return err
	}
	*c = DispatchCandidate{
		StationID:           id,
		StationType:         raw.StationType,
		Status:              raw.Status,
		Capacity:            raw.Capacity,
		BusySlots:           raw.BusySlots,
		VisibleBacklogSize:  raw.VisibleBacklogSize,
		VisibleBacklogLimit: raw.VisibleBacklogLimit,
		Health:              raw.Health,
	}
	return nil
}

type KdsDeliveryRequest struct {
	TaskID                   string `json:"task_id"`
	OrderID                  string `json:"order_id"`
	KitchenID                string `json:"kitchen_id"`
	StationType              string `json:"station_type"`
	Operation                string `json:"operation"`
	MenuItemName             string `json:"menu_item_name,omitempty"`
	EstimatedDurationSeconds int    `json:"estimated_duration_seconds"`
	PickupDeadline           string `json:"pickup_deadline,omitempty"`
	IdempotencyKey           string `json:"idempotency_key"`
}

type KdsDeliveryResponse struct {
	KdsTaskID string `json:"kds_task_id"`
	TaskID    string `json:"task_id"`
	StationID string `json:"station_id"`
	Status    string `json:"status"`
}

func (r *KdsDeliveryResponse) UnmarshalJSON(data []byte) error {
	type responseAlias struct {
		KdsTaskID json.RawMessage `json:"kds_task_id"`
		TaskID    string          `json:"task_id"`
		StationID json.RawMessage `json:"station_id"`
		Status    string          `json:"status"`
	}
	var raw responseAlias
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	kdsTaskID, err := flexibleString(raw.KdsTaskID)
	if err != nil {
		return err
	}
	stationID, err := flexibleString(raw.StationID)
	if err != nil {
		return err
	}
	*r = KdsDeliveryResponse{
		KdsTaskID: kdsTaskID,
		TaskID:    raw.TaskID,
		StationID: stationID,
		Status:    raw.Status,
	}
	return nil
}

func flexibleString(data json.RawMessage) (string, error) {
	var text string
	if err := json.Unmarshal(data, &text); err == nil {
		return text, nil
	}
	var number json.Number
	if err := json.Unmarshal(data, &number); err == nil {
		return number.String(), nil
	}
	var integer int64
	if err := json.Unmarshal(data, &integer); err == nil {
		return strconv.FormatInt(integer, 10), nil
	}
	return "", nil
}
