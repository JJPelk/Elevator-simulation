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

        result = compute_metrics(passengers, duration_s=100)
        self.assertAlmostEqual(result.average_wait, 5.0)
        self.assertAlmostEqual(result.average_travel, 15.0)
        self.assertAlmostEqual(result.throughput, len(passengers) / 100)
        self.assertEqual(result.unfinished_passengers, 0)

    def test_handles_unfinished(self):
        completed = Passenger(1, 0, 3, 0, 1)
        completed.record_board(4)
        completed.record_exit(10)
        unfinished = Passenger(2, 1, 4, 20, 1)
        passengers = [completed, unfinished]
        result = compute_metrics(passengers, duration_s=50)
        self.assertEqual(result.total_passengers, 1)
        self.assertEqual(result.unfinished_passengers, 1)


if __name__ == "__main__":
    unittest.main()
