from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Sequence

from ..config import ElevatorConfig
from ..elevator import ElevatorState
from ..passenger import Passenger
from .base import Strategy


class ZonedDispatchStrategy(Strategy):
    """Dispatch strategy that dedicates elevators to building zones with overflow sharing."""

    def __init__(self, elevator_cfg: ElevatorConfig, num_floors: int, num_elevators: int):
        super().__init__("zoned_dispatch")
        self.elevator_cfg = elevator_cfg
        self.num_floors = num_floors
        self.num_elevators = num_elevators
        self.zone_bounds = self._build_zones(num_floors, num_elevators)
        self.waiting: Dict[int, Dict[int, Dict[int, Deque[Passenger]]]] = defaultdict(
            lambda: defaultdict(lambda: {1: deque(), -1: deque()})
        )
        self.reassignment_threshold_s = 60.0

    def on_passenger_arrival(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> None:
        elevator_id = self._zone_for_floor(passenger.origin)
        elevator = elevators[elevator_id % len(elevators)]
        passenger.assigned_elevator = elevator.elevator_id
        queue = self._floor_queue(elevator.elevator_id, passenger.origin)[passenger.direction]
        queue.append(passenger)
        if passenger.origin not in elevator.pending_stops:
            elevator.add_stop(passenger.origin)

    def next_stop(self, elevator: ElevatorState, time_s: float) -> int | None:
        if elevator.pending_stops:
            return self._pop_next_stop(elevator)

        # Look for requests inside the elevator's zone
        zone_floor = self._nearest_waiting_floor(elevator.elevator_id, elevator.current_floor)
        if zone_floor is not None:
            elevator.direction = 1 if zone_floor > elevator.current_floor else -1
            return zone_floor

        # Assist other zones if a request has waited long enough
        reassigned = self._reassign_overflow_request(elevator, time_s)
        if reassigned is not None:
            elevator.direction = 1 if reassigned > elevator.current_floor else -1
            return reassigned

        return None

    def board_passengers(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> List[Passenger]:
        queues = self._floor_queue(elevator.elevator_id, floor)
        directions = self._direction_order(elevator, queues)
        boarded: List[Passenger] = []
        for direction in directions:
            queue = queues[direction]
            take: List[Passenger] = []
            for passenger in list(queue):
                if not elevator.has_capacity(self.elevator_cfg.capacity):
                    break
                passenger.record_board(time_s)
                passenger.assigned_elevator = elevator.elevator_id
                elevator.passengers.append(passenger)
                elevator.add_stop(passenger.destination)
                boarded.append(passenger)
                take.append(passenger)
            for passenger in take:
                queue.popleft()
        return boarded

    def after_servicing_floor(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> None:
        queues = self._floor_queue(elevator.elevator_id, floor)
        for direction in (1, -1):
            queue = queues[direction]
            queues[direction] = deque(p for p in queue if p.board_time is None)

    # Helper methods -----------------------------------------------------

    def _build_zones(self, num_floors: int, num_elevators: int) -> List[range]:
        zone_size = math.ceil(num_floors / num_elevators)
        zones: List[range] = []
        start = 0
        for elevator_id in range(num_elevators):
            end = min(num_floors, start + zone_size)
            if elevator_id == num_elevators - 1:
                end = num_floors
            zones.append(range(start, end))
            start = end
        return zones

    def _zone_for_floor(self, floor: int) -> int:
        for idx, zone in enumerate(self.zone_bounds):
            if floor in zone:
                return idx
        return min(self.num_elevators - 1, max(0, floor))

    def _floor_queue(self, elevator_id: int, floor: int) -> Dict[int, Deque[Passenger]]:
        floor_map = self.waiting[elevator_id]
        if floor not in floor_map:
            floor_map[floor] = {1: deque(), -1: deque()}
        return floor_map[floor]

    def _nearest_waiting_floor(self, elevator_id: int, current_floor: float) -> int | None:
        best_floor: int | None = None
        best_distance = float("inf")
        for floor, directions in self.waiting[elevator_id].items():
            if directions[1] or directions[-1]:
                distance = abs(floor - current_floor)
                if distance < best_distance:
                    best_floor = floor
                    best_distance = distance
        return best_floor

    def _direction_order(
        self, elevator: ElevatorState, queues: Dict[int, Deque[Passenger]]
    ) -> Sequence[int]:
        if elevator.direction > 0:
            return (1, -1)
        if elevator.direction < 0:
            return (-1, 1)
        return (1, -1) if len(queues[1]) >= len(queues[-1]) else (-1, 1)

    def _reassign_overflow_request(
        self, elevator: ElevatorState, time_s: float
    ) -> Optional[int]:
        for other_id, floor_map in self.waiting.items():
            if other_id == elevator.elevator_id:
                continue
            for floor, directions in floor_map.items():
                for direction in (1, -1):
                    queue = directions[direction]
                    if not queue:
                        continue
                    passenger = queue[0]
                    if time_s - passenger.request_time >= self.reassignment_threshold_s:
                        queue.popleft()
                        passenger.assigned_elevator = elevator.elevator_id
                        self._floor_queue(elevator.elevator_id, passenger.origin)[
                            passenger.direction
                        ].appendleft(passenger)
                        if passenger.origin in elevator.pending_stops:
                            elevator.pending_stops.remove(passenger.origin)
                        elevator.pending_stops.insert(0, passenger.origin)
                        return passenger.origin
        return None

    def _pop_next_stop(self, elevator: ElevatorState) -> int | None:
        if not elevator.pending_stops:
            return None
        return elevator.pending_stops.pop(0)
