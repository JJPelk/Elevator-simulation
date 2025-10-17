#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from elevator_sim.config import SimulationConfig
from elevator_sim.metrics import MetricResult
from elevator_sim.passenger import Passenger
from elevator_sim.simulation import Simulation, build_strategy, export_results, run_batch


def load_config(path: Path) -> SimulationConfig:
    data = json.loads(path.read_text())
    config = SimulationConfig.from_dict(data)
    return config


def passenger_rows(strategy: str, run_index: int, passengers: Iterable[Passenger]):
    for passenger in passengers:
        if passenger.metadata.get("discard"):
            continue
        yield {
            "strategy": strategy,
            "run_index": run_index,
            "passenger_id": passenger.passenger_id,
            "origin": passenger.origin,
            "destination": passenger.destination,
            "request_time": passenger.request_time,
            "board_time": passenger.board_time,
            "exit_time": passenger.exit_time,
            "wait_time": passenger.wait_time,
            "travel_time": passenger.travel_time,
            "system_time": passenger.system_time,
            "assigned_elevator": passenger.assigned_elevator,
            "completed": passenger.completed(),
        }


def metric_row(strategy: str, run_index: int, metrics: MetricResult, total_energy: float) -> dict:
    return {
        "strategy": strategy,
        "run_index": run_index,
        "average_wait": metrics.average_wait,
        "median_wait": metrics.median_wait,
        "pct90_wait": metrics.pct90_wait,
        "average_travel": metrics.average_travel,
        "average_system": metrics.average_system,
        "gini_wait": metrics.gini_wait,
        "throughput": metrics.throughput,
        "total_passengers": metrics.total_passengers,
        "unfinished_passengers": metrics.unfinished_passengers,
        "total_energy": total_energy,
    }


def run_single(config: SimulationConfig, strategy_name: str) -> None:
    strategy = build_strategy(strategy_name, config)
    simulation = Simulation(config, strategy)
    result = simulation.run()
    print(json.dumps(result.to_dict(), indent=2))


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Run elevator simulation experiments")
    parser.add_argument("--config", type=Path, required=True, help="Path to simulation config JSON file")
    parser.add_argument(
        "--strategy",
        dest="strategies",
        action="append",
        default=[],
        help="Strategy name to evaluate (default: both)",
    )
    parser.add_argument("--runs-per-strategy", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--export-json", type=Path, help="Optional path to export results as JSON")
    args = parser.parse_args()

    config = load_config(args.config)
    strategies = args.strategies or ["collective_control", "destination_dispatch"]

    results = run_batch(config, strategies, runs_per_strategy=args.runs_per_strategy)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary.csv"
    passenger_path = args.output_dir / "passengers.csv"
    elevator_path = args.output_dir / "elevators.csv"

    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "strategy",
                "run_index",
                "average_wait",
                "median_wait",
                "pct90_wait",
                "average_travel",
                "average_system",
                "gini_wait",
                "throughput",
                "total_passengers",
                "unfinished_passengers",
                "total_energy",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(metric_row(result.strategy_name, result.run_index, result.metrics, result.total_energy))

    with passenger_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "strategy",
            "run_index",
            "passenger_id",
            "origin",
            "destination",
            "request_time",
            "board_time",
            "exit_time",
            "wait_time",
            "travel_time",
            "system_time",
            "assigned_elevator",
            "completed",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for row in passenger_rows(result.strategy_name, result.run_index, result.passengers):
                writer.writerow(row)

    with elevator_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = ["strategy", "run_index", "elevator_id", "distance_travelled", "stops", "energy", "passengers_moved"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for stats in result.elevator_stats:
                writer.writerow({
                    "strategy": result.strategy_name,
                    "run_index": result.run_index,
                    **stats,
                })

    if args.export_json:
        export_results(results, str(args.export_json))

    print(f"Wrote summary metrics to {summary_path}")
    print(f"Wrote passenger-level data to {passenger_path}")
    print(f"Wrote elevator telemetry to {elevator_path}")


if __name__ == "__main__":
    run_cli()
