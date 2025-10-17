import unittest

from elevator_sim.metrics import compute_metrics
from elevator_sim.passenger import Passenger


class MetricsTest(unittest.TestCase):
    def test_basic_metrics(self):
        passengers = []
        for idx in range(5):
            p = Passenger(
                passenger_id=idx,
                origin=0,
                destination=5,
                request_time=idx * 10,
                direction=1,
            )
            p.record_board(p.request_time + 5)
            p.record_exit(p.board_time + 15)
            passengers.append(p)

        totals = {
            "total_energy": 100.0,
            "total_distance": 50.0,
            "occupancy_time": 200.0,
            "idle_time": 40.0,
            "moving_time": 30.0,
            "boarding_time": 30.0,
            "empty_distance": 10.0,
            "num_elevators": 2,
        }
        result = compute_metrics(passengers, duration_s=100, operational_totals=totals)
        self.assertAlmostEqual(result.average_wait, 5.0)
        self.assertAlmostEqual(result.median_wait, 5.0)
        self.assertAlmostEqual(result.max_wait, 5.0)
        self.assertAlmostEqual(result.std_wait, 0.0)
        self.assertAlmostEqual(result.average_travel, 15.0)
        self.assertAlmostEqual(result.median_travel, 15.0)
        self.assertAlmostEqual(result.std_travel, 0.0)
        self.assertAlmostEqual(result.throughput, len(passengers) / 100)
        self.assertEqual(result.unfinished_passengers, 0)
        self.assertAlmostEqual(result.energy_per_passenger, 20.0)
        self.assertAlmostEqual(result.distance_per_passenger, 10.0)
        self.assertAlmostEqual(result.average_occupancy, totals["occupancy_time"] / 200.0)
        self.assertAlmostEqual(result.idle_fraction, totals["idle_time"] / 200.0)
        self.assertAlmostEqual(result.empty_trip_fraction, totals["empty_distance"] / totals["total_distance"])

    def test_handles_unfinished(self):
        completed = Passenger(1, 0, 3, 0, 1)
        completed.record_board(4)
        completed.record_exit(10)
        unfinished = Passenger(2, 1, 4, 20, 1)
        passengers = [completed, unfinished]
        result = compute_metrics(passengers, duration_s=50)
        self.assertEqual(result.total_passengers, 1)
        self.assertEqual(result.unfinished_passengers, 1)
        self.assertAlmostEqual(result.completion_ratio, 0.5)


if __name__ == "__main__":
    unittest.main()
