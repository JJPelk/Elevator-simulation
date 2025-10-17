# Elevator Simulation Platform

This repository contains a configurable elevator simulation engine designed to generate rich datasets for analysing competing dispatch strategies. It supports multiple elevator control policies, flexible passenger arrival schedules, per-elevator telemetry, and summary statistics that can be fed directly into a technical report.

## Key Features

- **Discrete-time simulation core** with per-second resolution, configurable elevator dynamics, and stochastic passenger arrivals.
- **Two dispatch strategies** ready for comparison:
  - `collective_control`: a nearest-car collective control algorithm that serves hall calls while respecting travel direction.
  - `destination_dispatch`: a destination-grouping controller that forms elevator assignments based on passenger destinations.
- **Comprehensive metrics** including averages and percentiles for wait/travel times, throughput, fairness (Gini coefficient), and energy consumption estimates.
- **Passenger-level datasets** capturing request, boarding, and exit times for every simulated rider.
- **Batch experimentation CLI** to run multiple scenarios, export CSV summaries, and serialise complete results to JSON.
- **Extensible architecture** that allows new strategies or arrival profiles to be plugged in via Python.

## Project Layout

```
├── configs/                   # Example simulation configurations
│   └── highrise_commuter.json
├── scripts/
│   └── run_simulation.py      # Command-line entry point
├── src/elevator_sim/
│   ├── arrivals.py            # Passenger arrival processes
│   ├── config.py              # Dataclasses for core configuration
│   ├── elevator.py            # Elevator state tracking helpers
│   ├── metrics.py             # Aggregation utilities
│   ├── passenger.py           # Passenger lifecycle data
│   ├── simulation.py          # Simulation engine and batch runner
│   └── strategy/              # Dispatch strategy implementations
│       ├── base.py
│       ├── collective.py
│       └── destination_dispatch.py
└── tests/                     # Unit and integration tests
```

## Installation

The project targets Python 3.10 or newer. Create a virtual environment and install the package in editable mode if you plan to extend it:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

For development extras (e.g., pytest) install the `dev` optional dependency:

```bash
pip install -e .[dev]
```

## Running Simulations

Use the CLI to execute batch experiments. The command below runs both bundled strategies against the `highrise_commuter` scenario, repeating each three times and writing CSV outputs into `results/`:

```bash
python scripts/run_simulation.py --config configs/highrise_commuter.json --runs-per-strategy 3 --output-dir results --export-json results/summary.json
```

After running you will find:

- `summary.csv` – aggregated metrics per strategy and run.
- `passengers.csv` – passenger-level records for downstream analysis (e.g., plotting distributions).
- `elevators.csv` – per-elevator utilisation and energy summaries.
- `summary.json` – the raw structured output (optional).

## Configuration Reference

Simulation behaviour is governed by `SimulationConfig` (see `src/elevator_sim/config.py`). Core parameters include:

- `num_floors`, `num_elevators`: building topology.
- `duration_s`, `warmup_s`: total runtime and warmup period to discard initial transients.
- `elevator`: nested settings for capacity, travel time per floor, door timing, boarding time, energy model, and optional idle parking floors.
- `arrivals`: a list of time windows describing per-floor arrival rates for upward and downward passengers (rates expressed as passengers per minute).
- `random_seed`: ensures reproducible stochastic behaviour.

The provided `configs/highrise_commuter.json` showcases a three-phase workday profile (morning up-peak, midday balance, evening down-peak) across 20 floors and four elevators.

## Output Data

Each passenger entry includes request/board/exit timestamps, wait and travel durations, assigned elevator, and completion status. The summary table reports:

- Average, median, and 90th percentile wait times.
- Average travel and total system times.
- Gini coefficient of wait-time distribution as a fairness indicator.
- Throughput (passengers per simulated second).
- Total passengers served and unfinished riders.
- Estimated total energy use per strategy.

Per-elevator telemetry records distance travelled, number of stops, energy consumption, and passengers moved, enabling additional analyses such as workload balancing.

## Testing

Run the automated test suite to verify installation integrity:

```bash
pytest
```

The tests exercise the metric aggregation logic and execute short simulations for both bundled strategies to ensure they complete without errors.

## Extending the Simulator

- Add new dispatch strategies by subclassing `Strategy` (see `src/elevator_sim/strategy/base.py`) and plugging the implementation into `build_strategy` in `src/elevator_sim/simulation.py`.
- Modify passenger arrival behaviour by constructing new `PassengerArrivalConfig` sequences or replacing `PassengerArrivalProcess`.
- Integrate additional metrics by extending `compute_metrics` or augmenting the CLI exporters.

With these building blocks you can craft custom experiments, generate figures, and support a detailed technical report comparing elevator operation strategies under diverse conditions.
