package scheduler

import (
	"context"
	"errors"
	"log/slog"
	"testing"
	"time"

	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/fulfillment"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/kitchen"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/redisstream"
)

type fakeFulfillment struct {
	snapshot       fulfillment.TaskSnapshot
	readiness      fulfillment.DispatchReadiness
	snapshotErr    error
	markErr        error
	dispatchFailed int
	marked         int
}

func (f *fakeFulfillment) GetTaskSnapshot(context.Context, string, string) (fulfillment.TaskSnapshot, error) {
	return f.snapshot, f.snapshotErr
}

func (f *fakeFulfillment) GetDispatchReadiness(context.Context, string, string) (fulfillment.DispatchReadiness, error) {
	return f.readiness, nil
}

func (f *fakeFulfillment) MarkDisplayed(context.Context, string, fulfillment.MarkDisplayedRequest, string) (fulfillment.MarkDisplayedResponse, error) {
	f.marked++
	return fulfillment.MarkDisplayedResponse{Status: "displayed"}, f.markErr
}

func (f *fakeFulfillment) DispatchFailed(context.Context, string, fulfillment.DispatchFailedRequest, string) error {
	f.dispatchFailed++
	return nil
}

type fakeKitchen struct {
	candidates []kitchen.DispatchCandidate
	deliverErr error
	delivered  int
}

func (k *fakeKitchen) GetDispatchCandidates(context.Context, string, string, string) ([]kitchen.DispatchCandidate, error) {
	return k.candidates, nil
}

func (k *fakeKitchen) DeliverTaskToKDS(context.Context, string, kitchen.KdsDeliveryRequest, string) (kitchen.KdsDeliveryResponse, error) {
	k.delivered++
	return kitchen.KdsDeliveryResponse{KdsTaskID: "kds-1", StationID: "station-1", Status: "displayed"}, k.deliverErr
}

type fakeBroker struct {
	acked   int
	retried int
	dlq     int
}

func (b *fakeBroker) Ack(context.Context, string, string, string) error {
	b.acked++
	return nil
}

func (b *fakeBroker) Retry(context.Context, string, map[string]any) error {
	b.retried++
	return nil
}

func (b *fakeBroker) MoveToDLQ(context.Context, string, map[string]any) error {
	b.dlq++
	return nil
}

type fakeClock struct{}

func (fakeClock) Now() time.Time      { return time.Date(2026, 4, 30, 10, 0, 0, 0, time.UTC) }
func (fakeClock) Sleep(time.Duration) {}

func newTestDispatcher(ff *fakeFulfillment, fk *fakeKitchen, broker *fakeBroker) *Dispatcher {
	return &Dispatcher{
		WorkerID:    "worker-1",
		Group:       "group-1",
		MaxAttempts: 2,
		BackoffBase: time.Millisecond,
		BackoffMax:  time.Millisecond,
		Fulfillment: ff,
		Kitchen:     fk,
		Broker:      broker,
		Clock:       fakeClock{},
		Logger:      slog.Default(),
	}
}

func dispatchMessage(attempt string) redisstream.StreamMessage {
	values := map[string]any{
		"task_id":                    "task-1",
		"order_id":                   "order-1",
		"kitchen_id":                 "1",
		"station_type":               "grill",
		"operation":                  "cook",
		"menu_item_id":               "item-1",
		"estimated_duration_seconds": "10",
	}
	if attempt != "" {
		values["attempt"] = attempt
	}
	return redisstream.StreamMessage{Stream: "stream:kitchen:1:station:grill", ID: "1-0", Values: values}
}

func TestDispatcherTerminalTaskAcksWithoutKDS(t *testing.T) {
	ff := &fakeFulfillment{snapshot: fulfillment.TaskSnapshot{Status: "done"}}
	fk := &fakeKitchen{}
	broker := &fakeBroker{}
	err := newTestDispatcher(ff, fk, broker).Handle(context.Background(), dispatchMessage(""))
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if broker.acked != 1 || fk.delivered != 0 {
		t.Fatalf("acked=%d delivered=%d", broker.acked, fk.delivered)
	}
}

func TestDispatcherNotReadySchedulesRetryAndAck(t *testing.T) {
	ff := &fakeFulfillment{
		snapshot:  fulfillment.TaskSnapshot{Status: "queued"},
		readiness: fulfillment.DispatchReadiness{ReadyToDispatch: false},
	}
	broker := &fakeBroker{}
	err := newTestDispatcher(ff, &fakeKitchen{}, broker).Handle(context.Background(), dispatchMessage(""))
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if broker.retried != 1 || broker.acked != 1 {
		t.Fatalf("retried=%d acked=%d", broker.retried, broker.acked)
	}
}

func TestDispatcherSuccessfulFlow(t *testing.T) {
	ff := &fakeFulfillment{
		snapshot:  fulfillment.TaskSnapshot{Status: "queued"},
		readiness: fulfillment.DispatchReadiness{ReadyToDispatch: true},
	}
	fk := &fakeKitchen{candidates: []kitchen.DispatchCandidate{{StationID: "station-1", Status: "available", Health: "ok", VisibleBacklogLimit: 3}}}
	broker := &fakeBroker{}
	err := newTestDispatcher(ff, fk, broker).Handle(context.Background(), dispatchMessage(""))
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if fk.delivered != 1 || ff.marked != 1 || broker.acked != 1 {
		t.Fatalf("delivered=%d marked=%d acked=%d", fk.delivered, ff.marked, broker.acked)
	}
}

func TestDispatcherFailuresScheduleRetry(t *testing.T) {
	ff := &fakeFulfillment{
		snapshot:  fulfillment.TaskSnapshot{Status: "queued"},
		readiness: fulfillment.DispatchReadiness{ReadyToDispatch: true},
	}
	fk := &fakeKitchen{
		candidates: []kitchen.DispatchCandidate{{StationID: "station-1", Status: "available", Health: "ok", VisibleBacklogLimit: 3}},
		deliverErr: errors.New("temporary"),
	}
	broker := &fakeBroker{}
	err := newTestDispatcher(ff, fk, broker).Handle(context.Background(), dispatchMessage(""))
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if broker.retried != 1 || broker.acked != 1 {
		t.Fatalf("retried=%d acked=%d", broker.retried, broker.acked)
	}
}

func TestDispatcherMaxAttemptsDLQ(t *testing.T) {
	ff := &fakeFulfillment{
		snapshot:  fulfillment.TaskSnapshot{Status: "queued"},
		readiness: fulfillment.DispatchReadiness{ReadyToDispatch: true},
	}
	broker := &fakeBroker{}
	err := newTestDispatcher(ff, &fakeKitchen{}, broker).Handle(context.Background(), dispatchMessage("2"))
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if broker.dlq != 1 || broker.acked != 1 || ff.dispatchFailed != 1 {
		t.Fatalf("dlq=%d acked=%d dispatchFailed=%d", broker.dlq, broker.acked, ff.dispatchFailed)
	}
}

func TestDispatcherInvalidMessageDLQAndAck(t *testing.T) {
	broker := &fakeBroker{}
	msg := dispatchMessage("")
	delete(msg.Values, "task_id")
	err := newTestDispatcher(&fakeFulfillment{}, &fakeKitchen{}, broker).Handle(context.Background(), msg)
	if err != nil {
		t.Fatalf("Handle() error = %v", err)
	}
	if broker.dlq != 1 || broker.acked != 1 {
		t.Fatalf("dlq=%d acked=%d", broker.dlq, broker.acked)
	}
}
