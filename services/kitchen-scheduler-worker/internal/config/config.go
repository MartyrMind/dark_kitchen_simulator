package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	WorkerID              string
	Environment           string
	LogLevel              string
	LogFormat             string
	RedisURL              string
	RedisStreamPatterns   []string
	RedisConsumerGroup    string
	FulfillmentServiceURL string
	KitchenServiceURL     string
	StreamScanInterval    time.Duration
	XReadBlock            time.Duration
	XReadCount            int64
	MaxDispatchAttempts   int
	DispatchBackoffBase   time.Duration
	DispatchBackoffMax    time.Duration
	HTTPTimeout           time.Duration
	PrometheusPort        int
}

func Load() (Config, error) {
	cfg := Config{
		WorkerID:              envString("WORKER_ID", "scheduler-worker-1"),
		Environment:           envString("ENVIRONMENT", "local"),
		LogLevel:              envString("LOG_LEVEL", "INFO"),
		LogFormat:             envString("LOG_FORMAT", "json"),
		RedisURL:              envString("REDIS_URL", "redis://localhost:6379/0"),
		RedisStreamPatterns:   splitCSV(envString("REDIS_STREAM_PATTERNS", "stream:kitchen:*:station:*")),
		RedisConsumerGroup:    envString("REDIS_CONSUMER_GROUP", "group:kitchen-scheduler-workers"),
		FulfillmentServiceURL: strings.TrimRight(envString("FULFILLMENT_SERVICE_URL", "http://localhost:8003"), "/"),
		KitchenServiceURL:     strings.TrimRight(envString("KITCHEN_SERVICE_URL", "http://localhost:8001"), "/"),
		StreamScanInterval:    envDurationMS("STREAM_SCAN_INTERVAL_MS", 500),
		XReadBlock:            envDurationMS("XREAD_BLOCK_MS", 5000),
		XReadCount:            int64(envInt("XREAD_COUNT", 10)),
		MaxDispatchAttempts:   envInt("MAX_DISPATCH_ATTEMPTS", 5),
		DispatchBackoffBase:   envDurationMS("DISPATCH_BACKOFF_BASE_MS", 1000),
		DispatchBackoffMax:    envDurationMS("DISPATCH_BACKOFF_MAX_MS", 30000),
		HTTPTimeout:           envDurationMS("HTTP_TIMEOUT_MS", 3000),
		PrometheusPort:        envInt("PROMETHEUS_PORT", 9090),
	}
	return cfg, cfg.Validate()
}

func (c Config) Validate() error {
	var errs []error
	if strings.TrimSpace(c.WorkerID) == "" {
		errs = append(errs, errors.New("WORKER_ID must not be empty"))
	}
	if strings.TrimSpace(c.RedisURL) == "" {
		errs = append(errs, errors.New("REDIS_URL must not be empty"))
	}
	if strings.TrimSpace(c.FulfillmentServiceURL) == "" {
		errs = append(errs, errors.New("FULFILLMENT_SERVICE_URL must not be empty"))
	}
	if strings.TrimSpace(c.KitchenServiceURL) == "" {
		errs = append(errs, errors.New("KITCHEN_SERVICE_URL must not be empty"))
	}
	if c.MaxDispatchAttempts <= 0 {
		errs = append(errs, errors.New("MAX_DISPATCH_ATTEMPTS must be > 0"))
	}
	if c.HTTPTimeout <= 0 {
		errs = append(errs, errors.New("HTTP_TIMEOUT_MS must be > 0"))
	}
	if c.XReadCount <= 0 {
		errs = append(errs, errors.New("XREAD_COUNT must be > 0"))
	}
	if len(c.RedisStreamPatterns) == 0 {
		errs = append(errs, errors.New("REDIS_STREAM_PATTERNS must not be empty"))
	}
	return errors.Join(errs...)
}

func envString(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func envInt(key string, fallback int) int {
	value, ok := os.LookupEnv(key)
	if !ok || strings.TrimSpace(value) == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func envDurationMS(key string, fallback int) time.Duration {
	return time.Duration(envInt(key, fallback)) * time.Millisecond
}

func splitCSV(value string) []string {
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}

func (c Config) MetricsAddr() string {
	return fmt.Sprintf(":%d", c.PrometheusPort)
}
