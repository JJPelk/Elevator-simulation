from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ArrivalWindow:
    """Defines a time window with per-floor passenger arrival rates."""

    start_s: int
    end_s: int
    up_rate_per_minute: List[float]
    down_rate_per_minute: List[float]

    def duration(self) -> int:
        return self.end_s - self.start_s


@dataclass
class PassengerArrivalConfig:
    """Configures the stochastic passenger arrival process."""

    windows: List[ArrivalWindow]
    events: List["ArrivalEvent"] = field(default_factory=list)

    @property
    def max_floor(self) -> int:
        return len(self.windows[0].up_rate_per_minute)


@dataclass
class ArrivalEvent:
    """Represents a scheduled burst of passengers."""

    time_s: int
    floor: int
    direction: int
    count: int
    destinations: Optional[List[int]] = None


@dataclass
class ElevatorConfig:
    capacity: int = 14
    seconds_per_floor: float = 2.5
    door_time_s: float = 4.0
    passenger_board_time_s: float = 1.2
    energy_per_floor: float = 1.0
    energy_per_stop: float = 0.5
    idle_floors: Optional[List[int]] = None


@dataclass
class SimulationConfig:
    num_floors: int
    num_elevators: int
    duration_s: int
    warmup_s: int = 0
    elevator: ElevatorConfig = field(default_factory=ElevatorConfig)
    arrivals: Optional[PassengerArrivalConfig] = None
    random_seed: Optional[int] = None

    def validate(self) -> None:
        if self.num_floors < 2:
            raise ValueError("Building must have at least two floors")
        if self.num_elevators < 1:
            raise ValueError("Simulation requires at least one elevator")
        if self.arrivals:
            for window in self.arrivals.windows:
                if len(window.up_rate_per_minute) != self.num_floors:
                    raise ValueError("Arrival window up rates must match num floors")
                if len(window.down_rate_per_minute) != self.num_floors:
                    raise ValueError("Arrival window down rates must match num floors")
            for event in self.arrivals.events:
                if not 0 <= event.floor < self.num_floors:
                    raise ValueError("Arrival event floor must be within building range")
                if event.direction not in (-1, 1):
                    raise ValueError("Arrival event direction must be -1 or 1")
                if event.destinations:
                    for dest in event.destinations:
                        if not 0 <= dest < self.num_floors:
                            raise ValueError("Arrival event destination out of range")
                        if dest == event.floor:
                            raise ValueError("Arrival event destination cannot equal origin floor")

    @classmethod
    def from_dict(cls, data: Dict) -> "SimulationConfig":
        elevator_cfg = data.get("elevator", {})
        arrivals_cfg = data.get("arrivals")

        if arrivals_cfg:
            windows = [
                ArrivalWindow(
                    start_s=window["start_s"],
                    end_s=window["end_s"],
                    up_rate_per_minute=window["up_rate_per_minute"],
                    down_rate_per_minute=window["down_rate_per_minute"],
                )
                for window in arrivals_cfg.get("windows", [])
            ]
            events = [
                ArrivalEvent(
                    time_s=event["time_s"],
                    floor=event["floor"],
                    direction=event.get("direction", 1),
                    count=event["count"],
                    destinations=event.get("destinations"),
                )
                for event in arrivals_cfg.get("events", [])
            ]
            arrivals = PassengerArrivalConfig(windows=windows, events=events)
        else:
            arrivals = None

        cfg = cls(
            num_floors=data["num_floors"],
            num_elevators=data["num_elevators"],
            duration_s=data["duration_s"],
            warmup_s=data.get("warmup_s", 0),
            elevator=ElevatorConfig(**elevator_cfg),
            arrivals=arrivals,
            random_seed=data.get("random_seed"),
        )
        cfg.validate()
        return cfg
