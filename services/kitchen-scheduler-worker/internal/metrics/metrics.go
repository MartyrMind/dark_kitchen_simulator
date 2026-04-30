package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
)

type Metrics struct {
	DispatchAttempts *prometheus.CounterVec
	DispatchSuccess  *prometheus.CounterVec
	DispatchFailed   *prometheus.CounterVec
	DispatchRetries  *prometheus.CounterVec
	DispatchLatency  *prometheus.HistogramVec
	RedisPending     *prometheus.GaugeVec
	RedisDLQMessages *prometheus.CounterVec
}

func New(reg prometheus.Registerer) *Metrics {
	m := &Metrics{
		DispatchAttempts: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_attempts_total",
			Help: "Total dispatch attempts.",
		}, []string{"kitchen_id", "station_type"}),
		DispatchSuccess: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_success_total",
			Help: "Total successful dispatches.",
		}, []string{"kitchen_id", "station_type", "station_id"}),
		DispatchFailed: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_failed_total",
			Help: "Total failed dispatches.",
		}, []string{"kitchen_id", "station_type", "reason"}),
		DispatchRetries: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_retries_total",
			Help: "Total scheduled dispatch retries.",
		}, []string{"kitchen_id", "station_type", "reason"}),
		DispatchLatency: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "dispatch_latency_seconds",
			Help:    "Dispatch latency in seconds.",
			Buckets: prometheus.DefBuckets,
		}, []string{"kitchen_id", "station_type"}),
		RedisPending: prometheus.NewGaugeVec(prometheus.GaugeOpts{
			Name: "redis_pending_messages",
			Help: "Redis pending messages by kitchen and station type.",
		}, []string{"kitchen_id", "station_type"}),
		RedisDLQMessages: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "redis_dlq_messages_total",
			Help: "Total Redis DLQ messages written.",
		}, []string{"kitchen_id", "station_type"}),
	}
	reg.MustRegister(m.DispatchAttempts, m.DispatchSuccess, m.DispatchFailed, m.DispatchRetries, m.DispatchLatency, m.RedisPending, m.RedisDLQMessages)
	return m
}
