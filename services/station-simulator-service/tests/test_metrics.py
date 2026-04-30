from prometheus_client import CollectorRegistry

from app.metrics.metrics import SimulatorMetrics


def test_simulator_metrics_increment_and_render():
    metrics = SimulatorMetrics(CollectorRegistry())

    metrics.claim_attempts.labels("grill_1", "grill_1-worker-1").inc()
    metrics.claim_success.labels("grill_1", "grill_1-worker-1").inc()
    metrics.claim_conflicts.labels("grill_1", "grill_1-worker-1", "task_already_claimed").inc()
    metrics.completed_tasks.labels("grill_1", "grill_1-worker-1").inc()
    metrics.task_duration.labels("grill_1", "grill_1-worker-1").observe(8)

    rendered = metrics.render().decode()

    assert 'simulator_claim_attempts_total{station_id="grill_1",worker_id="grill_1-worker-1"} 1.0' in rendered
    assert 'simulator_claim_success_total{station_id="grill_1",worker_id="grill_1-worker-1"} 1.0' in rendered
    assert 'simulator_claim_conflicts_total{reason="task_already_claimed",station_id="grill_1",worker_id="grill_1-worker-1"} 1.0' in rendered
    assert 'simulator_completed_tasks_total{station_id="grill_1",worker_id="grill_1-worker-1"} 1.0' in rendered
    assert "simulator_task_duration_seconds_count" in rendered
