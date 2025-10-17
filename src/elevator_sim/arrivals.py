from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Sequence

from .config import ArrivalEvent, PassengerArrivalConfig
from .passenger import Passenger


@dataclass
class PassengerArrivalProcess:
    """Generates passengers according to time-varying Poisson processes."""

    config: PassengerArrivalConfig
    random_state: random.Random
    _events_by_time: Dict[int, List[ArrivalEvent]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        events: Dict[int, List[ArrivalEvent]] = {}
        for event in self.config.events:
            events.setdefault(event.time_s, []).append(event)
        self._events_by_time = events

    def generate(self, current_time: int) -> Iterator[Passenger]:
        window = self._window_for_time(current_time)
        if window is None:
            return iter(())

        passengers: List[Passenger] = []
        for floor, (up_rate, down_rate) in enumerate(
            zip(window.up_rate_per_minute, window.down_rate_per_minute)
        ):
            passengers.extend(
                self._spawn_passengers(
                    current_time,
                    floor,
                    direction=1,
                    rate_per_minute=up_rate,
                    valid_destinations=range(floor + 1, len(window.up_rate_per_minute)),
                )
            )
            passengers.extend(
                self._spawn_passengers(
                    current_time,
                    floor,
                    direction=-1,
                    rate_per_minute=down_rate,
                    valid_destinations=range(0, floor),
                )
            )
        if current_time in self._events_by_time:
            for event in self._events_by_time[current_time]:
                passengers.extend(self._spawn_event_passengers(current_time, event))
        return iter(passengers)

    def _spawn_passengers(
        self,
        current_time: int,
        floor: int,
        direction: int,
        rate_per_minute: float,
        valid_destinations: Sequence[int],
    ) -> List[Passenger]:
        if rate_per_minute <= 0 or not valid_destinations:
            return []
        prob = rate_per_minute / 60.0
        draws = self.random_state.random()
        count = self._poisson(prob, draws)
        passengers: List[Passenger] = []
        for _ in range(count):
            dest = self.random_state.choice(list(valid_destinations))
            passengers.append(
                Passenger(
                    passenger_id=-1,  # replaced by simulation when registered
                    origin=floor,
                    destination=dest,
                    request_time=float(current_time),
                    direction=direction,
                )
            )
        return passengers

    def _spawn_event_passengers(
        self, current_time: int, event: ArrivalEvent
    ) -> List[Passenger]:
        valid_destinations: Sequence[int]
        if event.direction == 1:
            valid_destinations = range(event.floor + 1, self.config.max_floor)
        else:
            valid_destinations = range(0, event.floor)
        destinations = event.destinations or list(valid_destinations)
        if not destinations:
            return []
        passengers: List[Passenger] = []
        for _ in range(event.count):
            dest = self.random_state.choice(destinations)
            passengers.append(
                Passenger(
                    passenger_id=-1,
                    origin=event.floor,
                    destination=dest,
                    request_time=float(current_time),
                    direction=event.direction,
                    metadata={"event": True},
                )
            )
        return passengers

    def _poisson(self, lambda_per_step: float, draw: float) -> int:
        if lambda_per_step <= 0:
            return 0
        # For small rates and short steps, approximate via Bernoulli
        if lambda_per_step < 0.1:
            return 1 if draw < lambda_per_step else 0
        # Otherwise use inverse transform
        L = math.exp(-lambda_per_step)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= self.random_state.random()
        return k - 1

    def _window_for_time(self, current_time: int):
        for window in self.config.windows:
            if window.start_s <= current_time < window.end_s:
                return window
        return None

