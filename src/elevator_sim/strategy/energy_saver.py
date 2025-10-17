from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Deque, Dict, List, Sequence

from ..config import ElevatorConfig
from ..elevator import ElevatorState
from ..passenger import Passenger
from .base import Strategy


class EnergySaverStrategy(Strategy):
    """Batches passengers to reduce energy-intensive empty trips."""

    def __init__(self, elevator_cfg: ElevatorConfig, num_floors: int):
        super().__init__("energy_saver")
        self.elevator_cfg = elevator_cfg
        self.num_floors = num_floors
        self.waiting: Dict[int, Dict[int, Deque[Passenger]]] = defaultdict(
            lambda: {1: deque(), -1: deque()}
        )
        capacity = max(1, elevator_cfg.capacity)
        self.min_batch_size = max(2, math.ceil(capacity * 0.35))
        self.grouping_delay_s = 25.0
        self.max_wait_s = 90.0

    def on_passenger_arrival(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> None:
        queue = self._floor_queue(passenger.origin)[passenger.direction]
        queue.append(passenger)
        passenger.assigned_elevator = None

    def next_stop(self, elevator: ElevatorState, time_s: float) -> int | None:
        if elevator.pending_stops:
            return elevator.pending_stops.pop(0)

        candidate = self._select_candidate_floor(elevator, time_s)
        if candidate is None:
            return None
        elevator.direction = 1 if candidate > elevator.current_floor else -1
        return candidate

    def board_passengers(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> List[Passenger]:
        queues = self._floor_queue(floor)
        if not queues[1] and not queues[-1]:
            return []
        preferred = self._preferred_direction(elevator, queues)
        directions = [preferred]
        if preferred == 1:
            fallback = -1
        else:
            fallback = 1
        directions.append(fallback)

        boarded: List[Passenger] = []
        destinations_added: set[int] = set(elevator.pending_stops)
        for direction in directions:
            queue = queues[direction]
            for passenger in list(queue):
                if not elevator.has_capacity(self.elevator_cfg.capacity):
                    break
                passenger.record_board(time_s)
                passenger.assigned_elevator = elevator.elevator_id
                elevator.passengers.append(passenger)
                boarded.append(passenger)
                if passenger.destination not in destinations_added:
                    elevator.pending_stops.append(passenger.destination)
                    destinations_added.add(passenger.destination)
                queue.popleft()
            if not elevator.has_capacity(self.elevator_cfg.capacity):
                break

        return boarded

    def after_servicing_floor(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> None:
        queues = self._floor_queue(floor)
        for direction in (1, -1):
            queues[direction] = deque(p for p in queues[direction] if p.board_time is None)

    # Helper methods -----------------------------------------------------

    def _floor_queue(self, floor: int) -> Dict[int, Deque[Passenger]]:
        return self.waiting[floor]

    def _select_candidate_floor(
        self, elevator: ElevatorState, time_s: float
    ) -> int | None:
        best_floor = None
        best_score = 0.0
        for floor, directions in self.waiting.items():
            total_waiting = len(directions[1]) + len(directions[-1])
            if total_waiting == 0:
                continue
            oldest_wait = min(
                (time_s - passenger.request_time)
                for direction in (1, -1)
                for passenger in directions[direction]
            )
            ready = total_waiting >= self.min_batch_size or oldest_wait >= self.grouping_delay_s
            if not ready and oldest_wait < self.grouping_delay_s:
                continue
            urgency = oldest_wait / max(1.0, self.max_wait_s) + total_waiting / self.elevator_cfg.capacity
            distance_penalty = abs(floor - elevator.current_floor) / max(1.0, self.num_floors - 1)
            score = urgency - 0.3 * distance_penalty
            if oldest_wait >= self.max_wait_s:
                score += 1.0
            if score > best_score:
                best_score = score
                best_floor = floor
        return best_floor

    def _preferred_direction(
        self, elevator: ElevatorState, queues: Dict[int, Deque[Passenger]]
    ) -> int:
        if elevator.direction != 0 and queues[elevator.direction]:
            return elevator.direction
        up = len(queues[1])
        down = len(queues[-1])
        if up == down:
            return 1 if elevator.current_floor <= (self.num_floors - 1) / 2 else -1
        return 1 if up > down else -1
