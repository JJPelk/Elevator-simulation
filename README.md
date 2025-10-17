# Elevator Simulation Platform

This repository contains a configurable elevator simulation engine designed to generate rich datasets for analysing competing dispatch strategies. It supports multiple elevator control policies, flexible passenger arrival schedules, per-elevator telemetry, and summary statistics that can be fed directly into a technical report.

## Key Features

- **Discrete-time simulation core** with per-second resolution, configurable elevator dynamics, and stochastic passenger arrivals.
- **Four dispatch strategies** ready for comparison:
  - `collective_control`: a nearest-car collective control algorithm that serves hall calls while respecting travel direction.
  - `destination_dispatch`: a destination-grouping controller that forms elevator assignments based on passenger destinations.
  - `zoned_dispatch`: dedicates elevators to building zones while sharing overloads to study fairness across high-rise stacks.
  - `energy_saver`: batches passengers to reduce empty travel and quantify energy-saving behaviour.
- **Comprehensive metrics** including averages, medians, and extreme wait statistics, fairness (Gini and completion ratio), energy-per-passenger, occupancy and mode-time fractions, and empty-trip ratios for energy analysis.
- **Arrival window + burst modelling** allowing both Poisson arrivals and scheduled crowd events for lunch rushes, conferences, or evacuation drills.
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
│       ├── destination_dispatch.py
│       ├── energy_saver.py
│       └── zoned.py
└── tests/                     # Unit and integration tests
```

## Installation

The project targets Python 3.10 or newer. Create a virtual environment and install the package in editable mode if you plan to extend it:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development extras (e.g., pytest) install the `dev` optional dependency:

```bash
pip install -e .[dev]
```

## Running Simulations

Use the CLI to execute batch experiments. The command below runs all bundled strategies against the `highrise_commuter` scenario, repeating each three times and writing CSV outputs into `results/`:

```bash
python scripts/run_simulation.py \
  --config configs/highrise_commuter.json \
  --runs-per-strategy 3 \
  --output-dir results \
  --export-json results/summary.json
```

After running you will find:

- `summary.csv` – aggregated metrics per strategy and run (wait-time distribution, fairness, energy intensity, utilisation fractions, etc.).
- `passengers.csv` – passenger-level records for downstream analysis (e.g., plotting distributions).
- `elevators.csv` – per-elevator utilisation and energy summaries including distance splits, idle/moving/boarding time, and occupancy-hours.
- `summary.json` – the raw structured output (optional).

## Configuration Reference

Simulation behaviour is governed by `SimulationConfig` (see `src/elevator_sim/config.py`). Core parameters include:

- `num_floors`, `num_elevators`: building topology.
- `duration_s`, `warmup_s`: total runtime and warmup period to discard initial transients.
- `elevator`: nested settings for capacity, travel time per floor, door timing, boarding time, energy model, and optional idle parking floors.
- `arrivals`: a list of time windows describing per-floor arrival rates for upward and downward passengers (rates expressed as passengers per minute) plus optional `events` for scripted bursts.
- `random_seed`: ensures reproducible stochastic behaviour.

The provided `configs/highrise_commuter.json` showcases a three-phase workday profile (morning up-peak, midday balance, evening down-peak) across 20 floors and four elevators.

## Output Data

Each passenger entry includes request/board/exit timestamps, wait and travel durations, assigned elevator, completion status, and whether the rider came from a scripted event. The summary table reports:

- Average, median, 90th percentile, maximum, and standard deviation of wait times.
- Average and median travel times plus variability statistics.
- Total system time, throughput (passengers per simulated second), and completion ratio.
- Fairness and equity metrics (Gini coefficient, unfinished passengers).
- Energy and efficiency metrics (total energy, per-passenger energy and distance, empty-trip fraction).
- Utilisation breakdowns (average occupancy and the fraction of time elevators spend idle, moving, or boarding).

Per-elevator telemetry records gross/operational distance, empty distance, energy consumption, time-in-mode breakdowns, and passengers moved—ideal for workload-balancing or energy-intensity studies.

### Arrival Events

In addition to Poisson arrivals, you can schedule deterministic bursts using the `events` array within `PassengerArrivalConfig`. Each event specifies `time_s`, `floor`, `direction`, `count`, and optional `destinations`. This enables scenarios such as fire drills, conference dismissals, or class changes. Event passengers are tagged in the passenger export (`event` column) for easy post-processing.

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
