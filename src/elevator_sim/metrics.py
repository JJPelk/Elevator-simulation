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
    max_wait: float
    std_wait: float
    average_travel: float
    median_travel: float
    std_travel: float
    average_system: float
    gini_wait: float
    throughput: float
    total_passengers: int
    unfinished_passengers: int
    completion_ratio: float
    energy_per_passenger: float
    distance_per_passenger: float
    average_occupancy: float
    idle_fraction: float
    moving_fraction: float
    boarding_fraction: float
    empty_trip_fraction: float


def compute_metrics(
    passengers: Iterable[Passenger],
    duration_s: float,
    operational_totals: Dict[str, float] | None = None,
) -> MetricResult:
    totals = operational_totals or {}
    total_energy = totals.get("total_energy", 0.0)
    total_distance = totals.get("total_distance", 0.0)
    occupancy_time = totals.get("occupancy_time", 0.0)
    idle_time = totals.get("idle_time", 0.0)
    moving_time = totals.get("moving_time", 0.0)
    boarding_time = totals.get("boarding_time", 0.0)
    empty_distance = totals.get("empty_distance", 0.0)
    num_elevators = max(1, int(totals.get("num_elevators", 1)))

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
        max_wait=max(waits) if waits else 0.0,
        std_wait=_stddev(waits),
        average_travel=_mean(travels),
        median_travel=_percentile(travels, 50),
        std_travel=_stddev(travels),
        average_system=_mean(systems),
        gini_wait=_gini(waits),
        throughput=finished / duration_s if duration_s else 0.0,
        total_passengers=finished,
        unfinished_passengers=unfinished,
        completion_ratio=
            finished / (finished + unfinished) if (finished + unfinished) else 0.0,
        energy_per_passenger=total_energy / finished if finished else 0.0,
        distance_per_passenger=total_distance / finished if finished else 0.0,
        average_occupancy=
            occupancy_time / (duration_s * num_elevators) if duration_s else 0.0,
        idle_fraction=idle_time / (duration_s * num_elevators) if duration_s else 0.0,
        moving_fraction=moving_time / (duration_s * num_elevators) if duration_s else 0.0,
        boarding_fraction=boarding_time / (duration_s * num_elevators) if duration_s else 0.0,
        empty_trip_fraction=
            empty_distance / total_distance if total_distance else 0.0,
    )


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: List[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


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

