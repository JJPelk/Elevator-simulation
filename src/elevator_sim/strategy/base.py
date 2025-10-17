from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Sequence

from ..elevator import ElevatorState
from ..passenger import Passenger


class Strategy(ABC):
    """Defines the interface shared by all dispatch strategies."""

    name: str

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def on_passenger_arrival(
        self, elevators: Sequence[ElevatorState], passenger: Passenger
    ) -> None:
        """Notified when a passenger arrives and joins a queue."""

    @abstractmethod
    def next_stop(self, elevator: ElevatorState, time_s: float) -> int | None:
        """Determines the next stop for an elevator when it becomes idle."""

    @abstractmethod
    def board_passengers(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> List[Passenger]:
        """Selects which passengers board when the elevator opens at a floor."""

    @abstractmethod
    def after_servicing_floor(
        self, elevator: ElevatorState, floor: int, time_s: float
    ) -> None:
        """Allows strategy to update state when an elevator completes a stop."""

    def on_tick(self, elevators: Sequence[ElevatorState], time_s: float) -> None:
        """Optional hook executed each simulation tick."""
        return None

    def assign_bulk(
        self, elevators: Sequence[ElevatorState], passengers: Iterable[Passenger]
    ) -> None:
        for passenger in passengers:
            self.on_passenger_arrival(elevators, passenger)

