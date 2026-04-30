package scheduler

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/clock"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/fulfillment"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/kitchen"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/metrics"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/redisstream"
)

const (
	ReasonTaskNotReady                  = "task_not_ready"
	ReasonNoDispatchCandidates          = "no_dispatch_candidates"
	ReasonKitchenServiceUnavailable     = "kitchen_service_unavailable"
	ReasonFulfillmentServiceUnavailable = "fulfillment_service_unavailable"
	ReasonKdsDeliveryFailed             = "kds_delivery_failed"
	ReasonMarkDisplayedFailed           = "mark_displayed_failed"
	ReasonInvalidMessage                = "invalid_message"
	ReasonUnexpectedError               = "unexpected_error"
)

type FulfillmentClient interface {
	GetTaskSnapshot(ctx context.Context, taskID, correlationID string) (fulfillment.TaskSnapshot, error)
	GetDispatchReadiness(ctx context.Context, taskID, correlationID string) (fulfillment.DispatchReadiness, error)
	MarkDisplayed(ctx context.Context, taskID string, req fulfillment.MarkDisplayedRequest, correlationID string) (fulfillment.MarkDisplayedResponse, error)
	DispatchFailed(ctx context.Context, taskID string, req fulfillment.DispatchFailedRequest, correlationID string) error
}

type KitchenClient interface {
	GetDispatchCandidates(ctx context.Context, kitchenID, stationType, correlationID string) ([]kitchen.DispatchCandidate, error)
	DeliverTaskToKDS(ctx context.Context, stationID string, req kitchen.KdsDeliveryRequest, correlationID string) (kitchen.KdsDeliveryResponse, error)
}

type Dispatcher struct {
	WorkerID     string
	Group        string
	MaxAttempts  int
	BackoffBase  time.Duration
	BackoffMax   time.Duration
	Fulfillment  FulfillmentClient
	Kitchen      KitchenClient
	Broker       redisstream.RedisBroker
	Clock        clock.Clock
	Metrics      *metrics.Metrics
	Logger       *slog.Logger
	AsyncRetries bool
}

func (d *Dispatcher) Handle(ctx context.Context, streamMsg redisstream.StreamMessage) error {
	started := time.Now()
	msg, err := redisstream.ParseTaskMessage(streamMsg.Values)
	if err != nil {
		return d.invalid(ctx, streamMsg, err)
	}
	if d.Metrics != nil {
		d.Metrics.DispatchAttempts.WithLabelValues(msg.KitchenID, msg.StationType).Inc()
		defer d.Metrics.DispatchLatency.WithLabelValues(msg.KitchenID, msg.StationType).Observe(time.Since(started).Seconds())
	}
	correlationID := msg.CorrelationID
	if correlationID == "" {
		correlationID = "dispatch-" + msg.TaskID
	}
	logger := d.Logger.With(
		"worker_id", d.WorkerID,
		"correlation_id", correlationID,
		"task_id", msg.TaskID,
		"order_id", msg.OrderID,
		"kitchen_id", msg.KitchenID,
		"station_type", msg.StationType,
		"redis_stream", streamMsg.Stream,
		"redis_message_id", streamMsg.ID,
		"attempt", msg.Attempt,
	)

	snapshot, err := d.Fulfillment.GetTaskSnapshot(ctx, msg.TaskID, correlationID)
	if errors.Is(err, fulfillment.ErrNotFound) {
		logger.Warn("task snapshot not found, acking stale message")
		return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
	}
	if err != nil {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonFulfillmentServiceUnavailable, err)
	}
	if isTerminal(snapshot.Status) {
		logger.Info("task already terminal or displayed, acking stale message", "status", snapshot.Status)
		return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
	}
	if !isDispatchable(snapshot.Status) {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonTaskNotReady, nil)
	}

	readiness, err := d.Fulfillment.GetDispatchReadiness(ctx, msg.TaskID, correlationID)
	if err != nil {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonFulfillmentServiceUnavailable, err)
	}
	if !readiness.ReadyToDispatch {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonTaskNotReady, nil)
	}

	candidates, err := d.Kitchen.GetDispatchCandidates(ctx, msg.KitchenID, msg.StationType, correlationID)
	if err != nil {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonKitchenServiceUnavailable, err)
	}
	station, ok := SelectStation(candidates)
	if !ok {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonNoDispatchCandidates, nil)
	}

	kdsTask, err := d.Kitchen.DeliverTaskToKDS(ctx, station.StationID, kitchen.KdsDeliveryRequest{
		TaskID:                   msg.TaskID,
		OrderID:                  msg.OrderID,
		KitchenID:                msg.KitchenID,
		StationType:              msg.StationType,
		Operation:                msg.Operation,
		MenuItemName:             msg.MenuItemName,
		EstimatedDurationSeconds: msg.EstimatedDurationSeconds,
		PickupDeadline:           msg.PickupDeadline,
		IdempotencyKey:           KDSIdempotencyKey(msg.TaskID),
	}, correlationID)
	if err != nil {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonKdsDeliveryFailed, err)
	}

	_, err = d.Fulfillment.MarkDisplayed(ctx, msg.TaskID, fulfillment.MarkDisplayedRequest{
		StationID:    station.StationID,
		KdsTaskID:    kdsTask.KdsTaskID,
		DisplayedAt:  d.nowRFC3339(),
		DispatcherID: d.WorkerID,
	}, correlationID)
	if err != nil {
		return d.retryOrDLQ(ctx, streamMsg, msg, correlationID, ReasonMarkDisplayedFailed, err)
	}

	logger.Info("task dispatched", "station_id", station.StationID, "kds_task_id", kdsTask.KdsTaskID)
	if d.Metrics != nil {
		d.Metrics.DispatchSuccess.WithLabelValues(msg.KitchenID, msg.StationType, station.StationID).Inc()
	}
	return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
}

