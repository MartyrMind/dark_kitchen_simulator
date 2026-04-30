package scheduler

func KDSIdempotencyKey(taskID string) string {
	return taskID + ":dispatch:v1"
}
