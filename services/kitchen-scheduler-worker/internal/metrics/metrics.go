package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
)

type Metrics struct {
	DispatchAttempts prometheus.Counter
	DispatchSuccess  prometheus.Counter
	DispatchFailed   *prometheus.CounterVec
	DispatchRetries  *prometheus.CounterVec
	DispatchLatency  prometheus.Histogram
	RedisDLQMessages prometheus.Counter
}

func New(reg prometheus.Registerer) *Metrics {
	m := &Metrics{
		DispatchAttempts: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "dispatch_attempts_total",
			Help: "Total dispatch attempts.",
		}),
		DispatchSuccess: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "dispatch_success_total",
			Help: "Total successful dispatches.",
		}),
		DispatchFailed: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_failed_total",
			Help: "Total failed dispatches.",
		}, []string{"reason"}),
		DispatchRetries: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "dispatch_retries_total",
			Help: "Total scheduled dispatch retries.",
		}, []string{"reason"}),
		DispatchLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "dispatch_latency_seconds",
			Help:    "Dispatch latency in seconds.",
			Buckets: prometheus.DefBuckets,
		}),
		RedisDLQMessages: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "redis_dlq_messages_total",
			Help: "Total Redis DLQ messages written.",
		}),
	}
	reg.MustRegister(m.DispatchAttempts, m.DispatchSuccess, m.DispatchFailed, m.DispatchRetries, m.DispatchLatency, m.RedisDLQMessages)
	return m
}
