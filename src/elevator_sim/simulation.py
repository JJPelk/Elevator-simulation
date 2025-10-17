from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .arrivals import PassengerArrivalProcess
from .config import ArrivalWindow, ElevatorConfig, PassengerArrivalConfig, SimulationConfig
from .elevator import ElevatorMode, ElevatorState
from .metrics import MetricResult, compute_metrics
from .passenger import Passenger
from .strategy.base import Strategy
from .strategy.collective import CollectiveControlStrategy
from .strategy.destination_dispatch import DestinationDispatchStrategy


@dataclass
class SimulationResult:
    strategy_name: str
    config: SimulationConfig
    passengers: List[Passenger]
    metrics: MetricResult
    elevator_stats: List[Dict[str, float]]
    total_energy: float
    run_index: int = 0

    def to_dict(self) -> Dict:
        return {
            "strategy": self.strategy_name,
            "metrics": self.metrics.__dict__,
            "total_energy": self.total_energy,
            "elevators": self.elevator_stats,
            "config": {
                "num_floors": self.config.num_floors,
                "num_elevators": self.config.num_elevators,
                "duration_s": self.config.duration_s,
                "warmup_s": self.config.warmup_s,
            },
        }


StrategyFactory = Callable[[SimulationConfig], Strategy]


def build_strategy(name: str, config: SimulationConfig) -> Strategy:
    elevator_cfg = config.elevator
    if name == "collective_control":
        return CollectiveControlStrategy(elevator_cfg, config.num_floors)
    if name == "destination_dispatch":
        return DestinationDispatchStrategy(elevator_cfg, config.num_floors)
    raise ValueError(f"Unknown strategy: {name}")


