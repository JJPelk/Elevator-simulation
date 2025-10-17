from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .passenger import Passenger


class ElevatorMode(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    BOARDING = "boarding"


@dataclass
class ElevatorState:
    elevator_id: int
    current_floor: float
    target_floor: Optional[int] = None
    direction: int = 0
    mode: ElevatorMode = ElevatorMode.IDLE
    time_to_next_action: float = 0.0
    passengers: List[Passenger] = field(default_factory=list)
    pending_stops: List[int] = field(default_factory=list)
    total_distance: float = 0.0
    total_stops: int = 0
    total_energy: float = 0.0

    def is_idle(self) -> bool:
        return self.mode == ElevatorMode.IDLE and not self.pending_stops and self.target_floor is None

    def add_stop(self, floor: int) -> None:
        if floor not in self.pending_stops:
            self.pending_stops.append(floor)

    def remove_stop(self, floor: int) -> None:
        self.pending_stops = [f for f in self.pending_stops if f != floor]

    def has_capacity(self, capacity: int) -> bool:
        return len(self.passengers) < capacity

    def occupants(self) -> int:
        return len(self.passengers)

