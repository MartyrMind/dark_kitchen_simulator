import pytest

from app.simulator.duration import calculate_simulated_duration


def test_duration_uses_estimate_factor_and_speed():
    duration = calculate_simulated_duration(
        estimated_duration_seconds=480,
        speed_factor=60,
        min_factor=0.7,
        max_factor=1.4,
        random_provider=lambda _min, _max: 1.0,
    )

    assert duration == 8


def test_duration_applies_random_factor():
    duration = calculate_simulated_duration(100, 10, 0.7, 1.4, random_provider=lambda _min, _max: 1.4)

    assert duration == 14


@pytest.mark.parametrize(
    "kwargs",
    [
        {"estimated_duration_seconds": 0, "speed_factor": 60, "min_factor": 0.7, "max_factor": 1.4},
        {"estimated_duration_seconds": 10, "speed_factor": 0, "min_factor": 0.7, "max_factor": 1.4},
        {"estimated_duration_seconds": 10, "speed_factor": 60, "min_factor": 0, "max_factor": 1.4},
        {"estimated_duration_seconds": 10, "speed_factor": 60, "min_factor": 1.5, "max_factor": 1.4},
    ],
)
def test_invalid_duration_config_raises(kwargs):
    with pytest.raises(ValueError):
        calculate_simulated_duration(**kwargs)
