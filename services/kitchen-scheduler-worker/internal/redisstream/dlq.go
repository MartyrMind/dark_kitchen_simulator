package redisstream

import "time"

func DLQValues(msg TaskMessage, reason, workerID, originalStream, originalMessageID string, attempts int, failedAt time.Time) map[string]any {
	values := msg.ValuesWithAttempt(attempts)
	values["failure_reason"] = reason
	values["failed_at"] = failedAt.UTC().Format(time.RFC3339Nano)
	values["worker_id"] = workerID
	values["attempts"] = attempts
	values["original_stream"] = originalStream
	values["original_message_id"] = originalMessageID
	return values
}