@dataclass
class Simulation:
    config: SimulationConfig
    strategy: Strategy
    dt: float = 1.0
    random_state: random.Random = field(init=False)
    passengers: List[Passenger] = field(default_factory=list)
    elevators: List[ElevatorState] = field(default_factory=list)
    arrival_process: Optional[PassengerArrivalProcess] = None
    _next_passenger_id: int = 0
    run_index: int = 0

    def __post_init__(self) -> None:
        seed = self.config.random_seed or random.randint(1, 10**6)
        self.random_state = random.Random(seed)
        self._initialise_elevators()
        self._initialise_arrival_process()

    def run(self) -> SimulationResult:
        duration = self.config.duration_s
        for tick in range(int(duration)):
            current_time = tick * self.dt
            self._process_passenger_arrivals(current_time)
            self.strategy.on_tick(self.elevators, current_time)
            for elevator in self.elevators:
                self._update_elevator(elevator, current_time)

        metrics = compute_metrics(self._passengers_post_warmup(), duration - self.config.warmup_s)
        elevator_stats = [
            {
                "elevator_id": elevator.elevator_id,
                "distance_travelled": elevator.total_distance,
                "stops": elevator.total_stops,
                "energy": elevator.total_energy,
                "passengers_moved": len(
                    [p for p in self.passengers if p.assigned_elevator == elevator.elevator_id]
                ),
            }
            for elevator in self.elevators
        ]
        total_energy = sum(elevator.total_energy for elevator in self.elevators)
        return SimulationResult(
            strategy_name=self.strategy.name,
            config=self.config,
            passengers=list(self.passengers),
            metrics=metrics,
            elevator_stats=elevator_stats,
            total_energy=total_energy,
            run_index=self.run_index,
        )

    def _initialise_elevators(self) -> None:
        self.elevators = []
        idle_floors = self.config.elevator.idle_floors or [0]
        for elevator_id in range(self.config.num_elevators):
            floor = idle_floors[elevator_id % len(idle_floors)]
            self.elevators.append(ElevatorState(elevator_id=elevator_id, current_floor=float(floor)))

    def _initialise_arrival_process(self) -> None:
        if self.config.arrivals:
            self.arrival_process = PassengerArrivalProcess(
                config=self.config.arrivals,
                random_state=self.random_state,
            )
        else:
            windows = [
                ArrivalWindow(
                    start_s=0,
                    end_s=self.config.duration_s,
                    up_rate_per_minute=[0.5] * self.config.num_floors,
                    down_rate_per_minute=[0.5] * self.config.num_floors,
                )
            ]
            passenger_config = PassengerArrivalConfig(windows=windows)
            self.arrival_process = PassengerArrivalProcess(passenger_config, self.random_state)

    def _process_passenger_arrivals(self, current_time: float) -> None:
        if not self.arrival_process:
            return
        new_passengers = list(self.arrival_process.generate(int(current_time)))
        for passenger in new_passengers:
            if passenger.destination == passenger.origin:
                continue
            passenger.passenger_id = self._next_passenger_id
            self._next_passenger_id += 1
            if current_time < self.config.warmup_s:
                passenger.metadata["discard"] = True
            self.passengers.append(passenger)
            self.strategy.on_passenger_arrival(self.elevators, passenger)

    def _update_elevator(self, elevator: ElevatorState, current_time: float) -> None:
        if elevator.time_to_next_action > 0:
            elevator.time_to_next_action -= self.dt
            if elevator.time_to_next_action > 0:
                return

        if elevator.mode == ElevatorMode.MOVING and elevator.target_floor is not None:
            elevator.current_floor = float(elevator.target_floor)
            elevator.mode = ElevatorMode.BOARDING
            stop_time = self._handle_floor_stop(elevator, int(elevator.current_floor), current_time)
            elevator.time_to_next_action = stop_time
            elevator.total_stops += 1
            elevator.total_energy += self.config.elevator.energy_per_stop
            return

        if elevator.mode == ElevatorMode.BOARDING:
            self.strategy.after_servicing_floor(elevator, int(round(elevator.current_floor)), current_time)
            next_target = self.strategy.next_stop(elevator, current_time)
            if next_target is not None:
                self._dispatch_to_floor(elevator, next_target, current_time)
            else:
                self._move_to_idle_floor(elevator, current_time)
            return

        if elevator.mode == ElevatorMode.IDLE:
            next_target = self.strategy.next_stop(elevator, current_time)
            if next_target is not None:
                self._dispatch_to_floor(elevator, next_target, current_time)
                return
            self._move_to_idle_floor(elevator, current_time)

    def _dispatch_to_floor(
        self, elevator: ElevatorState, target_floor: int, current_time: float
    ) -> None:
        if target_floor == int(round(elevator.current_floor)):
            elevator.mode = ElevatorMode.BOARDING
            elevator.target_floor = target_floor
            stop_time = self._handle_floor_stop(elevator, target_floor, current_time)
            elevator.time_to_next_action = stop_time
            elevator.total_stops += 1
            elevator.total_energy += self.config.elevator.energy_per_stop
            return
        distance = abs(target_floor - elevator.current_floor)
        travel_time = distance * self.config.elevator.seconds_per_floor
        elevator.time_to_next_action = travel_time
        elevator.mode = ElevatorMode.MOVING
        elevator.target_floor = target_floor
        elevator.direction = 1 if target_floor > elevator.current_floor else -1
        elevator.total_distance += distance
        elevator.total_energy += distance * self.config.elevator.energy_per_floor

    def _move_to_idle_floor(self, elevator: ElevatorState, current_time: float) -> None:
        idle_floors = self.config.elevator.idle_floors
        if not idle_floors:
            elevator.mode = ElevatorMode.IDLE
            elevator.target_floor = None
            elevator.direction = 0
            return
        preferred_floor = idle_floors[elevator.elevator_id % len(idle_floors)]
        if int(round(elevator.current_floor)) == preferred_floor:
            elevator.mode = ElevatorMode.IDLE
            elevator.target_floor = None
            elevator.direction = 0
            return
        self._dispatch_to_floor(elevator, preferred_floor, current_time)

    def _handle_floor_stop(
        self, elevator: ElevatorState, floor: int, current_time: float
    ) -> float:
        disembarked: List[Passenger] = []
        remaining_passengers: List[Passenger] = []
        for passenger in elevator.passengers:
            if passenger.destination == floor:
                passenger.record_exit(current_time)
                disembarked.append(passenger)
            else:
                remaining_passengers.append(passenger)
        elevator.passengers = remaining_passengers

        boarded = self.strategy.board_passengers(elevator, floor, current_time)
        total_people = len(disembarked) + len(boarded)
        stop_time = self.config.elevator.door_time_s + total_people * self.config.elevator.passenger_board_time_s
        return stop_time

    def _passengers_post_warmup(self) -> Iterable[Passenger]:
        warmup = self.config.warmup_s
        if warmup <= 0:
            return [p for p in self.passengers if not p.metadata.get("discard")] 
        return [
            p
            for p in self.passengers
            if p.request_time >= warmup and not p.metadata.get("discard")
        ]


def run_batch(
    config: SimulationConfig,
    strategies: Sequence[str],
    runs_per_strategy: int = 3,
) -> List[SimulationResult]:
    results: List[SimulationResult] = []
    for strategy_name in strategies:
        for run in range(runs_per_strategy):
            config_copy = SimulationConfig(
                num_floors=config.num_floors,
                num_elevators=config.num_elevators,
                duration_s=config.duration_s,
                warmup_s=config.warmup_s,
                elevator=config.elevator,
                arrivals=config.arrivals,
                random_seed=(config.random_seed or 0) + run * 997 + hash(strategy_name) % 997,
            )
            strategy = build_strategy(strategy_name, config_copy)
            simulation = Simulation(config_copy, strategy)
            simulation.run_index = run
            result = simulation.run()
            results.append(result)
    return results


def export_results(results: Sequence[SimulationResult], path: str) -> None:
    serialised = [result.to_dict() for result in results]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialised, fh, indent=2)

