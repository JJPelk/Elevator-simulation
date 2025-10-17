from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Sequence

from ..config import ElevatorConfig
from ..elevator import ElevatorState
from ..passenger import Passenger
from .base import Strategy


class DestinationDispatchStrategy(Strategy):
    """Destination dispatch that groups passengers by similar destinations."""

    def __init__(self, elevator_cfg: ElevatorConfig, num_floors: int, grouping_window_s: int = 30):
        super().__init__("destination_dispatch")
        self.elevator_cfg = elevator_cfg
        self.num_floors = num_floors
        self.grouping_window_s = grouping_window_s
        self.waiting: Dict[int, Dict[int, Deque[Passenger]]] = defaultdict(
            lambda: defaultdict(deque)
        )
        self.last_group_time: Dict[int, float] = defaultdict(float)

    def on_passenger_arrival(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> None:
        queue = self.waiting[passenger.origin][passenger.destination]
        queue.append(passenger)
        passenger.assigned_elevator = None

    def next_stop(self, elevator: ElevatorState, time_s: float) -> int | None:
        if elevator.pending_stops:
            next_floor = elevator.pending_stops.pop(0)
            return next_floor

        # Idle elevator: choose origin floor with most queued passengers or waiting too long
        best_floor = None
        best_score = -1
        for floor, destination_map in self.waiting.items():
            total_waiting = sum(len(queue) for queue in destination_map.values())
            if total_waiting == 0:
                continue
            time_since_last = time_s - self.last_group_time.get(floor, 0.0)
            score = total_waiting + time_since_last / self.grouping_window_s
            if score > best_score:
                best_score = score
                best_floor = floor
        if best_floor is None:
            return None

        group = self._form_group(best_floor, time_s)
        if not group:
            return None

        # Send elevator to pick up the group then deliver destinations
        pickup_floor = best_floor
        elevator.pending_stops.extend([pickup_floor] + group)
        return elevator.pending_stops.pop(0)

    def after_servicing_floor(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> None:
        # Remove passengers that have boarded from their queues
        for destination in list(self.waiting[floor].keys()):
            queue = self.waiting[floor][destination]
            self.waiting[floor][destination] = deque(
                passenger for passenger in queue if passenger.board_time is None
            )
            if not self.waiting[floor][destination]:
                del self.waiting[floor][destination]

    def board_passengers(self, elevator: ElevatorState, floor: int, time_s: float) -> List[Passenger]:
        boarded: List[Passenger] = []
        if elevator.pending_stops:
            # Determine destinations scheduled immediately after pickup
            destinations = [
                stop for stop in elevator.pending_stops if stop != floor
            ]
        else:
            destinations = []
        # Board passengers destined for upcoming stops
        scheduled_destinations = destinations or [passenger.destination for passenger in elevator.passengers]
        for destination in list(self.waiting[floor].keys()):
            if destination not in scheduled_destinations and scheduled_destinations:
                continue
            queue = self.waiting[floor][destination]
            while queue and elevator.has_capacity(self.elevator_cfg.capacity):
                passenger = queue.popleft()
                passenger.record_board(time_s)
                passenger.assigned_elevator = elevator.elevator_id
                elevator.passengers.append(passenger)
                boarded.append(passenger)
                if destination not in elevator.pending_stops:
                    elevator.pending_stops.append(destination)
            if not queue:
                del self.waiting[floor][destination]
        return boarded

    def _form_group(self, floor: int, time_s: float) -> List[int]:
        destination_map = self.waiting[floor]
        if not destination_map:
            return []
        # Choose destination with most passengers first
        sorted_destinations = sorted(
            destination_map.items(), key=lambda item: len(item[1]), reverse=True
        )
        group: List[int] = []
        seats_remaining = self.elevator_cfg.capacity
        for destination, queue in sorted_destinations:
            if seats_remaining == 0:
                break
            take = min(len(queue), seats_remaining)
            seats_remaining -= take
            if take > 0:
                group.append(destination)
        self.last_group_time[floor] = time_s
        return group

