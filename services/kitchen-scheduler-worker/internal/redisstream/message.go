package redisstream

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

type TaskMessage struct {
	TaskID                   string
	OrderID                  string
	KitchenID                string
	StationType              string
	Operation                string
	MenuItemID               string
	MenuItemName             string
	EstimatedDurationSeconds int
	PickupDeadline           string
	Attempt                  int
	CorrelationID            string
	RecipeStepOrder          string
	ItemUnitIndex            string
	Raw                      map[string]string
}

func ParseTaskMessage(values map[string]any) (TaskMessage, error) {
	raw := make(map[string]string, len(values))
	for key, value := range values {
		raw[key] = fmt.Sprint(value)
	}

	msg := TaskMessage{
		TaskID:          strings.TrimSpace(raw["task_id"]),
		OrderID:         strings.TrimSpace(raw["order_id"]),
		KitchenID:       strings.TrimSpace(raw["kitchen_id"]),
		StationType:     strings.TrimSpace(raw["station_type"]),
		Operation:       strings.TrimSpace(raw["operation"]),
		MenuItemID:      strings.TrimSpace(raw["menu_item_id"]),
		MenuItemName:    strings.TrimSpace(raw["menu_item_name"]),
		PickupDeadline:  strings.TrimSpace(raw["pickup_deadline"]),
		CorrelationID:   strings.TrimSpace(raw["correlation_id"]),
		RecipeStepOrder: strings.TrimSpace(raw["recipe_step_order"]),
		ItemUnitIndex:   strings.TrimSpace(raw["item_unit_index"]),
		Attempt:         1,
		Raw:             raw,
	}

	if msg.TaskID == "" {
		return TaskMessage{}, errors.New("task_id is required")
	}
	if msg.OrderID == "" {
		return TaskMessage{}, errors.New("order_id is required")
	}
	if msg.KitchenID == "" {
		return TaskMessage{}, errors.New("kitchen_id is required")
	}
	if msg.StationType == "" {
		return TaskMessage{}, errors.New("station_type is required")
	}
	if msg.Operation == "" {
		return TaskMessage{}, errors.New("operation is required")
	}
	if msg.MenuItemID == "" {
		return TaskMessage{}, errors.New("menu_item_id is required")
	}

	duration, err := strconv.Atoi(strings.TrimSpace(raw["estimated_duration_seconds"]))
	if err != nil || duration <= 0 {
		return TaskMessage{}, errors.New("estimated_duration_seconds must be a positive integer")
	}
	msg.EstimatedDurationSeconds = duration

	if attemptText := strings.TrimSpace(raw["attempt"]); attemptText != "" {
		attempt, err := strconv.Atoi(attemptText)
		if err != nil || attempt <= 0 {
			return TaskMessage{}, errors.New("attempt must be a positive integer")
		}
		msg.Attempt = attempt
	}
	return msg, nil
}

func (m TaskMessage) ValuesWithAttempt(attempt int) map[string]any {
	values := make(map[string]any, len(m.Raw)+1)
	for key, value := range m.Raw {
		values[key] = value
	}
	values["attempt"] = strconv.Itoa(attempt)
	return values
}

func DLQStream(kitchenID, stationType string) string {
	return fmt.Sprintf("stream:kitchen:%s:station:%s:dlq", kitchenID, stationType)
}

func IsDLQStream(stream string) bool {
	return strings.HasSuffix(stream, ":dlq")
}

func FilterDispatchStreams(streams []string) []string {
	filtered := make([]string, 0, len(streams))
	seen := map[string]struct{}{}
	for _, stream := range streams {
		if strings.TrimSpace(stream) == "" || IsDLQStream(stream) {
			continue
		}
		if _, ok := seen[stream]; ok {
			continue
		}
		seen[stream] = struct{}{}
		filtered = append(filtered, stream)
	}
	return filtered
}