func (d *Dispatcher) invalid(ctx context.Context, streamMsg redisstream.StreamMessage, parseErr error) error {
	values := map[string]any{
		"failure_reason":      ReasonInvalidMessage,
		"failed_at":           d.nowRFC3339(),
		"worker_id":           d.WorkerID,
		"original_stream":     streamMsg.Stream,
		"original_message_id": streamMsg.ID,
		"parse_error":         parseErr.Error(),
	}
	for key, value := range streamMsg.Values {
		values[key] = value
	}
	if err := d.Broker.MoveToDLQ(ctx, streamMsg.Stream+":dlq", values); err != nil {
		return err
	}
	if d.Metrics != nil {
		d.Metrics.RedisDLQMessages.WithLabelValues("unknown", "unknown").Inc()
		d.Metrics.DispatchFailed.WithLabelValues("unknown", "unknown", ReasonInvalidMessage).Inc()
	}
	return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
}

func (d *Dispatcher) retryOrDLQ(ctx context.Context, streamMsg redisstream.StreamMessage, msg redisstream.TaskMessage, correlationID, reason string, cause error) error {
	if msg.Attempt >= d.MaxAttempts {
		dlqStream := redisstream.DLQStream(msg.KitchenID, msg.StationType)
		values := redisstream.DLQValues(msg, reason, d.WorkerID, streamMsg.Stream, streamMsg.ID, msg.Attempt, d.now())
		if err := d.Broker.MoveToDLQ(ctx, dlqStream, values); err != nil {
			return err
		}
		if d.Metrics != nil {
			d.Metrics.RedisDLQMessages.WithLabelValues(msg.KitchenID, msg.StationType).Inc()
			d.Metrics.DispatchFailed.WithLabelValues(msg.KitchenID, msg.StationType, reason).Inc()
		}
		_ = d.Fulfillment.DispatchFailed(ctx, msg.TaskID, fulfillment.DispatchFailedRequest{
			Reason:       reason,
			FailedAt:     d.nowRFC3339(),
			DispatcherID: d.WorkerID,
			Attempts:     msg.Attempt,
		}, correlationID)
		return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
	}

	nextAttempt := msg.Attempt + 1
	delay := redisstream.Backoff(msg.Attempt, d.BackoffBase, d.BackoffMax)
	retry := func() error {
		if d.Clock != nil {
			d.Clock.Sleep(delay)
		} else {
			time.Sleep(delay)
		}
		return d.Broker.Retry(ctx, streamMsg.Stream, msg.ValuesWithAttempt(nextAttempt))
	}
	if d.AsyncRetries {
		go func() {
			if err := retry(); err != nil && d.Logger != nil {
				d.Logger.Error("failed to schedule retry", "error", err, "reason", reason)
			}
		}()
	} else if err := retry(); err != nil {
		return err
	}
	if d.Metrics != nil {
		d.Metrics.DispatchRetries.WithLabelValues(msg.KitchenID, msg.StationType, reason).Inc()
	}
	if d.Logger != nil {
		d.Logger.Info("scheduled dispatch retry", "reason", reason, "next_attempt", nextAttempt, "delay_ms", delay.Milliseconds(), "error", errorString(cause))
	}
	return d.Broker.Ack(ctx, streamMsg.Stream, d.Group, streamMsg.ID)
}

func (d *Dispatcher) now() time.Time {
	if d.Clock != nil {
		return d.Clock.Now().UTC()
	}
	return time.Now().UTC()
}

func (d *Dispatcher) nowRFC3339() string {
	return d.now().Format(time.RFC3339Nano)
}

func isDispatchable(status string) bool {
	return status == "queued" || status == "retrying"
}

func isTerminal(status string) bool {
	switch status {
	case "displayed", "in_progress", "done", "cancelled", "failed":
		return true
	default:
		return false
	}
}

func errorString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
