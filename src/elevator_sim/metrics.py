from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List

from .passenger import Passenger


@dataclass
class MetricResult:
    average_wait: float
    median_wait: float
    pct90_wait: float
    average_travel: float
    average_system: float
    gini_wait: float
    throughput: float
    total_passengers: int
    unfinished_passengers: int


def compute_metrics(passengers: Iterable[Passenger], duration_s: float) -> MetricResult:
    waits: List[float] = []
    travels: List[float] = []
    systems: List[float] = []
    finished = 0
    unfinished = 0

    for passenger in passengers:
        if passenger.completed():
            finished += 1
            if passenger.wait_time is not None:
                waits.append(passenger.wait_time)
            if passenger.travel_time is not None:
                travels.append(passenger.travel_time)
            if passenger.system_time is not None:
                systems.append(passenger.system_time)
        else:
            unfinished += 1

    waits.sort()
    travels.sort()
    systems.sort()

    return MetricResult(
        average_wait=_mean(waits),
        median_wait=_percentile(waits, 50),
        pct90_wait=_percentile(waits, 90),
        average_travel=_mean(travels),
        average_system=_mean(systems),
        gini_wait=_gini(waits),
        throughput=finished / duration_s if duration_s else 0.0,
        total_passengers=finished,
        unfinished_passengers=unfinished,
    )


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if percentile <= 0:
        return values[0]
    if percentile >= 100:
        return values[-1]
    k = (len(values) - 1) * percentile / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return d0 + d1


def _gini(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = 0.0
    weighted_sum = 0.0
    for i, value in enumerate(sorted_vals, start=1):
        cumulative += value
        weighted_sum += cumulative
    mean = cumulative / n
    if mean == 0:
        return 0.0
    return (n + 1 - 2 * weighted_sum / cumulative) / n

