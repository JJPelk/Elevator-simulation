import unittest

from elevator_sim.config import ArrivalWindow, ElevatorConfig, PassengerArrivalConfig, SimulationConfig
from elevator_sim.simulation import Simulation, build_strategy


class SimulationIntegrationTest(unittest.TestCase):
    def build_config(self) -> SimulationConfig:
        windows = [
            ArrivalWindow(
                start_s=0,
                end_s=300,
                up_rate_per_minute=[0.5, 0.2, 0.1, 0.1],
                down_rate_per_minute=[0.1, 0.2, 0.3, 0.4],
            )
        ]
        arrival_cfg = PassengerArrivalConfig(windows=windows)
        return SimulationConfig(
            num_floors=4,
            num_elevators=2,
            duration_s=300,
            warmup_s=30,
            elevator=ElevatorConfig(capacity=8, seconds_per_floor=2.0, door_time_s=3.0, passenger_board_time_s=1.0),
            arrivals=arrival_cfg,
            random_seed=101,
        )

    def test_collective_strategy_runs(self):
        config = self.build_config()
        strategy = build_strategy("collective_control", config)
        simulation = Simulation(config, strategy)
        result = simulation.run()
        self.assertGreaterEqual(result.metrics.total_passengers, 0)
        self.assertEqual(result.strategy_name, "collective_control")

    def test_destination_dispatch_runs(self):
        config = self.build_config()
        strategy = build_strategy("destination_dispatch", config)
        simulation = Simulation(config, strategy)
        result = simulation.run()
        self.assertEqual(result.strategy_name, "destination_dispatch")
        self.assertGreater(len(result.passengers), 0)


if __name__ == "__main__":
    unittest.main()
