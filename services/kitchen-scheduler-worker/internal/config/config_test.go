package config

import "testing"

func TestLoadDefaults(t *testing.T) {
	t.Setenv("WORKER_ID", "")
	cfg, err := Load()
	if err == nil {
		t.Fatal("expected empty worker id to fail validation")
	}
	if cfg.RedisURL == "" {
		t.Fatal("expected redis url default")
	}
}

func TestEnvOverrides(t *testing.T) {
	t.Setenv("WORKER_ID", "worker-x")
	t.Setenv("MAX_DISPATCH_ATTEMPTS", "9")
	t.Setenv("HTTP_TIMEOUT_MS", "1234")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if cfg.WorkerID != "worker-x" {
		t.Fatalf("WorkerID = %q", cfg.WorkerID)
	}
	if cfg.MaxDispatchAttempts != 9 {
		t.Fatalf("MaxDispatchAttempts = %d", cfg.MaxDispatchAttempts)
	}
	if cfg.HTTPTimeout.Milliseconds() != 1234 {
		t.Fatalf("HTTPTimeout = %s", cfg.HTTPTimeout)
	}
}

func TestInvalidMaxAttempts(t *testing.T) {
	t.Setenv("MAX_DISPATCH_ATTEMPTS", "0")
	if _, err := Load(); err == nil {
		t.Fatal("expected validation error")
	}
}

func TestMissingRequiredURLs(t *testing.T) {
	cfg := Config{WorkerID: "w", MaxDispatchAttempts: 1, HTTPTimeout: 1, XReadCount: 1, RedisStreamPatterns: []string{"stream:*"}}
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected missing url validation error")
	}
}
