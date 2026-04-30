package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/clock"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/config"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/fulfillment"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/kitchen"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/logging"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/metrics"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/redisstream"
	"github.com/dark-kitchen/dark-kitchen-fulfillment/services/kitchen-scheduler-worker/internal/scheduler"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		slog.Error("invalid config", "error", err)
		os.Exit(1)
	}
	logger := logging.New(cfg.LogLevel, cfg.LogFormat, os.Stdout).With(
		"service", "kitchen-scheduler-worker",
		"environment", cfg.Environment,
		"worker_id", cfg.WorkerID,
	)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	registry := prometheus.NewRegistry()
	workerMetrics := metrics.New(registry)
	metricsServer := startHTTPServer(cfg, registry, logger)

	redisOptions, err := redisstream.ParseRedisURL(cfg.RedisURL)
	if err != nil {
		logger.Error("invalid redis url", "error", err)
		os.Exit(1)
	}
	redisClient := redis.NewClient(redisOptions)
	defer redisClient.Close()

	httpClient := &http.Client{Timeout: cfg.HTTPTimeout}
	consumer := redisstream.NewConsumer(redisClient, cfg.RedisConsumerGroup, cfg.WorkerID, logger)
	dispatcher := &scheduler.Dispatcher{
		WorkerID:     cfg.WorkerID,
		Group:        cfg.RedisConsumerGroup,
		MaxAttempts:  cfg.MaxDispatchAttempts,
		BackoffBase:  cfg.DispatchBackoffBase,
		BackoffMax:   cfg.DispatchBackoffMax,
		Fulfillment:  fulfillment.NewClient(cfg.FulfillmentServiceURL, httpClient),
		Kitchen:      kitchen.NewClient(cfg.KitchenServiceURL, httpClient),
		Broker:       consumer,
		Clock:        clock.RealClock{},
		Metrics:      workerMetrics,
		Logger:       logger,
		AsyncRetries: true,
	}

	run(ctx, cfg, consumer, dispatcher, logger)

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = metricsServer.Shutdown(shutdownCtx)
}

func startHTTPServer(cfg config.Config, registry *prometheus.Registry, logger *slog.Logger) *http.Server {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.HandlerFor(registry, promhttp.HandlerOpts{}))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":    "ok",
			"service":   "kitchen-scheduler-worker",
			"worker_id": cfg.WorkerID,
		})
	})
	server := &http.Server{Addr: cfg.MetricsAddr(), Handler: mux}
	go func() {
		logger.Info("metrics server starting", "addr", cfg.MetricsAddr())
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("metrics server failed", "error", err)
		}
	}()
	return server
}

func run(ctx context.Context, cfg config.Config, consumer *redisstream.Consumer, dispatcher *scheduler.Dispatcher, logger *slog.Logger) {
	ticker := time.NewTicker(cfg.StreamScanInterval)
	defer ticker.Stop()
	var streams []string

	for {
		select {
		case <-ctx.Done():
			logger.Info("worker shutting down")
			return
		case <-ticker.C:
			discovered, err := consumer.DiscoverStreams(ctx, cfg.RedisStreamPatterns)
			if err != nil {
				logger.Error("stream discovery failed", "error", err)
				continue
			}
			streams = discovered
			for _, stream := range streams {
				if err := consumer.EnsureGroup(ctx, stream); err != nil {
					logger.Error("consumer group ensure failed", "stream", stream, "error", err)
				}
			}
		default:
			if len(streams) == 0 {
				time.Sleep(cfg.StreamScanInterval)
				continue
			}
			messages, err := consumer.Read(ctx, streams, cfg.XReadCount, cfg.XReadBlock)
			if errors.Is(err, context.Canceled) {
				return
			}
			if err != nil {
				logger.Error("xreadgroup failed", "error", err)
				time.Sleep(cfg.StreamScanInterval)
				continue
			}
			for _, msg := range messages {
				if err := dispatcher.Handle(ctx, msg); err != nil {
					logger.Error("message handling failed", "stream", msg.Stream, "message_id", msg.ID, "error", err)
				}
			}
		}
	}
}
