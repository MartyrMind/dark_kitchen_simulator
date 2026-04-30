package redisstream

import (
	"context"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

type StreamMessage struct {
	Stream string
	ID     string
	Values map[string]any
}

type RedisBroker interface {
	Ack(ctx context.Context, stream, group, messageID string) error
	Retry(ctx context.Context, stream string, values map[string]any) error
	MoveToDLQ(ctx context.Context, stream string, values map[string]any) error
}

type Consumer struct {
	client       *redis.Client
	group        string
	consumerName string
	logger       *slog.Logger
}

func NewConsumer(client *redis.Client, group, consumerName string, logger *slog.Logger) *Consumer {
	return &Consumer{client: client, group: group, consumerName: consumerName, logger: logger}
}

func (c *Consumer) DiscoverStreams(ctx context.Context, patterns []string) ([]string, error) {
	var streams []string
	for _, pattern := range patterns {
		var cursor uint64
		for {
			keys, next, err := c.client.Scan(ctx, cursor, pattern, 100).Result()
			if err != nil {
				return nil, err
			}
			streams = append(streams, keys...)
			cursor = next
			if cursor == 0 {
				break
			}
		}
	}
	return FilterDispatchStreams(streams), nil
}

func (c *Consumer) EnsureGroup(ctx context.Context, stream string) error {
	err := c.client.XGroupCreateMkStream(ctx, stream, c.group, "0").Err()
	if err == nil {
		return nil
	}
	if strings.Contains(err.Error(), "BUSYGROUP") {
		return nil
	}
	return err
}

func (c *Consumer) Read(ctx context.Context, streams []string, count int64, block time.Duration) ([]StreamMessage, error) {
	if len(streams) == 0 {
		return nil, nil
	}
	argsStreams := append([]string{}, streams...)
	for range streams {
		argsStreams = append(argsStreams, ">")
	}
	result, err := c.client.XReadGroup(ctx, &redis.XReadGroupArgs{
		Group:    c.group,
		Consumer: c.consumerName,
		Streams:  argsStreams,
		Count:    count,
		Block:    block,
	}).Result()
	if errors.Is(err, redis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	messages := make([]StreamMessage, 0)
	for _, stream := range result {
		for _, msg := range stream.Messages {
			messages = append(messages, StreamMessage{Stream: stream.Stream, ID: msg.ID, Values: msg.Values})
		}
	}
	return messages, nil
}

func (c *Consumer) Ack(ctx context.Context, stream, group, messageID string) error {
	return c.client.XAck(ctx, stream, group, messageID).Err()
}

func (c *Consumer) Retry(ctx context.Context, stream string, values map[string]any) error {
	return c.client.XAdd(ctx, &redis.XAddArgs{Stream: stream, Values: values}).Err()
}

func (c *Consumer) MoveToDLQ(ctx context.Context, stream string, values map[string]any) error {
	return c.client.XAdd(ctx, &redis.XAddArgs{Stream: stream, Values: values}).Err()
}

func ParseRedisURL(raw string) (*redis.Options, error) {
	return redis.ParseURL(raw)
}
