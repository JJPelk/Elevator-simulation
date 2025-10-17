from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Passenger:
    passenger_id: int
    origin: int
    destination: int
    request_time: float
    direction: int
    assigned_elevator: Optional[int] = None
    board_time: Optional[float] = None
    exit_time: Optional[float] = None
    wait_time: Optional[float] = None
    travel_time: Optional[float] = None
    system_time: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def record_board(self, time: float) -> None:
        self.board_time = time
        self.wait_time = time - self.request_time

    def record_exit(self, time: float) -> None:
        self.exit_time = time
        if self.board_time is not None:
            self.travel_time = time - self.board_time
        if self.wait_time is not None:
            self.system_time = self.wait_time + (self.travel_time or 0.0)

    def completed(self) -> bool:
        return self.exit_time is not None

