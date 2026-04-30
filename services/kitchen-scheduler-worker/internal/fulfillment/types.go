package fulfillment

type TaskSnapshot struct {
	TaskID                   string  `json:"task_id"`
	OrderID                  string  `json:"order_id"`
	KitchenID                string  `json:"kitchen_id"`
	MenuItemID               string  `json:"menu_item_id"`
	StationType              string  `json:"station_type"`
	StationID                *string `json:"station_id"`
	KdsTaskID                *string `json:"kds_task_id"`
	Operation                string  `json:"operation"`
	Status                   string  `json:"status"`
	EstimatedDurationSeconds int     `json:"estimated_duration_seconds"`
	PickupDeadline           string  `json:"pickup_deadline"`
	Attempts                 int     `json:"attempts"`
}

type DispatchReadiness struct {
	TaskID          string   `json:"task_id"`
	ReadyToDispatch bool     `json:"ready_to_dispatch"`
	WaitingFor      []string `json:"waiting_for"`
	Reason          string   `json:"reason"`
}

type MarkDisplayedRequest struct {
	StationID    string `json:"station_id"`
	KdsTaskID    string `json:"kds_task_id"`
	DisplayedAt  string `json:"displayed_at"`
	DispatcherID string `json:"dispatcher_id"`
}

type MarkDisplayedResponse struct {
	TaskID      string `json:"task_id"`
	Status      string `json:"status"`
	StationID   string `json:"station_id"`
	KdsTaskID   string `json:"kds_task_id"`
	DisplayedAt string `json:"displayed_at"`
}

type DispatchFailedRequest struct {
	Reason       string `json:"reason"`
	FailedAt     string `json:"failed_at"`
	DispatcherID string `json:"dispatcher_id"`
	Attempts     int    `json:"attempts,omitempty"`
}
