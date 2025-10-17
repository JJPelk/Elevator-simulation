from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence

from ..config import ElevatorConfig
from ..elevator import ElevatorMode, ElevatorState
from ..passenger import Passenger
from .base import Strategy


class CollectiveControlStrategy(Strategy):
    """Classic collective control with nearest car assignment."""

    def __init__(self, elevator_cfg: ElevatorConfig, num_floors: int):
        super().__init__("collective_control")
        self.elevator_cfg = elevator_cfg
        self.num_floors = num_floors
        self.waiting: Dict[int, Dict[int, List[Passenger]]] = defaultdict(
            lambda: {1: [], -1: []}
        )

    def on_passenger_arrival(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> None:
        best_elevator = self._choose_elevator(elevators, passenger)
        passenger.assigned_elevator = best_elevator.elevator_id if best_elevator else None
        self.waiting[passenger.origin][passenger.direction].append(passenger)
        if best_elevator and passenger.origin not in best_elevator.pending_stops:
            best_elevator.add_stop(passenger.origin)

    def next_stop(self, elevator: ElevatorState, time_s: float) -> int | None:
        if elevator.pending_stops:
            if elevator.direction > 0:
                upwards = [f for f in elevator.pending_stops if f >= elevator.current_floor]
                if upwards:
                    target = min(upwards)
                else:
                    target = max(elevator.pending_stops)
            elif elevator.direction < 0:
                downwards = [f for f in elevator.pending_stops if f <= elevator.current_floor]
                if downwards:
                    target = max(downwards)
                else:
                    target = min(elevator.pending_stops)
            else:
                target = min(elevator.pending_stops, key=lambda f: abs(elevator.current_floor - f))
            elevator.pending_stops.remove(target)
            return target
        # If idle, look for nearest waiting passenger
        nearest_floor = self._nearest_waiting_floor(elevator.current_floor)
        if nearest_floor is not None:
            elevator.direction = 1 if nearest_floor > elevator.current_floor else -1
            return nearest_floor
        return None

    def after_servicing_floor(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> None:
        # Remove passengers that have boarded from waiting list
        for direction in (1, -1):
            queue = self.waiting[floor][direction]
            remaining: List[Passenger] = []
            for passenger in queue:
                if passenger.board_time is None:
                    remaining.append(passenger)
            self.waiting[floor][direction] = remaining

    def board_passengers(self, elevator: ElevatorState, floor: int, time_s: float) -> List[Passenger]:
        boarded: List[Passenger] = []
        if elevator.direction > 0:
            directions = (1, -1)
        elif elevator.direction < 0:
            directions = (-1, 1)
        else:
            # Idle elevators take the largest queue first
            queues = self.waiting[floor]
            directions = tuple(
                sorted(queues.keys(), key=lambda d: len(queues[d]), reverse=True)
            ) or (1, -1)

        for direction in directions:
            queue = self.waiting[floor][direction]
            take: List[Passenger] = []
            for passenger in queue:
                if not elevator.has_capacity(self.elevator_cfg.capacity):
                    break
                # allow boarding if assigned to this elevator or elevator idle
                if passenger.assigned_elevator is None or passenger.assigned_elevator == elevator.elevator_id:
                    passenger.record_board(time_s)
                    take.append(passenger)
                    elevator.add_stop(passenger.destination)
                    boarded.append(passenger)
            for passenger in take:
                queue.remove(passenger)
                elevator.passengers.append(passenger)
                passenger.assigned_elevator = elevator.elevator_id
        return boarded

    def _choose_elevator(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> ElevatorState | None:
        best_elevator = None
        best_score = float("inf")
        for elevator in elevators:
            score = self._estimate_arrival_time(elevator, passenger)
            if score < best_score:
                best_score = score
                best_elevator = elevator
        return best_elevator

    def _estimate_arrival_time(
        self, elevator: ElevatorState, passenger: Passenger
    ) -> float:
        distance = abs(elevator.current_floor - passenger.origin)
        queue_penalty = len(elevator.pending_stops) * self.elevator_cfg.door_time_s
        if elevator.mode == ElevatorMode.MOVING and elevator.target_floor is not None:
            distance += abs(elevator.target_floor - elevator.current_floor)
        return distance + queue_penalty

    def _nearest_waiting_floor(self, current_floor: float) -> int | None:
        best_floor = None
        best_distance = float("inf")
        for floor, directions in self.waiting.items():
            if directions[1] or directions[-1]:
                distance = abs(floor - current_floor)
                if distance < best_distance:
                    best_floor = floor
                    best_distance = distance
        return best_floor

