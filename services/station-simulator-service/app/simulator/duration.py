from collections.abc import Callable
import random


RandomProvider = Callable[[float, float], float]


def calculate_simulated_duration(
    estimated_duration_seconds: int,
    speed_factor: float,
    min_factor: float,
    max_factor: float,
    random_provider: RandomProvider | None = None,
) -> float:
    if estimated_duration_seconds <= 0:
        msg = "estimated_duration_seconds must be greater than 0"
        raise ValueError(msg)
    if speed_factor <= 0:
        msg = "speed_factor must be greater than 0"
        raise ValueError(msg)
    if min_factor <= 0 or max_factor <= 0:
        msg = "duration factors must be greater than 0"
        raise ValueError(msg)
    if max_factor < min_factor:
        msg = "max_factor must be greater than or equal to min_factor"
        raise ValueError(msg)

    provider = random_provider or random.uniform
    factor = provider(min_factor, max_factor)
    return max(0.0, estimated_duration_seconds * factor / speed_factor)
