package redisstream

import "testing"

func validValues() map[string]any {
	return map[string]any{
		"task_id":                    "task-1",
		"order_id":                   "order-1",
		"kitchen_id":                 "kitchen-1",
		"station_type":               "grill",
		"operation":                  "cook",
		"menu_item_id":               "item-1",
		"estimated_duration_seconds": "120",
	}
}

func TestParseTaskMessageValid(t *testing.T) {
	msg, err := ParseTaskMessage(validValues())
	if err != nil {
		t.Fatalf("ParseTaskMessage() error = %v", err)
	}
	if msg.Attempt != 1 {
		t.Fatalf("Attempt = %d", msg.Attempt)
	}
}

func TestParseTaskMessageRequiredFields(t *testing.T) {
	for _, key := range []string{"task_id", "kitchen_id"} {
		values := validValues()
		delete(values, key)
		if _, err := ParseTaskMessage(values); err == nil {
			t.Fatalf("expected missing %s to fail", key)
		}
	}
}

func TestParseTaskMessageInvalidDuration(t *testing.T) {
	values := validValues()
	values["estimated_duration_seconds"] = "nope"
	if _, err := ParseTaskMessage(values); err == nil {
		t.Fatal("expected invalid duration error")
	}
}

func TestStreamHelpers(t *testing.T) {
	dlq := DLQStream("k1", "grill")
	if dlq != "stream:kitchen:k1:station:grill:dlq" {
		t.Fatalf("DLQStream() = %q", dlq)
	}
	if !IsDLQStream(dlq) {
		t.Fatal("expected dlq stream")
	}
	filtered := FilterDispatchStreams([]string{"stream:kitchen:k1:station:grill", dlq, "stream:kitchen:k1:station:grill"})
	if len(filtered) != 1 {
		t.Fatalf("filtered = %#v", filtered)
	}
}

func TestBackoff(t *testing.T) {
	if got := Backoff(3, 10, 100); got != 40 {
		t.Fatalf("Backoff() = %s", got)
	}
}
